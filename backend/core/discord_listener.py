#!/usr/bin/env -S PYTHONDONTWRITEBYTECODE=1 python3

"""The listener: lets you answer an agent from Discord.

The Telegram half of this is `telegram_listener`, and this is the same idea
over a different network: a message you write in the configured channel
arrives in an agent's chat, starts a run, and the answer comes back to you in
Discord - while the whole exchange sits in that agent's conversation in the
web interface, both halves of it.

    every pass:
      answers  -> for each question still open, ask the executor whether the
                  turn has closed; if it has, send what the agent said back
      messages -> ask Discord for everything newer than the last message dealt
                  with; route each one to an agent and ask the executor to
                  start the run that answers it

Polling, not the Gateway, and not a webhook. Three reasons, in the order they
matter:

  The Gateway is a WebSocket that needs heartbeats, a resume protocol and the
  Message Content Intent switched on in the developer portal. Without that
  last one every message arrives with `content` empty and nothing says why -
  which is a support question this project would be answering for ever.

  Polling connects outwards, so this works on a LAN with nothing forwarded,
  the same way Telegram's long poll does. An interactions webhook would need
  the opposite: a public HTTPS endpoint Discord can reach.

  It costs one request every few seconds. Discord's own limit is fifty a
  second.

What polling cannot do is receive an interaction, which is what a button press
and a slash command are. So there are no buttons here and the commands are
`!agents`, `!status` and `!help` - ordinary messages, which is all a polled
channel can see. `/agents` works too, because somebody who knows the Telegram
bot will type it.

Run as `boa`, like the Telegram listener and for the same reasons: it needs to
read the channel configuration, which is boa's, and to reach the executor's
socket, which is root:boa. Writing into an agent's 0700 home and starting a
process as that agent stay in the executor, because this service has no
privileges of its own to lend.

Four decisions worth knowing about:

  Only the configured channel is read, and only that channel. Everything else
  the bot can see on the server is never asked for.

  Replying routes. Answering a message an agent sent answers that agent, which
  is what makes a conversation feel like a conversation. `@name` starts one.

  A busy agent is told so, not queued. The executor refuses a second message
  while the first is still being answered, and a queue would hide that an
  agent is falling behind.

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
  os.path.abspath(__file__))
)))

from backend.core import agent_routing
from backend.core import channels
from backend.core import db
from backend.core import discord_inbox
from backend.core import discord_texts
from backend.core import exec_client
from backend.core import paths

# How often the channel is asked for new messages when nothing is waiting for
# an answer. Discord has no long poll: the request returns at once, so this is
# a sleep between requests rather than a timeout on one. Five seconds is
# twelve requests a minute against a limit of fifty a second, and it is the
# longest a person waits before deciding the bot is not listening.
cIdlePollSeconds = 5

# And when an agent is in the middle of answering, because then there is
# something about to be worth sending.
cBusyPollSeconds = 2

# How long to wait before looking again when Discord cannot be reached or is
# not configured. Long enough not to hammer anything, short enough that
# turning the channel on does not need a restart.
cRetrySeconds = 60

# The bot's own commands. The same three the Telegram bot has, so that one
# installation does not have two vocabularies.
cCommandAgents = "agents"
cCommandStatus = "status"
cCommandHelp = "help"
cCommandStart = "start"
lCommands = [cCommandAgents, cCommandStatus, cCommandHelp, cCommandStart]

# What may introduce a command. `!` is what a bot on Discord answers to; `/`
# is accepted because whoever set up the Telegram bot will type it out of
# habit, and refusing it would be a puzzle rather than a rule.
lCommandPrefixes = ("!", "/")

# The message types this listens to: an ordinary message and a reply. Discord
# uses the same object for somebody joining the server, a pin, a thread being
# created and a dozen other events, and none of those is anybody talking to an
# agent.
lHandledMessageTypes = [0, 19]

# The lowest id Discord accepts for `after`. Used when the channel is empty
# and there is no message to start from: everything is newer than this.
cOldestSnowflake = "1"

# `@everyone` and a role mention arrive inside the text like anything else.
# Nothing is done about them on the way IN - what a person writes is theirs -
# but an agent's answer never resolves one: see `dDiscordAllowedMentions`.
cMentionPattern = re.compile(r"<@!?(\d+)>")


def fLogLine(pMessage):
  """Write one timestamped line to stderr, which the service's log collects."""
  agent_routing.fLogLine(pMessage)


