#!/usr/bin/env -S PYTHONDONTWRITEBYTECODE=1 python3

"""Agent API: the door agents use to reach shared state.

An agent process runs as `agent-xxx`. The kanban database and the channel
credentials belong to `boa` and are unreadable to it, which is deliberate: an
agent that could write the board directly could rewrite another agent's
history, and an agent that could read telegram.json would own the bot.

This daemon runs as `boa` and is the only way across that line. It listens on a
Unix socket that every agent can open, and it checks each caller twice:

  1. The token the caller presents must match the stored hash of some agent's
     token. That proves the caller holds a token.
  2. SO_PEERCRED must say the calling process belongs to that same agent's
     system user. That proves the token was not copied from somewhere else.

Either check alone would be weaker than both: a leaked token is useless from
the wrong user, and being the right user is useless without the token.

A Unix socket rather than HTTPS because there is nothing to gain from a TLS
handshake between two processes on the same machine, and a self-signed
certificate would mean every agent runs with verification disabled.
"""

import json
import os
import pwd
import socket
import socketserver
import struct
import sys

from backend.core import agents
from backend.core import api_keys
from backend.core import channels
from backend.core import db
from backend.core import discord_inbox
from backend.core import exec_client
from backend.core import exec_protocol
from backend.core import kanban
from backend.core import local_server
from backend.core import mailbox
from backend.core import paths
from backend.core import telegram_inbox

# Socket agents talk to. It lives in its own runtime directory, created by
# systemd owned by the `boa` user: /run/boa belongs to root, and a process
# running as boa cannot create a socket inside a directory it cannot write.
#
# The socket itself is 0666, because every agent user must be able to open it;
# the token and the peer check are what actually authorize a caller.
cAgentSocketPath = "/run/boa-agent/agent.sock"

# Verbs an agent may ask for. Closed, like the executor's: an agent can move a
# card and send a message, and cannot ask for anything else.
cVerbKanbanAddCard = "kanban_add_card"
cVerbKanbanMoveCard = "kanban_move_card"
cVerbKanbanDeleteCard = "kanban_delete_card"
cVerbKanbanListCards = "kanban_list_cards"
cVerbKanbanAssignCard = "kanban_assign_card"
cVerbChannelWrite = "channel_write"
cVerbXPostRequest = "x_post_request"
cVerbMailRead = "mail_read"
cVerbMailDelete = "mail_delete"
cVerbMailMove = "mail_move"
cVerbMailForward = "mail_forward"
cVerbWhoAmI = "who_am_i"
cVerbGetApiKey = "get_api_key"
cVerbCronRead = "cron_read"
cVerbCronAdd = "cron_add"
cVerbCronRemove = "cron_remove"
cVerbCronFire = "cron_fire"
cVerbWake = "wake"
cVerbDailyRuns = "daily_runs"

lAgentVerbs = [
  cVerbKanbanAddCard,
  cVerbKanbanMoveCard,
  cVerbKanbanDeleteCard,
  cVerbKanbanListCards,
  cVerbKanbanAssignCard,
  cVerbChannelWrite,
  cVerbXPostRequest,
  cVerbMailRead,
  cVerbMailDelete,
  cVerbMailMove,
  cVerbMailForward,
  cVerbWhoAmI,
  cVerbGetApiKey,
  cVerbCronRead,
  cVerbCronAdd,
  cVerbCronRemove,
  cVerbCronFire,
  cVerbWake,
  cVerbDailyRuns,
]


# Seconds a caller has to send its request line before the connection is
# dropped. socketserver's default is None, which is "wait for ever": a
# connection that opens and says nothing held a thread of a threading server
# until the process restarted.
cRequestTimeoutSeconds = 30
cMaxAgentRequestBytes = 256 * 1024
class AgentApiError(RuntimeError):
  """Raised when a request from an agent is refused."""


def fLogLine(pMessage):
  """Write one line to stderr, which systemd routes to the journal."""
  sys.stderr.write("%s\n" % (pMessage,))
  sys.stderr.flush()


def fGetPeerCredentials(pSocket):
  """Return (pid, uid, gid) of the process on the other end of the socket."""
  cStructFormat = "3i"
  vCredentials = pSocket.getsockopt(
    socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize(cStructFormat)
  )
  return struct.unpack(cStructFormat, vCredentials)


def fGetSystemUserUid(pSystemUser):
  """Return the uid of one system user, or None when it does not exist."""
  try:
    return pwd.getpwnam(pSystemUser).pw_uid
  except KeyError:
    return None


