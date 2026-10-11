"""Shared procedures an agent can be given.

    /opt/boa/skills/BackupVerification/SKILL.md

A skill is how a task is done. The system prompt is what an agent is for, and
its memory is what that one agent happened to learn. Neither of those can be
handed to a second agent: the prompt is its identity, and the memory lives
inside a home no other agent can open. A procedure worth writing down once and
giving to three agents had nowhere to live until this.

One directory per skill, so a skill can ship more than prose: a script, a
template, a list of hosts. The directory is world-readable, so an agent that
has been given the skill can run what is in it with bash.run.

Owned by root, like the tools, and for the same reason. What a skill contains
is prepended to the reasoning of an agent that runs unattended at four in the
morning, which makes it exactly as sensitive as system-prompt.md - and that
file already lives in a directory the agent may read and may not write. So
skills are written on the server over SSH, and the web interface only decides
which agent gets which.

None ship with the application: the directory is created empty and everything
in it was written for this installation. A procedure is about THESE hosts,
THIS backup, THIS certificate, so a generic one would be a procedure nobody
follows, charged to every prompt of every run for saying so. An empty
directory here is the normal state of a fresh install.

Only the name and the description of each skill reach the model on every run.
The body is read with skill.read, once, when the agent decides it needs it. A
skill is usually a page or two, and five of those in every system prompt of
every run would cost more than the work they describe.
"""

import os
import re

from backend.core import paths

# The file that holds the procedure. The directory may hold anything else.
cSkillFileName = "SKILL.md"

# The shape of a skill name. It reaches this module from a URL and from an
# agent's info.json, so anything that is not a plain name is refused rather
# than cleaned up - the same rule the agent templates and the themes follow.
# Capitals are allowed here because a skill name is written by a person and
# read by a person: BackupVerification, not backup-verification.
cSkillNamePattern = re.compile(r"^[A-Za-z][A-Za-z0-9-]{0,63}$")

cHeaderRule = "---"

# What one skill.read may return. The same ceiling as bash.run and web.fetch,
# for the same reason: a tool result is part of the conversation from then on,
# and is resent on every remaining call of the run.
cMaxSkillCharacters = 20000


def fIsValidSkillName(pName):
  """Return whether this is a name and not an attempt at a path."""
  return bool(cSkillNamePattern.match(str(pName or "")))


def fGetSkillDir(pName):
  """Return the directory of one skill, or None when the name is not one."""
  if not fIsValidSkillName(pName):
    return None
  return os.path.join(paths.fGetSkillsDir(), str(pName))


def fGetSkillFilePath(pName):
  """Return the SKILL.md path of one skill, or None when the name is not one."""
  vDirectory = fGetSkillDir(pName)
  if vDirectory is None:
    return None
  return os.path.join(vDirectory, cSkillFileName)


def fParseSkill(pText):
  """Turn the text of a SKILL.md into a dictionary.

  The header is optional and the body is returned whole, with its own line
  breaks intact: it is read by a language model and by whoever maintains it,
  and rewrapping it would only make it harder to edit.
  """
  vText = str(pText or "").replace("\r\n", "\n")
  dSkill = {"name": "", "description": "", "body": ""}

  lLines = vText.split("\n")
  vIndex = 0
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
      if vKey in dSkill:
        dSkill[vKey] = vValue.strip()
    vIndex += 1                       # step over the closing rule

  dSkill["body"] = "\n".join(lLines[vIndex:]).strip() + "\n"
  return dSkill


def fListSkillFiles(pName):
  """Return the other files a skill ships, so the agent knows they are there.

  SKILL.md itself is left out: the agent is already reading it. Directories are
  named with a trailing slash rather than walked, because a skill that ships a
  tree is better described by its own prose than by a listing.
  """
  vDirectory = fGetSkillDir(pName)
  if vDirectory is None:
    return []
  try:
    lNames = sorted(os.listdir(vDirectory))
  except OSError:
    return []

  lFiles = []
  for vName in lNames:
    if vName == cSkillFileName:
      continue
    if os.path.isdir(os.path.join(vDirectory, vName)):
      lFiles.append("%s/" % (vName,))
    else:
      lFiles.append(vName)
  return lFiles


def fReadSkill(pName):
  """Return one skill, or None when there is no such skill.

  A missing directory and an unreadable one are the same answer on purpose:
  the caller is telling a model or a browser that the skill is not there, and
  which of the two it was is a question for the server's own logs.
  """
  vPath = fGetSkillFilePath(pName)
  if vPath is None:
    return None
  try:
    with open(vPath, "r", encoding="utf-8") as vFile:
      dSkill = fParseSkill(vFile.read())
  except OSError:
    return None

  dSkill["id"] = str(pName)
  if not dSkill["name"]:
    dSkill["name"] = str(pName)
  dSkill["files"] = fListSkillFiles(pName)
  dSkill["path"] = os.path.dirname(vPath)
  return dSkill


def fSkillExists(pName):
  """Return whether this skill is installed on this server."""
  vPath = fGetSkillFilePath(pName)
  return vPath is not None and os.path.isfile(vPath)


def fListSkills():
  """Return every installed skill, without any body in it.

  The bodies are left out because this is what the web interface lists and
  what validates an agent's skill list, and neither needs a page of prose per
  skill. Ordered by the name a person reads, like the agent templates.
  """
  ldSkills = []
  try:
    lNames = sorted(os.listdir(paths.fGetSkillsDir()))
  except OSError:
    # No skills directory is not an error. It means no agent has any skill,
    # which is what every installation looks like until somebody writes one.
    return []

  for vName in lNames:
    if not fIsValidSkillName(vName):
      continue
    dSkill = fReadSkill(vName)
    if dSkill is None:
      continue
    ldSkills.append({
      "id": dSkill["id"],
      "name": dSkill["name"],
      "description": dSkill["description"],
      "files": dSkill["files"],
    })
  return sorted(ldSkills, key=lambda dSkill: dSkill["name"].lower())


def fSelectInstalledSkills(pSkillNames):
  """Return the names in this list that are actually installed, in order.

  An agent can keep a skill in its info.json after the skill is deleted from
  the server, and being told about a procedure that no longer exists is worse
  than not being told at all.
  """
  lSelected = []
  for vName in (pSkillNames or []):
    vName = str(vName or "")
    if vName in lSelected:
      continue
    if fSkillExists(vName):
      lSelected.append(vName)
  return lSelected


def fBuildPromptSection(pSkillNames):
  """Return the index of an agent's skills, to go in its system prompt.

  Empty when the agent has none, so an agent without skills pays nothing for
  the feature - the same rule the memory section follows.

  Names and descriptions only. The whole point of the index is that the body
  of a skill is fetched once, by an agent that decided it needs it, instead of
  being resent on every call of every run for the rest of its life.
  """
  lNames = fSelectInstalledSkills(pSkillNames)
  if not lNames:
    return ""

  # Short on purpose, like the memory block: this is prepended to a prompt the
  # user may have written in any language, and every extra English sentence
  # here nudges the agent towards answering in English instead of theirs.
  lLines = [
    "## Skills available",
    "",
    "Procedures you have been given. Read one with skill.read before doing the work it covers.",
    "",
  ]
  for vName in lNames:
    dSkill = fReadSkill(vName)
    if dSkill is None:
      continue
    vDescription = dSkill["description"].strip()
    if vDescription:
      lLines.append("- %s: %s" % (dSkill["id"], vDescription))
    else:
      lLines.append("- %s" % (dSkill["id"],))

  return "\n".join(lLines)