# ------------------------------------------------------- where it got to ----
#
# Discord has no update counter. What it takes is `after`: the id of the last
# message already dealt with, and ids are ordered, so that one number is the
# whole of "what have I already seen".

def fReadAfterId():
  """Return the last message dealt with, or "" when there is no record."""
  try:
    with open(paths.fGetDiscordAfterPath(), "r", encoding="utf-8") as vFile:
      return (vFile.read() or "").strip()
  except OSError:
    # No file. The caller decides what that means, and it is not "read
    # everything ever said in this channel".
    return ""


def fWriteAfterId(pMessageId):
  """Record the last message dealt with."""
  vPath = paths.fGetDiscordAfterPath()
  vTempPath = "%s.tmp" % (vPath,)
  try:
    with open(vTempPath, "w", encoding="utf-8") as vFile:
      vFile.write("%s\n" % (str(pMessageId),))
    os.replace(vTempPath, vPath)
    return True
  except OSError as vError:
    # Not fatal: the worst case is that a restart re-reads a message. Saying
    # so matters, because that is what a duplicate answer would be explained
    # by.
    fLogLine("Cannot record where Discord got to: %s" % (vError,))
    return False


# ------------------------------------------------------------- the routing ----

def fListAgentNames():
  """Return [(id, name)] for every agent, from the index."""
  return agent_routing.fListAgentNames()


def fGetAgentName(pAgentId):
  """Return an agent's visible name, or its id when it has none."""
  return agent_routing.fGetAgentName(pAgentId)


def fMatchNamedAgent(pText):
  """Return (agent_id, rest) for a message naming an agent.

  `!name` as well as `@name` and `/name`, because `!` is the prefix this bot
  answers to and somebody addressing an agent will reach for it.
  """
  return agent_routing.fMatchNamedAgent(
    pText, agent_routing.lDiscordNamePrefixes)


def fBuildAgentsMessage():
  """Return what !agents answers with: the roster, as a list.

  Telegram puts a button under each name. A polled channel cannot receive a
  button press, so the names are written out with the id beside each - which
  is what somebody types next, and what still works when two agents are
  called almost the same thing.
  """
  lAgents = fListAgentNames()
  if not lAgents:
    return discord_texts.fText("agentsNone")

  lLines = [discord_texts.fText("agentsHeading"), ""]
  for vAgentId, vName in lAgents:
    lLines.append("- **@%s** — `%s`" % (vName or vAgentId, vAgentId))
  return "\n".join(lLines)


def fReadSelectedAgent():
  """Return the agent this conversation is with, or "" if there is none.

  Checked against the roster on the way out: an agent that has been deleted
  since it was picked must not go on catching every message, and silently
  reaching nobody is better than silently reaching whoever took its id.
  """
  try:
    vAgentId = discord_inbox.fGetSelectedAgent()
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
    discord_inbox.fSetSelectedAgent(pAgentId)
  except Exception as vError:
    fLogLine("Cannot record the selected agent: %s" % (vError,))


def fReadMessageText(pdMessage):
  """Return what a message says, with a mention of the bot taken off the front.

  Discord turns `@Boa` into `<@123456789>` before anybody else sees it, so a
  person who addresses the bot the way they address a person sends something
  that starts with a number nobody wrote. Stripped here rather than routed on,
  because what follows it is the instruction.
  """
  vText = str(pdMessage.get("content") or "").strip()
  if cMentionPattern.match(vText):
    vText = cMentionPattern.sub("", vText, count=1).strip()
  return vText


