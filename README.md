# Bunch of AIgents

Self-hosted AI agents that run on a schedule, on your own GNU/Linux server
(Debian or Alpine).

Each agent is a real Linux user with its own home directory, its own crontab
and its own shell access. They coordinate through a shared kanban board you can
watch in the browser, and they can message you on Telegram, Discord, Mattermost
or X.

It is built for one person running it on their own LAN.

![Bunch of AIgents interface](https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/doc/screenshot.png)

## Requirements

- **Debian with systemd as PID 1, or Alpine with OpenRC.** The init system is
  not incidental here: the seven services are systemd units on one and OpenRC
  scripts on the other, so a Debian that boots with anything else has nothing
  to run them. **Do not try it on a Debian without systemd** - the installer
  checks before it touches the machine and refuses, which is the right answer
  but a wasted download. Check it with `systemctl is-system-running`: it has
  to answer (`running`, `degraded`, `starting`), not print "System has not
  been booted with systemd as init system (PID 1)". A container needs
  `systemd systemd-sysv dbus` installed and `/sbin/init` as its command. On
  Alpine nothing is needed in advance: the installer adds `openrc` itself if
  the machine has none.
- `root` access. Neither installer uses `sudo`, and neither needs it.
- About 500 MB of disk for the application and its Python environment.
- `haproxy`, installed by the installer. It terminates TLS, because the PROXY
  header the machine's HAProxy sends arrives before the TLS handshake and only
  a proxy can read it there.
- A model to talk to: either an API key for a cloud provider, or Ollama,
  llama.cpp or vLLM running somewhere you can reach.

The installer also builds **whisper.cpp v1.9.4** in `/opt/boa/whisper/`, installs FFmpeg and downloads the multilingual `base` model (about 142 MiB extra). Compilation, system dependencies and the browser need additional disk space. A missing Python interpreter is installed before its version is checked. On Alpine, services release the installer's SSH output so it returns control when finished.

## What it does

- **Telegram audio.** **Settings → Audio** selects local whisper.cpp or OpenAI, Groq, Mistral, Together AI, Hugging Face or Cloudflare using an already saved API key. All 30 native models are offered, with downloads on demand. A voice reply reaches its original agent as text and appears in the web chat, with optional audio playback.
- **An agent is a Linux user.** Creating one in the web interface creates
  `agent-007` on the system, with a home directory no other agent can read.
  That is the isolation: the kernel's, not a sandbox written in Python.
- **Agents run on their own schedule.** Each has its own crontab, owned and run
  by its own user, so an agent wakes up, does its work and exits.
- **You talk to them.** Clicking an agent opens a chat: ask it to do
  something and it uses its tools and answers when it is done. The
  conversation is remembered.
- **One conversation per agent, not one per person.** A card that comes due is
  posted into that same chat as the run starts, and the answer appears under
  it, so an agent's chat is everything it was asked to do - by you or by
  another agent - and what it did about it.
- **They share a kanban board.** Agents add cards, move them and see each
  other's work. You watch at `/kanban/` instead of reading logs.
- **Any model, cloud or self-hosted.** Twenty-five providers ship with it -
  Anthropic, OpenAI, Google, DeepSeek, Mistral, Qwen, xAI and the rest; the
  routers in front of them, OpenRouter, Groq, Together, Vercel and more; and
  Ollama, llama.cpp and vLLM on your own hardware. Each agent picks its own,
  with a backup for when that one is down.
- **Spending ceilings that actually stop it.** Tokens, steps, seconds and runs
  per day, per agent. An unattended agent on a paid API is otherwise an open
  invoice.
- **Tools you can extend.** Each tool is one `.py` file in `/opt/boa/tools/`.
  Drop a new one in and it appears under **Settings → Tools**, grouped into
  subtabs such as Automation and Browser.
- **Skills they share.** A procedure written once in `/opt/boa/skills/` can be
  given to as many agents as you like. What an agent learns on its own dies in
  its own memory; a skill does not.
