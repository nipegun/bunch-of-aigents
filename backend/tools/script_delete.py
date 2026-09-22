"""Tool: script.delete - remove one of this agent's own scripts.

The cron lines that ran it go with it. A line pointing at a script that is no
longer there is a failure every few minutes, into a log nobody reads.
"""

from backend.core import agent_scripts
from backend.core import tool_registry

cToolName = "script.delete"

cToolDescription = (
  "Delete one of your own scripts. Any cron line that ran it is removed at "
  "the same time, so you cannot leave a schedule pointing at a file that is "
  "gone."
)

dToolSchema = {
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "description": "The script's file name, as given by script.list.",
    },
  },
  "required": ["name"],
  "additionalProperties": False,
}


def fRunTool(pArguments, pContext):
  """Delete one script and any cron line that ran it."""
  try:
    vRemovedLines = agent_scripts.fDeleteScript(
      pContext.vAgentId, pArguments.get("name"))
  except agent_scripts.ScriptError as vError:
    raise tool_registry.ToolFailure(str(vError))
  except OSError as vError:
    raise tool_registry.ToolFailure("Could not delete it: %s" % (vError,))

  if vRemovedLines:
    return "Deleted, along with %d cron line(s) that ran it." % (vRemovedLines,)
  return "Deleted. It was not in your crontab."
