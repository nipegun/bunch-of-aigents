"""Tool: image.send - attach a local PNG to this run's reply."""

from backend.core import attachments
from backend.core import tool_registry

cToolName = "image.send"
cToolDescription = (
  "Attach a PNG from your home directory to your reply in the web chat, and "
  "to Telegram when the conversation started there. Use the path from "
  "browser.screenshot. Maximum size: 50 MiB."
)

dToolSchema = {
  "type": "object",
  "properties": {
    "path": {"type": "string", "description": "Absolute path to a PNG in your home, or a path relative to your home."},
    "caption": {"type": "string", "description": "Optional description of the image."},
  },
  "required": ["path"],
  "additionalProperties": False,
}


def fRunTool(pArguments, pContext):
  """Queue the image for the runner to bind to the reply it records."""
  if not isinstance(pArguments.get("path"), str) or not pArguments["path"].strip():
    raise tool_registry.ToolFailure("image.send needs the path of a PNG image.")
  if len(pContext.lAttachments) >= attachments.cMaxPerMessage:
    raise tool_registry.ToolFailure("A reply can attach at most 16 images.")
  try:
    dImage = attachments.fStoreImage(
      pContext.vAgentId, pArguments["path"], pArguments.get("caption", ""))
  except (OSError, ValueError) as vError:
    raise tool_registry.ToolFailure("Could not attach the image: %s" % (vError,))
  pContext.lAttachments.append(dImage)
  return "Attached %s to your reply. The application will deliver the image when you finish answering." % (dImage["name"],)
