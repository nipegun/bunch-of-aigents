"""Kimi (Moonshot AI) provider adapter.

Moonshot serves the chat/completions dialect at api.moonshot.ai. The K2 and K3
models are built for tool use and carry a large context window, which is what
makes them interesting for an agent that replays a long conversation on every
step - and also what makes the token limits in the agent's own settings worth
setting deliberately rather than leaving at whatever fits.
"""

import os

from backend.providers import base
from backend.providers import openai_dialect

cApiKeyEnvironmentVariable = "MOONSHOT_API_KEY"


class KimiProvider(base.BaseProvider):
  """Talks to the Kimi chat/completions API."""

  cProviderName = "kimi"
  cDisplayName = "Kimi"
  # k2.5 is in the catalogue but Moonshot no longer serves it: the API
  # answers "Not found the model kimi-k2.5 or Permission denied". k2.6 is
  # the cheapest one it does serve.
  cDefaultModel = "kimi-k2.6"
  cDefaultBaseUrl = "https://api.moonshot.ai/v1"

  def __init__(self, pModel="", pBaseUrl="", pApiKey="", pTimeoutSeconds=None):
    base.BaseProvider.__init__(self, pModel, pBaseUrl, pApiKey, pTimeoutSeconds)
    self.vApiKey = self.vApiKey or os.environ.get(cApiKeyEnvironmentVariable, "")
    if not self.vApiKey:
      raise base.ProviderError(
        "No Kimi API key. Set it for this agent in the web interface."
      )

  def fSendMessages(self, pSystemPrompt, pMessages, pTools, pMaxTokens):
    """Send one chat/completions request."""
    return openai_dialect.fSendChatCompletion(
      self, pSystemPrompt, pMessages, pTools, pMaxTokens)
