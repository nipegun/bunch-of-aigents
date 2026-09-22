"""Tool: kanban.move_card - move a card between columns.

Moving a card is how the board stays honest. An agent that does the work but
never moves the card leaves the user looking at a board that says nothing is
happening.

Moving a card to the column it is already in is allowed: re-confirming a state
is being careful, and the event is recorded either way, so the history shows
that someone checked.
"""

from backend.core import agent_api
from backend.core import agent_api_client
from backend.core import tool_registry

cToolName = "kanban.move_card"

cToolDescription = (
  "Move a card to another column: todo, doing or done. Move a card to doing "
  "when you start it and to done only when you have verified it is finished."
)

dToolSchema = {
  "type": "object",
  "properties": {
    "card_id": {
      "type": "integer",
      "description": "The id of the card, as shown on the board.",
    },
    "state": {
      "type": "string",
      "enum": ["todo", "doing", "done"],
      "description": "Column to move it to.",
    },
    "note": {
      "type": "string",
      "description": "Why it moved. Recorded in the card's history.",
    },
  },
  "required": ["card_id", "state"],
  "additionalProperties": False,
}


def fRunTool(pArguments, pContext):
  """Move one card through the agent API."""
  try:
    dResult = agent_api_client.fCallFromContext(
      pContext, agent_api.cVerbKanbanMoveCard, {
        "card_id": pArguments.get("card_id"),
        "state": pArguments.get("state"),
        "note": pArguments.get("note", ""),
      }
    )
  except agent_api_client.AgentApiClientError as vError:
    raise tool_registry.ToolFailure(
      "Could not move the card: %s" % (vError,)
    )

  dCard = dResult.get("card") or {}
  return "Card #%s is now in %s: %s" % (
    dCard.get("id"), dCard.get("state"), dCard.get("title")
  )
