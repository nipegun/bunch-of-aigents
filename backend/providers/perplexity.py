"""Perplexity provider adapter.

The one provider here that does not serve chat/completions at all. It used to,
and now answers that request with a 403 and a migration notice:

    Sonar is now the Agent API. Use /v1/responses instead of /v1/sonar

So this adapter speaks the Responses API: one `input` list instead of
`messages`, the system prompt as `instructions`, `max_output_tokens` instead of
`max_tokens`, and a reply that arrives as a list of output items - a `message`
with its text in blocks, or a `function_call` - rather than as a choice with a
message inside it. A tool result goes back as an item of its own,
`function_call_output`, matched to its call by `call_id`.

Perplexity is also a router now rather than one model: `/v1/models` lists
models from Anthropic, Google, OpenAI and xAI beside its own `perplexity/*`
ones, priced per million tokens. Its own Sonar models are the ones that answer
with a web search already done, which overlaps with what this project's
`web.fetch` and `rss.fetch` tools do - the difference being that the search
happens on Perplexity's side and the agent never sees the pages.
"""

import json
import os

import requests

from backend.providers import base

cApiKeyEnvironmentVariable = "PERPLEXITY_API_KEY"

# The endpoint that replaced chat/completions, and the one that lists models.
cResponsesPath = "/responses"

# Output item types this adapter reads. Anything else in the list - a reasoning
# item, a web search record - is skipped rather than guessed at.
cItemMessage = "message"
cItemFunctionCall = "function_call"
cItemFunctionCallOutput = "function_call_output"

# What `status` says when the model was cut off by the token ceiling.
cStatusIncomplete = "incomplete"


