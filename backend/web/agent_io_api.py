"""Importing an agent from a .zip, and exporting one into a .zip.

Creating from a template of the templates repository is POST /agents with
`template`, in api.py; this blueprint holds the rest. The .zip travels in the
same bounded base64 chunks as a library document, is checked whole before the
user is shown what it would install, and is installed in the background.
"""

from flask import Blueprint, Response, request, stream_with_context

from backend.core import agent_io, agent_package, exec_client
from backend.web import api, auth

vAgentIoBlueprint = Blueprint("agent_io", __name__, url_prefix="/api/admin")
vAgentIoBlueprint.before_request(api.fRefuseChangesFromElsewhere)

lExpectedErrors = (exec_client.ExecError, ValueError, OSError)


def fJobForBrowser(pJob):
  """The job without its bookkeeping."""
  return {vKey: pJob[vKey] for vKey in ("state", "size", "received", "summary", "step",
                                        "done", "total", "agent_id", "error") if vKey in pJob}


@vAgentIoBlueprint.route("/agent-imports", methods=["POST"])
@auth.fRequireLogin
def fBeginImport():
  dBody = api.fGetJsonBody()
  try:
    return api.fSuccess(agent_io.fBeginImport(dBody.get("name"), dBody.get("size")), 201)
  except lExpectedErrors as vError:
    return api.fFailure(vError)


@vAgentIoBlueprint.route("/agent-imports/<vImportId>/upload", methods=["PUT"])
@auth.fRequireLogin
def fUploadImport(vImportId):
  dBody = api.fGetJsonBody()
  try:
    return api.fSuccess(agent_io.fUploadImportChunk(vImportId, dBody.get("offset"), dBody.get("data")))
  except lExpectedErrors as vError:
    return api.fFailure(vError)


@vAgentIoBlueprint.route("/agent-imports/<vImportId>/finish", methods=["POST"])
@auth.fRequireLogin
def fFinishImport(vImportId):
  dBody = api.fGetJsonBody()
  try:
    return api.fSuccess({"summary": agent_io.fFinishImport(vImportId, str(dBody.get("language") or ""))})
  except lExpectedErrors as vError:
    return api.fFailure(vError)


@vAgentIoBlueprint.route("/agent-imports/<vImportId>/install", methods=["POST"])
@auth.fRequireLogin
def fInstallImport(vImportId):
  dBody = api.fGetJsonBody()
  try:
    dJob = agent_io.fStartImport(vImportId, str(dBody.get("name") or ""), str(dBody.get("language") or ""))
    return api.fSuccess(fJobForBrowser(dJob), 202)
  except lExpectedErrors as vError:
    return api.fFailure(vError)


@vAgentIoBlueprint.route("/agent-imports/<vImportId>", methods=["GET", "DELETE"])
@auth.fRequireLogin
def fImport(vImportId):
  try:
    if request.method == "DELETE":
      return api.fSuccess(agent_io.fCancelImport(vImportId))
    return api.fSuccess(fJobForBrowser(agent_io.fReadJob(vImportId)))
  except lExpectedErrors as vError:
    return api.fFailure(vError, 404 if "Unknown import" in str(vError) else 400)


@vAgentIoBlueprint.route("/agents/<vAgentId>/export/preview", methods=["GET"])
@auth.fRequireLogin
def fPreviewExport(vAgentId):
  try:
    return api.fSuccess(agent_io.fPreviewExport(vAgentId))
  except lExpectedErrors as vError:
    return api.fFailure(vError)


@vAgentIoBlueprint.route("/agents/<vAgentId>/export", methods=["GET"])
@auth.fRequireLogin
def fExport(vAgentId):
  dOptions = {vKey: request.args.get(vKey) == "1" for vKey in ("memory", "home", "provider", "rag")}
  try:
    dInfo = exec_client.fReadAgentInfo(vAgentId).get("info") or {}
    vStream = agent_io.fExportAgent(vAgentId, pMemory=dOptions["memory"], pHome=dOptions["home"],
                                    pProvider=dOptions["provider"], pRag=dOptions["rag"])
    # The first piece is produced here, before the headers go: whatever fails
    # while reading the agent is still an error the page can show, not a
    # download that stops at zero bytes.
    vFirst = next(vStream)
  except lExpectedErrors as vError:
    return api.fFailure(vError)

  def fBody():
    yield vFirst
    yield from vStream

  return Response(stream_with_context(fBody()), mimetype="application/zip", headers={
    "Content-Disposition": 'attachment; filename="%s"' % (agent_io.fExportFileName(dInfo),),
    "Cache-Control": "no-store",
  })
