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
  cAgentsDir="/opt/boa/agents"
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
  vEmail=""
  vAssumeYes="no"
  vTempDir=""
  vPassword=""
  vSourceDir=""
  # "proxied": 11080/11443 on localhost, behind the machine's own HAProxy.
  # "direct":  80/443 on every interface, with nothing in front.
  vPortMode=""
  # "yes": download Chromium, so agents can be given the browser tools. The
  #        default, because reading a page without being able to use it is
  #        half of what an agent is usually asked for.
  # "no":  do not. The tools stay listed and say what to run.
  vBrowser=""

fCleanup() {
  local vExitCode=$?
  if [ -n "${vTempDir}" ] && [ -d "${vTempDir}" ]; then
    rm -rf "${vTempDir}"
  fi
  if [ "${vExitCode}" -ne 0 ]; then
    fLog "Exited with code ${vExitCode}. See ${cInstallLog} for details."
  fi
  return 0
}

trap fCleanup EXIT

fLog() {
  local vMessage="$1"
  local vStamp
  vStamp=$(date '+%Y-%m-%d %H:%M:%S')
  echo "[${vStamp}] ${vMessage}"

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
  # sets up is started and kept alive by systemd: six units, the machine's
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
  echo "Usage: $0 <--install|--update|--reinstall> [options]"
  echo ""
  echo "Mandatory flags (pick exactly one):"
  echo "  --install     Install from scratch. Does nothing if already installed."
  echo "  --update      Update code and dependencies, keeping data and agents."
  echo "  --reinstall   Wipe the whole installation, agents included, then install again."
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
          fDie "Only one of --install, --update or --reinstall may be given."
        fi
        vAction="install"
        shift
        ;;
      --update)
        if [ -n "${vAction}" ]; then
          fDie "Only one of --install, --update or --reinstall may be given."
        fi
        vAction="update"
        shift
        ;;
      --reinstall)
        if [ -n "${vAction}" ]; then
          fDie "Only one of --install, --update or --reinstall may be given."
        fi
        vAction="reinstall"
        shift
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
    fDie "Missing mandatory flag: --install, --update or --reinstall."
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

