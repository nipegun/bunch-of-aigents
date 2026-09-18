"""The kanban board.

The board is the shared memory of the installation: it is where agents leave
each other work, and where the user sees what has actually been done rather
than having to read logs.

It is a SQLite database and not a directory of JSON files because several
agents write to it at the same time - an agent waking on the same cron minute
as three others is the normal case, not the exception - and only a transaction
prevents two simultaneous additions from overwriting each other.

Every change is also appended to `card_events`, so a card carries its own
history: who moved it, when, and why. That history is what makes a board
trustworthy when the things moving the cards are unattended processes.
"""

import datetime

from backend.core import db

# How a scheduled time is written: UTC, to the second, the same shape SQLite's
# datetime('now') produces, so the two can be compared as strings.
cTimeFormat = "%Y-%m-%d %H:%M:%S"

# The three columns. There are deliberately only three: a board an agent has to
# reason about is better with few states than with a faithful copy of a human
# team's workflow.
cStateTodo = "todo"
cStateDoing = "doing"
cStateDone = "done"

lStates = [cStateTodo, cStateDoing, cStateDone]

# Field limits. A model asked for a card title will happily write an essay.
cMaxTitleLength = 200
cMaxBodyLength = 8000
cMaxNoteLength = 1000

# The two kinds of time a card can have. `cRunNow` is also the word the browser
# and the agents send instead of a timestamp.
cRunNow = "now"
cRunAtTime = "at"

# Default page size when listing a column.
cDefaultListLimit = 50
cMaxListLimit = 500


class KanbanError(ValueError):
  """Raised when a card operation is invalid."""


def fValidateState(pState):
  """Return a validated column name."""
  vState = str(pState or "").strip().lower()
  if vState not in lStates:
    raise KanbanError(
      "Unknown state %r. Use one of: %s" % (pState, ", ".join(lStates))
    )
  return vState


def fNowText():
  """Return the current UTC time in the format the board stores."""
  return datetime.datetime.now(datetime.timezone.utc).strftime(cTimeFormat)


def fValidateRunAt(pRunAt):
  """Return a validated scheduled time, or None.

  Accepts the word "now", what a browser's datetime-local sends
  (`2026-09-12T22:30`) and the stored shape, and normalises all of them to
  seconds. A time is not rejected for being in the past: "run this at 22:00"
  typed at 22:01 means "run it now", and refusing it would be pedantry at the
  user's expense.

  "now" is a word and not a timestamp everywhere it travels, because the
  browser's clock and the server's do not have to agree and only the server's
  decides when a card is due. It is turned into a time here, in the one place
  that also records that it was asked for as "now".
  """
  if pRunAt is None:
    return None
  vText = str(pRunAt).strip()
  if not vText:
    return None
  if vText.lower() == cRunNow:
    return fNowText()
  vText = vText.replace("T", " ")
  for vFormat in [cTimeFormat, "%Y-%m-%d %H:%M"]:
    try:
      return datetime.datetime.strptime(vText, vFormat).strftime(cTimeFormat)
    except ValueError:
      continue
  raise KanbanError(
    "Cannot read %r as a time. Use YYYY-MM-DD HH:MM." % (pRunAt,)
  )


def fReadRunMode(pRunAt):
  """Return which kind of time was asked for: "now", a chosen moment, or none.

  Taken from what the caller wrote and not from comparing the result against
  the clock: a card scheduled for 13:45 and picked up at 13:46 has a `run_at`
  in the past, exactly like one asked for straight away, and the agent is told
  which of the two it was.
  """
  vText = str(pRunAt or "").strip()
  if not vText:
    return None
  return cRunNow if vText.lower() == cRunNow else cRunAtTime


def fValidateTitle(pTitle):
  """Return a validated card title."""
  vTitle = " ".join(str(pTitle or "").split())
  if not vTitle:
    raise KanbanError("A card needs a title")
  if len(vTitle) > cMaxTitleLength:
    vTitle = vTitle[:cMaxTitleLength - 1] + "…"
  return vTitle


def fTruncate(pText, pLimit):
  """Return text cut to a limit, with an ellipsis when it was cut."""
  vText = str(pText or "")
  if len(vText) <= pLimit:
    return vText
  return vText[:pLimit - 1] + "…"


