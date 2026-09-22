"""Messaging channels.

One JSON file per channel in /opt/boa/config/channels/, owned by root:boa with
mode 0640. Agents cannot read those files: an agent that could read
telegram.json would have the bot token, and a token is not a message - it is
the ability to send anything, anywhere that bot can reach, forever.

So agents never send anything themselves. They call `channel.write`, which asks
the agent API, which runs as `boa`, reads the credentials and sends. The agent
learns whether the message went out and nothing else.
"""

import json
import os
import re
import sys
import time

import requests

from backend.core import discord_markdown
from backend.core import attachments
from backend.core import paths
from backend.core import telegram_html

# Supported channels. Each needs its own JSON file to be usable.
cChannelTelegram = "telegram"
cChannelDiscord = "discord"
cChannelMattermost = "mattermost"
cChannelX = "x"

lChannels = [cChannelTelegram, cChannelDiscord, cChannelMattermost, cChannelX]

# Seconds to wait for a channel before giving up.
cSendTimeoutSeconds = 30

# Longest message accepted. Telegram cuts at 4096 characters, which is the
# tightest of the four, so that is the limit everywhere for predictability.
cMaxMessageLength = 4096

# How long Telegram holds an empty getUpdates open before answering with
# nothing. Long enough that a quiet installation makes a couple of requests a
# minute, short enough that a restart is never waiting on it for long.
cLongPollSeconds = 25


class ChannelError(RuntimeError):
  """Raised when a channel is unconfigured, disabled or fails to send."""


class ChannelRejected(ChannelError):
  """Raised when the channel said no to THIS message and will say no again.

  A bot blocked, a chat gone, a token revoked, markup refused even as plain
  text: Telegram answers a 4xx, and a retry tomorrow gets the same answer.
  Kept apart from ChannelError so that a caller keeping a message to try
  again later can tell "not now" from "never".
  """


# ------------------------------------------------------- keeping secrets ----
#
# Every channel here authenticates with something that IS the account: a bot
# token, a webhook URL, a bearer token. Three of the four carry it in the URL,
# and that is the part nobody writes on purpose and everybody prints by
# accident - because `str(requests.RequestException)` quotes the URL it was
# given:
#
#   HTTPSConnectionPool(host='api.telegram.org', port=443): Max retries
#   exceeded with url: /bot1234567:REAL-TOKEN-HERE/sendMessage
#
# That string used to travel two ways: into the ChannelError that channel.write
# hands back to the AGENT, which is the one party this whole design exists to
# keep the credential from, and into the listener's log. So every error and
# every log line built from one of these calls goes through fRedactSecrets
# first. One function, because the second copy is the one that does not get
# the fix.

# Configuration fields whose value is a credential.
lSecretConfigFields = [
  "bot_token", "webhook_url", "bearer_token",
  "api_key", "api_secret", "access_token", "access_secret", "password",
]

# Configuration fields that are not credentials and that the settings page
# fills its form with, so that a channel shows the chat or channel it is
# pointed at instead of an empty box. A list of what may be shown rather than
# "everything that is not secret": a field added later is invisible until
# somebody decides it should be, which is the right way round.
lPublicConfigFields = ["chat_id", "channel_id", "channel", "username"]

cRedaction = "[redacted]"

# `/bot<token>` inside a Telegram API URL. Matched by shape as well as by
# value: a connection error is built inside urllib3, out of the path it was
# handed, and there is no guarantee the caller still has the config in hand.
cTelegramTokenInUrlPattern = re.compile(r"/bot[^/\s]+", re.IGNORECASE)

# `/api/webhooks/<id>/<token>` inside a Discord webhook URL, matched by shape
# for the same reason: the error is built inside urllib3 out of the URL it was
# handed, and whoever writes the log line may not have the config at all.
cDiscordWebhookInUrlPattern = re.compile(
  r"(/api/webhooks/\d+/)[^/\s?]+", re.IGNORECASE)


def fRedactSecrets(pText, pConfig=None):
  """Return one line of text with every credential in it replaced.

  Longest value first, so that a short secret which happens to be a substring
  of a longer one cannot chop the longer one in half and leave the rest of it
  readable.

  Never raises: this runs while something has already gone wrong, and a
  sanitiser that fails is worse than the error it was cleaning.
  """
  vText = str(pText or "")
  try:
    lSecrets = []
    for vField in lSecretConfigFields:
      vValue = str((pConfig or {}).get(vField) or "").strip()
      if len(vValue) >= 8:
        lSecrets.append(vValue)
    for vSecret in sorted(lSecrets, key=len, reverse=True):
      vText = vText.replace(vSecret, cRedaction)
    vText = cTelegramTokenInUrlPattern.sub("/bot" + cRedaction, vText)
    return cDiscordWebhookInUrlPattern.sub(r"\1" + cRedaction, vText)
  except Exception:
    return "an error whose text could not be checked for credentials"


