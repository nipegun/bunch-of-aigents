"""Groq provider adapter.

Groq runs open-weight models on its own hardware, which is what it sells:
the same model as elsewhere, answered in a fraction of the time. For an agent
that spends most of a run waiting on the model between tool calls, that is the
whole difference.
"""

import os

from backend.providers import base
from backend.providers import openai_dialect

cApiKeyEnvironmentVariable = "GROQ_API_KEY"


class GroqProvider(base.BaseProvider):
  """Talks to the Groq chat/completions API."""

  cProviderName = "groq"
  cDisplayName = "Groq"
  cDefaultModel = "openai/gpt-oss-20b"
  cDefaultBaseUrl = "https://api.groq.com/openai/v1"

  def __init__(self, pModel="", pBaseUrl="", pApiKey="", pTimeoutSeconds=None):
    base.BaseProvider.__init__(self, pModel, pBaseUrl, pApiKey, pTimeoutSeconds)
    self.vApiKey = self.vApiKey or os.environ.get(cApiKeyEnvironmentVariable, "")
    if not self.vApiKey:
      raise base.ProviderError(
        "No Groq API key. Set it for this agent in the web interface."
      )

  def fSendMessages(self, pSystemPrompt, pMessages, pTools, pMaxTokens):
    """Send one chat/completions request."""
    return openai_dialect.fSendChatCompletion(
      self, pSystemPrompt, pMessages, pTools, pMaxTokens)
