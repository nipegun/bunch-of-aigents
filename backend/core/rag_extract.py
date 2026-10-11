"""Bounded local document extraction, OCR and structure-aware text chunks."""

from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time
import zipfile

from backend.core import rag_embeddings, rag_store, zip_limits

cMaxTextCharacters = 32 * 1024 * 1024
cMaxPages = 10000
cMaxEpubEntries = 20000
# What one OCR subprocess may take at most, whatever is left of the batch.
cOcrSeconds = 90


class Paused(Exception):
  """The batch ran out of time between two pages. What was extracted is kept
  and the document goes back to the queue, so one long book never holds the
  worker for hours while every other library waits (rag_worker.fWork)."""


def fTimeLeft(pDeadline, pCap):
  """Seconds a step may take: pCap, or less when the batch ends sooner."""
  if pDeadline is None:
    return pCap
  vLeft = pDeadline - time.monotonic()
  if vLeft <= 0:
    raise Paused()
  return min(pCap, vLeft)


class BookText(HTMLParser):
  def __init__(self):
    super().__init__(convert_charrefs=True)
    self.lParts = []
    self.vIgnored = 0

  def handle_starttag(self, pTag, pAttributes):
    if pTag in ("script","style"):
      self.vIgnored += 1
    if pTag in ("p","div","br","pre","h1","h2","h3","li","tr"):
      self.lParts.append("\n")

  def handle_endtag(self, pTag):
    if pTag in ("script","style"):
      self.vIgnored = max(0,self.vIgnored-1)
    if pTag in ("p","div","pre","h1","h2","h3","li","tr"):
      self.lParts.append("\n")

  def handle_data(self, pData):
    if not self.vIgnored:
      self.lParts.append(pData)


def fOcrPage(pPath, pPage, pLanguages, pDirectory, pDeadline=None):
  # Each subprocess gets what is left of the batch, never more than
  # cOcrSeconds: two of them at ninety seconds each, per page, for up to ten
  # thousand pages, used to be what one document could take.
  with tempfile.TemporaryDirectory(prefix="ocr-",dir=pDirectory) as vTemporary:
    vImage = Path(vTemporary)/"page"
    try:
      subprocess.run(["pdftoppm","-f",str(pPage),"-l",str(pPage),"-scale-to","2400",
        "-png","-singlefile",str(pPath),str(vImage)], check=True, capture_output=True,
        timeout=fTimeLeft(pDeadline,cOcrSeconds))
      vResult = subprocess.run(["tesseract",str(vImage)+".png","stdout","-l",pLanguages],
        check=True,capture_output=True,timeout=fTimeLeft(pDeadline,cOcrSeconds))
    except FileNotFoundError as vError:
      raise ValueError("Local OCR needs pdftoppm and Tesseract. Update the BoA installation.") from vError
    except subprocess.TimeoutExpired as vError:
      if pDeadline is not None and time.monotonic() >= pDeadline-1:
        raise Paused() from vError
      raise ValueError("Local OCR failed on page %d; check the installed OCR languages." % pPage) from vError
    except subprocess.CalledProcessError as vError:
      raise ValueError("Local OCR failed on page %d; check the installed OCR languages." % pPage) from vError
    return vResult.stdout.decode("utf-8",errors="replace")