def fGetChannelConfigPath(pChannelName):
  """Return the configuration file path of one channel."""
  vChannel = str(pChannelName or "").strip().lower()
  if vChannel not in lChannels:
    raise ChannelError(
      "Unknown channel %r. Supported: %s" % (pChannelName, ", ".join(lChannels))
    )
  return os.path.join(paths.fGetChannelsDir(), "%s.json" % (vChannel,))


def fReadChannelConfig(pChannelName):
  """Read one channel's configuration.

  Runs as the `boa` user inside the agent API or the web application. An agent
  process calling this would simply get a permission error, which is the point.
  """
  vPath = fGetChannelConfigPath(pChannelName)
  try:
    with open(vPath, "r", encoding="utf-8") as vFile:
      dConfig = json.load(vFile)
  except FileNotFoundError:
    raise ChannelError(
      "Channel %r is not configured. Set it up in the web interface first."
      % (pChannelName,)
    )
  except PermissionError:
    raise ChannelError(
      "Not allowed to read the configuration of channel %r." % (pChannelName,)
    )
  except (OSError, ValueError) as vError:
    raise ChannelError("Cannot read %s: %s" % (vPath, vError))

  if not dConfig.get("enabled", True):
    raise ChannelError("Channel %r is disabled." % (pChannelName,))
  return dConfig


def fReadConfigForEditing(pChannelName):
  """Return a channel's configuration as it is on disk, or {} if there is none.

  Unlike fReadChannelConfig this does not refuse a disabled channel and does
  not raise for a missing one: it exists so that saving a change can merge into
  what is already there instead of replacing the file. Writing the whole file
  from a form whose secret fields are deliberately empty is how a bot token
  gets deleted by somebody correcting a chat id.
  """
  vPath = fGetChannelConfigPath(pChannelName)
  try:
    with open(vPath, "r", encoding="utf-8") as vFile:
      dConfig = json.load(vFile)
  except (OSError, ValueError):
    return {}
  return dConfig if isinstance(dConfig, dict) else {}


def fReadPublicValues(pdConfig):
  """Return the fields of one channel that may travel back to the browser.

  Never a credential: the form leaves those empty on purpose, and an empty
  secret field means "leave it as it is". Everything else is shown, because a
  channel pointed at the wrong chat looks exactly like a channel that is not
  working, and an empty box is no help in telling them apart.
  """
  dValues = {}
  for vField in lPublicConfigFields:
    vValue = (pdConfig or {}).get(vField)
    if vValue not in (None, ""):
      dValues[vField] = str(vValue)
  return dValues


def fListConfiguredChannels():
  """Return every channel's name and state alphabetically, without secrets."""
  lSummaries = []
  for vChannel in sorted(lChannels):
    dSummary = {"name": vChannel, "configured": False, "enabled": False}
    try:
      dConfig = fReadChannelConfig(vChannel)
      dSummary["configured"] = True
      dSummary["enabled"] = True
      dSummary["target"] = (dConfig.get("chat_id")
                            or dConfig.get("channel_id")
                            or dConfig.get("channel") or "")
      # Whether messages also come IN through this channel. Telegram and
      # Discord can; Mattermost and X cannot, and it is off on all four until
      # somebody says otherwise.
      dSummary["listen"] = bool(dConfig.get("listen", False))
      dSummary["values"] = fReadPublicValues(dConfig)
    except ChannelError:
      vPath = fGetChannelConfigPath(vChannel)
      dSummary["configured"] = os.path.exists(vPath)
      dStored = fReadConfigForEditing(vChannel)
      dSummary["listen"] = bool(dStored.get("listen", False))
      # A disabled channel still has a chat id, and the form that would
      # re-enable it is the one that needs to show it.
      dSummary["values"] = fReadPublicValues(dStored)
    lSummaries.append(dSummary)
  return lSummaries


