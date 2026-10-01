# Bunch of AIgents (BoA)

本 README 还提供以下语言版本：\
[de-DE](README.de-DE.md), [en-GB](README.en-GB.md), [en-US](README.md), [es-AR](README.es-AR.md), [es-ES](README.es-ES.md), [fr-FR](README.fr-FR.md), [he-IL](README.he-IL.md), [hi-IN](README.hi-IN.md), [it-IT](README.it-IT.md), [ja-JP](README.ja-JP.md), [ko-KR](README.ko-KR.md), [pt-BR](README.pt-BR.md), [pt-PT](README.pt-PT.md), [ru-RU](README.ru-RU.md)

## 这是什么

自托管的 AI 智能体，每个都以独立用户的身份运行在 GNU/Linux 服务器（Debian 或 Alpine）上。

每个智能体都独享：

- 主目录
- crontab
- shell 访问
- Samba 共享
- RAG（如有需要）
- 等等

你可以直接在 Web 应用中使用它们，也可以通过 Telegram 或 Discord。

## 截图

![Bunch of AIgents 界面](https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/doc/screenshot.png)

## 安装

请以 `root` 身份运行。

**Debian**（以 systemd 为 PID 1）：

```bash
curl -fsSL https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-debian.sh \
  | bash -s -- --install --email you@example.com
```

**Alpine Linux**：

```bash
wget -qO- https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-alpine.sh \
  | sh -s -- --install --email you@example.com
```

> **Alpine 上没有 Playwright。** Playwright 没有为 musl 发布构建，所以在 Alpine 上智能体没有浏览器：智能体调用 `browser.*` 工具时，它们会说明这一点。其他一切都和在 Debian 上一样工作。

## 阅读文档

进一步了解：

- [doc/MANUAL.zh-CN.md](doc/MANUAL.zh-CN.md)：学习如何安装、配置和使用。
- [doc/CODE.zh-CN.md](doc/CODE.zh-CN.md)：了解它是如何构建的（面向开发者和 AI 模型）。

## 赞助本项目

- **委托开发。** 个人和企业都可以委托我添加新功能：[给我发邮件](mailto:nipegun@gmail.com?subject=About%20the%20BoA%20repo)。
- **请我喝杯咖啡：**[buymeacoffee.com/nipegun](https://buymeacoffee.com/nipegun)。
- **GitHub Sponsors。** 你也可以在 GitHub 上为项目提供资金支持：[github.com/sponsors/nipegun](https://github.com/sponsors/nipegun)。
