#!/bin/sh

# ------------------------------------------------------------------------------
# Bunch of AIgents - Alpine Linux installer
#
# Usage:
#   ./install-update-reinstall-alpine.sh --install   [--email a@b.c] [--yes]
#   ./install-update-reinstall-alpine.sh --update
#   ./install-update-reinstall-alpine.sh --reinstall [--email a@b.c] [--yes]
#
# WHY THIS ONE IS NOT A BASH SCRIPT, when everything else in this project is:
# a fresh Alpine has no bash. A `#!/bin/bash` here means the one-line install
# cannot work at all - the kernel looks for an interpreter that is not there -
# and `curl ... | bash` fails before reading a single line, because there is
# no bash to pipe into. So this file is POSIX shell, which runs under BusyBox
# ash, under dash and under bash without changing a thing:
#
#   curl -fsSL <raw-url> | sh -s -- --install --email a@b.c      # any Alpine
#   curl -fsSL <raw-url> | bash -s -- --install --email a@b.c    # with bash
#
# Bash is still installed, by fInstallDependencies, because every agent is
# given a bash shell and `bash.run` runs through it. What changes is that the
# installer no longer needs it to start.
#
# What that costs, and what it does not: no arrays, no [[ ]], no ${var//x/y},
# no <(...). `local` is used and is not in POSIX, but BusyBox ash, dash and
# bash all have it, and the alternative - forty functions writing to global
# variables - would be worse in every way that matters.
#
# The script is idempotent: running it twice with the same flag leaves the
# system in the same state.
#
# What differs from the Debian installer, and why:
#
#   - Services are OpenRC scripts in /etc/init.d/, not systemd units, and they
#     are supervised with supervise-daemon, which is what gives them the
#     restart-on-failure the units had. The runtime directories systemd made
#     with RuntimeDirectory= are made by each script's own start_pre.
#   - `shadow` is installed for useradd and userdel. The privileged daemon
#     calls them with long options that BusyBox's adduser does not have, and
#     an agent that cannot be created is the whole application not working.
#   - `bash` is installed: it is the shell every agent is given, and Alpine
#     ships without it.
#   - There is no browser. Playwright publishes no wheel for musl and Alpine
#     packages none, so the Python side of it cannot be installed here at all -
#     and without it there is nothing to drive a Chromium with. The package is
#     left out of the requirements, the browser tools stay listed and say so
#     when an agent calls one, and everything else works. browser.conf is still
#     written, with an `executable=` line ready for the day that changes.
#   - In "direct" mode the capability to bind 80 and 443 as an unprivileged
#     user is put on the haproxy binary with setcap. systemd did it per-service
#     with AmbientCapabilities; OpenRC has no such thing.
# ------------------------------------------------------------------------------

# Abort on any error, and on any unset variable.
#
# `pipefail` is not in POSIX: BusyBox ash and bash both have it, dash does not,
# and this file has to run under all three. Asked for in a subshell first, so
# that the shell without it is not killed by `set -e` on the very line meant to
# make errors visible.
  set -eu
  if (set -o pipefail) 2>/dev/null; then
    set -o pipefail
  fi

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
  # The six OpenRC services, in dependency order: the executor first, because
  # everything else needs it, and the proxy last, because it needs the web.
  lServices="boa-exec boa-agent-api boa-buzzer boa-telegram boa-web boa-proxy"
  # Alpine's own Chromium, for the `executable=` line of browser.conf. It is
  # only of use the day there is a Playwright that runs on musl.
  cSystemChromium="/usr/bin/chromium-browser"
  # Requirements that cannot be installed on musl, dropped from the list with
  # a line in the log rather than with a failure nobody can act on. Playwright
  # ships a Node driver built against glibc: there is no wheel on PyPI and no
  # package in Alpine, and building it is not a thing one does.
  lUnsupportedPackages="playwright"

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
  # "yes": install Chromium, so agents can be given the browser tools.
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