def fSendToTelegram(pConfig, pMarkdown, pReplyToMessageId=None,
                    pReplyMarkup=None):
  """Send one message through the Telegram Bot API.

  **It takes markdown and renders it here.** Handing it HTML that has already
  been rendered produces a message showing `<b>` and `</b>` as text, because
  the second pass escapes what the first one wrote. The parameter is named
  after what it wants for that reason.

  The id Telegram gives the message is returned, because it is what makes a
  reply routable: somebody answering this message in Telegram is answering the
  agent that sent it, and the id is the only thing connecting the two.
  """
  vToken = pConfig.get("bot_token") or ""
  vChatId = pConfig.get("chat_id") or ""
  if not vToken or not vChatId:
    raise ChannelError("telegram.json needs both bot_token and chat_id.")

  dPayload = {"chat_id": vChatId, "disable_web_page_preview": True}
  if pReplyMarkup:
    # A keyboard travels with an ordinary message: there is no call that just
    # sets one. Sending it with everything is what keeps it in place and up to
    # date without the bot having to say anything on its own.
    dPayload["reply_markup"] = pReplyMarkup
  if pReplyToMessageId:
    dPayload["reply_to_message_id"] = int(pReplyToMessageId)
    # The message being answered may have been deleted from the chat by then.
    # Sending it as an ordinary message beats not sending it at all.
    dPayload["allow_sending_without_reply"] = True

  # What a model writes is markdown, and markdown shown raw is asterisks and
  # backticks in the middle of a sentence. Telegram renders a small HTML
  # subset, so that is what it gets.
  vUrl = "https://api.telegram.org/bot%s/sendMessage" % (vToken,)
  dPayload["text"] = telegram_html.fRenderWithinLimit(pMarkdown)
  dPayload["parse_mode"] = "HTML"
  vResponse = requests.post(vUrl, json=dPayload, timeout=cSendTimeoutSeconds)

  # Telegram answers 400 to markup it will not parse, and a 400 here means the
  # message does not arrive at all. Whatever the renderer got wrong, the words
  # are worth more than the formatting, so the plain text goes out instead -
  # and the log says so, because a formatting bug that silently degrades for
  # ever is a formatting bug nobody fixes.
  if vResponse.status_code == 400:
    sys.stderr.write(
      "[channels] Telegram refused the formatted message, sending it as "
      "plain text: %s\n"
      % (fRedactSecrets((vResponse.text or "")[:200], pConfig),)
    )
    dPayload["text"] = pMarkdown
    dPayload.pop("parse_mode", None)
    vResponse = requests.post(vUrl, json=dPayload, timeout=cSendTimeoutSeconds)

  if vResponse.status_code != 200:
    # The token is in the URL, so the URL must never reach the error message.
    # The body is the server's own words and is redacted too, rather than
    # trusted not to quote back what it was sent.
    vMessage = ("Telegram refused the message (HTTP %d): %s"
                % (vResponse.status_code,
                   fRedactSecrets((vResponse.text or "")[:200], pConfig)))
    # A 4xx is Telegram saying no to this message, and it will say no to it
    # again: the bot blocked, the chat gone, the token revoked. Everything
    # else is Telegram not answering, which is worth another try. 429 is the
    # one 4xx that means "later" rather than "never", so it goes with those.
    if 400 <= vResponse.status_code < 500 and vResponse.status_code != 429:
      raise ChannelRejected(vMessage)
    raise ChannelError(vMessage)

  vMessageId = None
  try:
    vMessageId = vResponse.json().get("result", {}).get("message_id")
  except ValueError:
    # It answered 200 with something that is not JSON. The message went out,
    # which is what the caller asked for; only the reply routing is lost.
    pass
  return {"channel": cChannelTelegram, "sent": True, "message_id": vMessageId}


