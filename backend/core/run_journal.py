"""Per-agent run journal.

An agent process runs as `agent-xxx` and the application database is 0700 owned
by `boa`, so an agent cannot write to it - by design, since a shared writable
database would let any agent rewrite another agent's history.

Each agent therefore keeps its own journal, one JSON object per line, inside
its own home directory:

    /opt/boa/agents/xxx/runs.jsonl

The agent appends to it; the web application reads it through the privileged
daemon. Two properties make this better than a shared table here: an agent can
record what it did even when the web application is down, and a corrupted
journal costs exactly one agent's history.

Lines are appended with a single write() call. On Linux, appends to a file
opened with O_APPEND are atomic below PIPE_BUF, and a journal line is far
smaller than that, so two runs of the same agent cannot interleave a line.
"""

import json
import os
import time

from backend.core import paths

# Journal file name inside each agent home.
cJournalFileName = "runs.jsonl"

# Lines kept when the journal is trimmed. At the default ceiling of 48 runs a
# day this is about six weeks of history.
cMaxJournalLines = 2000

# Journal entry kinds.
cEntryRunStarted = "run_started"
cEntryRunFinished = "run_finished"
cEntryUsage = "usage"
# The main provider would not answer and the run carried on with the backup.
# Worth its own entry: a run that quietly costs a different account money, or
# answers with a different model, is a run whose history has to say so.
cEntryFallback = "fallback"


