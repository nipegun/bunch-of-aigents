"""Tool: cron.add - run one of this agent's scripts on a schedule.

Only a script from the agent's own scripts directory. A free-form command in a
crontab is a thing nobody can review afterwards, and an agent that wants to run
one already has `bash.run`.

The line that wakes the agent up is never touched from here. An agent that
deleted it would go quiet for ever and would have no way of noticing.
"""

from backend.core import agent_scripts
from backend.core import tool_registry

cToolName = "cron.add"

cToolDescription = (
  "Run one of your own scripts on a schedule, by adding a line to your "
  "crontab. The script has to exist already - write it with script.write. "
  "This is how you do recurring work that does not need you to think: the "
  "script runs on its own, costs no tokens, and you read its results on your "
  "next run. Nothing more often than every 5 minutes."
)

dToolSchema = {
  "type": "object",
  "properties": {
    "script": {
      "type": "string",
      "description": "Which of your scripts to run, by file name.",
    },
    "schedule": {
      "type": "string",
      "description": "Five cron fields: minute hour day month weekday. "
                     "\"*/15 * * * *\" is every quarter of an hour, "
                     "\"0 7 * * *\" is every day at 07:00. @hourly and "
                     "@daily also work.",
    },
    "note": {
      "type": "string",
      "description": "One line saying why, written above it in the crontab "
                     "so the user can see what it is for.",
    },
  },
  "required": ["script", "schedule"],
  "additionalProperties": False,
}


def fRunTool(pArguments, pContext):
  """Add one cron line running one of this agent's scripts."""
  try:
    vLine = agent_scripts.fAddCronLine(
      pContext.vAgentId, pArguments.get("script"),
      pArguments.get("schedule"), pArguments.get("note", "")
    )
  except agent_scripts.ScriptError as vError:
    raise tool_registry.ToolFailure(str(vError))
  return "Added to your crontab: %s" % (vLine,)
