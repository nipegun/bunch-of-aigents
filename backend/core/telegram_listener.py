#!/usr/bin/env -S PYTHONDONTWRITEBYTECODE=1 python3

"""The listener: lets you answer an agent from Telegram.

Agents could already write to Telegram. This is the other half: a message you
send to the bot arrives in an agent's chat, starts a run, and the answer comes
back to you in Telegram - while the whole exchange sits in that agent's
conversation in the web interface, both halves of it, so one screen still shows
everything the agent was asked and everything it said.

    every pass:
      answers  -> for each question still open, ask the executor whether the
                  turn has closed; if it has, send what the agent said back
      updates  -> long-poll Telegram; route each message to an agent and ask
                  the executor to start the run that answers it

Long polling, never a webhook. A webhook needs Telegram to reach this machine,
which means a port open to the internet pointed at an installation whose own
README says it belongs on a LAN. `getUpdates` connects outwards and works from
behind any NAT, with nothing forwarded.

Run as `boa`, like the buzzer, and for the same reasons: it needs to read the
channel configuration, which is boa's, and to reach the executor's socket,
which is root:boa. Writing into an agent's 0700 home and starting a process as
that agent stay where they were - in the executor - because this service has no
privileges of its own to lend.

Four decisions worth knowing about:

  Only the configured chat is listened to. A bot's name is public and anybody
  can message it. Everything from any other chat is dropped without an answer,
  because answering would confirm the bot exists to whoever is probing it.

  Replying routes. Answering a message the bot sent answers the agent that sent
  it, which is what makes a conversation feel like a conversation. `@name` is
  for starting one.

  A busy agent is told so, not queued. The executor refuses a second message
  while the first is still being answered, and a queue would hide that an agent
  is falling behind.

  What is waiting is on disk. The service restarts on every update, and
  somebody who asked a question twenty seconds earlier should not lose the
  answer because of that.
"""

import argparse
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
  os.path.abspath(__file__)
))))

from backend.core import agent_routing
from backend.core import agents
from backend.core import attachments
from backend.core import channels
from backend.core import chat
from backend.core import db
from backend.core import exec_client
from backend.core import paths
from backend.core import telegram_inbox
from backend.core import telegram_texts

# How long Telegram is asked to hold an empty poll open when nothing is
# waiting for an answer. This is the quiet case: a couple of requests a minute.
cIdlePollSeconds = channels.cLongPollSeconds

# And when an agent is in the middle of answering. The poll is what paces the
# whole loop, so a long one here would mean an answer sitting written but unsent
# for up to half a minute.
cBusyPollSeconds = 3

# How long to wait before looking again when Telegram cannot be reached or is
# not configured. Long enough not to hammer anything, short enough that turning
# the channel on does not need a restart.
cRetrySeconds = 60

# The bot's own commands. Three tools, whatever the roster does.
cCommandAgents = "agents"
cCommandStatus = "status"
cCommandHelp = "help"
cCommandStart = "start"

# What a button carries back when it is tapped. Short, because Telegram
# allows 64 bytes and the id is enough to look the agent up again.
cCallbackAgentPrefix = "a:"

# The description of a command is one word, in the language this installation
# was set to: "Agentes", "Estado", "Ayuda".
#
# It is not decoration, it is the left-hand column. The menu draws the
# description on one side of each row and `/command` on the other, and which
# side each takes is the client's decision, not something the API exposes. So
# the description is what a person reads first, and a sentence explaining what
# the command does pushed the name of the action out of sight. One word puts
# it back. An empty description is not an option either: Telegram answers
# "command description must be non-empty", and a single space counts as empty.


def fLogLine(pMessage):
  """Write one timestamped line to stderr, which systemd collects."""
  agent_routing.fLogLine(pMessage)


# ------------------------------------------------------------- the offset ----
#
# Telegram hands over every update after the one last acknowledged, so this
# number is the whole of "what have I already dealt with".

def fReadOffset():
  """Return the first update id not dealt with yet, or 0 for everything."""
  try:
    with open(paths.fGetTelegramOffsetPath(), "r", encoding="utf-8") as vFile:
      return int((vFile.read() or "0").strip() or 0)
  except (OSError, ValueError):
    # No file, or something that is not a number. Starting from zero means
    # re-reading whatever Telegram still holds, which is a few messages at
    # worst and never a crash.
    return 0


