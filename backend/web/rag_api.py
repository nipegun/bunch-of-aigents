"""Authenticated RAG administration. Document data travels in bounded chunks."""

import base64
from flask import Blueprint, Response, request

from backend.core import exec_client, rag_settings
from backend.web import api, auth

vRagBlueprint=Blueprint("rag",__name__,url_prefix="/api/admin")
vRagBlueprint.before_request(api.fRefuseChangesFromElsewhere)


def fCall(pAgentId,pOperation,pArguments=None):
  try:
    return api.fSuccess(exec_client.fRag(pAgentId,pOperation,pArguments))
  except (exec_client.ExecError,ValueError) as vError:
    return api.fFailure(vError)


@vRagBlueprint.route("/rag",methods=["GET","PUT"])
@auth.fRequireLogin
def fRuntime():
  try:
    return api.fSuccess(exec_client.fRagRuntime(api.fGetJsonBody() if request.method=="PUT" else None))
  except (exec_client.ExecError,ValueError) as vError:
    return api.fFailure(vError)


@vRagBlueprint.route("/rag/models/<vModel>/install",methods=["POST"])
@auth.fRequireLogin
def fInstallModel(vModel):
  """Start downloading one embedding model of the catalogue; poll GET /rag."""
  try:
    return api.fSuccess({"download":exec_client.fInstallRagModel(vModel)},202)
  except (exec_client.ExecError,ValueError) as vError:
    return api.fFailure(vError)


@vRagBlueprint.route("/agents/<vAgentId>/rag",methods=["GET"])
@auth.fRequireLogin
def fOverview(vAgentId):
  try:
    dInfo=exec_client.fReadAgentInfo(vAgentId).get("info") or {}
    dModel=rag_settings.fSelectedModel()
    # The minimum similarity is on this model's scale; the tab says which
    # value was measured for it.
    return api.fSuccess({"settings":rag_settings.fValidateSettings(dInfo.get("rag") or {}),
      "embedding_model":{"id":dModel["id"],"name":dModel["name"],"min_similarity":dModel["min_similarity"]},
      **exec_client.fRag(vAgentId,"list",{"offset":request.args.get("offset",0)})})
  except (exec_client.ExecError,ValueError) as vError:
    return api.fFailure(vError)


@vRagBlueprint.route("/agents/<vAgentId>/rag/documents",methods=["POST"])
@auth.fRequireLogin
def fUpload(vAgentId):
  return fCall(vAgentId,"begin",api.fGetJsonBody())


@vRagBlueprint.route("/agents/<vAgentId>/rag/documents/<vDocumentId>/upload",methods=["PUT","POST"])
@auth.fRequireLogin
def fUploadPart(vAgentId,vDocumentId):
  dBody=api.fGetJsonBody()
  return fCall(vAgentId,"chunk" if request.method=="PUT" else "finish",{**dBody,"id":vDocumentId})


@vRagBlueprint.route("/agents/<vAgentId>/rag/documents/<vDocumentId>",methods=["PUT","DELETE"])
@auth.fRequireLogin
def fDocument(vAgentId,vDocumentId):
  dBody=api.fGetJsonBody()
  if request.method=="DELETE":
    dBody={"action":"delete"}
  return fCall(vAgentId,"action",{**dBody,"id":vDocumentId})


@vRagBlueprint.route("/agents/<vAgentId>/rag/documents/<vDocumentId>/content",methods=["GET"])
@auth.fRequireLogin
def fContent(vAgentId,vDocumentId):
  try:
    dFirst=exec_client.fRag(vAgentId,"content",{"id":vDocumentId})
  except exec_client.ExecError as vError:
    return api.fFailure(vError,404)
  def fIterate():
    dChunk=dFirst
    vOffset=0
    while True:
      vBytes=base64.b64decode(dChunk["data"],validate=True)
      if not vBytes:
        break
      yield vBytes
      vOffset+=len(vBytes)
      if vOffset>=dFirst["size"]:
        break
      dChunk=exec_client.fRag(vAgentId,"content",{"id":vDocumentId,"offset":vOffset})
  vResponse=Response(fIterate(),mimetype={".pdf":"application/pdf",".epub":"application/epub+zip"}.get(dFirst["format"],"text/plain"))
  vResponse.headers["Content-Length"]=str(dFirst["size"])
  vResponse.headers["Cache-Control"]="private, no-store"
  vResponse.headers.set("Content-Disposition","inline" if dFirst["format"]==".pdf" else "attachment",filename=dFirst["name"])
  return vResponse


@vRagBlueprint.route("/agents/<vAgentId>/rag/import",methods=["POST"])
@auth.fRequireLogin
def fImport(vAgentId):
  return fCall(vAgentId,"import")


@vRagBlueprint.route("/agents/<vAgentId>/rag/search",methods=["POST"])
@auth.fRequireLogin
def fSearch(vAgentId):
  return fCall(vAgentId,"search",api.fGetJsonBody())
