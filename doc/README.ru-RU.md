# Bunch of AIgents (BoA)

Этот README доступен также на языках:\
[de-DE](README.de-DE.md), [en-GB](README.en-GB.md), [en-US](../README.md), [es-AR](README.es-AR.md), [es-ES](README.es-ES.md), [fr-FR](README.fr-FR.md), [he-IL](README.he-IL.md), [hi-IN](README.hi-IN.md), [it-IT](README.it-IT.md), [ja-JP](README.ja-JP.md), [ko-KR](README.ko-KR.md), [pt-BR](README.pt-BR.md), [pt-PT](README.pt-PT.md), [zh-CN](README.zh-CN.md)

## Что это

Самостоятельно размещаемые ИИ-агенты, каждый из которых работает как отдельный пользователь на сервере GNU/Linux (Debian или Alpine).

У каждого агента есть свои:

- Домашний каталог
- Crontab
- Доступ к оболочке
- Общий ресурс Samba
- RAG (при необходимости)
- И так далее.

Обращаться к ним можно через веб-приложение, Telegram, Discord, Slack, Mattermost или личные сообщения X.

## Скриншоты

![Интерфейс Bunch of AIgents](https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/doc/screenshot.png)

## Установка

Запускайте от имени `root`.

**Debian** (с systemd в роли PID 1):

```bash
curl -fsSL https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-debian.sh \
  | bash -s -- --install --email you@example.com
```

**Alpine Linux**:

```bash
wget -qO- https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-alpine.sh \
  | sh -s -- --install --email you@example.com
```

> **В Alpine нет Playwright.** Playwright не публикует сборку для musl, поэтому
> в Alpine у агентов нет браузера: инструменты `browser.*` сообщают об этом,
> когда агент вызывает один из них. Всё остальное работает так же, как в
> Debian.

## Читайте документацию

Подробнее:

- [doc/MANUAL.ru-RU.md](MANUAL.ru-RU.md) — как его установить, настроить и использовать.
- [doc/CODE.ru-RU.md](CODE.ru-RU.md) — как он устроен (для разработчиков и для моделей ИИ).
- Настройка каналов: [Telegram](MANUAL.ru-RU.md#telegram), [Discord](MANUAL.ru-RU.md#discord-setup), [Slack](MANUAL.ru-RU.md#slack), [Mattermost](MANUAL.ru-RU.md#mattermost), [X](MANUAL.ru-RU.md#x).

## Спонсируйте этот проект

- **[Наймите меня](mailto:nipegun@gmail.com?subject=I%20want%20new%20BoA%20features%21)**, чтобы добавить новые функции.
- **GitHub Sponsors.** Поддержать проект деньгами можно и на GitHub: [github.com/sponsors/nipegun](https://github.com/sponsors/nipegun).