def fWriteOffset(pOffset):
  """Record the first update id not dealt with yet."""
  vPath = paths.fGetTelegramOffsetPath()
  vTempPath = "%s.tmp" % (vPath,)
  try:
    with open(vTempPath, "w", encoding="utf-8") as vFile:
      vFile.write("%d\n" % (int(pOffset),))
    os.replace(vTempPath, vPath)
    return True
  except OSError as vError:
    # Not fatal: the worst case is that a restart re-reads a message. Saying so
    # matters, because that is what a duplicate answer would be explained by.
    fLogLine("Cannot record the Telegram offset: %s" % (vError,))
    return False


# ------------------------------------------------------------- the routing ----

def fListAgentNames():
  """Return [(id, name)] for every agent, from the index.

  The index is what a process running as `boa` can read: agent homes are 0700
  and their info.json is not ours to open.
  """
  return agent_routing.fListAgentNames()


def fBuildCommandName(pName, pAgentId):
  """Return the /command for an agent, which Telegram is strict about.

  Lowercase letters, digits and underscores only, so "News Miner" becomes
  `news_miner`. A name left with nothing usable - one written in an alphabet
  Telegram will not take - falls back to the id, which always works.
  """
  return agent_routing.fBuildCommandName(pName, pAgentId)


def fBuildCommandList():
  """Return the menu of what this bot can do.

  Tools, not agents. An agent per command turned the menu into a directory
  that grew with the roster and said nothing about what the bot was for, and
  Telegram always draws `/name` beside each entry - so a list of agents there
  could never be the list of agents somebody wanted to look at.

  Which agents exist is a question, and /agents is what answers it.
  """
  return [
    {"command": cCommandAgents,
     "description": telegram_texts.fText("commandAgents")[:256]},
    {"command": cCommandStatus,
     "description": telegram_texts.fText("commandStatus")[:256]},
    {"command": cCommandHelp,
     "description": telegram_texts.fText("commandHelp")[:256]},
  ]


def fBuildAgentButtons():
  """Return the inline keyboard of agents, one button per row.

  Under a message rather than under the message box: these belong to the
  answer /agents gave, they are read in place, and they do not take up the
  bottom of the screen for ever afterwards.

  A button says `@os-watcher` and nothing else, which is the one thing the
  command menu cannot do. Tapping it sends a callback rather than a message,
  so nothing appears in the conversation that somebody has to read past.

  `callback_data` is limited to 64 bytes, so it carries the id and the id is
  looked up when it comes back. A name would not fit and would go stale.
  """
  lRows = []
  for vAgentId, vName in fListAgentNames():
    lRows.append([{
      "text": vName or vAgentId,
      "callback_data": "%s%s" % (cCallbackAgentPrefix, vAgentId),
    }])
  return {"inline_keyboard": lRows} if lRows else None


def fBuildAgentsMessage():
  """Return the text that goes above those buttons."""
  if not fListAgentNames():
    return telegram_texts.fText("agentsNone")
  return telegram_texts.fText("agentsHeading")


def fMatchNamedAgent(pText):
  """Return (agent_id, rest of the message) for a message naming an agent.

  Both @name and /name, because Telegram autocompletes the second one and the
  first is what a person writes from memory.

  Agent names can contain spaces, so the name cannot be read as "up to the
  first space". Every known name is tried instead and the longest match wins,
  which is what makes @News and @News Miner two different agents rather than
  one ambiguity. The id works too: @007 is always that agent, whatever it is
  called this week. And so does the command form, `/news_miner`, which is what
  Telegram puts in the box when the list is used.
  """
  return agent_routing.fMatchNamedAgent(pText)


