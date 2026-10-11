"""How many entries a .zip holds, counted before zipfile reads them.

zipfile.ZipFile reads the whole central directory when it is constructed and
builds one ZipInfo object for every entry in it, so a limit checked on
infolist() afterwards is a limit checked after the memory is spent. A .zip of
a few MiB made of empty entries is millions of objects.

This finds the directory with zipfile's own reader of the end records
(_EndRecData, the function ZipFile calls), refuses a directory larger than
the caller allows, and walks it the way ZipFile does, record by record,
counting without keeping anything. Finding it with the same function matters:
a second reader of ZIP64 records could be told one size while ZipFile is told
another. When this says yes, the ZipFile built next on the same file creates
at most the entries counted here.
"""

import struct
import zipfile

cEntrySignature = b"PK\x01\x02"
cEntryBytes = 46
# What one entry of a real archive takes in the directory: 46 fixed bytes, a
# name and a few extra fields. Generous on purpose; it only bounds how much is
# read before the entries are counted.
cMaxBytesPerEntry = 2048


class ZipLimitError(ValueError):
  """A .zip whose directory is larger than the caller accepts, or unreadable."""


def fCheckCentralDirectory(pFile, pMaxEntries):
  """Raise ZipLimitError unless the .zip has at most pMaxEntries entries.

  pFile is a binary file open at any position; it is left at its start, as
  ZipFile expects it.
  """
  try:
    lEnd = zipfile._EndRecData(pFile)
  except OSError as vError:
    raise ZipLimitError("This is not a .zip that can be read.") from vError
  except zipfile.BadZipFile as vError:
    raise ZipLimitError("This is not a .zip that can be read: %s" % (vError,)) from vError
  if not lEnd:
    raise ZipLimitError("This is not a .zip that can be read.")
  vSize = lEnd[zipfile._ECD_SIZE]
  vDeclared = lEnd[zipfile._ECD_ENTRIES_TOTAL]
  # ZipFile starts the directory at offset + concat, and concat is the end
  # record's location minus size minus offset: the location minus the size.
  vStart = lEnd[zipfile._ECD_LOCATION] - vSize
  if vDeclared > pMaxEntries or vSize > pMaxEntries * cMaxBytesPerEntry:
    raise ZipLimitError("The .zip holds more than %d entries." % (pMaxEntries,))
  if vStart < 0:
    raise ZipLimitError("The .zip directory is larger than the file.")
  pFile.seek(vStart)
  vDirectory = pFile.read(vSize)
  # The same walk as ZipFile's: it trusts the directory size, not the count,
  # so the count that matters is the number of records in those bytes.
  vOffset = 0
  vCount = 0
  while vOffset < vSize:
    if (len(vDirectory) - vOffset < cEntryBytes
        or vDirectory[vOffset:vOffset + 4] != cEntrySignature):
      raise ZipLimitError("The .zip directory is damaged.")
    vNameBytes, vExtraBytes, vCommentBytes = struct.unpack_from("<3H", vDirectory, vOffset + 28)
    vOffset += cEntryBytes + vNameBytes + vExtraBytes + vCommentBytes
    vCount += 1
    if vCount > pMaxEntries:
      raise ZipLimitError("The .zip holds more than %d entries." % (pMaxEntries,))
  pFile.seek(0)
  return vCount
