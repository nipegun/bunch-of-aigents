"""Google Gemini provider adapter.

Talks to the Generative Language REST API directly with `requests`, so that the
installation does not carry a third SDK for a provider used by one agent.

Gemini's shape differs from every other adapter here: the system prompt is a
separate `system_instruction` object, messages are "contents" with "parts",
the assistant role is called "model", and tool results go back as
`functionResponse` parts rather than as messages of their own.
"""

import json
import os

import requests

from backend.providers import base

cApiKeyEnvironmentVariable = "GOOGLE_API_KEY"

# The field Gemini 3 issues beside a function call and demands back when that
# call is replayed. https://ai.google.dev/gemini-api/docs/thought-signatures
cThoughtSignatureKey = "thoughtSignature"


# What Gemini's `function_declarations[].parameters` accepts.
#
# It is a SUBSET of JSON Schema, not JSON Schema, and it refuses what it does
# not know rather than ignoring it. Every tool in this project declares
# `"additionalProperties": false`, which is correct JSON Schema and which
# Gemini answers with:
#
#   400 Bad Request - Invalid JSON payload received. Unknown name
#   "additionalProperties" at 'tools[0].function_declarations[0].parameters':
#   Cannot find field.
#
# So EVERY tool call through Google failed, on every model, for as long as the
# adapter has passed the schema through untouched. Measured against a real key
# on gemini-3.6-flash and gemini-3.1-flash-lite: the same 400 with
# additionalProperties, and the tool called correctly without it.
#
# An allow list rather than a deny list, for the reason every allow list here
# is one: the next key somebody adds to a tool schema is refused by Gemini
# whether or not anybody remembered to add it to a list of things to strip.
sGoogleSchemaKeys = {
  "type", "format", "title", "description", "nullable", "enum",
  "items", "properties", "required", "example", "default", "anyOf",
  "minimum", "maximum", "minItems", "maxItems",
  "minLength", "maxLength", "minProperties", "maxProperties",
  "pattern", "propertyOrdering",
}


def fCleanSchemaForGoogle(pSchema):
  """Return a schema with everything Gemini does not accept taken out.

  Recursive: a tool whose argument is an object of its own carries a nested
  schema, and Gemini refuses the unknown key wherever it appears.
  """
  if isinstance(pSchema, list):
    return [fCleanSchemaForGoogle(vItem) for vItem in pSchema]
  if not isinstance(pSchema, dict):
    return pSchema

  dClean = {}
  for vKey, vValue in pSchema.items():
    if vKey not in sGoogleSchemaKeys:
      continue
    if vKey == "properties" and isinstance(vValue, dict):
      dClean[vKey] = {vName: fCleanSchemaForGoogle(vChild)
                      for vName, vChild in vValue.items()}
    elif vKey in ("items", "anyOf"):
      dClean[vKey] = fCleanSchemaForGoogle(vValue)
    else:
      dClean[vKey] = vValue
  return dClean


