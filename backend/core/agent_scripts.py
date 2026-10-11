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

from contextlib import contextmanager
import hashlib
import os
import re
import secrets
import shlex
import stat
import subprocess

from backend.core import paths

cScriptsDirName = "scripts"

# A plain file name: no directories, no dots leading anywhere.
cScriptNamePattern = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

cMaxScriptBytes = 64 * 1024
cMaxScripts = 50
cConflictError = "The script changed since it was opened. Reload it before saving."
cExistsError = "A script with that name already exists."
cMissingError = "The script no longer exists."

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


def fValidateFileName(pName):
  """Existing files may have Unicode or spaces, but never a path component."""
  if (not isinstance(pName, str) or not pName or pName in (".", "..")
      or "/" in pName or "\\" in pName or len(pName.encode("utf-8")) > 255
      or any(ord(vCharacter) < 32 for vCharacter in pName)
      or pName.startswith(".boa-script-")):
    raise ScriptError("Invalid script file name.")
  return pName


@contextmanager
def fScriptDirectory(pAgentId, pCreate=False):
  """Pin the directory before operating on files; never follow a symlink."""
  vHome = os.open(paths.fGetAgentHome(pAgentId), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
  try:
    if pCreate:
      try:
        os.mkdir(cScriptsDirName, 0o700, dir_fd=vHome)
      except FileExistsError:
        pass
    vDirectory = os.open(cScriptsDirName, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=vHome)
  finally:
    os.close(vHome)
  try:
    yield vDirectory
  finally:
    os.close(vDirectory)


def fEnsureScriptsDir(pAgentId):
  """Called as the agent, including when migrating an existing installation."""
  with fScriptDirectory(pAgentId, True) as vDirectory:
    os.fchmod(vDirectory, 0o700)
  return fGetScriptsDir(pAgentId)


def fScriptMetadata(pName, pStat):
  return {"name": pName, "bytes": pStat.st_size, "modified": pStat.st_mtime_ns // 1000000}


def fListScripts(pAgentId):
  """Regular files only, with sorting metadata but without loading their code."""
  lScripts = []
  try:
    with fScriptDirectory(pAgentId) as vDirectory:
      for vName in sorted(os.listdir(vDirectory)):
        if vName.startswith(".boa-script-"):
          continue
        try:
          dStat = os.stat(vName, dir_fd=vDirectory, follow_symlinks=False)
        except FileNotFoundError:
          continue
        if stat.S_ISREG(dStat.st_mode):
          lScripts.append(fScriptMetadata(vName, dStat))
  except FileNotFoundError:
    pass
  return lScripts


def fReadScriptFile(pDirectory, pName):
  """Read bounded UTF-8 code, rejecting links, devices and changing files."""
  try:
    vDescriptor = os.open(pName, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=pDirectory)
  except FileNotFoundError:
    raise ScriptError(cMissingError)
  with os.fdopen(vDescriptor, "rb") as vFile:
    dBefore = os.fstat(vFile.fileno())
    if not stat.S_ISREG(dBefore.st_mode):
      raise ScriptError("A script must be a regular file.")
    vData = vFile.read(cMaxScriptBytes + 1)
    dAfter = os.fstat(vFile.fileno())
  if len(vData) > cMaxScriptBytes:
    raise ScriptError("That script is larger than %d bytes." % cMaxScriptBytes)
  if (dBefore.st_mtime_ns, dBefore.st_size) != (dAfter.st_mtime_ns, dAfter.st_size):
    raise ScriptError(cConflictError)
  try:
    vContent = vData.decode("utf-8")
  except UnicodeDecodeError:
    raise ScriptError("Script code must be UTF-8 text.")
  if "\x00" in vContent:
    raise ScriptError("Script code must be UTF-8 text.")
  return dict(fScriptMetadata(pName, dAfter), content=vContent,
              revision=hashlib.sha256(vData).hexdigest())


def fReadScript(pAgentId, pName):
  vName = fValidateFileName(pName)
  with fScriptDirectory(pAgentId) as vDirectory:
    return fReadScriptFile(vDirectory, vName)


def fSaveScript(pAgentId, pName, pContent, pMode, pRevision=None):
  """Publish executable code atomically, as the agent, without running it."""
  if pMode not in ("create", "update", "upsert"):
    raise ScriptError("Unknown script write mode.")
  vName = fValidateScriptName(pName) if pMode != "update" else fValidateFileName(pName)
  if not isinstance(pContent, str) or not pContent.strip():
    raise ScriptError("An empty script is not a script.")
  vData = pContent.encode("utf-8")
  if len(vData) > cMaxScriptBytes:
    raise ScriptError("That script is larger than %d bytes." % cMaxScriptBytes)
  if "\x00" in pContent:
    raise ScriptError("Script code must be UTF-8 text.")
  if pMode == "update" and not re.fullmatch(r"[a-f0-9]{64}", str(pRevision or "")):
    raise ScriptError(cConflictError)
  # Keep the agent tool's existing quota. An administrator can manage files
  # created by hand, including homes that already exceed the tool's quota.
  lExisting = fListScripts(pAgentId)
  if (pMode == "upsert" and vName not in {dScript["name"] for dScript in lExisting}
      and len(lExisting) >= cMaxScripts):
    raise ScriptError("This agent already has %d scripts. Delete one first." % cMaxScripts)
  with fScriptDirectory(pAgentId, True) as vDirectory:
    if pMode == "update" and fReadScriptFile(vDirectory, vName)["revision"] != pRevision:
      raise ScriptError(cConflictError)
    vTemporary = ".boa-script-" + secrets.token_hex(16)
    vDescriptor = os.open(vTemporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                           0o700, dir_fd=vDirectory)
    try:
      with os.fdopen(vDescriptor, "wb") as vFile:
        vFile.write(vData)
        vFile.flush()
        os.fchmod(vFile.fileno(), 0o700)
        os.fsync(vFile.fileno())
        dStat = os.fstat(vFile.fileno())
      if pMode == "create":
        try:
          os.link(vTemporary, vName, src_dir_fd=vDirectory, dst_dir_fd=vDirectory,
                    follow_symlinks=False)
        except FileExistsError:
          raise ScriptError(cExistsError)
      else:
        if pMode == "update" and fReadScriptFile(vDirectory, vName)["revision"] != pRevision:
          raise ScriptError(cConflictError)
        os.replace(vTemporary, vName, src_dir_fd=vDirectory, dst_dir_fd=vDirectory)
      return dict(fScriptMetadata(vName, dStat), content=pContent,
                  revision=hashlib.sha256(vData).hexdigest())
    finally:
      try:
        os.unlink(vTemporary, dir_fd=vDirectory)
      except FileNotFoundError:
        pass


def fWriteScript(pAgentId, pName, pContent):
  """Write one script into this agent's scripts directory, 0700."""
  dScript = fSaveScript(pAgentId, pName, str(pContent or ""), "upsert")
  return fGetScriptPath(pAgentId, dScript["name"])


def fBuildPromptSection(pAgentId):
  return (
    "## Your scripts\n\n"
    "Your personal scripts directory is %s (~/scripts/). Save every reusable "
    "script you create there. Before creating a script, look in this directory "
    "for an existing one to reuse or update, using script.list or bash.run when "
    "available. Read a saved script before reusing it and run it from this "
    "directory, using its full path or ./name from ~/scripts/. Scripts added "
    "by the administrator in the Scripts tab are stored here too. Use a "
    "suitable shebang and executable permissions; script.write sets mode 0700. "
    "Scripts run with your own user permissions."
  ) % fGetScriptsDir(pAgentId)


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


def fGetCronLauncher():
  """(interpreter, agent_cron.py): what a scheduled script's line runs."""
  return (os.path.join(paths.fGetBaseDir(), "venv", "bin", "python3"),
          os.path.join(paths.fGetWebAppDir(), "backend", "core", "agent_cron.py"))


def fBuildCronLine(pAgentId, pName, pSchedule, pNote=""):
  """The crontab line that runs one of this agent's scripts.

  It does not run the script: cron starts it as the agent and outside every
  limit a run has. The line runs agent_cron.py, which asks the agent API, and
  the executor starts the script in a scope or cgroup of its own, with a
  run's memory and task ceilings (exec_daemon.fVerbRunScript).
  """
  vSchedule = fValidateSchedule(pSchedule)
  vName = fValidateScriptName(pName)
  vPython, vLauncher = fGetCronLauncher()
  vNote = " ".join(str(pNote or "").split())[:120]
  vComment = "# %s\n" % (vNote,) if vNote else ""
  return "%s%s %s %s --agent-id %s --script %s\n" % (
    vComment, vSchedule, vPython, vLauncher, paths.fNormalizeAgentId(pAgentId), vName)


def fIsRunnerLine(pLine):
  """Whether this line is the one that wakes the agent up.

  Never rewritten from here. An agent that deleted it would go quiet for ever
  and would have no way of noticing.
  """
  return cRunnerMarker in pLine


def fCallCronVerb(pAgentId, pVerb, pParams):
  """One of the agent API's cron verbs, failing as a ScriptError."""
  from backend.core import agent_api_client
  try:
    return agent_api_client.fCallForAgent(pAgentId, pVerb, pParams)
  except Exception as vError:
    raise ScriptError("Cannot change the crontab: %s" % (vError,))


def fAddCronLine(pAgentId, pName, pSchedule, pNote=""):
  """Add a line running one of this agent's own scripts.

  The script has to exist first. A cron line pointing at nothing is a failure
  every few minutes into a log nobody reads.

  What is sent is the script and the schedule, never the line: the agent API
  checks both again and builds the line itself (agent_api.fVerbCronAdd).
  """
  vName = fValidateScriptName(pName)
  if not os.path.isfile(fGetScriptPath(pAgentId, vName)):
    raise ScriptError(
      "There is no script called %r. Write it before scheduling it."
      % (pName,))

  fValidateSchedule(pSchedule)
  dResult = fCallCronVerb(pAgentId, "cron_add", {
    "script": vName, "schedule": pSchedule, "note": pNote or ""})
  return dResult.get("line") or ""


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
  # The program the line runs, which is the first argument. Anywhere among
  # the arguments was enough before, and `/usr/bin/tool <path>` - a line that
  # only mentions the script - counted as running it: cron.remove deleted it.
  if bool(lArguments) and lArguments[0] == str(pPath):
    return True
  # Or the launcher, naming that script of that agent (fBuildCronLine).
  vPython, vLauncher = fGetCronLauncher()
  vScripts = os.path.dirname(str(pPath))
  vAgentId = os.path.basename(os.path.dirname(vScripts))
  return (lArguments[:2] == [vPython, vLauncher]
          and lArguments[2:] == ["--agent-id", vAgentId, "--script", os.path.basename(str(pPath))])


def fMigrateCronText(pAgentId, pText):
  """The crontab with each bare script line rewritten through agent_cron.py.

  A bare line is a schedule and the path of one of this agent's scripts,
  nothing else: what cron.add wrote before scripts started through the
  executor (fBuildCronLine). Anything else is left as it is.
  """
  vScripts = fGetScriptsDir(pAgentId)
  lOut = []
  vChanged = False
  for vLine in str(pText or "").splitlines():
    vStripped = vLine.strip()
    lParts = vStripped.split()
    if not vStripped or vStripped.startswith("#") or fIsRunnerLine(vLine) or not lParts:
      lOut.append(vLine)
      continue
    vCount = 1 if lParts[0].startswith("@") else 5
    if len(lParts) != vCount + 1 or os.path.dirname(lParts[vCount]) != vScripts:
      lOut.append(vLine)
      continue
    try:
      vName = fValidateScriptName(os.path.basename(lParts[vCount]))
    except ScriptError:
      lOut.append(vLine)
      continue
    vPython, vLauncher = fGetCronLauncher()
    lOut.append("%s %s %s --agent-id %s --script %s" % (
      " ".join(lParts[:vCount]), vPython, vLauncher, paths.fNormalizeAgentId(pAgentId), vName))
    vChanged = True
  if not vChanged:
    return pText
  return "\n".join(lOut) + "\n"


def fRemoveCronLines(pAgentId, pName):
  """Remove every line that runs this script. Returns how many went.

  Done by the agent API (agent_api.fVerbCronRemove), which reads the crontab,
  removes those lines with fWithoutCronLines and writes it back: an agent
  names the script and never sends the crontab.
  """
  vName = fValidateScriptName(pName)
  dResult = fCallCronVerb(pAgentId, "cron_remove", {"script": vName})
  return int(dResult.get("removed") or 0)


def fWithoutCronLines(pText, pPath):
  """(the crontab without the lines that run pPath, how many went).

  The comment above a line goes with it: leaving it behind turns the crontab
  into a file of notes about jobs that no longer exist.
  """
  vCurrent = str(pText or "")
  if not vCurrent.strip():
    return vCurrent, 0

  lKept = []
  vRemoved = 0
  lPendingComments = []
  for vLine in vCurrent.splitlines():
    if vLine.strip().startswith("#"):
      lPendingComments.append(vLine)
      continue

    if fLineRunsPath(vLine, pPath) and not fIsRunnerLine(vLine):
      vRemoved += 1
      lPendingComments = []
      continue

    lKept.extend(lPendingComments)
    lPendingComments = []
    lKept.append(vLine)

  lKept.extend(lPendingComments)
  if not vRemoved:
    return vCurrent, 0
  return "\n".join(lKept) + "\n", vRemoved