def fRouteMessage(pdMessage):
  """Return (agent_id, text) for one incoming Discord message.

  Three ways to be addressed to somebody, in this order:

    1. It replies to something an agent said. Unambiguous, and what somebody
       reading the channel actually does.
    2. It names an agent: @os-watcher, !os-watcher, @001.
    3. Neither, in which case it goes to whoever was picked last.

  The third is what makes this a conversation rather than a command line.
  Having to name the agent on every line is fine once and tiresome by the
  fourth message, and there is nobody else it could sensibly be for.

  Picking is explicit and sticky: naming an agent, or answering one, changes
  who that is. Nothing else does, so an agent never inherits a conversation by
  being the one who happened to speak last.
  """
  vText = fReadMessageText(pdMessage)
  vRepliedId = str(
    (pdMessage.get("message_reference") or {}).get("message_id") or "")

  if vRepliedId:
    try:
      vAgentId = discord_inbox.fFindAgentForMessage(vRepliedId)
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


def fIsFromTheConfiguredChannel(pdMessage, pConfig):
  """Return whether this message came from the channel this bot is set up for.

  Every message polled came from that channel by construction: it is the only
  one asked about. This checks it anyway, because "by construction" is a
  property of today's code and the cost of being wrong is an agent acting on
  something written somewhere the user never pointed at.
  """
  vConfigured = str(pConfig.get("channel_id") or "").strip()
  if not vConfigured:
    return False
  vFrom = str(pdMessage.get("channel_id") or "").strip()
  return bool(vFrom) and vFrom == vConfigured


# ------------------------------------------------------------- the sending ----

def fSay(pConfig, pText, pReplyToMessageId=None, pAgentId=""):
  """Send one message to the configured channel.

  Returns True when it went out; False when Discord did not answer, which is
  worth trying again; and None when Discord rejected the message and would
  reject it again - the token revoked, the channel gone, the bot removed from
  the server. Both failures are falsy, so a caller that only wants to know
  whether the message arrived tests the result as before; the one caller that
  keeps a message to try again later, fDeliverAnswers, tells the two apart.

  When it carries an agent's words, **every part** of it is remembered as that
  agent's. A long answer arrives as several messages and a person replies to
  whichever one is on their screen; if only the last were routable, replying
  to the first would reach nobody.
  """
  try:
    dResult = channels.fSendToDiscord(pConfig, pText, pReplyToMessageId)
  except channels.ChannelRejected as vError:
    fLogLine("Discord rejected the message: %s"
             % (channels.fRedactSecrets(vError, pConfig),))
    return None
  except Exception as vError:
    # Redacted before it is written: a webhook URL is a credential and a
    # connection failure quotes it. A log anybody on the machine can read is
    # not where one belongs.
    fLogLine("Cannot send to Discord: %s"
             % (channels.fRedactSecrets(vError, pConfig),))
    return False

  if pAgentId:
    for vMessageId in (dResult.get("message_ids") or []):
      try:
        discord_inbox.fRememberMessage(vMessageId, pAgentId)
      except Exception as vError:
        fLogLine("Cannot remember message %s: %s" % (vMessageId, vError))
  return True


# ------------------------------------------------------------- the commands ----

def fBuildStatusReport(pLanguage=None):
  """Return what !status says: the services, the board and every agent."""
  return agent_routing.fBuildStatusReport(
    discord_texts.fText, "boa-discord", pLanguage)


def fHandleCommand(pCommand, pdMessage, pConfig):
  """Deal with one of the bot's own commands. Returns whether it was one.

  None of these replies TO the command. Discord draws a quoted copy of the
  message being answered above the reply, and quoting "!agents" above the list
  of agents says nothing the list does not.

  An agent's answer is still a reply, and for the opposite reason: there the
  quoted line is the question it belongs to, which may be far up the channel
  by the time the run finishes.
  """
  if pCommand in (cCommandAgents, cCommandStart):
    # !start included: somebody trying the bot for the first time is asking
    # exactly this question, and answering with the roster is more use than a
    # greeting.
    fSay(pConfig, fBuildAgentsMessage())
    return True

  if pCommand == cCommandStatus:
    fSay(pConfig, fBuildStatusReport())
    return True

  if pCommand == cCommandHelp:
    fSay(pConfig, discord_texts.fText("helpText"))
    return True

  return False


def fReadCommand(pText):
  """Return the bot command this message is, or "".

  Only when it is the whole of the first word: an agent called `status` would
  otherwise be unreachable, and "!status of the disk" addressed to nobody is
  still !status.
  """
  vText = str(pText or "").strip()
  if not vText or vText[0] not in lCommandPrefixes:
    return ""
  vFirstWord = vText.split(" ")[0][1:].lower()
  return vFirstWord if vFirstWord in lCommands else ""