def fSendImageToTelegram(pConfig, pPng, pName, pCaption="", pReplyToMessageId=None):
  """Upload a PNG; tall/large captures travel as original documents."""
  vToken = pConfig.get("bot_token") or ""
  vChatId = pConfig.get("chat_id") or ""
  if not vToken or not vChatId:
    raise ChannelRejected("telegram.json needs bot_token and chat_id.")
  vWidth, vHeight = attachments.fReadPngDimensions(pPng)
  if len(pPng) > attachments.cMaxImageBytes:
    raise ChannelRejected("The image is too large to send.")
  vAsPhoto = (len(pPng) <= 10 * 1024 * 1024
              and vWidth + vHeight <= 10000
              and max(vWidth, vHeight) <= 20 * min(vWidth, vHeight))
  lMethods = ["sendPhoto", "sendDocument"] if vAsPhoto else ["sendDocument"]
  dPayload = {"chat_id": vChatId, "caption": str(pCaption or "")[:1024]}
  if pReplyToMessageId:
    dPayload["reply_parameters"] = json.dumps({
      "message_id": int(pReplyToMessageId), "allow_sending_without_reply": True,
    })
  for vMethod in lMethods:
    vField = "photo" if vMethod == "sendPhoto" else "document"
    try:
      vResponse = requests.post(
        "https://api.telegram.org/bot%s/%s" % (vToken, vMethod),
        data=dPayload, files={vField: (pName, pPng, "image/png")}, timeout=120)
    except requests.RequestException as vError:
      raise ChannelError(fRedactSecrets(vError, pConfig))
    if vResponse.status_code == 200:
      try:
        dResponse = vResponse.json()
        if not isinstance(dResponse, dict) or not dResponse.get("ok"):
          raise ValueError("Telegram did not confirm the upload")
      except (ValueError, TypeError) as vError:
        raise ChannelError("Invalid image upload response: %s" % (vError,))
      return {"channel": cChannelTelegram, "sent": True,
              "message_id": (dResponse.get("result") or {}).get("message_id")}
    if vMethod == "sendPhoto" and vResponse.status_code == 400:
      continue
    vError = "Telegram refused the image (HTTP %d): %s" % (
      vResponse.status_code, fRedactSecrets((vResponse.text or "")[:200], pConfig))
    if 400 <= vResponse.status_code < 500 and vResponse.status_code != 429:
      raise ChannelRejected(vError)
    raise ChannelError(vError)


def fAnswerTelegramCallback(pConfig, pCallbackId):
  """Tell Telegram a button press has been dealt with.

  Until this is called the button keeps a spinner on it and the app eventually
  reports the bot as unresponsive, whatever else was done about the press.
  """
  vToken = pConfig.get("bot_token") or ""
  if not vToken or not pCallbackId:
    return False
  vResponse = requests.post(
    "https://api.telegram.org/bot%s/answerCallbackQuery" % (vToken,),
    json={"callback_query_id": pCallbackId},
    timeout=cSendTimeoutSeconds,
  )
  return vResponse.status_code == 200


# The scopes a bot's command list can be written to that ANY Telegram user
# resolves. Never written to; cleared, every time the list is refreshed.
ldPublicCommandScopes = [{"type": "default"}, {"type": "all_private_chats"}]


def fCallTelegram(pToken, pMethod, pdPayload):
  """One call to the bot API. Returns the response, raising on anything but 200.

  Both exits are redacted: the token is in the URL this builds, so a network
  failure quotes it back and an error message built from that failure would
  carry the credential wherever the caller sends it.
  """
  dSecrets = {"bot_token": pToken}
  try:
    vResponse = requests.post(
      "https://api.telegram.org/bot%s/%s" % (pToken, pMethod),
      json=pdPayload,
      timeout=cSendTimeoutSeconds,
    )
  except requests.RequestException as vError:
    raise ChannelError(
      "Cannot reach Telegram for %s: %s"
      % (pMethod, fRedactSecrets(vError, dSecrets))
    )
  if vResponse.status_code != 200:
    raise ChannelError(
      "Telegram refused %s (HTTP %d): %s"
      % (pMethod, vResponse.status_code,
         fRedactSecrets((vResponse.text or "")[:200], dSecrets))
    )
  return vResponse


def fSetTelegramCommands(pConfig, pldCommands):
  """Tell Telegram which commands this bot has, and tell nobody else.

  This is what makes typing `/` in the chat show a list to pick from, and
  picking one put it in the message box. It is the only autocompletion Telegram
  offers a bot: `@` is reserved for its own usernames, and nothing a bot says
  can add to that list.

  Each entry is {"command": "os_watcher", "description": "..."}. Telegram
  accepts 1 to 32 characters of lowercase letters, digits and underscores, and
  refuses the whole call over one bad entry, so the caller cleans the names.

  Written to ONE scope: the configured chat. A bot's username is public, so
  anything registered against `default` or `all_private_chats` is a menu shown
  to every stranger who opens the bot - "Server status" among it, which says
  there is a machine behind this worth poking at. They could never run any of
  it, because the listener drops what does not come from the configured chat,
  but a sign on a locked door is still a sign.

  Those two scopes are cleared rather than left alone: a list written to them
  by an older version of this code lives on Telegram's side, and stops being
  shown only when something deletes it. Clearing them also settles the
  precedence - Telegram resolves a chat's list from the most specific scope to
  the least, so with the public ones empty the configured chat still sees its
  own, and everybody else sees nothing.
  """
  vToken = pConfig.get("bot_token") or ""
  if not vToken:
    raise ChannelError("telegram.json needs a bot_token.")
  vChatId = pConfig.get("chat_id") or ""

  for dScope in ldPublicCommandScopes:
    fCallTelegram(vToken, "deleteMyCommands", {"scope": dScope})

  # No chat configured means nobody may talk to this bot at all, so there is
  # no list to write anywhere.
  if not vChatId:
    return True

  # Re-writing the chat's own scope is also what pushes the app to refresh a
  # list it has cached.
  fCallTelegram(vToken, "setMyCommands", {
    "commands": pldCommands,
    "scope": {"type": "chat", "chat_id": vChatId},
  })
  return True


