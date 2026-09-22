"""Tool: channel.write - send a message to a configured channel.

The agent never sees the channel's credentials. It names a channel and a
message; the agent API, running as `boa`, reads telegram.json or discord.json
and sends. That is the whole point of routing it through the API: a bot token
is not a message, it is permanent authority to send anything that bot can send.

The message arrives prefixed with the agent's real name, added by the API. An
agent cannot send a message that appears to come from another agent.
"""

from backend.core import agent_api
from backend.core import agent_api_client
from backend.core import tool_registry

cToolName = "channel.write"

cToolDescription = (
  "Send a message to one of the configured channels, such as telegram or "
  "discord. Use it to tell the user something they need to know now. Do not "
  "use it as a log: every message interrupts a person."
)

dToolSchema = {
  "type": "object",
  "properties": {
    "channel": {
      "type": "string",
      "enum": ["telegram", "discord", "mattermost", "x"],
      "description": "Which channel to send to.",
    },
    "message": {
      "type": "string",
      "description": "The message text. Plain text, no markup.",
    },
  },
  "required": ["channel", "message"],
  "additionalProperties": False,
}


def fRunTool(pArguments, pContext):
  """Send one message through the agent API."""
  try:
    dResult = agent_api_client.fCallFromContext(
      pContext, agent_api.cVerbChannelWrite, {
        "channel": pArguments.get("channel"),
        "message": pArguments.get("message"),
      }
    )
  except agent_api_client.AgentApiClientError as vError:
    raise tool_registry.ToolFailure(
      "Could not send the message: %s" % (vError,)
    )
  return "Message sent to %s." % (dResult.get("channel"),)