def fRouteMessage(pdMessage):
  """Return (agent_id, text) for one incoming Telegram message.

  Three ways to be addressed to somebody, in this order:

    1. It replies to something an agent said. Unambiguous, and what somebody
       holding a phone actually does.
    2. It names an agent: @os-watcher, /os_watcher, @001.
    3. Neither, in which case it goes to whoever was picked last.

  The third is what makes this a conversation rather than a command line.
  Having to name the agent on every line is fine once and tiresome by the
  fourth message, and there is nobody else it could sensibly be for.

  Picking is explicit and sticky: tapping a name in /agents, or naming one,
  changes who that is. Nothing else does, so an agent never inherits a
  conversation by being the one who happened to speak last.
  """
  vText = str(pdMessage.get("text") or pdMessage.get("caption") or "").strip()
  dReplyTo = pdMessage.get("reply_to_message") or {}
  vRepliedId = dReplyTo.get("message_id")

  if vRepliedId:
    try:
      vAgentId = telegram_inbox.fFindAgentForMessage(vRepliedId)
    except Exception as vError:
      fLogLine("Cannot look up message %s: %s" % (vRepliedId, vError))
      vAgentId = ""
    if vAgentId:
      # A named agent in the text of a reply is not a contradiction worth
      # refusing: strip it if it is there, so "@os-watcher yes" as a reply to
      # os-watcher does not reach it with its own name glued to the front.
      vNamedId, vRemainder = fMatchNamedAgent(vText)
      if vNamedId == vAgentId:
        vText = vRemainder
      return (vAgentId, vText)

  vNamedId, vRemainder = fMatchNamedAgent(vText)
  if vNamedId:
    return (vNamedId, vRemainder)

  vSelectedId = fReadSelectedAgent()
  if vSelectedId:
    return (vSelectedId, vText)
  return ("", vText)


def fReadSelectedAgent():
  """Return the agent this conversation is with, or "" if there is none.

  Checked against the roster on the way out: an agent that has been deleted
  since it was picked must not go on catching every message, and silently
  reaching nobody is better than silently reaching whoever took its id.
  """
  try:
    vAgentId = telegram_inbox.fGetSelectedAgent()
  except Exception as vError:
    fLogLine("Cannot read the selected agent: %s" % (vError,))
    return ""
  if not vAgentId:
    return ""
  if not any(vAgentId == vId for vId, vName in fListAgentNames()):
    return ""
  return vAgentId


def fSelectAgent(pAgentId):
  """Make this agent the one an unaddressed message goes to."""
  try:
    telegram_inbox.fSetSelectedAgent(pAgentId)
  except Exception as vError:
    fLogLine("Cannot record the selected agent: %s" % (vError,))


def fIsFromTheConfiguredChat(pdMessage, pConfig):
  """Return whether this message came from the chat this bot is set up for.

  A bot's username is public and anybody who finds it can write to it. Nothing
  else is a chat with the owner of this installation.
  """
  vConfigured = str(pConfig.get("chat_id") or "").strip()
  if not vConfigured:
    return False
  vFrom = str((pdMessage.get("chat") or {}).get("id") or "").strip()
  return bool(vFrom) and vFrom == vConfigured


# ------------------------------------------------------------- the sending ----

def fSay(pConfig, pText, pReplyToMessageId=None, pAgentId="",
         pReplyMarkup=None):
  """Send one message to the configured chat.

  Returns True when it went out; False when Telegram did not answer, which
  is worth trying again; and None when Telegram rejected the message and
  would reject it again - the bot blocked, the chat gone, the token revoked.
  Both failures are falsy, so a caller that only wants to know whether the
  message arrived tests the result as before; the one caller that keeps a
  message to try again later, fDeliverAnswers, tells the two apart.

  When it carries an agent's words, the id Telegram gives it is remembered, so
  that replying to it reaches that agent again. That is what turns a single
  answer into a conversation you can keep having.
  """
  try:
    dResult = channels.fSendToTelegram(
      pConfig, pText, pReplyToMessageId, pReplyMarkup)
  except channels.ChannelRejected as vError:
    fLogLine("Telegram rejected the message: %s"
             % (channels.fRedactSecrets(vError, pConfig),))
    return None
  except Exception as vError:
    # Redacted before it is written: a connection failure quotes the URL, and
    # the bot token is in that URL. A journal anybody on the machine can read
    # is not where a credential belongs.
    fLogLine("Cannot send to Telegram: %s"
             % (channels.fRedactSecrets(vError, pConfig),))
    return False

  if pAgentId and dResult.get("message_id"):
    try:
      telegram_inbox.fRememberMessage(dResult["message_id"], pAgentId)
    except Exception as vError:
      fLogLine("Cannot remember message %s: %s"
               % (dResult.get("message_id"), vError))
  return True


