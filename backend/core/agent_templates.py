"""Agent templates, read from the templates repository.

    https://github.com/nipegun/bunch-of-aigents-templates
      rag-consultant/agent.json
      rag-consultant/system-prompt.md
      site-watcher/...

The examples used to ship inside this repository, one Markdown file each. They
live in a repository of their own now: a new template reaches every
installation without an update of the application, and an installation can be
pointed at a fork or at a repository of its own under Settings -> Agents.

Each folder of the repository is one template, in the same package layout an
exported agent has (agent_package): installing a template and importing a .zip
are the same code.

The repository is downloaded as the one .tar.gz a branch is served as - the
address the installer downloads the application from - so listing the
templates is one request, with no API and no rate limit. A file:// address
works as it does for the installer, for a machine with no way out to GitHub:
<path>/archive/refs/heads/<branch>.tar.gz.

These are STARTING POINTS, not products. Every one of them is created disabled
and with no model unless it names one, because the user has to choose a
provider first.
"""

import re
import time
from urllib.parse import urlparse
import urllib.request

from backend.core import agent_package
from backend.core import db

cDefaultRepositoryUrl = "https://github.com/nipegun/bunch-of-aigents-templates"
cDefaultBranch = "main"
cSettingUrl = "templates_repo_url"
cSettingBranch = "templates_repo_branch"

cBranchPattern = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,99}$")
cMaxArchiveBytes = 64 * 1024 * 1024
cTimeoutSeconds = 20
# How long a downloaded repository is reused. Short: somebody who has just
# pushed a template should see it after a coffee, not after a restart.
cCacheSeconds = 300

dCache = {}


class TemplatesUnavailable(ValueError):
  """The repository could not be reached or read. The message says which."""


def fValidateRepositoryUrl(pUrl):
  """An https:// or file:// address with no spaces, or ValueError."""
  vUrl = str(pUrl or "").strip().rstrip("/")
  dUrl = urlparse(vUrl)
  if (len(vUrl) > 300 or re.search(r"\s", vUrl) or dUrl.query or dUrl.fragment
      or not ((dUrl.scheme == "https" and dUrl.netloc) or
              (dUrl.scheme == "file" and not dUrl.netloc and dUrl.path.startswith("/")))):
    raise ValueError("The templates repository must be an https:// or file:// address: %r"
                     % (str(pUrl)[:80],))
  return vUrl


def fValidateBranch(pBranch):
  vBranch = str(pBranch or "").strip()
  if not cBranchPattern.match(vBranch) or ".." in vBranch:
    raise ValueError("Invalid branch name: %r" % (vBranch[:80],))
  return vBranch


def fReadRepositorySettings():
  """(url, branch) from the settings, or the defaults when there are none."""
  dStored = {}
  try:
    vConnection = db.fOpenAppDb()
    try:
      dStored = dict(vConnection.execute(
        "SELECT key, value FROM settings WHERE key IN (?, ?)", (cSettingUrl, cSettingBranch)))
    finally:
      vConnection.close()
  except Exception:
    dStored = {}
  try:
    vUrl = fValidateRepositoryUrl(dStored.get(cSettingUrl) or cDefaultRepositoryUrl)
    vBranch = fValidateBranch(dStored.get(cSettingBranch) or cDefaultBranch)
  except ValueError:
    vUrl, vBranch = cDefaultRepositoryUrl, cDefaultBranch
  return vUrl, vBranch


def fArchiveUrl(pUrl, pBranch):
  return "%s/archive/refs/heads/%s.tar.gz" % (pUrl.rstrip("/"), pBranch)


def fDownloadArchive(pUrl):
  """The bytes of a repository archive, at most cMaxArchiveBytes of them."""
  dUrl = urlparse(pUrl)
  try:
    if dUrl.scheme == "file":
      with open(dUrl.path, "rb") as vFile:
        vData = vFile.read(cMaxArchiveBytes + 1)
    else:
      vRequest = urllib.request.Request(pUrl, headers={"User-Agent": "bunch-of-aigents"})
      with urllib.request.urlopen(vRequest, timeout=cTimeoutSeconds) as vResponse:
        vData = vResponse.read(cMaxArchiveBytes + 1)
  except (OSError, ValueError) as vError:
    raise TemplatesUnavailable("Could not download the templates from %s: %s" % (pUrl, vError))
  if len(vData) > cMaxArchiveBytes:
    raise TemplatesUnavailable("The templates repository is larger than %d MiB." % (cMaxArchiveBytes // 1024 ** 2,))
  return vData


def fLoadTemplates(pRefresh=False):
  """{template id: package source} for the configured repository."""
  vUrl, vBranch = fReadRepositorySettings()
  vKey = (vUrl, vBranch)
  dEntry = dCache.get(vKey)
  if dEntry and not pRefresh and time.monotonic() - dEntry[0] < cCacheSeconds:
    return dEntry[1]
  try:
    dSources = agent_package.fReadRepositoryArchive(fDownloadArchive(fArchiveUrl(vUrl, vBranch)))
  except agent_package.PackageError as vError:
    raise TemplatesUnavailable(str(vError))
  except (OSError, EOFError) as vError:
    raise TemplatesUnavailable("The templates repository archive could not be read: %s" % (vError,))
  dCache.clear()
  dCache[vKey] = (time.monotonic(), dSources)
  return dSources


def fListTemplates(pInstalledTools, pLanguage="", pRefresh=False):
  """Every template, summarised, ordered by the name the user sees.

  A template that does not pass the checks is listed with its error instead of
  being hidden: whoever wrote it needs to see why it is not offered.
  """
  lTemplates = []
  for vId, vSource in fLoadTemplates(pRefresh).items():
    try:
      dPackage = agent_package.fReadPackage(vSource, pInstalledTools)
    except agent_package.PackageError as vError:
      lTemplates.append({"id": vId, "name": vId, "error": str(vError)})
      continue
    lTemplates.append({"id": vId, **agent_package.fSummarise(dPackage, pLanguage)})
  return sorted(lTemplates, key=lambda dTemplate: dTemplate["name"].lower())


def fReadTemplate(pId, pInstalledTools):
  """(source, package) for one template, or None when there is no such one."""
  if not agent_package.fIsTemplateId(pId):
    return None
  vSource = fLoadTemplates().get(pId)
  if vSource is None:
    return None
  return vSource, agent_package.fReadPackage(vSource, pInstalledTools)
