#!/usr/bin/env -S PYTHONDONTWRITEBYTECODE=1 python3

"""RAG queue poller, running as boa; the executor launches workers as each agent."""

import time

from backend.core import agents, exec_client


def fMain():
  vOffset=0
  while True:
    try:
      lAgents=agents.fListIndexedAgents()
      if lAgents:
        vOffset%=len(lAgents)
        for dAgent in lAgents[vOffset:]+lAgents[:vOffset]:
          exec_client.fRag(dAgent["id"],"work")
        vOffset+=1
    except Exception as vError:
      print("RAG scheduling failed: %s"%vError,flush=True)
    time.sleep(5)


if __name__=="__main__":
  fMain()
