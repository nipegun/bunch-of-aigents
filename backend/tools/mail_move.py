"""Tool: mail.move - move one message to another folder of the same account.

Only inside the account: there is no destination parameter for another mailbox
and no way to reach one. Filing mail is what this is for.
"""

from backend.core import agent_api
from backend.core import agent_api_client
from backend.core import tool_registry

cToolName = "mail.move"

cToolDescription = (
  "Move one message to another folder of the same mailbox, by its id as given "
  "by mail.read. Use it to file messages where a rule says they belong. The "
  "folder has to exist already; you cannot create one."
)

dToolSchema = {
  "type": "object",
  "properties": {
    "message_id": {
      "type": "string",
      "description": "The id of the message, copied exactly as mail.read printed it. It is not a position in the folder.",
    },
    "target_folder": {
      "type": "string",
      "description": "Folder to move it to. It must already exist.",
    },
    "folder": {
      "type": "string",
      "description": "Folder the message is in now. Defaults to INBOX.",
    },
  },
  "required": ["message_id", "target_folder"],
  "additionalProperties": False,
}


def fRunTool(pArguments, pContext):
  """Move one message through the agent API."""
  try:
    dResult = agent_api_client.fCallFromContext(
      pContext, agent_api.cVerbMailMove, {
        "message_id": pArguments.get("message_id"),
        "target_folder": pArguments.get("target_folder"),
        "folder": pArguments.get("folder") or "INBOX",
      }
    )
  except agent_api_client.AgentApiClientError as vError:
    raise tool_registry.ToolFailure("Could not move the message: %s" % (vError,))
  return "Message %s moved to %s." % (pArguments.get("message_id"),
                                      dResult.get("moved_to"))
