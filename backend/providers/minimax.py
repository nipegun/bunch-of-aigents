"""MiniMax provider adapter.

The catalogue this project ships for MiniMax was read from the provider's own
/v1/models endpoint rather than from the model list the other providers came
from, which has no MiniMax rows. It carries no prices for that reason.

Its models answer with their reasoning inside the reply, wrapped in <think>
tags, rather than in a field of their own. That is stripped in the shared
dialect module, where it belongs: it is the model doing it, so the same model
served through a gateway does it too.
"""

import os

from backend.providers import base
from backend.providers import openai_dialect

cApiKeyEnvironmentVariable = "MINIMAX_API_KEY"


class MiniMaxProvider(base.BaseProvider):
  """Talks to the MiniMax chat/completions API."""

  cProviderName = "minimax"
  cDisplayName = "MiniMax"
  # From the provider's own /v1/models, because api-models.json lists none
  # for MiniMax. The first of them, there being no prices to sort by.
  cDefaultModel = "MiniMax-M2"
  cDefaultBaseUrl = "https://api.minimax.io/v1"

  def __init__(self, pModel="", pBaseUrl="", pApiKey="", pTimeoutSeconds=None):
    base.BaseProvider.__init__(self, pModel, pBaseUrl, pApiKey, pTimeoutSeconds)
    self.vApiKey = self.vApiKey or os.environ.get(cApiKeyEnvironmentVariable, "")
    if not self.vApiKey:
      raise base.ProviderError(
        "No MiniMax API key. Set it for this agent in the web interface."
      )

  def fSendMessages(self, pSystemPrompt, pMessages, pTools, pMaxTokens):
    """Send one chat/completions request."""
    return openai_dialect.fSendChatCompletion(
      self, pSystemPrompt, pMessages, pTools, pMaxTokens)
