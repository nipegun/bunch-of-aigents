"""What both listeners do the same way: who a message is for, and what /status says.

There are two services that take a message from a person and hand it to an
agent - `telegram_listener` and `discord_listener` - and most of what they do
is protocol. Long polling is not the same as REST polling, an inline keyboard
is not a list of names, and a reply is `reply_to_message` in one and
`message_reference` in the other. That part belongs in each of them.

What is not protocol is here, and here once:

  - Which agents exist, and what each is called.
  - Reading an agent's name out of a message: `@News Miner`, `/news_miner`,
    `@002`. The longest match wins, and getting that wrong the same way twice
    is how `@News` and `@News Miner` become one ambiguity in one channel and
    two agents in the other.
  - What an agent said to close a turn.
  - The status report, which is the one piece of user-facing text in either
    service that would quietly rot if it were written twice: a report that
    lists five services on Telegram and six on Discord is a report nobody can
    use to answer "is it running".

Everything in here is read-only and speaks to nobody: it reads the index, it
asks the executor, and it returns text. Sending belongs to the caller, which
is what lets a test replace one listener's `fSay` without the other noticing.
"""

import os
import re
import sys
import time

from backend.core import agents
from backend.core import chat
from backend.core import exec_client

# What a name has to be reduced to before a chat application will take it as a
# command: one to thirty-two characters of lowercase letters, digits and
# underscores. Telegram enforces it; Discord does not, and uses the same shape
# so that `/news_miner` means the same thing in both.
cCommandPattern = re.compile(r"[^a-z0-9_]+")
cMaxCommandLength = 32

# The socket the agent API listens on. Its presence is the whole check: a
# service that is up has it, and one that is down does not.
cAgentApiSocketPath = "/run/boa-agent/agent.sock"


