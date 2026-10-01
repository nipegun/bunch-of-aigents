# Bunch of AIgents (BoA)

Dieses README gibt es auch auf:\
[en-GB](README.en-GB.md), [en-US](README.md), [es-AR](README.es-AR.md), [es-ES](README.es-ES.md), [fr-FR](README.fr-FR.md), [he-IL](README.he-IL.md), [hi-IN](README.hi-IN.md), [it-IT](README.it-IT.md), [ja-JP](README.ja-JP.md), [ko-KR](README.ko-KR.md), [pt-BR](README.pt-BR.md), [pt-PT](README.pt-PT.md), [ru-RU](README.ru-RU.md), [zh-CN](README.zh-CN.md)

## Was ist das

Selbst gehostete KI-Agenten, die als eigene Benutzer auf einem GNU/Linux-Server (Debian oder Alpine) laufen.

Jeder Agent hat für sich allein:

- Home-Verzeichnis
- Crontab
- Shell-Zugang
- Samba-Freigabe
- RAG (falls nötig)
- Usw.

Du erreichst sie direkt in der Web-App oder über Telegram oder Discord.

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

- [doc/MANUAL.de-DE.md](doc/MANUAL.de-DE.md), um zu lernen, wie du es installierst, einrichtest und benutzt.
- [doc/CODE.de-DE.md](doc/CODE.de-DE.md), um zu verstehen, wie es aufgebaut ist (für Entwickler und für KI-Modelle).

## Dieses Projekt sponsern

- **Beauftrage mich.** Personen und Unternehmen können mich beauftragen, neue Funktionen hinzuzufügen: [schreib mir](mailto:nipegun@gmail.com?subject=About%20the%20BoA%20repo).
- **Spendier mir einen Kaffee:** [buymeacoffee.com/nipegun](https://buymeacoffee.com/nipegun).
- **GitHub Sponsors.** Du kannst das Projekt auch auf GitHub finanziell unterstützen: [github.com/sponsors/nipegun](https://github.com/sponsors/nipegun).
