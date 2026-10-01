"""Tool: kanban.assign_card - hand one of your cards to another agent.

This is what delegating looks like from inside an agent. The orchestrator is
given a card, decides who should do the work, and passes the same card on: it
keeps its id, its instructions and its whole history, so the board shows one
job moving between hands rather than a trail of near-duplicate cards.

The ownership rule is unchanged. An agent can only give away a card that is
already its own, and the check runs in the agent API, not in this description.

Handing over a card wakes the agent it lands on. A delegation nobody acts on is
a change of label.
"""

from backend.core import agent_api
from backend.core import agent_api_client
from backend.core import tool_registry

cToolName = "kanban.assign_card"

cToolDescription = (
  "Give one of your own cards to another agent, by agent id. The card keeps "
  "its history and the agent is woken up for it. Use this to delegate work "
  "rather than creating a second card for the same job."
)

dToolSchema = {
  "type": "object",
  "properties": {
    "card_id": {
      "type": "integer",
      "description": "The id of the card, as shown on the board.",
    },
    "owner_agent": {
      "type": "string",
      "description": "Which agent is to do it, as a three-digit id: 001.",
    },
    "note": {
      "type": "string",
      "description": "Why them. Recorded in the card's history.",
    },
    "run_at": {
      "type": "string",
      "description": (
        "When they should start, as YYYY-MM-DD HH:MM in UTC. Leave it out to "
        "have them woken straight away."
      ),
    },
  },
  "required": ["card_id", "owner_agent"],
  "additionalProperties": False,
}


def fRunTool(pArguments, pContext):
  """Hand one card to another agent through the agent API."""
  try:
    dResult = agent_api_client.fCallFromContext(
      pContext, agent_api.cVerbKanbanAssignCard, {
        "card_id": pArguments.get("card_id"),
        "owner_agent": pArguments.get("owner_agent"),
        "note": pArguments.get("note", ""),
        "run_at": pArguments.get("run_at", ""),
      }
    )
  except agent_api_client.AgentApiClientError as vError:
    raise tool_registry.ToolFailure(
      "Could not assign the card: %s" % (vError,)
    )

  dCard = dResult.get("card") or {}
  return "Card #%s is now %s's: %s" % (
    dCard.get("id"), dCard.get("owner_agent"), dCard.get("title")
  )
