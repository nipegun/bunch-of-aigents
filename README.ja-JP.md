# Bunch of AIgents (BoA)

この README は次の言語でも読めます:\
[de-DE](README.de-DE.md), [en-GB](README.en-GB.md), [en-US](README.md), [es-AR](README.es-AR.md), [es-ES](README.es-ES.md), [fr-FR](README.fr-FR.md), [he-IL](README.he-IL.md), [hi-IN](README.hi-IN.md), [it-IT](README.it-IT.md), [ko-KR](README.ko-KR.md), [pt-BR](README.pt-BR.md), [pt-PT](README.pt-PT.md), [ru-RU](README.ru-RU.md), [zh-CN](README.zh-CN.md)

## これは何か

GNU/Linux サーバー（Debian または Alpine）上で、それぞれが独立したユーザーとして動くセルフホスト型の AI エージェントです。

各エージェントは、次のものを専用に持ちます:

- ホームディレクトリ
- crontab
- シェルアクセス
- Samba 共有
- RAG（必要な場合）
- など

Web アプリから直接、または Telegram や Discord 経由で利用できます。

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

- [doc/MANUAL.ja-JP.md](doc/MANUAL.ja-JP.md)：インストール、設定、使い方を学べます。
- [doc/CODE.ja-JP.md](doc/CODE.ja-JP.md)：どのように作られているかがわかります（開発者と AI モデル向け）。

## このプロジェクトのスポンサーになる

- **開発のご依頼。** 個人・企業を問わず、新機能の追加をご依頼いただけます: [メールでご連絡ください](mailto:nipegun@gmail.com?subject=About%20the%20BoA%20repo)。
- **コーヒーをおごる:** [buymeacoffee.com/nipegun](https://buymeacoffee.com/nipegun)。
- **GitHub Sponsors。** GitHub でプロジェクトを金銭的に支援することもできます：[github.com/sponsors/nipegun](https://github.com/sponsors/nipegun)。
