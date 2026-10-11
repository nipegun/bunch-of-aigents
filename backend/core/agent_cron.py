#!/usr/bin/env -S PYTHONDONTWRITEBYTECODE=1 python3

"""What a line of an agent's crontab runs to start one of its scripts.

cron starts this as the agent. It does not run the script itself: a script cron
started directly ran outside every limit a run has - no memory ceiling, no
task ceiling, nothing to end what it left behind. It asks the agent API, which
checks that a line of this agent's crontab does schedule that script, and the
executor starts it in a scope or cgroup of its own (exec_daemon.fVerbRunScript).

    <schedule> /opt/boa/venv/bin/python3 /opt/boa/webapp/backend/core/agent_cron.py --agent-id 007 --script check.sh
"""

import argparse
import os
import sys

# cron hands over an environment with almost nothing in it.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.core import agent_api_client
from backend.core import paths


def fMain(plArguments=None):
  vParser = argparse.ArgumentParser(description="Start one of an agent's scripts through the executor.")
  vParser.add_argument("--agent-id", required=True)
  vParser.add_argument("--script", required=True)
  dArguments = vParser.parse_args(plArguments)
  try:
    vAgentId = paths.fNormalizeAgentId(dArguments.agent_id)
    dResult = agent_api_client.fCallForAgent(vAgentId, "cron_fire", {"script": dArguments.script})
  except Exception as vError:
    print("Could not start %s: %s" % (dArguments.script, vError), file=sys.stderr)
    return 1
  if not dResult.get("started"):
    print("%s was not started: %s" % (dArguments.script, dResult.get("reason") or "unknown"), file=sys.stderr)
  return 0


if __name__ == "__main__":
  raise SystemExit(fMain())
