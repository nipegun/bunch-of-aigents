"""Vercel AI Gateway adapter.

Also a router, in front of most of the providers this project talks to
directly, with the model named `vendor/model`. It answers with reasoning
nested inside the content blocks rather than in a field of its own; the shared
dialect module drops it, because reasoning is not meant to travel back on the
next turn.
"""

import os

from backend.providers import base
from backend.providers import openai_dialect

cApiKeyEnvironmentVariable = "AI_GATEWAY_API_KEY"


class VercelProvider(base.BaseProvider):
  """Talks to the Vercel AI Gateway chat/completions API."""

  cProviderName = "vercel"
  cDisplayName = "Vercel AI Gateway"
  cDefaultModel = "openai/gpt-oss-20b"
  cDefaultBaseUrl = "https://ai-gateway.vercel.sh/v1"

  cMaxTokensField = "max_tokens"

  def __init__(self, pModel="", pBaseUrl="", pApiKey="", pTimeoutSeconds=None):
    base.BaseProvider.__init__(self, pModel, pBaseUrl, pApiKey, pTimeoutSeconds)
    self.vApiKey = self.vApiKey or os.environ.get(cApiKeyEnvironmentVariable, "")
    if not self.vApiKey:
      raise base.ProviderError(
        "No Vercel AI Gateway API key. Set it for this agent in the web interface."
      )

  def fSendMessages(self, pSystemPrompt, pMessages, pTools, pMaxTokens):
    """Send one chat/completions request."""
    return openai_dialect.fSendChatCompletion(
      self, pSystemPrompt, pMessages, pTools, pMaxTokens)
