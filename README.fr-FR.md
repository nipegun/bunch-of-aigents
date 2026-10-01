# Bunch of AIgents (BoA)

Ce README est aussi disponible en :\
[de-DE](README.de-DE.md), [en-GB](README.en-GB.md), [en-US](README.md), [es-AR](README.es-AR.md), [es-ES](README.es-ES.md), [he-IL](README.he-IL.md), [hi-IN](README.hi-IN.md), [it-IT](README.it-IT.md), [ja-JP](README.ja-JP.md), [ko-KR](README.ko-KR.md), [pt-BR](README.pt-BR.md), [pt-PT](README.pt-PT.md), [ru-RU](README.ru-RU.md), [zh-CN](README.zh-CN.md)

## Qu'est-ce que c'est

Des agents d'IA auto-hébergés, chacun exécuté comme un utilisateur à part sur un serveur GNU/Linux (Debian ou Alpine).

Chaque agent a, rien que pour lui :

- Un répertoire personnel
- Une crontab
- Un accès au shell
- Un partage Samba
- Un RAG (si besoin)
- Etc.

Vous pouvez y accéder directement depuis l'application web ou via Telegram ou Discord.

## Captures d'écran

![Interface de Bunch of AIgents](https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/doc/screenshot.png)

## Installation

Exécutez-le en tant que `root`.

**Debian** (avec systemd comme PID 1) :

```bash
curl -fsSL https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-debian.sh \
  | bash -s -- --install --email you@example.com
```

**Alpine Linux** :

```bash
wget -qO- https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-alpine.sh \
  | sh -s -- --install --email you@example.com
```

> **Alpine n'a pas Playwright.** Playwright ne publie aucune version pour musl,
> donc sous Alpine les agents n'ont pas de navigateur : les outils `browser.*`
> le signalent quand un agent en appelle un. Tout le reste fonctionne comme sous
> Debian.

## Lire la documentation

À explorer :

- [doc/MANUAL.fr-FR.md](doc/MANUAL.fr-FR.md) pour apprendre à l'installer, le configurer et l'utiliser.
- [doc/CODE.fr-FR.md](doc/CODE.fr-FR.md) pour comprendre comment il est construit (pour les développeurs et pour les modèles d'IA).

## Sponsoriser ce projet

- **Engagez-moi.** Particuliers et entreprises peuvent m'engager pour ajouter de nouvelles fonctionnalités : [écrivez-moi](mailto:nipegun@gmail.com?subject=About%20the%20BoA%20repo).
- **Offrez-moi un café :** [buymeacoffee.com/nipegun](https://buymeacoffee.com/nipegun).
- **GitHub Sponsors.** Vous pouvez aussi soutenir financièrement le projet sur GitHub : [github.com/sponsors/nipegun](https://github.com/sponsors/nipegun).
