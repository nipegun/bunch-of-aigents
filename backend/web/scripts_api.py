"""Administrator access to scripts, with file operations delegated to the agent."""

from flask import Blueprint

from backend.core import agent_scripts, exec_client
from backend.web import api, auth

vScriptsBlueprint = Blueprint("scripts", __name__, url_prefix="/api/admin")
vScriptsBlueprint.before_request(api.fRefuseChangesFromElsewhere)


def fScriptResponse(pAgentId, pOperation, pArguments=None, pStatus=200):
  try:
    return api.fSuccess(exec_client.fAgentHome(pAgentId, pOperation, pArguments), pStatus)
  except (exec_client.ExecError, ValueError) as vError:
    dFailures = {
      agent_scripts.cConflictError: (409, "scriptChanged"),
      agent_scripts.cExistsError: (409, "scriptExists"),
      agent_scripts.cMissingError: (404, "scriptMissing"),
      "An empty script is not a script.": (400, "scriptEmpty"),
      "Script code must be UTF-8 text.": (400, "scriptNotText"),
      "That script is larger than %d bytes." % agent_scripts.cMaxScriptBytes: (413, "scriptTooLarge"),
    }
    vStatus, vCode = dFailures.get(str(vError), (400, None))
    return api.fFailure(vError, vStatus, pCode=vCode,
                        pParams={"limit": agent_scripts.cMaxScriptBytes})


@vScriptsBlueprint.route("/agents/<vAgentId>/scripts", methods=["GET"])
@auth.fRequireLogin
def fListAgentScripts(vAgentId):
  return fScriptResponse(vAgentId, "scripts_list")


@vScriptsBlueprint.route("/agents/<vAgentId>/scripts", methods=["POST"])
@auth.fRequireLogin
def fCreateAgentScript(vAgentId):
  dBody = api.fGetJsonBody()
  try:
    vName = agent_scripts.fValidateScriptName(dBody.get("name"))
  except ValueError as vError:
    return api.fFailure(vError, pCode="scriptNameInvalid")
  return fScriptResponse(vAgentId, "scripts_write", {
    "name": vName, "content": dBody.get("content"), "mode": "create"}, 201)


@vScriptsBlueprint.route("/agents/<vAgentId>/scripts/<vName>", methods=["GET"])
@auth.fRequireLogin
def fGetAgentScript(vAgentId, vName):
  return fScriptResponse(vAgentId, "scripts_read", {"name": vName})


@vScriptsBlueprint.route("/agents/<vAgentId>/scripts/<vName>", methods=["PUT"])
@auth.fRequireLogin
def fUpdateAgentScript(vAgentId, vName):
  dBody = api.fGetJsonBody()
  return fScriptResponse(vAgentId, "scripts_write", {
    "name": vName, "content": dBody.get("content"), "mode": "update",
    "revision": dBody.get("revision")})
