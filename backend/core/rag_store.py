"""Private per-agent document catalogue, uploads and durable indexing jobs.

Every entry point runs as the agent. Root never opens an agent's SQLite file.
Published revisions remain searchable while their replacements are built.
"""

import base64
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import time
import uuid

from backend.core import rag_settings

cIdPattern = re.compile(r"[a-f0-9]{32}")
cSchema = """
CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, format TEXT NOT NULL,
  size INTEGER NOT NULL, received INTEGER NOT NULL DEFAULT 0,
  sha256 TEXT NOT NULL DEFAULT '', title TEXT NOT NULL DEFAULT '',
  author TEXT NOT NULL DEFAULT '', language TEXT NOT NULL DEFAULT '',
  version TEXT NOT NULL DEFAULT '', tags TEXT NOT NULL DEFAULT '',
  year TEXT NOT NULL DEFAULT '',
  subtitle TEXT NOT NULL DEFAULT '',
  model TEXT NOT NULL DEFAULT '',
  state TEXT NOT NULL DEFAULT 'uploading', error TEXT NOT NULL DEFAULT '',
  progress INTEGER NOT NULL DEFAULT 0, pages INTEGER NOT NULL DEFAULT 0,
  active_revision INTEGER NOT NULL DEFAULT 0, next_revision INTEGER NOT NULL DEFAULT 1,
  replaces TEXT NOT NULL DEFAULT '', created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS chunks (
  id INTEGER PRIMARY KEY, document_id TEXT NOT NULL, revision INTEGER NOT NULL,
  position INTEGER NOT NULL, text TEXT NOT NULL, location TEXT NOT NULL,
  page INTEGER, section TEXT NOT NULL DEFAULT '', tokens INTEGER NOT NULL,
  vector BLOB, UNIQUE(document_id, revision, position),
  FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS chunks_document ON chunks(document_id, revision);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(text, content='chunks', content_rowid='id');
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
  INSERT INTO chunks_fts(rowid,text) VALUES(new.id,new.text);
END;
CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
  INSERT INTO chunks_fts(chunks_fts,rowid,text) VALUES('delete',old.id,old.text);
END;
CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""
# Columns added to `documents` after catalogues already existed, in the order
# they were added. fMigrate gives them to older catalogues and restored backups.
lAddedColumns = [("year", "TEXT NOT NULL DEFAULT ''"),
                 ("subtitle", "TEXT NOT NULL DEFAULT ''"),
                 # The fingerprint of the embedding model behind the vectors
                 # of the published revision (rag_search.fPublish).
                 ("model", "TEXT NOT NULL DEFAULT ''")]
# The document information a person can edit, in the order the form shows it.
lMetadataKeys = ["year", "title", "subtitle", "author", "version", "language", "tags"]


def fId(pId):
  if not isinstance(pId, str) or not cIdPattern.fullmatch(pId):
    raise ValueError("Invalid RAG document identifier.")
  return pId


def fEnsure(pAgentId):
  vRoot = rag_settings.fDirectory(pAgentId)
  for vPath in [vRoot] + [vRoot / v for v in ("inbox", "documents", "extracted", "index", "staging")]:
    try:
      vPath.mkdir(mode=0o700)
    except FileExistsError:
      if not stat.S_ISDIR(vPath.lstat().st_mode):
        raise ValueError("A RAG directory is not a regular directory.")
  return vRoot


def fMigrate(pConnection):
  """Add columns introduced after a catalogue was created.

  CREATE TABLE IF NOT EXISTS leaves an existing table untouched, so catalogues
  from earlier versions (or restored from their backups) lack newer columns.
  """
  lColumns = [v[1] for v in pConnection.execute("PRAGMA table_info(documents)")]
  for vName, vDefinition in lAddedColumns:
    if vName in lColumns:
      continue
    try:
      pConnection.execute("ALTER TABLE documents ADD COLUMN " + vName + " " + vDefinition)
    except sqlite3.OperationalError as vError:
      # Another worker may have added it between the check and the ALTER.
      if "duplicate column" not in str(vError):
        raise
      continue
    if vName == "model":
      # Until this column existed, a library had a single model, written in
      # its metadata: every published revision was indexed with it.
      pConnection.execute("UPDATE documents SET model=COALESCE((SELECT value FROM metadata "
        "WHERE key='model'),'') WHERE active_revision>0")
      pConnection.commit()


@contextlib.contextmanager
def fConnect(pAgentId):
  vPath = fEnsure(pAgentId) / "index" / "catalog.sqlite"
  if vPath.is_symlink() or (vPath.exists() and not stat.S_ISREG(vPath.stat().st_mode)):
    raise ValueError("The RAG catalogue is not a regular file.")
  vConnection = sqlite3.connect(vPath, timeout=15)
  vConnection.row_factory = sqlite3.Row
  try:
    vConnection.execute("PRAGMA journal_mode=WAL")
    vConnection.execute("PRAGMA foreign_keys=ON")
    vConnection.executescript(cSchema)
    fMigrate(vConnection)
    os.chmod(vPath, 0o600)
    with vConnection:
      yield vConnection
  finally:
    vConnection.close()


def fDocument(pConnection, pId):
  vRow = pConnection.execute("SELECT * FROM documents WHERE id=? AND state!='deleted'", (fId(pId),)).fetchone()
  if vRow is None:
    raise ValueError("Document not found in this agent's library.")
  return dict(vRow)


def fList(pAgentId, pOffset=0, pLimit=100):
  vOffset = max(0, int(pOffset))
  vLimit = min(200, max(1, int(pLimit)))
  with fConnect(pAgentId) as vConnection:
    lRows = [dict(v) for v in vConnection.execute(
      "SELECT * FROM documents WHERE state!='deleted' ORDER BY created_at DESC,id LIMIT ? OFFSET ?",
      (vLimit, vOffset))]
    dCounts = dict(vConnection.execute(
      "SELECT COUNT(*) AS count, COALESCE(SUM(size),0) AS bytes FROM documents WHERE state!='deleted'").fetchone())
    dCounts["chunks"] = vConnection.execute(
      "SELECT COUNT(*) FROM chunks c JOIN documents d ON d.id=c.document_id "
      "WHERE c.revision=d.active_revision AND d.state!='deleted'").fetchone()[0]
    vImport=vConnection.execute("SELECT value FROM metadata WHERE key='import_result'").fetchone()
    try:
      dImport=json.loads(vImport[0]) if vImport else {}
    except ValueError:
      dImport={}
    return {"documents": lRows, "totals": dCounts, "offset": vOffset,
            "import_result":dImport if isinstance(dImport,dict) else {}}


def fBeginUpload(pAgentId, pName, pSize, pReplaces=""):
  dSettings = rag_settings.fRead(pAgentId)
  vName = str(pName or "").replace("\\", "/").split("/")[-1][:240]
  vFormat = Path(vName).suffix.lower()
  if vFormat not in rag_settings.cFormats or not vName or any(ord(v) < 32 for v in vName):
    raise ValueError("Choose a PDF, EPUB, TXT or Markdown document.")
  if type(pSize) is not int or not 0 < pSize <= dSettings["max_file_mb"] * 1024 * 1024:
    raise ValueError("The document exceeds the configured file size limit or is empty.")
  vRoot = fEnsure(pAgentId)
  vId = uuid.uuid4().hex
  with fConnect(pAgentId) as vConnection:
    vConnection.execute("BEGIN IMMEDIATE")
    if pReplaces:
      fDocument(vConnection, pReplaces)
    vUsed = vConnection.execute("SELECT COALESCE(SUM(size),0) FROM documents WHERE state!='deleted'").fetchone()[0]
    if vUsed + pSize > dSettings["max_storage_mb"] * 1024 * 1024:
      raise ValueError("The library storage quota would be exceeded.")
    vNow = int(time.time())
    vConnection.execute("INSERT INTO documents(id,name,format,size,title,replaces,created_at,updated_at) "
      "VALUES(?,?,?,?,?,?,?,?)", (vId,vName,vFormat,pSize,Path(vName).stem,pReplaces,vNow,vNow))
    vDescriptor = os.open(vRoot / "staging" / (vId + ".upload"),
      os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    os.close(vDescriptor)
  return {"document_id": vId, "chunk_bytes": rag_settings.cUploadChunkBytes}


def fUploadChunk(pAgentId, pId, pOffset, pData):
  try:
    vData = base64.b64decode(pData, validate=True)
  except (ValueError, TypeError):
    raise ValueError("Invalid upload data.")
  if not vData or len(vData) > rag_settings.cUploadChunkBytes or type(pOffset) is not int or pOffset < 0:
    raise ValueError("Invalid upload chunk size or offset.")
  with fConnect(pAgentId) as vConnection:
    vConnection.execute("BEGIN IMMEDIATE")
    dDoc = fDocument(vConnection, pId)
    if dDoc["state"] != "uploading" or pOffset + len(vData) > dDoc["size"]:
      raise ValueError("The upload is not writable or exceeds its declared size.")
    vDescriptor = os.open(fEnsure(pAgentId) / "staging" / (pId + ".upload"), os.O_RDWR | os.O_NOFOLLOW)
    try:
      if not stat.S_ISREG(os.fstat(vDescriptor).st_mode):
        raise ValueError("Invalid upload file.")
      if pOffset < dDoc["received"]:
        if pOffset + len(vData) <= dDoc["received"] and os.pread(vDescriptor,len(vData),pOffset) == vData:
          return {"received": dDoc["received"]}
        raise ValueError("The upload chunk conflicts with previously received data.")
      if pOffset != dDoc["received"]:
        raise ValueError("Resume the upload at its recorded offset.")
      os.ftruncate(vDescriptor, dDoc["received"])
      with os.fdopen(os.dup(vDescriptor), "r+b") as vFile:
        vFile.seek(pOffset)
        vFile.write(vData)
        vFile.flush()
        os.fsync(vFile.fileno())
    finally:
      os.close(vDescriptor)
    vReceived = pOffset + len(vData)
    vConnection.execute("UPDATE documents SET received=?,updated_at=? WHERE id=?", (vReceived,int(time.time()),pId))
  return {"received": vReceived}


def fFinishUpload(pAgentId, pId):
  vRoot = fEnsure(pAgentId)
  with fConnect(pAgentId) as vConnection:
    vConnection.execute("BEGIN IMMEDIATE")
    dDoc = fDocument(vConnection,pId)
    if dDoc["state"] != "uploading":
      return {"document": dDoc}
    if dDoc["received"] != dDoc["size"]:
      raise ValueError("The document upload is incomplete.")
    vPath = vRoot / "staging" / (pId + ".upload")
    if not vPath.exists():
      # Recover a crash between the atomic rename and the catalogue commit.
      vPath=vRoot/"documents"/(pId+dDoc["format"])
    vDigest = hashlib.sha256()
    with fOpenRegular(vPath) as vFile:
      vHeader = vFile.read(1024)
      if dDoc["format"] == ".pdf" and b"%PDF-" not in vHeader:
        raise ValueError("This file is not a PDF.")
      if dDoc["format"] == ".epub" and not vHeader.startswith(b"PK"):
        raise ValueError("This file is not an EPUB archive.")
      vFile.seek(0)
      for vChunk in iter(lambda: vFile.read(1024 * 1024), b""):
        vDigest.update(vChunk)
    vHash = vDigest.hexdigest()
    dDuplicate = vConnection.execute("SELECT id FROM documents WHERE sha256=? AND state!='deleted' AND id!=?", (vHash,pId)).fetchone()
    if dDuplicate:
      vConnection.execute("DELETE FROM documents WHERE id=?", (pId,))
      vPath.unlink()
      return {"duplicate": dDuplicate[0]}
    os.replace(vPath, vRoot / "documents" / (pId + dDoc["format"]))
    vConnection.execute("UPDATE documents SET sha256=?,state='queued',updated_at=? WHERE id=?", (vHash,int(time.time()),pId))
    return {"document": fDocument(vConnection,pId)}


def fOpenRegular(pPath):
  vDescriptor = os.open(pPath, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
  if not stat.S_ISREG(os.fstat(vDescriptor).st_mode):
    os.close(vDescriptor)
    raise ValueError("Only regular document files can be read.")
  return os.fdopen(vDescriptor,"rb")


def fReadOriginal(pAgentId, pId, pOffset=0):
  if type(pOffset) is not int or pOffset < 0:
    raise ValueError("Invalid document offset.")
  with fConnect(pAgentId) as vConnection:
    dDoc = fDocument(vConnection,pId)
  with fOpenRegular(fEnsure(pAgentId) / "documents" / (pId+dDoc["format"])) as vFile:
    vFile.seek(pOffset)
    vChunk = vFile.read(1024*1024)
  return {"data": base64.b64encode(vChunk).decode(), "name": dDoc["name"],
          "size": dDoc["size"], "format": dDoc["format"]}


def fAction(pAgentId, pId, pAction, pMetadata=None):
  with fConnect(pAgentId) as vConnection:
    vConnection.execute("BEGIN IMMEDIATE")
    dDoc = fDocument(vConnection,pId)
    if pAction == "metadata":
      for vKey,vValue in (pMetadata or {}).items():
        if vKey not in lMetadataKeys or not isinstance(vValue,str) or len(vValue)>500:
          raise ValueError("Invalid document metadata.")
        if vKey == "year":
          vValue = vValue.strip()
          if vValue and not re.fullmatch(r"[0-9]{1,4}",vValue):
            raise ValueError("The publication year must be a number of up to four digits.")
        vConnection.execute("UPDATE documents SET " + vKey + "=? WHERE id=?", (vValue,pId))
    elif pAction in ("reindex","retry"):
      if dDoc["state"] in ("uploading","extracting","embedding"):
        raise ValueError("Wait for or cancel the current document operation first.")
      vConnection.execute("UPDATE documents SET state='queued',error='',progress=0,next_revision=next_revision+1 WHERE id=?",(pId,))
    elif pAction in ("cancel","delete"):
      vState = "deleted" if pAction == "delete" or dDoc["state"]=="uploading" else "cancelled"
      vConnection.execute("UPDATE documents SET state=?,next_revision=next_revision+1 WHERE id=?",(vState,pId))
      if pAction == "delete":
        vConnection.execute("DELETE FROM chunks WHERE document_id=?",(pId,))
    else:
      raise ValueError("Unknown document action.")
    vConnection.execute("UPDATE documents SET updated_at=? WHERE id=?",(int(time.time()),pId))
  if pAction == "delete" or (pAction == "cancel" and dDoc["state"] == "uploading"):
    for vPath in (fEnsure(pAgentId)/"staging"/(pId+".upload"),):
      vPath.unlink(missing_ok=True)
    if pAction == "delete":
      (fEnsure(pAgentId)/"documents"/(pId+dDoc["format"])).unlink(missing_ok=True)
      (fEnsure(pAgentId)/"extracted"/(pId+".jsonl")).unlink(missing_ok=True)
  return {"updated": True}


def fImportInbox(pAgentId):
  vRoot = fEnsure(pAgentId)
  lImported, lErrors = [], []
  for vPath in sorted((vRoot / "inbox").iterdir()):
    if vPath.suffix.lower() not in rag_settings.cFormats:
      continue
    vId = ""
    try:
      with fOpenRegular(vPath) as vFile:
        dBefore = os.fstat(vFile.fileno())
        vId = fBeginUpload(pAgentId,vPath.name,dBefore.st_size)["document_id"]
        vOffset = 0
        while vChunk := vFile.read(rag_settings.cUploadChunkBytes):
          fUploadChunk(pAgentId,vId,vOffset,base64.b64encode(vChunk).decode())
          vOffset += len(vChunk)
        dAfter = os.fstat(vFile.fileno())
        if (dBefore.st_size,dBefore.st_mtime_ns) != (dAfter.st_size,dAfter.st_mtime_ns):
          raise ValueError("The source file changed during import; finish copying it first.")
      dResult = fFinishUpload(pAgentId,vId)
      lImported.append({"name": vPath.name, **dResult})
      vPath.unlink()
    except (OSError,ValueError) as vError:
      if vId:
        fAction(pAgentId,vId,"delete")
      lErrors.append({"name": vPath.name,"error": str(vError)})
    if len(lImported)+len(lErrors)>=100:
      break
  return {"imported":lImported,"errors":lErrors}


def fSnapshot(pAgentId,pDestination=None):
  """Pin immutable originals and the index while taking a SQLite backup.

  The reservation blocks catalogue mutations. The second connection reads
  the committed state through SQLite's backup API without copying live WAL.
  Hard links retain the selected files even if a new generation replaces them.
  """
  vRoot=fEnsure(pAgentId)
  vTarget=Path(pDestination) if pDestination else vRoot/"staging"/"backup-snapshot"
  if vTarget.exists() and not pDestination:
    shutil.rmtree(vTarget)
  for vPart in ("documents","extracted","index","inbox","staging"):
    (vTarget/vPart).mkdir(parents=True,mode=0o700)
  with fConnect(pAgentId) as vConnection:
    vConnection.execute("BEGIN IMMEDIATE")
    with sqlite3.connect(vRoot/"index"/"catalog.sqlite") as vSource:
      with sqlite3.connect(vTarget/"index"/"catalog.sqlite") as vBackup:
        vSource.backup(vBackup)
        vBackup.execute("UPDATE documents SET state='cancelled',error='Upload interrupted by backup restore.' WHERE state='uploading'")
        vBackup.execute("UPDATE documents SET state='queued' WHERE state IN ('extracting','embedding')")
    for dDoc in vConnection.execute("SELECT * FROM documents WHERE state NOT IN ('deleted','uploading')"):
      for vSource in (vRoot/"documents"/(dDoc["id"]+dDoc["format"]),vRoot/"extracted"/(dDoc["id"]+".jsonl")):
        if vSource.exists():
          with fOpenRegular(vSource):
            os.link(vSource,vTarget/vSource.relative_to(vRoot),follow_symlinks=False)
    dIndex=vConnection.execute("SELECT value FROM metadata WHERE key='index'").fetchone()
    if dIndex and re.fullmatch(r"[a-f0-9]{32}\.usearch",dIndex[0]):
      vSource=vRoot/"index"/dIndex[0]
      with fOpenRegular(vSource):
        os.link(vSource,vTarget/"index"/dIndex[0],follow_symlinks=False)
    for vSource in (vRoot/"inbox").iterdir():
      if stat.S_ISREG(vSource.lstat().st_mode):
        os.link(vSource,vTarget/"inbox"/vSource.name,follow_symlinks=False)
  return {"snapshot":True}