def fAuthenticate(pToken, pPeerUid):
  """Return the agent identified by a token, or raise.

  Both the token and the calling user must agree. Root is allowed through the
  peer check so that an operator can test the daemon by hand.
  """
  dAgent = agents.fFindAgentByApiToken(pToken)
  if dAgent is None:
    raise AgentApiError("Unknown or invalid token")
  if not dAgent.get("enabled", 1):
    raise AgentApiError("Agent %s is disabled" % (dAgent["id"],))

  if pPeerUid == 0:
    return dAgent

  vExpectedUid = fGetSystemUserUid(dAgent["system_user"])
  if vExpectedUid is None:
    raise AgentApiError(
      "Agent %s has no system user on this machine" % (dAgent["id"],)
    )
  if pPeerUid != vExpectedUid:
    raise AgentApiError(
      "The token belongs to %s but the caller is uid %d"
      % (dAgent["system_user"], pPeerUid)
    )
  return dAgent


def fReadAgentInfo(pAgentId):
  """Return one agent's info.json, or None.

  This daemon runs as `boa` and an agent's info.json is 0600 owned by the
  agent, so it cannot be read directly - which is the same isolation that stops
  agents reading each other. The privileged daemon is asked instead.

  There is deliberately no cache. Reading it every time costs a local socket
  round trip and means that revoking a permission in the web interface takes
  effect on the agent's very next tool call, rather than whenever a cache
  happened to expire.
  """
  try:
    return exec_client.fReadAgentInfo(pAgentId).get("info") or None
  except exec_client.ExecError as vError:
    fLogLine("Cannot read the configuration of agent %s: %s" % (pAgentId, vError))
    return None


def fAgentMayUseKanban(pAgentId):
  """Return True when this agent may touch the board at all.

  The coarse half of the question: is the board switched on for this agent,
  and does it hold any kanban tool whatsoever. It is not enough on its own -
  see fRequireKanbanTool - because "has some kanban tool" is not the same
  question as "may delete a card".
  """
  dInfo = fReadAgentInfo(pAgentId)
  if dInfo is None:
    return False
  if not dInfo.get("kanban_enabled", True):
    return False
  return any(
    str(vTool).startswith("kanban.") for vTool in dInfo.get("tools") or []
  )


def fAgentMayUseKanbanTool(pAgentId, pToolName):
  """Return True when this agent holds one particular kanban tool."""
  dInfo = fReadAgentInfo(pAgentId)
  if dInfo is None:
    return False
  if not dInfo.get("kanban_enabled", True):
    return False
  return str(pToolName) in (dInfo.get("tools") or [])


def fRequireKanbanTool(pAgent, pToolName):
  """Raise unless this agent may use one kanban tool.

  One verb, one tool, checked by name. Every handler used to ask the same
  coarse question - does this agent have ANY tool starting with `kanban.` -
  so an agent granted nothing but kanban.list_cards could reach fDeleteCard by
  putting the request on the socket itself. The runner's tool list would never
  have offered it, but the tool list is advice to a model and this is the door.

  The board being switched on is checked by the same call, so a disabled board
  cannot be reached through any verb either.
  """
  if not fAgentMayUseKanbanTool(pAgent["id"], pToolName):
    raise AgentApiError(
      "This agent is not allowed to use %s" % (pToolName,)
    )


def fAgentMayUseChannel(pAgentId, pChannelName):
  """Return True when this agent may write to one channel."""
  dInfo = fReadAgentInfo(pAgentId)
  if dInfo is None:
    return False
  if "channel.write" not in (dInfo.get("tools") or []):
    return False
  lChannels = dInfo.get("channels") or []
  return str(pChannelName) in lChannels


# The setting that says which language agents answer in. Empty means the one
# their own prompt is written in, which is how it worked before this existed.
cAnswerLanguageSetting = "agent_language"


def fReadAnswerLanguage():
  """Which language agents should answer in, or "" for the prompt's own.

  Read here rather than by the agent, because the settings table lives in the
  web application's database and an agent cannot open it. It is not a secret -
  it is a language tag - so it travels on who_am_i rather than needing a verb
  of its own.
  """
  try:
    vConnection = db.fOpenAppDb()
  except Exception:
    return ""
  try:
    lRows = list(vConnection.execute(
      "SELECT value FROM settings WHERE key = ?", (cAnswerLanguageSetting,)))
  except Exception:
    return ""
  finally:
    vConnection.close()
  return str(lRows[0][0] if lRows else "").strip()


def fVerbWhoAmI(pAgent, pParams):
  """Tell an agent who the daemon thinks it is, and how to answer.

  The language is here because a run started by cron has no other way to know
  it: nobody wrote to it in any language, and the interface's own language is
  a preference kept in somebody's browser.
  """
  return {
    "agent_id": pAgent["id"],
    "name": pAgent["name"],
    "system_user": pAgent["system_user"],
    "answer_language": fReadAnswerLanguage(),
  }


