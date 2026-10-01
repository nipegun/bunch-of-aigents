"""Scripts an agent writes for itself, and the cron lines that run them.

An agent can already do both of these with `bash.run`: its home is its own,
and `crontab` as its own user works. So this is not about granting anything.
It is about a path that can be checked, and that leaves both halves where a
person can read them - the scripts in one directory, the lines that run them
in the crontab the interface already shows.

What is enforced here rather than asked for in a prompt:

  - A script goes in `agents/xxx/scripts/` and nowhere else. The name is
    checked, not cleaned: anything that is not a plain file name is refused,
    so no amount of `../` gets out of that directory.
  - A cron line may only run a script from that directory. A free-form command
    in a crontab is a thing nobody can review, and an agent that wants to run
    one already has `bash.run`.
  - Nothing here ever touches the line that wakes the agent up. An agent that
    deleted it would go quiet for ever, and it would have no way to notice.
  - No schedule more often than every few minutes. A run every minute is not a
    schedule, it is a loop.
"""

import os
import re
import shlex
import subprocess

from backend.core import paths

cScriptsDirName = "scripts"

# A plain file name: no directories, no dots leading anywhere.
cScriptNamePattern = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

cMaxScriptBytes = 64 * 1024
cMaxScripts = 50

# The line the installer wrote to wake this agent. Never rewritten here.
cRunnerMarker = "runner.py"

cCrontabCommand = "/usr/bin/crontab"

# Five fields, and the shorthands cron understands. @reboot is deliberately
# absent: a job that runs at boot runs outside any schedule anyone chose.
lAllowedShorthands = ["@hourly", "@daily", "@midnight", "@weekly", "@monthly",
                      "@yearly", "@annually"]

# The shortest gap a minute field may describe. Anything under this is a loop
# with a cron line in front of it.
cMinimumMinuteStep = 5


class ScriptError(ValueError):
  """Raised when a script or a schedule is not one this will write."""


def fGetScriptsDir(pAgentId):
  """The directory this agent keeps its own scripts in."""
  return os.path.join(paths.fGetAgentHome(pAgentId), cScriptsDirName)


def fValidateScriptName(pName):
  """Return the name if it is a plain file name, or raise.

  Checked rather than sanitised: a name that is not acceptable is refused,
  which is one rule, instead of rewritten, which is a rule plus whatever the
  rewriting turns out to do.
  """
  vName = str(pName or "").strip()
  if not cScriptNamePattern.match(vName):
    raise ScriptError(
      "A script name must be letters, digits, dots, dashes or underscores, "
      "and nothing else: %r is not one." % (pName,)
    )
  if vName in (".", "..") or "/" in vName:
    raise ScriptError("A script name cannot be a path.")
  return vName


def fGetScriptPath(pAgentId, pName):
  """The full path of one of this agent's scripts."""
  return os.path.join(fGetScriptsDir(pAgentId), fValidateScriptName(pName))


def fListScripts(pAgentId):
  """Every script this agent has written, with its size."""
  vDirectory = fGetScriptsDir(pAgentId)
  try:
    lNames = sorted(os.listdir(vDirectory))
  except OSError:
    return []

  lScripts = []
  for vName in lNames:
    vPath = os.path.join(vDirectory, vName)
    if not os.path.isfile(vPath):
      continue
    try:
      lScripts.append({"name": vName, "bytes": os.path.getsize(vPath)})
    except OSError:
      continue
  return lScripts


