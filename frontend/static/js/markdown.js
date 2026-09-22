/* Markdown for what a model writes in the chat.
 *
 * Why a renderer of our own rather than a library: the page is served under
 * `script-src 'self'` with no CDN and the project ships no JavaScript
 * dependencies, so a library would have to be vendored and kept up to date for
 * a feature this size.
 *
 * Why it builds nodes instead of HTML: every string here comes from a model,
 * which in turn has been reading the output of shell commands and web pages.
 * That is untrusted text. Nothing in this file touches innerHTML, so there is
 * no path from a message to executable markup - not a filter that has to be
 * right, but a shape in which the problem cannot occur.
 *
 * It covers what models actually write: headings, bold, italic, inline code,
 * fenced code, lists, tables, quotes and rules. Anything it does not know is
 * left as the text it was, which is the same thing the chat did before.
 */

/* A link is followed by a person, so only these two schemes are turned into
 * one. Anything else stays as plain text, javascript: included. */
const lSafeLinkSchemes = ["http://", "https://"];

const cHeadingPattern = /^(#{1,6})\s+(.*)$/;
const cUnorderedItemPattern = /^\s*[-*+]\s+(.*)$/;
const cOrderedItemPattern = /^\s*(\d+)[.)]\s+(.*)$/;
const cQuotePattern = /^\s*>\s?(.*)$/;
const cRulePattern = /^\s*([-*_])(\s*\1){2,}\s*$/;
const cFencePattern = /^\s*```(.*)$/;
const cTableRowPattern = /^\s*\|(.+)\|\s*$/;
const cTableDividerPattern = /^\s*\|[\s:|-]+\|\s*$/;

/* Inline markup, in the order it is looked for. Code comes first because
 * nothing inside a backtick span is markup. */
const lInlinePatterns = [
  { name: "code", pattern: /`([^`]+)`/ },
  { name: "bold", pattern: /\*\*([^*]+)\*\*/ },
  { name: "boldUnderscore", pattern: /__([^_]+)__/ },
  { name: "strike", pattern: /~~([^~]+)~~/ },
  { name: "italic", pattern: /\*([^*\n]+)\*/ },
  { name: "link", pattern: /\[([^\]]*)\]\(([^)\s]+)\)/ },
];

function fIsSafeLink(pUrl) {
  const vUrl = String(pUrl || "").trim().toLowerCase();
  return lSafeLinkSchemes.some(function (vScheme) {
    return vUrl.indexOf(vScheme) === 0;
  });
}

function fFindFirstInline(pText) {
  /* Return the earliest inline match in the text, or null. Earliest wins so
   * that `**a**` inside a code span is left alone by the bold rule. */
  let dEarliest = null;
  lInlinePatterns.forEach(function (dRule) {
    const dMatch = dRule.pattern.exec(pText);
    if (!dMatch) { return; }
    if (dEarliest === null || dMatch.index < dEarliest.match.index) {
      dEarliest = { rule: dRule, match: dMatch };
    }
  });
  return dEarliest;
}

function fBuildInlineNode(pRuleName, pMatch) {
  if (pRuleName === "code") {
    return fCreateElement("code", "", pMatch[1]);
  }
  if (pRuleName === "bold" || pRuleName === "boldUnderscore") {
    return fRenderInlineInto(document.createElement("strong"), pMatch[1]);
  }
  if (pRuleName === "italic") {
    return fRenderInlineInto(document.createElement("em"), pMatch[1]);
  }
  if (pRuleName === "strike") {
    return fRenderInlineInto(document.createElement("del"), pMatch[1]);
  }
  if (pRuleName === "link") {
    const vLabel = pMatch[1] || pMatch[2];
    if (!fIsSafeLink(pMatch[2])) {
      /* Not a scheme we open: show what it said, as text. */
      return document.createTextNode(pMatch[0]);
    }
    const vAnchor = fCreateElement("a", "", vLabel);
    vAnchor.href = pMatch[2];
    vAnchor.target = "_blank";
    /* noopener because the other page must not reach back into this one. */
    vAnchor.rel = "noopener noreferrer";
    return vAnchor;
  }
  return document.createTextNode(pMatch[0]);
}

