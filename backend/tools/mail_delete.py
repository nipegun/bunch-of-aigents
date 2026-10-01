"""Tool: mail.delete - delete one message from the configured mailbox.

Deleting moves the message to the account's Trash folder when it has one, and
only expunges it outright when it has none. What an agent removes, a person can
still go and find: an agent acting on rules written last month should not be
able to make a message disappear with no way back.
"""

from backend.core import agent_api
from backend.core import agent_api_client
from backend.core import tool_registry

cToolName = "mail.delete"

cToolDescription = (
  "Delete one message from the mailbox by its id, as given by mail.read. It "
  "goes to the account's Trash folder where there is one. Only delete what a "
  "rule you were given says to delete; when in doubt, move it or leave it."
)

dToolSchema = {
  "type": "object",
  "properties": {
    "message_id": {
      "type": "string",
      "description": "The id of the message, copied exactly as mail.read printed it. It is not a position in the folder.",
    },
    "folder": {
      "type": "string",
      "description": "Folder the message is in. Defaults to INBOX.",
    },
  },
  "required": ["message_id"],
  "additionalProperties": False,
}


def fRunTool(pArguments, pContext):
  """Delete one message through the agent API."""
  try:
    dResult = agent_api_client.fCallFromContext(
      pContext, agent_api.cVerbMailDelete, {
        "message_id": pArguments.get("message_id"),
        "folder": pArguments.get("folder") or "INBOX",
      }
    )
  except agent_api_client.AgentApiClientError as vError:
    raise tool_registry.ToolFailure("Could not delete the message: %s" % (vError,))

  if dResult.get("moved_to"):
    return "Message %s moved to %s." % (pArguments.get("message_id"),
                                        dResult["moved_to"])
  return ("Message %s deleted. This account has no Trash folder, so it is gone "
          "for good." % (pArguments.get("message_id"),))
