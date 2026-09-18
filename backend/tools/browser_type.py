"""Tool: browser.type - fill a field on the open page.

The half of a form that browser.click cannot do. `submit` presses Enter after
typing, which is how most search boxes and login forms are meant to be used
and saves a second call.
"""

from backend.core import browser
from backend.core import tool_registry

cToolName = "browser.type"

cToolDescription = (
  "Type into a field on the page open in your browser. Name the field by a "
  "CSS selector, or by its label or placeholder text. Set submit to press "
  "Enter afterwards, which is how a search box or a login form expects to be "
  "used."
)

dToolSchema = {
  "type": "object",
  "properties": {
    "selector": {
      "type": "string",
      "description": "CSS selector of the field, e.g. input[name=q].",
    },
    "label": {
      "type": "string",
      "description": "Its label or placeholder text instead, as you read it "
                     "on the page.",
    },
    "text": {
      "type": "string",
      "description": "What to type into it. Replaces whatever is there.",
    },
    "submit": {
      "type": "boolean",
      "description": "Press Enter after typing.",
    },
  },
  "required": ["text"],
  "additionalProperties": False,
}

cSettleMilliseconds = 3000


def fRunTool(pArguments, pContext):
  """Fill one field, optionally submitting it."""
  vText = str(pArguments.get("text") or "")
  vSelector = str(pArguments.get("selector") or "").strip()
  vLabel = str(pArguments.get("label") or "").strip()
  if not vSelector and not vLabel:
    raise tool_registry.ToolFailure(
      "Type into what? Give me a CSS selector or the field's label.")

  try:
    vPage = browser.fGetPage(pContext.vAgentId)
    if vSelector:
      vField = vPage.locator(vSelector).first
    else:
      # Label first, placeholder second: both are what somebody reading the
      # page would call the field, and a form usually has one or the other.
      vField = vPage.get_by_label(vLabel, exact=False).first
      if vField.count() == 0:
        vField = vPage.get_by_placeholder(vLabel, exact=False).first

    vField.fill(vText)
    vWhat = vSelector or vLabel

    if pArguments.get("submit"):
      vField.press("Enter")
      try:
        vPage.wait_for_load_state("networkidle", timeout=cSettleMilliseconds)
      except Exception:
        pass
  except browser.BrowserError as vError:
    raise tool_registry.ToolFailure(str(vError))
  except Exception as vError:
    raise tool_registry.ToolFailure(
      "Could not type into %r: %s. Read the page again to see what fields it "
      "has." % (vSelector or vLabel, vError))

  # What was typed is not echoed back. It may be a password the user handed
  # over for this one step, and a tool result is in the conversation for the
  # rest of the run.
  return browser.fDescribePage(
    vPage, "Typed into %r.\n\n%s" % (vWhat, vPage.inner_text("body")))
