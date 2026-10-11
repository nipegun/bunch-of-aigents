#!/usr/bin/env -S PYTHONDONTWRITEBYTECODE=1 python3

"""The cgroup an agent's work runs in, where systemd is not there to give one.

On Debian a run goes into a transient systemd scope with a memory and a task
ceiling (exec_daemon.fBuildContainedCommand). Alpine has no systemd, and its
runs, library workers and scheduled scripts used to run with neither ceiling.
cgroup v2 gives the same two limits directly, and this file is the two halves
of using it:

  --prepare      at boot, as root (boa-exec's start_pre): creates
                 /sys/fs/cgroup/boa-agents and delegates the memory and pids
                 controllers to it. The root of a container's cgroup
                 namespace may not delegate while processes live in it
                 directly ("no internal processes"), so whatever does is first
                 moved into a leaf of its own, boa-init - what systemd does
                 with init.scope.

  <cgroup> <uid> <gid> -- <command...>
                 for one launch, as root: enters the cgroup the daemon
                 created, THEN drops to the agent's user and its group with no
                 others, and execs the command. In that order, and in this
                 process: a process the daemon moved after starting it would
                 have had time to start children of its own outside, and once
                 it is the agent's it can no longer write cgroup.procs, which
                 is root's - so it cannot leave either.

Standard library only, and run with -I: it starts before anything of the
application is imported, as root.
"""

import errno
import os
import sys

cCgroupRoot = "/sys/fs/cgroup"
cParent = "/sys/fs/cgroup/boa-agents"
cInitLeaf = "/sys/fs/cgroup/boa-init"
lControllers = ["memory", "pids"]


def fRead(pPath):
  with open(pPath, encoding="ascii") as vFile:
    return vFile.read()


def fWrite(pPath, pText):
  with open(pPath, "w", encoding="ascii") as vFile:
    vFile.write(pText)


def fDelegated(pDirectory):
  return set(lControllers) <= set(fRead(os.path.join(pDirectory, "cgroup.subtree_control")).split())


def fEnable(pDirectory):
  fWrite(os.path.join(pDirectory, "cgroup.subtree_control"),
         " ".join("+" + vName for vName in lControllers))


def fPrepare():
  """Make boa-agents ready. Returns 0 even when this machine cannot have it:
  the daemon then launches without cgroups and says so."""
  try:
    sAvailable = set(fRead(os.path.join(cCgroupRoot, "cgroup.controllers")).split())
  except OSError:
    print("No cgroup v2 hierarchy at %s: agent work runs with process limits only." % (cCgroupRoot,))
    return 0
  if not set(lControllers) <= sAvailable:
    print("cgroup v2 does not offer %s here: agent work runs with process limits only."
          % (" and ".join(lControllers),))
    return 0
  try:
    os.makedirs(cParent, mode=0o755, exist_ok=True)
    if not fDelegated(cCgroupRoot):
      try:
        fEnable(cCgroupRoot)
      except OSError as vError:
        if vError.errno != errno.EBUSY:
          raise
        os.makedirs(cInitLeaf, mode=0o755, exist_ok=True)
        for _vAttempt in range(20):
          lPids = fRead(os.path.join(cCgroupRoot, "cgroup.procs")).split()
          if not lPids:
            break
          for vPid in lPids:
            try:
              fWrite(os.path.join(cInitLeaf, "cgroup.procs"), vPid)
            except OSError:
              # Gone already, or a kernel thread, which stays where it is.
              pass
        fEnable(cCgroupRoot)
    if not fDelegated(cParent):
      fEnable(cParent)
  except OSError as vError:
    print("Cannot prepare %s (%s): agent work runs with process limits only." % (cParent, vError))
    return 0
  print("%s is ready: memory and pids are delegated to it." % (cParent,))
  return 0


def fLaunch(plArguments):
  if len(plArguments) < 5 or plArguments[3] != "--":
    raise SystemExit("usage: contain_launch.py <cgroup> <uid> <gid> -- <command...>")
  vCgroup = os.path.realpath(plArguments[0])
  if os.path.dirname(vCgroup) != cParent:
    raise SystemExit("Refusing a cgroup outside %s: %s" % (cParent, plArguments[0]))
  vUid, vGid = int(plArguments[1]), int(plArguments[2])
  if vUid == 0 or vGid == 0:
    raise SystemExit("An agent never runs as root.")
  lCommand = plArguments[4:]
  if not os.path.isabs(lCommand[0]):
    raise SystemExit("The command must be an absolute path: %s" % (lCommand[0],))
  fWrite(os.path.join(vCgroup, "cgroup.procs"), str(os.getpid()))
  os.setgroups([])
  os.setgid(vGid)
  os.setuid(vUid)
  if os.getuid() != vUid or os.geteuid() != vUid or os.getgid() != vGid:
    raise SystemExit("Could not drop to the agent's user.")
  os.execv(lCommand[0], lCommand)


def fMain(plArguments=None):
  lArguments = list(sys.argv[1:] if plArguments is None else plArguments)
  if lArguments == ["--prepare"]:
    return fPrepare()
  fLaunch(lArguments)
  return 1


if __name__ == "__main__":
  raise SystemExit(fMain())
