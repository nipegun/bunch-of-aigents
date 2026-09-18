"""DeepSeek provider adapter.

DeepSeek serves a chat/completions endpoint, but enough of its behaviour is its
own to keep it in a separate file.

Thinking is a request parameter here rather than a property of the model: both
models can run with or without it, switched by `thinking: {"type": "enabled"}`
and tuned with `reasoning_effort`. It is off by default in this adapter,
because an agent on a cron schedule pays for that reasoning on every wake-up.

Pricing also changes by time of day - off-peak rates are several times cheaper
than peak - which is worth knowing when scheduling an agent's crontab.
"""

import os

import requests

from backend.providers import base

cApiKeyEnvironmentVariable = "DEEPSEEK_API_KEY"

# Models currently served. Both support tool calls and JSON output, and both
# have a 1M token context window with up to 384K tokens of output.
cModelFlash = "deepseek-flash"
cModelV4Pro = "deepseek-v4-pro"

lKnownModels = [cModelFlash, cModelV4Pro]

# Model ids that DeepSeek used to serve. They are still the first thing most
# people type, so they get a real message instead of an opaque upstream error.
dRetiredModels = {
  "deepseek-chat": cModelFlash,
  "deepseek-reasoner": cModelV4Pro,
  "deepseek-v3": cModelFlash,
  "deepseek-r1": cModelV4Pro,
}

# Accepted values for the reasoning_effort parameter, used only when thinking
# is switched on for an agent.
lReasoningEfforts = ["low", "medium", "high"]


class DeepSeekProvider(base.BaseProvider):
  """Talks to the DeepSeek chat/completions API."""

  cProviderName = "deepseek"
  cDefaultModel = cModelFlash
  cDefaultBaseUrl = "https://api.deepseek.com"
  lExtraConfigKeys = ["thinking", "reasoning_effort"]

  def __init__(self, pModel="", pBaseUrl="", pApiKey="", pTimeoutSeconds=None,
               pThinking=False, pReasoningEffort=""):
    base.BaseProvider.__init__(self, pModel, pBaseUrl, pApiKey, pTimeoutSeconds)
    self.vApiKey = self.vApiKey or os.environ.get(cApiKeyEnvironmentVariable, "")
    if not self.vApiKey:
      raise base.ProviderError(
        "No DeepSeek API key. Set it for this agent in the web interface."
      )

    if self.vModel in dRetiredModels:
      raise base.ProviderError(
        "DeepSeek no longer serves %r. Use %r instead (current models: %s)."
        % (self.vModel, dRetiredModels[self.vModel], ", ".join(lKnownModels))
      )

    self.vThinking = bool(pThinking)
    self.vReasoningEffort = str(pReasoningEffort or "").lower()
    if self.vReasoningEffort and self.vReasoningEffort not in lReasoningEfforts:
      raise base.ProviderError(
        "Unsupported reasoning effort %r. Use one of: %s"
        % (pReasoningEffort, ", ".join(lReasoningEfforts))
      )

  def fSendMessages(self, pSystemPrompt, pMessages, pTools, pMaxTokens):
    """Send one chat/completions request."""
    dPayload = {
      "model": self.vModel,
      "messages": base.fNeutralMessagesToOpenAiFormat(pSystemPrompt, pMessages),
      "max_tokens": int(pMaxTokens),
      "stream": False,
    }
    if pTools:
      dPayload["tools"] = [base.fToolSchemaToOpenAiFormat(dTool) for dTool in pTools]
      dPayload["tool_choice"] = "auto"
    if self.vThinking:
      dPayload["thinking"] = {"type": "enabled"}
      if self.vReasoningEffort:
        dPayload["reasoning_effort"] = self.vReasoningEffort

    try:
      vResponse = requests.post(
        "%s/chat/completions" % (self.vBaseUrl,),
        headers={
          "Authorization": "Bearer %s" % (self.vApiKey,),
          "Content-Type": "application/json",
        },
        json=dPayload,
        timeout=self.vTimeoutSeconds,
      )
      if vResponse.status_code == 402:
        raise base.ProviderError(
          "DeepSeek rejected the request for lack of balance. Top up the "
          "account or switch this agent to a self-hosted provider."
        )
      if vResponse.status_code == 400 and self.vModel not in lKnownModels:
        raise base.ProviderError(
          "DeepSeek refused the request. Model %r may not exist; the current "
          "models are %s." % (self.vModel, ", ".join(lKnownModels))
        )
      vResponse.raise_for_status()
      dBody = vResponse.json()
    except requests.ConnectionError:
      raise base.ProviderError("Cannot reach DeepSeek at %s." % (self.vBaseUrl,))
    except requests.RequestException as vError:
      raise base.ProviderError(
        "DeepSeek request failed: %s" % (base.fDescribeHttpError(vError),))
    except ValueError as vError:
      raise base.ProviderError("DeepSeek returned invalid JSON: %s" % (vError,))

    if dBody.get("error"):
      raise base.ProviderError(
        "DeepSeek error: %s" % (dBody["error"].get("message", dBody["error"]),)
      )

    lChoices = dBody.get("choices") or []
    if not lChoices:
      raise base.ProviderError("DeepSeek returned no choices")

    # Any reasoning text is dropped here, deliberately. The runner replays
    # every message it is given, and reasoning content is not meant to be sent
    # back on the next turn.
    dMessage = lChoices[0].get("message") or {}
    dMessage.pop("reasoning_content", None)

    return base.fParseOpenAiChoice(lChoices[0], dBody.get("usage"))