def fGetAgentName(pAgentId):
  """Return an agent's visible name, or its id when it has none."""
  return agent_routing.fGetAgentName(pAgentId)


def fDescribeAgents(pLanguage=None):
  """Return the "who is that for" message, with the agent buttons under it.

  The message says what went wrong and the buttons are how to fix it: the
  reader has just failed to reach an agent and the shortest path to trying
  again is tapping one, not reading a list and retyping a name from it.
  """
  return telegram_texts.fText("noAgent", pLanguage)


# ------------------------------------------------------------ the delivery ----

# ------------------------------------------------------------- the commands ----

def fBuildStatusReport(pLanguage=None):
  """Return what /status says: the services, the board and every agent.

  Read the same way the web interface reads it - the executor for anything
  inside an agent's 0700 home, the index and the board directly - because this
  service has no more privilege than that page does.

  An agent whose info.json cannot be read is listed saying so rather than left
  out. A status report that quietly drops what it could not check is worse
  than no report: the one agent missing is the one worth asking about.
  """
  return agent_routing.fBuildStatusReport(
    telegram_texts.fText, "boa-telegram", pLanguage)


def fHandleCommand(pCommand, pdMessage, pConfig):
  """Deal with one of the bot's own commands. Returns whether it was one.

  None of these replies TO the command. A reply makes Telegram draw the
  message being answered inside the bot's own bubble, so the answer to
  /agents arrived with "/agents" quoted above it - which says nothing that
  the message underneath does not, and pushes the buttons down the screen.

  An agent's answer is still a reply, and for the opposite reason: there the
  quoted line is the question it belongs to, which may be far up the chat by
  the time the run finishes.
  """
  if pCommand in (cCommandAgents, cCommandStart):
    # /start included: somebody opening the bot for the first time is asking
    # exactly this question, and answering with the roster is more use than a
    # greeting.
    fSay(pConfig, fBuildAgentsMessage(), None,
         pReplyMarkup=fBuildAgentButtons())
    return True

  if pCommand == cCommandStatus:
    fSay(pConfig, fBuildStatusReport())
    return True

  if pCommand == cCommandHelp:
    fSay(pConfig, telegram_texts.fText("helpText"))
    return True

  return False


def fHandleCallback(pdCallback, pConfig):
  """Deal with a tap on one of the agent buttons.

  Telegram shows a spinner on the button until the callback is answered, so
  that goes first and happens whatever else does.
  """
  vData = str(pdCallback.get("data") or "")
  dMessage = pdCallback.get("message") or {}

  try:
    channels.fAnswerTelegramCallback(pConfig, pdCallback.get("id"))
  except Exception as vError:
    fLogLine("Cannot answer the callback: %s" % (vError,))

  # Same silence as an ordinary message from another chat, and for the same
  # reason.
  if not fIsFromTheConfiguredChat(dMessage, pConfig):
    return False
  if not vData.startswith(cCallbackAgentPrefix):
    return False

  vAgentId = vData[len(cCallbackAgentPrefix):]
  if not any(vAgentId == vId for vId, vName in fListAgentNames()):
    fLogLine("A button named agent %r, which is not there any more."
             % (vAgentId,))
    fSay(pConfig, fBuildAgentsMessage(), None,
         pReplyMarkup=fBuildAgentButtons())
    return False

  # Picked: from here on, a message that names nobody goes to this agent.
  fSelectAgent(vAgentId)

  # The answer is registered as that agent's as well, so replying to it
  # reaches them too. Both ways work; this is the one that needs no aiming.
  fLogLine("Agent %s picked from the button list." % (vAgentId,))
  fSay(pConfig,
       telegram_texts.fText("whatShouldItDo", None,
                            name=fGetAgentName(vAgentId)),
       None, vAgentId)
  return True


