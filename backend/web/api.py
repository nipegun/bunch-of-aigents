"""The HTTP API, entirely under /api/admin/.

Every endpoint here needs a session. There is one account, so everything the
API exposes is administrative: creating agents, editing their configuration,
installing crontabs, moving cards, configuring channels.

Nothing in this module touches an agent home directory or a system user
directly. Anything privileged goes through the executor daemon, which is why
the web application can run unprivileged and stay that way.
"""

import socket
from urllib.parse import urlsplit

from flask import Blueprint, Response, jsonify, request, send_file

from backend.core import agents
from backend.core import agent_templates
from backend.core import api_keys
from backend.core import audio_inbox, audio_transcription
from backend.core import channels
from backend.core import exec_client
from backend.core import kanban
from backend.core import paths
from backend.core import provider_models
from backend.core import skills
from backend.core import system_info
from backend.core import themes
from backend.core import tool_registry
from backend.providers import factory
from backend.web import auth

# How long the status bar waits for the agent API to answer. Short: this runs
# on a timer in the browser, and a socket on the same machine either accepts at
# once or is not there.
cStatusProbeSeconds = 2

vApiBlueprint = Blueprint("api", __name__, url_prefix="/api/admin")


@vApiBlueprint.route("/audio", methods=["GET"])
@auth.fRequireLogin
def fGetAudioSettings():
  return fSuccess(audio_transcription.fDescribeSettings())


@vApiBlueprint.route("/audio", methods=["PUT"])
@auth.fRequireLogin
def fUpdateAudioSettings():
  try:
    dSettings = audio_transcription.fSaveSettings(fGetJsonBody())
    return fSuccess({"settings": dSettings})
  except ValueError as vError:
    return fFailure(str(vError))


@vApiBlueprint.route("/audio/models/<vModel>/install", methods=["POST"])
@auth.fRequireLogin
def fInstallAudioModel(vModel):
  try:
    return fSuccess({"download": exec_client.fInstallWhisperModel(vModel)}, 202)
  except (ValueError, exec_client.ExecError) as vError:
    return fFailure(str(vError))


# The one place in the backend where a parameter has no `p` prefix.
#
# Flask passes a URL variable to its view by KEYWORD, using the name written
# in the rule: `@route("/agents/<vAgentId>")` calls `fGetAgent(vAgentId=...)`.
# Renaming the parameter to `pvAgentId` without renaming the rule is a
# TypeError on the first request, and renaming the rule as well would change
# the names in the OpenAPI document and in every URL the interface builds.
#
# Measured, because it was tried: seven endpoints answered
# "fUpdateAgent() got an unexpected keyword argument 'vAgentId'".
#
# So the view functions keep the framework's names and everything else in the
# backend carries the `p`. Same reasoning as `self`, which no convention here
# applies to either.


def fSuccess(pPayload=None, pStatusCode=200):
  """Return a successful JSON response."""
  dBody = {"ok": True}
  dBody.update(pPayload or {})
  return jsonify(dBody), pStatusCode


def fFailure(pMessage, pStatusCode=400, pCode="", pParams=None):
  """Return a failed JSON response.

  `error` is English prose and is what gets shown when there is nothing
  better: a provider's own words, a mail server's refusal, anything that came
  from outside this application and should not have a translation invented for
  it.

  `code` is for the failures the interface has a wording of its own for. The
  code and its parameters travel instead of a sentence, and the browser writes
  the sentence in the user's language - the same shape a ceiling name or a
  chat reason already travels in. Without it, "The password must be at least
  12 characters long" appeared in the middle of a Spanish interface, because
  the only thing that crossed the wire was the English sentence.
  """
  dBody = {"ok": False, "error": str(pMessage)}
  if pCode:
    dBody["code"] = pCode
    dBody["params"] = pParams or {}
  return jsonify(dBody), pStatusCode


# Failures the interface writes itself. The name travels, never the sentence.
cErrorPasswordTooShort = "passwordTooShort"
cErrorWrongCurrentPassword = "wrongCurrentPassword"
cErrorInvalidEmail = "invalidEmail"
cErrorSettingsNotAnObject = "settingsNotAnObject"
cErrorInfoNotAnObject = "infoNotAnObject"
cErrorPartiallySaved = "partiallySaved"


# Methods that change something. A GET is answered to anybody logged in; one
# of these is answered only to this site's own pages.
lMutatingMethods = ("POST", "PUT", "PATCH", "DELETE")


