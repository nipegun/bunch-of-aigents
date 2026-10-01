# Bunch of AIgents (BoA)

Este README também está disponível em:\
[de-DE](README.de-DE.md), [en-GB](README.en-GB.md), [en-US](README.md), [es-AR](README.es-AR.md), [es-ES](README.es-ES.md), [fr-FR](README.fr-FR.md), [he-IL](README.he-IL.md), [hi-IN](README.hi-IN.md), [it-IT](README.it-IT.md), [ja-JP](README.ja-JP.md), [ko-KR](README.ko-KR.md), [pt-PT](README.pt-PT.md), [ru-RU](README.ru-RU.md), [zh-CN](README.zh-CN.md)

## O que é

Agentes de IA auto-hospedados que rodam como usuários individuais em um servidor GNU/Linux (Debian ou Alpine).

Cada agente tem, só para si:

- Diretório pessoal
- Crontab
- Acesso ao shell
- Compartilhamento Samba
- RAG (se precisar)
- Etc.

Você pode acessá-los diretamente pelo aplicativo web ou pelo Telegram ou Discord.

## Capturas de tela

![Interface do Bunch of AIgents](https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/doc/screenshot.png)

## Instalação

Execute como `root`.

**Debian** (com systemd como PID 1):

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
> musl, então no Alpine os agentes não têm navegador: as ferramentas
> `browser.*` avisam disso quando um agente chama uma delas. Todo o resto
> funciona como no Debian.

## Leia a documentação

Explore:

- [doc/MANUAL.pt-BR.md](doc/MANUAL.pt-BR.md) para aprender a instalar, configurar e usar.
- [doc/CODE.pt-BR.md](doc/CODE.pt-BR.md) para entender como ele é construído (para desenvolvedores e para modelos de IA).

## Patrocine este projeto

- **Me contrate.** Pessoas e empresas podem me contratar para adicionar novos recursos: [me mande um e-mail](mailto:nipegun@gmail.com?subject=About%20the%20BoA%20repo).
- **Me pague um café:** [buymeacoffee.com/nipegun](https://buymeacoffee.com/nipegun).
- **GitHub Sponsors.** Você também pode apoiar o projeto financeiramente no GitHub: [github.com/sponsors/nipegun](https://github.com/sponsors/nipegun).