def fFindClosedAnswer(pAgentId, pTurnId):
  """Return what the agent said to close this turn, or "" if it is still open.

  Read through the executor: the conversation lives in a 0700 home this service
  cannot enter.
  """
  return agent_routing.fFindClosedAnswer(pAgentId, pTurnId)


def fSayImage(pConfig, pAgentId, pImage, pReplyToMessageId=None):
  """Deliver one private image, retaining the same retry semantics as text."""
  try:
    dFirst = exec_client.fReadChatAttachment(pAgentId, pImage["id"])
    vPng = b"".join(exec_client.fIterChatAttachment(pAgentId, pImage["id"], dFirst))
    dImage = dFirst["attachment"]
    vCaption = "%s: %s" % (fGetAgentName(pAgentId),
                           dImage.get("caption") or dImage["name"])
    dResult = channels.fSendImageToTelegram(
      pConfig, vPng, dImage["name"], vCaption, pReplyToMessageId)
  except (exec_client.AttachmentUnavailable, channels.ChannelRejected) as vError:
    fLogLine("Cannot deliver image %s: %s" % (
      pImage["id"], channels.fRedactSecrets(vError, pConfig)))
    return None
  except Exception as vError:
    fLogLine("Image delivery will be retried: %s" % (
      channels.fRedactSecrets(vError, pConfig),))
    return False
  if dResult.get("message_id"):
    try:
      telegram_inbox.fRememberMessage(dResult["message_id"], pAgentId)
    except Exception as vError:
      fLogLine("Cannot remember image message %s: %s" % (dResult["message_id"], vError))
  return True


def fDeliverAnswerParts(pConfig, pPending, pMessage):
  """Resume a partially delivered answer without repeating successful parts."""
  vTurnId = pPending["turn_id"]
  vAgentId = pPending["agent_id"]
  vReplyTo = pPending.get("reply_to")
  sDelivered = telegram_inbox.fListDeliveredParts(vTurnId)
  vText = str(pMessage.get("text") or "")
  if vText and "text" not in sDelivered:
    vSent = fSay(pConfig, "**%s:**\n%s" % (fGetAgentName(vAgentId), vText),
                 vReplyTo, vAgentId)
    if not vSent:
      return vSent
    telegram_inbox.fRememberDeliveredPart(vTurnId, "text")
  for dImage in attachments.fListMessageAttachments(pMessage):
    vPart = "image:" + dImage["id"]
    if vPart in sDelivered:
      continue
    vSent = fSayImage(pConfig, vAgentId, dImage, vReplyTo)
    if vSent is None:
      vSent = fSay(pConfig, "**%s:**\n%s" % (fGetAgentName(vAgentId),
        telegram_texts.fText("imageFailed", name=str(dImage.get("name") or "image.png")[:128])),
        vReplyTo, vAgentId)
    if not vSent:
      return vSent
    telegram_inbox.fRememberDeliveredPart(vTurnId, vPart)
  return True


