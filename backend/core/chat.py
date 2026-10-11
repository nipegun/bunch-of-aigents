"""Per-agent chat history.

Talking to an agent is the same thing as running it: the message becomes the
prompt, the agent uses its tools, and its final answer is the reply. So a chat
turn is a run, with the ceilings that any run has.

The history lives in the agent's own home, one JSON object per line:

    /opt/boa/agents/xxx/chat.jsonl

Same reasoning as the run journal: the agent process runs as `agent-xxx` and
cannot write anywhere else, and keeping each agent's conversation in its own
0700 home means one agent cannot read what you said to another.

The web application reads it through the privileged daemon.
"""

import json
import os
import time
import uuid

from backend.core import paths

cChatFileName = "chat.jsonl"

# Turns kept in the file. At a few hundred bytes each this is a small file, and
# it is what the user scrolls back through.
cMaxChatLines = 500

# How many previous turns are replayed to the model. Every replayed turn is
# paid for again on each message, so this is a cost decision as much as a
# memory one: enough for the conversation to make sense, not enough to make a
# long thread expensive.
cReplayedTurns = 10

# Message roles.
cRoleUser = "user"
cRoleAgent = "agent"
cRoleError = "error"
# A card that came due and woke this agent. It opens a turn exactly as a typed
# message does - the agent's answer closes it - so the conversation shows the
# work the agent was given as well as the work it was asked for by hand.
cRoleCard = "card"
# A run nobody typed: the agent's own crontab woke it and it had something to
# report. It is one message and not a turn - nothing asked it anything - so it
# opens nothing and closes nothing.
cRoleRun = "run"

# Roles that ask the agent something, and so are waiting for an answer.
lAskingRoles = [cRoleUser, cRoleCard]

# Tools whose use leaves something the user would see: a card on the board, a
# message on a channel, a mailbox that changed. A scheduled run that used one
# of these has something to say and is written into the chat; a run that only
# looked at things is left in the journal, or an agent that wakes every hour
# would fill the conversation with "nothing to report".
lToolsWorthReporting = [
  "image.send",
  "channel.write",
  "kanban.add_card", "kanban.assign_card", "kanban.delete_card",
  "kanban.move_card",
  "mail.delete", "mail.forward", "mail.move",
]

# Longest card title and body kept in the history. The board holds the card
# itself and enforces its own limits; these are the copy the conversation shows,
# and they are cut here too so that one line of the file cannot grow without
# bound whatever reached the board.
cMaxCardTitleLength = 200
cMaxCardBodyLength = 4000


