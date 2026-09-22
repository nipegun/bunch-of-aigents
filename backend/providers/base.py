"""Common interface every provider adapter implements.

Each provider gets its own adapter file, even when two providers speak the same
dialect. That is deliberate: a shared "OpenAI-compatible" adapter looks tidy
right up to the day one of those providers changes a field name, and then the
fix has to be made without breaking the other four. One file per provider keeps
each provider's quirks where they belong.

What the adapters share is this file: the neutral message shape and the result
object. The neutral shape is modelled on the chat/completions convention
because most of the twenty-five providers already speak it; the Anthropic adapter
translates it into content blocks.

Neutral message shapes:

    {"role": "system",    "content": "..."}
    {"role": "user",      "content": "..."}
    {"role": "assistant", "content": "...", "tool_calls": [ToolCall, ...]}
    {"role": "tool",      "tool_call_id": "...", "name": "...", "content": "..."}
"""

import json
import re

# Neutral stop reasons. Every adapter maps its provider's vocabulary onto these.
cStopEndTurn = "end_turn"
cStopToolUse = "tool_use"
cStopMaxTokens = "max_tokens"
cStopRefusal = "refusal"
cStopError = "error"

# Seconds an adapter waits for a provider before giving up. Self-hosted models
# on modest hardware are slow, so this is generous.
cDefaultTimeoutSeconds = 300


class ToolCall:
  """One tool invocation requested by the model."""

  def __init__(self, pCallId, pName, pArguments, pProviderData=None):
    self.vCallId = pCallId
    self.vName = pName
    # Whatever the provider needs handed back when this same call is replayed
    # in the next request, and nothing else in the project reads. Gemini 3
    # refuses a conversation whose function calls come back without the
    # `thought_signature` it issued with them:
    #   Function call is missing a thought_signature in functionCall parts.
    # An empty dictionary for every other provider.
    self.dProviderData = pProviderData or {}
    # Arguments always reach the runner as a dict, whatever the provider sent.
    # Providers that return a JSON string get parsed here, once, so that no
    # tool implementation ever has to guess which shape it received.
    if isinstance(pArguments, dict):
      self.dArguments = pArguments
    else:
      try:
        self.dArguments = json.loads(pArguments or "{}")
      except (TypeError, ValueError):
        self.dArguments = {}

  def __repr__(self):
    return "ToolCall(%r, %r)" % (self.vName, self.dArguments)


class ProviderResponse:
  """One model reply, normalized across providers."""

  def __init__(self, pText="", pToolCalls=None, pStopReason=cStopEndTurn,
               pPromptTokens=0, pCompletionTokens=0, pRawStopReason=""):
    self.vText = pText or ""
    self.lToolCalls = pToolCalls or []
    self.vStopReason = pStopReason
    self.vPromptTokens = int(pPromptTokens or 0)
    self.vCompletionTokens = int(pCompletionTokens or 0)
    self.vRawStopReason = pRawStopReason

  @property
  def vTotalTokens(self):
    """Total tokens billed for this reply."""
    return self.vPromptTokens + self.vCompletionTokens

  def __repr__(self):
    return "ProviderResponse(stop=%r, tools=%d, tokens=%d)" % (
      self.vStopReason, len(self.lToolCalls), self.vTotalTokens
    )


class ProviderError(RuntimeError):
  """Raised when a provider cannot be reached or refuses a request."""


class BaseProvider:
  """Interface every adapter implements.

  An adapter is constructed from one agent's `provider` block in info.json and
  is used for the whole of one run.
  """

  # Overridden by each adapter.
  cProviderName = "base"
  cDefaultModel = ""
  cDefaultBaseUrl = ""

  # Extra keys an adapter accepts from the `provider` block of info.json,
  # beyond name/model/base_url. A key `reasoning_effort` here is passed to the
  # constructor as `pReasoningEffort`.
  lExtraConfigKeys = []

  def __init__(self, pModel="", pBaseUrl="", pApiKey="", pTimeoutSeconds=None):
    self.vModel = pModel or self.cDefaultModel
    self.vBaseUrl = (pBaseUrl or self.cDefaultBaseUrl).rstrip("/")
    self.vApiKey = pApiKey or ""
    self.vTimeoutSeconds = pTimeoutSeconds or cDefaultTimeoutSeconds

  def fSendMessages(self, pSystemPrompt, pMessages, pTools, pMaxTokens):
    """Send one request and return a ProviderResponse.

    pSystemPrompt : str, the agent's system-prompt.md
    pMessages     : list of neutral messages
    pTools        : list of neutral tool schemas
    pMaxTokens    : int, ceiling for this single reply
    """
    raise NotImplementedError("Each provider adapter implements fSendMessages")

  def fCountPromptTokens(self, pSystemPrompt, pMessages, pTools):
    """Return the prompt size in tokens, or None when the provider cannot say.

    Only Anthropic exposes an exact count. The runner treats None as "unknown"
    and falls back to the usage figures the provider reports after the call.
    """
    return None

  def fDescribe(self):
    """Return a short description used in logs and in the web interface."""
    return "%s/%s" % (self.cProviderName, self.vModel)


# A tool is called `family.action` everywhere in this project, but a provider
# validates the name of a function against `^[a-zA-Z0-9_-]+$`, which a dot does
# not match. DeepSeek answers
#   Invalid 'tools[0].function.name': string does not match pattern
# with a bare 400, so an agent with any tool at all never got to run. The dot
# is swapped for a double underscore on the way out and swapped back on the way
# in, in every adapter, so the name in the registry, in the interface, in the
# agent's info.json and in the logs keeps its dot and nothing else has to know.
cToolNameSeparator = "."
cToolNameWireSeparator = "__"