def fVerbKanbanAddCard(pAgent, pParams):
  """Add a card on behalf of an agent."""
  fRequireKanbanTool(pAgent, "kanban.add_card")
  dCard = kanban.fAddCard(
    pTitle=pParams.get("title"),
    pBody=pParams.get("body", ""),
    pState=pParams.get("state") or kanban.cStateTodo,
    # An agent may assign a card to another agent, but the creator is always
    # recorded as the agent that actually called, never as whatever it claims.
    pOwnerAgent=pParams.get("owner_agent") or pAgent["id"],
    pCreatedBy=pAgent["id"],
    pNote=pParams.get("note", ""),
  )
  return {"card": dCard}


def fRequireOwnCard(pAgent, pCardId, pAction):
  """Return the card when it belongs to this agent, or raise.

  An agent may only touch its own cards: the ones it created and the ones
  assigned to it. Reading the board is shared, changing it is not - otherwise
  one agent could mark another agent's work done, or delete it.
  """
  try:
    vCardId = int(pCardId)
  except (TypeError, ValueError):
    raise AgentApiError("card_id must be a number")

  dCard = kanban.fGetCard(vCardId)

  # One answer for "there is no such card" and for "that card is not yours".
  # The old message named the creator and the owner, which told an agent that
  # another agent's work existed and who was doing it - the thing it is not
  # allowed to know. A refusal that distinguishes the two cases is a way of
  # asking the board what is on it, one id at a time.
  if dCard is None or not (fIsOrchestrator(pAgent["id"])
                           or kanban.fAgentOwnsCard(dCard, pAgent["id"])):
    raise AgentApiError(
      "There is no card #%d of yours to %s. You may only change cards you "
      "created or that are assigned to you." % (vCardId, pAction)
    )
  return dCard


def fVerbKanbanMoveCard(pAgent, pParams):
  """Move a card on behalf of an agent, if the card is its own."""
  fRequireKanbanTool(pAgent, "kanban.move_card")
  fRequireOwnCard(pAgent, pParams.get("card_id"), "move")
  dCard = kanban.fMoveCard(
    pCardId=pParams.get("card_id"),
    pState=pParams.get("state"),
    pAgentId=pAgent["id"],
    pNote=pParams.get("note", ""),
  )
  return {"card": dCard}


def fVerbKanbanAssignCard(pAgent, pParams):
  """Hand one of this agent's cards to another agent.

  This is what delegating is: the card keeps its id, its instructions and its
  history, and changes hands. The ownership rule still applies - an agent can
  only give away a card that is already its own - so this widens what the
  orchestrator can do without widening what anyone can reach.

  Handing over a card clears the buzz, so the agent it lands on is woken for
  it. Otherwise delegation would be a change of label that nobody acts on.
  """
  fRequireKanbanTool(pAgent, "kanban.assign_card")
  dCard = fRequireOwnCard(pAgent, pParams.get("card_id"), "assign")

  vOwner = str(pParams.get("owner_agent") or "").strip()
  if not vOwner:
    raise AgentApiError("Say which agent the card is for")
  vOwner = paths.fNormalizeAgentId(vOwner)
  # Checked against the index and not against the agent's info.json: this
  # service runs as boa and agent homes are 0700. The index is what it can
  # read, and "does this agent exist" is exactly what the index answers.
  lKnown = [dAgent["id"] for dAgent in agents.fListIndexedAgents()]
  if vOwner not in lKnown:
    raise AgentApiError(
      "There is no agent %s. The agents are: %s"
      % (vOwner, ", ".join(lKnown) or "none")
    )

  kanban.fAssignCard(
    pCardId=dCard["id"],
    pOwnerAgent=vOwner,
    pAgentId=pAgent["id"],
    pNote=pParams.get("note", ""),
  )
  # A card handed to somebody is a card they should be woken for. Now, unless
  # the sender asked for a time.
  dAssigned = kanban.fSetCardSchedule(
    dCard["id"], pParams.get("run_at") or kanban.cRunNow,
    pAgentId=pAgent["id"], pNote="handed to %s" % (vOwner,)
  )
  return {"card": dAssigned}


def fVerbKanbanDeleteCard(pAgent, pParams):
  """Delete a card on behalf of an agent, if the card is its own.

  The deletion is recorded in `deleted_cards`, so removing a card takes it off
  the board without erasing the fact that it was there.
  """
  fRequireKanbanTool(pAgent, "kanban.delete_card")
  dCard = fRequireOwnCard(pAgent, pParams.get("card_id"), "delete")
  kanban.fDeleteCard(dCard["id"], pDeletedBy=pAgent["id"])
  return {"card_id": dCard["id"], "title": dCard["title"], "deleted": True}


def fIsOrchestrator(pAgentId):
  """Whether this agent is the one whose job is to see everyone's work.

  The orchestrator hands work out and follows it up, so it reads the whole
  board. Every other agent sees only its own, and that is checked here rather
  than asked for in a prompt: a rule written in a prompt is advice.
  """
  return str(pAgentId) == paths.cOrchestratorId


def fFilterCardsForAgent(plCards, pAgentId):
  """Only the cards this agent may know about."""
  if fIsOrchestrator(pAgentId):
    return plCards
  return [dCard for dCard in plCards
          if kanban.fAgentOwnsCard(dCard, pAgentId)]


