"""Cohere provider adapter.

The one provider added here that does not serve chat/completions. Its v2 API
takes the same message list - role and content, tool results as `role: tool` -
but answers with a shape of its own: the reply's text arrives as a list of
content blocks, the finish reason is an uppercase word from a different
vocabulary, and the token counts are nested under `usage.tokens` rather than
sitting at the top level.

That is the whole reason this file exists instead of a two-line subclass of
the shared dialect: three differences in the response, each of which would
otherwise have to be a branch in code the other seventeen providers run.
"""

import os

import requests

from backend.providers import base

cApiKeyEnvironmentVariable = "COHERE_API_KEY"

# What Cohere puts in finish_reason, mapped onto the neutral vocabulary. Any
# word not listed here is treated as a normal end of turn, which is what an
# unknown reason most often means.
dFinishReasons = {
  "COMPLETE": base.cStopEndTurn,
  "STOP_SEQUENCE": base.cStopEndTurn,
  "MAX_TOKENS": base.cStopMaxTokens,
  "TOOL_CALL": base.cStopToolUse,
  "ERROR": base.cStopError,
}


class CohereProvider(base.BaseProvider):
  """Talks to the Cohere v2 chat API."""

  cProviderName = "cohere"
  cDisplayName = "Cohere"
  cDefaultModel = "command-a-reasoning-08-2025"
  cDefaultBaseUrl = "https://api.cohere.ai/v2"

  def __init__(self, pModel="", pBaseUrl="", pApiKey="", pTimeoutSeconds=None):
    base.BaseProvider.__init__(self, pModel, pBaseUrl, pApiKey, pTimeoutSeconds)
    self.vApiKey = self.vApiKey or os.environ.get(cApiKeyEnvironmentVariable, "")
    if not self.vApiKey:
      raise base.ProviderError(
        "No Cohere API key. Set it for this agent in the web interface."
      )

  def fSendMessages(self, pSystemPrompt, pMessages, pTools, pMaxTokens):
    """Send one v2/chat request."""
    dPayload = {
      "model": self.vModel,
      "messages": base.fNeutralMessagesToOpenAiFormat(pSystemPrompt, pMessages),
      "max_tokens": int(pMaxTokens),
      "stream": False,
    }
    if pTools:
      # The tool schema is the OpenAI one. `tool_choice` is not sent: this API
      # only accepts REQUIRED or NONE there, and neither is what an agent
      # needs - it has to be free to answer without calling anything.
      dPayload["tools"] = [base.fToolSchemaToOpenAiFormat(dTool) for dTool in pTools]

    try:
      vResponse = requests.post(
        "%s/chat" % (self.vBaseUrl,),
        headers={
          "Authorization": "Bearer %s" % (self.vApiKey,),
          "Content-Type": "application/json",
          "Accept": "application/json",
        },
        json=dPayload,
        timeout=self.vTimeoutSeconds,
      )
      if vResponse.status_code in (401, 403):
        raise base.ProviderError(
          "Cohere refused the key. Check it in Settings, API keys.")
      if vResponse.status_code == 429:
        raise base.ProviderError(
          "Cohere is rate-limiting this account. The run can be tried again "
          "later.")
      vResponse.raise_for_status()
      dBody = vResponse.json()
    except requests.ConnectionError:
      raise base.ProviderError("Cannot reach Cohere at %s." % (self.vBaseUrl,))
    except requests.Timeout:
      raise base.ProviderError(
        "Cohere did not answer within %d seconds." % (int(self.vTimeoutSeconds),))
    except requests.RequestException as vError:
      raise base.ProviderError(
        "Cohere request failed: %s" % (base.fDescribeHttpError(vError),))
    except ValueError as vError:
      raise base.ProviderError("Cohere returned invalid JSON: %s" % (vError,))

    return fParseCohereReply(dBody)


def fParseCohereReply(pBody):
  """Turn one v2/chat body into a ProviderResponse."""
  dMessage = (pBody or {}).get("message") or {}

  lTextParts = []
  for dBlock in dMessage.get("content") or []:
    if isinstance(dBlock, str):
      lTextParts.append(dBlock)
    elif isinstance(dBlock, dict) and dBlock.get("type") == "text":
      lTextParts.append(str(dBlock.get("text") or ""))

  lToolCalls = []
  for dCall in dMessage.get("tool_calls") or []:
    dFunction = dCall.get("function") or {}
    lToolCalls.append(base.ToolCall(
      dCall.get("id") or "",
      base.fToolNameFromWire(dFunction.get("name") or ""),
      dFunction.get("arguments") or "{}",
    ))

  vRawReason = str((pBody or {}).get("finish_reason") or "")
  vStopReason = dFinishReasons.get(vRawReason.upper(), base.cStopEndTurn)
  # A reply with tool calls is a tool turn whatever the provider called it:
  # the runner decides what to do next from this field alone.
  if lToolCalls:
    vStopReason = base.cStopToolUse

  dTokens = ((pBody or {}).get("usage") or {}).get("tokens") or {}
  return base.ProviderResponse(
    pText="".join(lTextParts),
    pToolCalls=lToolCalls,
    pStopReason=vStopReason,
    pPromptTokens=dTokens.get("input_tokens", 0),
    pCompletionTokens=dTokens.get("output_tokens", 0),
    pRawStopReason=vRawReason,
  )
