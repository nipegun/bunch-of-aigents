"""Client for the privileged executor daemon.

Used by the web application, which runs unprivileged and therefore cannot
create users, install crontabs or start an agent run by itself. Every function
here is a thin wrapper over one verb, so that the rest of the web code never
builds a protocol message by hand.

A failed verb raises ExecError. Callers are expected to turn that into an HTTP
error, never to ignore it: a silent failure here means the user pressed "+",
saw nothing happen and has no idea why.
"""

import base64
import binascii
import socket

from backend.core import attachments
from backend.core import exec_protocol
from backend.core import paths


class ExecError(RuntimeError):
  """Raised when the executor daemon refuses or fails a request."""


class AttachmentUnavailable(ExecError):
  """An attachment was removed, is invalid, or is not part of this chat."""


def fSendRequest(pVerb, pParams=None):
  """Send one request to the daemon and return its result payload."""
  dRequest = exec_protocol.fBuildRequest(pVerb, pParams)
  vSocket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
  try:
    vSocket.settimeout(exec_protocol.cClientTimeoutSeconds)
    try:
      vSocket.connect(paths.cExecSocketPath)
    except (FileNotFoundError, ConnectionRefusedError):
      raise ExecError(
        "The executor daemon is not running. Check `systemctl status boa-exec`."
      )
    except PermissionError:
      raise ExecError(
        "Not allowed to talk to the executor daemon. The web application must "
        "run as the %s user." % (paths.cAppUser,)
      )

    vSocket.sendall(exec_protocol.fEncodeMessage(dRequest))

    vBuffer = b""
    while not vBuffer.endswith(b"\n"):
      vChunk = vSocket.recv(65536)
      if not vChunk:
        break
      vBuffer += vChunk
      # The RESPONSE limit, not the request one. They were the same number,
      # and a response is something the application accumulated rather than
      # something somebody typed: an ordinary chat history went past the
      # request limit and the client refused to read its own conversation.
      if len(vBuffer) > exec_protocol.cMaxResponseBytes:
        raise ExecError("The executor daemon sent an oversized response")
  except socket.timeout:
    raise ExecError(
      "The executor daemon did not answer within %d seconds"
      % (exec_protocol.cClientTimeoutSeconds,)
    )
  except OSError as vError:
    raise ExecError("Cannot talk to the executor daemon: %s" % (vError,))
  finally:
    vSocket.close()

  if not vBuffer.strip():
    raise ExecError("The executor daemon closed the connection without answering")

  try:
    dResponse = exec_protocol.fDecodeMessage(vBuffer)
  except (ValueError, UnicodeDecodeError) as vError:
    raise ExecError("Malformed response from the executor daemon: %s" % (vError,))

  if not dResponse.get("ok"):
    raise ExecError(dResponse.get("error") or "Unknown executor error")
  return dResponse.get("result") or {}


def fPing():
  """Check that the daemon is alive."""
  return fSendRequest(exec_protocol.cVerbPing)


def fCreateAgent(pName, pDescription="", pProvider="ollama", pModel="",
                 pBaseUrl="", pSystemPrompt="", pAgentId=None,
                 pTools=None, pLimits=None, pCrontab="", pEnabled=None,
                 pSkills=None):
  """Create a new agent, letting the daemon pick the next free id.

  The last five carry what an example agent brings with it: the tools it
  needs, what it may spend, when it wakes up, whether it starts switched on,
  and which shared procedures it is given. Each is left out of the message
  when it is None, so an ordinary blank agent is created exactly as before.
  """
  dParams = {
    "name": pName,
    "description": pDescription,
    "provider": pProvider,
    "model": pModel,
    "base_url": pBaseUrl,
    "system_prompt": pSystemPrompt,
    "agent_id": pAgentId,
    "crontab": pCrontab,
  }
  if pTools is not None:
    dParams["tools"] = list(pTools)
  if pSkills is not None:
    dParams["skills"] = list(pSkills)
  if pLimits is not None:
    dParams["limits"] = dict(pLimits)
  if pEnabled is not None:
    dParams["enabled"] = bool(pEnabled)
  return fSendRequest(exec_protocol.cVerbCreateAgent, dParams)


def fDeleteAgent(pAgentId):
  """Delete one agent and everything belonging to it."""
  return fSendRequest(exec_protocol.cVerbDeleteAgent, {"agent_id": pAgentId})


def fReadAgentInfo(pAgentId):
  """Return one agent's info.json."""
  return fSendRequest(exec_protocol.cVerbReadAgentInfo, {"agent_id": pAgentId})


def fWriteAgentInfo(pAgentId, pInfo):
  """Update one agent's info.json."""
  return fSendRequest(exec_protocol.cVerbWriteAgentInfo, {
    "agent_id": pAgentId,
    "info": pInfo,
  })


def fReadSystemPrompt(pAgentId):
  """Return one agent's system-prompt.md."""
  return fSendRequest(exec_protocol.cVerbReadSystemPrompt, {"agent_id": pAgentId})


def fWriteSystemPrompt(pAgentId, pSystemPrompt):
  """Replace one agent's system-prompt.md."""
  return fSendRequest(exec_protocol.cVerbWriteSystemPrompt, {
    "agent_id": pAgentId,
    "system_prompt": pSystemPrompt,
  })


