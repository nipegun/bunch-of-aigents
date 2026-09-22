# Manual

How to use Bunch of AIgents, day to day.

## Contents

1. [What it runs on](#what-it-runs-on)
1. [If you are on Alpine](#if-you-are-on-alpine)
1. [Logging in](#logging-in)
2. [The interface](#the-interface)
3. [The example agents](#the-example-agents)
3. [Creating your first agent](#creating-your-first-agent)
4. [Talking to an agent](#talking-to-an-agent)
5. [Agent settings](#agent-settings)
6. [Giving an agent a model](#giving-an-agent-a-model)
5. [Writing a system prompt](#writing-a-system-prompt)
6. [Choosing tools](#choosing-tools)
7. [Giving an agent a skill](#giving-an-agent-a-skill)
8. [Giving an agent a browser](#giving-an-agent-a-browser)
9. [Spending ceilings](#spending-ceilings)
8. [Scheduling an agent](#scheduling-an-agent)
9. [The kanban board](#the-kanban-board)
10. [Themes](#themes)
11. [Channels](#channels)
12. [The orchestrator](#the-orchestrator)
13. [Backing up and restoring](#backing-up-and-restoring)
14. [When something does not work](#when-something-does-not-work)
1. [Audio transcription](#audio-transcription)

---

## What it runs on

Two systems, and on each of them the init is part of the requirement, not a
detail:

- **Debian with systemd as PID 1.** The seven services are systemd units. On a
  Debian that boots with anything else there is nothing to start them, so the
  installer checks `systemctl is-system-running` before it touches the machine
  and refuses if systemd is not there. Do not try it on such a machine: the
  answer will not change.
- **Alpine with OpenRC.** The seven services are OpenRC scripts supervised with
  `supervise-daemon`. Nothing has to be installed in advance - the installer
  adds `openrc` itself when the machine has none.

Everything else in this manual is the same on both.

## If you are on Alpine

Every command in this manual that names `systemctl` or `journalctl` is the
Debian one. The application is the same on Alpine; what changes is the init
system and where the logs go:

| On Debian | On Alpine |
|---|---|
| `systemctl status boa-web` | `rc-service boa-web status`, or `rc-status` for all six |
| `systemctl restart boa-web` | `rc-service boa-web restart` |
| `journalctl -u boa-web -f` | `tail -f /opt/boa/logs/boa-web.log` |
| `install-update-reinstall-debian.sh` | `install-update-reinstall-alpine.sh` |

One feature is missing there and is not coming back: there is no browser,
because Playwright publishes no build for musl. The browser tools stay in the
list and say so when an agent calls one.

---

## Logging in

Open `https://your-server/` and log in with the email address you gave the
installer and the password it generated. If you do not have it:

```bash
cat /opt/boa/logs/install.log
```

That file is the whole installation log with the credentials at the end of it,
and the login page names it for exactly this moment.

**Log out** opens a confirmation in the centre of the screen. Confirm to end
the session, or choose **Cancel** or press Escape to stay signed in.

There is one account. Change its password under **Settings → Account**.
Changing it asks for the current one as well: that is what makes it a
change by you rather than by whoever finds the browser open. It also ends
every other session, on every other device, at once - which is the point
of changing it when you think somebody else has one.

The first time you open the application after an update, it asks you to
log in again. Sessions from before the update carry no record of when
they were granted, and "I cannot tell" is answered by asking.

After ten failed attempts from the same address the login is closed for fifteen
minutes, for correct passwords too.

## The interface

The sidebar on the left lists your agents. Each shows its id, its name, how
many times it has run and how many tokens it has spent. Every box is the same
height, so a long name is cut with an ellipsis - hover over it to read the whole
of it. The square around the
id is ringed in green when the agent is enabled and in red when it is not.

**When an agent is working, a lit segment travels clockwise round that
green ring.** It tells you
that the agent is in the middle of a run right now - not what it is doing, just
that it is doing something. It starts turning as soon as you send it a chat
message or press **Run now**, and stops when the run ends, whether the run came
from you, from its schedule or from a card falling due. The ring is checked
every few seconds, so it can lag a moment behind.

At the bottom of the sidebar, two dots show whether the background services are
running. If either is red, agents will not run — see
[When something does not work](#when-something-does-not-work).

The **+** button creates an agent.

## The agent you start with

The installation creates exactly one.

**`manager` (agent-000)** coordinates the others. It breaks goals into cards
and hands them out. It is enabled from the start.

That is deliberately all of it: an installation that arrives with agents nobody
asked for is one that starts with things to switch off. Everything else is an
**example**, offered when you press **+**.

## The example agents

Press **+** and you are asked what to start from:

The **empty agent** heads the list, because it is the one answer that is always
right and every example is a shortcut to it. The examples come underneath, in
alphabetical order:

| Choice | What it does |
|---|---|
| **Empty agent** | No prompt, no tools, no schedule. Write it yourself. |
| **backup-watcher** | Checks that your backups ran, are recent, and are not suspiciously small. |
| **cert-watcher** | Warns when a TLS certificate is about to expire, while there is still time. |
| **disk-cleaner** | Finds what is filling the disk and says what could go. Proposes; never deletes. |
| **kanban-watcher** | Reads the board every weekday morning and writes one short summary. |
| **log-watcher** | Reads the logs you point it at and reports what is new or newly frequent. |
| **mail-watcher** | Watches a mailbox and acts on what arrives, following rules you write into its prompt. |
| **news-watcher** | Reads the RSS feeds you list in its prompt and reports what matches your rules. |
| **os-watcher** | Watches this machine: disk, memory, swap, load, and whether the services are up. |
| **site-watcher** | Checks that the sites you list answer, answer quickly, and still say what they used to. |
| **web-navigator** | Drives its own browser to do what you ask on a site: search, log in, fill a form, click through, and report what it found. |

`web-navigator` is the one with no schedule: it works when you ask it to, and
the request is the task. It is also the one that shows what the browser is
installed for - it logs in, clicks and fills forms, where the others read
pages. It will not type a password, buy anything or press a send button: it
gets to that step and stops, saying which button would finish the job.

Every example says, before you pick it, which tool families it comes with and
how often it wakes up. An example is a set of permissions as much as it is a
prompt: "watches a mailbox" does not tell you it arrives able to delete mail.

Every example arrives **switched off and with no model**: choosing one gives
you its prompt, its tools and a suggested schedule, and then it waits for you
to pick a provider and turn it on.

They are starting points. Change the prompt, the tools, the schedule - all of
it - and several of them say in their own prompt what they need you to fill in
before they are any use, rather than failing at three in the morning.

They live on the server as one Markdown file each, in
`/opt/boa/webapp/backend/agents/examples/`. Dropping a file in there adds an example to
the list; there is nothing else to edit. If you would rather not be asked at
all, turn off **Offer example agents when creating one** under
**Settings → Interface**.

### No agent has root

Not one, the orchestrator included. That is the whole isolation model, and it
is worth being clear about because it decides what an agent like `os-watcher`
can do:

- **Looking needs no privileges.** `df`, `free`, `uptime`, `nproc`,
  `systemctl is-active` all work as an ordinary user. An agent can see a disk
  filling up long before it fills.
- **Fixing usually does need them, and it does not have them.** The prompts
  tell it to say exactly what it would run instead of trying and failing: a
  card reading "needs root: journalctl --vacuum-size=200M would free about
  1.2G" is worth more than a failed attempt.

If you want something fixed automatically, put that command in root's own
crontab. An agent deciding on its own to delete files as root is not a feature
anyone wants at three in the morning.

## Creating your first agent

Press **+**, choose an example or an empty agent, and give it a name. That
creates, on the server:

- the Linux user `agent-001`,
- its home at `/opt/boa/agents/001/`, mode 0700,
- `info.json`, `system-prompt.md` and an API token inside it.

The id is the lowest free number. `000` is reserved for the orchestrator.

A new agent starts with the kanban tools and nothing else, and with
conservative ceilings. It has no schedule, so it does nothing until you give it
one or press **Run now**.

## Talking to an agent

Click an agent in the sidebar and you get its chat. Type what you want it to
do and press Enter; Shift+Enter starts a new line.

A message is a run: the agent uses its tools, does the work and answers when it
is finished. That can take minutes, so the composer is disabled while it works
and the answer appears when it arrives. Each answer shows what it cost, in
tokens and steps.

Answers are rendered as markdown - headings, tables, lists, quotes and code
blocks - because that is how a model writes. Your own messages are shown
exactly as you typed them. A link is only a link when it points at http or
https; anything else stays as the text it was.

The conversation is remembered. The last ten exchanges are replayed to the
model on every message, so the agent knows what you were talking about - and so
a long thread costs more per message than a short one. **Clear chat** starts
over.

Talking to an agent does **not** count against its runs-per-day ceiling: that
ceiling exists to stop an unattended schedule, not to stop you typing. The
per-run ceilings on tokens, steps and time do apply.

Each agent has its own conversation, stored in its own home directory, and no
agent can read what you said to another.

The conversation is not only what you typed. When one of the agent's cards
comes due, the card is posted into that same chat the moment the run starts,
and the run's answer appears under it - so opening an agent shows everything it
was asked to do, by you or by another agent, and what it did about it. See
[When a card runs](#when-a-card-runs).

## Agent settings

The chat is what you get by clicking an agent. Everything else - model, tools,
ceilings, prompt, schedule - is behind the **wrench** on the right of the
agent's box in the sidebar.

## Giving an agent a model

Under **LLMs**, pick a provider. The list is short on purpose: it offers
the three self-hosted providers, which need no key, and every cloud provider
whose key is set in **Settings → API keys**. A cloud provider with no key
would take the agent all the way to its first run and fail there, so it is
not offered. Set its key and it appears.

An agent already configured with a provider keeps seeing it in the list even
if its key is removed, marked *(no key configured)* - otherwise the box would
show a provider nobody chose and save it on the next click.

**On hardware of yours.** No key, and the Base URL box is where your own server listens.

| Provider | Models listed | Default model |
|---|---|---|
| `ollama` | 23 | `gpt-oss:20b` |
| `llamacpp` | 1 | `local-model` |
| `vllm` | 3 | you name the model |

**Companies serving the models they built.**

| Provider | Models listed | Default model |
|---|---|---|
| `anthropic` | 10 | `claude-opus-5` |
| `openai` | 16 | `gpt-5-mini` |
| `google` | 8 | `gemini-3.6-flash` |
| `deepseek` | 2 | `deepseek-flash` |
| `kimi` | 3 | `kimi-k2.6` |
| `minimax` | 8 | `MiniMax-M2` |
| `mistral` | 3 | `labs-leanstral-1-5` |
| `qwen` | 15 | `qwen3.8-max` |
| `xai` | 3 | `grok-4.3` |
| `zai` | 10 | `glm-4.5` |
| `cohere` | 2 | `command-a-reasoning-08-2025` |
| `inception` | 1 | `mercury-2` |

**Hosts and routers, serving models other people built.** One key reaches many models; the model id names which one.

| Provider | Models listed | Default model |
|---|---|---|
| `openrouter` | 154 | `anthropic/claude-sonnet-4.5` |
| `perplexity` | 48 | `perplexity/deepseek-v4-flash-0731` |
| `cerebras` | 1 | `gpt-oss-120b` |
| `cloudflare` | 6 | `@cf/openai/gpt-oss-20b` |
| `deepinfra` | 49 | `moonshotai/Kimi-K3` |
| `fireworks` | 13 | `accounts/fireworks/models/gpt-oss-120b` |
| `groq` | 5 | `openai/gpt-oss-20b` |
| `huggingface` | 27 | `deepseek-ai/DeepSeek-V4-Flash-0731:fastest` |
| `together` | 8 | `openai/gpt-oss-120b` |
| `vercel` | 110 | `openai/gpt-oss-20b` |

One provider needs two values in the key box: **Cloudflare Workers AI**
builds its address out of the account id, so its key is written
`account-id:api-token`, both halves from the Cloudflare dashboard. The box in
**Settings → API keys** says so.

The model field suggests what that provider serves, and filters the list as you type - but it is a normal text box, so a model released this morning can simply be typed in. Those suggestions come from `/opt/boa/config/providers/<provider>.json`, which you can edit on the server; an update never overwrites a file you changed.

Self-hosted providers need nothing else if they run on the same machine.

**Base URL** appears only for `ollama`, `llamacpp` and `vllm`, and it is where
your own server listens - the default is the usual port on this machine, which
is right when the model runs beside the application. Pick a cloud provider and
the box is gone: that address is fixed, this installation already has it, and
the only thing a box there could do is let a typo break a working agent. The
backup model works the same way.

For a cloud provider, the simplest path is the **API keys** tab in Settings, which every agent on that provider then uses. To give this one agent a different key, write it into its own home, as root:

```bash
mkdir -p /opt/boa/agents/001/keys
echo "sk-..." > /opt/boa/agents/001/keys/anthropic.key
chown -R agent-001:agent-001 /opt/boa/agents/001/keys
chmod 700 /opt/boa/agents/001/keys
chmod 600 /opt/boa/agents/001/keys/anthropic.key
```

The file name is the provider name. Each agent reads only its own key, so one
agent cannot spend another's budget.

### API keys

Settings has an **API keys** tab: one key per cloud provider, shared by every
agent that uses it. The self-hosted providers are not listed, because they need
none.

A key is stored in `/opt/boa/config/apikeys/<provider>.key`. The directory is
`0700` and the files `0600`, both owned by the web user, so no agent can read
any of them: not the key of another provider, and not its own. When an agent
runs, the agent API hands it the key **for the provider that agent is
configured with, and no other**: an agent on Ollama cannot ask for the
Anthropic key.

Installations made before this directory was renamed keep their keys in
`/opt/boa/config/keys/`; `--update` moves them across and removes the old
directory.

Worth being clear about what that does and does not protect. An agent that
legitimately uses a paid provider holds its key while it runs - it needs it to
make the call, and an agent with `bash.run` could print it. What the shared
store prevents is one agent collecting the keys of providers it does not use,
and it keeps every key out of the agent home directories, where one stray
backup would expose all of them at once.

To bill one agent to a different account, put a key in that agent's own home at
`keys/<provider>.key`. That one wins over the shared one.

## Writing a system prompt

The system prompt is what the agent is. It is stored as `system-prompt.md` in
the agent's home and you edit it in the interface.

What works:

- **Say what the agent is for**, in one or two sentences.
- **Say what "done" means.** An agent with no definition of done either stops
  too early or never stops.
- **Say what to do when blocked.** Without this, models invent a way around the
  obstacle. "If you cannot do it, say so on the board and stop" is enough.
- **Tell it to read the board first.** It is the only memory it has between
  runs.

What does not work: telling it not to use a tool. If you do not want it to use
a tool, do not give it the tool — the prompt is a suggestion, the tool list is
enforced.

## What an agent remembers

Each agent has a `memory.md` in its home directory, and that file is the only
thing it carries from one run to the next. It writes to it with `memory.append`
when it learns something worth keeping, and tidies it with `memory.replace`.

The whole file is loaded at the start of every run, which is what makes it
useful and also what makes it cost: every character is paid for on every model
call. It is capped at 8000 characters, and past 6000 the agent is told to trim
it.

Good things to keep: where something lives, what a command turned out to be,
what you prefer. Not the diary of what it did - that is the board.

You can read and correct it yourself under **Memory** in the agent's settings.
A wrong fact an agent keeps acting on is worth fixing by hand.

## Choosing tools

Under **Tools**, tick what this agent may use. A tool that is not ticked is not
shown to the model and would be refused by the server even if asked for.

Each family gets a box of its own, with a count of how many of that family this
agent has: "may this agent read the mailbox?" is one decision, and it is drawn
as one box. The switch that turns the kanban board on for an agent sits at the
foot of the **Kanban** box, under the tools it governs.

- **`bash.run`** — shell commands as that agent's user. It has no root and
  cannot get any. Give it when the agent has actual work to do on the machine.
- **`kanban.*`** — the shared board. Give at least `list_cards` and `add_card`
  to anything that should be visible.
- **`channel.write`** — messages to you. Also tick the channels in the **Channels** tab.
- **`web.fetch`** — public pages only. Private and loopback addresses are
  refused.
- **`rss.fetch`** — an RSS or Atom feed, as a list of entries rather than the
  XML document. Much cheaper than fetching the same feed with `web.fetch`, and
  it saves the agent the parsing. Both live under **Internet**.
- **`script.*` and `cron.*`** — under **Automation**. The agent writes a script
  into its own `scripts/` directory and schedules it in its own crontab, for
  recurring work that does not need it to think: the script runs on its own,
  costs no tokens, and the agent reads the results on its next run. It may only
  schedule its own scripts, nothing more often than every 5 minutes, and it can
  never touch the line that wakes it up.

An agent can do a great deal inside its own home, and nothing at all outside
it. It cannot see that another agent exists, let alone read its prompt: the
agents directory is traversable but not listable and each home is private to
its own Linux user, so that is the kernel refusing rather than a check in
Python.

It also cannot rewrite **what it is**. Its granted tools, its spending
ceilings, its system prompt and its API token live in a drawer inside its home
that belongs to root: the agent reads them and cannot change them. You change
them; it does not. The one thing about itself it may edit is its memory.
- **`mail.*`** — the mailbox set up under **Settings → Email**. See below.
- **`skill.read`** — the written procedures ticked on the **Skills** panel. It
  needs both: the tool here and at least one skill there.

### The mail tools

Four of them, and they need an IMAP mailbox configured under
**Settings → Email**. The agent never sees that password: it says what it wants
done and the agent API, which holds the credentials, does it.

| Tool | What it does |
|---|---|
| `mail.read` | Reads messages. **Does not mark anything as seen**, so your own unread count still means what it meant. |
| `mail.move` | Files a message into another folder of the same account. The folder has to exist. |
| `mail.delete` | Sends a message to the account's Trash, where there is one. |
| `mail.forward` | Forwards a message, **only to the addresses you listed**. |

That last one is the important one. An inbox is the one input to an agent that
anybody in the world can write to, so `mail.forward` is checked against your
list by the server on every single forward - not by the agent, and not by
something written in its prompt. With the list empty, forwarding is refused
outright.

Give `mail.read` on its own to an agent that only has to watch. Add `mail.move`
for filing, and think twice before `mail.delete` and `mail.forward`.

The **kanban** checkbox at the bottom switches the board off for this agent
entirely. Unticked, it gets no kanban tools at all and stops adding cards,
which is the switch to use for an agent whose work does not belong on the
board.

## Giving an agent a skill

A skill is a written procedure: how a job is done here, step by step. None
ship with the application: a skill is about THIS machine - these hosts, this
backup, this certificate - so a generic one would be a procedure nobody
follows. You write your own on the server, as root:

```bash
mkdir -p /opt/boa/skills/BackupVerification
nano /opt/boa/skills/BackupVerification/SKILL.md
chown -R root:root /opt/boa/skills
chmod 00755 /opt/boa/skills/BackupVerification
chmod 0644 /opt/boa/skills/BackupVerification/SKILL.md
```

The file starts with a name and a one-line description between two `---`
rules, and the rest is the procedure:

```markdown
---
name: BackupVerification
description: How to check that last night's backups actually ran.
---

1. Read /var/log/backup.log ...
```

Each directory under `/opt/boa/skills/` then shows up as a checkbox on the
agent's **Skills** panel. Tick one, give the agent the `skill.read` tool under
**Tools**, and press **Save**. From its next run the agent knows that procedure exists and can read
it when the job comes up.

### Why bother, when there is already the system prompt

Three reasons, and the third is the one that matters:

- **The prompt is what an agent is for; a skill is how a job is done.** Six
  agents can share one procedure without six copies of it going out of date
  separately.
- **A skill can be as long as it needs to be.** A system prompt is paid for on
  every call of every run, so it has to stay short. A skill is paid for once,
  by the run that reads it.
- **What an agent learns on its own dies with it.** Its memory lives inside a
  home no other agent can open. A skill is the place to put what you want the
  next agent to know too.

### Writing one

There is no editor for this in the interface, on purpose: what a skill says
goes straight into the reasoning of an agent that runs at four in the morning
with nobody watching, so it belongs to root, like the tools. You write them on
the server:

```bash
mkdir -p /opt/boa/skills/DatabaseBackup
nano /opt/boa/skills/DatabaseBackup/SKILL.md
```

The file starts with a two-line header and then says whatever it needs to say:

```markdown
---
name: DatabaseBackup
description: How the nightly dump is taken and where it goes.
---

# Database backup

1. Dump with `mysqldump --single-transaction`, never with the table lock.
2. Write it to /srv/backups/, never to /tmp.
...
```

The `description` is the line that matters most. It is the only part every run
pays for, and it is what the agent decides on when it is choosing whether to
read the rest. "How the nightly dump is taken and where it goes" tells it when
this applies; "Database stuff" does not.

Reload the agent's page and the skill is in the list.

### A skill can bring its own files

Anything else in the directory travels with it:

```
/opt/boa/skills/DatabaseBackup/
  SKILL.md
  dump.sh
  exclude-tables.txt
```

Agents can read and run those, so the procedure can say "run `dump.sh` in this
directory" instead of spelling out forty lines of shell. `skill.read` tells the
agent which files are there and where.

### What it costs

Only the name and the description of each skill go into the prompt - about two
lines each. The body is fetched with `skill.read`, once, by an agent that
decided it needs it, and only then. Giving an agent five skills costs it a
couple of hundred tokens per run, not ten thousand, which is why you can give
it five without thinking about the bill.

### If you delete a skill that agents are using

Nothing breaks, and no agent is left promising something it cannot deliver:

- It **disappears from the prompt** of every agent that had it, on their next
  run. An agent is never told about a procedure it cannot read.
- It **disappears from the Skills panel**, so nobody can tick it again.
- The name **stays in the agent's `info.json`** until something rewrites it, so
  putting the directory back restores the skill with nothing else to do.
- If the agent asks for it anyway - it can remember the name from an earlier
  run - it is told the skill is on its list and not installed any more, and
  told not to guess what it said.

One thing to know: **pressing Save on that agent while the skill is missing
drops it from the list for good.** The interface only saves skills that exist,
which is what keeps a deleted one from lingering for ever. Put the directory
back before saving the agent, or tick the skill again afterwards.

## Giving an agent a browser

`web.fetch` reads a public page and nothing else: no login, no form, no button.
If an agent needs to *use* a site rather than read it, it needs a browser.

It comes installed: the installer asks once, and yes is the default. It is
about 600 MB of Chromium, so a machine short of disk can decline, and change
its mind later either way:

```bash
./install-update-reinstall-debian.sh --update --browser no    # leave it out
./install-update-reinstall-debian.sh --update --browser yes   # add it back
```

The answer is remembered, like the ports. Then tick the browser tools on the
agent's **Tools** panel:

None of this applies on Alpine: there is no browser there at all, because
Playwright publishes no build for musl. The tools stay in the list and say so
when an agent calls one.

| Tool | What the agent can do |
|---|---|
| `browser.open` | Go to a page. Cookies are kept |
| `browser.read` | Read the open page again, one part of it, or its links |
| `browser.click` | Click a link or button, by its visible text or a selector |
| `browser.type` | Fill a field, optionally pressing Enter |
| `browser.screenshot` | Save a PNG into its own downloads directory |
| `image.send` | Attach a PNG to the reply in the web chat and Telegram |


`browser.screenshot` saves a PNG on the server. To display it in the chat,
the agent then calls `image.send` with that path. Grant **image.send** under
**Agent settings → Tools → Images**, then save. New agents created from
**web-navigator** already include it; existing agents keep their current grants.

The image fills the message's text area in the web chat, preserving its
aspect ratio and full height. It can also be opened at its original size.
When the conversation started on Telegram, it is sent there too. Tall or large
captures are delivered as PNG documents. A failed upload retries the missing
part without repeating the text or images that already arrived.

Only PNG files inside that agent's home are accepted, up to 50 MiB each and
16 per reply. Attachments stay private and require a signed-in session to view.
An existing screenshot can be sent by asking the agent to use `image.send`
with its saved path.

### Each agent's sessions are its own

```
/opt/boa/agents/001/browser/profile/     agent-001, 0700
/opt/boa/agents/002/browser/profile/     agent-002, 0700
```

An agent that logs into a site stays logged in **on its next run**, because the
cookies are on its own disk. And no other agent is logged in, because that
directory is 0700 and belongs to its Linux user - the kernel refuses, there is
no check in Python to get wrong.

Session cookies still end when the browser closes, here as in any browser. What
a site marks to persist, persists.

### What it will not do

- **No private addresses.** `browser.open` refuses `192.168.*`, `127.*` and the
  rest, exactly as `web.fetch` does. An agent that has just read a hostile page
  must not be talked into opening your router, and a browser with a session
  would be a much better tool for that than a fetch.
- **No screen.** It is headless. `browser.screenshot` is how you see what it
  saw; the agent itself cannot look at the picture.
- **Nothing without the tools.** As with everything else, a tool the agent has
  not been given is a tool it cannot call, and that check is on the server.

If the browser was never installed, the tools still appear in the list and
answer with the command to run. They do not vanish, and they do not fail
silently.

## Spending ceilings

Four ceilings, per agent, and every run stops at whichever it reaches first:

| Ceiling | Default | What it protects against |
|---|---|---|
| Tokens per run | 16384 | A single expensive conversation |
| Steps per run | 25 | A loop that calls tools forever |
| Seconds per run | 300 | A run that hangs |
| Runs per day | 48 | A cron line that is too eager |

These are not paranoia. An agent that wakes hourly on a paid API, with no
ceiling and nobody watching, is an invoice that grows while you sleep.

Raise them once you have seen what the agent actually uses, on its **History**
panel.

### The backup model

Under **LLMs** there is a second provider and model, below the first. It is
used only when the main one **fails** - no key, no answer, a model that is not
there - and the run carries on with it from the same step, replaying what has
happened so far, so the work already done is not thrown away.

It is tried **once per run**. If the backup fails too, the run fails: trying
each in turn for ever would burn the ceilings on an outage and still have
nothing to show. Falling back is written into the agent's history, because a
run that quietly answers with a different model, and bills a different account,
has to say so.

Leaving the backup provider on **none** is the default, and means a failure
ends the run.

Pick the **same provider** for the backup and the model box fills in a
*different* model from that provider's catalogue, not the same one again. The
same provider and the same model cannot answer anything the main one could not:
it would fail for exactly the same reason, every time. If you type the pair
back to identical anyway, a line under the field says so - it is your agent, so
it is a warning and not a refusal.


When a run stops at its token or step ceiling, the agent is asked once more -
with no tools, on a small budget of its own - for the answer it was about to
give, so a run that spent its whole budget gathering facts does not end on
"I am going to check the system". The chat says so under the answer, because
that answer may be cut short. The time ceiling gets no such call: the run is
already late.

That closing call resends the whole conversation, so on a long tool-heavy run
it is not cheap: a run stopped at a 12000-token ceiling was measured finishing
at 24901. The token ceiling is therefore a budget for the work, not a hard
maximum for the run. Nothing is spent that way unless a ceiling was hit.

### What the kernel enforces on top

The four ceilings are enforced by the run itself. Two more are enforced by
the kernel, so they hold when the run is the thing that went wrong: no agent
may have more than 1024 processes and threads at once, so a command that
forks without end stops there and not at the machine; and on Debian each run
lives in a systemd scope of its own with 2 GiB of memory, which also ends
whatever the run left running in the background when it finishes. A run the
memory limit kills is reported in its History as failed and in its chat as an
error, like any other. A browser is already a few hundred threads, which is
why the number is not smaller.

## Scheduling an agent

Under **Cron**, write the agent's crontab. It is the agent's own crontab,
owned and run by its own Linux user, exactly as if you had run `crontab -e` as
that user.

Every hour:

```
0 * * * * /opt/boa/venv/bin/python3 /opt/boa/webapp/backend/core/runner.py --agent-id 001
```

Every weekday at 08:00:

```
0 8 * * 1-5 /opt/boa/venv/bin/python3 /opt/boa/webapp/backend/core/runner.py --agent-id 001
```

The interface shows the exact line for the agent you are editing, so you can
copy it and change only the timing.

Leave it empty to remove the schedule. Untick **Enabled** to keep the schedule
but have the agent ignore it.

If you use a paid provider whose pricing varies by hour — DeepSeek charges
several times more during peak hours — that choice belongs here.

## The kanban board

The page has two tabs: **Board**, which is the three columns, and **Create
card**, which is the form. Which one is open is in the URL, so a reload and the
back button keep it. Saving a card takes you back to the board.

Three columns: **todo**, **doing**, **done**.

The board is what agents use to leave each other work and what you use to see
what has actually happened. Every card carries its history: who created it, who
moved it, when and why.

A card has a title and a **What to do** box. The title names it; the box is
where the instructions go, and an agent reads both. A card assigned to an agent
with nothing in the box leaves it guessing, which is the usual reason an agent
does nothing with a card it has been handed.

The other reason is that the agent cannot see the board at all. An agent reads
it by calling `kanban.list_cards` or not at all - the board is never put into
its prompt - so an agent without that tool never learns the card exists. **Assign
to** says so when you pick such an agent. It is a warning, not a block: the card
is still created, and ticking the tool under the agent's **Tools** tab is all it
takes.

A card on the board shows who made it, who has it, when it was made, the
first two lines of its title, the first three of what there is to do, and
**when it runs**. The whole of a clipped title or body is in its tooltip.

That last line is the one worth reading. A card with no time on it is not
late: nobody is woken for it, and its agent will find it on its next
scheduled run. **Move to** is how you move a card by hand - this board has no
dragging.

You can add, move and delete any card. **An agent sees and changes only its
own**: a card is an agent's own if it created it or if it is assigned to it.

That is a wall, not a preference. An agent cannot learn that another agent's
work exists at all - not the titles, not how many there are, not that there is
anything there. Ask an agent to move a card that is not its own and it is told
there is no such card of its own; a card that does not exist gets the same
sentence, because a refusal that told the two apart would be a way of asking
the board what is on it, one id at a time.

The exception is **manager** (agent 000), the orchestrator: its job is to hand
work out and follow it up, so it reads the whole board. That is why
coordination is its job and not anyone else's.

A destructive confirmation has **no default button**: it opens with the focus
on the dialog itself, so Enter does neither thing and you have to say which one
you mean. Escape cancels. Click the red button to go ahead.

An ordinary confirmation, one that destroys nothing, does open with the focus on
its confirm button, ringed, where Enter means yes.

Deleting a card leaves a row recording that it existed and who deleted it, so
an agent cannot erase the evidence of what it was doing.

## Settings

Settings are grouped into tabs, and the tab is in the URL, so a reload or a
bookmark lands where you were:

| Tab | What is in it |
|---|---|
| **Operating system** | What this machine is, how much memory and disk are left, and whether the four services are up - each one green when active and red when it is not. Read with no privileges, the same way `os-watcher` reads it |
| **Account** | The single email address and password. Changing the password needs the current one |
| **Email** | SMTP, for when something needs to reach you by mail |
| **Channels** | Discord, Mattermost, Telegram, X, in alphabetical order - one box each, with its own Save |
| **Audio** | Transcription engine, provider, model downloads, language and Telegram audio retention |
| **Tools** | Installed tools, grouped into subtabs such as Automation and Browser |
| **Agents** | Settings for every agent at once. Kept on the server: a run started by cron has no browser to read a preference from |
| **Chat** | How the message box behaves: whether Enter sends, whether each answer shows what it cost |
| **Kanban** | How many cards each column shows, and whether to list recently deleted ones |
| **Interface** | Theme, language, how long a pop-up message stays, and whether the example agents are offered |

Under **Operating system**, the service states line up with the second column
of **This machine**.

The Chat, Kanban and Interface preferences are kept in your browser rather than
on the server: they describe how you work on this machine, and a phone and a
desktop can reasonably disagree.

### Audio transcription

On Alpine, installation and updates return control of the SSH session when finished; OpenRC keeps the services running.

Open **Settings → Audio**. These settings are stored on the server and apply to voice notes and audio files received through Telegram.

1. Choose **Local · whisper.cpp** or **Provider API**. Transcription starts disabled.
2. For local recognition, choose a model and click **Download model** if needed. The installer prepares `base`; the selector offers all 30 official models, including English `.en` and quantized variants, plus `ggml-*.bin` models manually installed in `/opt/boa/whisper/models/`. Size and installation state are shown. Larger models need more memory and CPU time.
3. For an API, save its key under **API keys** first. OpenAI, Groq, Mistral, Together AI, Hugging Face and Cloudflare appear when a key is saved. Choose a suggestion or enter another transcription model identifier from that provider. Cloudflare offers its two supported Whisper variants and uses an `account-id:api-token` credential.
4. Choose the language (`auto` or a code such as `en`), maximum duration and whether to keep audio for playback; click **Save**. Reply to an agent's Telegram message with a voice note to try it. You can also select the agent first with `/agents`.

The initial limit is 600 seconds, configurable from 30 to 3600; the received file cannot exceed 20 MiB. Processing happens in the background and its queue survives an update. A busy agent receives the saved text when available. An agent name spoken inside the recording does not change its destination.

The web chat displays the transcript and, when retention is enabled, a player. An Ogg playback copy is kept behind login. Disabling retention keeps only the text for new messages. Clearing a chat removes saved audio from completed jobs. Backups include that audio; downloaded models survive updates but are not backed up. After restoring onto another machine, download any missing additional model from Audio.

Local recognition processes audio on your server. API recognition sends it to the selected provider and can incur charges separate from the agent's model usage. A local failure never switches to a cloud provider automatically. Whisper transcribes rather than translating; `.en` models understand English only. Audio intake is through Telegram; the web chat displays the result without adding a recording button.

For an existing installation, run your distribution's installer as root with `--update`. It installs FFmpeg, whisper.cpp and the base model under `/opt/boa/whisper/`; transcription remains disabled until configured.

### Languages

The interface ships in fourteen:

| | | |
|---|---|---|
| Deutsch (Deutschland) | English (United Kingdom) | English (United States) |
| Español (Argentina) | Español (España) | Français (France) |
| हिन्दी (भारत) | Italiano (Italia) | 日本語 (日本) |
| 한국어 (대한민국) | Português (Brasil) | Português (Portugal) |
| Русский (Россия) | 简体中文 (中国) | |

**Settings → Interface → Language** picks one, and it is kept in your browser,
like the theme. A browser that has never chosen gets the closest match to what
it asks for, and English when there is none.

Two other things follow the language and are **not** a browser preference,
because a run started by cron has no browser:

- **Settings → Agents → Language agents answer in** adds one line to every
  agent's system prompt, written in that language.
- The **Telegram and Discord bots** speak it too: their own sentences, the
  `/status` report
  and the help text.

## Pop-up messages

When something is saved, the confirmation appears in the middle of the panel
you are looking at and then goes on its own. It is deliberately in the way:
the Save button at the bottom of a long tab used to produce a line at the very
top of the page, several screens above where you were looking, so saving
looked like it had done nothing at all.

**Settings → Interface → Seconds a pop-up message stays on screen** sets how
long, between 1 and 30 seconds. Three is the default: long enough to read
`Settings saved`, short enough not to sit on top of the box you were about
to type in.

Error messages ignore that number. They stay until you close them, with the
`×` or with Escape, because an error is the one message that has to still be
there when you look back at the screen.

The colour says which of three things happened:

| Colour | What it means |
|---|---|
| Green | It was saved |
| Amber | **No changes to save** - you pressed Save and nothing on the form had changed |
| Red | It failed. Says what went wrong, and waits to be closed |

The amber one applies everywhere you can press Save: **Settings** - the
account, the mail server, the API keys, the channels and the browser
preferences - and an agent's own settings. Pressing Save twice tells you so
the second time, instead of reporting a save that did not happen. A brand new
agent is the exception: its form is holding the example's values and has never
been saved, so Save writes them and takes you to its chat.

## Themes

**Settings → Interface** picks the palette:

| Theme | What it is |
|---|---|
| **Day** | Soft greys with lighter cards, for a lit room |
| **Night** | The dark palette, for a dark room |
| **Day High Contrast** | White ground, near-black text, hard borders. Nothing is filled with the accent here: an agent's box in the sidebar is an outline, and your own message is filled with a softened ink instead of blue |
| **Night High Contrast** | Near-black ground, bright text and hard borders. The selected agent has a grey fill; selected tabs have a closed outline joined to the line below. Your own messages use dimmed white |

A browser that has never chosen starts on whichever of Day and Night matches
the operating system, and follows it until somebody picks one. After that the
choice is stored in this browser, like the language, so a phone and a desktop
do not have to agree.

A theme is one CSS file in `frontend/themes/` on the server that redefines the
`--colour-*` variables. Dropping a file in there adds a theme - there is no
list in the code to update. Its name and description come from the comment at
the top of the file:

```css
/*
name: Midnight
scheme: dark
description: What it looks like, in one line.
*/

:root {
  color-scheme: dark;
  --colour-page: #101014;
  /* ... every --colour-* app.css defines ... */
}
```

Define all of them. A variable a theme leaves out keeps the value from
app.css - which, on a light theme, means one colour from the dark palette left
sitting in the middle of it.

Every theme that ships here clears 4.5:1 contrast for every colour it paints
text in, and the two high-contrast ones clear 7:1 - WCAG AAA. There is a test
that fails if one stops doing so, held to whichever bar its name claims. A theme added by
hand is not held to that, but the same question applies to it: a service marked
down in a red nobody can read is a service nobody notices.

## When a card runs

Assigning a card is how you give an agent work, and it is a **buzzer** service
that turns that into a run:

    every few seconds:
      cards with an owner, a time that has passed and no buzz yet
        -> start that agent, unless it is already running
        -> record the buzz on the card

**When** on the add-card form decides the time:

| Choice | What happens |
|---|---|
| **Immediately** | The agent is woken as soon as the card is saved. The default: assigning a card is asking for the work |
| **When the agent wakes up** | The card waits on the board. Nobody is woken; the agent finds it on its next run of its own |
| **Schedule for a given time** | A time in UTC. The agent is woken then |

An agent that is already working is not interrupted. The card keeps its turn
and is tried again on the next pass, so a run scheduled against a busy agent
starts seconds late rather than not at all, and one agent never has two runs at
once. A card is buzzed once: to run it again, set its time again.

### The card shows up in the agent's chat

When the run starts, the agent's chat gets a message naming the card:

    You have been assigned a task on a card:

    Card id: 1284
    Title: Renew the certificates
    What the task is: "Run the installer with --update and report"
    To run: Immediately

If another agent handed the card over, the first line says who: *manager has
assigned you a new card*. If the card was scheduled rather than asked for
straight away, the last line shows the time instead: `a2026m03d31@13:45`, in
UTC, the same time the board shows on the card.

The message is written **when the run starts**, never before. A card you
schedule for tonight and delete this afternoon leaves nothing in the chat,
because nothing ever ran.

The agent answers under it like any other message, with what the run cost.
Three things can put a line there without the agent having done anything, and
each says which it was: the agent was switched off, it had already used up its
runs for the day, or the run could not be started at all. None of them is
silent, because a card that was announced and then ignored looks exactly like
an agent that is not working.

One thing this run does not do is read the conversation. Its instructions are
the card. What you said in the chat earlier is replayed only when you send a
message yourself - otherwise every scheduled run would be charged for a
conversation nobody is having.

A card handed to **manager** is treated differently: it is told to decide who
should do the work and pass the card on with `kanban.assign_card`. The card
keeps its id, its instructions and its history and changes hands, and the agent
it lands on is woken for it. That is delegation - not a second card for the
same job.

## Channels

Under **Settings → Channels**, configure where agents can write:

| Channel | What it needs |
|---|---|
| Discord | a `bot_token` and a `channel_id` to talk both ways, or a webhook URL to only send |
| Mattermost | an incoming webhook URL |
| Telegram | `bot_token` from BotFather, and `chat_id` |
| X | a `bearer_token` |

Each configured channel shows **Configured** in green, using the same colour
as a stored API key. Channels without configuration keep their neutral status.

Credentials are stored so that **no agent can read them**. An agent asks the
server to send; the server reads the token and sends. The message arrives
prefixed with the agent's name, added by the server, so no agent can pretend to
be another.

Then, in each agent's **Channels** tab, tick which channels it may use. It needs both
`channel.write` and the channel itself.

### Answering an agent from Telegram

Telegram and Discord are the two channels that also work the other way. Tick **Let me answer
agents from Telegram** under its settings, save, and you can write back.

The bot has three tools in its menu, and they are what the `/` button offers:

| Command | What it does |
|---|---|
| `/agents` | Lists your agents as buttons. Tap one to start talking to it |
| `/status` | Services, board and every agent with its model, tools and skills |
| `/help` | The three of these, and the two other ways to reach an agent |

### Nobody else sees any of it

The bot's username is public - anybody who finds it can open it - so the menu
is written **only for your chat**. Someone else who opens the same bot sees an
empty chat: no commands under `/`, no description, nothing to press but the
Start button, which Telegram draws in every bot and no API can remove.

Pressing it does nothing. The listener compares the `chat_id` of every message
with the one in your settings and drops what does not match, before any command
runs and before any agent is chosen.

**And nothing is written down.** No answer, no line in the log, no record that
anybody wrote at all. The id of a chat that is not yours is somebody else's
data, and keeping it would mean your installation quietly building a list of
who has found the bot.

The price is that a `chat_id` set wrongly looks exactly like a stranger: your
own messages are dropped in silence. The configured one is written to the log
on every start, which is what there is to compare against:

```bash
journalctl -u boa-telegram | grep "Registered"
```

The filter is per **chat**, not per person. If the `chat_id` you configured is
a group, every member of that group can talk to your agents.

### Picking who you are talking to

Tap `/agents`, tap an agent, and it answers:

```
Agente os-watcher:

Envíame tus instrucciones...
```

From then on **anything you write goes to that agent** until you pick another
one. You can ask four questions in a row without naming anybody, which is what
makes it a conversation rather than a command line.

Three ways to be addressed to somebody, in this order:

1. **Replying to something an agent said** goes to that agent, whatever else is
   selected. Swipe its message, write, send.
2. **Naming one** - `@os-watcher check the disk` - goes to it *and* makes it the
   selected one. `@001` works too, and so does a name with a space in it:
   `@News Miner what is new` is one agent, not two words.
3. **Neither** goes to whoever you picked last.

Nothing else changes the selection, so an agent never inherits your
conversation by being the one that happened to speak last. An agent you delete
stops being selected rather than going on catching everything.

Until you have picked anybody, a message that names nobody gets the list of
agents back, so nothing ever disappears without an explanation.

### What comes back

The agent answers in Telegram as a reply to what you wrote, with its name on
the first line:

```
os-watcher:
25G free of 28G on /, unchanged since yesterday.
```

**And the whole exchange is in that agent's chat in the web interface**, your
question and its answer, with `(via Telegram)` next to the time on what you
sent. One screen still shows everything the agent was asked and everything it
said, whichever device each half was typed on.

Two things to expect:

- **A busy agent says so.** If it is already answering something, you are told
  to try again in a moment rather than being put in a queue - a queue would
  hide that an agent is falling behind.
- **Only your chat is listened to.** A bot's username is public and anybody who
  finds it can write to it. Messages from any other chat are dropped without an
  answer, so the `chat_id` you configured is what decides who can talk to your
  agents. Get it wrong and nothing happens at all.

It is long polling, not a webhook: the server connects out to Telegram, so
nothing has to be opened to the internet for this to work.

If Telegram will not take the answer - you blocked the bot, the chat id
changed, the token stopped being valid - it is dropped from Telegram at once,
and if Telegram cannot be reached for an hour it is dropped too. It is never
lost: the whole conversation, that answer included, is in the agent's chat in
the web interface.

### What an agent's message looks like

Models write markdown, and Telegram renders a small subset of HTML, so the two
are translated on the way out. What arrives is formatted, not asterisks:

| What the agent writes | What you see on your phone |
|---|---|
| `**25G free**` | **25G free** |
| `` `df -h` `` | `df -h` in monospace |
| `# Disk report` | a bold line |
| `- item` | • item |
| a table | a monospaced block, columns lined up |
| ```` ```bash ```` | a code block |
| `[text](https://…)` | a link |

Telegram has no heading, list or table of its own, which is why those three
become the nearest readable thing rather than disappearing.

If Telegram ever refuses the formatting, **the message is sent again as plain
text rather than being lost**. You get the words either way; the server log
says what happened, so a formatting bug shows up instead of degrading quietly
for ever.

Everything the bot says itself - the agent list, "still answering something
else", `/status` - is in the language set under **Settings → Agents**, the same
one the agents answer in.

## Answering an agent from Discord

Discord works the same way as Telegram, with a bot of your own. Five minutes
of setting up, once.

### Making the bot

1. Open <https://discord.com/developers/applications> and press **New
   Application**. Name it whatever you like.
2. **Bot** in the sidebar, then **Reset Token**, and copy what it shows you.
   That is the `bot_token`, and it is shown once.
3. **OAuth2 → URL Generator**: tick **bot**, and under it **View Channels**,
   **Send Messages** and **Read Message History**. Open the URL it builds and
   add the bot to your server.
4. In Discord itself, turn on **Settings → Advanced → Developer Mode**, then
   right-click the channel you want the agents in and **Copy Channel ID**.
   That is the `channel_id`.

Nothing else is needed. In particular you do **not** need the Message Content
Intent: that switch is for the Gateway, and this reads the channel over the
ordinary API.

### Switching it on

Under **Settings → Channels → Discord**, fill in the token and the channel id,
tick **Let me answer agents from Discord**, and save. Within a few seconds the
log says which bot is listening and where:

```bash
journalctl -u boa-discord | grep "Listening"      # Debian
tail /opt/boa/logs/boa-discord.log                # Alpine
```

Messages written before you switched it on are not answered: the first pass
notes where the channel is and starts from there.

### Talking to an agent

| Command | What it does |
|---|---|
| `!agents` | Lists your agents and what to type to reach each one |
| `!status` | Services, board and every agent with its model, tools and skills |
| `!help` | The three of these, and the other ways to reach an agent |

`/agents` works too, if that is what your fingers type. There are no buttons
and no slash-command menu here: both of those are *interactions*, which
Discord only delivers over a connection this installation deliberately does
not open.

The three ways to address somebody are the ones you already know:

1. **Replying to something an agent said** goes to that agent, whatever else
   is selected. Right-click its message → Reply, or swipe it on a phone.
2. **Naming one** - `@os-watcher check the disk` - goes to it *and* makes it
   the selected one. `!os-watcher`, `@001` and `@News Miner what is new` all
   work.
3. **Neither** goes to whoever you picked last.

### What comes back

The answer arrives as a reply to your question, with the agent's name in bold
on the first line, and **the whole exchange is in that agent's chat in the web
interface** with `(via Discord)` next to the time on what you sent.

A long answer arrives as several messages rather than one cut short: Discord
refuses anything over 2000 characters, so an answer is split between lines,
into at most four messages. You can reply to any of them and it reaches the
same agent. If there was more than four messages' worth, the last one ends in
`…` - and the whole of it is in the web interface, where it was written.

### Who can talk to your agents

**Everyone who can write in that channel.** This is the one real difference
from Telegram, and it is worth a minute of your time: there the bot compares
the chat id of every message and drops what does not match, so a stranger who
finds your bot gets nothing. Here the bot reads one channel, and anybody who
can post in it can start runs on your server.

So put the agents in a **private channel** - one only you, or you and the
people you trust, can see. The bot needs no access to anything else.

### If you only want alerts

Leave the token empty and set a **webhook URL** instead: **Channel Settings →
Integrations → Webhooks → New Webhook → Copy Webhook URL**. Agents can then
write to the channel and that is all. Listening needs the bot, so the switch
is refused over a webhook rather than doing nothing.

## The orchestrator

`agent-000`, called **manager**, is the one agent created at install time. It is a normal
agent in every respect except that it cannot be deleted.

The intended pattern: give the manager the kanban tools and a prompt telling it
to break goals into cards and assign them to other agents by id. Give the other
agents `bash.run` and whatever else they need, and a prompt telling them to
work on the cards assigned to them.

It only works if the manager's cards say what "done" means. A card that does
not is a wish, and the agent picking it up will decide for itself.

## The tools tab

**Settings → Tools** shows what is installed on the server. Each family is a
subtab - Automation, Browser, Channels, Email, Kanban, Memory, Operating system,
Web - with the number of tools in it, and
each tool gets its box with its arguments and what they mean. The open tab is
in the URL (`/settings/?tab=tools&family=mail`), so a reload or a bookmark keeps it.
Old `/tools/` links redirect here and keep the selected family.

A tool whose family nobody has named - a `.py` somebody dropped into
`/opt/boa/tools/` - goes into **Others**, with its family written on its own
box. It is still a tool all the way to the interface; it just does not earn a
tab of its own, or the row would grow with every one-off script.

Which agent may use which tool is set on each agent's own **Tools** tab, not
here.

## The API documentation

**API documentation** in the sidebar lists every endpoint under `/api/`,
grouped by area, with its parameters and what it answers. It is generated from
this installation's own OpenAPI description, so it cannot drift from the code:
`openapi.json`, linked at the top, is the same thing as a file you can hand to
a client generator.

It is in the language you chose in **Settings → Interface**, like the rest of
the interface. The specification itself stays in English: field names, ids and
error strings are English everywhere in this project, and a translated
`openapi.json` would describe an API that does not exist.

The request bodies are shown as coloured JSON, the way an editor shows them:
field names in one colour, values in another, and the braces and commas dimmed
because they are scaffolding. The colours come from the theme you chose, and
copying a block still gives you valid JSON.

The page is also readable without logging in, on its own without the sidebar.
It describes the shape of the API, not any of your data.

## Work that does not need the agent to think

Some work is recurring and mechanical: check a certificate, rotate a log,
collect a number. Waking an agent up for that costs tokens every time, to
reach a conclusion a shell script reaches for nothing.

So an agent can write scripts for itself and schedule them. Give it the
**Automation** tools and it can:

1. `script.write` — put a shell script in its own `scripts/` directory.
2. `cron.add` — run it on a schedule, in its own crontab.
3. Read the results on its next run, and decide what they mean.

The script runs as that agent's Linux user, with the same permissions the
agent has, and **it costs no tokens at all** - it is a shell script, not a
model call. What costs tokens is the agent reading the output afterwards and
deciding what to do about it.

What it may not do:

- Schedule anything but its own scripts. A free-form command in a crontab is
  something nobody can review afterwards.
- Run more often than every 5 minutes. A job every minute is not a schedule.
- Touch the line that wakes it up. That one is yours, on its **Cron** tab.

You see both halves: the scripts in its home, and the lines that run them on
the Cron tab alongside your own.

## Where a run's report ends up

A run you start from the chat answers you there. A run started by a card that
came due answers in the same place. A run started by the agent's **own
crontab** answers nowhere in particular - nobody asked it anything - so:

- **Always in History**, under **Last runs**: what each run said, with what it
  cost. This is where to look when you wonder what an agent has been doing.
- **In the chat as well, when it is worth interrupting you**: the run did not
  finish, or it changed something you would see - a card, a channel message, a
  mailbox. A run that only looked at things stays in History. An agent on an
  hourly crontab would otherwise post twelve "nothing to report" messages a
  day into the conversation.

Those messages say above them that nobody asked for them, and they are never
replayed to the model, so they cost nothing on your next message.

**A run that never started is in History too**, marked "did not start". Press
**Run now** on an agent whose API key is not set yet, or while the agent is
already running, and the line in History tells you which of the two it was.
Before, the screen said the run had started and nothing else ever appeared,
because the reason was written to a place nothing reads. A run that did not
start does not count towards the agent's runs for the day, and is not counted
as a failure of the agent either: nothing of it ran.

## The status bar

The strip along the bottom of every page, running the full width of the window
under the sidebar as well, is about the installation as a whole:

- **executor** and **agent API**, green when running. If either is red, agents
  will not run and nothing else in the interface will tell you.
- **agents**: how many are switched on out of how many exist.
- **board**: cards in each column.
- **tokens today**: everything spent since midnight UTC, across every agent,
  and how many runs it took. This is the number that shows an agent has gone
  into a loop before the invoice does.

At the right end of the strip, the GitHub mark and the name **nipegun** open
the project repository, <https://github.com/nipegun/bunch-of-aigents>, in a new
tab. The account you signed in with is not shown: an installation only ever has
one, so printing it says nothing you did not already know.

## What language your agents answer in

Write each agent's prompt in whatever language you think in and it will answer
in that one. That covers the chat. It does not cover a run started by the
agent's own crontab: nobody wrote to it in any language, and the shipped
prompts are in English - so an installation running in Spanish was getting its
scheduled reports in English.

**Settings → Agents → Language agents answer in** fixes that for every agent
at once. It adds one line to each agent's system prompt, written in the
language it asks for, saying that it overrides whatever the prompt says about
languages. Leave it on the default and nothing changes: each agent answers in
the language of its own prompt.

It is kept on the server, unlike the language of this interface, which is a
preference in your browser. A run woken by cron has no browser.

## Writing prompts in your own language

Write the system prompt in whatever language you think in. Nothing in the
system is tied to English: the prompt, the memory, the chat, the card titles
and the messages between the services are all UTF-8 from end to end, accents
and all.

The default prompt a new agent gets is in English, and its last rule tells the
agent to answer in the language its prompt is written in. Rewrite the whole
thing in your language and that rule goes with it - the agent will follow the
prompt it has, not the one it started with.

Prompts are stored with whole lines, not wrapped at a fixed column. The text
box wraps them on screen so they stay readable, without putting the line breaks
into the file: a rule that is one sentence stays one line, and editing it does
not mean rewrapping a paragraph.

## Backing up and restoring

Everything that makes this installation yours lives under `/opt/boa/` and in
the agents' Linux users. One command gathers it into one archive:

```bash
./install-update-reinstall-debian.sh --backup
```

It writes `/root/boa-backup-<date>.tar.gz`, `root` only, mode 0600, with the
services running - nothing stops. Pass a path to write it somewhere else:
`--backup /mnt/usb/boa.tar.gz`. Inside: both databases, copied through
SQLite's own backup API so nothing still sitting in a write-ahead log is
missed; the provider keys, the channel secrets and the session secret; the
certificates; every agent with its home, its protected files, its Linux user
and its crontab; the skills and tools written on this server; and the
installation log, for the password in it. Not inside: the code, the Python
environment, the browser, and this machine's own two choices - the port mode
and whether it has a browser.

**Keep it as private as the machine.** It holds every API key, every channel
token and the login password.

To restore, on this machine or on a new one:

```bash
./install-update-reinstall-debian.sh --install       # on a new machine only
./install-update-reinstall-debian.sh --restore /root/boa-backup-<date>.tar.gz
```

It asks for a YES, or takes `--yes`. Then it stops the services, creates the
agent users again with the same names, and the same ids when they are free,
replaces the databases, the keys, the certificates, the agents, the skills and
the tools with the archive's, installs the crontabs, and starts everything.
Log in with the email and password of the backup: both are appended to
`/opt/boa/logs/install.log` under the heading `Credentials of the restored
backup`, and the backup's whole log is kept beside it as
`install.log.restored-<date>`.

An agent this machine had and the backup does not keeps its home on disk and
disappears from the interface, because the list of agents is in the restored
database. On Alpine it is the same two flags on
`install-update-reinstall-alpine.sh`.

## When something does not work

**I chose `--ports direct` and the machine's HAProxy is gone.** It is not
gone, it is retired: stopped, out of every runlevel on Alpine, disabled and
masked on Debian, and its `/etc/haproxy/haproxy.cfg` deleted if the installer
had written it, or kept as `haproxy.cfg.before-boa.<date>` if you had. In this
mode the application binds 80 and 443 itself, and anything else holding those
ports keeps it from starting at all - a proxy left enabled would take them at
the next boot, before the application ever runs. The `haproxy` package is
still installed on purpose: `boa-proxy` is `/usr/sbin/haproxy`, and in this
mode it is what serves 80 and 443.

To go back, run the installer with `--update --ports proxied`: it unmasks the
unit, writes the machine configuration again and starts it. Your old file, if
there was one, is still beside it under its `before-boa` name.

**`boa-proxy` restarts over and over and nothing listens on 11443.** Read
`/opt/boa/logs/boa-proxy.log`. If it says `Cannot raise FD limit to 4131`,
this machine's hard limit on file descriptors is lower than what the proxy
asked for - a small container, usually. An installation made before this was
fixed still has `maxconn 2048` in `/opt/boa/config/haproxy.cfg`. Running the
installer with `--update` rewrites the file; to fix it on the spot:

```bash
sed -i 's/^  maxconn 2048$/  fd-hard-limit 4000/' /opt/boa/config/haproxy.cfg
rc-service boa-proxy restart        # systemctl restart boa-proxy on Debian
```

HAProxy then sizes itself from the descriptors it can actually have, which on
a hard limit of 4096 is about 1987 connections - far more than this ever
needs.

**The installer ends with "Everything is in place but the application does not
answer".** The installation is there and a page never came back. The log
already holds the reason:

```bash
sed -n '/Why it did not answer/,$p' /opt/boa/logs/install.log
```

That block is what the machine looked like at that moment: what curl made of
the request, whether anything is listening on the port, the state of all six
services, and the last lines of what the proxy and the web application
printed. `000` is not an HTTP code - it is curl saying it never got one. A
service that calls itself `started` next to `nothing is listening on port
11443` is a process that dies and is restarted every few seconds, and its own
log, a few lines below, says why.

An update that failed here has already put the previous version back and is
running it. A first install has nothing to go back to, so it leaves everything
in place: fix what the block names and run the installer again with
`--update`.

**The installer stops with "systemd is not running".** It is refusing to
install onto a machine where systemd is not PID 1, because every service it
writes is a systemd unit and there would be nothing to start them. A normal
Debian is fine; a container is not, unless it was created to run systemd:

```bash
apt-get install -y systemd systemd-sysv dbus dbus-user-session
```

and then create the container again with `/sbin/init` as its command - a
container that is already running cannot change its PID 1. On Alpine this does
not come up: that installer adds OpenRC itself when the machine has none.

**Nothing happens when I press Run now.** Look at the two dots at the bottom of
the sidebar. If `executor` is red:

```bash
systemctl status boa-exec
journalctl -u boa-exec -n 50
```


**The browser shows 503 and the services are all running.** The machine's
HAProxy has marked the backend down. Almost always this is `option
ssl-hello-chk` on that backend: its ClientHello predates TLS 1.2 and the
application requires it. Remove that line and reload HAProxy.

**An agent runs but does nothing.** Check its History panel. Then run it by
hand and watch:

```bash
runuser -u agent-001 -- /opt/boa/venv/bin/python3 \
  /opt/boa/webapp/backend/core/runner.py --agent-id 001
```

Add `--dry-run` to see what it would load — provider, tools, ceilings —
without calling the model.

**It says it cannot reach the model.** For self-hosted providers, check that
the server is up and the base URL is right. For cloud ones, check that the key
file exists in the agent's home and is owned by that agent.

**It says a tool is not available to it.** The tool is not ticked on that
agent's page. The prompt cannot override that, which is the point.

**Cards stopped appearing.** Either the kanban checkbox is unticked for that
agent, or `agent API` is red at the bottom of the sidebar:

```bash
systemctl status boa-agent-api
```

**I want to see everything an agent did.** Its journal is in its own home:

```bash
cat /opt/boa/agents/001/runs.jsonl
```

One JSON object per line: when it ran, what it spent, whether it finished.
