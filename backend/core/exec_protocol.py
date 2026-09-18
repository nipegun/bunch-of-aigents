"""Wire protocol between the web application and the privileged executor.

One request per connection, newline-terminated JSON in both directions:

    {"verb": "create_agent", "params": {...}}       ->
                                                    <- {"ok": true, "result": {...}}
                                                    <- {"ok": false, "error": "..."}

The verb list is closed on purpose. There is no "run this command as root"
verb, and there never should be: the whole point of this daemon is that the
web application can ask for a handful of specific privileged operations
without being able to ask for anything else.
"""

import json

# Closed vocabulary of privileged operations.
cVerbCreateAgent = "create_agent"
cVerbDeleteAgent = "delete_agent"
cVerbWriteCrontab = "write_crontab"
cVerbReadCrontab = "read_crontab"
cVerbRunNow = "run_now"
cVerbListRunningAgents = "list_running_agents"
cVerbReadAgentInfo = "read_agent_info"
cVerbWriteAgentInfo = "write_agent_info"
cVerbReadSystemPrompt = "read_system_prompt"
cVerbWriteSystemPrompt = "write_system_prompt"
cVerbReadRunJournal = "read_run_journal"
cVerbReadUsageSummary = "read_usage_summary"
cVerbReadChat = "read_chat"
cVerbSendChatMessage = "send_chat_message"
cVerbClearChat = "clear_chat"
cVerbReadMemory = "read_memory"
cVerbWriteMemory = "write_memory"
cVerbPing = "ping"

lKnownVerbs = [
  cVerbCreateAgent,
  cVerbDeleteAgent,
  cVerbWriteCrontab,
  cVerbReadCrontab,
  cVerbRunNow,
  cVerbListRunningAgents,
  cVerbReadAgentInfo,
  cVerbWriteAgentInfo,
  cVerbReadSystemPrompt,
  cVerbWriteSystemPrompt,
  cVerbReadRunJournal,
  cVerbReadUsageSummary,
  cVerbReadChat,
  cVerbSendChatMessage,
  cVerbClearChat,
  cVerbReadMemory,
  cVerbWriteMemory,
  cVerbPing,
]

# A request larger than this is refused unread. Crontabs and system prompts are
# small; anything bigger is either a bug or an attempt to exhaust memory.
cMaxRequestBytes = 256 * 1024

# Seconds the client waits for the daemon to answer. Creating a user is fast,
# but apt-triggered disk pressure on a small server can make it slow.
cClientTimeoutSeconds = 60


def fEncodeMessage(pPayload):
  """Serialize one message to newline-terminated UTF-8 bytes."""
  return (json.dumps(pPayload, ensure_ascii=False) + "\n").encode("utf-8")


def fDecodeMessage(pRawBytes):
  """Parse one message from bytes.

  Raises ValueError when the payload is not a JSON object, so that a malformed
  request is rejected before any field of it is looked at.
  """
  dPayload = json.loads(pRawBytes.decode("utf-8"))
  if not isinstance(dPayload, dict):
    raise ValueError("Message must be a JSON object")
  return dPayload


def fBuildRequest(pVerb, pParams=None):
  """Build a request payload for one verb."""
  if pVerb not in lKnownVerbs:
    raise ValueError("Unknown verb: %r" % (pVerb,))
  return {"verb": pVerb, "params": pParams or {}}


def fBuildSuccess(pResult=None):
  """Build a successful response payload."""
  return {"ok": True, "result": pResult or {}}


def fBuildFailure(pError):
  """Build a failed response payload."""
  return {"ok": False, "error": str(pError)}
