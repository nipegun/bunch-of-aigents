"""llama.cpp provider adapter.

Talks to a `llama-server` instance, which serves an OpenAI-compatible
chat/completions endpoint on port 8080 by default.

Two things separate it from the other self-hosted adapters. It usually serves
exactly one model, so the `model` field is a label rather than a selector and
an empty one is accepted. And tool support depends on the chat template the
server was started with: when the template cannot express tools, llama-server
answers with the function call written into the text instead of in a
`tool_calls` field, which this adapter reports as a clear error rather than
letting the agent silently do nothing.
"""

import requests

from backend.providers import base

cSelfHostedTimeoutSeconds = 600


class LlamaCppProvider(base.BaseProvider):
  """Talks to a llama.cpp llama-server instance."""

  cProviderName = "llamacpp"
  cDefaultModel = "local-model"
  cDefaultBaseUrl = "http://127.0.0.1:8080"

  def __init__(self, pModel="", pBaseUrl="", pApiKey="", pTimeoutSeconds=None):
    base.BaseProvider.__init__(
      self, pModel, pBaseUrl, pApiKey, pTimeoutSeconds or cSelfHostedTimeoutSeconds
    )

  def fSendMessages(self, pSystemPrompt, pMessages, pTools, pMaxTokens):
    """Send one chat/completions request to llama-server."""
    dPayload = {
      "model": self.vModel or self.cDefaultModel,
      "messages": base.fNeutralMessagesToOpenAiFormat(pSystemPrompt, pMessages),
      "max_tokens": int(pMaxTokens),
      "stream": False,
    }
    if pTools:
      dPayload["tools"] = [base.fToolSchemaToOpenAiFormat(dTool) for dTool in pTools]
      dPayload["tool_choice"] = "auto"

    dHeaders = {"Content-Type": "application/json"}
    if self.vApiKey:
      dHeaders["Authorization"] = "Bearer %s" % (self.vApiKey,)

    try:
      vResponse = requests.post(
        "%s/v1/chat/completions" % (self.vBaseUrl,),
        headers=dHeaders,
        json=dPayload,
        timeout=self.vTimeoutSeconds,
      )
      vResponse.raise_for_status()
      dBody = vResponse.json()
    except requests.ConnectionError:
      raise base.ProviderError(
        "Cannot reach llama.cpp at %s. Is llama-server running?" % (self.vBaseUrl,)
      )
    except requests.RequestException as vError:
      raise base.ProviderError(
        "llama.cpp request failed: %s" % (base.fDescribeHttpError(vError),))
    except ValueError as vError:
      raise base.ProviderError("llama.cpp returned invalid JSON: %s" % (vError,))

    lChoices = dBody.get("choices") or []
    if not lChoices:
      raise base.ProviderError("llama.cpp returned no choices")

    vParsed = base.fParseOpenAiChoice(lChoices[0], dBody.get("usage"))

    # A server started without a tool-capable chat template answers a tool
    # request with prose. Saying so is far more useful than an agent that
    # appears to work and never calls anything.
    if pTools and not vParsed.lToolCalls and "\"name\"" in vParsed.vText \
       and "arguments" in vParsed.vText:
      raise base.ProviderError(
        "llama.cpp answered with a tool call written as text. Start "
        "llama-server with a chat template that supports tools "
        "(--chat-template or --jinja)."
      )

    return vParsed