def fHideTelegramPublicProfile(pConfig):
  """Empty what Telegram shows a stranger who opens this bot.

  Two texts, both public and both shown before anybody has written anything:
  the description, which fills the empty chat under "What can this bot do?",
  and the short description, on the bot's profile. A bot set up to run someone
  else's servers has no reason to introduce itself to whoever finds its
  username.

  What cannot be removed is the Start button: Telegram draws it in every empty
  chat with a bot, and there is no API for it. Pressing it sends `/start`,
  which the listener drops like anything else from another chat - so the button
  is there and nothing is behind it.
  """
  vToken = pConfig.get("bot_token") or ""
  if not vToken:
    raise ChannelError("telegram.json needs a bot_token.")

  fCallTelegram(vToken, "setMyDescription", {"description": ""})
  fCallTelegram(vToken, "setMyShortDescription", {"short_description": ""})
  return True


def fReadTelegramUpdates(pConfig, pOffset=0, pTimeoutSeconds=None):
  """Return the messages waiting for the bot, long-polling for them.

  `getUpdates` holds the connection open until something arrives or the timeout
  runs out, so this is one request every `pTimeoutSeconds` on a quiet day
  rather than one every second. It also means the bot needs no inbound port:
  the connection is made from here, which is what lets this run on a LAN with
  nothing forwarded to it. A webhook would need the opposite.

  `pOffset` is the id of the first update wanted. Asking for it is also what
  tells Telegram that everything before it has been dealt with, so the same
  message is never handed over twice.
  """
  vToken = pConfig.get("bot_token") or ""
  if not vToken:
    raise ChannelError("telegram.json needs a bot_token.")

  vTimeout = (cLongPollSeconds if pTimeoutSeconds is None
              else max(0, int(pTimeoutSeconds)))
  # Button presses as well as messages: a tap on an inline button arrives as a
  # callback_query, and leaving it off this list means Telegram never sends it.
  dParameters = {"timeout": vTimeout,
                 "allowed_updates": ["message", "callback_query"]}
  if pOffset:
    dParameters["offset"] = int(pOffset)

  try:
    vResponse = requests.get(
      "https://api.telegram.org/bot%s/getUpdates" % (vToken,),
      params=dParameters,
      # Longer than the long poll itself, or the client gives up exactly when
      # Telegram is about to answer.
      timeout=vTimeout + cSendTimeoutSeconds,
    )
  except requests.RequestException as vError:
    # The listener calls this in a loop and logs whatever comes out of it. An
    # unwrapped requests error carries the URL, and the URL carries the token,
    # so a server that is merely unreachable used to write the bot's
    # credential into the journal once every retry.
    raise ChannelError(
      "Cannot reach Telegram: %s" % (fRedactSecrets(vError, pConfig),)
    )
  if vResponse.status_code != 200:
    raise ChannelError(
      "Telegram refused to hand over the updates (HTTP %d): %s"
      % (vResponse.status_code,
         fRedactSecrets((vResponse.text or "")[:200], pConfig))
    )
  try:
    dBody = vResponse.json()
  except ValueError:
    raise ChannelError("Telegram answered with something that is not JSON.")
  if not dBody.get("ok"):
    raise ChannelError("Telegram answered not ok: %s"
                       % (str(dBody.get("description"))[:200],))
  return dBody.get("result") or []


