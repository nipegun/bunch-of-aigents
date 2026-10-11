"""Tool: script.list - what this agent has written for itself."""

from backend.core import agent_scripts
from backend.core import tool_registry

cToolName = "script.list"

cToolDescription = (
  "List the scripts you have written, with their sizes. Call this before "
  "writing one, so you extend what is there rather than writing a second "
  "script that does nearly the same thing."
)

dToolSchema = {
  "type": "object",
  "properties": {},
  "additionalProperties": False,
}


def fRunTool(pArguments, pContext):
  """List this agent's own scripts."""
  lScripts = agent_scripts.fListScripts(pContext.vAgentId)
  if not lScripts:
    return "You have no scripts yet."
  return "\n".join(
    "%s (%d bytes)" % (dScript["name"], dScript["bytes"])
    for dScript in lScripts
  )