class PerplexityProvider(base.BaseProvider):
  """Talks to the Perplexity Agent API."""

  cProviderName = "perplexity"
  cDisplayName = "Perplexity"
  # The cheapest in the catalogue. The previous default was second cheapest
  # on input and was never compared against the list.  #
  # Verified against the real API on 2026-09-19 with `_/temp/probe-defaults.py`:
  # asked, called a tool, and answered that tool call. Re-run it after moving
  # a default; if one stops answering, move to the next cheapest and write the
  # provider's own error beside it, as kimi and together do.
  cDefaultModel = "openai/gpt-5-nano"
  cDefaultBaseUrl = "https://api.perplexity.ai/v1"

  def __init__(self, pModel="", pBaseUrl="", pApiKey="", pTimeoutSeconds=None):
    base.BaseProvider.__init__(self, pModel, pBaseUrl, pApiKey, pTimeoutSeconds)
    self.vApiKey = self.vApiKey or os.environ.get(cApiKeyEnvironmentVariable, "")
    if not self.vApiKey:
      raise base.ProviderError(
        "No Perplexity API key. Set it for this agent in the web interface."
      )

  def fBuildInput(self, pMessages):
    """Convert neutral messages to the Responses API input list.

    Tool calls and their results are items in this list rather than messages,
    which is the one real difference from the chat/completions shape: an
    assistant turn that called two tools becomes its text plus two items.
    """
    lInput = []
    for dMessage in pMessages:
      vRole = dMessage.get("role")

      if vRole == "tool":
        lInput.append({
          "type": cItemFunctionCallOutput,
          "call_id": dMessage.get("tool_call_id", ""),
          "output": str(dMessage.get("content", "")),
        })
        continue

      if vRole == "assistant" and dMessage.get("tool_calls"):
        if dMessage.get("content"):
          lInput.append({"role": "assistant",
                         "content": str(dMessage["content"])})
        for vCall in dMessage["tool_calls"]:
          lInput.append({
            "type": cItemFunctionCall,
            "call_id": vCall.vCallId,
            "name": base.fToolNameToWire(vCall.vName),
            "arguments": json.dumps(vCall.dArguments, ensure_ascii=False),
          })
        continue

      lInput.append({"role": vRole, "content": str(dMessage.get("content", ""))})

    return lInput

  def fBuildTools(self, pTools):
    """Convert neutral tool schemas to the Responses API shape.

    Flatter than the chat/completions one: name and parameters sit at the top
    level of the tool rather than inside a `function` object.
    """
    return [
      {
        "type": "function",
        "name": base.fToolNameToWire(dTool["name"]),
        "description": dTool.get("description", ""),
        "parameters": dTool.get("input_schema") or {
          "type": "object", "properties": {}
        },
      }
      for dTool in pTools
    ]

  def fSendMessages(self, pSystemPrompt, pMessages, pTools, pMaxTokens):
    """Send one Responses API request."""
    dPayload = {
      "model": self.vModel,
      "input": self.fBuildInput(pMessages),
      "max_output_tokens": int(pMaxTokens),
      "stream": False,
    }
    if pSystemPrompt:
      dPayload["instructions"] = pSystemPrompt
    if pTools:
      dPayload["tools"] = self.fBuildTools(pTools)
      dPayload["tool_choice"] = "auto"

    try:
      vResponse = requests.post(
        "%s%s" % (self.vBaseUrl, cResponsesPath),
        headers={
          "Authorization": "Bearer %s" % (self.vApiKey,),
          "Content-Type": "application/json",
        },
        json=dPayload,
        timeout=self.vTimeoutSeconds,
      )
      if vResponse.status_code in (401, 403):
        # 403 here is also what the retired chat/completions endpoint answers,
        # so the message names both possibilities rather than blaming the key.
        raise base.ProviderError(
          "Perplexity refused the request: %s"
          % (base.fDescribeHttpError(
            requests.HTTPError(response=vResponse)),)
        )
      if vResponse.status_code == 429:
        raise base.ProviderError(
          "Perplexity is rate-limiting this account. The run can be tried "
          "again later.")
      vResponse.raise_for_status()
      dBody = vResponse.json()
    except requests.ConnectionError:
      raise base.ProviderError(
        "Cannot reach Perplexity at %s." % (self.vBaseUrl,))
    except requests.Timeout:
      raise base.ProviderError(
        "Perplexity did not answer within %d seconds."
        % (int(self.vTimeoutSeconds),))
    except requests.RequestException as vError:
      raise base.ProviderError(
        "Perplexity request failed: %s" % (base.fDescribeHttpError(vError),))
    except ValueError as vError:
      raise base.ProviderError(
        "Perplexity returned invalid JSON: %s" % (vError,))

    return fParsePerplexityResponse(dBody)


def fParsePerplexityResponse(pBody):
  """Turn one Responses API body into a ProviderResponse."""
  dBody = pBody or {}

  dError = dBody.get("error")
  if dError:
    vMessage = dError.get("message") if isinstance(dError, dict) else dError
    raise base.ProviderError("Perplexity error: %s" % (vMessage,))

  lTextParts = []
  lToolCalls = []

  for dItem in dBody.get("output") or []:
    if not isinstance(dItem, dict):
      continue
    vType = dItem.get("type")

    if vType == cItemMessage:
      for dBlock in dItem.get("content") or []:
        if isinstance(dBlock, dict) and dBlock.get("text"):
          lTextParts.append(str(dBlock["text"]))
      continue

    if vType == cItemFunctionCall:
      lToolCalls.append(base.ToolCall(
        dItem.get("call_id") or dItem.get("id") or "",
        base.fToolNameFromWire(dItem.get("name") or ""),
        dItem.get("arguments") or "{}",
      ))

  vStatus = str(dBody.get("status") or "")
  if lToolCalls:
    vStopReason = base.cStopToolUse
  elif vStatus == cStatusIncomplete:
    vStopReason = base.cStopMaxTokens
  else:
    vStopReason = base.cStopEndTurn

  dUsage = dBody.get("usage") or {}
  return base.ProviderResponse(
    pText="".join(lTextParts),
    pToolCalls=lToolCalls,
    pStopReason=vStopReason,
    pPromptTokens=dUsage.get("input_tokens", 0),
    pCompletionTokens=dUsage.get("output_tokens", 0),
    pRawStopReason=vStatus,
  )