def fDeliverAnswers(pConfig):
  """Send back every answer that is ready. Returns how many are still waiting."""
  try:
    lPending = telegram_inbox.fListPending()
  except Exception as vError:
    fLogLine("Cannot read what is pending: %s" % (vError,))
    return 0

  vStillWaiting = 0
  for dPending in lPending:
    vTurnId = str(dPending.get("turn_id") or "")
    vAgentId = str(dPending.get("agent_id") or "")
    dAnswer = agent_routing.fFindClosedMessage(vAgentId, vTurnId)
    vAnswer = str((dAnswer or {}).get("text") or "")

    if not vAnswer and not attachments.fListMessageAttachments(dAnswer or {}):
      if telegram_inbox.fIsExpired(dPending):
        # The run died without closing its turn. Say so rather than leaving
        # somebody waiting for something that is never coming.
        fLogLine("Turn %s of agent %s expired without an answer."
                 % (vTurnId, vAgentId))
        fSay(pConfig,
             "**%s:**\n%s" % (fGetAgentName(vAgentId),
                              telegram_texts.fText("neverFinished")),
             dPending.get("reply_to"), vAgentId)
        telegram_inbox.fRemovePending(vTurnId)
      else:
        vStillWaiting += 1
      continue

    # Prefixed with the agent's name for the same reason channel.write is: a
    # message has to say which agent it came from. In bold, so the answer
    # underneath it is the thing being read.
    vSent = fDeliverAnswerParts(pConfig, dPending, dAnswer)
    if vSent:
      telegram_inbox.fRemovePending(vTurnId)
      fLogLine("Answered turn %s of agent %s on Telegram."
               % (vTurnId, vAgentId))
    elif vSent is None:
      # Telegram said no to this answer and will say no to it again: the bot
      # blocked, the chat gone, the token revoked. Kept, the row was asked
      # about on every pass for ever - the poll in its quick mode, a read of
      # the chat through the root daemon and up to two requests to Telegram
      # each time - and a restart did not end it, because the row is on disk
      # so that a restart does not lose an answer. The answer is not lost:
      # it is in the agent's conversation in the web interface.
      fLogLine("Telegram rejected the answer to turn %s of agent %s; it stays "
               "in the web conversation only." % (vTurnId, vAgentId))
      telegram_inbox.fRemovePending(vTurnId)
    elif telegram_inbox.fIsExpired(dPending):
      # Telegram has not answered for as long as this row is allowed to
      # wait: the same hour the other branch allows, for the same reason.
      fLogLine("Turn %s of agent %s: Telegram unreachable for too long; the "
               "answer stays in the web conversation only."
               % (vTurnId, vAgentId))
      telegram_inbox.fRemovePending(vTurnId)
    else:
      # Telegram is unreachable. Keep the row and try again next pass.
      vStillWaiting += 1
  return vStillWaiting


# ------------------------------------------------------------ the receiving ----

def fHandleMessage(pdMessage, pConfig):
  """Deal with one incoming message. Returns whether a run was started."""
  if (pdMessage.get("from") or {}).get("is_bot"):
    return False
  # Dropped without a word, and without a line in the log either. A stranger
  # who writes to this bot gets no answer, and leaves no record of having
  # written: the id of a chat that is not ours is somebody else's data, and
  # keeping it would mean this installation quietly collects a list of who has
  # found the bot. The cost is that a `chat_id` configured wrongly looks
  # exactly like silence - the configured one is written to the log on every
  # start, which is what there is to compare against.
  if not fIsFromTheConfiguredChat(pdMessage, pConfig):
    return False

  vMessageId = pdMessage.get("message_id")

  # The bot's own commands come first, and only when they are the whole of the
  # first word: an agent called `status` would otherwise be unreachable, and
  # "/status of the disk" addressed to nobody is still /status.
  vFirstWord = str(pdMessage.get("text") or "").strip().split(" ")[0].lstrip("/")
  vFirstWord = re.sub(r"@[A-Za-z0-9_]+bot$", "", vFirstWord, flags=re.I).lower()
  if (str(pdMessage.get("text") or "").lstrip().startswith("/")
      and vFirstWord in (cCommandAgents, cCommandStatus, cCommandHelp,
                         cCommandStart)):
    fLogLine("Command /%s." % (vFirstWord,))
    fHandleCommand(vFirstWord, pdMessage, pConfig)
    return False

  vAgentId, vText = fRouteMessage(pdMessage)

  if not vAgentId:
    # Logged as well as answered. A message that arrives and reaches nobody
    # leaves no other trace, and "I wrote to it and nothing happened" is the
    # hardest thing to tell apart from "it never arrived at all".
    fLogLine("A message from the configured chat named no agent: %r"
             % (str(pdMessage.get("text") or "")[:60],))
    fSay(pConfig, fDescribeAgents(), vMessageId,
         pReplyMarkup=fBuildAgentButtons())
    return False

  # Naming an agent picks it, the same as tapping its button: whoever was
  # addressed on purpose is who the next unaddressed line is for. Replying to
  # an agent counts too - that is an answer to that agent and nobody else.
  fSelectAgent(vAgentId)

  from backend.core import audio_inbox, audio_transcription
  if audio_inbox.fGetTelegramAudio(pdMessage):
    try:
      _vId, vCreated = audio_inbox.fEnqueueTelegram(pdMessage, pConfig, vAgentId, vText)
      if vCreated:
        fSay(pConfig, telegram_texts.fText("audioQueued", None, name=fGetAgentName(vAgentId)), vMessageId, vAgentId)
      return True
    except audio_transcription.AudioError as vError:
      fSay(pConfig, telegram_texts.fText("audioFailed", None, reason=str(vError)), vMessageId)
      return False

  if not vText:
    # An agent named with nothing to do. This is what sending `/os_watcher` on
    # its own produces, so it is not a mistake to complain about: it is
    # somebody halfway through addressing an agent. The answer is registered as
    # that agent's, so replying to it reaches them without the name having to
    # be typed again.
    fLogLine("Agent %s was named with nothing to do; asking for the task."
             % (vAgentId,))
    fSay(pConfig,
         telegram_texts.fText("whatShouldItDo", None,
                              name=fGetAgentName(vAgentId)),
         vMessageId, vAgentId)
    return False

  try:
    dResult = exec_client.fSendChatMessage(vAgentId, vText, pSource="telegram")
  except exec_client.ExecError as vError:
    vReason = str(vError)
    # The executor refuses a second message while the first is still being
    # answered. That is the common case and deserves its own sentence.
    if "still answering" in vReason:
      fSay(pConfig, telegram_texts.fText(
        "busy", None, name=fGetAgentName(vAgentId)), vMessageId)
    else:
      fSay(pConfig, telegram_texts.fText(
        "cannotStart", None, name=fGetAgentName(vAgentId), reason=vReason),
        vMessageId)
    return False

  vTurnId = str(dResult.get("turn_id") or "")
  if vTurnId:
    telegram_inbox.fAddPending(vTurnId, vAgentId, vMessageId)
  fLogLine("Agent %s started a run for a Telegram message." % (vAgentId,))
  return True