# ------------------------------------------------------------ the delivery ----

def fFindClosedAnswer(pAgentId, pTurnId):
  """Return what the agent said to close this turn, or "" if it is still open."""
  return agent_routing.fFindClosedAnswer(pAgentId, pTurnId)


def fDeliverAnswers(pConfig):
  """Send back every answer that is ready. Returns how many are still waiting."""
  try:
    lPending = discord_inbox.fListPending()
  except Exception as vError:
    fLogLine("Cannot read what is pending: %s" % (vError,))
    return 0

  vStillWaiting = 0
  for dPending in lPending:
    vTurnId = str(dPending.get("turn_id") or "")
    vAgentId = str(dPending.get("agent_id") or "")
    vAnswer = fFindClosedAnswer(vAgentId, vTurnId)

    if not vAnswer:
      if discord_inbox.fIsExpired(dPending):
        # The run died without closing its turn. Say so rather than leaving
        # somebody waiting for something that is never coming.
        fLogLine("Turn %s of agent %s expired without an answer."
                 % (vTurnId, vAgentId))
        fSay(pConfig,
             "**%s:**\n%s" % (fGetAgentName(vAgentId),
                              discord_texts.fText("neverFinished")),
             dPending.get("reply_to"), vAgentId)
        discord_inbox.fRemovePending(vTurnId)
      else:
        vStillWaiting += 1
      continue

    # Prefixed with the agent's name for the same reason channel.write is: a
    # message has to say which agent it came from. In bold, so the answer
    # underneath it is the thing being read.
    vSent = fSay(pConfig, "**%s:**\n%s" % (fGetAgentName(vAgentId), vAnswer),
                 dPending.get("reply_to"), vAgentId)
    if vSent:
      discord_inbox.fRemovePending(vTurnId)
      fLogLine("Answered turn %s of agent %s on Discord."
               % (vTurnId, vAgentId))
    elif vSent is None:
      # Discord said no to this answer and will say no to it again: the token
      # revoked, the channel gone, the bot removed. Kept, the row would be
      # asked about on every pass for ever, and a restart would not end it
      # because the row is on disk so that a restart does not lose an answer.
      # The answer is not lost: it is in the agent's conversation in the web
      # interface.
      fLogLine("Discord rejected the answer to turn %s of agent %s; it stays "
               "in the web conversation only." % (vTurnId, vAgentId))
      discord_inbox.fRemovePending(vTurnId)
    elif discord_inbox.fIsExpired(dPending):
      # Discord has not answered for as long as this row is allowed to wait:
      # the same hour the other branch allows, for the same reason.
      fLogLine("Turn %s of agent %s: Discord unreachable for too long; the "
               "answer stays in the web conversation only."
               % (vTurnId, vAgentId))
      discord_inbox.fRemovePending(vTurnId)
    else:
      # Discord is unreachable. Keep the row and try again next pass.
      vStillWaiting += 1
  return vStillWaiting


# ------------------------------------------------------------ the receiving ----

