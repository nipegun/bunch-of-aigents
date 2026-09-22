"""Ollama provider adapter.

Ollama is the self-hosted default of this installation: it needs no API key and
runs on the same machine or on another box on the LAN.

It has its own native endpoint, `/api/chat`, which is what this adapter uses
rather than Ollama's OpenAI compatibility layer. The native endpoint is the one
that reports load and evaluation counts, which is the only way an agent running
on a self-hosted model can account for its own token use.
"""

import requests

from backend.providers import base

# Self-hosted models on modest hardware are slow, and the first request also
# pays for loading the model into memory.
cSelfHostedTimeoutSeconds = 600


class OllamaProvider(base.BaseProvider):
  """Talks to a local or LAN Ollama server."""

  cProviderName = "ollama"
  # A model that is actually pulled is the only one that answers, so this is
  # a suggestion more than a default. The smallest of the two open-weight
  # models most installations pull first.
  cDefaultModel = "gpt-oss:20b"
  cDefaultBaseUrl = "http://127.0.0.1:11434"

  def __init__(self, pModel="", pBaseUrl="", pApiKey="", pTimeoutSeconds=None):
    base.BaseProvider.__init__(
      self, pModel, pBaseUrl, pApiKey, pTimeoutSeconds or cSelfHostedTimeoutSeconds
    )

  def fSendMessages(self, pSystemPrompt, pMessages, pTools, pMaxTokens):
    """Send one /api/chat request."""
    dPayload = {
      "model": self.vModel,
      "messages": base.fNeutralMessagesToOpenAiFormat(pSystemPrompt, pMessages),
      "stream": False,
      "options": {"num_predict": int(pMaxTokens)},
    }
    if pTools:
      dPayload["tools"] = [base.fToolSchemaToOpenAiFormat(dTool) for dTool in pTools]

    try:
      vResponse = requests.post(
        "%s/api/chat" % (self.vBaseUrl,),
        json=dPayload,
        timeout=self.vTimeoutSeconds,
      )
      vResponse.raise_for_status()
      dBody = vResponse.json()
    except requests.ConnectionError:
      raise base.ProviderError(
        "Cannot reach Ollama at %s. Is it running?" % (self.vBaseUrl,)
      )
    except requests.RequestException as vError:
      raise base.ProviderError(
        "Ollama request failed: %s" % (base.fDescribeHttpError(vError),))
    except ValueError as vError:
      raise base.ProviderError("Ollama returned invalid JSON: %s" % (vError,))

    return self.fParseResponse(dBody)

  def fParseResponse(self, pBody):
    """Turn one /api/chat response into a ProviderResponse."""
    dMessage = pBody.get("message") or {}

    lToolCalls = []
    vCallIndex = 0
    for dCall in dMessage.get("tool_calls") or []:
      dFunction = dCall.get("function") or {}
      # Ollama does not assign call ids, so the index becomes the id the runner
      # matches results against.
      vCallIndex += 1
      # Back through fToolNameFromWire, exactly as the shared OpenAI parser
      # does. The request sent `kanban__list_cards`, because a dot is not a
      # name a provider accepts; what comes back carries that same spelling,
      # and the registry only knows `kanban.list_cards`. Without this line
      # every tool call made through Ollama was refused as a tool the agent
      # had not been granted - the name it was refused for being the one this
      # code had just offered it.
      lToolCalls.append(base.ToolCall(
        dCall.get("id") or "ollama-call-%d" % (vCallIndex,),
        base.fToolNameFromWire(dFunction.get("name") or ""),
        dFunction.get("arguments") or {},
      ))

    vRawDoneReason = pBody.get("done_reason") or ""
    if lToolCalls:
      vStopReason = base.cStopToolUse
    elif vRawDoneReason == "length":
      vStopReason = base.cStopMaxTokens
    else:
      vStopReason = base.cStopEndTurn

    return base.ProviderResponse(
      pText=dMessage.get("content") or "",
      pToolCalls=lToolCalls,
      pStopReason=vStopReason,
      pPromptTokens=pBody.get("prompt_eval_count", 0),
      pCompletionTokens=pBody.get("eval_count", 0),
      pRawStopReason=vRawDoneReason,
    )
