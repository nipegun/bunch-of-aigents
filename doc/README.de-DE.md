# Bunch of AIgents (BoA)

Dieses README gibt es auch auf:\
[en-GB](README.en-GB.md), [en-US](../README.md), [es-AR](README.es-AR.md), [es-ES](README.es-ES.md), [fr-FR](README.fr-FR.md), [he-IL](README.he-IL.md), [hi-IN](README.hi-IN.md), [it-IT](README.it-IT.md), [ja-JP](README.ja-JP.md), [ko-KR](README.ko-KR.md), [pt-BR](README.pt-BR.md), [pt-PT](README.pt-PT.md), [ru-RU](README.ru-RU.md), [zh-CN](README.zh-CN.md)

## Was ist das

Selbst gehostete KI-Agenten, die als eigene Benutzer auf einem GNU/Linux-Server (Debian oder Alpine) laufen.

Jeder Agent hat für sich allein:

- Home-Verzeichnis
- Crontab
- Shell-Zugang
- Samba-Freigabe
- RAG (falls nötig)
- Usw.

Du erreichst sie direkt in der Web-App oder über Telegram, Discord, Slack, Mattermost oder X-Direktnachrichten.

## Screenshots

![Oberfläche von Bunch of AIgents](https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/doc/screenshot.png)

## Installation

Führe es als `root` aus.

**Debian** (mit systemd als PID 1):

```bash
curl -fsSL https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-debian.sh \
  | bash -s -- --install --email you@example.com
```

**Alpine Linux**:

```bash
wget -qO- https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-alpine.sh \
  | sh -s -- --install --email you@example.com
```

> **Alpine hat kein Playwright.** Playwright veröffentlicht keinen Build für
> musl, daher haben die Agenten auf Alpine keinen Browser: Die Werkzeuge
> `browser.*` sagen das, wenn ein Agent eines aufruft. Alles andere funktioniert
> wie auf Debian.

## Die Dokumentation lesen

Mehr dazu:

- [doc/MANUAL.de-DE.md](MANUAL.de-DE.md), um zu lernen, wie du es installierst, einrichtest und benutzt.
- [doc/CODE.de-DE.md](CODE.de-DE.md), um zu verstehen, wie es aufgebaut ist (für Entwickler und für KI-Modelle).
- Kanäle einrichten: [Telegram](MANUAL.de-DE.md#telegram), [Discord](MANUAL.de-DE.md#discord-setup), [Slack](MANUAL.de-DE.md#slack), [Mattermost](MANUAL.de-DE.md#mattermost), [X](MANUAL.de-DE.md#x).

## Dieses Projekt sponsern

- **[Beauftrage mich](mailto:nipegun@gmail.com?subject=I%20want%20new%20BoA%20features%21)**, um neue Funktionen hinzuzufügen.
- **GitHub Sponsors.** Du kannst das Projekt auch auf GitHub finanziell unterstützen: [github.com/sponsors/nipegun](https://github.com/sponsors/nipegun).
