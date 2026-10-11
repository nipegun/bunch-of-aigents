#!/usr/bin/env -S PYTHONDONTWRITEBYTECODE=1 python3

"""Receive X DMs from one configured account and return agent text and PNGs."""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.core import agent_routing, attachments, channels, db, exec_client
from backend.core import x_api, x_inbox, x_posts, x_texts


def fLogLine(pText, pConfig=None):
  agent_routing.fLogLine(channels.fRedactSecrets(pText, pConfig))


def fAudience(pConfig):
  return channels.fAudienceKey("x", pConfig)


def fReadListeningConfig():
  try:
    dConfig = channels.fReadChannelConfig("x")
  except channels.ChannelError:
    return None
  return dConfig if dConfig.get("listen") else None


def fExtractInput(pEvent, pConfig):
  """Accept only the chosen peer in this one-to-one conversation."""
  vSender = str(pEvent.get("sender_id") or "")
  sParticipants = {str(pConfig.get("account_id")), str(pConfig.get("recipient_id"))}
  sConversation = set(str(pEvent.get("dm_conversation_id") or "").split("-"))
  if (pEvent.get("event_type") != "MessageCreate" or vSender != str(pConfig.get("recipient_id"))
      or vSender == str(pConfig.get("account_id")) or sConversation != sParticipants
      or not str(pEvent.get("text") or "").strip()):
    return None
  vId = x_api.fId(pEvent.get("id"), "event ID")
  return x_inbox.fEventKey(fAudience(pConfig), vId), {
    "event_id": vId, "user": vSender, "text": str(pEvent["text"]), "created_at": x_api.fCreatedAt(pEvent)}


def fPoll(pConfig):
  """Read one page per interval; finish the snapshot before routing its input."""
  vAudience = fAudience(pConfig)
  dCursor = x_inbox.fReadCursor(vAudience)
  vGeneration = str(pConfig.get("poll_generation") or "")
  vInitialize = not dCursor or dCursor["generation"] != vGeneration
  lEvents, vNext = x_api.fReadEvents(pConfig, "" if vInitialize else dCursor["page_token"])
  if vInitialize:
    vLatest = str(max((int(dEvent["id"]) for dEvent in lEvents), default=0))
    x_inbox.fInitializePolling(vAudience, vLatest, vGeneration)
    fLogLine("X checkpoint initialized; earlier direct messages will not be replayed.")
    return True
  vFloor = int(dCursor["last_id"])
  vLatest = max(int(dCursor["scan_last_id"] or vFloor), vFloor)
  vComplete = not vNext
  lInputs = []
  for dEvent in sorted(lEvents, key=lambda pEvent: int(pEvent["id"])):
    vId = int(dEvent["id"])
    vLatest = max(vLatest, vId)
    if vId <= vFloor:
      vComplete = True
      continue
    if x_api.fCreatedAt(dEvent) < dCursor["first_at"]:
      continue
    vInput = fExtractInput(dEvent, pConfig)
    if vInput:
      lInputs.append(vInput)
  if vNext and vNext == dCursor["page_token"]:
    raise x_api.XRetryLater("X repeated its pagination token; the checkpoint was preserved.")
  x_inbox.fCommitPoll(vAudience, lInputs, str(vLatest), "" if vComplete else vNext)
  return vComplete


def fSay(pConfig, pText, pKey, pMediaId=""):
  vAudience = fAudience(pConfig)
  vState, vId = x_inbox.fReserveSend(vAudience, pKey)
  if vState == "sent":
    return vId
  if vState == "uncertain":
    raise x_api.XDeliveryUncertain("A previous X send has no confirmation. It will not be repeated automatically.")
  try:
    vId = x_api.fSendDm(pConfig, pText, pMediaId)
  except x_api.XDeliveryUncertain:
    raise
  except (x_api.XRetryLater, channels.ChannelRejected):
    x_inbox.fReleaseSend(vAudience, pKey)
    raise
  x_inbox.fConfirmSend(vAudience, pKey, vId)
  return vId


def fBuildAgentsMessage():
  lAgents = agent_routing.fListAgentNames()
  if not lAgents:
    return x_texts.fText("agentsNone")
  return "\n".join([x_texts.fText("agentsHeading"), ""] + [
    "- @%s — %s" % (vName or vId, vId) for vId, vName in lAgents])


