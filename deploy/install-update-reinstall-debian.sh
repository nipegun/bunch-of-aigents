#!/bin/bash

set -euo pipefail

# ------------------------------------------------------------------------------
# Bunch of AIgents - Debian installer
#
# Usage:
#   ./install-update-reinstall-debian.sh --install   [--email a@b.c] [--yes]
#   ./install-update-reinstall-debian.sh --update
#   ./install-update-reinstall-debian.sh --reinstall [--email a@b.c] [--yes]
#
# The script is idempotent: running it twice with the same flag leaves the
# system in the same state. It can be piped straight from the network:
#   curl -fsSL <raw-url> | bash -s -- --install --email a@b.c
# ------------------------------------------------------------------------------

# Constants
  cAppUser="boa"
  cAppGroup="boa"
  cBaseDir="/opt/boa"
  cWebAppDir="/opt/boa/webapp"
  cVenvDir="/opt/boa/venv"
  # Built beside the running one and switched in, so that a pip failure is an
  # update that did not happen rather than an installation that is down.
  cVenvNewDir="/opt/boa/venv.new"
  cVenvPreviousDir="/opt/boa/venv.previous"
  cWebAppPreviousDir="/opt/boa/webapp.previous"
  # pip itself, pinned: `--upgrade pip` with no version meant two updates of
  # the same code could resolve their dependencies differently.
  cPipVersion="25.2"
  # The oldest interpreter this code runs on. Implicit namespace
  # packages, so there is no __init__.py under backend/ to fall back on.
  cMinimumPythonVersion="3.13"
  # How many times to ask the application for the login page before calling
  # the update failed, and how long to wait between tries. HAProxy's health
  # check takes a few seconds to mark the backend up again after a restart,
  # so a 503 measured straight away is not a failure.
  cVerifyAttempts="15"
  cVerifySleepSeconds="2"
  cAgentsDir="/opt/boa/agents"
  # Each agent's protected configuration, OUTSIDE its home: every
  # directory on the way here belongs to root, so an agent cannot rename
  # its own drawer aside and put a substitute in its place.
  cAgentsConfigDir="/opt/boa/agents-config"
  cToolsDir="/opt/boa/tools"
  cSkillsDir="/opt/boa/skills"
  cConfigDir="/opt/boa/config"
  cChannelsDir="/opt/boa/config/channels"
  cProvidersDir="/opt/boa/config/providers"
  cApiKeysDir="/opt/boa/config/apikeys"
  # Where those keys used to live, kept only so that an update can move them.
  cLegacyApiKeysDir="/opt/boa/config/keys"
  cDbDir="/opt/boa/db"
  cKanbanDir="/opt/boa/kanban"
  cCertsDir="/opt/boa/certificates"
  cLogsDir="/opt/boa/logs"
  # Where logrotate is told about the files under cLogsDir.
  cLogRotateConfig="/etc/logrotate.d/boa"
  cManagerId="000"
  cManagerUser="agent-000"
  cSysAdminId="001"
  cSysAdminUser="agent-001"
  cRepoUrl="https://github.com/nipegun/bunch-of-aigents"
  # The branch this project lives on. GitHub still answers for "master" by
  # redirecting it here, because the branch was renamed, but a redirect is not
  # something to build on: it goes away the day a real master branch exists, and
  # `--repo-url file://...` - what the installers are tested with - has nobody to
  # redirect it.
  cRepoBranch="main"
  # One file for the whole installation: what happened, and the password it
  # generated. It used to be two, /root/app-web-install.log and
  # /root/app-web-credentials.txt, and two files in two places is two things
  # to find at three in the morning. It lives under the application's own tree
  # because that is where somebody looks for anything to do with it.
  #
  # root:root 0600 inside a directory the web user owns: `boa` can unlink it,
  # which is what owning the directory means, and cannot read the password in
  # it. Agents are not in the boa group and the directory is 0750, so they
  # cannot even enter.
  cInstallLog="/opt/boa/logs/install.log"
  # Written when an installation, a reinstall or an update has finished and
  # answered. Its absence over a tree that has the code and the user is an
  # installation that died halfway, which --install picks up again.
  cInstalledMarker="/opt/boa/installed"
  # Where the two files used to be. Kept only so that an update can move what
  # is in them into the new one and take them away.
  cLegacyInstallLog="/root/app-web-install.log"
  cLegacyCredentialsFile="/root/app-web-credentials.txt"
  cHttpPort="11080"
  cHttpsPort="11443"
  cPortsFile="/opt/boa/config/ports.conf"
  cPlaywrightDir="/opt/boa/playwright"
  cBrowserFile="/opt/boa/config/browser.conf"
  cMachineProxyConfig="/etc/haproxy/haproxy.cfg"
  # The line that tells our own machine-proxy configuration from somebody
  # else's, so an update never overwrites a file we did not write.
  cMachineProxyMarker="BOA-MANAGED"

# Runtime variables
  vAction=""
  # --backup writes here; --restore reads from here.
  vBackupPath=""
  vRestorePath=""
  # Where a backup is assembled, or a restore unpacked, until it is done.
  vStagingDir=""
  vEmail=""
  vAssumeYes="no"
  vTempDir=""
  vPassword=""
  # Where the output of everything this runs is copied from, and the tee that
  # copies it. See fStartCapturingOutput.
  vCaptureDir=""
  vCapturePipe=""
  vTeePid=""
  vSourceDir=""
  # "proxied": 11080/11443 on localhost, behind the machine's own HAProxy.
  # "direct":  80/443 on every interface, with nothing in front.
  vPortMode=""
  # "yes": download Chromium, so agents can be given the browser tools. The
  #        default, because reading a page without being able to use it is
  #        half of what an agent is usually asked for.
  # "no":  do not. The tools stay listed and say what to run.
  vBrowser=""
  # "yes" from the moment an update stops the services until the new version
  # has answered, or the previous one has been put back. fCleanup reads it: an
  # update that dies in between would otherwise leave the machine stopped,
  # with the new code in place and nobody putting the old one back.
  vUpdateSwitched=""

fCleanup() {
  local vExitCode=$?
  if [ -n "${vTempDir}" ] && [ -d "${vTempDir}" ]; then
    rm -rf "${vTempDir}"
  fi
  # `:-` and not a bare expansion: this runs in the EXIT trap under `set -u`,
  # and a variable that happens to be unset there must not end the cleanup -
  # and the rollback that follows it - as a second failure.
  if [ -n "${vStagingDir:-}" ] && [ -d "${vStagingDir:-}" ]; then
    rm -rf "${vStagingDir}"
  fi
  # An update that died between stopping the services and the new version
  # answering. Until this existed, fRollBack ran only when the final curl
  # failed: a fDie anywhere in the dozen steps before it - a missing
  # certificate file, a proxy configuration HAProxy would not parse, a unit
  # that would not install - left the services stopped, the new code in
  # place, and webapp.previous on disk with nobody putting it back. The
  # message said what had failed and not one word about the machine being
  # down.
  if [ "${vExitCode}" -ne 0 ] && [ "${vUpdateSwitched}" = "yes" ]; then
    fLog "The update failed after the services were stopped. Putting the previous version back."
    fRollBack
  fi
  if [ "${vExitCode}" -ne 0 ]; then
    fLog "Exited with code ${vExitCode}. See ${cInstallLog} for details."
  fi
  # After the last fLog, so that line reaches the file, and before the
  # directory holding the pipe is removed.
  fStopCapturingOutput
  if [ -n "${vCaptureDir}" ] && [ -d "${vCaptureDir}" ]; then
    rm -rf "${vCaptureDir}"
  fi
  return 0
}

trap fCleanup EXIT

fLog() {
  local vMessage="$1"
  local vStamp
  vStamp=$(date '+%Y-%m-%d %H:%M:%S')
  echo "[${vStamp}] ${vMessage}"

  # Once the capture is running, that echo is ALREADY on its way into the log:
  # fStartCapturingOutput points this shell's stdout at a tee that appends to
  # it. Writing the line again below put every one of them in the file twice,
  # which is how a 90-line installation produced a 185-line log.
  if [ -n "${vTeePid}" ]; then
    chmod 0600 "${cInstallLog}" 2> /dev/null || true
    return 0
  fi

  # The directory is made here rather than assumed, because this log lives
  # inside the tree the installer is building: on a first install it does not
  # exist yet when the first line is written, and a --reinstall deletes it
  # halfway through. fCreateDirectoryTree sets the modes afterwards; what
  # matters at this point is that no line is lost.
  local vLogDirectory
  vLogDirectory=$(dirname "${cInstallLog}")
  if [ ! -d "${vLogDirectory}" ]; then
    mkdir -p "${vLogDirectory}" 2> /dev/null || true
  fi
  if [ -w "${vLogDirectory}" ]; then
    echo "[${vStamp}] ${vMessage}" >> "${cInstallLog}"
    # The password ends up in this file, so it is shut before anything is
    # written into it and every time, not once at the end.
    chmod 0600 "${cInstallLog}" 2> /dev/null || true
  fi
}

fDie() {
  local vMessage="$1"
  fLog "ERROR: ${vMessage}"
  exit 1
}

fHasSystemd() {
  # Whether systemd is the init of the RUNNING system, which is a different
  # question from whether systemctl is installed. In a container built with
  # `docker build`, in a chroot and in a machine whose PID 1 is sshd, the
  # binary is there and every command that needs the bus - daemon-reload,
  # start, restart, `enable --now` - answers "System has not been booted with
  # systemd as init system (PID 1). Can't operate."
  #
  # /run/systemd/system is the directory systemd itself creates when it boots,
  # and testing for it is what systemd's own documentation gives as the way to
  # ask this question from a script.
  [ -d /run/systemd/system ]
}

fHasTty() {
  # Whether there is a terminal to ask the user on. `[ -r /dev/tty ]` is not
  # that test: the device node is there and readable by mode on every system,
  # so the test passes inside an ssh command with no pty, and the `read` that
  # follows then dies with ENXIO - a process with no controlling terminal
  # cannot open /dev/tty at all. Measured: it turned an installer run over
  # `ssh host ./installer` into an unreadable error mid-way through.
  #
  # So the file is opened for real - in a SUBSHELL, because a failed
  # redirection on `exec` kills a non-interactive shell outright, and the
  # first version of this function took the whole installer down with it
  # instead of returning "no terminal here". The subshell dies, the `if`
  # reads its exit status, and the descriptor it opened goes with it.
  if ( exec 9< /dev/tty ) 2> /dev/null; then
    return 0
  fi
  return 1
}

fIsContainer() {
  # Only used to decide which of two pieces of advice to print, so a guess is
  # good enough and a wrong guess costs nothing.
  if [ -f /.dockerenv ] || [ -f /run/.containerenv ]; then
    return 0
  fi
  if [ -r /proc/1/cgroup ] && grep -qE 'docker|lxc|containerd|kubepods' /proc/1/cgroup 2> /dev/null; then
    return 0
  fi
  return 1
}

fRequireSystemd() {
  # Checked before anything is installed, because everything this installer
  # sets up is started and kept alive by systemd: seven units, the machine's
  # HAProxy and cron. On a machine where systemd is not PID 1 the installation
  # would complete, report success and serve nothing - which is what used to
  # happen, quietly, in a container.
  #
  # It is refused rather than worked around: starting the daemons by hand here
  # would give an installation that dies with the shell that ran it and never
  # comes back after a reboot, and calling that "installed" helps nobody.
  if fHasSystemd; then
    return 0
  fi

  local vPidOne="unknown"
  if [ -r /proc/1/comm ]; then
    vPidOne=$(cat /proc/1/comm)
  fi

  fLog "systemd is not running on this machine: PID 1 is '${vPidOne}', not systemd."
  fLog "This installer writes systemd units, and without systemd nothing it installs"
  fLog "can be started, supervised or brought back after a reboot."
  fLog ""
  if fIsContainer; then
    fLog "This is a container. To turn it into one this can be installed on:"
    fLog ""
    fLog "  1. Install systemd inside it:"
    fLog "       apt-get update"
    fLog "       apt-get install -y systemd systemd-sysv dbus dbus-user-session"
    fLog ""
    fLog "  2. Create the container again with /sbin/init as its command, because"
    fLog "     a container that is already running cannot change its PID 1:"
    fLog "       docker run -d --name <name> \\"
    fLog "         --privileged --cgroupns=host \\"
    fLog "         --tmpfs /run --tmpfs /run/lock \\"
    fLog "         -v /sys/fs/cgroup:/sys/fs/cgroup:rw \\"
    fLog "         -p <ssh>:22 -p <http>:80 -p <https>:443 \\"
    fLog "         <image> /sbin/init"
    fLog ""
    fLog "  3. Start it, and run this installer again inside it."
  else
    fLog "Boot this system with systemd as PID 1 and run this installer again."
    fLog "If this is a chroot, run the installer on the booted machine instead."
  fi
  fLog ""
  fDie "systemd is not running. Nothing has been installed."
}

fEnableUnit() {
  # Enabling is what makes a unit come back after a reboot, and it is a
  # separate step from starting it: `enable` only writes symlinks under
  # /etc/systemd/system, `restart` is what talks to the running systemd.
  # Failing to enable is said out loud and is not fatal - the installation
  # still works today, it just would not survive the next boot - while failing
  # to start is, which is why the two are not one function.
  if systemctl enable "$@" > /dev/null 2>&1; then
    return 0
  fi
  fLog "WARNING: could not enable $*. That will not start at the next boot."
  return 0
}

fRestartUnit() {
  # Start or restart one unit, and fail the installation if it does not come
  # up. Before this, every systemctl call here was a bare command whose exit
  # code nothing read, so an installation whose services never started still
  # ended with "Installation finished".
  local vUnit="$1"
  if systemctl restart "${vUnit}"; then
    return 0
  fi
  systemctl status "${vUnit}" --no-pager --lines=20 || true
  fDie "The ${vUnit} service would not start. The output above says why."
}