def fAddCard(pTitle, pBody="", pState=cStateTodo, pOwnerAgent=None,
             pCreatedBy="", pNote="", pRunAt=None):
  """Add a card and return it.

  The card and its first event are written in one transaction: a card with no
  history would be a card nobody can account for.

  `pRunAt` is when the owner should be woken up for it, in UTC. None leaves the
  card waiting on the board with nobody woken for it.

  Whoever creates a card with an owner is also the one who assigned it, so
  `assigned_by` starts as the creator. A card with no owner has not been
  assigned to anybody yet and says so by leaving it empty.
  """
  vTitle = fValidateTitle(pTitle)
  vState = fValidateState(pState)
  vBody = fTruncate(pBody, cMaxBodyLength)
  vOwner = str(pOwnerAgent or "") or None
  vCreatedBy = str(pCreatedBy or "unknown")
  vRunAt = fValidateRunAt(pRunAt)
  vAssignedBy = vCreatedBy if vOwner else None
  vRunMode = fReadRunMode(pRunAt)

  vConnection = db.fOpenKanbanDb()
  try:
    with vConnection:
      vCursor = vConnection.execute(
        "INSERT INTO cards (title, body, state, owner_agent, created_by, "
        "run_at, assigned_by, run_mode) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (vTitle, vBody, vState, vOwner, vCreatedBy, vRunAt, vAssignedBy,
         vRunMode),
      )
      vCardId = vCursor.lastrowid
      vConnection.execute(
        "INSERT INTO card_events (card_id, from_state, to_state, agent_id, note) "
        "VALUES (?, NULL, ?, ?, ?)",
        (vCardId, vState, vCreatedBy, fTruncate(pNote, cMaxNoteLength)),
      )
    return fGetCard(vCardId)
  finally:
    vConnection.close()


def fGetCard(pCardId):
  """Return one card, or None."""
  vConnection = db.fOpenKanbanDb()
  try:
    vRow = vConnection.execute(
      "SELECT * FROM cards WHERE id = ?", (int(pCardId),)
    ).fetchone()
  finally:
    vConnection.close()
  return dict(vRow) if vRow else None


def fMoveCard(pCardId, pState, pAgentId="", pNote=""):
  """Move a card to another column and return it.

  Moving a card to the column it is already in is not an error: an agent that
  re-confirms a state is being careful, not broken. The event is still
  recorded, so the board shows that someone looked.
  """
  vState = fValidateState(pState)
  vCardId = int(pCardId)
  vAgentId = str(pAgentId or "unknown")

  vConnection = db.fOpenKanbanDb()
  try:
    with vConnection:
      vRow = vConnection.execute(
        "SELECT state FROM cards WHERE id = ?", (vCardId,)
      ).fetchone()
      if vRow is None:
        raise KanbanError("There is no card with id %d" % (vCardId,))
      vPreviousState = vRow["state"]

      vConnection.execute(
        "UPDATE cards SET state = ?, updated_at = datetime('now') WHERE id = ?",
        (vState, vCardId),
      )
      vConnection.execute(
        "INSERT INTO card_events (card_id, from_state, to_state, agent_id, note) "
        "VALUES (?, ?, ?, ?, ?)",
        (vCardId, vPreviousState, vState, vAgentId,
         fTruncate(pNote, cMaxNoteLength)),
      )
  finally:
    vConnection.close()
  return fGetCard(vCardId)


def fListCards(pState=None, pOwnerAgent=None, pLimit=None):
  """Return cards, newest first, optionally filtered by column and owner."""
  lConditions = []
  lParameters = []
  if pState:
    lConditions.append("state = ?")
    lParameters.append(fValidateState(pState))
  if pOwnerAgent:
    lConditions.append("owner_agent = ?")
    lParameters.append(str(pOwnerAgent))

  vWhere = (" WHERE " + " AND ".join(lConditions)) if lConditions else ""
  vLimit = min(int(pLimit or cDefaultListLimit), cMaxListLimit)
  lParameters.append(vLimit)

  vConnection = db.fOpenKanbanDb()
  try:
    lRows = vConnection.execute(
      "SELECT * FROM cards%s ORDER BY updated_at DESC, id DESC LIMIT ?"
      % (vWhere,),
      lParameters,
    ).fetchall()
  finally:
    vConnection.close()
  return [dict(vRow) for vRow in lRows]


