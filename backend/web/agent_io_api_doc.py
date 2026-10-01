"""OpenAPI contracts for importing and exporting agents."""

from backend.core import agent_package, rag_settings


def fAddPaths(pPaths, pBuilder, pAgentParameter):
  dImport = {"name": "vImportId", "in": "path", "required": True,
             "schema": {"type": "string", "pattern": "^[a-f0-9]{32}$"}}
  dResponses = {"200": {"description": "Success"},
                "400": {"description": "Invalid package, chunk or state; the error says which"},
                "401": {"description": "Not logged in"}}
  lRoutes = [
    ("/api/admin/agent-imports", "post", "Begin uploading an agent .zip",
     "Reserves a place in /opt/boa/imports for a .zip exported from an agent. The "
     "file then travels in base64 chunks of chunk_bytes, in order.",
     {"type": "object", "required": ["name", "size"], "properties": {
       "name": {"type": "string", "example": "rag-consultant.zip"},
       "size": {"type": "integer", "minimum": 1, "maximum": agent_package.cMaxPackageBytes}}}, []),
    ("/api/admin/agent-imports/{vImportId}/upload", "put", "Upload a chunk of an agent .zip",
     "Chunks arrive in order; a chunk at the wrong offset is refused and the error says "
     "where to resume.",
     {"type": "object", "required": ["offset", "data"], "properties": {
       "offset": {"type": "integer", "minimum": 0},
       "data": {"type": "string", "format": "byte",
                "maxLength": 4 * ((rag_settings.cUploadChunkBytes + 2) // 3)}}}, [dImport]),
    ("/api/admin/agent-imports/{vImportId}/finish", "post", "Check an uploaded agent .zip",
     "Checks the whole package - names, sizes, agent.json, schedules, limits, library "
     "settings - and returns what it would install: tools (and the ones this server lacks), "
     "schedules, whether it carries memory, home files, library documents and a model. "
     "Nothing is installed.",
     {"type": "object", "properties": {"language": {"type": "string", "example": "es-ES"}}}, [dImport]),
    ("/api/admin/agent-imports/{vImportId}/install", "post", "Install a checked agent .zip",
     "Starts the installation in the background and answers 202. The agent is created "
     "switched off; a failure half-way deletes it again. Poll GET /agent-imports/{id}.",
     {"type": "object", "properties": {"name": {"type": "string"},
                                       "language": {"type": "string"}}}, [dImport]),
    ("/api/admin/agent-imports/{vImportId}", "get", "Read the state of an import",
     "uploading, ready, invalid, installing (with step, done and total), installed (with "
     "agent_id), failed or interrupted (with error).", None, [dImport]),
    ("/api/admin/agent-imports/{vImportId}", "delete", "Discard an import",
     "Removes the uploaded .zip. An installation in progress cannot be discarded.", None, [dImport]),
    ("/api/admin/agents/{vAgentId}/export/preview", "get", "What an export of this agent would carry",
     "The size of its memory, the home files an export would include, its library documents "
     "and its model, so the user can choose before downloading.", None, [pAgentParameter]),
    ("/api/admin/agents/{vAgentId}/export", "get", "Export an agent as a .zip",
     "agent.json, system-prompt.md and, on request, memory.md, the home files, the library "
     "originals with their information, and the provider and model. Never an API key, the "
     "agent's token, channel credentials, its chat or its run journal.",
     None, [pAgentParameter] + [
       {"name": vName, "in": "query", "schema": {"type": "string", "enum": ["0", "1"]}}
       for vName in ("memory", "home", "provider", "rag")]),
  ]
  for vPath, vMethod, vSummary, vDescription, dBody, lParameters in lRoutes:
    pPaths.setdefault(vPath, {}).update(pBuilder(
      vSummary, vDescription, vMethod, "Agents", pParameters=lParameters,
      pRequestBody=dBody, pResponses=dResponses))
