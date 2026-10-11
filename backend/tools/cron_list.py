"""Tool: cron.list - this agent's own crontab, as installed."""

from backend.core import agent_scripts
from backend.core import tool_registry

cToolName = "cron.list"

cToolDescription = (
  "Read your own crontab: what you run on a schedule and when. The first "
  "line is the one that wakes you up, which you cannot change from here - "
  "the user sets it on your Cron tab."
)

dToolSchema = {
  "type": "object",
  "properties": {},
  "additionalProperties": False,
}


def fRunTool(pArguments, pContext):
  """Return this agent's crontab."""
  try:
    vCrontab = agent_scripts.fReadCrontab(pContext.vAgentId)
  except agent_scripts.ScriptError as vError:
    raise tool_registry.ToolFailure(str(vError))
  return vCrontab.strip() or "Your crontab is empty."
