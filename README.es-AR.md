# Bunch of AIgents (BoA)

Este README también está disponible en:\
[de-DE](README.de-DE.md), [en-GB](README.en-GB.md), [en-US](README.md), [es-ES](README.es-ES.md), [fr-FR](README.fr-FR.md), [he-IL](README.he-IL.md), [hi-IN](README.hi-IN.md), [it-IT](README.it-IT.md), [ja-JP](README.ja-JP.md), [ko-KR](README.ko-KR.md), [pt-BR](README.pt-BR.md), [pt-PT](README.pt-PT.md), [ru-RU](README.ru-RU.md), [zh-CN](README.zh-CN.md)

## Qué es

Agentes de IA autoalojados que se ejecutan como usuarios individuales en un servidor GNU/Linux (Debian o Alpine).

Cada agente tiene, en exclusiva:

- Carpeta home
- Crontab
- Acceso a la shell
- Recurso compartido de Samba
- RAG (si lo necesita)
- Etc.

Podés acceder a ellos directamente desde la aplicación web o a través de Telegram o Discord.

## Capturas de pantalla

![Interfaz de Bunch of AIgents](https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/doc/screenshot.png)

## Instalación

Ejecutalo como `root`.

**Debian** (con systemd como PID 1):

```bash
curl -fsSL https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-debian.sh \
  | bash -s -- --install --email tu@ejemplo.com
```

**Alpine Linux**:

```bash
wget -qO- https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-alpine.sh \
  | sh -s -- --install --email tu@ejemplo.com
```

> **En Alpine no hay Playwright.** Playwright no publica ninguna versión para
> musl, así que en Alpine los agentes no tienen navegador: las herramientas
> `browser.*` lo dicen cuando un agente llama a alguna. Todo lo demás funciona
> igual que en Debian.

## Leé la documentación

Explorá:

- [doc/MANUAL.es-AR.md](doc/MANUAL.es-AR.md) para aprender a instalarlo, configurarlo y usarlo.
- [doc/CODE.es-AR.md](doc/CODE.es-AR.md) para entender cómo está construido (para desarrolladores y para modelos de IA).

## Patrociná este proyecto

- **Contratame.** Personas y empresas pueden contratarme para agregar funcionalidades nuevas: [escribime](mailto:nipegun@gmail.com?subject=About%20the%20BoA%20repo).
- **Invitame un café:** [buymeacoffee.com/nipegun](https://buymeacoffee.com/nipegun).
- **GitHub Sponsors.** También podés apoyar el proyecto económicamente en GitHub: [github.com/sponsors/nipegun](https://github.com/sponsors/nipegun).