class GoogleProvider(base.BaseProvider):
  """Talks to the Google Gemini API."""

  cProviderName = "google"
  # A Flash-Lite: fast, cheapest in the catalogue, and enough for tool calls.
  # The newest Flash, gemini-3.7-flash, is deliberately not it - measured
  # against a real key it answers 503 "This model is currently experiencing
  # high demand", and a default that fails on the first run is worse than a
  # cheaper one. gemini-3.6-flash was three times the price of this on input
  # and was chosen when the rule was "a Flash" rather than "the cheapest".
  #
  # Verified against the real API on 2026-09-19 with `_/temp/probe-defaults.py`:
  # asked, called a tool, and answered that tool call. Re-run it after moving
  # a default; if one stops answering, move to the next cheapest and write the
  # provider's own error beside it, as kimi and together do.
  cDefaultModel = "gemini-3.1-flash-lite"
  cDefaultBaseUrl = "https://generativelanguage.googleapis.com/v1beta"

  def __init__(self, pModel="", pBaseUrl="", pApiKey="", pTimeoutSeconds=None):
    base.BaseProvider.__init__(self, pModel, pBaseUrl, pApiKey, pTimeoutSeconds)
    self.vApiKey = self.vApiKey or os.environ.get(cApiKeyEnvironmentVariable, "")
    if not self.vApiKey:
      raise base.ProviderError(
        "No Google API key. Set it for this agent in the web interface."
      )

  def fBuildToolDefinitions(self, pTools):
    """Convert neutral tool schemas to Gemini function declarations."""
    lDeclarations = []
    for dTool in pTools:
      lDeclarations.append({
        "name": base.fToolNameToWire(dTool["name"]),
        "description": dTool.get("description", ""),
        "parameters": fCleanSchemaForGoogle(
          dTool.get("input_schema") or {"type": "object", "properties": {}}),
      })
    return [{"functionDeclarations": lDeclarations}]

  def fBuildContents(self, pMessages):
    """Convert neutral messages to Gemini contents."""
    lContents = []
    for dMessage in pMessages:
      vRole = dMessage.get("role")

      if vRole == "tool":
        lContents.append({
          "role": "user",
          "parts": [{
            "functionResponse": {
              "name": base.fToolNameToWire(dMessage.get("name", "")),
              "response": {"result": str(dMessage.get("content", ""))},
            }
          }],
        })
        continue

      if vRole == "assistant" and dMessage.get("tool_calls"):
        lParts = []
        if dMessage.get("content"):
          lParts.append({"text": str(dMessage["content"])})
        for vCall in dMessage["tool_calls"]:
          dPart = {
            "functionCall": {"name": base.fToolNameToWire(vCall.vName),
                             "args": vCall.dArguments}
          }
          # Handed straight back the way it arrived. Gemini 3 refuses the
          # request outright without it - "Function call is missing a
          # thought_signature in functionCall parts" - which made every
          # Gemini agent fail on its second step, the moment it had used a
          # tool.
          vSignature = vCall.dProviderData.get(cThoughtSignatureKey)
          if vSignature:
            dPart[cThoughtSignatureKey] = vSignature
          lParts.append(dPart)
        lContents.append({"role": "model", "parts": lParts})
        continue

      lContents.append({
        "role": "model" if vRole == "assistant" else "user",
        "parts": [{"text": str(dMessage.get("content", ""))}],
      })

    return lContents

  def fSendMessages(self, pSystemPrompt, pMessages, pTools, pMaxTokens):
    """Send one generateContent request."""
    vUrl = "%s/models/%s:generateContent" % (self.vBaseUrl, self.vModel)
    dPayload = {
      "contents": self.fBuildContents(pMessages),
      "generationConfig": {"maxOutputTokens": int(pMaxTokens)},
    }
    if pSystemPrompt:
      dPayload["system_instruction"] = {"parts": [{"text": pSystemPrompt}]}
    if pTools:
      dPayload["tools"] = self.fBuildToolDefinitions(pTools)

    try:
      # In a header and not as `?key=...`: a query string is copied into
      # every error message requests builds, into the journal and into what
      # the user is shown, and a key that has been in a log file has to be
      # treated as disclosed. The API accepts both.
      vResponse = requests.post(
        vUrl,
        headers={"x-goog-api-key": self.vApiKey,
                 "Content-Type": "application/json"},
        json=dPayload,
        timeout=self.vTimeoutSeconds,
      )
      vResponse.raise_for_status()
      dBody = vResponse.json()
    except requests.RequestException as vError:
      raise base.ProviderError(
        "Google request failed: %s" % (base.fDescribeHttpError(vError),))
    except ValueError as vError:
      raise base.ProviderError("Google returned invalid JSON: %s" % (vError,))

    return self.fParseResponse(dBody)

  def fParseResponse(self, pBody):
    """Turn one generateContent response into a ProviderResponse."""
    lCandidates = pBody.get("candidates") or []
    if not lCandidates:
      raise base.ProviderError("Google returned no candidates")

    dCandidate = lCandidates[0]
    lTextParts = []
    lToolCalls = []
    vCallIndex = 0

    for dPart in (dCandidate.get("content") or {}).get("parts") or []:
      if "text" in dPart:
        lTextParts.append(dPart["text"])
      elif "functionCall" in dPart:
        dCall = dPart["functionCall"]
        # Gemini does not hand out call ids, but the runner needs one to match
        # a result back to its call, so the index becomes the id.
        vCallIndex += 1
        lToolCalls.append(base.ToolCall(
          "google-call-%d" % (vCallIndex,),
          base.fToolNameFromWire(dCall.get("name", "")),
          dCall.get("args") or {},
          # Kept on the call so that the next request can give it back.
          {cThoughtSignatureKey: dPart.get(cThoughtSignatureKey, "")},
        ))

    vFinishReason = dCandidate.get("finishReason") or ""
    if lToolCalls:
      vStopReason = base.cStopToolUse
    elif vFinishReason == "MAX_TOKENS":
      vStopReason = base.cStopMaxTokens
    elif vFinishReason in ("SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT"):
      vStopReason = base.cStopRefusal
    else:
      vStopReason = base.cStopEndTurn

    dUsage = pBody.get("usageMetadata") or {}
    return base.ProviderResponse(
      pText="\n".join(lTextParts),
      pToolCalls=lToolCalls,
      pStopReason=vStopReason,
      pPromptTokens=dUsage.get("promptTokenCount", 0),
      pCompletionTokens=dUsage.get("candidatesTokenCount", 0),
      pRawStopReason=vFinishReason,
    )
