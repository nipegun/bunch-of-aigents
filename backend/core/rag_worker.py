#!/usr/bin/env -S PYTHONDONTWRITEBYTECODE=1 python3

"""Fixed RAG operations executed after dropping to the agent's Unix user."""

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))

from backend.core import rag_embeddings, rag_extract, rag_search, rag_settings, rag_store


def fCheckJob(pAgentId,pId,pRevision,pState=None,pProgress=None):
  with rag_store.fConnect(pAgentId) as vConnection:
    dDoc=rag_store.fDocument(vConnection,pId)
    if dDoc["next_revision"]!=pRevision or dDoc["state"] in ("deleted","cancelled"):
      raise ValueError("Indexing was cancelled.")
    if pState:
      # A running job clears the notice an engine outage left on the document.
      vConnection.execute("UPDATE documents SET state=?,progress=?,error='',updated_at=? WHERE id=?",
        (pState,pProgress or 0,int(time.time()),pId))


def fIndexDocument(pAgentId,pDoc):
  """Index one revision. False only when the engine went away mid-job."""
  import numpy as np
  vId,vRevision=pDoc["id"],pDoc["next_revision"]
  vRoot=rag_store.fEnsure(pAgentId)
  dSettings=rag_settings.fRead(pAgentId)
  # Every vector of this revision comes from this model. If the model is
  # changed halfway, fEmbed refuses the next chunk and the job goes back to
  # the queue, where fWork sees the change and starts the document over.
  dModel=rag_embeddings.fModel()
  vExtracted=vRoot/"staging"/(vId+".jsonl")
  vIndex=None
  try:
    fCheckJob(pAgentId,vId,vRevision,"extracting",1)
    with rag_store.fOpenRegular(vRoot/"documents"/(vId+pDoc["format"])) as vOriginal:
      if hashlib.file_digest(vOriginal,"sha256").hexdigest()!=pDoc["sha256"]:
        raise ValueError("The original document changed. Upload its new version before indexing.")
    vPages=rag_extract.fExtractToFile(vRoot/"documents"/(vId+pDoc["format"]),dSettings,
      vExtracted,vRoot/"staging",lambda pPage:fCheckJob(pAgentId,vId,vRevision))
    with rag_store.fConnect(pAgentId) as vConnection:
      vConnection.execute("UPDATE documents SET pages=? WHERE id=?",(vPages,vId))
      vExisting=vConnection.execute("SELECT COUNT(*) FROM chunks c JOIN documents d ON d.id=c.document_id "
        "WHERE c.revision=d.active_revision AND d.id!=? AND d.state!='deleted'",(vId,)).fetchone()[0]
    vPosition=0
    with vExtracted.open(encoding="utf-8") as vFile:
      for vPageNumber,vLine in enumerate(vFile,1):
        dPage=json.loads(vLine)
        for vText,vTokens in rag_extract.fChunks(dPage["text"],dSettings["chunk_tokens"]):
          fCheckJob(pAgentId,vId,vRevision,"embedding",min(95,5+int(vPageNumber/vPages*90)))
          if vExisting+vPosition>=dSettings["max_chunks"]:
            raise ValueError("The library fragment quota would be exceeded.")
          with rag_store.fConnect(pAgentId) as vConnection:
            vCached=vConnection.execute("SELECT text,vector FROM chunks WHERE document_id=? AND revision=? AND position=?",
              (vId,vRevision,vPosition)).fetchone()
          if vCached and vCached[0]==vText and vCached[1]:
            vPosition+=1
            continue
          lVector=rag_embeddings.fEmbed([vText],pModel=dModel)[0]
          with rag_store.fConnect(pAgentId) as vConnection:
            vConnection.execute("DELETE FROM chunks WHERE document_id=? AND revision=? AND position=?",(vId,vRevision,vPosition))
            vConnection.execute("INSERT INTO chunks(document_id,revision,position,text,location,page,section,tokens,vector) "
              "VALUES(?,?,?,?,?,?,?,?,?)",(vId,vRevision,vPosition,vText,dPage["location"],dPage["page"],
              dPage["section"],vTokens,np.asarray(lVector,dtype="<f4").tobytes()))
          vPosition+=1
    if not vPosition:
      raise ValueError("No searchable text was found in this document.")
    fCheckJob(pAgentId,vId,vRevision,"embedding",96)
    vIndex=rag_search.fBuildIndex(pAgentId,vId,vRevision,dModel)
    rag_search.fPublish(pAgentId,vId,vRevision,vIndex,vExtracted,dModel)
  except rag_embeddings.EngineUnavailable as vError:
    # An outage (an update, a restart, a crash) says nothing about the
    # document. Queue it again with the SAME revision and keep its chunks, so
    # the next run reuses every stored vector instead of starting the book over.
    with rag_store.fConnect(pAgentId) as vConnection:
      vConnection.execute("UPDATE documents SET state='queued',error=?,updated_at=? "
        "WHERE id=? AND next_revision=? AND state NOT IN ('deleted','cancelled')",
        (str(vError)[:1000],int(time.time()),vId,vRevision))
    return False
  except Exception as vError:
    with rag_store.fConnect(pAgentId) as vConnection:
      vConnection.execute("UPDATE documents SET state='error',error=?,updated_at=? "
        "WHERE id=? AND next_revision=? AND state NOT IN ('deleted','cancelled')",
        (str(vError)[:1000],int(time.time()),vId,vRevision))
      vConnection.execute("DELETE FROM chunks WHERE document_id=? AND revision=? AND revision!=(SELECT active_revision FROM documents WHERE id=?)",
        (vId,vRevision,vId))
  finally:
    vExtracted.unlink(missing_ok=True)
    if vIndex:
      with rag_store.fConnect(pAgentId) as vConnection:
        vActive=vConnection.execute("SELECT value FROM metadata WHERE key='index'").fetchone()
      if not vActive or vActive[0]!=vIndex:
        (vRoot/"index"/vIndex).unlink(missing_ok=True)
  return True