- **A browser each, with its own sessions.** An agent can log into a site,
  fill a form and click - not just read a page - and its cookies live in its
  own 0700 home, so one agent's login is not every agent's login.
- **Answer them from Telegram or Discord.** Pick an agent with /agents, or
  reply to a message one sent you, and what you write reaches it, starts a run
  and comes back answered on your phone. The whole exchange is in that agent's
  conversation in the web interface too, both halves of it, so one screen still
  shows everything.
- **Fourteen languages.** German, English (UK and US), Spanish (Spain and
  Argentina), French, Hindi, Italian, Japanese, Korean, Portuguese (Brazil and
  Portugal), Russian and Simplified Chinese. The interface, the line that tells
  your agents which language to answer in, and what the two bots say.

## Shipped tools

| Tool | What an agent can do with it |
|---|---|
| `bash.run` | Run shell commands as its own unprivileged user |
| `kanban.add_card` | Put a task on the shared board |
| `kanban.move_card` | Move one of its own cards between columns |
| `kanban.delete_card` | Remove one of its own cards |
| `kanban.list_cards` | Read the whole board |
| `channel.write` | Send a message to a configured channel |
| `web.fetch` | Read a public web page |
| `memory.append` | Write something down for its future self |
| `memory.replace` | Tidy up what it remembers |
| `skill.read` | Read a procedure it has been given |
| `browser.open` | Open a page in its own browser, keeping cookies |
| `browser.read` | Read the open page, or its links |
| `browser.click` | Click a link or a button on it |
| `browser.type` | Fill a field, optionally submitting |
| `browser.screenshot` | Save a picture of it for you |
| `image.send` | Attach a PNG to the web chat and to the Telegram reply when the conversation started there. Images fill the web message's text area |

You choose per agent which of these it gets. A tool an agent is not given is a
tool it cannot call, and that check runs on the server rather than in the
prompt.

## Skills

A skill is a written procedure: how a job is done here, step by step. One
directory each, under `/opt/boa/skills/`:

```
/opt/boa/skills/BackupVerification/SKILL.md
/opt/boa/skills/DiskPressure/SKILL.md
```

None ship with it, and that is the point: a skill describes how a job is done
on THIS machine - these hosts, this backup, this certificate - so a generic
one would be a procedure nobody follows. You write yours over SSH, as root,
and an update never touches them. A skill can bring files of its own - a
script, a template - next to its `SKILL.md`, and the agent can run them.

Only the name and the one-line description of each skill go into an agent's
prompt. It reads the rest with `skill.read` when it decides it needs it, which
is why giving an agent five skills costs it a couple of hundred tokens per run
rather than ten thousand.

Skills belong to root and are written on the server, like the tools, for the
same reason: what a skill says goes into the reasoning of an agent that runs at
four in the morning with nobody watching. The web interface decides which agent
gets which; it does not edit them.


## Install

One installer per distribution, and both take the same three flags. Run it as
`root`.

### On Debian

> **systemd has to be running on the machine.** Run `systemctl is-system-running`
> first: if it prints "System has not been booted with systemd as init system
> (PID 1). Can't operate.", stop here. Every service this installs is a systemd
> unit, so there would be nothing to start them, and the installer refuses for
> that reason rather than leaving you with an installation that serves nothing.

```bash
curl -fsSL https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-debian.sh \
  | bash -s -- --install --email you@example.com
```

If `curl` is not installed - a minimal Debian often has neither it nor
`wget` - put it there first, or the line above prints `curl: command not
found` and stops:

```bash
apt-get update && apt-get install -y curl
```

Or download the installer first and read it before running it, which is the
better habit:

```bash
wget https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-debian.sh
less install-update-reinstall-debian.sh
chmod +x install-update-reinstall-debian.sh
./install-update-reinstall-debian.sh --install --email you@example.com
```

### On Alpine Linux

The same three flags, a different script: it writes OpenRC services instead of
systemd units. One line, with `wget` and piped into `sh`, because a fresh
Alpine has neither `curl` nor bash and both of those are BusyBox's:

```bash
wget -qO- https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-alpine.sh \
  | sh -s -- --install --email you@example.com
```

Use `curl -fsSL` in place of `wget -qO-` on a machine that has it - and watch
that line if you do, because `curl: not found` piped into `sh` prints its
error and then **succeeds**, having installed nothing.

The installer is POSIX shell rather than bash for the same reason as the
`wget`: a fresh Alpine has no bash for `| bash -s --` to reach. It installs
bash on the way through - every agent is given a bash shell - so on a machine
that already has one, `| bash -s --` works just as well.

Or download it first and read it before running it:

```bash
wget https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-alpine.sh
less install-update-reinstall-alpine.sh
chmod +x install-update-reinstall-alpine.sh
./install-update-reinstall-alpine.sh --install --email you@example.com
```

Two things differ once it is up, and both are the system's doing, not a
decision:

- **No browser.** Playwright publishes no build for musl and Alpine packages
  none, so `browser.open` and the rest say so when an agent calls one.
  `web.fetch` and `rss.fetch` work as they do anywhere.
- **`rc-status` instead of `systemctl status`**, and `rc-service boa-web
  restart` in place of `systemctl restart boa-web`.

The installer:

1. Creates the `boa` system user and the tree under `/opt/boa/`.
2. Installs Python dependencies into `/opt/boa/venv/`.
3. Generates a self-signed TLS certificate if there is no Let's Encrypt one.
4. Asks whether to serve the application on 11080/11443 behind an HAProxy on
   80 and 443, or on 80 and 443 directly. Pass `--ports proxied|direct` to
   answer it in advance. The answer is remembered, so `--update` never asks
   again nor quietly changes it. Choosing `direct` retires the machine's
   own HAProxy - stopped, out of every runlevel or masked, and its
   `/etc/haproxy/haproxy.cfg` deleted if this installer wrote it, kept as
   `haproxy.cfg.before-boa.<date>` if somebody else did - so that nothing
   takes 80 and 443 at the next boot. The haproxy package itself stays: the
   application's own proxy is that binary.
5. Creates one agent: `manager`, the orchestrator. Everything else is an
   example you pick from when you press **+** - `web-navigator`, `os-watcher`,
   `mail-watcher` and others, one Markdown file each in `backend/agents/examples/`. The
   empty agent is the first choice offered; the examples come under it.
6. Installs and starts seven services: systemd units on Debian, OpenRC
   services supervised with `supervise-daemon` on Alpine.
7. Writes what it did, and your login password, to
   `/opt/boa/logs/install.log` (root, mode 0600).
8. Asks the application for its login page before saying it has finished. If
   the page does not come, it says so, writes into that same log what the
   machine looked like at that moment - what curl made of the request, whether
   anything is listening on the port, the state of the seven services and the
   last lines of what they printed - and names the log rather than reporting
   success. An `--update` also puts the previous version back first.

The email address you give is the only login. The password is generated for
you; read it with:

```bash
cat /opt/boa/logs/install.log
```

That one file is both things: the full log of the installation and the
credentials it generated. The login page names it, so nobody has to remember
where it is.

## Update and reinstall

```bash
./install-update-reinstall-debian.sh --update      # keeps agents and data
./install-update-reinstall-debian.sh --reinstall   # deletes everything first
```

On Alpine it is the same two flags, on the other script:

```bash
./install-update-reinstall-alpine.sh --update
./install-update-reinstall-alpine.sh --reinstall
```

`--reinstall` deletes every agent, home directory, crontab and the kanban
board. It asks for confirmation unless you pass `--yes`.

An install that died halfway - a download that failed, a network that
dropped - is finished by running `--install` again: it picks up where it
stopped, and `--update` says so if it finds one.

## Backup and restore

```bash
./install-update-reinstall-debian.sh --backup                       # writes /root/boa-backup-<date>.tar.gz
./install-update-reinstall-debian.sh --backup /mnt/usb/boa.tar.gz
./install-update-reinstall-debian.sh --restore /root/boa-backup-<date>.tar.gz
```

