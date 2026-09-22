"""Markdown to what Discord renders, cut into messages it will accept.

Discord speaks markdown natively, which Telegram does not, so most of what a
model writes travels unchanged: `**bold**`, `*italic*`, `` `code` ``, fenced
blocks, `> quotes`, `- lists`, `[links](url)` and, since 2023, `#` to `###`
headings. There is no escaping step here for that reason, and none is wanted:
Telegram needs one because `<` is markup to it, Discord shows `<` as `<`.

Three shapes it has no syntax for, and one hard ceiling:

    | a | b |   ->  a fenced block, the only way columns stay under each other
    #### deep   ->  bold on its own line; Discord stops at three levels
    ---         ->  an em-dash rule, because a rule is only text here
    2000 chars  ->  the most one message's `content` may hold

**The ceiling is why this module exists.** `channels.cMaxMessageLength` is
4096, which is Telegram's number, and Discord answers 400 to a `content`
longer than 2000 - so a long answer did not arrive shortened, it did not
arrive at all. Splitting rather than truncating, for the same reason the
Telegram renderer re-renders instead of cutting its HTML: what is being sent
is somebody's answer, and half of one is not an answer.

A fenced block that a split lands inside is closed at the end of one message
and opened again at the start of the next, with its language. Without that,
one half arrives as ordinary text and the other as a block that never ends,
which in Discord swallows everything said after it.

The block patterns are imported from `telegram_html` rather than written
again. They are the same ones `frontend/static/js/markdown.js` uses, and the
point of having one set is that the three places an answer is shown - the web
conversation, Telegram and now Discord - agree about what counts as markdown.
"""

import re

from backend.core import telegram_html

# Discord's own ceiling for the `content` of one message.
cMaxDiscordLength = 2000

# How many messages one answer may be cut into. Four is eight thousand
# characters, which is twice what Telegram takes in its single message, and
# the point at which a chat channel stops being readable: an agent that has
# more to say than this is writing a report, and the whole of it is in the web
# conversation where it was written.
cMaxMessagesPerAnswer = 4

# What a cut answer ends with, so that a reader knows there was more.
cEllipsis = "…"

# What stands in for a horizontal rule, which Discord draws as the three
# characters it was typed with.
cRuleText = "——————————"

# Headings deeper than this are bold instead: Discord renders `#`, `##` and
# `###` and shows `####` as the hashes themselves.
cDeepestHeading = 3

# An image is a link here. Discord embeds an image URL posted on its own, but
# `![alt](url)` is shown as those exact characters.
cImagePattern = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")


def fBuildTable(plLines, pStart):
  """Return (block, next index) for a table, as a fenced code block.

  Discord has no table syntax at all: a markdown table posted as it is comes
  out as a wall of pipes. A fenced block keeps the columns under each other,
  which on a phone is the difference between a reading and a guess. Padded
  here rather than left to the font, because the font is the only thing
  holding it together.
  """
  lRows = []
  vIndex = pStart
  while vIndex < len(plLines) and telegram_html.cTableRowPattern.match(
      plLines[vIndex]):
    if not telegram_html.cTableDividerPattern.match(plLines[vIndex]):
      lRows.append(telegram_html.fSplitTableRow(plLines[vIndex]))
    vIndex += 1

  if not lRows:
    return ("", vIndex)

  vColumns = max(len(lRow) for lRow in lRows)
  lWidths = []
  for vColumn in range(vColumns):
    lWidths.append(max(
      len(lRow[vColumn]) if vColumn < len(lRow) else 0 for lRow in lRows))

  lRendered = []
  for lRow in lRows:
    lCells = []
    for vColumn in range(vColumns):
      vCell = lRow[vColumn] if vColumn < len(lRow) else ""
      lCells.append(vCell.ljust(lWidths[vColumn]))
    lRendered.append("  ".join(lCells).rstrip())

  return ("```\n%s\n```" % ("\n".join(lRendered),), vIndex)


def fRender(pMarkdown):
  """Return one answer as the markdown Discord actually renders.

  Line by line, and a fenced block is copied out untouched: what is inside one
  is not markup, and a table drawn inside a code block is a table somebody
  drew on purpose.
  """
  lLines = str(pMarkdown or "").replace("\r\n", "\n").split("\n")
  lOut = []
  vIndex = 0
  vInFence = False

  while vIndex < len(lLines):
    vLine = lLines[vIndex]

    vFence = telegram_html.cFencePattern.match(vLine)
    if vFence:
      vInFence = not vInFence
      lOut.append(vLine)
      vIndex += 1
      continue

    if vInFence:
      lOut.append(vLine)
      vIndex += 1
      continue

    # A table, which is the one block Discord cannot draw. Looked for before
    # anything else on the line, because a row is recognised whole.
    if (telegram_html.cTableRowPattern.match(vLine)
        and not telegram_html.cTableDividerPattern.match(vLine)):
      vBlock, vNext = fBuildTable(lLines, vIndex)
      if vBlock:
        lOut.append(vBlock)
        vIndex = vNext
        continue

    if telegram_html.cRulePattern.match(vLine):
      lOut.append(cRuleText)
      vIndex += 1
      continue

    vHeading = telegram_html.cHeadingPattern.match(vLine)
    if vHeading and len(vHeading.group(1)) > cDeepestHeading:
      # Deeper than Discord goes. Bold on its own line is what it was for.
      vText = vHeading.group(2).strip()
      lOut.append("**%s**" % (vText,) if vText else "")
      vIndex += 1
      continue

    lOut.append(cImagePattern.sub(r"[\1](\2)", vLine))
    vIndex += 1

  vRendered = "\n".join(lOut)
  # An odd number of fences means the answer itself opened a block and never
  # closed it. Closing it here costs one line and stops everything after the
  # message from being drawn as code.
  if vInFence:
    vRendered += "\n```"
  return vRendered


