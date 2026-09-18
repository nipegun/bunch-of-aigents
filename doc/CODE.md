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
it are not its business to change, and they sit in `agents/xxx/config/`, which
is `root:agent-xxx 0750`.

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

This was measured before it was fixed, on a real install: an agent appended
`mail.read` to its own `info.json` and the privileged daemon then reported the
tool as granted - so an agent could grant itself the mailbox, the channels, or
raise its own ceilings. It could also replace its own prompt with "ignore all
your rules", which would have stayed that way on every run from then on.

Isolation between agents needs none of this: `/opt/boa/agents/` is
`root:root 0711` and each home is 0700, so the kernel already refuses. That is
why it holds even when a tool has a bug in it.

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

### Six processes, one of them privileged

| Process | User | Why it exists |
|---|---|---|
| `boa-proxy` | `boa` | HAProxy: terminates TLS, serves both ports |
| `boa-web` | `boa` | Serves the interface and the API, on a Unix socket |
| `boa-exec` | `root` | The only privileged component |
| `boa-agent-api` | `boa` | Holds what agents may use but not read |
| `boa-buzzer` | `boa` | Wakes an agent when one of its cards comes due |
| `boa-telegram` | `boa` | Listens on Telegram and hands what arrives to an agent |

The last three are `boa` and not root on purpose: each of them wants something
done as an agent's own user - starting a run, writing into a 0700 home - and
each of them asks `boa-exec` to do it rather than being given the privilege. A
service that can be reached from outside, as the Telegram listener effectively
can, is the last one that should hold it.

### Two installers, one application

`deploy/install-update-reinstall-debian.sh` writes systemd units, and **needs
systemd to be PID 1 of the running machine**: a Debian booted with anything
else is not a target, and the installer refuses it rather than installing onto
a machine that would start nothing.
`deploy/install-update-reinstall-alpine.sh` writes OpenRC services into
`/etc/init.d/`, from `deploy/openrc/`, and needs nothing in advance: it
installs OpenRC itself when the machine has none. Both install the same six processes,
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
cache, so it keeps the old one and the six services stay out of it - they
start during the install, because `rc-service start` does not need the tree,
and then do not come back after a reboot, because `openrc default` does.
`fInstallServices` ends with an unconditional `rc-update -u`.

### What each installer demands of the machine, and what it installs itself

The Debian installer refuses to run where systemd is not PID 1
(`fRequireSystemd`, called before anything at all is installed). Everything it
sets up is started and kept alive by systemd - the six units, the machine's
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
to touch a service on a system it did not boot. The six services start in a
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

`fLoadTranslations` also carries a sequence number now, so that two changes in
quick succession cannot land out of order and leave the page in a language
nobody asked for.

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

Three things genuinely need root: creating a system user, installing another
user's crontab, and starting a process as another user. Everything else does
not. So root lives in one small daemon with a **closed vocabulary of verbs**
over a Unix socket, and there is deliberately no verb meaning "run this
command". An attacker reaching that socket can create an unprivileged agent;
they cannot run code as root.

The socket is `0660 root:boa`, and `SO_PEERCRED` is checked on every connection
so that only root and `boa` are served whatever the file mode happens to say
after some future update.

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

The patterns are the same ones `frontend/static/js/markdown.js` uses. Two
renderers disagreeing about what counts as markdown would mean one answer
reading differently in the two places it is shown, and the point of sending
both is that they are the same conversation.


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
nothing. And `browser.open` goes through `public_url.fCheckUrlIsPublic` like
`web.fetch`: an agent reading a hostile page could otherwise be told to open
the router's admin panel, and a browser with a session is a far better tool for
that than a fetch.

A session cookie still disappears when the browser closes, in this as in every
browser. What survives is what the site marked to survive.

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
    removes on a rule written last month, a person can still find.

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

One of them, `webnavigator`, has no crontab. It is the example for the browser
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

### No build step

