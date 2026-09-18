"""Example agents, offered when the user creates one.

    backend/agents/examples/<name>.md

One file is one agent worth having, and dropping a file in that directory adds
it to what the "+" button offers - there is no list in the code to update, the
same way there is no list of themes or of tools. That is the point: the useful
part of an agent is its system prompt, and a prompt is text, so a template is a
Markdown file whose body IS the prompt.

The header is the handful of things that are not prose - which tools it needs,
how often it should wake up, what it may spend - written as `key: value` lines
between two `---` rules, the way a Markdown document usually carries its front
matter. Parsed here rather than with a YAML library, because the values are
strings, numbers and comma-separated lists, and the project has no dependency
worth adding for that.

These are STARTING POINTS, not products. Every one of them is created disabled
and with no model, because the user has to choose a provider first; and several
describe work that needs something installed on the machine, which their own
prompt says out loud rather than failing at run time.
"""

import os
import re

# Where the templates live. Inside the deployed code and not under /opt/boa/
# config: they ship with the application and an update is meant to bring new
# ones, unlike the provider catalogues, which the user edits on the server.
#
# In a directory of their own under backend/agents/ rather than loose in it,
# so that the examples this project ships stay one identifiable thing: a
# directory that can be listed, compared between versions and, some day, sit
# next to a second one holding agents somebody else wrote.
lTemplatesDirectoryParts = ["agents", "examples"]

# The same shape as a theme name, and for the same reason: it reaches this
# module from a URL, so anything that is not a plain name is refused rather
# than cleaned up.
cTemplateNamePattern = re.compile(r"^[a-z][a-z0-9-]{0,39}$")

cHeaderRule = "---"

# Header keys holding a number rather than a string.
lNumericKeys = ["max_tokens_per_run", "max_steps_per_run", "timeout_seconds",
                "max_runs_per_day"]

# Header keys holding a comma-separated list.
lListKeys = ["tools", "channels", "skills"]


def fGetTemplatesDirectory():
  """Return the directory holding the example agents."""
  vBackendDir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
  return os.path.join(vBackendDir, *lTemplatesDirectoryParts)


def fIsValidTemplateName(pName):
  """Return whether this is a name and not an attempt at a path."""
  return bool(cTemplateNamePattern.match(str(pName or "")))


def fParseTemplate(pText):
  """Turn one template file into a dictionary.

  The body is returned whole under `system_prompt`, with its own line breaks
  intact: a prompt is stored in full lines and wrapping it to a fixed width
  would only make it harder to edit.
  """
  vText = str(pText or "").replace("\r\n", "\n")
  dTemplate = {"system_prompt": "", "tools": [], "channels": [], "skills": [],
               "enabled": False, "crontab": ""}

  lLines = vText.split("\n")
  vIndex = 0
  # The header is optional; a file that is only a prompt is still a template.
  if lLines and lLines[0].strip() == cHeaderRule:
    vIndex = 1
    while vIndex < len(lLines) and lLines[vIndex].strip() != cHeaderRule:
      vLine = lLines[vIndex]
      vIndex += 1
      if not vLine.strip() or vLine.lstrip().startswith("#"):
        continue
      if ":" not in vLine:
        continue
      vKey, vValue = vLine.split(":", 1)
      vKey = vKey.strip().lower()
      vValue = vValue.strip()

      if vKey in lListKeys:
        dTemplate[vKey] = [vItem.strip() for vItem in vValue.split(",")
                           if vItem.strip()]
      elif vKey in lNumericKeys:
        try:
          dTemplate[vKey] = int(vValue)
        except ValueError:
          # A number nobody can read is left out rather than guessed at, so
          # the agent is created with the ordinary default.
          continue
      elif vKey == "enabled":
        dTemplate[vKey] = vValue.lower() in ("true", "yes", "1")
      else:
        dTemplate[vKey] = vValue
    vIndex += 1                       # step over the closing rule

  dTemplate["system_prompt"] = "\n".join(lLines[vIndex:]).strip() + "\n"
  return dTemplate


def fReadTemplate(pName):
  """Return one template, or None when there is no such file."""
  if not fIsValidTemplateName(pName):
    return None
  vPath = os.path.join(fGetTemplatesDirectory(), "%s.md" % (pName,))
  try:
    with open(vPath, "r", encoding="utf-8") as vFile:
      dTemplate = fParseTemplate(vFile.read())
  except OSError:
    return None
  dTemplate["id"] = pName
  dTemplate.setdefault("name", pName)
  dTemplate.setdefault("description", "")
  return dTemplate


def fListTemplates():
  """Return every installed template, ordered by the name the user sees.

  Ordered by the visible name and not by the file name, for the same reason
  the theme list is: the two orders do not always agree, and the list is read
  by a person.
  """
  ldTemplates = []
  try:
    lFileNames = sorted(os.listdir(fGetTemplatesDirectory()))
  except OSError:
    # No templates directory is not an error: it means the "+" button offers
    # an empty agent, which is what it used to do anyway.
    return []

  for vFileName in lFileNames:
    if not vFileName.endswith(".md"):
      continue
    dTemplate = fReadTemplate(vFileName[:-3])
    if dTemplate is not None:
      ldTemplates.append(dTemplate)
  return sorted(ldTemplates, key=lambda dTemplate: dTemplate["name"].lower())
