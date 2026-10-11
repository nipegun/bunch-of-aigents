"""Together AI provider adapter.

A host for open-weight models, addressed by the model's full repository name -
`openai/gpt-oss-120b` and the like. Getting that name exactly right matters
more here than with a provider that serves half a dozen models of its own.

It also leaves a marker in the reply that the other hosts of the same model
strip: gpt-oss writes its answer in channels, `analysis` for its reasoning and
`final` for the answer, and Together returns the channel name stuck to the
front of the text - "finalThe weather in Madrid is 18 C". Groq and Cerebras,
serving the same model, do not. Removed here, because it is this provider
doing it.
"""

import os
import re

from backend.providers import base
from backend.providers import openai_dialect

cApiKeyEnvironmentVariable = "TOGETHER_API_KEY"

# Only at the very start, and only when the next character cannot be the
# continuation of a word: an answer that genuinely begins "final" is followed
# by a space or a lowercase letter, never by a capital or a quote.
cChannelMarkerPattern = re.compile(r"\A(?:analysis|commentary|final)+(?=[A-Z\"'])")


def fStripChannelMarker(pText):
  """Return the reply without the channel name Together leaves in front."""
  return cChannelMarkerPattern.sub("", str(pText or ""), count=1)


class TogetherProvider(base.BaseProvider):
  """Talks to the Together AI chat/completions API."""

  cProviderName = "together"
  cDisplayName = "Together AI"
  # Same reason as Fireworks: measured against a real account, the 20b comes
  # back "Unable to access non-serverless model" - it wants a dedicated
  # endpoint. The 120b is served without one.
  cDefaultModel = "openai/gpt-oss-120b"
  cDefaultBaseUrl = "https://api.together.ai/v1"

  cMaxTokensField = "max_tokens"

  def __init__(self, pModel="", pBaseUrl="", pApiKey="", pTimeoutSeconds=None):
    base.BaseProvider.__init__(self, pModel, pBaseUrl, pApiKey, pTimeoutSeconds)
    self.vApiKey = self.vApiKey or os.environ.get(cApiKeyEnvironmentVariable, "")
    if not self.vApiKey:
      raise base.ProviderError(
        "No Together AI API key. Set it for this agent in the web interface."
      )

  def fSendMessages(self, pSystemPrompt, pMessages, pTools, pMaxTokens):
    """Send one chat/completions request."""
    vResponse = openai_dialect.fSendChatCompletion(
      self, pSystemPrompt, pMessages, pTools, pMaxTokens)
    vResponse.vText = fStripChannelMarker(vResponse.vText)
    return vResponse
