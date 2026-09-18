"""vLLM provider adapter.

Talks to a vLLM OpenAI-compatible server, the option to reach for when the
installation has a GPU and several agents run at once: vLLM batches concurrent
requests, so ten agents waking on the same cron minute cost far less wall time
here than on a single-stream server.

Its particulars: the model field must be the exact served model name that vLLM
was started with (a wrong one returns 404 rather than falling back to a
default), and tool calling requires the server to have been started with
--enable-auto-tool-choice and a parser, which this adapter reports clearly.
"""

import requests

from backend.providers import base

cSelfHostedTimeoutSeconds = 600


class VllmProvider(base.BaseProvider):
  """Talks to a vLLM OpenAI-compatible server."""

  cProviderName = "vllm"
  cDefaultModel = ""
  cDefaultBaseUrl = "http://127.0.0.1:8000"

  def __init__(self, pModel="", pBaseUrl="", pApiKey="", pTimeoutSeconds=None):
    base.BaseProvider.__init__(
      self, pModel, pBaseUrl, pApiKey, pTimeoutSeconds or cSelfHostedTimeoutSeconds
    )
    if not self.vModel:
      raise base.ProviderError(
        "vLLM needs the exact served model name. Check `curl %s/v1/models`."
        % (self.vBaseUrl,)
      )

  def fListServedModels(self):
    """Return the model names this server actually serves."""
    try:
      vResponse = requests.get("%s/v1/models" % (self.vBaseUrl,), timeout=30)
      vResponse.raise_for_status()
      return [dModel.get("id", "") for dModel in vResponse.json().get("data") or []]
    except (requests.RequestException, ValueError):
      return []

  def fSendMessages(self, pSystemPrompt, pMessages, pTools, pMaxTokens):
    """Send one chat/completions request to vLLM."""
    dPayload = {
      "model": self.vModel,
      "messages": base.fNeutralMessagesToOpenAiFormat(pSystemPrompt, pMessages),
      "max_tokens": int(pMaxTokens),
      "stream": False,
    }
    if pTools:
      dPayload["tools"] = [base.fToolSchemaToOpenAiFormat(dTool) for dTool in pTools]
      dPayload["tool_choice"] = "auto"

    dHeaders = {"Content-Type": "application/json"}
    if self.vApiKey:
      dHeaders["Authorization"] = "Bearer %s" % (self.vApiKey,)

    try:
      vResponse = requests.post(
        "%s/v1/chat/completions" % (self.vBaseUrl,),
        headers=dHeaders,
        json=dPayload,
        timeout=self.vTimeoutSeconds,
      )
      if vResponse.status_code == 404:
        lServed = self.fListServedModels()
        raise base.ProviderError(
          "vLLM does not serve a model called %r. Served models: %s"
          % (self.vModel, ", ".join(lServed) or "none")
        )
      if vResponse.status_code == 400 and pTools \
         and "tool" in (vResponse.text or "").lower():
        raise base.ProviderError(
          "vLLM refused a request with tools. Start it with "
          "--enable-auto-tool-choice and a --tool-call-parser."
        )
      vResponse.raise_for_status()
      dBody = vResponse.json()
    except requests.ConnectionError:
      raise base.ProviderError(
        "Cannot reach vLLM at %s. Is the server running?" % (self.vBaseUrl,)
      )
    except requests.RequestException as vError:
      raise base.ProviderError(
        "vLLM request failed: %s" % (base.fDescribeHttpError(vError),))
    except ValueError as vError:
      raise base.ProviderError("vLLM returned invalid JSON: %s" % (vError,))

    lChoices = dBody.get("choices") or []
    if not lChoices:
      raise base.ProviderError("vLLM returned no choices")
    return base.fParseOpenAiChoice(lChoices[0], dBody.get("usage"))
