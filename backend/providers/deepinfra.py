"""DeepInfra provider adapter.

Another host for open-weight models, and one of the cheaper ones per token.
The OpenAI-compatible endpoint lives under `/v1/openai`, which is the only
thing that distinguishes its address from the rest.
"""

import os

from backend.providers import base
from backend.providers import openai_dialect

cApiKeyEnvironmentVariable = "DEEPINFRA_API_KEY"


class DeepInfraProvider(base.BaseProvider):
  """Talks to the DeepInfra chat/completions API."""

  cProviderName = "deepinfra"
  cDisplayName = "DeepInfra"
  cDefaultModel = "moonshotai/Kimi-K3"
  cDefaultBaseUrl = "https://api.deepinfra.com/v1/openai"

  cMaxTokensField = "max_tokens"

  def __init__(self, pModel="", pBaseUrl="", pApiKey="", pTimeoutSeconds=None):
    base.BaseProvider.__init__(self, pModel, pBaseUrl, pApiKey, pTimeoutSeconds)
    self.vApiKey = self.vApiKey or os.environ.get(cApiKeyEnvironmentVariable, "")
    if not self.vApiKey:
      raise base.ProviderError(
        "No DeepInfra API key. Set it for this agent in the web interface."
      )

  def fSendMessages(self, pSystemPrompt, pMessages, pTools, pMaxTokens):
    """Send one chat/completions request."""
    return openai_dialect.fSendChatCompletion(
      self, pSystemPrompt, pMessages, pTools, pMaxTokens)