fInstallDependencies() {
  fLog "Installing system dependencies."
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq \
    python3 \
    python3-venv \
    python3-pip \
    python3-dev \
    build-essential \
    libffi-dev \
    openssl \
    haproxy \
    cron \
    curl \
    ca-certificates \
    tar

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
           "${cDbDir}" "${cKanbanDir}" "${cCertsDir}" "${cLogsDir}"

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
  if ! curl -fsSL "${vTarUrl}" -o "${vTempDir}/source.tar.gz"; then
    fDie "Could not download the code from ${vTarUrl}."
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
  rm -rf "${cWebAppDir}"
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

fCreateVirtualEnv() {
  fRequireSourceCode
  fLog "Creating the Python virtual environment at ${cVenvDir}."
  if [ ! -d "${cVenvDir}" ]; then
    python3 -m venv "${cVenvDir}"
  fi
  "${cVenvDir}/bin/python3" -m pip install --quiet --upgrade pip
  "${cVenvDir}/bin/python3" -m pip install --quiet -r "${vSourceDir}/deploy/requirements.txt"
  chown -R root:root "${cVenvDir}"
  chmod -R 00755 "${cVenvDir}"
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
  # Three files in every agent home are not the agent's business to change:
  # info.json says which tools it has been granted and what it may spend,
  # system-prompt.md defines what it is, and api-token is how it identifies
  # itself. They used to sit in the home, which is the agent's own at 0700 -
  # so the agent could rewrite all three. Measured before this was written: an
  # agent added mail.read to its own info.json and the privileged daemon then
  # reported the tool as granted.
  #
  # Owning a file is not what decides whether it can be replaced; the write
  # permission on its DIRECTORY is. So they move into a drawer owned by root
  # that the agent may enter and read and cannot write.
  fLog "Moving each agent's protected files into its root-owned config directory."
  local vAgentHome=""
  local vAgentId=""
  local vConfigDir=""
  local vFileName=""
  for vAgentHome in "${cAgentsDir}"/*; do
    [ -d "${vAgentHome}" ] || continue
    vAgentId="$(basename "${vAgentHome}")"
    vConfigDir="${vAgentHome}/config"
    mkdir -p "${vConfigDir}"
    chown root:"agent-${vAgentId}" "${vConfigDir}"
    chmod 00750 "${vConfigDir}"
    for vFileName in info.json system-prompt.md api-token; do
      if [ -f "${vAgentHome}/${vFileName}" ] && [ ! -f "${vConfigDir}/${vFileName}" ]; then
        fLog "  ${vAgentId}: ${vFileName}"
        mv "${vAgentHome}/${vFileName}" "${vConfigDir}/${vFileName}"
      fi
      if [ -f "${vConfigDir}/${vFileName}" ]; then
        chown root:"agent-${vAgentId}" "${vConfigDir}/${vFileName}"
        chmod 0640 "${vConfigDir}/${vFileName}"
      fi
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

  fEnableUnit haproxy.service
  fRestartUnit haproxy.service
}

fStopMachineProxy() {
  # In "direct" mode the application binds 80 and 443 itself, so a machine
  # HAProxy holding those ports would keep it from starting at all. Only one
  # we wrote is stopped: another one is somebody else's service.
  if [ "${vPortMode}" != "direct" ]; then
    return 0
  fi
  if [ -f "${cMachineProxyConfig}" ] && \
     grep -q "${cMachineProxyMarker}" "${cMachineProxyConfig}"; then
    fLog "Stopping the machine HAProxy this installer wrote: ports 80 and 443 are now served directly."
    systemctl disable --now haproxy.service > /dev/null 2>&1 || true
  fi
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
  # offered when the user presses "+", and called oswatcher.
  #
  # Nothing is created any more: an installation that comes with an agent
  # nobody asked for is an installation that starts with something to switch
  # off. What is left to do is rename the one already out there, so that an
  # existing agent-001 matches what the documentation now calls it.
  local vSysAdminInfo="${cAgentsDir}/${cSysAdminId}/info.json"
  if [ ! -f "${vSysAdminInfo}" ]; then
    return 0
  fi

  if ! grep -q '"name": "SysAdmin"' "${vSysAdminInfo}"; then
    return 0
  fi

  fLog "Renaming the SysAdmin agent to oswatcher."
  python3 - "${vSysAdminInfo}" <<'PYEOF_INNER'
import json
import sys

vPath = sys.argv[1]
with open(vPath, encoding="utf-8") as vFile:
  dInfo = json.load(vFile)

dInfo["name"] = "oswatcher"

with open(vPath, "w", encoding="utf-8") as vFile:
  json.dump(dInfo, vFile, ensure_ascii=False, indent=2)
  vFile.write("\n")
PYEOF_INNER

  # The heading of its own prompt, so the agent is not told it is called
  # something the interface no longer shows.
  local vPrompt="${cAgentsDir}/${cSysAdminId}/system-prompt.md"
  if [ -f "${vPrompt}" ]; then
    sed -i -e 's/^# SysAdmin$/# oswatcher/' -e 's/\bSysAdmin\b/oswatcher/g' "${vPrompt}"
  fi

  # The index the sidebar reads is a copy of the name, so it has to be told.
  BOA_BASE_DIR="${cBaseDir}" PYTHONPATH="${cWebAppDir}" \
    "${cBaseDir}/venv/bin/python3" - "${cSysAdminId}" <<'PYEOF_INNER'
import json
import sys

from backend.core import agents
from backend.core import paths

vAgentId = sys.argv[1]
with open(paths.fGetAgentInfoPath(vAgentId), encoding="utf-8") as vFile:
  dInfo = json.load(vFile)
agents.fIndexAgent(vAgentId, dInfo)
PYEOF_INNER
}

fInstallSystemdUnits() {
  fRequireSourceCode
  fLog "Installing the systemd services."
  cp "${vSourceDir}/deploy/systemd/boa-exec.service"      /etc/systemd/system/
  cp "${vSourceDir}/deploy/systemd/boa-agent-api.service" /etc/systemd/system/
  cp "${vSourceDir}/deploy/systemd/boa-buzzer.service"    /etc/systemd/system/
  cp "${vSourceDir}/deploy/systemd/boa-telegram.service"  /etc/systemd/system/
  cp "${vSourceDir}/deploy/systemd/boa-web.service"       /etc/systemd/system/
  cp "${vSourceDir}/deploy/systemd/boa-proxy.service"     /etc/systemd/system/
  rm -f /etc/systemd/system/boa-redirect.service
  chmod 0644 /etc/systemd/system/boa-exec.service \
             /etc/systemd/system/boa-agent-api.service \
             /etc/systemd/system/boa-buzzer.service \
             /etc/systemd/system/boa-telegram.service \
             /etc/systemd/system/boa-web.service \
             /etc/systemd/system/boa-proxy.service
  systemctl daemon-reload
  fEnableUnit boa-exec.service boa-agent-api.service boa-buzzer.service \
              boa-telegram.service boa-web.service boa-proxy.service
}

fStartServices() {
  fLog "Starting the services."
  fRestartUnit boa-exec.service
  fRestartUnit boa-agent-api.service
  fRestartUnit boa-buzzer.service
  fRestartUnit boa-telegram.service
  fRestartUnit boa-web.service
  fRestartUnit boa-proxy.service
}

fStopServices() {
  fLog "Stopping the services."
  systemctl stop boa-proxy.service     > /dev/null 2>&1 || true
  systemctl stop boa-redirect.service  > /dev/null 2>&1 || true
  systemctl stop boa-web.service       > /dev/null 2>&1 || true
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
    "add more: it offers a catalogue of examples (oswatcher, mailwatcher and" \
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

  rm -rf "${cBaseDir}"

  if [ -n "${vSavedLog}" ]; then
    mkdir -p "$(dirname "${cInstallLog}")"
    cp "${vSavedLog}" "${cInstallLog}"
    rm -f "${vSavedLog}"
    chown root:root "${cInstallLog}"
    chmod 0600 "${cInstallLog}"
  fi

  if id -u "${cAppUser}" > /dev/null 2>&1; then
    userdel "${cAppUser}" > /dev/null 2>&1 || true
  fi
}

fIsInstalled() {
  if [ -d "${cWebAppDir}/backend" ] && id -u "${cAppUser}" > /dev/null 2>&1; then
    return 0
  fi
  return 1
}

fDoInstall() {
  if fIsInstalled; then
    fLog "Already installed. Use --update to update it, or --reinstall to start over."
    return 0
  fi
  fAskEmail
  fAskPortMode
  fGeneratePassword
  fInstallDependencies
  fCreateAppUser
  fCreateDirectoryTree
  fRememberPortMode
  fDownloadSourceCode
  fDeploySourceCode
  fCreateVirtualEnv
  fAskBrowser
  fRememberBrowser
  fInstallBrowser
  fGenerateCertificates
  fInstallProviderCatalogues
  fInstallProxyConfiguration
  fStopMachineProxy
  fInstallMachineProxy
  fCreateManagerAgent
  fRenameSysAdminAgent
  fProtectAgentConfigFiles
  fInitializeDatabase
  fInstallSystemdUnits
  fStartServices
  fWriteCredentialsFile
  fLog "Installation finished. The credentials are in ${cInstallLog}."
}

fDoUpdate() {
  if ! fIsInstalled; then
    fDie "Not installed yet. Use --install."
  fi
  fAskPortMode
  fInstallDependencies
  fDownloadSourceCode
  fStopServices
  fDeploySourceCode
  fCreateVirtualEnv
  fAskBrowser
  fRememberBrowser
  fInstallBrowser
  fCreateDirectoryTree
  fRememberPortMode
  fMigrateSystemPromptFileName
  fRenameSysAdminAgent
  fProtectAgentConfigFiles
  fBuildCombinedCertificate
  fInstallProviderCatalogues
  fInstallProxyConfiguration
  fStopMachineProxy
  fInstallMachineProxy
  fInstallSystemdUnits
  fStartServices
  fLog "Update finished. Data and agents have been kept."
}

fDoReinstall() {
  fConfirmDestructive "This will DELETE ${cBaseDir} entirely, including every agent, its home directory, its crontab and the kanban board. It cannot be undone."
  fAskEmail
  fAskPortMode
  fRemoveInstallation
  fGeneratePassword
  fInstallDependencies
  fCreateAppUser
  fCreateDirectoryTree
  fRememberPortMode
  fDownloadSourceCode
  fDeploySourceCode
  fCreateVirtualEnv
  fAskBrowser
  fRememberBrowser
  fInstallBrowser
  fGenerateCertificates
  fInstallProviderCatalogues
  fInstallProxyConfiguration
  fStopMachineProxy
  fInstallMachineProxy
  fCreateManagerAgent
  fRenameSysAdminAgent
  fProtectAgentConfigFiles
  fInitializeDatabase
  fInstallSystemdUnits
  fStartServices
  fWriteCredentialsFile
  fLog "Reinstall finished. The credentials are in ${cInstallLog}."
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
  fRequireSystemd

  mkdir -p "$(dirname "${cInstallLog}")"
  touch "${cInstallLog}"
  chmod 0600 "${cInstallLog}"
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
