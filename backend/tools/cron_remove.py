"""Tool: cron.remove - stop running one of this agent's scripts."""

from backend.core import agent_scripts
from backend.core import tool_registry

cToolName = "cron.remove"

cToolDescription = (
  "Stop running one of your scripts on a schedule. The script itself stays "
  "where it is; only the crontab lines that ran it are removed. Your own "
  "wake-up line is never touched."
)

dToolSchema = {
  "type": "object",
  "properties": {
    "script": {
      "type": "string",
      "description": "Which of your scripts to stop running, by file name.",
    },
  },
  "required": ["script"],
  "additionalProperties": False,
}


def fRunTool(pArguments, pContext):
  """Remove every cron line that runs one script."""
  try:
    vRemoved = agent_scripts.fRemoveCronLines(
      pContext.vAgentId, pArguments.get("script"))
  except agent_scripts.ScriptError as vError:
    raise tool_registry.ToolFailure(str(vError))
  if not vRemoved:
    return "Nothing to remove: no cron line runs that script."
  return "Removed %d cron line(s)." % (vRemoved,)
