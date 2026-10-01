"""Tool: browser.open - go to a page in this agent's own browser.

The browser stays open for the rest of the run, with this page on it, so the
other browser tools act on what this one left there.

Public addresses only, checked the same way web.fetch checks them. An agent
reading a hostile page could otherwise be told to open the router's admin
panel, and a browser with a session is a far better tool for that than a
fetch.
"""

from backend.core import browser
from backend.core import public_url
from backend.core import tool_registry

cToolName = "browser.open"

cToolDescription = (
  "Open a page in your own browser and read it. Unlike web.fetch this keeps "
  "cookies and stays open, so you can log in once and go on using the site "
  "with browser.click and browser.type. Your session is yours alone and "
  "survives to your next run. Public addresses only."
)

dToolSchema = {
  "type": "object",
  "properties": {
    "url": {
      "type": "string",
      "description": "The address, starting with http:// or https://.",
    },
    "wait_for": {
      "type": "string",
      "description": "Optional CSS selector to wait for before reading the "
                     "page, for a site that fills itself in with JavaScript.",
    },
  },
  "required": ["url"],
  "additionalProperties": False,
}


def fRunTool(pArguments, pContext):
  """Navigate to one page and return what it says."""
  vUrl = str(pArguments.get("url") or "").strip()
  if not vUrl:
    raise tool_registry.ToolFailure("Which page? Give me a URL.")

  try:
    public_url.fCheckUrlIsPublic(vUrl)
  except public_url.UnsafeUrlError as vError:
    raise tool_registry.ToolFailure("Refused: %s" % (vError,))

  try:
    vPage = browser.fGetPage(pContext.vAgentId)
    vPage.goto(vUrl)
    vSelector = str(pArguments.get("wait_for") or "").strip()
    if vSelector:
      vPage.wait_for_selector(vSelector)
    vText = vPage.inner_text("body")
  except browser.BrowserError as vError:
    raise tool_registry.ToolFailure(str(vError))
  except Exception as vError:
    raise tool_registry.ToolFailure("Could not open %s: %s" % (vUrl, vError))

  return browser.fDescribePage(vPage, vText)