def fRequestComesFromThisSite():
  """Whether a request that changes something came from this site's own pages.

  The session cookie is `SameSite=Lax`, which keeps a request from another
  SITE from carrying it. It does not keep out another ORIGIN on the same site:
  an agent with bash.run can serve a page on this very host, on a port of its
  own, and a link to it from a chat answer is one click away. A form there
  posting to `/api/admin/agents/000/run` is a same-site request, the cookie
  travels, and the run starts. Measured against the browser rules rather than
  against a machine: the request is a simple POST with no body, so no
  preflight stands in its way either.

  What tells the two apart is where the browser says the request came from.
  `Origin` is on every cross-origin request and every POST, and has to name
  this host and port exactly; `Sec-Fetch-Site` is on everything a current
  browser sends, and has to say `same-origin`. A request with neither is not
  a browser's - a script, the tests - and is left to the login to judge.
  """
  vOrigin = request.headers.get("Origin", "")
  if vOrigin:
    return urlsplit(vOrigin).netloc.lower() == request.host.lower()
  vSite = request.headers.get("Sec-Fetch-Site", "")
  if vSite:
    return vSite == "same-origin"
  return True


@vApiBlueprint.before_request
def fRefuseChangesFromElsewhere():
  """Refuse a request that changes something and came from another origin."""
  if request.method in lMutatingMethods and not fRequestComesFromThisSite():
    return fFailure("Refused: this request did not come from this site.", 403)
  return None


def fGetJsonBody():
  """Return the request body as a dictionary, never None."""
  dBody = request.get_json(silent=True)
  return dBody if isinstance(dBody, dict) else {}


# ---------------------------------------------------------------- agents ----

# The tool that lets an agent find out a card exists. Without it, assigning it
# one is writing to somebody who never opens their post.
cKanbanListTool = "kanban.list_cards"


def fCanReadKanban(pAgentId):
  """Return whether this agent would ever see a card assigned to it.

  Two things can stop it, and the runner applies both: the tool has to be
  granted, and the agent's kanban switch has to be on. The board is not put
  into the prompt - an agent reads it by calling the tool or not at all.
  """
  try:
    dInfo = exec_client.fReadAgentInfo(pAgentId).get("info") or {}
  except exec_client.ExecError:
    # The executor is down and this is a hint, not a permission check. Saying
    # "this agent cannot read the board" because a daemon is restarting would
    # be worse than saying nothing.
    return True
  if not dInfo.get("kanban_enabled", True):
    return False
  return cKanbanListTool in (dInfo.get("tools") or [])


@vApiBlueprint.route("/agents", methods=["GET"])
@auth.fRequireLogin
def fListAgents():
  """List every agent, with its run totals and whether it is working now.

  `running` is always included: it costs one call to the executor for the
  whole list, not one per agent, which is what lets the sidebar ask for it on
  a timer to spin the ring around a busy agent.

  With `?kanban=1` each agent also carries `reads_kanban`: whether it would
  ever see a card assigned to it. That costs one call to the executor per
  agent, so it is asked for only by the board, which is the one page where the
  answer changes what the user should do.
  """
  lAgents = agents.fListIndexedAgents()
  try:
    dSummaries = exec_client.fReadUsageSummary().get("summaries") or {}
  except exec_client.ExecError:
    # The sidebar must still draw when the executor is down.
    dSummaries = {}
  try:
    lRunning = exec_client.fListRunningAgents().get("agent_ids") or []
  except exec_client.ExecError:
    # With the executor down nothing can be started either, so reporting
    # nobody busy is both the safe answer and very nearly the true one. A ring
    # spinning for an agent that cannot possibly be running would be a lie.
    lRunning = []
  sRunning = set(lRunning)
  for dAgent in lAgents:
    dAgent["usage"] = dSummaries.get(dAgent["id"]) or {}
    dAgent["running"] = dAgent["id"] in sRunning

  if request.args.get("kanban"):
    for dAgent in lAgents:
      dAgent["reads_kanban"] = fCanReadKanban(dAgent["id"])
  return fSuccess({"agents": lAgents})