def fHandleInput(pKey, pInput, pConfig):
  vAudience = fAudience(pConfig)
  if "_reply" in pInput:
    fSay(pConfig, pInput["_reply"], "input:" + pKey)
    return

  def fReply(pText, pAgentId=""):
    pInput["_reply"] = pText
    x_inbox.fRememberResolution(pKey, pInput, vAudience, pAgentId)
    fSay(pConfig, pText, "input:" + pKey)

  vText = pInput["text"].strip()
  vCommand = vText.split()[0].lower() if vText else ""
  # The answer to a post an agent asked for (x_posts). Only the configured
  # interlocutor reaches this point, so the code is answered by that person.
  if vCommand in ("!post", "!discard"):
    lWords = vText.split()
    vCode = lWords[1] if len(lWords) > 1 else ""
    if vCommand == "!post":
      fReply(x_posts.fApprove(pConfig, vCode))
    else:
      fReply(x_posts.fDiscard(pConfig, vCode))
    return
  if vCommand in ("!agents", "!start", "!help", "!status"):
    if vCommand in ("!agents", "!start"):
      vAnswer = fBuildAgentsMessage()
    elif vCommand == "!status":
      vAnswer = agent_routing.fBuildStatusReport(x_texts.fText, "boa-channel-x")
    else:
      vAnswer = x_texts.fText("helpText")
    fReply(vAnswer)
    return
  if "_agent_id" in pInput:
    vAgentId, vText = pInput["_agent_id"], pInput["_message"]
  else:
    vAgentId, vRest = agent_routing.fMatchNamedAgent(vText, agent_routing.lDiscordNamePrefixes)
    if vAgentId:
      vText = vRest
    else:
      vAgentId = x_inbox.fReadSelectedAgent(vAudience)
    if not any(vId == vAgentId for vId, vName in agent_routing.fListAgentNames()):
      fReply(x_texts.fText("noAgent"))
      return
    pInput.update({"_agent_id": vAgentId, "_message": vText})
    x_inbox.fRememberResolution(pKey, pInput, vAudience, vAgentId)
  if not vText:
    fReply(x_texts.fText("whatShouldItDo", name=agent_routing.fGetAgentName(vAgentId)), vAgentId)
    return
  try:
    dResult = exec_client.fSendChatMessage(vAgentId, vText, pSource="x", pTurnId=pKey[:16], pChannelEventId=pKey)
  except exec_client.ExecError as vError:
    vReason = str(vError)
    if "still answering" in vReason:
      fReply(x_texts.fText("busy", name=agent_routing.fGetAgentName(vAgentId)))
    elif "disabled" in vReason or "too long" in vReason or "reserved" in vReason:
      fReply(x_texts.fText("cannotStart", name=agent_routing.fGetAgentName(vAgentId), reason=vReason))
    else:
      raise x_api.XRetryLater(vReason)
    return
  x_inbox.fAddPending(dResult["turn_id"], vAgentId, vAudience)
  fLogLine("Agent %s started X turn %s." % (vAgentId, dResult["turn_id"]))


def fProcessIncoming(pConfig):
  vAudience = fAudience(pConfig)
  x_inbox.fPrune(vAudience)
  dCursor = x_inbox.fReadCursor(vAudience)
  if dCursor and dCursor["page_token"]:
    return
  for dIncoming in x_inbox.fListIncoming(vAudience):
    try:
      fHandleInput(dIncoming["event_key"], json.loads(dIncoming["payload"]), pConfig)
      x_inbox.fCompleteIncoming(dIncoming["event_key"])
    except channels.ChannelRejected as vError:
      fLogLine("X input could not be answered: %s" % vError, pConfig)
      x_inbox.fCompleteIncoming(dIncoming["event_key"])
    except Exception as vError:
      fLogLine("X input will be retried: %s" % vError, pConfig)
      x_inbox.fDelayIncoming(dIncoming["event_key"], getattr(vError, "vRetryAfter", 65))
      break