The same two flags on the Alpine script. A backup is one archive, `root` and
mode 0600, taken with the services running. It holds everything the
installation is and the code is not: the two databases, copied through
SQLite's own backup API so nothing still in a write-ahead log is missed; the
provider keys, the channel secrets and the session secret; the certificates;
every agent with its home, its protected files, its Linux user and its
crontab; the skills and tools written on this server; and the installation
log, for the password in it. It does not hold the code, the Python environment
or the browser, nor this machine's own two choices - the port mode and whether
it has a browser - so a restore never imports another machine's.

To move to a new machine: `--install` there, then `--restore` the archive. The
restore stops the services, creates the agent users again with the same names
and, where free, the same ids, replaces the data, installs the crontabs and
starts everything. The login is then the backup's, and its password is
appended to `/opt/boa/logs/install.log`, under the heading `Credentials of
the restored backup`. It asks for confirmation unless you pass `--yes`.

The archive holds every secret the installation has. Keep it as private as
the machine.

## A browser for each agent

Grant `image.send` to attach captured PNGs to the web chat and to Telegram replies. New **web-navigator** agents include it; existing agents can enable it under their own **Tools → Images** tab.

Installed by default: without one an agent can read a public page and nothing
else. It is about 600 MB of Chromium, so the installer asks once, and an
installation short of disk can decline:

```bash
./install-update-reinstall-debian.sh --update --browser no    # leave it out
./install-update-reinstall-debian.sh --update --browser yes   # add it back
```

This whole section is about Debian. On Alpine there is no browser at all:
Playwright publishes no build for musl, so the flag is accepted and the
browser tools say so when an agent calls one.

The browser itself is one copy, in `/opt/boa/playwright/`, owned by root and
read-only to everybody else. What is **not** shared is the profile:

```
/opt/boa/agents/001/browser/profile/     agent-001, 0700
/opt/boa/agents/002/browser/profile/     agent-002, 0700
```

So agent 001 logging into something does not leave agent 002 logged in, and a
session survives to the next run because the cookies are on disk. That
separation is the kernel's - the same 0700 home everything else of an agent's
lives in - and it is the thing a hosted product cannot offer when all of its
agents share one machine.

Headless, always, and `browser.open` refuses private addresses exactly as
`web.fetch` does: an agent reading a hostile page must not be talked into
opening the router.

## Open it

The application's own HAProxy listens on `127.0.0.1:11443` (HTTPS) and
`127.0.0.1:11080` (HTTP, which redirects). Those ports are not reachable from
outside the server: the machine's own HAProxy is what serves the LAN, and it
forwards to 11443 with `send-proxy-v2` so the real client address survives.

With that configuration in place, open:

```
https://your-server/
```

The certificate is self-signed unless you have Let's Encrypt certificates in
`/opt/boa/certificates/`, so the browser will warn you once.

### What the machine's HAProxy must look like

The backend pointing at this application needs two things:

```
backend https-out
  mode tcp
  server srv-https-out 127.0.0.1:11443 check port 11080 send-proxy
```

- **`send-proxy`** so the real client address reaches the application. Without
  it every request looks like it came from 127.0.0.1 and the login rate limit
  stops being per address.
- **`check port 11080`**, so the health check knocks on the plain HTTP port
  and not on the TLS one. A TCP check against the TLS port connects and hangs
  up without a handshake, and the application's own HAProxy logs each one as
  an SSL handshake failure: one line every two seconds, for ever. Both ports
  belong to one process, so one answering means the other is there. Do not
  add `check-send-proxy`: 11080 does not accept PROXY protocol.
- **No `option ssl-hello-chk`.** Its ClientHello predates TLS 1.2, so a backend
  that requires TLS 1.2 - this one, and any modern Apache or nginx - fails the
  check and is marked down for ever. The symptom is a 503 from a service that
  is running perfectly. A plain `check` already verifies the port answers.

