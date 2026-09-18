"""Tool: memory.replace - rewrite your memory from scratch.

For when the memory needs tidying rather than adding to: facts that stopped
being true, notes that turned out not to matter, ten lines that are really one.

It replaces the whole file, which is deliberate. An agent that can only add
ends up with a memory that grows until it is mostly noise, and pays for that
noise on every call.
"""

from backend.core import memory
from backend.core import tool_registry

cToolName = "memory.replace"

cToolDescription = (
  "Replace your whole memory with new content. Use it to tidy up: remove what "
  "is no longer true, merge repeated notes, drop what turned out not to "
  "matter. Write the complete new memory, because what you send replaces "
  "everything you had."
)

dToolSchema = {
  "type": "object",
  "properties": {
    "content": {
      "type": "string",
      "description": "The complete new memory, in Markdown.",
    },
  },
  "required": ["content"],
  "additionalProperties": False,
}


def fRunTool(pArguments, pContext):
  """Replace this agent's memory."""
  vContent = str(pArguments.get("content") or "")
  if not vContent.strip():
    raise tool_registry.ToolFailure(
      "Refusing to erase your whole memory with an empty document. If that is "
      "really what you want, write a memory that says so."
    )
  try:
    memory.fWrite(pContext.vAgentId, vContent)
  except RuntimeError as vError:
    raise tool_registry.ToolFailure("Could not write to memory: %s" % (vError,))
  return "Memory replaced. It is now %d characters." % (len(vContent),)
