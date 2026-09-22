"""Tool: browser.screenshot - save a picture of the open page.

The model cannot see it. This is for the person: an agent that says "the form
would not submit" is worth far more when there is a PNG of the form next to
the sentence.

It lands in the agent's own downloads directory, which is inside its 0700
home, so the picture of whatever was on screen - a logged-in account, an
invoice - is no more readable to anyone else than the session that produced it.
"""

import os
import re
import time

from backend.core import browser
from backend.core import tool_registry

cToolName = "browser.screenshot"

cToolDescription = (
  "Save a PNG of the open page in your downloads directory. Use image.send "
  "when available to attach it to your reply. You cannot see the image yourself."
)

dToolSchema = {
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "description": "File name, e.g. login-failed.png. Letters, digits, "
                     "dashes and underscores - not a path.",
    },
    "full_page": {
      "type": "boolean",
      "description": "Capture the whole page instead of just what fits on "
                     "the screen.",
    },
  },
  "required": [],
  "additionalProperties": False,
}

# A name, never a path. Checked rather than cleaned: anything that is not a
# plain file name is refused, which is one rule instead of a rule plus
# whatever the cleaning turns out to do.
cNamePattern = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def fBuildFileName(pName):
  """Return the file to write, or raise when the name is not one."""
  vName = str(pName or "").strip()
  if not vName:
    vName = "screenshot-%s.png" % (time.strftime("%Y%m%d-%H%M%S"),)
  if not vName.lower().endswith(".png"):
    vName = "%s.png" % (vName,)
  if not cNamePattern.match(vName) or vName.startswith("."):
    raise tool_registry.ToolFailure(
      "%r is a path, not a file name. Letters, digits, dots, dashes and "
      "underscores." % (pName,))
  return vName


def fRunTool(pArguments, pContext):
  """Save one screenshot into this agent's downloads directory."""
  vFileName = fBuildFileName(pArguments.get("name"))

  try:
    vPage = browser.fGetPage(pContext.vAgentId)
    if not vPage.url or vPage.url == "about:blank":
      raise tool_registry.ToolFailure(
        "There is no page open. Use browser.open first.")
    browser.fEnsureDirectories(pContext.vAgentId)
    vPath = os.path.join(
      browser.fGetDownloadsDir(pContext.vAgentId), vFileName)
    vPage.screenshot(path=vPath, full_page=bool(pArguments.get("full_page")))
    # Chromium writes it with the process umask, which is not 0600. The
    # directory is 0700 so nobody can reach it anyway, but a picture of a
    # logged-in account should not be the one file in an agent's home that
    # relies on its directory rather than on its own mode.
    os.chmod(vPath, 0o600)
  except tool_registry.ToolFailure:
    raise
  except browser.BrowserError as vError:
    raise tool_registry.ToolFailure(str(vError))
  except Exception as vError:
    raise tool_registry.ToolFailure(
      "Could not save the screenshot: %s" % (vError,))

  return ("Saved to %s. Use image.send with this path to attach the PNG to your "
          "reply. Naming the path alone does not send or display the image." % (vPath,))
