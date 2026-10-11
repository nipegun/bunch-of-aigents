# Bunch of AIgents (BoA)

この README は次の言語でも読めます:\
[de-DE](README.de-DE.md), [en-GB](README.en-GB.md), [en-US](../README.md), [es-AR](README.es-AR.md), [es-ES](README.es-ES.md), [fr-FR](README.fr-FR.md), [he-IL](README.he-IL.md), [hi-IN](README.hi-IN.md), [it-IT](README.it-IT.md), [ko-KR](README.ko-KR.md), [pt-BR](README.pt-BR.md), [pt-PT](README.pt-PT.md), [ru-RU](README.ru-RU.md), [zh-CN](README.zh-CN.md)

## これは何か

GNU/Linux サーバー（Debian または Alpine）上で、それぞれが独立したユーザーとして動くセルフホスト型の AI エージェントです。

各エージェントは、次のものを専用に持ちます:

- ホームディレクトリ
- crontab
- シェルアクセス
- Samba 共有
- RAG（必要な場合）
- など

ウェブアプリ、Telegram、Discord、Slack、Mattermost、または X のダイレクトメッセージからアクセスできます。

## スクリーンショット

![Bunch of AIgents の画面](https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/doc/screenshot.png)

## インストール

`root` で実行してください。

**Debian**（systemd が PID 1 であること）:

```bash
curl -fsSL https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-debian.sh \
  | bash -s -- --install --email you@example.com
```

**Alpine Linux**:

```bash
wget -qO- https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-alpine.sh \
  | sh -s -- --install --email you@example.com
```

> **Alpine には Playwright がありません。** Playwright は musl 向けのビルドを公開していないため、Alpine ではエージェントがブラウザーを持てません。エージェントが `browser.*` ツールを呼び出すと、ツールがその旨を伝えます。それ以外はすべて Debian と同じように動きます。

## ドキュメントを読む

詳しくはこちら:

- [doc/MANUAL.ja-JP.md](MANUAL.ja-JP.md)：インストール、設定、使い方を学べます。
- [doc/CODE.ja-JP.md](CODE.ja-JP.md)：どのように作られているかがわかります（開発者と AI モデル向け）。
- チャンネルの導入手順: [Telegram](MANUAL.ja-JP.md#telegram), [Discord](MANUAL.ja-JP.md#discord-setup), [Slack](MANUAL.ja-JP.md#slack), [Mattermost](MANUAL.ja-JP.md#mattermost), [X](MANUAL.ja-JP.md#x).

## このプロジェクトのスポンサーになる

- 新機能の追加を**[私にご依頼ください](mailto:nipegun@gmail.com?subject=I%20want%20new%20BoA%20features%21)**。
- **GitHub Sponsors。** GitHub でプロジェクトを金銭的に支援することもできます：[github.com/sponsors/nipegun](https://github.com/sponsors/nipegun)。