@vApiBlueprint.route("/agents", methods=["POST"])
@auth.fRequireLogin
def fCreateAgent():
  """Create an agent. This is what the + button calls.

  With `template`, the prompt, tools, ceilings and schedule come from an
  example agent in `backend/agents/examples/`. The template is read HERE and not sent
  by the browser: what a template contains is the server's business, and a
  request that could name its own tools and schedule would let the interface
  hand an agent a permission the user never ticked.
  """
  dBody = fGetJsonBody()
  dTemplate = {}
  vTemplateName = dBody.get("template")
  if vTemplateName:
    dTemplate = agent_templates.fReadTemplate(vTemplateName) or {}
    if not dTemplate:
      return fFailure("Unknown example agent: %r" % (vTemplateName,), 404)

  dLimits = {vKey: dTemplate[vKey] for vKey in agents.dDefaultLimits
             if isinstance(dTemplate.get(vKey), int)}
  try:
    dResult = exec_client.fCreateAgent(
      # The name can still be the user's: an example is a starting point, and
      # two copies of os-watcher have to be able to coexist.
      pName=dBody.get("name") or dTemplate.get("name"),
      pDescription=dBody.get("description") or dTemplate.get("description", ""),
      pProvider=dBody.get("provider") or "ollama",
      pModel=dBody.get("model", ""),
      pBaseUrl=dBody.get("base_url", ""),
      pSystemPrompt=dBody.get("system_prompt") or dTemplate.get("system_prompt", ""),
      pTools=dTemplate.get("tools") if dTemplate else None,
      pSkills=dTemplate.get("skills") if dTemplate else None,
      pLimits=dLimits or None,
      pCrontab=dTemplate.get("crontab", ""),
      # Every example ships switched off: it has no model yet, and an agent
      # that wakes up hourly to fail is worse than one that waits.
      pEnabled=dTemplate.get("enabled") if dTemplate else None,
    )
  except exec_client.ExecError as vError:
    return fFailure(vError)
  return fSuccess(dResult, 201)


@vApiBlueprint.route("/agent-templates", methods=["GET"])
@auth.fRequireLogin
def fListAgentTemplates():
  """List the example agents offered when creating one.

  The system prompt is left out: it is long, the list is only a menu, and the
  browser never needs it - creating from a template names the template and the
  server reads the file.
  """
  return fSuccess({"templates": [
    {vKey: dTemplate[vKey] for vKey in
     ("id", "name", "description", "tools", "crontab")}
    for dTemplate in agent_templates.fListTemplates()
  ]})


@vApiBlueprint.route("/agents/<vAgentId>", methods=["GET"])
@auth.fRequireLogin
def fGetAgent(vAgentId):
  """Return one agent's full configuration."""
  try:
    dInfo = exec_client.fReadAgentInfo(vAgentId).get("info") or {}
    vSystemPrompt = exec_client.fReadSystemPrompt(vAgentId).get("system_prompt", "")
    vCrontab = exec_client.fReadCrontab(vAgentId).get("crontab", "")
    vMemory = exec_client.fReadMemory(vAgentId).get("memory", "")
    dUsage = exec_client.fReadUsageSummary(vAgentId).get("summaries") or {}
  except exec_client.ExecError as vError:
    return fFailure(vError, 404)
  return fSuccess({
    "info": dInfo,
    "system_prompt": vSystemPrompt,
    "crontab": vCrontab,
    "memory": vMemory,
    "usage": dUsage.get(paths.fNormalizeAgentId(vAgentId)) or {},
  })


@vApiBlueprint.route("/agents/<vAgentId>", methods=["PUT"])
@auth.fRequireLogin
def fUpdateAgent(vAgentId):
  """Update one agent's configuration.

  Four destinations, and no transaction that can span them: two files in a
  directory only root can write, a system crontab, and the agent's memory.
  A failure part of the way through therefore leaves the earlier parts
  applied, and there is no honest way to undo a crontab that cron has already
  accepted.

  So the answer says which parts went in. It used to be a bare error, which
  read as "nothing was saved" for a request where the name, the prompt and the
  schedule had all been written and only the memory had failed - and the only
  way to find out was to reload the page and compare.

  The order is deliberate: the crontab is the part most likely to be refused,
  because cron parses it and the user typed it, so it goes first. A refusal
  then leaves nothing else already written.
  """
  dBody = fGetJsonBody()
  if "info" in dBody and not isinstance(dBody["info"], dict):
    return fFailure(ValueError("info must be an object"),
                    pCode=cErrorInfoNotAnObject)

  lApplied = []
  lParts = [
    ("crontab", lambda: exec_client.fWriteCrontab(vAgentId, dBody["crontab"])),
    ("info", lambda: exec_client.fWriteAgentInfo(vAgentId, dBody["info"])),
    ("system_prompt",
     lambda: exec_client.fWriteSystemPrompt(vAgentId, dBody["system_prompt"])),
    ("memory", lambda: exec_client.fWriteMemory(vAgentId, dBody["memory"])),
  ]

  for vName, fWrite in lParts:
    if vName not in dBody:
      continue
    try:
      fWrite()
    except exec_client.ExecError as vError:
      if not lApplied:
        return fFailure(vError)
      return fFailure(
        ValueError("%s. What had already been saved: %s. The rest was not."
                   % (vError, ", ".join(lApplied))),
        pCode=cErrorPartiallySaved,
        pParams={"reason": str(vError), "saved": ", ".join(lApplied)})
    lApplied.append(vName)

  try:
    dInfo = exec_client.fReadAgentInfo(vAgentId).get("info") or {}
  except exec_client.ExecError as vError:
    return fFailure(vError)
  return fSuccess({"info": dInfo, "saved": lApplied})


