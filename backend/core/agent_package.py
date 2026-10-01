"""The portable form of an agent: an exported .zip, or a template folder.

    agent.json          what the agent is: name, description, tools, limits...
    system-prompt.md    its system prompt, as written
    memory.md           optional: its memory
    home/...            optional: files from its home directory
    rag/documents.json  optional: its library documents and their information
    rag/files/...       the originals listed there

One layout for all of them, so that installing a template from the templates
repository and importing a .zip somebody exported are the same code: a
template is simply a package that carries no memory, home or library.

Everything is checked here, before an agent exists: an import that fails
half-way leaves an agent nobody asked for. What cannot be checked here -
whether a tool or a skill is installed on this server - is reported, and the
agent is created without it rather than refused.

A package never carries what belongs to one installation and not to the agent:
API keys, the agent's own token, channel credentials, the Samba password,
which channels it listens on, its chat or its run journal. There is nowhere in
the format to put them.
"""

import io
import json
import os
import posixpath
import re
import stat
import tarfile
import zipfile

from backend.core import agent_home
from backend.core import agents
from backend.core import memory
from backend.core import paths
from backend.core import rag_settings
from backend.core import rag_store
from backend.core import skills

cFormatVersion = 1
cManifestName = "agent.json"
cPromptName = "system-prompt.md"
cMemoryName = "memory.md"
cHomePrefix = "home/"
cRagIndexName = "rag/documents.json"
cRagFilesPrefix = "rag/files/"

cMaxManifestBytes = 256 * 1024
cMaxPromptBytes = 1024 * 1024
cMaxDescriptionCharacters = 2000
cMaxRagDocuments = 2000
# What a whole package may unpack to. An agent's library may be allowed far
# more (rag_settings), but a package this size is already a backup, and the
# installation has --backup for that.
cMaxPackageBytes = 8 * 1024 ** 3
# Beyond this ratio a member is treated as a compression bomb. Text compresses
# well, but not a thousand to one.
cMaxCompressionRatio = 200

lManifestKeys = ["format", "name", "description", "tools", "skills", "schedules",
                 "limits", "rag", "kanban_enabled", "provider", "fallback_provider",
                 "exported_at"]
cToolNamePattern = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
cLanguagePattern = re.compile(r"^[a-z]{2}-[A-Z]{2}$")
# Files a template folder may hold for the people reading the repository.
cReadmePattern = re.compile(r"^README(\.[A-Za-z-]+)?\.md$")
# A template is named by its folder in the repository, and the name reaches
# the server from a URL: a plain name or nothing, like a theme's.
cTemplateIdPattern = re.compile(r"^[a-z][a-z0-9-]{0,39}$")


class PackageError(ValueError):
  """A package that cannot be installed, with the reason in the message."""


# ------------------------------------------------------------------ sources --
#
# A source is where the files of one package are: fNames() lists them relative
# to the package root, fSize() and fRead() give their size and bytes, and
# fChunks() streams one without loading it.