def fVerbKanbanListCards(pAgent, pParams):
  """List cards for an agent - its own, and nobody else's.

  An agent must not learn that another agent's work exists: not its titles,
  not how many there are, not that there is anything there. So the owner it
  asks for is ignored rather than trusted, and what comes back is filtered by
  what it actually owns.
  """
  fRequireKanbanTool(pAgent, "kanban.list_cards")

  if pParams.get("state"):
    # The owner_agent argument still narrows, but it can only ever narrow
    # further: asking for another agent's cards returns nothing rather than
    # an error, because an error would confirm they exist.
    #
    # `for_agent` goes into the query and not into a filter afterwards. The
    # orchestrator passes none, because the whole board is its job.
    vForAgent = None if fIsOrchestrator(pAgent["id"]) else pAgent["id"]
    lCards = kanban.fListCards(
      pParams.get("state"), pParams.get("owner_agent"), pParams.get("limit"),
      pForAgentId=vForAgent
    )
    # Filtered again on the way out. Two checks of the same rule, because this
    # one is the one that has always been here and the query is new.
    return {"cards": fFilterCardsForAgent(lCards, pAgent["id"])}

  if fIsOrchestrator(pAgent["id"]):
    return {"board": kanban.fGetBoard(pParams.get("limit"))}
  return {"board": kanban.fGetBoard(pParams.get("limit"), pAgent["id"])}


def fVerbChannelWrite(pAgent, pParams):
  """Send a message to a channel on behalf of an agent.

  The agent never sees the channel's credentials, and the message is prefixed
  with the agent's real name, so a message cannot arrive pretending to come
  from somewhere else.
  """
  vChannel = str(pParams.get("channel") or "")
  if not fAgentMayUseChannel(pAgent["id"], vChannel):
    raise AgentApiError(
      "This agent is not allowed to write to channel %r" % (vChannel,)
    )
  try:
    dOptions = {}
    if "x_destination" in pParams:
      if pParams["x_destination"] == "post":
        raise channels.ChannelError(
          "channel.write does not publish on X. Use x.post: the person approves "
          "each post by direct message before it is published.")
      if vChannel != channels.cChannelX or pParams["x_destination"] != "dm":
        raise channels.ChannelError("x_destination applies only to X and must be dm.")
      dOptions["pXDestination"] = pParams["x_destination"]
    dResult = channels.fSendMessage(
      vChannel, pParams.get("message"),
      pPrefix="[%s]" % (pAgent["name"],), **dOptions
    )
  except channels.ChannelError as vError:
    raise AgentApiError(str(vError))

  # Remember who said it, so that answering this message answers this agent.
  # A failure here must not turn a message that was sent into an error the
  # agent sees: the worst case is a reply that has to name its agent with @
  # instead.
  #
  # Discord records every part rather than one id: a long message is sent as
  # several, and somebody replies to whichever one is on their screen.
  if vChannel == channels.cChannelTelegram and dResult.get("message_id"):
    try:
      telegram_inbox.fRememberMessage(dResult["message_id"], pAgent["id"])
    except Exception:
      pass
  if vChannel == channels.cChannelDiscord:
    for vMessageId in (dResult.get("message_ids") or []):
      try:
        discord_inbox.fRememberMessage(vMessageId, pAgent["id"])
      except Exception:
        pass
  if vChannel == channels.cChannelSlack:
    from backend.core import slack_inbox
    vAudience = dResult.pop("_audience", "")
    for vMessageId in (dResult.get("message_ids") or []):
      try:
        slack_inbox.fRememberMessage(vAudience, vMessageId, pAgent["id"])
      except Exception:
        pass
  if vChannel == channels.cChannelMattermost:
    from backend.core import mattermost_inbox
    vAudience = dResult.pop("_audience", "")
    for vMessageId in (dResult.get("message_ids") or []):
      try:
        mattermost_inbox.fRememberMessage(vAudience, vMessageId, pAgent["id"])
      except Exception:
        pass
  return dResult


def fVerbXPostRequest(pAgent, pParams):
  """Ask the person in the X conversation to approve one post on the profile.

  Its own tool, x.post, and the X channel among the agent's channels: a
  public post is not one more thing channel.write may do. Nothing is
  published here; see x_posts.
  """
  from backend.core import x_posts

  dInfo = fReadAgentInfo(pAgent["id"])
  if (dInfo is None or "x.post" not in (dInfo.get("tools") or [])
      or channels.cChannelX not in (dInfo.get("channels") or [])):
    raise AgentApiError(
      "This agent is not allowed to publish on X: it needs the x.post tool "
      "and the x channel.")
  vMessage = str(pParams.get("message") or "").strip()
  if not vMessage:
    raise AgentApiError("There is nothing to publish: the text is empty.")
  try:
    dResult = x_posts.fRequestPost(
      pAgent["id"], pAgent["name"], "[%s] %s" % (pAgent["name"], vMessage))
  except channels.ChannelError as vError:
    raise AgentApiError(str(vError))
  fLogLine("Agent %s asked to publish on X" % (pAgent["id"],))
  return dResult