def fFetchAndRoute(pConfig, pTimeoutSeconds):
  """Long-poll Telegram once and deal with whatever it hands over."""
  vOffset = fReadOffset()
  try:
    lUpdates = channels.fReadTelegramUpdates(pConfig, vOffset, pTimeoutSeconds)
  except Exception as vError:
    # Redacted here as well as at the source. This catches Exception, so it
    # also catches whatever a future caller forgets to wrap, and a log line
    # written every retry is the worst place to find a token.
    fLogLine("Cannot read from Telegram: %s"
             % (channels.fRedactSecrets(vError, pConfig),))
    time.sleep(cRetrySeconds)
    return 0

  vHandled = 0
  vHighest = vOffset
  for dUpdate in lUpdates:
    vUpdateId = int(dUpdate.get("update_id") or 0)
    vHighest = max(vHighest, vUpdateId + 1)

    dCallback = dUpdate.get("callback_query")
    if dCallback:
      try:
        if fHandleCallback(dCallback, pConfig):
          vHandled += 1
      except Exception as vError:
        fLogLine("Cannot deal with button press %s: %s" % (vUpdateId, vError))
      continue

    dMessage = dUpdate.get("message")
    if not dMessage:
      continue
    try:
      if fHandleMessage(dMessage, pConfig):
        vHandled += 1
    except Exception as vError:
      # One bad message must not stop the others, and must not stop the
      # offset from moving: a message that makes this crash would otherwise
      # be handed over again for ever.
      fLogLine("Cannot deal with update %s: %s" % (vUpdateId, vError))

  if vHighest != vOffset:
    fWriteOffset(vHighest)
  return vHandled


# ------------------------------------------------------------------ the loop ----

def fReadListeningConfig():
  """Return the Telegram configuration if it is set up to listen, else None."""
  try:
    dConfig = channels.fReadChannelConfig(channels.cChannelTelegram)
  except channels.ChannelError:
    return None
  # Listening is opt-in per installation, and separate from sending: an
  # installation can have agents that write to Telegram without anybody being
  # able to write back.
  if not dConfig.get("listen", False):
    return None
  if not dConfig.get("bot_token") or not dConfig.get("chat_id"):
    return None
  return dConfig


# The command list last registered with Telegram, so it is only sent again
# when it would say something different. Module level because the loop has no
# other state and this is not worth a class.
ldRegisteredCommands = []