# ------------------------------------------------------------------ Discord ----
#
# Two ways in, and the configuration decides which:
#
#   bot_token + channel_id : the bot API. Sends, reads and replies, which is
#                            what `boa-discord` needs to exist at all.
#   webhook_url            : one direction only. Kept because an installation
#                            set up before there was a listener still works,
#                            and because a webhook is two clicks where a bot
#                            is a page of them.
#
# A bot token travels in a header rather than in the URL, so a connection
# error does not quote it back the way Telegram's does. The webhook URL is the
# other way round: it IS the credential and it is all URL.

cDiscordApiBase = "https://discord.com/api/v10"

# What a message this application sends is allowed to mention: nothing. An
# agent writing `@everyone` into an answer would otherwise notify an entire
# server, and the agent is the one party whose words are not the user's own.
# `replied_user` stays on, because an answer to a question should reach the
# person who asked it.
dDiscordAllowedMentions = {"parse": [], "replied_user": True}

# How many messages to ask for in one poll. Discord returns the newest first
# and caps this at 100; fifty is more than a quiet channel produces between
# two passes and small enough that a flood does not arrive in one lump.
cDiscordMessagesPerPoll = 50

# The longest a 429 may ask this to wait before it is treated as a failure
# rather than slept through. Discord answers a rate limit with `retry_after`
# in seconds, and it is normally a fraction of one.
cDiscordMaxRetryAfterSeconds = 10


def fGetDiscordMode(pConfig):
  """Return which way this configuration can reach Discord: "bot" or "hook"."""
  if (pConfig or {}).get("bot_token") and (pConfig or {}).get("channel_id"):
    return "bot"
  if (pConfig or {}).get("webhook_url"):
    return "hook"
  return ""


def fCallDiscord(pConfig, pMethod, pPath, pdPayload=None, pdParameters=None):
  """One call to the bot API, with the rate limit dealt with here.

  Raises ChannelRejected for a 4xx that will not change - a token revoked, a
  channel gone, the bot removed from the server - and ChannelError for
  everything else, which is worth another try. 429 is the one 4xx that means
  "later": slept through once when Discord says the wait is short, because
  that is what Discord's own clients do and the alternative is dropping a
  message over a fifth of a second.
  """
  vToken = (pConfig or {}).get("bot_token") or ""
  if not vToken:
    raise ChannelError("discord.json needs a bot_token.")

  # The base is configurable so that this can be pointed at a proxy, and so
  # that the round trip - poll, route, run, answer - can be exercised against
  # a server that speaks like Discord. A channel nobody can test end to end is
  # a channel whose first real message is the test.
  vBase = str((pConfig or {}).get("api_base") or cDiscordApiBase).rstrip("/")
  vUrl = "%s%s" % (vBase, pPath)
  dHeaders = {
    "Authorization": "Bot %s" % (vToken,),
    "Content-Type": "application/json",
    # Discord asks every library to identify itself, and answers a 403 with
    # "cloudflare" in it to some default clients.
    "User-Agent": "DiscordBot (https://github.com/nipegun/bunch-of-aigents, 1.0)",
  }

  for vAttempt in (1, 2):
    try:
      vResponse = requests.request(
        pMethod, vUrl, headers=dHeaders, json=pdPayload, params=pdParameters,
        timeout=cSendTimeoutSeconds,
      )
    except requests.RequestException as vError:
      raise ChannelError(
        "Cannot reach Discord: %s" % (fRedactSecrets(vError, pConfig),)
      )

    if vResponse.status_code == 429 and vAttempt == 1:
      vWait = 0
      try:
        vWait = float((vResponse.json() or {}).get("retry_after") or 0)
      except ValueError:
        vWait = 0
      if 0 < vWait <= cDiscordMaxRetryAfterSeconds:
        time.sleep(vWait)
        continue

    if vResponse.status_code in (200, 201, 204):
      return vResponse

    vMessage = ("Discord refused %s (HTTP %d): %s"
                % (pPath, vResponse.status_code,
                   fRedactSecrets((vResponse.text or "")[:200], pConfig)))
    if 400 <= vResponse.status_code < 500 and vResponse.status_code != 429:
      raise ChannelRejected(vMessage)
    raise ChannelError(vMessage)

  raise ChannelError("Discord is rate limiting this bot; try again later.")