@vApiBlueprint.route("/agents/<vAgentId>", methods=["DELETE"])
@auth.fRequireLogin
def fDeleteAgent(vAgentId):
  """Delete one agent, its system user, its home and its crontab."""
  try:
    dResult = exec_client.fDeleteAgent(vAgentId)
    audio_inbox.fRemoveAgentAudio(paths.fNormalizeAgentId(vAgentId), pIncludePending=True)
  except exec_client.ExecError as vError:
    return fFailure(vError)
  return fSuccess(dResult)


@vApiBlueprint.route("/agents/<vAgentId>/run", methods=["POST"])
@auth.fRequireLogin
def fRunAgentNow(vAgentId):
  """Start one agent run immediately."""
  try:
    dResult = exec_client.fRunNow(vAgentId)
  except exec_client.ExecError as vError:
    return fFailure(vError)
  return fSuccess(dResult, 202)


@vApiBlueprint.route("/agents/<vAgentId>/journal", methods=["GET"])
@auth.fRequireLogin
def fGetAgentJournal(vAgentId):
  """Return one agent's run journal."""
  try:
    dResult = exec_client.fReadRunJournal(
      vAgentId, request.args.get("limit", type=int)
    )
  except exec_client.ExecError as vError:
    return fFailure(vError, 404)
  return fSuccess(dResult)


# ---------------------------------------------------------------- memory ----

@vApiBlueprint.route("/agents/<vAgentId>/memory", methods=["GET"])
@auth.fRequireLogin
def fGetMemory(vAgentId):
  """Return one agent's memory."""
  try:
    dResult = exec_client.fReadMemory(vAgentId)
  except exec_client.ExecError as vError:
    return fFailure(vError, 404)
  return fSuccess(dResult)


@vApiBlueprint.route("/agents/<vAgentId>/memory", methods=["PUT"])
@auth.fRequireLogin
def fUpdateMemory(vAgentId):
  """Replace one agent's memory.

  It is the agent's memory, but a wrong fact it keeps acting on is something
  the user has to be able to correct.
  """
  dBody = fGetJsonBody()
  try:
    dResult = exec_client.fWriteMemory(vAgentId, dBody.get("memory", ""))
  except exec_client.ExecError as vError:
    return fFailure(vError)
  return fSuccess(dResult)


# ------------------------------------------------------------------ chat ----

@vApiBlueprint.route("/agents/<vAgentId>/chat", methods=["GET"])
@auth.fRequireLogin
def fGetChat(vAgentId):
  """Return one agent's conversation.

  `pending` says whether a question is still being answered, which is what the
  interface polls on rather than guessing from timing.
  """
  try:
    dResult = exec_client.fReadChat(vAgentId, request.args.get("limit", type=int))
    for dMessage in dResult.get("messages", []):
      vAudioId = dMessage.get("audio_id")
      if isinstance(vAudioId, str) and audio_inbox.cJobPattern.fullmatch(vAudioId):
        dJob = audio_inbox.fReadJob(vAudioId)
        dMessage["audio_available"] = bool(dJob and dJob["agent_id"] == paths.fNormalizeAgentId(vAgentId)
                                           and (audio_inbox.fGetJobDirectory(vAudioId) / "playback.ogg").is_file())
  except exec_client.ExecError as vError:
    return fFailure(vError, 404)
  return fSuccess(dResult)


@vApiBlueprint.route("/agents/<vAgentId>/audio/<vAudioId>", methods=["GET"])
@auth.fRequireLogin
def fGetChatAudio(vAgentId, vAudioId):
  try:
    vAgentId = paths.fNormalizeAgentId(vAgentId)
    dJob = audio_inbox.fReadJob(vAudioId)
    if not dJob or dJob["agent_id"] != vAgentId:
      return fFailure("Audio not found.", 404)
    dChat = exec_client.fReadChat(vAgentId)
    if not any(dMessage.get("audio_id") == vAudioId for dMessage in dChat.get("messages", [])):
      return fFailure("Audio not found.", 404)
    vPath = audio_inbox.fGetJobDirectory(vAudioId) / "playback.ogg"
    if not vPath.is_file() or vPath.is_symlink():
      return fFailure("Audio not retained.", 404)
    vResponse = send_file(vPath, mimetype="audio/ogg", conditional=True, max_age=0)
    vResponse.headers["Cache-Control"] = "private, no-store"
    vResponse.headers["X-Content-Type-Options"] = "nosniff"
    return vResponse
  except (ValueError, exec_client.ExecError):
    return fFailure("Audio not found.", 404)


