"""Tool: skill.read - read one of the procedures this agent has been given.

The agent already knows which skills it has: the name and one line of each are
in its system prompt from the first call of every run. This is how it gets the
rest, once, when it decides it needs it.

The check on whether it may read a skill happens here, on the server, against
its own info.json - not by asking the prompt nicely. A skill the agent has not
been given is refused even if it guesses the name, which it can, because the
names of the skills it does have are right there in front of it.
"""

import os

from backend.core import skills
from backend.core import tool_registry

cToolName = "skill.read"

cToolDescription = (
  "Read one of the skills listed in your system prompt. A skill is a written "
  "procedure: how a job is done here, step by step. Read it before doing the "
  "work it covers, not after. Some skills ship files of their own - scripts, "
  "templates - and this tells you where they are so you can use them with "
  "bash.run."
)

dToolSchema = {
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "description": "The name of the skill, exactly as it appears in the "
                     "list of skills in your system prompt.",
    },
  },
  "required": ["name"],
  "additionalProperties": False,
}


def fBuildFooter(dSkill):
  """Return the lines naming where the skill lives and what else it ships."""
  lLines = ["", "---", "This skill's own files are in %s" % (dSkill["path"],)]
  if dSkill["files"]:
    lLines.append("It ships: %s" % (", ".join(dSkill["files"]),))
  return "\n".join(lLines)


def fRunTool(pArguments, pContext):
  """Return the body of one skill this agent has been granted."""
  vName = str(pArguments.get("name") or "").strip()
  if not vName:
    raise tool_registry.ToolFailure("Which skill? Name one from your list.")

  lListed = [str(vSkill) for vSkill in
             ((pContext.dAgentInfo or {}).get("skills") or [])]
  lGranted = skills.fSelectInstalledSkills(lListed)

  # Asking for a skill that is in the agent's own list but no longer on the
  # server is not the same as asking for one it never had, and the difference
  # is worth spelling out. An agent can carry the name in its memory from a run
  # that happened before the directory was deleted, and telling it that it was
  # never given anything would be false - it would then say so to the user, or
  # write it down, and the real problem (a skill somebody removed) would never
  # be named by anybody.
  if vName in lListed and vName not in lGranted:
    raise tool_registry.ToolFailure(
      "The skill %r is on your list but is not installed on this server any "
      "more. Do not guess what it said. Tell the user it is missing." % (vName,)
    )

  if vName not in lGranted:
    if lGranted:
      raise tool_registry.ToolFailure(
        "You have not been given the skill %r. Yours are: %s."
        % (vName, ", ".join(lGranted))
      )
    raise tool_registry.ToolFailure(
      "You have not been given any skill. Ask the user to grant you one in "
      "the web interface."
    )

  dSkill = skills.fReadSkill(vName)
  if dSkill is None:
    # Installed a moment ago and unreadable now: deleted between the check and
    # this line, or readable to the check and not to this user.
    raise tool_registry.ToolFailure(
      "The skill %r is granted to you but cannot be read on this server. "
      "Tell the user: it was probably deleted or its permissions changed."
      % (vName,)
    )

  vBody = dSkill["body"].strip()
  if not vBody:
    raise tool_registry.ToolFailure(
      "The skill %r has no content in its %s."
      % (vName, skills.cSkillFileName)
    )

  # Truncated from the end rather than from the middle, unlike a command's
  # output: a procedure is read in order, and its first steps are the ones
  # worth keeping when there is not room for all of them.
  if len(vBody) > skills.cMaxSkillCharacters:
    vBody = "%s\n\n[... cut off here. The whole file is at %s - read the rest with bash.run]" % (
      vBody[:skills.cMaxSkillCharacters].rstrip(),
      os.path.join(dSkill["path"], skills.cSkillFileName),
    )

  return "%s%s" % (vBody, fBuildFooter(dSkill))
