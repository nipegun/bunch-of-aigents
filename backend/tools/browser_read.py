"""Tool: browser.read - read the page that is already open.

Either the whole of it again, one part of it by selector, or the links on it.
Separate from browser.open because a click changes the page without navigating
anywhere, and re-opening the URL to see the result would undo the click.
"""

from backend.core import browser
from backend.core import tool_registry

cToolName = "browser.read"

cToolDescription = (
  "Read the page currently open in your browser. Without arguments you get "
  "all of its text again - useful after a click changed it. With a selector "
  "you get just that part. With links set, the links on it, so you can find "
  "where to go next."
)

dToolSchema = {
  "type": "object",
  "properties": {
    "selector": {
      "type": "string",
      "description": "Optional CSS selector. Without it, the whole page.",
    },
    "links": {
      "type": "boolean",
      "description": "Return the links on the page instead of its text.",
    },
  },
  "required": [],
  "additionalProperties": False,
}

# How many links one answer may carry. A navigation menu can hold hundreds,
# and a list that long is not something a model reads - it is something it
# pays for.
cMaxLinks = 100


def fRunTool(pArguments, pContext):
  """Return the text or the links of the open page."""
  try:
    vPage = browser.fGetPage(pContext.vAgentId)
    if not vPage.url or vPage.url == "about:blank":
      raise tool_registry.ToolFailure(
        "There is no page open. Use browser.open first.")

    if pArguments.get("links"):
      lLinks = vPage.eval_on_selector_all(
        "a[href]",
        "lNodes => lNodes.map(vNode => vNode.innerText.trim() + ' -> ' "
        "+ vNode.href)")
      lLinks = [vLink for vLink in lLinks if vLink.strip(" ->")]
      vText = "\n".join(lLinks[:cMaxLinks])
      if len(lLinks) > cMaxLinks:
        vText += "\n[... and %d more]" % (len(lLinks) - cMaxLinks,)
      return browser.fDescribePage(vPage, vText or "(no links)")

    vSelector = str(pArguments.get("selector") or "").strip()
    if vSelector:
      vElement = vPage.query_selector(vSelector)
      if vElement is None:
        raise tool_registry.ToolFailure(
          "Nothing on this page matches %r. Read the whole page to see what "
          "is there." % (vSelector,))
      return browser.fDescribePage(vPage, vElement.inner_text())

    return browser.fDescribePage(vPage, vPage.inner_text("body"))
  except tool_registry.ToolFailure:
    raise
  except browser.BrowserError as vError:
    raise tool_registry.ToolFailure(str(vError))
  except Exception as vError:
    raise tool_registry.ToolFailure("Could not read the page: %s" % (vError,))
