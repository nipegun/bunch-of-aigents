"""Tool: kanban.add_card - put a task on the shared board.

The card is written by the agent API, not by this process: the board belongs to
`boa` and an agent cannot open it. What crosses the socket is a request; what
comes back is the card as it was actually stored.

The creator recorded on the card is always the calling agent, whatever the
model puts in the arguments. An agent may hand work to another agent through
`owner_agent`, but it cannot sign a card with someone else's name.
"""

from backend.core import agent_api
from backend.core import agent_api_client
from backend.core import tool_registry

cToolName = "kanban.add_card"

cToolDescription = (
  "Add a card to the kanban board so the user can see what is being done. "
  "Use it when you start a piece of work, not after you finish it. Give it a "
  "title that says what 'done' means."
)

dToolSchema = {
  "type": "object",
  "properties": {
    "title": {
      "type": "string",
      "description": "Short statement of the task. Say what done looks like.",
    },
    "body": {
      "type": "string",
      "description": "Optional detail: context, links, what you tried.",
    },
    "state": {
      "type": "string",
      "enum": ["todo", "doing", "done"],
      "description": "Column to put it in. Defaults to todo.",
    },
    "owner_agent": {
      "type": "string",
      "description": "Agent id that should do this, e.g. 007. Defaults to you.",
    },
    "note": {
      "type": "string",
      "description": "Optional note recorded in the card's history.",
    },
  },
  "required": ["title"],
  "additionalProperties": False,
}


def fRunTool(pArguments, pContext):
  """Add one card through the agent API."""
  try:
    dResult = agent_api_client.fCallFromContext(
      pContext, agent_api.cVerbKanbanAddCard, {
        "title": pArguments.get("title"),
        "body": pArguments.get("body", ""),
        "state": pArguments.get("state") or "todo",
        "owner_agent": pArguments.get("owner_agent") or "",
        "note": pArguments.get("note", ""),
      }
    )
  except agent_api_client.AgentApiClientError as vError:
    raise tool_registry.ToolFailure(
      "Could not add the card: %s" % (vError,)
    )

  dCard = dResult.get("card") or {}
  return "Card #%s added to %s: %s" % (
    dCard.get("id"), dCard.get("state"), dCard.get("title")
  )