def fSetCardSchedule(pCardId, pRunAt, pAgentId="user", pNote=""):
  """Set or clear when a card should wake its owner, and return the card.

  Rescheduling clears `buzzed_at`, so a card that has already run once can be
  asked to run again. Without that, "run it again at six" would do nothing and
  say nothing.

  `run_mode` moves with `run_at`: it is what says whether this was "run it now"
  or "run it at six", and the agent is told which when it is woken.
  """
  vCardId = int(pCardId)
  vRunAt = fValidateRunAt(pRunAt)
  vRunMode = fReadRunMode(pRunAt)

  vConnection = db.fOpenKanbanDb()
  try:
    with vConnection:
      vRow = vConnection.execute(
        "SELECT * FROM cards WHERE id = ?", (vCardId,)
      ).fetchone()
      if vRow is None:
        raise KanbanError("There is no card with id %d" % (vCardId,))
      vConnection.execute(
        "UPDATE cards SET run_at = ?, run_mode = ?, buzzed_at = NULL, "
        "updated_at = datetime('now') WHERE id = ?",
        (vRunAt, vRunMode, vCardId),
      )
      vConnection.execute(
        "INSERT INTO card_events (card_id, from_state, to_state, agent_id, note) "
        "VALUES (?, ?, ?, ?, ?)",
        (vCardId, vRow["state"], vRow["state"], str(pAgentId or "user"),
         fTruncate(pNote or ("scheduled for %s" % (vRunAt,) if vRunAt
                             else "schedule cleared"), cMaxNoteLength)),
      )
  finally:
    vConnection.close()
  return fGetCard(vCardId)


def fAssignCard(pCardId, pOwnerAgent, pAgentId="user", pNote=""):
  """Hand a card to an agent, and return it.

  This is how the manager delegates: the card keeps its id, its body and its
  whole history, and only changes hands. Creating a second card for the same
  job would split that history in two.

  `assigned_by` records who handed it over, which is not the same as who
  created it: a card the user wrote and the orchestrator passed on arrives with
  the orchestrator's name on it, because that is who gave the agent the work.
  """
  vCardId = int(pCardId)
  vOwner = str(pOwnerAgent or "").strip() or None
  vAssignedBy = str(pAgentId or "user")

  vConnection = db.fOpenKanbanDb()
  try:
    with vConnection:
      vRow = vConnection.execute(
        "SELECT * FROM cards WHERE id = ?", (vCardId,)
      ).fetchone()
      if vRow is None:
        raise KanbanError("There is no card with id %d" % (vCardId,))
      vConnection.execute(
        "UPDATE cards SET owner_agent = ?, assigned_by = ?, "
        "updated_at = datetime('now') WHERE id = ?",
        (vOwner, vAssignedBy if vOwner else None, vCardId),
      )
      vConnection.execute(
        "INSERT INTO card_events (card_id, from_state, to_state, agent_id, note) "
        "VALUES (?, ?, ?, ?, ?)",
        (vCardId, vRow["state"], vRow["state"], str(pAgentId or "user"),
         fTruncate(pNote or ("assigned to %s" % (vOwner or "nobody",)),
                   cMaxNoteLength)),
      )
  finally:
    vConnection.close()
  return fGetCard(vCardId)


def fListDueCards(pNow=None):
  """Return the cards whose time has come, oldest first.

  A card is due when it has an owner, a time that has passed, has not been
  buzzed yet, and is not already done. Cards are returned in the order they
  were meant to run, so a backlog is worked through in the order it was asked
  for rather than by card id.
  """
  vNow = pNow or fNowText()
  vConnection = db.fOpenKanbanDb()
  try:
    lRows = vConnection.execute(
      "SELECT * FROM cards "
      "WHERE owner_agent IS NOT NULL AND owner_agent != '' "
      "AND run_at IS NOT NULL AND run_at <= ? "
      "AND buzzed_at IS NULL AND state != ? "
      "ORDER BY run_at, id",
      (vNow, cStateDone),
    ).fetchall()
  finally:
    vConnection.close()
  return [dict(vRow) for vRow in lRows]


def fWasRequestedImmediately(pCard):
  """Return True when this card's time was "now" rather than a chosen moment.

  A card from before `run_mode` existed reports False, and so shows the time it
  carries: that is the honest answer when nothing says it was asked for
  straight away.
  """
  if not pCard:
    return False
  return str(pCard.get("run_mode") or "") == cRunNow


def fMarkCardBuzzed(pCardId, pNote=""):
  """Record that a run was started for this card.

  Written the moment the run starts, not when it ends: a card that woke its
  agent must not wake it again on the next pass, whatever the run does.
  """
  vCardId = int(pCardId)
  vConnection = db.fOpenKanbanDb()
  try:
    with vConnection:
      vRow = vConnection.execute(
        "SELECT state FROM cards WHERE id = ?", (vCardId,)
      ).fetchone()
      if vRow is None:
        return False
      vConnection.execute(
        "UPDATE cards SET buzzed_at = datetime('now') WHERE id = ?", (vCardId,)
      )
      vConnection.execute(
        "INSERT INTO card_events (card_id, from_state, to_state, agent_id, note) "
        "VALUES (?, ?, ?, 'buzzer', ?)",
        (vCardId, vRow["state"], vRow["state"],
         fTruncate(pNote or "woke the agent for this card", cMaxNoteLength)),
      )
  finally:
    vConnection.close()
  return True