@vApiBlueprint.route("/agents/<vAgentId>/attachments/<vAttachmentId>", methods=["GET"])
@auth.fRequireLogin
def fGetChatAttachment(vAgentId, vAttachmentId):
  """Stream a private image from this agent's chat, with no public file URL."""
  try:
    dFirst = exec_client.fReadChatAttachment(vAgentId, vAttachmentId)
  except exec_client.AttachmentUnavailable as vError:
    return fFailure(vError, 404)
  except (exec_client.ExecError, ValueError) as vError:
    return fFailure(vError, 503)
  vResponse = Response(
    exec_client.fIterChatAttachment(vAgentId, vAttachmentId, dFirst),
    mimetype="image/png")
  vResponse.headers["Content-Length"] = str(dFirst["size"])
  vResponse.headers["Cache-Control"] = "private, no-store"
  vResponse.headers["X-Content-Type-Options"] = "nosniff"
  vResponse.headers.set("Content-Disposition", "inline",
                         filename=dFirst["attachment"]["name"])
  return vResponse


@vApiBlueprint.route("/agents/<vAgentId>/chat", methods=["POST"])
@auth.fRequireLogin
def fSendChatMessage(vAgentId):
  """Send a message to an agent and start the run that answers it.

  Returns as soon as the run is started: an answer can take minutes, so the
  interface polls the GET above rather than holding a request open.
  """
  dBody = fGetJsonBody()
  try:
    dResult = exec_client.fSendChatMessage(vAgentId, dBody.get("message"))
  except exec_client.ExecError as vError:
    return fFailure(vError)
  return fSuccess(dResult, 202)


@vApiBlueprint.route("/agents/<vAgentId>/chat", methods=["DELETE"])
@auth.fRequireLogin
def fClearChat(vAgentId):
  """Delete one agent's conversation."""
  try:
    dResult = exec_client.fClearChat(vAgentId)
    audio_inbox.fRemoveAgentAudio(paths.fNormalizeAgentId(vAgentId))
  except exec_client.ExecError as vError:
    return fFailure(vError)
  return fSuccess(dResult)


# ---------------------------------------------------------------- kanban ----

@vApiBlueprint.route("/kanban", methods=["GET"])
@auth.fRequireLogin
def fGetBoard():
  """Return the whole board."""
  return fSuccess({
    "board": kanban.fGetBoard(request.args.get("limit", type=int)),
    "counts": kanban.fCountByState(),
  })


@vApiBlueprint.route("/kanban/cards", methods=["POST"])
@auth.fRequireLogin
def fCreateCard():
  """Add a card as the user.

  `run_at` is when the owner should be woken for it: "now" for straight away, a
  UTC time for later, or nothing at all to leave the card waiting on the board.
  The buzzer does the waking; nothing is started from here, so there is one
  path into a run rather than two that can disagree.

  The word "now" travels to the board as a word. Turning it into a timestamp
  here would lose the only thing that tells the two kinds of time apart once the
  moment has passed, which is exactly when the agent is told about the card.
  """
  dBody = fGetJsonBody()
  try:
    dCard = kanban.fAddCard(
      pTitle=dBody.get("title"),
      pBody=dBody.get("body", ""),
      pState=dBody.get("state") or kanban.cStateTodo,
      pOwnerAgent=dBody.get("owner_agent") or None,
      pCreatedBy="user",
      pNote=dBody.get("note", ""),
      pRunAt=dBody.get("run_at"),
    )
  except kanban.KanbanError as vError:
    return fFailure(vError)
  return fSuccess({"card": dCard}, 201)


@vApiBlueprint.route("/kanban/cards/<int:vCardId>/schedule", methods=["PUT"])
@auth.fRequireLogin
def fScheduleCard(vCardId):
  """Set or clear when a card should wake its owner.

  "now" reaches the board as a word, for the reason given above.
  """
  dBody = fGetJsonBody()
  try:
    dCard = kanban.fSetCardSchedule(vCardId, dBody.get("run_at"), "user",
                                    dBody.get("note", ""))
  except kanban.KanbanError as vError:
    return fFailure(vError, 404)
  return fSuccess({"card": dCard})


@vApiBlueprint.route("/kanban/cards/<int:vCardId>", methods=["PUT"])
@auth.fRequireLogin
def fMoveCard(vCardId):
  """Move a card as the user. The user may move any card."""
  dBody = fGetJsonBody()
  try:
    dCard = kanban.fMoveCard(
      vCardId, dBody.get("state"), "user", dBody.get("note", "")
    )
  except kanban.KanbanError as vError:
    return fFailure(vError)
  return fSuccess({"card": dCard})


@vApiBlueprint.route("/kanban/cards/<int:vCardId>", methods=["DELETE"])
@auth.fRequireLogin
def fDeleteCard(vCardId):
  """Delete a card as the user. The user may delete any card."""
  if not kanban.fDeleteCard(vCardId, "user"):
    return fFailure("There is no card with id %d" % (vCardId,), 404)
  return fSuccess({"card_id": vCardId, "deleted": True})


