# Bunch of AIgents (BoA)

קובץ ה-README הזה זמין גם בשפות:\
[de-DE](README.de-DE.md), [en-GB](README.en-GB.md), [en-US](README.md), [es-AR](README.es-AR.md), [es-ES](README.es-ES.md), [fr-FR](README.fr-FR.md), [hi-IN](README.hi-IN.md), [it-IT](README.it-IT.md), [ja-JP](README.ja-JP.md), [ko-KR](README.ko-KR.md), [pt-BR](README.pt-BR.md), [pt-PT](README.pt-PT.md), [ru-RU](README.ru-RU.md), [zh-CN](README.zh-CN.md)

## מה זה

סוכני בינה מלאכותית באירוח עצמי, שרצים כמשתמשים נפרדים בשרת GNU/Linux (Debian או Alpine).

לכל סוכן יש משלו:

- תיקיית בית
- קובץ crontab
- גישת shell
- שיתוף Samba
- ספריית RAG (אם צריך)
- ועוד.

אפשר לפנות אליהם ישירות באפליקציית הווב, או דרך Telegram או Discord.

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

- המדריך [doc/MANUAL.he-IL.md](doc/MANUAL.he-IL.md), כדי ללמוד איך להתקין, להגדיר ולהשתמש בו.
- המסמך [doc/CODE.he-IL.md](doc/CODE.he-IL.md), כדי להבין איך הוא בנוי (למפתחים ולמודלי בינה מלאכותית).

## מתן חסות לפרויקט

- **אפשר להעסיק אותי.** אנשים וחברות יכולים להעסיק אותי כדי להוסיף תכונות חדשות: [שלחו לי דוא״ל](mailto:nipegun@gmail.com?subject=About%20the%20BoA%20repo).
- **קנו לי קפה:** [buymeacoffee.com/nipegun](https://buymeacoffee.com/nipegun).
- **תמיכה דרך GitHub Sponsors.** אפשר גם לתמוך בפרויקט כלכלית ב-GitHub: [github.com/sponsors/nipegun](https://github.com/sponsors/nipegun).
