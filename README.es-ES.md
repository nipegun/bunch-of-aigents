# Bunch of AIgents (BoA)

Este README también está disponible en:\
[de-DE](README.de-DE.md), [en-GB](README.en-GB.md), [en-US](README.md), [es-AR](README.es-AR.md), [fr-FR](README.fr-FR.md), [he-IL](README.he-IL.md), [hi-IN](README.hi-IN.md), [it-IT](README.it-IT.md), [ja-JP](README.ja-JP.md), [ko-KR](README.ko-KR.md), [pt-BR](README.pt-BR.md), [pt-PT](README.pt-PT.md), [ru-RU](README.ru-RU.md), [zh-CN](README.zh-CN.md)

## Qué es

Agentes de IA autoalojados que se ejecutan como usuarios individuales en un servidor GNU/Linux (Debian o Alpine).

Cada agente tiene, en exclusiva:

- Carpeta home
- Crontab
- Acceso a la shell
- Recurso compartido de Samba
- RAG (si lo necesita)
- Etc.

Puedes acceder a ellos directamente desde la aplicación web o a través de Telegram o Discord.

## Capturas de pantalla

![Interfaz de Bunch of AIgents](https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/doc/screenshot.png)

## Instalación

Ejecútalo como `root`.

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

## Lee la documentación

Explora:

- [doc/MANUAL.es-ES.md](doc/MANUAL.es-ES.md) para aprender a instalarlo, configurarlo y usarlo.
- [doc/CODE.es-ES.md](doc/CODE.es-ES.md) para entender cómo está construido (para desarrolladores y para modelos de IA).

## Patrocina este proyecto

- **Contrátame.** Personas y empresas pueden contratarme para añadir funcionalidades nuevas: [escríbeme](mailto:nipegun@gmail.com?subject=About%20the%20BoA%20repo).
- **Invítame a un café:** [buymeacoffee.com/nipegun](https://buymeacoffee.com/nipegun).
- **GitHub Sponsors.** También puedes apoyar el proyecto económicamente en GitHub: [github.com/sponsors/nipegun](https://github.com/sponsors/nipegun).