fEnsureOpenRcUsable() {
  # OpenRC refuses to touch a service on a system it did not boot: it prints
  # "you are attempting to run an openrc service on a system which openrc did
  # not boot", names the file it wants, and returns a failure. That is every
  # container and every chroot - PID 1 is sshd, or the shell of a build - and
  # it is where this installer is tested.
  #
  # /run/openrc/softlevel is the file OpenRC writes itself at boot, and the
  # one its own message asks for here. Creating it is what makes rc-service
  # work on such a machine; on a machine OpenRC did boot, it is already there
  # and this does nothing.
  if [ -f /run/openrc/softlevel ]; then
    return 0
  fi
  fLog "OpenRC did not boot this system: PID 1 is not its init (a container, or a chroot)."
  fLog "Creating /run/openrc/softlevel, which is what OpenRC asks for to run services here."
  mkdir -p /run/openrc
  touch /run/openrc/softlevel
  fLog "NOTE: the services will run, but nothing will start them again by itself."
  fLog "      /run is a tmpfs and PID 1 is not OpenRC, so after a restart of this"
  fLog "      container they are stopped and this file is gone. For a machine that"
  fLog "      comes back on its own, give the container /sbin/init as its command."
}

fShowHelp() {
  echo "Bunch of AIgents - Alpine Linux installer"
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
  echo "  --browser <yes|no> Whether to install Alpine's chromium package, which"
  echo "                     is what lets an agent use a site rather than only"
  echo "                     read one. Installed by default. Asked once and"
  echo "                     remembered."
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

fCheckAlpine() {
  if [ ! -f /etc/alpine-release ]; then
    fDie "This installer only supports Alpine Linux. On Debian use install-update-reinstall-debian.sh."
  fi
  # OpenRC is not checked here any more. It is a dependency like haproxy or
  # dcron, it is installed with the rest of them, and an Alpine container image
  # - the thing these installers are tested in - ships without it. Refusing at
  # this point turned "install this on Alpine" into "install OpenRC yourself
  # first, then install this", for a package the installer can perfectly well
  # add. fInstallDependencies checks it once it has been added.
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
  apk update --quiet

  # shadow: useradd and userdel with the long options the privileged daemon
  #   calls them with. BusyBox's adduser does not have them.
  # bash: the shell every agent is given, and what bash.run runs through.
  # dcron: a crond that reads per-user crontabs from /etc/crontabs, which is
  #   how every agent wakes itself up.
  # gcc, musl-dev, libffi-dev, python3-dev: argon2-cffi and friends have no
  #   musl wheels, so pip builds them here.
  # libcap: setcap, for binding 80 and 443 unprivileged in direct mode.
  # openrc: the init this installer writes services for. Every Alpine
  #   installed with setup-alpine has it; an Alpine container image does not,
  #   and there is no reason to send somebody away to install it by hand.
  apk add --quiet --no-progress \
    openrc \
    python3 \
    py3-pip \
    python3-dev \
    gcc \
    musl-dev \
    libffi-dev \
    openssl \
    openssl-dev \
    haproxy \
    dcron \
    bash \
    shadow \
    libcap \
    curl \
    ca-certificates \
    tar

  # Checked now that apk has had its turn, rather than before it: these two are
  # what every service this installer writes is run and supervised by, so an
  # Alpine that still has neither after `apk add openrc` is one where nothing
  # would ever start, and saying so here beats failing six functions later.
  if [ ! -x /sbin/openrc-run ]; then
    fDie "OpenRC is still not installed after apk add openrc. This installer writes OpenRC services."
  fi
  if [ ! -x /sbin/supervise-daemon ]; then
    fDie "supervise-daemon is missing. Without it a crashed service would stay down."
  fi
  fEnsureOpenRcUsable

  # Without a running crond, every agent's schedule is a file nothing reads.
  #
  # dcron replaces BusyBox's crond, which a stock Alpine has in the default
  # runlevel: installing the package takes over /usr/bin/crontab, and the
  # BusyBox service is then left `crashed` in rc-status - two cron daemons
  # reading the same /etc/crontabs would also mean every agent job running
  # twice. So the old one is stopped and taken out of the runlevel first.
  if [ -x /etc/init.d/crond ]; then
    rc-service crond stop > /dev/null 2>&1 || true
    rc-update del crond default > /dev/null 2>&1 || true
  fi
  rc-update add dcron default > /dev/null 2>&1 || true
  rc-service dcron start > /dev/null 2>&1 || true
}

fCreateAppUser() {
  if id -u "${cAppUser}" > /dev/null 2>&1; then
    fLog "System user ${cAppUser} already exists."
  else
    fLog "Creating system user ${cAppUser}."
    # From `shadow`, so that this reads the same as the Debian installer and
    # behaves the same way: a system account with no shell and no password.
    useradd --system --home-dir "${cBaseDir}" --shell /sbin/nologin "${cAppUser}"
  fi
}

fSetCodeModes() {
  # The deployed code: directories 00755, files 0644. Five digits on the
  # directory mode because a four-digit chmod keeps a setgid bit that arrived
  # with the tree.
  #
  # Nothing under webapp/ is executed by path: the daemon runs the runner as
  # `venv/bin/python3 .../runner.py`, and so does the crontab it writes.
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

  # Base directory and code belong to root: the web application cannot rewrite itself.
    chown root:root "${cBaseDir}"
    chmod 00755 "${cBaseDir}"
    fSetCodeModes

  # Only root writes tools, because the web application imports them as code.
    chown root:root "${cToolsDir}"
    chmod 00755 "${cToolsDir}"

  # One browser for the whole installation. On Alpine it is the system
  # package, so this directory holds only what Playwright wants to find.
    if [ -d "${cPlaywrightDir}" ]; then
      chown -R root:root "${cPlaywrightDir}"
      chmod 00755 "${cPlaywrightDir}"
    fi

  # Only root writes skills either: what a skill says goes into the reasoning
  # of an agent nobody is watching, which makes it as sensitive as its system
  # prompt. Readable by everyone, because an agent granted a skill has to be
  # able to read it.
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
  # nothing at all for the group. A mode that grants the group nothing cannot
  # be undone by a later usermod.
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

  # Gunicorn writes a control directory under the service user's home.
    mkdir -p "${cBaseDir}/.gunicorn"
    chown "${cAppUser}":"${cAppGroup}" "${cBaseDir}/.gunicorn"
    chmod 00700 "${cBaseDir}/.gunicorn"

  # Certificates: the private key is read by the proxy to serve TLS.
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
  # Everything the installer copies - the services, the proxy configurations,
  # the agent templates, the provider catalogues, the requirements - is read
  # from the downloaded tree and never from a copy under /opt/boa. So a
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
  # Only what the application runs. `deploy/` is not copied: it is the
  # installer's own material, read from the tree that was just downloaded.
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

  # The requirements, minus what musl cannot have. Written to a file of its
  # own so that the pins of every other package are the ones the project
  # tested, and so that the log says what was dropped and why.
  local vRequirements="${cVenvDir}/requirements-alpine.txt"
  local vPackage=""
  cp "${vSourceDir}/deploy/requirements.txt" "${vRequirements}"
  for vPackage in ${lUnsupportedPackages}; do
    if grep -q "^${vPackage}==" "${vRequirements}"; then
      fLog "Leaving out ${vPackage}: it has no musl build. The browser tools will say so."
      sed -i "/^${vPackage}==/d" "${vRequirements}"
    fi
  done

  # Several of the rest have no musl wheel either and are compiled here, which
  # is why gcc and the -dev packages are installed above. Slow the first time,
  # cached afterwards.
  if ! "${cVenvDir}/bin/python3" -m pip install --quiet -r "${vRequirements}"; then
    fDie "Could not install the Python dependencies. The output above says which one failed."
  fi
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

fMigrateApiKeysDirectory() {
  # The shared provider keys used to live in config/keys, a name that read as
  # "the keys of this installation" and sat one typo away from the per-agent
  # keys/ inside each agent home. They are in config/apikeys now.
  #
  # Only a file with no counterpart in the new directory is moved: a key
  # already written there is the one the application is using.
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
    chown -R "${cAppUser}":"${cAppGroup}" "${cLegacyApiKeysDir}"
    chmod 00700 "${cLegacyApiKeysDir}"
    chmod 0600 "${cLegacyApiKeysDir}"/*
  fi
}

fMigrateSystemPromptFileName() {
  # The system prompt file used to be called SystemPrompt.md. An agent whose
  # prompt the application can no longer find would run with no instructions.
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

fProtectAgentConfigFiles() {
  # Three files in every agent home are not the agent's business to change:
  # info.json says which tools it has been granted and what it may spend,
  # system-prompt.md defines what it is, and api-token is how it identifies
  # itself. Owning a file is not what decides whether it can be replaced; the
  # write permission on its DIRECTORY is. So they live in a drawer owned by
  # root that the agent may enter and read and cannot write.
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
  fRequireSourceCode
  # Model lists, one JSON per provider. Only files that do not exist yet are
  # written: providers ship models faster than this project ships versions, so
  # the user is expected to edit these, and an --update must not undo that.
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
  chmod 00750 "${cProvidersDir}"
  if [ -n "$(ls -A "${cProvidersDir}" 2>/dev/null)" ]; then
    chmod 0640 "${cProvidersDir}"/*
  fi
}

fAskPortMode() {
  # Two ways to serve this, and the right one depends on what else is on the
  # machine, which is why it is a question and not a default. Once chosen it is
  # remembered, so `--update` never asks again and never quietly changes which
  # ports the machine listens on.
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
    "# Change it with: install-update-reinstall-alpine.sh --update --ports <mode>" \
    "mode=${vPortMode}" \
    > "${cPortsFile}"
  chown "${cAppUser}":"${cAppGroup}" "${cPortsFile}"
  chmod 0640 "${cPortsFile}"
}

fAskBrowser() {
  # Nothing to ask. The Debian installer offers the browser because there it
  # is a real choice; here Playwright cannot be installed at all, so an agent
  # has web.fetch and rss.fetch and nothing that clicks.
  #
  # --browser yes is answered rather than refused: somebody running the same
  # command on both distributions should get an installation, not an error,
  # and a line saying what they did not get.
  if [ "${vBrowser}" = "yes" ]; then
    fLog "There is no browser on Alpine: Playwright has no musl build, so nothing can drive a Chromium."
    fLog "Installing without it. Every other tool works; the browser tools say so when called."
  fi
  vBrowser="no"
}

fRememberBrowser() {
  # Two lines, not one. `browser=` is the choice, and `executable=` is where
  # the browser tool has to look: on Alpine that is the system chromium,
  # because the build Playwright downloads is linked against glibc and does
  # not run here at all.
  mkdir -p "$(dirname "${cBrowserFile}")"
  local vExecutable=""
  if [ "${vBrowser}" = "yes" ] && [ -x "${cSystemChromium}" ]; then
    vExecutable="${cSystemChromium}"
  fi
  printf '%s\n' \
    "# Whether a browser is installed for the agents. Written by the installer." \
    "# Change it with: install-update-reinstall-alpine.sh --update --browser <yes|no>" \
    "browser=${vBrowser}" \
    "# The binary the browser tools launch. Empty means whatever Playwright" \
    "# downloaded; on Alpine it is the system package, because a glibc build" \
    "# does not run on musl." \
    "executable=${vExecutable}" \
    > "${cBrowserFile}"
  chown "${cAppUser}":"${cAppGroup}" "${cBrowserFile}"
  chmod 0640 "${cBrowserFile}"
}

fInstallBrowser() {
  # Kept as a step of its own, with the same name as the Debian installer's,
  # so that the two flows read alike and the reason lives in one place.
  fLog "No browser: Playwright has no musl build. The browser tools stay listed and say so."
  return 0
}

fStripMissingErrorFiles() {
  # Debian's haproxy package ships /etc/haproxy/errors/*.http and its stock
  # configuration points at them. Alpine's package ships no such directory, and
  # haproxy refuses to start over a file it cannot open - so the lines naming a
  # file that is not there are removed, and haproxy answers with its own
  # built-in messages instead.
  #
  # Only the missing ones: an administrator who put those files there keeps
  # the pages they wrote.
  local vConfigFile="$1"
  local vErrorFile=""
  local vLine=""
  for vLine in $(sed -n 's/^[[:space:]]*errorfile[[:space:]]\+[0-9]\+[[:space:]]\+\(.*\)$/\1/p' "${vConfigFile}"); do
    vErrorFile="${vLine}"
    if [ ! -f "${vErrorFile}" ]; then
      sed -i "\#^[[:space:]]*errorfile[[:space:]].*${vErrorFile}\$#d" "${vConfigFile}"
    fi
  done
}

fPrepareHaproxyPaths() {
  # Debian's haproxy package makes two directories its stock configuration
  # needs. Alpine's makes neither, and haproxy exits rather than start without
  # them.
  #
  #   /var/lib/haproxy   the chroot. A real directory on disk, so making it
  #                      here is enough.
  #   /run/haproxy       the admin socket. /run is a tmpfs, so anything made
  #                      here is gone at the next boot.
  #
  # The first is created. The second is not: the line naming the socket is
  # removed from the configuration instead. Creating the directory was tried
  # first, with a script in /etc/local.d to remake it on every boot, and it
  # does not work - `local` runs at the END of the boot, so haproxy had
  # already failed to start by the time the directory appeared. The admin
  # socket is a convenience for `socat`; serving traffic does not need it.
  mkdir -p /var/lib/haproxy
  rm -f /etc/local.d/boa-haproxy.start
}

fStripMissingSocketDirectory() {
  # Remove a `stats socket` line whose directory is not there. Only that case:
  # an administrator who created the directory keeps the socket.
  local vConfigFile="$1"
  local vSocketPath=""
  vSocketPath=$(sed -n 's/^[[:space:]]*stats[[:space:]]\+socket[[:space:]]\+\([^[:space:]]*\).*$/\1/p' \
                "${vConfigFile}" | head -n 1)
  if [ -n "${vSocketPath}" ] && [ ! -d "$(dirname "${vSocketPath}")" ]; then
    fLog "Leaving out haproxy's admin socket: $(dirname "${vSocketPath}") is on a tmpfs nothing recreates."
    sed -i '/^[[:space:]]*stats[[:space:]]\+socket[[:space:]]/d' "${vConfigFile}"
  fi
}

fMachineProxyIsPristine() {
  # Whether the HAProxy configuration on this machine is the one its package
  # shipped, byte for byte.
  #
  # It matters because this installer installs haproxy itself: on a fresh
  # machine the file it then finds is the package's example, not a
  # configuration somebody wrote, and treating the two the same turns every
  # first install into a destructive confirmation about nothing.
  #
  # `apk audit --system` looks like the way to ask it and is not: measured on
  # Alpine 3.24, it reports nothing at all for an edited
  # /etc/haproxy/haproxy.cfg. Believing it would mean overwriting somebody's
  # proxy without asking, which is the one thing this check exists to prevent.
  # apk's own database does hold the hash of every file it installed, so that
  # is what is read here - the same question dpkg is asked on Debian.
  local vDirectory=""
  local vFileName=""
  vDirectory=$(dirname "${cMachineProxyConfig}" | sed 's#^/##')
  vFileName=$(basename "${cMachineProxyConfig}")

  local vExpected=""
  vExpected=$(sed -n "\#^P:haproxy\$#,\#^\$#p" /lib/apk/db/installed 2> /dev/null \
              | sed -n "\#^F:${vDirectory}\$#,\#^F:#p" \
              | sed -n "\#^R:${vFileName}\$#,\#^Z:#p" \
              | sed -n 's#^Z:\(.*\)$#\1#p' \
              | head -n 1)
  if [ -z "${vExpected}" ]; then
    return 1
  fi

  # Q1 is sha1 in base64, Q2 is sha256; apk writes one or the other and says
  # which in the first two characters.
  local vActual=""
  case "${vExpected}" in
    Q1*)
      vActual="Q1$(openssl dgst -binary -sha1 "${cMachineProxyConfig}" 2> /dev/null \
                   | openssl base64 2> /dev/null)"
      ;;
    Q2*)
      vActual="Q2$(openssl dgst -binary -sha256 "${cMachineProxyConfig}" 2> /dev/null \
                   | openssl base64 2> /dev/null)"
      ;;
    *)
      return 1
      ;;
  esac
  if [ "${vExpected}" = "${vActual}" ]; then
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
  fPrepareHaproxyPaths
  cp "${vSourceDir}/deploy/haproxy/machine.cfg" "${cMachineProxyConfig}"
  chmod 0644 "${cMachineProxyConfig}"
  fStripMissingErrorFiles "${cMachineProxyConfig}"
  fStripMissingSocketDirectory "${cMachineProxyConfig}"

  if ! /usr/sbin/haproxy -c -f "${cMachineProxyConfig}" > /dev/null 2>&1; then
    /usr/sbin/haproxy -c -f "${cMachineProxyConfig}" || true
    fDie "The machine's HAProxy configuration is not valid."
  fi

  rc-update add haproxy default > /dev/null 2>&1 || true
  if ! rc-service haproxy restart > /dev/null 2>&1; then
    rc-service haproxy restart || true
    fDie "The machine's HAProxy would not start. The output above says why."
  fi
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
    rc-service haproxy stop > /dev/null 2>&1 || true
    rc-update del haproxy default > /dev/null 2>&1 || true
  fi
}

fInstallProxyConfiguration() {
  fRequireSourceCode
  fLog "Installing the application HAProxy configuration (${vPortMode})."
  cp "${vSourceDir}/deploy/haproxy/boa.cfg" "${cConfigDir}/haproxy.cfg"
  fStripMissingErrorFiles "${cConfigDir}/haproxy.cfg"
  fStripMissingSocketDirectory "${cConfigDir}/haproxy.cfg"

  if [ "${vPortMode}" = "direct" ]; then
    # Serving the public ports itself. Two things change, and both have to:
    # the addresses it binds, and `accept-proxy` - a browser connecting
    # straight to 443 sends no PROXY header, so demanding one would refuse
    # every real client.
    sed -i \
      -e "s#bind 127.0.0.1:${cHttpsPort} accept-proxy ssl#bind 0.0.0.0:443 ssl#" \
      -e "s#bind 127.0.0.1:${cHttpPort}#bind 0.0.0.0:80#" \
      "${cConfigDir}/haproxy.cfg"

    # And the one capability the proxy cannot do without. systemd gave it per
    # service with AmbientCapabilities; here it goes on the binary, where it
    # lets any haproxy bind a low port and do nothing else.
    if ! setcap 'cap_net_bind_service=+ep' /usr/sbin/haproxy 2>/dev/null; then
      fLog "WARNING: could not give haproxy permission to bind ports 80 and 443."
      fLog "On a container this needs CAP_SETFCAP. Use --ports proxied instead."
    fi
  fi

  chown "${cAppUser}":"${cAppGroup}" "${cConfigDir}/haproxy.cfg"
  chmod 0640 "${cConfigDir}/haproxy.cfg"
  # Refuse to start with a configuration HAProxy cannot parse, rather than
  # leaving a service that restarts forever.
  if ! /usr/sbin/haproxy -c -f "${cConfigDir}/haproxy.cfg" > /dev/null 2>&1; then
    /usr/sbin/haproxy -c -f "${cConfigDir}/haproxy.cfg" || true
    fDie "The HAProxy configuration is not valid."
  fi
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

fInstallServices() {
  fRequireSourceCode
  fLog "Installing the OpenRC services."
  local vService=""
  for vService in ${lServices}; do
    cp "${vSourceDir}/deploy/openrc/${vService}" "/etc/init.d/${vService}"
    chmod 0755 "/etc/init.d/${vService}"
  done
  for vService in ${lServices}; do
    rc-update add "${vService}" default > /dev/null 2>&1 || true
  done
  # OpenRC caches the dependency tree and decides whether to rebuild it by
  # comparing timestamps with /etc/init.d. On a reinstall the scripts are
  # overwritten within the same second as the previous cache, so it thinks it
  # is still current and the services stay out of it: they start now, because
  # `rc-service start` does not need the tree, and then they do not start at
  # the next boot, because `openrc default` does. Rebuild it unconditionally.
  rc-update -u > /dev/null 2>&1 || true
}

fStartServices() {
  fLog "Starting the services."
  local vService=""
  for vService in ${lServices}; do
    # Said twice on purpose: once quietly, and if that failed, again with its
    # output on the screen, because what OpenRC prints is the only thing that
    # says WHY a service would not start.
    if ! rc-service "${vService}" restart > /dev/null 2>&1; then
      rc-service "${vService}" restart || true
      fDie "The ${vService} service would not start. The output above says why."
    fi
  done
}

fStopServices() {
  fLog "Stopping the services."
  # In reverse order: the proxy first, the executor last, so that nothing is
  # left talking to a socket that has just gone.
  local vService=""
  for vService in boa-proxy boa-web boa-telegram boa-buzzer boa-agent-api boa-exec; do
    if [ -x "/etc/init.d/${vService}" ]; then
      rc-service "${vService}" stop > /dev/null 2>&1 || true
    fi
  done
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
    "This installation runs on Alpine Linux with OpenRC. The services are" \
    "boa-exec, boa-agent-api, boa-buzzer, boa-telegram, boa-web and boa-proxy;" \
    "read their state with: rc-status" \
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
    for vAgentUser in $(sed -n 's/^\(agent-[0-9][0-9][0-9]\):.*$/\1/p' /etc/passwd); do
      fLog "Deleting agent ${vAgentUser} and its crontab."
      crontab -u "${vAgentUser}" -r > /dev/null 2>&1 || true
      rm -f "/etc/crontabs/${vAgentUser}"
      userdel --remove "${vAgentUser}" > /dev/null 2>&1 || true
    done

  # Every service this installer has ever written.
    local vService=""
    for vService in ${lServices}; do
      rc-update del "${vService}" default > /dev/null 2>&1 || true
      rm -f "/etc/init.d/${vService}"
    done

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
  # Dependencies first: the password is generated with openssl, which a fresh
  # Alpine does not have. On Debian it happened to be there already.
  fInstallDependencies
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
  fGenerateCertificates
  fInstallProviderCatalogues
  fInstallProxyConfiguration
  fStopMachineProxy
  fInstallMachineProxy
  fCreateManagerAgent
  fProtectAgentConfigFiles
  fInitializeDatabase
  fInstallServices
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
  fProtectAgentConfigFiles
  fBuildCombinedCertificate
  fInstallProviderCatalogues
  fInstallProxyConfiguration
  fStopMachineProxy
  fInstallMachineProxy
  fInstallServices
  fStartServices
  fLog "Update finished. Data and agents have been kept."
}

fDoReinstall() {
  fConfirmDestructive "This will DELETE ${cBaseDir} entirely, including every agent, its home directory, its crontab and the kanban board. It cannot be undone."
  fAskEmail
  fAskPortMode
  fRemoveInstallation
  fInstallDependencies
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
  fGenerateCertificates
  fInstallProviderCatalogues
  fInstallProxyConfiguration
  fStopMachineProxy
  fInstallMachineProxy
  fCreateManagerAgent
  fProtectAgentConfigFiles
  fInitializeDatabase
  fInstallServices
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
  fCheckAlpine

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
# the shell ignores errexit for any command in the condition of an `if`, and
# that includes every command run by the function it calls, and by the
# functions that one calls. Measured on a machine with no init running: a row
# of commands failed, each one printed its error, the script carried on past
# all of them and ended with "Installation finished". A child process gets the
# errexit setting back, because the suspension does not survive the fork.
# BusyBox ash, dash and bash all behave the same way here, in both halves of
# that sentence.
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