def fLogLine(pMessage):
  """Write one timestamped line to stderr, which the service's log collects."""
  sys.stderr.write("[%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), pMessage))
  sys.stderr.flush()


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


def fGetAgentName(pAgentId):
  """Return an agent's visible name, or its id when it has none."""
  for vAgentId, vName in fListAgentNames():
    if vAgentId == str(pAgentId):
      return vName or str(pAgentId)
  return str(pAgentId)


def fBuildCommandName(pName, pAgentId):
  """Return the /command for an agent, which Telegram is strict about.

  Lowercase letters, digits and underscores only, so "News Miner" becomes
  `news_miner`. A name left with nothing usable - one written in an alphabet
  Telegram will not take - falls back to the id, which always works.
  """
  vCommand = cCommandPattern.sub("_", str(pName or "").lower()).strip("_")
  vCommand = vCommand[:cMaxCommandLength]
  return vCommand or ("agent_%s" % (pAgentId,))


# What may introduce an agent's name. Telegram takes the first two: `@` is how
# a person writes one from memory and `/` is what its command menu puts in the
# box. Discord adds `!`, the shape every bot on that network answers to - and
# gets it as an argument rather than as a third entry here, because widening
# Telegram's rule to suit Discord would change what an existing installation
# does with a line starting `!`.
lDefaultNamePrefixes = ("@", "/")
lDiscordNamePrefixes = ("@", "/", "!")


def fMatchNamedAgent(pText, plPrefixes=lDefaultNamePrefixes):
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
  if not any(vText.startswith(vPrefix) for vPrefix in plPrefixes):
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
  # "@os-watcher: check the disk" is a natural way to write it, and the colon
  # belongs to the address, not to the instruction. Same for a comma or a dash.
  return (vBestId, vRest[vBestLength:].lstrip(" :,-–—\t").strip())


def fFindClosedMessage(pAgentId, pTurnId):
  """Return the reply and its attachment references, or None while open.

  Read through the executor: the conversation lives in a 0700 home no listener
  can enter.
  """
  try:
    dResult = exec_client.fReadChat(pAgentId)
  except exec_client.ExecError as vError:
    fLogLine("Cannot read the chat of agent %s: %s" % (pAgentId, vError))
    return None

  for dMessage in reversed(dResult.get("messages") or []):
    if str(dMessage.get("turn_id")) != str(pTurnId):
      continue
    if dMessage.get("role") in (chat.cRoleAgent, chat.cRoleError):
      return dMessage
  return None


def fFindClosedAnswer(pAgentId, pTurnId):
  """Return the reply text for callers that do not deliver attachments."""
  dMessage = fFindClosedMessage(pAgentId, pTurnId)
  return str((dMessage or {}).get("text") or "")


def fBuildStatusReport(pfText, pServiceName, pLanguage=None):
  """Return what /status says: the services, the board and every agent.

  `pfText` is the asking service's own catalogue of sentences and
  `pServiceName` is the unit it runs as, because those are the only two things
  that differ between the two listeners. Everything else - what is checked and
  how it is phrased - is one answer to one question and is written once.

  Read the same way the web interface reads it: the executor for anything
  inside an agent's 0700 home, the index and the board directly. A listener
  has no more privilege than that page does.

  An agent whose info.json cannot be read is listed saying so rather than left
  out. A status report that quietly drops what it could not check is worse
  than no report: the one agent missing is the one worth asking about.
  """
  lLines = [pfText("statusHeading", pLanguage), ""]

  # The two services that stop everything when they are down. There is nothing
  # to check for the third: it is the thing writing the answer.
  vExecutorUp = True
  try:
    exec_client.fPing()
  except Exception:
    vExecutorUp = False
  vAgentApiUp = os.path.exists(cAgentApiSocketPath)

  vUp = pfText("statusServiceUp", pLanguage)
  vDown = pfText("statusServiceDown", pLanguage)
  lLines.append(pfText("statusServices", pLanguage))
  lLines.append("- boa-exec: %s" % (vUp if vExecutorUp else vDown,))
  lLines.append("- boa-agent-api: %s" % (vUp if vAgentApiUp else vDown,))
  lLines.append("- %s: %s" % (pServiceName, vUp))
  lLines.append("")

  try:
    from backend.core import kanban
    dCounts = kanban.fCountByState()
    lLines.append(pfText(
      "statusBoard", pLanguage, todo=dCounts.get("todo", 0),
      doing=dCounts.get("doing", 0), done=dCounts.get("done", 0)))
    lLines.append("")
  except Exception as vError:
    fLogLine("Cannot read the board for /status: %s" % (vError,))

  lAgents = fListAgentNames()
  lLines.append(pfText("statusAgents", pLanguage, count=len(lAgents)))

  for vAgentId, vName in lAgents:
    try:
      dInfo = exec_client.fReadAgentInfo(vAgentId).get("info") or {}
    except Exception:
      lLines.append("- **%s** %s — %s" % (
        vAgentId, vName or vAgentId, pfText("statusUnreadable", pLanguage)))
      continue

    vState = pfText(
      "statusAgentOn" if dInfo.get("enabled", True) else "statusAgentOff",
      pLanguage)
    dProvider = dInfo.get("provider") or {}
    vModel = dProvider.get("model") or ""
    vProvider = ("%s %s" % (dProvider.get("name") or "", vModel)).strip()
    if not vModel:
      vProvider = pfText("statusNoModel", pLanguage)

    lLines.append("- **%s** %s — %s, %s" % (
      vAgentId, vName or vAgentId, vState, vProvider))
    vTools = len(dInfo.get("tools") or [])
    vSkills = len(dInfo.get("skills") or [])
    lLines.append("  %d %s, %d %s" % (
      vTools,
      pfText("statusTool" if vTools == 1 else "statusTools", pLanguage),
      vSkills,
      pfText("statusSkill" if vSkills == 1 else "statusSkills", pLanguage)))
    lTools = [str(vTool) for vTool in (dInfo.get("tools") or [])]
    if lTools:
      lLines.append("  `%s`" % ("`, `".join(sorted(lTools)),))

  return "\n".join(lLines)
