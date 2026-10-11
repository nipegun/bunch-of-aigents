# Bunch of AIgents (BoA)

קובץ ה-README הזה זמין גם בשפות:\
[de-DE](README.de-DE.md), [en-GB](README.en-GB.md), [en-US](../README.md), [es-AR](README.es-AR.md), [es-ES](README.es-ES.md), [fr-FR](README.fr-FR.md), [hi-IN](README.hi-IN.md), [it-IT](README.it-IT.md), [ja-JP](README.ja-JP.md), [ko-KR](README.ko-KR.md), [pt-BR](README.pt-BR.md), [pt-PT](README.pt-PT.md), [ru-RU](README.ru-RU.md), [zh-CN](README.zh-CN.md)

## מה זה

סוכני בינה מלאכותית באירוח עצמי, שרצים כמשתמשים נפרדים בשרת GNU/Linux (Debian או Alpine).

לכל סוכן יש משלו:

- תיקיית בית
- קובץ crontab
- גישת shell
- שיתוף Samba
- ספריית RAG (אם צריך)
- ועוד.

אפשר לגשת אליהם ישירות באפליקציית האתר או דרך Telegram, Discord, Slack, Mattermost או הודעות פרטיות ב-X.

## צילומי מסך

![הממשק של Bunch of AIgents](https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/doc/screenshot.png)

## התקנה

יש להריץ בתור `root`.

**ב-Debian** (עם systemd כ-PID 1):

```bash
curl -fsSL https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-debian.sh \
  | bash -s -- --install --email you@example.com
```

**ב-Alpine Linux**:

```bash
wget -qO- https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-alpine.sh \
  | sh -s -- --install --email you@example.com
```

> **ב-Alpine אין Playwright.** הפרויקט Playwright לא מפרסם גרסה בנויה
> ל-musl, ולכן ב-Alpine לסוכנים אין דפדפן: הכלים `browser.*` אומרים זאת
> כשסוכן קורא לאחד מהם. כל השאר עובד כמו ב-Debian.

## קריאת התיעוד

לעיון:

- המדריך [doc/MANUAL.he-IL.md](MANUAL.he-IL.md), כדי ללמוד איך להתקין, להגדיר ולהשתמש בו.
- המסמך [doc/CODE.he-IL.md](CODE.he-IL.md), כדי להבין איך הוא בנוי (למפתחים ולמודלי בינה מלאכותית).
- הפעלת ערוצי התקשורת: [Telegram](MANUAL.he-IL.md#telegram), [Discord](MANUAL.he-IL.md#discord-setup), [Slack](MANUAL.he-IL.md#slack), [Mattermost](MANUAL.he-IL.md#mattermost), [X](MANUAL.he-IL.md#x).

## מתן חסות לפרויקט

- **[העסיקו אותי](mailto:nipegun@gmail.com?subject=I%20want%20new%20BoA%20features%21)** כדי להוסיף תכונות חדשות.
- **תמיכה דרך GitHub Sponsors.** אפשר גם לתמוך בפרויקט כלכלית ב-GitHub: [github.com/sponsors/nipegun](https://github.com/sponsors/nipegun).
