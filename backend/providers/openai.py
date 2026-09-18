"""OpenAI provider adapter.

Uses the official `openai` SDK against chat/completions, which is the dialect
the other cloud and self-hosted adapters imitate. It is kept separate from
those even so: OpenAI is the only one of them with reasoning models that reject
a `temperature`, and that quirk belongs here rather than in shared code four
other providers have to tiptoe around.
"""

import os

from backend.providers import base

try:
  import openai as vOpenAiSdk
except ImportError:
  vOpenAiSdk = None

cApiKeyEnvironmentVariable = "OPENAI_API_KEY"

# What this API says when a reasoning model used the whole ceiling thinking.
cOutputLimitMarker = "max_tokens or model output limit was reached"


class OpenAiProvider(base.BaseProvider):
  """Talks to the OpenAI chat/completions API."""

  cProviderName = "openai"
  # gpt-4o is not served any more. Its replacement here is the small model
  # of the current generation rather than the large one: an agent on a cron
  # schedule nobody watches is the cheapest way to run up a bill, and the
  # bigger models are one click away in the LLM tab, with their price shown.
  cDefaultModel = "gpt-5-mini"
  cDefaultBaseUrl = "https://api.openai.com/v1"

  def __init__(self, pModel="", pBaseUrl="", pApiKey="", pTimeoutSeconds=None):
    base.BaseProvider.__init__(self, pModel, pBaseUrl, pApiKey, pTimeoutSeconds)
    if vOpenAiSdk is None:
      raise base.ProviderError(
        "The openai package is not installed. Run the installer to update the "
        "virtual environment."
      )
    vApiKey = self.vApiKey or os.environ.get(cApiKeyEnvironmentVariable, "")
    if not vApiKey:
      raise base.ProviderError(
        "No OpenAI API key. Set it for this agent in the web interface."
      )
    self.vClient = vOpenAiSdk.OpenAI(
      api_key=vApiKey,
      base_url=self.vBaseUrl or self.cDefaultBaseUrl,
      timeout=float(self.vTimeoutSeconds),
    )

  def fSendMessages(self, pSystemPrompt, pMessages, pTools, pMaxTokens):
    """Send one chat/completions request."""
    dRequest = {
      "model": self.vModel,
      "messages": base.fNeutralMessagesToOpenAiFormat(pSystemPrompt, pMessages),
      "max_completion_tokens": int(pMaxTokens),
    }
    if pTools:
      dRequest["tools"] = [base.fToolSchemaToOpenAiFormat(dTool) for dTool in pTools]
      dRequest["tool_choice"] = "auto"

    try:
      vCompletion = self.vClient.chat.completions.create(**dRequest)
    except Exception as vError:
      vDescription = base.fDescribeSdkError(vError)
      # A reasoning model spends tokens thinking before it writes anything, and
      # when the ceiling is reached during that, this API returns a 400 rather
      # than a short answer:
      #   Could not finish the message because max_tokens or model output
      #   limit was reached
      # Which reads like a bug in the request and is in fact a budget, so it is
      # said in the words of the setting that controls it.
      if cOutputLimitMarker in vDescription:
        raise base.ProviderError(
          "%s ran out of tokens while reasoning, before writing an answer. "
          "Raise this agent's token ceiling in its Limits tab, or pick a "
          "model that does not reason. (%s)"
          % (self.cProviderName, vDescription[:200])
        )
      raise base.ProviderError("OpenAI request failed: %s" % (vDescription,))

    dCompletion = vCompletion.model_dump()
    lChoices = dCompletion.get("choices") or []
    if not lChoices:
      raise base.ProviderError("OpenAI returned no choices")
    return base.fParseOpenAiChoice(lChoices[0], dCompletion.get("usage"))
