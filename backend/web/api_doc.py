"""API documentation at /api/doc/.

Serves an OpenAPI 3 description of everything under /api/, and renders it as a
readable page in Swagger's style.

The page is rendered by this project rather than by loading Swagger UI from a
CDN, because the production server is a self-hosted box on a LAN that may have
no outbound internet access at all. Documentation that only works when a CDN is
reachable is documentation that fails exactly when someone is debugging.
"""

import re

from flask import Blueprint, jsonify, render_template

from backend.core import channels
from backend.providers import factory
from backend.web import auth

vApiDocBlueprint = Blueprint("api_doc", __name__, url_prefix="/api/doc")

cApiVersion = "1.0.0"


def fSlug(pText):
  """The stable part of an i18n key, from a piece of English or a path."""
  return re.sub(r"[^a-z0-9]+", "-", str(pText).lower()).strip("-")[:60]


def fAnnotateSpecForTranslation(pSpec):
  """Hang an i18n key on every piece of English the page renders.

  The specification itself stays in English: it is the contract of an API
  whose field names, ids and error strings are all en-US, and a translated
  openapi.json would describe an API that does not exist. What gets
  translated is the PAGE, and it does so the same way every other page in
  this application does - the server writes the English in and marks it with
  a data-i18n key, and the browser swaps it for whatever language this person
  chose. That keeps the strings in the frontend .json files, next to all the
  others, and it works for an anonymous reader too.

  Keys are derived from the text, not written by hand, so adding an endpoint
  adds its keys automatically. A key with no translation keeps the English,
  which is what fApplyTranslations does with a key it does not know.
  """
  pSpec["info"]["x-i18n"] = "apidoc.info.description"

  for dTag in pSpec.get("tags", []):
    dTag["x-i18n"] = "apidoc.tag." + fSlug(dTag["name"])
    dTag["x-i18n-description"] = "apidoc.tagDesc." + fSlug(dTag["name"])

  for vPath, dMethods in pSpec.get("paths", {}).items():
    for vMethod, dOperation in dMethods.items():
      vBase = "apidoc.op.%s-%s" % (vMethod, fSlug(vPath))
      dOperation["x-i18n-summary"] = vBase + ".summary"
      dOperation["x-i18n-description"] = vBase + ".description"

      for dParameter in dOperation.get("parameters", []):
        if dParameter.get("description"):
          dParameter["x-i18n"] = "apidoc.param." + fSlug(dParameter["description"])

      for dResponse in dOperation.get("responses", {}).values():
        if dResponse.get("description"):
          dResponse["x-i18n"] = "apidoc.res." + fSlug(dResponse["description"])

  return pSpec