def fOpenForAppend(pPath):
  """Open a file for appending, creating it 0600 if it does not exist.

  The umask would otherwise create it 0644. The agent home is 0700 so nobody
  else can reach it anyway, but a file that is private on its own survives
  somebody later relaxing the directory.
  """
  vDescriptor = os.open(pPath, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
  return os.fdopen(vDescriptor, "a", encoding="utf-8")


def fGetChatPath(pAgentId):
  """Return the chat history path of one agent."""
  return os.path.join(paths.fGetAgentHome(pAgentId), cChatFileName)


def fAppendMessage(pAgentId, pRole, pText, pTurnId="", pPending=False,
                   pMetadata=None):
  """Append one message to an agent's chat history.

  Never raises: failing to record a message must not abort the run that
  produced it.
  """
  dMessage = {
    "id": uuid.uuid4().hex,
    "turn_id": pTurnId or uuid.uuid4().hex,
    "role": pRole,
    "text": str(pText or ""),
    "pending": bool(pPending),
    "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
  }
  if pMetadata:
    dMessage.update(pMetadata)

  try:
    with fOpenForAppend(fGetChatPath(pAgentId)) as vFile:
      vFile.write(json.dumps(dMessage, ensure_ascii=False) + "\n")
  except OSError:
    return None
  return dMessage


def fAppendRunMessage(pAgentId, pText, pReason, pToolsUsed=None, pAttachments=None):
  """Write what a run nobody asked for ended up saying.

  Always recorded in the journal; this is the second half of the answer to
  "who told me that?". A run that changed something, or that failed, is worth
  seeing where the user already reads what this agent says.

  `reason` travels as a name rather than as a sentence, like `ceiling` does:
  the interface writes the sentence in the user's own language.
  """
  return fAppendMessage(
    pAgentId, cRoleRun, pText, pTurnId="", pPending=False,
    pMetadata={
      "reason": pReason,
      "tools_used": sorted(set(pToolsUsed or [])),
      **({"attachments": list(pAttachments)} if pAttachments else {}),
    }
  )


def fIsRunWorthReporting(pStatus, pToolsUsed):
  """Whether a run nobody asked for should appear in the chat.

  Two cases: it did not finish, or it changed something outside the agent's
  own home. Everything else - looked, read, remembered - stays in the
  journal. An agent on an hourly crontab would otherwise post twelve
  "nothing to report" messages a day into the conversation.
  """
  if pStatus != "finished":
    return True
  return any(vTool in lToolsWorthReporting for vTool in (pToolsUsed or []))


def fAppendCardMessage(pAgentId, pdCard, pTurnId=""):
  """Announce in the chat that a card came due, and open its turn.

  Written the moment the run starts and not when the card was created: a card
  the user schedules for tonight and deletes this afternoon never ran, and a
  conversation claiming it was handed over would be a record of something that
  did not happen.

  The text of the message is the card's own instructions and nothing else. What
  the interface says around it - who assigned it, whether it was asked for now
  or for a time - is built from the fields below, in the user's own language,
  for the same reason a stopped run records `ceiling: "tokens"` rather than an
  English sentence.
  """
  return fAppendMessage(
    pAgentId, cRoleCard,
    str(pdCard.get("body") or "")[:cMaxCardBodyLength],
    pTurnId, pPending=True,
    pMetadata={
      "card_id": pdCard.get("id"),
      "card_title": str(pdCard.get("title") or "")[:cMaxCardTitleLength],
      "card_run_at": str(pdCard.get("run_at") or ""),
      "card_immediate": bool(pdCard.get("immediate")),
      "card_assigned_by": str(pdCard.get("assigned_by") or ""),
      "card_assigned_by_name": str(pdCard.get("assigned_by_name") or ""),
    }
  )


def fBuildCardTurnText(pdMessage):
  """Return what the model is replayed for a card turn.

  The title and the id go back in, because the body on its own reads as an
  instruction with no subject - and the agent may well have moved that very
  card since.
  """
  vTitle = str(pdMessage.get("card_title") or "")
  vBody = str(pdMessage.get("text") or "")
  vHeader = "Card #%s: %s" % (pdMessage.get("card_id"), vTitle)
  return "%s\n\n%s" % (vHeader, vBody) if vBody else vHeader


def fReadMessages(pAgentId, pLimit=None):
  """Return an agent's chat history, oldest first.

  Read through paths.fReadAgentOwnedFile, for the same reason the journal is:
  the daemon reads this as root out of a directory the agent owns, so only a
  regular file of the agent's is accepted, and never more than cMaxChatBytes
  of it - the newest lines when it is larger, which is the end of the
  conversation that gets shown.
  """
  lMessages = []
  try:
    vText, _vTruncated = paths.fReadAgentOwnedFile(
      pAgentId, fGetChatPath(pAgentId), paths.cMaxChatBytes, pKeepEnd=True)
  except PermissionError:
    # A FIFO, a link, a file that is not the agent's: not a conversation.
    # Said rather than swallowed.
    raise
  except OSError:
    return []
  for vLine in vText.splitlines():
    vLine = vLine.strip()
    if not vLine:
      continue
    try:
      lMessages.append(json.loads(vLine))
    except ValueError:
      continue

  # A turn whose answer arrived is no longer pending, whatever the line that
  # opened it said: the file is append-only, so the later line wins.
  sAnswered = set()
  for dMessage in lMessages:
    if dMessage.get("role") in (cRoleAgent, cRoleError):
      sAnswered.add(dMessage.get("turn_id"))
  for dMessage in lMessages:
    if dMessage.get("turn_id") in sAnswered:
      dMessage["pending"] = False

  if pLimit:
    return lMessages[-int(pLimit):]
  return lMessages


def fTurnIsOpen(pAgentId, pTurnId):
  """Return True while one turn has a question and no answer or error yet.

  Asked by the daemon about a run that ended without a word: a runner that
  wrote its own error before dying has closed the turn already, and one
  that was killed has not.
  """
  vTurnId = str(pTurnId or "")
  if not vTurnId:
    return False
  vAsked = False
  for dMessage in fReadMessages(pAgentId):
    if dMessage.get("turn_id") != vTurnId:
      continue
    if dMessage.get("role") in lAskingRoles:
      vAsked = True
    elif dMessage.get("role") in (cRoleAgent, cRoleError):
      return False
  return vAsked


def fHasPendingTurn(pAgentId):
  """Return True when a question is still waiting for its answer.

  A card that woke the agent counts: the agent is working on it, and while it
  is, the composer has to say so rather than letting a second run be started on
  top of the first.
  """
  for dMessage in fReadMessages(pAgentId):
    if dMessage.get("role") in lAskingRoles and dMessage.get("pending"):
      return True
  return False


def fBuildConversationForModel(pAgentId, pNewMessage, pTurns=None):
  """Return the neutral message list for one chat turn.

  Replays the last few exchanges so the agent remembers the conversation, then
  appends what the user just said. Pending questions that never got an answer
  are skipped: replaying them would have the agent answer them again.
  """
  lHistory = fReadMessages(pAgentId)
  lTurns = []
  dCurrentTurn = {}

  for dMessage in lHistory:
    if dMessage.get("role") == cRoleUser:
      dCurrentTurn = {"user": dMessage.get("text", ""), "agent": None}
    elif dMessage.get("role") == cRoleCard:
      # A card the agent was woken for is replayed as what it was asked, so a
      # later question about "that card" finds it in the conversation.
      dCurrentTurn = {"user": fBuildCardTurnText(dMessage), "agent": None}
    elif dMessage.get("role") == cRoleAgent and dCurrentTurn:
      dCurrentTurn["agent"] = dMessage.get("text", "")
      lTurns.append(dCurrentTurn)
      dCurrentTurn = {}
    elif dMessage.get("role") in (cRoleError, cRoleRun):
      # Neither is an exchange. A scheduled run in particular is never
      # replayed: it is a report, nobody asked it anything, and replaying one
      # would have the user paying for every hourly run on their next message.
      dCurrentTurn = {}

  lRecent = lTurns[-int(pTurns or cReplayedTurns):]
  lMessages = []
  for dTurn in lRecent:
    lMessages.append({"role": "user", "content": dTurn["user"]})
    if dTurn["agent"]:
      lMessages.append({"role": "assistant", "content": dTurn["agent"]})
  lMessages.append({"role": "user", "content": str(pNewMessage or "")})
  return lMessages


def fTrimHistory(pAgentId, pMaxLines=None):
  """Keep only the most recent lines of a chat history."""
  vMaxLines = int(pMaxLines or cMaxChatLines)
  vChatPath = fGetChatPath(pAgentId)
  try:
    with open(vChatPath, "r", encoding="utf-8") as vFile:
      lLines = vFile.readlines()
  except OSError:
    return False
  if len(lLines) <= vMaxLines:
    return False
  vTempPath = vChatPath + ".tmp"
  try:
    with open(vTempPath, "w", encoding="utf-8") as vFile:
      vFile.writelines(lLines[-vMaxLines:])
    os.chmod(vTempPath, 0o600)
    os.replace(vTempPath, vChatPath)
  except OSError:
    try:
      os.unlink(vTempPath)
    except OSError:
      pass
    return False
  return True


def fClearHistory(pAgentId):
  """Delete an agent's chat history."""
  try:
    os.unlink(fGetChatPath(pAgentId))
  except FileNotFoundError:
    return True
  except OSError:
    return False
  return True