@vApiBlueprint.route("/kanban/cards/<int:vCardId>/events", methods=["GET"])
@auth.fRequireLogin
def fGetCardEvents(vCardId):
  """Return the history of one card."""
  return fSuccess({"events": kanban.fListCardEvents(vCardId)})


@vApiBlueprint.route("/kanban/deleted", methods=["GET"])
@auth.fRequireLogin
def fGetDeletedCards():
  """Return recently deleted cards."""
  return fSuccess({"deleted": kanban.fListDeletedCards()})


# ----------------------------------------------------------------- tools ----

@vApiBlueprint.route("/tools", methods=["GET"])
@auth.fRequireLogin
def fListTools():
  """List every tool installed on the server."""
  dTools, lErrors = tool_registry.fLoadAllTools()
  lToolSummaries = []
  for vName in sorted(dTools):
    vModule = dTools[vName]
    lToolSummaries.append({
      "name": vName,
      "description": vModule.cToolDescription,
      "schema": vModule.dToolSchema,
    })
  return fSuccess({"tools": lToolSummaries, "errors": lErrors})


# ---------------------------------------------------------------- skills ----

@vApiBlueprint.route("/skills", methods=["GET"])
@auth.fRequireLogin
def fListSkills():
  """List every skill installed on the server.

  Names and descriptions, never bodies: this fills a list of checkboxes, and
  a skill is a page or two of prose that nothing in the browser would do
  anything with.
  """
  return fSuccess({"skills": skills.fListSkills()})


# -------------------------------------------------------------- providers ----

@vApiBlueprint.route("/providers", methods=["GET"])
@auth.fRequireLogin
def fListProviders():
  """List every provider adapter and whether it can be picked for an agent.

  A cloud provider with no key would fail on its first run, so it is not worth
  offering: `selectable` says which ones are worth picking, and the interface
  lists those. It is a filter, not a rule - an agent can still be configured
  with any of them, because a key can also live in the agent's own home, where
  the web application cannot see it.
  """
  lProviders = []
  for vName in factory.fListProviderNames():
    vModuleName, vClassName = factory.dProviderRegistry[vName]
    vSelfHosted = factory.fIsSelfHosted(vName)
    vKeyConfigured = bool(api_keys.fDescribe(vName).get("configured"))
    try:
      vModule = __import__(
        "backend.providers.%s" % (vModuleName,), fromlist=[vClassName]
      )
      vClass = getattr(vModule, vClassName)
      dCatalogue = provider_models.fReadCatalogue(vName)
      lProviders.append({
        "name": vName,
        "default_model": vClass.cDefaultModel,
        "default_base_url": vClass.cDefaultBaseUrl,
        "self_hosted": vSelfHosted,
        "key_configured": vKeyConfigured,
        "selectable": vSelfHosted or vKeyConfigured,
        "available": True,
        # Suggestions for the model field, read from
        # /opt/boa/config/providers/<name>.json. The field still accepts
        # anything typed into it.
        "models": dCatalogue.get("models") or [],
        "documentation": dCatalogue.get("documentation", ""),
        "note": dCatalogue.get("note", ""),
      })
    except ImportError as vError:
      lProviders.append({
        "name": vName, "available": False, "error": str(vError),
        "self_hosted": vSelfHosted,
        "key_configured": vKeyConfigured,
        # An adapter whose SDK is missing cannot run at all, key or no key.
        "selectable": False,
      })
  return fSuccess({"providers": lProviders})


# ---------------------------------------------------------------- themes ----

@vApiBlueprint.route("/themes", methods=["GET"])
@auth.fRequireLogin
def fListThemes():
  """List the installed themes, for the Interface tab to offer.

  Which one is in use is not here: like the language, it is stored in the
  browser, because it describes how one person works at one machine and it
  would be odd for a phone and a desktop to have to agree.
  """
  return fSuccess({"themes": themes.fListThemes()})


# --------------------------------------------------------------- api keys ----

@vApiBlueprint.route("/keys", methods=["GET"])
@auth.fRequireLogin
def fListApiKeys():
  """List which providers have a shared key.

  Never returns a key. The hint is the last four characters, which tells two
  keys apart and is useless on its own.
  """
  return fSuccess({
    "keys": api_keys.fDescribeAll(factory.fListProviderNames()),
    "self_hosted": factory.lSelfHostedProviders,
  })