# ----------------------------------------------------------------- mail ----
#
# Same shape as the channels: the agent names what it wants done, this process
# holds the password and does it. An agent that could read the mailbox password
# would not have "access to the inbox" - it would have the account.


def fAgentMayUseMailTool(pAgentId, pToolName):
  """Return True when this agent has been granted one mail tool.

  Checked here and not only in the tool, for the reason the whole agent API
  exists: the tool runs as the agent, so a tool's own check is a check the
  agent could remove. This one it cannot reach.
  """
  dInfo = fReadAgentInfo(pAgentId)
  if dInfo is None:
    return False
  return str(pToolName) in (dInfo.get("tools") or [])


def fRequireMailTool(pAgent, pToolName):
  """Raise unless this agent may use one mail tool."""
  if not fAgentMayUseMailTool(pAgent["id"], pToolName):
    raise AgentApiError(
      "This agent is not allowed to use %s" % (pToolName,)
    )


def fVerbMailRead(pAgent, pParams):
  """Return messages from the mailbox, newest first.

  Read-only: nothing is marked as seen by looking. An agent that quietly marks
  a mailbox read takes away the one signal the person was relying on.
  """
  fRequireMailTool(pAgent, "mail.read")
  try:
    ldMessages = mailbox.fReadMessages(
      pFolder=pParams.get("folder") or "INBOX",
      pOnlyUnread=bool(pParams.get("only_unread", True)),
      pLimit=pParams.get("limit") or 10,
      pSearch=pParams.get("search") or "",
    )
  except mailbox.MailboxError as vError:
    raise AgentApiError(str(vError))
  return {"messages": ldMessages, "count": len(ldMessages)}


def fVerbMailDelete(pAgent, pParams):
  """Delete one message: to Trash where there is one, expunged where not."""
  fRequireMailTool(pAgent, "mail.delete")
  try:
    return mailbox.fDeleteMessage(
      pParams.get("message_id"), pFolder=pParams.get("folder") or "INBOX")
  except mailbox.MailboxError as vError:
    raise AgentApiError(str(vError))


def fVerbMailMove(pAgent, pParams):
  """Move one message to another folder of the same account."""
  fRequireMailTool(pAgent, "mail.move")
  try:
    return mailbox.fMoveMessage(
      pParams.get("message_id"), pParams.get("target_folder"),
      pFolder=pParams.get("folder") or "INBOX")
  except mailbox.MailboxError as vError:
    raise AgentApiError(str(vError))


def fVerbMailForward(pAgent, pParams):
  """Forward one message, to an address the user listed and no other.

  The allow list is checked inside `mailbox`, in the process that actually
  sends. It is deliberately not something the agent can be talked into
  widening: the instructions it follows arrive, in part, inside the messages
  it reads.
  """
  fRequireMailTool(pAgent, "mail.forward")
  try:
    dResult = mailbox.fForwardMessage(
      pParams.get("message_id"), pParams.get("to"),
      pNote=pParams.get("note") or "",
      pFolder=pParams.get("folder") or "INBOX")
  except mailbox.MailboxError as vError:
    raise AgentApiError(str(vError))
  fLogLine("Agent %s forwarded message %s to %s"
           % (pAgent["id"], pParams.get("message_id"), dResult.get("forwarded_to")))
  return dResult


def fListAgentProviders(pInfo):
  """Return the provider names this agent is configured to use, in order.

  Two at most: the one it runs on and the one it falls back to. Both come from
  the agent's own info.json, which only root can write, so this is a list the
  agent cannot add to by asking.
  """
  lProviders = []
  for vKey in ("provider", "fallback_provider"):
    vName = str((pInfo.get(vKey) or {}).get("name") or "").strip().lower()
    if vName and vName not in lProviders:
      lProviders.append(vName)
  return lProviders


