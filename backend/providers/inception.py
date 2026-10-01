"""Inception Labs provider adapter.

Serves diffusion language models, which generate a whole reply at once instead
of token by token. From this side of the API nothing about that is visible:
the request and the response are the ordinary chat/completions ones.
"""

import os

from backend.providers import base
from backend.providers import openai_dialect

cApiKeyEnvironmentVariable = "INCEPTION_API_KEY"


class InceptionProvider(base.BaseProvider):
  """Talks to the Inception Labs chat/completions API."""

  cProviderName = "inception"
  cDisplayName = "Inception Labs"
  cDefaultModel = "mercury-2"
  cDefaultBaseUrl = "https://api.inceptionlabs.ai/v1"

  cMaxTokensField = "max_tokens"

  def __init__(self, pModel="", pBaseUrl="", pApiKey="", pTimeoutSeconds=None):
    base.BaseProvider.__init__(self, pModel, pBaseUrl, pApiKey, pTimeoutSeconds)
    self.vApiKey = self.vApiKey or os.environ.get(cApiKeyEnvironmentVariable, "")
    if not self.vApiKey:
      raise base.ProviderError(
        "No Inception Labs API key. Set it for this agent in the web interface."
      )

  def fSendMessages(self, pSystemPrompt, pMessages, pTools, pMaxTokens):
    """Send one chat/completions request."""
    return openai_dialect.fSendChatCompletion(
      self, pSystemPrompt, pMessages, pTools, pMaxTokens)
