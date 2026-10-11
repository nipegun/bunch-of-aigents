# Bunch of AIgents (BoA)

This README is also available in:\
[de-DE](README.de-DE.md), [en-US](../README.md), [es-AR](README.es-AR.md), [es-ES](README.es-ES.md), [fr-FR](README.fr-FR.md), [he-IL](README.he-IL.md), [hi-IN](README.hi-IN.md), [it-IT](README.it-IT.md), [ja-JP](README.ja-JP.md), [ko-KR](README.ko-KR.md), [pt-BR](README.pt-BR.md), [pt-PT](README.pt-PT.md), [ru-RU](README.ru-RU.md), [zh-CN](README.zh-CN.md)

## What is it

Self-hosted AI agents that run as individual users on a GNU/Linux server (Debian or Alpine).

Each agent has its own:

- Home directory
- Crontab
- Shell access
- Samba share
- RAG (if needed)
- Etc.

You can reach them directly in the web app or via Telegram, Discord, Slack, Mattermost or X direct messages.

## Screenshots

![Bunch of AIgents interface](https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/doc/screenshot.png)

## Install

Run it as `root`.

**Debian** (with systemd as PID 1):

```bash
curl -fsSL https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-debian.sh \
  | bash -s -- --install --email you@example.com
```

**Alpine Linux**:

```bash
wget -qO- https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-alpine.sh \
  | sh -s -- --install --email you@example.com
```

> **Alpine has no Playwright.** Playwright publishes no build for musl, so on
> Alpine the agents have no browser: the `browser.*` tools say so when an agent
> calls one. Everything else works as it does on Debian.

## Read the documentation

Explore:

- [doc/MANUAL.en-GB.md](MANUAL.en-GB.md) to learn how to install it, set it up and use it.
- [doc/CODE.en-GB.md](CODE.en-GB.md) to understand how it is built (for developers and for AI models).
- Channel setup: [Telegram](MANUAL.en-GB.md#telegram), [Discord](MANUAL.en-GB.md#discord-setup), [Slack](MANUAL.en-GB.md#slack), [Mattermost](MANUAL.en-GB.md#mattermost), [X](MANUAL.en-GB.md#x).

## Sponsor this project

- **[Hire me](mailto:nipegun@gmail.com?subject=I%20want%20new%20BoA%20features%21)** to add new features.
- **GitHub Sponsors.** You can also support the project financially on GitHub: [github.com/sponsors/nipegun](https://github.com/sponsors/nipegun).
