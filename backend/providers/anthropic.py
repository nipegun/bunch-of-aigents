"""Anthropic provider adapter.

Uses the official `anthropic` SDK against the Messages API. Anthropic is the
one provider here that does not speak the chat/completions dialect: tool calls
and results are content blocks inside messages rather than separate fields, so
this adapter does the most translation work of the seven.

Two Anthropic features the other adapters have no equivalent for are used:
adaptive thinking, which lets the model decide how much to reason instead of
being given a fixed budget, and `count_tokens`, which is why an agent on this
provider can know its prompt size before spending anything on the call.
"""

import os

from backend.providers import base

try:
  import anthropic as vAnthropicSdk
except ImportError:
  vAnthropicSdk = None

# Environment variable holding the key, read by the agent's own process.
cApiKeyEnvironmentVariable = "ANTHROPIC_API_KEY"


class AnthropicProvider(base.BaseProvider):
  """Talks to the Anthropic Messages API."""

  cProviderName = "anthropic"
  # The cheapest model in this provider's catalogue, which is the rule: an
  # agent on a cron schedule that nobody is watching is the easiest way there
  # is to run up a bill, so the default is the one that costs least and the
  # bigger models are one click away in the LLM tab with their price shown.
  #
  # Verified against the real API on 2026-09-19 with `_/temp/probe-defaults.py`:
  # asked, called a tool, and answered that tool call. Re-run it after moving
  # a default; if one stops answering, move to the next cheapest and write the
  # provider's own error beside it, as kimi and together already do.
  cDefaultModel = "claude-sonnet-5"
  cDefaultBaseUrl = ""

  def __init__(self, pModel="", pBaseUrl="", pApiKey="", pTimeoutSeconds=None):
    base.BaseProvider.__init__(self, pModel, pBaseUrl, pApiKey, pTimeoutSeconds)
    if vAnthropicSdk is None:
      raise base.ProviderError(
        "The anthropic package is not installed. Run the installer to update "
        "the virtual environment."
      )
    vApiKey = self.vApiKey or os.environ.get(cApiKeyEnvironmentVariable, "")
    if not vApiKey:
      raise base.ProviderError(
        "No Anthropic API key. Set it for this agent in the web interface."
      )
    dClientKeywords = {"api_key": vApiKey, "timeout": float(self.vTimeoutSeconds)}
    if self.vBaseUrl:
      dClientKeywords["base_url"] = self.vBaseUrl
    self.vClient = vAnthropicSdk.Anthropic(**dClientKeywords)

  def fBuildToolDefinitions(self, pTools):
    """Convert neutral tool schemas to Anthropic tool definitions."""
    lDefinitions = []
    for dTool in pTools:
      lDefinitions.append({
        "name": base.fToolNameToWire(dTool["name"]),
        "description": dTool.get("description", ""),
        "input_schema": dTool.get("input_schema") or {
          "type": "object", "properties": {}
        },
      })
    return lDefinitions

  def fBuildMessages(self, pMessages):
    """Convert neutral messages to Anthropic content blocks.

    Tool results must arrive in a single user message, in the same order the
    model asked for them, so consecutive neutral tool messages are merged into
    one block list rather than sent one message at a time.
    """
    lConverted = []
    for dMessage in pMessages:
      vRole = dMessage.get("role")

      if vRole == "tool":
        dResultBlock = {
          "type": "tool_result",
          "tool_use_id": dMessage.get("tool_call_id", ""),
          "content": str(dMessage.get("content", "")),
        }
        if dMessage.get("is_error"):
          dResultBlock["is_error"] = True
        if lConverted and lConverted[-1]["role"] == "user" \
           and isinstance(lConverted[-1]["content"], list) \
           and lConverted[-1]["content"] \
           and lConverted[-1]["content"][0].get("type") == "tool_result":
          lConverted[-1]["content"].append(dResultBlock)
        else:
          lConverted.append({"role": "user", "content": [dResultBlock]})
        continue

      if vRole == "assistant" and dMessage.get("tool_calls"):
        lBlocks = []
        if dMessage.get("content"):
          lBlocks.append({"type": "text", "text": str(dMessage["content"])})
        for vCall in dMessage["tool_calls"]:
          lBlocks.append({
            "type": "tool_use",
            "id": vCall.vCallId,
            "name": base.fToolNameToWire(vCall.vName),
            "input": vCall.dArguments,
          })
        lConverted.append({"role": "assistant", "content": lBlocks})
        continue

      lConverted.append({
        "role": vRole,
        "content": str(dMessage.get("content", "")),
      })

    return lConverted

  def fSendMessages(self, pSystemPrompt, pMessages, pTools, pMaxTokens):
    """Send one request to the Messages API."""
    dRequest = {
      "model": self.vModel,
      "max_tokens": int(pMaxTokens),
      "messages": self.fBuildMessages(pMessages),
      # Adaptive thinking: the model decides how much to reason. There is no
      # token budget to tune, which is why the agent's own limit is a ceiling
      # on the reply rather than on the reasoning.
      "thinking": {"type": "adaptive"},
    }
    if pSystemPrompt:
      dRequest["system"] = pSystemPrompt
    if pTools:
      dRequest["tools"] = self.fBuildToolDefinitions(pTools)

    try:
      # Streaming, because an agent run with a large max_tokens would otherwise
      # risk an HTTP timeout on a long reply.
      with self.vClient.messages.stream(**dRequest) as vStream:
        vMessage = vStream.get_final_message()
    except Exception as vError:
      raise base.ProviderError(
        "Anthropic request failed: %s" % (base.fDescribeSdkError(vError),))

    return self.fParseMessage(vMessage)

  def fParseMessage(self, pMessage):
    """Turn one Anthropic message into a ProviderResponse."""
    lTextParts = []
    lToolCalls = []
    for vBlock in pMessage.content:
      if vBlock.type == "text":
        lTextParts.append(vBlock.text)
      elif vBlock.type == "tool_use":
        lToolCalls.append(base.ToolCall(
          vBlock.id, base.fToolNameFromWire(vBlock.name), vBlock.input))

    vRawStopReason = pMessage.stop_reason or ""
    if vRawStopReason == "tool_use":
      vStopReason = base.cStopToolUse
    elif vRawStopReason == "max_tokens":
      vStopReason = base.cStopMaxTokens
    elif vRawStopReason == "refusal":
      vStopReason = base.cStopRefusal
    else:
      vStopReason = base.cStopEndTurn

    vUsage = getattr(pMessage, "usage", None)
    return base.ProviderResponse(
      pText="\n".join(lTextParts),
      pToolCalls=lToolCalls,
      pStopReason=vStopReason,
      pPromptTokens=getattr(vUsage, "input_tokens", 0) if vUsage else 0,
      pCompletionTokens=getattr(vUsage, "output_tokens", 0) if vUsage else 0,
      pRawStopReason=vRawStopReason,
    )

  def fCountPromptTokens(self, pSystemPrompt, pMessages, pTools):
    """Return the exact prompt size, which lets a run stop before it spends."""
    dRequest = {
      "model": self.vModel,
      "messages": self.fBuildMessages(pMessages),
    }
    if pSystemPrompt:
      dRequest["system"] = pSystemPrompt
    if pTools:
      dRequest["tools"] = self.fBuildToolDefinitions(pTools)
    try:
      vCount = self.vClient.messages.count_tokens(**dRequest)
      return vCount.input_tokens
    except Exception:
      # Counting is an optimization, never a reason to fail a run.
      return None
