"""Agent Markdown rendered as Slack mrkdwn, without executable mentions."""

import html
import re

from backend.core import discord_markdown, telegram_html

cMaxMessageLength = 4000
cInlinePattern = re.compile(r"(`[^`\n]+`|\[[^\]\n]+\]\(https?://[^\s)]+\))")
cLinkPattern = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")


def fEscape(pText):
  return str(pText).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fRenderInline(pText):
  lOut = []
  for vPart in cInlinePattern.split(pText):
    vLink = cLinkPattern.fullmatch(vPart)
    if vLink:
      lOut.append("<%s|%s>" % (fEscape(vLink[2]).replace("|", "%7C"),
                              fEscape(vLink[1]).replace("|", "¦")))
    elif vPart.startswith("`") and vPart.endswith("`"):
      lOut.append(fEscape(vPart))
    else:
      vText = fEscape(vPart)
      # Convert italics before bold, so the newly emitted single stars stay bold.
      vText = re.sub(r"(?<!\*)\*(?!\*)([^*\n]+)\*(?!\*)", r"_\1_", vText)
      vText = re.sub(r"\*\*([^\n]+?)\*\*", r"*\1*", vText)
      vText = re.sub(r"__([^\n]+?)__", r"*\1*", vText)
      vText = re.sub(r"~~([^\n]+?)~~", r"~\1~", vText)
      lOut.append(vText)
  return "".join(lOut)


def fRender(pMarkdown):
  lOut = []
  vInFence = False
  for vLine in discord_markdown.fRender(pMarkdown).split("\n"):
    if telegram_html.cFencePattern.match(vLine):
      vInFence = not vInFence
      lOut.append("```")
    elif vInFence:
      lOut.append(fEscape(vLine))
    else:
      vHeading = telegram_html.cHeadingPattern.match(vLine)
      if vHeading:
        lOut.append("*%s*" % fRenderInline(vHeading[2]))
      elif vLine.startswith("> "):
        lOut.append("> " + fRenderInline(vLine[2:]))
      else:
        lOut.append(fRenderInline(vLine))
  return "\n".join(lOut)


def fRenderToMessages(pMarkdown):
  return discord_markdown.fSplit(fRender(pMarkdown), cMaxMessageLength, 4)


def fReadMessageText(pText, pBotUserId=""):
  """Decode Slack's link encoding and remove only this bot's leading mention."""
  vText = str(pText or "").strip()
  vMention = "<@%s>" % pBotUserId
  if pBotUserId and vText.startswith(vMention):
    vText = vText[len(vMention):].lstrip(" :,")
  vText = re.sub(r"<(https?://[^>|]+)\|[^>]*>", r"\1", vText)
  vText = re.sub(r"<(https?://[^>]+)>", r"\1", vText)
  return html.unescape(vText).strip()
