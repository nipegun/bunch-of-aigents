"""Hugging Face Inference Providers adapter.

A router rather than a provider: the model id names the model and, after a
colon, which upstream provider should serve it - `:fastest` lets Hugging Face
pick. The reply can arrive with its content in blocks rather than as a string,
which the shared dialect module flattens.
"""

import os

from backend.providers import base
from backend.providers import openai_dialect

cApiKeyEnvironmentVariable = "HF_TOKEN"


class HuggingFaceProvider(base.BaseProvider):
  """Talks to the Hugging Face chat/completions API."""

  cProviderName = "huggingface"
  cDisplayName = "Hugging Face"
  cDefaultModel = "deepseek-ai/DeepSeek-V4-Flash-0731:fastest"
  cDefaultBaseUrl = "https://router.huggingface.co/v1"

  cMaxTokensField = "max_tokens"

  def __init__(self, pModel="", pBaseUrl="", pApiKey="", pTimeoutSeconds=None):
    base.BaseProvider.__init__(self, pModel, pBaseUrl, pApiKey, pTimeoutSeconds)
    self.vApiKey = self.vApiKey or os.environ.get(cApiKeyEnvironmentVariable, "")
    if not self.vApiKey:
      raise base.ProviderError(
        "No Hugging Face API key. Set it for this agent in the web interface."
      )

  def fSendMessages(self, pSystemPrompt, pMessages, pTools, pMaxTokens):
    """Send one chat/completions request."""
    return openai_dialect.fSendChatCompletion(
      self, pSystemPrompt, pMessages, pTools, pMaxTokens)
