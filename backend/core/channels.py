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
import sys

import requests

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


def fListConfiguredChannels():
  """Return the name and state of every channel, without any secret in it."""
  lSummaries = []
  for vChannel in lChannels:
    dSummary = {"name": vChannel, "configured": False, "enabled": False}
    try:
      dConfig = fReadChannelConfig(vChannel)
      dSummary["configured"] = True
      dSummary["enabled"] = True
      dSummary["target"] = dConfig.get("chat_id") or dConfig.get("channel") or ""
      # Whether messages also come IN through this channel. Telegram is the
      # only one that can today, and it is off until somebody says otherwise.
      dSummary["listen"] = bool(dConfig.get("listen", False))
    except ChannelError:
      vPath = fGetChannelConfigPath(vChannel)
      dSummary["configured"] = os.path.exists(vPath)
      dSummary["listen"] = bool(
        fReadConfigForEditing(vChannel).get("listen", False))
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
      "plain text: %s\n" % ((vResponse.text or "")[:200],)
    )
    dPayload["text"] = pMarkdown
    dPayload.pop("parse_mode", None)
    vResponse = requests.post(vUrl, json=dPayload, timeout=cSendTimeoutSeconds)

  if vResponse.status_code != 200:
    # The token is in the URL, so the URL must never reach the error message.
    raise ChannelError(
      "Telegram refused the message (HTTP %d): %s"
      % (vResponse.status_code, (vResponse.text or "")[:200])
    )

  vMessageId = None
  try:
    vMessageId = vResponse.json().get("result", {}).get("message_id")
  except ValueError:
    # It answered 200 with something that is not JSON. The message went out,
    # which is what the caller asked for; only the reply routing is lost.
    pass
  return {"channel": cChannelTelegram, "sent": True, "message_id": vMessageId}


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


def fCallTelegram(pToken, pMethod, dPayload):
  """One call to the bot API. Returns the response, raising on anything but 200."""
  vResponse = requests.post(
    "https://api.telegram.org/bot%s/%s" % (pToken, pMethod),
    json=dPayload,
    timeout=cSendTimeoutSeconds,
  )
  if vResponse.status_code != 200:
    raise ChannelError(
      "Telegram refused %s (HTTP %d): %s"
      % (pMethod, vResponse.status_code, (vResponse.text or "")[:200])
    )
  return vResponse


def fSetTelegramCommands(pConfig, ldCommands):
  """Tell Telegram which commands this bot has, and tell nobody else.

  This is what makes typing `/` in the chat show a list to pick from, and
  picking one put it in the message box. It is the only autocompletion Telegram
  offers a bot: `@` is reserved for its own usernames, and nothing a bot says
  can add to that list.

  Each entry is {"command": "oswatcher", "description": "..."}. Telegram
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
    "commands": ldCommands,
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

  vResponse = requests.get(
    "https://api.telegram.org/bot%s/getUpdates" % (vToken,),
    params=dParameters,
    # Longer than the long poll itself, or the client gives up exactly when
    # Telegram is about to answer.
    timeout=vTimeout + cSendTimeoutSeconds,
  )
  if vResponse.status_code != 200:
    raise ChannelError(
      "Telegram refused to hand over the updates (HTTP %d): %s"
      % (vResponse.status_code, (vResponse.text or "")[:200])
    )
  try:
    dBody = vResponse.json()
  except ValueError:
    raise ChannelError("Telegram answered with something that is not JSON.")
  if not dBody.get("ok"):
    raise ChannelError("Telegram answered not ok: %s"
                       % (str(dBody.get("description"))[:200],))
  return dBody.get("result") or []


def fSendToDiscord(pConfig, pMessage):
  """Send one message through a Discord webhook."""
  vWebhookUrl = pConfig.get("webhook_url") or ""
  if not vWebhookUrl:
    raise ChannelError("discord.json needs a webhook_url.")

  vResponse = requests.post(
    vWebhookUrl,
    json={"content": pMessage},
    timeout=cSendTimeoutSeconds,
  )
  # Discord answers 204 with no body on success.
  if vResponse.status_code not in (200, 204):
    raise ChannelError(
      "Discord refused the message (HTTP %d): %s"
      % (vResponse.status_code, (vResponse.text or "")[:200])
    )
  return {"channel": cChannelDiscord, "sent": True}


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
      % (vResponse.status_code, (vResponse.text or "")[:200])
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
      % (vResponse.status_code, (vResponse.text or "")[:200])
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

  pReplyToMessageId only means anything on Telegram, and is passed only to it:
  the other three senders take two arguments and adding a third to all of them
  to carry something three of them cannot use would be worse than this.
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
    if vChannel == cChannelTelegram:
      return fSender(dConfig, vMessage, pReplyToMessageId)
    return fSender(dConfig, vMessage)
  except requests.RequestException as vError:
    raise ChannelError("Cannot reach %s: %s" % (vChannel, vError))