def fBuildOpenApiSpec():
  """Build the OpenAPI 3 description of the whole API."""
  dAgentSchema = {
    "type": "object",
    "properties": {
      "id": {"type": "string", "example": "007"},
      "name": {"type": "string", "example": "News Miner"},
      "system_user": {"type": "string", "example": "agent-007"},
      "enabled": {"type": "boolean"},
      "kanban_enabled": {"type": "boolean"},
      "tools": {"type": "array", "items": {"type": "string"}},
      "channels": {"type": "array", "items": {"type": "string"}},
      "skills": {"type": "array", "items": {"type": "string"},
                 "example": ["BackupVerification"]},
      "provider": {
        "type": "object",
        "properties": {
          "name": {"type": "string", "enum": factory.fListProviderNames()},
          "model": {"type": "string"},
          "base_url": {"type": "string"},
        },
      },
      "fallback_provider": {
        "type": "object",
        "description": (
          "The backup model, tried once when the main one will not answer. "
          "An empty name means there is none, which is the default. The "
          "agent API hands over the shared key of this provider as well as "
          "of the main one, and of no other."
        ),
        "properties": {
          "name": {"type": "string", "enum": [""] + factory.fListProviderNames()},
          "model": {"type": "string"},
          "base_url": {"type": "string"},
        },
      },
      "limits": {
        "type": "object",
        "properties": {
          "max_tokens_per_run": {"type": "integer"},
          "max_steps_per_run": {"type": "integer"},
          "timeout_seconds": {"type": "integer"},
          "max_runs_per_day": {"type": "integer"},
        },
      },
    },
  }

  dCardSchema = {
    "type": "object",
    "properties": {
      "id": {"type": "integer"},
      "title": {"type": "string"},
      "body": {"type": "string"},
      "state": {"type": "string", "enum": ["todo", "doing", "done"]},
      "owner_agent": {"type": "string"},
      "created_by": {"type": "string"},
      "assigned_by": {
        "type": "string",
        "description": "Who put the card in its owner's hands: \"user\" or an "
                       "agent id. Not the same as created_by: the user can "
                       "write a card the orchestrator later hands on.",
      },
      "run_at": {
        "type": "string",
        "description": "When the owner is woken for it, in UTC. Null leaves the "
                       "card waiting on the board with nobody woken.",
      },
      "run_mode": {
        "type": "string",
        "enum": ["now", "at"],
        "description": "Which kind of time run_at is. Both are in the past by "
                       "the time the agent is woken, and this is what tells the "
                       "agent which it was.",
      },
      "buzzed_at": {
        "type": "string",
        "description": "When a run was actually started for it. Set once.",
      },
    },
  }

  def fPath(pSummary, pDescription, pMethod, pTag, pParameters=None,
            pRequestBody=None, pResponses=None):
    """Build one OpenAPI operation object."""
    dOperation = {
      "summary": pSummary,
      "description": pDescription,
      "tags": [pTag],
      "responses": pResponses or {
        "200": {"description": "Success"},
        "401": {"description": "Not logged in"},
      },
    }
    if pParameters:
      dOperation["parameters"] = pParameters
    if pRequestBody:
      dOperation["requestBody"] = {
        "required": True,
        "content": {"application/json": {"schema": pRequestBody}},
      }
    return {pMethod: dOperation}

  dAgentIdParameter = {
    "name": "vAgentId", "in": "path", "required": True,
    "schema": {"type": "string", "pattern": "^[0-9]{1,3}$"},
    "description": "Agent id, 000 to 999.",
  }
  dCardIdParameter = {
    "name": "vCardId", "in": "path", "required": True,
    "schema": {"type": "integer"}, "description": "Card id.",
  }

  dPaths = {}

  dPaths["/api/admin/agents"] = {}
  dPaths["/api/admin/agents"].update(fPath(
    "List agents",
    "Every agent with its run and token totals. This is what draws the sidebar.",
    "get", "Agents"
  ))
  dPaths["/api/admin/agents"].update(fPath(
    "Create an agent",
    "Creates the system user agent-xxx, its 0700 home, its info.json, its "
    "system-prompt.md and its API token. This is what the + button calls.",
    "post", "Agents",
    pRequestBody={
      "type": "object",
      "required": ["name"],
      "properties": {
        "name": {"type": "string", "example": "News Miner"},
        "description": {"type": "string"},
        "provider": {"type": "string", "enum": factory.fListProviderNames()},
        "model": {"type": "string"},
        "base_url": {"type": "string"},
        "system_prompt": {"type": "string"},
      },
    },
    pResponses={
      "201": {"description": "Agent created"},
      "400": {"description": "Invalid name, or no free agent id left"},
      "401": {"description": "Not logged in"},
    }
  ))

  dPaths["/api/admin/agents/{vAgentId}"] = {}
  dPaths["/api/admin/agents/{vAgentId}"].update(fPath(
    "Read one agent",
    "Configuration, system prompt, crontab and usage totals.",
    "get", "Agents", [dAgentIdParameter]
  ))
  dPaths["/api/admin/agents/{vAgentId}"].update(fPath(
    "Update one agent",
    "Any of info, system_prompt or crontab. Identity fields in info are "
    "ignored: an agent's id, home and system user cannot be changed.",
    "put", "Agents", [dAgentIdParameter],
    pRequestBody={
      "type": "object",
      "properties": {
        "info": dAgentSchema,
        "system_prompt": {"type": "string"},
        "crontab": {
          "type": "string",
          "example": "0 * * * * /opt/boa/venv/bin/python3 "
                     "/opt/boa/webapp/backend/core/runner.py --agent-id 007",
        },
      },
    }
  ))
  dPaths["/api/admin/agents/{vAgentId}"].update(fPath(
    "Delete one agent",
    "Removes the system user, its home directory and its crontab. Cannot "
    "delete agent 000, the orchestrator.",
    "delete", "Agents", [dAgentIdParameter]
  ))

  dPaths["/api/admin/agents/{vAgentId}/run"] = fPath(
    "Run an agent now",
    "Starts one run immediately, as that agent's own user. Returns as soon as "
    "the process is started; a run can take minutes.",
    "post", "Agents", [dAgentIdParameter],
    pResponses={
      "202": {"description": "Run started"},
      "400": {"description": "The executor refused"},
      "401": {"description": "Not logged in"},
    }
  )

  dPaths["/api/admin/agents/{vAgentId}/journal"] = fPath(
    "Read an agent's journal",
    "Run and token history, read from the agent's own runs.jsonl through the "
    "privileged daemon.",
    "get", "Agents",
    [dAgentIdParameter,
     {"name": "limit", "in": "query", "schema": {"type": "integer"}}]
  )

  dPaths["/api/admin/kanban"] = fPath(
    "Read the board", "Every card, grouped by column, plus per-column counts.",
    "get", "Kanban",
    [{"name": "limit", "in": "query", "schema": {"type": "integer"}}]
  )

  dPaths["/api/admin/kanban/cards"] = fPath(
    "Add a card",
    "Adds a card as the user, not as an agent. Nothing is started from here: "
    "the card gets a time and the buzzer wakes its owner, so there is one path "
    "into a run rather than two that can disagree.",
    "post", "Kanban",
    pRequestBody={
      "type": "object",
      "required": ["title"],
      "properties": {
        "title": {"type": "string"},
        "body": {"type": "string"},
        "state": {"type": "string", "enum": ["todo", "doing", "done"]},
        "owner_agent": {"type": "string", "example": "007"},
        "run_at": {
          "type": "string",
          "example": "now",
          "description": "\"now\" to wake the owner straight away, a UTC time "
                         "(YYYY-MM-DD HH:MM) for a moment of your choosing, or "
                         "nothing to leave the card waiting on the board. The "
                         "word \"now\" is sent as a word: only the server's "
                         "clock decides when a card is due.",
        },
      },
    },
    pResponses={"201": {"description": "Card created"},
                "400": {"description": "A card needs a title"}}
  )

  dPaths["/api/admin/kanban/cards/{vCardId}"] = {}
  dPaths["/api/admin/kanban/cards/{vCardId}"].update(fPath(
    "Move a card",
    "The user may move any card. Agents may only move their own.",
    "put", "Kanban", [dCardIdParameter],
    pRequestBody={
      "type": "object",
      "required": ["state"],
      "properties": {
        "state": {"type": "string", "enum": ["todo", "doing", "done"]},
        "note": {"type": "string"},
      },
    }
  ))
  dPaths["/api/admin/kanban/cards/{vCardId}"].update(fPath(
    "Delete a card",
    "The user may delete any card. A row is kept in deleted_cards.",
    "delete", "Kanban", [dCardIdParameter]
  ))

  dPaths["/api/admin/kanban/cards/{vCardId}/schedule"] = fPath(
    "Set or clear when a card runs",
    "Rescheduling clears the buzz, so a card that has already run once can be "
    "asked to run again.",
    "put", "Kanban", [dCardIdParameter],
    pRequestBody={
      "type": "object",
      "properties": {
        "run_at": {
          "type": "string",
          "example": "2026-03-31 13:45",
          "description": "\"now\", a UTC time, or nothing to clear the "
                         "schedule and leave the card waiting on the board.",
        },
        "note": {"type": "string"},
      },
    },
    pResponses={"200": {"description": "Card rescheduled"},
                "404": {"description": "There is no card with that id"}}
  )

  dPaths["/api/admin/kanban/cards/{vCardId}/events"] = fPath(
    "Read a card's history", "Every move, who made it and when.",
    "get", "Kanban", [dCardIdParameter]
  )

  dPaths["/api/admin/kanban/deleted"] = fPath(
    "List deleted cards", "What was removed from the board, and by whom.",
    "get", "Kanban"
  )

  dPaths["/api/admin/tools"] = fPath(
    "List tools",
    "Every .py in /opt/boa/tools/ that declares a valid tool interface. Files "
    "that failed to load are reported in `errors`.",
    "get", "Tools"
  )

  dPaths["/api/admin/skills"] = fPath(
    "List skills",
    "Every directory under /opt/boa/skills/ holding a SKILL.md. Names and "
    "descriptions only: the body of a skill is read by the agent it was "
    "granted to, with the skill.read tool.",
    "get", "Skills"
  )

  dPaths["/api/admin/providers"] = fPath(
    "List providers",
    "Every provider adapter, its default model and whether it is self-hosted. "
    "A provider whose SDK is missing is reported as unavailable.",
    "get", "Providers"
  )

  dPaths["/api/admin/channels"] = fPath(
    "List channels",
    "Which channels are configured and enabled. Never returns credentials.",
    "get", "Channels"
  )

  dPaths["/api/admin/channels/{vChannelName}"] = fPath(
    "Configure a channel",
    "Writes the channel's JSON file as root:boa 0640. Agents cannot read it.",
    "put", "Channels",
    [{"name": "vChannelName", "in": "path", "required": True,
      "schema": {"type": "string", "enum": channels.lChannels}}],
    pRequestBody={
      "type": "object",
      "properties": {
        "enabled": {"type": "boolean"},
        "listen": {"type": "boolean",
                   "description": "telegram, discord: also receive messages"},
        "bot_token": {"type": "string", "description": "telegram, discord"},
        "chat_id": {"type": "string", "description": "telegram"},
        "channel_id": {"type": "string", "description": "discord"},
        "webhook_url": {"type": "string", "description": "discord, mattermost"},
        "channel": {"type": "string", "description": "mattermost"},
        "username": {"type": "string", "description": "mattermost"},
        "bearer_token": {"type": "string", "description": "x"},
      },
    }
  )

  dPaths["/api/admin/settings"] = {}
  dAudioSchema = {
    "type": "object", "additionalProperties": False,
    "properties": {
      "engine": {"type": "string", "enum": ["disabled", "local", "api"]},
      "provider": {"type": "string"}, "api_model": {"type": "string"},
      "local_model": {"type": "string"}, "language": {"type": "string", "default": "auto"},
      "max_seconds": {"type": "integer", "minimum": 30, "maximum": 3600},
      "threads": {"type": "integer", "minimum": 1, "maximum": 32},
      "keep_audio": {"type": "boolean"},
    },
  }
  dPaths["/api/admin/audio"] = fPath(
    "Read audio settings", "Transcription settings, installed native models and providers with a saved API key.",
    "get", "Settings")
  dPaths["/api/admin/audio"].update(fPath(
    "Update audio settings", "Save engine, provider, model, language, duration and audio retention.",
    "put", "Settings", pRequestBody=dAudioSchema))
  dPaths["/api/admin/audio/models/{vModel}/install"] = fPath(
    "Download a local audio model", "Queue a verified whisper.cpp model download. Poll GET /api/admin/audio for progress.",
    "post", "Settings", [{"name": "vModel", "in": "path", "required": True, "schema": {"type": "string"}}],
    pResponses={"202": {"description": "Success"}, "400": {"description": "Invalid model"}, "401": {"description": "Not logged in"}})
  dPaths["/api/admin/agents/{vAgentId}/audio/{vAudioId}"] = fPath(
    "Play an audio message", "Session-protected playback of audio retained in this agent's chat.",
    "get", "Agents", [dAgentIdParameter, {"name": "vAudioId", "in": "path", "required": True,
                                           "schema": {"type": "string", "pattern": "^[a-f0-9]{32}$"}}],
    pResponses={"200": {"description": "Success", "content": {"audio/ogg": {"schema": {"type": "string", "format": "binary"}}}},
                "206": {"description": "Partial content"}, "404": {"description": "Audio not found"},
                "401": {"description": "Not logged in"}})
  dPaths["/api/admin/settings"].update(fPath(
    "Read settings", "Interface settings and the account email address.",
    "get", "Settings"
  ))
  dPaths["/api/admin/settings"].update(fPath(
    "Update settings", "Interface settings, the account email or the password.",
    "put", "Settings",
    pRequestBody={
      "type": "object",
      "properties": {
        "email": {"type": "string"},
        "password": {"type": "string", "minLength": 12},
        "settings": {"type": "object", "additionalProperties": {"type": "string"}},
      },
    }
  ))

  dPaths["/api/admin/system"] = fPath(
    "Read the machine",
    "Distribution, kernel, uptime, memory, load, disk and the state of the "
    "four services. Read with no privileges, the same way the os-watcher agent "
    "reads it. This is what the Operating System tab in Settings shows.",
    "get", "Status"
  )

  dPaths["/api/admin/agents/{vAgentId}/memory"] = {}
  dPaths["/api/admin/agents/{vAgentId}/memory"].update(fPath(
    "Read an agent's memory",
    "The contents of memory.md in the agent's home, which is loaded into the "
    "system prompt of every run.",
    "get", "Agents", [dAgentIdParameter]
  ))
  dPaths["/api/admin/agents/{vAgentId}/memory"].update(fPath(
    "Replace an agent's memory",
    "It is the agent's memory, but a wrong fact it keeps acting on has to be "
    "correctable by hand.",
    "put", "Agents", [dAgentIdParameter],
    pRequestBody={"type": "object", "properties": {"memory": {"type": "string"}}}
  ))

  dPaths["/api/admin/agents/{vAgentId}/attachments/{vAttachmentId}"] = fPath(
    "Read a chat image",
    "Returns a private PNG attached to this agent's conversation. Requires login.",
    "get", "Agents", [dAgentIdParameter, {
      "name": "vAttachmentId", "in": "path", "required": True,
      "schema": {"type": "string", "pattern": "^[a-f0-9]{32}$"},
    }],
    pResponses={
      "200": {"description": "PNG image", "content": {
        "image/png": {"schema": {"type": "string", "format": "binary"}},
      }},
      "401": {"description": "Not logged in"},
      "404": {"description": "Image unavailable"},
      "503": {"description": "Executor unavailable"},
    })

  dPaths["/api/admin/agents/{vAgentId}/chat"] = {}
  dPaths["/api/admin/agents/{vAgentId}/chat"].update(fPath(
    "Read a conversation",
    "Every message, and whether an answer is still pending. The interface "
    "polls this rather than holding a request open, because an answer can take "
    "minutes.",
    "get", "Agents", [dAgentIdParameter]
  ))
  dPaths["/api/admin/agents/{vAgentId}/chat"].update(fPath(
    "Send a message to an agent",
    "Records the message and starts the run that answers it. Returns as soon "
    "as the run is started. Does not count against the agent's runs-per-day "
    "ceiling.",
    "post", "Agents", [dAgentIdParameter],
    pRequestBody={
      "type": "object", "required": ["message"],
      "properties": {"message": {"type": "string"}},
    },
    pResponses={"202": {"description": "Run started"},
                "400": {"description": "Empty message, agent disabled, or one still answering"}}
  ))
  dPaths["/api/admin/agents/{vAgentId}/chat"].update(fPath(
    "Clear a conversation", "Deletes the agent's chat history.",
    "delete", "Agents", [dAgentIdParameter]
  ))

  dPaths["/api/admin/status"] = fPath(
    "Service status",
    "Whether the executor daemon and the agent API are reachable. When "
    "pressing Run does nothing, this is what to check first.",
    "get", "Status"
  )

  dPaths["/api/admin/agent-templates"] = fPath(
    "List the example agents",
    "The examples offered when creating an agent, each with the tools and "
    "schedule it arrives with. The system prompt is left out: it is long, "
    "this is a menu, and creating from an example names the example - the "
    "server reads the file, so the browser cannot hand an agent a tool "
    "nobody ticked.",
    "get", "Agents"
  )

  dPaths["/api/admin/themes"] = fPath(
    "List the installed themes",
    "Every theme in the themes directory, with its name, its scheme and its "
    "description. The name is the theme's own; the scheme and description "
    "are translated by the interface where it has a wording for them.",
    "get", "Settings"
  )

  dPaths["/api/admin/keys"] = fPath(
    "Which providers have a shared key",
    "Whether a key is stored for each provider, never the key itself. A key "
    "that has been written is never readable again through this API: the "
    "only thing that reads one is the agent API, on behalf of an agent "
    "configured for that provider.",
    "get", "Settings",
    pResponses={
      "200": {
        "description": "One entry per provider, with `set` and nothing else",
        "content": {"application/json": {"example": {
          "ok": True,
          "keys": [{"provider": "anthropic", "set": True},
                   {"provider": "openai", "set": False}],
        }}},
      },
      "401": {"description": "Not logged in"},
    }
  )

  dPaths["/api/admin/keys/{vProviderName}"] = fPath(
    "Store or clear one provider's shared key",
    "An empty key deletes the stored one rather than storing an empty "
    "string: \"no key\" and \"a key that is empty\" behave differently "
    "everywhere else. The file is written with the permissions that keep it "
    "unreadable to agents.",
    "put", "Settings",
    pParameters=[{
      "name": "vProviderName", "in": "path", "required": True,
      "schema": {"type": "string", "enum": factory.fListProviderNames()},
    }],
    pRequestBody={
      "type": "object",
      "properties": {"key": {"type": "string"}},
    }
  )

  return {
    "openapi": "3.0.3",
    "info": {
      "title": "Bunch of AIgents API",
      "version": cApiVersion,
      "description": (
        "Everything this installation exposes over HTTP. Every endpoint "
        "requires a session cookie obtained from POST /login.\n\n"
        "The API never touches agent home directories or system users "
        "directly: privileged work goes through the executor daemon over a "
        "Unix socket, which is what lets the web application run unprivileged."
      ),
    },
    "servers": [{"url": "https://localhost:11443", "description": "Local install"}],
    "tags": [
      {"name": "Agents", "description": "Create, configure, schedule and run agents."},
      {"name": "Kanban", "description": "The shared board."},
      {"name": "Tools", "description": "Tools installed on the server."},
      {"name": "Skills", "description": "Shared procedures an agent can be given."},
      {"name": "Providers", "description": "Model provider adapters."},
      {"name": "Channels", "description": "Messaging channels."},
      {"name": "Settings", "description": "Account and interface settings."},
      {"name": "Status", "description": "Health of the background services."},
    ],
    "components": {
      "schemas": {"Agent": dAgentSchema, "Card": dCardSchema},
      "securitySchemes": {
        "sessionCookie": {"type": "apiKey", "in": "cookie", "name": "session"}
      },
    },
    "security": [{"sessionCookie": []}],
    "paths": dPaths,
  }


@vApiDocBlueprint.route("/openapi.json", methods=["GET"])
def fGetOpenApiSpec():
  """Return the OpenAPI description as JSON.

  Public on purpose: it describes the shape of the API, not its data, and
  having it behind the login makes it useless to whoever is trying to log in.
  """
  return jsonify(fBuildOpenApiSpec())


@vApiDocBlueprint.route("/", methods=["GET"])
def fGetApiDocPage():
  """Render the API documentation page.

  Inside the application's frame when there is a session, so that reaching it
  from the sidebar does not drop the user onto a bare page with no way back
  except the browser's own Back button; on its own when there is not, because
  the frame's sidebar would ask for a list of agents that an anonymous caller
  is not allowed to have.
  """
  vLayout = "app_base.html" if auth.fIsLoggedIn() else "base.html"
  # Annotated here and not in fBuildOpenApiSpec: openapi.json is the contract
  # and has no business carrying the page's translation keys.
  dSpec = fAnnotateSpecForTranslation(fBuildOpenApiSpec())
  return render_template("api_doc.html", dSpec=dSpec,
                         vLayout=vLayout, vActiveSection="api-doc")