def fExtract(pPath, pSettings, pStaging, pStart=0, pDeadline=None):
  """Yield page/chapter records without reading external links or resources.

  pStart skips the records an earlier batch already extracted; pDeadline is
  checked before each record, and Paused raised once it has passed.
  """
  vSuffix = pPath.suffix.lower()
  if vSuffix == ".pdf":
    from pypdf import PdfReader
    with rag_store.fOpenRegular(pPath) as vFile:
      vReader = PdfReader(vFile)
      if vReader.is_encrypted:
        raise ValueError("This PDF is encrypted. Upload an unlocked copy.")
      if len(vReader.pages)>cMaxPages:
        raise ValueError("The PDF exceeds the page limit.")
      for vNumber,vPage in enumerate(vReader.pages,1):
        if vNumber<=pStart:
          continue
        fTimeLeft(pDeadline,1)
        vText = vPage.extract_text(extraction_mode="layout") or ""
        if len(vText.strip())<40 and pSettings["ocr"]:
          vText = fOcrPage(pPath,vNumber,pSettings["ocr_languages"],pStaging,pDeadline)
        yield {"text":vText,"page":vNumber,"location":"Page %d"%vNumber,"section":""}
  elif vSuffix == ".epub":
    # Validate the expanded archive before the EPUB library reads its entries.
    # The entries are counted before ZipFile builds an object for each one.
    with rag_store.fOpenRegular(pPath) as vFile:
      try:
        zip_limits.fCheckCentralDirectory(vFile,cMaxEpubEntries)
      except zip_limits.ZipLimitError as vError:
        raise ValueError("The expanded EPUB exceeds the size limit.") from vError
      with zipfile.ZipFile(vFile) as vZip:
        lItems = vZip.infolist()
        if len(lItems)>cMaxEpubEntries or sum(v.file_size for v in lItems)>256*1024*1024:
          raise ValueError("The expanded EPUB exceeds the size limit.")
        for vItem in lItems:
          if vItem.file_size>32*1024*1024 or (vItem.flag_bits & 1):
            raise ValueError("The EPUB has an oversized or encrypted entry.")
          if Path(vItem.filename).is_absolute() or ".." in Path(vItem.filename).parts:
            raise ValueError("The EPUB contains an invalid path.")
          if vItem.filename.lower().endswith((".xml",".opf",".xhtml",".html")):
            if b"<!ENTITY" in vZip.read(vItem).upper():
              raise ValueError("EPUB entity declarations are not supported.")
    from ebooklib import epub
    vBook = epub.read_epub(str(pPath),options={"ignore_ncx":True})
    for vNumber,(vId,vLinear) in enumerate(vBook.spine,1):
      if vNumber<=pStart:
        continue
      fTimeLeft(pDeadline,1)
      vItem = vBook.get_item_with_id(vId)
      if vItem is None:
        continue
      vParser = BookText()
      vParser.feed(vItem.get_content().decode("utf-8",errors="replace"))
      vSection = vItem.get_name()
      yield {"text":"".join(vParser.lParts),"page":None,"section":vSection,
             "location":"Chapter %d: %s"%(vNumber,vSection)}
  else:
    if pStart:
      return
    with rag_store.fOpenRegular(pPath) as vFile:
      vRaw = vFile.read(cMaxTextCharacters*4+1)
    if len(vRaw)>cMaxTextCharacters*4 or b"\x00" in vRaw:
      raise ValueError("The text document is too large or is not UTF-8 text.")
    try:
      vText = vRaw.decode("utf-8-sig")
    except UnicodeDecodeError as vError:
      raise ValueError("Text and Markdown documents must use UTF-8.") from vError
    yield {"text":vText,"page":None,"section":"","location":"Document text"}


def fChunks(pText, pTokenLimit):
  """Keep paragraphs and code intact where they fit; split long blocks exactly."""
  vText = pText.replace("\r\n","\n").replace("\x00","").strip()
  if not vText:
    return
  # Tokenize modest windows rather than making a multi-megabyte RPC request.
  vOffset = 0
  while vOffset<len(vText):
    vEnd = min(len(vText),vOffset+2400)
    vPiece = vText[vOffset:vEnd]
    lTokens = rag_embeddings.fTokenize(vPiece)
    if len(lTokens)>pTokenLimit:
      vLow,vHigh = 1,len(vPiece)
      while vLow<vHigh:
        vMiddle = (vLow+vHigh+1)//2
        if len(rag_embeddings.fTokenize(vPiece[:vMiddle]))<=pTokenLimit:
          vLow=vMiddle
        else:
          vHigh=vMiddle-1
      vEnd = vOffset+vLow
    if vEnd<len(vText):
      vBoundary = vText.rfind("\n",vOffset+(vEnd-vOffset)//2,vEnd)
      if vBoundary>vOffset:
        vEnd=vBoundary+1
    vPiece = vText[vOffset:vEnd]
    if vPiece.strip():
      yield vPiece,len(rag_embeddings.fTokenize(vPiece))
    # Small overlap preserves explanations that cross a fragment boundary.
    if vEnd==len(vText):
      break
    vOffset = max(vOffset+1,vEnd-min(100,(vEnd-vOffset)//5))


def fResumeFile(pTarget):
  """(records already in pTarget, their characters), dropping a cut last line."""
  if not pTarget.exists():
    return 0,0
  vData = pTarget.read_bytes()
  vEnd = vData.rfind(b"\n")+1
  if vEnd<len(vData):
    with pTarget.open("r+b") as vFile:
      vFile.truncate(vEnd)
  vPages,vTotal = 0,0
  for vLine in vData[:vEnd].decode("utf-8").splitlines():
    vPages += 1
    vTotal += len(json.loads(vLine)["text"])
  return vPages,vTotal


def fExtractToFile(pPath, pSettings, pTarget, pStaging, pProgress, pDeadline=None):
  # Appends: a batch that ran out of time left the pages it extracted in
  # pTarget, and the next one carries on after them.
  vPages,vTotal = fResumeFile(pTarget)
  with pTarget.open("a",encoding="utf-8") as vOutput:
    for dPage in fExtract(pPath,pSettings,pStaging,vPages,pDeadline):
      vPages += 1
      vTotal += len(dPage["text"])
      if vTotal>cMaxTextCharacters:
        raise ValueError("The extracted document exceeds the text size limit.")
      pProgress(vPages)
      vOutput.write(json.dumps(dPage,ensure_ascii=False)+"\n")
      vOutput.flush()
  if not vTotal:
    raise ValueError("No readable text was extracted. Check the document, scan quality and OCR language settings.")
  return vPages