def fSendThroughDiscordWebhook(pConfig, pMessage):
  """Send one message through a Discord webhook, which cannot do anything else."""
  vWebhookUrl = pConfig.get("webhook_url") or ""
  vResponse = requests.post(
    vWebhookUrl,
    json={"content": pMessage, "allowed_mentions": dDiscordAllowedMentions},
    timeout=cSendTimeoutSeconds,
  )
  # Discord answers 204 with no body on success.
  if vResponse.status_code not in (200, 204):
    vText = ("Discord refused the message (HTTP %d): %s"
             % (vResponse.status_code,
                fRedactSecrets((vResponse.text or "")[:200], pConfig)))
    if 400 <= vResponse.status_code < 500 and vResponse.status_code != 429:
      raise ChannelRejected(vText)
    raise ChannelError(vText)
  return True


def fSendToDiscord(pConfig, pMarkdown, pReplyToMessageId=None):
  """Send one message to Discord, in as many parts as it takes.

  **It takes markdown and Discord renders it**, which is the opposite of the
  Telegram sender: there the markup has to be translated, here it is already
  what the reader sees. What does have to change is the length. Discord
  answers 400 to a `content` over 2000 characters, so an answer longer than
  that did not arrive shortened - it did not arrive. `discord_markdown` cuts
  it between lines and keeps fenced blocks whole.

  The ids of every part are returned, not just the last one: a person replies
  to whichever part is on their screen, and all of them have to lead back to
  the agent that wrote it.
  """
  vMode = fGetDiscordMode(pConfig)
  if not vMode:
    raise ChannelError(
      "discord.json needs either bot_token and channel_id, or a webhook_url."
    )

  lParts = discord_markdown.fRenderToMessages(pMarkdown)
  if not lParts:
    raise ChannelError("There is nothing to send: the message is empty.")

  if vMode == "hook":
    for vPart in lParts:
      fSendThroughDiscordWebhook(pConfig, vPart)
    # A webhook answers 204 with no body, so there is no id to reply to and
    # nothing to route a later answer with.
    return {"channel": cChannelDiscord, "sent": True, "message_id": None,
            "message_ids": []}

  lMessageIds = []
  vChannelId = str(pConfig.get("channel_id") or "").strip()
  for vIndex, vPart in enumerate(lParts):
    dPayload = {"content": vPart,
                "allowed_mentions": dDiscordAllowedMentions}
    # Only the first part answers the question: the rest are the same answer
    # continuing, and a quoted question above every one of them is noise.
    if pReplyToMessageId and vIndex == 0:
      dPayload["message_reference"] = {
        "message_id": str(pReplyToMessageId),
        # The message being answered may have been deleted by now. Sending it
        # as an ordinary message beats not sending it at all.
        "fail_if_not_exists": False,
      }
    vResponse = fCallDiscord(
      pConfig, "POST", "/channels/%s/messages" % (vChannelId,), dPayload)
    try:
      vMessageId = (vResponse.json() or {}).get("id")
    except ValueError:
      # It answered 200 with something that is not JSON. The message went out,
      # which is what the caller asked for; only the reply routing is lost.
      vMessageId = None
    if vMessageId:
      lMessageIds.append(str(vMessageId))

  return {"channel": cChannelDiscord, "sent": True,
          "message_id": lMessageIds[-1] if lMessageIds else None,
          "message_ids": lMessageIds}


def fReadDiscordMessages(pConfig, pAfterId="", pLimit=cDiscordMessagesPerPoll):
  """Return the messages of the configured channel, oldest first.

  Polled rather than streamed. The Gateway is a WebSocket that would need
  heartbeats, a resume protocol and the Message Content Intent switched on in
  the developer portal - and without that last one every message arrives with
  an empty `content` and nothing says why. This is one outward request every
  few seconds, it needs no inbound port any more than Telegram's long poll
  does, and the content is simply there.

  `pAfterId` is the last message already dealt with. Discord hands back
  everything newer than it, **newest first**, so the list is reversed here:
  answering them in the order they were sent is the whole point of a
  conversation.
  """
  vChannelId = str((pConfig or {}).get("channel_id") or "").strip()
  if not vChannelId:
    raise ChannelError("discord.json needs a channel_id to listen.")

  dParameters = {"limit": max(1, min(100, int(pLimit)))}
  if pAfterId:
    dParameters["after"] = str(pAfterId)

  vResponse = fCallDiscord(
    pConfig, "GET", "/channels/%s/messages" % (vChannelId,),
    None, dParameters)
  try:
    lMessages = vResponse.json()
  except ValueError:
    raise ChannelError("Discord answered with something that is not JSON.")
  if not isinstance(lMessages, list):
    raise ChannelError("Discord answered with something that is not a list.")
  return list(reversed(lMessages))


