"""Tool: script.write - write a script into this agent's own scripts directory.

The agent runs as its own user and the directory is in its own home, so the
file is written directly: no daemon, no socket. What this adds over doing the
same thing with `bash.run` is a path that can be checked - the name is
validated rather than cleaned, so nothing lands outside scripts/ - and a place
where both halves of a scheduled job can be read: the script here, the line
that runs it in the crontab.
"""

from backend.core import agent_scripts
from backend.core import tool_registry

cToolName = "script.write"

cToolDescription = (
  "Write a script into your own scripts directory, replacing it if it is "
  "already there. Use it for work that has to happen on a schedule and does "
  "not need you: a check, a backup, a clean-up. Start it with a shebang line "
  "such as #!/bin/bash - it is made executable for you. Schedule it "
  "afterwards with cron.add. It runs as you, with your own permissions, and "
  "nothing it does costs any tokens."
)

dToolSchema = {
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "description": "File name, e.g. check-disk.sh. Letters, digits, dots, "
                     "dashes and underscores only - not a path.",
    },
    "content": {
      "type": "string",
      "description": "The whole script. What you send replaces the file, so "
                     "send all of it, starting with its shebang line.",
    },
  },
  "required": ["name", "content"],
  "additionalProperties": False,
}


def fRunTool(pArguments, pContext):
  """Write one script into this agent's scripts directory."""
  try:
    vPath = agent_scripts.fWriteScript(
      pContext.vAgentId, pArguments.get("name"), pArguments.get("content"))
  except agent_scripts.ScriptError as vError:
    raise tool_registry.ToolFailure(str(vError))
  except OSError as vError:
    raise tool_registry.ToolFailure("Could not write the script: %s" % (vError,))
  return ("Written to %s, executable by you. Schedule it with cron.add, or "
          "run it now with bash.run." % (vPath,))
