"""Tool: kanban.delete_card - remove one of your own cards from the board.

An agent may only delete a card it created or that is assigned to it. That
check happens in the agent API, not here: a rule enforced in a tool description
is advice to a model, and a rule enforced at the socket is a rule.

Deleting is for cards that should never have existed - a duplicate, a task that
turned out not to be needed. It is not how work gets finished: a task that is
done goes to the done column, where the user can see it was done.

The deletion itself is recorded, so a removed card still leaves a trace of
having existed and of who removed it.
"""

from backend.core import agent_api
from backend.core import agent_api_client
from backend.core import tool_registry

cToolName = "kanban.delete_card"

cToolDescription = (
  "Delete one of your own cards from the board. You may only delete cards you "
  "created or that are assigned to you. Use it for duplicates and for tasks "
  "that turned out to be unnecessary. Never use it for work you finished: "
  "move that to done instead, so the user can see it was done."
)

dToolSchema = {
  "type": "object",
  "properties": {
    "card_id": {
      "type": "integer",
      "description": "The id of the card to delete, as shown on the board.",
    },
    "reason": {
      "type": "string",
      "description": "Why it should not exist. Duplicate, obsolete, mistaken.",
    },
  },
  "required": ["card_id"],
  "additionalProperties": False,
}


def fRunTool(pArguments, pContext):
  """Delete one card through the agent API."""
  try:
    dResult = agent_api_client.fCallFromContext(
      pContext, agent_api.cVerbKanbanDeleteCard, {
        "card_id": pArguments.get("card_id"),
        "reason": pArguments.get("reason", ""),
      }
    )
  except agent_api_client.AgentApiClientError as vError:
    raise tool_registry.ToolFailure(
      "Could not delete the card: %s" % (vError,)
    )
  return "Card #%s deleted: %s" % (dResult.get("card_id"), dResult.get("title"))
