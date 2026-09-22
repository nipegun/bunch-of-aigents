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

# OpenRC's equivalent, for Alpine. `rc-service <name> status` exits 0 when the
# service is started, so the exit code answers the question and the wording of
# its output does not have to be parsed.
cRcServiceCommand = "/sbin/rc-service"

# The seven services this project installs, by their bare name. The suffix is
# added for systemd and left off for OpenRC, because that is the only
# difference between how the two name them.
#
# boa-buzzer and boa-telegram were missing from this list: two of the
# processes the installer sets up could be dead and the Operating System tab
# said nothing at all, which is worse than saying they are down. boa-discord
# went in with the listener it names, on the same day it was written, for the
# same reason.
lBoaServiceNames = [
  "boa-proxy",
  "boa-web",
  "boa-exec",
  "boa-agent-api",
  "boa-buzzer",
  "boa-telegram",
  "boa-discord",
]

# cron is not this project's service but every scheduled run depends on it.
cCronServiceSystemd = "cron.service"
# Alpine has two crons: BusyBox's `crond`, in a stock install, and `dcron`,
# which the installer puts in its place because the daemon needs `crontab -u`.
# Asking about `crond` on a machine running dcron reported cron stopped on a
# healthy installation. The first of these with a service script is the one
# asked about, so the tab names what is actually installed.
lCronServicesOpenRc = ["dcron", "crond"]
cOpenRcInitDir = "/etc/init.d"


def fPickOpenRcCronService(pInitDir=None):
  """Return the OpenRC cron service this machine has, dcron before crond."""
  vInitDir = pInitDir or cOpenRcInitDir
  for vName in lCronServicesOpenRc:
    if os.path.exists(os.path.join(vInitDir, vName)):
      return vName
  return lCronServicesOpenRc[0]


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


# What the installer records about how this installation is served.
cPortsFileName = "ports.conf"

# The two modes the installer offers, and the ports each one listens on.
dPortModes = {
  # Behind the application's own HAProxy, which is behind the machine's.
  "proxied": {"http_port": paths.cHttpPort, "https_port": paths.cHttpsPort},
  # 80 and 443 on every interface, with nothing in front.
  "direct": {"http_port": 80, "https_port": 443},
}


def fReadPortMode():
  """Return the mode the installer recorded, or "proxied".

  The file is written by fRememberPortMode in both installers. Nothing here
  read it, so the Operating System tab reported 11080 and 11443 to somebody
  whose installation was answering on 80 and 443 - a number to paste into a
  browser that does not work.
  """
  vPath = os.path.join(paths.fGetConfigDir(), cPortsFileName)
  try:
    with open(vPath, "r", encoding="utf-8") as vFile:
      for vLine in vFile:
        vLine = vLine.strip()
        if vLine.startswith("mode="):
          vMode = vLine.split("=", 1)[1].strip()
          if vMode in dPortModes:
            return vMode
  except OSError:
    pass
  return "proxied"


def fReadPorts():
  """Return the ports this installation actually serves on."""
  vMode = fReadPortMode()
  dPorts = dict(dPortModes[vMode])
  dPorts["port_mode"] = vMode
  return dPorts


def fDetectInitSystem():
  """Return "systemd", "openrc" or "" for the init this machine is running.

  The RUNNING init, not the binary that happens to be installed. systemd's own
  documentation gives /run/systemd/system as the way to ask - it is the
  directory systemd creates when it boots - and the installers use the same
  test for the same reason.

  This was not asked at all: the report only ever ran `systemctl`, so on
  Alpine every service came back "unknown" and the Operating System tab said
  nothing about a machine where everything was running perfectly well.
  """
  if os.path.isdir("/run/systemd/system"):
    return "systemd"
  if os.path.isdir("/run/openrc") or os.path.exists(cRcServiceCommand):
    return "openrc"
  return ""


def fReadServiceStateSystemd(pName):
  """Return one service's state, asked of systemd."""
  try:
    vCompleted = subprocess.run(
      [cSystemctlCommand, "is-active", pName],
      capture_output=True, text=True, timeout=5, check=False,
    )
  except (OSError, subprocess.TimeoutExpired):
    return "unknown"
  return (vCompleted.stdout or "").strip() or "unknown"


def fReadServiceStateOpenRc(pName):
  """Return one service's state, asked of OpenRC.

  `rc-service <name> status` exits 0 when the service is started, so the exit
  code is the answer and the wording of the output is not parsed.
  """
  try:
    vCompleted = subprocess.run(
      [cRcServiceCommand, pName, "status"],
      capture_output=True, text=True, timeout=5, check=False,
    )
  except (OSError, subprocess.TimeoutExpired):
    return "unknown"
  if vCompleted.returncode == 0:
    return "active"
  vOutput = ((vCompleted.stdout or "") + (vCompleted.stderr or "")).lower()
  if "does not exist" in vOutput or "not found" in vOutput:
    return "not-installed"
  return "inactive"


def fReadServices():
  """Return whether each service is active, on either init system.

  Neither command needs privileges, which is why this can run as the web user.
  """
  vInit = fDetectInitSystem()
  lStates = []

  if vInit == "openrc":
    lNames = list(lBoaServiceNames) + [fPickOpenRcCronService()]
    fReadState = fReadServiceStateOpenRc
  else:
    lNames = ["%s.service" % (vName,) for vName in lBoaServiceNames]
    lNames.append(cCronServiceSystemd)
    fReadState = fReadServiceStateSystemd

  for vName in lNames:
    vState = fReadState(vName) if vInit else "unknown"
    lStates.append({"name": vName, "state": vState,
                    "active": vState == "active"})
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
    "installation": dict(
      {
        "base_dir": paths.fGetBaseDir(),
        "size_mb": fReadDirectorySize(paths.fGetBaseDir()),
      },
      **fReadPorts()
    ),
    "init": fDetectInitSystem() or "unknown",
    "services": fReadServices(),
  }
