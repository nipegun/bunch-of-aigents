"""The chat/completions request itself, for the providers that serve one.

Most providers added after the first eight speak OpenAI's chat/completions
dialect, and `base.py` explains why each of them still gets its own adapter
file: the day one of them renames a field, the fix has to happen there and
nowhere else. What those files should not each carry is a private copy of the
same forty lines of `requests.post`, error handling and response parsing -
that is not a quirk, it is the dialect, and a bug fixed in one copy would
survive in the other sixteen.

So the dialect lives here and the quirks live in each adapter, declared as
class attributes this module reads:

    cDisplayName        what the provider calls itself, used in errors
    cChatCompletionsPath  the path appended to the base URL
    cMaxTokensField     `max_tokens` for most, `max_completion_tokens` for the
                        providers that follow OpenAI's newer spelling
    cToolChoiceMode     "auto", "any" or "omit" - see fBuildToolChoice
    cAssistantContentWhenEmpty  what to send instead of null content, for a
                        provider whose schema refuses null
    dExtraHeaders       headers a provider requires beyond Authorization

An adapter that needs to do something else entirely stops using this module
and writes its own fSendMessages, which is exactly what Anthropic, Google,
llama.cpp and Cohere do.
"""

import json
import re

import requests

from backend.providers import base

# Sent when a provider asks for one. OpenRouter reads them to attribute the
# request; the others ignore them.
cRefererHeader = "https://github.com/nipegun/bunch-of-aigents"
cTitleHeader = "Bunch of AIgents"


def fBuildToolChoice(pMode):
  """Return what to put in `tool_choice`, or None to leave the field out.

  Three answers, because providers disagree on what the field means:

    auto  the model decides whether to call a tool. What an agent needs: it
          has to be able to answer without calling anything, or a run never
          ends.
    any   the model must call a tool on every turn. Only for a provider that
          rejects "auto".
    omit  the field is not sent at all, for the providers that refuse the
          request when it is present.
  """
  vMode = str(pMode or "auto").lower()
  if vMode == "omit":
    return None
  if vMode == "any":
    return "any"
  return "auto"


def fNormalizeMessageContent(dMessage):
  """Return the text of one reply, whatever shape the provider put it in.

  A gateway that forwards several upstream providers - Vercel's, Hugging
  Face's - answers with `content` as a list of blocks rather than a string,
  with the model's reasoning as one of them. Reasoning is deliberately
  dropped: the runner replays every message it is given on the next turn, and
  reasoning is not meant to be sent back.
  """
  vContent = dMessage.get("content")
  if isinstance(vContent, str) or vContent is None:
    return dMessage

  lParts = []
  for vBlock in vContent or []:
    if isinstance(vBlock, str):
      lParts.append(vBlock)
      continue
    if not isinstance(vBlock, dict):
      continue
    vType = str(vBlock.get("type") or "")
    if vType in ("reasoning", "thinking", "redacted_reasoning"):
      continue
    vText = vBlock.get("text")
    if vText is None:
      vText = vBlock.get("content")
    if isinstance(vText, str):
      lParts.append(vText)

  dMessage["content"] = "".join(lParts)
  return dMessage


# A reasoning block written into the reply itself, rather than sent in a field
# of its own. Measured with MiniMax, whose answer to "say ok" began
# "<think> The user wants me to say ok...", but it belongs to the model rather
# than to the provider: the same model served through a gateway does the same
# thing, so it is handled here and not in one adapter.
#
# Only stripped when the reply STARTS with the tag. A model quoting the string
# in the middle of an answer about HTML is writing, not thinking.
cThinkingBlockPattern = re.compile(
  r"\A\s*<(think|thinking|reasoning)>.*?</\1>\s*", re.DOTALL | re.IGNORECASE)


def fStripThinkingBlock(pText):
  """Return a reply without the reasoning block some models write into it."""
  return cThinkingBlockPattern.sub("", str(pText or ""), count=1)


def fNormalizeEmptyAssistantContent(pMessages, pReplacement):
  """Replace a null `content` on an assistant message with something else.

  A model that answers with nothing but tool calls produces an assistant
  message whose content is null, which is what OpenAI's own API documents.
  Cloudflare Workers AI validates that field against a schema that does not
  allow null and refuses the whole request:

      Type mismatch of '/messages/2/content', 'string' not in 'null'

  so every agent on it died on its second step, the moment it had used a tool.
  Sending "" instead is accepted there and changes nothing for anyone else -
  but it is done only for the adapters that ask, because null is what the
  dialect actually specifies.
  """
  for dMessage in pMessages:
    if dMessage.get("role") == "assistant" and dMessage.get("content") is None:
      dMessage["content"] = pReplacement
  return pMessages