def fWriteScript(pAgentId, pName, pContent):
  """Write one script into this agent's scripts directory, 0700."""
  vName = fValidateScriptName(pName)
  vContent = str(pContent or "")
  if not vContent.strip():
    raise ScriptError("An empty script is not a script.")
  if len(vContent.encode("utf-8")) > cMaxScriptBytes:
    raise ScriptError(
      "That script is larger than %d bytes." % (cMaxScriptBytes,))

  vDirectory = fGetScriptsDir(pAgentId)
  os.makedirs(vDirectory, mode=0o700, exist_ok=True)

  lExisting = [dScript["name"] for dScript in fListScripts(pAgentId)]
  if vName not in lExisting and len(lExisting) >= cMaxScripts:
    raise ScriptError(
      "This agent already has %d scripts. Delete one first." % (cMaxScripts,))

  vPath = os.path.join(vDirectory, vName)
  # Opened by descriptor so the mode is the one asked for, whatever the umask
  # of whatever started this run happens to be.
  vDescriptor = os.open(vPath, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o700)
  with os.fdopen(vDescriptor, "w", encoding="utf-8") as vFile:
    vFile.write(vContent)
  os.chmod(vPath, 0o700)
  return vPath


def fDeleteScript(pAgentId, pName):
  """Remove one script, and any cron line that ran it.

  Both halves together: a cron line pointing at a script that is gone is a
  failure every few minutes, in a log nobody reads.
  """
  vPath = fGetScriptPath(pAgentId, pName)
  if not os.path.isfile(vPath):
    raise ScriptError("There is no script called %r." % (pName,))
  vRemovedLines = fRemoveCronLines(pAgentId, pName)
  os.remove(vPath)
  return vRemovedLines


def fValidateSchedule(pSchedule):
  """Return a cron schedule this will write, or raise.

  Not a full cron parser: it checks the shape and the one thing worth
  refusing, which is a schedule that fires more often than anybody meant.
  """
  vSchedule = " ".join(str(pSchedule or "").split())
  if not vSchedule:
    raise ScriptError("A cron line needs a schedule.")

  if vSchedule.startswith("@"):
    if vSchedule not in lAllowedShorthands:
      raise ScriptError(
        "%r is not a schedule this accepts. Use one of %s, or five fields."
        % (vSchedule, ", ".join(lAllowedShorthands))
      )
    return vSchedule

  lFields = vSchedule.split(" ")
  if len(lFields) != 5:
    raise ScriptError(
      "A cron schedule has five fields (minute hour day month weekday); "
      "%r has %d." % (vSchedule, len(lFields))
    )
  for vField in lFields:
    if not re.match(r"^[0-9*,/-]+$", vField):
      raise ScriptError("%r is not a cron field." % (vField,))

  # Every field is range-checked, not only the minute. `99 99 99 99 99` used
  # to pass this: it matched the character class, it was not `*` and it was
  # not `*/N`, so nothing looked at it. cron refuses it later, which turns a
  # bad schedule into a failure at write time with cron's own wording.
  for vIndex, vField in enumerate(lFields):
    fCheckFieldRange(vField, lCronFields[vIndex])

  fCheckMinuteField(lFields[0])
  return vSchedule


# Name, lowest and highest value of each of the five fields, in cron's order.
# Weekday allows 7 as well as 0, because both mean Sunday and both are used.
lCronFields = [
  ("minute", 0, 59),
  ("hour", 0, 23),
  ("day of month", 1, 31),
  ("month", 1, 12),
  ("weekday", 0, 7),
]


def fExpandField(pField, pLow, pHigh):
  """Return every value one cron field fires on, as a sorted list.

  Handles the four shapes cron allows in a field: `*`, a number, `a-b`, and
  any of those with `/step` after it, joined by commas.

  Raises ScriptError for a value outside the field's range.
  """
  sValues = set()
  for vPart in str(pField).split(","):
    vPart = vPart.strip()
    if not vPart:
      raise ScriptError("%r has an empty entry in it." % (pField,))

    vStep = 1
    if "/" in vPart:
      vPart, vStepText = vPart.split("/", 1)
      if not vStepText.isdigit() or int(vStepText) < 1:
        raise ScriptError("%r is not a step." % (vStepText,))
      vStep = int(vStepText)

    if vPart in ("*", ""):
      vFrom, vTo = pLow, pHigh
    elif "-" in vPart:
      vFromText, vToText = vPart.split("-", 1)
      if not vFromText.isdigit() or not vToText.isdigit():
        raise ScriptError("%r is not a range." % (vPart,))
      vFrom, vTo = int(vFromText), int(vToText)
    elif vPart.isdigit():
      vFrom = vTo = int(vPart)
    else:
      raise ScriptError("%r is not a cron field." % (pField,))

    if vFrom < pLow or vTo > pHigh or vFrom > vTo:
      raise ScriptError(
        "%s is outside the range %d-%d for this field." % (vPart, pLow, pHigh))
    sValues.update(range(vFrom, vTo + 1, vStep))
  return sorted(sValues)


