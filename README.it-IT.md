# Bunch of AIgents (BoA)

Questo README è disponibile anche in:\
[de-DE](README.de-DE.md), [en-GB](README.en-GB.md), [en-US](README.md), [es-AR](README.es-AR.md), [es-ES](README.es-ES.md), [fr-FR](README.fr-FR.md), [he-IL](README.he-IL.md), [hi-IN](README.hi-IN.md), [ja-JP](README.ja-JP.md), [ko-KR](README.ko-KR.md), [pt-BR](README.pt-BR.md), [pt-PT](README.pt-PT.md), [ru-RU](README.ru-RU.md), [zh-CN](README.zh-CN.md)

## Che cos'è

Agenti di IA self-hosted che girano come utenti distinti su un server GNU/Linux (Debian o Alpine).

Ogni agente ha, tutto per sé:

- Directory home
- Crontab
- Accesso alla shell
- Condivisione Samba
- RAG (se serve)
- Ecc.

Puoi raggiungerli direttamente dall'applicazione web o tramite Telegram o Discord.

## Screenshot

![Interfaccia di Bunch of AIgents](https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/doc/screenshot.png)

## Installazione

Eseguilo come `root`.

**Debian** (con systemd come PID 1):

```bash
curl -fsSL https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-debian.sh \
  | bash -s -- --install --email you@example.com
```

**Alpine Linux**:

```bash
wget -qO- https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-alpine.sh \
  | sh -s -- --install --email you@example.com
```

> **Alpine non ha Playwright.** Playwright non pubblica alcuna build per musl,
> quindi su Alpine gli agenti non hanno un browser: gli strumenti `browser.*` lo
> dicono quando un agente ne chiama uno. Tutto il resto funziona come su Debian.

## Leggi la documentazione

Esplora:

- [doc/MANUAL.it-IT.md](doc/MANUAL.it-IT.md) per imparare a installarlo, configurarlo e usarlo.
- [doc/CODE.it-IT.md](doc/CODE.it-IT.md) per capire come è costruito (per sviluppatori e per modelli di IA).

## Sponsorizza questo progetto

- **Lavoro su commissione.** Persone e aziende possono incaricarmi di aggiungere nuove funzionalità: [scrivimi](mailto:nipegun@gmail.com?subject=About%20the%20BoA%20repo).
- **Offrimi un caffè:** [buymeacoffee.com/nipegun](https://buymeacoffee.com/nipegun).
- **GitHub Sponsors.** Puoi anche sostenere economicamente il progetto su GitHub: [github.com/sponsors/nipegun](https://github.com/sponsors/nipegun).