def fFollowNewModel(pConnection,pModel):
  """Index again, with the model now selected, what another model indexed.

  A new model defines a different vector space, even when dimensions happen
  to match: its vectors and the old ones cannot be searched together. The
  published revisions are not deleted, though. Until its turn comes, each
  document is still found by its words (rag_search.fSearch), instead of the
  library going blank for the hours a large one takes to index again.
  """
  # Chunks of unfinished revisions were embedded with the old model, and a
  # job resuming after an outage would reuse them as if they were new.
  pConnection.execute("DELETE FROM chunks WHERE revision!=(SELECT active_revision FROM documents "
    "WHERE documents.id=chunks.document_id)")
  pConnection.execute("UPDATE documents SET state='queued',next_revision=next_revision+1,progress=0,error='' "
    "WHERE model!=? AND state NOT IN ('deleted','uploading') AND (state!='cancelled' OR active_revision>0)",
    (pModel,))
  # The vector index belongs to the old model; the first document published
  # with the new one starts a new index.
  pConnection.execute("DELETE FROM metadata WHERE key='index'")
  pConnection.execute("INSERT OR REPLACE INTO metadata VALUES('model',?)",(pModel,))


def fWork(pAgentId):
  vRoot=rag_store.fEnsure(pAgentId)
  vDescriptor=os.open(vRoot/"staging"/"worker.lock",os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
  try:
    try:
      fcntl.flock(vDescriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
      return {"busy":True}
    vCurrent=rag_embeddings.fModel()["sha256"]
    with rag_store.fConnect(pAgentId) as vConnection:
      vStoredModel=vConnection.execute("SELECT value FROM metadata WHERE key='model'").fetchone()
      if vStoredModel and vStoredModel[0]!=vCurrent:
        fFollowNewModel(vConnection,vCurrent)
      elif not vStoredModel:
        vConnection.execute("INSERT INTO metadata VALUES('model',?)",(vCurrent,))
      # Owning the OS lock proves an earlier indexing process no longer runs.
      vConnection.execute("UPDATE documents SET state='queued' WHERE state IN ('extracting','embedding')")
      vImport=vConnection.execute("SELECT value FROM metadata WHERE key='import_requested'").fetchone()
    if vImport:
      dResult=rag_store.fImportInbox(pAgentId)
      with rag_store.fConnect(pAgentId) as vConnection:
        vConnection.execute("DELETE FROM metadata WHERE key='import_requested'")
        vConnection.execute("INSERT OR REPLACE INTO metadata VALUES('import_result',?)",(json.dumps(dResult),))
    vProcessed=0
    vDeadline=time.monotonic()+90
    # Drain a bounded batch while we already own the lock. Starting one child
    # per book left short documents waiting through a full scheduler rotation.
    while vProcessed<8 and time.monotonic()<vDeadline:
      with rag_store.fConnect(pAgentId) as vConnection:
        dRow=vConnection.execute("SELECT * FROM documents WHERE state='queued' ORDER BY created_at,id LIMIT 1").fetchone()
      if dRow is None:
        break
      # Without the engine a job would extract (or OCR) the whole document
      # just to stop at its first chunk, again on every scheduler pass.
      if not rag_embeddings.fIsAvailable():
        return {"processed":bool(vProcessed),"count":vProcessed,"waiting_for_engine":True}
      vProcessed+=1
      if not fIndexDocument(pAgentId,dict(dRow)):
        return {"processed":True,"count":vProcessed,"waiting_for_engine":True}
    return {"processed":bool(vProcessed),"count":vProcessed}
  finally:
    os.close(vDescriptor)


def fDispatch(pAgentId,pOperation,pArguments):
  d=pArguments
  if pOperation=="list": return rag_store.fList(pAgentId,d.get("offset",0),d.get("limit",100))
  if pOperation=="begin": return rag_store.fBeginUpload(pAgentId,d.get("name"),d.get("size"),d.get("replaces",""))
  if pOperation=="chunk": return rag_store.fUploadChunk(pAgentId,d.get("id"),d.get("offset"),d.get("data"))
  if pOperation=="finish": return rag_store.fFinishUpload(pAgentId,d.get("id"))
  if pOperation=="action": return rag_store.fAction(pAgentId,d.get("id"),d.get("action"),d.get("metadata"))
  if pOperation=="content": return rag_store.fReadOriginal(pAgentId,d.get("id"),d.get("offset",0))
  if pOperation=="import":
    with rag_store.fConnect(pAgentId) as vConnection:
      vConnection.execute("INSERT OR REPLACE INTO metadata VALUES('import_requested','1')")
    return {"queued":True}
  if pOperation=="search": return rag_search.fSearch(pAgentId,d.get("query"),d.get("documents"),d.get("filters"))
  if pOperation=="ensure": return {"directory":str(rag_store.fEnsure(pAgentId))}
  if pOperation=="snapshot": return rag_store.fSnapshot(pAgentId,d.get("destination"))
  if pOperation=="snapshot_cleanup":
    shutil.rmtree(rag_store.fEnsure(pAgentId)/"staging"/"backup-snapshot",ignore_errors=True)
    return {"removed":True}
  if pOperation=="work": return fWork(pAgentId)
  raise ValueError("Unknown RAG operation.")


def fMain():
  vParser=argparse.ArgumentParser()
  vParser.add_argument("--agent",required=True)
  vParser.add_argument("--operation",required=True)
  dArguments=vParser.parse_args()
  os.umask(0o077)
  resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
  resource.setrlimit(resource.RLIMIT_CPU,(7200,7200))
  try:
    vInput=sys.stdin.buffer.read(1024*1024+1)
    if len(vInput)>1024*1024:
      raise ValueError("RAG request is too large.")
    dParams=json.loads(vInput or b"{}")
    dResult=fDispatch(dArguments.agent,dArguments.operation,dParams)
    print(json.dumps({"ok":True,"result":dResult},ensure_ascii=False))
    return 0
  except Exception as vError:
    print(json.dumps({"ok":False,"error":str(vError)[:1500]}))
    return 1


if __name__=="__main__":
  raise SystemExit(fMain())