def fHandleMessage(pdMessage, pConfig):
  """Deal with one incoming message. Returns whether a run was started."""
  if (pdMessage.get("author") or {}).get("bot"):
    # The bot's own answers come back in the next poll, and so does anything
    # any other bot on the server says.
    return False
  if int(pdMessage.get("type") or 0) not in lHandledMessageTypes:
    # Somebody joined, something was pinned, a thread was made. None of it is
    # a person writing to an agent.
    return False
  if not fIsFromTheConfiguredChannel(pdMessage, pConfig):
    return False

  vMessageId = str(pdMessage.get("id") or "")
  vText = fReadMessageText(pdMessage)

  if not vText:
    # An attachment with no words, or a message whose content is empty. The
    # second is what an installation using the Gateway would see for every
    # message without the Message Content Intent; this one polls, so it means
    # what it says.
    if pdMessage.get("attachments"):
      fLogLine("A message with an attachment and no text was ignored.")
    return False

  vCommand = fReadCommand(vText)
  if vCommand:
    fLogLine("Command !%s." % (vCommand,))
    fHandleCommand(vCommand, pdMessage, pConfig)
    return False

  vAgentId, vText = fRouteMessage(pdMessage)

  if not vAgentId:
    # Logged as well as answered. A message that arrives and reaches nobody
    # leaves no other trace, and "I wrote to it and nothing happened" is the
    # hardest thing to tell apart from "it never arrived at all".
    fLogLine("A message in the configured channel named no agent: %r"
             % (fReadMessageText(pdMessage)[:60],))
    fSay(pConfig, discord_texts.fText("noAgent"), vMessageId)
    return False

  # Naming an agent picks it: whoever was addressed on purpose is who the next
  # unaddressed line is for. Answering an agent counts too - that is an answer
  # to that agent and nobody else.
  fSelectAgent(vAgentId)

  if not vText:
    # An agent named with nothing to do. This is what sending `@os-watcher` on
    # its own produces, so it is not a mistake to complain about: it is
    # somebody halfway through addressing an agent. The answer is registered
    # as that agent's, so replying to it reaches them without the name having
    # to be typed again.
    fLogLine("Agent %s was named with nothing to do; asking for the task."
             % (vAgentId,))
    fSay(pConfig,
         discord_texts.fText("whatShouldItDo", None,
                             name=fGetAgentName(vAgentId)),
         vMessageId, vAgentId)
    return False

  try:
    dResult = exec_client.fSendChatMessage(vAgentId, vText, pSource="discord")
  except exec_client.ExecError as vError:
    vReason = str(vError)
    # The executor refuses a second message while the first is still being
    # answered. That is the common case and deserves its own sentence.
    if "still answering" in vReason:
      fSay(pConfig, discord_texts.fText(
        "busy", None, name=fGetAgentName(vAgentId)), vMessageId)
    else:
      fSay(pConfig, discord_texts.fText(
        "cannotStart", None, name=fGetAgentName(vAgentId), reason=vReason),
        vMessageId)
    return False

  vTurnId = str(dResult.get("turn_id") or "")
  if vTurnId:
    discord_inbox.fAddPending(vTurnId, vAgentId, vMessageId)
  fLogLine("Agent %s started a run for a Discord message." % (vAgentId,))
  return True


def fStartFromTheNewestMessage(pConfig):
  """Record where to start without answering anything that came before.

  A bot switched on this afternoon must not work its way through a month of
  the channel. What is asked for is the newest message, and only its id is
  kept: from the next pass on, `after` does the rest.
  """
  try:
    lMessages = channels.fReadDiscordMessages(pConfig, "", 1)
  except channels.ChannelError as vError:
    fLogLine("Cannot read the channel to find where to start: %s"
             % (channels.fRedactSecrets(vError, pConfig),))
    return False

  if not lMessages:
    # An empty channel: there is nothing to skip. The mark is set to the
    # lowest id there is, so the next pass asks for everything after it and
    # the FIRST message somebody writes is answered. Leaving the mark unset
    # would spend that message on working out where to start, and "I wrote to
    # it and nothing happened" is exactly the failure this project goes out of
    # its way to avoid.
    fWriteAfterId(cOldestSnowflake)
    fLogLine("The channel is empty; the next message written is the first "
             "one answered.")
    return True

  vNewest = str(lMessages[-1].get("id") or "")
  fWriteAfterId(vNewest)
  fLogLine("Starting after message %s: what was said before is not answered."
           % (vNewest,))
  return True


def fFetchAndRoute(pConfig):
  """Ask Discord for what is new and deal with whatever it hands over."""
  vAfter = fReadAfterId()
  if not vAfter:
    fStartFromTheNewestMessage(pConfig)
    return 0

  try:
    lMessages = channels.fReadDiscordMessages(pConfig, vAfter)
  except Exception as vError:
    # Redacted here as well as at the source. This catches Exception, so it
    # also catches whatever a future caller forgets to wrap, and a log line
    # written every retry is the worst place to find a credential.
    fLogLine("Cannot read from Discord: %s"
             % (channels.fRedactSecrets(vError, pConfig),))
    time.sleep(cRetrySeconds)
    return 0

  vHandled = 0
  vHighest = vAfter
  for dMessage in lMessages:
    vMessageId = str(dMessage.get("id") or "")
    if vMessageId:
      vHighest = vMessageId
    try:
      if fHandleMessage(dMessage, pConfig):
        vHandled += 1
    except Exception as vError:
      # One bad message must not stop the others, and must not stop `after`
      # from moving: a message that makes this crash would otherwise be handed
      # over again for ever.
      fLogLine("Cannot deal with message %s: %s" % (vMessageId, vError))

  if vHighest != vAfter:
    fWriteAfterId(vHighest)
  return vHandled