fShowHelp() {
  echo "Bunch of AIgents - Debian installer"
  echo ""
  echo "Usage: $0 <--install|--update|--reinstall|--backup [file]|--restore <file>> [options]"
  echo ""
  echo "Mandatory flags (pick exactly one):"
  echo "  --install     Install from scratch. Does nothing if already installed."
  echo "  --update      Update code and dependencies, keeping data and agents."
  echo "  --reinstall   Wipe the whole installation, agents included, then install again."
  echo "  --backup [file]    Write everything this installation is - databases, keys,"
  echo "                     certificates, agents and their homes, skills, tools -"
  echo "                     into one archive. Default: /root/boa-backup-<date>.tar.gz."
  echo "  --restore <file>   Put a --backup archive in place of what this machine has."
  echo "                     On a new machine: --install first, then this."
  echo ""
  echo "Options:"
  echo "  --email <address>  Main email address, the only login of the web application."
  echo "  --repo-url <url>   Repository to download the code from. Default: ${cRepoUrl}"
  echo "  --branch <branch>  Branch to download. Default: ${cRepoBranch}"
  echo "  --ports <mode>     How the application is served. One of:"
  echo "                       proxied  11080/11443 on localhost, with an HAProxy"
  echo "                                in front of it on 80 and 443 (default)."
  echo "                       direct   80 and 443 served by the application"
  echo "                                itself, with nothing in front."
  echo "  --browser <yes|no> Whether to install Chromium (about 600 MB), which is"
  echo "                     what lets an agent use a site rather than only read"
  echo "                     one. Installed by default. Asked once and remembered."
  echo "  --yes              Do not ask for confirmation on destructive operations."
  echo "  --help             Show this help."
}

fParseArguments() {
  if [ "$#" -eq 0 ]; then
    fShowHelp
    exit 1
  fi
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --install)
        if [ -n "${vAction}" ]; then
          fDie "Only one of --install, --update, --reinstall, --backup or --restore may be given."
        fi
        vAction="install"
        shift
        ;;
      --update)
        if [ -n "${vAction}" ]; then
          fDie "Only one of --install, --update, --reinstall, --backup or --restore may be given."
        fi
        vAction="update"
        shift
        ;;
      --reinstall)
        if [ -n "${vAction}" ]; then
          fDie "Only one of --install, --update, --reinstall, --backup or --restore may be given."
        fi
        vAction="reinstall"
        shift
        ;;
      --backup)
        if [ -n "${vAction}" ]; then
          fDie "Only one of --install, --update, --reinstall, --backup or --restore may be given."
        fi
        vAction="backup"
        shift
        # An optional value, the file to write. Anything that looks like a
        # flag is the next argument, not a file name.
        if [ "$#" -gt 0 ] && [ "${1#--}" = "$1" ]; then
          vBackupPath="$1"
          shift
        fi
        ;;
      --restore)
        if [ -n "${vAction}" ]; then
          fDie "Only one of --install, --update, --reinstall, --backup or --restore may be given."
        fi
        if [ "$#" -lt 2 ]; then
          fDie "The --restore flag needs a value: the archive a --backup wrote."
        fi
        vAction="restore"
        vRestorePath="$2"
        shift 2
        ;;
      --email)
        if [ "$#" -lt 2 ]; then
          fDie "The --email flag needs a value."
        fi
        vEmail="$2"
        shift 2
        ;;
      --repo-url)
        if [ "$#" -lt 2 ]; then
          fDie "The --repo-url flag needs a value."
        fi
        cRepoUrl="$2"
        shift 2
        ;;
      --branch)
        if [ "$#" -lt 2 ]; then
          fDie "The --branch flag needs a value."
        fi
        cRepoBranch="$2"
        shift 2
        ;;
      --ports)
        if [ "$#" -lt 2 ]; then
          fDie "The --ports flag needs a value: proxied or direct."
        fi
        case "$2" in
          proxied|direct)
            vPortMode="$2"
            ;;
          *)
            fDie "Unknown value for --ports: $2. Use proxied or direct."
            ;;
        esac
        shift 2
        ;;
      --browser)
        if [ "$#" -lt 2 ]; then
          fDie "The --browser flag needs a value: yes or no."
        fi
        case "$2" in
          yes|no)
            vBrowser="$2"
            ;;
          *)
            fDie "Unknown value for --browser: $2. Use yes or no."
            ;;
        esac
        shift 2
        ;;
      --yes)
        vAssumeYes="yes"
        shift
        ;;
      --help|-h)
        fShowHelp
        exit 0
        ;;
      *)
        fDie "Unknown argument: $1. Run with --help to see the options."
        ;;
    esac
  done
  if [ -z "${vAction}" ]; then
    fDie "Missing mandatory flag: --install, --update, --reinstall, --backup or --restore."
  fi
}

fCheckRoot() {
  if [ "$(id -u)" -ne 0 ]; then
    fDie "This script must run as root. The production server has no sudo."
  fi
}

fCheckDebian() {
  if [ ! -f /etc/debian_version ]; then
    fDie "This installer only supports Debian."
  fi
}

fAskEmail() {
  if [ -n "${vEmail}" ]; then
    return 0
  fi
  if ! fHasTty; then
    fDie "No terminal available. Pass the address with --email when running without a terminal."
  fi
  while [ -z "${vEmail}" ]; do
    printf 'Enter the main email address, the only login of the web application: '
    read -r vEmail < /dev/tty
    if ! echo "${vEmail}" | grep -qE '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$'; then
      echo "That address is not valid. Try again."
      vEmail=""
    fi
  done
}

fConfirmDestructive() {
  local vMessage="$1"
  if [ "${vAssumeYes}" = "yes" ]; then
    return 0
  fi
  if ! fHasTty; then
    fDie "Destructive operation with no terminal to confirm on. Run it again with --yes if you are sure."
  fi
  local vAnswer=""
  printf '%s\n' "${vMessage}"
  printf 'Type exactly YES to continue: '
  read -r vAnswer < /dev/tty
  if [ "${vAnswer}" != "YES" ]; then
    fDie "Cancelled by the user."
  fi
}

fRunWithRetries() {
  # Network operations, given three goes with a pause between them.
  #
  # A resolver that loses one query in ten is not a broken network and is not
  # something this installer can fix, but it is enough to end an installation
  # halfway through. Measured on a LAN whose DNS answered every direct query
  # and still failed one download in ten.
  #
  # Three attempts, 5s and 10s apart, and then it gives up and says what to
  # look at. Anything not about the network is deterministic and fails the
  # same way three times, which costs 15 seconds and no correctness.
  local vDescription="$1"
  shift
  local vAttempt=1
  local vMaximum=3
  while [ "${vAttempt}" -le "${vMaximum}" ]; do
    if "$@"; then
      return 0
    fi
    if [ "${vAttempt}" -lt "${vMaximum}" ]; then
      fLog "${vDescription}: attempt ${vAttempt} of ${vMaximum} failed. Trying again in $((vAttempt * 5)) seconds."
      sleep $((vAttempt * 5))
    fi
    vAttempt=$((vAttempt + 1))
  done
  fLog "${vDescription}: failed ${vMaximum} times."
  return 1
}

fInstallDependencies() {
  fLog "Installing system dependencies."
  export DEBIAN_FRONTEND=noninteractive
  if ! fRunWithRetries "Updating the package index" apt-get update -qq; then
    fDie "Could not update the package index. Check this machine's DNS (/etc/resolv.conf) and that it can reach the mirror."
  fi
  if ! fRunWithRetries "Installing the system packages" \
       apt-get install -y -qq \
    python3 \
    python3-venv \
    python3-pip \
    python3-dev \
    build-essential \
    cmake \
    ffmpeg \
    libffi-dev \
    openssl \
    haproxy \
    cron \
    logrotate \
    curl \
    ca-certificates \
    tar; then
    fDie "Could not install the system packages. Check this machine's DNS (/etc/resolv.conf) and that it can reach the mirror."
  fi

  # Without a running cron, every agent's schedule is a file nothing reads.
  # Enabled always, started only where there is an init to start it with.
  fEnableUnit cron.service
  fRestartUnit cron.service
}

fCreateAppUser() {
  if id -u "${cAppUser}" > /dev/null 2>&1; then
    fLog "System user ${cAppUser} already exists."
  else
    fLog "Creating system user ${cAppUser}."
    useradd --system --home-dir "${cBaseDir}" --shell /usr/sbin/nologin "${cAppUser}"
  fi
}

fSetCodeModes() {
  # The deployed code: directories 00755, files 0644. In one place because it
  # used to be in two, and they disagreed - fDeploySourceCode set 0644 on the
  # files and fCreateDirectoryTree, which runs after it on an update, then did
  # `chmod -R 00755` over the same tree and gave every .py, .css and .json the
  # execute bit back.
  #
  # Nothing under webapp/ is ever executed by path: the daemon runs the runner
  # as `venv/bin/python3 .../runner.py`, and the crontab it writes for each
  # agent says the same. So the bit buys nothing and only claims something
  # about the file that is not true.
  #
  # Five digits on the directory mode, as everywhere else here: four or fewer
  # keeps a setgid bit that arrived with the tree.
  chown -R root:root "${cWebAppDir}"
  find "${cWebAppDir}" -type d -exec chmod 00755 {} +
  find "${cWebAppDir}" -type f -exec chmod 0644 {} +
}