def fRefreshCommands(pConfig):
  """Register the agent list with Telegram if it has changed.

  This is what puts the agents in the list that appears when somebody types
  `/`, and picking one from there is the only way Telegram will write a name
  into the message box for you.

  Compared before sending because agents change rarely and this runs on every
  pass. A failure is logged and dropped: an out-of-date command list is a
  worse menu, not a broken bot.
  """
  global ldRegisteredCommands
  ldCommands = fBuildCommandList()
  if ldCommands == ldRegisteredCommands:
    return False
  try:
    channels.fSetTelegramCommands(pConfig, ldCommands)
  except Exception as vError:
    fLogLine("Cannot register the command list: %s" % (vError,))
    return False
  ldRegisteredCommands = ldCommands
  fLogLine("Registered %d command(s) for chat %s only: %s"
           % (len(ldCommands), pConfig.get("chat_id") or "?",
              ", ".join("/%s" % (d["command"],) for d in ldCommands)))

  # In the same pass, and only when the list has just been written: the two
  # public texts are what a stranger sees before typing anything, and they are
  # set once by whoever made the bot rather than changing while it runs.
  try:
    channels.fHideTelegramPublicProfile(pConfig)
    fLogLine("Cleared the bot's public description.")
  except Exception as vError:
    fLogLine("Cannot clear the public description: %s" % (vError,))
  return True


def fRunOnePass(pConfig, pPollSeconds=None):
  """One pass: deliver what is ready, then listen for what is new."""
  fRefreshCommands(pConfig)
  vWaiting = fDeliverAnswers(pConfig)
  vTimeout = pPollSeconds
  if vTimeout is None:
    # Poll briefly while an agent is mid-answer, because the poll is what
    # paces the loop and the answer is waiting behind it.
    vTimeout = cBusyPollSeconds if vWaiting else cIdlePollSeconds
  return fFetchAndRoute(pConfig, vTimeout)


def fMain():
  """Listen until stopped."""
  vParser = argparse.ArgumentParser(
    description="Let people answer agents from Telegram.")
  vParser.add_argument(
    "--once", action="store_true",
    help="Do one pass and exit, instead of running as a service."
  )
  vParser.add_argument(
    "--poll", type=int, default=None,
    help="Seconds to hold each poll open. Default: %d, or %d while an agent "
         "is answering." % (cIdlePollSeconds, cBusyPollSeconds)
  )
  dArguments = vParser.parse_args()

  # Bring the database up to date before reading it. Idempotent, and it means
  # this service does not depend on another one having started first: after an
  # update that adds a table, whichever process gets there first creates it.
  try:
    db.fCreateAppSchema()
  except Exception as vError:
    fLogLine("Cannot prepare the database: %s" % (vError,))

  if dArguments.once:
    dConfig = fReadListeningConfig()
    if dConfig is None:
      fLogLine("Telegram is not set up to listen. Nothing to do.")
      return 0
    fLogLine("One pass: %d message(s) handled."
             % (fRunOnePass(dConfig, dArguments.poll),))
    from backend.core import audio_inbox
    audio_inbox.fRunOneJob(dConfig, fSay, fLogLine)
    return 0

  from backend.core import audio_inbox
  audio_inbox.fStartWorker(fReadListeningConfig, fSay, fLogLine)
  fLogLine("Telegram listener started.")
  vWasListening = None
  while True:
    dConfig = fReadListeningConfig()
    if dConfig is None:
      # Not configured, or listening switched off. Say it once rather than
      # every minute, and keep looking: turning it on should not need a
      # restart of anything.
      if vWasListening is not False:
        fLogLine("Telegram is not set up to listen. Waiting for it to be.")
        vWasListening = False
      time.sleep(cRetrySeconds)
      continue

    if vWasListening is not True:
      fLogLine("Listening to Telegram.")
      vWasListening = True
    fRunOnePass(dConfig, dArguments.poll)


if __name__ == "__main__":
  try:
    sys.exit(fMain())
  except KeyboardInterrupt:
    fLogLine("Telegram listener stopping.")
    sys.exit(0)