def fDeliverParts(pConfig, pPending, pAnswer):
  vTurn, vAgent = pPending["turn_id"], pPending["agent_id"]
  dDelivered = x_inbox.fListDeliveredParts(vTurn)
  vText = "%s:\n%s" % (agent_routing.fGetAgentName(vAgent), str(pAnswer.get("text") or ""))
  # DM limits count ordinary characters; keep each part below the wire limit.
  lParts = [vText[vStart:vStart + 9000] for vStart in range(0, len(vText), 9000)][:4]
  if len(vText) > 36000:
    lParts[-1] = lParts[-1].rstrip() + "…"
  for vIndex, vPart in enumerate(lParts):
    vKey = "text:" + str(vIndex)
    if vKey not in dDelivered:
      vId = fSay(pConfig, vPart, vTurn + ":" + vKey)
      x_inbox.fRememberDeliveredPart(vTurn, vKey, vId)
  for dImage in attachments.fListMessageAttachments(pAnswer):
    vKey = "image:" + dImage["id"]
    if vKey in dDelivered:
      continue
    try:
      vMedia = dDelivered.get("upload:" + vKey)
      if not vMedia:
        dFirst = exec_client.fReadChatAttachment(vAgent, dImage["id"])
        vBytes = b"".join(exec_client.fIterChatAttachment(vAgent, dImage["id"], dFirst))
        vMedia = x_api.fUploadImage(pConfig, vBytes, dFirst["attachment"]["name"])
        x_inbox.fRememberDeliveredPart(vTurn, "upload:" + vKey, vMedia)
      vCaption = str(dImage.get("caption") or dImage.get("name") or "image.png")[:1000]
      vId = fSay(pConfig, vCaption, vTurn + ":" + vKey, vMedia)
      x_inbox.fRememberDeliveredPart(vTurn, vKey, vId)
    except x_api.XDeliveryUncertain:
      raise
    except (exec_client.AttachmentUnavailable, channels.ChannelRejected) as vError:
      fLogLine("Cannot deliver X image: %s" % vError, pConfig)
      fSay(pConfig, x_texts.fText("imageFailed", name=str(dImage.get("name") or "image.png")[:128]),
        vTurn + ":failed:" + vKey)
      x_inbox.fRememberDeliveredPart(vTurn, vKey, "unavailable")


def fDeliverAnswers(pConfig):
  for dPending in x_inbox.fListPending():
    vTurn = dPending["turn_id"]
    if dPending["audience"] != fAudience(pConfig):
      x_inbox.fRemovePending(vTurn)
      continue
    if dPending["retry_at"] > time.time():
      continue
    vExpired = time.time() - dPending["asked_at"] > x_inbox.cExpirySeconds
    try:
      dAnswer = agent_routing.fFindClosedMessage(dPending["agent_id"], vTurn)
      if dAnswer is None and not vExpired:
        continue
      fDeliverParts(pConfig, dPending, dAnswer or {"text": x_texts.fText("neverFinished")})
      x_inbox.fRemovePending(vTurn)
    except channels.ChannelRejected as vError:
      fLogLine("X could not confirm turn %s; its answer remains in the web chat: %s" % (vTurn, vError), pConfig)
      x_inbox.fRemovePending(vTurn)
    except Exception as vError:
      fLogLine("X answer will be retried: %s" % vError, pConfig)
      if vExpired:
        x_inbox.fRemovePending(vTurn)
      else:
        x_inbox.fDelayPending(vTurn, getattr(vError, "vRetryAfter", 65))
      break


def fMain():
  vParser = argparse.ArgumentParser(description="Receive X direct messages through the user-context API.")
  vParser.add_argument("--once", action="store_true", help="Poll and process input and answers once.")
  dArguments = vParser.parse_args()
  db.fCreateAppSchema()
  vNextPoll, vAudience = 0, ""
  fLogLine("X listener started.")
  while True:
    dConfig = fReadListeningConfig()
    if dConfig:
      try:
        x_api.fCheckConfig(dConfig)
        vKey = fAudience(dConfig) + str(dConfig.get("poll_generation") or "")
        if vKey != vAudience:
          vNextPoll, vAudience = 0, vKey
        if time.monotonic() >= vNextPoll:
          vNextPoll = time.monotonic() + x_api.cPollSeconds
          fPoll(dConfig)
        fProcessIncoming(dConfig)
        fDeliverAnswers(dConfig)
      except Exception as vError:
        fLogLine("X listener will retry: %s" % vError, dConfig)
        vNextPoll = time.monotonic() + getattr(vError, "vRetryAfter", 65)
        if dArguments.once:
          return 1
    else:
      vAudience = ""
    if dArguments.once:
      return 0
    time.sleep(2)


if __name__ == "__main__":
  try:
    sys.exit(fMain())
  except KeyboardInterrupt:
    fLogLine("X listener stopping.")
