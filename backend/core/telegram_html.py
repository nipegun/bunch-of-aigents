"""Markdown to the small HTML that Telegram understands.

A model writes markdown. It writes it into the chat, where the browser renders
it, and it writes it into Telegram, where until now it arrived as `**25G
free**` with the asterisks showing. This turns it into what Telegram calls
HTML, which is not HTML: it is fourteen tags and nothing else.

    supported: b i u s a code pre blockquote, and a few aliases
    not supported: headings, lists, tables, images, anything with attributes

So half the work is translating what Telegram has no tag for into something a
person can still read:

    # Heading      ->  bold on its own line
    - item         ->  • item
    1. item        ->  1. item
    | a | b |      ->  a monospaced block, which is the only way a table keeps
                       its columns on a phone
    ---            ->  an em-dash rule

The patterns are deliberately the same ones `frontend/static/js/markdown.js`
uses. Two renderers that disagree about what counts as markdown would mean the
same answer reading differently in the two places it is shown, and the whole
point of sending both is that they are the same conversation.

Escaping comes first and is not optional. `&`, `<` and `>` are markup to
Telegram, and an agent reporting `df -h | grep <dev>` would otherwise produce a
message Telegram rejects with a 400 - which is to say, a message that silently
never arrives. Every piece of text goes through fEscape before anything wraps
it, and the wrapping is added afterwards, so there is no path where a tag this
module writes gets escaped or where text it did not write does not.
"""

import re

# Block patterns, in the order the renderer looks for them. Same shapes as
# markdown.js, so both agree on what is markdown and what is text.
cHeadingPattern = re.compile(r"^(#{1,6})\s+(.*)$")
cUnorderedItemPattern = re.compile(r"^\s*[-*+]\s+(.*)$")
cOrderedItemPattern = re.compile(r"^\s*(\d+)[.)]\s+(.*)$")
cQuotePattern = re.compile(r"^\s*>\s?(.*)$")
cRulePattern = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
cFencePattern = re.compile(r"^\s*```(.*)$")
cTableRowPattern = re.compile(r"^\s*\|(.+)\|\s*$")
cTableDividerPattern = re.compile(r"^\s*\|[\s:|-]+\|\s*$")

# What may follow a fence and be treated as a language name. Matched whole:
# the value goes into a class attribute, and a name is either one or it is not.
cLanguagePattern = re.compile(r"^[A-Za-z][A-Za-z0-9+#_-]{0,19}$")

