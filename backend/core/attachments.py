"""Private PNG attachments, copied into the agent's home for each reply.

The model supplies a local image to image.send. Readers only receive an opaque
ID from the recorded reply, never a path to open as root. Directory descriptors
pin each component and refuse symlinks, including intermediate directories.
"""

import os
import re
import stat
import struct
import uuid

from backend.core import paths

cDirectoryName = "attachments"
cMaxImageBytes = 50 * 1024 * 1024
cChunkBytes = 1024 * 1024
cMaxPerMessage = 16
cIdPattern = re.compile(r"[a-f0-9]{32}")
cPngSignature = b"\x89PNG\r\n\x1a\n"


def fIsValidId(pId):
  return isinstance(pId, str) and cIdPattern.fullmatch(pId) is not None


def fReadPngDimensions(pData):
  """Read PNG dimensions without decoding pixels or accepting another format."""
  if (len(pData) < 33 or pData[:8] != cPngSignature
      or pData[8:16] != b"\x00\x00\x00\rIHDR"):
    raise ValueError("Only PNG images can be attached.")
  vWidth, vHeight = struct.unpack(">II", pData[16:24])
  if not vWidth or not vHeight:
    raise ValueError("The PNG has invalid dimensions.")
  return vWidth, vHeight


def fOpenImage(pAgentId, plParts):
  """Open a regular file owned by this agent, without following any links."""
  if not plParts or any(vPart in ("", ".", "..") for vPart in plParts):
    raise ValueError("The image must be inside this agent's home.")
  vDirectory = os.open(paths.fGetAgentHome(pAgentId),
                       os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
  vFile = None
  try:
    for vPart in plParts[:-1]:
      vNext = os.open(vPart, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                      dir_fd=vDirectory)
      os.close(vDirectory)
      vDirectory = vNext
    vFile = os.open(plParts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
                    | os.O_NOCTTY, dir_fd=vDirectory)
    dStat = os.fstat(vFile)
    if (not stat.S_ISREG(dStat.st_mode)
        or dStat.st_uid not in paths.fListAllowedAgentFileOwners(pAgentId)):
      raise PermissionError("The image must be a regular file owned by this agent.")
    if not 33 <= dStat.st_size <= cMaxImageBytes:
      raise ValueError("The PNG must be no larger than 50 MiB.")
    fReadPngDimensions(os.pread(vFile, 33, 0))
    vResult = vFile
    vFile = None
    return vResult, dStat.st_size
  finally:
    if vFile is not None:
      os.close(vFile)
    os.close(vDirectory)


def fStoreImage(pAgentId, pPath, pCaption=""):
  """Snapshot a local PNG so later screenshots cannot replace an old reply."""
  vHome = os.path.abspath(paths.fGetAgentHome(pAgentId))
  vSource = os.path.abspath(os.path.join(vHome, str(pPath or "")))
  if os.path.commonpath([vHome, vSource]) != vHome:
    raise ValueError("The image must be inside this agent's home.")
  lParts = os.path.relpath(vSource, vHome).split(os.sep)
  vSourceFile, vSize = fOpenImage(pAgentId, lParts)
  vDirectory = None
  vDestination = None
  vCreated = False
  vId = uuid.uuid4().hex
  vStoredName = vId + ".png"
  try:
    vHomeFile = os.open(vHome, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
      try:
        os.mkdir(cDirectoryName, mode=0o700, dir_fd=vHomeFile)
      except FileExistsError:
        pass
      vDirectory = os.open(cDirectoryName,
                           os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                           dir_fd=vHomeFile)
    finally:
      os.close(vHomeFile)
    vDestination = os.open(vStoredName, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                           | os.O_NOFOLLOW, 0o600, dir_fd=vDirectory)
    vCreated = True
    with os.fdopen(vDestination, "wb") as vOutput:
      vDestination = None
      vRemaining = vSize
      while vRemaining:
        vChunk = os.read(vSourceFile, min(cChunkBytes, vRemaining))
        if not vChunk:
          raise ValueError("The image changed while it was being attached.")
        vOutput.write(vChunk)
        vRemaining -= len(vChunk)
      if os.read(vSourceFile, 1):
        raise ValueError("The image changed while it was being attached.")
    vWidth, vHeight = fReadPngDimensions(os.pread(vSourceFile, 33, 0))
    vName = re.sub(r"[^A-Za-z0-9._-]", "_", os.path.basename(vSource))[:128]
    if not vName.lower().endswith(".png"):
      vName += ".png"
    return {"id": vId, "name": vName, "media_type": "image/png",
            "size": vSize, "width": vWidth, "height": vHeight,
            "caption": str(pCaption or "")[:1000]}
  except Exception:
    if vDirectory is not None and vCreated:
      try:
        os.unlink(vStoredName, dir_fd=vDirectory)
      except FileNotFoundError:
        pass
    raise
  finally:
    os.close(vSourceFile)
    if vDestination is not None:
      os.close(vDestination)
    if vDirectory is not None:
      os.close(vDirectory)


def fListMessageAttachments(pMessage):
  """Select bounded, local attachment references from an untrusted chat row."""
  if not isinstance(pMessage, dict):
    return []
  lImages = pMessage.get("attachments") or []
  if not isinstance(lImages, list):
    return []
  lResult = []
  sSeen = set()
  for dImage in lImages:
    if not isinstance(dImage, dict) or not fIsValidId(dImage.get("id")):
      continue
    if dImage["id"] in sSeen:
      continue
    sSeen.add(dImage["id"])
    lResult.append(dImage)
    if len(lResult) == cMaxPerMessage:
      break
  return lResult


def fReadImageChunk(pAgentId, pId, pOffset=0):
  """Read a bounded piece of a stored PNG through the executor protocol."""
  if not fIsValidId(pId):
    raise ValueError("Invalid attachment ID.")
  if type(pOffset) is not int or not 0 <= pOffset < cMaxImageBytes:
    raise ValueError("Invalid attachment offset.")
  vFile, vSize = fOpenImage(pAgentId, [cDirectoryName, pId + ".png"])
  try:
    if pOffset >= vSize:
      raise ValueError("Invalid attachment offset.")
    vLength = min(cChunkBytes, vSize - pOffset)
    vData = os.pread(vFile, vLength, pOffset)
    if len(vData) != vLength:
      raise ValueError("The attachment changed while it was being read.")
    return vData, vSize
  finally:
    os.close(vFile)