The frontend is Jinja2 templates, plain CSS and plain JavaScript. The
production target is a self-hosted Debian or Alpine box; a deployment that
needs a Node
toolchain to change a stylesheet is a deployment that rots. For the same reason
`/api/doc/` renders its own OpenAPI spec rather than loading Swagger UI from a
CDN: a LAN server may have no outbound internet, and documentation that fails
without one fails exactly when someone is debugging.

---

## 2. Module map

| Module | Path | Responsibility | Depends on | Used by |
|---|---|---|---|---|
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
| `public_url` | `backend/core/public_url.py` | Whether a URL an agent was given resolves to a public address | — | `web.fetch`, `rss.fetch` |
| `agent_scripts` | `backend/core/agent_scripts.py` | Scripts an agent writes for itself, and the cron lines that run them. Validates names and schedules, and never rewrites the wake-up line | `paths` | `script.*`, `cron.*` |
| `kanban` | `backend/core/kanban.py` | The board and its history | `db` | `agent_api`, `web/api` |
| `channels` | `backend/core/channels.py` | Telegram, Discord, Mattermost, X | `paths` | `agent_api`, `web/api` |
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
| `telegram_inbox` | `backend/core/telegram_inbox.py` | Which agent said what on Telegram, and which questions are still being answered | `db` | `telegram_listener`, `agent_api` |
| `browser` | `backend/core/browser.py` | The shared browser and this agent's own profile. One handle for the length of a run, closed by `atexit` | `paths` | the five `browser.*` tools |
| `telegram_html` | `backend/core/telegram_html.py` | Markdown into the fourteen tags Telegram accepts. Same patterns as `markdown.js`, so both renderers agree on what markdown is | — | `channels` |
| `telegram_texts` | `backend/core/telegram_texts.py` | What the bot says itself, in the language the installation was set to | `db` | `telegram_listener` |
| `markdown.js` | `frontend/static/js/markdown.js` | Renders an agent's answer as DOM nodes, never as markup | — | `dashboard.js` |
| `jsonhighlight.js` | `frontend/static/js/jsonhighlight.js` | Colours the schema blocks on the documentation page. DOM nodes, never markup | — | `api_doc.html` |
| `themes` | `backend/core/themes.py` | Lists the stylesheets in `frontend/themes/` and reads their headers | `paths` | `web/api`, `web/views` |
| `agent_templates` | `backend/core/agent_templates.py` | Reads the example agents in `backend/agents/examples/`, one Markdown file each | — | `web/api` |
| `mailbox` | `backend/core/mailbox.py` | IMAP and SMTP for the configured mailbox. Holds the credentials so agents never do | `db` | `agent_api` |
| `theme.js` | `frontend/static/js/theme.js` | Adds the chosen theme's stylesheet, from the head, before the first paint | — | every page |
| `system_info` | `backend/core/system_info.py` | What the machine looks like, read with no privileges | `paths` | `web/api` |

---

## 3. Key symbol index

Public and load-bearing symbols only. Line numbers move; the file and the
behaviour are what to trust.

### Paths and identity

| Symbol | File:line | What it does |
|---|---|---|
| `fNormalizeAgentId` | `backend/core/paths.py:105` | Validates an agent id and zero-pads it. **Every path built from user input goes through this.** Raises on anything outside 0–999 |
| `fGetAgentHome` | `backend/core/paths.py:120` | `/opt/boa/agents/xxx` |
| `fGetAgentApiTokenPath` | `backend/core/paths.py:140` | Where an agent's API token lives |

### Agents

| Symbol | File:line | What it does |
|---|---|---|
| `fValidateAgentName` | `backend/core/agents.py:58` | 2–40 characters, no shell metacharacters |
| `fGetNextFreeAgentId` | `backend/core/agents.py:101` | Lowest free id from the filesystem, starting at 001 |
| `fBuildAgentInfo` | `backend/core/agents.py:114` | The `info.json` of a new agent, with conservative defaults |
| `fWriteAgentInfo` | `backend/core/agents.py:154` | Atomic write preserving 0600 ownership |
| `fHashApiToken` | `backend/core/agents.py:179` | SHA-256; the raw token is never stored |
| `fFindAgentByApiToken` | `backend/core/agents.py:224` | Turns a token into an identity |