class ZipSource:
  """A .zip on disk. The package may be at its root or in one folder."""

  def __init__(self, pPath):
    self.vZip = zipfile.ZipFile(pPath)
    lInfos = [vInfo for vInfo in self.vZip.infolist() if not vInfo.is_dir()]
    vTotal = 0
    for vInfo in lInfos:
      fCheckMemberName(vInfo.filename)
      if vInfo.flag_bits & 0x1:
        raise PackageError("The .zip is encrypted: %s" % (vInfo.filename,))
      if stat.S_ISLNK(vInfo.external_attr >> 16):
        raise PackageError("The .zip contains a link: %s" % (vInfo.filename,))
      if (vInfo.file_size > 1024 * 1024 and
          vInfo.file_size > cMaxCompressionRatio * max(1, vInfo.compress_size)):
        raise PackageError("The .zip member %s expands too much to be trusted." % (vInfo.filename,))
      vTotal += vInfo.file_size
    if vTotal > cMaxPackageBytes:
      raise PackageError("The package unpacks to more than %d GiB." % (cMaxPackageBytes // 1024 ** 3,))
    vPrefix = fFindRoot([vInfo.filename for vInfo in lInfos])
    self.dInfos = {vInfo.filename[len(vPrefix):]: vInfo for vInfo in lInfos}

  def fNames(self):
    return list(self.dInfos)

  def fSize(self, pName):
    return self.dInfos[pName].file_size

  def fMode(self, pName):
    return (self.dInfos[pName].external_attr >> 16) & 0o777

  def fChunks(self, pName, pChunkBytes=1024 * 1024):
    vInfo = self.dInfos[pName]
    vRead = 0
    with self.vZip.open(vInfo) as vFile:
      while True:
        vData = vFile.read(pChunkBytes)
        if not vData:
          break
        vRead += len(vData)
        if vRead > vInfo.file_size:
          raise PackageError("The .zip member %s is larger than it says." % (pName,))
        yield vData

  def fRead(self, pName, pLimit):
    if self.fSize(pName) > pLimit:
      raise PackageError("%s is larger than %d bytes." % (pName, pLimit))
    return b"".join(self.fChunks(pName))

  def fClose(self):
    self.vZip.close()


class TarFolderSource:
  """One folder of a repository archive already read into memory."""

  def __init__(self, pFiles):
    # {relative name: (bytes, mode)}, built by fReadRepositoryArchive.
    self.dFiles = pFiles

  def fNames(self):
    return list(self.dFiles)

  def fSize(self, pName):
    return len(self.dFiles[pName][0])

  def fMode(self, pName):
    return self.dFiles[pName][1]

  def fChunks(self, pName, pChunkBytes=1024 * 1024):
    vData = self.dFiles[pName][0]
    for vOffset in range(0, len(vData), pChunkBytes):
      yield vData[vOffset:vOffset + pChunkBytes]

  def fRead(self, pName, pLimit):
    if self.fSize(pName) > pLimit:
      raise PackageError("%s is larger than %d bytes." % (pName, pLimit))
    return self.dFiles[pName][0]

  def fClose(self):
    pass


class DirSource:
  """A template folder on disk, as in a checkout of the templates repository.

  Links are skipped, not followed, the way a repository archive's are.
  """

  def __init__(self, pPath):
    self.vRoot = str(pPath)
    self.dFiles = {}
    for vDirectory, lDirectories, lNames in os.walk(self.vRoot):
      lDirectories[:] = [v for v in lDirectories if not os.path.islink(os.path.join(vDirectory, v))]
      for vName in lNames:
        vPath = os.path.join(vDirectory, vName)
        if os.path.islink(vPath) or not os.path.isfile(vPath):
          continue
        self.dFiles[os.path.relpath(vPath, self.vRoot).replace(os.sep, "/")] = vPath

  def fNames(self):
    return list(self.dFiles)

  def fSize(self, pName):
    return os.path.getsize(self.dFiles[pName])

  def fMode(self, pName):
    return os.stat(self.dFiles[pName]).st_mode & 0o777

  def fChunks(self, pName, pChunkBytes=1024 * 1024):
    with open(self.dFiles[pName], "rb") as vFile:
      while True:
        vData = vFile.read(pChunkBytes)
        if not vData:
          break
        yield vData

  def fRead(self, pName, pLimit):
    if self.fSize(pName) > pLimit:
      raise PackageError("%s is larger than %d bytes." % (pName, pLimit))
    with open(self.dFiles[pName], "rb") as vFile:
      return vFile.read()

  def fClose(self):
    pass


def fCheckMemberName(pName):
  """Refuse a member name that could land outside the package."""
  vName = str(pName)
  if (not vName or vName.startswith("/") or "\\" in vName or "\x00" in vName
      or any(vPart == ".." for vPart in vName.split("/"))):
    raise PackageError("Unsafe file name in the package: %r" % (vName[:120],))


def fFindRoot(pNames):
  """"" when agent.json is at the top, "<folder>/" when all is in one folder."""
  if cManifestName in pNames:
    return ""
  sTops = {vName.split("/", 1)[0] for vName in pNames}
  if len(sTops) == 1 and all("/" in vName for vName in pNames):
    vPrefix = next(iter(sTops)) + "/"
    if vPrefix + cManifestName in pNames:
      return vPrefix
  raise PackageError("The package has no agent.json at its top.")


def fIsTemplateId(pName):
  """Whether a repository folder name can be a template id."""
  return bool(cTemplateIdPattern.match(str(pName or "")))


def fReadRepositoryArchive(pData, pMaxBytes=64 * 1024 * 1024):
  """Split a repository .tar.gz into {template id: TarFolderSource}.

  The archive GitHub serves has one top folder, <repository>-<branch>; each
  folder inside it that holds an agent.json is a template, named by its folder.
  Only regular files are kept: a link in a repository archive is skipped, not
  followed.
  """
  dFolders = {}
  vTotal = 0
  with tarfile.open(fileobj=io.BytesIO(pData), mode="r:gz") as vTar:
    for vMember in vTar:
      if not vMember.isreg():
        continue
      fCheckMemberName(vMember.name)
      lParts = vMember.name.split("/")
      if len(lParts) < 3 or not fIsTemplateId(lParts[1]):
        continue
      vTotal += vMember.size
      if vTotal > pMaxBytes:
        raise PackageError("The templates repository is larger than %d MiB." % (pMaxBytes // 1024 ** 2,))
      vFile = vTar.extractfile(vMember)
      dFolders.setdefault(lParts[1], {})["/".join(lParts[2:])] = (vFile.read(), vMember.mode & 0o777)
  return {vId: TarFolderSource(dFiles) for vId, dFiles in dFolders.items() if cManifestName in dFiles}



# --------------------------------------------------------------- validation --

def fText(pSource, pName, pLimit):
  try:
    return pSource.fRead(pName, pLimit).decode("utf-8")
  except UnicodeDecodeError:
    raise PackageError("%s is not UTF-8 text." % (pName,))


def fValidateDescription(pDescription):
  """Always a {language: text} dictionary; a single text is kept under ""."""
  if pDescription is None:
    return {}
  if isinstance(pDescription, str):
    pDescription = {"": pDescription}
  if not isinstance(pDescription, dict):
    raise PackageError("description must be a text or an object of texts by language.")
  dDescription = {}
  for vLanguage, vText in pDescription.items():
    if vLanguage and not cLanguagePattern.match(str(vLanguage)):
      raise PackageError("Invalid description language: %r" % (vLanguage,))
    if not isinstance(vText, str) or len(vText) > cMaxDescriptionCharacters:
      raise PackageError("Each description must be a text of at most %d characters." % (cMaxDescriptionCharacters,))
    dDescription[str(vLanguage)] = vText.strip()
  return dDescription


def fPickDescription(pDescription, pLanguage):
  """The description in pLanguage, else en-US, else whatever there is."""
  dDescription = pDescription or {}
  for vLanguage in (pLanguage, "en-US", ""):
    if dDescription.get(vLanguage):
      return dDescription[vLanguage]
  return next((vText for vText in dDescription.values() if vText), "")


def fValidateProviderEntry(pValue, pKey, pRequireName):
  if pValue is None:
    return None
  if not isinstance(pValue, dict) or set(pValue) - {"name", "model", "base_url"}:
    raise PackageError("%s must be an object with name, model and base_url." % (pKey,))
  vName = str(pValue.get("name") or "").strip()
  if vName or pRequireName:
    try:
      vName = agents.fValidateProvider(vName)
    except ValueError as vError:
      raise PackageError("%s: %s" % (pKey, vError))
  vModel = str(pValue.get("model") or "")
  vBaseUrl = str(pValue.get("base_url") or "")
  if len(vModel) > 200 or len(vBaseUrl) > 500 or (vBaseUrl and not re.match(r"^https?://", vBaseUrl)):
    raise PackageError("%s has an invalid model or base_url." % (pKey,))
  return {"name": vName, "model": vModel, "base_url": vBaseUrl}


def fValidateManifest(pManifest, pInstalledTools):
  """Check agent.json and return it normalised, with what will be dropped."""
  if not isinstance(pManifest, dict):
    raise PackageError("agent.json must be a JSON object.")
  lUnknown = sorted(set(pManifest) - set(lManifestKeys))
  if lUnknown:
    raise PackageError("agent.json has keys this version does not know: %s" % (", ".join(lUnknown),))
  if pManifest.get("format") != cFormatVersion:
    raise PackageError("This package is format %r; this installation reads format %d."
                       % (pManifest.get("format"), cFormatVersion))
  try:
    vName = agents.fValidateAgentName(pManifest.get("name"))
  except ValueError as vError:
    raise PackageError(str(vError))

  lTools = pManifest.get("tools", [])
  if not isinstance(lTools, list) or len(lTools) > 200 or not all(
      isinstance(vTool, str) and cToolNamePattern.match(vTool) for vTool in lTools):
    raise PackageError("tools must be a list of tool names such as \"web.fetch\".")
  lTools = list(dict.fromkeys(lTools))
  lSkills = pManifest.get("skills", [])
  if not isinstance(lSkills, list) or len(lSkills) > 200 or not all(
      isinstance(vSkill, str) and skills.fIsValidSkillName(vSkill) for vSkill in lSkills):
    raise PackageError("skills must be a list of skill names.")
  lSchedules = pManifest.get("schedules", [])
  if not isinstance(lSchedules, list) or len(lSchedules) > 20:
    raise PackageError("schedules must be a list of at most 20 cron schedules.")
  try:
    lSchedules = [agents.fValidateSchedule(vSchedule) for vSchedule in lSchedules]
  except ValueError as vError:
    raise PackageError(str(vError))

  dLimits = pManifest.get("limits", {})
  if not isinstance(dLimits, dict) or set(dLimits) - set(agents.dDefaultLimits):
    raise PackageError("limits may only hold: %s" % (", ".join(agents.dDefaultLimits),))
  for vKey, vValue in dLimits.items():
    if type(vValue) is not int or vValue <= 0:
      raise PackageError("Limit %s must be a whole number greater than zero." % (vKey,))
  if "max_memory_characters" in dLimits:
    try:
      memory.fValidateLimit(dLimits["max_memory_characters"])
    except ValueError as vError:
      raise PackageError(str(vError))

  dRag = None
  if pManifest.get("rag") is not None:
    try:
      dRag = rag_settings.fValidateSettings(pManifest["rag"])
    except (ValueError, TypeError) as vError:
      raise PackageError("rag: %s" % (vError,))
  vKanban = pManifest.get("kanban_enabled", True)
  if type(vKanban) is not bool:
    raise PackageError("kanban_enabled must be true or false.")
  vExportedAt = pManifest.get("exported_at", "")
  if not isinstance(vExportedAt, str) or len(vExportedAt) > 64:
    raise PackageError("exported_at must be a short text.")

  sInstalled = set(pInstalledTools)
  return {
    "name": vName,
    "description": fValidateDescription(pManifest.get("description")),
    "tools": [vTool for vTool in lTools if vTool in sInstalled],
    "missing_tools": [vTool for vTool in lTools if vTool not in sInstalled],
    "skills": list(dict.fromkeys(lSkills)),
    "schedules": lSchedules,
    "limits": dLimits,
    "rag": dRag,
    "kanban_enabled": vKanban,
    "provider": fValidateProviderEntry(pManifest.get("provider"), "provider", True),
    "fallback_provider": fValidateProviderEntry(pManifest.get("fallback_provider"), "fallback_provider", False),
    "exported_at": vExportedAt,
  }


def fValidateRagIndex(pSource, pIndex):
  """The library documents a package carries, checked against its files."""
  if not isinstance(pIndex, list) or len(pIndex) > cMaxRagDocuments:
    raise PackageError("rag/documents.json must be a list of at most %d documents." % (cMaxRagDocuments,))
  sNames = set(pSource.fNames())
  lDocuments = []
  for dEntry in pIndex:
    if not isinstance(dEntry, dict) or set(dEntry) - {"file", "name", "metadata"}:
      raise PackageError("Each document in rag/documents.json needs file, name and metadata.")
    vFile = str(dEntry.get("file") or "")
    if not vFile.startswith(cRagFilesPrefix) or vFile not in sNames:
      raise PackageError("rag/documents.json names a file the package does not have: %r" % (vFile[:120],))
    vName = str(dEntry.get("name") or "").replace("\\", "/").split("/")[-1][:240]
    if posixpath.splitext(vName)[1].lower() not in rag_settings.cFormats:
      raise PackageError("%s is not a PDF, EPUB, TXT or Markdown document." % (vName or vFile,))
    dMetadata = dEntry.get("metadata") or {}
    if not isinstance(dMetadata, dict) or set(dMetadata) - set(rag_store.lMetadataKeys):
      raise PackageError("Invalid document information for %s." % (vName,))
    for vKey, vValue in dMetadata.items():
      if not isinstance(vValue, str) or len(vValue) > 500:
        raise PackageError("Invalid document information for %s." % (vName,))
      if vKey == "year" and vValue.strip() and not re.fullmatch(r"[0-9]{1,4}", vValue.strip()):
        raise PackageError("The publication year of %s must be up to four digits." % (vName,))
    lDocuments.append({"file": vFile, "name": vName, "size": pSource.fSize(vFile), "metadata": dMetadata})
  return lDocuments


def fReadPackage(pSource, pInstalledTools):
  """Validate a whole package. Returns a dictionary describing it.

  Raises PackageError with a sentence a person can act on.
  """
  lNames = pSource.fNames()
  for vName in lNames:
    fCheckMemberName(vName)
    if vName in (cManifestName, cPromptName, cMemoryName, cRagIndexName):
      continue
    if vName.startswith(cHomePrefix):
      try:
        agent_home.fValidatePath(vName[len(cHomePrefix):])
      except ValueError as vError:
        raise PackageError(str(vError))
      continue
    if vName.startswith(cRagFilesPrefix) or cReadmePattern.match(vName):
      continue
    raise PackageError("The package has a file this format does not know: %s" % (vName,))
  if cPromptName not in lNames:
    raise PackageError("The package has no system-prompt.md.")

  try:
    dManifest = json.loads(fText(pSource, cManifestName, cMaxManifestBytes))
  except json.JSONDecodeError as vError:
    raise PackageError("agent.json is not valid JSON: %s" % (vError,))
  dPackage = fValidateManifest(dManifest, pInstalledTools)

  vPrompt = fText(pSource, cPromptName, cMaxPromptBytes)
  if not vPrompt.strip():
    raise PackageError("system-prompt.md is empty.")
  dPackage["system_prompt"] = vPrompt

  dPackage["memory"] = None
  if cMemoryName in lNames:
    vMemory = fText(pSource, cMemoryName, paths.cMaxMemoryBytes)
    vLimit = dPackage["limits"].get("max_memory_characters", agents.dDefaultLimits["max_memory_characters"])
    try:
      memory.fValidateContent(vMemory, vLimit)
    except ValueError as vError:
      raise PackageError("memory.md: %s" % (vError,))
    dPackage["memory"] = vMemory

  dPackage["home"] = [{"path": vName[len(cHomePrefix):], "member": vName,
                       "size": pSource.fSize(vName), "mode": pSource.fMode(vName)}
                      for vName in sorted(lNames) if vName.startswith(cHomePrefix)]
  if len(dPackage["home"]) > agent_home.cMaxFiles:
    raise PackageError("The package carries more than %d home files." % (agent_home.cMaxFiles,))

  dPackage["rag_documents"] = []
  if cRagIndexName in lNames:
    try:
      lIndex = json.loads(fText(pSource, cRagIndexName, cMaxManifestBytes * 16))
    except json.JSONDecodeError as vError:
      raise PackageError("rag/documents.json is not valid JSON: %s" % (vError,))
    dPackage["rag_documents"] = fValidateRagIndex(pSource, lIndex)
  # Checked now rather than found out half-way through the upload: the
  # library refuses a file or a total beyond the limits the package brings.
  dRagLimits = dPackage["rag"] or rag_settings.fValidateSettings({})
  for dDocument in dPackage["rag_documents"]:
    if dDocument["size"] > dRagLimits["max_file_mb"] * 1024 * 1024:
      raise PackageError("%s is larger than the library's file limit of %d MiB."
                         % (dDocument["name"], dRagLimits["max_file_mb"]))
  if sum(dDocument["size"] for dDocument in dPackage["rag_documents"]) > dRagLimits["max_storage_mb"] * 1024 * 1024:
    raise PackageError("The documents exceed the library's storage limit of %d MiB."
                       % (dRagLimits["max_storage_mb"],))
  sListed = {dDocument["file"] for dDocument in dPackage["rag_documents"]}
  lStray = [vName for vName in lNames if vName.startswith(cRagFilesPrefix) and vName not in sListed]
  if lStray:
    raise PackageError("rag/files holds documents rag/documents.json does not list: %s" % (lStray[0],))
  return dPackage


def fSummarise(pPackage, pLanguage=""):
  """What the interface shows before anything is installed."""
  return {
    "name": pPackage["name"],
    "description": fPickDescription(pPackage["description"], pLanguage),
    "descriptions": pPackage["description"],
    "tools": pPackage["tools"],
    "missing_tools": pPackage["missing_tools"],
    "skills": pPackage["skills"],
    "schedules": pPackage["schedules"],
    "rag_enabled": bool(pPackage["rag"] and pPackage["rag"].get("enabled")),
    "provider": pPackage["provider"],
    "memory": pPackage["memory"] is not None,
    "home_files": len(pPackage["home"]),
    "home_bytes": sum(dFile["size"] for dFile in pPackage["home"]),
    "rag_documents": len(pPackage["rag_documents"]),
    "rag_bytes": sum(dDocument["size"] for dDocument in pPackage["rag_documents"]),
  }