# Inline markup, in the order it is looked for. Code first, because nothing
# inside a backtick span is markup.
lInlinePatterns = [
  ("code", re.compile(r"`([^`]+)`")),
  ("bold", re.compile(r"\*\*([^*]+)\*\*")),
  ("boldUnderscore", re.compile(r"__([^_]+)__")),
  ("strike", re.compile(r"~~([^~]+)~~")),
  ("italic", re.compile(r"\*([^*\n]+)\*")),
  ("link", re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")),
]

# A link is followed by a person, so only these two schemes become one.
# Anything else stays as the text it was, `javascript:` included.
lSafeLinkSchemes = ["http://", "https://"]

# What stands in for a horizontal rule, which Telegram has no tag for.
cRuleText = "——————————"

# The bullet for an unordered list, for the same reason.
cBulletText = "•"

# Telegram's own ceiling for one message.
cMaxTelegramLength = 4096


def fEscape(pText):
  """Escape the three characters Telegram treats as markup.

  Ampersand first: doing it last would escape the ampersands of the entities
  the other two just produced.
  """
  return (str(pText or "")
          .replace("&", "&amp;")
          .replace("<", "&lt;")
          .replace(">", "&gt;"))


def fEscapeAttribute(pText):
  """Escape a value that goes inside double quotes, the quote included.

  A URL is allowed to contain a double quote, and one that does would
  otherwise close the href and turn the rest of itself into attributes:

      [x](https://e.com/"onmouseover="evil)
      -> <a href="https://e.com/"onmouseover="evil">x</a>

  Telegram answers that with a 400, so the message never arrives - and an
  attribute nobody wrote is the wrong thing to be building either way.
  """
  return fEscape(pText).replace('"', "&quot;")


def fIsSafeLink(pUrl):
  """Return whether this is a scheme worth turning into a link."""
  vUrl = str(pUrl or "").strip().lower()
  return any(vUrl.startswith(vScheme) for vScheme in lSafeLinkSchemes)


def fFindFirstInline(pText):
  """Return the earliest inline match in this text, or None.

  Earliest wins rather than first pattern wins, so `**a** and `b`` is bold
  followed by code and not one enormous bold span.
  """
  dEarliest = None
  for vName, vPattern in lInlinePatterns:
    vMatch = vPattern.search(pText)
    if vMatch is None:
      continue
    if dEarliest is None or vMatch.start() < dEarliest[1].start():
      dEarliest = (vName, vMatch)
  return dEarliest


def fRenderInline(pText):
  """Turn the inline markup of one piece of text into Telegram's HTML."""
  vText = str(pText or "")
  lParts = []

  while vText:
    dFound = fFindFirstInline(vText)
    if dFound is None:
      lParts.append(fEscape(vText))
      break

    vName, vMatch = dFound
    lParts.append(fEscape(vText[:vMatch.start()]))

    if vName == "code":
      lParts.append("<code>%s</code>" % (fEscape(vMatch.group(1)),))
    elif vName in ("bold", "boldUnderscore"):
      lParts.append("<b>%s</b>" % (fRenderInline(vMatch.group(1)),))
    elif vName == "strike":
      lParts.append("<s>%s</s>" % (fRenderInline(vMatch.group(1)),))
    elif vName == "italic":
      lParts.append("<i>%s</i>" % (fRenderInline(vMatch.group(1)),))
    elif vName == "link":
      vLabel = fRenderInline(vMatch.group(1))
      vUrl = vMatch.group(2)
      if fIsSafeLink(vUrl):
        # The href is an attribute, so the quote is escaped too: a quote in a
        # URL must not be able to close the tag.
        lParts.append('<a href="%s">%s</a>' % (fEscapeAttribute(vUrl), vLabel))
      else:
        lParts.append(fEscape(vMatch.group(0)))

    vText = vText[vMatch.end():]

  return "".join(lParts)


def fSplitTableRow(pLine):
  """Return the cells of one table row."""
  vInner = cTableRowPattern.match(pLine).group(1)
  return [vCell.strip() for vCell in vInner.split("|")]


def fBuildTable(lLines, pStart):
  """Return (html, next index) for a table, as a monospaced block.

  Telegram has no table tag, and a table flattened into prose stops being a
  table. A <pre> block keeps the columns under each other, which on a phone is
  the difference between a reading and a wall of words. Padded here rather than
  left to the font, because the font is the only thing holding it together.
  """
  lRows = []
  vIndex = pStart
  while vIndex < len(lLines) and cTableRowPattern.match(lLines[vIndex]):
    if not cTableDividerPattern.match(lLines[vIndex]):
      lRows.append(fSplitTableRow(lLines[vIndex]))
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

  return ("<pre>%s</pre>" % (fEscape("\n".join(lRendered)),), vIndex)


def fBuildFencedCode(lLines, pStart):
  """Return (html, next index) for a fenced code block."""
  vLanguage = cFencePattern.match(lLines[pStart]).group(1).strip()
  lBody = []
  vIndex = pStart + 1
  while vIndex < len(lLines) and not cFencePattern.match(lLines[vIndex]):
    lBody.append(lLines[vIndex])
    vIndex += 1
  # Step over the closing fence when there is one. A block nobody closed runs
  # to the end of the message, which is what the browser does with it too.
  if vIndex < len(lLines):
    vIndex += 1

  vCode = fEscape("\n".join(lBody))
  # It lands in a class attribute, so it is matched rather than cleaned:
  # stripping the characters out of `x" onload="evil` leaves `xonloadevil`,
  # which is not an attack but is not a language either. Anything that is not
  # a language name means no language.
  if vLanguage and not cLanguagePattern.match(vLanguage):
    vLanguage = ""
  if vLanguage:
    return ('<pre><code class="language-%s">%s</code></pre>'
            % (vLanguage, vCode), vIndex)
  return ("<pre>%s</pre>" % (vCode,), vIndex)


def fBuildQuote(lLines, pStart):
  """Return (html, next index) for a run of quoted lines."""
  lBody = []
  vIndex = pStart
  while vIndex < len(lLines) and cQuotePattern.match(lLines[vIndex]):
    lBody.append(cQuotePattern.match(lLines[vIndex]).group(1))
    vIndex += 1
  return ("<blockquote>%s</blockquote>"
          % ("\n".join(fRenderInline(vLine) for vLine in lBody),), vIndex)


def fBuildList(lLines, pStart, pOrdered):
  """Return (html, next index) for a run of list items.

  Telegram has no list tag, so the marker becomes part of the text: a bullet
  for an unordered list, and the writer's own number for an ordered one -
  renumbering it would be rewriting what the agent said.
  """
  cPattern = cOrderedItemPattern if pOrdered else cUnorderedItemPattern
  lItems = []
  vIndex = pStart
  while vIndex < len(lLines):
    vMatch = cPattern.match(lLines[vIndex])
    if vMatch is None:
      break
    if pOrdered:
      lItems.append("%s. %s"
                    % (vMatch.group(1), fRenderInline(vMatch.group(2))))
    else:
      lItems.append("%s %s" % (cBulletText, fRenderInline(vMatch.group(1))))
    vIndex += 1
  return ("\n".join(lItems), vIndex)


def fBuildParagraph(lLines, pStart):
  """Return (html, next index) for a run of ordinary lines."""
  lBody = []
  vIndex = pStart
  while vIndex < len(lLines):
    vLine = lLines[vIndex]
    if not vLine.strip():
      break
    if (cHeadingPattern.match(vLine) or cUnorderedItemPattern.match(vLine)
        or cOrderedItemPattern.match(vLine) or cQuotePattern.match(vLine)
        or cRulePattern.match(vLine) or cFencePattern.match(vLine)
        or cTableRowPattern.match(vLine)):
      break
    lBody.append(fRenderInline(vLine))
    vIndex += 1
  return ("\n".join(lBody), vIndex)


def fRender(pMarkdown):
  """Turn markdown into the HTML subset Telegram accepts."""
  vText = str(pMarkdown or "").replace("\r\n", "\n")
  lLines = vText.split("\n")

  lBlocks = []
  vIndex = 0
  while vIndex < len(lLines):
    vLine = lLines[vIndex]

    if not vLine.strip():
      vIndex += 1
      continue

    vMatch = cHeadingPattern.match(vLine)
    if vMatch:
      # Bold on its own line. Telegram has no headings, and the alternative -
      # leaving the hashes in - is what this module exists to stop.
      lBlocks.append("<b>%s</b>" % (fRenderInline(vMatch.group(2)),))
      vIndex += 1
      continue

    if cRulePattern.match(vLine):
      lBlocks.append(cRuleText)
      vIndex += 1
      continue

    if cFencePattern.match(vLine):
      vBlock, vIndex = fBuildFencedCode(lLines, vIndex)
      lBlocks.append(vBlock)
      continue

    if cTableRowPattern.match(vLine):
      vBlock, vNext = fBuildTable(lLines, vIndex)
      if vBlock:
        lBlocks.append(vBlock)
      vIndex = vNext
      continue

    if cQuotePattern.match(vLine):
      vBlock, vIndex = fBuildQuote(lLines, vIndex)
      lBlocks.append(vBlock)
      continue

    if cOrderedItemPattern.match(vLine):
      vBlock, vIndex = fBuildList(lLines, vIndex, True)
      lBlocks.append(vBlock)
      continue

    if cUnorderedItemPattern.match(vLine):
      vBlock, vIndex = fBuildList(lLines, vIndex, False)
      lBlocks.append(vBlock)
      continue

    vBlock, vNext = fBuildParagraph(lLines, vIndex)
    if vBlock:
      lBlocks.append(vBlock)
    # A line that matched nothing and produced nothing would loop for ever.
    vIndex = vNext if vNext > vIndex else vIndex + 1

  return "\n\n".join(lBlocks)


def fRenderWithinLimit(pMarkdown, pLimit=cMaxTelegramLength):
  """Render, shortening the source until the result fits.

  The limit is on what Telegram receives, tags included, so a message trimmed
  before rendering can still come out too long - and cutting the rendered HTML
  instead would leave a tag half written, which Telegram answers with a 400.
  So the markdown is what gets shorter, and it is re-rendered whole.
  """
  vMarkdown = str(pMarkdown or "")
  vRendered = fRender(vMarkdown)
  vAttempts = 0
  while len(vRendered) > pLimit and vAttempts < 12 and len(vMarkdown) > 40:
    # Cut in proportion to the overshoot, with a little off the top, so a
    # message with heavy markup converges instead of creeping down.
    vKeep = int(len(vMarkdown) * pLimit / len(vRendered) * 0.9)
    vMarkdown = vMarkdown[:max(40, vKeep)].rstrip()
    vRendered = fRender(vMarkdown + "\n\n…")
    vAttempts += 1
  if len(vRendered) > pLimit:
    # Nothing else worked: plain escaped text, cut hard. It is the one shape
    # that cannot come out malformed.
    return fEscape(vMarkdown)[:pLimit]
  return vRendered
