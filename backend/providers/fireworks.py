"""Fireworks AI provider adapter.

Model ids here are full account paths - `accounts/fireworks/models/<model>` -
and an account that has deployed its own model addresses it the same way with
its own account name in the first segment. The catalogue lists the public
ones; the field takes any of them.
"""

import os

from backend.providers import base
from backend.providers import openai_dialect

cApiKeyEnvironmentVariable = "FIREWORKS_API_KEY"


class FireworksProvider(base.BaseProvider):
  """Talks to the Fireworks AI chat/completions API."""

  cProviderName = "fireworks"
  cDisplayName = "Fireworks AI"
  # The 120b and not the cheaper 20b: measured against a real account, the
  # 20b answers "Model not found, inaccessible, and/or not deployed" - it
  # needs a deployment of its own, while this one is served to everybody.
  cDefaultModel = "accounts/fireworks/models/gpt-oss-120b"
  cDefaultBaseUrl = "https://api.fireworks.ai/inference/v1"

  cMaxTokensField = "max_tokens"

  def __init__(self, pModel="", pBaseUrl="", pApiKey="", pTimeoutSeconds=None):
    base.BaseProvider.__init__(self, pModel, pBaseUrl, pApiKey, pTimeoutSeconds)
    self.vApiKey = self.vApiKey or os.environ.get(cApiKeyEnvironmentVariable, "")
    if not self.vApiKey:
      raise base.ProviderError(
        "No Fireworks AI API key. Set it for this agent in the web interface."
      )

  def fSendMessages(self, pSystemPrompt, pMessages, pTools, pMaxTokens):
    """Send one chat/completions request."""
    return openai_dialect.fSendChatCompletion(
      self, pSystemPrompt, pMessages, pTools, pMaxTokens)