fCreateDirectoryTree() {
  fLog "Creating the directory tree under ${cBaseDir}."
  mkdir -p "${cBaseDir}" "${cWebAppDir}" "${cAgentsDir}" "${cToolsDir}" \
           "${cSkillsDir}" "${cChannelsDir}" "${cProvidersDir}" "${cApiKeysDir}" \
           "${cDbDir}" "${cKanbanDir}" "${cCertsDir}" "${cLogsDir}" \
           "${cAgentsConfigDir}"

  mkdir -p "${cBaseDir}/audio"
  chown -R "${cAppUser}:${cAppGroup}" "${cBaseDir}/audio"
  chmod 00700 "${cBaseDir}/audio"

  # Before the modes below are applied, so that whatever arrives from the old
  # directory is left with the modes of the new one.
  fMigrateApiKeysDirectory

  # Every mode of a directory below is written with FIVE digits, and the leading
  # zero is not decoration. GNU chmod keeps a directory's setuid and setgid bits
  # when the mode has four digits or fewer, so `chmod 0755` on a directory that
  # arrived with setgid leaves it at 2755 and reports success. Only 00755 clears
  # it. This was measured: a tree copied from a workstation whose project
  # directory was setgid carried that bit all the way into /opt/boa/skills/ and
  # survived two explicit chmods.
  #
  # Files are not affected - a numeric chmod on a file sets exactly what it says
  # - so the 0644 and 0600 modes further down are left as they are.

  # Base directory and code belong to root: the web application cannot rewrite itself.
    chown root:root "${cBaseDir}"
    chmod 00755 "${cBaseDir}"
    fSetCodeModes

  # Only root writes tools, because the web application imports them as code.
    chown root:root "${cToolsDir}"
    chmod 00755 "${cToolsDir}"

  # One browser for the whole installation, read-only to everybody else. What
  # has to be isolated is not the binary but the cookies, and those live in
  # each agent's own 0700 home.
    if [ -d "${cPlaywrightDir}" ]; then
      chown -R root:root "${cPlaywrightDir}"
      chmod 00755 "${cPlaywrightDir}"
    fi

  # Only root writes skills either: what a skill says goes into the reasoning of
  # an agent nobody is watching, which makes it as sensitive as its system
  # prompt. Readable by everyone, because an agent granted a skill has to be
  # able to read it - and to run the files it ships.
    chown root:root "${cSkillsDir}"
    chmod 00755 "${cSkillsDir}"

  # Nobody may list the agents. 0711 allows traversing the directory, not reading it.
    chown root:root "${cAgentsDir}"
    chmod 00711 "${cAgentsDir}"
  # Every agent's protected configuration, outside every agent home. Same
  # 0711 as above and for the same reason: an agent traverses to its own and
  # cannot list the others. What matters more is the owner - root, so that no
  # agent can rename its drawer aside and create a substitute.
    chown root:root "${cAgentsConfigDir}"
    chmod 00711 "${cAgentsConfigDir}"

  # Configuration is written by the web application - the user sets channels up
  # in the interface - so it belongs to the web user, not to root. Agents are
  # not in the boa group, so 0750 still keeps every channel token away from
  # them, which is the property that matters.
    chown -R "${cAppUser}":"${cAppGroup}" "${cConfigDir}"
    chmod 00750 "${cConfigDir}" "${cChannelsDir}" "${cProvidersDir}"

  # The provider API keys are stricter than the rest of the configuration:
  # nothing at all for the group. 0750 and 0640 would already keep agents
  # out, since no agent is in the boa group, but that rests on every agent
  # user's group list staying empty for the life of the installation. A mode
  # that grants the group nothing cannot be undone by a later usermod.
    chmod 00700 "${cApiKeysDir}"
    if [ -n "$(ls -A "${cApiKeysDir}" 2>/dev/null)" ]; then
      chmod 0600 "${cApiKeysDir}"/*
    fi
    if [ -n "$(ls -A "${cChannelsDir}" 2>/dev/null)" ]; then
      chmod 0640 "${cChannelsDir}"/*
    fi

  # Application state: only the web application gets in.
    chown "${cAppUser}":"${cAppGroup}" "${cDbDir}" "${cKanbanDir}" "${cLogsDir}"
    chmod 00700 "${cDbDir}" "${cKanbanDir}"
    chmod 00750 "${cLogsDir}"

  # Gunicorn writes a control directory under the service user's home. Without
  # it, every start logs a read-only filesystem error.
    mkdir -p "${cBaseDir}/.gunicorn"
    chown "${cAppUser}":"${cAppGroup}" "${cBaseDir}/.gunicorn"
    chmod 00700 "${cBaseDir}/.gunicorn"

  # Certificates: the private key is read by the web application to serve TLS.
    chown root:"${cAppGroup}" "${cCertsDir}"
    chmod 00750 "${cCertsDir}"
}

fDownloadSourceCode() {
  fLog "Downloading the code from ${cRepoUrl} (branch ${cRepoBranch})."
  vTempDir=$(mktemp -d /tmp/boa-install.XXXXXXXX)
  local vTarUrl="${cRepoUrl}/archive/refs/heads/${cRepoBranch}.tar.gz"
  if ! fRunWithRetries "Downloading the code" \
       curl -fsSL "${vTarUrl}" -o "${vTempDir}/source.tar.gz"; then
    fDie "Could not download the code from ${vTarUrl}. Check this machine's DNS (/etc/resolv.conf) and that it can reach that host."
  fi
  tar -xzf "${vTempDir}/source.tar.gz" -C "${vTempDir}"
  vSourceDir=$(find "${vTempDir}" -maxdepth 1 -mindepth 1 -type d | head -n 1)
  if [ -z "${vSourceDir}" ]; then
    fDie "The downloaded archive contains no source directory."
  fi
  fLog "Code downloaded to ${vSourceDir}."
}

fRequireSourceCode() {
  # Everything the installer copies - the units, the proxy configurations,
  # the agent templates, the provider catalogues, the requirements - is read
  # from the downloaded tree and no longer from a copy under /opt/boa. So a
  # function that runs before fDownloadSourceCode would silently copy from
  # `/deploy/...`, and it says so here instead.
  if [ -z "${vSourceDir}" ] || [ ! -d "${vSourceDir}" ]; then
    fDie "The source code has not been downloaded yet. This is a bug in the order of the installer's own steps."
  fi
}

fDeploySourceCode() {
  fRequireSourceCode
  fLog "Deploying the code to ${cWebAppDir}."
  # The previous version is MOVED aside, not deleted. It is what fRollBack
  # puts back when the new one does not answer, and it is removed by
  # fFinishUpdate once it has.
  rm -rf "${cWebAppPreviousDir}"
  if [ -d "${cWebAppDir}" ]; then
    mv "${cWebAppDir}" "${cWebAppPreviousDir}"
  fi
  mkdir -p "${cWebAppDir}"
  # Only what the application runs. `deploy/` is not copied: the units, the
  # proxy configurations, the templates and this script itself are the
  # installer's own material, every one of them is read from the tree that
  # was just downloaded, and a copy of them under /opt/boa would only be a
  # second version of files that already live in the repository. The
  # `rm -rf` above is what removes it from an installation made before this.
  cp -a "${vSourceDir}/backend"  "${cWebAppDir}/"
  cp -a "${vSourceDir}/frontend" "${cWebAppDir}/"
  fSetCodeModes

  # Tools live outside the deployed code, so that root can add its own without
  # an update wiping them out.
    if [ -d "${vSourceDir}/backend/tools" ]; then
      cp -a "${vSourceDir}/backend/tools/." "${cToolsDir}/"
      chown -R root:root "${cToolsDir}"
      find "${cToolsDir}" -type f -exec chmod 0644 {} +
    fi

  # No skills are copied here, because the application ships none: a skill is
  # a procedure for THIS installation - these hosts, this backup, this
  # certificate - so the ones that mean anything are the ones written on the
  # server. ${cSkillsDir} is created empty, root-owned and world-readable, and
  # an update never touches what is in it.
}

fBuildVirtualEnv() {
  # Built BESIDE the running one, never over it.
  #
  # An update used to stop the services, delete webapp/ and only then run pip.
  # A pip that failed - no network, an index that was down, a wheel that would
  # not build - left an installation with its services stopped and its code
  # gone, needing somebody to notice and to recover it by hand. Nothing here
  # touches the running installation, so a failure at this point is an update
  # that did not happen rather than an installation that is down.
  fRequireSourceCode
  fLog "Building the Python virtual environment at ${cVenvNewDir}."
  rm -rf "${cVenvNewDir}"
  python3 -m venv "${cVenvNewDir}"

  # pip itself is pinned. `--upgrade pip` with no version meant two updates of
  # the same code could resolve differently, which is the thing pinning the
  # requirements was for.
  "${cVenvNewDir}/bin/python3" -m pip install --quiet "pip==${cPipVersion}"
  "${cVenvNewDir}/bin/python3" -m pip install --quiet \
    -r "${vSourceDir}/deploy/requirements.txt"

  # What actually got installed, transitive dependencies and all, so that a
  # later update can show what moved. The direct dependencies are pinned in
  # requirements.txt; their own are not, and this is where that shows.
  "${cVenvNewDir}/bin/python3" -m pip freeze > "${cVenvNewDir}/resolved.txt"

  # It has to be able to import what the application imports before anything
  # is switched over. A venv that builds and cannot import is a service that
  # starts and fails on its first request.
  if ! "${cVenvNewDir}/bin/python3" -c 'import flask, gunicorn, argon2, requests' \
       > /dev/null 2>&1; then
    fDie "The new virtual environment cannot import what the application needs."
  fi

  # And one CONSOLE SCRIPT has to run, which is a different question.
  # bin/python3 is a symlink to the system interpreter and answers from any
  # path at all, so the import check above says nothing about whether the
  # files systemd actually executes work. bin/gunicorn is the one it executes.
  if ! "${cVenvNewDir}/bin/gunicorn" --version > /dev/null 2>&1; then
    fDie "The new virtual environment has no gunicorn that runs."
  fi

  fRepointVirtualEnv

  chown -R root:root "${cVenvNewDir}"
  chmod -R 00755 "${cVenvNewDir}"
}

fRepointVirtualEnv() {
  # A Python virtual environment is NOT relocatable, and this one is built at
  # ${cVenvNewDir} and then renamed to ${cVenvDir}.
  #
  # `python3 -m venv` writes the absolute path it was given into three places:
  # the shebang of every console script in bin/, the VIRTUAL_ENV line of the
  # activate scripts, and the `command` line of pyvenv.cfg. After the rename
  # each one of them names a directory that does not exist any more.
  #
  # Measured on a real machine: the installer said "Installation finished" and
  # boa-web then restarted every five seconds with
  #
  #   status=203/EXEC - Failed to execute /opt/boa/venv/bin/gunicorn:
  #   No such file or directory
  #
  # The file was there. Its first line read #!/opt/boa/venv.new/bin/python3,
  # and THAT was not. Both installers, both actions, every installation: the
  # web application could not start at all.
  #
  # The paths are rewritten here, while the environment is still at its
  # building name, so that what lands at ${cVenvDir} is already correct.
  fLog "Pointing the virtual environment at ${cVenvDir}, where it is about to be moved."
  local vFile=""
  for vFile in "${cVenvNewDir}"/bin/*; do
    [ -f "${vFile}" ] || continue
    # A console script is a text file whose first two bytes are "#!". The rest
    # of bin/ is the activate scripts and the python symlinks, and one of
    # them - Activate.ps1 - holds null bytes, which a command substitution
    # reading it turns into a warning in the middle of the log.
    [ "$(head -c 2 "${vFile}" 2> /dev/null)" = "#!" ] || continue
    case "$(head -n 1 "${vFile}" 2> /dev/null)" in
      "#!${cVenvNewDir}/"*)
        sed -i "1s|^#!${cVenvNewDir}/|#!${cVenvDir}/|" "${vFile}"
        ;;
    esac
  done
  for vFile in "${cVenvNewDir}/pyvenv.cfg" "${cVenvNewDir}"/bin/[aA]ctivate*; do
    [ -f "${vFile}" ] || continue
    sed -i "s|${cVenvNewDir}|${cVenvDir}|g" "${vFile}"
  done

  # Checked and not assumed. If a future pip writes its console scripts some
  # other way, this is the line that has to say so - not seven services failing
  # to start twenty minutes later.
  local vShebang=""
  vShebang="$(head -n 1 "${cVenvNewDir}/bin/gunicorn" 2> /dev/null || true)"
  if [ "${vShebang}" != "#!${cVenvDir}/bin/python3" ]; then
    fDie "The virtual environment could not be pointed at ${cVenvDir}: bin/gunicorn still reads ${vShebang}."
  fi
}

fActivateVirtualEnv() {
  # The switch itself: two renames, with the old one kept until the end.
  fLog "Switching to the new virtual environment."
  rm -rf "${cVenvPreviousDir}"
  if [ -d "${cVenvDir}" ]; then
    mv "${cVenvDir}" "${cVenvPreviousDir}"
  fi
  mv "${cVenvNewDir}" "${cVenvDir}"

  # What moved since the last successful update, said out loud. Transitive
  # dependencies are not pinned, so two updates of the same code can install
  # different versions - and the only way anybody would find that out is a
  # line like this one.
  if [ -f "${cVenvPreviousDir}/resolved.txt" ] \
     && ! diff -q "${cVenvPreviousDir}/resolved.txt" "${cVenvDir}/resolved.txt" \
          > /dev/null 2>&1; then
    fLog "The resolved dependencies changed since the last update:"
    diff "${cVenvPreviousDir}/resolved.txt" "${cVenvDir}/resolved.txt" || true
  fi
}

fCreateVirtualEnv() {
  # Kept for --install and --reinstall, where there is nothing running to
  # protect and no previous version to keep.
  fBuildVirtualEnv
  rm -rf "${cVenvDir}"
  mv "${cVenvNewDir}" "${cVenvDir}"
}

fRollBack() {
  # Put back what was running, if there is anything to put back.
  #
  # Only reachable between the switch and the moment the services answer. A
  # failure before the switch has changed nothing; a failure after the
  # services answer is not this function's business.
  fLog "Rolling back to the previous version."
  if [ -d "${cWebAppPreviousDir}" ]; then
    rm -rf "${cWebAppDir}"
    mv "${cWebAppPreviousDir}" "${cWebAppDir}"
  fi
  if [ -d "${cVenvPreviousDir}" ]; then
    rm -rf "${cVenvDir}"
    mv "${cVenvPreviousDir}" "${cVenvDir}"
  fi
  # In a SUBSHELL, and the `|| true` is not enough on its own: fStartServices
  # calls fDie when a service will not come up, fDie calls exit, and `exit`
  # ends the shell whatever is written beside it. A subshell is where that
  # exit stops.
  #
  # Measured on a real Alpine: boa-proxy was taken down by OpenRC while
  # boa-web was flapping, the rollback's own start of it lost the race for the
  # service lock, and the installer died INSIDE fRollBack. The rollback had
  # worked - the previous version was back and answering - but what the
  # operator was told was "The boa-proxy service would not start", with not
  # one word about an update having been rolled back. The account of what
  # happened is the only thing an operator has at that point.
  ( fStartServices ) || true
  # The switch has been undone: whatever exit follows, fCleanup must not do
  # this a second time.
  vUpdateSwitched=""
  return 0
}

fReportServiceStates() {
  # What systemd says about each of the seven, and then the journal of the two
  # that serve a page. `is-active` returns a failure for anything that is not
  # running, and this function runs while the installer is already failing: it
  # must not become the reason it stops.
  local vUnit=""
  local vState=""
  for vUnit in boa-exec boa-agent-api boa-buzzer boa-telegram boa-discord boa-web boa-proxy; do
    vState="$(systemctl is-active "${vUnit}.service" 2>&1 | tr '\n' ' ' || true)"
    # The newline turned into a space above is a space at the end of the line.
    vState="$(printf '%s' "${vState}" | sed -e 's/[[:space:]]*$//')"
    fLog "  ${vUnit}: ${vState:-systemctl said nothing}"
  done
  # 203/EXEC, a Python traceback, a port already taken: whatever killed one of
  # these is in here, and this is the file the operator was told to read.
  for vUnit in boa-web boa-proxy; do
    fLog "  the last lines of the ${vUnit} journal:"
    journalctl -u "${vUnit}.service" -n 15 --no-pager 2> /dev/null \
      | sed 's/^/      /' || true
  done
}

fExplainWhyItDoesNotAnswer() {
  # What this machine looks like at the moment it did not answer.
  #
  # The line above this one used to be everything the operator was given:
  # "The application did not answer on port 11443 (last code: 000)", over a
  # log that said nothing else about it. Measured on a fresh Alpine: an
  # installation that had printed no error anywhere ended exactly there, and
  # finding out why meant knowing which seven services to ask about and which
  # files to read - none of which is written down in the one file the error
  # points at. The log could not answer the question it was being opened to
  # answer.
  #
  # 000 is not an HTTP code. It is curl saying it never got one, and whether
  # that was a refused connection, a TLS handshake that failed or a request
  # that timed out is the whole diagnosis. `-sS` prints it; the `-s` of the
  # attempt above swallows it on purpose, because it runs fifteen times.
  local vPort="$1"
  local vProxyFlag="$2"
  local vCode="$3"

  fLog "Why it did not answer - the state of this machine, read now:"

  # ${vProxyFlag} is unquoted for the same reason as in fVerifyInstallation:
  # empty, it has to vanish rather than reach curl as an empty argument.
  local vCurlSays=""
  vCurlSays="$(curl -sS -k --max-time 10 ${vProxyFlag} -o /dev/null \
               "https://127.0.0.1:${vPort}/login" 2>&1 || true)"
  if [ -n "${vCurlSays}" ]; then
    fLog "  curl: ${vCurlSays}"
  else
    fLog "  curl: the request was answered, and the answer was ${vCode:-nothing}."
  fi

  # Whether anything is holding the port at all. Asked before the services
  # are, because it is one line and what follows is thirty: nothing listening,
  # next to a service that calls itself started, is a process that dies and is
  # restarted, and that pair is the diagnosis.
  local vListening=""
  if command -v ss > /dev/null 2>&1; then
    vListening="$(ss -lnt 2> /dev/null | grep -E "[:.]${vPort}([^0-9]|$)" || true)"
  elif command -v netstat > /dev/null 2>&1; then
    vListening="$(netstat -lnt 2> /dev/null | grep -E "[:.]${vPort}([^0-9]|$)" || true)"
  fi
  if [ -n "${vListening}" ]; then
    fLog "  listening on ${vPort}:"
    echo "${vListening}" | sed 's/^/      /'
  else
    fLog "  nothing is listening on port ${vPort}."
  fi

  # Each service, and whether it is up. A supervised service that dies the
  # instant it starts is reported as started by the command that started it -
  # the supervisor did accept it - so this is the first place the truth about
  # one shows up.
  fReportServiceStates

  # And what the parts that serve a page wrote before they gave up. The two
  # service files exist on Alpine, where supervise-daemon is what collects a
  # service's output; on Debian the journal holds it and fReportServiceStates
  # is what prints it. gunicorn's own error log is written on both.
  local vFile=""
  for vFile in "${cLogsDir}/boa-proxy.log" "${cLogsDir}/boa-web.log" \
               "${cLogsDir}/error.log"; do
    if [ -s "${vFile}" ]; then
      fLog "  the last lines of ${vFile}:"
      tail -n 15 "${vFile}" 2> /dev/null | sed 's/^/      /' || true
    fi
  done
  return 0
}

fVerifyInstallation() {
  # The services are up; the question is whether the application answers.
  #
  # An update used to end at "Update finished" the moment systemd had accepted
  # seven start commands, which says nothing about whether a request gets a
  # page. The login page is the cheapest thing that exercises gunicorn, the
  # proxy and the certificate at once.
  #
  # In "proxied" mode the HTTPS port expects PROXY protocol, so curl has to
  # send it. In "direct" mode it must NOT: that bind has no `accept-proxy`,
  # so the header lands in the TLS handshake and the request never gets an
  # answer. Sending it unconditionally meant every `--install --ports direct`
  # ended in "did not answer" over a working installation, and every direct
  # `--update` rolled itself back.
  local vPort="${cHttpsPort}"
  local vProxyFlag="--haproxy-protocol"
  if [ "${vPortMode}" = "direct" ]; then
    vPort="443"
    vProxyFlag=""
  fi

  local vAttempt=0
  local vCode=""
  fLog "Checking that the application answers on port ${vPort}."
  while [ "${vAttempt}" -lt "${cVerifyAttempts}" ]; do
    # ${vProxyFlag} is unquoted on purpose: empty, it has to vanish rather
    # than reach curl as an empty argument.
    vCode="$(curl -sk --max-time 10 ${vProxyFlag} -o /dev/null \
              -w '%{http_code}' "https://127.0.0.1:${vPort}/login" 2> /dev/null || true)"
    if [ "${vCode}" = "200" ]; then
      fLog "The application answered 200 on ${vPort}."
      return 0
    fi
    vAttempt=$((vAttempt + 1))
    sleep "${cVerifySleepSeconds}"
  done

  fLog "The application did not answer on port ${vPort} (last code: ${vCode:-none})."
  fExplainWhyItDoesNotAnswer "${vPort}" "${vProxyFlag}" "${vCode}"
  return 1
}

fFinishUpdate() {
  # The previous version is kept until the new one has answered, and only
  # then removed. Up to this point a failure can still be undone.
  rm -rf "${cWebAppPreviousDir}"
  rm -rf "${cVenvPreviousDir}"
  # The new version has answered: a failure after this point is not one an
  # update can undo, and there is nothing left to undo it with.
  vUpdateSwitched=""
  return 0
}

fGenerateCertificates() {
  local vFullChain="${cCertsDir}/fullchain.pem"
  local vPrivKey="${cCertsDir}/privkey.pem"
  if [ -f "${vFullChain}" ] && [ -f "${vPrivKey}" ]; then
    fLog "Certificates already present. Not regenerating them."
    return 0
  fi
  fLog "No Let's Encrypt certificates found. Generating a self-signed one."
  openssl req -x509 -nodes -newkey rsa:4096 -days 3650 \
    -keyout "${vPrivKey}" \
    -out "${vFullChain}" \
    -subj "/CN=$(hostname -f 2>/dev/null || hostname)" \
    > /dev/null 2>&1
  chown root:"${cAppGroup}" "${vFullChain}" "${vPrivKey}"
  chmod 0640 "${vFullChain}" "${vPrivKey}"
  fBuildCombinedCertificate
}

fBuildCombinedCertificate() {
  # HAProxy wants the certificate and the private key in a single file, and it
  # reads it as the boa user. Rebuilt on every run so that renewing a Let's
  # Encrypt certificate and re-running --update is enough to pick it up.
  local vFullChain="${cCertsDir}/fullchain.pem"
  local vPrivKey="${cCertsDir}/privkey.pem"
  local vCombined="${cCertsDir}/boa.pem"
  if [ ! -f "${vFullChain}" ] || [ ! -f "${vPrivKey}" ]; then
    fDie "Missing certificate files in ${cCertsDir}."
  fi
  fLog "Building the combined certificate for HAProxy."
  cat "${vFullChain}" "${vPrivKey}" > "${vCombined}"
  chown root:"${cAppGroup}" "${vCombined}"
  chmod 0640 "${vCombined}"
}

fMigrateSystemPromptFileName() {
  # The system prompt file used to be called SystemPrompt.md. Installations
  # made before the rename still have it, and an agent whose prompt the
  # application can no longer find would run with no instructions at all.
  local vAgentHome=""
  local vOldPath=""
  local vNewPath=""
  for vAgentHome in "${cAgentsDir}"/*; do
    [ -d "${vAgentHome}" ] || continue
    vOldPath="${vAgentHome}/SystemPrompt.md"
    vNewPath="${vAgentHome}/system-prompt.md"
    if [ -f "${vOldPath}" ] && [ ! -f "${vNewPath}" ]; then
      fLog "Renaming $(basename "${vAgentHome}")/SystemPrompt.md to system-prompt.md."
      mv "${vOldPath}" "${vNewPath}"
    fi
  done
}

fMigrateApiKeysDirectory() {
  # The shared provider keys used to live in config/keys, a name that read as
  # "the keys of this installation" and sat one typo away from the per-agent
  # keys/ inside each agent home. They are in config/apikeys now.
  #
  # Only a file with no counterpart in the new directory is moved: a key
  # already written there is the one the application is using, and an update
  # is not entitled to replace it with an older copy.
  if [ ! -d "${cLegacyApiKeysDir}" ]; then
    return 0
  fi

  fLog "Moving the shared provider keys to ${cApiKeysDir}."
  mkdir -p "${cApiKeysDir}"
  local vKeyFile=""
  local vKeyName=""
  for vKeyFile in "${cLegacyApiKeysDir}"/*; do
    [ -f "${vKeyFile}" ] || continue
    vKeyName="$(basename "${vKeyFile}")"
    if [ -f "${cApiKeysDir}/${vKeyName}" ]; then
      fLog "  ${vKeyName}: already there, the old copy is left where it is."
      continue
    fi
    fLog "  ${vKeyName}"
    mv "${vKeyFile}" "${cApiKeysDir}/${vKeyName}"
  done

  # Removed only when empty, which is the proof that no key was left behind.
  if rmdir "${cLegacyApiKeysDir}" 2>/dev/null; then
    fLog "  ${cLegacyApiKeysDir} removed."
  else
    fLog "  ${cLegacyApiKeysDir} still holds files and has been kept."
    # Whatever is left there is still a key, so it is shut as tightly as the
    # new directory rather than left on whatever mode it happened to have.
    chown -R "${cAppUser}":"${cAppGroup}" "${cLegacyApiKeysDir}"
    chmod 00700 "${cLegacyApiKeysDir}"
    chmod 0600 "${cLegacyApiKeysDir}"/*
  fi
}

fProtectAgentConfigFiles() {
  # Three files per agent are not the agent's business to change: info.json
  # says which tools it has been granted and what it may spend,
  # system-prompt.md defines what it is, and api-token is how it identifies
  # itself. They used to sit in the home, which is the agent's own at 0700 -
  # so the agent could rewrite all three. Measured before that was fixed: an
  # agent added mail.read to its own info.json and the privileged daemon then
  # reported the tool as granted.
  #
  # The first fix put them in ${vAgentHome}/config, owned by root. That was
  # not enough, and the reason is the same sentence as before: owning a file
  # is not what decides whether it can be replaced, the write permission on
  # its DIRECTORY is - and that applies to the drawer too. ~/config is an
  # entry in the HOME, the home is the agent's at 0700, so:
  #
  #   mv ~/config ~/config-old && mkdir ~/config && echo '...' > ~/config/info.json
  #
  # The mode on the drawer is never consulted by a rename; only the parent's
  # is. So the drawer moves out of the home altogether, to
  # ${cAgentsConfigDir}/<id>, where every directory on the way is root's.
  fLog "Moving each agent's protected files out of its home directory."
  mkdir -p "${cAgentsConfigDir}"
  chown root:root "${cAgentsConfigDir}"
  # 0711: an agent may traverse to its own and cannot list the others, which
  # is exactly what ${cAgentsDir} does.
  chmod 00711 "${cAgentsConfigDir}"

  local vAgentHome=""
  local vAgentId=""
  local vConfigDir=""
  local vLegacyDir=""
  local vFileName=""
  local vSourcePath=""
  for vAgentHome in "${cAgentsDir}"/*; do
    [ -d "${vAgentHome}" ] || continue
    vAgentId="$(basename "${vAgentHome}")"
    getent passwd "agent-${vAgentId}" > /dev/null 2>&1 || continue

    vConfigDir="${cAgentsConfigDir}/${vAgentId}"
    vLegacyDir="${vAgentHome}/config"
    mkdir -p "${vConfigDir}"
    chown root:"agent-${vAgentId}" "${vConfigDir}"
    chmod 00750 "${vConfigDir}"

    for vFileName in info.json system-prompt.md api-token; do
      if [ ! -f "${vConfigDir}/${vFileName}" ]; then
        # The old drawer first, then the bare home. A symlink is skipped
        # rather than followed: an agent that left one called info.json would
        # otherwise have a file of its own promoted into the protected
        # directory.
        for vSourcePath in "${vLegacyDir}/${vFileName}" "${vAgentHome}/${vFileName}"; do
          if [ -f "${vSourcePath}" ] && [ ! -L "${vSourcePath}" ]; then
            fLog "  ${vAgentId}: ${vFileName}"
            mv "${vSourcePath}" "${vConfigDir}/${vFileName}"
            break
          fi
        done
      fi
      if [ -f "${vConfigDir}/${vFileName}" ]; then
        chown root:"agent-${vAgentId}" "${vConfigDir}/${vFileName}"
        chmod 0640 "${vConfigDir}/${vFileName}"
      fi
      # Nothing reads the old places any more. Whatever is still sitting there
      # under one of these three names is removed, so that a stale copy cannot
      # be mistaken for the real one by somebody reading the tree.
      rm -f "${vLegacyDir}/${vFileName}" "${vAgentHome}/${vFileName}"
    done
  done
}

fInstallProviderCatalogues() {
  # Model lists, one JSON per provider. Only files that do not exist yet are
  # written: providers ship models faster than this project ships versions, so
  # the user is expected to edit these, and an --update must not undo that.
  fRequireSourceCode
  fLog "Installing the provider model catalogues."
  local vSourceFile=""
  local vTargetFile=""
  for vSourceFile in "${vSourceDir}"/deploy/providers/*.json; do
    [ -e "${vSourceFile}" ] || continue
    vTargetFile="${cProvidersDir}/$(basename "${vSourceFile}")"
    if [ -f "${vTargetFile}" ]; then
      # Kept, but said out loud when this version ships a different list: the
      # models a provider serves change, and an installation that never hears
      # about it goes on suggesting models that were retired two releases ago.
      # Not overwritten, because the file may be the user's own edit and there
      # is no way to tell one from the other.
      if cmp -s "${vSourceFile}" "${vTargetFile}"; then
        fLog "Keeping the existing $(basename "${vTargetFile}")."
      else
        fLog "Keeping the existing $(basename "${vTargetFile}") - this version ships a newer list. Delete the file and run --update to take it."
      fi
      continue
    fi
    cp "${vSourceFile}" "${vTargetFile}"
  done
  # A catalogue for a provider this version does not have: a leftover from an
  # older one, or a file somebody wrote by hand. Named, never deleted - the
  # application ignores it either way, and deleting a file the user may have
  # written is not the installer's call.
  local vInstalledFile=""
  for vInstalledFile in "${cProvidersDir}"/*.json; do
    [ -e "${vInstalledFile}" ] || continue
    if [ ! -f "${vSourceDir}/deploy/providers/$(basename "${vInstalledFile}")" ]; then
      fLog "Note: $(basename "${vInstalledFile}") is not a provider this version has. Nothing reads it; delete it when you like."
    fi
  done
  chown -R "${cAppUser}":"${cAppGroup}" "${cProvidersDir}"
  chmod 0640 "${cProvidersDir}"/*.json 2>/dev/null || true
}

fAskPortMode() {
  # Two ways to serve this, and the right one depends on what else is on the
  # machine - which is why it is a question and not a default:
  #
  #   proxied  The application listens on 11080 and 11443, on localhost only,
  #            and an HAProxy on 80 and 443 hands the traffic to it. This is
  #            what to choose when the machine serves anything else, or is
  #            behind another proxy: the front HAProxy is where the other
  #            sites go, and it already speaks PROXY protocol.
  #
  #   direct   The application serves 80 and 443 itself, on every interface,
  #            with nothing in front. Fewer moving parts, and the right answer
  #            when this machine does nothing else.
  #
  # Once chosen it is remembered, so `--update` never asks again and never
  # quietly changes which ports the machine listens on.
  if [ -n "${vPortMode}" ]; then
    return 0
  fi

  if [ -f "${cPortsFile}" ]; then
    vPortMode=$(sed -n 's/^mode=\(.*\)$/\1/p' "${cPortsFile}" | head -n 1)
    if [ "${vPortMode}" = "proxied" ] || [ "${vPortMode}" = "direct" ]; then
      fLog "Keeping the ports chosen when this was installed: ${vPortMode}."
      return 0
    fi
    vPortMode=""
  fi

  if ! fHasTty; then
    fLog "No terminal to ask on. Serving on ${cHttpPort}/${cHttpsPort} behind a proxy."
    vPortMode="proxied"
    return 0
  fi

  local vAnswer=""
  while [ -z "${vPortMode}" ]; do
    printf '%s\n' \
      "" \
      "How should the web application be served?" \
      "" \
      "  1) On ports ${cHttpPort} and ${cHttpsPort}, with an HAProxy in front of it on 80" \
      "     and 443. Choose this if the machine serves anything else, or sits" \
      "     behind another proxy. The installer writes that HAProxy for you." \
      "" \
      "  2) Directly on ports 80 and 443, with nothing in front. Fewer moving" \
      "     parts, and the right answer if this machine does nothing else." \
      ""
    printf 'Enter 1 or 2 [1]: '
    read -r vAnswer < /dev/tty
    case "${vAnswer}" in
      ""|1) vPortMode="proxied" ;;
      2)    vPortMode="direct" ;;
      *)    echo "Answer 1 or 2." ;;
    esac
  done
}

fRememberPortMode() {
  mkdir -p "$(dirname "${cPortsFile}")"
  printf '%s\n' \
    "# How this installation is served. Written by the installer." \
    "# Change it with: install-update-reinstall-debian.sh --update --ports <mode>" \
    "mode=${vPortMode}" \
    > "${cPortsFile}"
  chown "${cAppUser}":"${cAppGroup}" "${cPortsFile}"
  chmod 0640 "${cPortsFile}"
}

fAskBrowser() {
  # The browser is part of what this is for: without one an agent can read a
  # public page and nothing else - no login, no form, no button. So it is
  # installed unless somebody says not to, and the question exists for the
  # installation that is short of disk or genuinely never needs it.
  #
  # Remembered like the ports: an --update never asks again, never quietly
  # removes a browser somebody installed, and never quietly downloads 600 MB
  # onto a machine whose owner already said no.
  if [ -n "${vBrowser}" ]; then
    return 0
  fi

  if [ -f "${cBrowserFile}" ]; then
    vBrowser=$(sed -n 's/^browser=\(.*\)$/\1/p' "${cBrowserFile}" | head -n 1)
    if [ "${vBrowser}" = "yes" ] || [ "${vBrowser}" = "no" ]; then
      fLog "Keeping the browser choice made when this was installed: ${vBrowser}."
      return 0
    fi
    vBrowser=""
  fi

  if ! fHasTty; then
    fLog "No terminal to ask on. Installing the browser, which is the default."
    vBrowser="yes"
    return 0
  fi

  local vAnswer=""
  printf '\n'
  printf 'The agents get a browser: about 600 MB of Chromium, and what lets\n'
  printf 'one log into a site, fill a form and click rather than only read a\n'
  printf 'page. Each agent gets its own profile, so their sessions stay apart.\n'
  printf '\n'
  printf 'Say no if this machine is short of disk. You can change it later\n'
  printf 'either way with --update --browser <yes|no>.\n'
  printf '\n'
  printf 'Install it? [Y/n]: '
  read -r vAnswer < /dev/tty
  case "${vAnswer}" in
    n|N|no|NO) vBrowser="no" ;;
    *)         vBrowser="yes" ;;
  esac
}

fRememberBrowser() {
  mkdir -p "$(dirname "${cBrowserFile}")"
  printf '%s\n' \
    "# Whether a browser is installed for the agents. Written by the installer." \
    "# Change it with: install-update-reinstall-debian.sh --update --browser <yes|no>" \
    "browser=${vBrowser}" \
    > "${cBrowserFile}"
  chown "${cAppUser}":"${cAppGroup}" "${cBrowserFile}"
  chmod 0640 "${cBrowserFile}"
}

fInstallWhisper() {
  local vWhisperDir vVersion vBuildDir vSourceArchive
  vWhisperDir="${cBaseDir}/whisper"
  vVersion="v1.9.4"
  mkdir -p "${vWhisperDir}/bin" "${vWhisperDir}/models" "${vWhisperDir}/status"
  chown root:root "${vWhisperDir}" "${vWhisperDir}/bin" "${vWhisperDir}/models" "${vWhisperDir}/status"
  chmod 00755 "${vWhisperDir}" "${vWhisperDir}/bin" "${vWhisperDir}/models" "${vWhisperDir}/status"
  if [ ! -x "${vWhisperDir}/bin/whisper-cli" ] || [ "$(cat "${vWhisperDir}/version" 2>/dev/null || true)" != "${vVersion}" ]; then
    fLog "Building whisper.cpp ${vVersion} for this machine."
    vSourceArchive="${vTempDir}/whisper.tar.gz"
    vBuildDir="${vTempDir}/whisper.cpp-1.9.4"
    if ! fRunWithRetries "Downloading whisper.cpp" curl -fsSL "https://codeload.github.com/ggml-org/whisper.cpp/tar.gz/refs/tags/${vVersion}" -o "${vSourceArchive}"; then
      fDie "Could not download whisper.cpp."
    fi
    printf '%s  %s\n' '57e280cee375ab02425b806ad5146b99f6eb9357e3c2b31357c8a6af2e2e44ae' "${vSourceArchive}" | sha256sum -c -
    tar -xzf "${vSourceArchive}" -C "${vTempDir}"
    cmake -S "${vBuildDir}" -B "${vBuildDir}/build" -DCMAKE_BUILD_TYPE=Release \
      -DBUILD_SHARED_LIBS=OFF -DGGML_NATIVE=OFF -DGGML_CCACHE=OFF \
      -DCMAKE_DISABLE_FIND_PACKAGE_Git=TRUE -DWHISPER_BUILD_TESTS=OFF -DWHISPER_BUILD_SERVER=OFF
    cmake --build "${vBuildDir}/build" --target whisper-cli -j 2
    cp "${vBuildDir}/build/bin/whisper-cli" "${vWhisperDir}/bin/whisper-cli.new"
    chmod 0755 "${vWhisperDir}/bin/whisper-cli.new"
    mv -f "${vWhisperDir}/bin/whisper-cli.new" "${vWhisperDir}/bin/whisper-cli"
    printf '%s\n' "${vVersion}" > "${vWhisperDir}/version"
    chmod 0644 "${vWhisperDir}/version"
  fi
  fLog "Preparing the multilingual base transcription model (about 142 MiB)."
  BOA_BASE_DIR="${cBaseDir}" PYTHONDONTWRITEBYTECODE=1 \
    python3 "${cWebAppDir}/backend/core/whisper_runtime.py" --install-model base
}

fInstallBrowser() {
  if [ "${vBrowser}" != "yes" ]; then
    fLog "Browser not installed, by request. The browser tools will say so if an agent uses one."
    return 0
  fi

  fLog "Installing the browser for the agents. This downloads about 600 MB."
  mkdir -p "${cPlaywrightDir}"

  # The system libraries Chromium needs. Playwright knows the list for this
  # distribution, which is why it is asked rather than written out here: the
  # list changes with the Debian release and with Chromium's own version.
  if ! PLAYWRIGHT_BROWSERS_PATH="${cPlaywrightDir}" \
       "${cVenvDir}/bin/python3" -m playwright install-deps chromium; then
    fLog "WARNING: could not install the browser's system dependencies."
    fLog "The browser tools may not work. Everything else is unaffected."
    return 0
  fi

  if ! PLAYWRIGHT_BROWSERS_PATH="${cPlaywrightDir}" \
       "${cVenvDir}/bin/python3" -m playwright install chromium; then
    fLog "WARNING: could not download the browser."
    fLog "The browser tools will say so. Everything else is unaffected."
    return 0
  fi

  # Readable and executable by every agent, writable by none: it is a binary,
  # and an agent that could rewrite it would be rewriting what every other
  # agent runs.
  chown -R root:root "${cPlaywrightDir}"
  find "${cPlaywrightDir}" -type d -exec chmod 00755 {} +
  fLog "Browser installed in ${cPlaywrightDir}."
}

fMachineProxyIsPristine() {
  # Whether the HAProxy configuration on this machine is the one its package
  # shipped, byte for byte. dpkg records the md5 of every conffile it owns, so
  # the question is answered from what the package manager already knows
  # rather than by guessing from the contents.
  #
  # It matters because this installer installs haproxy itself: on a fresh
  # machine the file it then finds is the package's example, not a
  # configuration somebody wrote, and treating the two the same turns every
  # first install into a destructive confirmation about nothing.
  local vExpected=""
  vExpected=$(dpkg-query -W -f='${Conffiles}\n' haproxy 2> /dev/null \
              | sed -n "s#^ *${cMachineProxyConfig} \([0-9a-f]\{32\}\).*\$#\1#p" \
              | head -n 1)
  if [ -z "${vExpected}" ]; then
    return 1
  fi
  local vActual=""
  vActual=$(md5sum "${cMachineProxyConfig}" 2> /dev/null | cut -d' ' -f1)
  if [ -n "${vActual}" ] && [ "${vExpected}" = "${vActual}" ]; then
    return 0
  fi
  return 1
}

fInstallMachineProxy() {
  # Only in "proxied" mode, and only over a file we wrote ourselves. The
  # machine's HAProxy may be carrying other sites, and replacing somebody
  # else's configuration to install a web application would be the rudest
  # thing this script could do.
  if [ "${vPortMode}" != "proxied" ]; then
    return 0
  fi

  if [ -f "${cMachineProxyConfig}" ] && \
     ! grep -q "${cMachineProxyMarker}" "${cMachineProxyConfig}"; then
    if fMachineProxyIsPristine; then
      # The example file the haproxy package ships, exactly as it shipped it -
      # and the package was installed by this installer, minutes ago, in
      # fInstallDependencies. There is no work of anybody's in it, so it is
      # replaced without a word. Asking here is what used to stop a plain
      # `--install` on a fresh machine dead: no terminal to answer on, and the
      # installation ended at "Destructive operation with no terminal to
      # confirm on" having already built half of itself.
      fLog "Replacing the stock ${cMachineProxyConfig} that came with the haproxy package."
    elif [ "${vAction}" = "update" ]; then
      # Somebody else's proxy. On an update it is left exactly as it is: the
      # installation was working through it a minute ago, and a routine update
      # that rewrites the machine's proxy is a routine update that takes other
      # sites down. Only a fresh install or a reinstall asks.
      fLog "Leaving ${cMachineProxyConfig} alone: it was not written by this installer."
      fLog "The application is served on ${cHttpPort} and ${cHttpsPort}; point your proxy at those."
      return 0
    else
      local vBackup="${cMachineProxyConfig}.before-boa.$(date '+%Y%m%d%H%M%S')"
      fLog "There is already an HAProxy configuration on this machine, and it has been edited."
      fConfirmDestructive "The installer wants to replace ${cMachineProxyConfig} with one that serves this application on 80 and 443. A copy of the current file will be kept at ${vBackup}, but any other site it serves will stop working until you merge them back."
      cp -a "${cMachineProxyConfig}" "${vBackup}"
      fLog "Kept a copy of the previous configuration at ${vBackup}."
    fi
  fi

  fRequireSourceCode
  fLog "Installing the machine's HAProxy configuration on 80 and 443."
  mkdir -p /etc/haproxy
  cp "${vSourceDir}/deploy/haproxy/machine.cfg" "${cMachineProxyConfig}"
  chmod 0644 "${cMachineProxyConfig}"

  if ! /usr/sbin/haproxy -c -f "${cMachineProxyConfig}" > /dev/null 2>&1; then
    /usr/sbin/haproxy -c -f "${cMachineProxyConfig}" || true
    fDie "The machine's HAProxy configuration is not valid."
  fi

  # Unmasked first. A machine that was installed with `--ports direct` had
  # this unit masked by fRetireMachineProxy, and a masked unit cannot be
  # enabled or started by anything - so going back to `proxied` would end at
  # "The machine's HAProxy would not start" over a mask this installer put
  # there itself.
  systemctl unmask haproxy.service > /dev/null 2>&1 || true
  fEnableUnit haproxy.service
  fRestartUnit haproxy.service
}

fRetireMachineProxy() {
  # In "direct" mode the application binds 80 and 443 itself, so anything else
  # holding those ports keeps it from starting at all. This takes the
  # machine's HAProxy out of the way for good: stopped, disabled, masked, and
  # with no configuration left to start from.
  #
  # What it does not do is purge the haproxy package, and that is not
  # timidity. `boa-proxy` IS /usr/sbin/haproxy: it terminates TLS and reads
  # the PROXY header in front of gunicorn, in this mode as much as in the
  # other one - in "direct" it is the thing that binds 80 and 443. Purging the
  # package would leave this application with nothing listening at all.
  #
  # A configuration this installer did not write is moved aside rather than
  # deleted. Either way haproxy has nothing to start from - it does not run
  # without /etc/haproxy/haproxy.cfg - and somebody else's file is not this
  # installer's to destroy.
  if [ "${vPortMode}" != "direct" ]; then
    return 0
  fi

  fLog "Serving 80 and 443 directly: taking the machine's HAProxy out of the way."
  systemctl disable --now haproxy.service > /dev/null 2>&1 || true
  # Masked as well. `disable` only keeps it from starting at boot: a package
  # upgrade, a `systemctl start` or another unit's Wants= can still pull it
  # in, and it would take the ports from under a running application. A masked
  # unit cannot be started by anything, which is what retiring it means.
  systemctl mask haproxy.service > /dev/null 2>&1 || true

  if [ -f "${cMachineProxyConfig}" ]; then
    if grep -q "${cMachineProxyMarker}" "${cMachineProxyConfig}" 2> /dev/null; then
      fLog "Deleting ${cMachineProxyConfig}: this installer wrote it, and this mode has no use for it."
      rm -f "${cMachineProxyConfig}"
    else
      local vKept="${cMachineProxyConfig}.before-boa.$(date '+%Y%m%d%H%M%S')"
      mv "${cMachineProxyConfig}" "${vKept}"
      fLog "Moved the HAProxy configuration that was here to ${vKept}: not written by this installer, so kept rather than deleted."
    fi
  fi

  # Whatever else may be holding those two ports. In this mode the proxy
  # cannot start without them, and finding that out from "the application did
  # not answer" a minute later is a much worse way to learn it. The services
  # are stopped by now in every action that reaches here, so nothing of this
  # installation's own is in this list.
  local vHolding=""
  if command -v ss > /dev/null 2>&1; then
    vHolding="$(ss -lnt 2> /dev/null | grep -E "[:.](80|443)([^0-9]|$)" || true)"
  elif command -v netstat > /dev/null 2>&1; then
    vHolding="$(netstat -lnt 2> /dev/null | grep -E "[:.](80|443)([^0-9]|$)" || true)"
  fi
  if [ -n "${vHolding}" ]; then
    fLog "WARNING: something is still listening on 80 or 443, and this mode needs both:"
    echo "${vHolding}" | sed 's/^/      /'
  fi
  return 0
}

fInstallProxyConfiguration() {
  fRequireSourceCode
  fLog "Installing the application HAProxy configuration (${vPortMode})."
  cp "${vSourceDir}/deploy/haproxy/boa.cfg" "${cConfigDir}/haproxy.cfg"

  if [ "${vPortMode}" = "direct" ]; then
    # Serving the public ports itself. Two things change, and both have to:
    # the addresses it binds, and `accept-proxy` - a browser connecting
    # straight to 443 sends no PROXY header, so demanding one would refuse
    # every real client.
    sed -i \
      -e "s#bind 127.0.0.1:${cHttpsPort} accept-proxy ssl#bind 0.0.0.0:443 ssl#" \
      -e "s#bind 127.0.0.1:${cHttpPort}#bind 0.0.0.0:80#" \
      "${cConfigDir}/haproxy.cfg"
    # `%[src]` is already the real client address once nothing is in front of
    # it, so the X-Forwarded-For line needs no change: what it recovered from
    # the PROXY header it now reads from the connection itself.
  fi

  chown "${cAppUser}":"${cAppGroup}" "${cConfigDir}/haproxy.cfg"
  chmod 0640 "${cConfigDir}/haproxy.cfg"
  # Refuse to start with a configuration HAProxy cannot parse, rather than
  # leaving a service that restarts forever.
  if ! /usr/sbin/haproxy -c -f "${cConfigDir}/haproxy.cfg" > /dev/null 2>&1; then
    /usr/sbin/haproxy -c -f "${cConfigDir}/haproxy.cfg" || true
    fDie "The HAProxy configuration is not valid."
  fi

  # The packaged haproxy service is the machine's own proxy, which this
  # installation does not manage. Only our instance is touched.
}

fCreateManagerAgent() {
  fRequireSourceCode
  local vManagerHome="${cAgentsDir}/${cManagerId}"
  if id -u "${cManagerUser}" > /dev/null 2>&1; then
    fLog "Orchestrating agent ${cManagerUser} already exists."
  else
    fLog "Creating orchestrating agent ${cManagerUser}."
    useradd --home-dir "${vManagerHome}" --create-home --shell /bin/bash "${cManagerUser}"
  fi
  mkdir -p "${vManagerHome}"

  if [ ! -f "${vManagerHome}/system-prompt.md" ]; then
    cp "${vSourceDir}/deploy/templates/manager-system-prompt.md" "${vManagerHome}/system-prompt.md"
  fi

  if [ ! -f "${vManagerHome}/info.json" ]; then
    local vCreatedAt
    vCreatedAt=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
    sed -e "s#__AGENT_ID__#${cManagerId}#g" \
        -e "s#__AGENT_NAME__#manager#g" \
        -e "s#__AGENT_DESCRIPTION__#Orchestrating agent. Coordinates the other agents.#g" \
        -e "s#__AGENT_IS_ORCHESTRATOR__#true#g" \
        -e "s#__AGENT_CREATED_AT__#${vCreatedAt}#g" \
        "${vSourceDir}/deploy/templates/agent-info.json" > "${vManagerHome}/info.json"
  fi

  # Token the agent identifies itself with against the local API. It is what
  # lets an agent post to a channel without ever reading that channel's secrets.
    if [ ! -f "${vManagerHome}/api-token" ]; then
      openssl rand -hex 32 > "${vManagerHome}/api-token"
    fi

  # An empty memory, so the agent has somewhere to write from its first run.
    if [ ! -f "${vManagerHome}/memory.md" ]; then
      printf '%s\n' \
        "# Memory" \
        "" \
        "What I want to remember between runs. Everything here is loaded at the" \
        "start of every run, and everything here is paid for on every model" \
        "call, so it is worth keeping short and worth deleting what stopped" \
        "being true." \
        > "${vManagerHome}/memory.md"
    fi

  chown -R "${cManagerUser}":"${cManagerUser}" "${vManagerHome}"
  chmod 00700 "${vManagerHome}"
  chmod 0600 "${vManagerHome}/api-token" "${vManagerHome}/info.json" \
             "${vManagerHome}/memory.md"
}

fRenameSysAdminAgent() {
  # SysAdmin used to be created here, as the second agent of every
  # installation. It is now one of the example agents in backend/agents/examples/,
  # offered when the user presses "+", and called os-watcher.
  #
  # Nothing is created any more: an installation that comes with an agent
  # nobody asked for is an installation that starts with something to switch
  # off. What is left to do is rename the one already out there, so that an
  # existing agent-001 matches what the documentation now calls it.
  #
  # Runs AFTER fProtectAgentConfigFiles, so info.json is always in the one
  # place it is read from. It used to run before it and name the old path
  # inside the home, which stopped being where the file lives.
  #
  # Written with `python3 -c` rather than a here-document, which the project's
  # Bash rules do not allow anywhere.
  local vSysAdminInfo="${cAgentsConfigDir}/${cSysAdminId}/info.json"
  if [ ! -f "${vSysAdminInfo}" ]; then
    return 0
  fi

  if ! grep -q '"name": "SysAdmin"' "${vSysAdminInfo}"; then
    return 0
  fi

  fLog "Renaming the SysAdmin agent to os-watcher."
  python3 -c 'import json, sys
vPath = sys.argv[1]
with open(vPath, encoding="utf-8") as vFile:
  dInfo = json.load(vFile)
dInfo["name"] = "os-watcher"
with open(vPath, "w", encoding="utf-8") as vFile:
  json.dump(dInfo, vFile, ensure_ascii=False, indent=2)
  vFile.write("\n")
' "${vSysAdminInfo}"

  # The heading of its own prompt, so the agent is not told it is called
  # something the interface no longer shows.
  local vPrompt="${cAgentsConfigDir}/${cSysAdminId}/system-prompt.md"
  if [ -f "${vPrompt}" ]; then
    sed -i -e 's/^# SysAdmin$/# os-watcher/' -e 's/\bSysAdmin\b/os-watcher/g' "${vPrompt}"
  fi

  # The index the sidebar reads is a copy of the name, so it has to be told.
  BOA_BASE_DIR="${cBaseDir}" PYTHONPATH="${cWebAppDir}" \
    "${cBaseDir}/venv/bin/python3" -c 'import json, sys
from backend.core import agents
from backend.core import paths
vAgentId = sys.argv[1]
with open(paths.fGetAgentInfoPath(vAgentId), encoding="utf-8") as vFile:
  dInfo = json.load(vFile)
agents.fIndexAgent(vAgentId, dInfo)
' "${cSysAdminId}"
}

fInstallSystemdUnits() {
  fRequireSourceCode
  fLog "Installing the systemd services."
  cp "${vSourceDir}/deploy/systemd/boa-exec.service"      /etc/systemd/system/
  cp "${vSourceDir}/deploy/systemd/boa-agent-api.service" /etc/systemd/system/
  cp "${vSourceDir}/deploy/systemd/boa-buzzer.service"    /etc/systemd/system/
  cp "${vSourceDir}/deploy/systemd/boa-telegram.service"  /etc/systemd/system/
  cp "${vSourceDir}/deploy/systemd/boa-discord.service"   /etc/systemd/system/
  cp "${vSourceDir}/deploy/systemd/boa-web.service"       /etc/systemd/system/
  cp "${vSourceDir}/deploy/systemd/boa-proxy.service"     /etc/systemd/system/
  rm -f /etc/systemd/system/boa-redirect.service
  chmod 0644 /etc/systemd/system/boa-exec.service \
             /etc/systemd/system/boa-agent-api.service \
             /etc/systemd/system/boa-buzzer.service \
             /etc/systemd/system/boa-telegram.service \
             /etc/systemd/system/boa-discord.service \
             /etc/systemd/system/boa-web.service \
             /etc/systemd/system/boa-proxy.service
  systemctl daemon-reload
  fEnableUnit boa-exec.service boa-agent-api.service boa-buzzer.service \
              boa-telegram.service boa-discord.service boa-web.service \
              boa-proxy.service
}

fInstallLogRotation() {
  # The files under /opt/boa/logs grow for as long as the installation lives:
  # gunicorn's access and error logs on both distributions, and on Alpine the
  # seven services' own output, which supervise-daemon appends to a file each
  # because nothing else there collects it. journald caps what the systemd
  # units print; nothing capped these. Weekly, eight kept, compressed.
  #
  # `su boa boa`: logrotate refuses a directory it does not consider root's
  # unless told which user rotates it, and every file here is boa's - the
  # executor's log included, which its service script creates as boa before
  # root writes to it. install.log is not in the list on purpose: root's,
  # 0600, and the one file here somebody may need to read months later.
  # copytruncate, because supervise-daemon and gunicorn keep their file open.
  fLog "Installing the log rotation."
  printf '%s\n' \
    "/opt/boa/logs/boa-*.log /opt/boa/logs/access.log /opt/boa/logs/error.log {" \
    "  su boa boa" \
    "  weekly" \
    "  rotate 8" \
    "  compress" \
    "  delaycompress" \
    "  missingok" \
    "  notifempty" \
    "  copytruncate" \
    "}" \
    > "${cLogRotateConfig}"
  chmod 0644 "${cLogRotateConfig}"
}

fStartServices() {
  fLog "Starting the services."
  fRestartUnit boa-exec.service
  fRestartUnit boa-agent-api.service
  fRestartUnit boa-buzzer.service
  fRestartUnit boa-telegram.service
  fRestartUnit boa-discord.service
  fRestartUnit boa-web.service
  fRestartUnit boa-proxy.service
}

fStopServices() {
  fLog "Stopping the services."
  systemctl stop boa-proxy.service     > /dev/null 2>&1 || true
  systemctl stop boa-redirect.service  > /dev/null 2>&1 || true
  systemctl stop boa-web.service       > /dev/null 2>&1 || true
  systemctl stop boa-discord.service   > /dev/null 2>&1 || true
  systemctl stop boa-telegram.service  > /dev/null 2>&1 || true
  systemctl stop boa-buzzer.service    > /dev/null 2>&1 || true
  systemctl stop boa-agent-api.service > /dev/null 2>&1 || true
  systemctl stop boa-exec.service      > /dev/null 2>&1 || true
}

fGeneratePassword() {
  vPassword=$(openssl rand -base64 32 | tr -dc 'A-Za-z0-9' | cut -c1-24)
  if [ ${#vPassword} -lt 16 ]; then
    fDie "Could not generate a long enough password."
  fi
}

fInitializeDatabase() {
  fLog "Initializing the database and the login account."
  BOA_BASE_DIR="${cBaseDir}" \
  BOA_ADMIN_EMAIL="${vEmail}" \
  BOA_ADMIN_PASSWORD="${vPassword}" \
    "${cVenvDir}/bin/python3" -c 'import sys; sys.path.insert(0, "'"${cWebAppDir}"'"); from backend.core.bootstrap import fInitializeInstallation; fInitializeInstallation()'
  chown -R "${cAppUser}":"${cAppGroup}" "${cDbDir}" "${cKanbanDir}"
  chmod 0600 "${cDbDir}"/*.sqlite "${cKanbanDir}"/*.sqlite
}

fWriteCredentialsFile() {
  # The credentials go into the installation log itself, under a heading, and
  # not into a second file beside it: what the user needs at the end of an
  # install is one path to look at, and the login page names this one.
  fLog "Writing the credentials to ${cInstallLog}."
  local vPortsNote=""
  if [ "${vPortMode}" = "direct" ]; then
    vPortsNote="The application serves 0.0.0.0:443 (HTTPS) and 0.0.0.0:80 (HTTP, redirects to HTTPS) itself."
  else
    vPortsNote="The application serves 127.0.0.1:${cHttpsPort} and 127.0.0.1:${cHttpPort}, behind the machine HAProxy on 80 and 443."
  fi
  local vStamp
  vStamp=$(date '+%Y-%m-%d %H:%M:%S')
  mkdir -p "$(dirname "${cInstallLog}")"
  touch "${cInstallLog}"
  chmod 0600 "${cInstallLog}"
  printf '%s\n' \
    "" \
    "# Bunch of AIgents - credentials generated on ${vStamp}" \
    "" \
    "## Web application login" \
    "URL: https://$(hostname -f 2>/dev/null || hostname)/" \
    "Email: ${vEmail}" \
    "Password: ${vPassword}" \
    "" \
    "## System users" \
    "Web application user: ${cAppUser} (no shell)" \
    "Orchestrating agent: ${cManagerUser} (manager)" \
    "" \
    "## Notes" \
    "Agent users have no password: they are only reachable as root." \
    "This is the only agent created for you. Press + in the web interface to" \
    "add more: it offers a catalogue of examples (os-watcher, mail-watcher and" \
    "others) or an empty agent to write yourself." \
    "${vPortsNote}" \
    >> "${cInstallLog}"
  chown root:root "${cInstallLog}"
  chmod 0600 "${cInstallLog}"
}

fMigrateInstallFiles() {
  # Installations made before this had two files in /root: the log and a
  # credentials file. Whatever is in them is copied into the one file that
  # replaces them - the password in there may be the only copy anybody has -
  # and only then are they removed.
  local vLegacyFile=""
  for vLegacyFile in "${cLegacyCredentialsFile}" "${cLegacyInstallLog}"; do
    if [ ! -f "${vLegacyFile}" ]; then
      continue
    fi
    fLog "Moving ${vLegacyFile} into ${cInstallLog}."
    mkdir -p "$(dirname "${cInstallLog}")"
    touch "${cInstallLog}"
    chmod 0600 "${cInstallLog}"
    printf '%s\n' "" "# Copied from ${vLegacyFile} on $(date '+%Y-%m-%d %H:%M:%S')" "" \
      >> "${cInstallLog}"
    cat "${vLegacyFile}" >> "${cInstallLog}"
    rm -f "${vLegacyFile}"
  done
  if [ -f "${cInstallLog}" ]; then
    chown root:root "${cInstallLog}"
    chmod 0600 "${cInstallLog}"
  fi
}

fRemoveInstallation() {
  fLog "Removing the previous installation."
  fStopServices

  # Delete every agent user along with its crontab.
    local vAgentUser=""
    for vAgentUser in $(getent passwd | sed -n 's/^\(agent-[0-9][0-9][0-9]\):.*$/\1/p'); do
      fLog "Deleting agent ${vAgentUser} and its crontab."
      crontab -u "${vAgentUser}" -r > /dev/null 2>&1 || true
      userdel --remove "${vAgentUser}" > /dev/null 2>&1 || true
    done

  # Every unit this installer has ever written, including the buzzer - which
  # was missing from this list and survived a --reinstall as an orphan pointing
  # at a file that had been deleted - and boa-redirect, which no longer exists.
  rm -f /etc/systemd/system/boa-exec.service \
        /etc/systemd/system/boa-agent-api.service \
        /etc/systemd/system/boa-buzzer.service \
        /etc/systemd/system/boa-telegram.service \
        /etc/systemd/system/boa-discord.service \
        /etc/systemd/system/boa-web.service \
        /etc/systemd/system/boa-proxy.service \
        /etc/systemd/system/boa-redirect.service
  systemctl daemon-reload

  # The log of the run that is happening right now lives inside the tree about
  # to be deleted, so it is put aside and brought back: a --reinstall that
  # takes its own log with it leaves the user without the record of what it
  # just did, and without the password it is about to generate.
  local vSavedLog=""
  if [ -f "${cInstallLog}" ]; then
    vSavedLog=$(mktemp /tmp/boa-install-log.XXXXXXXX)
    cp "${cInstallLog}" "${vSavedLog}"
  fi

  rm -f "${cLogRotateConfig}"
  rm -rf "${cBaseDir}"

  if [ -n "${vSavedLog}" ]; then
    mkdir -p "$(dirname "${cInstallLog}")"
    cp "${vSavedLog}" "${cInstallLog}"
    rm -f "${vSavedLog}"
    chown root:root "${cInstallLog}"
    chmod 0600 "${cInstallLog}"
  fi

  # The log that everything from here on is written to is a new file now, and
  # the tee started at the top of the run is still holding the old one.
  fRestartCapturingOutput

  if id -u "${cAppUser}" > /dev/null 2>&1; then
    userdel "${cAppUser}" > /dev/null 2>&1 || true
  fi
}

fIsInstalled() {
  # A finished installation leaves cInstalledMarker: fMarkInstalled writes it
  # once the application has answered, and nothing else does. An installation
  # that died halfway - a pip that could not download, a network that dropped -
  # has the code and the user and not the marker. It used to count as
  # installed by exactly those two, so `--install` said "already installed",
  # `--update` died on whatever was missing, and only `--reinstall --yes` got
  # past it. Installations made before the marker existed have none either:
  # for those, the four things a finished one always has stand in for it, and
  # the next update writes the marker.
  if [ -f "${cInstalledMarker}" ]; then
    return 0
  fi
  if [ -d "${cWebAppDir}/backend" ] && id -u "${cAppUser}" > /dev/null 2>&1 \
     && [ -x "${cVenvDir}/bin/gunicorn" ] && [ -f "${cDbDir}/boa.sqlite" ] \
     && [ -f "${cCertsDir}/privkey.pem" ]; then
    return 0
  fi
  return 1
}

fMarkInstalled() {
  # Only after fVerifyInstallation: an installation that is in place and does
  # not answer is not one to be counted as finished.
  printf 'finished=%s\n' "$(date '+%Y-%m-%d %H:%M:%S')" > "${cInstalledMarker}"
  chmod 0644 "${cInstalledMarker}"
}

fDoInstall() {
  if fIsInstalled; then
    fLog "Already installed. Use --update to update it, or --reinstall to start over."
    return 0
  fi
  fAskEmail
  fAskPortMode
  fInstallDependencies
  fRequirePython
  fGeneratePassword
  fCreateAppUser
  fCreateDirectoryTree
  fRememberPortMode
  fDownloadSourceCode
  fDeploySourceCode
  fCreateVirtualEnv
  fAskBrowser
  fRememberBrowser
  fInstallBrowser
  fInstallWhisper
  fGenerateCertificates
  fInstallProviderCatalogues
  fInstallProxyConfiguration
  fRetireMachineProxy
  fInstallMachineProxy
  fCreateManagerAgent
  fProtectAgentConfigFiles
  fRenameSysAdminAgent
  fInitializeDatabase
  fInstallSystemdUnits
  fInstallLogRotation
  fStartServices
  fWriteCredentialsFile
  # Asked for the login page before saying a word about having finished. This
  # used to end here, and "Installation finished" was printed on a machine
  # whose web service was restarting every five seconds - the installer had no
  # idea, because nothing had ever asked the application anything. An update
  # has somewhere to go back to and rolls back; a first install has not, so it
  # says plainly that it is not serving and leaves the log to explain why.
  if ! fVerifyInstallation; then
    fDie "Everything is in place but the application does not answer. Nothing was rolled back - there is no previous version on this machine. The reason is in the lines above and in ${cInstallLog}; fix it and run this again with --update."
  fi
  fMarkInstalled
  fLog "Installation finished. The credentials are in ${cInstallLog}."
}

fDoUpdate() {
  if ! fIsInstalled; then
    fDie "Not installed, or an installation that did not finish. Use --install: it picks up where the last one stopped."
  fi

  # Three stages, in this order, and the order is the whole repair.
  #
  # This used to stop the services, delete webapp/ and only then run pip. A
  # pip that failed - no network, an index down, a wheel that would not
  # build - left an installation with its services stopped and its code gone:
  # a machine that was working a minute ago, now needing somebody to notice
  # and to recover it by hand.
  #
  #   1. PREPARE. Everything that can fail, while the old version is still
  #      running and untouched. A failure here stops the update and changes
  #      nothing at all.
  #   2. SWITCH. Stop, move the old code and environment aside, put the new
  #      ones in place, start. Short, and every step of it undoable.
  #   3. VERIFY. Ask the application for a page. If it does not answer, put
  #      the previous version back and say so. Only once it has answered is
  #      the previous version removed.
  fAskPortMode
  fAskBrowser
  fInstallDependencies
  fRequirePython
  fDownloadSourceCode
  fBuildVirtualEnv

  # From here on a failure leaves the machine stopped, so from here on a
  # failure is rolled back: fCleanup reads this flag. The two ways out of the
  # switch clear it: the rollback, and the new version having answered.
  vUpdateSwitched="yes"
  fStopServices
  fDeploySourceCode
  fActivateVirtualEnv
  fRememberBrowser
  fInstallBrowser
  fInstallWhisper
  fCreateDirectoryTree
  fRememberPortMode
  fMigrateSystemPromptFileName
  fProtectAgentConfigFiles
  fRenameSysAdminAgent
  fBuildCombinedCertificate
  fInstallProviderCatalogues
  fInstallProxyConfiguration
  fRetireMachineProxy
  fInstallMachineProxy
  fInstallSystemdUnits
  fInstallLogRotation
  fStartServices

  # `if !` here is deliberate, and it is the one place in this file where it
  # is. It does switch errexit off inside fVerifyInstallation - see the note
  # at the bottom - and that function does nothing but ask curl a question and
  # return a code, so there is nothing for errexit to protect. Everything that
  # CHANGES something is called outside a condition.
  if ! fVerifyInstallation; then
    fRollBack
    fDie "The update was rolled back: the new version did not answer. The previous one is running again."
  fi
  fFinishUpdate
  fMarkInstalled
  fLog "Update finished. Data and agents have been kept."
}

fDoReinstall() {
  fConfirmDestructive "This will DELETE ${cBaseDir} entirely, including every agent, its home directory, its crontab and the kanban board. It cannot be undone."
  fAskEmail
  fAskPortMode
  fRemoveInstallation
  fInstallDependencies
  fRequirePython
  fGeneratePassword
  fCreateAppUser
  fCreateDirectoryTree
  fRememberPortMode
  fDownloadSourceCode
  fDeploySourceCode
  fCreateVirtualEnv
  fAskBrowser
  fRememberBrowser
  fInstallBrowser
  fInstallWhisper
  fGenerateCertificates
  fInstallProviderCatalogues
  fInstallProxyConfiguration
  fRetireMachineProxy
  fInstallMachineProxy
  fCreateManagerAgent
  fProtectAgentConfigFiles
  fRenameSysAdminAgent
  fInitializeDatabase
  fInstallSystemdUnits
  fInstallLogRotation
  fStartServices
  fWriteCredentialsFile
  # Asked for the login page before saying a word about having finished. This
  # used to end here, and "Installation finished" was printed on a machine
  # whose web service was restarting every five seconds - the installer had no
  # idea, because nothing had ever asked the application anything. An update
  # has somewhere to go back to and rolls back; a first install has not, so it
  # says plainly that it is not serving and leaves the log to explain why.
  if ! fVerifyInstallation; then
    fDie "Everything is in place but the application does not answer. Nothing was rolled back - there is no previous version on this machine. The reason is in the lines above and in ${cInstallLog}; fix it and run this again with --update."
  fi
  fMarkInstalled
  fLog "Reinstall finished. The credentials are in ${cInstallLog}."
}

fStartCapturingOutput() {
  # Everything this installer prints, and everything the commands it runs
  # print, into the one file the login screen names.
  #
  # fLog was writing its OWN lines to the log and nothing else. apt, pip, the
  # HAProxy validation and every other subprocess wrote to the terminal, so a
  # failed installation left a log holding "Installing the dependencies." and
  # not one word of the apt error that explained why - which is precisely the
  # detail somebody opens that file to find.
  #
  # Done with a FIFO rather than `exec > >(tee ...)`, which is bash-only, or a
  # pipeline around fMain, which would put fMain in a subshell and undo the
  # `fMain & wait` arrangement that keeps errexit alive. The FIFO redirects
  # this shell's own descriptors and leaves the process structure alone, and
  # it works the same in bash and in the POSIX shell Alpine starts with.
  #
  # tee is started FIRST: opening a FIFO for writing blocks until something
  # opens it for reading.
  vCapturePipe="${vCaptureDir}/output"
  if ! mkfifo "${vCapturePipe}" 2> /dev/null; then
    fLog "Could not create the output pipe; only this script's own lines will be logged."
    return 0
  fi

  tee -a "${cInstallLog}" < "${vCapturePipe}" &
  vTeePid=$!
  exec > "${vCapturePipe}" 2>&1

  # The log holds the generated password, so it is shut before anything else
  # goes into it and again every time fLog writes.
  chmod 0600 "${cInstallLog}" 2> /dev/null || true
  return 0
}

fStopCapturingOutput() {
  # Descriptors back to where they were, so that the last lines this script
  # prints reach the terminal even after the pipe is gone, and tee is waited
  # for so nothing it still held is lost.
  if [ -z "${vTeePid}" ]; then
    return 0
  fi
  exec 1>&3 2>&4
  wait "${vTeePid}" 2> /dev/null || true
  vTeePid=""
  rm -f "${vCapturePipe}"
  return 0
}

fRestartCapturingOutput() {
  # tee holds the log open by INODE, not by name. A --reinstall deletes the
  # whole tree, log included, and puts a fresh copy back: from that moment tee
  # is appending to an inode that has no name any more, so every line to the
  # end of the run is written where nobody can read it. Since fLog stopped
  # writing to the file itself - see the note there - that would be the entire
  # second half of a reinstall, password included.
  if [ -z "${vTeePid}" ]; then
    return 0
  fi
  fStopCapturingOutput
  fStartCapturingOutput
  return 0
}

fRequirePython() {
  # The code is written for Python 3.13 or newer, and says so: the project
  # uses implicit namespace packages, so there is no `__init__.py` anywhere
  # under backend/. On an older interpreter `import backend.core.paths` finds
  # nothing, and what the user sees is seven services that start and die with an
  # ImportError in the journal - which says what is missing and not why.
  #
  # Asked here, before anything is installed, so the answer is one sentence at
  # the top of the log instead of a failure at the end of it.
  local vVersion=""
  vVersion="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])' \
              2> /dev/null || true)"
  if [ -z "${vVersion}" ]; then
    fDie "There is no python3 on this machine. Install it and run this again."
  fi

  if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 13) else 1)' \
       > /dev/null 2>&1; then
    fDie "This needs Python ${cMinimumPythonVersion} or newer and this machine has ${vVersion}. The code uses implicit namespace packages, so an older interpreter cannot import it at all."
  fi
  fLog "Python ${vVersion} found."
  return 0
}

fRequireInstalled() {
  if ! fIsInstalled; then
    fDie "Not installed. There is nothing to back up or to restore into: use --install first."
  fi
}

fCopySqliteDatabase() {
  # A consistent copy of one SQLite database, through SQLite's own backup
  # API and not with cp: both databases run in WAL mode, so a plain copy of
  # the .sqlite file misses whatever is still in the -wal file, and a copy
  # taken while a service writes can be torn in the middle of a page. The
  # virtual environment's python has the module; the sqlite3 command is
  # installed on neither distribution.
  local vSource="$1"
  local vTarget="$2"
  "${cVenvDir}/bin/python3" -c 'import sqlite3, sys
vSource = sqlite3.connect(sys.argv[1])
vTarget = sqlite3.connect(sys.argv[2])
with vTarget:
  vSource.backup(vTarget)
vTarget.close()
vSource.close()' "${vSource}" "${vTarget}"
  chmod 0600 "${vTarget}"
  chown "$(stat -c '%u:%g' "${vSource}")" "${vTarget}"
}

fBackupAgentUsers() {
  # Which system users the agents are, so that a restore on another machine
  # can create them again: same names always, same ids where they are free.
  # And their crontabs, which live in the cron spool and not under /opt/boa.
  local vStaging="$1"
  local vAgentHome=""
  local vAgentId=""
  local vUser=""
  local vCrontab=""
  mkdir -p "${vStaging}/crontabs"
  : > "${vStaging}/agents.txt"
  for vAgentHome in "${cAgentsDir}"/*; do
    [ -d "${vAgentHome}" ] || continue
    vAgentId="$(basename "${vAgentHome}")"
    vUser="agent-${vAgentId}"
    if ! id -u "${vUser}" > /dev/null 2>&1; then
      fLog "Agent ${vAgentId} has no system user: its home is backed up, no user is."
      continue
    fi
    printf '%s %s %s %s\n' "${vAgentId}" "${vUser}" "$(id -u "${vUser}")" \
      "$(id -g "${vUser}")" >> "${vStaging}/agents.txt"
    if vCrontab="$(crontab -u "${vUser}" -l 2> /dev/null)" && [ -n "${vCrontab}" ]; then
      printf '%s\n' "${vCrontab}" > "${vStaging}/crontabs/${vUser}"
    fi
  done
}

fDoBackup() {
  # Everything this installation is and the code is not: the two databases,
  # the keys and channels, the certificates, every agent with its home and
  # its protected files, the skills and the tools, the agent users and their
  # crontabs, and the installation log for the password in it. Not the code,
  # the virtual environment or the browser: --install puts those back.
  #
  # Taken with the services running. The databases go through SQLite's
  # backup API, which gives a consistent copy whatever is being written; a
  # journal line of a run in flight may be cut, and the reader skips a cut
  # line.
  fRequireInstalled
  local vStamp
  vStamp="$(date '+%Y%m%d-%H%M%S')"
  if [ -z "${vBackupPath}" ]; then
    vBackupPath="/root/boa-backup-${vStamp}.tar.gz"
  fi
  if [ -e "${vBackupPath}" ]; then
    fDie "${vBackupPath} already exists. A backup is never written over another: choose a name."
  fi
  fLog "Backing up the installation to ${vBackupPath}."

  # Staged next to the data and not under /tmp, which may be a tmpfs: a home
  # with a browser profile in it can be hundreds of megabytes.
  vStagingDir="$(mktemp -d "${cBaseDir}/backup-staging.XXXXXX")"
  chmod 0700 "${vStagingDir}"
  mkdir -p "${vStagingDir}/db" "${vStagingDir}/kanban"

  fLog "Copying the two databases through SQLite's backup API."
  fCopySqliteDatabase "${cDbDir}/boa.sqlite" "${vStagingDir}/db/boa.sqlite"
  fCopySqliteDatabase "${cKanbanDir}/kanban.sqlite" "${vStagingDir}/kanban/kanban.sqlite"
  fBackupAgentUsers "${vStagingDir}"

  # The installation log, for the password in it: after a restore on another
  # machine it is the one that opens the door. Under another name, so that
  # a restore never writes over the log being written at that moment.
  : > "${vStagingDir}/install.log.backup"
  if [ -f "${cInstallLog}" ]; then
    cp "${cInstallLog}" "${vStagingDir}/install.log.backup"
  fi
  chmod 0600 "${vStagingDir}/install.log.backup"
  printf '%s\n' \
    "format=1" \
    "created=${vStamp}" \
    "host=$(uname -n)" \
    "base_dir=${cBaseDir}" \
    > "${vStagingDir}/manifest.txt"

  # Three files under config/ describe THIS machine - which ports, whether it
  # has a browser, and the proxy configuration generated from both - and are
  # left out, so that a restore does not import another machine's choices.
  #
  # Owners travel by name: a restore maps `boa` and `agent-001` onto the
  # users the new machine has, whatever their uids there.
  # Older installations may not have received audio yet.
  set --
  if [ -d "${cBaseDir}/audio" ]; then
    set -- audio
  fi
  tar -czf "${vBackupPath}" \
    --exclude='config/ports.conf' \
    --exclude='config/browser.conf' \
    --exclude='config/haproxy.cfg' \
    -C "${cBaseDir}" agents agents-config config certificates skills tools "$@" \
    -C "${vStagingDir}" db kanban crontabs agents.txt manifest.txt install.log.backup
  chmod 0600 "${vBackupPath}"
  rm -rf "${vStagingDir}"
  vStagingDir=""
  fLog "Backup written: ${vBackupPath} ($(du -h "${vBackupPath}" | cut -f1))."
  fLog "It holds the API keys, the channel secrets and the login password. Keep it as private as this machine."
}

fRestoreAgentUsers() {
  # The users in agents.txt, created again when missing: same name always,
  # same uid and gid when they are free. The name is what the extraction
  # maps ownership by, so a different uid costs nothing. A user of that name
  # that already exists is kept as it is, and no home is created here: the
  # archive brings it, owner and all.
  local vListFile="$1"
  local vAgentId=""
  local vUser=""
  local vUid=""
  local vGid=""
  [ -f "${vListFile}" ] || return 0
  while read -r vAgentId vUser vUid vGid; do
    [ -n "${vUser}" ] || continue
    if id -u "${vUser}" > /dev/null 2>&1; then
      fLog "Agent ${vAgentId}: user ${vUser} already exists and is kept."
      continue
    fi
    if ! groupadd -g "${vGid}" "${vUser}" > /dev/null 2>&1; then
      groupadd "${vUser}"
      fLog "Agent ${vAgentId}: gid ${vGid} was taken, ${vUser} got another."
    fi
    if ! useradd -u "${vUid}" -g "${vUser}" --home-dir "${cAgentsDir}/${vAgentId}" \
         --no-create-home --shell /bin/bash "${vUser}" > /dev/null 2>&1; then
      useradd -g "${vUser}" --home-dir "${cAgentsDir}/${vAgentId}" \
        --no-create-home --shell /bin/bash "${vUser}"
      fLog "Agent ${vAgentId}: uid ${vUid} was taken, ${vUser} got another."
    fi
    fLog "Agent ${vAgentId}: user ${vUser} created."
  done < "${vListFile}"
}

fRestoreCrontabs() {
  local vCrontabDir="$1"
  local vFile=""
  local vUser=""
  [ -d "${vCrontabDir}" ] || return 0
  for vFile in "${vCrontabDir}"/*; do
    [ -f "${vFile}" ] || continue
    vUser="$(basename "${vFile}")"
    if ! id -u "${vUser}" > /dev/null 2>&1; then
      fLog "No user ${vUser} on this machine: its crontab is not installed."
      continue
    fi
    crontab -u "${vUser}" "${vFile}"
    fLog "Crontab of ${vUser} installed."
  done
}

fDoRestore() {
  # The other half of fDoBackup, onto an installed application: --install
  # first on a new machine, then this. What the machine has is replaced by
  # what the archive holds; an agent the machine has and the archive does
  # not keeps its home on disk and drops out of the interface, because the
  # index of agents is in the restored database.
  fRequireInstalled
  if [ ! -f "${vRestorePath}" ]; then
    fDie "${vRestorePath} does not exist."
  fi
  if ! tar -tzf "${vRestorePath}" manifest.txt > /dev/null 2>&1; then
    fDie "${vRestorePath} is not a backup this installer wrote: it has no manifest.txt."
  fi
  fConfirmDestructive "This will REPLACE the database, the board, the API keys, the channels, the certificates, the skills, the tools and every agent on this machine with the contents of ${vRestorePath}. What this machine has now will be gone."

  fStopServices
  vStagingDir="$(mktemp -d "${cBaseDir}/restore-staging.XXXXXX")"
  chmod 0700 "${vStagingDir}"
  tar -xzf "${vRestorePath}" -C "${vStagingDir}" \
    manifest.txt agents.txt crontabs install.log.backup
  fLog "Restoring the backup taken on $(sed -n 's/^created=//p' "${vStagingDir}/manifest.txt") on $(sed -n 's/^host=//p' "${vStagingDir}/manifest.txt")."
  fRestoreAgentUsers "${vStagingDir}/agents.txt"

  # The database files are replaced whole, so what the OLD database left in
  # its -wal and -shm files must not be read as part of the new one: SQLite
  # would apply that write-ahead log to the restored file.
  rm -f "${cDbDir}/boa.sqlite-wal" "${cDbDir}/boa.sqlite-shm" \
        "${cKanbanDir}/kanban.sqlite-wal" "${cKanbanDir}/kanban.sqlite-shm"
  fLog "Putting the files in place."
  tar -xzpf "${vRestorePath}" -C "${cBaseDir}" \
    --exclude='manifest.txt' --exclude='agents.txt' --exclude='crontabs' \
    --exclude='install.log.backup'
  fRestoreCrontabs "${vStagingDir}/crontabs"

  # The password that opens the restored installation is the one in the
  # backup's own log, not this machine's. The whole log is kept beside this
  # one, and its credential lines are appended here, which is the file the
  # login page names.
  local vRestoredLog
  vRestoredLog="${cLogsDir}/install.log.restored-$(date '+%Y%m%d-%H%M%S')"
  cp "${vStagingDir}/install.log.backup" "${vRestoredLog}"
  chmod 0600 "${vRestoredLog}"
  fLog "=== Credentials of the restored backup, copied from ${vRestoredLog} ==="
  grep -i -e "email" -e "password" "${vRestoredLog}" >> "${cInstallLog}" || true

  # The modes and owners the tree has to have, applied to what was just put
  # in place, exactly as an update applies them.
  fCreateDirectoryTree
  fProtectAgentConfigFiles
  fBuildCombinedCertificate
  rm -rf "${vStagingDir}"
  vStagingDir=""
  fStartServices
  if ! fVerifyInstallation; then
    fDie "The restored installation does not answer. See ${cInstallLog}."
  fi
  fLog "Restore finished. Log in with the email and password of the backup: both are in ${cInstallLog}, under the heading Credentials of the restored backup."
}

fMain() {
  # The cleanup trap is installed here, and not only next to the function, because
  # fMain runs in a child process (see the bottom of this file) and a subshell
  # does not inherit its parent's EXIT trap. Without this line the temporary
  # directory with the downloaded code would be left behind on every run.
  trap fCleanup EXIT

  fParseArguments "$@"
  fCheckRoot
  fCheckDebian
  if command -v python3 > /dev/null 2>&1; then
    fRequirePython
  fi
  fRequireSystemd

  mkdir -p "$(dirname "${cInstallLog}")"
  touch "${cInstallLog}"
  chmod 0600 "${cInstallLog}"

  # The terminal, kept, so that fStopCapturingOutput can put it back.
  exec 3>&1 4>&2
  vCaptureDir="$(mktemp -d)"
  fStartCapturingOutput

  fLog "=== Action: ${vAction} ==="
  fMigrateInstallFiles

  case "${vAction}" in
    install)
      fDoInstall
      ;;
    update)
      fDoUpdate
      ;;
    reinstall)
      fDoReinstall
      ;;
    backup)
      fDoBackup
      ;;
    restore)
      fDoRestore
      ;;
    *)
      fDie "Unknown action: ${vAction}."
      ;;
  esac
}

# fMain is started as a child process, and the `if !` below tests what that
# child returned. Writing it as `if ! fMain "$@"` instead - the shape this
# reads like - would quietly switch `set -e` off for the whole installation:
# bash ignores errexit for any command in the condition of an `if`, and that
# includes every command run by the function it calls, and by the functions
# that one calls. Measured on a machine with no systemd: eight commands failed
# in a row, each one printed its error, the script carried on past all of them
# and ended with "Installation finished". A child process gets the errexit
# setting back, because the suspension does not survive the fork.
fMain "$@" &
vMainPid=$!
if ! wait "${vMainPid}"; then
  # The child has already logged what failed and removed its own temporary
  # directory, so this process has nothing left to clean up and would only
  # repeat the "Exited with code" line.
  trap - EXIT
  echo "The Bunch of AIgents installer failed. See ${cInstallLog}."
  exit 1
fi