@vApiBlueprint.route("/keys/<vProviderName>", methods=["PUT"])
@auth.fRequireLogin
def fSetApiKey(vProviderName):
  """Store or remove the shared key of one provider."""
  if vProviderName not in factory.fListProviderNames():
    return fFailure("Unknown provider: %r" % (vProviderName,), 404)

  dBody = fGetJsonBody()
  try:
    vStored = api_keys.fWrite(vProviderName, dBody.get("api_key", ""))
  except (ValueError, RuntimeError) as vError:
    return fFailure(vError)
  return fSuccess({"provider": vProviderName, "configured": vStored})


# --------------------------------------------------------------- channels ----

@vApiBlueprint.route("/channels", methods=["GET"])
@auth.fRequireLogin
def fListChannels():
  """List the channels and whether each is configured. Never returns secrets."""
  return fSuccess({"channels": channels.fListConfiguredChannels()})


@vApiBlueprint.route("/channels/<vChannelName>", methods=["PUT"])
@auth.fRequireLogin
def fConfigureChannel(vChannelName):
  """Write one channel's configuration file."""
  import json
  import os

  dBody = fGetJsonBody()
  try:
    vPath = channels.fGetChannelConfigPath(vChannelName)
  except channels.ChannelError as vError:
    return fFailure(vError, 404)

  # Merged into what is on disk, not written over it. The form deliberately
  # sends a secret field only when somebody typed in it - an empty one means
  # "leave it as it is" - so replacing the file wholesale would delete a bot
  # token every time somebody corrected a chat id, and nothing would say so
  # until the next message failed to send.
  dConfig = channels.fReadConfigForEditing(vChannelName)
  dConfig.update(dBody)
  dConfig.setdefault("enabled", True)
  try:
    vTempPath = vPath + ".tmp"
    with open(vTempPath, "w", encoding="utf-8") as vFile:
      json.dump(dConfig, vFile, ensure_ascii=False, indent=2)
      vFile.write("\n")
    os.chmod(vTempPath, 0o640)
    os.replace(vTempPath, vPath)
  except OSError as vError:
    return fFailure("Cannot write the channel configuration: %s" % (vError,), 500)
  return fSuccess({"channel": vChannelName, "configured": True})


# --------------------------------------------------------------- settings ----

# Settings whose value never travels back to the browser. A password that is
# displayed is a password in a page cache, in a screenshot, and in whatever
# read the response on the way; the interface only ever needs to know whether
# there is one, which is what the `*_set` flags say.
lSecretSettings = ["smtp_password", "imap_password"]


@vApiBlueprint.route("/settings", methods=["GET"])
@auth.fRequireLogin
def fGetSettings():
  """Return the interface settings and the account email.

  Stored passwords are replaced by a `<key>_set` flag. They go in and they do
  not come out, the same way the account password and the channel tokens do
  not.
  """
  from backend.core import db
  vConnection = db.fOpenAppDb()
  try:
    dStored = {
      vRow["key"]: vRow["value"]
      for vRow in vConnection.execute("SELECT key, value FROM settings")
    }
  finally:
    vConnection.close()

  dSettings = {vKey: vValue for vKey, vValue in dStored.items()
               if vKey not in lSecretSettings}
  for vKey in lSecretSettings:
    dSettings["%s_set" % (vKey,)] = "1" if dStored.get(vKey) else "0"

  dAdministrator = auth.fGetAdministrator() or {}
  return fSuccess({"settings": dSettings, "email": dAdministrator.get("email", "")})


