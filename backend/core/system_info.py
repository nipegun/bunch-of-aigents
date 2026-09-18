"""What the machine looks like from inside the application.

Everything here is read as the `boa` user, with no privileges: the distribution
name, the kernel, uptime, memory, disk and where the installation's own files
live. Looking at a Linux machine needs no permissions, which is the same reason
the SysAdmin agent can do its job without root.

Used by the Operating System tab in Settings, which answers the questions
somebody asks before opening a terminal: what is this running on, is it running
out of anything, and how big has it got.
"""

import os
import platform
import shutil
import subprocess
import sys
import time

from backend.core import paths

# Commands used to read machine state. Absolute paths, so what runs does not
# depend on an inherited PATH.
cSystemctlCommand = "/usr/bin/systemctl"

lServiceNames = [
  "boa-proxy.service",
  "boa-web.service",
  "boa-exec.service",
  "boa-agent-api.service",
  "cron.service",
]


def fReadOsRelease():
  """Return the distribution's name and version."""
  dRelease = {}
  try:
    with open("/etc/os-release", "r", encoding="utf-8") as vFile:
      for vLine in vFile:
        if "=" not in vLine:
          continue
        vKey, vValue = vLine.strip().split("=", 1)
        dRelease[vKey] = vValue.strip('"')
  except OSError:
    return {"name": "unknown", "version": ""}
  return {
    "name": dRelease.get("PRETTY_NAME") or dRelease.get("NAME") or "unknown",
    "version": dRelease.get("VERSION_ID", ""),
  }


def fReadUptimeSeconds():
  """Return how long the machine has been up, in seconds."""
  try:
    with open("/proc/uptime", "r", encoding="utf-8") as vFile:
      return int(float(vFile.read().split()[0]))
  except (OSError, ValueError, IndexError):
    return 0


def fReadMemory():
  """Return memory figures in megabytes.

  Reports available memory, not free memory. Linux uses spare RAM for cache and
  hands it back on demand, so "free" on a healthy machine is alarmingly small
  and means nothing.
  """
  dMemory = {}
  try:
    with open("/proc/meminfo", "r", encoding="utf-8") as vFile:
      for vLine in vFile:
        vKey, _, vRest = vLine.partition(":")
        lParts = vRest.split()
        if lParts:
          dMemory[vKey] = int(lParts[0])
  except (OSError, ValueError):
    return {"total_mb": 0, "available_mb": 0, "used_percent": 0,
            "swap_total_mb": 0, "swap_used_mb": 0}

  vTotal = dMemory.get("MemTotal", 0) // 1024
  vAvailable = dMemory.get("MemAvailable", 0) // 1024
  vSwapTotal = dMemory.get("SwapTotal", 0) // 1024
  vSwapFree = dMemory.get("SwapFree", 0) // 1024
  return {
    "total_mb": vTotal,
    "available_mb": vAvailable,
    "used_percent": round((vTotal - vAvailable) * 100.0 / vTotal, 1) if vTotal else 0,
    "swap_total_mb": vSwapTotal,
    "swap_used_mb": vSwapTotal - vSwapFree,
  }


def fReadLoad():
  """Return the load averages and the number of cores.

  Both, because one without the other says nothing: a load of 4 is calm on
  eight cores and a fire on one.
  """
  try:
    lLoad = os.getloadavg()
  except OSError:
    lLoad = (0.0, 0.0, 0.0)
  return {
    "one": round(lLoad[0], 2),
    "five": round(lLoad[1], 2),
    "fifteen": round(lLoad[2], 2),
    "cores": os.cpu_count() or 1,
  }


def fReadDisk(pPath):
  """Return disk usage of the filesystem holding one path, in gigabytes."""
  try:
    dUsage = shutil.disk_usage(pPath)
  except OSError:
    return {"total_gb": 0, "free_gb": 0, "used_percent": 0}
  return {
    "total_gb": round(dUsage.total / (1024 ** 3), 1),
    "free_gb": round(dUsage.free / (1024 ** 3), 1),
    "used_percent": round(dUsage.used * 100.0 / dUsage.total, 1) if dUsage.total else 0,
  }


def fReadDirectorySize(pPath):
  """Return the size of a directory tree in megabytes."""
  vTotal = 0
  for vRoot, lDirectories, lFiles in os.walk(pPath, onerror=lambda vError: None):
    for vName in lFiles:
      try:
        vTotal += os.path.getsize(os.path.join(vRoot, vName))
      except OSError:
        continue
  return round(vTotal / (1024 ** 2), 1)


def fReadServices():
  """Return whether each service is active.

  `systemctl is-active` needs no privileges, which is why this can run as the
  web user.
  """
  lStates = []
  for vName in lServiceNames:
    vState = "unknown"
    try:
      vCompleted = subprocess.run(
        [cSystemctlCommand, "is-active", vName],
        capture_output=True, text=True, timeout=5, check=False,
      )
      vState = (vCompleted.stdout or "").strip() or "unknown"
    except (OSError, subprocess.TimeoutExpired):
      vState = "unknown"
    lStates.append({"name": vName, "state": vState, "active": vState == "active"})
  return lStates


def fBuildReport():
  """Return everything the Operating System tab shows."""
  dRelease = fReadOsRelease()
  return {
    "os": {
      "name": dRelease["name"],
      "version": dRelease["version"],
      "kernel": platform.release(),
      "architecture": platform.machine(),
      "hostname": platform.node(),
      "uptime_seconds": fReadUptimeSeconds(),
      "time": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
    },
    "python": {
      "version": platform.python_version(),
      "executable": sys.executable,
    },
    "memory": fReadMemory(),
    "load": fReadLoad(),
    "disk": fReadDisk(paths.fGetBaseDir()),
    "installation": {
      "base_dir": paths.fGetBaseDir(),
      "size_mb": fReadDirectorySize(paths.fGetBaseDir()),
      "https_port": paths.cHttpsPort,
      "http_port": paths.cHttpPort,
    },
    "services": fReadServices(),
  }
