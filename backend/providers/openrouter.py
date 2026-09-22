"""OpenRouter provider adapter.

OpenRouter proxies many vendors' models behind one chat/completions endpoint,
so it is reached over plain HTTP rather than through the OpenAI SDK: its model
identifiers are namespaced (`anthropic/claude-opus-4.5`, `meta-llama/...`) and
it expects two identification headers the OpenAI client does not send.
"""

import os

import requests

from backend.providers import base

cApiKeyEnvironmentVariable = "OPENROUTER_API_KEY"

# OpenRouter asks callers to identify the application. It is not a credential:
# it is what makes this installation visible in the account's own usage view.
cRefererHeader = "https://github.com/nipegun/bunch-of-aigents"
cTitleHeader = "Bunch of AIgents"


class OpenRouterProvider(base.BaseProvider):
  """Talks to the OpenRouter chat/completions API."""

  cProviderName = "openrouter"
  # The cheapest model in this provider's catalogue, which is the rule: an
  # agent on a cron schedule that nobody is watching is the easiest way there
  # is to run up a bill, so the default is the one that costs least and the
  # bigger models are one click away in the LLM tab with their price shown.
  #
  # Verified against the real API on 2026-09-19 with `_/temp/probe-defaults.py`:
  # asked, called a tool, and answered that tool call. Re-run it after moving
  # a default; if one stops answering, move to the next cheapest and write the
  # provider's own error beside it, as kimi and together already do.
  cDefaultModel = "inclusionai/ling-3.0-flash"
  cDefaultBaseUrl = "https://openrouter.ai/api/v1"

  def __init__(self, pModel="", pBaseUrl="", pApiKey="", pTimeoutSeconds=None):
    base.BaseProvider.__init__(self, pModel, pBaseUrl, pApiKey, pTimeoutSeconds)
    self.vApiKey = self.vApiKey or os.environ.get(cApiKeyEnvironmentVariable, "")
    if not self.vApiKey:
      raise base.ProviderError(
        "No OpenRouter API key. Set it for this agent in the web interface."
      )

  def fSendMessages(self, pSystemPrompt, pMessages, pTools, pMaxTokens):
    """Send one chat/completions request."""
    dPayload = {
      "model": self.vModel,
      "messages": base.fNeutralMessagesToOpenAiFormat(pSystemPrompt, pMessages),
      "max_tokens": int(pMaxTokens),
    }
    if pTools:
      dPayload["tools"] = [base.fToolSchemaToOpenAiFormat(dTool) for dTool in pTools]
      dPayload["tool_choice"] = "auto"

    try:
      vResponse = requests.post(
        "%s/chat/completions" % (self.vBaseUrl,),
        headers={
          "Authorization": "Bearer %s" % (self.vApiKey,),
          "HTTP-Referer": cRefererHeader,
          "X-Title": cTitleHeader,
          "Content-Type": "application/json",
        },
        json=dPayload,
        timeout=self.vTimeoutSeconds,
      )
      vResponse.raise_for_status()
      dBody = vResponse.json()
    except requests.RequestException as vError:
      raise base.ProviderError(
        "OpenRouter request failed: %s" % (base.fDescribeHttpError(vError),))
    except ValueError as vError:
      raise base.ProviderError("OpenRouter returned invalid JSON: %s" % (vError,))

    # OpenRouter reports upstream failures inside a 200 response.
    if dBody.get("error"):
      raise base.ProviderError(
        "OpenRouter error: %s" % (dBody["error"].get("message", dBody["error"]),)
      )

    lChoices = dBody.get("choices") or []
    if not lChoices:
      raise base.ProviderError("OpenRouter returned no choices")
    return base.fParseOpenAiChoice(lChoices[0], dBody.get("usage"))