def fCheckFieldRange(pField, pdSpecification):
  """Raise when one field names a value cron would refuse."""
  vName, vLow, vHigh = pdSpecification
  try:
    fExpandField(pField, vLow, vHigh)
  except ScriptError as vError:
    raise ScriptError("The %s field: %s" % (vName, vError))


def fCheckMinuteField(pMinute):
  """Refuse a minute field that fires more often than every few minutes.

  The minute field is EXPANDED and the real gaps between its values measured,
  rather than the two shapes that happened to be easy to spot being refused by
  name. `*` and `*/1` were caught; `0-59` and `0,1,2` fire exactly as often
  and went straight through, so the protection against a schedule that is a
  loop with a cron line in front of it was a protection against two spellings
  of it.

  The gap from the last run of one hour to the first of the next counts too,
  or `55-59` would look like a schedule that fires five times and rests.
  """
  vMinute = str(pMinute)
  lValues = fExpandField(vMinute, 0, 59)
  if not lValues:
    raise ScriptError("%r never fires." % (pMinute,))

  if len(lValues) == 1:
    return

  lGaps = [lValues[vIndex + 1] - lValues[vIndex]
           for vIndex in range(len(lValues) - 1)]
  # Round the hour: the last minute of one hour to the first of the next.
  lGaps.append(60 - lValues[-1] + lValues[0])

  vSmallest = min(lGaps)
  if vSmallest < cMinimumMinuteStep:
    raise ScriptError(
      "%r runs again after %d minute(s); %d is the shortest gap allowed. Use "
      "*/%d or more." % (pMinute, vSmallest, cMinimumMinuteStep,
                         cMinimumMinuteStep)
    )


# How the crontab is reached.
#
# Not by running `crontab` as the agent. That worked on Debian, where the
# binary is setgid and every user may run it, and not on Alpine: dcron ships
# `crontab` as 4750 root:wheel, so an agent running it gets "Permission
# denied" and cron.add, cron.remove and cron.list behaved differently on the
# two distributions the project installs on. The privileged daemon had already
# worked this out for the web interface and writes with `-u <agent>` as root;
# these three verbs were the half that had not been moved.
#
# The ways to make the direct call work were to put every agent in `wheel` -
# the group that means sudo on most systems - or to loosen the permissions of
# a setuid binary belonging to the distribution. Neither is worth it for a
# file another process can write.
#
# So an agent names a script and a schedule, and the agent API - which runs as
# `boa`, authenticates the caller and validates what it is asked for - has the
# daemon write it. The same shape as channels and mail: the agent says what it
# wants done and never holds the thing that does it.


def fReadCrontab(pAgentId):
  """This agent's crontab as it is installed right now.

  Read through the agent API. See the note above: running `crontab -l` here
  is a call that works on one of the two distributions.
  """
  from backend.core import agent_api_client
  try:
    dResult = agent_api_client.fCallForAgent(
      pAgentId, "cron_read", {})
  except Exception as vError:
    raise ScriptError("Cannot read the crontab: %s" % (vError,))
  return dResult.get("crontab") or ""


def fWriteCrontab(pAgentId, pText):
  """Install this agent's crontab, through the agent API."""
  from backend.core import agent_api_client
  vText = pText if pText.endswith("\n") else pText + "\n"
  try:
    agent_api_client.fCallForAgent(
      pAgentId, "cron_write", {"crontab": vText})
  except Exception as vError:
    raise ScriptError("Cannot write the crontab: %s" % (vError,))
  return True