def fVerbGetApiKey(pAgent, pParams):
  """Hand an agent the shared key of a provider it is configured with.

  Its own, and its backup's. Both are read from the agent's info.json rather
  than from the request, so an agent still cannot collect every key on the
  installation - which is the property this check exists for.

  The backup used to be refused, because only `provider.name` was accepted.
  That meant `fallback_provider` worked only for an agent with a per-agent key
  file: configured from the interface with a shared key, the backup failed at
  exactly the moment it was there to cover, and the run failed with it.
  """
  dInfo = fReadAgentInfo(pAgent["id"])
  if dInfo is None:
    raise AgentApiError("Cannot read the configuration of agent %s" % (pAgent["id"],))

  lProviders = fListAgentProviders(dInfo)
  if not lProviders:
    raise AgentApiError("This agent has no provider configured")

  vRequested = str(pParams.get("provider") or "").lower()
  if vRequested and vRequested not in lProviders:
    raise AgentApiError(
      "This agent is configured for %s, so it cannot have the %r key"
      % (" and ".join(repr(v) for v in lProviders), vRequested)
    )

  vProvider = vRequested or lProviders[0]
  from backend.providers import factory
  for vField in ("provider", "fallback_provider"):
    dProvider = dInfo.get(vField) or {}
    if (factory.fResolveProviderName(dProvider.get("name")) == vProvider
        and not factory.fMayUseSharedKey(dProvider)):
      raise AgentApiError(
        "A custom provider URL requires a per-agent key; shared keys are "
        "restricted to the provider's built-in HTTPS origin.")
  vKey = api_keys.fRead(vProvider)
  if not vKey:
    raise AgentApiError(
      "There is no shared key for %r. Add one in Settings, or put one in this "
      "agent's own keys/%s.key." % (vProvider, vProvider)
    )
  return {"provider": vProvider, "api_key": vKey}


# ------------------------------------------------------------- cron ----
#
# An agent used to run `crontab` itself. That works on Debian, where the
# binary is setgid and every user may run it, and not on Alpine, where dcron
# ships it 4750 root:wheel - so cron.add, cron.remove and cron.list did
# different things on the two distributions this project installs on.
#
# The privileged daemon had already solved this for the web interface: it
# writes with `-u <agent>` as root. These verbs are how an agent reaches
# that, and what they add is the validation that the daemon's own verb does
# not do, because the daemon's verb serves the USER, who may write whatever
# they like in their own installation.
#
# An agent never sends a crontab. It used to - one verb, cron_write, replaced
# the whole file once a few heuristics had looked at it - and the heuristics
# were the hole: any line containing "runner.py" passed as the wake-up line,
# a script path anywhere among the arguments passed as running that script,
# and the schedule was not checked at all. Add-only agents could also delete,
# because deleting was a rewrite authorised by cron.add.
#
# Now an agent names a script and, to add, a schedule. This side checks the
# schedule, checks that the script exists, builds the one line it writes
# (agent_scripts.fBuildCronLine) and changes only that line:
#
#   cron_add     needs cron.add and appends one canonical line.
#   cron_remove  needs cron.remove (or script.delete, which takes a script's
#                schedules with it) and removes the lines that run that
#                script, never anything else.
#
# So every line an agent adds runs a script from its own scripts directory,
# and the line that wakes it up cannot be dropped: no verb writes it.


def fRequireCronTool(pAgent, pToolName, *pOtherToolNames):
  """Raise unless this agent holds the cron tool, or one of the others named."""
  dInfo = fReadAgentInfo(pAgent["id"])
  if dInfo is None:
    raise AgentApiError(
      "Cannot read the configuration of agent %s" % (pAgent["id"],))
  lTools = dInfo.get("tools") or []
  if not any(str(vName) in lTools for vName in (pToolName,) + pOtherToolNames):
    raise AgentApiError("This agent is not allowed to use %s" % (pToolName,))


def fVerbCronRead(pAgent, pParams):
  """Return this agent's crontab, as root reads it."""
  fRequireCronTool(pAgent, "cron.list")
  try:
    dResult = exec_client.fReadCrontab(pAgent["id"])
  except exec_client.ExecError as vError:
    raise AgentApiError(str(vError))
  return {"crontab": dResult.get("crontab") or ""}


def fReadCurrentCrontab(pAgentId):
  """The crontab installed for this agent now, as root reads it."""
  try:
    return exec_client.fReadCrontab(pAgentId).get("crontab") or ""
  except exec_client.ExecError as vError:
    raise AgentApiError(str(vError))


def fInstallCrontab(pAgentId, pText):
  try:
    exec_client.fWriteCrontab(pAgentId, pText)
  except exec_client.ExecError as vError:
    raise AgentApiError(str(vError))


def fVerbCronAdd(pAgent, pParams):
  """Schedule one of this agent's scripts: one canonical line, appended."""
  from backend.core import agent_scripts

  fRequireCronTool(pAgent, "cron.add")
  vAgentId = pAgent["id"]
  try:
    vName = agent_scripts.fValidateScriptName(pParams.get("script"))
    vLine = agent_scripts.fBuildCronLine(
      vAgentId, vName, pParams.get("schedule"), pParams.get("note", ""))
  except agent_scripts.ScriptError as vError:
    raise AgentApiError(str(vError))

  # Through the daemon, as the agent: this process cannot enter a home, which
  # is 0700 and belongs to the agent's own user.
  try:
    dScripts = exec_client.fAgentHome(vAgentId, "scripts_list")
  except exec_client.ExecError as vError:
    raise AgentApiError(str(vError))
  if vName not in [dScript.get("name") for dScript in dScripts.get("scripts") or []]:
    raise AgentApiError(
      "There is no script called %r. Write it before scheduling it." % (vName,))

  vCurrent = fReadCurrentCrontab(vAgentId)
  if vLine.strip().splitlines()[-1] in vCurrent.splitlines():
    raise AgentApiError("That exact line is already in the crontab.")
  vNew = vCurrent if vCurrent.endswith("\n") or not vCurrent else vCurrent + "\n"
  fInstallCrontab(vAgentId, vNew + vLine)
  fLogLine("Agent %s scheduled %s" % (vAgentId, vName))
  return {"line": vLine.strip()}


