# Bunch of AIgents (BoA)

Este README também está disponível em:\
[de-DE](README.de-DE.md), [en-GB](README.en-GB.md), [en-US](README.md), [es-AR](README.es-AR.md), [es-ES](README.es-ES.md), [fr-FR](README.fr-FR.md), [he-IL](README.he-IL.md), [hi-IN](README.hi-IN.md), [it-IT](README.it-IT.md), [ja-JP](README.ja-JP.md), [ko-KR](README.ko-KR.md), [pt-BR](README.pt-BR.md), [ru-RU](README.ru-RU.md), [zh-CN](README.zh-CN.md)

## O que é

Agentes de IA auto-alojados que correm como utilizadores individuais num servidor GNU/Linux (Debian ou Alpine).

Cada agente tem, só para si:

- Pasta pessoal
- Crontab
- Acesso à shell
- Partilha Samba
- RAG (se precisar)
- Etc.

Pode aceder-lhes diretamente na aplicação web ou através do Telegram ou do Discord.

## Capturas de ecrã

![Interface do Bunch of AIgents](https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/doc/screenshot.png)

## Instalação

Execute-o como `root`.

**Debian** (com o systemd como PID 1):

```bash
curl -fsSL https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-debian.sh \
  | bash -s -- --install --email you@example.com
```

**Alpine Linux**:

```bash
wget -qO- https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-alpine.sh \
  | sh -s -- --install --email you@example.com
```

> **O Alpine não tem Playwright.** O Playwright não publica nenhuma build para
> musl, por isso em Alpine os agentes não têm navegador: as ferramentas
> `browser.*` dizem-no quando um agente chama uma delas. Tudo o resto funciona
> como em Debian.

## Leia a documentação

Explore:

- [doc/MANUAL.pt-PT.md](doc/MANUAL.pt-PT.md) para aprender a instalá-lo, configurá-lo e utilizá-lo.
- [doc/CODE.pt-PT.md](doc/CODE.pt-PT.md) para perceber como está construído (para programadores e para modelos de IA).

## Patrocine este projeto

- **Contrate-me.** Pessoas e empresas podem contratar-me para acrescentar novas funcionalidades: [envie-me um e-mail](mailto:nipegun@gmail.com?subject=About%20the%20BoA%20repo).
- **Pague-me um café:** [buymeacoffee.com/nipegun](https://buymeacoffee.com/nipegun).
- **GitHub Sponsors.** Também pode apoiar financeiramente o projeto no GitHub: [github.com/sponsors/nipegun](https://github.com/sponsors/nipegun).
