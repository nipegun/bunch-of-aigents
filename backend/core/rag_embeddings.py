"""Embedding and tokenization requests over a fixed Unix socket only."""

import http.client
import json
import math
import socket

from backend.core import rag_settings


class EngineUnavailable(ValueError):
  """The engine is not answering: stopped, restarting or still loading.

  A ValueError, so every caller that reports engine failures keeps doing so.
  Separate, so indexing can tell an outage (retry later, keep the vectors)
  from a problem with the document itself (mark it as an error).
  """


def fModel():
  """The embedding model selected in Settings -> RAG."""
  return rag_settings.fSelectedModel()


class LocalConnection(http.client.HTTPConnection):
  def connect(self):
    self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    self.sock.settimeout(self.timeout)
    self.sock.connect(rag_settings.cSocketPath)


def fRequest(pPath, pBody=None, pTimeout=60):
  """Never resolve a hostname, use a proxy, follow redirects or call a cloud API."""
  vConnection = LocalConnection("localhost", timeout=pTimeout)
  try:
    vConnection.request("POST" if pBody is not None else "GET", pPath,
      json.dumps(pBody, ensure_ascii=False).encode() if pBody is not None else None,
      {"Content-Type": "application/json"})
    vResponse = vConnection.getresponse()
    vData = vResponse.read(8 * 1024 * 1024 + 1)
    if vResponse.status == 503:
      # What the engine answers while it loads the model after a restart.
      raise EngineUnavailable("Local embeddings are unavailable. Check the boa-embeddings service.")
    if vResponse.status != 200 or len(vData) > 8 * 1024 * 1024:
      raise ValueError("The local embedding engine refused the request (%d)." % vResponse.status)
    return json.loads(vData)
  except (OSError, http.client.HTTPException) as vError:
    raise EngineUnavailable("Local embeddings are unavailable. Check the boa-embeddings service.") from vError
  finally:
    vConnection.close()


def fTokenize(pText):
  return fRequest("/tokenize", {"content": pText, "add_special": False})["tokens"]


def fServedModel():
  """The id of the model the engine has loaded, as it reports it.

  The engine is started with the model id as its alias. Right after the model
  is changed, the old engine can still be answering, or the new one still
  loading: nothing may be embedded until the two agree.
  """
  lModels = fRequest("/v1/models", pTimeout=10).get("data") or []
  return lModels[0].get("id", "") if lModels else ""


def fCheckServedModel(pModel):
  if fServedModel() != pModel["id"]:
    raise EngineUnavailable("The local embedding engine is still switching to %s." % pModel["name"])


def fIsAvailable(pModel=None):
  """Whether the engine answers, and answers with the model in use."""
  try:
    fCheckServedModel(pModel or fModel())
    fTokenize("probe")
    return True
  except EngineUnavailable:
    return False


def fEmbed(pTexts, pQuery=False, pModel=None):
  """Unit vectors for these texts, from the model given or else the selected one.

  An indexing job passes the model it started with. A vector from any other
  model would sit in the same index as numbers that mean something else, so a
  model change in the middle of a job stops the job instead: the engine
  answers with another model, and that is an outage, not a bad document.
  """
  dModel = pModel or fModel()
  fCheckServedModel(dModel)
  vPrefix = dModel["query_prefix" if pQuery else "document_prefix"]
  lInputs = [vPrefix + vText for vText in pTexts]
  # Check with the model's own tokenizer; silently truncated vectors would
  # make the end of a book passage impossible to retrieve.
  for vText in lInputs:
    if len(fTokenize(vText)) > dModel["context"] - 2:
      raise ValueError("Text exceeds the local embedding model context; split it first.")
  dResult = fRequest("/v1/embeddings", {"input": lInputs, "encoding_format": "float"})
  lRows = sorted(dResult.get("data", []), key=lambda pRow: pRow["index"])
  if len(lRows) != len(lInputs):
    raise ValueError("The local embedding engine returned an incomplete batch.")
  lVectors = []
  for dRow in lRows:
    lVector = dRow["embedding"]
    if len(lVector) != dModel["dimensions"]:
      # Restarted with another model between the check above and this answer.
      raise EngineUnavailable("The local embedding engine switched models during the request.")
    if not all(math.isfinite(v) for v in lVector):
      raise ValueError("The local embedding engine returned an invalid vector.")
    vNorm = math.sqrt(sum(v * v for v in lVector))
    if not vNorm:
      raise ValueError("The local embedding engine returned an empty vector.")
    lVectors.append([v / vNorm for v in lVector])
  return lVectors
