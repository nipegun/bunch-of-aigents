"""xAI provider adapter.

Grok's chat/completions endpoint. The models carry a large output ceiling -
larger than the context window of most providers - so `max_tokens_per_run` in
the agent's settings is the thing that actually bounds a reply here, not the
model.
"""

import os

from backend.providers import base
from backend.providers import openai_dialect

cApiKeyEnvironmentVariable = "XAI_API_KEY"


class XaiProvider(base.BaseProvider):
  """Talks to the xAI chat/completions API."""

  cProviderName = "xai"
  cDisplayName = "xAI"
  cDefaultModel = "grok-4.3"
  cDefaultBaseUrl = "https://api.x.ai/v1"

  def __init__(self, pModel="", pBaseUrl="", pApiKey="", pTimeoutSeconds=None):
    base.BaseProvider.__init__(self, pModel, pBaseUrl, pApiKey, pTimeoutSeconds)
    self.vApiKey = self.vApiKey or os.environ.get(cApiKeyEnvironmentVariable, "")
    if not self.vApiKey:
      raise base.ProviderError(
        "No xAI API key. Set it for this agent in the web interface."
      )

  def fSendMessages(self, pSystemPrompt, pMessages, pTools, pMaxTokens):
    """Send one chat/completions request."""
    return openai_dialect.fSendChatCompletion(
      self, pSystemPrompt, pMessages, pTools, pMaxTokens)
