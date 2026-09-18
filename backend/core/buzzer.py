#!/usr/bin/env -S PYTHONDONTWRITEBYTECODE=1 python3

"""The buzzer: wakes an agent when one of its cards is due.

A card assigned to an agent used to sit on the board until that agent happened
to wake on its own crontab - which for an agent with no crontab is never. This
service is the other half of assigning work: it watches the board and starts
the run.

    every few seconds:
      cards with an owner, a time that has passed and no buzz yet
        -> ask the executor to start that agent, if it is not already running
        -> the executor announces the card in that agent's chat
        -> record the buzz on the card

Run as `boa`. It needs to read the board, which belongs to boa, and to reach
the executor's socket, which is root:boa - and nothing else. Starting a process
as an agent's own user is the executor's job, and it stays that way: this
service has no privileges of its own to lend.

Four decisions worth knowing about:

  A busy agent is not interrupted. The card keeps its turn and is tried again
  on the next pass, so a run scheduled for 22:00 against a busy agent starts a
  few seconds late rather than not at all, and two runs of one agent never
  overlap.

  The buzz is recorded when the run starts, not when it ends. A card must not
  wake its agent twice, whatever the run then does with it.

  What the agent is told is short and names the card. Everything else it needs
  is on the board, which it can read - and every English sentence the system
  adds to a prompt pushes the agent towards answering in English rather than in
  the language its own prompt is written in.

  The card is announced in the agent's chat, so that conversation shows the
  work the agent was given as well as the work it was asked for by hand. The
  announcement goes with the request to start the run and not a moment earlier:
  a card scheduled for tonight and deleted this afternoon never ran, and a
  conversation saying it was handed over would be a record of something that
  did not happen. The writing itself is the executor's job, because the chat
  file lives in a 0700 home this service cannot enter.
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
  os.path.abspath(__file__)
))))

from backend.core import agents
from backend.core import db
from backend.core import exec_client
from backend.core import kanban

# How often the board is asked. Short enough that "immediately" means what it
# says, long enough that an idle installation is not spending its day asking
# SQLite the same question.
cPollSeconds = 5

# How the agent is told which card woke it.
cCardPromptTemplate = (
  "Card #%(id)s is due: %(title)s\n\n%(body)s\n\n"
  "Work on this card. Move it to doing while you work and to done when it is "
  "finished. If it is not yours to act on, say why in a note."
)

# The orchestrator is told to delegate rather than to do the work itself. Its
# own system prompt says the same thing; this is the reminder at the moment it
# matters.
cManagerAgentId = "000"
cManagerPromptTemplate = (
  "Card #%(id)s is due: %(title)s\n\n%(body)s\n\n"
  "Decide who should do this and assign the card to them. Do the work yourself "
  "only if no agent you have is suited to it."
)


def fLogLine(pMessage):
  """Write one timestamped line to stderr, which systemd collects."""
  sys.stderr.write("[%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), pMessage))
  sys.stderr.flush()


def fBuildPrompt(dCard):
  """Return what the agent is told when this card wakes it."""
  vTemplate = (cManagerPromptTemplate
               if str(dCard.get("owner_agent")) == cManagerAgentId
               else cCardPromptTemplate)
  return vTemplate % {
    "id": dCard["id"],
    "title": dCard["title"],
    "body": (dCard.get("body") or "").strip() or "(no instructions on the card)",
  }


def fGetAgentName(pAgentId):
  """Return an agent's visible name, or its id when it has none.

  Read from the index, which is what a service running as `boa` can read: agent
  homes are 0700 and their info.json is not ours to open.
  """
  vAgentId = str(pAgentId or "")
  if not vAgentId:
    return ""
  try:
    for dAgent in agents.fListIndexedAgents():
      if str(dAgent.get("id")) == vAgentId:
        return str(dAgent.get("name") or vAgentId)
  except Exception:
    pass
  return vAgentId


def fBuildCardAnnouncement(dCard):
  """Return what the agent's chat is told about the card that woke it.

  Two things are worked out here rather than in the browser, because this is the
  only place that has the card: who handed the work over, and whether it was
  asked for straight away or scheduled for a moment. By the time the interface
  draws it, "now" has passed either way.

  `assigned_by` falls back to whoever created the card, for cards that predate
  the column.
  """
  vAssignedBy = str(dCard.get("assigned_by") or dCard.get("created_by") or "")
  return {
    "id": dCard.get("id"),
    "title": dCard.get("title") or "",
    "body": dCard.get("body") or "",
    "run_at": dCard.get("run_at") or "",
    "immediate": kanban.fWasRequestedImmediately(dCard),
    "assigned_by": vAssignedBy,
    # "user" is the person, who has no agent name: the interface says so in
    # their own language.
    "assigned_by_name": ("" if vAssignedBy in ("", "user")
                         else fGetAgentName(vAssignedBy)),
  }


def fRingOne(dCard):
  """Start a run for one due card. Returns whether it started.

  A card whose agent is busy is left exactly as it was - no buzz recorded - so
  the next pass picks it up again.
  """
  vAgentId = str(dCard.get("owner_agent") or "")
  try:
    dResult = exec_client.fRunNow(
      vAgentId, pPrompt=fBuildPrompt(dCard), pOnlyIfIdle=True,
      pCard=fBuildCardAnnouncement(dCard)
    )
  except exec_client.ExecError as vError:
    # The executor is down or restarting. The card keeps its turn.
    fLogLine("Card #%s: cannot reach the executor: %s" % (dCard["id"], vError))
    return False

  if not dResult.get("started"):
    fLogLine("Card #%s: agent %s is busy, will try again."
             % (dCard["id"], vAgentId))
    return False

  kanban.fMarkCardBuzzed(
    dCard["id"], "woke agent %s for this card" % (vAgentId,)
  )
  fLogLine("Card #%s: started a run for agent %s." % (dCard["id"], vAgentId))
  return True


def fRingDueCards():
  """Start a run for every card whose time has come. Returns how many started."""
  try:
    lDue = kanban.fListDueCards()
  except Exception as vError:
    # A pass that fails must not take the service down with it: the board may
    # be locked by a write that is still going.
    fLogLine("Cannot read the board: %s" % (vError,))
    return 0

  vStarted = 0
  for dCard in lDue:
    if fRingOne(dCard):
      vStarted += 1
  return vStarted


def fMain():
  """Watch the board until stopped."""
  vParser = argparse.ArgumentParser(description="Wake agents for due cards.")
  vParser.add_argument(
    "--once", action="store_true",
    help="Do one pass and exit, instead of running as a service."
  )
  vParser.add_argument(
    "--interval", type=int, default=cPollSeconds,
    help="Seconds between passes. Default: %d." % (cPollSeconds,)
  )
  dArguments = vParser.parse_args()

  # Bring the board up to date before reading it. Idempotent, and it means this
  # service does not depend on another one having started first: after an
  # upgrade that adds a column, whichever process gets there first migrates.
  try:
    db.fCreateKanbanSchema()
  except Exception as vError:
    fLogLine("Cannot prepare the board: %s" % (vError,))

  if dArguments.once:
    fLogLine("One pass: %d run(s) started." % (fRingDueCards(),))
    return 0

  fLogLine("Buzzer watching the board every %d seconds."
           % (dArguments.interval,))
  while True:
    fRingDueCards()
    time.sleep(max(1, dArguments.interval))


if __name__ == "__main__":
  try:
    sys.exit(fMain())
  except KeyboardInterrupt:
    fLogLine("Buzzer stopping.")
    sys.exit(0)
