"""Cloudflare Workers AI provider adapter.

Speaks chat/completions like most of the others, but is the only provider here
whose address depends on the credential: every account has its own endpoint,

    https://api.cloudflare.com/client/v4/accounts/<account id>/ai/v1

so there is no base URL that works before the key is known. The key stored for
this provider is therefore two values with a colon between them,

    <account id>:<api token>

which is what the field in Settings, API keys expects for Cloudflare and what
the placeholder there says. The account id goes into the URL and the token
into the Authorization header.

Model ids are the `@cf/vendor/model` names Workers AI publishes.
"""

import os

from backend.providers import base
from backend.providers import openai_dialect

cApiKeyEnvironmentVariable = "CLOUDFLARE_API_TOKEN"
cAccountEnvironmentVariable = "CLOUDFLARE_ACCOUNT_ID"

cBaseUrlTemplate = "https://api.cloudflare.com/client/v4/accounts/%s/ai/v1"

# How the two halves of the credential are joined, in the key file and in the
# box in the web interface.
cCredentialSeparator = ":"


class CloudflareProvider(base.BaseProvider):
  """Talks to the Workers AI chat/completions API of one account."""

  cProviderName = "cloudflare"
  cDisplayName = "Cloudflare Workers AI"
  cDefaultModel = "@cf/openai/gpt-oss-20b"
  # Left empty on purpose: it cannot be known until the account id is.
  cDefaultBaseUrl = ""
  cMaxTokensField = "max_tokens"
  # Its schema does not allow a null `content`, which is what an assistant
  # message carries when the model answered with tool calls and no words.
  cAssistantContentWhenEmpty = ""

  def __init__(self, pModel="", pBaseUrl="", pApiKey="", pTimeoutSeconds=None):
    base.BaseProvider.__init__(self, pModel, pBaseUrl, pApiKey, pTimeoutSeconds)

    vCredential = self.vApiKey or os.environ.get(cApiKeyEnvironmentVariable, "")
    if not vCredential:
      raise base.ProviderError(
        "No Cloudflare credential. Set it for this agent in the web "
        "interface, as account-id:api-token."
      )

    self.vAccountId, self.vApiKey = fSplitCredential(vCredential)
    if not self.vAccountId:
      self.vAccountId = os.environ.get(cAccountEnvironmentVariable, "")
    if not self.vAccountId:
      raise base.ProviderError(
        "The Cloudflare credential has no account id. It is written as "
        "account-id:api-token, both halves from the Cloudflare dashboard."
      )

    # An installation that put its own gateway in front keeps the address it
    # typed; everyone else gets the account's own endpoint.
    if not self.vBaseUrl:
      self.vBaseUrl = cBaseUrlTemplate % (self.vAccountId,)

  def fSendMessages(self, pSystemPrompt, pMessages, pTools, pMaxTokens):
    """Send one chat/completions request."""
    return openai_dialect.fSendChatCompletion(
      self, pSystemPrompt, pMessages, pTools, pMaxTokens)


def fSplitCredential(pCredential):
  """Return (account id, token) from what the user stored.

  A token on its own is accepted and leaves the account id empty, so that an
  installation holding the id in the environment still works. Split on the
  first colon only: a token containing one is the user's problem to paste, not
  a reason to lose the rest of it.
  """
  vCredential = str(pCredential or "").strip()
  if cCredentialSeparator not in vCredential:
    return "", vCredential
  vAccountId, vToken = vCredential.split(cCredentialSeparator, 1)
  return vAccountId.strip(), vToken.strip()