def fBuildCronLine(pAgentId, pName, pSchedule, pNote=""):
  """The crontab line that runs one of this agent's scripts."""
  vSchedule = fValidateSchedule(pSchedule)
  vPath = fGetScriptPath(pAgentId, pName)
  vNote = " ".join(str(pNote or "").split())[:120]
  vComment = "# %s\n" % (vNote,) if vNote else ""
  return "%s%s %s\n" % (vComment, vSchedule, vPath)


def fIsRunnerLine(pLine):
  """Whether this line is the one that wakes the agent up.

  Never rewritten from here. An agent that deleted it would go quiet for ever
  and would have no way of noticing.
  """
  return cRunnerMarker in pLine


def fAddCronLine(pAgentId, pName, pSchedule, pNote=""):
  """Add a line running one of this agent's own scripts.

  The script has to exist first. A cron line pointing at nothing is a failure
  every few minutes into a log nobody reads.
  """
  vName = fValidateScriptName(pName)
  if not os.path.isfile(fGetScriptPath(pAgentId, vName)):
    raise ScriptError(
      "There is no script called %r. Write it before scheduling it."
      % (pName,))

  vLine = fBuildCronLine(pAgentId, vName, pSchedule, pNote)
  vCurrent = fReadCrontab(pAgentId)
  if vLine.strip().splitlines()[-1] in vCurrent:
    raise ScriptError("That exact line is already in the crontab.")

  vNew = vCurrent if vCurrent.endswith("\n") or not vCurrent else vCurrent + "\n"
  fWriteCrontab(pAgentId, vNew + vLine)
  return vLine.strip()


def fLineRunsPath(pLine, pPath):
  """Whether one crontab line runs exactly this script.

  Compared as a whole argument, never as a substring. `vPath in vLine` matched
  any line whose command merely CONTAINED the path, so asking to unschedule
  `check.sh` also removed the line running `check.sh.backup` - a schedule
  nobody asked to delete, gone without a word.

  The schedule is dropped first and the rest is split the way a shell would,
  so that a quoted path with a space in it is still one argument.
  """
  vLine = str(pLine or "")
  if not vLine.strip() or vLine.strip().startswith("#"):
    return False

  vRest = vLine.strip()
  if vRest.startswith("@"):
    # `@daily /path/to/script`
    lParts = vRest.split(None, 1)
    vRest = lParts[1] if len(lParts) > 1 else ""
  else:
    # Five schedule fields, then the command.
    lParts = vRest.split(None, 5)
    vRest = lParts[5] if len(lParts) > 5 else ""

  try:
    lArguments = shlex.split(vRest)
  except ValueError:
    # An unbalanced quote is not something to guess at. Falling back to the
    # whitespace split keeps the comparison exact even then.
    lArguments = vRest.split()
  return str(pPath) in lArguments


def fRemoveCronLines(pAgentId, pName):
  """Remove every line that runs this script. Returns how many went.

  The comment above a line goes with it: leaving it behind turns the crontab
  into a file of notes about jobs that no longer exist.
  """
  vName = fValidateScriptName(pName)
  vPath = fGetScriptPath(pAgentId, vName)
  vCurrent = fReadCrontab(pAgentId)
  if not vCurrent.strip():
    return 0

  lKept = []
  vRemoved = 0
  lPendingComments = []
  for vLine in vCurrent.splitlines():
    if vLine.strip().startswith("#"):
      lPendingComments.append(vLine)
      continue

    if fLineRunsPath(vLine, vPath) and not fIsRunnerLine(vLine):
      vRemoved += 1
      lPendingComments = []
      continue

    lKept.extend(lPendingComments)
    lPendingComments = []
    lKept.append(vLine)

  lKept.extend(lPendingComments)
  if vRemoved:
    fWriteCrontab(pAgentId, "\n".join(lKept) + "\n")
  return vRemoved