# ------------------------------------------------------------------ the loop ----

def fReadListeningConfig():
  """Return the Discord configuration if it is set up to listen, else None."""
  try:
    dConfig = channels.fReadChannelConfig(channels.cChannelDiscord)
  except channels.ChannelError:
    return None
  # Listening is opt-in per installation, and separate from sending: an
  # installation can have agents that write to Discord without anybody being
  # able to write back.
  if not dConfig.get("listen", False):
    return None
  # A webhook can send and nothing else. Listening needs the bot API, which
  # needs both of these.
  if not dConfig.get("bot_token") or not dConfig.get("channel_id"):
    return None
  return dConfig


def fAnnounceBot(pConfig):
  """Write which bot is listening, and where. Returns whether it answered.

  The first question when nothing arrives is whether this is even the bot that
  was invited to the server, and the second is whether the channel id is the
  one on screen. Both are answered here, once per start, the way the Telegram
  listener writes the chat it registered its commands for.
  """
  try:
    dUser = channels.fReadDiscordBotUser(pConfig)
  except channels.ChannelError as vError:
    fLogLine("Discord did not accept the bot token: %s"
             % (channels.fRedactSecrets(vError, pConfig),))
    return False
  fLogLine("Listening to Discord as %s (%s) on channel %s only."
           % (dUser.get("username") or "?", dUser.get("id") or "?",
              pConfig.get("channel_id") or "?"))
  return True


def fRunOnePass(pConfig):
  """One pass: deliver what is ready, then read what is new.

  Returns how many messages started a run, and how long to wait before the
  next pass: briefly while an agent is mid-answer, because then there is
  something about to be worth sending.
  """
  vWaiting = fDeliverAnswers(pConfig)
  vHandled = fFetchAndRoute(pConfig)
  return (vHandled, cBusyPollSeconds if vWaiting else cIdlePollSeconds)


def fMain():
  """Listen until stopped."""
  vParser = argparse.ArgumentParser(
    description="Let people answer agents from Discord.")
  vParser.add_argument(
    "--once", action="store_true",
    help="Do one pass and exit, instead of running as a service."
  )
  vParser.add_argument(
    "--poll", type=int, default=None,
    help="Seconds between passes. Default: %d, or %d while an agent is "
         "answering." % (cIdlePollSeconds, cBusyPollSeconds)
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
      fLogLine("Discord is not set up to listen. Nothing to do.")
      return 0
    vHandled, vWait = fRunOnePass(dConfig)
    fLogLine("One pass: %d message(s) handled." % (vHandled,))
    return 0

  fLogLine("Discord listener started.")
  vWasListening = None
  while True:
    dConfig = fReadListeningConfig()
    if dConfig is None:
      # Not configured, or listening switched off. Say it once rather than
      # every minute, and keep looking: turning it on should not need a
      # restart of anything.
      if vWasListening is not False:
        fLogLine("Discord is not set up to listen. Waiting for it to be.")
        vWasListening = False
      time.sleep(cRetrySeconds)
      continue

    if vWasListening is not True:
      if not fAnnounceBot(dConfig):
        # A token Discord will not accept is not going to start working in
        # five seconds, and asking it every five would fill the log with the
        # same line for ever.
        time.sleep(cRetrySeconds)
        continue
      vWasListening = True

    vHandled, vWait = fRunOnePass(dConfig)
    time.sleep(dArguments.poll if dArguments.poll is not None else vWait)


if __name__ == "__main__":
  try:
    sys.exit(fMain())
  except KeyboardInterrupt:
    fLogLine("Discord listener stopping.")
    sys.exit(0)
