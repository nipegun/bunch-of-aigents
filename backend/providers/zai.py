"""Z.ai provider adapter.

Z.ai serves the GLM family on an OpenAI-compatible endpoint under a path of
its own, `/api/paas/v4`, which is why the base URL looks unlike the others.
The GLM models take tool calls the ordinary way.
"""

import os

from backend.providers import base
from backend.providers import openai_dialect

cApiKeyEnvironmentVariable = "ZAI_API_KEY"


class ZaiProvider(base.BaseProvider):
  """Talks to the Z.ai chat/completions API."""

  cProviderName = "zai"
  cDisplayName = "Z.ai"
  cDefaultModel = "glm-4.5"
  cDefaultBaseUrl = "https://api.z.ai/api/paas/v4"

  def __init__(self, pModel="", pBaseUrl="", pApiKey="", pTimeoutSeconds=None):
    base.BaseProvider.__init__(self, pModel, pBaseUrl, pApiKey, pTimeoutSeconds)
    self.vApiKey = self.vApiKey or os.environ.get(cApiKeyEnvironmentVariable, "")
    if not self.vApiKey:
      raise base.ProviderError(
        "No Z.ai API key. Set it for this agent in the web interface."
      )

  def fSendMessages(self, pSystemPrompt, pMessages, pTools, pMaxTokens):
    """Send one chat/completions request."""
    return openai_dialect.fSendChatCompletion(
      self, pSystemPrompt, pMessages, pTools, pMaxTokens)