def fReadDiscordBotUser(pConfig):
  """Return the bot's own account, to say which one is listening.

  Written to the log once on every start, the way the Telegram listener writes
  the chat it is registered for: when nothing arrives, the first question is
  whether this is even the bot that was invited to the server.
  """
  vResponse = fCallDiscord(pConfig, "GET", "/users/@me")
  try:
    dUser = vResponse.json() or {}
  except ValueError:
    return {}
  return {"id": str(dUser.get("id") or ""),
          "username": str(dUser.get("username") or "")}


def fSendToMattermost(pConfig, pMessage):
  """Send one message through a Mattermost incoming webhook."""
  vWebhookUrl = pConfig.get("webhook_url") or ""
  if not vWebhookUrl:
    raise ChannelError("mattermost.json needs a webhook_url.")

  dPayload = {"text": pMessage}
  if pConfig.get("channel"):
    dPayload["channel"] = pConfig["channel"]
  if pConfig.get("username"):
    dPayload["username"] = pConfig["username"]

  vResponse = requests.post(
    vWebhookUrl, json=dPayload, timeout=cSendTimeoutSeconds
  )
  if vResponse.status_code != 200:
    raise ChannelError(
      "Mattermost refused the message (HTTP %d): %s"
      % (vResponse.status_code,
         fRedactSecrets((vResponse.text or "")[:200], pConfig))
    )
  return {"channel": cChannelMattermost, "sent": True}


def fSendToX(pConfig, pMessage):
  """Post one message to X.

  X is the only channel here that publishes to an audience rather than to a
  room the user chose, so the adapter refuses anything over its length limit
  instead of silently truncating a public post.
  """
  vBearerToken = pConfig.get("bearer_token") or ""
  if not vBearerToken:
    raise ChannelError("x.json needs a bearer_token.")

  cMaxPostLength = 280
  if len(pMessage) > cMaxPostLength:
    raise ChannelError(
      "The message is %d characters and X accepts %d. Shorten it rather than "
      "posting half of it." % (len(pMessage), cMaxPostLength)
    )

  vResponse = requests.post(
    "https://api.x.com/2/tweets",
    headers={
      "Authorization": "Bearer %s" % (vBearerToken,),
      "Content-Type": "application/json",
    },
    json={"text": pMessage},
    timeout=cSendTimeoutSeconds,
  )
  if vResponse.status_code not in (200, 201):
    raise ChannelError(
      "X refused the post (HTTP %d): %s"
      % (vResponse.status_code,
         fRedactSecrets((vResponse.text or "")[:200], pConfig))
    )
  return {"channel": cChannelX, "sent": True}


# Channel name -> sender. Adding a channel means writing its sender and adding
# one row here.
dChannelSenders = {
  cChannelTelegram: fSendToTelegram,
  cChannelDiscord: fSendToDiscord,
  cChannelMattermost: fSendToMattermost,
  cChannelX: fSendToX,
}


def fSendMessage(pChannelName, pMessage, pPrefix="", pReplyToMessageId=None):
  """Send one message to one channel.

  pPrefix is prepended by the caller, not by the agent: it is how a message
  arrives saying which agent sent it, without the agent being able to claim it
  is someone else.

  pReplyToMessageId means something on Telegram and on Discord, which are the
  two channels a person can answer through, and is passed only to those two.
  Mattermost and X take two arguments: adding a third to carry something they
  cannot use would be worse than this.
  """
  vChannel = str(pChannelName or "").strip().lower()
  vMessage = str(pMessage or "").strip()
  if not vMessage:
    raise ChannelError("There is nothing to send: the message is empty.")

  if pPrefix:
    vMessage = "%s %s" % (pPrefix, vMessage)
  if len(vMessage) > cMaxMessageLength:
    vMessage = vMessage[:cMaxMessageLength - 1] + "…"

  dConfig = fReadChannelConfig(vChannel)
  fSender = dChannelSenders.get(vChannel)
  if fSender is None:
    raise ChannelError("No sender for channel %r." % (vChannel,))

  try:
    if vChannel in (cChannelTelegram, cChannelDiscord):
      return fSender(dConfig, vMessage, pReplyToMessageId)
    return fSender(dConfig, vMessage)
  except requests.RequestException as vError:
    # str(vError) carries the URL the request was made to, and for three of
    # the four channels the URL IS the credential. This is the line that used
    # to hand an agent the bot token it is not allowed to have.
    raise ChannelError(
      "Cannot reach %s: %s" % (vChannel, fRedactSecrets(vError, dConfig))
    )
