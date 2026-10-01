"""Client the tools use to reach the agent API.

Runs inside the agent's own process, as `agent-xxx`. It reads the agent's token
from its home directory and presents it on every request.

The tools in /opt/boa/tools/ use this rather than touching the kanban database
or the channel configuration, because as that user they could not touch either.
"""

import socket

from backend.core import exec_protocol
from backend.core import agent_api
from backend.core import paths

# Seconds to wait for the agent API. Sending to a channel involves an outbound
# HTTP request, so this is more generous than a local call would need.
cClientTimeoutSeconds = 60


class AgentApiClientError(RuntimeError):
  """Raised when the agent API refuses or fails a request."""


def fReadToken(pAgentId):
  """Read this agent's API token from its own home directory."""
  try:
    with paths.fOpenProtectedAgentFile(
        pAgentId, paths.cApiTokenFileName) as vFile:
      return vFile.read().strip()
  except OSError as vError:
    raise AgentApiClientError(
      "Cannot read this agent's API token: %s" % (vError,)
    )


def fSendRequest(pVerb, pToken, pParams=None):
  """Send one request to the agent API and return its result payload."""
  if pVerb not in agent_api.lAgentVerbs:
    raise AgentApiClientError("Unknown verb: %r" % (pVerb,))

  dRequest = {"verb": pVerb, "token": pToken, "params": pParams or {}}
  vSocket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
  try:
    vSocket.settimeout(cClientTimeoutSeconds)
    try:
      vSocket.connect(agent_api.cAgentSocketPath)
    except (FileNotFoundError, ConnectionRefusedError):
      raise AgentApiClientError(
        "The agent API is not running. Ask the user to check "
        "`systemctl status boa-agent-api`."
      )
    except PermissionError:
      raise AgentApiClientError("Not allowed to open the agent API socket.")

    vSocket.sendall(exec_protocol.fEncodeMessage(dRequest))

    vBuffer = b""
    while not vBuffer.endswith(b"\n"):
      vChunk = vSocket.recv(65536)
      if not vChunk:
        break
      vBuffer += vChunk
      if len(vBuffer) > exec_protocol.cMaxResponseBytes:
        raise AgentApiClientError("The agent API sent an oversized response")
  except socket.timeout:
    raise AgentApiClientError(
      "The agent API did not answer within %d seconds" % (cClientTimeoutSeconds,)
    )
  except OSError as vError:
    raise AgentApiClientError("Cannot talk to the agent API: %s" % (vError,))
  finally:
    vSocket.close()

  if not vBuffer.strip():
    raise AgentApiClientError("The agent API closed the connection without answering")

  try:
    dResponse = exec_protocol.fDecodeMessage(vBuffer)
  except (ValueError, UnicodeDecodeError) as vError:
    raise AgentApiClientError("Malformed response: %s" % (vError,))

  if not dResponse.get("ok"):
    raise AgentApiClientError(dResponse.get("error") or "Unknown agent API error")
  return dResponse.get("result") or {}


def fCallFromContext(pContext, pVerb, pParams=None):
  """Send one request using the token carried in a tool context.

  Tools receive a context built by the runner, which already read the token, so
  a tool never has to find the token itself.
  """
  vToken = getattr(pContext, "vApiToken", "") or fReadToken(pContext.vAgentId)
  return fSendRequest(pVerb, vToken, pParams)


def fGetApiKey(pAgentId, pProviderName, pToken=""):
  """Return the shared key of this agent's provider, via the agent API."""
  vToken = pToken or fReadToken(pAgentId)
  dResult = fSendRequest(agent_api.cVerbGetApiKey, vToken,
                         {"provider": pProviderName})
  return dResult.get("api_key", "")


def fCallForAgent(pAgentId, pVerb, pParams=None):
  """Send one request on behalf of an agent, finding its token itself.

  For the few places that are not a tool and so have no context to carry the
  token: agent_scripts reaches the crontab this way, because running `crontab`
  as the agent works on Debian and not on Alpine.
  """
  return fSendRequest(pVerb, fReadToken(pAgentId), pParams)