def fDescribeSdkError(pError):
  """Return something readable for an exception raised by a provider SDK.

  Some of them carry an empty message - an SDK connection error in particular -
  and "Anthropic request failed: " with nothing after the colon tells the user
  precisely nothing. The class name is not much, but it names the kind of
  failure, which is enough to know where to look next.
  """
  vDescription = str(pError).strip()
  if vDescription:
    return vDescription
  vCause = getattr(pError, "__cause__", None)
  if vCause is not None and str(vCause).strip():
    return "%s (%s)" % (type(pError).__name__, str(vCause).strip())
  return type(pError).__name__


# Anything that looks like a credential in a URL. Providers are not supposed
# to want one there - this project sends keys in headers - but an error string
# is built from whatever the request actually was, and a key that reaches a
# log file has to be treated as disclosed.
cCredentialInUrlPattern = re.compile(
  r"([?&](?:key|api_key|apikey|access_token|token)=)[^&\s'\"]+",
  re.IGNORECASE)


def fRedactCredentials(pText):
  """Return an error message with any credential in a URL replaced.

  Measured, not theoretical: Gemini used to be called with `?key=...`, and a
  503 from it put the whole key in the error the user reads and the journal
  keeps.
  """
  return cCredentialInUrlPattern.sub(r"\1REDACTED", str(pText))


def fDescribeHttpError(pError):
  """Return a request failure with whatever the provider said about it.

  `raise_for_status()` on its own produces "400 Client Error: Bad Request for
  url: ...", which names no cause. The body of that same response usually says
  exactly what was wrong with the request, so it is worth the few lines it
  takes to dig it out and put it in front of whoever is reading the error.
  """
  vDescription = str(pError)
  vResponse = getattr(pError, "response", None)
  if vResponse is None:
    return fRedactCredentials(vDescription)

  vDetail = ""
  try:
    dBody = vResponse.json()
    dError = dBody.get("error") if isinstance(dBody, dict) else None
    if isinstance(dError, dict):
      vDetail = str(dError.get("message") or dError)
    elif dError:
      vDetail = str(dError)
    elif isinstance(dBody, dict) and dBody.get("message"):
      vDetail = str(dBody["message"])
  except ValueError:
    vDetail = (vResponse.text or "").strip()

  if not vDetail:
    return fRedactCredentials(vDescription)
  return fRedactCredentials("%s - %s" % (vDescription, vDetail[:500]))


def fToolNameToWire(pName):
  """Return a tool name in the form a provider accepts."""
  return str(pName).replace(cToolNameSeparator, cToolNameWireSeparator)


def fToolNameFromWire(pName):
  """Return this project's own name for a tool the model asked for."""
  return str(pName).replace(cToolNameWireSeparator, cToolNameSeparator)


def fToolSchemaToOpenAiFormat(pTool):
  """Convert a neutral tool schema to the chat/completions function shape."""
  return {
    "type": "function",
    "function": {
      "name": fToolNameToWire(pTool["name"]),
      "description": pTool.get("description", ""),
      "parameters": pTool.get("input_schema") or {"type": "object", "properties": {}},
    },
  }


def fNeutralMessagesToOpenAiFormat(pSystemPrompt, pMessages):
  """Convert neutral messages to the chat/completions message list."""
  lConverted = []
  if pSystemPrompt:
    lConverted.append({"role": "system", "content": pSystemPrompt})

  for dMessage in pMessages:
    vRole = dMessage.get("role")

    if vRole == "tool":
      lConverted.append({
        "role": "tool",
        "tool_call_id": dMessage.get("tool_call_id", ""),
        "content": str(dMessage.get("content", "")),
      })
      continue

    if vRole == "assistant" and dMessage.get("tool_calls"):
      lConverted.append({
        "role": "assistant",
        "content": dMessage.get("content") or None,
        "tool_calls": [
          {
            "id": vCall.vCallId,
            "type": "function",
            "function": {
              "name": fToolNameToWire(vCall.vName),
              "arguments": json.dumps(vCall.dArguments, ensure_ascii=False),
            },
          }
          for vCall in dMessage["tool_calls"]
        ],
      })
      continue

    lConverted.append({
      "role": vRole,
      "content": str(dMessage.get("content", "")),
    })

  return lConverted


def fParseOpenAiChoice(pChoice, pUsage):
  """Turn one chat/completions choice into a ProviderResponse."""
  dMessage = pChoice.get("message") or {}
  vFinishReason = pChoice.get("finish_reason") or ""

  lToolCalls = []
  for dCall in dMessage.get("tool_calls") or []:
    dFunction = dCall.get("function") or {}
    lToolCalls.append(ToolCall(
      dCall.get("id") or "",
      fToolNameFromWire(dFunction.get("name") or ""),
      dFunction.get("arguments") or "{}",
    ))

  if lToolCalls:
    vStopReason = cStopToolUse
  elif vFinishReason == "length":
    vStopReason = cStopMaxTokens
  elif vFinishReason == "content_filter":
    vStopReason = cStopRefusal
  else:
    vStopReason = cStopEndTurn

  dUsage = pUsage or {}
  return ProviderResponse(
    pText=dMessage.get("content") or "",
    pToolCalls=lToolCalls,
    pStopReason=vStopReason,
    pPromptTokens=dUsage.get("prompt_tokens", 0),
    pCompletionTokens=dUsage.get("completion_tokens", 0),
    pRawStopReason=vFinishReason,
  )
