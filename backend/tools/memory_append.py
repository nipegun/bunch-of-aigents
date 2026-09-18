"""Tool: memory.append - write something down for your future self.

The agent runs as its own user and this file is in its own home, so the note is
written directly: no daemon, no socket, nothing to be refused by.

Everything in memory is loaded at the start of every run and paid for on every
model call, which is why the tool tells the agent how big its memory has got
rather than letting it grow quietly.
"""

from backend.core import memory
from backend.core import tool_registry

cToolName = "memory.append"

cToolDescription = (
  "Write one thing down in your memory, so you still know it on your next "
  "run. Use it for what you learned and would otherwise have to work out "
  "again: where something lives, what a command turned out to be, what the "
  "user prefers. Do not use it as a diary of what you did - that is what the "
  "kanban board is for."
)

dToolSchema = {
  "type": "object",
  "properties": {
    "note": {
      "type": "string",
      "description": "One fact worth keeping. One sentence is usually enough.",
    },
  },
  "required": ["note"],
  "additionalProperties": False,
}


def fRunTool(pArguments, pContext):
  """Append one note to this agent's memory."""
  try:
    vSize = memory.fAppend(pContext.vAgentId, pArguments.get("note"))
  except ValueError as vError:
    raise tool_registry.ToolFailure(str(vError))
  except RuntimeError as vError:
    raise tool_registry.ToolFailure("Could not write to memory: %s" % (vError,))

  if vSize > memory.cMemoryWarningCharacters:
    return (
      "Noted. Your memory is now %d characters, which is getting long: all of "
      "it is sent on every call. Consider using memory.replace to cut it down "
      "to what still matters." % (vSize,)
    )
  return "Noted. Your memory is now %d characters." % (vSize,)