def fReadFenceLanguage(pLine):
  """Return the language written after an opening fence, or ""."""
  vFence = telegram_html.cFencePattern.match(pLine or "")
  if not vFence:
    return ""
  vLanguage = (vFence.group(1) or "").strip()
  return vLanguage if telegram_html.cLanguagePattern.match(vLanguage) else ""


def fSplitLongLine(pLine, pLimit):
  """Return one over-long line as several, cut at a space where there is one.

  A URL or a base64 blob has no spaces in it, and a line of those is cut
  wherever the limit falls: there is nothing better to do with it, and the
  alternative is a message Discord refuses.
  """
  lPieces = []
  vRest = str(pLine or "")
  while len(vRest) > pLimit:
    vCut = vRest.rfind(" ", 0, pLimit + 1)
    if vCut <= pLimit // 2:
      vCut = pLimit
    lPieces.append(vRest[:vCut].rstrip())
    vRest = vRest[vCut:].lstrip()
  if vRest:
    lPieces.append(vRest)
  return lPieces


def fSplit(pText, pLimit=cMaxDiscordLength, pMaxMessages=cMaxMessagesPerAnswer):
  """Return one rendered answer as the messages it has to be sent in.

  Cut between lines wherever possible, because a paragraph broken mid-word
  reads as a transmission error. A fenced block the cut lands inside is closed
  and opened again, so neither half arrives malformed.

  The last message ends with an ellipsis when there was more than `pMaxMessages`
  would carry. The rest is not lost: it is in the agent's conversation in the
  web interface, which is where it was written first.
  """
  vText = str(pText or "")
  if not vText.strip():
    return []

  # What a message ending inside a fenced block has to add to close it. Kept
  # free only while a block is open: reserving it always would split an answer
  # of exactly the limit into two, and most answers have no block in them.
  cFenceClose = len("\n```")

  lMessages = []
  lCurrent = []
  vLength = 0
  vFenceLanguage = ""
  vInFence = False

  def fCloseMessage(plLines, pInFence):
    """Return the text of one message, closing a block it leaves open."""
    vBody = "\n".join(plLines).rstrip()
    if pInFence:
      vBody += "\n```"
    return vBody

  lLines = vText.split("\n")
  vIndex = 0
  while vIndex < len(lLines):
    vLine = lLines[vIndex]
    vRoom = max(40, pLimit - (cFenceClose if vInFence else 0))

    # Lines longer than a whole message exist: a table row, a log line, a URL.
    if len(vLine) > vRoom:
      lLines[vIndex:vIndex + 1] = fSplitLongLine(vLine, vRoom)
      vLine = lLines[vIndex]

    vAdded = len(vLine) + (1 if lCurrent else 0)
    if lCurrent and vLength + vAdded > vRoom:
      lMessages.append(fCloseMessage(lCurrent, vInFence))
      if len(lMessages) >= pMaxMessages:
        break
      # A block that was open when the message ended opens again here, with
      # the language it had, so the next half is still drawn as code.
      lCurrent = ["```%s" % (vFenceLanguage,)] if vInFence else []
      vLength = len(lCurrent[0]) if lCurrent else 0
      continue

    if telegram_html.cFencePattern.match(vLine):
      if vInFence:
        vInFence = False
        vFenceLanguage = ""
      else:
        vInFence = True
        vFenceLanguage = fReadFenceLanguage(vLine)

    lCurrent.append(vLine)
    vLength += vAdded
    vIndex += 1

  if lCurrent and len(lMessages) < pMaxMessages:
    lMessages.append(fCloseMessage(lCurrent, vInFence))

  # Something was left over: say so rather than stopping mid-sentence.
  if vIndex < len(lLines) and lMessages:
    vLast = lMessages[-1]
    if len(vLast) + len(cEllipsis) + 1 <= pLimit:
      lMessages[-1] = "%s\n%s" % (vLast, cEllipsis)
    else:
      lMessages[-1] = vLast[:pLimit - len(cEllipsis)] + cEllipsis

  # Nothing may leave here over the limit, whatever the arithmetic above did.
  return [vMessage[:pLimit] for vMessage in lMessages if vMessage.strip()]


def fRenderToMessages(pMarkdown, pLimit=cMaxDiscordLength,
                      pMaxMessages=cMaxMessagesPerAnswer):
  """Return one markdown answer as the list of messages to send for it."""
  return fSplit(fRender(pMarkdown), pLimit, pMaxMessages)
