"""Qwen (Alibaba DashScope) provider adapter.

The address is DashScope's OpenAI-compatible endpoint, and the international
one: the mainland-China host is a different domain, which is why the base URL
is worth reading before assuming an account works against it. An installation
on the other side of that split changes it in the agent's Base URL box.
"""

import os

from backend.providers import base
from backend.providers import openai_dialect

cApiKeyEnvironmentVariable = "DASHSCOPE_API_KEY"


class QwenProvider(base.BaseProvider):
  """Talks to the Qwen chat/completions API."""

  cProviderName = "qwen"
  cDisplayName = "Qwen"
  cDefaultModel = "qwen3.8-max"
  cDefaultBaseUrl = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

  def __init__(self, pModel="", pBaseUrl="", pApiKey="", pTimeoutSeconds=None):
    base.BaseProvider.__init__(self, pModel, pBaseUrl, pApiKey, pTimeoutSeconds)
    self.vApiKey = self.vApiKey or os.environ.get(cApiKeyEnvironmentVariable, "")
    if not self.vApiKey:
      raise base.ProviderError(
        "No Qwen API key. Set it for this agent in the web interface."
      )

  def fSendMessages(self, pSystemPrompt, pMessages, pTools, pMaxTokens):
    """Send one chat/completions request."""
    return openai_dialect.fSendChatCompletion(
      self, pSystemPrompt, pMessages, pTools, pMaxTokens)