### The privileged daemon

| Symbol | File:line | What it does |
|---|---|---|
| `fIsPeerAllowed` | `backend/core/exec_daemon.py:74` | Only root and `boa`, checked per connection |
| `fRunPrivilegedCommand` | `backend/core/exec_daemon.py:90` | Runs a command list with no shell, optionally as another user |
| `fVerbCreateAgent` | `backend/core/exec_daemon.py:142` | Creates user, home, config, token; **rolls back on any failure** |
| `fVerbWriteCrontab` | `backend/core/exec_daemon.py:277` | Installs a crontab as the agent's own user |
| `fListRunningAgentIds` | `backend/core/exec_daemon.py` | One sweep of `/proc` naming every agent with a run in flight. Backs both `only_if_idle` and the sidebar's turning ring |
| `dVerbHandlers` | `backend/core/exec_daemon.py` | The closed verb table. The whole privileged surface is these ten rows |

### The agent API

| Symbol | File:line | What it does |
|---|---|---|
| `fAuthenticate` | `backend/core/agent_api.py:88` | Token **and** `SO_PEERCRED` must agree |
| `fAgentMayUseKanban` | `backend/core/agent_api.py:116` | Server-side permission check, not a prompt instruction |
| `fRequireOwnCard` | `backend/core/agent_api.py:171` | An agent may only change cards it created or owns |
| `fVerbChannelWrite` | `backend/core/agent_api.py` | Sends on the agent's behalf, prefixing its real name |

### The run loop

| Symbol | File:line | What it does |
|---|---|---|
| `AgentRun` | `backend/core/runner.py:124` | One bounded conversation |
| `fCheckCeilings` | `backend/core/runner.py:166` | Returns which ceiling stopped the run, or empty to continue |
| `fAskForClosingAnswer` | `backend/core/runner.py` | After a ceiling, asks once with no tools for the answer it was cut off from giving |
| `fExecute` | `backend/core/runner.py:187` | The loop: ask, run tools, feed back, stop |
| `fSelectAllowedTools` | `backend/core/runner.py:111` | Withholds kanban tools when the agent has them switched off |
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
| `fLoadAllTools` | `backend/core/tool_registry.py:92` | Loads every valid tool; a broken file is skipped, not fatal |
| `fRunTool` | `backend/core/tool_registry.py:125` | Enforces permission, returns `(text, is_error)`; a raising tool never kills a run |
| `ToolContext` | `backend/core/tool_registry.py:43` | What a tool is told about its caller |

### Skills

| Symbol | File:line | What it does |
|---|---|---|
| `fIsValidSkillName` | `backend/core/skills.py:57` | A name, never a path. Refuses rather than cleans, like the template and theme names |
| `fParseSkill` | `backend/core/skills.py:76` | The `---` header and the body. Same parser shape as `agent_templates.fParseTemplate` |
| `fSelectInstalledSkills` | `backend/core/skills.py:176` | The names in an agent's list that still exist on disk. **Every path into the feature goes through this**, so a deleted skill never reaches a prompt |
| `fBuildPromptSection` | `backend/core/skills.py:193` | The index: one line per skill, names and descriptions only. `""` when the agent has none |
| `fRunTool` | `backend/tools/skill_read.py` | Returns one body, checked against the agent's own `info.json` |


### Telegram, both ways

| Symbol | File:line | What it does |
|---|---|---|
| `fReadTelegramUpdates` | `backend/core/channels.py` | One long poll. The connection is made outwards, which is what lets this work behind a NAT with nothing forwarded |
| `fSendToTelegram` | `backend/core/channels.py` | Sends, and returns the `message_id` - the only thing that makes a later reply routable |
| `fReadConfigForEditing` | `backend/core/channels.py` | A channel's file as it is on disk, so saving a change merges instead of replacing it |
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
| `fAgentOwnsCard` | `backend/core/kanban.py:217` | Creator **or** assignee |
| `fDeleteCard` | `backend/core/kanban.py:235` | Deletes, keeping a row in `deleted_cards` |
| `fReadMessages` | `backend/core/mailbox.py` | Newest messages of a folder, read-only: nothing is marked seen |
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
        Popen runner.py --prompt … --turn-id …     ← as agent-007
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
          Popen runner.py --chat-message --turn-id
      telegram_inbox.fAddPending      ← on disk: a restart must not lose the answer
