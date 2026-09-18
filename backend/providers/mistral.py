"""Mistral AI provider adapter.

One deliberate difference from the reference catalogue this was built from:
that catalogue records Mistral's tool_choice as `any`, which on this API means
the model must call a tool on every turn. An agent that can never answer
without calling something never finishes a run, so `auto` is used instead -
which is also what the API does when the field is absent.
"""

import os

from backend.providers import base
from backend.providers import openai_dialect

cApiKeyEnvironmentVariable = "MISTRAL_API_KEY"


class MistralProvider(base.BaseProvider):
  """Talks to the Mistral AI chat/completions API."""

  cProviderName = "mistral"
  cDisplayName = "Mistral AI"
  cDefaultModel = "labs-leanstral-1-5"
  cDefaultBaseUrl = "https://api.mistral.ai/v1"

  cMaxTokensField = "max_tokens"

  def __init__(self, pModel="", pBaseUrl="", pApiKey="", pTimeoutSeconds=None):
    base.BaseProvider.__init__(self, pModel, pBaseUrl, pApiKey, pTimeoutSeconds)
    self.vApiKey = self.vApiKey or os.environ.get(cApiKeyEnvironmentVariable, "")
    if not self.vApiKey:
      raise base.ProviderError(
        "No Mistral AI API key. Set it for this agent in the web interface."
      )

  def fSendMessages(self, pSystemPrompt, pMessages, pTools, pMaxTokens):
    """Send one chat/completions request."""
    return openai_dialect.fSendChatCompletion(
      self, pSystemPrompt, pMessages, pTools, pMaxTokens)