function fRenderInlineInto(pElement, pText) {
  /* Fill one element with text and its inline markup. */
  let vRest = String(pText === undefined || pText === null ? "" : pText);

  while (vRest.length > 0) {
    const dFound = fFindFirstInline(vRest);
    if (!dFound) {
      pElement.appendChild(document.createTextNode(vRest));
      break;
    }
    const vIndex = dFound.match.index;
    if (vIndex > 0) {
      pElement.appendChild(document.createTextNode(vRest.slice(0, vIndex)));
    }
    pElement.appendChild(fBuildInlineNode(dFound.rule.name, dFound.match));
    vRest = vRest.slice(vIndex + dFound.match[0].length);
  }
  return pElement;
}

function fSplitTableRow(pLine) {
  const dMatch = cTableRowPattern.exec(pLine);
  if (!dMatch) { return null; }
  return dMatch[1].split("|").map(function (vCell) { return vCell.trim(); });
}

function fBuildTable(lLines, pStart) {
  /* A table is a row, a divider, and the rows after it. Without the divider it
   * is not a table, which is how a line that merely contains a pipe stays a
   * paragraph. */
  const lHeader = fSplitTableRow(lLines[pStart]);
  if (!lHeader || pStart + 1 >= lLines.length) { return null; }
  if (!cTableDividerPattern.test(lLines[pStart + 1])) { return null; }

  const vTable = document.createElement("table");
  const vHead = document.createElement("thead");
  const vHeadRow = document.createElement("tr");
  lHeader.forEach(function (vCell) {
    vHeadRow.appendChild(fRenderInlineInto(document.createElement("th"), vCell));
  });
  vHead.appendChild(vHeadRow);
  vTable.appendChild(vHead);

  const vBody = document.createElement("tbody");
  let vIndex = pStart + 2;
  while (vIndex < lLines.length) {
    const lCells = fSplitTableRow(lLines[vIndex]);
    if (!lCells) { break; }
    const vRow = document.createElement("tr");
    lCells.forEach(function (vCell) {
      vRow.appendChild(fRenderInlineInto(document.createElement("td"), vCell));
    });
    vBody.appendChild(vRow);
    vIndex += 1;
  }
  vTable.appendChild(vBody);

  /* Its own scroll box: a wide table must scroll inside the bubble rather than
   * drag the whole page sideways on a phone. */
  const vWrap = fCreateElement("div", "md-table-wrap");
  vWrap.appendChild(vTable);
  return { node: vWrap, next: vIndex };
}

function fBuildList(lLines, pStart, pOrdered) {
  const cPattern = pOrdered ? cOrderedItemPattern : cUnorderedItemPattern;
  const vList = document.createElement(pOrdered ? "ol" : "ul");
  let vIndex = pStart;

  while (vIndex < lLines.length) {
    const dMatch = cPattern.exec(lLines[vIndex]);
    if (!dMatch) { break; }
    const vText = pOrdered ? dMatch[2] : dMatch[1];
    vList.appendChild(fRenderInlineInto(document.createElement("li"), vText));
    vIndex += 1;
  }

  if (pOrdered) {
    const dFirst = cOrderedItemPattern.exec(lLines[pStart]);
    const vFirstNumber = parseInt(dFirst[1], 10);
    if (vFirstNumber > 1) { vList.setAttribute("start", String(vFirstNumber)); }
  }
  return { node: vList, next: vIndex };
}

function fBuildFencedCode(lLines, pStart) {
  const dOpen = cFencePattern.exec(lLines[pStart]);
  const vLanguage = (dOpen[1] || "").trim();
  const lBody = [];
  let vIndex = pStart + 1;

  while (vIndex < lLines.length && !cFencePattern.test(lLines[vIndex])) {
    lBody.push(lLines[vIndex]);
    vIndex += 1;
  }
  /* A fence nobody closed still ends the block, at the end of the message. */
  if (vIndex < lLines.length) { vIndex += 1; }

  const vPre = fCreateElement("pre", "md-code");
  const vCode = fCreateElement("code", "", lBody.join("\n"));
  if (vLanguage) { vPre.setAttribute("data-language", vLanguage); }
  vPre.appendChild(vCode);
  return { node: vPre, next: vIndex };
}

