"""Tool: browser.click - click something on the open page.

By visible text or by CSS selector. Text first in the description, because
that is what a model has: it has just read the page and knows it says "Log
in", not that the button is `button.btn-primary:nth-child(2)`.
"""

from backend.core import browser
from backend.core import tool_registry

cToolName = "browser.click"

cToolDescription = (
  "Click something on the page open in your browser: a link, a button, a "
  "checkbox. Name it by the text you can see on it, or by a CSS selector if "
  "you know one. The page after the click is returned, so you can see what "
  "happened."
)

dToolSchema = {
  "type": "object",
  "properties": {
    "text": {
      "type": "string",
      "description": "The visible text of the thing to click, as you read it "
                     "on the page.",
    },
    "selector": {
      "type": "string",
      "description": "A CSS selector instead, when the text is ambiguous or "
                     "there is none.",
    },
  },
  "required": [],
  "additionalProperties": False,
}

# How long to give the page to settle after a click. A click that navigates
# needs it; one that only ticks a box does not, and this is not worth failing
# over either way.
cSettleMilliseconds = 3000


def fRunTool(pArguments, pContext):
  """Click one thing and return the page that results."""
  vText = str(pArguments.get("text") or "").strip()
  vSelector = str(pArguments.get("selector") or "").strip()
  if not vText and not vSelector:
    raise tool_registry.ToolFailure(
      "Click what? Give me the visible text or a CSS selector.")

  try:
    vPage = browser.fGetPage(pContext.vAgentId)
    if vSelector:
      vPage.click(vSelector)
      vWhat = vSelector
    else:
      # get_by_text finds the innermost element holding it, which is what a
      # person means by "the Log in button" even when the text is inside a
      # span inside the button.
      vPage.get_by_text(vText, exact=False).first.click()
      vWhat = vText

    try:
      vPage.wait_for_load_state("networkidle", timeout=cSettleMilliseconds)
    except Exception:
      # A page that never goes idle - a chat, a ticker - is not a failed
      # click. What is on screen now is the answer either way.
      pass
  except browser.BrowserError as vError:
    raise tool_registry.ToolFailure(str(vError))
  except Exception as vError:
    raise tool_registry.ToolFailure(
      "Could not click %r: %s. Read the page again to see what is on it."
      % (vText or vSelector, vError))

  return browser.fDescribePage(
    vPage, "Clicked %r.\n\n%s" % (vWhat, vPage.inner_text("body")))
