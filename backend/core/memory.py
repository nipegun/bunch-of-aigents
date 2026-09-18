"""Per-agent long-term memory.

    /opt/boa/agents/xxx/memory.md

An agent wakes up with no recollection of anything: each run is a fresh
process, and the chat only replays the last few turns. This file is what
survives. The agent writes to it what it wants its future self to know, and
every run starts with it loaded.

The agent writes it itself, as its own user - no daemon, no socket - because
its home is the one place it can already write. The web application reads and
edits it through the privileged daemon, like everything else in that directory.

Markdown rather than JSON because the reader is a language model and the writer
is a language model, and neither benefits from quoting rules.
"""

import os
import time

from backend.core import paths

cMemoryFileName = "memory.md"

# The whole file is sent to the model on every single run, so its size is a
# recurring cost, not a one-off. This ceiling is about 2000 tokens: enough for
# what an agent actually needs to carry forward, small enough that carrying it
# is not the expensive part of the run.
cMaxMemoryCharacters = 8000

# When the file passes this, the agent is told to tidy it up rather than being
# cut off mid-sentence later.
cMemoryWarningCharacters = 6000

cDefaultMemoryHeader = """# Memory

What I want to remember between runs. Everything here is loaded at the start of
every run, and everything here is paid for on every model call, so it is worth
keeping short and worth deleting what stopped being true.
"""


def fGetMemoryPath(pAgentId):
  """Return the memory file path of one agent."""
  return os.path.join(paths.fGetAgentHome(pAgentId), cMemoryFileName)


def fRead(pAgentId):
  """Return an agent's memory, or an empty string when it has none."""
  try:
    with open(fGetMemoryPath(pAgentId), "r", encoding="utf-8") as vFile:
      return vFile.read()
  except OSError:
    return ""


def fWrite(pAgentId, pContent):
  """Replace an agent's memory, atomically.

  Written to a temporary file and renamed, so an agent that dies mid-write
  keeps the memory it had rather than ending up with half of a new one.
  """
  vContent = str(pContent or "")
  if len(vContent) > cMaxMemoryCharacters:
    vContent = vContent[:cMaxMemoryCharacters] + "\n\n[truncated]\n"

  vMemoryPath = fGetMemoryPath(pAgentId)
  vTempPath = vMemoryPath + ".tmp"
  try:
    vDescriptor = os.open(vTempPath, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(vDescriptor, "w", encoding="utf-8") as vFile:
      vFile.write(vContent)
    os.replace(vTempPath, vMemoryPath)
  except OSError as vError:
    try:
      os.unlink(vTempPath)
    except OSError:
      pass
    raise RuntimeError("Cannot write the memory of agent %s: %s"
                       % (pAgentId, vError))
  return True


def fAppend(pAgentId, pNote):
  """Add one dated note to an agent's memory.

  Returns the new size, so the caller can tell the agent when it is getting
  close to the ceiling - which is more useful than truncating silently.
  """
  vNote = str(pNote or "").strip()
  if not vNote:
    raise ValueError("There is nothing to remember: the note is empty")

  vExisting = fRead(pAgentId)
  if not vExisting.strip():
    vExisting = cDefaultMemoryHeader

  vStamp = time.strftime("%Y-%m-%d", time.gmtime())
  vNew = "%s\n- %s: %s\n" % (vExisting.rstrip("\n"), vStamp, vNote)
  fWrite(pAgentId, vNew)
  return len(vNew)


def fEnsureExists(pAgentId):
  """Create an empty memory file if the agent has none."""
  if os.path.exists(fGetMemoryPath(pAgentId)):
    return False
  fWrite(pAgentId, cDefaultMemoryHeader)
  return True


def fBuildPromptSection(pAgentId):
  """Return the memory as a block to put in front of the system prompt.

  Empty when there is nothing worth sending: an agent whose memory is only the
  default header should not pay to be told that on every call.
  """
  vContent = fRead(pAgentId).strip()
  if not vContent or vContent == cDefaultMemoryHeader.strip():
    return ""

  # Short on purpose. This block is prepended to a prompt the user may have
  # written in any language, and every extra English sentence here nudges the
  # agent towards answering in English instead of theirs.
  lLines = [
    "## Your memory",
    "",
    "What you wrote down in previous runs. Correct it or delete from it when it stops being true.",
    "",
    vContent,
  ]

  if len(vContent) > cMemoryWarningCharacters:
    lLines.append("")
    lLines.append(
      "Your memory is getting long, and all of it is sent on every call. Use memory.replace to cut it down to what still matters."
    )

  return "\n".join(lLines)