```

The answer is sent by the listener and not by the run, for the same reason the
card announcement is written by the executor: the run is the agent's own user,
and the channel credentials belong to `boa`. The run only writes to its chat;
the listener reads that and does the sending.

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
and `/agents` answers it with inline buttons, where a button says `oswatcher`
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

## 5. Entry point and route map

### HTTP

| Route | Method | Handler | File |
|---|---|---|---|
| `/login` | GET, POST | `fLoginPage` | `backend/web/views.py` |
| `/logout` | GET, POST | `fLogoutPage` | `backend/web/views.py` |
| `/` | GET | `fDashboardPage` | `backend/web/views.py` |
| `/kanban/` | GET | `fKanbanPage` | `backend/web/views.py` |
| `/tools/` | GET | `fToolsPage` | `backend/web/views.py` |
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
| `/api/admin/settings` | GET, PUT | `fGetSettings`, `fUpdateSettings` | `backend/web/api.py` |
| `/api/admin/status` | GET | `fGetStatus` | `backend/web/api.py` |

Everything that is an API lives under `/api/`. Everything under `/api/admin/`
requires a session.

### Unix sockets

| `/run/boa-web/web.sock` | `0750 boa:boa` | gunicorn | The application itself. Only `boa-proxy` reaches it |

| Socket | Mode | Server | Verbs |
|---|---|---|---|
| `/run/boa/exec.sock` | `0660 root:boa` | `exec_daemon` | `ping`, `create_agent`, `delete_agent`, `read_agent_info`, `write_agent_info`, `read_system_prompt`, `write_system_prompt`, `read_crontab`, `write_crontab`, `run_now`, `list_running_agents`, `read_run_journal`, `read_usage_summary`, `read_chat`, `send_chat_message`, `clear_chat` |
| `/run/boa/agent.sock` | `0666` | `agent_api` | `who_am_i`, `kanban_add_card`, `kanban_move_card`, `kanban_delete_card`, `kanban_list_cards`, `channel_write`, `mail_read`, `mail_delete`, `mail_move`, `mail_forward` |

### Command line

| Command | File |
|---|---|
| `runner.py --agent-id NNN [--prompt …] [--dry-run]` | `backend/core/runner.py` |
| `install-update-reinstall-debian.sh --install\|--update\|--reinstall` | `deploy/` |
| `install-update-reinstall-alpine.sh --install\|--update\|--reinstall` | `deploy/` |

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
| `exec_daemon.fVerbWriteAgentInfo` | **Every field of `info.json` that survives a save.** It rebuilds the file key by key, so a field it does not name is a field the interface silently drops the first time somebody presses Save |
| `skills.fSelectInstalledSkills` | What reaches a prompt and what `skill.read` will open. Both the index and the tool filter through it, so a skill deleted from the server stops being mentioned instead of being promised and then failing |
| `providers.base` neutral shape | Every adapter and the runner |
| `tool_registry` interface | Every tool in `/opt/boa/tools/`, including ones the user wrote |
| `telegram_listener.fIsFromTheConfiguredChat` | Who may talk to your agents. A bot's username is public, so this check is the whole of the authorisation: weakening it lets anyone who finds the bot start runs on your server |
| `channels.fSendMessage` signature | Every caller, and the three senders that take two arguments. `pReplyToMessageId` is passed to Telegram alone on purpose |
| `kanban.lStates` | The board, the API, the frontend and every agent's prompt |
| `run_journal` entry shape | Both writer (runner) and readers (daemon, web). Old lines stay in journals: readers must tolerate missing fields |
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

1. Write `fSendTo<Name>` in `channels.py`.
2. Add it to `lChannels` and `dChannelSenders`.
3. Add its fields to `dChannelFields` in `frontend/static/js/settings.js`.

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
   `lSupportedLanguages`, or the bot falls back to English.

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
