"""Cerebras provider adapter.

Like Groq, open-weight models served fast on hardware of its own. The
catalogue is short because that is what the provider serves, not because it
was trimmed.
"""

import os

from backend.providers import base
from backend.providers import openai_dialect

cApiKeyEnvironmentVariable = "CEREBRAS_API_KEY"


class CerebrasProvider(base.BaseProvider):
  """Talks to the Cerebras chat/completions API."""

  cProviderName = "cerebras"
  cDisplayName = "Cerebras"
  cDefaultModel = "gpt-oss-120b"
  cDefaultBaseUrl = "https://api.cerebras.ai/v1"

  def __init__(self, pModel="", pBaseUrl="", pApiKey="", pTimeoutSeconds=None):
    base.BaseProvider.__init__(self, pModel, pBaseUrl, pApiKey, pTimeoutSeconds)
    self.vApiKey = self.vApiKey or os.environ.get(cApiKeyEnvironmentVariable, "")
    if not self.vApiKey:
      raise base.ProviderError(
        "No Cerebras API key. Set it for this agent in the web interface."
      )

  def fSendMessages(self, pSystemPrompt, pMessages, pTools, pMaxTokens):
    """Send one chat/completions request."""
    return openai_dialect.fSendChatCompletion(
      self, pSystemPrompt, pMessages, pTools, pMaxTokens)
