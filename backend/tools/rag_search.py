"""Search only the calling agent's local document library."""

import json
from backend.core import rag_search, rag_settings, tool_registry

cToolName="rag.search"
cToolDescription="Search your document library by meaning and exact terms. Cite the returned ref values as [rag:REFERENCE]."
dToolSchema={"type":"object","properties":{
  "query":{"type":"string","description":"What to find in the documents."},
  "documents":{"type":"array","items":{"type":"string"},"description":"Optional document identifiers to search."}},
  "required":["query"],"additionalProperties":False}


def fRunTool(pArguments,pContext):
  if not rag_settings.fRead(pContext.vAgentId)["enabled"]:
    raise tool_registry.ToolFailure("Document retrieval is disabled for this agent.")
  try:
    if pContext.vRagRemaining is not None and pContext.vRagRemaining<1000:
      raise ValueError("The document retrieval budget for this run is exhausted. Use the passages already retrieved.")
    dResult=rag_search.fSearch(pContext.vAgentId,pArguments.get("query"),pArguments.get("documents"),pBudget=pContext.vRagRemaining)
    pContext.lRagSources.extend(dResult["sources"])
    vText=json.dumps(dResult,ensure_ascii=False)
    if pContext.vRagRemaining is not None:
      pContext.vRagRemaining-=len(vText.encode("utf-8"))
    return vText
  except (ValueError,OSError) as vError:
    raise tool_registry.ToolFailure(str(vError)) from vError