def fVerbCronFire(pAgent, pParams):
  """A line of this agent's crontab fired: start that script, contained.

  Only a script a line of its crontab does schedule - lines root wrote, the
  agent having no `crontab` of its own to write them with - so this is not a
  way to run something nothing scheduled. The executor starts it in a scope
  or cgroup with a run's ceilings, where cron used to start it bare.
  """
  from backend.core import agent_scripts

  vAgentId = pAgent["id"]
  try:
    vName = agent_scripts.fValidateScriptName(pParams.get("script"))
  except agent_scripts.ScriptError as vError:
    raise AgentApiError(str(vError))
  vPath = agent_scripts.fGetScriptPath(vAgentId, vName)
  if not any(agent_scripts.fLineRunsPath(vLine, vPath)
             for vLine in fReadCurrentCrontab(vAgentId).splitlines()):
    raise AgentApiError("No line of your crontab runs %r." % (vName,))
  try:
    return exec_client.fRunScript(vAgentId, vName)
  except exec_client.ExecError as vError:
    raise AgentApiError(str(vError))


def fVerbWake(pAgent, pParams):
  """The agent's wake-up line fired: start its scheduled run, contained.

  runner.py asks for this when cron started it outside a scope or cgroup
  (runner.fShouldAskTheExecutor), so the run itself is started by the
  executor like every other one. Not a second run: one already in flight
  means this one is not started.
  """
  try:
    dResult = exec_client.fRunNow(pAgent["id"], pOnlyIfIdle=True)
  except exec_client.ExecError as vError:
    raise AgentApiError(str(vError))
  return {"started": bool(dResult.get("started")), "reason": dResult.get("reason", "")}


# ------------------------------------------------------------ run count ----
#
# max_runs_per_day is what stops an unattended schedule from spending without
# end. It was enforced by counting the run_started lines of the run journal,
# and the journal is in the agent's home: an agent with bash.run that emptied
# runs.jsonl woke up next time with the whole day's budget back. The count is
# kept here now, in the application database, which no agent can write. The
# journal stays what History shows.


def fVerbDailyRuns(pAgent, pParams):
  """This agent's scheduled runs today and, with `claim`, one more if allowed.

  The ceiling comes from the agent's info.json, which only root writes, so
  the agent cannot raise it by asking; the count and the check are
  agents.fCountDailyRun. An agent that claims runs it does not make only
  spends its own day.
  """
  dInfo = fReadAgentInfo(pAgent["id"])
  if dInfo is None:
    raise AgentApiError(
      "Cannot read the configuration of agent %s" % (pAgent["id"],))
  vClaim = bool(pParams.get("claim"))
  dResult = agents.fCountDailyRun(pAgent["id"], agents.fReadDailyRunCeiling(dInfo), vClaim)
  if vClaim and dResult["allowed"]:
    fLogLine("Agent %s started scheduled run %d of %d today"
             % (pAgent["id"], dResult["runs"], dResult["ceiling"]))
  return dResult


def fVerbCronRemove(pAgent, pParams):
  """Stop running one of this agent's scripts. Nothing else is touched."""
  from backend.core import agent_scripts

  fRequireCronTool(pAgent, "cron.remove", "script.delete")
  vAgentId = pAgent["id"]
  try:
    vName = agent_scripts.fValidateScriptName(pParams.get("script"))
  except agent_scripts.ScriptError as vError:
    raise AgentApiError(str(vError))
  vCurrent = fReadCurrentCrontab(vAgentId)
  vNew, vRemoved = agent_scripts.fWithoutCronLines(
    vCurrent, agent_scripts.fGetScriptPath(vAgentId, vName))
  if vRemoved:
    fInstallCrontab(vAgentId, vNew)
    fLogLine("Agent %s unscheduled %s (%d line(s))" % (vAgentId, vName, vRemoved))
  return {"removed": vRemoved}


