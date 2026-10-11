"""OpenAPI contracts for local retrieval and resumable document uploads."""

from backend.core import rag_settings


def fSettingsSchema():
  return {"type":"object","properties":{
    "enabled":{"type":"boolean","default":False},
    "mode":{"type":"string","enum":["mixed","documental","verified"],"default":"mixed",
      "description":"mixed: documents and general knowledge. documental: the model must call "
        "rag.search before answering, and a run that retrieves nothing answers with a fixed "
        "sentence. verified: as documental, and every paragraph must cite a retrieved passage "
        "that backs it; the rest is removed before the answer is delivered."},
    "max_file_mb":{"type":"integer","minimum":1,"maximum":1024,"default":128},
    "max_storage_mb":{"type":"integer","minimum":1,"maximum":1048576,"default":2048},
    "max_chunks":{"type":"integer","minimum":100,"maximum":2000000,"default":200000},
    "context_characters":{"type":"integer","minimum":1000,"maximum":64000,"default":16000},
    "results":{"type":"integer","minimum":1,"maximum":30,"default":8},
    "min_similarity":{"type":"number","minimum":0,"maximum":1,
      "description":"Below this similarity a passage is dropped unless it matches the query's words. Each "
        "embedding model has its own scale: the default is the value measured for the model in use "
        "(0.2 for EmbeddingGemma, 0.35 for Qwen3-Embedding)."},
    "ocr":{"type":"boolean","default":True},
    "ocr_languages":{"type":"string","default":"eng+spa"},
    "chunk_tokens":{"type":"integer","minimum":64,"maximum":440,"default":320}},
    "additionalProperties":False}


def fAddPaths(pPaths,pBuilder,pAgentParameter):
  dDocument={"name":"vDocumentId","in":"path","required":True,
    "schema":{"type":"string","pattern":"^[a-f0-9]{32}$"}}
  vBase="/api/admin/agents/{vAgentId}/rag"
  lRoutes=[
    ("/api/admin/rag","get","Read local embedding status",None,[]),
    ("/api/admin/rag","put","Configure local document processing",{
      "type":"object","properties":{"threads":{"type":"integer","minimum":1,"maximum":32},
      "workers":{"type":"integer","minimum":1,"maximum":4},"ocr_languages":{"type":"string"},
      "model":{"type":"string","enum":[v["id"] for v in rag_settings.fReadModelCatalogue()["models"]],
        "description":"The embedding model, for every agent. It must be downloaded first. Changing it "
          "restarts the engine and indexes every library again; until each document is done, it is "
          "found only by the words of a query."}}},[]),
    (vBase,"get","List an agent's documents",None,[pAgentParameter,
      {"name":"offset","in":"query","schema":{"type":"integer","minimum":0}}]),
    (vBase+"/documents","post","Begin a document upload",{"type":"object","required":["name","size"],
      "properties":{"name":{"type":"string"},"size":{"type":"integer","minimum":1},"replaces":{"type":"string"}}},[pAgentParameter]),
    (vBase+"/documents/{vDocumentId}/upload","put","Upload a document chunk",{"type":"object","required":["offset","data"],
      "properties":{"offset":{"type":"integer","minimum":0},"data":{"type":"string","format":"byte",
        "maxLength":4*((rag_settings.cUploadChunkBytes+2)//3)}}},[pAgentParameter,dDocument]),
    (vBase+"/documents/{vDocumentId}/upload","post","Finish a document upload",{"type":"object"},[pAgentParameter,dDocument]),
    (vBase+"/documents/{vDocumentId}","put","Update a library document",{"type":"object","required":["action"],
      "properties":{"action":{"type":"string","enum":["metadata","reindex","retry","cancel"]},
        "metadata":{"type":"object","properties":{**{"year":{"type":"string","pattern":"^[0-9]{0,4}$",
          "description":"Publication year; empty to clear it."}},**{v:{"type":"string","maxLength":500}
          for v in ("title","subtitle","author","version","language","tags")}}}}},[pAgentParameter,dDocument]),
    (vBase+"/documents/{vDocumentId}","delete","Delete a library document",None,[pAgentParameter,dDocument]),
    (vBase+"/documents/{vDocumentId}/content","get","Download a source document",None,[pAgentParameter,dDocument]),
    (vBase+"/import","post","Import the agent's inbox",{"type":"object"},[pAgentParameter]),
    (vBase+"/search","post","Search an agent's library",{"type":"object","required":["query"],
      "properties":{"query":{"type":"string","minLength":1,"maxLength":16000},
      "documents":{"type":"array","items":{"type":"string"}},
      "filters":{"type":"object","properties":{v:{"type":"string"} for v in ("language","version","author","tags")}}}},[pAgentParameter]),
  ]
  pPaths["/api/admin/rag/models/{vModel}/install"]=pBuilder("Download a local embedding model",
    "Queue a verified download of one embedding model of the catalogue. Poll GET /api/admin/rag for "
    "progress, then choose it with PUT /api/admin/rag.","post","Agents",
    pParameters=[{"name":"vModel","in":"path","required":True,"schema":{"type":"string",
      "enum":[v["id"] for v in rag_settings.fReadModelCatalogue()["models"]]}}],
    pResponses={"202":{"description":"Success"},"400":{"description":"Invalid model"},
                "401":{"description":"Not logged in"}})
  for vPath,vMethod,vSummary,dBody,lParameters in lRoutes:
    pPaths.setdefault(vPath,{}).update(pBuilder(vSummary,
      "Private per-agent document retrieval. Extraction and embeddings run locally. "
      "Uploads use bounded base64 chunks; indexing continues in the background. "
      "Only the agent's configured answer model receives retrieved passages.",
      vMethod,"Agents",pParameters=lParameters,pRequestBody=dBody,
      pResponses={"200":{"description":"Success"},"400":{"description":"Invalid document, settings or unavailable local engine"},
                  "401":{"description":"Not logged in"}}))
