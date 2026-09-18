/* Syntax colouring for the JSON blocks on the API documentation page.
 *
 * Written here rather than pulled in, for the same reason the markdown
 * renderer is: the page is served with `script-src 'self'` and no CDN, so a
 * highlighting library would have to live inside this repository and be
 * maintained. Colouring JSON needs one regular expression.
 *
 * It builds DOM nodes and never assigns markup. The text being coloured comes
 * from this server, so the risk here is smaller than in the chat - but the
 * safe way is not harder, and a rule with an exception in it is a rule nobody
 * remembers. A test fails if innerHTML appears in this file.
 *
 * The colours are theme variables, so every installed theme sets its own and
 * the contrast test holds them to the same bar as everything else that paints
 * text.
 */

/* One pass finds all four kinds of token. A string followed by a colon is a
 * key rather than a value, which is why the colon is part of the pattern: it
 * is the only thing that tells them apart. Everything between matches -
 * braces, brackets, commas, the indentation - is left as plain text and takes
 * the block's own dimmed colour. */
const cJsonTokenPattern =
  /("(?:\\.|[^"\\])*")(\s*:)?|\b(true|false|null)\b|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g;

function fAppendJsonToken(pParent, pClassName, pText) {
  if (!pText) { return; }
  const vSpan = document.createElement("span");
  vSpan.className = pClassName;
  vSpan.textContent = pText;
  pParent.appendChild(vSpan);
}

/* Replaces the element's text with the same text in coloured pieces. The
 * result reads identically when copied: every character of the original is
 * emitted exactly once, either inside a span or as plain text. */
function fHighlightJsonElement(pElement) {
  const vSource = pElement.textContent;
  if (!vSource) { return; }

  const vFragment = document.createDocumentFragment();
  let vLastIndex = 0;
  let lMatch;

  cJsonTokenPattern.lastIndex = 0;
  while ((lMatch = cJsonTokenPattern.exec(vSource)) !== null) {
    if (lMatch.index > vLastIndex) {
      vFragment.appendChild(
        document.createTextNode(vSource.slice(vLastIndex, lMatch.index)));
    }

    if (lMatch[1] !== undefined) {
      /* A key is the name of a field; a string is a value. Two different
       * things, so two different colours. */
      fAppendJsonToken(vFragment,
                       lMatch[2] !== undefined ? "json-key" : "json-string",
                       lMatch[1]);
      if (lMatch[2] !== undefined) {
        vFragment.appendChild(document.createTextNode(lMatch[2]));
      }
    } else if (lMatch[3] !== undefined) {
      fAppendJsonToken(vFragment, "json-literal", lMatch[3]);
    } else {
      fAppendJsonToken(vFragment, "json-number", lMatch[4]);
    }

    vLastIndex = cJsonTokenPattern.lastIndex;
  }

  if (vLastIndex < vSource.length) {
    vFragment.appendChild(document.createTextNode(vSource.slice(vLastIndex)));
  }

  while (pElement.firstChild) { pElement.removeChild(pElement.firstChild); }
  pElement.appendChild(vFragment);
  pElement.classList.add("json-code");
}

function fHighlightJsonBlocks(pRoot) {
  (pRoot || document).querySelectorAll("pre.json").forEach(fHighlightJsonElement);
}

document.addEventListener("DOMContentLoaded", function () {
  fHighlightJsonBlocks(document);
});