dAgentVerbHandlers = {
  cVerbWhoAmI: fVerbWhoAmI,
  cVerbGetApiKey: fVerbGetApiKey,
  cVerbKanbanAddCard: fVerbKanbanAddCard,
  cVerbKanbanMoveCard: fVerbKanbanMoveCard,
  cVerbKanbanAssignCard: fVerbKanbanAssignCard,
  cVerbKanbanDeleteCard: fVerbKanbanDeleteCard,
  cVerbKanbanListCards: fVerbKanbanListCards,
  cVerbChannelWrite: fVerbChannelWrite,
  cVerbXPostRequest: fVerbXPostRequest,
  cVerbMailRead: fVerbMailRead,
  cVerbMailDelete: fVerbMailDelete,
  cVerbMailMove: fVerbMailMove,
  cVerbMailForward: fVerbMailForward,
  cVerbCronRead: fVerbCronRead,
  cVerbCronAdd: fVerbCronAdd,
  cVerbCronRemove: fVerbCronRemove,
  cVerbCronFire: fVerbCronFire,
  cVerbWake: fVerbWake,
  cVerbDailyRuns: fVerbDailyRuns,
}


class AgentRequestHandler(socketserver.StreamRequestHandler):
  """Handle one request from an agent."""

  # Seconds this handler waits for a caller to send its line.
  #
  # socketserver leaves `timeout` as None, so `self.rfile.readline` blocks for
  # ever on a connection that opens and never sends a newline. The server is a
  # threading one, so each of those holds a thread and a file descriptor until
  # the process restarts: opening a few hundred connections and saying nothing
  # is a local denial of service that needs no permission at all.
  timeout = cRequestTimeoutSeconds

  def handle(self):
    try:
      vPid, vUid, vGid = fGetPeerCredentials(self.request)
    except OSError as vError:
      fLogLine("Cannot read peer credentials: %s" % (vError,))
      return

    try:
      vRawRequest = local_server.fReadRequest(
        self.request, cMaxAgentRequestBytes, cRequestTimeoutSeconds)
    except (OSError, ValueError) as vError:
      fLogLine("Cannot read request: %s" % (vError,))
      return

    dResponse = self.fProcessRequest(vRawRequest, vUid)
    try:
      self.wfile.write(exec_protocol.fEncodeMessage(dResponse))
    except OSError as vError:
      fLogLine("Cannot write response: %s" % (vError,))

  def fProcessRequest(self, pRawRequest, pUid):
    """Turn one raw request into a response payload."""
    try:
      dRequest = exec_protocol.fDecodeMessage(pRawRequest)
    except (ValueError, UnicodeDecodeError) as vError:
      return exec_protocol.fBuildFailure("Malformed request: %s" % (vError,))

    vVerb = dRequest.get("verb")
    dParams = dRequest.get("params") or {}
    if not isinstance(dParams, dict):
      return exec_protocol.fBuildFailure("params must be an object")

    fHandler = dAgentVerbHandlers.get(vVerb)
    if fHandler is None:
      return exec_protocol.fBuildFailure("Unknown verb: %r" % (vVerb,))

    try:
      dAgent = fAuthenticate(dRequest.get("token"), pUid)
    except AgentApiError as vError:
      fLogLine("Refused uid %d: %s" % (pUid, vError))
      return exec_protocol.fBuildFailure(vError)

    fLogLine("agent %s requested %s" % (dAgent["id"], vVerb))
    try:
      return exec_protocol.fBuildSuccess(fHandler(dAgent, dParams))
    except (AgentApiError, kanban.KanbanError, channels.ChannelError) as vError:
      return exec_protocol.fBuildFailure(vError)
    except Exception as vError:
      fLogLine("Verb %s failed: %s" % (vVerb, vError))
      return exec_protocol.fBuildFailure(vError)


class AgentApiServer(local_server.BoundedUnixServer):
  """Unix socket server for the agent API."""

  daemon_threads = True
  allow_reuse_address = True


def fPrepareSocketPath():
  """Create the runtime directory and remove any stale socket file.

  systemd normally has it ready through RuntimeDirectory=. Creating it here as
  well is what lets the daemon be started by hand for debugging.
  """
  vRuntimeDir = os.path.dirname(cAgentSocketPath)
  os.makedirs(vRuntimeDir, mode=0o755, exist_ok=True)
  if os.path.exists(cAgentSocketPath):
    os.unlink(cAgentSocketPath)
  return cAgentSocketPath


def fMain():
  """Run the agent API until it is stopped."""
  # The tables this daemon writes, before the first request: after an update
  # it can be serving before the web application has created a new one.
  try:
    db.fCreateAppSchema()
  except Exception as vError:
    fLogLine("Cannot prepare the application database: %s" % (vError,))
  vSocketPath = fPrepareSocketPath()
  vServer = AgentApiServer(vSocketPath, AgentRequestHandler)

  # Every agent user must be able to connect. Authorization is the token plus
  # the peer check, not the file mode.
  os.chmod(vSocketPath, 0o666)

  fLogLine("Agent API listening on %s" % (vSocketPath,))
  try:
    vServer.serve_forever()
  except KeyboardInterrupt:
    fLogLine("Agent API stopping.")
  finally:
    vServer.server_close()
    if os.path.exists(vSocketPath):
      os.unlink(vSocketPath)
  return 0


if __name__ == "__main__":
  sys.exit(fMain())