function fBuildQuote(lLines, pStart) {
  const lBody = [];
  let vIndex = pStart;
  while (vIndex < lLines.length) {
    const dMatch = cQuotePattern.exec(lLines[vIndex]);
    if (!dMatch) { break; }
    lBody.push(dMatch[1]);
    vIndex += 1;
  }
  const vQuote = fCreateElement("blockquote", "md-quote");
  /* The body of a quote is markdown too, so it goes back through the same
   * renderer rather than being pasted in as text. */
  vQuote.appendChild(fRenderMarkdown(lBody.join("\n")));
  return { node: vQuote, next: vIndex };
}

function fBuildParagraph(lLines, pStart) {
  const lBody = [];
  let vIndex = pStart;

  while (vIndex < lLines.length) {
    const vLine = lLines[vIndex];
    if (vLine.trim() === "") { break; }
    if (cHeadingPattern.test(vLine) || cFencePattern.test(vLine) ||
        cRulePattern.test(vLine) || cQuotePattern.test(vLine) ||
        cUnorderedItemPattern.test(vLine) || cOrderedItemPattern.test(vLine) ||
        fSplitTableRow(vLine)) {
      break;
    }
    lBody.push(vLine);
    vIndex += 1;
  }

  if (lBody.length === 0) { return { node: null, next: pStart + 1 }; }
  const vParagraph = document.createElement("p");
  /* A single newline inside a paragraph is a line break here. Models lay text
   * out with them and collapsing them, as strict markdown does, runs their
   * lines together. */
  lBody.forEach(function (vLine, vIndexInBody) {
    if (vIndexInBody > 0) { vParagraph.appendChild(document.createElement("br")); }
    fRenderInlineInto(vParagraph, vLine);
  });
  return { node: vParagraph, next: vIndex };
}

function fRenderMarkdown(pText) {
  /* Return a DocumentFragment with the rendered message. */
  const vFragment = document.createDocumentFragment();
  const lLines = String(pText === undefined || pText === null ? "" : pText)
    .replace(/\r\n?/g, "\n").split("\n");

  let vIndex = 0;
  while (vIndex < lLines.length) {
    const vLine = lLines[vIndex];

    if (vLine.trim() === "") { vIndex += 1; continue; }

    if (cFencePattern.test(vLine)) {
      const dBlock = fBuildFencedCode(lLines, vIndex);
      vFragment.appendChild(dBlock.node);
      vIndex = dBlock.next;
      continue;
    }

    if (cRulePattern.test(vLine)) {
      vFragment.appendChild(document.createElement("hr"));
      vIndex += 1;
      continue;
    }

    const dHeading = cHeadingPattern.exec(vLine);
    if (dHeading) {
      /* h1 and h2 in a chat bubble are shouting, so everything lands one or
       * two levels down: the bubble is not the page. */
      const vLevel = Math.min(6, dHeading[1].length + 2);
      vFragment.appendChild(fRenderInlineInto(
        document.createElement("h" + vLevel), dHeading[2]));
      vIndex += 1;
      continue;
    }

    if (cQuotePattern.test(vLine)) {
      const dBlock = fBuildQuote(lLines, vIndex);
      vFragment.appendChild(dBlock.node);
      vIndex = dBlock.next;
      continue;
    }

    if (fSplitTableRow(vLine)) {
      const dTable = fBuildTable(lLines, vIndex);
      if (dTable) {
        vFragment.appendChild(dTable.node);
        vIndex = dTable.next;
        continue;
      }
    }

    if (cUnorderedItemPattern.test(vLine)) {
      const dBlock = fBuildList(lLines, vIndex, false);
      vFragment.appendChild(dBlock.node);
      vIndex = dBlock.next;
      continue;
    }

    if (cOrderedItemPattern.test(vLine)) {
      const dBlock = fBuildList(lLines, vIndex, true);
      vFragment.appendChild(dBlock.node);
      vIndex = dBlock.next;
      continue;
    }

    const dParagraph = fBuildParagraph(lLines, vIndex);
    if (dParagraph.node) { vFragment.appendChild(dParagraph.node); }
    vIndex = dParagraph.next;
  }

  return vFragment;
}
