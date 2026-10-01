# Handbuch

Wie du Bunch of AIgents im Alltag verwendest.

## Inhalt

1. [Was es tut](#was-es-tut)
1. [Worauf es läuft](#worauf-es-läuft)
1. [Wenn du Alpine verwendest](#wenn-du-alpine-verwendest)
1. [Installation](#installation)
1. [Aktualisieren und neu installieren](#aktualisieren-und-neu-installieren)
1. [Aufrufen](#aufrufen)
1. [Anmelden](#anmelden)
1. [Der erste Start](#der-erste-start)
2. [Die Oberfläche](#die-oberfläche)
3. [Woher ein neuer Agent kommt](#woher-ein-neuer-agent-kommt)
3. [Deinen ersten Agenten erstellen](#deinen-ersten-agenten-erstellen)
4. [Mit einem Agenten sprechen](#mit-einem-agenten-sprechen)
5. [Agenteneinstellungen](#agenteneinstellungen)
5. [Einen Agenten exportieren](#einen-agenten-exportieren)
5. [Samba-Freigaben](#samba-freigaben)
6. [Einem Agenten ein Modell geben](#einem-agenten-ein-modell-geben)
5. [Einen System-Prompt schreiben](#einen-system-prompt-schreiben)
6. [Werkzeuge auswählen](#werkzeuge-auswählen)
7. [Einem Agenten eine Fähigkeit geben](#einem-agenten-eine-fähigkeit-geben)
8. [Einem Agenten einen Browser geben](#einem-agenten-einen-browser-geben)
9. [Ausgabenobergrenzen](#ausgabenobergrenzen)
8. [Einen Agenten planen](#einen-agenten-planen)
9. [Das Kanban-Board](#das-kanban-board)
10. [Themes](#themes)
11. [Kanäle](#kanäle)
12. [Der Orchestrator](#der-orchestrator)
13. [Sichern und Wiederherstellen](#sichern-und-wiederherstellen)
13. [Dienste](#dienste)
13. [Sicherheit](#sicherheit)
14. [Wenn etwas nicht funktioniert](#wenn-etwas-nicht-funktioniert)
1. [Audiotranskription](#audiotranskription)
1. [Lizenz](#lizenz)

---

- [Lokale Dokumentbibliotheken (RAG)](#lokale-dokumentbibliotheken-rag)

## Was es tut

- **Ein Agent ist ein Linux-Benutzer.** Wenn du in der Weboberfläche einen
  anlegst, entsteht auf dem System `agent-007`, mit einem Home-Verzeichnis, das
  kein anderer Agent lesen kann. Das ist die Isolation: die des Kernels, keine
  in Python geschriebene Sandbox.
- **Agenten laufen nach ihrem eigenen Zeitplan.** Jeder hat seine eigene
  Crontab, die seinem eigenen Benutzer gehört und von ihm ausgeführt wird: Ein
  Agent wacht auf, erledigt seine Arbeit und beendet sich.
- **Du sprichst mit ihnen.** Ein Klick auf einen Agenten öffnet einen Chat: Bitte
  ihn um etwas, und er setzt seine Werkzeuge ein und antwortet, wenn er fertig
  ist. Das Gespräch bleibt erhalten.
- **Ein Gespräch pro Agent, nicht eines pro Person.** Eine fällige Karte wird zu
  Beginn des Laufs in genau diesen Chat gestellt, und die Antwort erscheint
  darunter. Der Chat eines Agenten ist also alles, worum er gebeten wurde - von
  dir oder von einem anderen Agenten - und was er daraus gemacht hat.
- **Sie teilen sich ein Kanban-Board.** Agenten legen Karten an, verschieben sie
  und sehen die Arbeit der anderen. Du schaust unter `/kanban/` zu, statt Logs
  zu lesen.
- **Jedes Modell, aus der Cloud oder selbst gehostet.** Fünfundzwanzig Anbieter
  sind dabei - Anthropic, OpenAI, Google, DeepSeek, Mistral, Qwen, xAI und der
  Rest; die Router davor, OpenRouter, Groq, Together, Vercel und weitere; und
  Ollama, llama.cpp und vLLM auf deiner eigenen Hardware. Jeder Agent wählt
  seines selbst, mit einem Ersatz für den Fall, dass es ausfällt.
- **Ausgabenobergrenzen, die wirklich stoppen.** Token, Schritte, Sekunden und
  Läufe pro Tag, pro Agent. Ein unbeaufsichtigter Agent an einer
  kostenpflichtigen API ist sonst eine offene Rechnung.
- **Einstellbares Gedächtnis.** Lege das Gedächtnislimit jedes Agenten in seinen
  Einstellungen fest, von 1.000 bis 1.000.000 Zeichen (standardmäßig 8.000).
  Zu große Schreibvorgänge werden abgelehnt, ohne den Text zu kürzen oder das
  gespeicherte Gedächtnis zu ersetzen.
- **Eine Dokumentbibliothek pro Agent.** Lade Bücher als PDF, EPUB, TXT oder
  Markdown hoch. Extraktion, OCR und Vektorisierung bleiben lokal; die Agenten
  rufen die passenden Abschnitte ab und nennen ihre Quellen. Eingerichtet wird
  das unter **RAG**. Das Einbettungsmodell ist standardmäßig EmbeddingGemma
  300M; eine Maschine mit Prozessor und Arbeitsspeicher übrig kann unter
  **Einstellungen → RAG** auf Qwen3-Embedding 0.6B wechseln.
- **Agenten, die du umziehen kannst.** Der Tab **Exportieren** eines Agenten lädt
  ihn als `.zip` herunter - wahlweise mit seinem Gedächtnis, seinem Modell,
  seiner Bibliothek und den Dateien seines Home-Verzeichnisses, nie mit einem
  Schlüssel -, und **+** importiert ihn hier oder in einer anderen
  Installation. Fertige Agenten kommen aus dem
  [Vorlagen-Repository](https://github.com/nipegun/bunch-of-aigents-templates).
- **Werkzeuge, die du erweitern kannst.** Jedes Werkzeug ist eine `.py`-Datei in
  `/opt/boa/tools/`. Leg eine neue dort ab, und sie erscheint unter
  **Einstellungen → Werkzeuge**, gruppiert in Unter-Tabs wie Automatisierung und
  Browser.
- **Fähigkeiten, die sie teilen.** Ein Ablauf, der einmal in `/opt/boa/skills/`
  geschrieben wurde, lässt sich beliebig vielen Agenten geben. Was ein Agent
  selbst lernt, stirbt in seinem eigenen Gedächtnis; eine Fähigkeit nicht.
- **Ein Browser für jeden, mit eigenen Sitzungen.** Ein Agent kann sich auf
  einer Website anmelden, ein Formular ausfüllen und klicken - nicht nur eine
  Seite lesen -, und seine Cookies liegen in seinem eigenen Home mit 0700. Die
  Anmeldung eines Agenten ist also nicht die Anmeldung aller Agenten.
- **Antworte ihnen aus Telegram oder Discord.** Wähle mit /agents einen Agenten
  oder antworte auf eine Nachricht, die dir einer geschickt hat: Was du
  schreibst, erreicht ihn, startet einen Lauf und kommt beantwortet auf dein
  Handy zurück. Der ganze Austausch steht auch im Gespräch dieses Agenten in
  der Weboberfläche, beide Hälften, sodass ein einziger Bildschirm weiterhin
  alles zeigt.
- **Telegram-Audio.** **Einstellungen → Audio** wählt lokal whisper.cpp oder
  OpenAI, Groq, Mistral, Together AI, Hugging Face oder Cloudflare, mit einem
  bereits gespeicherten API-Schlüssel. Alle 30 nativen Modelle stehen zur
  Auswahl und werden bei Bedarf heruntergeladen. Eine Sprachantwort erreicht
  ihren ursprünglichen Agenten als Text und erscheint im Webchat, wahlweise mit
  Audiowiedergabe.
- **Ein freigegebener Ordner für jeden.** Der Ordner `samba/` jedes Agenten ist
  eine SMB-Freigabe, die nach seinem Linux-Benutzer benannt ist, sodass du
  Dateien von Windows, Linux oder macOS aus hineinlegen kannst.
- **Fünfzehn Sprachen.** Deutsch, Englisch (UK und US), Spanisch (Spanien und
  Argentinien), Französisch, Hebräisch, Hindi, Italienisch, Japanisch, Koreanisch,
  Portugiesisch (Brasilien und Portugal), Russisch und vereinfachtes
  Chinesisch. Die Oberfläche, die Zeile, die deinen Agenten sagt, in welcher
  Sprache sie antworten sollen, und das, was die beiden Bots sagen.

Es ist für eine einzelne Person gebaut, die es in ihrem eigenen LAN betreibt.

## Worauf es läuft

Zwei Systeme, und bei beiden gehört das Init-System zur Voraussetzung, es ist
kein Detail:

- **Debian mit systemd als PID 1.** Die zehn Dienste sind systemd-Units. Auf
  einem Debian, das mit etwas anderem bootet, gibt es nichts, was sie starten
  könnte. Deshalb prüft der Installer `systemctl is-system-running`, bevor er
  die Maschine anfasst, und verweigert die Arbeit, wenn systemd nicht da ist.
  Versuch es auf so einer Maschine gar nicht erst: Die Antwort wird sich nicht
  ändern.
- **Alpine mit OpenRC.** Die zehn Dienste sind OpenRC-Skripte, überwacht von
  `supervise-daemon`. Vorab muss nichts installiert werden - der Installer
  fügt `openrc` selbst hinzu, wenn die Maschine keins hat.

Prüfe es auf Debian mit `systemctl is-system-running`: Es muss antworten
(`running`, `degraded`, `starting`) und darf nicht „System has not been booted
with systemd as init system (PID 1)“ ausgeben. Ein Container braucht
installiertes `systemd systemd-sysv dbus` und `/sbin/init` als Befehl.

Neben dem Init-System braucht es:

- `root`-Zugriff. Keiner der beiden Installer verwendet `sudo`, und keiner
  braucht es.
- Etwa 500 MB Festplattenplatz für die Anwendung und ihre Python-Umgebung.
- `haproxy`, das der Installer installiert. Es terminiert TLS, weil der
  PROXY-Header, den das HAProxy der Maschine sendet, vor dem TLS-Handshake
  ankommt und ihn dort nur ein Proxy lesen kann.
- Ein Modell, mit dem es sprechen kann: entweder einen API-Schlüssel für einen
  Cloud-Anbieter oder Ollama, llama.cpp oder vLLM, das irgendwo läuft, wo du
  es erreichst.

Der Installer baut außerdem **whisper.cpp v1.9.4** in `/opt/boa/whisper/`,
installiert FFmpeg und lädt das mehrsprachige Modell `base` herunter (etwa
142 MiB zusätzlich). Kompilierung, Systemabhängigkeiten und der Browser
brauchen zusätzlichen Festplattenplatz. Ein fehlender Python-Interpreter wird
installiert, bevor seine Version geprüft wird.

Alles andere in diesem Handbuch ist auf beiden gleich.

## Wenn du Alpine verwendest

Jeder Befehl in diesem Handbuch, der `systemctl` oder `journalctl` nennt, ist
der für Debian. Die Anwendung ist auf Alpine dieselbe; was sich ändert, sind
das Init-System und der Ort, an dem die Logs landen:

| Auf Debian | Auf Alpine |
|---|---|
| `systemctl status boa-web` | `rc-service boa-web status` oder `rc-status` für alle zehn |
| `systemctl restart boa-web` | `rc-service boa-web restart` |
| `journalctl -u boa-web -f` | `tail -f /opt/boa/logs/boa-web.log` |
| `install-update-reinstall-debian.sh` | `install-update-reinstall-alpine.sh` |

Eine Funktion fehlt dort, und sie kommt auch nicht zurück: Es gibt keinen
Browser, weil Playwright keinen Build für musl veröffentlicht. Die
Browser-Werkzeuge bleiben in der Liste und sagen das, wenn ein Agent eines
aufruft.

---

## Installation

Ein Installer pro Distribution, und beide nehmen dieselben Flags. Führe ihn als
`root` aus.

### Unter Debian

> **systemd muss auf der Maschine laufen.** Führe zuerst
> `systemctl is-system-running` aus: Wenn es „System has not been booted with
> systemd as init system (PID 1). Can't operate.“ ausgibt, hör hier auf. Jeder
> Dienst, den das hier installiert, ist eine systemd-Unit, es gäbe also nichts,
> was sie starten könnte, und der Installer verweigert aus diesem Grund die
> Arbeit, statt dir eine Installation zu hinterlassen, die nichts ausliefert.

```bash
curl -fsSL https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-debian.sh \
  | bash -s -- --install --email you@example.com
```

Wenn `curl` nicht installiert ist - ein minimales Debian hat oft weder das noch
`wget` -, installiere es zuerst, sonst gibt die Zeile oben `curl: command not
found` aus und bricht ab:

```bash
apt-get update && apt-get install -y curl
```

Oder lade den Installer zuerst herunter und lies ihn, bevor du ihn ausführst,
was die bessere Gewohnheit ist:

```bash
wget https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-debian.sh
less install-update-reinstall-debian.sh
chmod +x install-update-reinstall-debian.sh
./install-update-reinstall-debian.sh --install --email you@example.com
```

### Unter Alpine Linux

Dieselben Flags, ein anderes Skript: Es schreibt OpenRC-Dienste statt
systemd-Units. Eine Zeile, mit `wget` und in `sh` geleitet, weil ein frisches
Alpine weder `curl` noch bash hat und beide von BusyBox stammen:

```bash
wget -qO- https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-alpine.sh \
  | sh -s -- --install --email you@example.com
```

Verwende auf einer Maschine, die es hat, `curl -fsSL` anstelle von `wget -qO-` -
und achte dann auf diese Zeile, denn ein in `sh` geleitetes `curl: not found`
gibt seinen Fehler aus und **gelingt** dann, ohne etwas installiert zu haben.

Der Installer ist POSIX-Shell statt bash, aus demselben Grund wie das `wget`:
Ein frisches Alpine hat kein bash, das `| bash -s --` erreichen könnte. Er
installiert bash unterwegs - jeder Agent bekommt eine bash-Shell -, sodass auf
einer Maschine, die schon eines hat, `| bash -s --` genauso gut funktioniert.

Oder lade ihn zuerst herunter und lies ihn, bevor du ihn ausführst:

```bash
wget https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-alpine.sh
less install-update-reinstall-alpine.sh
chmod +x install-update-reinstall-alpine.sh
./install-update-reinstall-alpine.sh --install --email you@example.com
```

Zwei Dinge sind anders, sobald es läuft, und beide gehen auf das System zurück,
nicht auf eine Entscheidung:

- **Kein Browser.** Playwright veröffentlicht keinen Build für musl, und Alpine
  paketiert keinen, also sagen `browser.open` und die übrigen das, wenn ein
  Agent eines aufruft. `web.fetch` und `rss.fetch` funktionieren wie überall.
- **`rc-status` statt `systemctl status`**, und `rc-service boa-web
  restart` anstelle von `systemctl restart boa-web`. Siehe
  [Wenn du Alpine verwendest](#wenn-du-alpine-verwendest).

Auf Alpine geben die Dienste die SSH-Ausgabe des Installers frei, sodass der
Installer die Kontrolle über die Sitzung zurückgibt, wenn er fertig ist.

### Was der Installer tut

1. Legt den Systembenutzer `boa` und den Verzeichnisbaum unter `/opt/boa/` an.
2. Installiert die Python-Abhängigkeiten in `/opt/boa/venv/`.
3. Erzeugt ein selbstsigniertes TLS-Zertifikat, es sei denn, du hast ein
   eigenes `fullchain.pem` und `privkey.pem` in `/opt/boa/certificates/`
   abgelegt.
4. Fragt, ob die Anwendung auf 11080/11443 hinter einem HAProxy auf 80 und 443
   ausgeliefert werden soll oder direkt auf 80 und 443. Übergib
   `--ports proxied|direct`, um die Frage vorab zu beantworten. Die Antwort wird
   gespeichert, sodass `--update` nie wieder fragt und sie auch nicht still
   ändert. Wer `direct` wählt, legt das eigene HAProxy der Maschine still -
   gestoppt, aus jedem Runlevel entfernt oder maskiert, und seine
   `/etc/haproxy/haproxy.cfg` gelöscht, wenn dieser Installer sie geschrieben
   hat, oder als `haproxy.cfg.before-boa.<date>` aufbewahrt, wenn jemand anderes
   es war -, damit beim nächsten Booten nichts 80 und 443 belegt. Das
   haproxy-Paket selbst bleibt: Der eigene Proxy der Anwendung ist genau dieses
   Binary.
5. Legt einen Agenten an: `manager`, den Orchestrator. Alles andere ist ein
   leerer Agent, eine aus einem Agenten exportierte `.zip` oder eine Vorlage
   aus dem
   [Vorlagen-Repository](https://github.com/nipegun/bunch-of-aigents-templates) -
   `web-navigator`, `os-watcher`, `mail-watcher` und andere -, ausgewählt, wenn
   du **+** drückst. Der leere Agent ist die erste angebotene Wahl.
6. Installiert und startet die unter [Dienste](#dienste) aufgeführten Dienste:
   systemd-Units auf Debian, OpenRC-Dienste, überwacht von `supervise-daemon`,
   auf Alpine.
7. Schreibt, was er getan hat, und dein Anmeldepasswort nach
   `/opt/boa/logs/install.log` (root, Modus 0600).
8. Ruft die Anmeldeseite der Anwendung ab, bevor er meldet, dass er fertig ist.
   Kommt die Seite nicht, sagt er das, schreibt in dasselbe Log, wie die
   Maschine in diesem Moment aussah - was curl aus der Anfrage gemacht hat, ob
   etwas auf dem Port lauscht, den Zustand der Dienste und die letzten Zeilen
   ihrer Ausgabe -, und nennt das Log, statt Erfolg zu melden. Ein `--update`
   stellt außerdem zuerst die vorherige Version wieder her.

### Wo das Passwort steht

Die E-Mail-Adresse, die du angibst, ist die einzige Anmeldung. Das Passwort
wird für dich erzeugt; lies es mit:

```bash
cat /opt/boa/logs/install.log
```

Diese eine Datei ist beides: das vollständige Log der Installation und die
Zugangsdaten, die sie erzeugt hat. Die Anmeldeseite nennt sie, sodass sich
niemand merken muss, wo sie liegt.

## Aktualisieren und neu installieren

```bash
./install-update-reinstall-debian.sh --update      # behält Agenten und Daten
./install-update-reinstall-debian.sh --reinstall   # löscht vorher alles
```

Auf Alpine sind es dieselben zwei Flags, am anderen Skript:

```bash
./install-update-reinstall-alpine.sh --update
./install-update-reinstall-alpine.sh --reinstall
```

`--reinstall` löscht jeden Agenten, jedes Home-Verzeichnis, jede Crontab und das
Kanban-Board. Es fragt nach einer Bestätigung, es sei denn, du übergibst
`--yes`.

Eine Installation, die auf halbem Weg abgebrochen ist - ein fehlgeschlagener
Download, ein abgerissenes Netzwerk -, wird abgeschlossen, indem du `--install`
erneut ausführst: Es macht dort weiter, wo es aufgehört hat, und `--update`
sagt es, wenn es eine solche findet.

Die beiden anderen Flags, `--backup` und `--restore`, werden unter
[Sichern und Wiederherstellen](#sichern-und-wiederherstellen) erklärt.

## Aufrufen

Im Standardmodus `proxied` lauscht das eigene HAProxy der Anwendung auf
`127.0.0.1:11443` (HTTPS) und `127.0.0.1:11080` (HTTP, das weiterleitet).
Diese Ports sind von außerhalb des Servers nicht erreichbar: Das eigene HAProxy
der Maschine bedient das LAN und leitet mit `send-proxy-v2` an 11443 weiter,
damit die echte Client-Adresse erhalten bleibt. Im Modus `direct` lauscht die
Anwendung selbst auf 80 und 443, ohne etwas davor.

Ist das eingerichtet, öffne:

```
https://your-server/
```

Das Zertifikat ist selbstsigniert, es sei denn, du hast eigene Zertifikate in
`/opt/boa/certificates/` abgelegt, also wird der Browser dich einmal warnen.

### Wie das HAProxy der Maschine aussehen muss

Das Backend, das auf diese Anwendung zeigt, braucht zwei Dinge:

```
backend https-out
  mode tcp
  server srv-https-out 127.0.0.1:11443 check port 11080 send-proxy
```

- **`send-proxy`**, damit die echte Client-Adresse die Anwendung erreicht. Ohne
  das sieht jede Anfrage so aus, als käme sie von 127.0.0.1, und die
  Begrenzung der Anmeldeversuche gilt nicht mehr pro Adresse.
- **`check port 11080`**, damit der Health Check am reinen HTTP-Port anklopft
  und nicht am TLS-Port. Ein TCP-Check gegen den TLS-Port verbindet sich und
  legt ohne Handshake wieder auf, und das eigene HAProxy der Anwendung
  protokolliert jeden davon als fehlgeschlagenen SSL-Handshake: eine Zeile alle
  zwei Sekunden, für immer. Beide Ports gehören zu einem Prozess, wenn also
  einer antwortet, ist auch der andere da. Füge kein `check-send-proxy` hinzu:
  11080 akzeptiert kein PROXY-Protokoll.
- **Kein `option ssl-hello-chk`.** Dessen ClientHello ist älter als TLS 1.2,
  daher fällt ein Backend, das TLS 1.2 verlangt - dieses hier und jedes moderne
  Apache oder nginx -, beim Check durch und wird für immer als down markiert.
  Das Symptom ist ein 503 von einem Dienst, der tadellos läuft. Ein einfaches
  `check` prüft bereits, dass der Port antwortet.

## Anmelden

Öffne `https://your-server/` und melde dich mit der E-Mail-Adresse an, die du
dem Installer gegeben hast, und mit dem Passwort, das er erzeugt hat. Wenn du
es nicht hast:

```bash
cat /opt/boa/logs/install.log
```

Diese Datei ist das gesamte Installationslog mit den Zugangsdaten am Ende, und
die Anmeldeseite nennt sie genau für diesen Moment.

**Abmelden** öffnet eine Bestätigung in der Mitte des Bildschirms. Bestätige, um
die Sitzung zu beenden, oder wähle **Abbrechen** oder drücke Escape, um
angemeldet zu bleiben.

Es gibt ein Konto. Ändere sein Passwort unter **Einstellungen → Konto**. Die
Änderung verlangt zusätzlich das aktuelle: Genau das macht sie zu einer
Änderung durch dich und nicht durch jemanden, der den Browser offen vorfindet.
Außerdem beendet sie sofort jede andere Sitzung auf jedem anderen Gerät - und
genau darum geht es, wenn du es änderst, weil du glaubst, dass jemand anderes
eine hat.

Wenn du die Anwendung nach einem Update zum ersten Mal öffnest, bittet sie dich,
dich erneut anzumelden. Sitzungen von vor dem Update tragen keine Angabe
darüber, wann sie erteilt wurden, und auf „Ich kann es nicht sagen“ wird mit
einer Nachfrage geantwortet.

Nach zehn fehlgeschlagenen Versuchen von derselben Adresse wird die Anmeldung
für fünfzehn Minuten gesperrt, auch für richtige Passwörter.

## Der erste Start

1. Melde dich mit deiner E-Mail-Adresse und dem erzeugten Passwort an.
2. Wenn der Agent einen Cloud-Anbieter verwenden soll, speichere dessen
   Schlüssel zuerst unter **Einstellungen → API-Schlüssel**: Die Anbieterliste
   bietet nur Cloud-Anbieter an, die einen Schlüssel haben (siehe
   [API-Schlüssel](#api-schlüssel)).
3. Drücke **+** in der Seitenleiste, um deinen ersten Agenten zu erstellen.
4. Wähle seinen Anbieter und sein Modell. Für Ollama auf derselben Maschine
   stimmen die Standardwerte bereits. Um nur diesen einen Agenten über ein
   anderes Konto abzurechnen, gib ihm einen eigenen Schlüssel (siehe
   [Einem Agenten ein Modell geben](#einem-agenten-ein-modell-geben)).
5. Schreib seinen System-Prompt: wofür er da ist und was „fertig“ bedeutet.
6. Gib ihm die Werkzeuge, die er braucht. Fang mit denen für das Kanban an.
7. Drücke **Jetzt ausführen** und beobachte das Board.
8. Wenn er tut, was du willst, gib ihm einen Zeitplan.

## Die Oberfläche

Das runde blaue Logo zeigt drei Roboter-Agenten mit hellen Gesichtsplatten,
dunklen Visieren und blauen Augen, in schwarzen Anzügen, weißen Hemden und
dunklen Krawatten. Sie sind ab der Hüfte aufwärts zu sehen, mit einem größeren
Agenten in der Mitte. Das Logo erscheint auf der Anmeldeseite, in der
Seitenleiste und im Browser-Tab.

Die Seitenleiste links listet deine Agenten auf. Jeder zeigt seine ID, seinen
Namen, wie oft er gelaufen ist und wie viele Token er verbraucht hat. Jedes
Kästchen ist gleich hoch, ein langer Name wird also mit Auslassungspunkten
abgeschnitten - fahre mit der Maus darüber, um ihn ganz zu lesen. Das Quadrat
um die
ID ist grün umrandet, wenn der Agent eingeschaltet ist, und rot, wenn nicht.

**Wenn ein Agent arbeitet, wandert ein leuchtendes Segment im Uhrzeigersinn um
diesen grünen Ring.** Es zeigt dir,
dass der Agent gerade mitten in einem Lauf ist - nicht, was er tut, nur dass
er etwas tut. Es beginnt sich zu drehen, sobald du ihm eine Chatnachricht
schickst oder **Jetzt ausführen** drückst, und hält an, wenn der Lauf endet,
egal ob der Lauf von dir kam, von seinem Zeitplan oder von einer fällig
gewordenen Karte. Der Ring wird alle paar Sekunden geprüft, er kann also einen
Moment hinterherhinken.

Unten in der Seitenleiste zeigen zwei Punkte, ob die Hintergrunddienste laufen.
Ist einer davon rot, laufen keine Agenten — siehe
[Wenn etwas nicht funktioniert](#wenn-etwas-nicht-funktioniert).

Die Schaltfläche **+** erstellt einen Agenten.

## Der Agent, mit dem du anfängst

Die Installation legt genau einen an.

**`manager` (agent-000)** koordiniert die anderen. Er zerlegt Ziele in Karten
und verteilt sie. Er ist von Anfang an eingeschaltet.

Das ist mit Absicht alles: Eine Installation, die mit Agenten ankommt, um die
niemand gebeten hat, beginnt mit Dingen, die man abschalten muss. Alles andere
ist eine **Vorlage** aus dem Vorlagen-Repository oder eine `.zip`, die jemand
exportiert hat, angeboten, wenn du **+** drückst.

## Woher ein neuer Agent kommt

Drücke **+**, und du wirst gefragt, womit du beginnen willst:

| Wahl | Was sie tut |
|---|---|
| **Leerer Agent** | Kein Prompt, keine Werkzeuge, kein Zeitplan. Du schreibst ihn selbst. |
| **Aus einer .zip-Datei importieren** | Ein Agent, der über seinen Tab **Exportieren** exportiert wurde, hier oder in einer anderen Installation. |
| **Aus einer GitHub-Vorlage importieren** | Einer der Agenten aus dem Vorlagen-Repository, aus einer Liste ausgewählt. |

Der **leere Agent** steht ganz oben in der Liste, weil er die eine Antwort ist,
die immer richtig ist, und jede andere nur eine Abkürzung zu ihm ist.

### Vorlagen von GitHub

Die Vorlagen liegen in einem eigenen Repository,
[bunch-of-aigents-templates](https://github.com/nipegun/bunch-of-aigents-templates),
je ein Ordner pro Vorlage, sodass eine neue deine Installation erreicht, ohne
dass du sie aktualisieren musst. Wenn du **Aus einer GitHub-Vorlage
importieren** wählst, lädt der Server dieses Repository herunter (eine
`.tar.gz`, fünf Minuten lang aufbewahrt) und listet seine Agenten in
alphabetischer Reihenfolge auf, jeden mit seiner Beschreibung in deiner
Sprache, den Werkzeugfamilien, die er mitbringt, wie oft er aufwacht und ob er
seine Bibliothek einschaltet. Ein Werkzeug, das diese Installation nicht hat,
wird weggelassen, und die Liste sagt das. Eine Vorlage, die die Prüfungen nicht
besteht, wird nicht angeboten, und eine Zeile sagt, wie viele weggelassen
wurden.

Das sind die Vorlagen, die das Repository heute enthält:

| Vorlage | Was sie tut |
|---|---|
| **backup-watcher** | Prüft, dass deine Backups gelaufen sind, aktuell sind und nicht verdächtig klein. |
| **cert-watcher** | Warnt, wenn ein TLS-Zertifikat bald abläuft, solange noch Zeit ist. |
| **disk-cleaner** | Findet, was die Festplatte füllt, und sagt, was weg könnte. Schlägt vor; löscht nie. |
| **kanban-watcher** | Liest an jedem Werktagmorgen das Board und schreibt eine kurze Zusammenfassung. |
| **log-watcher** | Liest die Logs, auf die du ihn ansetzt, und meldet, was neu ist oder neuerdings häufig auftritt. |
| **mail-watcher** | Überwacht ein Postfach und handelt bei dem, was ankommt, nach Regeln, die du in seinen Prompt schreibst. |
| **news-watcher** | Liest die RSS-Feeds, die du in seinem Prompt aufführst, und meldet, was zu deinen Regeln passt. |
| **os-watcher** | Überwacht diese Maschine: Festplatte, Arbeitsspeicher, Swap, Last und ob die Dienste laufen. |
| **rag-consultant** | Beantwortet Fragen aus den Dokumenten seiner RAG-Bibliothek, zitiert die Stelle hinter jeder Aussage und sagt es, wenn die Dokumente etwas nicht abdecken. |
| **site-watcher** | Prüft, dass die Websites, die du aufführst, antworten, schnell antworten und noch sagen, was sie früher gesagt haben. |
| **web-navigator** | Steuert seinen eigenen Browser, um auf einer Website zu tun, worum du bittest: suchen, anmelden, ein Formular ausfüllen, sich durchklicken und berichten, was er gefunden hat. |

`web-navigator` und `rag-consultant` haben keinen Zeitplan: Sie arbeiten, wenn
du sie darum bittest, und die Bitte ist die Aufgabe. `web-navigator` ist
außerdem derjenige, der zeigt, wofür der Browser
installiert ist - er meldet sich an, klickt und füllt Formulare aus, wo die
anderen Seiten lesen. Er tippt kein Passwort ein, kauft nichts und drückt keine
Senden-Schaltfläche: Er kommt bis zu diesem Schritt und hält an und sagt,
welche Schaltfläche die Aufgabe abschließen würde.

`rag-consultant` antwortet aus seiner eigenen Dokumentbibliothek, und er ist
die einzige Vorlage, die mit eingeschalteter Bibliothek ankommt: Seine
Werkzeuge bleiben ihm vorenthalten, solange die Bibliothek aus ist. Bevor er zu
etwas taugt, lade Dokumente in seinem Tab **RAG** hoch (siehe
[Lokale Dokumentbibliotheken](#lokale-dokumentbibliotheken-rag)) und wähle ein
Modell. Jede Aussage in seinen Antworten verlinkt auf die Seite des Dokuments,
aus der sie stammt; wenn die Dokumente etwas nicht abdecken, sagt er das,
statt die Lücke zu füllen. Seine Token-Obergrenze (40.000 pro Lauf) ist höher
als die der anderen, weil die Abschnitte, die er liest, darauf angerechnet
werden.

Jede Vorlage sagt, bevor du sie auswählst, welche Werkzeugfamilien sie
mitbringt und wie oft sie aufwacht. Eine Vorlage ist ebenso sehr ein Satz von
Berechtigungen wie ein Prompt: „Überwacht ein Postfach“ verrät dir nicht, dass
sie mit der Fähigkeit ankommt, Mails zu löschen.

Jede Vorlage kommt **ausgeschaltet und ohne Modell** an: Wenn du eine wählst,
bekommst du ihren Prompt, ihre Werkzeuge und einen vorgeschlagenen Zeitplan,
und dann wartet sie darauf, dass du einen Anbieter auswählst und sie
einschaltest.

Sie sind Ausgangspunkte. Ändere den Prompt, die Werkzeuge, den Zeitplan - alles
davon -, und mehrere von ihnen sagen in ihrem eigenen Prompt, was du ausfüllen
musst, bevor sie zu etwas taugen, statt um drei Uhr morgens zu scheitern.

**Einstellungen → Agenten** zeigt, aus welchem Repository und Branch die Liste
stammt: standardmäßig dem des Projekts, oder einem Fork, oder einem eigenen mit
demselben Aufbau. Eine Maschine ohne Weg nach draußen zu GitHub kann einen
`file://`-Pfad verwenden, der `archive/refs/heads/<branch>.tar.gz` enthält,
derselbe Aufbau, den der Installer akzeptiert. Wenn das Repository nicht
erreichbar ist, sagt die Liste, welche Adresse fehlgeschlagen ist; das
Importieren einer `.zip` funktioniert weiterhin.

### Eine .zip importieren

1. Wähle die `.zip`. Sie wird in Stücken hochgeladen, mit Prozentanzeige,
   sodass auch eine Bibliothek von Hunderten MiB ankommt.
2. Der Server prüft das ganze Paket, bevor irgendetwas anderes geschieht. Nichts
   darin darf ein Pfad aus dem Home des Agenten hinaus sein, eine versteckte
   Datei wie `.ssh` oder `.bashrc`, der Chat oder das Ausführungsprotokoll oder
   ein Zeitplan, der einen Befehl mitbringt. Wenn etwas nicht stimmt, erfährst
   du, was, und es wird nichts angelegt.
3. Dir wird gezeigt, was es mitbringen würde: seine Beschreibung, seine
   Werkzeuge (und die, die dieser Installation fehlen), seine Zeitpläne und ob
   es sein Gedächtnis, Dateien für sein Home, Bibliotheksdokumente oder ein
   Modell mitbringt. Bestätige und gib ihm einen Namen.
4. Es wird im Hintergrund installiert, mit dem Fortschritt auf dem Bildschirm.
   Bibliotheksdokumente werden einzeln hochgeladen und hier neu indexiert.
   Schlägt auf halbem Weg etwas fehl, wird der Agent wieder gelöscht, statt halb
   installiert liegen zu bleiben.

Auch ein importierter Agent kommt **ausgeschaltet** an. Wenn er einen Anbieter
nennt, muss dessen Schlüssel in dieser Installation hinterlegt sein: Schlüssel
reisen nie in einer `.zip`.

Wenn du lieber gar nicht gefragt werden willst, schalte **Fragen, womit ein
neuer Agent beginnt** unter **Einstellungen → Oberfläche** aus: **+** führt
dann direkt zu einem leeren Agenten.

### Kein Agent hat root

Kein einziger, den Orchestrator eingeschlossen. Das ist das ganze
Isolationsmodell, und es lohnt sich, darüber im Klaren zu sein, weil es
entscheidet, was ein Agent wie `os-watcher` tun kann:

- **Hinschauen braucht keine Rechte.** `df`, `free`, `uptime`, `nproc`,
  `systemctl is-active` funktionieren alle als gewöhnlicher Benutzer. Ein Agent
  sieht eine Festplatte volllaufen, lange bevor sie voll ist.
- **Reparieren braucht sie meistens schon, und er hat sie nicht.** Die Prompts
  sagen ihm, genau anzugeben, was er ausführen würde, statt es zu versuchen und
  zu scheitern: Eine Karte mit „braucht root: journalctl --vacuum-size=200M
  würde etwa 1,2G freigeben“ ist mehr wert als ein gescheiterter Versuch.

Wenn du etwas automatisch reparieren lassen willst, setz diesen Befehl in die
eigene Crontab von root. Ein Agent, der auf eigene Faust beschließt, als root
Dateien zu löschen, ist keine Funktion, die sich irgendjemand um drei Uhr
morgens wünscht.

## Deinen ersten Agenten erstellen

Drücke **+**, wähle einen leeren Agenten, eine `.zip` oder eine Vorlage und gib
ihm einen Namen. Das legt auf dem Server an:

- den Linux-Benutzer `agent-001`,
- sein Home unter `/opt/boa/agents/001/`, Modus 0700,
- `info.json`, `system-prompt.md` und ein API-Token darin.

Die ID ist die niedrigste freie Nummer. `000` ist für den Orchestrator
reserviert.

Ein neuer Agent beginnt mit den Kanban-Werkzeugen und sonst nichts, und mit
vorsichtigen Obergrenzen. Er hat keinen Zeitplan, tut also nichts, bis du ihm
einen gibst oder **Jetzt ausführen** drückst.

## Mit einem Agenten sprechen

Klicke in der Seitenleiste auf einen Agenten, und du bekommst seinen Chat.
Tippe, was er tun soll, und drücke Enter; Umschalt+Enter beginnt eine neue
Zeile.

Das Eingabefeld bleibt an seinem Platz, direkt über der Statusleiste unten auf
der Seite: Nur das Gespräch darüber scrollt, es wird also nie verdeckt, und du
musst nie nach unten scrollen, um es zu erreichen. Solange es leer ist,
erinnert es dich in Grau daran, wie sich Enter verhält - oder dass der Agent
noch arbeitet -, und auf einem schmalen Handy wächst es um eine oder zwei
Zeilen, damit dieser Hinweis nie abgeschnitten wird.

Eine Nachricht ist ein Lauf: Der Agent setzt seine Werkzeuge ein, erledigt die
Arbeit und antwortet, wenn er fertig ist. Das kann Minuten dauern, daher ist
das Eingabefeld deaktiviert, während er arbeitet, und die Antwort erscheint,
wenn sie eintrifft. Jede Antwort zeigt, was sie gekostet hat, in Token und
Schritten.

Antworten werden als Markdown dargestellt - Überschriften, Tabellen, Listen,
Zitate und Codeblöcke -, weil ein Modell so schreibt. Deine eigenen Nachrichten
werden genau so angezeigt, wie du sie getippt hast. Ein Link ist nur dann ein
Link, wenn er auf http oder https zeigt; alles andere bleibt der Text, der es
war.

Das Gespräch bleibt erhalten. Die letzten zehn Wortwechsel werden dem Modell
bei jeder Nachricht erneut vorgespielt, damit der Agent weiß, worüber ihr
gesprochen habt - und deshalb kostet ein langer Verlauf pro Nachricht mehr als
ein kurzer. **Chat leeren** fängt von vorn an.

Mit einem Agenten zu sprechen zählt **nicht** gegen seine Obergrenze für Läufe
pro Tag: Diese Obergrenze gibt es, um einen unbeaufsichtigten Zeitplan zu
stoppen, nicht, um dich am Tippen zu hindern. Die Obergrenzen pro Lauf für
Token, Schritte und Zeit gelten sehr wohl.

Jeder Agent hat sein eigenes Gespräch, gespeichert in seinem eigenen
Home-Verzeichnis, und kein Agent kann lesen, was du zu einem anderen gesagt
hast.

Das Gespräch ist nicht nur das, was du getippt hast. Wenn eine der Karten des
Agenten fällig wird, wird die Karte in dem Moment, in dem der Lauf beginnt, in
genau diesen Chat gestellt, und die Antwort des Laufs erscheint darunter - wenn
du einen Agenten öffnest, siehst du also alles, worum er gebeten wurde, von dir
oder von einem anderen Agenten, und was er daraus gemacht hat. Siehe
[Wenn eine Karte läuft](#wenn-eine-karte-läuft).

### API Calls

Der Name des Agenten steht über den Tabs Chat und API Calls. Standardmäßig ist
nur **Chat** sichtbar. Um den anderen Tab anzuzeigen, öffne den
Schraubenschlüssel des Agenten, wähle **Oberfläche**, schalte **Tab API Calls
anzeigen** ein und drücke **Speichern**. Die Wahl wird für diesen Agenten auf
dem Server gespeichert. Wenn du einen Agenten öffnest oder neu lädst, beginnt
er immer bei Chat, auch wenn API Calls eingeschaltet ist.

**API Calls** zeigt das tatsächlich ausgehende JSON, einschließlich des
vollständigen Agenten-Prompts, des Gesprächs, der Werkzeugdefinitionen und der
Werkzeugergebnisse, die in dieser Anfrage gesendet wurden. Die neueste Anfrage
ist aufgeklappt; klappe einen anderen Aufruf auf, um ihn anzusehen. Neue
Aufrufe erscheinen, während der Agent läuft, einschließlich fehlgeschlagener
Anfragen, SDK-Wiederholungen und Aufrufe an sein Ersatzmodell. Einrückung und
Farben machen das JSON lesbar, ohne es als Chat darzustellen oder große
numerische Bezeichner zu runden.

Die letzten 100 vollständigen Anfragen werden getrennt vom Gespräch
aufbewahrt. Das Leeren des Chats löscht sie nicht. Die Aufzeichnung beginnt mit
dieser Version; frühere Anfragen lassen sich nicht rekonstruieren.
Authentifizierungs-Header werden nicht aufgezeichnet.

## Agenteneinstellungen

Die Überschrift zeigt **Einstellungen für Agent 001**, mit der ID des
ausgewählten Agenten. **Jetzt ausführen** erscheint nur im Arbeitsbereich, der
Chat und API Calls enthält. Um einen Agenten zu löschen, öffne **Allgemein →
Agent löschen** und bestätige seinen Namen im Dialog. Das Löschen ist ein
eigener Abschnitt unterhalb von Identität.


Der Chat ist das, was du bekommst, wenn du auf einen Agenten klickst. Alles
andere - Modell, Werkzeuge, Obergrenzen, System-Prompt, Zeitplan - liegt hinter
dem **Schraubenschlüssel** rechts im Kästchen des Agenten in der Seitenleiste.

## Einen Agenten exportieren

Der letzte Tab der Einstellungen eines Agenten, **Exportieren**, lädt ihn als
`.zip` herunter, die **+ → Aus einer .zip-Datei importieren** installieren
kann, hier oder in einer anderen Installation. Seine Konfiguration, sein
System-Prompt und seine Zeitpläne sind immer dabei. Vier Dinge kommen nur
hinein, wenn du sie ankreuzt, und jedes Kästchen sagt vorher, was es
hinzufügen würde:

| Option | Was sie hinzufügt |
|---|---|
| **Gedächtnis** | Seine `memory.md`, mit der Angabe, wie viele Zeichen sie enthält |
| **Anbieter und Modell** | Welchen Anbieter und welches Modell er verwendet. Nie den Schlüssel |
| **Bibliotheksdokumente** | Die Originale seiner Bibliothek mit ihren Informationen (Titel, Jahr...). Sie werden dort, wo sie importiert werden, neu indexiert |
| **Dateien in seinem Home-Verzeichnis** | Seine Skripte, sein Ordner `samba` und was er sonst noch in seinem Home aufbewahrt. Darin kann stehen, was du nicht teilen würdest, daher wird die Liste der Dateien vor dem Herunterladen angezeigt |

Manches kommt nie hinein, egal was du ankreuzt: API-Schlüssel, das eigene Token
des Agenten, Zugangsdaten der Kanäle, sein Chat, sein Ausführungsprotokoll,
seine Browsersitzungen und die versteckten Dateien seines Home-Verzeichnisses.
Aus seiner Crontab reisen nur die Zeitpläne, die den Agenten starten, keine
anderen Befehle, die jemand dort eingetragen hat: Eine `.zip`, die Befehle
mitbrächte, würde sie auf der Maschine ausführen, in die sie importiert wird.

## Samba-Freigaben

Jeder Agent hat in seinem Home einen Ordner `samba/`, der automatisch unter
seinem Linux-Benutzernamen freigegeben wird. Die Freigabe **agent-001** zeigt
zum Beispiel nur auf `/opt/boa/agents/001/samba/`. Wenn du den Agenten unter
Allgemein umbenennst, wird die Freigabe nicht umbenannt. Der Rest seines Home
und seine geschützte Konfiguration werden nicht freigegeben.

1. Öffne beim Agenten **Schraubenschlüssel → Samba**.
2. Gib ein **neues Samba-Passwort** mit mindestens 8 Zeichen ein, wähle die Berechtigungen und drücke **Speichern**.
3. Öffne die im Tab angezeigte Windows- oder SMB-Adresse - `\\server\agent-001` unter Windows, `smb://server/agent-001` unter Linux und macOS - und melde dich mit dem angezeigten Benutzernamen und diesem Passwort an.

Die Freigabe ist anfangs eingeschaltet, in der Freigabeliste des Servers
sichtbar und für Lese- und Schreibzugriff eingerichtet, mit ausgeschaltetem
Gastzugriff. Lege vor ihrer ersten authentifizierten Verbindung in diesem Tab
ihr Passwort fest. Ein leeres Passwortfeld bei späterem Speichern behält das
vorhandene Passwort. Samba-Zugangsdaten sind von den Linux-Anmeldedaten
getrennt; sie festzulegen entsperrt nicht das Linux-Konto des Agenten.

| Einstellung | Wirkung |
|---|---|
| Diesen Ordner freigeben | Schaltet diese Ressource ein oder aus, ohne ihre Dateien zu löschen |
| Authentifizierung | Standardmäßig Benutzername/Passwort des Agenten; Gastzugriff nur, wenn ausdrücklich ausgewählt |
| Berechtigungen | Nur Lesen oder Lesen und Schreiben über SMB; der Agent kann weiterhin mit seinen eigenen lokalen Dateien arbeiten |
| Sichtbarkeit und Beschreibung | Ob sie in der Freigabeliste des Servers erscheint, und ihre Beschreibung |
| Rechte für neue Dateien/Ordner | Oktale Unix-Modi, anfangs `0600` / `0700`; vorhandene Dateien behalten ihre Modi |

Freigabename und Pfad sind fest. Der Ordner bleibt privat für seinen
Linux-Besitzer. Wer geänderte Zugriffseinstellungen speichert, schließt die
bestehenden Verbindungen dieser Freigabe, damit sich die Clients mit den neuen
Berechtigungen neu verbinden. Die Freigaben der anderen Agenten bleiben
bestehen. Das Passwort selbst wird von der API nie zurückgegeben und nie in
`info.json` gespeichert.

`--update` fügt bestehenden Agenten Samba-Ordner und -Freigaben hinzu,
`agent-000` eingeschlossen. Das Löschen eines Agenten entfernt
seine Freigabe und sein Samba-Konto zusammen mit seinem Home. `--backup` /
`--restore` bewahren freigegebene Daten, Einstellungen, Samba-Passwörter und
Kontenidentitäten. Die Wiederherstellung prüft den gespeicherten Portmodus des
Webs, einschließlich Installationen, die 443 direkt bedienen.

Samba verwendet TCP **445**, unabhängig vom Web-Proxy. In Docker muss dieser
Port ausdrücklich veröffentlicht werden. BoA betreibt seinen eigenen Dienst
`boa-samba`, mit eigener Konfiguration und eigener Passwortdatenbank unter
`/opt/boa/samba/`; er überschreibt die Konfiguration eines anderen
Samba-Servers nicht und übernimmt sie nicht, und der Installer weigert sich,
eine bestehende Samba-Installation zu übernehmen, die er nicht verwaltet.

## Einem Agenten ein Modell geben

Wähle unter **LLMs** einen Anbieter. Die Liste ist absichtlich kurz: Sie bietet
die drei selbst gehosteten Anbieter an, die keinen Schlüssel brauchen, und
jeden Cloud-Anbieter, dessen Schlüssel unter **Einstellungen → API-Schlüssel**
hinterlegt ist. Ein Cloud-Anbieter ohne Schlüssel würde den Agenten bis zu
seinem ersten Lauf bringen und dort scheitern lassen, deshalb wird er nicht
angeboten. Hinterlege seinen Schlüssel, und er erscheint.

Ein Agent, der bereits mit einem Anbieter eingerichtet ist, sieht diesen
weiterhin in der Liste, auch wenn dessen Schlüssel entfernt wurde, markiert mit
*(kein Schlüssel eingerichtet)* - sonst würde das Feld einen Anbieter anzeigen,
den niemand gewählt hat, und ihn beim nächsten Klick speichern.

**Auf deiner eigenen Hardware.** Kein Schlüssel, und das Feld Basis-URL gibt an, wo dein eigener Server lauscht.

| Anbieter | Gelistete Modelle | Standardmodell |
|---|---|---|
| `ollama` | 23 | `gpt-oss:20b` |
| `llamacpp` | 1 | `local-model` |
| `vllm` | 3 | du gibst das Modell an |

**Unternehmen, die die Modelle ausliefern, die sie selbst gebaut haben.**

| Anbieter | Gelistete Modelle | Standardmodell |
|---|---|---|
| `anthropic` | 10 | `claude-opus-5` |
| `openai` | 16 | `gpt-5-mini` |
| `google` | 8 | `gemini-3.6-flash` |
| `deepseek` | 2 | `deepseek-flash` |
| `kimi` | 3 | `kimi-k2.6` |
| `minimax` | 8 | `MiniMax-M2` |
| `mistral` | 3 | `labs-leanstral-1-5` |
| `qwen` | 15 | `qwen3.8-max` |
| `xai` | 3 | `grok-4.3` |
| `zai` | 10 | `glm-4.5` |
| `cohere` | 2 | `command-a-reasoning-08-2025` |
| `inception` | 1 | `mercury-2` |

**Hoster und Router, die Modelle anderer ausliefern.** Ein Schlüssel erreicht viele Modelle; die Modell-ID gibt an, welches.

| Anbieter | Gelistete Modelle | Standardmodell |
|---|---|---|
| `openrouter` | 154 | `anthropic/claude-sonnet-4.5` |
| `perplexity` | 48 | `perplexity/deepseek-v4-flash-0731` |
| `cerebras` | 1 | `gpt-oss-120b` |
| `cloudflare` | 6 | `@cf/openai/gpt-oss-20b` |
| `deepinfra` | 49 | `moonshotai/Kimi-K3` |
| `fireworks` | 13 | `accounts/fireworks/models/gpt-oss-120b` |
| `groq` | 5 | `openai/gpt-oss-20b` |
| `huggingface` | 27 | `deepseek-ai/DeepSeek-V4-Flash-0731:fastest` |
| `together` | 8 | `openai/gpt-oss-120b` |
| `vercel` | 110 | `openai/gpt-oss-20b` |

Ein Anbieter braucht zwei Werte im Schlüsselfeld: **Cloudflare Workers AI**
setzt seine Adresse aus der Konto-ID zusammen, daher wird sein Schlüssel als
`account-id:api-token` geschrieben, beide Hälften aus dem Cloudflare-Dashboard.
Das Feld unter **Einstellungen → API-Schlüssel** sagt das.

Das Modellfeld schlägt vor, was dieser Anbieter ausliefert, und filtert die Liste beim Tippen - aber es ist ein normales Textfeld, sodass ein Modell, das heute Morgen erschienen ist, einfach eingetippt werden kann. Diese Vorschläge stammen aus `/opt/boa/config/providers/<provider>.json`, das du auf dem Server bearbeiten kannst; ein Update überschreibt nie eine Datei, die du geändert hast.

Selbst gehostete Anbieter brauchen nichts weiter, wenn sie auf derselben
Maschine laufen.

**Basis-URL** erscheint nur bei `ollama`, `llamacpp` und `vllm` und gibt an, wo
dein eigener Server lauscht - der Standardwert ist der übliche Port auf dieser
Maschine, was richtig ist, wenn das Modell neben der Anwendung läuft. Wählst du
einen Cloud-Anbieter, verschwindet das Feld: Diese Adresse ist fest, diese
Installation kennt sie bereits, und das Einzige, was ein Feld dort bewirken
könnte, wäre, dass ein Tippfehler einen funktionierenden Agenten kaputtmacht.
Beim Ersatzmodell ist es genauso.

Für einen Cloud-Anbieter ist der einfachste Weg der Tab **API-Schlüssel** in den Einstellungen, den dann jeder Agent mit diesem Anbieter verwendet. Um nur diesem einen Agenten einen anderen Schlüssel zu geben, schreib ihn als root in sein eigenes Home:

```bash
mkdir -p /opt/boa/agents/001/keys
echo "sk-..." > /opt/boa/agents/001/keys/anthropic.key
chown -R agent-001:agent-001 /opt/boa/agents/001/keys
chmod 700 /opt/boa/agents/001/keys
chmod 600 /opt/boa/agents/001/keys/anthropic.key
```

Der Dateiname ist der Name des Anbieters. Jeder Agent liest nur seinen eigenen
Schlüssel, sodass ein Agent nicht das Budget eines anderen ausgeben kann.

### API-Schlüssel

Die Einstellungen haben einen Tab **API-Schlüssel**: ein Schlüssel pro
Cloud-Anbieter, gemeinsam genutzt von jedem Agenten, der ihn verwendet. Die
selbst gehosteten Anbieter stehen nicht in der Liste, weil sie keinen
brauchen.

Ein Schlüssel wird in `/opt/boa/config/apikeys/<provider>.key` gespeichert. Das
Verzeichnis hat `0700` und die Dateien `0600`, beide gehören dem Web-Benutzer,
sodass kein Agent auch nur einen davon lesen kann: weder den Schlüssel eines
anderen Anbieters noch seinen eigenen. Wenn ein Agent läuft, gibt ihm die
Agenten-API den Schlüssel **für den Anbieter, mit dem dieser Agent eingerichtet
ist, und keinen anderen**: Ein Agent auf Ollama kann nicht nach dem
Anthropic-Schlüssel fragen.

Installationen, die vor der Umbenennung dieses Verzeichnisses entstanden sind,
haben ihre Schlüssel in `/opt/boa/config/keys/`; `--update` verschiebt sie und
entfernt das alte Verzeichnis.

Es lohnt sich, klar zu sehen, was das schützt und was nicht. Ein Agent, der
rechtmäßig einen kostenpflichtigen Anbieter verwendet, hält dessen Schlüssel,
während er läuft - er braucht ihn für den Aufruf, und ein Agent mit `bash.run`
könnte ihn ausgeben. Was der gemeinsame Speicher verhindert, ist, dass ein
Agent die Schlüssel von Anbietern einsammelt, die er nicht verwendet, und er
hält jeden Schlüssel aus den Home-Verzeichnissen der Agenten heraus, wo ein
einziges verirrtes Backup sie alle auf einmal preisgeben würde.

Um einen Agenten über ein anderes Konto abzurechnen, lege einen Schlüssel in
das eigene Home dieses Agenten unter `keys/<provider>.key`. Dieser hat Vorrang
vor dem gemeinsamen.

## Einen System-Prompt schreiben

Der System-Prompt ist das, was der Agent ist. Er wird als `system-prompt.md` im
Home des Agenten gespeichert, und du bearbeitest ihn in der Oberfläche.

Was funktioniert:

- **Sag, wofür der Agent da ist**, in ein oder zwei Sätzen.
- **Sag, was „fertig“ bedeutet.** Ein Agent ohne Definition von „fertig“ hört
  entweder zu früh auf oder nie.
- **Sag, was er tun soll, wenn er festsitzt.** Ohne das erfinden Modelle einen
  Weg um das Hindernis herum. „Wenn du es nicht schaffst, sag es auf dem Board
  und hör auf“ genügt.
- **Sag ihm, dass er zuerst das Board lesen soll.** Es ist das einzige
  Gedächtnis, das er zwischen den Läufen hat.

Was nicht funktioniert: ihm zu sagen, ein Werkzeug nicht zu benutzen. Wenn du
nicht willst, dass er ein Werkzeug benutzt, gib ihm das Werkzeug nicht — der
Prompt ist ein Vorschlag, die Werkzeugliste wird durchgesetzt.

## Was sich ein Agent merkt

Jeder Agent hat eine `memory.md` in seinem Home-Verzeichnis, und diese Datei
ist das Einzige, was er von einem Lauf in den nächsten mitnimmt. Er schreibt
mit `memory.append` hinein, wenn er etwas lernt, das sich zu behalten lohnt,
und räumt sie mit `memory.replace` auf.

Die ganze Datei wird zu Beginn jedes Laufs geladen, was sie nützlich macht und
zugleich Kosten verursacht: Jedes Zeichen wird bei jedem Modellaufruf bezahlt.
Unter **Agenteneinstellungen → Gedächtnis → Gedächtnislimit (Zeichen)** wählst
du ein Limit von 1.000 bis 1.000.000 Zeichen. Der Standardwert ist 8.000, auch
für bestehende Agenten. Der Agent wird gebeten, sein Gedächtnis aufzuräumen,
sobald es 75 % seines Limits überschreitet.

Der Zähler zeigt die aktuelle Anzahl und das gewählte Limit, Leerzeichen und
Zeilenumbrüche eingeschlossen. Du kannst das Limit erhöhen und im selben
Speichervorgang ein größeres Gedächtnis einfügen. Wenn der Text das gewählte
Limit überschreitet, wird nichts aus dieser Einstellungsanfrage gespeichert:
Kürze den Text oder erhöhe das Limit. Das bisherige Gedächtnis bleibt
unversehrt; neue Schreibvorgänge fügen nie `[truncated]` an. Früher verworfener
Text muss erneut aus dem Original eingefügt werden. Das ganze Gedächtnis muss
weiterhin zusammen mit Prompt, Gespräch und Werkzeugen in den Kontext des
gewählten Modells passen.

Gut zu behalten: wo etwas liegt, was ein Befehl am Ende war, was du
bevorzugst. Nicht das Tagebuch dessen, was er getan hat - das ist das Board.

Du kannst es selbst unter **Gedächtnis** in den Einstellungen des Agenten
lesen und korrigieren. Eine falsche Tatsache, nach der ein Agent immer wieder
handelt, lohnt es sich, von Hand zu korrigieren.

## Lokale Dokumentbibliotheken (RAG)

Jeder Agent hat seine eigene Bibliothek unter `/opt/boa/agents/<id>/rag/`.
Unterstützt werden PDF-, EPUB-, UTF-8-TXT- und Markdown-Dateien. Der Installer
bereitet das lokale Einbettungsmodell vor - EmbeddingGemma 300M Q8 (etwa
318 MiB), sofern kein anderes gewählt wurde (siehe
[Das Einbettungsmodell wählen](#das-einbettungsmodell-wählen)) -,
seine llama.cpp-Engine und OCR.
Extraktion, OCR, Dokument-Einbettungen und Anfrage-Einbettungen laufen auf
diesem Server. Abgerufene Abschnitte werden an den für die Antwort gewählten
Anbieter des Agenten gesendet, einschließlich Cloud-Anbietern, wenn sie
eingerichtet sind. Es gibt keinen externen Einbettungs-Endpunkt. Installation,
Updates, Dokumentimport, OCR und Sicherung/Wiederherstellung wurden auf
Debian 13 und Alpine 3.24 geprüft, einschließlich des Dienststarts nach einem
Neustart.

1. Öffne **Einstellungen → RAG** und prüfe, dass die lokale Engine bereit ist.
2. Öffne den Tab **RAG** eines Agenten, schalte den Abruf ein und speichere den
   Agenten. Die Vorlage **rag-consultant** kommt mit bereits eingeschaltetem
   Abruf.
3. Wähle Dateien und klicke auf **Dokumente hochladen**. Große Dateien reisen in
   Stücken. Alternativ kopierst du vollständige Dateien nach `rag/inbox/` und
   klickst auf **Dateien aus rag/inbox importieren**. Importierte Originale
   wandern in den verwalteten Dokumentspeicher.
4. Warte auf **Bereit**. Extraktion und Vektorisierung laufen im Hintergrund;
   andere fertige Dokumente bleiben durchsuchbar. Die Seite zeigt Fortschritt
   und Fehler.
5. Teste eine Frage mit **Bibliothek durchsuchen** oder frag den Agenten in
   seinem normalen Chat. Zitate verlinken auf die Seite des Quell-PDFs oder auf
   das ursprüngliche EPUB/Dokument.

Fehler beim Import aus `rag/inbox/` erscheinen über der Dokumentliste.
Fehlgeschlagene Originale bleiben zur Korrektur im Eingang. Die Indexierung
verarbeitet begrenzte Stapel, damit kleine Dokumente nicht zwischen jedem Buch
eine Runde des Schedulers abwarten müssen.

Die Felder unter **Dokumentinformationen** bearbeiten, in dieser Reihenfolge,
Erscheinungsjahr, Titel, Untertitel, Autor(en), Version, Sprache und
Schlagwörter. Das Jahr ist optional und nimmt bis zu vier Ziffern an. Der
Untertitel, wenn es einen gibt, wird in der Dokumentliste direkt unter dem
Titel angezeigt. Untertitel, Jahr, Autor, Version und Sprache reisen mit jedem
Abschnitt, den der Agent abruft, sodass er Dokumente mit demselben Titel
auseinanderhalten, das Zitierte datieren und zuordnen und Ausgaben
unterscheiden kann, die sich widersprechen. Beim Ersetzen einer Datei bleibt
das vorherige durchsuchbare Dokument erhalten,
bis das neue fertig indexiert ist. Wenn die lokale Einbettungsengine stoppt,
während ein Dokument indexiert wird (ein Update, ein Neustart), geht das
Dokument mit der Meldung „Local embeddings are unavailable“ zurück auf
**Eingereiht** und macht, sobald die Engine wieder antwortet, dort weiter, wo
es aufgehört hat; es muss nichts neu indexiert werden. Neu indizieren baut ein Dokument neu auf; Abbrechen stoppt
seine ausstehende Arbeit; Löschen nimmt es aus künftigen Suchen heraus. Filter
nach Sprache und Version verwenden die Metadaten, die du eingegeben hast.
EPUB-Zitate nennen Kapitel, keine erfundenen Seitenzahlen. Gescannte PDFs
brauchen auf dem Server installierte OCR-Sprachen; Englisch und Spanisch sind
standardmäßig installiert (`eng+spa`). Nicht unterstützte oder verschlüsselte
Dateien melden einen Fehler statt eines erfolgreichen leeren Index.

**Antwortmodus** entscheidet, wie weit der Agent über seine Dokumente
hinausgehen darf; die Zeile unter der Liste sagt, was der gewählte Modus tut.

- **Dokumente und Allgemeinwissen**: Der Agent darf beides verwenden, sauber
  getrennt.
- **Dokumentbelege erforderlich**: Der Agent muss die Bibliothek selbst
  durchsuchen, bevor er antwortet; eine Antwort ohne Suche wird ihm einmal
  zurückgeschickt. Hat der Lauf überhaupt keinen Abschnitt abgerufen, bekommst
  du anstelle dessen, was das Modell geschrieben hat, den festen Satz „Die
  Dokumentbibliothek enthält nicht genug Informationen, um diese Frage zu
  beantworten“.
- **Nur Dokumente (geprüft)**: wie der vorige, und zusätzlich muss jeder Absatz
  und jeder Listenpunkt der Antwort einen in diesem Lauf abgerufenen Abschnitt
  zitieren. Jeder Absatz wird geprüft: Kein Zitat, ein Zitat eines Abschnitts,
  der nicht abgerufen wurde, oder eine Bedeutung, die weit von dem zitierten
  Abschnitt entfernt ist (gemessen mit der lokalen Einbettungsengine), schickt
  die Antwort einmal mit der Liste dieser Absätze zurück. Was danach immer noch
  unbelegt ist, wird entfernt, und eine letzte Zeile sagt, wie viele Absätze
  weggefallen sind. Bleibt nichts Belegtes übrig, bekommst du den festen Satz.
  Ist die Engine für die Prüfung nicht erreichbar, wird die Antwort
  zurückgehalten, statt ungeprüft angezeigt zu werden.

Was der geprüfte Modus nicht kann, ist nachzuweisen, dass ein zitierter Absatz
genau das sagt, was sein Abschnitt sagt. In unseren Messungen erzielt ein
Absatz, der seinem Abschnitt widerspricht oder etwas zum selben Thema
hinzufügt, dieselben Werte wie ein getreuer; was die Prüfung erwischt, ist ein
Absatz, der einen Abschnitt über etwas anderes zitiert, und ein Absatz ganz
ohne Quelle. Exakt ist sie in keiner Richtung: In unseren Tests entfernte sie
etwa 6 von 100 getreuen Absätzen - meist kurze Listenpunkte und einzeilige
Zusammenfassungen, die ihr wenig zum Vergleichen bieten - und ließ weniger als
1 von 100 Zitaten eines Abschnitts zu einem anderen Thema durch. Ein
Codebeispiel wird zusammen mit dem Satz beurteilt, der es einleitet. Prüfe den
zitierten Abschnitt, wenn es auf Genauigkeit ankommt. Die festen Sätze werden
in der Sprache geschrieben, die unter **Einstellungen → Agenten → Sprache, in
der Agenten antworten** gewählt ist, und auf Englisch, wenn keine gewählt ist.
Zitate werden nur aus den Kennungen abgerufener Quellen aufgelöst.

Standardwerte pro Agent: 128 MiB pro Datei, 2.048 MiB an Originaldokumenten,
200.000 Fragmente, 8 Ergebnisse und bis zu 16.000 Zeichen abgerufenen Texts pro
Lauf. Ein vorsichtiges Byte-Budget begrenzt außerdem, was neben Prompt und
Verlauf Platz hat.
Die **Mindestähnlichkeit** beginnt bei dem Wert, der für das verwendete
Einbettungsmodell gemessen wurde - 0,20 für EmbeddingGemma, 0,35 für
Qwen3-Embedding -, und die Zeile unter dem Feld sagt, welcher das ist. Sie ist
ein Suchwert, keine Wahrscheinlichkeit, und jedes Modell hat seine eigene
Skala. Erhöhe sie, wenn die semantischen Ergebnisse zu breit sind. Wörtliche
Treffer fließen ebenfalls ein.
Die API stellt zusätzlich Fragmentkontingente und die Token-Größe der
Fragmente bereit.

Globale Einstellungen steuern die Einbettungs-Threads, die gleichzeitigen
Indexierungsaufträge und die Standard-OCR-Sprachen. **Gleichzeitige
Indexierungsaufträge** gibt an, wie viele Agentenbibliotheken gleichzeitig
indexiert werden (ein Auftrag pro Agent, seine Dokumente eines nach dem
anderen); jeder Auftrag kann bis zu 4GB RAM belegen, woran die Beschriftung
erinnert. Die Bibliothek eines einzelnen Agenten wird dadurch nicht schneller:
Die Einbettungsengine beantwortet eine Anfrage nach der anderen. Um schneller
zu vektorisieren, erhöhe stattdessen **CPU-Threads für Einbettungen**. Das
Modell wird gemeinsam genutzt; Bibliotheken und Berechtigungen gelten pro
Agent.
Die Verarbeitung wird nach Neustarts fortgesetzt und behält fertige Dokumente
und wiederverwendbare Fragmente aus unterbrochenen Aufträgen. Eine
fehlgeschlagene Neuindexierung behält die zuletzt veröffentlichte Version. Nur
die Installation des Modells braucht einen Download; der normale Abruf kann
ohne Internet laufen. Eine nicht verfügbare lokale Engine wird gemeldet, nie
durch einen externen Vektorisierungsdienst ersetzt.

`boa-embeddings` stellt das Modell über einen Unix-Socket bereit; `boa-rag`
plant die Warteschlange. Beide haben systemd- und OpenRC-Units und erscheinen in
den Systemeinstellungen. Backups enthalten die Originaldokumente, die Metadaten
und konsistente Schnappschüsse von SQLite und Vektorindex. Die
Laufzeiteinstellungen sind enthalten und mit ihnen das gewählte
Einbettungsmodell; Modell-Binaries und heruntergeladene Gewichte nicht. Eine
Wiederherstellung lädt das gewählte Modell herunter, wenn die Maschine es nicht
hat, und wenn dieser Download fehlschlägt, sagt sie das und macht weiter: Das
Modell lässt sich dann unter **Einstellungen → RAG** herunterladen oder ein
anderes wählen. Uploads, die noch laufen, werden in einem wiederhergestellten
Backup abgebrochen. Indexierte Bibliotheken überstehen ein normales Update.

### Das Einbettungsmodell wählen

Das Einbettungsmodell verwandelt jeden Abschnitt und jede Frage in die Zahlen,
nach denen die Bibliothek durchsucht wird. **Einstellungen → RAG →
Einbettungsmodell** bietet zwei an, und dasselbe dient allen Agenten:

| | EmbeddingGemma 300M (Q8) | Qwen3-Embedding 0.6B (Q8) |
|---|---|---|
| Download | 318 MiB | 610 MiB |
| Arbeitsspeicher der Engine im Betrieb | etwa 600 MB | etwa 1,1 GB |
| Indexierungszeit, gleicher Prozessor | 1× | etwa 4× |
| Lizenz | Gemma Terms of Use | Apache 2.0 |

EmbeddingGemma ist der Standard und passt zu jeder Maschine. Qwen3-Embedding
ist für eine Maschine mit Prozessor und Arbeitsspeicher übrig: Bei den
spanischen Python-Büchern der Testbibliothek hielt es Fragen zu den Büchern
(0,51-0,79) weiter von themenfremden (höchstens 0,21) entfernt als
EmbeddingGemma (0,35-0,67 gegenüber 0,17), und Absätze, die einen Abschnitt
wiedergeben, weiter von Absätzen über etwas anderes. Auf der Testmaschine mit
zwei Prozessoren brauchte es 2,2 Sekunden pro Fragment, gegenüber 0,5.

So wechselst du es:

1. Wähle das Modell in der Liste. Darunter siehst du seine Größe, seinen
   Arbeitsspeicher, seine Geschwindigkeit und seine Lizenz und ob es
   heruntergeladen ist.
2. Wenn nicht, klicke auf **Modell herunterladen** und warte, bis der Balken
   durch ist. Der Download wird vor der Verwendung gegen seinen veröffentlichten
   SHA-256 geprüft.
3. Klicke auf **Speichern** und bestätige. Die Engine startet mit dem neuen
   Modell neu; die Zeile oben zeigt einige Sekunden lang „Die Engine lädt
   dieses Modell“ und dann **Bereit**.

Was ein Wechsel in Gang setzt:

- Jedes Dokument jedes Agenten wird neu indexiert, eine Bibliothek pro
  Indexierungsauftrag, wie bei einem neuen Upload. Bei einer großen Bibliothek
  dauert das Stunden.
- Bis es an der Reihe ist, bleibt ein Dokument in der Bibliothek und wird über
  die Wörter einer Frage gefunden, nicht über die Bedeutung. Eine Suche in
  dieser Zeit sagt dem Agenten, wie viele Dokumente warten, damit ein fehlender
  Abschnitt nicht so verstanden wird, als decke die Bibliothek die Frage nicht
  ab.
- Die **Mindestähnlichkeit** jedes Agenten, der noch den empfohlenen Wert des
  alten Modells hatte, wechselt auf den des neuen. Ein Agent, bei dem du einen
  anderen Wert festgelegt hast, behält ihn.
- Der geprüfte Modus vergleicht Absätze und Abschnitte mit dem verwendeten
  Modell, gegen eine dafür gemessene Schwelle (0,36 für EmbeddingGemma, 0,44
  für Qwen3-Embedding).

Die Gewichte des vorherigen Modells bleiben auf der Festplatte, ein Zurück
braucht also keinen Download -
aber es indexiert jedes Dokument neu, das mit dem anderen indexiert wurde.

## Werkzeuge auswählen

Kreuze unter **Werkzeuge** an, was dieser Agent verwenden darf. Ein Werkzeug,
das nicht angekreuzt ist, wird dem Modell nicht gezeigt und würde vom Server
abgelehnt, selbst wenn es angefordert würde: Diese Prüfung läuft auf dem
Server, nicht im Prompt.

Das sind die Werkzeuge, die mitgeliefert werden:

| Werkzeug | Was ein Agent damit tun kann |
|---|---|
| `bash.run` | Shell-Befehle als sein eigener Benutzer ohne Sonderrechte ausführen |
| `kanban.add_card` | Eine Aufgabe auf das gemeinsame Board setzen |
| `kanban.assign_card` | Eine seiner eigenen Karten an einen anderen Agenten übergeben |
| `kanban.move_card` | Eine seiner eigenen Karten zwischen Spalten verschieben |
| `kanban.delete_card` | Eine seiner eigenen Karten entfernen |
| `kanban.list_cards` | Das Board lesen: seine eigenen Karten oder, für **manager**, alle Karten |
| `channel.write` | Eine Nachricht an einen eingerichteten Kanal senden |
| `web.fetch` | Eine öffentliche Webseite lesen |
| `rss.fetch` | Einen RSS- oder Atom-Feed als Liste von Einträgen lesen |
| `memory.append` | Etwas für sein künftiges Ich notieren |
| `memory.replace` | Aufräumen, was er sich merkt |
| `skill.read` | Einen Ablauf lesen, den er bekommen hat |
| `script.write` | Ein Skript in sein eigenes Verzeichnis `scripts/` schreiben |
| `script.list` | Die Skripte auflisten, die er geschrieben hat |
| `script.delete` | Eines seiner Skripte entfernen, samt den Cron-Zeilen, die es gestartet haben |
| `cron.add` | Eines seiner Skripte nach Zeitplan ausführen, in seiner eigenen Crontab |
| `cron.list` | Seine eigene Crontab lesen |
| `cron.remove` | Aufhören, eines seiner Skripte auszuführen |
| `mail.read` | Nachrichten aus dem eingerichteten Postfach lesen |
| `mail.move` | Eine Nachricht in einen anderen Ordner desselben Kontos ablegen |
| `mail.delete` | Eine Nachricht in den Papierkorb des Kontos verschieben |
| `mail.forward` | Eine Nachricht an eine von dir erlaubte Adresse weiterleiten |
| `rag.search` | Seine eigene Dokumentbibliothek durchsuchen |
| `rag.read` | Ein Fragment lesen, das eine Suche geliefert hat |
| `rag.list` | Die Dokumente in seiner Bibliothek auflisten |
| `browser.open` | Eine Seite in seinem eigenen Browser öffnen, mit Cookies |
| `browser.read` | Die geöffnete Seite oder ihre Links lesen |
| `browser.click` | Einen Link oder eine Schaltfläche darauf anklicken |
| `browser.type` | Ein Feld ausfüllen, wahlweise mit Absenden |
| `browser.screenshot` | Ein Bild davon für dich speichern |
| `image.send` | Ein PNG an den Webchat anhängen und an die Telegram-Antwort, wenn das Gespräch dort begonnen hat. Bilder füllen den Textbereich der Webnachricht |

Jede Familie bekommt ein eigenes Kästchen, mit der Angabe, wie viele aus dieser
Familie dieser Agent hat: „Darf dieser Agent das Postfach lesen?“ ist eine
Entscheidung, und sie wird als ein Kästchen dargestellt. Der Schalter, der das
Kanban-Board für einen Agenten einschaltet, sitzt am Fuß des Kästchens
**Kanban**, unter den Werkzeugen, die er steuert.

- **`bash.run`** — Shell-Befehle als Benutzer dieses Agenten. Er hat kein root
  und kann es auch nicht bekommen. Gib es, wenn der Agent auf der Maschine
  tatsächlich Arbeit zu erledigen hat.
- **`kanban.*`** — das gemeinsame Board. Gib allem, was sichtbar sein soll,
  mindestens `list_cards` und `add_card`.
- **`channel.write`** — Nachrichten an dich. Kreuze außerdem die Kanäle im Tab **Kanäle** an.
- **`web.fetch`** — nur öffentliche Seiten. Private und Loopback-Adressen
  werden abgelehnt.
- **`rss.fetch`** — ein RSS- oder Atom-Feed, als Liste von Einträgen statt als
  XML-Dokument. Viel billiger, als denselben Feed mit `web.fetch` abzurufen, und
  es erspart dem Agenten das Parsen. Beide liegen unter **Internet**.
- **`script.*` und `cron.*`** — unter **Automatisierung**. Der Agent schreibt
  ein Skript in sein eigenes Verzeichnis `scripts/` und plant es in seiner
  eigenen Crontab ein, für wiederkehrende Arbeit, bei der er nicht denken muss:
  Das Skript läuft von selbst, kostet keine Token, und der Agent liest die
  Ergebnisse bei seinem nächsten Lauf. Er darf nur seine eigenen Skripte
  planen, nichts häufiger als alle 5 Minuten, und er kann nie die Zeile
  anrühren, die ihn aufweckt.

Ein Agent kann innerhalb seines eigenen Home sehr viel tun und außerhalb davon
gar nichts. Er kann nicht sehen, dass ein anderer Agent existiert, geschweige
denn dessen Prompt lesen: Das Agentenverzeichnis ist durchquerbar, aber nicht
auflistbar, und jedes Home ist privat für seinen eigenen Linux-Benutzer - es
ist also der Kernel, der ablehnt, keine Prüfung in Python.

Er kann auch nicht umschreiben, **was er ist**. Seine gewährten Werkzeuge,
seine Ausgabenobergrenzen, sein System-Prompt und sein API-Token liegen in
einer Schublade in seinem Home, die root gehört: Der Agent liest sie und kann
sie nicht ändern. Du änderst sie; er nicht. Das Einzige an sich selbst, das er
bearbeiten darf, ist sein Gedächtnis.
- **`mail.*`** — das unter **Einstellungen → E-Mail** eingerichtete Postfach.
  Siehe unten.
- **`skill.read`** — die im Bereich **Fähigkeiten** angekreuzten schriftlichen
  Abläufe. Es braucht beides: das Werkzeug hier und mindestens eine Fähigkeit
  dort.

### Die Mail-Werkzeuge

Es sind vier, und sie brauchen ein IMAP-Postfach, das unter
**Einstellungen → E-Mail** eingerichtet ist. Der Agent sieht dieses Passwort
nie: Er sagt, was er erledigt haben will, und die Agenten-API, die die
Zugangsdaten hält, erledigt es.

| Werkzeug | Was es tut |
|---|---|
| `mail.read` | Liest Nachrichten. **Markiert nichts als gelesen**, sodass dein eigener Zähler ungelesener Nachrichten weiterhin bedeutet, was er bedeutet hat. |
| `mail.move` | Legt eine Nachricht in einem anderen Ordner desselben Kontos ab. Der Ordner muss existieren. |
| `mail.delete` | Verschiebt eine Nachricht in den Papierkorb des Kontos, sofern es einen gibt. |
| `mail.forward` | Leitet eine Nachricht weiter, **nur an die Adressen, die du aufgeführt hast**. |

Das letzte ist das wichtige. Ein Posteingang ist die eine Eingabe eines
Agenten, in die jeder auf der Welt schreiben kann, deshalb wird `mail.forward`
bei jeder einzelnen Weiterleitung vom Server gegen deine Liste geprüft - nicht
vom Agenten und nicht von etwas, das in seinem Prompt steht. Ist die Liste
leer, wird das Weiterleiten rundweg abgelehnt.

Gib `mail.read` allein einem Agenten, der nur beobachten soll. Füge `mail.move`
zum Ablegen hinzu, und überleg es dir zweimal, bevor du `mail.delete` und
`mail.forward` vergibst.

Das Kontrollkästchen **Kanban** unten schaltet das Board für diesen Agenten
ganz ab. Ohne Haken bekommt er überhaupt keine Kanban-Werkzeuge und legt keine
Karten mehr an - das ist der Schalter für einen Agenten, dessen Arbeit nicht
aufs Board gehört.

## Einem Agenten eine Fähigkeit geben

Eine Fähigkeit ist ein schriftlicher Ablauf: wie eine Aufgabe hier erledigt
wird, Schritt für Schritt. Mit der Anwendung wird keine ausgeliefert: Eine
Fähigkeit handelt von DIESER Maschine - diesen Hosts, diesem Backup, diesem
Zertifikat -, eine allgemeine wäre also ein Ablauf, dem niemand folgt. Du
schreibst deine eigenen auf dem Server, als root:

```bash
mkdir -p /opt/boa/skills/BackupVerification
nano /opt/boa/skills/BackupVerification/SKILL.md
chown -R root:root /opt/boa/skills
chmod 00755 /opt/boa/skills/BackupVerification
chmod 0644 /opt/boa/skills/BackupVerification/SKILL.md
```

Die Datei beginnt mit einem Namen und einer einzeiligen Beschreibung zwischen
zwei `---`-Linien, und der Rest ist der Ablauf:

```markdown
---
name: BackupVerification
description: How to check that last night's backups actually ran.
---

1. Read /var/log/backup.log ...
```

Jedes Verzeichnis unter `/opt/boa/skills/` erscheint dann als Kontrollkästchen
im Bereich **Fähigkeiten** des Agenten. Kreuze eines an, gib dem Agenten das
Werkzeug `skill.read` unter **Werkzeuge** und drücke **Speichern**. Ab seinem nächsten Lauf weiß der Agent, dass es diesen Ablauf gibt, und kann ihn
lesen, wenn die Aufgabe ansteht.

### Wozu, wenn es schon den System-Prompt gibt

Drei Gründe, und der dritte ist der, auf den es ankommt:

- **Der Prompt sagt, wofür ein Agent da ist; eine Fähigkeit, wie eine Aufgabe
  erledigt wird.** Sechs Agenten können sich einen Ablauf teilen, ohne dass
  sechs Kopien davon jede für sich veralten.
- **Eine Fähigkeit darf so lang sein, wie sie sein muss.** Ein System-Prompt
  wird bei jedem Aufruf jedes Laufs bezahlt, also muss er kurz bleiben. Eine
  Fähigkeit wird einmal bezahlt, von dem Lauf, der sie liest.
- **Was ein Agent selbst lernt, stirbt mit ihm.** Sein Gedächtnis liegt in
  einem Home, das kein anderer Agent öffnen kann. Eine Fähigkeit ist der Ort
  für das, was auch der nächste Agent wissen soll.

### Eine schreiben

Dafür gibt es in der Oberfläche absichtlich keinen Editor: Was eine Fähigkeit
sagt, geht direkt in das Denken eines Agenten ein, der um vier Uhr morgens
läuft, ohne dass jemand zuschaut, also gehört sie root, wie die Werkzeuge. Du
schreibst sie auf dem Server:

```bash
mkdir -p /opt/boa/skills/DatabaseBackup
nano /opt/boa/skills/DatabaseBackup/SKILL.md
```

Die Datei beginnt mit einem zweizeiligen Kopf und sagt dann, was immer sie
sagen muss:

```markdown
---
name: DatabaseBackup
description: How the nightly dump is taken and where it goes.
---

# Database backup

1. Dump with `mysqldump --single-transaction`, never with the table lock.
2. Write it to /srv/backups/, never to /tmp.
...
```

Die `description` ist die Zeile, auf die es am meisten ankommt. Sie ist der
einzige Teil, den jeder Lauf bezahlt, und sie ist das, wonach der Agent
entscheidet, ob er den Rest lesen will. „How the nightly dump is taken and
where it goes“ sagt ihm, wann das zutrifft; „Database stuff“ nicht.

Lade die Seite des Agenten neu, und die Fähigkeit steht in der Liste.

Ein Update rührt `/opt/boa/skills/` nie an: Was du dort schreibst, bleibt
deins. Die Weboberfläche entscheidet, welcher Agent welche Fähigkeit bekommt;
sie bearbeitet sie nicht.

### Eine Fähigkeit kann eigene Dateien mitbringen

Alles andere im Verzeichnis reist mit ihr:

```
/opt/boa/skills/DatabaseBackup/
  SKILL.md
  dump.sh
  exclude-tables.txt
```

Agenten können diese lesen und ausführen, sodass der Ablauf „führe `dump.sh`
in diesem Verzeichnis aus“ sagen kann, statt vierzig Zeilen Shell
auszubuchstabieren. `skill.read` sagt dem Agenten, welche Dateien da sind und
wo.

### Was sie kostet

Nur der Name und die Beschreibung jeder Fähigkeit kommen in den Prompt - etwa
zwei Zeilen pro Fähigkeit. Der Rumpf wird mit `skill.read` abgerufen, einmal,
von einem Agenten, der entschieden hat, dass er ihn braucht, und erst dann.
Einem Agenten fünf Fähigkeiten zu geben kostet ihn ein paar hundert Token pro
Lauf, nicht zehntausend, und deshalb kannst du ihm fünf geben, ohne an die
Rechnung zu denken.

### Wenn du eine Fähigkeit löschst, die Agenten verwenden

Nichts geht kaputt, und kein Agent verspricht am Ende etwas, das er nicht
halten kann:

- Sie **verschwindet aus dem Prompt** jedes Agenten, der sie hatte, bei dessen
  nächstem Lauf. Einem Agenten wird nie von einem Ablauf erzählt, den er nicht
  lesen kann.
- Sie **verschwindet aus dem Bereich Fähigkeiten**, sodass niemand sie erneut
  ankreuzen kann.
- Der Name **bleibt in der `info.json` des Agenten**, bis etwas sie neu
  schreibt, sodass das Zurücklegen des Verzeichnisses die Fähigkeit
  wiederherstellt, ohne dass sonst etwas zu tun ist.
- Fragt der Agent trotzdem danach - er kann sich den Namen aus einem früheren
  Lauf merken -, wird ihm gesagt, dass die Fähigkeit auf seiner Liste steht,
  aber nicht mehr installiert ist, und dass er nicht raten soll, was darin
  stand.

Eines solltest du wissen: **Wer bei diesem Agenten Speichern drückt, während
die Fähigkeit fehlt, streicht sie endgültig von der Liste.** Die Oberfläche
speichert nur Fähigkeiten, die existieren, und genau das verhindert, dass eine
gelöschte für immer hängen bleibt. Leg das Verzeichnis zurück, bevor du den
Agenten speicherst, oder kreuze die Fähigkeit danach erneut an.

## Einem Agenten einen Browser geben

`web.fetch` liest eine öffentliche Seite und sonst nichts: keine Anmeldung,
kein Formular, keine Schaltfläche. Wenn ein Agent eine Website *benutzen* statt
lesen muss, braucht er einen Browser.

Er kommt installiert: Der Installer fragt einmal, und Ja ist der Standard. Es
sind etwa 600 MB Chromium, eine Maschine mit knappem Festplattenplatz kann also
ablehnen und es sich später in beide Richtungen anders überlegen:

```bash
./install-update-reinstall-debian.sh --update --browser no    # weglassen
./install-update-reinstall-debian.sh --update --browser yes   # wieder hinzufügen
```

Die Antwort wird gespeichert, wie bei den Ports. Kreuze dann die
Browser-Werkzeuge im Bereich **Werkzeuge** des Agenten an:

Nichts davon gilt auf Alpine: Dort gibt es überhaupt keinen Browser, weil
Playwright keinen Build für musl veröffentlicht. Die Werkzeuge bleiben in der
Liste und sagen das, wenn ein Agent eines aufruft.

| Werkzeug | Was der Agent tun kann |
|---|---|
| `browser.open` | Eine Seite aufrufen. Cookies werden behalten |
| `browser.read` | Die geöffnete Seite erneut lesen, einen Teil davon oder ihre Links |
| `browser.click` | Einen Link oder eine Schaltfläche anklicken, über den sichtbaren Text oder einen Selektor |
| `browser.type` | Ein Feld ausfüllen, wahlweise mit Enter |
| `browser.screenshot` | Ein PNG in sein eigenes Download-Verzeichnis speichern |
| `image.send` | Ein PNG an die Antwort im Webchat und in Telegram anhängen |


`browser.screenshot` speichert ein PNG auf dem Server. Um es im Chat
anzuzeigen, ruft der Agent danach `image.send` mit diesem Pfad auf. Gewähre
**image.send** unter **Agenteneinstellungen → Werkzeuge → Bilder** und
speichere dann. Neue Agenten, die aus **web-navigator** erstellt werden, haben
es bereits; bestehende Agenten behalten ihre aktuellen Berechtigungen.

Das Bild füllt im Webchat den Textbereich der Nachricht, mit erhaltenem
Seitenverhältnis und voller Höhe. Es lässt sich auch in Originalgröße öffnen.
Wenn das Gespräch in Telegram begonnen hat, wird es auch dorthin geschickt.
Hohe oder große Aufnahmen werden als PNG-Dokumente zugestellt. Ein
fehlgeschlagener Upload wiederholt den fehlenden Teil, ohne Text oder Bilder zu
wiederholen, die schon angekommen sind.

Akzeptiert werden nur PNG-Dateien im Home dieses Agenten, bis zu 50 MiB pro
Datei und 16 pro Antwort. Anhänge bleiben privat und lassen sich nur mit einer
angemeldeten Sitzung ansehen. Einen vorhandenen Screenshot kannst du senden
lassen, indem du den Agenten bittest, `image.send` mit dem gespeicherten Pfad
zu verwenden.

### Jeder Agent hat seine eigenen Sitzungen

Der Browser selbst ist eine einzige Kopie, in `/opt/boa/playwright/`, die root
gehört und für alle anderen nur lesbar ist. Was **nicht** geteilt wird, ist das
Profil:

```
/opt/boa/agents/001/browser/profile/     agent-001, 0700
/opt/boa/agents/002/browser/profile/     agent-002, 0700
```

Ein Agent, der sich auf einer Website anmeldet, bleibt **bei seinem nächsten
Lauf** angemeldet, weil die Cookies auf seiner eigenen Festplatte liegen. Und
kein anderer Agent ist angemeldet, weil dieses Verzeichnis 0700 hat und seinem
Linux-Benutzer gehört - der Kernel lehnt ab, es gibt keine Prüfung in Python,
die man falsch machen könnte. Diese Trennung ist genau das, was ein gehostetes
Produkt nicht bieten kann, wenn sich alle seine Agenten eine Maschine teilen.

Sitzungscookies enden trotzdem, wenn der Browser geschlossen wird, hier wie in
jedem Browser. Was eine Website als dauerhaft markiert, bleibt erhalten.

### Was er nicht tut

- **Keine privaten Adressen.** `browser.open` lehnt `192.168.*`, `127.*` und
  den Rest ab, genau wie `web.fetch`. Ein Agent, der gerade eine feindselige
  Seite gelesen hat, darf sich nicht dazu überreden lassen, deinen Router zu
  öffnen, und ein Browser mit einer Sitzung wäre dafür ein viel besseres
  Werkzeug als ein Abruf.
- **Kein Bildschirm.** Er läuft headless. Mit `browser.screenshot` siehst du,
  was er gesehen hat; der Agent selbst kann das Bild nicht ansehen.
- **Nichts ohne die Werkzeuge.** Wie bei allem anderen ist ein Werkzeug, das
  dem Agenten nicht gegeben wurde, ein Werkzeug, das er nicht aufrufen kann,
  und diese Prüfung liegt auf dem Server.

Wenn der Browser nie installiert wurde, erscheinen die Werkzeuge trotzdem in
der Liste und antworten mit dem Befehl, der auszuführen ist. Sie verschwinden
nicht, und sie scheitern nicht stillschweigend.

## Ausgabenobergrenzen

Vier Obergrenzen, pro Agent, und jeder Lauf stoppt bei derjenigen, die er
zuerst erreicht:

| Obergrenze | Standard | Wogegen sie schützt |
|---|---|---|
| Token pro Lauf | 16384 | Ein einzelnes teures Gespräch |
| Schritte pro Lauf | 25 | Eine Schleife, die endlos Werkzeuge aufruft |
| Sekunden pro Lauf | 300 | Ein Lauf, der hängt |
| Läufe pro Tag | 48 | Eine Cron-Zeile, die zu eifrig ist |

Das ist keine Paranoia. Ein Agent, der stündlich an einer kostenpflichtigen
API aufwacht, ohne Obergrenze und ohne dass jemand zuschaut, ist eine Rechnung,
die wächst, während du schläfst.

Erhöhe sie, sobald du in seinem Bereich **Verlauf** gesehen hast, was der Agent
tatsächlich verbraucht.

### Das Ersatzmodell

Unter **LLMs** gibt es unter dem ersten einen zweiten Anbieter mit Modell. Er
wird nur verwendet, wenn der Hauptanbieter **ausfällt** - kein Schlüssel, keine
Antwort, ein Modell, das es nicht gibt -, und der Lauf macht damit ab demselben
Schritt weiter und spielt erneut ab, was bisher geschehen ist, sodass die
bereits erledigte Arbeit nicht weggeworfen wird.

Er wird **einmal pro Lauf** versucht. Scheitert auch der Ersatz, scheitert der
Lauf: Beide endlos abwechselnd zu versuchen würde bei einem Ausfall die
Obergrenzen verbrennen und am Ende trotzdem nichts vorweisen. Das Ausweichen
wird im Verlauf des Agenten festgehalten, denn ein Lauf, der still mit einem
anderen Modell antwortet und ein anderes Konto belastet, muss das sagen.

Den Ersatzanbieter auf **keiner** zu lassen ist der Standard und bedeutet, dass
ein Fehler den Lauf beendet.

Wählst du für den Ersatz **denselben Anbieter**, füllt das Modellfeld ein
*anderes* Modell aus dem Katalog dieses Anbieters ein, nicht noch einmal
dasselbe. Derselbe Anbieter mit demselben Modell kann nichts beantworten, was
der Hauptanbieter nicht konnte: Er würde jedes Mal aus genau demselben Grund
scheitern. Wenn du das Paar trotzdem wieder identisch eintippst, sagt eine
Zeile unter dem Feld das - es ist dein Agent, also ist es eine Warnung und
keine Ablehnung.


Wenn ein Lauf an seiner Token- oder Schrittobergrenze stoppt, wird der Agent
noch einmal gefragt - ohne Werkzeuge, mit einem kleinen eigenen Budget - nach
der Antwort, die er gerade geben wollte, damit ein Lauf, der sein ganzes Budget
fürs Faktensammeln verbraucht hat, nicht mit „Ich werde das System prüfen“
endet. Der Chat vermerkt das unter der Antwort, weil diese Antwort abgeschnitten
sein kann. Die Zeitobergrenze bekommt keinen solchen Aufruf: Der Lauf ist
bereits zu spät.

Dieser abschließende Aufruf schickt das ganze Gespräch erneut, ist also bei
einem langen, werkzeuglastigen Lauf nicht billig: Ein Lauf, der an einer
Obergrenze von 12000 Token gestoppt wurde, endete gemessen bei 24901. Die
Token-Obergrenze ist daher ein Budget für die Arbeit, kein hartes Maximum für
den Lauf. Auf diese Weise wird nichts ausgegeben, es sei denn, eine
Obergrenze wurde erreicht.

### Was der Kernel zusätzlich durchsetzt

Die vier Obergrenzen setzt der Lauf selbst durch. Zwei weitere setzt der Kernel
durch, sodass sie auch dann halten, wenn der Lauf selbst das ist, was schiefging:
Kein Agent darf mehr als 1024 Prozesse und Threads gleichzeitig haben, sodass
ein Befehl, der sich endlos forkt, dort stoppt und nicht erst an der Grenze der
Maschine; und auf Debian lebt jeder Lauf in einem eigenen systemd-Scope mit
2 GiB Arbeitsspeicher, der außerdem alles beendet, was der Lauf im Hintergrund
laufen ließ, wenn er fertig ist. Ein Lauf, den das Speicherlimit beendet, wird
in seinem Verlauf als fehlgeschlagen und in seinem Chat als Fehler gemeldet,
wie jeder andere. Ein Browser allein bringt schon ein paar hundert Threads
mit, deshalb ist die Zahl nicht kleiner.

## Einen Agenten planen

Schreib unter **Cron** die Crontab des Agenten. Es ist die eigene Crontab des
Agenten, die seinem eigenen Linux-Benutzer gehört und von ihm ausgeführt wird,
genau als hättest du als dieser Benutzer `crontab -e` ausgeführt.

Stündlich:

```
0 * * * * /opt/boa/venv/bin/python3 /opt/boa/webapp/backend/core/runner.py --agent-id 001
```

An jedem Werktag um 08:00:

```
0 8 * * 1-5 /opt/boa/venv/bin/python3 /opt/boa/webapp/backend/core/runner.py --agent-id 001
```

Die Oberfläche zeigt die genaue Zeile für den Agenten, den du gerade
bearbeitest, sodass du sie kopieren und nur die Zeitangabe ändern kannst.

Lass das Feld leer, um den Zeitplan zu entfernen. Nimm den Haken bei
**Eingeschaltet** heraus, um den Zeitplan zu behalten, ihn aber vom Agenten
ignorieren zu lassen.

Wenn du einen kostenpflichtigen Anbieter verwendest, dessen Preise nach Uhrzeit
schwanken — DeepSeek verlangt zu Spitzenzeiten ein Mehrfaches —, gehört diese
Entscheidung hierher.

## Das Kanban-Board

Die Seite hat zwei Tabs: **Board**, das sind die drei Spalten, und **Karte
erstellen**, das ist das Formular. Welcher offen ist, steht in der URL, sodass
ein Neuladen und die Zurück-Schaltfläche ihn beibehalten. Das Speichern einer
Karte bringt dich zurück zum Board.

Drei Spalten: **zu tun**, **in Arbeit**, **erledigt**.

Über das Board hinterlassen Agenten einander Arbeit, und über das Board siehst
du, was tatsächlich passiert ist. Jede Karte trägt ihren Verlauf: wer sie
angelegt hat, wer sie verschoben hat, wann und warum.

Eine Karte hat einen Titel und ein Feld **Was zu tun ist**. Der Titel benennt
sie; in das Feld gehören die Anweisungen, und ein Agent liest beides. Eine
Karte, die einem Agenten zugewiesen ist und deren Feld leer ist, lässt ihn
raten, und das ist der übliche Grund, warum ein Agent mit einer Karte, die man
ihm übergeben hat, nichts anfängt.

Der andere Grund ist, dass der Agent das Board überhaupt nicht sehen kann. Ein
Agent liest es, indem er `kanban.list_cards` aufruft, oder gar nicht - das
Board wird nie in seinen Prompt gestellt -, also erfährt ein Agent ohne dieses
Werkzeug nie, dass die Karte existiert. **Zuweisen an** sagt das, wenn du einen
solchen Agenten auswählst. Es ist eine Warnung, keine Sperre: Die Karte wird
trotzdem angelegt, und es genügt, das Werkzeug im Tab **Werkzeuge** des Agenten
anzukreuzen.

Eine Karte auf dem Board zeigt, wer sie angelegt hat, wer sie hat, wann sie
angelegt wurde, die ersten zwei Zeilen ihres Titels, die ersten drei dessen,
was zu tun ist, und **wann sie läuft**. Ein abgeschnittener Titel oder Text
steht vollständig in seinem Tooltip.

Diese letzte Zeile ist die, die sich zu lesen lohnt. Eine Karte ohne Uhrzeit
ist nicht verspätet: Niemand wird für sie geweckt, und ihr Agent findet sie bei
seinem nächsten geplanten Lauf. Mit **Verschieben nach** verschiebst du eine
Karte von Hand - dieses Board kennt kein Ziehen.

Du kannst jede Karte hinzufügen, verschieben und löschen. **Ein Agent sieht und
ändert nur seine eigenen**: Eine Karte gehört einem Agenten, wenn er sie
angelegt hat oder wenn sie ihm zugewiesen ist.

Das ist eine Mauer, keine Vorliebe. Ein Agent kann überhaupt nicht erfahren,
dass die Arbeit eines anderen Agenten existiert - nicht die Titel, nicht wie
viele es sind, nicht dass da überhaupt etwas ist. Bittest du einen Agenten,
eine Karte zu verschieben, die nicht seine ist, bekommt er zu hören, dass es
keine solche eigene Karte gibt; eine Karte, die nicht existiert, bekommt
denselben Satz, denn eine Ablehnung, die beides unterscheidet, wäre ein Weg,
das Board zu fragen, was darauf steht, eine ID nach der anderen.

Die Ausnahme ist **manager** (Agent 000), der Orchestrator: Seine Aufgabe ist
es, Arbeit zu verteilen und nachzuverfolgen, deshalb liest er das ganze Board.
Darum ist die Koordination seine Aufgabe und die von niemandem sonst.

Eine zerstörerische Bestätigung hat **keine Standardschaltfläche**: Sie öffnet
sich mit dem Fokus auf dem Dialog selbst, sodass Enter keines von beiden tut
und du sagen musst, was du meinst. Escape bricht ab. Klicke auf die rote
Schaltfläche, um fortzufahren.

Eine gewöhnliche Bestätigung, die nichts zerstört, öffnet sich dagegen mit dem
Fokus auf ihrer Bestätigungsschaltfläche, umrandet, und Enter bedeutet Ja.

Das Löschen einer Karte hinterlässt eine Zeile, die festhält, dass es sie gab
und wer sie gelöscht hat, sodass ein Agent die Spuren dessen, was er getan hat,
nicht verwischen kann.

## Einstellungen

Die Einstellungen sind in Tabs gruppiert, und der Tab steht in der URL, sodass
ein Neuladen oder ein Lesezeichen dort landet, wo du warst:

| Tab | Was darin ist |
|---|---|
| **Betriebssystem** | Was diese Maschine ist, wie viel Arbeitsspeicher und Festplatte übrig sind und ob die vier Dienste laufen - jeder grün, wenn aktiv, und rot, wenn nicht. Ohne Rechte gelesen, genauso wie `os-watcher` es liest |
| **Konto** | Die einzige E-Mail-Adresse und das Passwort. Zum Ändern des Passworts braucht es das aktuelle |
| **E-Mail** | SMTP, für den Fall, dass dich etwas per Mail erreichen muss |
| **Kanäle** | Discord, Mattermost, Telegram, X, in alphabetischer Reihenfolge - je ein Kästchen, mit eigenem Speichern |
| **Audio** | Transkriptionsdienst, Anbieter, Modell-Downloads, Sprache und Aufbewahrung von Telegram-Audio |
| **Werkzeuge** | Installierte Werkzeuge, gruppiert in Unter-Tabs wie Automatisierung und Browser |
| **Agenten** | Einstellungen für alle Agenten auf einmal und das Repository und der Branch, aus dem die Vorlagen kommen. Auf dem Server gespeichert: Ein von cron gestarteter Lauf hat keinen Browser, aus dem er eine Vorliebe lesen könnte |
| **Chat** | Wie sich das Nachrichtenfeld verhält: ob Enter sendet, ob jede Antwort zeigt, was sie gekostet hat |
| **Kanban** | Wie viele Karten jede Spalte zeigt und ob kürzlich gelöschte aufgeführt werden |
| **Oberfläche** | Theme, Sprache, wie lange eine Pop-up-Nachricht stehen bleibt und ob **+** fragt, womit ein neuer Agent beginnt |

Unter **Betriebssystem** stehen die Zustände der Dienste in einer Linie mit der
zweiten Spalte von **Diese Maschine**.

Die Vorlieben für Chat, Kanban und Oberfläche werden in deinem Browser
gespeichert statt auf dem Server: Sie beschreiben, wie du an diesem Gerät
arbeitest, und ein Handy und ein Desktop dürfen da durchaus unterschiedlicher
Meinung sein.

### Audiotranskription

Auf Alpine geben Installation und Updates die Kontrolle über die SSH-Sitzung zurück, wenn sie fertig sind; OpenRC hält die Dienste am Laufen.

Öffne **Einstellungen → Audio**. Diese Einstellungen werden auf dem Server gespeichert und gelten für Sprachnachrichten und Audiodateien, die über Telegram ankommen.

1. Wähle **Lokal · whisper.cpp** oder **Anbieter-API**. Die Transkription ist anfangs deaktiviert.
2. Für die lokale Erkennung wähle ein Modell und klicke bei Bedarf auf **Modell herunterladen**. Der Installer bereitet `base` vor; die Auswahl bietet alle 30 offiziellen Modelle an, einschließlich der englischen `.en`- und der quantisierten Varianten, dazu `ggml-*.bin`-Modelle, die von Hand in `/opt/boa/whisper/models/` installiert wurden. Größe und Installationszustand werden angezeigt. Größere Modelle brauchen mehr Arbeitsspeicher und CPU-Zeit.
3. Für eine API speichere zuerst ihren Schlüssel unter **API-Schlüssel**. OpenAI, Groq, Mistral, Together AI, Hugging Face und Cloudflare erscheinen, sobald ein Schlüssel gespeichert ist. Wähle einen Vorschlag oder gib eine andere Transkriptionsmodell-Kennung dieses Anbieters ein. Cloudflare bietet seine zwei unterstützten Whisper-Varianten an und verwendet Zugangsdaten der Form `account-id:api-token`.
4. Wähle die Sprache (`auto` oder einen Code wie `en`), die maximale Dauer und ob Audio zur Wiedergabe gespeichert wird; klicke auf **Speichern**. Antworte auf eine Telegram-Nachricht eines Agenten mit einer Sprachnachricht, um es auszuprobieren. Du kannst den Agenten auch vorher mit `/agents` auswählen.

Das anfängliche Limit liegt bei 600 Sekunden, einstellbar von 30 bis 3600; die empfangene Datei darf 20 MiB nicht überschreiten. Die Verarbeitung läuft im Hintergrund, und ihre Warteschlange übersteht ein Update. Ein beschäftigter Agent bekommt den gespeicherten Text, sobald er verfügbar ist. Ein Agentenname, der in der Aufnahme gesprochen wird, ändert ihr Ziel nicht.

Der Webchat zeigt das Transkript und, wenn die Aufbewahrung eingeschaltet ist, einen Player. Eine Ogg-Kopie zur Wiedergabe wird hinter der Anmeldung aufbewahrt. Wer die Aufbewahrung abschaltet, behält bei neuen Nachrichten nur den Text. Das Leeren eines Chats entfernt gespeichertes Audio abgeschlossener Aufträge. Backups enthalten dieses Audio; heruntergeladene Modelle überstehen Updates, werden aber nicht gesichert. Nach einer Wiederherstellung auf einer anderen Maschine lade jedes fehlende zusätzliche Modell unter Audio herunter.

Die lokale Erkennung verarbeitet Audio auf deinem Server. Die Erkennung per API schickt es an den gewählten Anbieter und kann Kosten verursachen, die getrennt von der Modellnutzung des Agenten anfallen. Ein lokaler Fehler wechselt nie automatisch zu einem Cloud-Anbieter. Whisper transkribiert, statt zu übersetzen; `.en`-Modelle verstehen nur Englisch. Audio kommt über Telegram herein; der Webchat zeigt das Ergebnis an, ohne eine Aufnahmeschaltfläche hinzuzufügen.

Führe bei einer bestehenden Installation den Installer deiner Distribution als root mit `--update` aus. Er installiert FFmpeg, whisper.cpp und das Modell base unter `/opt/boa/whisper/`; die Transkription bleibt deaktiviert, bis sie eingerichtet ist.

### Sprachen

Die Oberfläche gibt es in fünfzehn:

| | | |
|---|---|---|
| Deutsch (Deutschland) | English (United Kingdom) | English (United States) |
| Español (Argentina) | Español (España) | Français (France) |
| עברית (ישראל) | हिन्दी (भारत) | Italiano (Italia) |
| 日本語 (日本) | 한국어 (대한민국) | Português (Brasil) |
| Português (Portugal) | Русский (Россия) | 简体中文 (中国) |

Hebräisch wird von rechts nach links geschrieben, und seine Wahl spiegelt die
gesamte Oberfläche: Die Seitenleiste wandert nach rechts, und alles andere
folgt. Code, Pfade und Befehle bleiben von links nach rechts, und jede
Chat-Nachricht folgt ihrer eigenen Sprache, sodass eine Antwort auf Englisch
auf einer hebräischen Seite weiterhin von links nach rechts gelesen wird.

**Einstellungen → Oberfläche → Sprache** wählt eine aus, und sie wird in deinem
Browser gespeichert, wie das Theme. Ein Browser, der nie eine gewählt hat,
bekommt die nächstliegende Entsprechung zu dem, was er anfragt, und Englisch,
wenn es keine gibt.

Zwei weitere Dinge folgen der Sprache und sind **keine** Browser-Vorliebe, weil
ein von cron gestarteter Lauf keinen Browser hat:

- **Einstellungen → Agenten → Sprache, in der Agenten antworten** fügt dem
  System-Prompt jedes Agenten eine Zeile hinzu, in dieser Sprache geschrieben.
- Die **Telegram- und Discord-Bots** sprechen sie auch: ihre eigenen Sätze, den
  Bericht von `/status`
  und den Hilfetext.

## Pop-up-Nachrichten

Wenn etwas gespeichert wird, erscheint die Bestätigung mitten in dem Bereich,
den du gerade ansiehst, und verschwindet dann von selbst. Sie steht absichtlich
im Weg: Die Schaltfläche Speichern unten in einem langen Tab erzeugte früher
eine Zeile ganz oben auf der Seite, mehrere Bildschirme über der Stelle, auf
die du geschaut hast, sodass das Speichern aussah, als hätte es gar nichts
getan.

**Einstellungen → Oberfläche → Sekunden, die eine Pop-up-Nachricht stehen
bleibt** legt fest, wie lange, zwischen 1 und 30 Sekunden. Drei ist der
Standard: lang genug, um „Einstellungen gespeichert“ zu lesen, kurz genug, um
nicht über dem Feld zu liegen, in das du gerade tippen wolltest.

Fehlermeldungen ignorieren diese Zahl. Sie bleiben, bis du sie schließt, mit
dem `×` oder mit Escape, denn ein Fehler ist die eine Nachricht, die noch da
sein muss, wenn du wieder auf den Bildschirm schaust.

Die Farbe sagt, welche von drei Möglichkeiten eingetreten ist:

| Farbe | Was sie bedeutet |
|---|---|
| Grün | Es wurde gespeichert |
| Bernstein | **Keine Änderungen zu speichern** - du hast Speichern gedrückt, und im Formular hatte sich nichts geändert |
| Rot | Es ist fehlgeschlagen. Sagt, was schiefging, und wartet darauf, geschlossen zu werden |

Die bernsteinfarbene gilt überall, wo du Speichern drücken kannst:
**Einstellungen** - das Konto, der Mailserver, die API-Schlüssel, die Kanäle
und die Browser-Vorlieben - und die eigenen Einstellungen eines Agenten. Wer
zweimal Speichern drückt, bekommt das beim zweiten Mal gesagt, statt dass ein
Speichern gemeldet wird, das nicht stattgefunden hat. Ein brandneuer Agent ist
die Ausnahme: Sein Formular enthält die Werte der Vorlage und wurde nie
gespeichert, also schreibt Speichern sie und bringt dich zu seinem Chat.

## Themes

**Einstellungen → Oberfläche** wählt die Farbpalette:

| Theme | Was es ist |
|---|---|
| **Day** | Sanfte Grautöne mit helleren Karten, für einen beleuchteten Raum |
| **Night** | Die dunkle Palette, für einen dunklen Raum |
| **Day High Contrast** | Weißer Grund, fast schwarzer Text, harte Ränder. Hier ist nichts mit der Akzentfarbe gefüllt: Das Kästchen eines Agenten in der Seitenleiste ist eine Umrandung, und deine eigene Nachricht ist mit einer abgeschwächten Tintenfarbe statt mit Blau gefüllt |
| **Night High Contrast** | Fast schwarzer Grund, heller Text und harte Ränder. Der ausgewählte Agent hat eine graue Füllung; ausgewählte Tabs haben eine geschlossene Umrandung, die mit der Linie darunter verbunden ist. Deine eigenen Nachrichten verwenden gedämpftes Weiß |

Ein Browser, der nie eines gewählt hat, beginnt mit demjenigen von Day und
Night, das zum Betriebssystem passt, und folgt ihm, bis jemand eines auswählt.
Danach wird die Wahl in diesem Browser gespeichert, wie die Sprache, sodass
ein Handy und ein Desktop sich nicht einig sein müssen.

Ein Theme ist eine CSS-Datei in `frontend/themes/` auf dem Server, die die
Variablen `--colour-*` neu definiert. Eine Datei dort abzulegen fügt ein Theme
hinzu - es gibt keine Liste im Code, die aktualisiert werden müsste. Name und
Beschreibung stammen aus dem Kommentar am Anfang der Datei:

```css
/*
name: Midnight
scheme: dark
description: What it looks like, in one line.
*/

:root {
  color-scheme: dark;
  --colour-page: #101014;
  /* ... every --colour-* app.css defines ... */
}
```

Definiere sie alle. Eine Variable, die ein Theme auslässt, behält den Wert aus
app.css - was bei einem hellen Theme bedeutet, dass eine Farbe aus der dunklen
Palette mitten darin stehen bleibt.

Jedes hier mitgelieferte Theme erreicht für jede Farbe, in der es Text malt,
einen Kontrast von 4,5:1, und die beiden Hochkontrast-Themes erreichen 7:1 -
WCAG AAA. Es gibt einen Test, der fehlschlägt, wenn eines das nicht mehr tut,
gemessen an der Messlatte, die sein Name beansprucht. Ein von Hand
hinzugefügtes Theme
wird daran nicht gemessen, aber dieselbe Frage gilt auch für es: Ein Dienst,
der in einem Rot als ausgefallen markiert ist, das niemand lesen kann, ist ein
Dienst, den niemand bemerkt.

## Wenn eine Karte läuft

Eine Karte zuzuweisen ist der Weg, einem Agenten Arbeit zu geben, und es ist
ein Dienst namens **buzzer**, der daraus einen Lauf macht:

    alle paar Sekunden:
      Karten mit Besitzer, einer verstrichenen Uhrzeit und noch ohne Buzz
        -> diesen Agenten starten, es sei denn, er läuft schon
        -> den Buzz auf der Karte vermerken

**Wann** im Formular zum Hinzufügen einer Karte legt die Uhrzeit fest:

| Wahl | Was passiert |
|---|---|
| **Sofort** | Der Agent wird geweckt, sobald die Karte gespeichert ist. Der Standard: Eine Karte zuzuweisen heißt, um die Arbeit zu bitten |
| **Wenn der Agent aufwacht** | Die Karte wartet auf dem Board. Niemand wird geweckt; der Agent findet sie bei seinem nächsten eigenen Lauf |
| **Für eine bestimmte Zeit planen** | Eine Uhrzeit in UTC. Der Agent wird dann geweckt |

Ein Agent, der schon arbeitet, wird nicht unterbrochen. Die Karte behält ihren
Platz in der Reihe und wird beim nächsten Durchgang erneut versucht, sodass ein
Lauf, der für einen beschäftigten Agenten geplant ist, einige Sekunden später
startet statt gar nicht, und ein Agent nie zwei Läufe gleichzeitig hat. Eine
Karte wird einmal gebuzzt: Um sie erneut laufen zu lassen, setze ihre Uhrzeit
neu.

### Die Karte erscheint im Chat des Agenten

Wenn der Lauf beginnt, bekommt der Chat des Agenten eine Nachricht, die die
Karte nennt:

    Dir wurde eine Aufgabe auf einer Karte zugewiesen:

    Karten-ID: 1284
    Titel: Die Zertifikate erneuern
    Worum es geht: „Führe den Installer mit --update aus und berichte“
    Auszuführen: Sofort

Hat ein anderer Agent die Karte übergeben, sagt die erste Zeile, wer: *manager
hat dir eine neue Karte zugewiesen*. Wurde die Karte geplant, statt sofort
angefordert zu werden, zeigt die letzte Zeile stattdessen die Uhrzeit:
`a2026m03d31@13:45`, in UTC, dieselbe Uhrzeit, die das Board auf der Karte
zeigt.

Die Nachricht wird **geschrieben, wenn der Lauf beginnt**, nie vorher. Eine
Karte, die du für heute Nacht planst und heute Nachmittag löschst, hinterlässt
nichts im Chat, weil nie etwas gelaufen ist.

Der Agent antwortet darunter wie auf jede andere Nachricht, mit den Kosten des
Laufs. Drei Dinge können dort eine Zeile hinterlassen, ohne dass der Agent
etwas getan hat, und jede sagt, welches es war: Der Agent war ausgeschaltet, er
hatte seine Läufe für den Tag schon aufgebraucht, oder der Lauf konnte gar
nicht erst gestartet werden. Keines davon ist still, denn eine Karte, die
angekündigt und dann ignoriert wurde, sieht genauso aus wie ein Agent, der
nicht funktioniert.

Was dieser Lauf nicht tut, ist das Gespräch lesen. Seine Anweisungen sind die
Karte. Was du früher im Chat gesagt hast, wird nur erneut abgespielt, wenn du
selbst eine Nachricht schickst - sonst würde jedem geplanten Lauf ein Gespräch
berechnet, das niemand führt.

Eine Karte, die an **manager** übergeben wird, wird anders behandelt: Ihm wird
gesagt, er solle entscheiden, wer die Arbeit erledigen soll, und die Karte mit
`kanban.assign_card` weitergeben. Die Karte behält ihre ID, ihre Anweisungen
und ihren Verlauf und wechselt den Besitzer, und der Agent, bei dem sie landet,
wird für sie geweckt. Das ist Delegation - keine zweite Karte für dieselbe
Aufgabe.

## Kanäle

Richte unter **Einstellungen → Kanäle** ein, wohin Agenten schreiben können:

| Kanal | Was er braucht |
|---|---|
| Discord | ein `bot_token` und eine `channel_id`, um in beide Richtungen zu sprechen, oder eine Webhook-URL, um nur zu senden |
| Mattermost | eine Incoming-Webhook-URL |
| Telegram | `bot_token` von BotFather und `chat_id` |
| X | ein `bearer_token` |

Jeder eingerichtete Kanal zeigt **Eingerichtet** in Grün, in derselben Farbe
wie ein gespeicherter API-Schlüssel. Kanäle ohne Konfiguration behalten ihren
neutralen Status.

Die Zugangsdaten werden so gespeichert, dass **kein Agent sie lesen kann**. Ein
Agent bittet den Server zu senden; der Server liest das Token und sendet. Die
Nachricht kommt mit dem Namen des Agenten davor an, den der Server hinzufügt,
sodass kein Agent sich als ein anderer ausgeben kann.

Kreuze dann im Tab **Kanäle** jedes Agenten an, welche Kanäle er verwenden darf. Er braucht beides:
`channel.write` und den Kanal selbst.

### Einem Agenten aus Telegram antworten

Telegram und Discord sind die beiden Kanäle, die auch in die andere Richtung funktionieren. Kreuze in den Einstellungen von Telegram **Mir erlauben, Agenten
über Telegram zu antworten** an, speichere, und du kannst zurückschreiben.

Der Bot hat drei Werkzeuge in seinem Menü, und sie sind das, was die Schaltfläche `/` anbietet:

| Befehl | Was er tut |
|---|---|
| `/agents` | Listet deine Agenten als Schaltflächen auf. Tippe einen an, um mit ihm zu sprechen |
| `/status` | Dienste, Board und jeder Agent mit seinem Modell, seinen Werkzeugen und Fähigkeiten |
| `/help` | Diese drei und die beiden anderen Wege, einen Agenten zu erreichen |

### Niemand sonst sieht etwas davon

Der Benutzername des Bots ist öffentlich - jeder, der ihn findet, kann ihn
öffnen -, deshalb wird das Menü **nur für deinen Chat** geschrieben. Jemand
anderes, der denselben Bot öffnet, sieht einen leeren Chat: keine Befehle unter
`/`, keine Beschreibung, nichts zum Drücken außer der Schaltfläche Start, die
Telegram in jedem Bot zeichnet und die keine API entfernen kann.

Sie zu drücken bewirkt nichts. Der Listener vergleicht die `chat_id` jeder
Nachricht mit der in deinen Einstellungen und verwirft, was nicht passt, bevor
irgendein Befehl läuft und bevor irgendein Agent ausgewählt wird.

**Und es wird nichts aufgeschrieben.** Keine Antwort, keine Zeile im Log, kein
Vermerk, dass überhaupt jemand geschrieben hat. Die ID eines Chats, der nicht
deiner ist, sind die Daten von jemand anderem, und sie zu behalten hieße, dass
deine Installation still eine Liste derer anlegt, die den Bot gefunden haben.

Der Preis dafür ist, dass eine falsch gesetzte `chat_id` genauso aussieht wie
ein Fremder: Deine eigenen Nachrichten werden stillschweigend verworfen. Die
eingerichtete wird bei jedem Start ins Log geschrieben, und damit hast du
etwas, womit du vergleichen kannst:

```bash
journalctl -u boa-channel-telegram.service | grep "Registered"
```

Auf Debian verwenden die Kanal-Units `boa-channel-<channel>.service`. Führe den
Installer mit `--update` aus, um die alten Unit-Namen automatisch zu
migrieren. Alpine behält seine OpenRC-Namen `boa-telegram` und `boa-discord`.

Der Filter gilt pro **Chat**, nicht pro Person. Ist die `chat_id`, die du
eingerichtet hast, eine Gruppe, kann jedes Mitglied dieser Gruppe mit deinen
Agenten sprechen.

### Auswählen, mit wem du sprichst

Tippe auf `/agents`, tippe einen Agenten an, und er antwortet:

```
Agente os-watcher:

Envíame tus instrucciones...
```

Von da an **geht alles, was du schreibst, an diesen Agenten**, bis du einen
anderen auswählst. Du kannst vier Fragen hintereinander stellen, ohne jemanden
zu nennen, und genau das macht es zu einem Gespräch statt zu einer
Befehlszeile.

Drei Wege, an jemanden gerichtet zu sein, in dieser Reihenfolge:

1. **Eine Antwort auf etwas, das ein Agent gesagt hat,** geht an diesen
   Agenten, egal wer sonst ausgewählt ist. Antworte auf seine Nachricht (wische sie zur Seite, oder halte sie gedrückt bzw. klicke sie mit rechts an und wähle Antworten), dann schreib und sende.
2. **Einen nennen** - `@os-watcher check the disk` - geht an ihn *und* macht
   ihn zum ausgewählten. `@001` funktioniert auch, und ebenso ein Name mit
   Leerzeichen: `@News Miner what is new` ist ein Agent, nicht zwei Wörter.
3. **Keines von beiden** geht an den, den du zuletzt ausgewählt hast.

Nichts anderes ändert die Auswahl, sodass ein Agent nie dein Gespräch erbt,
nur weil er zufällig als Letzter gesprochen hat. Ein Agent, den du löschst, ist
nicht mehr ausgewählt, statt weiterhin alles abzufangen.

Solange du niemanden ausgewählt hast, bekommt eine Nachricht, die niemanden
nennt, die Liste der Agenten zurück, sodass nie etwas ohne Erklärung
verschwindet.

### Was zurückkommt

Der Agent antwortet in Telegram als Antwort auf das, was du geschrieben hast,
mit seinem Namen in der ersten Zeile:

```
os-watcher:
25G frei von 28G auf /, seit gestern unverändert.
```

**Und der ganze Austausch steht im Chat dieses Agenten in der
Weboberfläche**, deine Frage und seine Antwort, mit `(über Telegram)` neben der
Uhrzeit dessen, was du geschickt hast. Ein einziger Bildschirm zeigt weiterhin
alles, worum der Agent gebeten wurde, und alles, was er gesagt hat, egal auf
welchem Gerät jede Hälfte getippt wurde.

Zwei Dinge, mit denen du rechnen solltest:

- **Ein beschäftigter Agent sagt das.** Wenn er schon etwas beantwortet, wird
  dir gesagt, du sollst es gleich noch einmal versuchen, statt in eine
  Warteschlange gestellt zu werden - eine Warteschlange würde verbergen, dass
  ein Agent ins Hintertreffen gerät.
- **Nur dein Chat wird angehört.** Der Benutzername eines Bots ist öffentlich,
  und jeder, der ihn findet, kann ihm schreiben. Nachrichten aus jedem anderen
  Chat werden ohne Antwort verworfen, also entscheidet die `chat_id`, die du
  eingerichtet hast, wer mit deinen Agenten sprechen kann. Ist sie falsch,
  passiert überhaupt nichts.

Es ist Long Polling, kein Webhook: Der Server verbindet sich nach außen zu
Telegram, sodass dafür nichts zum Internet hin geöffnet werden muss.

Wenn Telegram die Antwort nicht annimmt - du hast den Bot blockiert, die
Chat-ID hat sich geändert, das Token ist nicht mehr gültig -, wird sie für
Telegram sofort verworfen, und wenn Telegram eine Stunde lang nicht erreichbar
ist, ebenfalls. Verloren geht sie nie: Das ganze Gespräch, diese Antwort
eingeschlossen, steht im Chat des Agenten in der Weboberfläche.

### Wie die Nachricht eines Agenten aussieht

Modelle schreiben Markdown, und Telegram stellt eine kleine Teilmenge von HTML
dar, daher wird beim Hinausgehen das eine ins andere übersetzt. Was ankommt,
ist formatiert, keine Sternchen:

| Was der Agent schreibt | Was du auf deinem Handy siehst |
|---|---|
| `**25G frei**` | **25G frei** |
| `` `df -h` `` | `df -h` in Festbreitenschrift |
| `# Festplattenbericht` | eine fette Zeile |
| `- Eintrag` | • Eintrag |
| eine Tabelle | ein Block in Festbreitenschrift, die Spalten ausgerichtet |
| ```` ```bash ```` | ein Codeblock |
| `[Text](https://…)` | ein Link |

Telegram hat keine eigenen Überschriften, Listen oder Tabellen, deshalb werden
diese drei zum nächsten lesbaren Ding, statt zu verschwinden.

Wenn Telegram die Formatierung je ablehnt, **wird die Nachricht erneut als
reiner Text gesendet, statt verloren zu gehen**. Die Worte bekommst du so oder
so; das Server-Log sagt, was passiert ist, sodass ein Formatierungsfehler
auffällt, statt für immer still vor sich hin zu verschlechtern.

Alles, was der Bot selbst sagt - die Agentenliste, „beantwortet gerade noch
etwas anderes“, `/status` - ist in der Sprache, die unter **Einstellungen →
Agenten** eingestellt ist, derselben, in der die Agenten antworten.

## Einem Agenten aus Discord antworten

Discord funktioniert genauso wie Telegram, mit einem eigenen Bot. Fünf Minuten
Einrichtung, einmalig.

### Den Bot anlegen

1. Öffne <https://discord.com/developers/applications> und drücke **New
   Application**. Nenn sie, wie du willst.
2. **Bot** in der Seitenleiste, dann **Reset Token**, und kopiere, was dir
   angezeigt wird. Das ist das `bot_token`, und es wird nur einmal angezeigt.
3. **OAuth2 → URL Generator**: Kreuze **bot** an und darunter **View
   Channels**, **Send Messages** und **Read Message History**. Öffne die URL,
   die daraus entsteht, und füge den Bot deinem Server hinzu.
4. Schalte in Discord selbst **Einstellungen → Erweitert → Entwicklermodus**
   ein, klicke dann mit der rechten Maustaste auf den Kanal, in dem die Agenten
   sein sollen, und wähle **Kanal-ID kopieren**. Das ist die `channel_id`.

Mehr braucht es nicht. Insbesondere brauchst du den Message Content Intent
**nicht**: Dieser Schalter ist für das Gateway, und das hier liest den Kanal
über die gewöhnliche API.

### Einschalten

Trage unter **Einstellungen → Kanäle → Discord** das Token und die Kanal-ID
ein, kreuze **Mir erlauben, Agenten über Discord zu antworten** an und
speichere. Innerhalb weniger Sekunden sagt das Log, welcher Bot lauscht und
wo:

```bash
journalctl -u boa-channel-discord.service | grep "Listening"      # Debian
tail /opt/boa/logs/boa-discord.log                # Alpine
```

Nachrichten, die geschrieben wurden, bevor du es eingeschaltet hast, werden
nicht beantwortet: Der erste Durchgang merkt sich, wo der Kanal steht, und
beginnt von dort.

### Mit einem Agenten sprechen

| Befehl | Was er tut |
|---|---|
| `!agents` | Listet deine Agenten auf und was du tippen musst, um jeden zu erreichen |
| `!status` | Dienste, Board und jeder Agent mit seinem Modell, seinen Werkzeugen und Fähigkeiten |
| `!help` | Diese drei und die anderen Wege, einen Agenten zu erreichen |

`/agents` funktioniert auch, wenn deine Finger das tippen. Hier gibt es keine
Schaltflächen und kein Slash-Befehlsmenü: Beides sind *Interactions*, die
Discord nur über eine Verbindung zustellt, die diese Installation absichtlich
nicht öffnet.

Die drei Wege, jemanden anzusprechen, kennst du schon:

1. **Eine Antwort auf etwas, das ein Agent gesagt hat,** geht an diesen
   Agenten, egal wer sonst ausgewählt ist. Rechtsklick auf seine Nachricht →
   Antworten, oder auf dem Handy wischen.
2. **Einen nennen** - `@os-watcher check the disk` - geht an ihn *und* macht
   ihn zum ausgewählten. `!os-watcher`, `@001` und `@News Miner what is new`
   funktionieren alle.
3. **Keines von beiden** geht an den, den du zuletzt ausgewählt hast.

### Was zurückkommt

Die Antwort kommt als Antwort auf deine Frage, mit dem Namen des Agenten fett
in der ersten Zeile, und **der ganze Austausch steht im Chat dieses Agenten in
der Weboberfläche**, mit `(über Discord)` neben der Uhrzeit dessen, was du
geschickt hast.

Eine lange Antwort kommt als mehrere Nachrichten an statt als eine
abgeschnittene: Discord lehnt alles über 2000 Zeichen ab, daher wird eine
Antwort zwischen den Zeilen aufgeteilt, auf höchstens vier Nachrichten. Du
kannst auf jede davon antworten, und es erreicht denselben Agenten. War es mehr
als vier Nachrichten wert, endet die letzte mit `…` - und das Ganze steht in
der Weboberfläche, wo es geschrieben wurde.

### Wer mit deinen Agenten sprechen kann

**Jeder, der in diesem Kanal schreiben kann.** Das ist der eine echte
Unterschied zu Telegram, und er ist eine Minute deiner Zeit wert: Dort
vergleicht der Bot die Chat-ID jeder Nachricht und verwirft, was nicht passt,
sodass ein Fremder, der deinen Bot findet, nichts bekommt. Hier liest der Bot
einen Kanal, und jeder, der darin posten kann, kann Läufe auf deinem Server
starten.

Setz die Agenten also in einen **privaten Kanal** - einen, den nur du oder du
und die Leute, denen du vertraust, sehen können. Der Bot braucht auf nichts
anderes Zugriff.

### Wenn du nur Benachrichtigungen willst

Lass das Token leer und hinterlege stattdessen eine **Webhook-URL**:
**Kanaleinstellungen → Integrationen → Webhooks → Neuer Webhook → Webhook-URL
kopieren**. Agenten können dann in den Kanal schreiben, und das ist alles.
Lauschen braucht den Bot, deshalb wird der Schalter bei einem Webhook
abgelehnt, statt nichts zu tun.

## Der Orchestrator

`agent-000`, genannt **manager**, ist der eine Agent, der bei der Installation angelegt wird. Er ist
in jeder Hinsicht ein normaler Agent, außer dass er nicht gelöscht werden kann.

Das vorgesehene Muster: Gib dem manager die Kanban-Werkzeuge und einen Prompt,
der ihm sagt, Ziele in Karten zu zerlegen und sie über die ID anderen Agenten
zuzuweisen. Gib den anderen Agenten `bash.run` und was sie sonst brauchen, und
einen Prompt, der ihnen sagt, an den ihnen zugewiesenen Karten zu arbeiten.

Das funktioniert nur, wenn die Karten des managers sagen, was „fertig“
bedeutet. Eine Karte, die das nicht tut, ist ein Wunsch, und der Agent, der sie
aufnimmt, entscheidet selbst.

## Der Tab Werkzeuge

**Einstellungen → Werkzeuge** zeigt, was auf dem Server installiert ist. Jede
Familie ist ein Unter-Tab - Automatisierung, Browser, Kanäle, E-Mail, Bilder,
Internet, Kanban, Gedächtnis, Betriebssystem, RAG, Fähigkeiten - mit der Anzahl ihrer Werkzeuge, und
jedes Werkzeug bekommt sein Kästchen mit seinen Argumenten und deren
Bedeutung. Der offene Tab steht in der URL
(`/settings/?tab=tools&family=mail`), sodass ein Neuladen oder ein Lesezeichen
ihn beibehält.
Alte `/tools/`-Links leiten hierher weiter und behalten die ausgewählte
Familie.

Ein Werkzeug, dessen Familie niemand benannt hat - eine `.py`, die jemand in
`/opt/boa/tools/` gelegt hat -, kommt unter **Andere**, mit seiner Familie auf
seinem eigenen Kästchen. Es ist trotzdem bis in die Oberfläche hinein ein
vollwertiges Werkzeug; es verdient sich nur keinen eigenen Tab, sonst würde die
Leiste mit jedem Einmal-Skript wachsen.

Welcher Agent welches Werkzeug verwenden darf, wird im eigenen Tab
**Werkzeuge** jedes Agenten festgelegt, nicht hier.

## Die API-Dokumentation

**API-Dokumentation** in der Seitenleiste listet jeden Endpunkt unter `/api/`
auf, nach Bereich gruppiert, mit seinen Parametern und dem, was er antwortet.
Sie wird aus der eigenen OpenAPI-Beschreibung dieser Installation erzeugt und
kann daher nicht vom Code abweichen: `openapi.json`, oben verlinkt, ist
dasselbe als Datei, die du einem Client-Generator übergeben kannst.

Sie ist in der Sprache, die du unter **Einstellungen → Oberfläche** gewählt
hast, wie der Rest der Oberfläche. Die Spezifikation selbst bleibt auf
Englisch: Feldnamen, IDs und Fehlertexte sind in diesem Projekt überall
englisch, und eine übersetzte `openapi.json` würde eine API beschreiben, die es
nicht gibt.

Die Anfragekörper werden als farbiges JSON angezeigt, so wie ein Editor sie
zeigt: Feldnamen in einer Farbe, Werte in einer anderen, und die geschweiften
Klammern und Kommas gedämpft, weil sie Gerüst sind. Die Farben kommen aus dem
Theme, das du gewählt hast, und das Kopieren eines Blocks liefert weiterhin
gültiges JSON.

Die Seite ist auch ohne Anmeldung lesbar, für sich allein ohne die
Seitenleiste. Sie beschreibt die Form der API, keine deiner Daten.

## Arbeit, bei der der Agent nicht denken muss

Manche Arbeit wiederholt sich und ist mechanisch: ein Zertifikat prüfen, ein
Log rotieren, eine Zahl einsammeln. Einen Agenten dafür aufzuwecken kostet
jedes Mal Token, um zu einem Schluss zu kommen, zu dem ein Shell-Skript
umsonst kommt.

Deshalb kann ein Agent Skripte für sich selbst schreiben und einplanen. Gib ihm
die Werkzeuge unter **Automatisierung**, und er kann:

1. `script.write` — ein Shell-Skript in sein eigenes Verzeichnis `scripts/`
   legen.
2. `cron.add` — es nach Zeitplan ausführen, in seiner eigenen Crontab.
3. Bei seinem nächsten Lauf die Ergebnisse lesen und entscheiden, was sie
   bedeuten.

Das Skript läuft als Linux-Benutzer dieses Agenten, mit denselben Rechten, die
der Agent hat, und **es kostet überhaupt keine Token** - es ist ein
Shell-Skript, kein Modellaufruf. Was Token kostet, ist, dass der Agent danach
die Ausgabe liest und entscheidet, was damit zu tun ist.

Was er nicht darf:

- Etwas anderes als seine eigenen Skripte einplanen. Ein frei formulierter
  Befehl in einer Crontab ist etwas, das hinterher niemand prüfen kann.
- Häufiger als alle 5 Minuten laufen. Ein Auftrag jede Minute ist kein
  Zeitplan.
- Die Zeile anrühren, die ihn aufweckt. Die gehört dir, in seinem Tab
  **Cron**.

Du siehst beide Hälften: die Skripte in seinem Home und die Zeilen, die sie
ausführen, im Tab Cron neben deinen eigenen.

## Wo der Bericht eines Laufs landet

Ein Lauf, den du aus dem Chat startest, antwortet dir dort. Ein Lauf, der von
einer fällig gewordenen Karte gestartet wurde, antwortet an derselben Stelle.
Ein Lauf, der von der **eigenen Crontab** des Agenten gestartet wurde,
antwortet nirgendwo im Besonderen - niemand hat ihn etwas gefragt -, deshalb:

- **Immer im Verlauf**, unter **Letzte Läufe**: was jeder Lauf gesagt hat und
  was er gekostet hat. Hier schaust du nach, wenn du dich fragst, was ein Agent
  getrieben hat.
- **Zusätzlich im Chat, wenn es sich lohnt, dich zu unterbrechen**: Der Lauf
  ist nicht zu Ende gekommen, oder er hat etwas geändert, das du sehen würdest -
  eine Karte, eine Kanalnachricht, ein Postfach. Ein Lauf, der sich nur Dinge
  angesehen hat, bleibt im Verlauf. Ein Agent mit stündlicher Crontab würde
  sonst vierundzwanzig Nachrichten „nichts zu berichten“ am Tag ins Gespräch stellen.

Über diesen Nachrichten steht, dass niemand um sie gebeten hat, und sie werden
dem Modell nie erneut vorgespielt, kosten also nichts bei deiner nächsten
Nachricht.

**Ein Lauf, der nie gestartet ist, steht ebenfalls im Verlauf**, markiert mit
„nicht gestartet“. Drücke **Jetzt ausführen** bei einem Agenten, dessen
API-Schlüssel noch nicht hinterlegt ist, oder während der Agent schon läuft,
und die Zeile im Verlauf sagt dir, welcher der beiden Fälle es war. Früher
sagte der Bildschirm, der Lauf sei gestartet, und danach erschien nie wieder
etwas, weil der Grund an eine Stelle geschrieben wurde, die nichts liest. Ein
Lauf, der nicht gestartet ist, zählt nicht zu den Läufen des Agenten für den
Tag und wird auch nicht als Fehlschlag des Agenten gezählt: Nichts davon ist
gelaufen.

## Die Statusleiste

Der Streifen am unteren Rand jeder Seite, der über die volle Breite des
Fensters läuft, auch unter der Seitenleiste, betrifft die Installation als
Ganzes:

- **Executor** und **Agenten-API**, grün, wenn sie laufen. Ist einer davon rot,
  laufen keine Agenten, und nichts anderes in der Oberfläche wird es dir sagen.
- **Agenten**: wie viele eingeschaltet sind, von wie vielen vorhandenen.
- **Board**: Karten in jeder Spalte.
- **Token heute**: alles, was seit Mitternacht UTC verbraucht wurde, über alle
  Agenten, und wie viele Läufe es dafür brauchte. Das ist die Zahl, die zeigt,
  dass ein Agent in eine Schleife geraten ist, bevor die Rechnung es tut.

Am rechten Ende des Streifens öffnen das GitHub-Logo und der Name **nipegun**
das Projekt-Repository, <https://github.com/nipegun/bunch-of-aigents>, in einem
neuen Tab. Das Konto, mit dem du angemeldet bist, wird nicht angezeigt: Eine
Installation hat immer nur eines, es anzuzeigen sagt also nichts, was du nicht
schon wüsstest.

## In welcher Sprache deine Agenten antworten

Schreib den Prompt jedes Agenten in der Sprache, in der du denkst, und er wird
in dieser antworten. Das deckt den Chat ab. Es deckt keinen Lauf ab, den die
eigene Crontab des Agenten gestartet hat: Niemand hat ihm in irgendeiner
Sprache geschrieben, und die mitgelieferten Prompts sind auf Englisch - eine
Installation, die auf Spanisch lief, bekam ihre geplanten Berichte also auf
Englisch.

**Einstellungen → Agenten → Sprache, in der Agenten antworten** behebt das für
alle Agenten auf einmal. Es fügt dem System-Prompt jedes Agenten eine Zeile
hinzu, in der gewünschten Sprache geschrieben, die besagt, dass sie Vorrang
vor allem hat, was der Prompt über Sprachen sagt. Belässt du es beim
Standard, ändert sich nichts: Jeder Agent antwortet in der Sprache seines
eigenen Prompts.

Es wird auf dem Server gespeichert, anders als die Sprache dieser Oberfläche,
die eine Vorliebe in deinem Browser ist. Ein von cron geweckter Lauf hat keinen
Browser.

## Prompts in deiner eigenen Sprache schreiben

Schreib den System-Prompt in der Sprache, in der du denkst. Nichts im System
ist an Englisch gebunden: Der Prompt, das Gedächtnis, der Chat, die
Kartentitel und die Nachrichten zwischen den Diensten sind alle durchgehend
UTF-8, Umlaute und Akzente inklusive.

Der Standard-Prompt, den ein neuer Agent bekommt, ist auf Englisch, und seine
letzte Regel sagt dem Agenten, in der Sprache zu antworten, in der sein Prompt
geschrieben ist. Schreib das Ganze in deiner Sprache neu, und diese Regel geht
mit - der Agent folgt dem Prompt, den er hat, nicht dem, mit dem er
angefangen hat.

Prompts werden mit ganzen Zeilen gespeichert, nicht an einer festen Spalte
umbrochen. Das Textfeld bricht sie auf dem Bildschirm um, damit sie lesbar
bleiben, ohne die Zeilenumbrüche in die Datei zu schreiben: Eine Regel, die
ein Satz ist, bleibt eine Zeile, und sie zu bearbeiten heißt nicht, einen
Absatz neu umzubrechen.

## Sichern und Wiederherstellen

Alles, was diese Installation zu deiner macht, liegt unter `/opt/boa/` und in
den Linux-Benutzern der Agenten. Ein Befehl sammelt es in einem Archiv:

```bash
./install-update-reinstall-debian.sh --backup
```

Er schreibt `/root/boa-backup-<date>.tar.gz`, nur für `root`, Modus 0600,
während die Dienste laufen - nichts wird angehalten. Übergib einen Pfad, um es
woanders hinzuschreiben: `--backup /mnt/usb/boa.tar.gz`. Darin: beide
Datenbanken, kopiert über die eigene Backup-API von SQLite, sodass nichts
verloren geht, was noch in einem Write-Ahead-Log steht; die Anbieterschlüssel,
die Geheimnisse der Kanäle und das Sitzungsgeheimnis; die Zertifikate; jeder
Agent mit seinem Home, seinen geschützten Dateien, seinem Linux-Benutzer und
seiner Crontab; die Fähigkeiten und Werkzeuge, die auf diesem Server
geschrieben wurden; und das Installationslog, wegen des Passworts darin. Nicht
darin: der Code, die Python-Umgebung, der Browser und die zwei eigenen
Entscheidungen dieser Maschine - der Portmodus und ob sie einen Browser hat -,
damit eine Wiederherstellung nie die einer anderen Maschine übernimmt.

**Bewahre es so privat auf wie die Maschine.** Es enthält jeden API-Schlüssel,
jedes Kanal-Token und das Anmeldepasswort.

Zum Wiederherstellen, auf dieser Maschine oder auf einer neuen:

```bash
./install-update-reinstall-debian.sh --install       # nur auf einer neuen Maschine
./install-update-reinstall-debian.sh --restore /root/boa-backup-<date>.tar.gz
```

Es verlangt ein YES oder nimmt `--yes`. Dann stoppt es die Dienste, legt die
Agentenbenutzer mit denselben Namen neu an, und mit denselben IDs, wenn diese
frei sind, ersetzt die Datenbanken, die Schlüssel, die Zertifikate, die
Agenten, die Fähigkeiten und die Werkzeuge durch die aus dem Archiv,
installiert die Crontabs und startet alles. Melde dich mit der E-Mail-Adresse
und dem Passwort des Backups an: Beide werden an `/opt/boa/logs/install.log`
unter der Überschrift `Credentials of the restored
backup` angehängt, und das ganze Log des Backups wird daneben als
`install.log.restored-<date>` aufbewahrt.

Ein Agent, den diese Maschine hatte und das Backup nicht, behält sein Home auf
der Festplatte und verschwindet aus der Oberfläche, weil die Liste der Agenten
in der wiederhergestellten Datenbank steht. Auf Alpine sind es dieselben zwei
Flags an `install-update-reinstall-alpine.sh`.

## Dienste

| Dienst | Läuft als | Was er tut |
|---|---|---|
| `boa-proxy` | `boa` | HAProxy: terminiert TLS auf 11443, leitet 11080 weiter und bedient die Web-Ports |
| `boa-web` | `boa` | Die Weboberfläche und die API, auf einem Unix-Socket hinter dem Proxy |
| `boa-exec` | `root` | Legt Benutzer an, installiert Crontabs, startet Läufe der Agenten |
| `boa-samba` | `root` | Authentifiziert SMB-Benutzer und stellt jeden Ordner samba/ als dessen Agentenbenutzer bereit |
| `boa-agent-api` | `boa` | Die Tür, durch die Agenten das Board und die Kanäle erreichen |
| `boa-buzzer` | `boa` | Überwacht das Board und weckt einen Agenten, wenn eine Karte fällig wird |
| `boa-embeddings` | `boa` | Stellt das lokale Einbettungsmodell der Dokumentbibliotheken bereit, auf einem Unix-Socket |
| `boa-rag` | `boa` | Plant die Indexierungswarteschlange der Dokumentbibliotheken |
| `boa-channel-telegram.service` | `boa` | Lauscht auf Telegram, damit du einem Agenten von deinem Handy aus antworten kannst |
| `boa-channel-discord.service` | `boa` | Dasselbe für einen Discord-Kanal |

```bash
systemctl status boa-proxy boa-web boa-exec boa-agent-api boa-buzzer \
                 boa-embeddings boa-rag \
                 boa-channel-telegram.service boa-channel-discord.service boa-samba
journalctl -u boa-exec -f
```

Die Kanal-Units auf Debian verwenden `boa-channel-<channel>.service`. Ein
Update mit `--update` stoppt und deaktiviert die alten Kanal-Units, bevor es
die neuen aktiviert.

Auf Alpine laufen dieselben Prozesse; seine Kanaldienste bleiben
`boa-telegram` und `boa-discord`. Es sind OpenRC-Dienste, überwacht von
`supervise-daemon`, und was jeder ausgibt, landet in einer eigenen Datei unter
`/opt/boa/logs/`, wöchentlich rotiert:

```bash
rc-status
rc-service boa-exec status
tail -f /opt/boa/logs/boa-exec.log
```

## Sicherheit

Der Entwurf geht davon aus, dass ein Agent früher oder später etwas tut, das
du nicht beabsichtigt hast, weil er ein Sprachmodell mit einer Shell ist.

- **Jeder Agent ist ein eigener Linux-Benutzer**, und sein Home hat `0700`.
  Agenten können die Dateien, Prompts oder API-Schlüssel der anderen nicht
  lesen.
- **`/opt/boa/agents/` hat `0711`**, sodass kein Agent auch nur auflisten kann,
  welche anderen Agenten existieren.
- **Kein Agent läuft je als root.** Nur `boa-exec` tut das, und er akzeptiert
  über einen Unix-Socket eine geschlossene Liste von Operationen. Ein „führe
  diesen Befehl aus“ ist nicht darunter.
- **Ein Lauf wird vom Kernel begrenzt, nicht nur von seinen Obergrenzen.** Kein
  Agent darf mehr als 1024 Prozesse und Threads haben, sodass eine Fork-Bombe
  an dieser Zahl stoppt; auf Debian lebt jeder Lauf in einem eigenen
  systemd-Scope mit 2 GiB Arbeitsspeicher, der außerdem alles beendet, was der
  Lauf laufen ließ, wenn er fertig ist.
- **Agenten sehen nie die Zugangsdaten der Kanäle.** Ein Bot-Token ist keine
  Nachricht: Es ist die dauerhafte Befugnis, alles zu senden, was dieser Bot
  senden kann. Agenten bitten die Agenten-API zu senden, und sie sendet.
- **Agenten fassen nur ihre eigenen Karten an.** Siehe
  [Das Kanban-Board](#das-kanban-board).
- **`web.fetch` lehnt private Adressen ab**, prüft die aufgelöste IP und prüft
  bei jeder Weiterleitung erneut, sodass einem Agenten, der eine feindselige
  Seite liest, nicht befohlen werden kann, dein internes Netz aufzurufen.

Es ist für ein LAN gedacht und sollte nicht dem Internet ausgesetzt werden.

## Wenn etwas nicht funktioniert

**Ich habe `--ports direct` gewählt, und das HAProxy der Maschine ist weg.** Es
ist nicht weg, es ist stillgelegt: gestoppt, auf Alpine aus jedem Runlevel
entfernt, auf Debian deaktiviert und maskiert, und seine
`/etc/haproxy/haproxy.cfg` gelöscht, wenn der Installer sie geschrieben hatte,
oder als `haproxy.cfg.before-boa.<date>` aufbewahrt, wenn du es warst. In
diesem Modus bindet die Anwendung 80 und 443 selbst, und alles andere, was
diese Ports belegt, hindert sie überhaupt am Starten - ein eingeschaltet
gelassener Proxy würde sie beim nächsten Booten belegen, bevor die Anwendung
überhaupt läuft. Das Paket `haproxy` ist absichtlich noch installiert:
`boa-proxy` ist `/usr/sbin/haproxy`, und in diesem Modus bedient es 80 und 443.

Um zurückzukehren, führe den Installer mit `--update --ports proxied` aus: Er
hebt die Maskierung der Unit auf, schreibt die Konfiguration der Maschine neu
und startet sie. Deine alte Datei, falls es eine gab, liegt weiterhin daneben
unter ihrem `before-boa`-Namen.

**`boa-proxy` startet immer wieder neu, und nichts lauscht auf 11443.** Lies
`/opt/boa/logs/boa-proxy.log`. Steht dort `Cannot raise FD limit to 4131`, ist
das harte Limit dieser Maschine für Dateideskriptoren niedriger als das, was
der Proxy angefordert hat - meistens ein kleiner Container. Eine Installation
von vor der Behebung hat noch `maxconn 2048` in
`/opt/boa/config/haproxy.cfg`. Den Installer mit `--update` auszuführen
schreibt die Datei neu; um es sofort zu beheben:

```bash
sed -i 's/^  maxconn 2048$/  fd-hard-limit 4000/' /opt/boa/config/haproxy.cfg
rc-service boa-proxy restart        # systemctl restart boa-proxy auf Debian
```

HAProxy bemisst sich dann nach den Deskriptoren, die es tatsächlich bekommen
kann, was bei einem harten Limit von 4096 etwa 1987 Verbindungen sind - weit
mehr, als das hier je braucht.

**Der Installer endet mit „Everything is in place but the application does
not answer“.** Die Installation ist da, und eine Seite kam nie zurück. Das Log
enthält den Grund bereits:

```bash
sed -n '/Why it did not answer/,$p' /opt/boa/logs/install.log
```

Dieser Block zeigt, wie die Maschine in diesem Moment aussah: was curl aus der
Anfrage gemacht hat, ob etwas auf dem Port lauscht, den Zustand aller zehn
Dienste und die letzten Zeilen dessen, was der Proxy und die Webanwendung
ausgegeben haben. `000` ist kein HTTP-Code - es ist curl, das sagt, dass es nie
einen bekommen hat. Ein Dienst, der sich neben `nothing is listening on port
11443` als `started` bezeichnet, ist ein Prozess, der stirbt und alle paar
Sekunden neu gestartet wird, und sein eigenes Log, ein paar Zeilen weiter
unten, sagt, warum.

Ein Update, das hier gescheitert ist, hat die vorherige Version bereits
wiederhergestellt und lässt sie laufen. Eine Erstinstallation hat nichts, zu
dem sie zurückkehren könnte, also lässt sie alles an Ort und Stelle: Behebe,
was der Block nennt, und führe den Installer erneut mit `--update` aus.

**Der Installer bricht mit „systemd is not running“ ab.** Er weigert sich, auf
einer Maschine zu installieren, auf der systemd nicht PID 1 ist, weil jeder
Dienst, den er schreibt, eine systemd-Unit ist und es nichts gäbe, was sie
starten könnte. Ein normales Debian ist in Ordnung; ein Container nicht, es sei
denn, er wurde dafür angelegt, systemd auszuführen:

```bash
apt-get install -y systemd systemd-sysv dbus dbus-user-session
```

und lege den Container dann mit `/sbin/init` als Befehl neu an - ein Container,
der schon läuft, kann seine PID 1 nicht ändern. Auf Alpine stellt sich das
nicht: Dieser Installer fügt OpenRC selbst hinzu, wenn die Maschine keins hat.

**Nichts passiert, wenn ich Jetzt ausführen drücke.** Schau dir die zwei Punkte
unten in der Seitenleiste an. Wenn `Executor` rot ist:

```bash
systemctl status boa-exec
journalctl -u boa-exec -n 50
```


**Der Browser zeigt 503, und die Dienste laufen alle.** Das HAProxy der
Maschine hat das Backend als down markiert. Fast immer ist das `option
ssl-hello-chk` an diesem Backend: Dessen ClientHello ist älter als TLS 1.2, und
die Anwendung verlangt es. Entferne diese Zeile und lade HAProxy neu.

**Ein Agent läuft, tut aber nichts.** Sieh in seinem Bereich Verlauf nach.
Führe ihn dann von Hand aus und schau zu:

```bash
runuser -u agent-001 -- /opt/boa/venv/bin/python3 \
  /opt/boa/webapp/backend/core/runner.py --agent-id 001
```

Füge `--dry-run` hinzu, um zu sehen, was er laden würde — Anbieter, Werkzeuge,
Obergrenzen —, ohne das Modell aufzurufen.

**Er sagt, dass er das Modell nicht erreicht.** Prüfe bei selbst gehosteten
Anbietern, ob der Server läuft und die Basis-URL stimmt. Prüfe bei
Cloud-Anbietern, ob die Schlüsseldatei im Home des Agenten existiert und
diesem Agenten gehört.

**Er sagt, dass ihm ein Werkzeug nicht zur Verfügung steht.** Das Werkzeug ist
auf der Seite dieses Agenten nicht angekreuzt. Der Prompt kann das nicht
aushebeln, und genau darum geht es.

**Es erscheinen keine Karten mehr.** Entweder ist das Kontrollkästchen Kanban
für diesen Agenten nicht angekreuzt, oder `Agenten-API` ist unten in der
Seitenleiste rot:

```bash
systemctl status boa-agent-api
```

**Ich will alles sehen, was ein Agent getan hat.** Sein Protokoll liegt in
seinem eigenen Home:

```bash
cat /opt/boa/agents/001/runs.jsonl
```

Ein JSON-Objekt pro Zeile: wann er gelaufen ist, was er verbraucht hat, ob er
fertig geworden ist.

## Lizenz

MIT. Siehe [LICENSE](../LICENSE).