def fReadCrontab(pAgentId):
  """Return one agent's crontab."""
  return fSendRequest(exec_protocol.cVerbReadCrontab, {"agent_id": pAgentId})


def fWriteCrontab(pAgentId, pCrontab):
  """Install one agent's crontab. An empty string removes it."""
  return fSendRequest(exec_protocol.cVerbWriteCrontab, {
    "agent_id": pAgentId,
    "crontab": pCrontab,
  })


def fRunNow(pAgentId, pPrompt="", pOnlyIfIdle=False, pCard=None):
  """Start one agent run immediately.

  With `pOnlyIfIdle` the daemon refuses to start a second run of an agent that
  is already working, and answers `started: False` instead.

  `pCard` is the card this run is for, when there is one. The daemon announces
  it in the agent's chat and ties the answer to it, and it does so only if the
  run actually starts: a card that found its agent busy has not been handed over
  yet, and saying it had would be a conversation about work nobody began.
  """
  dParams = {
    "agent_id": pAgentId,
    "prompt": pPrompt,
    "only_if_idle": bool(pOnlyIfIdle),
  }
  if pCard:
    dParams["card"] = dict(pCard)
  return fSendRequest(exec_protocol.cVerbRunNow, dParams)


def fListRunningAgents():
  """Return the ids of the agents that are working right now.

  One call answers for every agent, so the sidebar can ask for it on a timer
  without the cost growing with the number of agents.
  """
  return fSendRequest(exec_protocol.cVerbListRunningAgents)


def fReadRunJournal(pAgentId, pLimit=None):
  """Return one agent's run journal."""
  return fSendRequest(exec_protocol.cVerbReadRunJournal, {
    "agent_id": pAgentId,
    "limit": pLimit,
  })


def fReadUsageSummary(pAgentId=None):
  """Return run and token totals for one agent, or for every agent."""
  return fSendRequest(exec_protocol.cVerbReadUsageSummary, {"agent_id": pAgentId})


def fReadChat(pAgentId, pLimit=None):
  """Return one agent's chat history."""
  return fSendRequest(exec_protocol.cVerbReadChat, {
    "agent_id": pAgentId,
    "limit": pLimit,
  })


def fReadChatAttachment(pAgentId, pAttachmentId, pOffset=0):
  """Read one image chunk without increasing the ordinary RPC size limit."""
  dResult = fSendRequest(exec_protocol.cVerbReadChatAttachment, {
    "agent_id": pAgentId, "attachment_id": pAttachmentId, "offset": pOffset,
  })
  if not dResult.get("available"):
    raise AttachmentUnavailable("The image attachment is unavailable.")
  try:
    vSize = int(dResult["size"])
    vData = base64.b64decode(dResult["data"], validate=True)
    if (not 33 <= vSize <= attachments.cMaxImageBytes
        or dResult.get("offset") != pOffset
        or len(vData) != min(attachments.cChunkBytes, vSize - pOffset)
        or not vData):
      raise ValueError("Invalid attachment chunk")
  except (KeyError, TypeError, ValueError, binascii.Error) as vError:
    raise ExecError("Malformed image attachment: %s" % (vError,))
  dResult["size"] = vSize
  dResult["content"] = vData
  return dResult


def fIterChatAttachment(pAgentId, pAttachmentId, pFirstChunk=None):
  """Stream an attachment with a fixed total length and bounded RPC replies."""
  dChunk = pFirstChunk or fReadChatAttachment(pAgentId, pAttachmentId)
  vSize = dChunk["size"]
  vOffset = 0
  while True:
    if dChunk["size"] != vSize or dChunk["offset"] != vOffset:
      raise ExecError("The image attachment changed while being read.")
    yield dChunk["content"]
    vOffset += len(dChunk["content"])
    if vOffset == vSize:
      return
    dChunk = fReadChatAttachment(pAgentId, pAttachmentId, vOffset)


def fSendChatMessage(pAgentId, pMessage, pSource="", pTurnId="", pAudioId=""):
  """Record a chat message and start the run that answers it.

  pSource says where the message came in through, when it was not the web
  interface - "telegram" today. It travels with the turn so the conversation
  shows the whole exchange, whichever door each half came through.
  """
  return fSendRequest(exec_protocol.cVerbSendChatMessage, {
    "agent_id": pAgentId,
    "message": pMessage,
    "source": pSource,
    "turn_id": pTurnId,
    "audio_id": pAudioId,
  })


def fInstallWhisperModel(pModel):
  return fSendRequest(exec_protocol.cVerbInstallWhisperModel, {"model": pModel})


def fClearChat(pAgentId):
  """Delete one agent's chat history."""
  return fSendRequest(exec_protocol.cVerbClearChat, {"agent_id": pAgentId})


def fReadMemory(pAgentId):
  """Return one agent's memory."""
  return fSendRequest(exec_protocol.cVerbReadMemory, {"agent_id": pAgentId})


def fWriteMemory(pAgentId, pMemory):
  """Replace one agent's memory."""
  return fSendRequest(exec_protocol.cVerbWriteMemory, {
    "agent_id": pAgentId,
    "memory": pMemory,
  })
