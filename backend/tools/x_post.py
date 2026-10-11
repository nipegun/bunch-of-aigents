"""Tool: x.post - ask to publish one text on the installation's X profile.

Nothing is published by calling it. The agent API stores the exact text and
sends it, with a one-time code, to the person BoA talks to on X; the post goes
out only when that person answers `!post <code>` within the hour (x_posts).

A tool of its own, rather than an argument of channel.write, so that granting
an agent private messages on X does not also grant it the public profile.
"""

from backend.core import agent_api
from backend.core import agent_api_client
from backend.core import tool_registry

cToolName = "x.post"

cToolDescription = (
  "Ask to publish one text on the X profile of this installation. Nothing is "
  "published yet: the user receives the exact text by private message with a "
  "one-time code, and it is published only if they answer with that code "
  "within 60 minutes. Use it only when the user expressly asks for a public "
  "post; never publish a private conversation."
)

dToolSchema = {
  "type": "object",
  "properties": {
    "message": {
      "type": "string",
      "description": "The exact text to publish. Plain text, no markup.",
    },
  },
  "required": ["message"],
  "additionalProperties": False,
}


def fRunTool(pArguments, pContext):
  """Ask for one post; the user approves or discards it by direct message."""
  try:
    dResult = agent_api_client.fCallFromContext(
      pContext, agent_api.cVerbXPostRequest, {"message": pArguments.get("message")}
    )
  except agent_api_client.AgentApiClientError as vError:
    raise tool_registry.ToolFailure(
      "Could not ask to publish on X: %s" % (vError,)
    )
  return (
    "Not published yet. The user received the text by private message and "
    "decides: it is published only if they approve it within %d minutes."
    % (dResult.get("expires_in_minutes") or 60,)
  )
