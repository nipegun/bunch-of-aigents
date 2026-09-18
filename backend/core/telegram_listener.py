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

from backend.core import agents
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

# What a name has to be reduced to before Telegram will take it as a command:
# one to thirty-two characters of lowercase letters, digits and underscores.
cCommandPattern = re.compile(r"[^a-z0-9_]+")
cMaxCommandLength = 32

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
  sys.stderr.write("[%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), pMessage))
  sys.stderr.flush()


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
  try:
    return [(str(dAgent.get("id")), str(dAgent.get("name") or ""))
            for dAgent in agents.fListIndexedAgents()]
  except Exception as vError:
    fLogLine("Cannot read the agents index: %s" % (vError,))
    return []


def fBuildCommandName(pName, pAgentId):
  """Return the /command for an agent, which Telegram is strict about.

  Lowercase letters, digits and underscores only, so "News Miner" becomes
  `news_miner`. A name left with nothing usable - one written in an alphabet
  Telegram will not take - falls back to the id, which always works.
  """
  vCommand = cCommandPattern.sub("_", str(pName or "").lower()).strip("_")
  vCommand = vCommand[:cMaxCommandLength]
  return vCommand or ("agent_%s" % (pAgentId,))


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

  A button says `@oswatcher` and nothing else, which is the one thing the
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
  vText = str(pText or "").lstrip()
  if not (vText.startswith("@") or vText.startswith("/")):
    return ("", vText)

  vRest = vText[1:]
  # Telegram appends @botname to a command sent in a group.
  vRest = re.sub(r"^([^\s]+)@[A-Za-z0-9_]+bot\b", r"\1", vRest, flags=re.I)
  vLowered = vRest.lower()
  vBestId = ""
  vBestLength = 0
  for vAgentId, vName in fListAgentNames():
    # The command form as well as the name: /news_miner has to reach the agent
    # called "News Miner", because that is what Telegram writes in the box.
    for vCandidate in (vName, fBuildCommandName(vName, vAgentId), vAgentId):
      if not vCandidate:
        continue
      if len(vCandidate) <= vBestLength:
        continue
      if vLowered.startswith(vCandidate.lower()):
        vBestId = vAgentId
        vBestLength = len(vCandidate)

  if not vBestId:
    return ("", vText)
  # "@oswatcher: check the disk" is a natural way to write it, and the colon
  # belongs to the address, not to the instruction. Same for a comma or a dash.
  return (vBestId, vRest[vBestLength:].lstrip(" :,-–—\t").strip())


def fRouteMessage(dMessage):
  """Return (agent_id, text) for one incoming Telegram message.

  Three ways to be addressed to somebody, in this order:

    1. It replies to something an agent said. Unambiguous, and what somebody
       holding a phone actually does.
    2. It names an agent: @oswatcher, /oswatcher, @001.
    3. Neither, in which case it goes to whoever was picked last.

  The third is what makes this a conversation rather than a command line.
  Having to name the agent on every line is fine once and tiresome by the
  fourth message, and there is nobody else it could sensibly be for.

  Picking is explicit and sticky: tapping a name in /agents, or naming one,
  changes who that is. Nothing else does, so an agent never inherits a
  conversation by being the one who happened to speak last.
  """
  vText = str(dMessage.get("text") or "").strip()
  dReplyTo = dMessage.get("reply_to_message") or {}
  vRepliedId = dReplyTo.get("message_id")

  if vRepliedId:
    try:
      vAgentId = telegram_inbox.fFindAgentForMessage(vRepliedId)
    except Exception as vError:
      fLogLine("Cannot look up message %s: %s" % (vRepliedId, vError))
      vAgentId = ""
    if vAgentId:
      # A named agent in the text of a reply is not a contradiction worth
      # refusing: strip it if it is there, so "@oswatcher yes" as a reply to
      # oswatcher does not reach it with its own name glued to the front.
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


def fIsFromTheConfiguredChat(dMessage, pConfig):
  """Return whether this message came from the chat this bot is set up for.

  A bot's username is public and anybody who finds it can write to it. Nothing
  else is a chat with the owner of this installation.
  """
  vConfigured = str(pConfig.get("chat_id") or "").strip()
  if not vConfigured:
    return False
  vFrom = str((dMessage.get("chat") or {}).get("id") or "").strip()
  return bool(vFrom) and vFrom == vConfigured


# ------------------------------------------------------------- the sending ----

def fSay(pConfig, pText, pReplyToMessageId=None, pAgentId="",
         pReplyMarkup=None):
  """Send one message to the configured chat. Returns whether it went out.

  When it carries an agent's words, the id Telegram gives it is remembered, so
  that replying to it reaches that agent again. That is what turns a single
  answer into a conversation you can keep having.
  """
  try:
    dResult = channels.fSendToTelegram(
      pConfig, pText, pReplyToMessageId, pReplyMarkup)
  except Exception as vError:
    fLogLine("Cannot send to Telegram: %s" % (vError,))
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
  for vAgentId, vName in fListAgentNames():
    if vAgentId == str(pAgentId):
      return vName or str(pAgentId)
  return str(pAgentId)


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
  lLines = [telegram_texts.fText("statusHeading", pLanguage), ""]

  # The two services that stop everything when they are down. There is nothing
  # to check for this one: it is the thing writing the answer.
  vExecutorUp = True
  try:
    exec_client.fPing()
  except Exception:
    vExecutorUp = False
  vAgentApiUp = os.path.exists("/run/boa-agent/agent.sock")

  vUp = telegram_texts.fText("statusServiceUp", pLanguage)
  vDown = telegram_texts.fText("statusServiceDown", pLanguage)
  lLines.append(telegram_texts.fText("statusServices", pLanguage))
  lLines.append("- boa-exec: %s" % (vUp if vExecutorUp else vDown,))
  lLines.append("- boa-agent-api: %s" % (vUp if vAgentApiUp else vDown,))
  lLines.append("- boa-telegram: %s" % (vUp,))
  lLines.append("")

  try:
    from backend.core import kanban
    dCounts = kanban.fCountByState()
    lLines.append(telegram_texts.fText(
      "statusBoard", pLanguage, todo=dCounts.get("todo", 0),
      doing=dCounts.get("doing", 0), done=dCounts.get("done", 0)))
    lLines.append("")
  except Exception as vError:
    fLogLine("Cannot read the board for /status: %s" % (vError,))

  lAgents = fListAgentNames()
  lLines.append(telegram_texts.fText(
    "statusAgents", pLanguage, count=len(lAgents)))

  for vAgentId, vName in lAgents:
    try:
      dInfo = exec_client.fReadAgentInfo(vAgentId).get("info") or {}
    except Exception:
      lLines.append("- **%s** %s — %s" % (
        vAgentId, vName or vAgentId,
        telegram_texts.fText("statusUnreadable", pLanguage)))
      continue

    vState = telegram_texts.fText(
      "statusAgentOn" if dInfo.get("enabled", True) else "statusAgentOff",
      pLanguage)
    dProvider = dInfo.get("provider") or {}
    vModel = dProvider.get("model") or ""
    vProvider = ("%s %s" % (dProvider.get("name") or "", vModel)).strip()
    if not vModel:
      vProvider = telegram_texts.fText("statusNoModel", pLanguage)

    lLines.append("- **%s** %s — %s, %s" % (
      vAgentId, vName or vAgentId, vState, vProvider))
    vTools = len(dInfo.get("tools") or [])
    vSkills = len(dInfo.get("skills") or [])
    lLines.append("  %d %s, %d %s" % (
      vTools,
      telegram_texts.fText(
        "statusTool" if vTools == 1 else "statusTools", pLanguage),
      vSkills,
      telegram_texts.fText(
        "statusSkill" if vSkills == 1 else "statusSkills", pLanguage)))
    lTools = [str(vTool) for vTool in (dInfo.get("tools") or [])]
    if lTools:
      lLines.append("  `%s`" % ("`, `".join(sorted(lTools)),))

  return "\n".join(lLines)


def fHandleCommand(pCommand, dMessage, pConfig):
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


def fHandleCallback(dCallback, pConfig):
  """Deal with a tap on one of the agent buttons.

  Telegram shows a spinner on the button until the callback is answered, so
  that goes first and happens whatever else does.
  """
  vData = str(dCallback.get("data") or "")
  dMessage = dCallback.get("message") or {}

  try:
    channels.fAnswerTelegramCallback(pConfig, dCallback.get("id"))
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
  try:
    dResult = exec_client.fReadChat(pAgentId)
  except exec_client.ExecError as vError:
    fLogLine("Cannot read the chat of agent %s: %s" % (pAgentId, vError))
    return ""

  for dMessage in reversed(dResult.get("messages") or []):
    if str(dMessage.get("turn_id")) != str(pTurnId):
      continue
    if dMessage.get("role") in (chat.cRoleAgent, chat.cRoleError):
      return str(dMessage.get("text") or "")
  return ""


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
    vAnswer = fFindClosedAnswer(vAgentId, vTurnId)

    if not vAnswer:
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
    if fSay(pConfig, "**%s:**\n%s" % (fGetAgentName(vAgentId), vAnswer),
            dPending.get("reply_to"), vAgentId):
      telegram_inbox.fRemovePending(vTurnId)
      fLogLine("Answered turn %s of agent %s on Telegram."
               % (vTurnId, vAgentId))
    else:
      # Telegram is unreachable. Keep the row and try again next pass.
      vStillWaiting += 1
  return vStillWaiting


# ------------------------------------------------------------ the receiving ----

def fHandleMessage(dMessage, pConfig):
  """Deal with one incoming message. Returns whether a run was started."""
  if (dMessage.get("from") or {}).get("is_bot"):
    return False
  # Dropped without a word, and without a line in the log either. A stranger
  # who writes to this bot gets no answer, and leaves no record of having
  # written: the id of a chat that is not ours is somebody else's data, and
  # keeping it would mean this installation quietly collects a list of who has
  # found the bot. The cost is that a `chat_id` configured wrongly looks
  # exactly like silence - the configured one is written to the log on every
  # start, which is what there is to compare against.
  if not fIsFromTheConfiguredChat(dMessage, pConfig):
    return False

  vMessageId = dMessage.get("message_id")

  # The bot's own commands come first, and only when they are the whole of the
  # first word: an agent called `status` would otherwise be unreachable, and
  # "/status of the disk" addressed to nobody is still /status.
  vFirstWord = str(dMessage.get("text") or "").strip().split(" ")[0].lstrip("/")
  vFirstWord = re.sub(r"@[A-Za-z0-9_]+bot$", "", vFirstWord, flags=re.I).lower()
  if (str(dMessage.get("text") or "").lstrip().startswith("/")
      and vFirstWord in (cCommandAgents, cCommandStatus, cCommandHelp,
                         cCommandStart)):
    fLogLine("Command /%s." % (vFirstWord,))
    fHandleCommand(vFirstWord, dMessage, pConfig)
    return False

  vAgentId, vText = fRouteMessage(dMessage)

  if not vAgentId:
    # Logged as well as answered. A message that arrives and reaches nobody
    # leaves no other trace, and "I wrote to it and nothing happened" is the
    # hardest thing to tell apart from "it never arrived at all".
    fLogLine("A message from the configured chat named no agent: %r"
             % (str(dMessage.get("text") or "")[:60],))
    fSay(pConfig, fDescribeAgents(), vMessageId,
         pReplyMarkup=fBuildAgentButtons())
    return False

  # Naming an agent picks it, the same as tapping its button: whoever was
  # addressed on purpose is who the next unaddressed line is for. Replying to
  # an agent counts too - that is an answer to that agent and nobody else.
  fSelectAgent(vAgentId)

  if not vText:
    # An agent named with nothing to do. This is what sending `/oswatcher` on
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
    fLogLine("Cannot read from Telegram: %s" % (vError,))
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
    return 0

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