def fListCardEvents(pCardId, pLimit=None):
  """Return the history of one card, oldest first."""
  vConnection = db.fOpenKanbanDb()
  try:
    lRows = vConnection.execute(
      "SELECT * FROM card_events WHERE card_id = ? "
      "ORDER BY happened_at ASC, id ASC LIMIT ?",
      (int(pCardId), min(int(pLimit or cDefaultListLimit), cMaxListLimit)),
    ).fetchall()
  finally:
    vConnection.close()
  return [dict(vRow) for vRow in lRows]


def fGetBoard(pLimitPerState=None, pForAgentId=None):
  """Return the board, grouped by column.

  `pForAgentId` narrows it to that agent's own cards: the ones assigned to it
  and the ones it created. An agent must not learn that another agent's work
  exists - not the titles, not the count, not that there is anything there at
  all - so the filtering happens here, where the rows are, rather than in the
  tool that asks for them.

  The user's own view passes nothing and gets everything: the board is theirs.
  """
  dBoard = {}
  for vState in lStates:
    lCards = fListCards(vState, None, pLimitPerState)
    if pForAgentId:
      lCards = [dCard for dCard in lCards
                if fAgentOwnsCard(dCard, pForAgentId)]
    dBoard[vState] = lCards
  return dBoard


def fCountByState():
  """Return how many cards sit in each column."""
  dCounts = {vState: 0 for vState in lStates}
  vConnection = db.fOpenKanbanDb()
  try:
    lRows = vConnection.execute(
      "SELECT state, COUNT(*) AS total FROM cards GROUP BY state"
    ).fetchall()
  finally:
    vConnection.close()
  for vRow in lRows:
    dCounts[vRow["state"]] = vRow["total"]
  return dCounts


def fAgentOwnsCard(pCard, pAgentId):
  """Return True when a card belongs to one agent.

  A card is an agent's own when it created it or when it is assigned to it.
  Creation alone would not be enough: the orchestrator creates most cards and
  hands them to other agents, and the agent doing the work has to be able to
  move the card it was given.
  """
  if not pCard:
    return False
  vAgentId = str(pAgentId or "")
  if not vAgentId:
    return False
  return vAgentId in (
    str(pCard.get("owner_agent") or ""), str(pCard.get("created_by") or "")
  )


def fDeleteCard(pCardId, pDeletedBy="user"):
  """Delete one card and its history, recording that it existed.

  The card row and its events go, so the board stays clean, but a row is kept
  in `deleted_cards` saying what it was and who removed it. Without that, an
  agent deleting its own cards would be able to erase the evidence of what it
  had been doing, and the board would quietly stop being a record.
  """
  vCardId = int(pCardId)
  vConnection = db.fOpenKanbanDb()
  try:
    with vConnection:
      vRow = vConnection.execute(
        "SELECT * FROM cards WHERE id = ?", (vCardId,)
      ).fetchone()
      if vRow is None:
        return False
      vConnection.execute(
        "INSERT OR REPLACE INTO deleted_cards "
        "(id, title, state, owner_agent, created_by, deleted_by) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (vCardId, vRow["title"], vRow["state"], vRow["owner_agent"],
         vRow["created_by"], str(pDeletedBy or "user")),
      )
      vConnection.execute("DELETE FROM cards WHERE id = ?", (vCardId,))
    return True
  finally:
    vConnection.close()


def fListDeletedCards(pLimit=None):
  """Return recently deleted cards, newest first."""
  vConnection = db.fOpenKanbanDb()
  try:
    lRows = vConnection.execute(
      "SELECT * FROM deleted_cards ORDER BY deleted_at DESC, id DESC LIMIT ?",
      (min(int(pLimit or cDefaultListLimit), cMaxListLimit),),
    ).fetchall()
  finally:
    vConnection.close()
  return [dict(vRow) for vRow in lRows]


def fFormatBoardForAgent(pBoard):
  """Render the board as compact text for a model.

  Agents read this on every wake-up, so it is written to be cheap in tokens and
  unambiguous: one line per card, id first, owner explicit.
  """
  lLines = []
  for vState in lStates:
    lCards = pBoard.get(vState) or []
    lLines.append("## %s (%d)" % (vState, len(lCards)))
    if not lCards:
      lLines.append("(empty)")
    for dCard in lCards:
      lLines.append(
        "- #%d %s [owner: %s]"
        % (dCard["id"], dCard["title"], dCard.get("owner_agent") or "nobody")
      )
    lLines.append("")
  return "\n".join(lLines).strip()