def fBuildPayload(pProvider, pSystemPrompt, pMessages, pTools, pMaxTokens):
  """Return the request body one adapter would send."""
  lMessages = base.fNeutralMessagesToOpenAiFormat(pSystemPrompt, pMessages)
  vEmptyContent = getattr(pProvider, "cAssistantContentWhenEmpty", None)
  if vEmptyContent is not None:
    lMessages = fNormalizeEmptyAssistantContent(lMessages, vEmptyContent)

  dPayload = {
    "model": pProvider.vModel,
    "messages": lMessages,
    getattr(pProvider, "cMaxTokensField", "max_tokens"): int(pMaxTokens),
    "stream": False,
  }
  if pTools:
    dPayload["tools"] = [base.fToolSchemaToOpenAiFormat(dTool) for dTool in pTools]
    vToolChoice = fBuildToolChoice(getattr(pProvider, "cToolChoiceMode", "auto"))
    if vToolChoice is not None:
      dPayload["tool_choice"] = vToolChoice
  return dPayload


def fSendChatCompletion(pProvider, pSystemPrompt, pMessages, pTools, pMaxTokens):
  """Send one chat/completions request and return a ProviderResponse."""
  vDisplayName = getattr(pProvider, "cDisplayName", pProvider.cProviderName)

  if not pProvider.vModel:
    raise base.ProviderError(
      "No model set for %s. Type the model name in this agent's LLM tab - the "
      "field accepts anything the provider serves." % (vDisplayName,)
    )

  vUrl = "%s%s" % (
    pProvider.vBaseUrl,
    getattr(pProvider, "cChatCompletionsPath", "/chat/completions"),
  )
  dHeaders = {
    "Authorization": "Bearer %s" % (pProvider.vApiKey,),
    "Content-Type": "application/json",
  }
  dHeaders.update(getattr(pProvider, "dExtraHeaders", {}) or {})

  try:
    vResponse = requests.post(
      vUrl,
      headers=dHeaders,
      json=fBuildPayload(pProvider, pSystemPrompt, pMessages, pTools, pMaxTokens),
      timeout=pProvider.vTimeoutSeconds,
    )
    if vResponse.status_code in (401, 403):
      raise base.ProviderError(
        "%s refused the key. Check it in Settings, API keys."
        % (vDisplayName,)
      )
    if vResponse.status_code == 402:
      raise base.ProviderError(
        "%s rejected the request for lack of balance. Top up the account or "
        "switch this agent to another provider." % (vDisplayName,)
      )
    if vResponse.status_code == 429:
      raise base.ProviderError(
        "%s is rate-limiting this account. The run can be tried again later."
        % (vDisplayName,)
      )
    vResponse.raise_for_status()
    dBody = vResponse.json()
  except requests.ConnectionError:
    raise base.ProviderError(
      "Cannot reach %s at %s." % (vDisplayName, pProvider.vBaseUrl))
  except requests.Timeout:
    raise base.ProviderError(
      "%s did not answer within %d seconds."
      % (vDisplayName, int(pProvider.vTimeoutSeconds))
    )
  except requests.RequestException as vError:
    raise base.ProviderError(
      "%s request failed: %s" % (vDisplayName, base.fDescribeHttpError(vError)))
  except ValueError as vError:
    raise base.ProviderError(
      "%s returned invalid JSON: %s" % (vDisplayName, vError))

  if dBody.get("error"):
    dError = dBody["error"]
    vMessage = dError.get("message") if isinstance(dError, dict) else dError
    raise base.ProviderError("%s error: %s" % (vDisplayName, vMessage))

  lChoices = dBody.get("choices") or []
  if not lChoices:
    raise base.ProviderError(
      "%s returned no choices. Model %r may not exist on this account."
      % (vDisplayName, pProvider.vModel)
    )

  dChoice = lChoices[0]
  dMessage = dChoice.get("message") or {}
  # Reasoning text is dropped for the same reason DeepSeek's is: it is not
  # meant to travel back on the next turn.
  dMessage.pop("reasoning_content", None)
  dMessage.pop("reasoning", None)
  dChoice["message"] = fNormalizeMessageContent(dMessage)

  vResponse = base.fParseOpenAiChoice(dChoice, dBody.get("usage"))
  vResponse.vText = fStripThinkingBlock(vResponse.vText)
  return vResponse


def fDescribePayloadForTests(pProvider, pTools):
  """Return the payload one adapter builds, for a test to look at.

  Kept here rather than assembled in the tests: what a provider sends is part
  of what this module promises, and a test that rebuilt it by hand would go on
  passing after this module changed.
  """
  return json.loads(json.dumps(
    fBuildPayload(pProvider, "system", [{"role": "user", "content": "hello"}],
                  pTools, 1024)
  ))
