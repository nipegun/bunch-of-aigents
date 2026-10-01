"""List the calling agent's own documents."""

import json
from backend.core import rag_settings, rag_store, tool_registry

cToolName="rag.list"
cToolDescription="List the documents in your library, their identifiers, editions and processing status."
dToolSchema={"type":"object","properties":{
  "offset":{"type":"integer","description":"Number of documents to skip for pagination."}},
  "additionalProperties":False}


def fRunTool(pArguments,pContext):
  if not rag_settings.fRead(pContext.vAgentId)["enabled"]:
    raise tool_registry.ToolFailure("Document retrieval is disabled for this agent.")
  return json.dumps(rag_store.fList(pContext.vAgentId,pArguments.get("offset",0),50),ensure_ascii=False)