def fOpenForAppend(pPath):
  """Open a file for appending, creating it 0600 if it does not exist.

  The umask would otherwise create it 0644. The agent home is 0700 so nobody
  else can reach it anyway, but a file that is private on its own survives
  somebody later relaxing the directory.
  """
  vDescriptor = os.open(pPath, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
  return os.fdopen(vDescriptor, "a", encoding="utf-8")


def fGetJournalPath(pAgentId):
  """Return the journal path of one agent."""
  return os.path.join(paths.fGetAgentHome(pAgentId), cJournalFileName)


def fAppendEntry(pAgentId, pEntry):
  """Append one entry to an agent's journal.

  Never raises: an agent that cannot write its journal should still do its
  work. Losing a line of accounting is bad; refusing to run because of it is
  worse.
  """
  dEntry = dict(pEntry)
  dEntry.setdefault("at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
  try:
    with fOpenForAppend(fGetJournalPath(pAgentId)) as vFile:
      vFile.write(json.dumps(dEntry, ensure_ascii=False) + "\n")
  except OSError:
    return False
  return True


def fReadEntries(pAgentId, pLimit=None):
  """Return an agent's journal entries, oldest first.

  Unparseable lines are skipped rather than fatal: a half-written line from a
  killed process must not hide the rest of the history.
  """
  lEntries = []
  try:
    with open(fGetJournalPath(pAgentId), "r", encoding="utf-8") as vFile:
      for vLine in vFile:
        vLine = vLine.strip()
        if not vLine:
          continue
        try:
          lEntries.append(json.loads(vLine))
        except ValueError:
          continue
  except OSError:
    return []
  if pLimit:
    return lEntries[-int(pLimit):]
  return lEntries


def fRecordRunStarted(pAgentId, pRunId, pProvider, pModel):
  """Record the start of a run."""
  return fAppendEntry(pAgentId, {
    "kind": cEntryRunStarted,
    "run_id": pRunId,
    "provider": pProvider,
    "model": pModel,
  })


# What a run answered, kept in the journal. Long enough for the report an
# agent writes at the end of a run, short enough that a journal of a thousand
# runs is still a file somebody can read.
cMaxAnswerLength = 4000


def fRecordRunFinished(pAgentId, pRunId, pStatus, pSteps, pTokens, pError="",
                       pAnswer=""):
  """Record the end of a run, and what it answered.

  The answer is kept because otherwise a scheduled run has nowhere to put it.
  A run started from the chat closes its turn there; a run started by cron
  wrote its report to standard output, which cron mails to a local mailbox
  that on a LAN box nobody reads. The agent did the work, wrote it up, and
  the text was thrown away.

  The journal is the right place for it: it already records what a run cost,
  it is already shown under History, and it is never replayed to the model -
  so keeping the text here costs nothing on the next run.
  """
  return fAppendEntry(pAgentId, {
    "kind": cEntryRunFinished,
    "run_id": pRunId,
    "status": pStatus,
    "steps": pSteps,
    "tokens": pTokens,
    "error": pError or "",
    "answer": str(pAnswer or "")[:cMaxAnswerLength],
  })


def fRecordFallback(pAgentId, pRunId, pProvider, pModel, pError=""):
  """Record that a run switched to the backup model, and why."""
  return fAppendEntry(pAgentId, {
    "kind": cEntryFallback,
    "run_id": pRunId,
    "provider": pProvider,
    "model": pModel,
    "error": str(pError or "")[:500],
  })


def fRecordUsage(pAgentId, pRunId, pProvider, pModel, pPromptTokens,
                 pCompletionTokens):
  """Record what one model call cost."""
  return fAppendEntry(pAgentId, {
    "kind": cEntryUsage,
    "run_id": pRunId,
    "provider": pProvider,
    "model": pModel,
    "prompt_tokens": int(pPromptTokens),
    "completion_tokens": int(pCompletionTokens),
  })


def fCountRunsOn(pAgentId, pDate=None):
  """Return how many runs an agent started on one UTC date.

  This is what enforces max_runs_per_day, and it is read by the agent itself
  from its own journal: the ceiling holds even when nothing else is running.
  """
  vDate = pDate or time.strftime("%Y-%m-%d", time.gmtime())
  vCount = 0
  for dEntry in fReadEntries(pAgentId):
    if dEntry.get("kind") == cEntryRunStarted \
       and str(dEntry.get("at", "")).startswith(vDate):
      vCount += 1
  return vCount


def fSummarizeUsage(pAgentId):
  """Return totals for one agent: runs, failures and tokens."""
  dSummary = {
    "runs": 0,
    "failed_runs": 0,
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "last_run_at": "",
    "last_status": "",
  }
  for dEntry in fReadEntries(pAgentId):
    vKind = dEntry.get("kind")
    if vKind == cEntryRunStarted:
      dSummary["runs"] += 1
      dSummary["last_run_at"] = dEntry.get("at", "")
    elif vKind == cEntryRunFinished:
      dSummary["last_status"] = dEntry.get("status", "")
      if dEntry.get("status") == "failed":
        dSummary["failed_runs"] += 1
    elif vKind == cEntryUsage:
      dSummary["prompt_tokens"] += int(dEntry.get("prompt_tokens", 0))
      dSummary["completion_tokens"] += int(dEntry.get("completion_tokens", 0))
  dSummary["total_tokens"] = dSummary["prompt_tokens"] + dSummary["completion_tokens"]
  return dSummary


def fTrimJournal(pAgentId, pMaxLines=None):
  """Keep only the most recent lines of a journal.

  Called by the agent at the end of a run, so a long-lived agent does not grow
  an unbounded file in a home directory nobody looks at.
  """
  vMaxLines = int(pMaxLines or cMaxJournalLines)
  vJournalPath = fGetJournalPath(pAgentId)
  try:
    with open(vJournalPath, "r", encoding="utf-8") as vFile:
      lLines = vFile.readlines()
  except OSError:
    return False
  if len(lLines) <= vMaxLines:
    return False
  vTempPath = vJournalPath + ".tmp"
  try:
    with open(vTempPath, "w", encoding="utf-8") as vFile:
      vFile.writelines(lLines[-vMaxLines:])
    os.chmod(vTempPath, 0o600)
    os.replace(vTempPath, vJournalPath)
  except OSError:
    try:
      os.unlink(vTempPath)
    except OSError:
      pass
    return False
  return True
