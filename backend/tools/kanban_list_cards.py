"""Tool: kanban.list_cards - read this agent's own cards.

The first thing an agent should call when it wakes up: it is its memory of
what it has been given and what it has already done, across runs.

What comes back is its OWN cards - the ones assigned to it and the ones it
created - and never another agent's. An agent is not allowed to learn that
another agent's work exists: not the titles, not how many there are, not that
there is anything there. The filtering happens in the agent API, where the
rows are; this file only asks.

The one exception is the orchestrator, whose job is to hand work out and
follow it up, so it reads all of it.

The board comes back as compact text rather than JSON, because it is read on
every single wake-up and one line per card costs a fraction of the tokens.
"""

from backend.core import agent_api
from backend.core import agent_api_client
from backend.core import tool_registry
from backend.core import kanban

cToolName = "kanban.list_cards"

cToolDescription = (
  "Read your own cards on the kanban board: the ones assigned to you and the "
  "ones you created. Call this before doing anything else, so you know what "
  "you have already been given and what you have already done. You cannot "
  "see other agents' cards."
)

dToolSchema = {
  "type": "object",
  "properties": {
    "state": {
      "type": "string",
      "enum": ["todo", "doing", "done"],
      "description": "Only this column. Omit to get all of your cards.",
    },
    "owner_agent": {
      "type": "string",
      "description": "Narrow to one owner. It can only ever narrow further within your own cards.",
    },
    "limit": {
      "type": "integer",
      "description": "Maximum cards per column. Default 50.",
    },
  },
  "additionalProperties": False,
}


def fFormatCardList(pCards):
  """Render a flat list of cards as one line each."""
  if not pCards:
    return "(no cards)"
  lLines = []
  for dCard in pCards:
    lLines.append("- #%d [%s] %s [owner: %s]" % (
      dCard["id"], dCard["state"], dCard["title"],
      dCard.get("owner_agent") or "nobody"
    ))
  return "\n".join(lLines)


def fRunTool(pArguments, pContext):
  """Read the board through the agent API."""
  try:
    dResult = agent_api_client.fCallFromContext(
      pContext, agent_api.cVerbKanbanListCards, {
        "state": pArguments.get("state") or "",
        "owner_agent": pArguments.get("owner_agent") or "",
        "limit": pArguments.get("limit"),
      }
    )
  except agent_api_client.AgentApiClientError as vError:
    raise tool_registry.ToolFailure(
      "Could not read the board: %s" % (vError,)
    )

  if "board" in dResult:
    return kanban.fFormatBoardForAgent(dResult["board"])
  return fFormatCardList(dResult.get("cards") or [])