@vApiBlueprint.route("/settings", methods=["PUT"])
@auth.fRequireLogin
def fUpdateSettings():
  """Update interface settings, the account email or the password."""
  from backend.core import db

  dBody = fGetJsonBody()

  # Everything is checked before anything is written. An endpoint that
  # validates as it goes answers "that is not a valid email address" to a
  # request that has already changed the password, and the error says nothing
  # about what did happen - so the only way to find out is to look.
  dSettings = dBody.get("settings")
  if dSettings is None:
    dSettings = {}
  if not isinstance(dSettings, dict):
    # A list here used to reach `dSettings.pop(key, None)` and come back as an
    # unhandled TypeError, which is a 500 for a request that is simply wrong.
    return fFailure(ValueError("settings must be an object"),
                    pCode=cErrorSettingsNotAnObject)
  dSettings = dict(dSettings)
  if audio_transcription.cSetting in dSettings:
    return fFailure("Use the Audio settings endpoint to configure transcription.")

  try:
    if dBody.get("email"):
      auth.fValidateEmail(dBody["email"])
  except ValueError as vError:
    return fFailure(vError, pCode=cErrorInvalidEmail)

  if dBody.get("password"):
    try:
      auth.fValidatePassword(dBody["password"])
    except ValueError as vError:
      return fFailure(vError, pCode=cErrorPasswordTooShort,
                      pParams={"count": auth.cMinimumPasswordLength})
    if not auth.fVerifyCurrentPassword(dBody.get("current_password")):
      return fFailure(ValueError("The current password is not correct"),
                      pCode=cErrorWrongCurrentPassword)

  try:
    if dBody.get("email"):
      auth.fChangeEmail(dBody["email"])
    if dBody.get("password"):
      auth.fChangePassword(dBody["password"],
                           dBody.get("current_password"))
      # Everyone else is out; the browser this was typed in stays. Logging the
      # owner out of their own session would make changing a password feel
      # like an error, and they have just proved they know both passwords.
      auth.fKeepThisSessionValid()
  except ValueError as vError:
    return fFailure(vError)
  # The password boxes are sent empty every time the form is saved without
  # retyping them, and an empty value there means "I did not change it".
  # Erasing one is done by saying so, with the `<key>_clear` flag.
  for vKey in lSecretSettings:
    if vKey in dSettings and not str(dSettings[vKey]).strip():
      dSettings.pop(vKey)
    if dSettings.pop("%s_clear" % (vKey,), None):
      dSettings[vKey] = ""

  if dSettings:
    vConnection = db.fOpenAppDb()
    try:
      for vKey, vValue in dSettings.items():
        vConnection.execute(
          "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, datetime('now')) "
          "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
          "updated_at = datetime('now')",
          (str(vKey), str(vValue)),
        )
      vConnection.commit()
    finally:
      vConnection.close()
  return fSuccess({"updated": True})


# ----------------------------------------------------------------- system ----

@vApiBlueprint.route("/system", methods=["GET"])
@auth.fRequireLogin
def fGetSystem():
  """Return what the machine looks like: distribution, memory, disk, services.

  Read with no privileges, the same way the SysAdmin agent reads it.
  """
  return fSuccess({"system": system_info.fBuildReport()})


# ---------------------------------------------------------------- status ----

def fCanReachAgentApi():
  """Whether something is listening on the agent API socket right now."""
  from backend.core import agent_api
  vSocket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
  try:
    vSocket.settimeout(cStatusProbeSeconds)
    vSocket.connect(agent_api.cAgentSocketPath)
    return True
  except OSError:
    return False
  finally:
    vSocket.close()


@vApiBlueprint.route("/status", methods=["GET"])
@auth.fRequireLogin
def fGetStatus():
  """Return everything the status bar shows, in one request.

  The two services are first because "nothing happens when I press run" is
  almost always one of them being down, and nothing else in the interface says
  so.
  """
  import os
  from backend.core import agent_api

  dStatus = {"executor": False, "agent_api": False}
  try:
    exec_client.fPing()
    dStatus["executor"] = True
  except exec_client.ExecError:
    dStatus["executor"] = False
  # Connected to, not merely looked for. A socket file outlives the process
  # that made it - a crash, a kill -9, an unclean stop all leave one behind -
  # so `os.path.exists` reported a dead agent API as running, and the status
  # bar said everything was fine while every tool call failed.
  dStatus["agent_api"] = fCanReachAgentApi()

  lAgents = agents.fListIndexedAgents()
  dStatus["agents_total"] = len(lAgents)
  dStatus["agents_enabled"] = len([d for d in lAgents if d.get("enabled")])

  dCounts = kanban.fCountByState()
  dStatus["board"] = dCounts
  dStatus["board_total"] = sum(dCounts.values())

  # Tokens spent today, across every agent. The number that tells you an agent
  # has gone into a loop before the invoice does.
  vTokensToday = 0
  vRunsToday = 0
  try:
    from backend.core import run_journal
    import time
    vToday = time.strftime("%Y-%m-%d", time.gmtime())
    dSummaries = exec_client.fReadUsageSummary().get("summaries") or {}
    for vAgentId in dSummaries:
      try:
        dJournal = exec_client.fReadRunJournal(vAgentId)
      except exec_client.ExecError:
        # One journal the daemon refuses - a link or a FIFO left where
        # runs.jsonl should be - costs that agent its share of today's
        # totals, not every other agent theirs.
        continue
      for dEntry in dJournal.get("entries") or []:
        if not str(dEntry.get("at", "")).startswith(vToday):
          continue
        if dEntry.get("kind") == run_journal.cEntryUsage:
          vTokensToday += int(dEntry.get("prompt_tokens", 0))
          vTokensToday += int(dEntry.get("completion_tokens", 0))
        elif dEntry.get("kind") == run_journal.cEntryRunStarted:
          vRunsToday += 1
  except exec_client.ExecError:
    # The bar still draws with the executor down; that is what the first two
    # items are for.
    pass
  dStatus["tokens_today"] = vTokensToday
  dStatus["runs_today"] = vRunsToday

  return fSuccess({"status": dStatus})
