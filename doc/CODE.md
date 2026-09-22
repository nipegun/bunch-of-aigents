# CODE.md

Technical reference for Bunch of AIgents. Written to be read surgically: jump to
the section you need, do not read it end to end.

## Index

1. [Architecture and design decisions](#1-architecture-and-design-decisions)
2. [Module map](#2-module-map)
3. [Key symbol index](#3-key-symbol-index)
4. [Main flows](#4-main-flows)
5. [Entry point and route map](#5-entry-point-and-route-map)
6. [Impact analysis](#6-impact-analysis)
7. [Extension points](#7-extension-points)

---

## 1. Architecture and design decisions

This is the part that cannot be derived from the code, so it is the part worth
reading.

### The premise

An agent here is a language model with a shell on a server, woken by cron, with
nobody watching. Every structural decision follows from taking that seriously:
the model will eventually do something unintended, so the question is not how
to prevent it but what it can reach when it happens.

### One Linux user per agent

Agent `007` is the system user `agent-007`, owning `/opt/boa/agents/007/` at
mode `0700`. Isolation between agents is the kernel's, not a sandbox written in
Python. An agent cannot read another agent's system prompt, journal or API key
because the filesystem says so.

`/opt/boa/agents/` itself is `root:root 0711`: traversable, not listable. An
agent cannot enumerate the other agents, only fail to open paths it guesses.

This decision is why `bash.run` needs no allowlist. A blocklist on a shell is
theatre — anything that can run `sh` can run whatever the list names — while a
user account is a boundary the kernel enforces.

### What an agent may not rewrite about itself

The home is the agent's own, 0700, and that is the point: its memory, its
journal, its conversation and any script it writes live there. Three files in
it are not its business to change, and they sit OUTSIDE the home, in
`/opt/boa/agents-config/xxx/`, which is `root:agent-xxx 0750` under a
`root:root 0711` parent.

| File | Why it is not the agent's |
|---|---|
| `info.json` | Which tools it has been granted and what it may spend |
| `system-prompt.md` | The definition of what it is supposed to do |
| `api-token` | What it identifies itself to the agent API with |

What makes this work is not the files' owner: it is the directory's. The write
permission on a directory is what decides whether a file in it can be deleted
and replaced, so an agent that owned the directory could delete `info.json`
and write its own whoever owned the file. It may enter this one and read it,
and it may not create, rename or delete anything in it.

**And that rule applies to the drawer as much as to what is in it**, which is
why these no longer live in `agents/xxx/config/`. That path was an entry in
the HOME, the home is the agent's at 0700, and renaming an entry needs write
permission on the parent and nothing else - the mode of the thing being
renamed is never consulted. So the agent could not edit `info.json` and could
do this:

    mv ~/config ~/config-old && mkdir ~/config && echo '...' > ~/config/info.json

and be read from the substitute. Moving the drawer out of the home puts every
directory on the way under root. Two things follow from the move:

  - **There is no fallback to the home any more.** There used to be one, so
    that an update was not a service that stopped answering before the
    migration ran - and it was itself a bypass, since hiding the real file was
    enough to have the agent's own read instead. The daemon now migrates at
    startup as well as the installer doing it, so nothing is left to cover.
  - **Deleting an agent deletes its configuration too.** It is no longer
    inside the home that `userdel --remove` takes away, and left behind it
    would be handed to the next agent given that id.

`fOpenProtectedAgentFile` is the second answer to the same question: it opens
with `O_NOFOLLOW` and checks on the OPEN FILE that it is a regular file, owned
by root, and writable by nobody else. That is what survives a mistaken chmod
during an update or a restore from a backup with the wrong owner.

This was measured before it was fixed, on a real install: an agent appended
`mail.read` to its own `info.json` and the privileged daemon then reported the
tool as granted - so an agent could grant itself the mailbox, the channels, or
raise its own ceilings. It could also replace its own prompt with "ignore all
your rules", which would have stayed that way on every run from then on.

Isolation between agents needs none of this: `/opt/boa/agents/` is
`root:root 0711` and each home is 0700, so the kernel already refuses. That is
why it holds even when a tool has a bug in it.

### What root reads out of the home

The journal, the memory and the chat are the agent's own files: written by
its own processes, in its own 0700 home, and read by the privileged daemon as
root - which reads whatever it is pointed at. Measured on the code before this
existed: a FIFO named `runs.jsonl` held the daemon thread that opened it for
ever, and since the agents list reads every agent's journal, every later
request for that list leaked one more thread; a link named `memory.md`
pointing at any file on the machine had root hand that file's text to the
interface; and a link to something without an end had root read until it was
killed.

So all three are read through `fReadAgentOwnedFile`, which is
`fOpenProtectedAgentFile`'s sibling for the files that ARE the agent's:
`O_NOFOLLOW` refuses a link at the open, `O_NONBLOCK` keeps a FIFO from
holding the open until somebody writes to it, and the checks are made on the
open descriptor - a regular file, owned by the agent's user - so nothing can
be swapped between the check and the read. It never reads more than a bound,
held on what is read and not only on what `fstat` said, because the agent can
append while the read is going on: 32 MB for the journal and for the chat,
read from the END when the file is larger, since the newest lines are what a
history shows; 1 MB for the memory, cut with the same `[truncated]` mark that
`fWrite` leaves. A bad byte costs one line, not the read.

What is refused is said, not swallowed: `read_run_journal`, `read_chat` and
`read_memory` fail with the reason, so an operator learns that something in
that home is not what the application wrote. The one exception is
`read_usage_summary` for every agent, which the sidebar is drawn from: there
one unreadable journal costs that agent its totals, with the reason beside
them, and nobody else theirs.

### What travels on the command line

The daemon starts a run as the agent with `Popen`, and the message the owner
typed - or the prompt a due card builds - used to be one of its arguments:
`--chat-message <text>`, `--prompt <text>`. The command line of a process is
readable by every user of the machine through `/proc/<pid>/cmdline`, and an
agent with `bash.run` is a user of the machine. Measured on the Debian test
machine: `ps` run as `agent-001` showed the message the owner had just sent
to `agent-000`, for as long as that run lived, which by default is up to five
minutes.

So the text goes down the child's standard input and the command line
carries only `--chat-message-on-stdin` or `--prompt-on-stdin`. `fStartRunner`
is the one place that starts a runner: it refuses a text longer than
`cMaxStdinPayloadBytes` before any process exists, because that bound is
below a pipe's 64 KiB buffer and a write that fits in the buffer never waits
for the child - this daemon does not wait for runners. A child that is
already gone when the write happens, an interpreter failing at import, is a
broken pipe and not the daemon's failure. On the other side the runner reads
the text with the same bound, refuses an empty chat message rather than
answering a question nobody asked, and closes the turn it was started for
when it refuses, so the conversation does not wait for ever. `--prompt` and
`--chat-message` stay, for a run started by hand from a terminal.

### What a run may do to the machine

The ceilings in `info.json` - tokens, steps, seconds, runs a day - are
enforced by the runner, and the runner is a program the agent is driving.
What holds when the program is the thing that went wrong is enforced by the
kernel, in two layers.

The runner lowers its own resource limits before it does anything else,
`fApplyResourceLimits`, from the entry point and not from `fMain` - the
tests call `fMain` in-process, and RLIMIT_NPROC lowered inside a developer's
session with thousands of threads already running stops that session
forking. Every process the run starts inherits them: RLIMIT_NPROC at 1024,
counted against the agent's uid as a whole, so a fork bomb from `bash.run`
stops at the number and not at the machine - threads count too, which is why
it is not smaller, a browser being a few hundred of them; no core files; no
file past 4 GiB. Not RLIMIT_AS: Chromium reserves address space by the tens
of gigabytes and would not start. That layer is the same on Debian and on
Alpine, and it is the only one a run started by the agent's own crontab has.

Where systemd is PID 1 the daemon adds the second: `fStartRunner` puts the
run into a transient scope of its own, `boa-agent-<id>-<random>.scope` under
`boa-agents.slice`, with `TasksMax=1024` and `MemoryMax=2G`. `systemd-run
--scope` execs into the command, so the pid is still the runner's and
`/proc` still shows its command line; `setpriv` is what drops to the agent,
because systemd-run has to be root to create the scope. Measured before it
was so: a run was a child of `boa-exec.service`, in the daemon's own cgroup,
and a runaway agent spent the daemon's TasksMax and left it unable to fork.
The scope is also what ends what a run left behind: `bash.run` signals its
own process group, so a command that called `setsid`, or a background child
of one that finished in time, outlived the run; `fWatchRunner` waits for the
run and stops its scope, which reaches everything the run started wherever
it moved itself. A run that was killed - by the memory limit, by an
operator - wrote nothing on the way out, so the same thread records the
finish in the journal and closes the turn in the chat; a run that exited on
its own has done both already, and the turn is checked rather than assumed.

### Where the provider keys live

The keys shared by every agent are in `/opt/boa/config/apikeys/<provider>.key`,
`boa`-owned, the directory `0700` and the files `0600`.

0750 and 0640 would already keep agents out - no agent user is in the `boa`
group - but that rests on every agent's group list staying empty for the life
of the installation, which is one `usermod -aG` away from being false. A mode
that grants the group nothing does not depend on it. `api_keys.fWrite` sets
both modes on every write rather than only on creation, so a directory that
arrives from an older installation is shut the first time a key is saved.

The directory was called `keys` until it was renamed: it read as "the keys of
this installation" and sat one typo away from the per-agent `keys/` inside
each agent home, which is a different thing that an agent *can* read - its own
key, put there to bill it to another account. The installer moves the old
directory across on `--update` and only deletes it once it is empty.

None of this stops an agent from holding the key of the provider it actually
runs on: the agent API hands it that one, it needs it to make the call, and an
agent with `bash.run` could print it. What it stops is an agent reading the
keys of the providers it does not use.

### Seven processes, one of them privileged

| Process | User | Why it exists |
|---|---|---|
| `boa-proxy` | `boa` | HAProxy: terminates TLS, serves both ports |
| `boa-web` | `boa` | Serves the interface and the API, on a Unix socket |
| `boa-exec` | `root` | The only privileged component |
| `boa-agent-api` | `boa` | Holds what agents may use but not read |
| `boa-buzzer` | `boa` | Wakes an agent when one of its cards comes due |
| `boa-telegram` | `boa` | Listens on Telegram and hands what arrives to an agent |
| `boa-discord` | `boa` | The same, for a Discord channel |

The last four are `boa` and not root on purpose: each of them wants something
done as an agent's own user - starting a run, writing into a 0700 home - and
each of them asks `boa-exec` to do it rather than being given the privilege. A
service that can be reached from outside, as the two listeners effectively
can, is the last one that should hold it.

### A virtual environment is not relocatable

`python3 -m venv <path>` writes `<path>` into the shebang of every console
script later installed into it, into `VIRTUAL_ENV` in the activate scripts,
and into the `command` line of `pyvenv.cfg`. The environment is built at
`venv.new` and renamed to `venv`, so all three then name a directory that is
gone.

Measured on a real Debian 13 and a real Alpine 3.24: both installations
completed, both printed "Installation finished", and both left `boa-web`
restarting every five seconds with

```
status=203/EXEC - Failed to execute /opt/boa/venv/bin/gunicorn:
No such file or directory
```

The file was there. Its first line named `/opt/boa/venv.new/bin/python3`,
which was not.

`fBuildVirtualEnv` had a check for exactly this class of failure and it passed,
because it runs `bin/python3` - a SYMLINK to the system interpreter, which
answers from wherever it happens to be. Only a console script has the path
baked in. So the check now also runs `bin/gunicorn --version`, which is the
file the service unit executes, and `fRepointVirtualEnv` rewrites all three
recorded paths while the environment is still at its building name. The
rewrite is verified rather than assumed: if a future pip writes its console
scripts some other way, the installer stops there.

### An update that fails leaves something running

Three stages, and the order is the repair.

An update used to stop the services, delete `webapp/` and only then run pip. A
pip that failed - no network, an index down, a wheel that would not build -
left an installation with its services stopped and its code gone: a machine
that was working a minute ago, needing somebody to notice and recover it by
hand.

| Stage | What happens | What a failure costs |
|---|---|---|
| Prepare | Questions asked, dependencies installed, code downloaded, the new virtualenv BUILT beside the running one and checked that it imports | Nothing. The old version is still running and untouched |
| Switch | Stop, `webapp/` moved to `webapp.previous`, `venv` to `venv.previous`, the new ones put in place, start | Undoable: both previous versions are still on disk |
| Verify | `curl` asks the application for the login page, fifteen times over thirty seconds | `fRollBack` puts both back and starts them again |

That `curl` sends PROXY protocol only in `proxied` mode. In `direct` mode the
bind has no `accept-proxy`, so a PROXY header lands in the TLS handshake and
the request gets no answer at all. It used to be sent in both modes, which
made every `--install --ports direct` end in "did not answer" over an
installation that was serving pages, and every direct `--update` roll itself
back. Confirmed by switching both test machines to `direct` and back: with the
flag tied to the mode, both answered 200 on 443 and then on 11443. A test runs
`fVerifyInstallation` from both installers against a `curl` that records its
arguments, once per mode, and checks that the flag is there in one and gone in
the other.

When that `curl` never gets an answer, `fExplainWhyItDoesNotAnswer` writes
what the machine looked like at that moment into the same log the error points
at: what curl itself says - asked again with `-sS`, so that a refused
connection, a handshake that failed and a request that timed out are told
apart, because `000` is not an HTTP code but curl saying it never got one -
the state of each of the seven services, whether anything is listening on the
port at all, and the last fifteen lines of `boa-proxy.log`, `boa-web.log` and
gunicorn's `error.log`. `fReportServiceStates` is the half that differs
between the two: `rc-service ... status` on Alpine, `systemctl is-active` plus
the journal of `boa-web` and `boa-proxy` on Debian.

It exists because a first install on a fresh Alpine ended at "The application
did not answer on port 11443 (last code: 000)" and the log held nothing else
about it - not which service was down, not whether the port was held, not one
line of what gunicorn had printed. The one file the error names could not
answer the question it was being opened to answer. What to look for in it: a
service that calls itself started next to "nothing is listening on port 11443"
is a process dying and being restarted, because a supervised service that dies
the instant it starts is reported as started by the command that started it.
Four tests RUN both functions - against a `curl` that refuses to connect, an
`ss` that holds the port and one that does not, and an `rc-service` and a
`systemctl` that answer "stopped" and return a failure.

`fRollBack` starts the services in a SUBSHELL, and the `|| true` beside it is
not enough on its own: `fStartServices` calls `fDie` when a service will not
come up, `fDie` calls `exit`, and `exit` ends the shell whatever is written
beside it. Measured on a real Alpine: `boa-proxy` was taken down by OpenRC
while `boa-web` was flapping, the rollback's own start of it lost the race for
the service lock, and the installer died INSIDE `fRollBack`. The rollback had
worked - the previous version was back and answering - but what the operator
was told was "The boa-proxy service would not start", with not one word about
an update having just been rolled back. At that point the account of what
happened is the only thing an operator has.

The previous version is removed by `fFinishUpdate`, and only after the new one
has answered.

`fRollBack` used to run in one place only: when that final `curl` failed.
Between `fStopServices` and that check there are a dozen steps that can die -
a certificate file gone missing, a proxy configuration HAProxy will not parse,
a unit that will not install - and each of them left the services stopped,
the new code in place and `webapp.previous` on disk with nobody putting it
back. The message named what had failed and said nothing about the machine
being down. So `fDoUpdate` sets `vUpdateSwitched` just before stopping the
services, and `fCleanup` - the EXIT trap, which runs whichever way the child
process ends - rolls back when it finds the flag set and the exit code not
zero. The two ways out of the switch clear it: `fRollBack` itself, so the
explicit path does not roll back twice, and `fFinishUpdate`, because once the
new version has answered there is nothing to go back to. Measured on both test
machines with the private key hidden: "Missing certificate files", "Putting
the previous version back", seven services up and the login page answering 200
on the previous code. A test runs the real `fCleanup`, `fRollBack` and
`fFinishUpdate` of each installer through three exits: after the switch,
before it, and after the finish.

`--install` and `--reinstall` have no previous version to keep, so they have
no Switch and no rollback - but they do Verify. They used to end at
`fWriteCredentialsFile`, and "Installation finished" was printed on two real
machines whose web service was restarting every five seconds: nothing had ever
asked the application anything. They now ask for the same login page, and when
it does not come they say so and name the log, because there is nothing on the
machine to go back to.

`pip` itself is pinned. `--upgrade pip` with no version meant two updates of
the same code could resolve differently, which is what pinning the
requirements was for. What is still not pinned is the TRANSITIVE
dependencies - so `pip freeze` is recorded into the environment and the next
update prints what moved, which is the only way anybody would find out.

### An installation that stopped halfway

`fIsInstalled` counted a machine as installed the moment `webapp/backend`
and the `boa` user existed - which is before the virtual environment, the
certificates, the database and the administrator. An install that died at
pip, on a network that dropped, then got "already installed" from
`--install` and a death on whatever was missing from `--update`, and only
`--reinstall --yes` got past it, with nothing telling the operator so.

A finished installation now leaves `/opt/boa/installed`, written by
`fMarkInstalled` only after `fVerifyInstallation` has had its page: an
installation that is in place and does not answer is not finished, and an
update that rolled back is not the new version. Without the marker, the
four things a finished installation always has - the code, the user,
`venv/bin/gunicorn`, `db/boa.sqlite` and `certificates/privkey.pem` - stand
in for it, so an installation from before the marker existed still counts
and gets its marker at the next update. Everything else `--install` does is
already safe to do twice: the user is created only if missing, the
environment is built beside the old one, the certificates are kept when
present, the administrator is deleted and written again with the new
password. So a half-finished installation is finished by running
`--install` once more, and `--update` says exactly that when it finds one.
On the way, `fGeneratePassword` moved after `fInstallDependencies` in the
Debian installer, where it was the other way round: `openssl` is
Priority: optional on Debian, and a minimal image generated the password
before the package that generates it was installed.

### Everything the installer runs reaches its log

`fLog` wrote its own lines to `install.log` and nothing else. apt, pip, the
HAProxy validation and every other subprocess wrote to the terminal, so a
failed installation left a log holding "Installing the dependencies." and not
one word of the apt error that explained why - which is precisely the detail
somebody opens that file to find.

`fStartCapturingOutput` redirects this shell's own stdout and stderr into a
FIFO that `tee` copies to the log and to the terminal. A FIFO rather than
`exec > >(tee ...)`, which is bash-only and Alpine starts without bash, and
rather than a pipeline around `fMain`, which would put it in a subshell and
undo the `fMain & wait` arrangement that keeps errexit alive.

Two consequences, both of which had to be handled:

`fLog` echoed the line AND appended it to the log itself. Once stdout is a tee
that appends to that same file, the second write is a duplicate: a 90-line
installation produced a 185-line log with every line in it twice. `fLog` now
writes to the file only while the capture is not running.

`tee` holds the log open by INODE. A `--reinstall` deletes the whole tree, log
included, and puts a fresh copy back - so from that moment `tee` is appending
to an inode with no name, and with `fLog` no longer writing to the file that
would be the whole second half of the reinstall, generated password included.
`fRestartCapturingOutput` points the capture at the file that now exists.

### Two installers, one application

`deploy/install-update-reinstall-debian.sh` writes systemd units, and **needs
systemd to be PID 1 of the running machine**: a Debian booted with anything
else is not a target, and the installer refuses it rather than installing onto
a machine that would start nothing.
`deploy/install-update-reinstall-alpine.sh` writes OpenRC services into
`/etc/init.d/`, from `deploy/openrc/`, and needs nothing in advance: it
installs OpenRC itself when the machine has none. Both install the same seven processes,
the same tree under `/opt/boa`, the same user model; a test compares the two
step by step and fails when one grows a step the other does not have.

They are not written in the same language, and that is deliberate. The Debian
one is bash, like everything else here. The Alpine one is POSIX shell, with
`#!/bin/sh`, because a fresh Alpine has no bash: with `#!/bin/bash` the kernel
would look for an interpreter that is not there, and

    curl -fsSL <raw-url> | bash -s -- --install

would fail before reading a line, on the machine that needs the one-line
install most. As POSIX it runs under BusyBox ash, dash and bash alike, so the
same file works piped into `sh` on a bare Alpine and into `bash` on one that
already has it. It still installs bash - every agent is given a bash shell -
it just no longer needs one to start. What that costs is arrays, `[[ ]]`,
`${var//x/y}` and `<(...)`; `local` stays, because all three shells have it,
and `pipefail` is asked for in a subshell before being set, because dash does
not. A test refuses each of those constructs, since a shell feature that is
not there fails at install time on somebody else's machine.

What Alpine needs that Debian does not, and why each one is not optional:

| | Why |
|---|---|
| `shadow` | The privileged daemon calls `useradd --home-dir --create-home --shell`. BusyBox's `adduser` has none of those options, and an agent that cannot be created is the whole application not working |
| `bash` | The shell every agent is given, and what `bash.run` runs through. Alpine ships without it, which is also why the Alpine installer is the one file in this project written in POSIX shell rather than bash: `#!/bin/bash` would make `curl ... \| sh` impossible on the machine that needs it most |
| `dcron` | Something has to read the crontabs the daemon writes. Also the reason for the `-d` below |
| `gcc`, `musl-dev`, `libffi-dev`, `python3-dev` | Several requirements publish no musl wheel and are compiled during the install |
| `libcap` | `setcap cap_net_bind_service` on the haproxy binary, in `direct` mode. systemd granted that per service with `AmbientCapabilities`; OpenRC has no equivalent |

Three things the port had to change in code, each one found by installing:

- **`crontab -u <agent>` instead of dropping to the agent.** Debian's
  `crontab` is setgid and any user may run it; Alpine's dcron ships it
  `4750 root:wheel`, so an agent running it gets `Permission denied`. The ways
  to keep the old shape were to put every agent in `wheel` - the group that
  means sudo on most systems - or to loosen a setuid binary of the system's.
  The daemon is root and can name the user instead.
- **`-r` or `-d` when deleting one.** Vixie cron deletes a crontab with `-r`;
  dcron with `-d`, and answers `-r` with a usage message and exit code 2. Only
  trying `-r` left the crontab of a deleted agent behind, still pointing at the
  runner of a user that no longer existed. Both are tried, because what decides
  it is the binary installed, not the distribution's name.
- **`executable=` in `browser.conf`.** Playwright publishes no musl build, so
  on Alpine the package is left out of the requirements entirely and there is
  no browser. The line is read by `browser.fReadConfiguredExecutable` and is
  what a system Chromium would be named in, the day there is a Playwright that
  can drive one.

One more, found by looking at `/proc/<pid>/fd/2` on the Alpine test
machine: `supervise-daemon` sends a process's stdout and stderr to
`/dev/null` unless told otherwise, and nothing else on Alpine collects them -
the units on Debian have journald for that. All seven services wrote nothing
anywhere. Each OpenRC script now names `output_log` and `error_log`, one
file per service under `/opt/boa/logs/`, created as `boa` in `start_pre` so
that logrotate can rotate it as `boa` whoever writes to it.
`fInstallLogRotation`, in both installers, writes `/etc/logrotate.d/boa`
for those files and for gunicorn's two: weekly, eight kept, `copytruncate`
because both writers keep their file open, and never `install.log`, which
is root's and holds the password. The other half of the same finding: the
System tab asked OpenRC about `crond`, BusyBox's cron, while the installer
runs `dcron` in its place, so a healthy Alpine reported cron stopped.
`fPickOpenRcCronService` asks about the first of the two that has a
service script.

And two the installer works around rather than fixes, because they belong to
Alpine's haproxy package: it ships no `/etc/haproxy/errors/`, and no
`/run/haproxy` for the admin socket. Both lines are dropped from the
configuration when their file or directory is not there, which is also correct
on a machine where an administrator did create them. Creating `/run/haproxy`
was tried first, with a script in `/etc/local.d/` to remake it on each boot:
`local` runs at the END of the boot, so haproxy had already failed to start by
the time it appeared.

One more belongs to OpenRC itself: it caches the service dependency tree and
decides whether to rebuild it by comparing timestamps with `/etc/init.d`. On a
reinstall the service scripts are overwritten within the same second as the
cache, so it keeps the old one and the seven services stay out of it - they
start during the install, because `rc-service start` does not need the tree,
and then do not come back after a reboot, because `openrc default` does.
`fInstallServices` ends with an unconditional `rc-update -u`.

### What each installer demands of the machine, and what it installs itself

The Debian installer refuses to run where systemd is not PID 1
(`fRequireSystemd`, called before anything at all is installed). Everything it
sets up is started and kept alive by systemd - the seven units, the machine's
HAProxy, cron - so on such a machine the installation used to finish, report
success and serve nothing: `systemctl` is installed, it answers "System has not
been booted with systemd as init system (PID 1). Can't operate.", and nothing
read that exit code. What it prints now is how to fix it: install `systemd
systemd-sysv dbus`, create the container again with `/sbin/init` as its command,
run the installer again. It says "create again" rather than "restart" because a
running container cannot change its PID 1.

The Alpine installer takes the opposite decision about OpenRC, because there
the missing piece is one it can supply: `openrc` is installed along with the
other packages - a container image ships without it, an Alpine installed with
`setup-alpine` has it - and `fEnsureOpenRcUsable` then creates
`/run/openrc/softlevel`, which is the file OpenRC itself names when it refuses
to touch a service on a system it did not boot. The seven services start in a
container after that. The log says they will not come back on their own,
because `/run` is a tmpfs and PID 1 is not OpenRC.

The two are not inconsistent: systemd cannot be made to work as anything other
than PID 1, and OpenRC can.

### `if ! fMain` turns `set -e` off for the whole installation

Both installers end with fMain started as a child process:

    fMain "$@" &
    vMainPid=$!
    if ! wait "${vMainPid}"; then ...

and not with `if ! fMain "$@"`, which is what it reads like and what they used
to have. A command in the condition of an `if` runs with errexit suspended, and
the suspension is inherited by every function it calls and by every function
those call - which is the entire installation. Measured on a machine with no
systemd: eight commands failed in a row, each one printed its error, the script
carried on past all of them and ended with "Installation finished". A child
process gets errexit back, because the suspension does not survive a fork.
bash, dash and BusyBox ash all behave this way, in both halves of that
sentence, and neither `set -e` inside the function nor a subshell recovers it.

Two consequences of running fMain in a child: `trap fCleanup EXIT` is installed
inside fMain as well, because a subshell does not inherit its parent's EXIT
trap and the downloaded tree under `/tmp` would be left behind on every run;
and the parent clears its own trap before exiting, so the "Exited with code"
line is not printed twice.

`fHasTty` is a fix of the same family: it opens `/dev/tty` and closes it again,
rather than testing `[ -r /dev/tty ]`. The device node is readable by mode on
every system, so that test passed under `ssh host ./installer` with no pty and
the `read` that followed died with ENXIO - a process with no controlling
terminal cannot open it at all.

### The stock haproxy.cfg is not somebody's work

`fInstallMachineProxy` replaces `/etc/haproxy/haproxy.cfg` when it is in
`proxied` mode, and it will not touch a file it did not write without asking
first - the machine's proxy may be carrying other sites. The catch is that the
file it finds on a fresh machine was put there by the haproxy package, which
**this installer installed itself** a minute earlier in `fInstallDependencies`.

Treating that example as somebody's work is what stopped every plain
`--install` dead: no `--yes`, no terminal to answer on, and the run ended at
"Destructive operation with no terminal to confirm on" having already built
the tree, the virtualenv and the certificates. Measured on all four test
machines, Debian and Alpine alike, running exactly the line the README gives.

`fMachineProxyIsPristine` asks the package manager instead of guessing:

- Debian: the md5 dpkg recorded for that conffile (`dpkg-query -W -f
  '${Conffiles}'`) against the file's own md5.
- Alpine: the hash apk recorded for that file, read out of
  `/lib/apk/db/installed` (the `Z:` line under `R:haproxy.cfg`), against
  `openssl dgst` of the file. `Q1` is sha1 in base64, `Q2` is sha256.

`apk audit --system` looks like the Alpine answer and is not: measured on
Alpine 3.24, it reports **nothing** for an edited `/etc/haproxy/haproxy.cfg`.
The first version of this check believed it, and would have replaced
somebody's proxy without asking - the one thing the confirmation exists to
prevent. Tested since with the package's file, with a line added to it, and
with the file this installer writes.

Pristine means it is replaced with a line in the log and no question. Edited
means the old behaviour: left alone on an `--update`, confirmed and backed up
to `.before-boa.<timestamp>` on an install or a reinstall.

### One file for the log and the password

The installer writes `/opt/boa/logs/install.log` and nothing else: what it
did, and at the end of it the credentials it generated. It used to write two
files in /root - `app-web-install.log` and `app-web-credentials.txt` - and two
files in two places is two things to find. `fMigrateInstallFiles` copies what
is in the old ones into the new one before removing them, because the password
in there may be the only copy anybody has.

Three details hold it together:

- `fLog` makes the directory when it is not there. The log lives inside the
  tree the installer is building, so on a first install it does not exist when
  the first line is written, and a `--reinstall` deletes it halfway through.
- `fRemoveInstallation` copies the log aside before `rm -rf /opt/boa` and puts
  it back afterwards, so a reinstall does not take its own record with it.
- The file is `root:root 0600` inside a directory owned by `boa` at 0750.
  `boa` can unlink it - that is what owning the directory means - and cannot
  read the password in it; agents are not in the `boa` group and cannot enter
  the directory at all.

The login page names that path, in `frontend/templates/login.html`, on a line
of its own and coloured with `--colour-path`. It is not in the fourteen
translation files: the sentence above it is translated, the path is the same
everywhere, and a path wrapped into the middle of a sentence is a path
somebody types back wrong.

### The interface speaks en-US until somebody says otherwise

`fGetLanguage` reads the choice out of `localStorage` and, finding none,
returns `en-US`. It used to negotiate with `navigator.languages` first, which
meant a new installation spoke whatever the first browser to open it spoke -
the language of a machine, not a decision. The choice is one control away, in
the corner of the login card and in Settings, and is remembered per browser.

Two bugs lived in the same file and both showed up as "the login form does not
change language until you change it twice":

- `fApplyTranslations` wrote a string only when the loaded file had that key,
  and `textContent` had already been overwritten by the previous language. So
  switching to en-US - which has no file, `dTranslations` is `{}` - changed
  nothing at all, and switching to a language missing one key left that key in
  the language before it. Every translated element's original string is now
  kept in a `WeakMap` the first time it is translated, and a key with no
  translation restores it.
- `fSetLanguage` stored the choice and then called `fLoadTranslations()` with
  no argument, which read the choice back out of storage. In a private window
  the store throws, the read returns the previous language, and the page
  reloads what it was already showing. It passes the language it was given.

`fLoadTranslations` carries a sequence number, so that two changes in quick
succession cannot land out of order and leave the page in a language nobody
asked for. Three things about it were wrong and each showed the user a
language they had not chosen:

- The `lang` attribute was set at the TOP, before the file had been fetched.
  A 404 or a parse error then left the previous language's strings on screen
  under the new language's name: `lang=fr-FR` with Spanish text. Nothing is
  published until the dictionary is in hand, and `fPublish` sets the two
  together because the failure is exactly the two being set apart.
- The sequence was checked BEFORE `await response.json()`. A slow BODY for an
  earlier request landed after a later one had finished. It is checked after
  every await, because the sequence can move across any of them.
- A failure said nothing and left the page in an unknown state. It falls back
  to en-US and reports through `fOnLoadFailed`.

### en-US.json is the source, and the markup is the fallback

The loader short-circuited `en-US` to an empty dictionary, on the grounds that
the markup already carries the en-US text. That is true, and it made
`en-US.json` five hundred keys of dead weight: shipped, listed as a catalogue,
checked by the tests for parity with the other thirteen, and read by nothing.
Correcting a typo in it changed nothing on screen, and the only way to find
that out was to try.

It is fetched like any other language now. The markup text stays as the
fallback it was always described as being: a key the catalogue does not have,
or a catalogue that will not load, still leaves a readable page rather than a
page of blanks. What changed is which of the two is the source.

### Five hundred keys is not a translated interface

Four kinds of visible string carried no key at all, so they stayed English in
all fourteen languages:

| What | How it is translated now |
|---|---|
| The tab title | `data-i18n` on `<title>`, one key per page |
| The API's own failures | A `code` and its `params` travel; the browser writes the sentence in `fDescribeApiError`. `error` stays for what came from outside - a provider's words, a mail server's refusal - which should not have a translation invented for it |
| Example agent descriptions | `template.desc.<id>`, with the file's own English as the fallback, exactly as a tool's description works |
| Theme scheme and description | `theme.scheme.<scheme>` and `theme.desc.<id>`, same bargain. The NAME is not translated: a theme is somebody's palette with a name, and translating "Nord" would help nobody find it |

The last two mean an example or a theme somebody writes for their own
installation keeps its own words rather than disappearing.

The language dropdown on the login page lists codes - `es-ES`, `en-US` - and
not language names. Fourteen names in their own languages made the control as
wide as the card; the code is 80px, and it is what somebody looking for their
own language picks out fastest in a list of codes. The full names stay on the
settings page, which has the room.

### The branch the code is downloaded from

`cRepoBranch` is `main`, the repository's real branch. It was `master`, which
worked only because GitHub redirects the old name after a rename - a redirect
that goes away the day a real `master` branch exists, and that nobody performs
for `--repo-url file:///...`, which is how both installers are tested.

### Why the application ships its own HAProxy

The machine's HAProxy forwards to port 11443 with `send-proxy-v2`, so a PROXY
header arrives **before** the TLS handshake. Gunicorn cannot read it there: its
`proxy_protocol` option parses that header while parsing HTTP, which happens
after TLS is terminated, so the header's bytes land in the handshake and break
it with `WRONG_VERSION_NUMBER`. This was found by deploying, not by testing.

HAProxy accepts both on one bind - `accept-proxy ssl crt ...` - so the
application brings its own instance, which is also the only component listening
on a port. Gunicorn binds a Unix socket instead, which means there is no way
into the application that does not pass through the proxy, and the real client
address survives as `X-Forwarded-For` - without it, the login rate limit would
see 127.0.0.1 for everyone and stop being per address.

It is HAProxy rather than nginx because the deployment already depends on
HAProxy: no new technology for a problem an existing one solves.

The machine's HAProxy must not use `option ssl-hello-chk` on this backend: that
check's ClientHello predates TLS 1.2, so it fails against a bind that requires
it and marks the backend down for ever. The symptom is a 503 from a service
that is running perfectly, which is worth knowing because nothing in the
application's own logs says anything is wrong.

And the check has to knock on 11080, not on 11443. A TCP check against the
TLS bind connects and hangs up without a handshake, and this HAProxy logged
each one as "SSL handshake failure" - measured on the Debian test machine,
64,075 lines in two days, one every two seconds, burying anything real in
the journal. `check-ssl verify none` was tried first and swapped one line for
another: the check's abrupt close arrived while the handshake was still
being finished, and every check logged either that or `ECONNRESET`. Against
11080 the same connect-and-close is a null session that `option dontlognull`
keeps out of the log, both ports belong to one process, and the journal went
quiet: zero lines in thirty seconds with the site answering 200 from outside.

It fixes no `maxconn`, and that is not an oversight. `maxconn 2048` asks the
kernel for 4131 file descriptors and HAProxy exits rather than start without
them: *Cannot raise FD limit to 4131, current limit is 1024 and hard limit is
4096*. Reported from an Alpine LXC running under OpenWrt on a BPI-R3, whose
hard limit is 4096: `boa-proxy` was restarted seventy times over, nothing ever
listened on 11443, and a first install ended at "The application did not
answer on port 11443 (last code: 000)". Both test machines are Proxmox LXCs
with a hard limit of 524288, which is why neither ever showed it, and
`haproxy -c` accepted the file on every one of them - the configuration was
never invalid, the process died at startup. Without `maxconn`, HAProxy sizes
itself from the descriptors it can actually have, which is what its own
message asks for, and `fd-hard-limit 4000` caps what it takes where the limit
is enormous. Measured with one binary at three hard limits: 4096 gives maxconn
1987, 1024 gives 499, 524288 gives 1987. A test starts the real haproxy over
the shipped file under a hard limit of 4096 and requires it to stay up, and
starts it again with the old `maxconn 2048` and requires it to die - a test
that only read the file is how this was missed in the first place.

Three things genuinely need root: creating a system user, installing another
user's crontab, and starting a process as another user. Everything else does
not. So root lives in one small daemon with a **closed vocabulary of verbs**
over a Unix socket, and there is deliberately no verb meaning "run this
command". An attacker reaching that socket can create an unprivileged agent;
they cannot run code as root.

The socket is `0660 root:boa`, and `SO_PEERCRED` is checked on every connection
so that only root and `boa` are served whatever the file mode happens to say
after some future update.

### A change has to come from this site's own pages

The session cookie is `SameSite=Lax`, which keeps a request from another
site from carrying it. It does not keep out another ORIGIN on the same
site: an agent with `bash.run` can serve a page on this very host, on a
port of its own, and a link to it from a chat answer is one click away. A
form there posting to `/api/admin/agents/000/run` is a same-site request,
the cookie travels, and the run starts; being a simple POST with no body,
no preflight stands in its way either. So `fRefuseChangesFromElsewhere`,
a `before_request` on the API blueprint, answers 403 to any POST, PUT,
PATCH or DELETE that did not come from this site's own pages: an `Origin`
header has to name this host and port exactly - `localhost` and
`localhost:8080` are two origins, and the second is exactly the page an
agent could serve - and a `Sec-Fetch-Site` header has to say
`same-origin`. A request with neither is not a browser's, a script or the
tests, and is left to the login to judge, as before. A GET is not gated:
it changes nothing, and a page from elsewhere cannot read the answer,
because there are no CORS headers to let it.

### The agent API, and why it exists at all

Two things belong to `boa` and must not be readable by agents: the kanban
database (an agent that could write it directly could rewrite another agent's
history) and the channel credentials (a bot token is not a message — it is
permanent authority to send).

So agents reach both through `boa-agent-api`, over a second Unix socket that
every agent can open. Authorization is two independent checks:

1. The presented token matches the stored SHA-256 of some agent's token.
2. `SO_PEERCRED` says the calling process belongs to *that* agent's user.

Either alone would be weaker: a leaked token is useless from the wrong account,
and being the right account is useless without the token.

It is a Unix socket rather than HTTPS because there is nothing to gain from TLS
between two processes on one machine, and a self-signed certificate would mean
every agent runs with verification disabled — which is worse than no TLS,
because it looks like security.

### Where state lives, and why it is split

| State | Where | Why there |
|---|---|---|
| Agent configuration | `agents/xxx/info.json` | The agent must read it as itself |
| Agent history | `agents/xxx/runs.jsonl` | The only place an agent can write |
| Shared procedures | `skills/<Name>/SKILL.md` (root, 0755) | Read by every agent given it, written by none |
| Agents index, login, settings | `db/boa.sqlite` (0700 `boa`) | The web process needs it |
| The board | `kanban/kanban.sqlite` (0700 `boa`) | Many concurrent writers |

There are deliberately **no `runs` or `usage` tables**. An agent process cannot
open the `boa`-owned database, and granting it write access would let any agent
rewrite any other's history. Each agent appends to its own journal instead, and
the web application reads those through `boa-exec`. The side benefit is that an
agent still records what it did when the web application is down.

The board is SQLite and not a directory of JSON files because several agents
waking on the same cron minute is the normal case, and only a transaction stops
two simultaneous additions from overwriting each other.

### What a backup holds

`--backup` writes one archive of everything the installation is and the code
is not, and `--restore` puts one in place of what a machine has; both are in
both installers, function for function. The list is the table above turned
into a `tar` line: the two databases, the keys and channels, the certificates,
every agent with its home and its protected files, the skills and the tools.
Around it, three things a `tar` of `/opt/boa` would get wrong:

- **The databases go through SQLite's backup API**, `fCopySqliteDatabase`,
  and not through `cp`. Both run in WAL mode, so a copy of the `.sqlite` file
  misses whatever is still in the `-wal` file, and a copy taken mid-write can
  be torn. The venv's `python3` has the module; the `sqlite3` command is on
  neither distribution. The same reason cuts the other way on restore: the
  old `-wal` and `-shm` files are removed before the restored file is read,
  or SQLite would apply the old log to it.
- **Agent users travel by name.** `agents.txt` records each agent's user,
  uid and gid, and `fRestoreAgentUsers` creates the missing ones with the
  same name always and the same ids when they are free. Ownership in the
  archive is mapped by name on extraction, so a `boa` or an `agent-001` with
  another uid on the new machine still owns its files. Crontabs live in the
  cron spool, not under `/opt/boa`, so they are read out with `crontab -l`
  and put back with `crontab -u`.
- **Three files are left out on purpose**: `config/ports.conf`,
  `config/browser.conf` and the `haproxy.cfg` generated from them describe
  THIS machine, and a restore must not import another machine's choices.
  The installation log travels as `install.log.backup`, under another name so
  that a restore never writes over the log being written at that moment;
  its credential lines are appended to the current log, because the login
  after a restore is the backup's.

The restore is the one action that replaces data and cannot be undone, so it
confirms like a reinstall does. Both functions are run by the tests over a
real tree, under bash and under dash: the archive is checked for what it
holds and leaves out, the tree is damaged in every way a restore has to undo,
and the restore is checked file by file.

### A skill is indexed in the prompt and fetched on demand

An agent's memory is loaded whole into every system prompt, and that is right
for a memory: it is capped at 8000 characters and it is the one thing the agent
cannot work out again.

Skills are not like that. A procedure is a page or two, an agent can be given
several, and most runs need none of them - the disk check does not need the
certificate procedure. Loading them the way the memory is loaded would mean
paying for all of them on every call of every run, and the ceilings in
`info.json` are measured in tokens.

So the prompt carries an index - one line per skill, its name and its
description - and the body is fetched with `skill.read`, once, by an agent that
decided it needs it. Five skills cost about 200 tokens per run instead of
10000, and the one that gets read is charged once rather than on every call.

The description in the header is therefore the load-bearing part: it is what
the agent decides on, and it is what every run pays for whether the skill is
read or not.

### Skills belong to root, like the tools

A tool is owned by root because the application imports it as code. A skill is
not executed by anything, but it is prepended to the reasoning of an agent that
wakes at four in the morning with nobody watching, which makes it exactly as
sensitive as `system-prompt.md` - and that file already lives in a directory
the agent may read and may not write.

So there is no skill editor in the web interface, and no privileged verb for
writing one. Skills are written on the server over SSH. The interface decides
which agent gets which, which is the same thing it does for tools.

The other half of that decision is where they live: `/opt/boa/skills/`, outside
`webapp/`, because `fDeploySourceCode` does `rm -rf` on `webapp` and a
procedure somebody wrote on this server is not something an update is entitled
to delete. Same reasoning, same place in the tree, as `/opt/boa/tools/`.

The application ships none. There is no `backend/skills/` and the installers
copy nothing into that directory: they create it empty, root-owned and 0755.
A skill is a procedure for ONE installation - these hosts, this backup, this
certificate - so a generic one would be a procedure nobody follows, taking up
a line of every prompt of every run to say so. The directory being empty on a
fresh install is the feature working, not a piece missing.


### `deploy/` is not deployed

`/opt/boa/webapp/` holds `backend/` and `frontend/` and nothing else. The
`deploy/` directory - the units, the two HAProxy configurations, the agent
templates, the provider catalogues, `requirements.txt` and the installer
itself - is the installer's own material, and it is read from the tree the
installer has just downloaded into `/tmp`, which is thrown away when it
exits.

That is not only tidiness. Reading the units from a copy under `/opt/boa`
meant installing the units of whatever version happened to be on disk;
reading them from the downloaded tree installs the units of the version
being deployed, which is the only pair that can be reasoned about. Every
one of those reads calls `fRequireSourceCode` first, so a step that ever
runs before the download fails with a sentence instead of copying from
`/deploy/...`.

It is also why `gunicorn.conf.py` sits in `backend/web/` rather than in
`deploy/`: gunicorn reads it on every start, so it has to be a file that is
actually on the server, and the directory that is on the server is the one
holding the code it configures.

What is deployed is `root:root`, directories `00755` and files `0644`, set by
`fSetCodeModes` and by nothing else. Nothing under `webapp/` is executed by
path - the daemon runs the runner as `venv/bin/python3 .../runner.py`, and so
does the crontab it writes for each agent - so no file there needs the
execute bit. It had it anyway until this was one function: `fDeploySourceCode`
set `0644` and `fCreateDirectoryTree`, which runs after it on an update, then
did `chmod -R 00755` over the same tree.

### Telegram gets HTML, and falls back to the words

A model writes markdown. Shown raw, that is `**25G free**` with the asterisks
in the middle of the sentence, which is what arrived on a phone until this.

Telegram renders a small HTML subset - fourteen tags, no attributes worth the
name, and no heading, list or table among them. So `telegram_html` translates
what there is a tag for and finds a readable shape for what there is not:
headings become bold on their own line, list items get a bullet, and a table
becomes a padded `<pre>` block, which is the only way columns stay under each
other on a phone.

Two things about it are load-bearing.

**Escaping comes first.** `&`, `<` and `>` are markup to Telegram, so an agent
reporting `grep <dev> && echo` produces a message Telegram answers with a 400 -
which is to say, a message that never arrives. Every piece of text goes through
`fEscape` before anything wraps it. An href goes through `fEscapeAttribute`,
which also escapes the double quote: a URL containing one would close the
attribute and turn the rest of itself into attributes nobody wrote.

**A rejected message is sent again as plain text.** Whatever the renderer got
wrong, the words are worth more than the formatting, so a 400 is retried
without `parse_mode` and the line goes out unformatted. The fallback logs what
Telegram said, because formatting that silently degrades for ever is formatting
nobody fixes.

**An answer Telegram rejects is dropped, and one it cannot take is kept for
an hour.** `fSay` returns three things and not two: sent, not answered, and
rejected - a 4xx other than 429, `ChannelRejected`, which is Telegram saying
no to this message and meaning it tomorrow too: the bot blocked, the chat
gone, the token revoked. `fDeliverAnswers` used to keep the row on any
failure and try again next pass, and the row is on disk so that a restart
does not lose an answer, so a blocked bot turned the listener into a loop
that never ended: the poll in its quick mode, a read of the chat through the
root daemon and up to two requests to Telegram on every pass, past every
restart. A rejected answer is dropped at once with a line saying so, and an
answer Telegram has not taken within the hour a run is given is dropped too,
for the same reason the other branch gives up on a run that never finished.
Neither loses the answer: it is in the agent's conversation in the web
interface, where it was written first.

The patterns are the same ones `frontend/static/js/markdown.js` uses. Two
renderers disagreeing about what counts as markdown would mean one answer
reading differently in the two places it is shown, and the point of sending
both is that they are the same conversation.


### Discord is polled, and an answer is two thousand characters

Discord is the second channel a person can answer an agent through, and the
half that receives is `discord_listener` - `boa-discord`, the seventh service.
Four things separate it from the Telegram one.

**It polls, over REST.** `GET /channels/<id>/messages?after=<id>`, every five
seconds and every two while an agent is mid-answer. The Gateway is the obvious
alternative and was not taken: it is a WebSocket needing heartbeats, a resume
protocol and a dependency this project does not have, and it needs the Message
Content Intent switched on in the developer portal - without which every
message arrives with `content` empty and nothing says why. Polling also
connects outwards, which is what lets this run on a LAN with nothing
forwarded, exactly as Telegram's long poll does. What it costs is latency
measured in seconds, and twelve requests a minute against a limit of fifty a
second.

**Two thousand characters, not four thousand.** `channels.cMaxMessageLength`
is 4096, which is Telegram's ceiling, and Discord answers 400 to a `content`
longer than 2000. A long answer did not arrive shortened - it did not arrive.
`discord_markdown` cuts it between lines into at most four messages, and a
fenced block a cut lands inside is closed at the end of one and opened again
at the start of the next: without that, one half arrives as plain text and the
other as a block that never ends, which in Discord swallows everything said
after it. Every part is recorded as that agent's, because a person replies to
whichever one is on their screen.

**No buttons, and `!` for commands.** A button press and a slash command are
both *interactions*, and an interaction arrives over the Gateway or over an
HTTPS endpoint Discord can reach. A polled channel sees neither. So `/agents`
is `!agents`, an ordinary message, and the roster is a list of names to type
rather than a column of buttons. `/agents` is accepted as well, because
whoever set up the Telegram bot will type it out of habit.

**An agent's answer mentions nobody.** Every message this sends carries
`allowed_mentions: {"parse": []}`, so an `@everyone` a model writes is text
and not a notification to a whole server. `replied_user` stays on: an answer
should reach the person who asked. A rule at the socket rather than in a
prompt, for the same reason the mail forwarding list is one.

What Discord does not have is Telegram's silence towards strangers. There is
no `chat_id` to compare against: the bot asks for one channel and reads that
channel, so who may talk to the agents is who may write in it. A private
channel is the configuration that matches what `fIsFromTheConfiguredChat`
enforces in code - and it is named in the manual, because it is the whole of
the authorisation.

The webhook this channel had before is still there and still sends. A webhook
cannot read, cannot reply and gets no message id back, so `listen` over one is
refused rather than offered: a switch that does nothing is worse than no
switch.

### One routing, two listeners

`agent_routing` holds what both listeners do identically: which agents exist,
reading a name out of `@News Miner`, `/news_miner` or `@002` with the longest
match winning, what an agent said to close a turn, and the status report. The
protocol stays in each of them - a long poll is not a REST poll, an inline
keyboard is not a list of names, and a reply is `reply_to_message` in one and
`message_reference` in the other.

It was written when the second listener was, and the status report is the
reason. Two copies of that answer would be two answers to "is it running", and
the first thing they would disagree about is how many services there are.

Sending is not in there. It stays in each listener as `fSay`, which is what
lets a test replace one listener's and leave the other alone.

### One browser, shared; one profile, not

`web.fetch` reads a public page and stops there: no session, no form, no
button. The browser is the other thing, and it splits in two:

| | Where | Who owns it |
|---|---|---|
| The browser | `/opt/boa/playwright/` | root, 0755, one copy |
| The profile | `agents/xxx/browser/profile/` | the agent, 0700, one each |

The binary is shared because it is a binary and there is nothing to isolate
about it; a copy per agent would be 600 MB each and an update to do N times.
The profile is not shared, because it holds the cookies: agent 007 logging into
something must not leave agent 008 logged in. That separation is the kernel's,
the same 0700 home everything else of an agent's lives in - which is precisely
what a hosted agent product cannot offer when all of its agents share one
machine and one set of sessions.

Three decisions follow:

**The browser stays open across tool calls within a run.** `browser.click` acts
on what `browser.open` left on the screen, and a run is one process from the
first tool call to the last, so a module-level handle is all the state that
needs. `atexit` closes it; without that, an hourly agent leaves a Chromium
behind on every run and fills the machine by morning.

**Playwright is imported inside the functions, never at module scope.** The
browser tools are listed in the interface whether or not a browser was
installed, and an ImportError at the top would make them vanish from that list
with no explanation anywhere. Imported late, a missing browser is a sentence
saying which command to run.

**Headless, and public addresses only.** What is wanted is the session and the
DOM, not a picture of a window, so a virtual display would be a moving part for
nothing.

"Public addresses only" is enforced by a route handler installed on the
CONTEXT (`browser.fInstallNetworkPolicy`), not by each tool. Checking the URL
in `browser.open` covered exactly one address per run: a page is free to
redirect, and a page an agent was told to read is free to hold a link, an
iframe, an image or a form pointing at `127.0.0.1` - and `browser.click` had
no check at all. On the context it covers navigations, redirects, clicks,
submissions and every subresource, and the sixth browser tool somebody writes
gets it without knowing it exists. What is refused is named in the tool's
answer, because a blocked request is otherwise invisible: the page renders
without it and the agent spends its budget trying again.

Hostnames are resolved once per run and remembered, which bounds rather than
removes the window in which a name could resolve publicly for the check and
privately for the connection. Closing that needs the connection pinned to the
address that was checked, which Chromium does not expose from here.

A session cookie still disappears when the browser closes, in this as in every
browser. What survives is what the site marked to survive.

### What a provider accepts is not what the standard says

Two adapters sent something their provider refuses, and in both cases the
result was the same: every tool call through that provider failed, on every
model, and nothing in the test suite noticed because the suite tested the
pieces rather than the round trip.

| Provider | What was sent | What came back |
|---|---|---|
| Ollama | `kanban__list_cards` decoded back to nothing | The registry refused a tool the agent had not been granted - the name it had just been offered |
| Google | `"additionalProperties": false`, which is correct JSON Schema | `400 - Unknown name "additionalProperties" at 'tools[0].function_declarations[0].parameters'` |

Gemini's `function_declarations[].parameters` is a SUBSET of JSON Schema and
refuses what it does not know rather than ignoring it, so
`fCleanSchemaForGoogle` filters the schema through an allow list, recursively.
An allow list and not a deny list, for the reason every allow list here is
one: the next key somebody adds to a tool schema would otherwise be refused by
Gemini whether or not anybody remembered to add it to a list of things to
strip.

Both were found by running the whole cycle - ask, call a tool, answer that
call - against the real APIs with real keys. `_/temp/probe-defaults.py` is
that check, and it is the only thing that finds this class of bug: a schema
that is valid, a name that is correct, and a provider that will not take it.

### One adapter file per provider

Twenty-five providers, twenty-five files, even though most speak the same
dialect. A single "OpenAI-compatible" adapter looks tidy until one of those
providers changes a field name, and then the fix has to be made without
breaking the other twenty. Each file carries its own provider's quirks:
DeepSeek drops `reasoning_content` before the runner can replay it, llama.cpp
detects a chat template with no tool support, vLLM turns a 404 into the list of
models it does serve, Cloudflare builds its address out of the credential.

What they share is `base.py`: a neutral message shape modelled on
chat/completions, because most of them already speak it, and the Anthropic
adapter translates into content blocks.

They also share `openai_dialect.py`, and the difference between that and a
shared adapter is the point. The dialect module holds the request itself - the
POST, the HTTP errors worth naming, the response parsing - which is not any
provider's quirk. The quirks stay in each file, declared as class attributes
the module reads:

| Attribute | What it decides |
|---|---|
| `cDisplayName` | The name in every error message. "zai request failed" is not what anybody would search for |
| `cMaxTokensField` | `max_tokens` or `max_completion_tokens`, depending on which spelling the provider followed |
| `cToolChoiceMode` | `auto`, `any`, or `omit` for the providers that refuse the field. `auto` is what an agent needs: a model forced to call a tool on every turn never finishes a run |
| `cChatCompletionsPath` | The path after the base URL, for the few that do not use the usual one |
| `cAssistantContentWhenEmpty` | What to send instead of a null `content`, for a provider whose schema refuses null |

### What twenty-two real keys changed

Every provider here was called with a real key, asked a question, given a tool
and then handed the answer to the tool call it made. All twenty-two that have
a key complete that round trip. Seven things only showed up on the second step
- the one a test with a canned response never reaches - and each is now a line
of code with the provider's own words next to it:

- **Perplexity had retired the endpoint.** `chat/completions` answers 403
  "Sonar is now the Agent API. Use /v1/responses instead of /v1/sonar", so
  that adapter was rewritten against the Responses API, and the provider moved
  from being one model to being a router over 48 of them.

- **A key in an error message.** Gemini was called as `?key=...`, so a 503
  from it put the whole key into the error the user reads and the journal
  keeps. The key moved to the `x-goog-api-key` header, and
  `base.fRedactCredentials` now scrubs `key=`, `api_key=`, `access_token=` and
  `token=` out of every error any adapter produces, because that failure mode
  should not depend on one adapter remembering.
- **Gemini 3 wants its thought signature back.** A conversation whose function
  calls return without the signature it issued is refused outright, so every
  Gemini agent failed the moment it had used a tool. `ToolCall.dProviderData`
  carries it there and back, opaque to everything else.
- **Cloudflare refuses a null `content`.** Which is exactly what an assistant
  message holds when the model answered with tool calls and no words. It gets
  `""`; the dialect keeps sending null to everyone else, because null is what
  the dialect specifies.
- **Reasoning written into the reply.** MiniMax answers with
  `<think>...</think>` in the text itself. Stripped in the dialect module and
  not in one adapter, because the model does it, so the same model behind a
  gateway does it too - and only when the reply STARTS with the tag, so that a
  model writing about HTML keeps its words.
- **Together leaves the channel name in front.** gpt-oss writes in channels and
  Together returns "finalThe weather in Madrid"; Groq and Cerebras, serving the
  same model, do not. Stripped in `together.py`, where a quirk of one provider
  belongs.
- **Four default models the provider would not serve.** Fireworks' 20b needs
  its own deployment, Together's is not serverless, Moonshot retired
  kimi-k2.5, and gemini-3.7-flash answers 503 "experiencing high demand". A
  default that fails on the first run is worse than one version behind.

Five adapters do not use it at all, because their API is not that one:
Anthropic's content blocks, Google's `generateContent`, llama.cpp's
`/completion`, Cohere's v2 chat - which takes the same messages but answers
with text in blocks, an uppercase finish reason of its own, and token counts
nested under `usage.tokens` - and Perplexity, which retired chat/completions
altogether and answers it with

    403 Sonar is now the Agent API. Use /v1/responses instead of /v1/sonar

so that adapter speaks the Responses API: one `input` list instead of
`messages`, the system prompt as `instructions`, and a reply that arrives as
output items - a `message` with its text in blocks, or a `function_call` -
rather than as a choice. A tool result goes back as an item of its own,
`function_call_output`, matched by `call_id`.

Two names get resolved before anything else sees them, through
`factory.dProviderAliases`: `gemini` is what Google's documentation calls the
API and `google` is what every agent's `info.json` has said since the first
version, so both reach the same adapter and only one of them is ever stored.

Which of the twenty-five an agent may be set to is decided in `fListProviders`,
not in the browser: a provider is `selectable` when it is self-hosted or its
key is stored. It is a filter on what is worth offering, not a rule - a key can
also live in the agent's own home, where the web application cannot look, so
the interface still shows an agent the provider it is already set to.

That same flag decides one thing in the interface: the **Base URL** box, on
both the main model and the backup, is shown for a self-hosted provider and
hidden for a cloud one. `base.fInit` already falls back to the adapter's
`cDefaultBaseUrl`, so for a cloud provider the field asked a question that was
answered before it was asked - and the only answer it could take that the
default does not give is a wrong one. It is hidden and not emptied: an
installation that puts a proxy in front of a cloud provider has that address
stored, and hiding a box is not a reason to discard what is in it.

One thing `base.py` hides from all of them is the name of a tool. This project
calls a tool `family.action`; a provider validates the name of a function
against `^[a-zA-Z0-9_-]+$` and refuses the whole request over the dot, with no
hint as to which field was wrong. `fToolNameToWire` swaps the dot for `__` on
the way out and `fToolNameFromWire` swaps it back on the way in, in every
adapter, so the registry, the interface, `info.json` and the logs never see the
encoded form.

### Ceilings, not trust

Every run stops at the first of four ceilings: tokens, steps, seconds, runs per
day. They exist because an unattended loop on a paid API is an open invoice and,
on a self-hosted model, a GPU that never comes back. `max_tokens` for each
request shrinks by what the run has already spent, so a run cannot exceed its
budget by one last expensive call.

Four things make the difference between a ceiling and a suggestion, and each
of them was one of the two until it was fixed:

  - **No floor under the token request.** `max(512, remaining)` asked for 512
    tokens when the budget was spent, so an agent with one token left was
    still allowed half a page.
  - **Each call gets the time that is LEFT**, not the whole run timeout. The
    adapter's own `vTimeoutSeconds` is moved before every call, rather than
    adding a parameter to the twenty-six adapters that implement
    `fSendMessages`.
  - **The deadline is checked before every tool**, not once per step. A batch
    of six tool calls arriving just before the deadline used to run in full,
    each with its own timeout on top of a run that was already over.
  - **A monotonic clock.** `time.time()` moves when NTP steps it, and a run
    that started "in the future" never reaches its timeout at all.

What is still not bounded is the prompt. A call spends its input plus its
output and only the output is capped here, so a long conversation overshoots
on the way in; counting it would mean running each provider's own tokeniser
over the conversation before every call. The closing answer after a ceiling is
also deliberately over budget, and says so where it is written.

### One run of an agent at a time

Two locks, because there are two kinds of caller.

The daemon holds a `threading.Lock` per agent across "is this agent running"
and "start the process". It serves every request on its own thread, so two
`run_now` calls with `only_if_idle` were two threads of one process with
nothing between them - and a /proc sweep cannot see a process that has not
been forked yet. Measured: two simultaneous calls, two runs.

The runner takes an `flock` on `<home>/run.lock` and holds it for the length
of the process. That one is the authority, because a crontab starts the runner
directly and never comes through the daemon. It is not a permission boundary -
an agent with `bash.run` can start whatever it likes - it exists so the
APPLICATION does not start the same agent twice, spending two budgets on one
browser profile and one conversation.

### A run that never started says so

The privileged daemon starts the runner with stdin, stdout and stderr on
`/dev/null`. Everything `fLogLine` writes therefore goes nowhere, and two
failures used to live entirely in that output:

- the run lock was held, so this run is not happening;
- something failed before `fExecute` wrote `run_started` - an unreadable
  `info.json`, or a provider whose API key has not been set, which is by far
  the likelier of the two.

Measured on a real installation: with the lock held, `POST /agents/001/run`
answered `202 {"started": true}` and nothing appeared in the journal, in
`journalctl`, or in any file. The same failure under cron WAS visible, because
cron keeps the output of what it starts - which is why this lasted as long as
it did. The hole was only ever in the path the interface uses.

`fRecordRunRefused` writes it into the journal instead, as a finish with
status `refused` and no `run_id`. Every part of that shape is load-bearing:

| Part | Why |
|---|---|
| `kind: run_finished` | History renders finishes. A kind of its own would need the interface to learn it, and an entry nothing renders is the same as no entry |
| `status: refused` | `failed_runs` counts finishes whose status is `failed`. Nothing of the agent ran, so nothing of the agent failed |
| no `run_started` | `runs` and `max_runs_per_day` count starts. A held lock must not eat one of the day's runs for a run that did not happen |
| `run_id: ""` | Nothing started, so there is no run to identify |

Written only when nothing else wrote it. Once `fExecute` has a run id it has
already written `run_started`, and its own handlers write the matching
`run_finished` before re-raising, so `fMain` checks `vRun.vRunId` before
adding a second finish for one run. The same check decides who closes the chat
turn: `fExecute`'s handlers close it as they record the finish, and `fMain`
closes it only for a run that never got that far. Measured before it was so,
on the Debian test machine: every run that could not reach its provider
answered its question twice, with the same sentence.

### History shows the newest, and it did not

`fReadEntries` returns a journal oldest first - it says so in its own
docstring - and `fRenderRunHistory` took `.slice(0, cShownRuns)` of it. That
is the ten OLDEST runs. An agent with more than ten runs behind it had a
History that never changed again.

Found by driving the real application with a real browser, which is the only
way it could have been found: every other test of `dashboard.js` in this
project reads the file and looks for a string in it, and the string was there.
Measured on a real installation, in three languages: an agent whose most
recent run had just been refused for want of an API key showed a provider
failure from forty minutes earlier, and the refusal never appeared at all.

`.slice(-cShownRuns).reverse()`: the last ten, newest at the top, which is
what the heading over the list says.

The summary table above that list had two faults of its own, both found in the
same screenshot: it printed `last_status` raw, so a Spanish page read "Último
estado: refused", and it printed `last_run_at` raw, so a bare
`2026-09-19T03:44:29Z` sat directly above a list of cleaned timestamps. Both
now go through what the rows below them already used.

### A mailbox is the one input anybody can write to

The four `mail.*` tools follow the channels exactly: the agent names what it
wants done, and the agent API - which runs as `boa` and holds the credentials -
does it. An agent that could read the mailbox password would not have "access
to the inbox"; it would have the account, every message in it, for ever, and
the ability to send as its owner.

What is different about mail is the direction the input travels. An agent
reading a mailbox is an agent whose instructions arrive, in part, inside the
messages it reads, written by anybody in the world. Three decisions follow:

  - **Forwarding is allowed only to addresses the user listed**, and that list
    is checked inside `mailbox`, in the process that opens the connection -
    never in the prompt. A rule in a prompt is advice; a rule at the socket is
    a rule. With no list, forwarding is refused outright.
  - **Reading marks nothing as seen** (`BODY.PEEK[]` on a read-only select), so
    an agent looking at a mailbox does not take away the unread count the
    person was relying on.
  - **Deleting moves to Trash** where the account has one. What an agent
    removes on a rule written last month, a person can still find. "This
    account has no trash folder" and "the folder list could not be read" are
    kept apart, because only the first of them may end in an expunge: they
    used to arrive at `fDeleteMessage` as the same empty string, so one
    unparsed LIST line turned every `mail.delete` into a permanent one.

### Shipped with one agent, offered many

The installation creates exactly one agent: the orchestrator. Everything else
is an EXAMPLE, in `backend/agents/examples/`, one Markdown file each, offered when the
user presses "+". An installation that arrives with agents nobody asked for is
one that starts with things to switch off.

The body of the file IS the system prompt and the header is `key: value` lines
between two `---` rules. That shape follows from what a template is worth: the
useful part of an agent is its prompt, and a prompt is text, so the file is
edited like a document rather than like a data structure. Dropping a file in
that directory adds an example - the same arrangement as themes and tools, and
for the same reason: no list in the code to keep in step.

Creating from one names the TEMPLATE and nothing else. The server reads the
file: a request that could carry its own tools and its own schedule would let
the browser hand an agent a permission the user never ticked.

The dialog puts the EMPTY agent first and the examples under it. Every example
is a shortcut to the empty one, and somebody who already knows what they want
should not read the whole catalogue to reach the plain choice. The examples
keep the order `fListTemplates` returns, which is by the name the reader sees.

One of them, `web-navigator`, has no crontab. It is the example for the browser
- it opens pages, logs in, clicks and fills forms, where the rest read - and
that work is whatever the user just asked for, not something to do at four in
the morning. Its prompt is where the rules that a browser with a session needs
are written down: never type a credential, never complete a purchase or a
send, and treat the page as data rather than as instructions.

### Two ways to serve it, chosen at install time

Either 11080 and 11443 on localhost with an HAProxy in front on 80 and 443, or
80 and 443 served directly. The installer asks, remembers the answer in
`config/ports.conf`, and an update never asks again nor quietly changes which
ports the machine listens on.

The difference is not only the numbers: `accept-proxy` has to come off the bind
in direct mode, because a browser connecting straight to 443 sends no PROXY
header and a bind demanding one refuses every real client.

In `direct` mode the machine's own HAProxy is not merely left alone: it is
retired. `fRetireMachineProxy` stops it, takes it out of every runlevel on
Alpine, disables **and masks** it on Debian, and then deletes
`/etc/haproxy/haproxy.cfg` when this installer wrote it or moves it to
`haproxy.cfg.before-boa.<date>` when somebody else did. Stopping it is not
enough on its own: one left enabled takes 80 and 443 at the next boot, before
this application ever runs, and under systemd a package upgrade, another
unit's `Wants=` or a plain `systemctl start` can bring even a disabled one
back. A masked unit cannot be started by anything, and haproxy with no
`/etc/haproxy/haproxy.cfg` has nothing to start from. Whatever still holds 80
or 443 after that is named in the log, because in this mode the proxy cannot
start without them and reading it from "the application did not answer" half
a minute later is a much worse way to find out.

What is deliberately NOT done is removing the haproxy package. `boa-proxy` IS
`/usr/sbin/haproxy` - it terminates TLS and reads the PROXY header in front of
gunicorn, and in `direct` mode it is the very thing that binds 80 and 443 - so
purging the package would leave the application with nothing listening at all,
in either mode. What is retired is the machine's HAProxy *service*, which is a
different thing that happens to use the same binary. Going back to `proxied`
unmasks the unit before enabling it, or the way back would end at "The
machine's HAProxy would not start" over a mask this installer had put there
itself.

Measured on both test machines with `--update --ports direct`: the unit ended
masked on Debian and in no runlevel on Alpine, `/etc/haproxy` was left without
a configuration, and the application answered 200 on 443 and 301 on 80. The
way back, `--update --ports proxied`, left it enabled and active again with
200 on 11443 and on 443. Seven tests RUN the function against fake service
commands, over a configuration with the marker and one without, in both modes,
and one of them fails if a future version ever reaches for `apk del haproxy`
or `apt-get purge haproxy`.

### A confirmation is shown where the user is looking

`Settings saved` used to be written at the top of the content column. That is fine on
a short panel and useless on a long one: the Save button at the bottom of an
agent's Tools tab produced a message several screens above it, outside what
the browser was drawing, so saving looked like it did nothing.

It is now a pop-up centred over the content column, on a `fixed` layer that is
a sibling of that column rather than a child of it. `fixed` is the point:
centring inside the column would land in the middle of the *document*, which
on a long tab is the same bug a few screens lower. The layer stops at the
sidebar, because a message drawn over the agent list would look like it
belonged to the agent list, and it takes no pointer events, so nothing behind
it stops working while a message is up.

How long it stays is a preference of this browser (`boa.noticeSeconds`,
Settings → Interface), next to the theme and the language and for the same
reason: three seconds is plenty for one word and not enough for a sentence,
and which of the two a message is depends on who is reading it. Errors are
the exception and ignore the number entirely — an error waits to be closed,
because it is the one message that has to still be there when the user looks
back at the screen.

A message has three colours, and the third one exists because of what the
other two cannot say. Green is a save that happened, red is a failure, and
amber is **`No changes to save`**: Save was pressed and the form held exactly
what is already stored. Reporting that in green is worse than saying nothing -
"Settings saved" after a save that wrote nothing is the one sentence that
would stop somebody noticing their edit never took - and red would claim a
failure where nothing went wrong.

Every form that saves checks it the same way: the payload it *would* send,
compared as JSON against the snapshot taken when the form was filled from the
server, or after the last save. An agent's settings build that payload in one
function, `fCollectAgentPayload`, used both to save and to take the snapshot,
because two readers of the same form that drifted apart would report "no
changes" on the one field one of them never looked at. The browser preference
panels already kept such a snapshot, for the "unsaved changes" hint, and it
answers this question too.

The exception is a **new** agent: its form is holding the example's own values
and has never been saved, so pressing Save writes them and moves on to the
chat rather than saying there is nothing to do.

### Colour is state, movement is activity

The ring around an agent's avatar carries two different facts and draws them on
two different channels, so that neither has to be looked up. Whether the agent
is switched on is a colour that does not move: green or red. Whether it is
working right now is movement: a lit segment travels clockwise round that green
ring. A second static colour for "busy" would be a convention to learn, whereas
something turning is understood without being taught.

It is drawn as an SVG rounded rectangle laid exactly over the border, stroked
with a dash whose offset is animated, so the **shape stays still and only the
light moves along it**. That is the whole reason for the SVG: rotating a ring
instead — a conic gradient, an arc, anything under `transform: rotate` — turns
the shape as well, and the corners stop lining up with the rounded square
underneath. `pathLength="100"` normalises the outline, so the stylesheet talks
in percentages of the perimeter and nothing has to be recomputed if the avatar
or its radius changes.

Answering "who is busy?" means reading every process's command line, which only
root can do, so it is a verb on the privileged daemon. One sweep of `/proc`
answers for every agent at once — not one call per agent — and that is what
makes it cheap enough for the sidebar to ask every five seconds. The same sweep
backs `only_if_idle`, so the buzzer and the interface cannot disagree about
whether an agent is working.

### A card that comes due is announced in the conversation

An agent's chat is the record of everything that agent was asked to do, not
only of what was typed at it. So when the buzzer starts a run for a due card,
that card is written into the agent's `chat.jsonl` as a turn of its own, and
the run's answer closes it: opening the conversation shows the work arriving,
what the agent did about it and what it cost.

Three decisions hold it together.

**It is written when the run starts, not when the card is made.** A card
scheduled for tonight and deleted this afternoon never ran, and a conversation
saying it was handed over would be a record of something that did not happen.
The buzzer only ever sees cards that are still on the board, so writing at the
moment of the buzz is what makes the announcement true.

**The file stores the card's fields, not a sentence.** `role: "card"` carries
the id, the title, who assigned it and whether it was asked for straight away;
the text of the message is the card's own instructions. Every word around them
is written by the interface, in the user's own language — the same rule that
makes a stopped run record `ceiling: "tokens"` rather than an English phrase.

**"Now" and "at 13:45" have to be told apart, and by the time the agent is
woken both are in the past.** So the board records which was asked for
(`run_mode`) instead of working it out afterwards from the clock, and the word
`now` travels from the browser to `kanban.fValidateRunAt` as a word, turning
into a timestamp in the one place that also records what it was.

The writing is the privileged daemon's job, not the buzzer's: `chat.jsonl`
lives in a 0700 home owned by the agent, and the buzzer runs as `boa`. The
daemon forks, drops to the agent, writes the announcement and only then starts
the run — and if the home cannot be written to, the run starts anyway. The
announcement is the record of the work, not the work.

The reverse failure is not benign and is handled the other way round: if the
process cannot be started **after** the turn was opened, the daemon writes the
failure into that turn before raising. Nothing else would ever close it, and an
open turn does not merely leave a card unanswered — it shuts the composer for
that agent for good.

The run that follows is neither a plain scheduled run nor a chat turn. It
writes its answer back to the chat, because the question is there, but the
conversation is **not** replayed to it: its prompt is the card, and replaying
ten exchanges would charge every scheduled run for a conversation nobody is
having. In the runner those are two separate flags — `vWritesToChat` and
`vIsChat` — and that distinction is the whole of it. The corollary is that a
run which stops before asking the model anything (a switched-off agent, the
daily ceiling) must still close the turn, or the interface waits for an answer
for ever and the composer stays shut.

### The API documentation is a page of this application

It renders from the OpenAPI spec this project builds, rather than by loading
Swagger UI from a CDN, because the production server is a LAN box that may
have no outbound internet at all. Two things follow from it being one of our
own pages rather than a foreign widget.

It **follows the chosen language**. The specification stays in English - it is
the contract of an API whose field names, ids and error strings are all en-US,
and a translated `openapi.json` would describe an API that does not exist.
What is translated is the page: `fAnnotateSpecForTranslation` hangs a
`data-i18n` key on every piece of English before rendering, and the browser
swaps it the same way it does on every other page. That keeps the strings in
the frontend `.json` files next to all the others, and it works for an
anonymous reader too. The keys are derived from the text and the path rather
than written by hand, so a new endpoint brings its own; a key with no
translation keeps the English, which is what `fApplyTranslations` does with a
key it does not know.

It **fills the column it is given**, like every other page. It used to keep a
900px measure and centre itself, which reads well for prose and badly for
this: the page is mostly parameter tables and blocks of JSON, and those were
being squeezed into a third of a wide screen with empty gutters either side.

### Image attachments are an explicit tool permission

`browser.screenshot` saves a file; `image.send` attaches it to the current
reply. The latter is a separate grant, included in the web-navigator template.
The tool snapshots the PNG into `agents/<id>/attachments/<opaque-id>.png`
with a 0700 directory and 0600 file. Overwriting the original screenshot later
does not change an earlier reply. `ToolContext.lAttachments` carries the
references to `AgentRun.fRecordChatAnswer` or its failure/run report.

Only the executor reads those private files for the web process. Its
`read_chat_attachment` verb requires a reference in that agent's recorded chat,
opens every directory component without following links, and checks that the
image is a regular file owned by the agent. It reads PNGs in 1 MiB chunks;
base64 replies stay below the existing RPC limit even for a 50 MiB attachment.
The authenticated HTTP endpoint streams the bytes with `private, no-store`.
The frontend builds local image URLs from IDs, never from model-supplied URLs.

Telegram uses [sendPhoto](https://core.telegram.org/bots/api#sendphoto) for
eligible images and [sendDocument](https://core.telegram.org/bots/api#senddocument)
for tall or large captures, with the original PNG. The private file is uploaded
as multipart data; no public URL or agent access to bot credentials is needed.
`telegram_deliveries` records acknowledged text and image parts for each pending
turn. Retries resume with the missing part, and removing the pending row clears
those checkpoints. Permanent failures are reported to the user. Both inboxes
compare SQLite's UTC timestamps with Unix time; interpreting them as local
time made recent deliveries expire during daylight-saving time.

### No build step

The frontend is Jinja2 templates, plain CSS and plain JavaScript. The
production target is a self-hosted Debian or Alpine box; a deployment that
needs a Node
toolchain to change a stylesheet is a deployment that rots. For the same reason
`/api/doc/` renders its own OpenAPI spec rather than loading Swagger UI from a
CDN: a LAN server may have no outbound internet, and documentation that fails
without one fails exactly when someone is debugging.

---

### Audio transcription

When starting OpenRC services, the installer closes descriptors 3 and 4 on `rc-service` commands. These are its saved SSH stdout/stderr pipes: `supervise-daemon` was observed retaining them after a successful installer exit. Ordinary output is still captured in `install.log`.

`audio_transcription` stores one validated JSON configuration in `settings.audio_transcription`. OpenAI, Groq, Mistral and Together use multipart; Hugging Face and Cloudflare receive binary WAV. They reuse `api_keys` without returning secrets to the browser. FFmpeg bounds containers, protocols, size, duration and runtime. Audio is split into 120-second segments (30 seconds for the raw Hugging Face and Cloudflare endpoints, avoiding reliance on long-form generation options); whisper.cpp and decoding run as `boa`, with no shell or automatic provider fallback.

`audio_inbox` persists destination, settings and transcript in SQLite. One process-locked background thread in `boa-telegram` recovers its queue after a restart. A reserved turn ID lets the executor acknowledge a repeated submission before checking whether the agent is busy. Marking the job submitted and inserting `telegram_pending` happen in one transaction. Private audio lives in `/opt/boa/audio/` (0700, owned by boa), requires both login and a matching chat reference for playback, and is removed when completed chat turns are cleared.

Both installers compile whisper.cpp v1.9.4 after verifying the source archive SHA-256 and download `base`. `whisper_models.json` contains all 30 official names, sizes and hashes. Only the root executor downloads models through `install_whisper_model`; arbitrary URLs and paths are rejected. A partial file becomes visible only after hash verification. Root owns `whisper/`; `boa` only reads it. Updates retain models and audio; backups include audio but exclude model weights. A missing Python interpreter is installed with dependencies before checking the minimum version.

## 2. Module map

| Module | Path | Responsibility | Depends on | Used by |
|---|---|---|---|---|
| `audio_transcription` | `backend/core/audio_transcription.py` | Speech settings and recognition engines | db, api_keys, whisper_runtime | audio_inbox, api |
| `audio_inbox` | `backend/core/audio_inbox.py` | Durable queue, routing, retries and private playback | db, exec_client, audio_transcription | telegram_listener, api |
| `whisper_runtime` | `backend/core/whisper_runtime.py` | Catalogue, status and verified model downloads | paths, whisper_models.json | installer, exec_daemon, api |
| `settings_audio.js` | `frontend/static/js/settings_audio.js` | Audio form, model downloads and progress | api.js, i18n.js | settings.js, settings_audio.html |
| `paths` | `backend/core/paths.py` | Every filesystem path and agent id validation | — | everything |
| `db` | `backend/core/db.py` | SQLite connections and both schemas | `paths` | `agents`, `kanban`, `auth`, `bootstrap` |
| `agents` | `backend/core/agents.py` | Agent model, `info.json`, agents index, token hashing | `db`, `paths` | `exec_daemon`, `agent_api`, `api` |
| `bootstrap` | `backend/core/bootstrap.py` | First-run initialization | `agents`, `db`, `paths` | installer |
| `exec_protocol` | `backend/core/exec_protocol.py` | Wire protocol and verb list | — | `exec_daemon`, `exec_client`, `agent_api` |
| `exec_daemon` | `backend/core/exec_daemon.py` | The privileged daemon (root) | `agents`, `paths`, `run_journal` | `boa-exec` service |
| `exec_client` | `backend/core/exec_client.py` | Client for the above | `exec_protocol`, `paths` | `web/api` |
| `agent_api` | `backend/core/agent_api.py` | The daemon agents talk to | `agents`, `kanban`, `channels` | `boa-agent-api` service |
| `agent_api_client` | `backend/core/agent_api_client.py` | Client for the above | `agent_api`, `exec_protocol` | the shipped tools |
| `runner` | `backend/core/runner.py` | One agent run: the loop and its ceilings | `providers`, `tool_registry`, `run_journal` | cron, `exec_daemon` |
| `run_journal` | `backend/core/run_journal.py` | Per-agent `runs.jsonl` | `paths` | `runner`, `exec_daemon` |
| `chat` | `backend/core/chat.py` | Per-agent `chat.jsonl` and the conversation replayed to the model | `paths` | `runner`, `exec_daemon` |
| `memory` | `backend/core/memory.py` | Per-agent `memory.md`, loaded into every run's system prompt | `paths` | `runner`, `exec_daemon`, tools |
| `skills` | `backend/core/skills.py` | The shared procedures in `/opt/boa/skills/`, one directory each. Parses `SKILL.md`, builds the index that goes in the prompt, and says which of an agent's skills still exist | `paths` | `runner`, `exec_daemon`, `web/api`, `skill.read` |
| `provider_models` | `backend/core/provider_models.py` | Model catalogues from `config/providers/*.json` | `paths` | `web/api` |
| `api_keys` | `backend/core/api_keys.py` | The shared provider keys in `config/apikeys/*.key`, written 0600 in a 0700 directory. Never returns a key to the browser, only whether one is stored and its last four characters | `paths` | `agent_api`, `web/api` |
| `tool_registry` | `backend/core/tool_registry.py` | Discovery, permissions and dispatch of tools | `paths` | `runner`, `web/api` |
| `attachments` | `backend/core/attachments.py` | Private PNG snapshots, opaque IDs, checked file ownership and bounded reads | `paths` | `image_send`, `exec_daemon`, `exec_client`, `telegram_listener` |
| `image_send` | `backend/tools/image_send.py` | Attaches an owned PNG to the reply through the tool context | `attachments`, `tool_registry` | `runner` |
| `public_url` | `backend/core/public_url.py` | Whether a URL an agent was given resolves to a public address. Stated positively with `is_global` plus an explicit multicast refusal, because a list of ranges to refuse is a list to leave one off - and 100.64.0.0/10 was left off it | — | `web.fetch`, `rss.fetch`, `browser` |
| `agent_scripts` | `backend/core/agent_scripts.py` | Scripts an agent writes for itself, and the cron lines that run them. Validates names and schedules, and never rewrites the wake-up line | `paths` | `script.*`, `cron.*` |
| `kanban` | `backend/core/kanban.py` | The board and its history | `db` | `agent_api`, `web/api` |
| `channels` | `backend/core/channels.py` | Telegram, Discord, Mattermost, X. Sending for all four; reading for the two that can be answered | `paths`, `telegram_html`, `discord_markdown` | `agent_api`, `web/api`, both listeners |
| `agent_routing` | `backend/core/agent_routing.py` | What both listeners do the same: the roster, reading an agent's name out of a message, the closed answer of a turn, the status report | `agents`, `chat`, `exec_client` | `telegram_listener`, `discord_listener` |
| `providers.base` | `backend/providers/base.py` | Adapter interface and neutral message shape | — | every adapter |
| `providers.factory` | `backend/providers/factory.py` | Provider name → adapter class | `providers.base` | `runner`, `web/api` |
| `providers.openai_dialect` | `backend/providers/openai_dialect.py` | The chat/completions request the OpenAI-dialect adapters share; quirks stay in each adapter | `providers.base` | most adapters |
| `providers.*` | `backend/providers/<name>.py` | One adapter per provider | `providers.base`, `providers.openai_dialect` | `factory` |
| `web.server` | `backend/web/server.py` | Flask factory, session key, security headers | `db`, `web.*` | gunicorn |
| `deploy/haproxy/boa.cfg` | `deploy/haproxy/boa.cfg` | TLS termination, PROXY protocol, 11080 → 11443 | — | `boa-proxy` service |
| `web.auth` | `backend/web/auth.py` | Login, sessions, rate limiting | `db` | `web.api`, `web.views` |
| `web.api` | `backend/web/api.py` | Everything under `/api/admin/` | `exec_client`, `kanban`, `channels` | browser |
| `web.api_doc` | `backend/web/api_doc.py` | OpenAPI spec and its page. Annotates the spec with i18n keys for the page only, never for `openapi.json` | `channels`, `providers.factory` | browser |
| `web.views` | `backend/web/views.py` | The HTML pages | `web.auth` | browser |
| `buzzer` | `backend/core/buzzer.py` | Watches the board and starts a run when a card is due | `kanban`, `exec_client` | `boa-buzzer` service |
| `telegram_listener` | `backend/core/telegram_listener.py` | Long-polls Telegram, routes each message to an agent, sends the answer back | `channels`, `exec_client`, `telegram_inbox` | `boa-telegram` service |
| `telegram_inbox` | `backend/core/telegram_inbox.py` | Which agent said what on Telegram, and which questions are still being answered. Expiry is calculated in UTC | `db` | `telegram_listener`, `agent_api` |
| `discord_listener` | `backend/core/discord_listener.py` | Polls one Discord channel, routes each message to an agent, sends the answer back | `agent_routing`, `channels`, `exec_client`, `discord_inbox` | `boa-discord` service |
| `discord_inbox` | `backend/core/discord_inbox.py` | The same two tables for Discord. Separate from Telegram's: a snowflake is a string, and one listener must not be able to answer the other's questions. Expiry is calculated in UTC | `db` | `discord_listener`, `agent_api` |
| `discord_markdown` | `backend/core/discord_markdown.py` | Markdown into what Discord renders, cut into messages of 2000 characters. Tables become fenced blocks; a block a cut lands inside is closed and opened again | `telegram_html` (the block patterns) | `channels` |
| `discord_texts` | `backend/core/discord_texts.py` | The three sentences Discord says differently. Everything else falls through to `telegram_texts`, so one catalogue serves both bots | `telegram_texts` | `discord_listener` |
| `browser` | `backend/core/browser.py` | The shared browser and this agent's own profile. One handle for the length of a run, closed by `atexit`. Carries the network policy every request passes through | `paths`, `public_url` | the five `browser.*` tools |
| `telegram_html` | `backend/core/telegram_html.py` | Markdown into the fourteen tags Telegram accepts. Same patterns as `markdown.js`, so both renderers agree on what markdown is | — | `channels` |
| `telegram_texts` | `backend/core/telegram_texts.py` | What the bot says itself, in the language the installation was set to | `db` | `telegram_listener` |
| `markdown.js` | `frontend/static/js/markdown.js` | Renders an agent's answer as DOM nodes, never as markup | — | `dashboard.js` |
| `jsonhighlight.js` | `frontend/static/js/jsonhighlight.js` | Colours the schema blocks on the documentation page. DOM nodes, never markup | — | `api_doc.html` |
| `themes` | `backend/core/themes.py` | Lists the stylesheets in `frontend/themes/` and reads their headers | `paths` | `web/api`, `web/views` |
| `agent_templates` | `backend/core/agent_templates.py` | Reads the example agents in `backend/agents/examples/`, one Markdown file each; filenames, IDs and default names use hyphens, including `kanban-watcher` and `web-navigator` | — | `web/api` |
| `mailbox` | `backend/core/mailbox.py` | IMAP and SMTP for the configured mailbox. Holds the credentials so agents never do. Names a message by UID and UIDVALIDITY, never by its position in the folder | `db` | `agent_api` |
| `theme.js` | `frontend/static/js/theme.js` | Adds the chosen theme's stylesheet, from the head, before the first paint | — | every page |
| `night-high-contrast.css` | `frontend/themes/night-high-contrast.css` | Fills the selected agent with grey and draws selected tabs with a closed outline joined to the baseline | `app.css` | `theme.js` |
| `settings.js` | `frontend/static/js/settings.js` | Loads main settings tabs with selectors scoped to their own tab bar; `fRenderChannelForms` marks configured channels with `data-state="good"`, sharing the API key status style and the theme's `--colour-ok` | `api.js`, `i18n.js`, `tools.js`, `app.css` | `settings.html` |
| `tools.js` | `frontend/static/js/tools.js` | Loads the catalogue inside Settings → Tools; keeps the subtab in the URL's `family` parameter and refreshes its labels when returning from Interface | `api.js`, `i18n.js` | `settings.js`, `settings_tools.html` |
| `app.css` | `frontend/static/css/app.css` | The `system-table` class shares a two-column layout, with 35% for labels, so machine values and service states align; `.chat-attachment img` fills 100% of the text width with automatic, uncapped height; `.chat-audio` fits the message width and its heading inherits the message text color | — | `settings.html`, `dashboard.html` |
| `system_info` | `backend/core/system_info.py` | What the machine looks like, read with no privileges | `paths` | `web/api` |

---

## 3. Key symbol index

Public and load-bearing symbols only. Line numbers move; the file and the
behaviour are what to trust.

### Paths and identity

| Symbol | File:line | What it does |
|---|---|---|
| `fNormalizeAgentId` | `backend/core/paths.py:155` | Validates an agent id and zero-pads it. **Every path built from user input goes through this.** Raises on anything outside 0–999 |
| `fGetAgentHome` | `backend/core/paths.py:170` | `/opt/boa/agents/xxx` |
| `fReadAgentOwnedFile` | `backend/core/paths.py:392` | How root reads a file of an agent's home: on the open descriptor, regular and the agent's own or refused, never more than a bound. The journal, the chat and the memory all go through it |
| `fGetAgentApiTokenPath` | `backend/core/paths.py:476` | Where an agent's API token lives |

### Agents

| Symbol | File:line | What it does |
|---|---|---|
| `fValidateAgentName` | `backend/core/agents.py:53` | 2–40 characters, no shell metacharacters |
| `fGetNextFreeAgentId` | `backend/core/agents.py:100` | Lowest free id from the filesystem, starting at 001 |
| `fBuildAgentInfo` | `backend/core/agents.py:113` | The `info.json` of a new agent, with conservative defaults |
| `fWriteAgentInfo` | `backend/core/agents.py:179` | Atomic write preserving 0600 ownership |
| `fHashApiToken` | `backend/core/agents.py:216` | SHA-256; the raw token is never stored |
| `fFindAgentByApiToken` | `backend/core/agents.py:261` | Turns a token into an identity |

### The privileged daemon

| Symbol | File:line | What it does |
|---|---|---|
| `fIsPeerAllowed` | `backend/core/exec_daemon.py:102` | Only root and `boa`, checked per connection |
| `fRunPrivilegedCommand` | `backend/core/exec_daemon.py:118` | Runs a command list with no shell, optionally as another user |
| `fVerbCreateAgent` | `backend/core/exec_daemon.py:392` | Creates user, home, config, token; **rolls back on any failure** |
| `fStartRunner` | `backend/core/exec_daemon.py:300` | The one place a runner is started as the agent. The chat message or the card's prompt goes on its standard input, never on the command line |
| `fWatchRunner` | `backend/core/exec_daemon.py:251` | Waits for a run: stops its scope, and records the end of one that was killed |
| `fVerbWriteCrontab` | `backend/core/exec_daemon.py:748` | Installs a crontab as the agent's own user |
| `fListRunningAgentIds` | `backend/core/exec_daemon.py` | One sweep of `/proc` naming every agent with a run in flight. Backs both `only_if_idle` and the sidebar's turning ring |
| `dVerbHandlers` | `backend/core/exec_daemon.py` | The closed verb table. The whole privileged surface is these ten rows |

### The agent API

| Symbol | File:line | What it does |
|---|---|---|
| `fAuthenticate` | `backend/core/agent_api.py:121` | Token **and** `SO_PEERCRED` must agree |
| `fAgentMayUseKanban` | `backend/core/agent_api.py` | Whether the board is switched on and the agent holds any kanban tool. The coarse half |
| `fRequireKanbanTool` | `backend/core/agent_api.py` | One verb, one tool, by name. Every handler used to ask the coarse question, so `kanban.list_cards` - a read - reached `fDeleteCard` for an agent that put the request on the socket itself |
| `fRequireOwnCard` | `backend/core/agent_api.py:283` | An agent may only change cards it created or owns |
| `fVerbChannelWrite` | `backend/core/agent_api.py` | Sends on the agent's behalf, prefixing its real name |

### The run loop

| Symbol | File:line | What it does |
|---|---|---|
| `AgentRun` | `backend/core/runner.py:314` | One bounded conversation |
| `fCheckCeilings` | `backend/core/runner.py` | Returns which ceiling stopped the run, or empty to continue |
| `fSecondsLeft` | `backend/core/runner.py` | Time left before the run's deadline, on a monotonic clock. Each provider call and each tool gets what is left, not the whole ceiling |
| `fTakeRunLock` | `backend/core/runner.py` | An flock on `<home>/run.lock`, held for the length of the process. The one check a cron-started run also makes |
| `fTrimToByteBudget` | `backend/core/exec_protocol.py` | The newest entries that fit in a byte budget, and how many were dropped. Counted in bytes, because a line count is not a size |
| `fRunWithLimits` | `backend/tools/bash_run.py` | Runs a command with a byte ceiling applied WHILE it produces output, and a deadline that kills the whole process group |
| `fAskForClosingAnswer` | `backend/core/runner.py` | After a ceiling, asks once with no tools for the answer it was cut off from giving |
| `fExecute` | `backend/core/runner.py:462` | The loop: ask, run tools, feed back, stop |
| `fSelectAllowedTools` | `backend/core/runner.py:301` | Withholds kanban tools when the agent has them switched off |
| `fReadStdinArguments` | `backend/core/runner.py:849` | The runner's half of that: reads the text from standard input, bounded, and refuses an empty chat message |
| `fApplyResourceLimits` | `backend/core/runner.py:930` | Lowers the run's own kernel limits before anything is started: processes, core files, file size |
| `fRecordChatAnswer` | `backend/core/runner.py` | Writes the answer back when the run has a turn to close (`vWritesToChat`) |
| `fRecordChatFailure` | `backend/core/runner.py` | Closes the turn when nothing else will, naming the reason so the interface can translate it |
| `fAppendCardMessage` | `backend/core/chat.py` | Announces a due card as a turn of its own, with the card's fields and no sentences |
| `fBuildCardAnnouncement` | `backend/core/buzzer.py` | What the chat is told: who assigned it, and whether it was asked for now |

### Tools

| Symbol | File:line | What it does |
|---|---|---|
| `fGetContext` | `backend/core/browser.py` | Starts the browser on this agent's profile, or returns the one already running |
| `fClose` | `backend/core/browser.py` | Registered with `atexit`. Without it every run leaves a Chromium behind |
| `fIsInstalled` | `backend/core/browser.py` | Whether there is a browser to drive, so the tools can say what to run instead of raising |
| `fLoadAllTools` | `backend/core/tool_registry.py:103` | Loads every valid tool; a broken file is skipped, not fatal |
| `fRunTool` | `backend/core/tool_registry.py:136` | Enforces permission, returns `(text, is_error)`; a raising tool never kills a run |
| `ToolContext` | `backend/core/tool_registry.py:53` | What a tool is told about its caller |
| `fStoreImage` | `backend/core/attachments.py` | Copies a PNG from the agent's home into a private snapshot |
| `fReadImageChunk` | `backend/core/attachments.py` | Reads at most 1 MiB, refusing symlinks, other owners and special files |
| `fVerbReadChatAttachment` | `backend/core/exec_daemon.py` | Requires an attachment reference in the requested agent's chat before reading |
| `fGetChatAttachment` | `backend/web/api.py` | Streams the PNG to a signed-in user, with no public or cached file URL |
| `fRenderChatAttachments` | `frontend/static/js/dashboard.js` | Shows the reply's images and an error when an image cannot be loaded |
| `fDeliverAnswerParts` | `backend/core/telegram_listener.py` | Resumes Telegram delivery from the last acknowledged text/image part |

### Skills

| Symbol | File:line | What it does |
|---|---|---|
| `fIsValidSkillName` | `backend/core/skills.py:57` | A name, never a path. Refuses rather than cleans, like the template and theme names |
| `fParseSkill` | `backend/core/skills.py:77` | The `---` header and the body. Same parser shape as `agent_templates.fParseTemplate` |
| `fSelectInstalledSkills` | `backend/core/skills.py:194` | The names in an agent's list that still exist on disk. **Every path into the feature goes through this**, so a deleted skill never reaches a prompt |
| `fBuildPromptSection` | `backend/core/skills.py:211` | The index: one line per skill, names and descriptions only. `""` when the agent has none |
| `fRunTool` | `backend/tools/skill_read.py` | Returns one body, checked against the agent's own `info.json` |


### Telegram, both ways

| Symbol | File:line | What it does |
|---|---|---|
| `fReadTelegramUpdates` | `backend/core/channels.py` | One long poll. The connection is made outwards, which is what lets this work behind a NAT with nothing forwarded |
| `fSendToTelegram` | `backend/core/channels.py` | Sends, and returns the `message_id` - the only thing that makes a later reply routable |
| `fRedactSecrets` | `backend/core/channels.py` | Removes every credential from an error or a log line. `str(RequestException)` quotes the URL, and for three of the four channels the URL **is** the credential |
| `fReadConfigForEditing` | `backend/core/channels.py` | A channel's file as it is on disk, so saving a change merges instead of replacing it |
| `fListConfiguredChannels` | `backend/core/channels.py` | Returns Discord, Mattermost, Telegram and X alphabetically, with their state and without secrets; used by Settings and each agent's permissions |
| `fRouteMessage` | `backend/core/telegram_listener.py` | Who a message is for: the agent replied to, or the one named with @ |
| `fMatchNamedAgent` | `backend/core/telegram_listener.py` | Longest-match on every known name, because agent names may contain spaces |
| `fIsFromTheConfiguredChat` | `backend/core/telegram_listener.py` | **The whole authorisation.** Anything from another chat is dropped without an answer |
| `fDeliverAnswers` | `backend/core/telegram_listener.py` | Sends back every turn that has closed since the last pass |
| `fRememberMessage` | `backend/core/telegram_inbox.py` | Ties a sent message to the agent that sent it, pruned to the last few hundred |
| `fRouteMessage` | `backend/core/telegram_listener.py` | Who a message is for: the agent replied to, the one named with @ or /, or the one selected |
| `fReadSelectedAgent` | `backend/core/telegram_listener.py` | Who the conversation is with, checked against the roster so a deleted agent stops catching everything |
| `fBuildAgentButtons` | `backend/core/telegram_listener.py` | The inline keyboard /agents answers with. A button's text is the bot's to choose, which the command menu's is not |
| `fBuildStatusReport` | `backend/core/telegram_listener.py` | What /status says. An agent it cannot read is listed saying so, never left out |
| `fHandleCallback` | `backend/core/telegram_listener.py` | A tap on an agent button: answered first, then the agent is selected |
| `fRender` | `backend/core/telegram_html.py` | Markdown to Telegram's HTML. Headings become bold, lists become bullets, tables become a monospaced block - Telegram has a tag for none of the three |
| `fEscape` | `backend/core/telegram_html.py` | `&`, `<`, `>`. **Called before anything wraps the text**, never after |
| `fEscapeAttribute` | `backend/core/telegram_html.py` | The same plus the double quote, for an href. A quote in a URL would otherwise close the attribute and invent the ones after it |
| `fRenderWithinLimit` | `backend/core/telegram_html.py` | Shortens the markdown and re-renders until the HTML fits. Cutting the HTML instead would leave a tag half written |

### Discord, both ways

| Symbol | File:line | What it does |
|---|---|---|
| `fReadDiscordMessages` | `backend/core/channels.py` | One poll. **Reverses what Discord returns**, which is newest first: answering in that order would have the agent read a conversation backwards |
| `fSendToDiscord` | `backend/core/channels.py` | Sends, in as many parts as the 2000-character limit needs, and returns every part's id |
| `fCallDiscord` | `backend/core/channels.py` | One call. A 429 with a short `retry_after` is slept through once; any other 4xx is `ChannelRejected` |
| `fGetDiscordMode` | `backend/core/channels.py` | `"bot"`, `"hook"` or `""`. A webhook sends and nothing else |
| `fReadDiscordBotUser` | `backend/core/channels.py` | Which bot this is, written to the log once per start: when nothing arrives, that is the first question |
| `fRenderToMessages` | `backend/core/discord_markdown.py` | An answer as the list of messages to send for it |
| `fSplit` | `backend/core/discord_markdown.py` | Cuts between lines, closing and reopening a fenced block the cut lands inside |
| `fIsFromTheConfiguredChannel` | `backend/core/discord_listener.py` | Every polled message came from that channel by construction; checked anyway, because "by construction" is a property of today's code |
| `fReadCommand` | `backend/core/discord_listener.py` | `!agents`, `!status`, `!help`, and the `/` forms. Only as the whole first word, or an agent called `status` would be unreachable |
| `fReadMessageText` | `backend/core/discord_listener.py` | The text with a mention of the bot taken off the front: Discord turns `@Boa` into `<@123>` before anybody else sees it |
| `fStartFromTheNewestMessage` | `backend/core/discord_listener.py` | Where a fresh installation starts. A bot switched on this afternoon must not answer a month of the channel |
| `fReadAfterId` / `fWriteAfterId` | `backend/core/discord_listener.py` | The mark, in `config/discord-after`. A snowflake, not a counter |
| `fRememberMessage` | `backend/core/discord_inbox.py` | Ties one sent part to the agent that sent it. Pruned by insertion order, not by id |

### Shared by both listeners

| Symbol | File:line | What it does |
|---|---|---|
| `fMatchNamedAgent` | `backend/core/agent_routing.py` | Longest-match on every known name. Prefixes are an argument: Telegram takes `@` and `/`, Discord adds `!` |
| `fBuildStatusReport` | `backend/core/agent_routing.py` | What /status says. Takes the asking service's catalogue and its own unit name, which are the only two things that differ |
| `fFindClosedAnswer` | `backend/core/agent_routing.py` | What an agent said to close a turn, read through the executor |
| `fListAgentNames` | `backend/core/agent_routing.py` | The roster, from the index: an agent's home is 0700 and its info.json is not a listener's to open |

### An agent's own scripts and cron

| Symbol | File:line | What it does |
|---|---|---|
| `fValidateScriptName` | `backend/core/agent_scripts.py` | Checks a name rather than cleaning it: anything that is not a plain file name is refused, which is one rule instead of a rule plus whatever the cleaning turns out to do |
| `fValidateSchedule` | `backend/core/agent_scripts.py` | The shape of a cron schedule, and the one thing worth refusing: a job that fires more often than anybody meant |
| `fIsRunnerLine` | `backend/core/agent_scripts.py` | The line that wakes the agent up. Never rewritten from here: an agent that deleted it would go quiet for ever with no way of noticing |
| `fAddCronLine` | `backend/core/agent_scripts.py` | Adds a line running one of the agent's own scripts. The script has to exist first |
| `fRemoveCronLines` | `backend/core/agent_scripts.py` | Removes every line running one script, and the comment above each |

### Board and channels

| Symbol | File:line | What it does |
|---|---|---|
| `fAddCard` | `backend/core/kanban.py:132` | Card and first event in one transaction |
| `fMoveCard` | `backend/core/kanban.py:188` | Move plus history event |
| `fValidateRunAt` | `backend/core/kanban.py:68` | Accepts `"now"`, a browser time or a stored time, and normalises all three |
| `fReadRunMode` | `backend/core/kanban.py:100` | Which kind of time was asked for: `now`, `at`, or none |
| `fWasRequestedImmediately` | `backend/core/kanban.py` | Whether the card said "now". Read from `run_mode`, never inferred from the clock |
| `fAssignCard` | `backend/core/kanban.py` | Hands a card over, recording who handed it in `assigned_by` |
| `fAgentOwnsCard` | `backend/core/kanban.py:462` | Creator **or** assignee |
| `fDeleteCard` | `backend/core/kanban.py:480` | Deletes, keeping a row in `deleted_cards` |
| `fReadMessages` | `backend/core/mailbox.py` | Newest messages of a folder, read-only: nothing is marked seen |
| `_fParseFolderLine` | `backend/core/mailbox.py` | One LIST line as flags, delimiter and name. Raises rather than guessing: an unreadable listing is an error, not an account with no folders |
| `fListFoldersWithFlags` | `backend/core/mailbox.py` | Every folder with its SPECIAL-USE flags |
| `fFindTrashFolder` | `backend/core/mailbox.py` | `\\Trash` first, then the names in nine languages. `""` means there is none; a failure raises |
| `fIsForwardAllowed` | `backend/core/mailbox.py` | Whether one address is on the user's list. Checked where the password is, never in a prompt |
| `fListTemplates` | `backend/core/agent_templates.py` | Every example agent, ordered by the name the user sees |
| `fParseTemplate` | `backend/core/agent_templates.py` | `key: value` header between two `---`, body is the prompt |

### The sidebar

| Symbol | File:line | What it does |
|---|---|---|
| `fRenderSidebar` | `frontend/static/js/api.js` | Rebuilds the agent list. Called on page load and after a create or delete, never on a timer |
| `fPickDifferentModel` | `frontend/static/js/dashboard.js` | The model to fill in when a provider is picked. The backup avoids the main one's: same provider and model fails for the same reason, every time |
| `fSetAgentAvatarActivity` | `frontend/static/js/api.js` | Sets `data-running` and the tooltip on one avatar, and adds or removes the arc |
| `fBuildAgentActivityArc` | `frontend/static/js/api.js` | The SVG rounded rect laid over the border, `pathLength="100"` so the stylesheet can speak in percentages of the perimeter |
| `fRefreshAgentActivity` | `frontend/static/js/api.js` | Every 5s, repaints only the rings; skipped while the tab is hidden |
| `fDescribeChannelName` / `fDescribeProviderName` | `frontend/static/js/api.js` | The name a channel or a provider spells itself by. Not i18n keys: DeepSeek is DeepSeek in every language |
| `fDescribeTool` / `fDescribeToolArgument` | `frontend/static/js/api.js` | What a tool and its arguments say, in the reader's language. The schema stays English: it is what the model is sent |
| `fRenderToolCheckboxes` | `frontend/static/js/dashboard.js` | One box per tool family, built from whatever is installed. Moves the kanban switch into the kanban box rather than rebuilding it, so a tick made and not yet saved survives the redraw |

### Pop-up messages

| Symbol | File:line | What it does |
|---|---|---|
| `fShowNotice` | `frontend/static/js/api.js` | Puts one message on the layer over the content column. Replaces whatever was there, so confirmations never stack |
| `fShowError` | `frontend/static/js/api.js` | The same, as an error: no timer, closed by hand |
| `fConfirmLogout` | `frontend/static/js/api.js` | Opens `fConfirm` in the centre of the screen; navigates to `/logout` only after confirmation. Cancel and Escape keep the session open |
| `fHideNotice` | `frontend/static/js/api.js` | Fades a message out and removes it afterwards, so it does not blink out of existence when the timer runs down |
| `fGetNoticeSeconds` / `fSetNoticeSeconds` | `frontend/static/js/api.js` | How long a message stays, kept in this browser and clamped to 1–30 seconds |
| `fBuildCloseCross` | `frontend/static/js/api.js` | The close cross as two SVG lines. A `×` character is centred on the font's maths axis rather than in its own box, so it sits above the middle of the button whatever the button does |

### JSON highlighting

| Symbol | File:line | What it does |
|---|---|---|
| `cJsonTokenPattern` | `frontend/static/js/jsonhighlight.js` | One expression for all four token kinds. A string followed by a colon is a key, which is the only thing that tells a name from a value |
| `fHighlightJsonElement` | `frontend/static/js/jsonhighlight.js` | Rebuilds one block as coloured spans and plain text. Every character of the original is emitted exactly once, so the block still copies as valid JSON |

### Providers

| Symbol | File:line | What it does |
|---|---|---|
| `BaseProvider.fSendMessages` | `backend/providers/base.py` | The one method every adapter implements |
| `fNeutralMessagesToOpenAiFormat` | `backend/providers/base.py` | Neutral shape → chat/completions |
| `fToolNameToWire` / `fToolNameFromWire` | `backend/providers/base.py` | `family.action` ↔ `family__action`, because no provider accepts the dot |
| `fDescribeHttpError` | `backend/providers/base.py` | Appends what the provider said to a bare HTTP failure |
| `fBuildProvider` | `backend/providers/factory.py` | Config → adapter instance, importing lazily |
| `fResolveProviderName` | `backend/providers/factory.py` | Follows the aliases, so `gemini` and `google` reach one adapter |
| `fSendChatCompletion` | `backend/providers/openai_dialect.py` | The shared chat/completions request, parameterised by each adapter's quirks |
| `fNormalizeMessageContent` | `backend/providers/openai_dialect.py` | Flattens a reply whose content arrived as blocks, dropping reasoning |

---

### Audio symbols

| Symbol | File:line | Responsibility |
|---|---|---|
| `fTranscribe` | `backend/core/audio_transcription.py:223` | Decode, segment and transcribe |
| `fEnqueueTelegram` | `backend/core/audio_inbox.py:57` | Persist destination before transcription |
| `fRunOneJob` | `backend/core/audio_inbox.py:233` | Process or retry one reserved turn |
| `fDownloadModel` | `backend/core/whisper_runtime.py:134` | Validate size and SHA-256 before publication |
| `fGetChatAudio` | `backend/web/api.py:457` | Serve audio after session and chat-reference checks |

## 4. Main flows

### Creating an agent

```
browser  POST /api/admin/agents {name}
  web/api.fCreateAgent
    exec_client.fCreateAgent          → Unix socket /run/boa/exec.sock
      exec_daemon.ExecRequestHandler
        fGetPeerCredentials + fIsPeerAllowed    ← refuses anyone but root/boa
        fVerbCreateAgent
          agents.fValidateAgentName
          agents.fGetNextFreeAgentId            ← lowest free, from the filesystem
          useradd --home-dir … --create-home
          agents.fWriteAgentInfo                 (0600, owned by the agent)
          fWriteAgentFile system-prompt.md        (0600)
          fWriteAgentFile api-token              (0600)
          chmod 0700 on the home
          agents.fIndexAgent(…, vApiToken)       ← stores only the SHA-256
        on any exception: fRemoveAgentUser       ← no half-created agents
```

### One scheduled run

```
cron (agent-007's own crontab)
  runner.py --agent-id 007            ← already running as agent-007
    fTakeRunLock                      ← refused → fRecordRunRefused, and stop
    AgentRun.__init__
      fReadOwnInfo / fReadOwnSystemPrompt / fReadOwnApiToken
      fBuildSystemPrompt              ← prompt + memory + skill index + language
      tool_registry.fLoadAllTools
      fSelectAllowedTools             ← kanban tools withheld if switched off
    fExecute
      run_journal.fCountRunsOn        ← daily ceiling, from its own journal
      factory.fBuildProvider
      loop:
        fCheckCeilings                ← steps, tokens, seconds
        provider.fSendMessages        ← max_tokens shrinks as budget is spent
        run_journal.fRecordUsage
        if no tool calls: stop
        fRunToolCalls                 ← all results returned in one batch
      fAskForClosingAnswer            ← one tool-less call after a steps or
                                        tokens ceiling, so the work already
                                        paid for turns into an answer
      run_journal.fRecordRunFinished  ← "stopped" when a ceiling ended it
```

### A card comes due

```
boa-buzzer (as boa), every 5 seconds
  kanban.fListDueCards              ← owner, run_at passed, not buzzed, not done
  fRingOne
    fBuildCardAnnouncement          ← assigned_by → name, run_mode → immediate
    exec_client.fRunNow(prompt, only_if_idle, card)
      exec_daemon.fVerbRunNow                      ← as root
        fIsAgentRunning             ← busy: started=False, no buzz, try again
        fRunAsAgent → chat.fAppendCardMessage      ← announced, turn opened
        Popen runner.py --prompt-on-stdin --turn-id …  ← as agent-007, the prompt on its stdin
    kanban.fMarkCardBuzzed          ← only after the run started
  runner.AgentRun (vWritesToChat, not vIsChat)
    fExecute                        ← card prompt, no conversation replayed
    fRecordChatAnswer               ← answer + cost close the turn
    fRecordChatFailure              ← or the reason nothing ran
```

### An agent moves a card

```
model asks for kanban.move_card
  tool_registry.fRunTool              ← refuses if not granted to this agent
    tools/kanban_move_card.fRunTool
      agent_api_client.fCallFromContext   → /run/boa/agent.sock
        agent_api.AgentRequestHandler
          fAuthenticate               ← token hash + SO_PEERCRED
          fVerbKanbanMoveCard
            fAgentMayUseKanban        ← server-side, reads info.json
            fRequireOwnCard           ← creator or assignee only
            kanban.fMoveCard          ← move + event, one transaction
```

### An agent sends a message

```
model asks for channel.write
  tools/channel_write.fRunTool
    agent_api_client → agent_api.fVerbChannelWrite
      fAgentMayUseChannel             ← tool granted AND channel granted
      channels.fSendMessage(prefix="[Agent name]")
        fReadChannelConfig            ← as boa; the agent never sees this
        fSendToTelegram / Discord / Mattermost / X
```


### A message arrives from Telegram

```
boa-telegram (as boa)
  fRefreshCommands                    ← /agents /status /help, when they change
  fDeliverAnswers                     ← anything finished since the last pass
    exec_client.fReadChat             ← the chat is in a 0700 home; only root reads it
    channels.fSendToTelegram          ← "**name:**\n..." as a reply
    telegram_inbox.fRemovePending
  channels.fReadTelegramUpdates       ← long poll: 25s idle, 3s while answering
    fIsFromTheConfiguredChat          ← anything else is dropped, silently
    callback_query -> fHandleCallback ← a tap on an agent button
      fSelectAgent                    ← from here on, unaddressed messages go there
    message -> fHandleMessage
      fHandleCommand                  ← /agents /status /help, answered and done
      fRouteMessage                   ← reply, then @name, then the selected one
      exec_client.fSendChatMessage(source="telegram")
        exec_daemon.fVerbSendChatMessage
          chat.fAppendMessage(metadata={"source": "telegram"})
          Popen runner.py --chat-message-on-stdin --turn-id   ← the message on its stdin
      telegram_inbox.fAddPending      ← on disk: a restart must not lose the answer
```

The answer is sent by the listener and not by the run, for the same reason the
card announcement is written by the executor: the run is the agent's own user,
and the channel credentials belong to `boa`. The run only writes to its chat;
the listener reads that and does the sending.

### A message arrives from Discord

```
boa-discord (as boa)
  fDeliverAnswers                     ← anything finished since the last pass
    exec_client.fReadChat             ← the chat is in a 0700 home; only root reads it
    channels.fSendToDiscord           ← "**name:**\n…" as a reply, in 2000-character parts
      discord_markdown.fRenderToMessages
    discord_inbox.fRememberMessage    ← every part, so replying to any of them routes
    discord_inbox.fRemovePending
  channels.fReadDiscordMessages       ← GET /channels/<id>/messages?after=<id>
    (reversed: Discord answers newest first)
    fHandleMessage
      author.bot, type                ← its own words, and everything that is not a message
      fIsFromTheConfiguredChannel
      fReadCommand                    ← !agents !status !help, answered and done
      fRouteMessage                   ← reply, then @name, then the selected one
      exec_client.fSendChatMessage(source="discord")
      discord_inbox.fAddPending       ← on disk: a restart must not lose the answer
  fWriteAfterId                       ← config/discord-after
```

The answer is sent by the listener and not by the run, for the reason the
Telegram one is: the run is the agent's own user, and the channel credentials
belong to `boa`.

The first pass of a fresh installation asks for the newest message and keeps
only its id. An empty channel is marked with the lowest id there is, so the
**first** message somebody writes is answered rather than spent working out
where to start.

### The bot shows a stranger nothing

A bot's username is public: anybody who finds it can open a chat with it. So
`fIsFromTheConfiguredChat` compares the `chat.id` Telegram puts on every
message - which the sender cannot forge - against the configured one, and
`fHandleMessage` drops what does not match before a command is dispatched and
before an agent is chosen. `fHandleCallback` does the same for a button press.
Nothing is sent back: answering would confirm the bot is alive to whoever is
probing it. Nothing is written down either. The drop used to be logged with the
id of the chat it came from, which is somebody else's data and would have meant
this installation quietly accumulating a list of who has found the bot. What is
left is a message that never existed.

The cost is real and worth naming: a `chat_id` configured wrongly now looks
exactly like a stranger, and the owner's own messages vanish in silence. The
configured id is written to the log on every start - `Registered 3 command(s)
for chat <id> only` - which is the number to compare against. A message from
the *configured* chat that reaches no agent is still logged, because there the
sender is the owner and "I wrote to it and nothing happened" is otherwise
indistinguishable from "it never arrived".

What the filter does not cover, and cannot, is *who* inside the chat: a
`chat_id` that names a group is a group whose every member can talk to the
agents.

The same reasoning decides where the command list is written. `setMyCommands`
takes a scope, and `default` and `all_private_chats` are resolved for every
user of Telegram - so a list written there is a menu shown to strangers, with
"Server status" in it, announcing that there is a machine behind this worth
poking at. They could never run any of it, but a sign on a locked door is
still a sign. `fSetTelegramCommands` writes the list to the configured chat's
scope alone and **deletes** the two public ones on every refresh: a list
written by an older version of this code lives on Telegram's side until
something removes it. `fHideTelegramPublicProfile` empties the other two public
strings, `setMyDescription` and `setMyShortDescription`, which are what fills
an empty chat under "What can this bot do?".

What remains visible is the bot's name, its picture and the Start button, which
Telegram draws in every empty chat with a bot and no API can remove. Pressing
it sends `/start`, which is dropped like anything else from another chat.

### Why the menu holds tools and not agents

Telegram draws `/name` beside every entry in the command menu - that string is
the entry, it is what gets typed into the box when it is tapped, and no API
hides it. So a menu of agents could never be the list of agents somebody wanted
to look at, and it grew with the roster while saying nothing about what the bot
was for.

The menu holds three things the bot can do. Which agents exist is a question,
and `/agents` answers it with inline buttons, where a button says `os-watcher`
and nothing else because a button's text is the bot's to choose.

The rest follows from that:

- **The selected agent is sticky.** Tapping a button or naming an agent picks
  it; everything unaddressed goes there until another one is picked. Naming the
  agent on every line is fine once and tiresome by the fourth message. It lives
  in `settings`, not in memory, because the service restarts on every update.
- **A reply still wins.** It is unambiguous, and it is what somebody holding a
  phone does. Nothing else changes the selection, so an agent never inherits a
  conversation by being the one that happened to speak last.
- **A deleted agent stops being selected.** `fReadSelectedAgent` checks the
  roster on the way out: reaching nobody beats reaching whoever took its id.
- **The bot speaks the installation's language.** `agent_language` first, the
  same setting the agents answer in - its lines appear in the same conversation
  as theirs.

### The sidebar shows who is working

```
every 5 seconds, and right after send / run now / an answer arriving
  api.js fRefreshAgentActivity        ← skipped while the tab is hidden
    GET /api/admin/agents
      web/api.fListAgents
        exec_client.fListRunningAgents          → /run/boa/exec.sock
          exec_daemon.fVerbListRunningAgents
            fListRunningAgentIds      ← one sweep of /proc, every agent at once
      each agent carries `running`
    fSetAgentAvatarActivity           ← data-running on the avatar; the list
                                        itself is never rebuilt on a timer
      fBuildAgentActivityArc          ← an SVG rounded rect over the border
  CSS animates its stroke-dashoffset  ← the shape stays still, the lit dash
                                        travels clockwise along the outline
```

### Logging in

```
POST /login
  views.fLoginPage
    auth.fCountRecentFailures         ← 10 per 15 minutes per address
    auth.fVerifyCredentials           ← argon2id; wrong email still hashes
    auth.fRecordAttempt
    auth.fLogIn                       ← session cookie, 12 hours
```

---

### A voice note arrives

`fHandleMessage → fRouteMessage → fEnqueueTelegram → audio_jobs → fRunOneJob → fDownloadTelegram → fTranscribe → fSubmitTranscript → fSendChatMessageLocked → runner`. The response uses ordinary Telegram delivery; the web chat adds the transcript and private player. Settings → Audio uses GET/PUT `/api/admin/audio`; model downloads use the `install_whisper_model` RPC and poll progress without blocking HTTP.

## 5. Entry point and route map

### HTTP

| Route | Method | Handler | File |
|---|---|---|---|
| `/login` | GET, POST | `fLoginPage` | `backend/web/views.py` |
| `/logout` | GET, POST | `fLogoutPage` | `backend/web/views.py` |
| `/` | GET | `fDashboardPage` | `backend/web/views.py` |
| `/kanban/` | GET | `fKanbanPage` | `backend/web/views.py` |
| `/tools/` | GET | `fToolsPage` → `/settings/?tab=tools` (preserves `family` and `agent`) | `backend/web/views.py` |
| `/settings/` | GET | `fSettingsPage` | `backend/web/views.py` |
| `/api/doc/` | GET | `fGetApiDocPage` | `backend/web/api_doc.py` |
| `/api/doc/openapi.json` | GET | `fGetOpenApiSpec` | `backend/web/api_doc.py` |
| `/api/admin/agent-templates` | GET | `fListAgentTemplates` | `backend/web/api.py` |
| `/api/admin/agents` | GET, POST | `fListAgents` (always carries `running` per agent), `fCreateAgent` | `backend/web/api.py` |
| `/api/admin/agents?kanban=1` | GET | `fListAgents`, adds `reads_kanban` per agent | `backend/web/api.py` |
| `/api/admin/agents/<id>` | GET, PUT, DELETE | `fGetAgent`, `fUpdateAgent`, `fDeleteAgent` | `backend/web/api.py` |
| `/api/admin/agents/<id>/run` | POST | `fRunAgentNow` | `backend/web/api.py` |
| `/api/admin/agents/<id>/journal` | GET | `fGetAgentJournal` | `backend/web/api.py` |
| `/api/admin/agents/<id>/chat` | GET, POST, DELETE | `fGetChat`, `fSendChatMessage`, `fClearChat` | `backend/web/api.py` |
| `/api/admin/agents/<id>/attachments/<id>` | GET | `fGetChatAttachment` | `backend/web/api.py` |
| `/api/admin/kanban` | GET | `fGetBoard` | `backend/web/api.py` |
| `/api/admin/kanban/cards` | POST | `fCreateCard` | `backend/web/api.py` |
| `/api/admin/kanban/cards/<id>` | PUT, DELETE | `fMoveCard`, `fDeleteCard` | `backend/web/api.py` |
| `/api/admin/kanban/cards/<id>/events` | GET | `fGetCardEvents` | `backend/web/api.py` |
| `/api/admin/kanban/cards/<id>/schedule` | PUT | `fScheduleCard` | `backend/web/api.py` |
| `/api/admin/kanban/deleted` | GET | `fGetDeletedCards` | `backend/web/api.py` |
| `/api/admin/tools` | GET | `fListTools` | `backend/web/api.py` |
| `/api/admin/skills` | GET | `fListSkills` | `backend/web/api.py` |
| `/api/admin/providers` | GET | `fListProviders` | `backend/web/api.py` |
| `/api/admin/themes` | GET | `fListThemes` | `backend/web/api.py` |
| `/themes/<name>.css` | GET | `fThemeStylesheet` | `backend/web/views.py` |
| `/api/admin/channels` | GET | `fListChannels` | `backend/web/api.py` |
| `/api/admin/channels/<name>` | PUT | `fConfigureChannel` | `backend/web/api.py` |
| `/api/admin/audio` | GET, PUT | `fGetAudioSettings`, `fUpdateAudioSettings` | `backend/web/api.py` |
| `/api/admin/audio/models/<vModel>/install` | POST | `fInstallAudioModel` | `backend/web/api.py` |
| `/api/admin/agents/<vAgentId>/audio/<vAudioId>` | GET | `fGetChatAudio` | `backend/web/api.py` |
| `/api/admin/settings` | GET, PUT | `fGetSettings`, `fUpdateSettings` | `backend/web/api.py` |
| `/api/admin/status` | GET | `fGetStatus` | `backend/web/api.py` |

Everything that is an API lives under `/api/`. Everything under `/api/admin/`
requires a session.

### Unix sockets

| `/run/boa-web/web.sock` | `0750 boa:boa` | gunicorn | The application itself. Only `boa-proxy` reaches it |

| Socket | Mode | Server | Verbs |
|---|---|---|---|
| `/run/boa/exec.sock` | `0660 root:boa` | `exec_daemon` | `ping`, `create_agent`, `delete_agent`, `read_agent_info`, `write_agent_info`, `read_system_prompt`, `write_system_prompt`, `read_crontab`, `write_crontab`, `run_now`, `list_running_agents`, `read_run_journal`, `read_usage_summary`, `read_chat`, `read_chat_attachment`, `send_chat_message`, `clear_chat` |
| `/run/boa/agent.sock` | `0666` | `agent_api` | `who_am_i`, `kanban_add_card`, `kanban_move_card`, `kanban_delete_card`, `kanban_list_cards`, `channel_write`, `mail_read`, `mail_delete`, `mail_move`, `mail_forward` |

### Command line

| Command | File |
|---|---|
| `runner.py --agent-id NNN [--prompt … or --prompt-on-stdin] [--chat-message … or --chat-message-on-stdin] [--turn-id …] [--dry-run]` | `backend/core/runner.py` |
| `install-update-reinstall-debian.sh --install\|--update\|--reinstall\|--backup [file]\|--restore <file>` | `deploy/` |
| `install-update-reinstall-alpine.sh --install\|--update\|--reinstall\|--backup [file]\|--restore <file>` | `deploy/` |

---

## 6. Impact analysis

What breaks if you change these.

| Component | Changing it affects |
|---|---|
| `paths.fNormalizeAgentId` | **Every path in the system.** It is the only validation between user input and a filesystem path. Weakening it turns any agent id into path traversal |
| `paths.py` constants | All four services, the installer and the systemd units. Changing `/opt/boa` means reinstalling |
| `deploy/haproxy/boa.cfg` | Every request. `accept-proxy` must match what the machine's HAProxy sends: with `send-proxy-v2` on that backend it is required, without it the bind refuses every connection |
| `backend/web/gunicorn.conf.py` bind | Must stay a Unix socket. Giving gunicorn a port and a certificate again reintroduces the PROXY-before-TLS failure |
| `exec_protocol.lKnownVerbs` | The privileged surface. Adding a verb adds a way for the web process to ask root for something. Each addition needs the same scrutiny as the first |
| `exec_daemon.fRunPrivilegedCommand` | Every privileged command. It never uses a shell; introducing `shell=True` there would make every agent name an injection point |
| `agent_api.fAuthenticate` | Every agent request to the board and channels. Both checks must stay |
| `db.cAppSchema` / `cKanbanSchema` | Existing installations. There is no migration system: schemas use `IF NOT EXISTS`, so **new columns need explicit migration code**, not a schema edit |
| `agent_scripts.cMinimumMinuteStep` | How often an agent may schedule itself. It is the only thing standing between a careless schedule and a loop with a cron line in front of it |
| `paths.lProtectedAgentFiles` | Which files move into the root-owned drawer. The installer's migration and the daemon that creates an agent both read it, so they cannot disagree about which they are |
| `agents.fBuildAgentInfo` | Only new agents. Existing `info.json` files are untouched, so new fields need a default read path |
| `exec_daemon.fVerbWriteAgentInfo` | **Every field of `info.json` that survives a save.** It rebuilds the file key by key, so a field it does not name is a field the interface silently drops the first time somebody presses Save. Lists are read through `fReadNameList`, which tells an absent key ("leave this alone") from an empty list ("take them all away"): read with `or`, unticking the last tool restored the previous list |
| `skills.fSelectInstalledSkills` | What reaches a prompt and what `skill.read` will open. Both the index and the tool filter through it, so a skill deleted from the server stops being mentioned instead of being promised and then failing |
| `providers.base` neutral shape | Every adapter and the runner |
| `tool_registry` interface | Every tool in `/opt/boa/tools/`, including ones the user wrote |
| `telegram_listener.fIsFromTheConfiguredChat` | Who may talk to your agents. A bot's username is public, so this check is the whole of the authorisation: weakening it lets anyone who finds the bot start runs on your server |
| `channels.fSendMessage` signature | Every caller, and the two senders that take two arguments. `pReplyToMessageId` is passed to Telegram and Discord, which are the two channels a person can answer through |
| `discord_markdown.cMaxDiscordLength` | Whether an agent's answer arrives at all. Discord refuses a `content` over 2000 characters, and refusing is what it does - not truncating |
| `agent_routing.fMatchNamedAgent` | Who a message reaches, in **both** listeners. The longest match is what makes `@News` and `@News Miner` two agents |
| `agent_routing.fBuildStatusReport` | What /status answers on both. One report, so the two cannot disagree about how many services there are |
| `discord_listener.fIsFromTheConfiguredChannel` | Which channel the agents listen to. Unlike Telegram there is no second check on who is talking: whoever may write in that channel may start runs |
| `kanban.lStates` | The board, the API, the frontend and every agent's prompt |
| `run_journal` entry shape | Both writer (runner) and readers (daemon, web). Old lines stay in journals: readers must tolerate missing fields |
| A file the daemon reads out of an agent home (`runs.jsonl`, `chat.jsonl`, `memory.md`) | Read only through `paths.fReadAgentOwnedFile`. A new file the daemon reads out of a home has to go through it too, or root reads whatever the agent points it at - a FIFO that never answers, a link to any file on the machine |
| What a backup holds (the `tar` line of `fDoBackup`) | New state under `/opt/boa/` that is the installation's and not the code's has to be added there, or a restore on a new machine loses it |
| The kernel limits of a run (`runner.cMaxProcesses`, `exec_daemon.cRunTasksMax`, `cRunMemoryMax`) | A tool that needs more than 1024 tasks or 2 GiB has to raise them; a browser is already a few hundred threads |
| `runner.py` as a path | Every scheduled run. Cron starts it by path with almost no environment, so the runner puts its own root on sys.path: without that, `import backend` fails and the traceback goes to cron's mail, which on a LAN box goes nowhere |
| `runner.dAnswerLanguageLines` | The line added to a system prompt telling the agent which language to answer in. Written IN that language, and it says it overrides the prompt's own rule - a preference next to a rule loses, measured |
| `agent_api.fFilterCardsForAgent` | What an agent may know exists. Every read of the board goes through it, and the orchestrator is the one exception. Filtering in the tool instead would put a security rule in a description the model can be talked out of |
| Which side a chat bubble sits on | Who is talking. A card is what the agent was asked to do, so it goes right with the user's messages; a scheduled run's report is the agent talking, so it stays left |
| `chat.lToolsWorthReporting` | Which tools make a scheduled run worth putting in the chat. Everything else stays in the journal: an hourly agent would otherwise post twelve "nothing to report" messages a day |
| `chat.lAskingRoles` | Which roles wait for an answer. A role that opens a turn and is not listed leaves the composer open while the agent works; one listed but never closed shuts the composer for ever |
| `kanban.cRunNow` | The word the browser, the agents and the API all send instead of a timestamp. Turning it into a time anywhere but `fValidateRunAt` loses `run_mode`, and with it the difference between "now" and a chosen moment |
| `chat.cReplayedTurns` | What every chat message costs. Each replayed turn is paid for again on the next message, so raising it makes long conversations progressively more expensive |
| `lTextColours` in `TestThemes` | Which colours the contrast test measures. A colour painted as text and left off that list is a colour nothing checks |
| A `style=` attribute in any template | Nothing: `style-src` is `'self'` with no `unsafe-inline`, so the browser throws it away. There is a test that fails if one appears |
| `.notice-layer` in `app.css` | Where every confirmation and every error in the application appears. `position: fixed` is load-bearing: `absolute` centres in the document instead of on the screen, which is the bug the layer exists to fix |
| `frontend/static/i18n/en-US.json` | Adding a key means adding it to the other thirteen, or that string falls back to English. `TestTranslations` fails on a missing key, a lost `{placeholder}` and a translated path or tool name |

---

## 7. Extension points

### A new provider

1. Write `backend/providers/<name>.py` with a class extending
   `base.BaseProvider`, setting `cProviderName`, `cDefaultModel`,
   `cDefaultBaseUrl` and implementing `fSendMessages`.
2. Add one row to `factory.dProviderRegistry`.
3. Add the name to `agents.lSupportedProviders`.
4. If it needs no key, add it to `factory.lSelfHostedProviders`.
5. Extra options (like DeepSeek's `thinking`) go in `lExtraConfigKeys`; the
   factory maps `reasoning_effort` → `pReasoningEffort` automatically.

Do not merge it into an existing adapter because the dialect matches. One file
per provider is deliberate.

### A new tool

Create one `.py` in `/opt/boa/tools/` declaring:

```python
cToolName = "namespace.verb"
cToolDescription = "What the model is told it does."
dToolSchema = {"type": "object", "properties": {...}, "required": [...]}

def fRunTool(pArguments, pContext):
  return "text the model sees"
```

It runs as the calling agent. If it needs something agents may not reach, add a
verb to the agent API instead and call it through `agent_api_client`.

The file must be owned by root: the application imports it as code.

### A new skill

Create a directory in `/opt/boa/skills/` with a `SKILL.md` in it:

```markdown
---
name: BackupVerification
description: One line. This is what every run pays for.
---

The procedure, at whatever length it needs.
```

Nothing to register and no restart: `fListSkills` reads the directory, so it
appears in the interface on the next page load. Tick it on an agent, give that
agent `skill.read`, and it is in its prompt on the next run.

Anything else in the directory ships with the skill. It is world-readable, so
the skill can say "run `verify.sh` in this directory" and the agent can.

The name is the directory name: letters, digits and dashes, starting with a
letter. The `name:` in the header is what a person sees in the list; the
directory name is what an agent asks for.

### A new privileged operation

1. Add the verb constant to `exec_protocol` and to `lKnownVerbs`.
2. Write `fVerb<Name>` in `exec_daemon` and add it to `dVerbHandlers`.
3. Add a wrapper in `exec_client`.

Validate every argument before it reaches a path or a command line, and keep
the verb specific. A verb general enough to be reusable is usually a verb
general enough to be abused.

### A new channel

Sending only:

1. Write `fSendTo<Name>` in `channels.py`.
2. Add it to `lChannels` and `dChannelSenders`.
3. Add its fields to `dChannelFields` in `frontend/static/js/settings.js`, and
   any that is a credential to `lSecretChannelFields` there and to
   `lSecretConfigFields` in `channels.py`.

Receiving as well, which is what makes it a conversation:

4. Write `fRead<Name>Messages` in `channels.py`, returning them oldest first.
5. Write `<name>_inbox.py`: two tables in `db.cAppSchema` and the selected
   agent in a setting.
6. Write `<name>_listener.py` against `agent_routing`, which already holds the
   roster, the name matching, the closed answer and the status report. What is
   left is the protocol.
7. Write `<name>_texts.py` for the sentences that channel says differently,
   falling through to `telegram_texts` for the rest.
8. A service file in `deploy/systemd/` and one in `deploy/openrc/`, the name
   in `lServices` and in the seven places the Debian installer names its
   units, and in `system_info.lBoaServiceNames`.
9. Its switch in `dChannelSwitches`, its `chat.source<Name>` key in the
   fourteen catalogues, and `<name>` in `exec_daemon.lKnownChatSources`.

### A new language

Fourteen ship: `de-DE`, `en-GB`, `en-US`, `es-AR`, `es-ES`, `fr-FR`, `hi-IN`,
`it-IT`, `ja-JP`, `ko-KR`, `pt-BR`, `pt-PT`, `ru-RU`, `zh-CN`. A fifteenth is
five places, and the tests name every one of them:

1. Copy `frontend/static/i18n/en-US.json` and translate the values.
2. Add the tag to `lSupportedLanguages` in `frontend/static/js/i18n.js`.
3. Add an `<option>` to the three pickers: two in
   `frontend/templates/settings.html`, one in `login.html`, by tag.
4. Add a line to `runner.dAnswerLanguageLines`, written IN that language.
5. Add a block to `telegram_texts.dTexts` and its tag to that module's
   `lSupportedLanguages`, or the bot falls back to English. Add one to
   `discord_texts.dTexts` too: it holds the three sentences Discord says
   differently, and a language missing from it gets those three in English.

`TestTranslations` in `tests/test_web.py` fails on a missing key, an extra
one, an empty string, a lost `{placeholder}`, a translated path or tool name,
an unsorted file, a picker that does not offer the language, a missing prompt
line and a missing Telegram block. The five non-Latin languages are also
checked for actually being written in their own script, because a file of
English strings under a Russian name passes every other check.

What a translation may change: a file name the English text gives as an
EXAMPLE, such as `check-disk.sh`. Nothing looks for those.

### A new page

1. A route in `backend/web/views.py` returning `render_template`.
2. A template extending `app_base.html`.
3. A `<li>` in the `nav` of `app_base.html`.
4. Its own JS in `frontend/static/js/`, starting with
   `await fWaitForTranslations()` before rendering anything.
