"""Read a cited fragment in the calling agent's library."""

import json
from backend.core import rag_search, rag_settings, tool_registry

cToolName="rag.read"
cToolDescription="Read a document fragment by its chunk identifier. Returns the original text and a verifiable source reference."
dToolSchema={"type":"object","properties":{
  "chunk_id":{"type":"integer","description":"The fragment identifier returned by rag.search."}},
  "required":["chunk_id"],"additionalProperties":False}


def fRunTool(pArguments,pContext):
  if not rag_settings.fRead(pContext.vAgentId)["enabled"]:
    raise tool_registry.ToolFailure("Document retrieval is disabled for this agent.")
  try:
    if pContext.vRagRemaining is not None and pContext.vRagRemaining<1000:
      raise ValueError("The document retrieval budget for this run is exhausted.")
    lSources=rag_search.fReadNeighbours(pContext.vAgentId,pArguments.get("chunk_id"))
    vText=json.dumps({"sources":lSources},ensure_ascii=False)
    if pContext.vRagRemaining is not None:
      if len(vText.encode("utf-8"))>pContext.vRagRemaining:
        raise ValueError("The surrounding passages exceed the remaining retrieval budget.")
      pContext.vRagRemaining-=len(vText.encode("utf-8"))
    pContext.lRagSources.extend(lSources)
    return vText
  except (ValueError,TypeError,OSError) as vError:
    raise tool_registry.ToolFailure(str(vError)) from vError