## First run

1. Log in with your email and the generated password.
2. Press **+** in the sidebar to create your first agent.
3. Pick its provider and model. For Ollama on the same machine, the defaults
   are already right.
4. If it is a cloud provider, write the API key to the agent's own home:
   ```bash
   mkdir -p /opt/boa/agents/001/keys
   echo "sk-..." > /opt/boa/agents/001/keys/anthropic.key
   chown -R agent-001:agent-001 /opt/boa/agents/001/keys
   chmod 700 /opt/boa/agents/001/keys
   chmod 600 /opt/boa/agents/001/keys/anthropic.key
   ```
5. Write its system prompt: what it is for, and what "done" means.
6. Give it the tools it needs. Start with the kanban ones.
7. Press **Run now** and watch the board.
8. When it does what you want, give it a schedule.

In **Settings → Channels**, channels are ordered alphabetically and each
configured channel shows **Configured** in green, matching a stored API key.
Under **Operating system**, service states align with the values in **This machine**.

**Night High Contrast** fills the selected agent with grey and frames each
selected tab with a closed outline. **Log out** asks for confirmation in the
centre of the screen.

## Services

| Service | Runs as | What it does |
|---|---|---|
| `boa-proxy` | `boa` | HAProxy: terminates TLS on 11443, redirects 11080, and is the only thing listening on a port |
| `boa-web` | `boa` | The web interface and the API, on a Unix socket behind the proxy |
| `boa-exec` | `root` | Creates users, installs crontabs, starts agent runs |
| `boa-agent-api` | `boa` | The door agents use to reach the board and channels |
| `boa-buzzer` | `boa` | Watches the board and wakes an agent when a card comes due |
| `boa-telegram` | `boa` | Listens on Telegram, so you can answer an agent from your phone |
| `boa-discord` | `boa` | The same for a Discord channel |

```bash
systemctl status boa-proxy boa-web boa-exec boa-agent-api boa-buzzer \
                 boa-telegram boa-discord
journalctl -u boa-exec -f
```

The same six on Alpine, where they are OpenRC services supervised with
`supervise-daemon`, and what each one prints goes to its own file under
`/opt/boa/logs/`, rotated weekly:

```bash
rc-status
rc-service boa-exec status
tail -f /opt/boa/logs/boa-exec.log
```

## Security

The design assumes an agent will eventually do something you did not intend,
because it is a language model with a shell.

- **Each agent is a separate Linux user**, and its home is `0700`. Agents
  cannot read each other's files, prompts or API keys.
- **`/opt/boa/agents/` is `0711`**, so no agent can even list which other
  agents exist.
- **No agent runs as root, ever.** Only `boa-exec` does, and it accepts a
  closed list of eighteen operations over a Unix socket. There is no "run this
  command" among them.
- **A run is bounded by the kernel, not only by its ceilings.** No agent may
  have more than 1024 processes and threads, so a fork bomb stops at the
  number; on Debian each run lives in a systemd scope of its own with 2 GiB
  of memory, which also ends whatever the run left running when it finishes.
- **Agents never see channel credentials.** A bot token is not a message: it is
  permanent authority to send anything that bot can send. Agents ask the agent
  API to send, and it sends.
- **Agents only touch their own cards.** Reading the board is shared; changing
  it is not.
- **`web.fetch` refuses private addresses**, checking the resolved IP and
  re-checking on every redirect, so an agent reading a hostile page cannot be
  told to call your internal network.

It is meant for a LAN and should not be exposed to the internet.

## Documentation

- [doc/MANUAL.md](doc/MANUAL.md) — how to use it, day to day.
- [doc/CODE.md](doc/CODE.md) — how it is built, for developers and for AI
  models.
- `/api/doc/` on the running server — the full API reference.

Spanish translations: [README.es-ES.md](README.es-ES.md),
[README.es-AR.md](README.es-AR.md).

## Licence

MIT. See [LICENSE](LICENSE).
