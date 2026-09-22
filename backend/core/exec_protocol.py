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
cVerbReadChatAttachment = "read_chat_attachment"
cVerbSendChatMessage = "send_chat_message"
cVerbClearChat = "clear_chat"
cVerbReadMemory = "read_memory"
cVerbWriteMemory = "write_memory"
cVerbPing = "ping"
cVerbInstallWhisperModel = "install_whisper_model"

lKnownVerbs = [
  cVerbInstallWhisperModel,
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
  cVerbReadChatAttachment,
  cVerbSendChatMessage,
  cVerbClearChat,
  cVerbReadMemory,
  cVerbWriteMemory,
  cVerbPing,
]

# A request larger than this is refused unread. Crontabs and system prompts are
# small; anything bigger is either a bug or an attempt to exhaust memory.
cMaxRequestBytes = 256 * 1024

# What a RESPONSE may be, which is a different question and used to be the same
# number.
#
# A request is something somebody typed: a crontab, a prompt, a chat message.
# A response is something the application accumulated - and the application
# itself allows 500 chat lines and 2000 journal lines, with no cap on the
# length of any one of them. Measured: 71 ordinary messages came to 290,448
# bytes, and the client refused its own history with "the executor daemon sent
# an oversized response". The conversation could not be opened again, by the
# web interface or by Telegram, and nothing in the interface said why.
#
# So the two are separate, and the response side is sized for what the
# retention rules actually permit rather than for what a person types. The
# daemon also counts bytes before it serializes (see fTrimToByteBudget), so
# reaching this limit means a bug rather than a full conversation.
cMaxResponseBytes = 8 * 1024 * 1024

# What one verb may return before the daemon starts dropping the oldest
# entries. Below cMaxResponseBytes by a wide margin: the first is the point at
# which a reply is trimmed, the second is the point at which it is refused.
cMaxPayloadBytes = 4 * 1024 * 1024

# Seconds the client waits for the daemon to answer. Creating a user is fast,
# but apt-triggered disk pressure on a small server can make it slow.
cClientTimeoutSeconds = 60


def fTrimToByteBudget(plEntries, pBudgetBytes=None):
  """Return the newest entries that fit in a byte budget, oldest first.

  Counted in bytes before anything is serialized, because a line count is not
  a size: chat retention allows 500 lines and puts no ceiling on the length of
  any one of them, so "500 lines" is anywhere between a few kilobytes and
  whatever the agent felt like writing. Multibyte text makes the gap wider -
  one Japanese character is three bytes, and a character count would be wrong
  by a factor of three for a conversation that is entirely in Japanese.

  The newest are kept, because the end of a conversation is the part somebody
  is reading.

  Returns (entries, dropped).
  """
  vBudget = int(pBudgetBytes or cMaxPayloadBytes)
  lKept = []
  vTotal = 0
  for dEntry in reversed(list(plEntries or [])):
    vSize = len(json.dumps(dEntry, ensure_ascii=False).encode("utf-8")) + 1
    if lKept and vTotal + vSize > vBudget:
      break
    lKept.append(dEntry)
    vTotal += vSize
  lKept.reverse()
  return lKept, len(plEntries or []) - len(lKept)


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
