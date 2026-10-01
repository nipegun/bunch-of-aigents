"""Bounded local document extraction, OCR and structure-aware text chunks."""

from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

from backend.core import rag_embeddings, rag_store

cMaxTextCharacters = 32 * 1024 * 1024
cMaxPages = 10000


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


def fOcrPage(pPath, pPage, pLanguages, pDirectory):
  with tempfile.TemporaryDirectory(prefix="ocr-",dir=pDirectory) as vTemporary:
    vImage = Path(vTemporary)/"page"
    try:
      subprocess.run(["pdftoppm","-f",str(pPage),"-l",str(pPage),"-scale-to","2400",
        "-png","-singlefile",str(pPath),str(vImage)], check=True, capture_output=True,timeout=90)
      vResult = subprocess.run(["tesseract",str(vImage)+".png","stdout","-l",pLanguages],
        check=True,capture_output=True,timeout=90)
    except FileNotFoundError as vError:
      raise ValueError("Local OCR needs pdftoppm and Tesseract. Update the BoA installation.") from vError
    except (subprocess.CalledProcessError,subprocess.TimeoutExpired) as vError:
      raise ValueError("Local OCR failed on page %d; check the installed OCR languages." % pPage) from vError
    return vResult.stdout.decode("utf-8",errors="replace")


def fExtract(pPath, pSettings, pStaging):
  """Yield page/chapter records without reading external links or resources."""
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
        vText = vPage.extract_text(extraction_mode="layout") or ""
        if len(vText.strip())<40 and pSettings["ocr"]:
          vText = fOcrPage(pPath,vNumber,pSettings["ocr_languages"],pStaging)
        yield {"text":vText,"page":vNumber,"location":"Page %d"%vNumber,"section":""}
  elif vSuffix == ".epub":
    # Validate the expanded archive before the EPUB library reads its entries.
    with rag_store.fOpenRegular(pPath) as vFile, zipfile.ZipFile(vFile) as vZip:
      lItems = vZip.infolist()
      if len(lItems)>20000 or sum(v.file_size for v in lItems)>256*1024*1024:
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
      vItem = vBook.get_item_with_id(vId)
      if vItem is None:
        continue
      vParser = BookText()
      vParser.feed(vItem.get_content().decode("utf-8",errors="replace"))
      vSection = vItem.get_name()
      yield {"text":"".join(vParser.lParts),"page":None,"section":vSection,
             "location":"Chapter %d: %s"%(vNumber,vSection)}
  else:
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


def fExtractToFile(pPath, pSettings, pTarget, pStaging, pProgress):
  vTotal,vPages = 0,0
  with pTarget.open("w",encoding="utf-8") as vOutput:
    for dPage in fExtract(pPath,pSettings,pStaging):
      vPages += 1
      vTotal += len(dPage["text"])
      if vTotal>cMaxTextCharacters:
        raise ValueError("The extracted document exceeds the text size limit.")
      pProgress(vPages)
      vOutput.write(json.dumps(dPage,ensure_ascii=False)+"\n")
  if not vTotal:
    raise ValueError("No readable text was extracted. Check the document, scan quality and OCR language settings.")
  return vPages
