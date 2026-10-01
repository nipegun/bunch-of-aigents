# CODE.md

Technische Referenz für Bunch of AIgents. Geschrieben, um gezielt gelesen zu
werden: Spring zu dem Abschnitt, den du brauchst, statt alles von vorn bis
hinten zu lesen.

## Inhalt

1. [Architektur und Designentscheidungen](#1-architektur-und-designentscheidungen)
2. [Modulübersicht](#2-modulübersicht)
3. [Index der wichtigsten Symbole](#3-index-der-wichtigsten-symbole)
4. [Hauptabläufe](#4-hauptabläufe)
5. [Übersicht der Einstiegspunkte und Routen](#5-übersicht-der-einstiegspunkte-und-routen)
6. [Auswirkungsanalyse](#6-auswirkungsanalyse)
7. [Erweiterungspunkte](#7-erweiterungspunkte)

---

## 1. Architektur und Designentscheidungen

Das ist der Teil, der sich nicht aus dem Code ableiten lässt, also der Teil,
der das Lesen lohnt.

### Die Prämisse

Ein Agent ist hier ein Sprachmodell mit einer Shell auf einem Server, von Cron
geweckt, ohne dass jemand zusieht. Jede strukturelle Entscheidung folgt daraus,
das ernst zu nehmen: Das Modell wird irgendwann etwas Unbeabsichtigtes tun,
also lautet die Frage nicht, wie man das verhindert, sondern was es erreichen
kann, wenn es passiert.

### Ein Linux-Benutzer pro Agent

Agent `007` ist der Systembenutzer `agent-007`, dem `/opt/boa/agents/007/` mit
Modus `0700` gehört. Die Isolation zwischen Agenten leistet der Kernel, nicht
eine in Python geschriebene Sandbox. Ein Agent kann den System-Prompt, das
Journal oder den API-Schlüssel eines anderen Agenten nicht lesen, weil das
Dateisystem es so sagt.

`/opt/boa/agents/` selbst ist `root:root 0711`: durchquerbar, nicht auflistbar.
Ein Agent kann die anderen Agenten nicht aufzählen, nur an Pfaden scheitern,
die er errät.

Diese Entscheidung ist der Grund, warum `bash.run` keine Allowlist braucht.
Eine Blocklist für eine Shell ist Theater – alles, was `sh` ausführen kann,
kann auch ausführen, was die Liste nennt –, während ein Benutzerkonto eine
Grenze ist, die der Kernel durchsetzt.

### Was ein Agent an sich selbst nicht umschreiben darf

Das Home-Verzeichnis gehört dem Agenten, 0700, und genau darum geht es: Sein
Gedächtnis, sein Journal, sein Gespräch und jedes Skript, das er schreibt,
liegen dort. Drei Dateien darin zu ändern ist nicht seine Sache, und sie
liegen AUSSERHALB des Home-Verzeichnisses, in `/opt/boa/agents-config/xxx/`,
das `root:agent-xxx 0750` unter einem Elternverzeichnis `root:root 0711` ist.

| Datei | Warum sie nicht dem Agenten gehört |
|---|---|
| `info.json` | Welche Werkzeuge ihm gewährt wurden und was er ausgeben darf |
| `system-prompt.md` | Die Definition dessen, was er tun soll |
| `api-token` | Womit er sich gegenüber der Agenten-API ausweist |

Was das funktionieren lässt, ist nicht der Besitzer der Dateien, sondern der
des Verzeichnisses. Das Schreibrecht auf ein Verzeichnis entscheidet, ob eine
Datei darin gelöscht und ersetzt werden kann; ein Agent, dem das Verzeichnis
gehörte, könnte also `info.json` löschen und seine eigene schreiben, egal wem
die Datei gehörte. Dieses hier darf er betreten und lesen, und er darf darin
nichts anlegen, umbenennen oder löschen.

**Und diese Regel gilt für die Schublade genauso wie für ihren Inhalt**,
weshalb diese Dateien nicht mehr in `agents/xxx/config/` liegen. Dieser Pfad
war ein Eintrag im HOME-Verzeichnis, das Home-Verzeichnis gehört dem Agenten
mit 0700, und einen Eintrag umzubenennen braucht Schreibrecht auf das
Elternverzeichnis und sonst nichts – der Modus dessen, was umbenannt wird,
wird nie geprüft. Der Agent konnte also `info.json` nicht bearbeiten, aber
das hier tun:

    mv ~/config ~/config-old && mkdir ~/config && echo '...' > ~/config/info.json

und wurde dann aus dem Ersatz gelesen. Die Schublade aus dem Home-Verzeichnis
zu verlegen stellt jedes Verzeichnis auf dem Weg unter root. Aus dem Umzug
folgen zwei Dinge:

  - **Es gibt keinen Rückfall auf das Home-Verzeichnis mehr.** Früher gab es
    einen, damit ein Update kein Dienst war, der nicht mehr antwortete, bevor
    die Migration lief – und er war selbst eine Umgehung, denn es reichte, die
    echte Datei zu verstecken, damit stattdessen die des Agenten gelesen
    wurde. Der Daemon migriert jetzt beim Start, und zusätzlich tut es der
    Installer, es bleibt also nichts abzudecken.
  - **Einen Agenten zu löschen löscht auch seine Konfiguration.** Sie liegt
    nicht mehr in dem Home-Verzeichnis, das `userdel --remove` mitnimmt, und
    bliebe sie zurück, bekäme sie der nächste Agent mit dieser ID.

`fOpenProtectedAgentFile` ist die zweite Antwort auf dieselbe Frage: Sie
öffnet mit `O_NOFOLLOW` und prüft an der GEÖFFNETEN DATEI, dass sie eine
reguläre Datei ist, root gehört und von niemandem sonst beschreibbar ist. Das
übersteht ein irrtümliches chmod während eines Updates oder eine
Wiederherstellung aus einem Backup mit falschem Besitzer.

Das wurde gemessen, bevor es behoben wurde, auf einer echten Installation:
Ein Agent hängte `mail.read` an seine eigene `info.json` an, und der
privilegierte Daemon meldete das Werkzeug danach als gewährt – ein Agent
konnte sich also das Postfach, die Kanäle gewähren oder seine eigenen
Obergrenzen anheben. Er konnte auch seinen eigenen Prompt durch „ignoriere
alle deine Regeln“ ersetzen, und das wäre von da an bei jedem Lauf so
geblieben.

Die Isolation zwischen Agenten braucht nichts davon: `/opt/boa/agents/` ist
`root:root 0711` und jedes Home-Verzeichnis ist 0700, der Kernel verweigert
also bereits. Deshalb hält sie auch dann, wenn ein Werkzeug einen Fehler hat.

### Was root aus dem Home-Verzeichnis liest

Das Journal, das Gedächtnis und der Chat sind die eigenen Dateien des
Agenten: von seinen eigenen Prozessen geschrieben, in seinem eigenen
0700-Home-Verzeichnis, und vom privilegierten Daemon als root gelesen – der
liest, worauf auch immer man ihn zeigen lässt. Gemessen am Code, bevor es
das hier gab: Ein FIFO namens `runs.jsonl` hielt den Daemon-Thread, der ihn
öffnete, für immer fest, und da die Agentenliste das Journal jedes Agenten
liest, verlor jede spätere Anfrage nach dieser Liste einen weiteren Thread;
ein Link namens `memory.md`, der auf irgendeine Datei der Maschine zeigte,
brachte root dazu, den Text dieser Datei an die Oberfläche zu geben; und ein
Link auf etwas ohne Ende ließ root lesen, bis es beendet wurde.

Deshalb werden alle drei über `fReadAgentOwnedFile` gelesen, das Geschwister
von `fOpenProtectedAgentFile` für die Dateien, die dem Agenten GEHÖREN:
`O_NOFOLLOW` weist einen Link schon beim Öffnen ab, `O_NONBLOCK` verhindert,
dass ein FIFO das Öffnen festhält, bis jemand hineinschreibt, und die
Prüfungen erfolgen am geöffneten Deskriptor – eine reguläre Datei, die dem
Benutzer des Agenten gehört –, sodass zwischen Prüfung und Lesen nichts
ausgetauscht werden kann. Es liest nie mehr als eine Grenze, die an dem
gemessen wird, was gelesen wird, und nicht nur an dem, was `fstat` gesagt
hat, weil der Agent anhängen kann, während gelesen wird: 32 MB für das
Journal und für den Chat, vom ENDE her gelesen, wenn die Datei größer ist,
denn die neuesten Zeilen sind das, was ein Verlauf zeigt; 4 MiB für das
Gedächtnis, genug für sein Maximum von einer Million UTF-8-Zeichen. Nur von
außen geschriebene Dateien, die dieses Lesebudget überschreiten, bekommen
`[truncated]`; `fWrite` weist zu großen Inhalt zurück, bevor irgendetwas ersetzt wird. Ein fehlerhaftes Byte kostet eine Zeile, nicht den ganzen Lesevorgang.

Was abgewiesen wird, wird gesagt, nicht verschluckt: `read_run_journal`,
`read_chat` und `read_memory` schlagen mit dem Grund fehl, sodass ein
Betreiber erfährt, dass etwas in diesem Home-Verzeichnis nicht das ist, was
die Anwendung geschrieben hat. Die einzige Ausnahme ist `read_usage_summary`
für jeden Agenten, aus dem die Seitenleiste gezeichnet wird: Dort kostet ein
unlesbares Journal diesen Agenten seine Summen, mit dem Grund daneben, und
niemanden sonst die seinen.

### Was über die Befehlszeile reist

Der Daemon startet einen Lauf als der Agent mit `Popen`, und die Nachricht,
die der Besitzer getippt hat – oder der Prompt, den eine fällige Karte baut –,
war früher eines seiner Argumente: `--chat-message <text>`,
`--prompt <text>`. Die Befehlszeile eines Prozesses ist für jeden Benutzer
der Maschine über `/proc/<pid>/cmdline` lesbar, und ein Agent mit `bash.run`
ist ein Benutzer der Maschine. Gemessen auf der Debian-Testmaschine: `ps`,
als `agent-001` ausgeführt, zeigte die Nachricht, die der Besitzer gerade an
`agent-000` geschickt hatte, so lange dieser Lauf lebte, also standardmäßig
bis zu fünf Minuten.

Deshalb geht der Text über die Standardeingabe des Kindprozesses, und die
Befehlszeile trägt nur `--chat-message-on-stdin` oder `--prompt-on-stdin`.
`fStartRunner` ist die einzige Stelle, die einen Runner startet: Sie weist
einen Text, der länger als `cMaxStdinPayloadBytes` ist, ab, bevor überhaupt
ein Prozess existiert, weil diese Grenze unter dem 64-KiB-Puffer einer Pipe
liegt und ein Schreibvorgang, der in den Puffer passt, nie auf das Kind
wartet – dieser Daemon wartet nicht auf Runner. Ein Kind, das schon weg ist,
wenn geschrieben wird, etwa ein Interpreter, der beim Import scheitert, ist
eine kaputte Pipe und kein Fehler des Daemons. Auf der anderen Seite liest
der Runner den Text mit derselben Grenze, weist eine leere Chatnachricht ab,
statt eine Frage zu beantworten, die niemand gestellt hat, und schließt die
Gesprächsrunde, für die er gestartet wurde, wenn er abweist, damit das
Gespräch nicht ewig wartet. `--prompt` und `--chat-message` bleiben, für
einen Lauf, der von Hand in einem Terminal gestartet wird.

### Was ein Lauf mit der Maschine anstellen darf

Die Obergrenzen in `info.json` – Token, Schritte, Sekunden, Läufe pro Tag –
setzt der Runner durch, und der Runner ist ein Programm, das der Agent
steuert. Was hält, wenn das Programm selbst das ist, was schiefging, setzt
der Kernel durch, in zwei Schichten.

Der Runner senkt seine eigenen Ressourcenlimits, bevor er irgendetwas anderes
tut, `fApplyResourceLimits`, vom Einstiegspunkt aus und nicht aus `fMain` –
die Tests rufen `fMain` im selben Prozess auf, und ein RLIMIT_NPROC, das in
der Sitzung eines Entwicklers gesenkt wird, in der schon Tausende Threads
laufen, hindert diese Sitzung am Forken. Jeder Prozess, den der Lauf
startet, erbt sie: RLIMIT_NPROC bei 1024, gezählt gegen die uid des Agenten
als Ganzes, sodass eine Fork-Bombe aus `bash.run` an dieser Zahl stoppt und
nicht an der Maschine – Threads zählen mit, weshalb der Wert nicht kleiner
ist, denn ein Browser besteht aus einigen Hundert davon; keine Core-Dateien;
keine Datei über 4 GiB. Kein RLIMIT_AS: Chromium reserviert Adressraum im
Umfang von Dutzenden Gigabytes und würde nicht starten. Diese Schicht ist auf
Debian und auf Alpine dieselbe, und sie ist die einzige, die ein Lauf hat,
der vom eigenen Crontab des Agenten gestartet wird.

Wo systemd PID 1 ist, fügt der Daemon die zweite hinzu: `fStartRunner` setzt
den Lauf in einen eigenen transienten Scope, `boa-agent-<id>-<random>.scope`
unter `boa-agents.slice`, mit `TasksMax=1024` und `MemoryMax=2G`.
`systemd-run --scope` ersetzt sich per exec durch den Befehl, die PID ist
also weiterhin die des Runners und `/proc` zeigt weiterhin seine
Befehlszeile; `setpriv` ist das, was auf den Agenten herunterstuft, weil
systemd-run root sein muss, um den Scope anzulegen. Gemessen, bevor es so
war: Ein Lauf war ein Kind von `boa-exec.service`, in der eigenen cgroup des
Daemons, und ein außer Kontrolle geratener Agent verbrauchte das TasksMax des
Daemons und ließ ihn unfähig zu forken. Der Scope ist auch das, was beendet,
was ein Lauf hinterlassen hat: `bash.run` signalisiert seine eigene
Prozessgruppe, sodass ein Befehl, der `setsid` aufrief, oder ein
Hintergrundkind eines Befehls, der rechtzeitig fertig wurde, den Lauf
überlebte; `fWatchRunner` wartet auf den Lauf und stoppt seinen Scope, was
alles erreicht, was der Lauf gestartet hat, wohin auch immer es sich verlegt
hat. Ein Lauf, der beendet wurde – durch das Speicherlimit, durch einen
Betreiber –, hat beim Abgang nichts geschrieben, also hält derselbe Thread
das Ende im Journal fest und schließt die Gesprächsrunde im Chat; ein Lauf,
der von selbst endete, hat beides schon getan, und die Gesprächsrunde wird
geprüft statt angenommen.

### Wo die Anbieterschlüssel liegen

Die Schlüssel, die alle Agenten teilen, liegen in
`/opt/boa/config/apikeys/<provider>.key`, im Besitz von `boa`, das
Verzeichnis `0700` und die Dateien `0600`.

0750 und 0640 würden die Agenten schon draußen halten – kein Agentenbenutzer
ist in der Gruppe `boa` –, aber das beruht darauf, dass die Gruppenliste
jedes Agenten über die gesamte Lebensdauer der Installation leer bleibt, und
das ist nur ein `usermod -aG` davon entfernt, falsch zu sein. Ein Modus, der
der Gruppe nichts gewährt, hängt nicht davon ab. `api_keys.fWrite` setzt
beide Modi bei jedem Schreiben und nicht nur beim Anlegen, sodass ein
Verzeichnis, das aus einer älteren Installation kommt, beim ersten Speichern
eines Schlüssels verschlossen wird.

Das Verzeichnis hieß `keys`, bis es umbenannt wurde: Es las sich wie „die
Schlüssel dieser Installation“ und lag nur einen Tippfehler entfernt vom
agentenspezifischen `keys/` in jedem Home-Verzeichnis eines Agenten, das
etwas anderes ist, das ein Agent *lesen kann* – sein eigener Schlüssel, dort
abgelegt, um ihn einem anderen Konto in Rechnung zu stellen. Der Installer
verschiebt das alte Verzeichnis bei `--update` und löscht es erst, wenn es
leer ist.

Nichts davon hindert einen Agenten daran, den Schlüssel des Anbieters zu
besitzen, auf dem er tatsächlich läuft: Die Agenten-API gibt ihm diesen, er
braucht ihn, um den Aufruf zu machen, und ein Agent mit `bash.run` könnte ihn
ausgeben. Was es verhindert, ist, dass ein Agent die Schlüssel der Anbieter
liest, die er nicht benutzt.

### Zehn Dienste, zwei davon als root gestartet

| Prozess | Benutzer | Warum es ihn gibt |
|---|---|---|
| `boa-proxy` | `boa` | HAProxy: terminiert TLS, bedient beide Ports |
| `boa-web` | `boa` | Liefert die Oberfläche und die API aus, über einen Unix-Socket |
| `boa-exec` | `root` | Legt Benutzer an und startet Agentenläufe |
| `boa-samba` | `root` | Authentifiziert SMB-Sitzungen und liefert dann Dateien als der besitzende Agent aus |
| `boa-embeddings` | `boa` | Stellt das lokale Einbettungsmodell der Dokumentbibliotheken bereit, auf einem Unix-Socket |
| `boa-rag` | `boa` | Plant die Indexierungswarteschlange der Dokumentbibliotheken |
| `boa-agent-api` | `boa` | Hält, was Agenten benutzen, aber nicht lesen dürfen |
| `boa-buzzer` | `boa` | Weckt einen Agenten, wenn eine seiner Karten fällig wird |
| `boa-channel-telegram` | `boa` | Lauscht auf Telegram und übergibt, was ankommt, an einen Agenten |
| `boa-channel-discord` | `boa` | Dasselbe für einen Discord-Kanal |

Die Kanal-Units heißen auf Debian `boa-channel-telegram.service` und
`boa-channel-discord.service`; künftige Kanal-Units folgen
`boa-channel-<channel>.service`. OpenRC behält `boa-telegram` und
`boa-discord`. `system_info.fServiceName` löst diese Namen sowohl für den
Tab Betriebssystem als auch für die Statusmeldungen der Listener auf.

`fInstallSystemdUnits` ruft `fRetireLegacyChannelUnits` auf, um jede alte
Kanal-Unit zu stoppen und zu deaktivieren, bevor sie gelöscht und ihre
Nachfolgerin aktiviert wird. Wiederholte Updates funktionieren auch, wenn
keine alte Unit existiert. Scheitert ein Update, bevor die neuen Units
installiert sind, kann `fStartServices` die alten beim Rollback neu starten.

Die letzten vier sind mit Absicht `boa` und nicht root: Jeder von ihnen will,
dass etwas als der eigene Benutzer eines Agenten getan wird – einen Lauf
starten, in ein 0700-Home-Verzeichnis schreiben –, und jeder bittet
`boa-exec`, es zu tun, statt das Privileg selbst zu bekommen. Ein Dienst, der
von außen erreichbar ist, wie es die beiden Listener faktisch sind, ist der
letzte, der es halten sollte.

### Eine virtuelle Umgebung ist nicht verschiebbar

`python3 -m venv <path>` schreibt `<path>` in den Shebang jedes
Konsolenskripts, das später darin installiert wird, in `VIRTUAL_ENV` in den
activate-Skripten und in die Zeile `command` von `pyvenv.cfg`. Die Umgebung
wird unter `venv.new` gebaut und in `venv` umbenannt, sodass alle drei danach
ein Verzeichnis nennen, das es nicht mehr gibt.

Gemessen auf einem echten Debian 13 und einem echten Alpine 3.24: Beide
Installationen liefen durch, beide gaben „Installation finished“ aus, und
beide hinterließen ein `boa-web`, das sich alle fünf Sekunden neu startete,
mit

```
status=203/EXEC - Failed to execute /opt/boa/venv/bin/gunicorn:
No such file or directory
```

Die Datei war da. Ihre erste Zeile nannte `/opt/boa/venv.new/bin/python3`,
und das war nicht da.

`fBuildVirtualEnv` hatte eine Prüfung für genau diese Art von Fehler, und sie
bestand, weil sie `bin/python3` ausführt – einen SYMLINK auf den
System-Interpreter, der antwortet, wo auch immer er gerade liegt. Nur ein
Konsolenskript hat den Pfad fest eingebrannt. Deshalb führt die Prüfung jetzt
auch `bin/gunicorn --version` aus, also die Datei, die die Service-Unit
ausführt, und `fRepointVirtualEnv` schreibt alle drei gespeicherten Pfade um,
solange die Umgebung noch unter ihrem Baunamen liegt. Das Umschreiben wird
überprüft statt angenommen: Schreibt ein künftiges pip seine Konsolenskripte
auf andere Weise, hält der Installer dort an.

### Ein Update, das scheitert, lässt etwas laufen

Drei Stufen, und die Reihenfolge ist die Reparatur.

Ein Update stoppte früher die Dienste, löschte `webapp/` und führte erst dann
pip aus. Ein pip, das scheiterte – kein Netz, ein Index nicht erreichbar, ein
Wheel, das sich nicht bauen ließ –, hinterließ eine Installation mit
gestoppten Diensten und verschwundenem Code: eine Maschine, die vor einer
Minute noch funktionierte und darauf angewiesen war, dass jemand es bemerkt
und sie von Hand wiederherstellt.

| Stufe | Was passiert | Was ein Fehler kostet |
|---|---|---|
| Vorbereiten | Fragen gestellt, Abhängigkeiten installiert, Code heruntergeladen, die neue virtualenv NEBEN der laufenden GEBAUT und geprüft, dass sie importiert | Nichts. Die alte Version läuft weiter und bleibt unberührt |
| Umschalten | Stoppen, `webapp/` nach `webapp.previous` verschoben, `venv` nach `venv.previous`, die neuen an ihren Platz gesetzt, starten | Umkehrbar: Beide vorherigen Versionen liegen noch auf der Platte |
| Überprüfen | `curl` fragt die Anwendung fünfzehnmal innerhalb von dreißig Sekunden nach der Anmeldeseite | `fRollBack` stellt beide zurück und startet sie wieder |

Dieses `curl` sendet das PROXY-Protokoll nur im Modus `proxied`. Im Modus
`direct` hat das Bind kein `accept-proxy`, ein PROXY-Header landet also im
TLS-Handshake, und die Anfrage bekommt überhaupt keine Antwort. Früher wurde
er in beiden Modi gesendet, wodurch jedes `--install --ports direct` mit
„did not answer“ endete, über einer Installation, die Seiten auslieferte, und
jedes direkte `--update` sich selbst zurückrollte. Bestätigt, indem beide
Testmaschinen auf `direct` und zurück umgestellt wurden: Mit an den Modus
gebundenem Flag antworteten beide mit 200 auf 443 und danach auf 11443. Ein
Test führt `fVerifyInstallation` aus beiden Installern gegen ein `curl` aus,
das seine Argumente aufzeichnet, einmal pro Modus, und prüft, dass das Flag
im einen vorhanden ist und im anderen fehlt.

Wenn dieses `curl` nie eine Antwort bekommt, schreibt
`fExplainWhyItDoesNotAnswer` in dasselbe Log, auf das der Fehler verweist,
wie die Maschine in diesem Moment aussah: was curl selbst sagt – noch einmal
mit `-sS` gefragt, damit eine abgelehnte Verbindung, ein gescheiterter
Handshake und eine Anfrage mit Zeitüberschreitung unterschieden werden, denn
`000` ist kein HTTP-Code, sondern curl, das sagt, dass es nie einen bekommen
hat –, den Zustand jedes der zehn Dienste, ob überhaupt etwas auf dem Port
lauscht, und die letzten fünfzehn Zeilen von `boa-proxy.log`, `boa-web.log`
und dem `error.log` von gunicorn. `fReportServiceStates` ist die Hälfte, die
sich zwischen den beiden unterscheidet: `rc-service ... status` auf Alpine,
`systemctl is-active` plus das Journal von `boa-web` und `boa-proxy` auf
Debian.

Es gibt sie, weil eine Erstinstallation auf einem frischen Alpine mit „The
application did not answer on port 11443 (last code: 000)“ endete und das Log
nichts weiter dazu enthielt – nicht, welcher Dienst ausgefallen war, nicht,
ob der Port belegt war, keine einzige Zeile dessen, was gunicorn ausgegeben
hatte. Die eine Datei, die der Fehler nennt, konnte die Frage nicht
beantworten, für die sie geöffnet wurde. Worauf man darin achten sollte: Ein
Dienst, der sich als gestartet bezeichnet, neben „nothing is listening on
port 11443“, ist ein Prozess, der stirbt und neu gestartet wird, denn ein
überwachter Dienst, der im Moment seines Starts stirbt, wird von dem Befehl,
der ihn gestartet hat, als gestartet gemeldet. Vier Tests FÜHREN beide
Funktionen AUS – gegen ein `curl`, das die Verbindung verweigert, ein `ss`,
das den Port hält, und eines, das es nicht tut, und ein `rc-service` und ein
`systemctl`, die „stopped“ antworten und einen Fehler zurückgeben.

`fRollBack` startet die Dienste in einer SUBSHELL, und das `|| true` daneben
reicht allein nicht: `fStartServices` ruft `fDie` auf, wenn ein Dienst nicht
hochkommt, `fDie` ruft `exit` auf, und `exit` beendet die Shell, egal was
daneben steht. Gemessen auf einem echten Alpine: `boa-proxy` wurde von OpenRC
heruntergefahren, während `boa-web` flatterte, der eigene Start durch den
Rollback verlor das Rennen um die Dienstsperre, und der Installer starb
INNERHALB von `fRollBack`. Der Rollback hatte funktioniert – die vorherige
Version war zurück und antwortete –, aber dem Betreiber wurde „The boa-proxy
service would not start“ gesagt, ohne ein Wort darüber, dass gerade ein
Update zurückgerollt worden war. In diesem Moment ist der Bericht darüber,
was passiert ist, das Einzige, was ein Betreiber hat.

Die vorherige Version wird von `fFinishUpdate` entfernt, und erst nachdem die
neue geantwortet hat.

`fRollBack` lief früher nur an einer Stelle: wenn dieses abschließende `curl`
scheiterte. Zwischen `fStopServices` und dieser Prüfung liegen ein Dutzend
Schritte, die sterben können – eine verschwundene Zertifikatsdatei, eine
Proxy-Konfiguration, die HAProxy nicht parst, eine Unit, die sich nicht
installieren lässt –, und jeder davon hinterließ die Dienste gestoppt, den
neuen Code an seinem Platz und `webapp.previous` auf der Platte, ohne dass
jemand es zurückstellte. Die Meldung nannte, was gescheitert war, und sagte
nichts darüber, dass die Maschine nicht lief. Deshalb setzt `fDoUpdate`
`vUpdateSwitched` direkt vor dem Stoppen der Dienste, und `fCleanup` – der
EXIT-Trap, der läuft, wie auch immer der Kindprozess endet – rollt zurück,
wenn er das Flag gesetzt und den Exit-Code ungleich null findet. Die beiden
Wege aus dem Umschalten löschen es: `fRollBack` selbst, damit der explizite
Weg nicht zweimal zurückrollt, und `fFinishUpdate`, weil es nichts gibt, zu
dem man zurückkehren könnte, sobald die neue Version geantwortet hat.
Gemessen auf beiden Testmaschinen mit verstecktem privatem Schlüssel:
„Missing certificate files“, „Putting the previous version back“, alle
Dienste oben und die Anmeldeseite antwortet mit 200 auf dem vorherigen Code.
Ein Test führt das echte `fCleanup`, `fRollBack` und `fFinishUpdate` jedes
Installers durch drei Ausgänge: nach dem Umschalten, davor und nach dem
Abschluss.

`--install` und `--reinstall` haben keine vorherige Version zu behalten, also
haben sie kein Umschalten und keinen Rollback – aber sie überprüfen. Früher
endeten sie bei `fWriteCredentialsFile`, und „Installation finished“ wurde
auf zwei echten Maschinen ausgegeben, deren Webdienst sich alle fünf
Sekunden neu startete: Niemand hatte die Anwendung je etwas gefragt. Jetzt
fragen sie nach derselben Anmeldeseite, und wenn sie nicht kommt, sagen sie
es und nennen das Log, denn auf der Maschine gibt es nichts, zu dem man
zurückkehren könnte.

`pip` selbst ist festgepinnt. `--upgrade pip` ohne Version bedeutete, dass
zwei Updates desselben Codes unterschiedlich auflösen konnten, und genau
dafür wurden die Anforderungen gepinnt. Was weiterhin nicht gepinnt ist,
sind die TRANSITIVEN Abhängigkeiten – deshalb wird `pip freeze` in der
Umgebung festgehalten, und das nächste Update gibt aus, was sich bewegt hat,
denn nur so würde es überhaupt jemand erfahren.

### Eine Installation, die auf halbem Weg stehen blieb

`fIsInstalled` zählte eine Maschine als installiert, sobald `webapp/backend`
und der Benutzer `boa` existierten – also vor der virtuellen Umgebung, den
Zertifikaten, der Datenbank und dem Administrator. Eine Installation, die bei
pip starb, in einem Netz, das wegbrach, bekam danach von `--install` „already
installed“ und von `--update` einen Abbruch an dem, was gerade fehlte, und
nur `--reinstall --yes` kam darüber hinweg, ohne dass dem Betreiber das
irgendetwas gesagt hätte.

Eine fertige Installation hinterlässt jetzt `/opt/boa/installed`, geschrieben
von `fMarkInstalled` erst, nachdem `fVerifyInstallation` seine Seite bekommen
hat: Eine Installation, die an Ort und Stelle ist und nicht antwortet, ist
nicht fertig, und ein Update, das zurückgerollt wurde, ist nicht die neue
Version. Ohne die Markierung stehen die fünf Dinge, die eine fertige
Installation immer hat – der Code, der Benutzer, `venv/bin/gunicorn`,
`db/boa.sqlite` und `certificates/privkey.pem` – an ihrer Stelle, sodass eine
Installation aus der Zeit vor der Markierung weiterhin zählt und beim
nächsten Update ihre Markierung bekommt. Alles andere, was `--install` tut,
kann schon gefahrlos zweimal getan werden: Der Benutzer wird nur angelegt,
wenn er fehlt, die Umgebung wird neben der alten gebaut, die Zertifikate
bleiben erhalten, wenn sie vorhanden sind, der Administrator wird gelöscht
und mit dem neuen Passwort neu geschrieben. Eine halb fertige Installation
wird also fertig, indem man `--install` noch einmal ausführt, und `--update`
sagt genau das, wenn es eine findet. Nebenbei ist `fGeneratePassword` im
Debian-Installer hinter `fInstallDependencies` gerückt, wo es umgekehrt war:
`openssl` hat auf Debian Priority: optional, und ein minimales Image erzeugte
das Passwort, bevor das Paket installiert war, das es erzeugt.

### Alles, was der Installer ausführt, landet in seinem Log

`fLog` schrieb seine eigenen Zeilen nach `install.log` und sonst nichts. apt,
pip, die HAProxy-Validierung und jeder andere Unterprozess schrieben ins
Terminal, sodass eine gescheiterte Installation ein Log hinterließ, das
„Installing the dependencies.“ enthielt und kein einziges Wort des
apt-Fehlers, der erklärte, warum – und genau dieses Detail sucht jemand, der
diese Datei öffnet.

`fStartCapturingOutput` leitet stdout und stderr dieser Shell selbst in einen
FIFO um, den `tee` ins Log und ins Terminal kopiert. Ein FIFO statt
`exec > >(tee ...)`, was nur in bash geht, und Alpine startet ohne bash; und
statt einer Pipeline um `fMain`, die es in eine Subshell stecken und die
Anordnung `fMain & wait` aufheben würde, die errexit am Leben hält.

Zwei Folgen, die beide behandelt werden mussten:

`fLog` gab die Zeile per echo aus UND hängte sie selbst ans Log an. Sobald
stdout ein tee ist, das an dieselbe Datei anhängt, ist der zweite
Schreibvorgang ein Duplikat: Eine Installation mit 90 Zeilen erzeugte ein
Log mit 185 Zeilen, in dem jede Zeile doppelt stand. `fLog` schreibt jetzt
nur in die Datei, solange die Erfassung nicht läuft.

`tee` hält das Log über die INODE offen. Ein `--reinstall` löscht den ganzen
Baum, das Log eingeschlossen, und legt eine frische Kopie zurück – ab diesem
Moment hängt `tee` also an eine Inode ohne Namen an, und da `fLog` nicht mehr
in die Datei schreibt, wäre das die gesamte zweite Hälfte der
Neuinstallation, das erzeugte Passwort eingeschlossen.
`fRestartCapturingOutput` richtet die Erfassung auf die Datei, die jetzt
existiert.

### Zwei Installer, eine Anwendung

`deploy/install-update-reinstall-debian.sh` schreibt systemd-Units und
**braucht systemd als PID 1 der laufenden Maschine**: Ein Debian, das mit
etwas anderem gebootet wurde, ist kein Ziel, und der Installer verweigert
es, statt auf eine Maschine zu installieren, die nichts starten würde.
`deploy/install-update-reinstall-alpine.sh` schreibt OpenRC-Dienste nach
`/etc/init.d/`, aus `deploy/openrc/`, und braucht nichts im Voraus: Er
installiert OpenRC selbst, wenn die Maschine keines hat. Beide installieren dieselben zehn Prozesse,
denselben Baum unter `/opt/boa`, dasselbe Benutzermodell; ein Test vergleicht
die beiden Schritt für Schritt und schlägt fehl, wenn einer einen Schritt
bekommt, den der andere nicht hat.

Sie sind nicht in derselben Sprache geschrieben, und das ist Absicht. Der
Debian-Installer ist bash, wie alles andere hier. Der Alpine-Installer ist
POSIX-Shell, mit `#!/bin/sh`, weil ein frisches Alpine kein bash hat: Mit
`#!/bin/bash` würde der Kernel nach einem Interpreter suchen, der nicht da
ist, und

    curl -fsSL <raw-url> | bash -s -- --install

würde scheitern, bevor eine Zeile gelesen ist, und zwar auf der Maschine, die
die Installation per Einzeiler am meisten braucht. Als POSIX läuft er unter
BusyBox ash, dash und bash gleichermaßen, sodass dieselbe Datei per Pipe in
`sh` auf einem nackten Alpine funktioniert und in `bash` auf einem, das es
schon hat. Er installiert trotzdem bash – jeder Agent bekommt eine
bash-Shell –, er braucht es nur nicht mehr zum Starten. Was das kostet, sind
Arrays, `[[ ]]`, `${var//x/y}` und `<(...)`; `local` bleibt, weil alle drei
Shells es haben, und `pipefail` wird in einer Subshell abgefragt, bevor es
gesetzt wird, weil dash es nicht hat. Ein Test weist jedes dieser Konstrukte
zurück, denn ein Shell-Feature, das nicht da ist, scheitert zur
Installationszeit auf der Maschine von jemand anderem.

Was Alpine braucht und Debian nicht, und warum keines davon optional ist:

| | Warum |
|---|---|
| `shadow` | Der privilegierte Daemon ruft `useradd --home-dir --create-home --shell` auf. Das `adduser` von BusyBox hat keine dieser Optionen, und ein Agent, der sich nicht anlegen lässt, bedeutet, dass die ganze Anwendung nicht funktioniert |
| `bash` | Die Shell, die jeder Agent bekommt, und das, worüber `bash.run` läuft. Alpine wird ohne sie ausgeliefert, und das ist auch der Grund, warum der Alpine-Installer die einzige Datei in diesem Projekt ist, die in POSIX-Shell statt in bash geschrieben ist: `#!/bin/bash` würde `curl ... \| sh` auf genau der Maschine unmöglich machen, die es am meisten braucht |
| `dcron` | Irgendetwas muss die Crontabs lesen, die der Daemon schreibt. Auch der Grund für das `-d` weiter unten |
| `gcc`, `musl-dev`, `libffi-dev`, `python3-dev` | Mehrere Anforderungen veröffentlichen kein musl-Wheel und werden während der Installation kompiliert |
| `libcap` | `setcap cap_net_bind_service` auf das haproxy-Binary, im Modus `direct`. systemd gewährte das pro Dienst mit `AmbientCapabilities`; OpenRC hat nichts Entsprechendes |

Drei Dinge musste die Portierung im Code ändern, jedes davon beim
Installieren gefunden:

- **`crontab -u <agent>`, statt zum Agenten herunterzustufen.** Das
  `crontab` von Debian ist setgid und jeder Benutzer darf es ausführen; das
  dcron von Alpine liefert es als `4750 root:wheel` aus, sodass ein Agent, der
  es ausführt, `Permission denied` bekommt. Die Wege, die alte Form zu
  behalten, wären gewesen, jeden Agenten in `wheel` aufzunehmen – die Gruppe,
  die auf den meisten Systemen sudo bedeutet – oder ein setuid-Binary des
  Systems zu lockern. Der Daemon ist root und kann stattdessen den Benutzer
  nennen.
- **`-r` oder `-d` beim Löschen eines Crontabs.** Vixie cron löscht einen
  Crontab mit `-r`; dcron mit `-d`, und auf `-r` antwortet es mit einer
  Usage-Meldung und Exit-Code 2. Nur `-r` zu versuchen ließ den Crontab eines
  gelöschten Agenten zurück, der weiterhin auf den Runner eines Benutzers
  zeigte, den es nicht mehr gab. Beide werden versucht, weil das installierte
  Binary entscheidet, nicht der Name der Distribution.
- **`executable=` in `browser.conf`.** Playwright veröffentlicht keinen
  musl-Build, deshalb wird das Paket auf Alpine ganz aus den Anforderungen
  herausgelassen, und es gibt keinen Browser. Die Zeile wird von
  `browser.fReadConfiguredExecutable` gelesen und ist der Ort, an dem ein
  System-Chromium benannt würde, an dem Tag, an dem es ein Playwright gibt,
  das eines steuern kann.

Noch eines, gefunden beim Blick auf `/proc/<pid>/fd/2` auf der
Alpine-Testmaschine: `supervise-daemon` schickt stdout und stderr eines
Prozesses nach `/dev/null`, sofern nichts anderes gesagt wird, und nichts
anderes auf Alpine sammelt sie ein – die Units auf Debian haben dafür
journald. Alle Dienste schrieben nirgendwohin etwas. Jedes OpenRC-Skript
nennt jetzt `output_log` und `error_log`, eine Datei pro Dienst unter
`/opt/boa/logs/`, in `start_pre` als `boa` angelegt, damit logrotate sie als
`boa` rotieren kann, egal wer hineinschreibt. `fInstallLogRotation`, in
beiden Installern, schreibt `/etc/logrotate.d/boa` für diese Dateien und für
die zwei von gunicorn: wöchentlich, acht behalten, `copytruncate`, weil beide
Schreiber ihre Datei offen halten, und nie `install.log`, das root gehört und
das Passwort enthält. Die andere Hälfte desselben Fundes: Der Tab Betriebssystem
fragte OpenRC nach `crond`, dem cron von BusyBox, während der Installer an
seiner Stelle `dcron` laufen lässt, sodass ein gesundes Alpine cron als
gestoppt meldete. `fPickOpenRcCronService` fragt nach dem ersten der beiden,
der ein Dienstskript hat.

Und zwei, die der Installer umgeht, statt sie zu beheben, weil sie zum
haproxy-Paket von Alpine gehören: Es liefert kein `/etc/haproxy/errors/` aus
und kein `/run/haproxy` für den Admin-Socket. Beide Zeilen werden aus der
Konfiguration gestrichen, wenn ihre Datei oder ihr Verzeichnis nicht da ist,
was auch auf einer Maschine richtig ist, auf der ein Administrator sie doch
angelegt hat. Zuerst wurde versucht, `/run/haproxy` anzulegen, mit einem
Skript in `/etc/local.d/`, das es bei jedem Booten neu erzeugt: `local` läuft
am ENDE des Bootvorgangs, sodass haproxy schon mit dem Starten gescheitert
war, als es auftauchte.

Noch eines gehört zu OpenRC selbst: Es cacht den Abhängigkeitsbaum der
Dienste und entscheidet, ob es ihn neu baut, indem es Zeitstempel mit
`/etc/init.d` vergleicht. Bei einer Neuinstallation werden die Dienstskripte
in derselben Sekunde wie der Cache überschrieben, also behält es den alten,
und die Dienste bleiben draußen – sie starten während der Installation,
weil `rc-service start` den Baum nicht braucht, und kommen nach einem
Neustart nicht zurück, weil `openrc default` ihn braucht.
`fInstallServices` endet mit einem bedingungslosen `rc-update -u`.

### Was jeder Installer von der Maschine verlangt und was er selbst installiert

Der Debian-Installer weigert sich zu laufen, wo systemd nicht PID 1 ist
(`fRequireSystemd`, aufgerufen, bevor überhaupt etwas installiert wird).
Alles, was er einrichtet, wird von systemd gestartet und am Leben gehalten –
die zehn Units, das HAProxy der Maschine, cron –, sodass die Installation auf
einer solchen Maschine früher durchlief, Erfolg meldete und nichts
auslieferte: `systemctl` ist installiert, es antwortet „System has not been
booted with systemd as init system (PID 1). Can't operate.“, und niemand las
diesen Exit-Code. Was er jetzt ausgibt, ist, wie man es behebt: `systemd
systemd-sysv dbus` installieren, den Container mit `/sbin/init` als Befehl
neu anlegen, den Installer erneut ausführen. Er sagt „neu anlegen“ statt „neu
starten“, weil ein laufender Container seine PID 1 nicht ändern kann.

Der Alpine-Installer trifft bei OpenRC die gegenteilige Entscheidung, weil
das fehlende Stück dort eines ist, das er liefern kann: `openrc` wird
zusammen mit den anderen Paketen installiert – ein Container-Image wird ohne
es ausgeliefert, ein mit `setup-alpine` installiertes Alpine hat es –, und
`fEnsureOpenRcUsable` legt dann `/run/openrc/softlevel` an, die Datei, die
OpenRC selbst nennt, wenn es sich weigert, einen Dienst auf einem System
anzufassen, das es nicht gebootet hat. Danach starten die zehn Dienste in
einem Container. Das Log sagt, dass sie nicht von selbst zurückkommen
werden, weil `/run` ein tmpfs ist und PID 1 nicht OpenRC ist.

Die beiden sind nicht widersprüchlich: systemd lässt sich nur als PID 1 zum
Laufen bringen, OpenRC auch anders.

### `if ! fMain` schaltet `set -e` für die gesamte Installation ab

Beide Installer enden damit, dass fMain als Kindprozess gestartet wird:

    fMain "$@" &
    vMainPid=$!
    if ! wait "${vMainPid}"; then ...

und nicht mit `if ! fMain "$@"`, wonach es aussieht und was sie früher
hatten. Ein Befehl in der Bedingung eines `if` läuft mit ausgesetztem
errexit, und die Aussetzung wird von jeder Funktion geerbt, die er aufruft,
und von jeder Funktion, die diese aufrufen – also von der gesamten
Installation. Gemessen auf einer Maschine ohne systemd: Acht Befehle
scheiterten hintereinander, jeder gab seinen Fehler aus, das Skript lief an
allen vorbei weiter und endete mit „Installation finished“. Ein Kindprozess
bekommt errexit zurück, weil die Aussetzung einen Fork nicht überlebt. bash,
dash und BusyBox ash verhalten sich alle so, in beiden Hälften dieses Satzes,
und weder `set -e` innerhalb der Funktion noch eine Subshell stellen es
wieder her.

Zwei Folgen davon, fMain in einem Kindprozess laufen zu lassen:
`trap fCleanup EXIT` wird auch innerhalb von fMain installiert, weil eine
Subshell den EXIT-Trap ihres Elternprozesses nicht erbt und der
heruntergeladene Baum unter `/tmp` sonst bei jedem Lauf zurückbliebe; und
der Elternprozess löscht seinen eigenen Trap, bevor er endet, damit die Zeile
„Exited with code“ nicht zweimal ausgegeben wird.

`fHasTty` ist eine Korrektur aus derselben Familie: Es öffnet `/dev/tty` und
schließt es wieder, statt `[ -r /dev/tty ]` zu testen. Der Geräteknoten ist
auf jedem System dem Modus nach lesbar, sodass dieser Test unter
`ssh host ./installer` ohne pty bestand und das folgende `read` mit ENXIO
starb – ein Prozess ohne steuerndes Terminal kann es überhaupt nicht öffnen.

### Die mitgelieferte haproxy.cfg ist nicht die Arbeit von jemandem

`fInstallMachineProxy` ersetzt `/etc/haproxy/haproxy.cfg`, wenn es im Modus
`proxied` ist, und eine Datei, die es nicht geschrieben hat, rührt es nicht
an, ohne vorher zu fragen – der Proxy der Maschine trägt vielleicht andere
Sites. Der Haken ist, dass die Datei, die es auf einer frischen Maschine
findet, vom haproxy-Paket dorthin gelegt wurde, das **dieser Installer selbst
installiert hat**, eine Minute früher in `fInstallDependencies`.

Dieses Beispiel als die Arbeit von jemandem zu behandeln, ist das, was jedes
schlichte `--install` abrupt stoppte: kein `--yes`, kein Terminal zum
Antworten, und der Lauf endete bei „Destructive operation with no terminal to
confirm on“, nachdem er den Baum, die virtualenv und die Zertifikate schon
gebaut hatte. Gemessen auf allen vier Testmaschinen, Debian und Alpine
gleichermaßen, mit genau der Zeile, die das README angibt.

`fMachineProxyIsPristine` fragt den Paketmanager, statt zu raten:

- Debian: die md5, die dpkg für diese Conffile aufgezeichnet hat
  (`dpkg-query -W -f '${Conffiles}'`), gegen die eigene md5 der Datei.
- Alpine: der Hash, den apk für diese Datei aufgezeichnet hat, gelesen aus
  `/lib/apk/db/installed` (die Zeile `Z:` unter `R:haproxy.cfg`), gegen
  `openssl dgst` der Datei. `Q1` ist sha1 in base64, `Q2` ist sha256.

`apk audit --system` sieht wie die Alpine-Antwort aus und ist es nicht:
Gemessen auf Alpine 3.24 meldet es **nichts** für eine bearbeitete
`/etc/haproxy/haproxy.cfg`. Die erste Version dieser Prüfung glaubte ihm und
hätte den Proxy von jemandem ohne zu fragen ersetzt – genau das, was die
Bestätigung verhindern soll. Seitdem getestet mit der Datei des Pakets, mit
einer hinzugefügten Zeile darin und mit der Datei, die dieser Installer
schreibt.

Unverändert heißt, sie wird mit einer Zeile im Log und ohne Frage ersetzt.
Bearbeitet heißt das alte Verhalten: bei einem `--update` in Ruhe gelassen,
bei einer Installation oder Neuinstallation bestätigt und nach
`.before-boa.<timestamp>` gesichert.

### Eine Datei für das Log und das Passwort

Der Installer schreibt `/opt/boa/logs/install.log` und sonst nichts: was er
getan hat, und an dessen Ende die Zugangsdaten, die er erzeugt hat. Früher
schrieb er zwei Dateien in /root – `app-web-install.log` und
`app-web-credentials.txt` –, und zwei Dateien an zwei Orten sind zwei Dinge,
die man finden muss. `fMigrateInstallFiles` kopiert, was in den alten steht,
in die neue, bevor es sie entfernt, weil das Passwort darin vielleicht die
einzige Kopie ist, die irgendjemand hat.

Drei Details halten das zusammen:

- `fLog` legt das Verzeichnis an, wenn es nicht da ist. Das Log liegt in dem
  Baum, den der Installer baut, sodass es bei einer Erstinstallation nicht
  existiert, wenn die erste Zeile geschrieben wird, und ein `--reinstall` es
  mittendrin löscht.
- `fRemoveInstallation` kopiert das Log vor `rm -rf /opt/boa` beiseite und
  legt es danach zurück, damit eine Neuinstallation ihr eigenes Protokoll
  nicht mitnimmt.
- Die Datei ist `root:root 0600` in einem Verzeichnis, das `boa` mit 0750
  gehört. `boa` kann sie entfernen – das bedeutet es, das Verzeichnis zu
  besitzen – und kann das Passwort darin nicht lesen; Agenten sind nicht in
  der Gruppe `boa` und können das Verzeichnis gar nicht betreten.

Die Anmeldeseite nennt diesen Pfad, in `frontend/templates/login.html`, auf
einer eigenen Zeile und mit `--colour-path` eingefärbt. Er steht nicht in den
fünfzehn Übersetzungsdateien: Der Satz darüber wird übersetzt, der Pfad ist
überall derselbe, und ein Pfad, der mitten in einen Satz umbrochen wird, ist
ein Pfad, den jemand falsch abtippt.

### Rundes Anwendungslogo

`frontend/static/img/boa.svg` ist ein blaues, rundes Zeichen mit drei
hüftaufwärts dargestellten Roboteragenten in schwarzen Anzügen, weißen Hemden
und dunklen Krawatten. Ihre Köpfe haben helle Metallplatten, mechanische
Gelenke und dunkle Visiere mit blauen Augen. Der Stil ist leicht
illustrativ, mit glatten Stofftexturen und ohne Einstecktuch beim mittleren
Agenten. Ihre Köpfe sind mit sichtbaren Roboterhälsen verbunden; der größere
mittlere Agent steht vor den beiden kleineren seitlichen Agenten.
Das schattierte Motiv ist ein 512px großes WebP, eingebettet in SVG,
mit kreisförmigem Zuschnitt und Transparenz außerhalb des Kreises. Die
Figuren bleiben deckend und behalten in allen Themes dasselbe Aussehen. Das
ist Rastergrafik in einem SVG-Container, keine Vektorpfade.
`favicon.svg` enthält dasselbe Motiv. Halte beide SVG-Dateien synchron.
Die URLs für Anmeldeseite, Seitenleiste und Favicon verwenden
`v=robot-agents`, um zwischengespeicherte Kopien des vorherigen Zeichens zu
erneuern. Die angezeigten Größen bleiben 30px auf der Anmeldeseite und 24px
in der Seitenleiste.

### Die Oberfläche spricht en-US, bis jemand etwas anderes sagt

`fGetLanguage` liest die Wahl aus `localStorage` und gibt, wenn es keine
findet, `en-US` zurück. Früher verhandelte es zuerst mit
`navigator.languages`, was bedeutete, dass eine neue Installation die Sprache
sprach, die der erste Browser sprach, der sie öffnete – die Sprache einer
Maschine, keine Entscheidung. Die Wahl ist nur ein Bedienelement entfernt, in
der Ecke der Anmeldekarte und in den Einstellungen, und wird pro Browser
gespeichert.

Zwei Fehler steckten in derselben Datei, und beide zeigten sich als „das
Anmeldeformular wechselt die Sprache erst, wenn man sie zweimal wechselt“:

- `fApplyTranslations` schrieb einen String nur, wenn die geladene Datei
  diesen Schlüssel hatte, und `textContent` war bereits von der vorherigen
  Sprache überschrieben worden. Ein Wechsel zu en-US – das keine Datei hat,
  `dTranslations` ist `{}` – änderte also überhaupt nichts, und ein Wechsel zu
  einer Sprache, der ein Schlüssel fehlte, ließ diesen Schlüssel in der
  vorherigen Sprache stehen. Der ursprüngliche String jedes übersetzten
  Elements wird jetzt beim ersten Übersetzen in einer `WeakMap` aufbewahrt,
  und ein Schlüssel ohne Übersetzung stellt ihn wieder her.
- `fSetLanguage` speicherte die Wahl und rief dann `fLoadTranslations()` ohne
  Argument auf, das die Wahl wieder aus dem Speicher las. In einem privaten
  Fenster wirft der Speicher eine Ausnahme, das Lesen liefert die vorherige
  Sprache, und die Seite lädt neu, was sie schon anzeigte. Jetzt übergibt es
  die Sprache, die es bekommen hat.

`fLoadTranslations` führt eine Sequenznummer mit, damit zwei Wechsel kurz
hintereinander nicht in falscher Reihenfolge ankommen und die Seite in einer
Sprache hinterlassen, um die niemand gebeten hat. Drei Dinge daran waren
falsch, und jedes zeigte dem Benutzer eine Sprache, die er nicht gewählt
hatte:

- Das Attribut `lang` wurde ganz OBEN gesetzt, bevor die Datei abgerufen
  war. Ein 404 oder ein Parse-Fehler ließ dann die Strings der vorherigen
  Sprache unter dem Namen der neuen auf dem Bildschirm: `lang=fr-FR` mit
  spanischem Text. Nichts wird veröffentlicht, bevor das Wörterbuch vorliegt,
  und `fPublish` setzt beides zusammen, weil der Fehler genau darin besteht,
  dass beides getrennt gesetzt wird.
- Die Sequenz wurde VOR `await response.json()` geprüft. Ein langsamer BODY
  einer früheren Anfrage kam an, nachdem eine spätere schon fertig war. Sie
  wird nach jedem await geprüft, weil sich die Sequenz über jedes davon hinweg
  bewegen kann.
- Ein Fehler sagte nichts und ließ die Seite in einem unbekannten Zustand.
  Jetzt fällt sie auf en-US zurück und meldet es über `fOnLoadFailed`.

### en-US.json ist die Quelle, und das Markup ist der Rückfall

Der Loader schloss `en-US` kurz auf ein leeres Wörterbuch, mit der
Begründung, dass das Markup den en-US-Text bereits enthält. Das stimmt, und
es machte `en-US.json` zu fünfhundert Schlüsseln totem Gewicht: ausgeliefert,
als Katalog aufgeführt, von den Tests auf Gleichstand mit den anderen
dreizehn geprüft und von nichts gelesen. Einen Tippfehler darin zu
korrigieren änderte nichts auf dem Bildschirm, und der einzige Weg, das
herauszufinden, war, es auszuprobieren.

Jetzt wird es wie jede andere Sprache abgerufen. Der Markup-Text bleibt der
Rückfall, als der er immer beschrieben wurde: Ein Schlüssel, den der Katalog
nicht hat, oder ein Katalog, der sich nicht laden lässt, hinterlässt weiterhin
eine lesbare Seite statt einer Seite voller Lücken. Geändert hat sich, welches
der beiden die Quelle ist.

### Fünfhundert Schlüssel sind noch keine übersetzte Oberfläche

Vier Arten sichtbarer Strings hatten überhaupt keinen Schlüssel und blieben
deshalb in allen vierzehn Sprachen Englisch:

| Was | Wie es jetzt übersetzt wird |
|---|---|
| Der Titel des Browser-Tabs | `data-i18n` auf `<title>`, ein Schlüssel pro Seite |
| Die eigenen Fehler der API | Ein `code` und seine `params` reisen mit; der Browser schreibt den Satz in `fDescribeApiError`. `error` bleibt für das, was von außen kam – die Worte eines Anbieters, die Ablehnung eines Mailservers –, für das man keine Übersetzung erfinden sollte |
| Beschreibungen der Vorlagen | Nicht in den Katalogen: Die `agent.json` jeder Vorlage trägt ihre Beschreibung in den fünfzehn Sprachen, und der Server wählt die, nach der die Oberfläche fragt (`agent_package.fPickDescription`) |
| Schema und Beschreibung eines Themes | `theme.scheme.<scheme>` und `theme.desc.<id>`, dieselbe Abmachung. Der NAME wird nicht übersetzt: Ein Theme ist die Palette von jemandem mit einem Namen, und „Nord“ zu übersetzen würde niemandem helfen, es zu finden |

Eine Vorlage oder ein Theme, das jemand für die eigene Installation schreibt,
behält seine eigenen Worte, statt zu verschwinden.

Das Sprachmenü auf der Anmeldeseite listet Codes – `es-ES`, `en-US` – und
keine Sprachnamen. Fünfzehn Namen in ihren eigenen Sprachen machten das
Bedienelement so breit wie die Karte; der Code ist 80px breit, und er ist
das, was jemand, der seine eigene Sprache sucht, in einer Liste von Codes am
schnellsten herausfindet. Die vollen Namen bleiben auf der
Einstellungsseite, die den Platz hat.

### Von rechts nach links

Hebräisch wird von rechts nach links geschrieben, und eine von links nach
rechts gesetzte Seite mit Hebräisch darin ist eine Seite, die niemand lesen
kann. Vier Entscheidungen sorgen dafür, dass ein einziges Stylesheet beide
Richtungen bedient:

**Die Richtung reist mit der Sprache.** `fPublish` in `i18n.js` setzt `dir`
auf `<html>` im selben Schritt wie `lang`, aus `lRightToLeftLanguages`, sodass
beide nie voneinander abweichen können – der Fehler, den die Funktion für
`lang` allein verhindern soll. Grid- und Flex-Zeilen folgen `dir` von selbst,
sodass die Seitenleiste und alles, was in einer Zeile angeordnet ist, ohne
eine eigene Regel gespiegelt werden.

**Das Stylesheet sagt Anfang und Ende, nicht links und rechts.** Jeder
Außenabstand, jedes Padding, jeder Rahmen, jedes `inset` und jedes
`text-align`, das den Textfluss betrifft, ist eine logische Eigenschaft
(`margin-inline-start`, `inset-inline-end`, `text-align: start`). Das eine
physische `left`, das in `app.css` übrig bleibt, ist der Ring um den Avatar
eines Agenten, der Geometrie ist und kein Text.

**Inhalte behalten ihre eigene Richtung.** Code, Pfade und Befehle laufen in
jeder Sprache von links nach rechts (`code, pre { direction: ltr; unicode-bidi: isolate }`),
sodass ein Pfad in einem hebräischen Satz nicht umgeordnet wird. Eine
Chat-Nachricht und jeder Absatz einer gerenderten Antwort übernehmen ihre
Richtung vom eigenen ersten Buchstaben (`unicode-bidi: plaintext`): Eine
englische Antwort auf einer hebräischen Seite liest sich von links nach
rechts, eine hebräische auf einer englischen Seite von rechts nach links. Die Textfelder, in die jemand freien Text schreibt, folgen derselben Regel, und ein leeres Feld folgt der Seite, sodass sein Hinweistext auf Hebräisch von rechts nach links läuft (`dir="auto"` würde ein leeres Feld samt Hinweis von links nach rechts setzen); die Crontab und die E-Mail-Adresse tragen `dir="ltr"`.

**Was von links nach rechts gelesen wird, wird innerhalb eines Satzes isoliert.** Der Bidi-Algorithmus schlägt ein neutrales Zeichen derjenigen Seite zu, die es berührt, sodass ein Pfad am Ende eines hebräischen Satzes seinen Schrägstrich und seinen Punkt an die Wörter ringsum verlor: „/tmp/x/007/." wurde als ".tmp/x/007/ /" angezeigt. In einer Sprache von rechts nach links leitet `fPublish` das Wörterbuch durch `fIsolateLeftToRightRuns`, das jeden `{placeholder}` und jede Folge mit einem Schrägstrich darin in U+2068 FIRST STRONG ISOLATE ... U+2069 POP DIRECTIONAL ISOLATE einschließt, sodass der Wert, den ein Aufrufer in einen Satz setzt, innerhalb der Isolation landet. Was die Maschine unter Einstellungen → Betriebssystem meldet (`fLeftToRight` in `settings.js`), eine Route in der API-Dokumentation (`.endpoint-path`), die Beispiel-Crontab-Zeile und die Zähler an Tabs und Spalten werden auf dieselbe Weise von links nach rechts isoliert; ohne das wurde eine Kernel-Version als „deb13-amd64 · x86_64+6.12.111“ angezeigt.

### Der Branch, von dem der Code heruntergeladen wird

`cRepoBranch` ist `main`, der echte Branch des Repositorys. Er war `master`,
was nur funktionierte, weil GitHub den alten Namen nach einer Umbenennung
weiterleitet – eine Weiterleitung, die an dem Tag verschwindet, an dem es
einen echten Branch `master` gibt, und die niemand für
`--repo-url file:///...` ausführt, womit beide Installer getestet werden.

### Warum die Anwendung ihr eigenes HAProxy mitbringt

Das HAProxy der Maschine leitet mit `send-proxy-v2` an Port 11443 weiter,
sodass ein PROXY-Header **vor** dem TLS-Handshake ankommt. Gunicorn kann ihn
dort nicht lesen: Seine Option `proxy_protocol` parst diesen Header beim
Parsen von HTTP, was erst geschieht, nachdem TLS terminiert ist, also landen
die Bytes des Headers im Handshake und brechen ihn mit
`WRONG_VERSION_NUMBER`. Gefunden wurde das beim Deployen, nicht beim Testen.

HAProxy akzeptiert beides auf einem Bind – `accept-proxy ssl crt ...` –, also
bringt die Anwendung ihre eigene Instanz mit, die außerdem die einzige
Komponente ist, die auf einem Port lauscht. Gunicorn bindet stattdessen einen
Unix-Socket, was bedeutet, dass es keinen Weg in die Anwendung gibt, der nicht
durch den Proxy geht, und die echte Client-Adresse als `X-Forwarded-For`
erhalten bleibt – ohne sie würde die Ratenbegrenzung der Anmeldung für alle
127.0.0.1 sehen und nicht mehr pro Adresse wirken.

Es ist HAProxy und nicht nginx, weil das Deployment bereits von HAProxy
abhängt: keine neue Technologie für ein Problem, das eine vorhandene löst.

Das HAProxy der Maschine darf auf diesem Backend kein
`option ssl-hello-chk` verwenden: Das ClientHello dieser Prüfung ist älter als
TLS 1.2, also scheitert sie an einem Bind, der TLS 1.2 verlangt, und markiert
das Backend für immer als ausgefallen. Das Symptom ist ein 503 von einem
Dienst, der einwandfrei läuft, und das zu wissen lohnt sich, weil nichts in
den eigenen Logs der Anwendung sagt, dass etwas nicht stimmt.

Und die Prüfung muss an 11080 anklopfen, nicht an 11443. Eine TCP-Prüfung
gegen den TLS-Bind verbindet sich und legt ohne Handshake auf, und dieses
HAProxy protokollierte jede davon als „SSL handshake failure“ – gemessen auf
der Debian-Testmaschine 64.075 Zeilen in zwei Tagen, eine alle zwei
Sekunden, die alles Echte im Journal begruben. `check-ssl verify none` wurde
zuerst versucht und tauschte eine Zeile gegen eine andere: Das abrupte
Schließen der Prüfung kam an, während der Handshake noch abgeschlossen
wurde, und jede Prüfung protokollierte entweder das oder `ECONNRESET`. Gegen
11080 ist dasselbe Verbinden und Schließen eine Null-Session, die
`option dontlognull` aus dem Log heraushält, beide Ports gehören zu einem
Prozess, und das Journal wurde still: null Zeilen in dreißig Sekunden,
während die Site von außen mit 200 antwortete.

Das Backend auf dem HAProxy der Maschine ist also vollständig:

```
backend https-out
  mode tcp
  server srv-https-out 127.0.0.1:11443 check port 11080 send-proxy
```

`send-proxy` ist das, was die Client-Adresse transportiert.
`check-send-proxy` ist mit Absicht weggelassen: 11080 akzeptiert das
PROXY-Protokoll nicht. Die Fassung davon für Betreiber steht in
MANUAL.de-DE.md, unter „Wie das HAProxy der Maschine aussehen muss“.

Es legt kein `maxconn` fest, und das ist kein Versehen. `maxconn 2048`
verlangt vom Kernel 4131 Dateideskriptoren, und HAProxy beendet sich, statt
ohne sie zu starten: *Cannot raise FD limit to 4131, current limit is 1024 and
hard limit is 4096*. Gemeldet von einem Alpine-LXC unter OpenWrt auf einem
BPI-R3, dessen hartes Limit 4096 ist: `boa-proxy` wurde siebzigmal neu
gestartet, nichts lauschte je auf 11443, und eine Erstinstallation endete bei
„The application did not answer on port 11443 (last code: 000)“. Beide
Testmaschinen sind Proxmox-LXCs mit einem harten Limit von 524288, weshalb es
keine von beiden je zeigte, und `haproxy -c` akzeptierte die Datei auf jeder
davon – die Konfiguration war nie ungültig, der Prozess starb beim Start.
Ohne `maxconn` bemisst sich HAProxy nach den Deskriptoren, die es tatsächlich
haben kann, was seine eigene Meldung verlangt, und `fd-hard-limit 4000`
deckelt, was es nimmt, wo das Limit riesig ist. Gemessen mit einem Binary bei
drei harten Limits: 4096 ergibt maxconn 1987, 1024 ergibt 499, 524288 ergibt 1987.
Ein Test startet das echte haproxy mit der ausgelieferten Datei unter
einem harten Limit von 4096 und verlangt, dass es oben bleibt, und startet es
noch einmal mit dem alten `maxconn 2048` und verlangt, dass es stirbt – ein
Test, der nur die Datei las, ist genau der Grund, warum das überhaupt
übersehen wurde.

Drei Dinge brauchen wirklich root: einen Systembenutzer anlegen, den Crontab
eines anderen Benutzers installieren und einen Prozess als anderer Benutzer
starten. Alles andere nicht. Also lebt root in einem kleinen Daemon mit einem
**geschlossenen Vokabular von Verben** über einen Unix-Socket, und es gibt
absichtlich kein Verb, das „führe diesen Befehl aus“ bedeutet. Ein Angreifer,
der diesen Socket erreicht, kann einen unprivilegierten Agenten anlegen; er
kann keinen Code als root ausführen.

Der Socket ist `0660 root:boa`, und `SO_PEERCRED` wird bei jeder Verbindung
geprüft, sodass nur root und `boa` bedient werden, egal was der Dateimodus
nach irgendeinem künftigen Update gerade sagt.

### Eine Änderung muss von den eigenen Seiten dieser Site kommen

Das Session-Cookie ist `SameSite=Lax`, was verhindert, dass eine Anfrage von
einer anderen Site es mitschickt. Es hält aber keinen anderen ORIGIN auf
derselben Site fern: Ein Agent mit `bash.run` kann auf genau diesem Host eine
Seite ausliefern, auf einem eigenen Port, und ein Link darauf aus einer
Chat-Antwort ist nur einen Klick entfernt. Ein Formular dort, das an
`/api/admin/agents/000/run` sendet, ist eine Same-Site-Anfrage, das Cookie
reist mit, und der Lauf startet; da es ein einfaches POST ohne Body ist,
steht auch kein Preflight im Weg. Deshalb antwortet
`fRefuseChangesFromElsewhere`, ein `before_request` auf dem API-Blueprint,
mit 403 auf jedes POST, PUT, PATCH oder DELETE, das nicht von den eigenen
Seiten dieser Site kam: Ein `Origin`-Header muss genau diesen Host und Port
nennen – `localhost` und `localhost:8080` sind zwei Origins, und der zweite
ist genau die Seite, die ein Agent ausliefern könnte –, und ein
`Sec-Fetch-Site`-Header muss `same-origin` sagen. Eine Anfrage mit keinem von
beiden stammt nicht von einem Browser, sondern von einem Skript oder den
Tests, und wird wie bisher der Anmeldung zur Beurteilung überlassen. Ein GET
wird nicht gesperrt: Es ändert nichts, und eine Seite von anderswo kann die
Antwort nicht lesen, weil es keine CORS-Header gibt, die ihr das erlauben.

### Die Agenten-API, und warum es sie überhaupt gibt

Zwei Dinge gehören `boa` und dürfen für Agenten nicht lesbar sein: die
Kanban-Datenbank (ein Agent, der sie direkt schreiben könnte, könnte den
Verlauf eines anderen Agenten umschreiben) und die Zugangsdaten der Kanäle
(ein Bot-Token ist keine Nachricht – es ist die dauerhafte Befugnis zu
senden).

Also erreichen Agenten beides über `boa-agent-api`, über einen zweiten
Unix-Socket, den jeder Agent öffnen kann. Die Autorisierung besteht aus zwei
unabhängigen Prüfungen:

1. Das vorgelegte Token stimmt mit dem gespeicherten SHA-256 des Tokens
   irgendeines Agenten überein.
2. `SO_PEERCRED` sagt, dass der aufrufende Prozess dem Benutzer *dieses*
   Agenten gehört.

Jede allein wäre schwächer: Ein durchgesickertes Token ist vom falschen Konto
aus nutzlos, und das richtige Konto zu sein ist ohne das Token nutzlos.

Es ist ein Unix-Socket und kein HTTPS, weil TLS zwischen zwei Prozessen auf
einer Maschine nichts bringt, und ein selbstsigniertes Zertifikat würde
bedeuten, dass jeder Agent mit abgeschalteter Überprüfung läuft – was
schlimmer ist als kein TLS, weil es wie Sicherheit aussieht.

### Wo der Zustand liegt, und warum er aufgeteilt ist

| Zustand | Wo | Warum dort |
|---|---|---|
| Agentenkonfiguration | `agents/xxx/info.json` | Der Agent muss sie als er selbst lesen |
| Agentenverlauf | `agents/xxx/runs.jsonl` | Der einzige Ort, an den ein Agent schreiben kann |
| Gemeinsame Abläufe | `skills/<Name>/SKILL.md` (root, 0755) | Von jedem Agenten gelesen, dem sie gegeben wurden, von keinem geschrieben |
| Agentenindex, Anmeldung, Einstellungen | `db/boa.sqlite` (0700 `boa`) | Der Webprozess braucht sie |
| Das Board | `kanban/kanban.sqlite` (0700 `boa`) | Viele gleichzeitige Schreiber |

Es gibt absichtlich **keine Tabellen `runs` oder `usage`**. Ein
Agentenprozess kann die Datenbank, die `boa` gehört, nicht öffnen, und ihm
Schreibzugriff zu gewähren, würde jeden Agenten den Verlauf jedes anderen
umschreiben lassen. Stattdessen hängt jeder Agent an sein eigenes Journal an,
und die Webanwendung liest diese über `boa-exec`. Der Nebeneffekt ist, dass
ein Agent auch dann festhält, was er getan hat, wenn die Webanwendung nicht
läuft.

Das Board ist SQLite und kein Verzeichnis voller JSON-Dateien, weil mehrere
Agenten, die in derselben Cron-Minute aufwachen, der Normalfall sind, und nur
eine Transaktion verhindert, dass sich zwei gleichzeitige Hinzufügungen
gegenseitig überschreiben.

### Was ein Backup enthält

`--backup` schreibt ein Archiv mit allem, was die Installation ist und der
Code nicht, und `--restore` setzt eines an die Stelle dessen, was eine
Maschine hat; beide sind in beiden Installern, Funktion für Funktion. Die
Liste ist die Tabelle oben, in eine `tar`-Zeile verwandelt: die beiden
Datenbanken, die Schlüssel und Kanäle, die Zertifikate, jeder Agent mit
seinem Home-Verzeichnis und seinen geschützten Dateien, die Fähigkeiten und
die Werkzeuge. Drumherum drei Dinge, die ein `tar` von `/opt/boa` falsch
machen würde:

- **Die Datenbanken gehen über die Backup-API von SQLite**,
  `fCopySqliteDatabase`, und nicht über `cp`. Beide laufen im WAL-Modus,
  sodass einer Kopie der `.sqlite`-Datei fehlt, was noch in der `-wal`-Datei
  steht, und eine mitten im Schreiben gezogene Kopie zerrissen sein kann. Das
  `python3` der venv hat das Modul; der Befehl `sqlite3` ist auf keiner der
  beiden Distributionen vorhanden. Derselbe Grund wirkt beim Wiederherstellen
  in die andere Richtung: Die alten `-wal`- und `-shm`-Dateien werden
  entfernt, bevor die wiederhergestellte Datei gelesen wird, sonst würde
  SQLite das alte Log auf sie anwenden.
- **Agentenbenutzer reisen per Name.** `agents.txt` hält Benutzer, uid und
  gid jedes Agenten fest, und `fRestoreAgentUsers` legt die fehlenden immer
  mit demselben Namen und mit denselben IDs an, wenn diese frei sind. Der
  Besitz im Archiv wird beim Entpacken per Name zugeordnet, sodass ein `boa`
  oder ein `agent-001` mit einer anderen uid auf der neuen Maschine weiterhin
  seine Dateien besitzt. Crontabs liegen im Cron-Spool, nicht unter
  `/opt/boa`, also werden sie mit `crontab -l` ausgelesen und mit
  `crontab -u` zurückgelegt.
- **Drei Dateien werden absichtlich weggelassen**: `config/ports.conf`,
  `config/browser.conf` und die daraus erzeugte `haproxy.cfg` beschreiben
  DIESE Maschine, und eine Wiederherstellung darf nicht die Entscheidungen
  einer anderen Maschine importieren. Das Installationslog reist als
  `install.log.backup`, unter anderem Namen, damit eine Wiederherstellung nie
  das Log überschreibt, das gerade in diesem Moment geschrieben wird; seine
  Zeilen mit Zugangsdaten werden an das aktuelle Log angehängt, weil die
  Anmeldung nach einer Wiederherstellung die des Backups ist.

Die Wiederherstellung ist die eine Aktion, die Daten ersetzt und sich nicht
rückgängig machen lässt, also bestätigt sie wie eine Neuinstallation. Beide
Funktionen werden von den Tests über einem echten Baum ausgeführt, unter bash
und unter dash: Das Archiv wird darauf geprüft, was es enthält und was es
weglässt, der Baum wird auf jede Weise beschädigt, die eine Wiederherstellung
rückgängig machen muss, und die Wiederherstellung wird Datei für Datei
geprüft.

### Eine Fähigkeit wird im Prompt indexiert und bei Bedarf abgerufen

Das Gedächtnis eines Agenten wird vollständig in jeden System-Prompt geladen,
und für ein Gedächtnis ist das richtig: Sein Zeichenlimit ist pro Agent
einstellbar (standardmäßig 8.000, erlaubt 1.000–1.000.000), und es ist das
Einzige, was der Agent sich nicht wieder erarbeiten kann.

Fähigkeiten sind nicht so. Ein Ablauf umfasst eine oder zwei Seiten, ein
Agent kann mehrere bekommen, und die meisten Läufe brauchen keinen davon – die
Plattenprüfung braucht den Zertifikatsablauf nicht. Sie so zu laden wie das
Gedächtnis, hieße, bei jedem Aufruf jedes Laufs für alle zu bezahlen, und die
Obergrenzen in `info.json` werden in Token gemessen.

Deshalb trägt der Prompt einen Index – eine Zeile pro Fähigkeit, ihr Name und
ihre Beschreibung –, und der Inhalt wird mit `skill.read` abgerufen, einmal,
von einem Agenten, der entschieden hat, dass er ihn braucht. Fünf Fähigkeiten
kosten etwa 200 Token pro Lauf statt 10.000, und die, die gelesen wird, wird
einmal berechnet statt bei jedem Aufruf.

Die Beschreibung im Kopf ist daher der tragende Teil: Auf ihrer Grundlage
entscheidet der Agent, und für sie bezahlt jeder Lauf, ob die Fähigkeit
gelesen wird oder nicht.

### Fähigkeiten gehören root, wie die Werkzeuge

Ein Werkzeug gehört root, weil die Anwendung es als Code importiert. Eine
Fähigkeit wird von nichts ausgeführt, aber sie wird dem Denken eines Agenten
vorangestellt, der um vier Uhr morgens aufwacht, ohne dass jemand zusieht,
was sie genauso heikel macht wie `system-prompt.md` – und diese Datei liegt
bereits in einem Verzeichnis, das der Agent lesen und nicht beschreiben darf.

Deshalb gibt es in der Weboberfläche keinen Editor für Fähigkeiten und kein
privilegiertes Verb, um eine zu schreiben. Fähigkeiten werden per SSH auf dem
Server geschrieben. Die Oberfläche entscheidet, welcher Agent welche bekommt,
und das ist dasselbe, was sie für Werkzeuge tut.

Die andere Hälfte dieser Entscheidung ist, wo sie liegen: `/opt/boa/skills/`,
außerhalb von `webapp/`, weil `fDeploySourceCode` ein `rm -rf` auf `webapp`
ausführt und ein Ablauf, den jemand auf diesem Server geschrieben hat, nichts
ist, was ein Update löschen darf. Dieselbe Begründung, derselbe Platz im Baum
wie `/opt/boa/tools/`.

Die Anwendung liefert keine mit. Es gibt kein `backend/skills/`, und die
Installer kopieren nichts in dieses Verzeichnis: Sie legen es leer an, root
gehörend und 0755. Eine Fähigkeit ist ein Ablauf für EINE Installation – diese
Hosts, dieses Backup, dieses Zertifikat –, eine generische wäre also ein
Ablauf, dem niemand folgt und der eine Zeile in jedem Prompt jedes Laufs
belegt, um das zu sagen. Dass das Verzeichnis bei einer frischen Installation
leer ist, ist die Funktion, die funktioniert, kein fehlendes Teil.


### `deploy/` wird nicht deployt

`/opt/boa/webapp/` enthält `backend/` und `frontend/` und sonst nichts. Das
Verzeichnis `deploy/` – die Units, die beiden HAProxy-Konfigurationen, die
Agentenvorlagen, die Anbieterkataloge, `requirements.txt` und der Installer
selbst – ist das eigene Material des Installers, und es wird aus dem Baum
gelesen, den der Installer gerade nach `/tmp` heruntergeladen hat und der
weggeworfen wird, wenn er endet.

Das ist nicht nur Ordnungsliebe. Die Units aus einer Kopie unter `/opt/boa` zu
lesen hieß, die Units der Version zu installieren, die gerade zufällig auf
der Platte lag; sie aus dem heruntergeladenen Baum zu lesen installiert die
Units der Version, die deployt wird, und das ist das einzige Paar, über das
man nachdenken kann. Jeder dieser Lesevorgänge ruft zuerst
`fRequireSourceCode` auf, sodass ein Schritt, der je vor dem Download läuft,
mit einem Satz scheitert, statt aus `/deploy/...` zu kopieren.

Das ist auch der Grund, warum `gunicorn.conf.py` in `backend/web/` liegt und
nicht in `deploy/`: gunicorn liest sie bei jedem Start, also muss sie eine
Datei sein, die tatsächlich auf dem Server ist, und das Verzeichnis, das auf
dem Server ist, ist das mit dem Code, den sie konfiguriert.

Was deployt wird, ist `root:root`, Verzeichnisse `00755` und Dateien `0644`,
gesetzt von `fSetCodeModes` und von nichts anderem. Nichts unter `webapp/`
wird über seinen Pfad ausgeführt – der Daemon startet den Runner als
`venv/bin/python3 .../runner.py`, und ebenso der Crontab, den er für jeden
Agenten schreibt –, also braucht keine Datei dort das Ausführungsbit. Sie
hatte es trotzdem, bis das eine einzige Funktion wurde: `fDeploySourceCode`
setzte `0644`, und `fCreateDirectoryTree`, das bei einem Update danach läuft,
führte dann `chmod -R 00755` über denselben Baum aus.

### Telegram bekommt HTML und fällt auf die Worte zurück

Ein Modell schreibt Markdown. Roh angezeigt ist das `**25G free**` mit den
Sternchen mitten im Satz, und genau das kam bis dahin auf einem Handy an.

Telegram rendert eine kleine HTML-Teilmenge – vierzehn Tags, keine Attribute,
die den Namen verdienen, und keine Überschrift, Liste oder Tabelle darunter.
Also übersetzt `telegram_html`, wofür es ein Tag gibt, und findet für den
Rest eine lesbare Form: Überschriften werden fett auf einer eigenen Zeile,
Listeneinträge bekommen einen Aufzählungspunkt, und eine Tabelle wird zu
einem aufgefüllten `<pre>`-Block, was die einzige Möglichkeit ist, Spalten auf
einem Handy untereinander zu halten.

Drei Dinge daran sind tragend.

**Das Escapen kommt zuerst.** `&`, `<` und `>` sind für Telegram Markup,
sodass ein Agent, der `grep <dev> && echo` meldet, eine Nachricht erzeugt, auf
die Telegram mit einem 400 antwortet – also eine Nachricht, die nie ankommt.
Jedes Stück Text geht durch `fEscape`, bevor irgendetwas es umschließt. Ein
href geht durch `fEscapeAttribute`, das auch das doppelte Anführungszeichen
escapt: Eine URL, die eines enthält, würde das Attribut schließen und ihren
Rest in Attribute verwandeln, die niemand geschrieben hat.

**Eine abgelehnte Nachricht wird erneut als reiner Text gesendet.** Was auch
immer der Renderer falsch gemacht hat, die Worte sind mehr wert als die
Formatierung, also wird ein 400 ohne `parse_mode` wiederholt, und die Zeile
geht unformatiert hinaus. Der Rückfall protokolliert, was Telegram gesagt
hat, denn eine Formatierung, die stillschweigend für immer verfällt, ist eine
Formatierung, die niemand repariert.

**Eine Antwort, die Telegram ablehnt, wird verworfen, und eine, die es nicht
annehmen kann, wird eine Stunde lang behalten.** `fSay` gibt drei Dinge
zurück und nicht zwei: gesendet, nicht beantwortet und abgelehnt – ein 4xx
außer 429, `ChannelRejected`, also Telegram, das Nein zu dieser Nachricht
sagt und es auch morgen meint: der Bot blockiert, der Chat weg, das Token
widerrufen. `fDeliverAnswers` behielt früher die Zeile bei jedem Fehler und
versuchte es im nächsten Durchgang erneut, und die Zeile liegt auf der
Platte, damit ein Neustart keine Antwort verliert, sodass ein blockierter
Bot den Listener in eine Schleife verwandelte, die nie endete: das Polling im
schnellen Modus, ein Lesen des Chats über den root-Daemon und bis zu zwei
Anfragen an Telegram bei jedem Durchgang, über jeden Neustart hinweg. Eine
abgelehnte Antwort wird sofort verworfen, mit einer Zeile, die das sagt, und
eine Antwort, die Telegram nicht innerhalb der Stunde angenommen hat, die
einem Lauf gegeben wird, wird ebenfalls verworfen, aus demselben Grund, aus
dem der andere Zweig einen Lauf aufgibt, der nie fertig wurde. Keines von
beiden verliert die Antwort: Sie steht im Gespräch des Agenten in der
Weboberfläche, wo sie zuerst geschrieben wurde.

Die Muster sind dieselben, die `frontend/static/js/markdown.js` verwendet.
Zwei Renderer, die sich uneinig sind, was als Markdown zählt, würden bedeuten,
dass sich eine Antwort an den zwei Orten, an denen sie angezeigt wird,
unterschiedlich liest, und der Sinn davon, an beide zu senden, ist, dass es
dasselbe Gespräch ist.


### Discord wird gepollt, und eine Antwort hat zweitausend Zeichen

Discord ist der zweite Kanal, über den ein Mensch einem Agenten antworten
kann, und die empfangende Hälfte ist `discord_listener` –
`boa-channel-discord`, der siebte Dienst. Vier Dinge unterscheiden ihn von
dem für Telegram.

**Er pollt, über REST.** `GET /channels/<id>/messages?after=<id>`, alle fünf
Sekunden und alle zwei, während ein Agent mitten in einer Antwort ist. Das
Gateway ist die naheliegende Alternative und wurde nicht gewählt: Es ist ein
WebSocket, der Heartbeats, ein Resume-Protokoll und eine Abhängigkeit
braucht, die dieses Projekt nicht hat, und es braucht den im
Entwicklerportal eingeschalteten Message Content Intent – ohne den jede
Nachricht mit leerem `content` ankommt und nichts sagt, warum. Polling
verbindet außerdem nach außen, und das lässt es in einem LAN laufen, in dem
nichts weitergeleitet wird, genau wie das Long Polling von Telegram. Was es
kostet, ist eine in Sekunden gemessene Latenz und zwölf Anfragen pro Minute
bei einem Limit von fünfzig pro Sekunde.

**Zweitausend Zeichen, nicht viertausend.** `channels.cMaxMessageLength` ist
4096, die Obergrenze von Telegram, und Discord antwortet mit 400 auf einen
`content`, der länger als 2000 ist. Eine lange Antwort kam nicht gekürzt an –
sie kam gar nicht an. `discord_markdown` schneidet sie zwischen Zeilen in
höchstens vier Nachrichten, und ein umzäunter Block, in dem ein Schnitt
landet, wird am Ende der einen geschlossen und am Anfang der nächsten wieder
geöffnet: Ohne das kommt eine Hälfte als reiner Text an und die andere als
ein Block, der nie endet, was in Discord alles verschluckt, was danach gesagt
wird. Jeder Teil wird als der dieses Agenten festgehalten, weil ein Mensch
auf den antwortet, der gerade auf seinem Bildschirm steht.

**Keine Buttons, und `!` für Befehle.** Ein Buttondruck und ein
Slash-Befehl sind beide *Interaktionen*, und eine Interaktion kommt über das
Gateway oder über einen HTTPS-Endpunkt, den Discord erreichen kann. Ein
gepollter Kanal sieht keines von beiden. Also ist `/agents` `!agents`, eine
gewöhnliche Nachricht, und die Liste ist eine Liste von Namen zum Abtippen
statt einer Spalte von Buttons. `/agents` wird ebenfalls akzeptiert, weil
jemand, der den Telegram-Bot eingerichtet hat, es aus Gewohnheit tippen wird.

**Die Antwort eines Agenten erwähnt niemanden.** Jede Nachricht, die dies
sendet, trägt `allowed_mentions: {"parse": []}`, sodass ein `@everyone`, das
ein Modell schreibt, Text ist und keine Benachrichtigung an einen ganzen
Server. `replied_user` bleibt eingeschaltet: Eine Antwort soll den Menschen
erreichen, der gefragt hat. Eine Regel am Socket statt in einem Prompt, aus
demselben Grund, aus dem es die Weiterleitungsliste für Mail ist.

Was Discord nicht hat, ist das Schweigen von Telegram gegenüber Fremden. Es
gibt keine `chat_id`, mit der man vergleichen könnte: Der Bot fragt nach
einem Kanal und liest diesen Kanal, also darf mit den Agenten sprechen, wer
darin schreiben darf. Ein privater Kanal ist die Konfiguration, die dem
entspricht, was `fIsFromTheConfiguredChat` im Code durchsetzt – und sie wird
im Handbuch genannt, weil sie die gesamte Autorisierung ist.

Der Webhook, den dieser Kanal vorher hatte, ist noch da und sendet weiterhin.
Ein Webhook kann nicht lesen, nicht antworten und bekommt keine
Nachrichten-ID zurück, also wird `listen` über einen Webhook abgelehnt statt
angeboten: Ein Schalter, der nichts tut, ist schlimmer als kein Schalter.

### Ein Routing, zwei Listener

`agent_routing` enthält, was beide Listener identisch tun: welche Agenten es
gibt, einen Namen aus `@News Miner`, `/news_miner` oder `@002` herauslesen,
wobei der längste Treffer gewinnt, was ein Agent gesagt hat, um eine
Gesprächsrunde zu schließen, und den Statusbericht. Das Protokoll bleibt in
jedem von ihnen – ein Long Poll ist kein REST-Poll, eine Inline-Tastatur ist
keine Liste von Namen, und eine Antwort ist im einen `reply_to_message` und
im anderen `message_reference`.

Es wurde geschrieben, als der zweite Listener geschrieben wurde, und der
Statusbericht ist der Grund. Zwei Kopien dieser Antwort wären zwei Antworten
auf „läuft es“, und das Erste, worüber sie uneins wären, ist, wie viele
Dienste es gibt.

Das Senden ist nicht darin. Es bleibt in jedem Listener als `fSay`, und das
lässt einen Test das eines Listeners ersetzen und das andere in Ruhe lassen.

### Ein Browser, geteilt; ein Profil, nicht

`web.fetch` liest eine öffentliche Seite und hört dort auf: keine Sitzung,
kein Formular, kein Button. Der Browser ist das andere, und er teilt sich in
zwei:

| | Wo | Wem es gehört |
|---|---|---|
| Der Browser | `/opt/boa/playwright/` | root, 0755, eine Kopie |
| Das Profil | `agents/xxx/browser/profile/` | dem Agenten, 0700, eines pro Agent |

Das Binary wird geteilt, weil es ein Binary ist und es daran nichts zu
isolieren gibt; eine Kopie pro Agent wären jeweils 600 MB und ein Update, das
man N-mal machen müsste. Das Profil wird nicht geteilt, weil es die Cookies
enthält: Wenn sich Agent 007 irgendwo anmeldet, darf Agent 008 danach nicht
angemeldet sein. Diese Trennung leistet der Kernel, dasselbe
0700-Home-Verzeichnis, in dem alles andere eines Agenten liegt – und genau
das kann ein gehostetes Agentenprodukt nicht bieten, wenn alle seine Agenten
eine Maschine und einen Satz Sitzungen teilen.

Drei Entscheidungen folgen daraus:

**Der Browser bleibt innerhalb eines Laufs über Werkzeugaufrufe hinweg
offen.** `browser.click` wirkt auf das, was `browser.open` auf dem Bildschirm
hinterlassen hat, und ein Lauf ist ein Prozess vom ersten Werkzeugaufruf bis
zum letzten, also ist ein Handle auf Modulebene der gesamte Zustand, der
gebraucht wird. `atexit` schließt ihn; ohne das hinterlässt ein stündlicher
Agent bei jedem Lauf ein Chromium und füllt die Maschine bis zum Morgen.

**Playwright wird innerhalb der Funktionen importiert, nie auf Modulebene.**
Die Browserwerkzeuge werden in der Oberfläche aufgeführt, ob ein Browser
installiert wurde oder nicht, und ein ImportError ganz oben würde sie ohne
jede Erklärung aus dieser Liste verschwinden lassen. Spät importiert ist ein
fehlender Browser ein Satz, der sagt, welcher Befehl auszuführen ist.

**Headless, und nur öffentliche Adressen.** Gewollt sind die Sitzung und das
DOM, nicht das Bild eines Fensters, also wäre ein virtuelles Display ein
bewegliches Teil für nichts.

„Nur öffentliche Adressen“ wird von einem Route-Handler durchgesetzt, der auf
dem KONTEXT installiert ist (`browser.fInstallNetworkPolicy`), nicht von
jedem Werkzeug. Die URL in `browser.open` zu prüfen deckte genau eine Adresse
pro Lauf ab: Eine Seite darf frei umleiten, und eine Seite, die ein Agent
lesen soll, darf frei einen Link, ein iframe, ein Bild oder ein Formular
enthalten, das auf `127.0.0.1` zeigt – und `browser.click` hatte überhaupt
keine Prüfung. Auf dem Kontext deckt er Navigationen, Weiterleitungen,
Klicks, Formularabsendungen und jede Unterressource ab, und das sechste
Browserwerkzeug, das jemand schreibt, bekommt ihn, ohne zu wissen, dass es
ihn gibt. Was abgewiesen wird, wird in der Antwort des Werkzeugs genannt,
weil eine blockierte Anfrage sonst unsichtbar ist: Die Seite rendert ohne sie,
und der Agent verbraucht sein Budget mit neuen Versuchen.

Hostnamen werden einmal pro Lauf aufgelöst und gemerkt, was das Fenster, in
dem ein Name für die Prüfung öffentlich und für die Verbindung privat
aufgelöst werden könnte, begrenzt statt beseitigt. Es zu schließen, bräuchte
eine Verbindung, die an die geprüfte Adresse gebunden ist, und das stellt
Chromium von hier aus nicht bereit.

Ein Session-Cookie verschwindet weiterhin, wenn der Browser geschlossen wird,
hier wie in jedem Browser. Was überlebt, ist das, was die Site zum Überleben
markiert hat.

### Was ein Anbieter akzeptiert, ist nicht das, was der Standard sagt

Zwei Adapter schickten etwas, das ihr Anbieter ablehnt, und in beiden Fällen
war das Ergebnis dasselbe: Jeder Werkzeugaufruf über diesen Anbieter
scheiterte, bei jedem Modell, und nichts in der Testsuite bemerkte es, weil
die Suite die Einzelteile testete statt den ganzen Hin- und Rückweg.

| Anbieter | Was gesendet wurde | Was zurückkam |
|---|---|---|
| Ollama | `kanban__list_cards`, zu nichts zurückdekodiert | Die Registry lehnte ein Werkzeug ab, das dem Agenten nicht gewährt worden war – den Namen, der ihm gerade angeboten worden war |
| Google | `"additionalProperties": false`, was korrektes JSON Schema ist | `400 - Unknown name "additionalProperties" at 'tools[0].function_declarations[0].parameters'` |

`function_declarations[].parameters` von Gemini ist eine TEILMENGE von JSON
Schema und lehnt ab, was es nicht kennt, statt es zu ignorieren, deshalb
filtert `fCleanSchemaForGoogle` das Schema rekursiv durch eine Allowlist.
Eine Allowlist und keine Denylist, aus dem Grund, aus dem jede Allowlist hier
eine ist: Den nächsten Schlüssel, den jemand einem Werkzeugschema hinzufügt,
würde Gemini sonst ablehnen, ob nun jemand daran gedacht hat, ihn auf eine
Liste der zu entfernenden Dinge zu setzen, oder nicht.

Beide wurden gefunden, indem der ganze Zyklus – fragen, ein Werkzeug
aufrufen, diesen Aufruf beantworten – gegen die echten APIs mit echten
Schlüsseln durchlaufen wurde. `_/temp/probe-defaults.py` ist diese Prüfung,
und sie ist das Einzige, was diese Art von Fehler findet: ein Schema, das
gültig ist, ein Name, der korrekt ist, und ein Anbieter, der es nicht nimmt.

### Eine Adapterdatei pro Anbieter

Fünfundzwanzig Anbieter, fünfundzwanzig Dateien, obwohl die meisten denselben
Dialekt sprechen. Ein einziger „OpenAI-kompatibler“ Adapter sieht ordentlich
aus, bis einer dieser Anbieter einen Feldnamen ändert, und dann muss die
Korrektur gemacht werden, ohne die anderen zwanzig kaputtzumachen. Jede Datei
trägt die Eigenheiten ihres eigenen Anbieters: DeepSeek verwirft
`reasoning_content`, bevor der Runner es erneut abspielen kann, llama.cpp
erkennt eine Chat-Vorlage ohne Werkzeugunterstützung, vLLM verwandelt einen
404 in die Liste der Modelle, die es tatsächlich ausliefert, Cloudflare baut
seine Adresse aus dem Zugangsschlüssel.

Was sie teilen, ist `base.py`: eine neutrale Nachrichtenform nach dem Vorbild
von chat/completions, weil die meisten das schon sprechen, und der
Anthropic-Adapter übersetzt in Content-Blöcke.

Sie teilen außerdem `openai_dialect.py`, und der Unterschied zwischen diesem
und einem geteilten Adapter ist der springende Punkt. Das Dialektmodul
enthält die Anfrage selbst – das POST, die HTTP-Fehler, die es wert sind,
benannt zu werden, das Parsen der Antwort –, was keine Eigenheit irgendeines
Anbieters ist. Die Eigenheiten bleiben in jeder Datei, deklariert als
Klassenattribute, die das Modul liest:

| Attribut | Was es entscheidet |
|---|---|
| `cDisplayName` | Der Name in jeder Fehlermeldung. „zai request failed“ ist nicht das, wonach jemand suchen würde |
| `cMaxTokensField` | `max_tokens` oder `max_completion_tokens`, je nachdem, welcher Schreibweise der Anbieter gefolgt ist |
| `cToolChoiceMode` | `auto`, `any` oder `omit` für die Anbieter, die das Feld ablehnen. `auto` ist das, was ein Agent braucht: Ein Modell, das gezwungen wird, in jeder Runde ein Werkzeug aufzurufen, beendet nie einen Lauf |
| `cChatCompletionsPath` | Der Pfad nach der Basis-URL, für die wenigen, die nicht den üblichen verwenden |
| `cAssistantContentWhenEmpty` | Was statt eines `content` mit null gesendet wird, für einen Anbieter, dessen Schema null ablehnt |

### Was zweiundzwanzig echte Schlüssel verändert haben

Jeder Anbieter hier wurde mit einem echten Schlüssel aufgerufen, bekam eine
Frage gestellt und ein Werkzeug gegeben und dann die Antwort auf den
Werkzeugaufruf zurückgereicht, den er gemacht hatte. Alle zweiundzwanzig, die
einen Schlüssel haben, schaffen diesen Hin- und Rückweg. Sieben Dinge zeigten
sich erst beim zweiten Schritt
– dem, den ein Test mit einer vorgefertigten Antwort nie erreicht –, und jedes
ist jetzt eine Codezeile mit den eigenen Worten des Anbieters daneben:

- **Perplexity hatte den Endpunkt stillgelegt.** `chat/completions` antwortet
  mit 403 „Sonar is now the Agent API. Use /v1/responses instead of
  /v1/sonar“, also wurde dieser Adapter gegen die Responses-API neu
  geschrieben, und der Anbieter wurde von einem Modell zu einem Router über 48
  davon.

- **Ein Schlüssel in einer Fehlermeldung.** Gemini wurde als `?key=...`
  aufgerufen, sodass ein 503 von dort den ganzen Schlüssel in den Fehler
  setzte, den der Benutzer liest und das Journal aufbewahrt. Der Schlüssel
  ist in den Header `x-goog-api-key` umgezogen, und
  `base.fRedactCredentials` entfernt jetzt `key=`, `api_key=`,
  `access_token=` und `token=` aus jedem Fehler, den irgendein Adapter
  erzeugt, denn diese Fehlerart sollte nicht davon abhängen, dass ein Adapter
  daran denkt.
- **Gemini 3 will seine Gedankensignatur zurück.** Ein Gespräch, dessen
  Funktionsaufrufe ohne die ausgegebene Signatur zurückkommen, wird rundweg
  abgelehnt, sodass jeder Gemini-Agent in dem Moment scheiterte, in dem er ein
  Werkzeug benutzt hatte. `ToolCall.dProviderData` trägt sie hin und zurück,
  undurchsichtig für alles andere.
- **Cloudflare lehnt einen `content` mit null ab.** Und genau das enthält
  eine Assistentennachricht, wenn das Modell mit Werkzeugaufrufen und ohne
  Worte geantwortet hat. Sie bekommt `""`; der Dialekt schickt allen anderen
  weiterhin null, weil null das ist, was der Dialekt vorschreibt.
- **In die Antwort geschriebenes Reasoning.** MiniMax antwortet mit
  `<think>...</think>` im Text selbst. Im Dialektmodul entfernt und nicht in
  einem Adapter, weil das Modell es tut, und dasselbe Modell hinter einem
  Gateway tut es also auch – und nur, wenn die Antwort mit dem Tag BEGINNT,
  damit ein Modell, das über HTML schreibt, seine Worte behält.
- **Together lässt den Kanalnamen vorne stehen.** gpt-oss schreibt in Kanälen,
  und Together gibt „finalThe weather in Madrid“ zurück; Groq und Cerebras,
  die dasselbe Modell ausliefern, tun das nicht. Entfernt in `together.py`,
  wohin eine Eigenheit eines einzelnen Anbieters gehört.
- **Vier Standardmodelle, die der Anbieter nicht ausliefern wollte.** Das
  20b von Fireworks braucht ein eigenes Deployment, das von Together ist
  nicht serverless, Moonshot hat kimi-k2.5 stillgelegt, und gemini-3.7-flash
  antwortet mit 503 „experiencing high demand“. Ein Standard, der beim ersten
  Lauf scheitert, ist schlimmer als einer, der eine Version zurückliegt.

Fünf Adapter benutzen es überhaupt nicht, weil ihre API nicht diese ist: die
Content-Blöcke von Anthropic, `generateContent` von Google, `/completion` von
llama.cpp, der v2-Chat von Cohere – der dieselben Nachrichten nimmt, aber mit
Text in Blöcken antwortet, mit einem eigenen großgeschriebenen Endgrund und
mit Tokenzahlen, die unter `usage.tokens` verschachtelt sind – und
Perplexity, das chat/completions ganz stillgelegt hat und darauf mit

    403 Sonar is now the Agent API. Use /v1/responses instead of /v1/sonar

antwortet, weshalb dieser Adapter die Responses-API spricht: eine
`input`-Liste statt `messages`, der System-Prompt als `instructions` und eine
Antwort, die als Ausgabeelemente ankommt – eine `message` mit ihrem Text in
Blöcken oder ein `function_call` – statt als Choice. Ein Werkzeugergebnis geht
als eigenes Element zurück, `function_call_output`, zugeordnet über
`call_id`.

Zwei Namen werden aufgelöst, bevor irgendetwas anderes sie sieht, über
`factory.dProviderAliases`: `gemini` ist das, wie die Dokumentation von Google
die API nennt, und `google` ist das, was die `info.json` jedes Agenten seit
der ersten Version sagt, also erreichen beide denselben Adapter, und nur
einer von ihnen wird je gespeichert.

Auf welchen der fünfundzwanzig ein Agent eingestellt werden darf, wird in
`fListProviders` entschieden, nicht im Browser: Ein Anbieter ist
`selectable`, wenn er selbst gehostet ist oder sein Schlüssel gespeichert
ist. Das ist ein Filter darauf, was anzubieten sich lohnt, keine Regel – ein
Schlüssel kann auch im eigenen Home-Verzeichnis des Agenten liegen, wo die
Webanwendung nicht hineinsehen kann, also zeigt die Oberfläche einem Agenten
weiterhin den Anbieter, auf den er bereits eingestellt ist.

Dasselbe Flag entscheidet eine Sache in der Oberfläche: Das Feld
**Basis-URL**, sowohl beim Hauptmodell als auch beim Ersatzmodell, wird für
einen selbst gehosteten Anbieter angezeigt und für einen Cloud-Anbieter
ausgeblendet. `base.fInit` fällt bereits auf das `cDefaultBaseUrl` des
Adapters zurück, also stellte das Feld bei einem Cloud-Anbieter eine Frage,
die beantwortet war, bevor sie gestellt wurde – und die einzige Antwort, die
es annehmen konnte und die der Standard nicht schon gibt, ist eine falsche.
Es wird ausgeblendet und nicht geleert: Eine Installation, die einen Proxy
vor einen Cloud-Anbieter setzt, hat diese Adresse gespeichert, und ein Feld
auszublenden ist kein Grund, seinen Inhalt zu verwerfen.

Eine Sache, die `base.py` vor allen verbirgt, ist der Name eines Werkzeugs.
Dieses Projekt nennt ein Werkzeug `family.action`; ein Anbieter validiert den
Namen einer Funktion gegen `^[a-zA-Z0-9_-]+$` und lehnt wegen des Punkts die
ganze Anfrage ab, ohne Hinweis darauf, welches Feld falsch war.
`fToolNameToWire` tauscht den Punkt auf dem Weg hinaus gegen `__`, und
`fToolNameFromWire` tauscht ihn auf dem Weg herein zurück, in jedem Adapter,
sodass die Registry, die Oberfläche, `info.json` und die Logs die kodierte
Form nie sehen.

### Obergrenzen, nicht Vertrauen

Jeder Lauf stoppt an der ersten von vier Obergrenzen: Token, Schritte,
Sekunden, Läufe pro Tag. Es gibt sie, weil eine unbeaufsichtigte Schleife an
einer kostenpflichtigen API eine offene Rechnung ist und bei einem selbst
gehosteten Modell eine GPU, die nie zurückkommt. `max_tokens` jeder Anfrage
schrumpft um das, was der Lauf schon verbraucht hat, sodass ein Lauf sein
Budget nicht durch einen letzten teuren Aufruf überschreiten kann.

Vier Dinge machen den Unterschied zwischen einer Obergrenze und einem
Vorschlag aus, und jedes davon war das eine der beiden, bis es behoben wurde:

  - **Kein Boden unter der Token-Anfrage.** `max(512, remaining)` verlangte
    512 Token, wenn das Budget verbraucht war, sodass einem Agenten mit einem
    verbleibenden Token immer noch eine halbe Seite erlaubt war.
  - **Jeder Aufruf bekommt die Zeit, die ÜBRIG ist**, nicht das ganze
    Lauf-Timeout. Das eigene `vTimeoutSeconds` des Adapters wird vor jedem
    Aufruf verschoben, statt den sechsundzwanzig Adaptern, die
    `fSendMessages` implementieren, einen Parameter hinzuzufügen.
  - **Die Frist wird vor jedem Werkzeug geprüft**, nicht einmal pro Schritt.
    Ein Bündel von sechs Werkzeugaufrufen, das kurz vor der Frist ankam, lief
    früher vollständig, jeder mit seinem eigenen Timeout, obendrauf auf einen
    Lauf, der schon vorbei war.
  - **Eine monotone Uhr.** `time.time()` bewegt sich, wenn NTP sie
    verstellt, und ein Lauf, der „in der Zukunft“ begann, erreicht sein
    Timeout überhaupt nie.

Was weiterhin nicht begrenzt ist, ist der Prompt. Ein Aufruf verbraucht
seine Eingabe plus seine Ausgabe, und hier wird nur die Ausgabe gedeckelt,
sodass ein langes Gespräch auf dem Weg hinein überschießt; es zu zählen,
hieße, vor jedem Aufruf den eigenen Tokenizer jedes Anbieters über das
Gespräch laufen zu lassen. Die abschließende Antwort nach einer Obergrenze
liegt ebenfalls absichtlich über dem Budget, und das steht dort, wo sie
geschrieben wird.

### Ein Lauf pro Agent zur selben Zeit

Zwei Sperren, weil es zwei Arten von Aufrufern gibt.

Der Daemon hält pro Agent ein `threading.Lock` über „läuft dieser Agent“ und
„starte den Prozess“ hinweg. Er bedient jede Anfrage in einem eigenen Thread,
also waren zwei `run_now`-Aufrufe mit `only_if_idle` zwei Threads eines
Prozesses, zwischen denen nichts stand – und ein Durchsuchen von /proc kann
keinen Prozess sehen, der noch nicht geforkt wurde. Gemessen: zwei
gleichzeitige Aufrufe, zwei Läufe.

Der Runner nimmt ein `flock` auf `<home>/run.lock` und hält es für die Dauer
des Prozesses. Dieses ist die maßgebliche Sperre, weil ein Crontab den Runner
direkt startet und nie über den Daemon kommt. Es ist keine Rechtegrenze – ein
Agent mit `bash.run` kann starten, was er will –, es existiert, damit die
ANWENDUNG denselben Agenten nicht zweimal startet und zwei Budgets für ein
Browserprofil und ein Gespräch ausgibt.

### Ein Lauf, der nie gestartet ist, sagt das

Der privilegierte Daemon startet den Runner mit stdin, stdout und stderr auf
`/dev/null`. Alles, was `fLogLine` schreibt, geht also nirgendwohin, und zwei
Fehler lebten früher vollständig in dieser Ausgabe:

- die Laufsperre war belegt, also findet dieser Lauf nicht statt;
- etwas scheiterte, bevor `fExecute` `run_started` geschrieben hatte – eine
  unlesbare `info.json` oder ein Anbieter, dessen API-Schlüssel nicht gesetzt
  ist, was bei Weitem der wahrscheinlichere der beiden Fälle ist.

Gemessen auf einer echten Installation: Bei belegter Sperre antwortete
`POST /agents/001/run` mit `202 {"started": true}`, und nichts erschien im
Journal, in `journalctl` oder in irgendeiner Datei. Derselbe Fehler unter
cron WAR sichtbar, weil cron die Ausgabe dessen behält, was es startet – und
genau deshalb hielt sich das so lange. Das Loch war immer nur im Pfad, den
die Oberfläche benutzt.

`fRecordRunRefused` schreibt es stattdessen ins Journal, als Ende mit dem
Status `refused` und ohne `run_id`. Jeder Teil dieser Form ist tragend:

| Teil | Warum |
|---|---|
| `kind: run_finished` | Der Verlauf rendert Enden. Eine eigene Art müsste die Oberfläche erst lernen, und ein Eintrag, den nichts rendert, ist dasselbe wie kein Eintrag |
| `status: refused` | `failed_runs` zählt Enden, deren Status `failed` ist. Vom Agenten ist nichts gelaufen, also ist vom Agenten nichts gescheitert |
| kein `run_started` | `runs` und `max_runs_per_day` zählen Starts. Eine belegte Sperre darf keinen der Läufe des Tages für einen Lauf verbrauchen, der nicht stattgefunden hat |
| `run_id: ""` | Nichts ist gestartet, also gibt es keinen Lauf zu identifizieren |

Nur geschrieben, wenn nichts anderes es geschrieben hat. Sobald `fExecute`
eine Lauf-ID hat, hat es `run_started` bereits geschrieben, und seine eigenen
Handler schreiben das passende `run_finished`, bevor sie erneut werfen, also
prüft `fMain` `vRun.vRunId`, bevor es ein zweites Ende für einen Lauf
hinzufügt. Dieselbe Prüfung entscheidet, wer die Gesprächsrunde im Chat
schließt: Die Handler von `fExecute` schließen sie, während sie das Ende
festhalten, und `fMain` schließt sie nur für einen Lauf, der nie so weit
kam. Gemessen, bevor es so war, auf der Debian-Testmaschine: Jeder Lauf, der
seinen Anbieter nicht erreichen konnte, beantwortete seine Frage zweimal, mit
demselben Satz.

### Der Verlauf zeigt die neuesten, und er tat es nicht

`fReadEntries` gibt ein Journal mit dem ältesten Eintrag zuerst zurück – das
sagt sein eigener Docstring –, und `fRenderRunHistory` nahm davon
`.slice(0, cShownRuns)`. Das sind die zehn ÄLTESTEN Läufe. Ein Agent mit mehr
als zehn Läufen hinter sich hatte einen Verlauf, der sich nie wieder
änderte.

Gefunden, indem die echte Anwendung mit einem echten Browser gesteuert
wurde, und nur so hätte es gefunden werden können: Jeder andere Test von
`dashboard.js` in diesem Projekt liest die Datei und sucht darin nach einem
String, und der String war da. Gemessen auf einer echten Installation, in
drei Sprachen: Ein Agent, dessen jüngster Lauf gerade mangels API-Schlüssel
abgewiesen worden war, zeigte einen Anbieterfehler von vierzig Minuten zuvor,
und die Abweisung erschien überhaupt nicht.

`.slice(-cShownRuns).reverse()`: die letzten zehn, die neuesten oben, was die
Überschrift über der Liste sagt.

Die Übersichtstabelle über dieser Liste hatte zwei eigene Fehler, beide auf
demselben Screenshot gefunden: Sie gab `last_status` roh aus, sodass auf einer
spanischen Seite „Último estado: refused“ stand, und sie gab `last_run_at`
roh aus, sodass ein nacktes `2026-09-19T03:44:29Z` direkt über einer Liste
aufbereiteter Zeitstempel stand. Beide gehen jetzt durch das, was die Zeilen
darunter schon verwendeten.

### Ein Postfach ist die eine Eingabe, in die jeder schreiben kann

Die vier `mail.*`-Werkzeuge folgen genau den Kanälen: Der Agent benennt, was
er getan haben will, und die Agenten-API – die als `boa` läuft und die
Zugangsdaten hält – tut es. Ein Agent, der das Passwort des Postfachs lesen
könnte, hätte nicht „Zugriff auf den Posteingang“; er hätte das Konto, jede
Nachricht darin, für immer, und die Möglichkeit, als dessen Besitzer zu
senden.

Was bei Mail anders ist, ist die Richtung, in die die Eingabe reist. Ein
Agent, der ein Postfach liest, ist ein Agent, dessen Anweisungen zum Teil in
den Nachrichten ankommen, die er liest, geschrieben von irgendwem auf der
Welt. Drei Entscheidungen folgen daraus:

  - **Weiterleiten ist nur an Adressen erlaubt, die der Benutzer aufgeführt
    hat**, und diese Liste wird innerhalb von `mailbox` geprüft, in dem
    Prozess, der die Verbindung öffnet – nie im Prompt. Eine Regel in einem
    Prompt ist ein Rat; eine Regel am Socket ist eine Regel. Ohne Liste wird
    das Weiterleiten rundweg abgelehnt.
  - **Lesen markiert nichts als gesehen** (`BODY.PEEK[]` auf einem
    schreibgeschützten Select), sodass ein Agent, der in ein Postfach schaut,
    dem Menschen nicht den Ungelesen-Zähler wegnimmt, auf den er sich
    verlassen hat.
  - **Löschen verschiebt in den Papierkorb**, wo das Konto einen hat. Was ein
    Agent aufgrund einer Regel entfernt, die letzten Monat geschrieben wurde,
    kann ein Mensch noch finden. „Dieses Konto hat keinen Papierkorbordner“
    und „die Ordnerliste konnte nicht gelesen werden“ werden auseinandergehalten,
    weil nur der erste der beiden Fälle in einem Expunge enden darf: Früher
    kamen sie bei `fDeleteMessage` als derselbe leere String an, sodass eine
    nicht geparste LIST-Zeile jedes `mail.delete` in ein endgültiges
    verwandelte.

### Mit einem Agenten ausgeliefert, viele angeboten

Die Installation legt genau einen Agenten an: den Orchestrator. Alles andere
kommt über „+“, das drei Ausgangspunkte anbietet: einen LEEREN Agenten, ein
aus einem Agenten exportiertes `.zip` oder eine VORLAGE aus dem
Vorlagen-Repository. Eine Installation, die mit Agenten ankommt, um die
niemand gebeten hat, ist eine, die mit Dingen beginnt, die man abschalten
muss.

Die Vorlagen wurden früher in diesem Repository ausgeliefert, je eine
Markdown-Datei in `backend/agents/examples/`. Sie leben jetzt in einem
eigenen Repository,
[bunch-of-aigents-templates](https://github.com/nipegun/bunch-of-aigents-templates),
neben diesem als `../bunch-of-aigents-templates` ausgecheckt: Eine neue
Vorlage erreicht jede Installation ohne ein Update der Anwendung, und eine
Installation kann unter Einstellungen -> Agenten auf einen Fork oder auf ein
eigenes Repository gerichtet werden (`templates_repo_url`,
`templates_repo_branch`, beim Speichern von
`agent_templates.fValidateRepositoryUrl` und `fValidateBranch` geprüft).
`agent_templates` lädt das ganze Repository als das eine `.tar.gz` herunter,
als das ein Branch ausgeliefert wird – die Adresse, von der der Installer die
Anwendung herunterlädt –, sodass das Auflisten der Vorlagen eine einzige
Anfrage ist, ohne GitHub-API und ohne Ratenlimit. Es wird pro Web-Worker fünf
Minuten lang zwischengespeichert. Eine `file://`-Adresse mit demselben Aufbau
`archive/refs/heads/<branch>.tar.gz` bedient eine Maschine ohne Weg nach
draußen.

**Ein Format für alles, was zu einem Agenten wird** (`agent_package`): ein
Ordner mit `agent.json` und `system-prompt.md` und optional `memory.md`,
`home/...` und `rag/documents.json` mit `rag/files/...`. Ein Vorlagenordner
ist ein solches Paket, das nur die ersten beiden mitbringt; ein exportiertes
`.zip` hat denselben Aufbau mit den Optionen, die der Benutzer angehakt hat.
Eine Vorlage zu installieren und ein `.zip` zu importieren ist also dieselbe
Funktion, `agent_io.fInstallPackage`, und alles, was exportiert werden kann,
kann als Vorlage veröffentlicht werden.

Alles wird geprüft, bevor ein Agent existiert (`agent_package.fReadPackage`),
weil ein Import, der auf halbem Weg scheitert, einen Agenten hinterlässt, um
den niemand gebeten hat:

- `agent.json` darf nur die Schlüssel aus `lManifestKeys` enthalten, und
  `format` 1. Ein unbekannter Schlüssel wird abgewiesen statt ignoriert: Er
  ist ein Tippfehler in einer Vorlage oder ein Paket aus einer neueren
  Version, das diese hier falsch lesen würde.
- Im Format gibt es keinen Platz für `enabled`, für Schlüssel, Token oder
  Zugangsdaten von Kanälen oder dafür, auf welchen Kanälen der Agent lauscht.
  Ein importierter Agent wird immer ausgeschaltet angelegt, und ein Anbieter
  reist nur als Name, Modell und Basis-URL – `api_key_ref` nie.
- Zeitpläne sind fünf Cron-Felder, sonst nichts (`agents.fValidateSchedule`),
  und werden in `exec_daemon.fVerbCreateAgent` NOCH EINMAL geprüft. Ein
  Zeitplan wird als root an den Anfang einer Crontab-Zeile geschrieben; einer,
  der „ /bin/sh -c ...“ oder einen Zeilenumbruch mitbrächte, wäre ein Befehl.
  Dass der Webprozess prüft, reicht nicht: Der Executor ist die Grenze.
- Werkzeuge werden nur behalten, wenn sie hier installiert sind, und die
  verworfenen werden aufgelistet (`missing_tools`), damit der Benutzer sie
  sieht, bevor er bestätigt. Fähigkeiten werden als Namen übergeben, und der
  Executor behält die installierten, wie bisher.
- `rag` geht durch `rag_settings.fValidateSettings`, wie ein Schreibvorgang
  aus dem Tab RAG, und die Bibliotheksdokumente müssen in die Datei- und
  Speicherlimits passen, die das Paket selbst mitbringt.
- Jeder Pfad im Home-Verzeichnis geht durch `agent_home.fValidatePath`:
  relativ, kein `..` und nie ein ausgeschlossener Name auf oberster Ebene
  (siehe unten).
- Ein `.zip` (`ZipSource`) wird abgewiesen bei einem Mitgliedsnamen, der nach
  außen klettert, einem Link, einem verschlüsselten Mitglied, einem Mitglied,
  das sich jenseits von 1 MiB mehr als 200:1 ausdehnt, oder bei mehr als 8 GiB
  insgesamt. Ein Repository-Archiv behält nur reguläre Dateien; ein Link darin
  wird übersprungen, nicht verfolgt.

Das Anlegen aus einer Vorlage nennt die VORLAGE und sonst nichts. Der Server
lädt sie herunter und liest sie: Eine Anfrage, die ihre eigenen Werkzeuge und
ihren eigenen Zeitplan mitbringen könnte, ließe den Browser einem Agenten eine
Berechtigung geben, die der Benutzer nie angehakt hat. Der Dialog stellt den
LEEREN Agenten an erste Stelle, dann das `.zip`, dann die Vorlagen, deren
Beschreibungen aus der `agent.json` jeder Vorlage in der Sprache der
Oberfläche kommen (`fPickDescription`: diese Sprache, sonst en-US).

**Ein Import besteht aus drei Momenten**, weil eine Bibliothek Hunderte MiB
wiegen kann und HAProxy eine Anfrage verwirft, die 300 Sekunden lang nichts
sendet: Der Browser lädt das `.zip` in Blöcken nach `/opt/boa/imports/<id>/`
hoch (`boa`, 0700, von beiden Installern angelegt und in den
`ReadWritePaths` der Web-Unit aufgeführt); `fFinishImport` prüft es als
Ganzes und gibt zurück, was es installieren würde; sobald der Benutzer
bestätigt, installiert `fStartImport` es in einem Thread des Webprozesses,
der seinen Fortschritt in `job.json` schreibt, damit der Browser ihn abfragen
kann. Jeder Worker kann die Abfrage beantworten, weil der Zustand eine Datei
ist. Ein Auftrag, dessen Thread drei Minuten lang nichts geschrieben hat,
gilt als unterbrochen: Sein Prozess wurde neu gestartet. Ein Fehler, nachdem
der Agent existiert, löscht ihn wieder (`fInstallPackage`).

**Ein Export wird gestreamt** (`fExportAgent`): Das `.zip` wird geschrieben,
während es gesendet wird, sodass ein Agent mit einer Bibliothek von Hunderten
MiB exportiert wird, ohne im Speicher gehalten zu werden. Aus dem Crontab
reisen nur die Zeilen mit, die diese Anwendung geschrieben hat, um den
Agenten auszuführen, als ihre fünf Felder (`fReadSchedules`); jede andere
Zeile ist ein Befehl, den jemand getippt hat, und ein Paket, das Befehle
mitbrächte, würde sie auf der Maschine ausführen, auf der es landet.

**Das Home-Verzeichnis wird als der Agent gelesen und geschrieben**
(`agent_home`, Executor-Verb `agent_home`): Der Executor startet das Modul
als der Benutzer des Agenten, so wie er den RAG-Worker startet, sodass root
nie einen Baum durchläuft, den der Agent umordnen kann, und ein im
Home-Verzeichnis platzierter Link nirgendwohin führt, wohin der Agent nicht
ohnehin schon käme. In beiden Richtungen ausgelassen: was das System dort
aufbewahrt (`chat.jsonl`, `runs.jsonl`, die Aufzeichnungen der API-Aufrufe,
`run.lock`, `attachments/`), was im Paket einen eigenen Platz hat
(`memory.md`, `rag/`), das Browserprofil mit seinen angemeldeten Sitzungen
und jeder versteckte Eintrag auf der obersten Ebene des Home-Verzeichnisses.
Ein importiertes `.ssh/authorized_keys` wäre ein Weg hinein, und ein
`.bashrc` führt Code aus, und keines von beiden ist die seltene legitime
Verwendung wert.

Eine der Vorlagen, `web-navigator`, hat keinen Crontab. Sie ist die für den
Browser – sie öffnet Seiten, meldet sich an, klickt und füllt Formulare aus,
wo die übrigen lesen –, und diese Arbeit ist das, worum der Benutzer gerade
gebeten hat, nicht etwas, das man um vier Uhr morgens tut. In ihrem Prompt
sind die Regeln festgeschrieben, die ein Browser mit einer Sitzung braucht:
nie Zugangsdaten eintippen, nie einen Kauf oder ein Absenden abschließen und
die Seite als Daten behandeln statt als Anweisungen.

`rag-consultant` hat ebenfalls keinen Crontab: Er beantwortet Fragen aus
seiner eigenen RAG-Bibliothek. Er ist die einzige Vorlage, deren `agent.json`
`"rag": {"enabled": true}` sagt. Der Runner hält die `rag.*`-Werkzeuge zurück,
solange die Bibliothek eines Agenten ausgeschaltet ist, ohne das würde der
Agent also ganz ohne Werkzeuge angelegt. Das `rag` des Pakets erreicht
`exec_daemon.fVerbCreateAgent` als `pRag` (der Anfragekörper wird dafür nie
gelesen), wo es durch `rag_settings.fValidateSettings` geht, dieselbe
Prüfung, durch die die Schreibvorgänge des Tabs RAG gehen: Eine Vorlage kann
die Bibliothek einschalten und ihr nichts geben, was dieser Tab nicht geben
könnte. Sein `max_tokens_per_run` ist 40000, weil der Runner das
Passagenbudget als `max_tokens_per_run` minus Prompt, Verlauf und 4096
bemisst; mit dem Standardwert 16384 bliebe kein Platz für Passagen. Sein
Prompt beschreibt die Werkzeuge, wie sie sind – `rag.read` gibt eine Passage
und ihre Nachbarn zurück, kein Dokument –, und verlangt die
`[rag:REF]`-Markierungen, die `fResolveCitations` überprüft.

### Zwei Arten, sie auszuliefern, gewählt bei der Installation

Entweder 11080 und 11443 auf localhost mit einem HAProxy davor auf 80 und
443, oder 80 und 443 direkt ausgeliefert. Der Installer fragt, merkt sich die
Antwort in `config/ports.conf`, und ein Update fragt nie wieder und ändert
auch nicht stillschweigend, auf welchen Ports die Maschine lauscht.

Der Unterschied liegt nicht nur in den Zahlen: `accept-proxy` muss im
direkten Modus vom Bind entfernt werden, weil ein Browser, der sich direkt
mit 443 verbindet, keinen PROXY-Header sendet, und ein Bind, der einen
verlangt, jeden echten Client abweist.

Im Modus `direct` wird das eigene HAProxy der Maschine nicht bloß in Ruhe
gelassen: Es wird stillgelegt. `fRetireMachineProxy` stoppt es, nimmt es auf
Alpine aus jedem Runlevel, deaktiviert **und maskiert** es auf Debian und
löscht dann `/etc/haproxy/haproxy.cfg`, wenn dieser Installer sie geschrieben
hat, oder verschiebt sie nach `haproxy.cfg.before-boa.<date>`, wenn es jemand
anderes getan hat. Es zu stoppen reicht allein nicht: Eines, das aktiviert
bleibt, nimmt sich beim nächsten Booten 80 und 443, bevor diese Anwendung
überhaupt läuft, und unter systemd können ein Paket-Upgrade, das `Wants=`
einer anderen Unit oder ein schlichtes `systemctl start` sogar ein
deaktiviertes zurückholen. Eine maskierte Unit kann von nichts gestartet
werden, und haproxy ohne `/etc/haproxy/haproxy.cfg` hat nichts, womit es
starten könnte. Was danach noch 80 oder 443 belegt, wird im Log genannt, weil
der Proxy in diesem Modus ohne sie nicht starten kann, und es eine halbe
Minute später aus „the application did not answer“ herauszulesen, ein viel
schlechterer Weg ist, es zu erfahren.

Was absichtlich NICHT getan wird, ist das haproxy-Paket zu entfernen.
`boa-proxy` IST `/usr/sbin/haproxy` – es terminiert TLS und liest den
PROXY-Header vor gunicorn, und im Modus `direct` ist es genau das, was 80 und
443 bindet –, sodass das Entfernen des Pakets die Anwendung in beiden Modi
ohne irgendetwas ließe, das lauscht. Was stillgelegt wird, ist der *Dienst*
HAProxy der Maschine, und das ist etwas anderes, das zufällig dasselbe Binary
benutzt. Die Rückkehr zu `proxied` demaskiert die Unit, bevor sie sie
aktiviert, sonst würde der Rückweg bei „The machine's HAProxy would not
start“ enden, wegen einer Maskierung, die dieser Installer selbst gesetzt
hatte.

Gemessen auf beiden Testmaschinen mit `--update --ports direct`: Die Unit
war am Ende auf Debian maskiert und auf Alpine in keinem Runlevel,
`/etc/haproxy` blieb ohne Konfiguration, und die Anwendung antwortete mit 200
auf 443 und 301 auf 80. Der Rückweg, `--update --ports proxied`, ließ sie
wieder aktiviert und aktiv, mit 200 auf 11443 und auf 443. Sieben Tests
FÜHREN die Funktion gegen gefälschte Dienstbefehle AUS, über einer
Konfiguration mit der Markierung und einer ohne, in beiden Modi, und einer
davon schlägt fehl, wenn eine künftige Version je zu `apk del haproxy` oder
`apt-get purge haproxy` greift.

### Eine Bestätigung wird dort angezeigt, wo der Benutzer hinsieht

`Settings saved` wurde früher oben in die Inhaltsspalte geschrieben. Das ist in Ordnung auf
einem kurzen Panel und nutzlos auf einem langen: Die Schaltfläche Speichern
unten im Tab Werkzeuge eines Agenten erzeugte eine Meldung mehrere
Bildschirme darüber, außerhalb dessen, was der Browser gerade zeichnete,
sodass das Speichern aussah, als täte es nichts.

Jetzt ist es ein Pop-up, zentriert über der Inhaltsspalte, auf einer
`fixed`-Ebene, die ein Geschwister dieser Spalte ist und nicht ihr Kind.
`fixed` ist der springende Punkt: Innerhalb der Spalte zu zentrieren würde
mitten im *Dokument* landen, was auf einem langen Tab derselbe Fehler ein
paar Bildschirme tiefer ist. Die Ebene hört an der Seitenleiste auf, weil eine
Meldung, die über der Agentenliste gezeichnet wird, aussähe, als gehöre sie
zur Agentenliste, und sie nimmt keine Zeigerereignisse an, sodass nichts
dahinter aufhört zu funktionieren, solange eine Meldung angezeigt wird.

Wie lange sie stehen bleibt, ist eine Einstellung dieses Browsers
(`boa.noticeSeconds`, Einstellungen → Oberfläche), neben dem Theme und der
Sprache und aus demselben Grund: Drei Sekunden sind reichlich für ein Wort
und zu wenig für einen Satz, und was von beiden eine Meldung ist, hängt davon
ab, wer sie liest. Fehler sind die Ausnahme und ignorieren die Zahl
vollständig – ein Fehler wartet darauf, geschlossen zu werden, weil er die
eine Meldung ist, die noch da sein muss, wenn der Benutzer wieder auf den
Bildschirm schaut.

Eine Meldung hat drei Farben, und die dritte gibt es wegen dessen, was die
anderen beiden nicht sagen können. Grün ist ein Speichern, das stattgefunden
hat, Rot ist ein Fehler, und Bernstein ist **`No changes to save`**:
Speichern wurde gedrückt, und das Formular enthielt genau das, was schon
gespeichert ist. Das in Grün zu melden ist schlimmer, als nichts zu sagen –
„Settings saved“ nach einem Speichern, das nichts geschrieben hat, ist genau
der Satz, der jemanden daran hindern würde zu bemerken, dass seine Änderung
nie übernommen wurde –, und Rot würde einen Fehler behaupten, wo nichts
schiefging.

Jedes Formular, das speichert, prüft es auf dieselbe Weise: die Nutzlast, die
es senden *würde*, als JSON verglichen mit dem Schnappschuss, der beim
Befüllen des Formulars vom Server oder nach dem letzten Speichern gemacht
wurde. Die Einstellungen eines Agenten bauen diese Nutzlast in einer
Funktion, `fCollectAgentPayload`, die sowohl zum Speichern als auch für den
Schnappschuss verwendet wird, weil zwei Leser desselben Formulars, die
auseinanderdriften, „keine Änderungen“ bei genau dem Feld melden würden, das
einer von ihnen nie angesehen hat. Die Panels mit den Browsereinstellungen
hatten bereits einen solchen Schnappschuss, für den Hinweis „Nicht
gespeicherte Änderungen“, und er beantwortet auch diese Frage.

Die Ausnahme ist ein **neuer** Agent: Sein Formular enthält die eigenen
Werte der Vorlage und wurde nie gespeichert, also schreibt ein Druck auf
Speichern sie und geht weiter zum Chat, statt zu sagen, dass es nichts zu
tun gibt.

### Farbe ist Zustand, Bewegung ist Aktivität

Der Ring um den Avatar eines Agenten trägt zwei verschiedene Tatsachen und
zeichnet sie auf zwei verschiedenen Kanälen, sodass keine nachgeschlagen
werden muss. Ob der Agent eingeschaltet ist, ist eine Farbe, die sich nicht
bewegt: grün oder rot. Ob er gerade arbeitet, ist Bewegung: Ein leuchtendes
Segment wandert im Uhrzeigersinn um diesen grünen Ring. Eine zweite statische
Farbe für „beschäftigt“ wäre eine Konvention, die man lernen müsste, während
etwas, das sich dreht, verstanden wird, ohne dass man es erklären muss.

Gezeichnet wird es als abgerundetes SVG-Rechteck, das genau über den Rand
gelegt ist, mit einer Strichelung, deren Versatz animiert wird, sodass die
**Form stillsteht und sich nur das Licht an ihr entlang bewegt**. Das ist der
ganze Grund für das SVG: Stattdessen einen Ring zu drehen – einen konischen
Verlauf, einen Bogen, irgendetwas unter `transform: rotate` – dreht auch die
Form, und die Ecken liegen nicht mehr deckungsgleich über dem abgerundeten
Quadrat darunter. `pathLength="100"` normalisiert den Umriss, sodass das
Stylesheet in Prozent des Umfangs spricht und nichts neu berechnet werden
muss, wenn sich der Avatar oder sein Radius ändert.

„Wer ist beschäftigt?“ zu beantworten heißt, die Befehlszeile jedes Prozesses
zu lesen, was nur root kann, also ist es ein Verb des privilegierten Daemons.
Ein Durchgang durch `/proc` beantwortet es für alle Agenten auf einmal –
nicht ein Aufruf pro Agent –, und das macht es billig genug, dass die
Seitenleiste alle fünf Sekunden fragen kann. Derselbe Durchgang steht hinter
`only_if_idle`, sodass sich der Buzzer und die Oberfläche nicht uneinig sein
können, ob ein Agent arbeitet.

### Eine Karte, die fällig wird, wird im Gespräch angekündigt

Der Chat eines Agenten ist die Aufzeichnung von allem, worum dieser Agent
gebeten wurde, nicht nur dessen, was ihm getippt wurde. Wenn der Buzzer also
einen Lauf für eine fällige Karte startet, wird diese Karte als eigene
Gesprächsrunde in die `chat.jsonl` des Agenten geschrieben, und die Antwort
des Laufs schließt sie: Wer das Gespräch öffnet, sieht die Arbeit ankommen,
was der Agent damit gemacht hat und was es gekostet hat.

Drei Entscheidungen halten das zusammen.

**Es wird geschrieben, wenn der Lauf startet, nicht wenn die Karte angelegt
wird.** Eine Karte, die für heute Abend geplant und heute Nachmittag gelöscht
wurde, ist nie gelaufen, und ein Gespräch, das sagt, sie sei übergeben
worden, wäre die Aufzeichnung von etwas, das nicht passiert ist. Der Buzzer
sieht immer nur Karten, die noch auf dem Board sind, also macht das Schreiben
im Moment des Summens die Ankündigung wahr.

**Die Datei speichert die Felder der Karte, keinen Satz.** `role: "card"`
trägt die ID, den Titel, wer sie zugewiesen hat und ob sie sofort verlangt
wurde; der Text der Nachricht sind die eigenen Anweisungen der Karte. Jedes
Wort drumherum schreibt die Oberfläche, in der eigenen Sprache des
Benutzers – dieselbe Regel, die einen gestoppten Lauf `ceiling: "tokens"`
festhalten lässt statt einer englischen Formulierung.

**„Jetzt“ und „um 13:45“ müssen unterschieden werden, und wenn der Agent
geweckt wird, liegen beide in der Vergangenheit.** Deshalb hält das Board
fest, was verlangt wurde (`run_mode`), statt es hinterher aus der Uhr
abzuleiten, und das Wort `now` reist vom Browser zu `kanban.fValidateRunAt`
als Wort und wird an der einen Stelle zu einem Zeitstempel, die auch
festhält, was es war.

Das Schreiben ist die Aufgabe des privilegierten Daemons, nicht des Buzzers:
`chat.jsonl` liegt in einem 0700-Home-Verzeichnis, das dem Agenten gehört,
und der Buzzer läuft als `boa`. Der Daemon forkt, stuft auf den Agenten
herunter, schreibt die Ankündigung und startet erst dann den Lauf – und wenn
in das Home-Verzeichnis nicht geschrieben werden kann, startet der Lauf
trotzdem. Die Ankündigung ist die Aufzeichnung der Arbeit, nicht die
Arbeit.

Der umgekehrte Fehler ist nicht harmlos und wird andersherum behandelt: Wenn
der Prozess **nach** dem Öffnen der Gesprächsrunde nicht gestartet werden
kann, schreibt der Daemon den Fehler in diese Gesprächsrunde, bevor er eine
Ausnahme wirft. Nichts anderes würde sie je schließen, und eine offene
Gesprächsrunde lässt nicht bloß eine Karte unbeantwortet – sie sperrt das
Eingabefeld für diesen Agenten endgültig.

Der Lauf, der folgt, ist weder ein schlichter geplanter Lauf noch eine
Chat-Gesprächsrunde. Er schreibt seine Antwort zurück in den Chat, weil die
Frage dort steht, aber das Gespräch wird ihm **nicht** erneut vorgespielt:
Sein Prompt ist die Karte, und zehn Wortwechsel erneut vorzuspielen, würde
jedem geplanten Lauf ein Gespräch in Rechnung stellen, das niemand führt. Im
Runner sind das zwei getrennte Flags – `vWritesToChat` und `vIsChat` –, und
diese Unterscheidung ist schon alles. Die Folge ist, dass ein Lauf, der
stoppt, bevor er das Modell irgendetwas fragt (ein ausgeschalteter Agent, die
Tagesobergrenze), trotzdem die Gesprächsrunde schließen muss, sonst wartet
die Oberfläche ewig auf eine Antwort, und das Eingabefeld bleibt gesperrt.

### Die API-Dokumentation ist eine Seite dieser Anwendung

Sie wird aus der OpenAPI-Spezifikation gerendert, die dieses Projekt baut,
statt Swagger UI von einem CDN zu laden, weil der Produktionsserver ein
Rechner im LAN ist, der womöglich überhaupt keinen Internetzugang nach außen
hat. Daraus, dass sie eine unserer eigenen Seiten ist und kein fremdes
Widget, folgen zwei Dinge.

Sie **folgt der gewählten Sprache**. Die Spezifikation bleibt Englisch – sie
ist der Vertrag einer API, deren Feldnamen, IDs und Fehlerstrings alle en-US
sind, und eine übersetzte `openapi.json` würde eine API beschreiben, die es
nicht gibt. Übersetzt wird die Seite: `fAnnotateSpecForTranslation` hängt vor
dem Rendern an jedes englische Textstück einen `data-i18n`-Schlüssel, und der
Browser tauscht es auf dieselbe Weise aus wie auf jeder anderen Seite. So
bleiben die Strings in den `.json`-Dateien des Frontends neben allen anderen,
und es funktioniert auch für einen anonymen Leser. Die Schlüssel werden aus
dem Text und dem Pfad abgeleitet, statt von Hand geschrieben, sodass ein
neuer Endpunkt seine eigenen mitbringt; ein Schlüssel ohne Übersetzung behält
das Englische, und genau das macht `fApplyTranslations` mit einem Schlüssel,
den es nicht kennt.

Sie **füllt die Spalte, die sie bekommt**, wie jede andere Seite. Früher hielt
sie eine Satzbreite von 900px und zentrierte sich, was sich für Fließtext gut
liest und hierfür schlecht: Die Seite besteht größtenteils aus
Parametertabellen und JSON-Blöcken, und die wurden in ein Drittel eines
breiten Bildschirms gequetscht, mit leeren Rändern auf beiden Seiten.

### Bildanhänge sind eine ausdrückliche Werkzeugberechtigung

`browser.screenshot` speichert eine Datei; `image.send` hängt sie an die
aktuelle Antwort an. Letzteres ist eine eigene Berechtigung, die in der
Vorlage web-navigator enthalten ist. Das Werkzeug legt einen Schnappschuss
des PNG in `agents/<id>/attachments/<opaque-id>.png` ab, mit einem
Verzeichnis 0700 und einer Datei 0600. Wird der ursprüngliche Screenshot
später überschrieben, ändert das keine frühere Antwort.
`ToolContext.lAttachments` trägt die Verweise zu
`AgentRun.fRecordChatAnswer` oder zu dessen Fehler- bzw. Laufbericht.

Nur der Executor liest diese privaten Dateien für den Webprozess. Sein Verb
`read_chat_attachment` verlangt einen Verweis im aufgezeichneten Chat dieses
Agenten, öffnet jede Verzeichniskomponente, ohne Links zu folgen, und prüft,
dass das Bild eine reguläre Datei ist, die dem Agenten gehört. Er liest PNGs
in Blöcken von 1 MiB; base64-Antworten bleiben selbst bei einem Anhang von
50 MiB unter dem bestehenden RPC-Limit. Der authentifizierte HTTP-Endpunkt
streamt die Bytes mit `private, no-store`. Das Frontend baut lokale Bild-URLs
aus IDs, nie aus URLs, die das Modell liefert.

Telegram verwendet [sendPhoto](https://core.telegram.org/bots/api#sendphoto)
für geeignete Bilder und
[sendDocument](https://core.telegram.org/bots/api#senddocument) für hohe oder
große Aufnahmen, mit dem ursprünglichen PNG. Die private Datei wird als
Multipart-Daten hochgeladen; es wird weder eine öffentliche URL noch ein
Zugriff des Agenten auf die Zugangsdaten des Bots gebraucht.
`telegram_deliveries` hält für jede ausstehende Gesprächsrunde die
bestätigten Text- und Bildteile fest. Wiederholungen setzen mit dem
fehlenden Teil fort, und das Entfernen der ausstehenden Zeile löscht diese
Kontrollpunkte. Dauerhafte Fehler werden dem Benutzer gemeldet. Beide
Eingangswarteschlangen vergleichen die UTC-Zeitstempel von SQLite mit der
Unix-Zeit; sie als Ortszeit zu interpretieren ließ jüngste Zustellungen
während der Sommerzeit verfallen.

### Kein Build-Schritt

Das Frontend besteht aus Jinja2-Vorlagen, schlichtem CSS und schlichtem
JavaScript. Das Produktionsziel ist ein selbst gehosteter Debian- oder
Alpine-Rechner; ein Deployment, das eine Node-Toolchain
braucht, um ein Stylesheet zu ändern, ist ein Deployment, das verrottet. Aus
demselben Grund rendert `/api/doc/` seine eigene OpenAPI-Spezifikation, statt
Swagger UI von einem CDN zu laden: Ein LAN-Server hat womöglich keinen
Internetzugang nach außen, und eine Dokumentation, die ohne ihn versagt,
versagt genau dann, wenn jemand Fehler sucht.

---

### Audiotranskription

Beim Starten von OpenRC-Diensten schließt der Installer die Deskriptoren 3 und 4 bei den `rc-service`-Befehlen. Das sind seine gesicherten SSH-Pipes für stdout/stderr: Es wurde beobachtet, dass `supervise-daemon` sie nach einem erfolgreichen Ende des Installers festhielt. Die gewöhnliche Ausgabe wird weiterhin in `install.log` erfasst.

`audio_transcription` speichert eine validierte JSON-Konfiguration in `settings.audio_transcription`. OpenAI, Groq, Mistral und Together verwenden Multipart; Hugging Face und Cloudflare bekommen binäres WAV. Sie verwenden `api_keys` wieder, ohne Geheimnisse an den Browser zurückzugeben. FFmpeg begrenzt Container, Protokolle, Größe, Dauer und Laufzeit. Audio wird in Segmente von 120 Sekunden geteilt (30 Sekunden für die rohen Endpunkte von Hugging Face und Cloudflare, damit man sich nicht auf Optionen für die Generierung langer Formate verlassen muss); whisper.cpp und das Dekodieren laufen als `boa`, ohne Shell und ohne automatischen Rückfall auf einen anderen Anbieter.

`audio_inbox` speichert Ziel, Einstellungen und Transkript dauerhaft in SQLite. Ein einzelner, per Prozesssperre geschützter Hintergrundthread in `boa-channel-telegram` stellt seine Warteschlange nach einem Neustart wieder her. Eine reservierte ID für die Gesprächsrunde lässt den Executor eine wiederholte Einreichung bestätigen, bevor er prüft, ob der Agent beschäftigt ist. Den Auftrag als eingereicht zu markieren und `telegram_pending` einzufügen geschieht in einer Transaktion. Private Audiodateien liegen in `/opt/boa/audio/` (0700, im Besitz von boa), verlangen für die Wiedergabe sowohl eine Anmeldung als auch einen passenden Chat-Verweis und werden entfernt, wenn abgeschlossene Chat-Gesprächsrunden gelöscht werden.

Beide Installer kompilieren whisper.cpp v1.9.4, nachdem sie die SHA-256 des Quellarchivs überprüft haben, und laden `base` herunter. `whisper_models.json` enthält alle 30 offiziellen Namen, Größen und Hashes. Nur der root-Executor lädt Modelle über `install_whisper_model` herunter; beliebige URLs und Pfade werden abgewiesen. Eine unvollständige Datei wird erst nach der Hash-Prüfung sichtbar. `whisper/` gehört root; `boa` liest es nur. Updates behalten Modelle und Audio; Backups enthalten Audio, schließen aber die Modellgewichte aus. Ein fehlender Python-Interpreter wird mit den Abhängigkeiten installiert, bevor die Mindestversion geprüft wird.

### Rohe Anbieteranfragen und der Arbeitsbereich des Agenten

`AgentRun.fSendRecordedRequest` hängt für diesen Aufruf einen Recorder an den
gewählten Anbieter, Ersatz- und Abschlussaufrufe eingeschlossen. Adapter auf
Basis von Requests verwenden `BaseProvider.fPostJson`, das denselben
serialisierten JSON-Körper aufzeichnet, bevor es ihn sendet. Die SDK-Clients
von OpenAI und Anthropic verwenden Request-Hooks und erfassen den
vorbereiteten Körper einschließlich der SDK-Felder und jeder Wiederholung.
Der Recorder speichert nie Authentifizierungsheader und baut nie eine Anfrage
aus dem Chatverlauf nach.

`api_calls` schreibt einen Index nach `agents/<id>/api-calls.jsonl` und einen
vollständigen Körper `api-call-<id>.json` pro Anfrage, Modus 0600, im
privaten Home-Verzeichnis des Agenten. Die Aufbewahrung entfernt ganze
Anfragen jenseits der neuesten 100. Der Executor liest nur reguläre Dateien,
die diesem Agenten gehören, und weist symbolische Links und FIFOs ab. Die
Körper reisen in begrenzten Blöcken über seinen Socket; die authentifizierte
HTTP-Route streamt ihren ursprünglichen JSON-Text unter `body`. Der Browser
formatiert Token, ohne Zahlen zu parsen, sodass große Ganzzahlen und
String-Escapes unversehrt bleiben.

Die geschützte `info.json` speichert `interface.show_api_calls`,
standardmäßig false. Es steuert nur die Sichtbarkeit; Anfragen werden
aufgezeichnet, ob der Tab sichtbar ist oder verborgen. `dashboard.js` trennt
die Gesprächstabs von den Einstellungstabs und wählt beim Laden eines
Agenten immer Chat aus. Es fragt die Metadaten der Anfragen nur ab, solange
API Calls geöffnet ist, und lädt die vollständigen Körper, wenn ihre Details
aufgeklappt werden. Die Überschrift der Einstellungen identifiziert den
Agenten über seine ID; Jetzt ausführen gehört zum Arbeitsbereich, und das
Löschen hat ein eigenes Panel innerhalb von Allgemein.

Das Eingabefeld ist direkt über der Statusleiste festgesteckt, und nur
`#vChatLog` scrollt. Bei Desktopbreiten macht `app.css` `.app` genau eine
Viewport-Höhe hoch, solange der Chat angezeigt wird
(`.app:has(#vChatPanel:not([hidden]))`), und reicht die Höhe über eine
Flex-Spalte an `.chat` weiter, sodass es keinen Seitenscroll gibt, in dem das
Formular verloren gehen könnte. Bei 820 px und darunter scrollt die Seite
wieder als Block, und `.chat` ist ein Viewport minus
`--status-bar-live-height`, das `api.js:fTrackStatusBarHeight` mit einem
`ResizeObserver` gleich der echten Höhe der Leiste hält – auf einem Handy
bricht die Leiste auf mehrere Zeilen um, und ein fester Schätzwert ließ das
Textfeld darunter verschwinden. Unter dem Eingabefeld gibt es keine
Hinweiszeile: `fSetComposerEnabled` schreibt sie als zweite Zeile des
Platzhalters (wie sich Enter verhält oder dass der Agent arbeitet), und
`fFitChatInputToPlaceholder` misst diesen Platzhalter an einem unsichtbaren
Zwilling und setzt die `min-height` des Feldes so, dass er nie abgeschnitten
wird. Es läuft, wann immer sich der Platzhalter oder die Breite des
Eingabefelds ändert (`fTrackChatInputWidth`). Höhen werden über das CSSOM
gesetzt, nie über ein `style`-Attribut, das die CSP verwerfen würde.

### Samba-Freigaben pro Agent

`agents.dDefaultSambaSettings` legt fest: Freigabe an, Lesen/Schreiben,
sichtbar in der Freigabeliste, authentifizierter Zugriff und Datei- bzw.
Verzeichnismodi 0600/0700. Passwörter sind anfangs nicht gesetzt.
`info.json.samba` ist geschützte Konfiguration; das Passwort existiert nur in
der root-privaten passdb von Samba. Es geht über stdin an `smbpasswd`, nie
über argv, das Modell, das zurückgegebene API-Objekt oder `info.json`.

`boa-samba` betreibt ein isoliertes smbd auf TCP 445, mit Konfiguration und
nativem Zustand im root gehörenden `/opt/boa/samba/` und Laufzeitdateien in
`/run/boa-samba/`. Es hat keinen homes-Dienst. Ein Freigabename wird aus
`fGetAgentSystemUser` abgeleitet; sein Pfad ist immer `<agent home>/samba`.
Die Authentifizierung verwendet dieses Konto, und Dateioperationen verwenden
die uid dieses Agenten. Gastzugriff verlangt eine ausdrückliche Einstellung
pro Agent. Der Installer weigert sich, eine fremde Samba-Installation zu
übernehmen, und deaktiviert die Standardinstanz der Distribution nur für die
eigene Installation von BoA.

Der Executor legt den Ordner nach dem Anlegen bzw. Indexieren eines Agenten
an und entfernt Freigabe und Konto, bevor er den Benutzer löscht. Beide
Installer gleichen bestehende Agenten nach Installation, Update und
Wiederherstellung ab. Eine exklusive Dateisperre serialisiert Änderungen;
`testparm` validiert vor dem atomaren Ersetzen der Konfiguration.
`smbcontrol` lädt die Konfiguration neu und schließt nur die Verbindungen der
geänderten Freigabe. Die Freigabe eines Agenten zu deaktivieren ist
unabhängig vom Ausführungsschalter des Agenten.

Das Einrichten des Ordners verwendet Verzeichnisdeskriptoren mit
`O_NOFOLLOW` und Besitzprüfungen. Samba weist Links innerhalb der Freigabe
ab, und ein root-preexec-Wächter prüft die Wurzel der Freigabe bei jeder
Verbindung erneut. Der Wächter führt den vertrauenswürdigen Python-Code mit
`-I` aus, sodass das Arbeitsverzeichnis eines Agenten keine importierten
Module liefern kann.

Backups enthalten die freigegebenen Dateien über das normale Archiv der
Home-Verzeichnisse der Agenten und die Einstellungen über die geschützte
info-Datei. `tdbbackup` macht im laufenden Betrieb einen Schnappschuss der
nativen Passwortdatenbank; das Backup bewahrt außerdem die Server-SID auf.
Die Wiederherstellung verlangt ein gestopptes smbd, validiert eine temporäre
Datenbank und ersetzt sie, statt aktuelle Zugangsdaten einzumischen. Der
Export über das alte smbpasswd-Format wurde bei einigen nativen Konto-RIDs
abgewiesen und wird nicht verwendet. `fVerifyInstallation` liest den
gespeicherten Portmodus des Webs, damit die Wiederherstellung den
tatsächlichen HTTPS-Port prüft, einschließlich des direkten Modus ohne
ausdrückliches Flag `--ports`.

Referenz: [Freigabeoptionen von Samba](https://www.samba.org/samba/docs/current/man-html/smb.conf.5),
[TDB-Backup-Werkzeug](https://www.samba.org/samba/docs/3.6/man-html/tdbbackup.8.html).

### Lokaler Dokumentenabruf

Die Beschriftung des Tabs ist in jeder Sprache `RAG`, auch in den Rückfällen in HTML und JavaScript.

`rag_store` verwaltet den Katalog pro Agent (SQLite WAL, FTS5, Dokumente,
Revisionen und Upload-Offsets). Ursprüngliche Namen sind Metadaten;
Dateinamen auf der Platte verwenden erzeugte Bezeichner. `rag_extract` liest
PDFs/EPUB/TXT/Markdown und ruft für OCR lokal Poppler und Tesseract auf. Es
bewahrt Seiten- und Kapitelpositionen und prüft die entpackten Größen von
EPUBs vor dem Parsen. `rag_embeddings` verwendet nur `AF_UNIX`, mit dem
festen `/run/boa-embeddings/engine.sock`: kein Hostname, kein Proxy, kein
Rückfall auf die Cloud.

Die bearbeitbaren **Dokumentinformationen** eines Dokuments sind, in der
Reihenfolge, in der das Formular sie zeigt (`rag_store.lMetadataKeys`, gegen
die auch `fAction` prüft): Erscheinungsjahr, Titel, Untertitel, Autor(en),
Version, Sprache und Schlagwörter. Die Dokumentliste zeigt den Untertitel,
wenn es einen gibt, direkt unter dem Titel. Das Jahr wird als Text
gespeichert (leer oder bis zu vier Ziffern), damit „unbekannt“ von einer Zahl
unterscheidbar bleibt. `rag_store.fMigrate` fügt die in
`rag_store.lAddedColumns` aufgeführten Spalten hinzu, also die, die
eingeführt wurden, nachdem es schon Kataloge gab (bisher `year` und
`subtitle`): `CREATE TABLE IF NOT EXISTS` ändert nie eine bestehende Tabelle,
und sowohl ältere Bibliotheken als auch wiederhergestellte Backups tragen das
alte Schema. `rag_search.fSource` setzt Untertitel, Jahr, Autor, Version und
Sprache auf jede Passage, sodass das Modell Dokumente mit demselben Titel
auseinanderhalten, ein Zitat datieren und zuordnen und zwei Ausgaben, die
sich widersprechen, abwägen kann, ohne einen zusätzlichen Aufruf von
`rag.list`. Zitatlinks und die Bibliothekssuche behalten nur den Titel und
die Position: Sie benennen eine Stelle, und der Untertitel würde den Link
nur länger machen.

`rag_models.json` ist der Katalog der Einbettungsmodelle: für jedes seine
gepinnte URL und SHA-256, Dimensionen, Kontext, Pooling, Präfixe für Anfragen
und Passagen und die zwei dafür gemessenen Ähnlichkeiten (`min_support` für
den geprüften Modus, `min_similarity` für die Untergrenze der Suche). Zwei
werden ausgeliefert: EmbeddingGemma 300M Q8 (das `default`; 768 Dimensionen,
Mean Pooling) und Qwen3-Embedding 0.6B Q8 (1024 Dimensionen,
Last-Token-Pooling, eine englische Anweisung vor jeder Anfrage und nichts vor
einer Passage). Das verwendete ist `model` in den Laufzeiteinstellungen
(`/opt/boa/rag-runtime/settings.json`, von root geschrieben und für jeden
Agenten lesbar), gelesen über `rag_settings.fSelectedModel` und
`rag_embeddings.fModel`. `rag_runtime` installiert Gewichte – der Installer
das gewählte Modell, der Executor auf Anfrage jedes andere
(`install_rag_model`, ein Download zur Zeit in einem Thread, sein Fortschritt
in `rag-runtime/status/<id>.json`) –, und eine Datei bekommt ihren Namen
erst, wenn ihre Größe und SHA-256 stimmen. Es startet llama.cpp v0.5.0 mit
dem Pooling des Modells und mit der Modell-ID als `--alias`. Netzzugriff
gehört nur zur Installation. Die Laufzeit verwendet den Tokenizer und die
Retrieval-Präfixe des Modells und weist zu große Eingaben ab. SQLite
speichert Text und Vektoren; USearch speichert inkrementelle
HNSW-Generationen. Das Veröffentlichen einer Revision schaltet atomar die
Sichtbarkeit im Katalog und den Indexnamen um.

Es gibt eine Engine, also wird das Modell für die ganze Maschine gewählt, und
der root-Executor nimmt die Änderung vor (`rag_exec.fRuntime`): Er weist
Gewichte ab, die nicht auf der Platte liegen, speichert die Wahl, setzt die
`min_similarity` jedes Agenten, der noch auf der Empfehlung des alten Modells
steht, auf die des neuen (`fFollowModelSimilarity`; ein Wert, den jemand
gewählt hat, bleibt) und startet `boa-embeddings` neu. Keinem Vektor wird
allein aufgrund der Einstellungsdatei vertraut. `rag_embeddings.fEmbed`
fragt die Engine vor dem Einbetten, welches Modell sie ausliefert
(`/v1/models`, der Alias), und wirft `EngineUnavailable`, wenn es nicht das
erwartete ist oder ein Vektor die falsche Anzahl an Dimensionen hat; ein
Indexierungsauftrag übergibt das Modell, mit dem er begonnen hat, sodass eine
Änderung auf halbem Weg den Auftrag stoppt, statt zwei Vektorräume in einer
Revision zu vermischen. Jedes Dokument hält den Fingerabdruck des Modells
hinter seiner veröffentlichten Revision fest (`documents.model`). Bei seinem
nächsten Durchgang sieht `rag_worker.fWork`, dass das Modell der Bibliothek
nicht das gewählte ist (`fFollowNewModel`): Es verwirft die Chunks
unfertiger Revisionen, reiht jedes Dokument, das mit einem anderen Modell
indexiert wurde, erneut ein und vergisst den Index. Die veröffentlichten
Revisionen bleiben. Bis es an der Reihe ist, wird ein Dokument allein über
FTS5 gefunden: `fSearch` bildet Vektorränge nur aus Dokumenten des
verwendeten Modells – über den neuen Index oder, solange es keinen gibt,
indem es ihre gespeicherten Vektoren einzeln vergleicht – und fügt eine
`notice` hinzu, die sagt, wie viele Dokumente warten. Derselbe Rückfall auf
Schlüsselwörter beantwortet eine Suche, während die Engine neu startet.
`rag_verify` pinnt ein Modell für beide Seiten seines Vergleichs und nimmt
seinen Schwellenwert von diesem Modell.

`boa-rag` läuft als boa und bittet den vorhandenen Executor, feste
Worker-Befehle zu starten. `rag_exec` gibt UID/GID ab, vor allen Dokument-
oder SQLite-Operationen; root parst nie ein Buch und öffnet nie den Katalog
eines Agenten. Worker verwenden eine Sperre des Betriebssystems,
Ressourcenlimits und dauerhafte Zustände. Upload-RPCs sind Blöcke von
256 KiB, Downloads Blöcke von 1 MiB; ganze Bücher gehen nie als eine
Nachricht über das Executor-Protokoll. Der Worker hält die vorherige Revision
durchsuchbar und setzt nach einer Unterbrechung bei den fertigen Chunks fort.
Die Einstellungen bleiben in der geschützten Agentenkonfiguration.

Ein Ausfall der Engine ist kein Dokumentfehler. `rag_embeddings` wirft
`EngineUnavailable` (ein `ValueError`), wenn der Socket versagt oder die
Engine mit 503 antwortet, während sie das Modell lädt; jede andere Ablehnung
bleibt ein schlichter `ValueError`. `fIndexDocument` fängt den Ausfall
gesondert ab: Das Dokument geht mit DERSELBEN Revision zurück auf `queued`,
behält jeden bereits eingebetteten Chunk und zeigt den Grund an, bis wieder
ein Auftrag läuft. Das alte Verhalten – `error` und die Chunks der Revision
gelöscht – kostete bei jedem `--update` Stunden an einem großen Buch, weil
der Installer `boa-embeddings` stoppt, während ein von `boa-exec` gestarteter
Worker noch läuft. `fWork` prüft die Engine (`fIsAvailable`), bevor es jedes
eingereihte Dokument beginnt, und beendet den Stapel bei einem Ausfall; sonst
würde jeder 5-Sekunden-Durchgang des Schedulers das ganze Dokument
extrahieren oder per OCR erfassen, nur um bei seinem ersten Chunk
anzuhalten.

`rag_search` kombiniert FTS5- und semantische Ränge; gefilterte Suchen werten
die gewählte Teilmenge aus. Der Runner ruft vor dem Antwortaufruf ab und
gewährt die drei schreibgeschützten RAG-Werkzeuge nur, wenn RAG eingeschaltet
ist. Quellen werden durch das eingestellte Textbudget und eine vorsichtige
Schätzung der Lauf-Token begrenzt. Zitatmarkierungen werden nur gegen
Quellen aufgelöst, die während des Laufs tatsächlich zurückgegeben wurden.
Der Antwortanbieter darf entfernt sein: Die rein lokale Verarbeitung gilt
für die Vektorisierung.

Die drei Antwortmodi unterscheiden sich darin, was der RUNNER durchsetzt,
nicht nur darin, was der Prompt sagt. `mixed` lässt das Modell
Allgemeinwissen hinzufügen. In `documental` und `verified`
(`runner.lRagModesThatSearch`) muss das Modell `rag.search` selbst aufrufen:
`fCheckRagAnswer` schickt eine abschließende Antwort, die ohne diesen Aufruf
gegeben wurde, einmal zurück (`cRagSearchFirstPrompt`). Die eigene Suche des
Runners ist die letzte Nachricht des Benutzers, Wort für Wort, und in einem
Gespräch („und in der zweiten Ausgabe?“) findet sie nichts, wo die Anfrage
des Modells, geschrieben mit dem ganzen Gespräch vor Augen, etwas findet. Aus
demselben Grund beendet eine leere Suche den dokumentbasierten Lauf nicht
mehr, bevor das Modell gefragt wird; die Garantie ist ans Ende gewandert:
`fFinishRagAnswer` ersetzt die Antwort eines Laufs, der überhaupt keine
Passage abgerufen hat, durch einen festen Satz. `tool_choice` wird nicht
benutzt, um die Suche zu erzwingen: Von den 29 Adaptern senden einige
`auto`, Cohere sendet nichts und Mistral verwendet `any`, also kann nur der
Runner sie jedem Anbieter auferlegen.

`verified` fügt `rag_verify` hinzu. Die Antwort wird in Einheiten
geschnitten – Absätze, und jeder Listeneintrag für sich, wobei ein umzäunter
Codeblock an den Absatz davor gehängt und zusammen mit ihm verglichen wird
(die Einleitung eines Beispiels allein sagt so gut wie nichts, und treue Beispiele wurden deswegen entfernt); Überschriften, kurze Beschriftungen, die auf „:“ enden, und Trennlinien sind ausgenommen. Eine
Einheit braucht ein `[rag:REF]` unter den im Lauf abgerufenen Passagen und
muss, sofern sie kein bloßer Verweis ist, nahe an einer davon liegen: die
Einheit als Anfrage eingebettet gegen die Passagen als Dokumente
eingebettet, derselbe Abstand, den die Suche verwendet, beim `min_support`
des Modells (0,36 für EmbeddingGemma, 0,44 für Qwen3-Embedding). Die erste
scheiternde Antwort geht
einmal mit den scheiternden Einheiten zurück (`fBuildCorrectionPrompt`);
danach werden sie entfernt, und eine lokalisierte Zeile sagt, wie viele. Wenn
nichts Belegtes übrig bleibt, gibt es den festen Satz; eine Engine, die nicht
erreichbar ist, hält die Antwort zurück (fail closed). Die festen Sätze
(`rag_verify.dFixedTexts`) stehen in der Sprache, in der der System-Prompt
zu antworten angewiesen wurde, erkannt an ihrer Zeile in
`dAnswerLanguageLines`, sonst auf Englisch. Die Grenze der Prüfung ist
gemessen und neben der Prüfung festgehalten. Über 138 treue Absätze und
2.652 Zitate auf Passagen eines anderen Themas trennt kein Schwellenwert die
beiden, mit keinem der beiden Modelle; die verwendeten entfernen etwa 6 % der
treuen Absätze (meist kurze Listeneinträge und einzeilige Zusammenfassungen)
und lassen weniger als 1 % dieser falschen Zitate durch. Ein Zitat auf eine
Passage zum selben Thema geht etwa in einem Viertel der Fälle durch, und ein
Absatz, der seiner Passage widerspricht, schneidet wie ein treuer ab: Was die
Prüfung fängt, ist ein Zitat auf eine Passage über etwas anderes und ein
Absatz ohne Quelle.

Das Backup legt Schnappschüsse unter root gehörenden Staging-Verzeichnissen
an, lässt das Agenten-Kind ein SQLite-Backup ziehen und seine ausgewählten
unveränderlichen Dateien hart verlinken und archiviert dann diesen
Schnappschuss. Das hält WAL- und HNSW-Generationen konsistent und vermeidet,
dass root einen Schnappschussbaum durchläuft, den der Agent austauschen
kann. Die Wiederherstellung bricht unvollständige Uploads ab und reiht
unterbrochene Indexierungen erneut ein. Index-Fingerabdrücke bleiben für
Neuaufbauten verfügbar.

## 2. Modulübersicht

| Modul | Pfad | Verantwortung | Hängt ab von | Verwendet von |
|---|---|---|---|---|
| `audio_transcription` | `backend/core/audio_transcription.py` | Spracheinstellungen und Erkennungs-Engines | db, api_keys, whisper_runtime | audio_inbox, api |
| `audio_inbox` | `backend/core/audio_inbox.py` | Dauerhafte Warteschlange, Routing, Wiederholungen und private Wiedergabe | db, exec_client, audio_transcription | telegram_listener, api |
| `whisper_runtime` | `backend/core/whisper_runtime.py` | Katalog, Status und überprüfte Modell-Downloads | paths, whisper_models.json | Installer, exec_daemon, api |
| `settings_audio.js` | `frontend/static/js/settings_audio.js` | Audioformular, Modell-Downloads und Fortschritt | api.js, i18n.js | settings.js, settings_audio.html |
| `rag_store` | `backend/core/rag_store.py` | Katalog, Uploads, Revisionen und Schnappschüsse | `rag_settings` | `rag_worker, rag_search` |
| `rag_extract` | `backend/core/rag_extract.py` | Lokale Extraktion aus PDF/EPUB/Text und OCR | `rag_embeddings, pypdf, EbookLib` | `rag_worker` |
| `rag_embeddings` | `backend/core/rag_embeddings.py` | Tokenizer und Einbettungsclient über den lokalen Socket; weist einen Vektor von jedem anderen als dem erwarteten Modell ab | `rag_settings` | `rag_extract, rag_search, rag_worker, rag_verify` |
| `rag_search` | `backend/core/rag_search.py` | Hybride Suche, HNSW-Veröffentlichung und Zitate | `rag_store, usearch, numpy` | `runner, tools` |
| `rag_worker` | `backend/core/rag_worker.py` | Dauerhafte Indexierungsaufträge im Besitz des Agenten | `rag_store, rag_extract, rag_search` | `rag_exec` |
| `rag_verify` | `backend/core/rag_verify.py` | Prüft jeden Absatz einer Antwort gegen die Passagen, die er zitiert; die festen RAG-Sätze in 15 Sprachen | `rag_embeddings` | `runner` |
| `rag_exec` | `backend/core/rag_exec.py` | Abgabe der Privilegien und feste Worker-Befehle | `paths, rag_settings` | `exec_daemon` |
| `rag_runtime` | `backend/core/rag_runtime.py` | Überprüfte Modellinstallation und Downloads, lokale Engine, Status und Vorbereitung der Wiederherstellung | `rag_settings, rag_embeddings` | `installers, boa-embeddings, rag_exec, exec_daemon` |
| `rag_models.json` | `backend/core/rag_models.json` | Die Einbettungsmodelle: Gewichte, Hashes, Pooling, Präfixe und die für jedes gemessenen Ähnlichkeiten | — | `rag_settings` |
| `rag_scheduler` | `backend/core/rag_scheduler.py` | Faires Abfragen der Warteschlange | `agents, exec_client` | `boa-rag` |
| `paths` | `backend/core/paths.py` | Jeder Dateisystempfad und die Validierung von Agenten-IDs | — | alles |
| `db` | `backend/core/db.py` | SQLite-Verbindungen und beide Schemas | `paths` | `agents`, `kanban`, `auth`, `bootstrap` |
| `agents` | `backend/core/agents.py` | Agentenmodell, `info.json` (einschließlich der Samba-Einstellungen), Agentenindex, Hashing der Token | `db`, `paths` | `exec_daemon`, `agent_api`, `api` |
| `bootstrap` | `backend/core/bootstrap.py` | Initialisierung beim ersten Start | `agents`, `db`, `paths` | Installer |
| `exec_protocol` | `backend/core/exec_protocol.py` | Übertragungsprotokoll und Verbliste | — | `exec_daemon`, `exec_client`, `agent_api` |
| `exec_daemon` | `backend/core/exec_daemon.py` | Der privilegierte Daemon (root) | `agents`, `paths`, `run_journal`, `api_calls`, `samba` | Dienst `boa-exec` |
| `exec_client` | `backend/core/exec_client.py` | Client für den obigen | `exec_protocol`, `paths` | `web/api` |
| `agent_api` | `backend/core/agent_api.py` | Der Daemon, mit dem die Agenten sprechen | `agents`, `kanban`, `channels` | Dienst `boa-agent-api` |
| `agent_api_client` | `backend/core/agent_api_client.py` | Client für den obigen | `agent_api`, `exec_protocol` | die mitgelieferten Werkzeuge |
| `runner` | `backend/core/runner.py` | Ein Lauf eines Agenten: die Schleife und ihre Obergrenzen | `providers`, `tool_registry`, `run_journal`, `api_calls` | cron, `exec_daemon` |
| `run_journal` | `backend/core/run_journal.py` | `runs.jsonl` pro Agent | `paths` | `runner`, `exec_daemon` |
| `api_calls` | `backend/core/api_calls.py` | Exakte Anfragekörper, privater Index, Aufbewahrung und begrenztes Lesen | `paths`, `run_journal` | `runner`, `exec_daemon` |
| `dashboard.js` | `frontend/static/js/dashboard.js` | Arbeitsbereich Chat/API Calls, Agenteneinstellungen und verzögertes Rendern der Anfragen | `api.js`, `jsonhighlight.js`, `markdown.js` | `dashboard.html` |
| `chat` | `backend/core/chat.py` | `chat.jsonl` pro Agent und das Gespräch, das dem Modell erneut vorgespielt wird | `paths` | `runner`, `exec_daemon` |
| `memory` | `backend/core/memory.py` | `memory.md` pro Agent, einstellbares Zeichenlimit und vollständige Schreibvorgänge; wird in den System-Prompt jedes Laufs geladen | `agents`, `paths` | `runner`, `exec_daemon`, `web/api`, Werkzeuge |
| `skills` | `backend/core/skills.py` | Die gemeinsamen Abläufe in `/opt/boa/skills/`, je ein Verzeichnis. Parst `SKILL.md`, baut den Index, der in den Prompt kommt, und sagt, welche der Fähigkeiten eines Agenten noch existieren | `paths` | `runner`, `exec_daemon`, `web/api`, `skill.read` |
| `provider_models` | `backend/core/provider_models.py` | Modellkataloge aus `config/providers/*.json` | `paths` | `web/api` |
| `api_keys` | `backend/core/api_keys.py` | Die gemeinsamen Anbieterschlüssel in `config/apikeys/*.key`, mit 0600 in einem 0700-Verzeichnis geschrieben. Gibt dem Browser nie einen Schlüssel zurück, nur ob einer gespeichert ist und seine letzten vier Zeichen | `paths` | `agent_api`, `web/api` |
| `tool_registry` | `backend/core/tool_registry.py` | Erkennung, Berechtigungen und Aufruf der Werkzeuge | `paths` | `runner`, `web/api` |
| `attachments` | `backend/core/attachments.py` | Private PNG-Schnappschüsse, undurchsichtige IDs, geprüfter Dateibesitz und begrenztes Lesen | `paths` | `image_send`, `exec_daemon`, `exec_client`, `telegram_listener` |
| `image_send` | `backend/tools/image_send.py` | Hängt über den Werkzeugkontext ein PNG im eigenen Besitz an die Antwort an | `attachments`, `tool_registry` | `runner` |
| `public_url` | `backend/core/public_url.py` | Ob eine URL, die ein Agent bekommen hat, zu einer öffentlichen Adresse auflöst. Positiv formuliert mit `is_global` plus einer ausdrücklichen Ablehnung von Multicast, weil eine Liste abzulehnender Bereiche eine Liste ist, in der man einen vergessen kann – und 100.64.0.0/10 wurde vergessen | — | `web.fetch`, `rss.fetch`, `browser` |
| `agent_scripts` | `backend/core/agent_scripts.py` | Skripte, die ein Agent für sich selbst schreibt, und die Cron-Zeilen, die sie ausführen. Validiert Namen und Zeitpläne und schreibt die Weckzeile nie um | `paths` | `script.*`, `cron.*` |
| `kanban` | `backend/core/kanban.py` | Das Board und sein Verlauf | `db` | `agent_api`, `web/api` |
| `channels` | `backend/core/channels.py` | Telegram, Discord, Mattermost, X. Senden für alle vier; Lesen für die zwei, auf denen man antworten kann | `paths`, `telegram_html`, `discord_markdown` | `agent_api`, `web/api`, beide Listener |
| `agent_routing` | `backend/core/agent_routing.py` | Was beide Listener gleich tun: die Agentenliste, den Namen eines Agenten aus einer Nachricht herauslesen, die abschließende Antwort einer Gesprächsrunde, der Statusbericht | `agents`, `chat`, `exec_client`, `system_info` | `telegram_listener`, `discord_listener` |
| `providers.base` | `backend/providers/base.py` | Adapterschnittstelle und neutrale Nachrichtenform | — | jeder Adapter |
| `providers.factory` | `backend/providers/factory.py` | Anbietername → Adapterklasse | `providers.base` | `runner`, `web/api` |
| `providers.openai_dialect` | `backend/providers/openai_dialect.py` | Die chat/completions-Anfrage, die sich die Adapter im OpenAI-Dialekt teilen; Eigenheiten bleiben in jedem Adapter | `providers.base` | die meisten Adapter |
| `providers.*` | `backend/providers/<name>.py` | Ein Adapter pro Anbieter | `providers.base`, `providers.openai_dialect` | `factory` |
| `web.server` | `backend/web/server.py` | Flask-Factory, Sitzungsschlüssel, Sicherheitsheader | `db`, `web.*` | gunicorn |
| `deploy/haproxy/boa.cfg` | `deploy/haproxy/boa.cfg` | TLS-Terminierung, PROXY-Protokoll, 11080 → 11443 | — | Dienst `boa-proxy` |
| `web.auth` | `backend/web/auth.py` | Anmeldung, Sitzungen, Ratenbegrenzung | `db` | `web.api`, `web.views` |
| `web.api` | `backend/web/api.py` | Alles unter `/api/admin/` | `exec_client`, `kanban`, `channels` | Browser |
| `web.api_doc` | `backend/web/api_doc.py` | OpenAPI-Spezifikation und ihre Seite. Versieht die Spezifikation nur für die Seite mit i18n-Schlüsseln, nie für `openapi.json` | `channels`, `providers.factory` | Browser |
| `web.views` | `backend/web/views.py` | Die HTML-Seiten | `web.auth` | Browser |
| `buzzer` | `backend/core/buzzer.py` | Beobachtet das Board und startet einen Lauf, wenn eine Karte fällig ist | `kanban`, `exec_client` | Dienst `boa-buzzer` |
| `telegram_listener` | `backend/core/telegram_listener.py` | Fragt Telegram per Long Polling ab, leitet jede Nachricht an einen Agenten weiter, schickt die Antwort zurück | `channels`, `exec_client`, `telegram_inbox` | Dienst `boa-channel-telegram` |
| `telegram_inbox` | `backend/core/telegram_inbox.py` | Welcher Agent was auf Telegram gesagt hat und welche Fragen noch beantwortet werden. Der Ablauf wird in UTC berechnet | `db` | `telegram_listener`, `agent_api` |
| `discord_listener` | `backend/core/discord_listener.py` | Pollt einen Discord-Kanal, leitet jede Nachricht an einen Agenten weiter, schickt die Antwort zurück | `agent_routing`, `channels`, `exec_client`, `discord_inbox` | Dienst `boa-channel-discord` |
| `discord_inbox` | `backend/core/discord_inbox.py` | Dieselben zwei Tabellen für Discord. Getrennt von denen für Telegram: Ein Snowflake ist ein String, und ein Listener darf die Fragen des anderen nicht beantworten können. Der Ablauf wird in UTC berechnet | `db` | `discord_listener`, `agent_api` |
| `discord_markdown` | `backend/core/discord_markdown.py` | Markdown in das, was Discord rendert, geschnitten in Nachrichten von 2000 Zeichen. Tabellen werden zu umzäunten Blöcken; ein Block, in dem ein Schnitt landet, wird geschlossen und wieder geöffnet | `telegram_html` (die Blockmuster) | `channels` |
| `discord_texts` | `backend/core/discord_texts.py` | Die drei Sätze, die Discord anders sagt. Alles andere fällt auf `telegram_texts` durch, sodass ein Katalog beiden Bots dient | `telegram_texts` | `discord_listener` |
| `browser` | `backend/core/browser.py` | Der geteilte Browser und das eigene Profil dieses Agenten. Ein Handle für die Dauer eines Laufs, von `atexit` geschlossen. Trägt die Netzwerkrichtlinie, durch die jede Anfrage geht | `paths`, `public_url` | die fünf `browser.*`-Werkzeuge |
| `telegram_html` | `backend/core/telegram_html.py` | Markdown in die vierzehn Tags, die Telegram akzeptiert. Dieselben Muster wie `markdown.js`, sodass beide Renderer sich einig sind, was Markdown ist | — | `channels` |
| `telegram_texts` | `backend/core/telegram_texts.py` | Was der Bot selbst sagt, in der Sprache, auf die die Installation eingestellt wurde | `db` | `telegram_listener` |
| `markdown.js` | `frontend/static/js/markdown.js` | Rendert die Antwort eines Agenten als DOM-Knoten, nie als Markup | — | `dashboard.js` |
| `jsonhighlight.js` | `frontend/static/js/jsonhighlight.js` | Formatiert rohes JSON, ohne Zahlen zu runden, und färbt es mit sicheren DOM-Knoten ein | — | `api_doc.html`, `dashboard.html` |
| `themes` | `backend/core/themes.py` | Listet die Stylesheets in `frontend/themes/` und liest ihre Kopfzeilen | `paths` | `web/api`, `web/views` |
| `agent_templates` | `backend/core/agent_templates.py` | Lädt das Vorlagen-Repository (Einstellungen `templates_repo_url`, `templates_repo_branch`) als ein `.tar.gz` herunter, speichert es fünf Minuten zwischen und listet oder liest seine Vorlagen | `agent_package`, `db` | `web/api` |
| `agent_package` | `backend/core/agent_package.py` | Die portable Form eines Agenten: liest ein `.zip`, ein Repository-Archiv oder einen Ordner und prüft alles, bevor ein Agent existiert | `agent_home`, `agents`, `memory`, `rag_settings`, `rag_store`, `skills` | `agent_templates`, `agent_io` |
| `agent_io` | `backend/core/agent_io.py` | Installiert ein Paket, führt `.zip`-Importe im Hintergrund mit `job.json` aus, streamt Exporte | `agent_package`, `exec_client`, `tool_registry` | `web/api`, `web/agent_io_api` |
| `agent_home` | `backend/core/agent_home.py` | Listet, liest und schreibt die Dateien im Home-Verzeichnis eines Agenten als der Agent; das Verb `agent_home` des Executors | `paths` | `exec_daemon`, `agent_package` |
| `agent_io_api` | `backend/web/agent_io_api.py` | `/agent-imports/...` und `/agents/<id>/export...` | `agent_io` | `server` |
| `agent_export.js` | `frontend/static/js/agent_export.js` | Der Tab Exportieren: was jede Option hinzufügt, und der Download-Link | `api.js` | `dashboard.html` |
| `mailbox` | `backend/core/mailbox.py` | IMAP und SMTP für das eingerichtete Postfach. Hält die Zugangsdaten, damit Agenten es nie tun. Benennt eine Nachricht über UID und UIDVALIDITY, nie über ihre Position im Ordner | `db` | `agent_api` |
| `theme.js` | `frontend/static/js/theme.js` | Fügt das Stylesheet des gewählten Themes aus dem Head ein, vor dem ersten Zeichnen | — | jede Seite |
| `night-high-contrast.css` | `frontend/themes/night-high-contrast.css` | Füllt den ausgewählten Agenten grau und zeichnet ausgewählte Tabs mit einem geschlossenen Umriss, der an die Grundlinie anschließt | `app.css` | `theme.js` |
| `settings.js` | `frontend/static/js/settings.js` | Lädt die Haupttabs der Einstellungen mit Selektoren, die auf ihre eigene Tableiste beschränkt sind; `fRenderChannelForms` markiert eingerichtete Kanäle mit `data-state="good"` und teilt sich damit den Stil des API-Schlüsselstatus und das `--colour-ok` des Themes | `api.js`, `i18n.js`, `tools.js`, `app.css` | `settings.html` |
| `tools.js` | `frontend/static/js/tools.js` | Lädt den Katalog innerhalb von Einstellungen → Werkzeuge; hält den Untertab im Parameter `family` der URL und aktualisiert seine Beschriftungen bei der Rückkehr von Oberfläche | `api.js`, `i18n.js` | `settings.js`, `settings_tools.html` |
| `app.css` | `frontend/static/css/app.css` | Die Klasse `system-table` teilt ein zweispaltiges Layout mit 35 % für Beschriftungen, damit Maschinenwerte und Dienstzustände sich ausrichten; `.chat-attachment img` füllt 100 % der Textbreite mit automatischer, unbegrenzter Höhe; `.chat-audio` passt sich der Breite der Nachricht an, und seine Überschrift erbt die Textfarbe der Nachricht | — | `settings.html`, `dashboard.html` |
| `system_info` | `backend/core/system_info.py` | Zustand der Maschine und Dienstnamen für das laufende Init-System | `paths` | `web/api`, `agent_routing` |
| `samba` | `backend/core/samba.py` | Lebenszyklus der Freigaben, Validierung, native Zugangsdaten, geschützte Ordner und Backups | `agents`, `paths`, Samba-Befehle | `exec_daemon`, Installer |
| `samba.js` | `frontend/static/js/samba.js` | Verzögert geladenes Samba-Formular, Geheimniseingabe und Schnappschuss pro Agent | `api.js`, `dashboard.js` | `dashboard.html` |

---

## 3. Index der wichtigsten Symbole

Nur öffentliche und tragende Symbole. Zeilennummern verschieben sich; die
Datei und das Verhalten sind das, worauf man sich verlassen kann.

### Pfade und Identität

| Symbol | Datei:Zeile | Was es tut |
|---|---|---|
| `fNormalizeAgentId` | `backend/core/paths.py:164` | Validiert eine Agenten-ID und füllt sie mit Nullen auf. **Jeder Pfad, der aus Benutzereingaben gebaut wird, geht hier durch.** Wirft bei allem außerhalb von 0–999 |
| `fGetAgentHome` | `backend/core/paths.py:179` | `/opt/boa/agents/xxx` |
| `fReadAgentOwnedFile` | `backend/core/paths.py:401` | Wie root eine Datei aus dem Home-Verzeichnis eines Agenten liest: am geöffneten Deskriptor, regulär und im Besitz des Agenten oder abgewiesen, nie mehr als eine Grenze. Das Journal, der Chat und das Gedächtnis gehen alle hier durch |
| `fGetAgentApiTokenPath` | `backend/core/paths.py:485` | Wo das API-Token eines Agenten liegt |

### Agenten

| Symbol | Datei:Zeile | Was es tut |
|---|---|---|
| `fValidateAgentName` | `backend/core/agents.py:71` | 2–40 Zeichen, keine Shell-Metazeichen |
| `fGetNextFreeAgentId` | `backend/core/agents.py:137` | Niedrigste freie ID laut Dateisystem, beginnend bei 001 |
| `fBuildAgentInfo` | `backend/core/agents.py:150` | Die `info.json` eines neuen Agenten, mit vorsichtigen Standardwerten |
| `fWriteAgentInfo` | `backend/core/agents.py:219` | Atomares Schreiben, das 0600 und den Besitz bewahrt |
| `fHashApiToken` | `backend/core/agents.py:256` | SHA-256; das rohe Token wird nie gespeichert |
| `fFindAgentByApiToken` | `backend/core/agents.py:301` | Macht aus einem Token eine Identität |

### Der privilegierte Daemon

| Symbol | Datei:Zeile | Was es tut |
|---|---|---|
| `fIsPeerAllowed` | `backend/core/exec_daemon.py:106` | Nur root und `boa`, pro Verbindung geprüft |
| `fRunPrivilegedCommand` | `backend/core/exec_daemon.py:122` | Führt eine Befehlsliste ohne Shell aus, optional als anderer Benutzer |
| `fVerbCreateAgent` | `backend/core/exec_daemon.py:396` | Legt Benutzer, Home-Verzeichnis, Konfiguration und Token an; übernimmt die Werkzeuge, Limits, den Schalter und die validierten `rag`-Einstellungen einer Vorlage; **rollt bei jedem Fehler zurück** |
| `fStartRunner` | `backend/core/exec_daemon.py:304` | Die einzige Stelle, an der ein Runner als der Agent gestartet wird. Die Chatnachricht oder der Prompt der Karte geht über seine Standardeingabe, nie über die Befehlszeile |
| `fWatchRunner` | `backend/core/exec_daemon.py:255` | Wartet auf einen Lauf: stoppt seinen Scope und hält das Ende eines Laufs fest, der beendet wurde |
| `fVerbWriteCrontab` | `backend/core/exec_daemon.py:780` | Installiert einen Crontab als der eigene Benutzer des Agenten |
| `fListRunningAgentIds` | `backend/core/exec_daemon.py` | Ein Durchgang durch `/proc`, der jeden Agenten mit einem laufenden Lauf nennt. Steht hinter `only_if_idle` und dem sich drehenden Ring der Seitenleiste |
| `dVerbHandlers` | `backend/core/exec_daemon.py` | Die geschlossene Verbtabelle. Die gesamte privilegierte Angriffsfläche sind diese zehn Zeilen |

### Die Agenten-API

| Symbol | Datei:Zeile | Was es tut |
|---|---|---|
| `fAuthenticate` | `backend/core/agent_api.py:121` | Token **und** `SO_PEERCRED` müssen übereinstimmen |
| `fAgentMayUseKanban` | `backend/core/agent_api.py` | Ob das Board eingeschaltet ist und der Agent irgendein Kanban-Werkzeug hat. Die grobe Hälfte |
| `fRequireKanbanTool` | `backend/core/agent_api.py` | Ein Verb, ein Werkzeug, per Name. Früher stellte jeder Handler die grobe Frage, sodass `kanban.list_cards` – ein Lesevorgang – bei einem Agenten, der die Anfrage selbst auf den Socket legte, bis zu `fDeleteCard` kam |
| `fRequireOwnCard` | `backend/core/agent_api.py:283` | Ein Agent darf nur Karten ändern, die er angelegt hat oder besitzt |
| `fVerbChannelWrite` | `backend/core/agent_api.py` | Sendet im Namen des Agenten und stellt seinen echten Namen voran |

### Die Laufschleife

| Symbol | Datei:Zeile | Was es tut |
|---|---|---|
| `AgentRun` | `backend/core/runner.py:336` | Ein begrenztes Gespräch |
| `fCheckCeilings` | `backend/core/runner.py` | Gibt zurück, welche Obergrenze den Lauf gestoppt hat, oder leer, um weiterzumachen |
| `fSecondsLeft` | `backend/core/runner.py` | Verbleibende Zeit bis zur Frist des Laufs, auf einer monotonen Uhr. Jeder Anbieteraufruf und jedes Werkzeug bekommt, was übrig ist, nicht die ganze Obergrenze |
| `fTakeRunLock` | `backend/core/runner.py` | Ein flock auf `<home>/run.lock`, für die Dauer des Prozesses gehalten. Die eine Prüfung, die auch ein von cron gestarteter Lauf macht |
| `fTrimToByteBudget` | `backend/core/exec_protocol.py` | Die neuesten Einträge, die in ein Byte-Budget passen, und wie viele verworfen wurden. In Bytes gezählt, weil eine Zeilenzahl keine Größe ist |
| `fRunWithLimits` | `backend/tools/bash_run.py` | Führt einen Befehl mit einer Byte-Obergrenze aus, die WÄHREND der Ausgabe angewendet wird, und mit einer Frist, die die ganze Prozessgruppe beendet |
| `fAskForClosingAnswer` | `backend/core/runner.py` | Fragt nach einer Obergrenze einmal ohne Werkzeuge nach der Antwort, die zu geben er abgeschnitten wurde |
| `fExecute` | `backend/core/runner.py:503` | Die Schleife: fragen, Werkzeuge ausführen, zurückspeisen, stoppen |
| `fSelectAllowedTools` | `backend/core/runner.py:319` | Hält Kanban-Werkzeuge zurück, wenn der Agent sie ausgeschaltet hat |
| `fReadStdinArguments` | `backend/core/runner.py:988` | Die Hälfte des Runners dabei: liest den Text begrenzt von der Standardeingabe und weist eine leere Chatnachricht ab |
| `fApplyResourceLimits` | `backend/core/runner.py:1069` | Senkt die eigenen Kernel-Limits des Laufs, bevor irgendetwas gestartet wird: Prozesse, Core-Dateien, Dateigröße |
| `fRecordChatAnswer` | `backend/core/runner.py` | Schreibt die Antwort zurück, wenn der Lauf eine Gesprächsrunde zu schließen hat (`vWritesToChat`) |
| `fRecordChatFailure` | `backend/core/runner.py` | Schließt die Gesprächsrunde, wenn es nichts anderes tut, und nennt den Grund, damit die Oberfläche ihn übersetzen kann |
| `fAppendCardMessage` | `backend/core/chat.py` | Kündigt eine fällige Karte als eigene Gesprächsrunde an, mit den Feldern der Karte und ohne Sätze |
| `fBuildCardAnnouncement` | `backend/core/buzzer.py` | Was dem Chat gesagt wird: wer sie zugewiesen hat und ob sie sofort verlangt wurde |

### Werkzeuge

| Symbol | Datei:Zeile | Was es tut |
|---|---|---|
| `fGetContext` | `backend/core/browser.py` | Startet den Browser mit dem Profil dieses Agenten oder gibt den schon laufenden zurück |
| `fClose` | `backend/core/browser.py` | Bei `atexit` registriert. Ohne es hinterlässt jeder Lauf ein Chromium |
| `fIsInstalled` | `backend/core/browser.py` | Ob es einen Browser zum Steuern gibt, damit die Werkzeuge sagen können, was auszuführen ist, statt eine Ausnahme zu werfen |
| `fLoadAllTools` | `backend/core/tool_registry.py:105` | Lädt jedes gültige Werkzeug; eine kaputte Datei wird übersprungen, nicht fatal |
| `fRunTool` | `backend/core/tool_registry.py:138` | Setzt die Berechtigung durch, gibt `(text, is_error)` zurück; ein Werkzeug, das eine Ausnahme wirft, beendet nie einen Lauf |
| `fGetLimit` | `backend/core/memory.py:53` | Liest das geschützte Gedächtnislimit pro Agent, mit dem alten Standardwert |
| `fValidateContent` | `backend/core/memory.py:71` | Weist zu großes Gedächtnis ab, ohne Text zu verwerfen |
| `fCheckMemoryUpdate` | `backend/web/api.py:127` | Validiert das Gedächtnis und das vorgeschlagene Limit vor jedem Schreiben der Einstellungen |
| `fSearch` | `backend/core/rag_search.py:123` | Hybrider Abruf mit Quellenverweisen |
| `fPrompt` | `backend/core/rag_search.py:243` | Die abgerufenen Passagen und die Regel des Antwortmodus, an den System-Prompt angehängt |
| `fVerify` | `backend/core/rag_verify.py:235` | Einheiten ohne abgerufenes Zitat oder ungleich dem, was sie zitieren: gibt den behaltenen Text zurück und was entfernt wurde |
| `fSplitUnits` | `backend/core/rag_verify.py:163` | Schneidet eine Antwort in Absätze und Listeneinträge und behält, was nötig ist, um sie wieder zusammenzusetzen |
| `fCheckRagAnswer` | `backend/core/runner.py:681` | Schickt eine abschließende Antwort einmal zurück: noch keine Suche (documental, verified) oder unbelegte Absätze (verified) |
| `fFinishRagAnswer` | `backend/core/runner.py:704` | Was dem Benutzer gezeigt wird: fester Satz ohne Passagen, unbelegte Absätze entfernt, zurückgehalten, wenn es nicht geprüft werden kann |
| `fIndexDocument` | `backend/core/rag_worker.py:32` | Extrahiert, bettet ein und veröffentlicht eine Revision; `False`, wenn ein Ausfall der Engine sie erneut eingereiht hat |
| `fWork` | `backend/core/rag_worker.py:129` | Begrenzter Indexierungsstapel; wartet ohne zu extrahieren, solange die Engine ausgefallen ist |
| `EngineUnavailable` | `backend/core/rag_embeddings.py:11` | Ausfall der Engine (Socketfehler oder 503), unterschieden von einer abgewiesenen Anfrage |
| `fIsAvailable` | `backend/core/rag_embeddings.py:73` | Billige Probe, die der Worker vor jedem Dokument ausführt: Die Engine antwortet, und zwar mit dem verwendeten Modell |
| `fCheckServedModel` | `backend/core/rag_embeddings.py:68` | `EngineUnavailable`, außer `/v1/models` der Engine nennt das erwartete Modell |
| `fSelectedModel` | `backend/core/rag_settings.py:39` | Der Katalogeintrag, der in Einstellungen → RAG gewählt wurde, der Standard, wenn keiner oder ein unbekannter gespeichert ist |
| `fInstallModel` | `backend/core/rag_runtime.py:76` | Lädt ein Modell in eine private Datei herunter und benennt sie erst, wenn ihre Größe und SHA-256 stimmen |
| `fStartModelDownload` | `backend/core/rag_runtime.py:125` | Reiht einen Download im Executor ein und gibt sofort seinen Status zurück |
| `fFollowModelSimilarity` | `backend/core/rag_exec.py:113` | Setzt bei einem Modellwechsel Agenten, die noch auf der alten empfohlenen `min_similarity` stehen, auf die neue |
| `fFollowNewModel` | `backend/core/rag_worker.py:107` | Reiht erneut ein, was ein anderes Modell indexiert hat, und hält veröffentlichte Revisionen über Wörter durchsuchbar |
| `fMigrate` | `backend/core/rag_store.py:83` | Fügt bei jeder Verbindung die `lAddedColumns` hinzu, die älteren Katalogen fehlen (`year`, `subtitle`) |
| `fAction` | `backend/core/rag_store.py:270` | Dokumentinformationen, neu indizieren, abbrechen und löschen; validiert die Metadatenschlüssel und das Jahr |
| `fSnapshot` | `backend/core/rag_store.py:334` | Konsistentes Backup von Dokumenten und Index |
| `ToolContext` | `backend/core/tool_registry.py:53` | Was einem Werkzeug über seinen Aufrufer gesagt wird |
| `fStoreImage` | `backend/core/attachments.py` | Kopiert ein PNG aus dem Home-Verzeichnis des Agenten in einen privaten Schnappschuss |
| `fReadImageChunk` | `backend/core/attachments.py` | Liest höchstens 1 MiB und weist Symlinks, andere Besitzer und Spezialdateien ab |
| `fVerbReadChatAttachment` | `backend/core/exec_daemon.py` | Verlangt vor dem Lesen einen Anhangsverweis im Chat des angefragten Agenten |
| `fGetChatAttachment` | `backend/web/api.py` | Streamt das PNG an einen angemeldeten Benutzer, ohne öffentliche oder zwischengespeicherte Datei-URL |
| `fRenderChatAttachments` | `frontend/static/js/dashboard.js` | Zeigt die Bilder der Antwort und einen Fehler, wenn ein Bild nicht geladen werden kann |
| `fSetComposerEnabled` | `frontend/static/js/dashboard.js` | Öffnet oder sperrt das Eingabefeld und schreibt die zweite Zeile des Platzhalters: wie sich Enter verhält oder dass der Agent arbeitet |
| `fFitChatInputToPlaceholder` | `frontend/static/js/dashboard.js` | Vergrößert das Textfeld, bis sein ganzer Platzhalter hineinpasst, gemessen an einem unsichtbaren Zwilling |
| `fTrackStatusBarHeight` | `frontend/static/js/api.js` | Hält `--status-bar-live-height` gleich der echten Höhe der Statusleiste, die das Chatlayout auf dem Handy abzieht |
| `fDeliverAnswerParts` | `backend/core/telegram_listener.py` | Setzt die Zustellung an Telegram ab dem letzten bestätigten Text- oder Bildteil fort |

### Fähigkeiten

| Symbol | Datei:Zeile | Was es tut |
|---|---|---|
| `fIsValidSkillName` | `backend/core/skills.py:57` | Ein Name, nie ein Pfad. Weist ab, statt zu bereinigen, wie bei den Namen von Vorlagen und Themes |
| `fParseSkill` | `backend/core/skills.py:77` | Der Kopf `---` und der Inhalt |
| `fSelectInstalledSkills` | `backend/core/skills.py:194` | Die Namen in der Liste eines Agenten, die noch auf der Platte existieren. **Jeder Weg in die Funktion geht hier durch**, sodass eine gelöschte Fähigkeit nie einen Prompt erreicht |
| `fBuildPromptSection` | `backend/core/skills.py:211` | Der Index: eine Zeile pro Fähigkeit, nur Namen und Beschreibungen. `""`, wenn der Agent keine hat |
| `fRunTool` | `backend/tools/skill_read.py` | Gibt einen Inhalt zurück, geprüft gegen die eigene `info.json` des Agenten |


### Telegram, in beide Richtungen

| Symbol | Datei:Zeile | Was es tut |
|---|---|---|
| `fReadTelegramUpdates` | `backend/core/channels.py` | Ein Long Poll. Die Verbindung wird nach außen aufgebaut, und das lässt es hinter einem NAT funktionieren, ohne dass etwas weitergeleitet wird |
| `fSendToTelegram` | `backend/core/channels.py` | Sendet und gibt die `message_id` zurück – das Einzige, was eine spätere Antwort routbar macht |
| `fRedactSecrets` | `backend/core/channels.py` | Entfernt alle Zugangsdaten aus einem Fehler oder einer Logzeile. `str(RequestException)` zitiert die URL, und bei drei der vier Kanäle **ist** die URL die Zugangsberechtigung |
| `fReadConfigForEditing` | `backend/core/channels.py` | Die Datei eines Kanals so, wie sie auf der Platte liegt, damit das Speichern einer Änderung zusammenführt, statt sie zu ersetzen |
| `fListConfiguredChannels` | `backend/core/channels.py` | Gibt Discord, Mattermost, Telegram und X alphabetisch zurück, mit ihrem Zustand und ohne Geheimnisse; verwendet von den Einstellungen und den Berechtigungen jedes Agenten |
| `fRouteMessage` | `backend/core/telegram_listener.py` | Für wen eine Nachricht ist: der Agent, auf den geantwortet wurde, oder der mit @ genannte |
| `fMatchNamedAgent` | `backend/core/telegram_listener.py` | Längster Treffer über alle bekannten Namen, weil Agentennamen Leerzeichen enthalten dürfen |
| `fIsFromTheConfiguredChat` | `backend/core/telegram_listener.py` | **Die gesamte Autorisierung.** Alles aus einem anderen Chat wird ohne Antwort verworfen |
| `fDeliverAnswers` | `backend/core/telegram_listener.py` | Schickt jede Gesprächsrunde zurück, die seit dem letzten Durchgang geschlossen wurde |
| `fRememberMessage` | `backend/core/telegram_inbox.py` | Verknüpft eine gesendete Nachricht mit dem Agenten, der sie gesendet hat, beschnitten auf die letzten paar Hundert |
| `fRouteMessage` | `backend/core/telegram_listener.py` | Für wen eine Nachricht ist: der Agent, auf den geantwortet wurde, der mit @ oder / genannte oder der ausgewählte |
| `fReadSelectedAgent` | `backend/core/telegram_listener.py` | Mit wem das Gespräch geführt wird, geprüft gegen die Agentenliste, damit ein gelöschter Agent nicht mehr alles abfängt |
| `fBuildAgentButtons` | `backend/core/telegram_listener.py` | Die Inline-Tastatur, mit der /agents antwortet. Den Text eines Buttons wählt der Bot selbst, den des Befehlsmenüs nicht |
| `fBuildStatusReport` | `backend/core/telegram_listener.py` | Was /status sagt. Ein Agent, den es nicht lesen kann, wird mit genau diesem Hinweis aufgeführt, nie weggelassen |
| `fHandleCallback` | `backend/core/telegram_listener.py` | Ein Tippen auf einen Agenten-Button: Zuerst wird geantwortet, dann der Agent ausgewählt |
| `fRender` | `backend/core/telegram_html.py` | Markdown in das HTML von Telegram. Überschriften werden fett, Listen werden zu Aufzählungspunkten, Tabellen werden zu einem Block in Festbreitenschrift – Telegram hat für keines der drei ein Tag |
| `fEscape` | `backend/core/telegram_html.py` | `&`, `<`, `>`. **Wird aufgerufen, bevor irgendetwas den Text umschließt**, nie danach |
| `fEscapeAttribute` | `backend/core/telegram_html.py` | Dasselbe plus das doppelte Anführungszeichen, für ein href. Ein Anführungszeichen in einer URL würde sonst das Attribut schließen und die danach erfinden |
| `fRenderWithinLimit` | `backend/core/telegram_html.py` | Kürzt das Markdown und rendert neu, bis das HTML passt. Stattdessen das HTML zu kürzen, ließe ein Tag halb geschrieben zurück |

### Discord, in beide Richtungen

| Symbol | Datei:Zeile | Was es tut |
|---|---|---|
| `fReadDiscordMessages` | `backend/core/channels.py` | Ein Poll. **Kehrt um, was Discord zurückgibt**, nämlich die neuesten zuerst: In dieser Reihenfolge zu antworten, ließe den Agenten ein Gespräch rückwärts lesen |
| `fSendToDiscord` | `backend/core/channels.py` | Sendet in so vielen Teilen, wie das Limit von 2000 Zeichen erfordert, und gibt die ID jedes Teils zurück |
| `fCallDiscord` | `backend/core/channels.py` | Ein Aufruf. Ein 429 mit kurzem `retry_after` wird einmal abgewartet; jedes andere 4xx ist `ChannelRejected` |
| `fGetDiscordMode` | `backend/core/channels.py` | `"bot"`, `"hook"` oder `""`. Ein Webhook sendet und sonst nichts |
| `fReadDiscordBotUser` | `backend/core/channels.py` | Welcher Bot das ist, einmal pro Start ins Log geschrieben: Wenn nichts ankommt, ist das die erste Frage |
| `fRenderToMessages` | `backend/core/discord_markdown.py` | Eine Antwort als die Liste der Nachrichten, die dafür zu senden sind |
| `fSplit` | `backend/core/discord_markdown.py` | Schneidet zwischen Zeilen und schließt und öffnet einen umzäunten Block, in dem ein Schnitt landet, erneut |
| `fIsFromTheConfiguredChannel` | `backend/core/discord_listener.py` | Jede gepollte Nachricht kam konstruktionsbedingt aus diesem Kanal; trotzdem geprüft, weil „konstruktionsbedingt“ eine Eigenschaft des heutigen Codes ist |
| `fReadCommand` | `backend/core/discord_listener.py` | `!agents`, `!status`, `!help` und die `/`-Formen. Nur als ganzes erstes Wort, sonst wäre ein Agent namens `status` unerreichbar |
| `fReadMessageText` | `backend/core/discord_listener.py` | Der Text mit einer vorn entfernten Erwähnung des Bots: Discord macht aus `@Boa` ein `<@123>`, bevor irgendwer sonst es sieht |
| `fStartFromTheNewestMessage` | `backend/core/discord_listener.py` | Wo eine frische Installation beginnt. Ein Bot, der heute Nachmittag eingeschaltet wurde, darf nicht auf einen Monat des Kanals antworten |
| `fReadAfterId` / `fWriteAfterId` | `backend/core/discord_listener.py` | Die Markierung, in `config/discord-after`. Ein Snowflake, kein Zähler |
| `fRememberMessage` | `backend/core/discord_inbox.py` | Verknüpft einen gesendeten Teil mit dem Agenten, der ihn gesendet hat. Beschnitten nach Einfügereihenfolge, nicht nach ID |

### Von beiden Listenern geteilt

| Symbol | Datei:Zeile | Was es tut |
|---|---|---|
| `fMatchNamedAgent` | `backend/core/agent_routing.py` | Längster Treffer über alle bekannten Namen. Präfixe sind ein Argument: Telegram nimmt `@` und `/`, Discord fügt `!` hinzu |
| `fBuildStatusReport` | `backend/core/agent_routing.py` | Was /status sagt. Nimmt den Katalog des fragenden Dienstes und seinen eigenen Unit-Namen, die einzigen zwei Dinge, die sich unterscheiden; löst den Dienstnamen des Kanals für systemd oder OpenRC auf |
| `fFindClosedAnswer` | `backend/core/agent_routing.py` | Was ein Agent gesagt hat, um eine Gesprächsrunde zu schließen, gelesen über den Executor |
| `fListAgentNames` | `backend/core/agent_routing.py` | Die Agentenliste, aus dem Index: Das Home-Verzeichnis eines Agenten ist 0700, und seine info.json zu öffnen ist nicht Sache eines Listeners |

### Die eigenen Skripte eines Agenten und Cron

| Symbol | Datei:Zeile | Was es tut |
|---|---|---|
| `fValidateScriptName` | `backend/core/agent_scripts.py` | Prüft einen Namen, statt ihn zu bereinigen: Alles, was kein schlichter Dateiname ist, wird abgewiesen, und das ist eine Regel statt einer Regel plus dem, was das Bereinigen am Ende tut |
| `fValidateSchedule` | `backend/core/agent_scripts.py` | Die Form eines Cron-Zeitplans und das eine, was abzuweisen sich lohnt: ein Auftrag, der öfter auslöst, als irgendwer wollte |
| `fIsRunnerLine` | `backend/core/agent_scripts.py` | Die Zeile, die den Agenten weckt. Wird von hier aus nie umgeschrieben: Ein Agent, der sie gelöscht hätte, würde für immer verstummen, ohne dass man es bemerken könnte |
| `fAddCronLine` | `backend/core/agent_scripts.py` | Fügt eine Zeile hinzu, die eines der eigenen Skripte des Agenten ausführt. Das Skript muss zuerst existieren |
| `fRemoveCronLines` | `backend/core/agent_scripts.py` | Entfernt jede Zeile, die ein Skript ausführt, und den Kommentar über jeder |

### Board und Kanäle

| Symbol | Datei:Zeile | Was es tut |
|---|---|---|
| `fAddCard` | `backend/core/kanban.py:132` | Karte und erstes Ereignis in einer Transaktion |
| `fMoveCard` | `backend/core/kanban.py:188` | Verschiebung plus Verlaufsereignis |
| `fValidateRunAt` | `backend/core/kanban.py:68` | Akzeptiert `"now"`, eine Browserzeit oder eine gespeicherte Zeit und normalisiert alle drei |
| `fReadRunMode` | `backend/core/kanban.py:100` | Welche Art von Zeit verlangt wurde: `now`, `at` oder keine |
| `fWasRequestedImmediately` | `backend/core/kanban.py` | Ob die Karte „jetzt“ sagte. Aus `run_mode` gelesen, nie aus der Uhr abgeleitet |
| `fAssignCard` | `backend/core/kanban.py` | Übergibt eine Karte und hält in `assigned_by` fest, wer sie übergeben hat |
| `fAgentOwnsCard` | `backend/core/kanban.py:462` | Ersteller **oder** Zugewiesener |
| `fDeleteCard` | `backend/core/kanban.py:480` | Löscht und behält eine Zeile in `deleted_cards` |
| `fReadMessages` | `backend/core/mailbox.py` | Neueste Nachrichten eines Ordners, schreibgeschützt: Nichts wird als gesehen markiert |
| `_fParseFolderLine` | `backend/core/mailbox.py` | Eine LIST-Zeile als Flags, Trennzeichen und Name. Wirft, statt zu raten: Eine unlesbare Auflistung ist ein Fehler, kein Konto ohne Ordner |
| `fListFoldersWithFlags` | `backend/core/mailbox.py` | Jeder Ordner mit seinen SPECIAL-USE-Flags |
| `fFindTrashFolder` | `backend/core/mailbox.py` | Zuerst `\\Trash`, dann die Namen in neun Sprachen. `""` heißt, es gibt keinen; ein Fehler wirft |
| `fIsForwardAllowed` | `backend/core/mailbox.py` | Ob eine Adresse auf der Liste des Benutzers steht. Geprüft dort, wo das Passwort ist, nie in einem Prompt |
| `fListTemplates` | `backend/core/agent_templates.py:134` | Jede Vorlage des Repositorys, zusammengefasst, unter dem Namen, den der Benutzer sieht; eine kaputte mit ihrem Fehler |
| `fReadTemplate` | `backend/core/agent_templates.py:151` | Quelle und geprüftes Paket einer Vorlage, oder None; weist einen Namen, der keine schlichte ID ist, vor dem Download ab |
| `fReadPackage` | `backend/core/agent_package.py:418` | Prüft ein ganzes Paket – Namen, agent.json, Prompt, Gedächtnis, Pfade im Home-Verzeichnis, Bibliothek – und beschreibt es |
| `fValidateManifest` | `backend/core/agent_package.py:317` | agent.json: nur bekannte Schlüssel, format 1, Zeitpläne, hier installierte Werkzeuge, Limits, rag, Anbieter ohne Schlüssel |
| `ZipSource` | `backend/core/agent_package.py:84` | Ein `.zip`: weist kletternde Namen, Links, Verschlüsselung, Mitglieder mit 200:1 und mehr als 8 GiB ab |
| `fReadRepositoryArchive` | `backend/core/agent_package.py:236` | Teilt ein Repository-`.tar.gz` in Vorlagenordner auf; überspringt Links |
| `fInstallPackage` | `backend/core/agent_io.py:60` | Legt den Agenten ausgeschaltet an, dann sein Gedächtnis, die Dateien im Home-Verzeichnis und die Bibliothek; löscht ihn bei einem Fehler wieder |
| `fStartImport` | `backend/core/agent_io.py:265` | Startet die Installation eines geprüften `.zip` in einem Thread, einmal, egal wie oft geklickt wird |
| `fExportAgent` | `backend/core/agent_io.py:420` | Liefert das `.zip`, während es geschrieben wird; Home-Verzeichnis und Bibliothek gestreamt |
| `fReadSchedules` | `backend/core/agent_io.py:320` | Nur die Crontab-Zeilen, die den Agenten ausführen, als fünf Felder |
| `fValidateSchedule` | `backend/core/agents.py:85` | Fünf Cron-Felder, eine Zeile, nichts, was ein Befehl sein könnte |
| `fList` | `backend/core/agent_home.py:86` | Die Dateien im Home-Verzeichnis, die ein Paket mitnehmen darf, als der Agent, ohne System- und versteckte Dateien |
| `fWrite` | `backend/core/agent_home.py:130` | Schreibt einen Block der Reihe nach, durch keinen Link, mit Modus nur für den Besitzer |
| `fBroker` | `backend/core/agent_home.py:170` | Führt eine Operation im Home-Verzeichnis als der Agent aus; das Verb `agent_home` des Executors |
| `fChooseAgentSource` | `frontend/static/js/api.js` | Der Dialog +: leerer Agent, .zip oder Vorlage |
| `fImportAgentZip` | `frontend/static/js/api.js` | In Blöcken hochladen, prüfen, anzeigen, bestätigen, installieren, abfragen |
| `fLoadExportPreview` | `frontend/static/js/agent_export.js` | Was jede Exportoption hinzufügen würde, bei jedem Öffnen des Tabs abgefragt |
| `fSource` | `backend/core/rag_search.py:88` | Eine Passage, wie das Modell und die Zitate sie sehen: Ref, Position, Titel, Untertitel, Jahr, Autor, Version, Sprache, Text, Link |

### Die Seitenleiste

| Symbol | Datei:Zeile | Was es tut |
|---|---|---|
| `fRenderSidebar` | `frontend/static/js/api.js` | Baut die Agentenliste neu auf. Aufgerufen beim Laden der Seite und nach einem Anlegen oder Löschen, nie per Timer |
| `fPickDifferentModel` | `frontend/static/js/dashboard.js` | Das Modell, das eingetragen wird, wenn ein Anbieter gewählt wird. Das Ersatzmodell meidet das des Hauptmodells: Derselbe Anbieter und dasselbe Modell scheitern aus demselben Grund, jedes Mal |
| `fSetAgentAvatarActivity` | `frontend/static/js/api.js` | Setzt `data-running` und den Tooltip auf einem Avatar und fügt den Bogen hinzu oder entfernt ihn |
| `fBuildAgentActivityArc` | `frontend/static/js/api.js` | Das abgerundete SVG-Rechteck über dem Rand, `pathLength="100"`, damit das Stylesheet in Prozent des Umfangs sprechen kann |
| `fRefreshAgentActivity` | `frontend/static/js/api.js` | Zeichnet alle 5 s nur die Ringe neu; wird übersprungen, solange der Tab verborgen ist |
| `fDescribeChannelName` / `fDescribeProviderName` | `frontend/static/js/api.js` | Der Name, mit dem sich ein Kanal oder ein Anbieter selbst schreibt. Keine i18n-Schlüssel: DeepSeek ist in jeder Sprache DeepSeek |
| `fDescribeTool` / `fDescribeToolArgument` | `frontend/static/js/api.js` | Was ein Werkzeug und seine Argumente sagen, in der Sprache des Lesers. Das Schema bleibt Englisch: Es ist das, was dem Modell geschickt wird |
| `fRenderToolCheckboxes` | `frontend/static/js/dashboard.js` | Ein Kästchen pro Werkzeugfamilie, gebaut aus dem, was installiert ist. Verschiebt den Kanban-Schalter in das Kanban-Kästchen, statt ihn neu zu bauen, sodass ein gesetzter, noch nicht gespeicherter Haken das Neuzeichnen übersteht |

### Pop-up-Meldungen

| Symbol | Datei:Zeile | Was es tut |
|---|---|---|
| `fShowNotice` | `frontend/static/js/api.js` | Setzt eine Meldung auf die Ebene über der Inhaltsspalte. Ersetzt, was dort war, sodass sich Bestätigungen nie stapeln |
| `fShowError` | `frontend/static/js/api.js` | Dasselbe, als Fehler: kein Timer, wird von Hand geschlossen |
| `fConfirmLogout` | `frontend/static/js/api.js` | Öffnet `fConfirm` in der Mitte des Bildschirms; navigiert erst nach der Bestätigung zu `/logout`. Abbrechen und Escape halten die Sitzung offen |
| `fHideNotice` | `frontend/static/js/api.js` | Blendet eine Meldung aus und entfernt sie danach, damit sie nicht schlagartig verschwindet, wenn der Timer abläuft |
| `fGetNoticeSeconds` / `fSetNoticeSeconds` | `frontend/static/js/api.js` | Wie lange eine Meldung stehen bleibt, in diesem Browser gespeichert und auf 1–30 Sekunden begrenzt |
| `fBuildCloseCross` | `frontend/static/js/api.js` | Das Schließen-Kreuz als zwei SVG-Linien. Ein Zeichen `×` wird auf der mathematischen Achse der Schrift zentriert statt in seinem eigenen Kasten, also sitzt es über der Mitte des Buttons, was auch immer der Button tut |

### JSON-Hervorhebung

| Symbol | Datei:Zeile | Was es tut |
|---|---|---|
| `cJsonTokenPattern` | `frontend/static/js/jsonhighlight.js` | Ein Ausdruck für alle vier Tokenarten. Ein String, auf den ein Doppelpunkt folgt, ist ein Schlüssel, und nur daran lässt sich ein Name von einem Wert unterscheiden |
| `fHighlightJsonElement` | `frontend/static/js/jsonhighlight.js` | Baut einen Block als farbige Spans und schlichten Text neu auf. Jedes Zeichen des Originals wird genau einmal ausgegeben, sodass sich der Block weiterhin als gültiges JSON kopieren lässt |

### Anbieter

| Symbol | Datei:Zeile | Was es tut |
|---|---|---|
| `BaseProvider.fSendMessages` | `backend/providers/base.py` | Die eine Methode, die jeder Adapter implementiert |
| `fNeutralMessagesToOpenAiFormat` | `backend/providers/base.py` | Neutrale Form → chat/completions |
| `fToolNameToWire` / `fToolNameFromWire` | `backend/providers/base.py` | `family.action` ↔ `family__action`, weil kein Anbieter den Punkt akzeptiert |
| `fDescribeHttpError` | `backend/providers/base.py` | Hängt an einen nackten HTTP-Fehler an, was der Anbieter gesagt hat |
| `fBuildProvider` | `backend/providers/factory.py` | Konfiguration → Adapterinstanz, mit verzögertem Import |
| `fResolveProviderName` | `backend/providers/factory.py` | Folgt den Aliasen, sodass `gemini` und `google` einen Adapter erreichen |
| `fSendChatCompletion` | `backend/providers/openai_dialect.py` | Die geteilte chat/completions-Anfrage, parametrisiert durch die Eigenheiten jedes Adapters |
| `fNormalizeMessageContent` | `backend/providers/openai_dialect.py` | Glättet eine Antwort, deren Inhalt als Blöcke ankam, und verwirft dabei das Reasoning |

---

### Audiosymbole

| Symbol | Datei:Zeile | Verantwortung |
|---|---|---|
| `fTranscribe` | `backend/core/audio_transcription.py:223` | Dekodieren, segmentieren und transkribieren |
| `fEnqueueTelegram` | `backend/core/audio_inbox.py:57` | Das Ziel vor der Transkription dauerhaft speichern |
| `fRunOneJob` | `backend/core/audio_inbox.py:233` | Eine reservierte Gesprächsrunde verarbeiten oder wiederholen |
| `fDownloadModel` | `backend/core/whisper_runtime.py:134` | Größe und SHA-256 vor der Veröffentlichung validieren |
| `fGetChatAudio` | `backend/web/api.py:571` | Audio nach Prüfung von Sitzung und Chat-Verweis ausliefern |

### API Calls

| Symbol | Datei | Verantwortung |
|---|---|---|
| `fRecordCall` | `backend/core/api_calls.py` | Speichert einen vollständigen ausgehenden Körper vor dem Versand dauerhaft |
| `fReadBodyChunk` | `backend/core/api_calls.py` | Liest einen begrenzten Teil einer validierten Agentendatei |
| `fSelectConversationTab` | `frontend/static/js/dashboard.js` | Schaltet zwischen Chat/API Calls und ihrem Polling um |
| `fBeautifyJson` | `frontend/static/js/jsonhighlight.js` | Rückt JSON ein und bewahrt dabei die Literalwerte |

### Samba

| Symbol | Datei | Verantwortung |
|---|---|---|
| `fProvisionAgent` / `fRemoveAgent` | `backend/core/samba.py` | Lebenszyklus von Freigabe und Konto |
| `fSaveSettings` | `backend/core/samba.py` | Validieren, Zugangsdaten speichern und Berechtigungen aktivieren |
| `fCheckShareDirectory` | `backend/core/samba.py` | Prüfung von Ordner und Besitz beim Verbindungsaufbau |
| `fBackup` / `fRestore` | `backend/core/samba.py` | Konsistentes Backup und Ersetzen der nativen Zugangsdaten |
| `fLoadSambaSettings` / `fCollectSambaSettings` | `frontend/static/js/samba.js` | Laden und speichern, ohne Passwörter preiszugeben oder andere Änderungen zu verwerfen |

## 4. Hauptabläufe

### Dokumentenabruf

Die Installer räumen die alten RAG-Bäume der wiederhergestellten Agenten,
bevor sie den Schnappschuss entpacken, damit veraltete SQLite-WAL-Dateien und
Vektorgenerationen eine Wiederherstellung nicht überleben können. Die
Laufzeiteinstellungen werden wiederhergestellt, ohne installierte
Modellgewichte zu ersetzen. Worker arbeiten pro Runde höchstens acht
Dokumente ab oder beginnen höchstens 90 Sekunden lang neue Dokumente;
unfertige Aufträge bleiben dauerhaft erhalten. Die Antwort der Bibliothek
zeigt Fehler beim Import aus der Inbox an. Die lokale OCR installiert
Liberation-Schriften für PDFs ohne eingebettete Schriften. Der Build der
Einbettungen schaltet den Download vorgefertigter Web-UIs ab.

Upload: `rag_api → exec_client.fRag → rag_exec → rag_worker` als der Agent.
Indexierung: `boa-rag → exec_daemon → rag_worker.fWork → rag_embeddings.fIsAvailable → extraction → local embeddings → publication`.
Ausfall der Engine beim Indexieren: `rag_embeddings.fRequest → EngineUnavailable → fIndexDocument → state queued, chunks kept → fWork ends the batch → next pass resumes at the first missing chunk`.
Modell-Download: `settings_rag.js → POST /api/admin/rag/models/<id>/install → exec_client.fInstallRagModel → exec_daemon.fVerbInstallRagModel → rag_runtime.fStartModelDownload → thread fInstallModel → status file ← GET /api/admin/rag (fDescribe) polled every 2 s`.
Modellwechsel: `settings_rag.js (fConfirmModelChange) → PUT /api/admin/rag → rag_exec.fRuntime → fIsModelInstalled → fSaveRuntimeSettings → fFollowModelSimilarity → restart boa-embeddings → [each library] rag_worker.fWork → fFollowNewModel → fIsAvailable waits for the new alias → fIndexDocument(pModel) → fBuildIndex/fPublish (documents.model)`; währenddessen `fSearch → FTS5 only for the waiting documents → notice`.
Antwort: `AgentRun.fExecute → rag_search.fSearch → bounded passages → configured provider → verified citation links`.
Dokumentbasierte und geprüfte Antwort: `model answers → fCheckRagAnswer (no rag.search yet → cRagSearchFirstPrompt, once) → rag.search → model answers → [verified] rag_verify.fVerify → unbacked units → fBuildCorrectionPrompt, once → model answers → fFinishRagAnswer (no passages → fixed sentence; verified → units removed + count, engine down → withheld) → fResolveCitations`.

### Das Gedächtnis und sein Limit speichern

`dashboard.js:fSaveAgent` zählt Unicode-Codepunkte und übermittelt `memory`
zusammen mit `info.limits.max_memory_characters`. `api.fCheckMemoryUpdate`
validiert vor jedem Schreiben gegen das vorgeschlagene Limit (oder liest das
gespeicherte), sodass das Erhöhen des Limits und das Speichern eines längeren
Textes in einer Anfrage funktionieren. Bei einer Ablehnung gibt es die
übersetzten Fehler `memoryTooLong` oder `memoryLimitInvalid` zurück. Danach
speichert `fVerbWriteAgentInfo` das Limit, und `fVerbWriteMemory` validiert,
bevor die Privilegien abgegeben werden. `memory.fWrite` prüft die geschützte
Einstellung erneut und ersetzt die Datei atomar, ohne sie abzuschneiden.
`memory.append` und `memory.replace` verwenden dieselbe Prüfung; die Warnung
beginnt oberhalb von 75 % des Limits. Das Formular lässt zu großen,
eingefügten Text zum Bearbeiten stehen.

Die Transportbudgets tragen die Obergrenze: 6 MiB pro Executor-Anfrage, vom
Client vor dem Verbinden geprüft; 8 MiB pro Antwort; 4 MiB pro gelesener
Gedächtnisdatei; 16 MiB pro HTTP-Körper, einschließlich JSON-Clients, die
ergänzende Unicode-Zeichen escapen. Das sind Transportlimits, keine Limits
des Modellkontexts.

### Einen Agenten anlegen

```
Browser  POST /api/admin/agents {name}
  web/api.fCreateAgent
    exec_client.fCreateAgent          → Unix socket /run/boa/exec.sock
      exec_daemon.ExecRequestHandler
        fGetPeerCredentials + fIsPeerAllowed    ← weist alle außer root/boa ab
        fVerbCreateAgent
          agents.fValidateAgentName
          agents.fGetNextFreeAgentId            ← niedrigste freie, laut Dateisystem
          useradd --home-dir … --create-home
          agents.fWriteAgentInfo                 (0600, im Besitz des Agenten)
          fWriteAgentFile system-prompt.md        (0600)
          fWriteAgentFile api-token              (0600)
          chmod 0700 auf das Home-Verzeichnis
          agents.fIndexAgent(…, vApiToken)       ← speichert nur den SHA-256
        bei jeder Ausnahme: fRemoveAgentUser     ← keine halb angelegten Agenten
```

### Einen Agenten aus einer Vorlage anlegen

```
Browser  GET /api/admin/agent-templates?language=es-ES
  agent_templates.fListTemplates
    fLoadTemplates → fDownloadArchive(<repo>/archive/refs/heads/<branch>.tar.gz)   5 min zwischengespeichert
      agent_package.fReadRepositoryArchive                   eine Quelle pro Ordner mit agent.json
    agent_package.fReadPackage + fSummarise                  pro Vorlage; ein Fehler wird mit seiner Meldung aufgeführt
Browser  POST /api/admin/agents {name, template, language}
  api.fCreateAgent
    agent_templates.fReadTemplate(template)                  der Server liest sie erneut
    agent_io.fInstallPackage
      exec_client.fCreateAgent(tools, skills, limits, pRag, pSchedules, pEnabled=False)
        exec_daemon.fVerbCreateAgent → agents.fValidateSchedule, noch einmal
      exec_client.fWriteAgentInfo / fWriteMemory / fAgentHome / fRag   wenn das Paket sie mitbringt
      bei einem Fehler: exec_client.fDeleteAgent
```

### Ein .zip importieren

```
Browser  POST /api/admin/agent-imports {name, size}          → /opt/boa/imports/<id>/package.zip
Browser  PUT  /api/admin/agent-imports/<id>/upload {offset, data}   der Reihe nach, je 256 KiB
Browser  POST /api/admin/agent-imports/<id>/finish            ZipSource + fReadPackage → Zusammenfassung
Browser  (zeigt die Zusammenfassung; der Benutzer bestätigt und benennt ihn)
Browser  POST /api/admin/agent-imports/<id>/install           → 202
  agent_io.fStartImport → install.lock (einmal) → Thread fRunImport
    fInstallPackage, meldet step/done/total in job.json
Browser  GET  /api/admin/agent-imports/<id>                   jede Sekunde, bis installed/failed
```

### Einen Agenten exportieren

```
Browser  GET /api/admin/agents/<id>/export/preview            Gedächtnisgröße, Dateien im Home, Bibliothek, Modell
Browser  GET /api/admin/agents/<id>/export?memory=1&home=1&provider=1&rag=1   ein Download-Link
  agent_io_api.fExport → erster Block vor den Headern erzeugt (Fehler bleiben JSON)
    agent_io.fExportAgent
      fBuildManifest ← fReadAgentInfo, fReadCrontab → fReadSchedules
      memory.md ← fReadMemory
      home/... ← exec_client.fAgentHome(list, read) als der Agent
      rag/files/... + rag/documents.json ← exec_client.fRag(list, content)
```

### Ein geplanter Lauf

```
cron (der eigene Crontab von agent-007)
  runner.py --agent-id 007            ← läuft bereits als agent-007
    fTakeRunLock                      ← abgewiesen → fRecordRunRefused, und Stopp
    AgentRun.__init__
      fReadOwnInfo / fReadOwnSystemPrompt / fReadOwnApiToken
      fBuildSystemPrompt              ← Prompt + Gedächtnis + Fähigkeitenindex + Sprache
      tool_registry.fLoadAllTools
      fSelectAllowedTools             ← Kanban-Werkzeuge zurückgehalten, wenn ausgeschaltet
    fExecute
      run_journal.fCountRunsOn        ← Tagesobergrenze, aus dem eigenen Journal
      factory.fBuildProvider
      Schleife:
        fCheckCeilings                ← Schritte, Token, Sekunden
        provider.fSendMessages        ← max_tokens schrumpft, während das Budget verbraucht wird
        run_journal.fRecordUsage
        ohne Werkzeugaufrufe: Stopp
        fRunToolCalls                 ← alle Ergebnisse in einem Bündel zurückgegeben
      fAskForClosingAnswer            ← ein Aufruf ohne Werkzeuge nach einer
                                        Obergrenze für Schritte oder Token, damit
                                        die schon bezahlte Arbeit zu einer Antwort wird
      run_journal.fRecordRunFinished  ← „stopped“, wenn eine Obergrenze ihn beendet hat
```

### Eine Karte wird fällig

```
boa-buzzer (als boa), alle 5 Sekunden
  kanban.fListDueCards              ← Besitzer, run_at verstrichen, nicht gesummt, nicht erledigt
  fRingOne
    fBuildCardAnnouncement          ← assigned_by → Name, run_mode → sofort
    exec_client.fRunNow(prompt, only_if_idle, card)
      exec_daemon.fVerbRunNow                      ← als root
        fIsAgentRunning             ← beschäftigt: started=False, kein Summen, erneut versuchen
        fRunAsAgent → chat.fAppendCardMessage      ← angekündigt, Gesprächsrunde geöffnet
        Popen runner.py --prompt-on-stdin --turn-id …  ← als agent-007, der Prompt auf seiner stdin
    kanban.fMarkCardBuzzed          ← erst nachdem der Lauf gestartet ist
  runner.AgentRun (vWritesToChat, nicht vIsChat)
    fExecute                        ← Prompt der Karte, kein Gespräch erneut vorgespielt
    fRecordChatAnswer               ← Antwort + Kosten schließen die Gesprächsrunde
    fRecordChatFailure              ← oder der Grund, warum nichts lief
```

### Ein Agent verschiebt eine Karte

```
Modell verlangt kanban.move_card
  tool_registry.fRunTool              ← weist ab, wenn diesem Agenten nicht gewährt
    tools/kanban_move_card.fRunTool
      agent_api_client.fCallFromContext   → /run/boa/agent.sock
        agent_api.AgentRequestHandler
          fAuthenticate               ← Token-Hash + SO_PEERCRED
          fVerbKanbanMoveCard
            fAgentMayUseKanban        ← serverseitig, liest info.json
            fRequireOwnCard           ← nur Ersteller oder Zugewiesener
            kanban.fMoveCard          ← Verschiebung + Ereignis, eine Transaktion
```

### Ein Agent sendet eine Nachricht

```
Modell verlangt channel.write
  tools/channel_write.fRunTool
    agent_api_client → agent_api.fVerbChannelWrite
      fAgentMayUseChannel             ← Werkzeug gewährt UND Kanal gewährt
      channels.fSendMessage(prefix="[Agent name]")
        fReadChannelConfig            ← als boa; der Agent sieht das nie
        fSendToTelegram / Discord / Mattermost / X
```


### Eine Nachricht kommt von Telegram

```
boa-channel-telegram (als boa)
  fRefreshCommands                    ← /agents /status /help, wenn sie sich ändern
  fDeliverAnswers                     ← alles, was seit dem letzten Durchgang fertig ist
    exec_client.fReadChat             ← der Chat liegt in einem 0700-Home; nur root liest ihn
    channels.fSendToTelegram          ← "**name:**\n..." als Antwort
    telegram_inbox.fRemovePending
  channels.fReadTelegramUpdates       ← Long Poll: 25s im Leerlauf, 3s beim Antworten
    fIsFromTheConfiguredChat          ← alles andere wird stillschweigend verworfen
    callback_query -> fHandleCallback ← ein Tippen auf einen Agenten-Button
      fSelectAgent                    ← ab hier gehen nicht adressierte Nachrichten dorthin
    message -> fHandleMessage
      fHandleCommand                  ← /agents /status /help, beantwortet und erledigt
      fRouteMessage                   ← Antwort, dann @name, dann der ausgewählte
      exec_client.fSendChatMessage(source="telegram")
        exec_daemon.fVerbSendChatMessage
          chat.fAppendMessage(metadata={"source": "telegram"})
          Popen runner.py --chat-message-on-stdin --turn-id   ← die Nachricht auf seiner stdin
      telegram_inbox.fAddPending      ← auf der Platte: ein Neustart darf die Antwort nicht verlieren
```

Die Antwort sendet der Listener und nicht der Lauf, aus demselben Grund, aus
dem die Ankündigung einer Karte vom Executor geschrieben wird: Der Lauf ist
der eigene Benutzer des Agenten, und die Zugangsdaten der Kanäle gehören
`boa`. Der Lauf schreibt nur in seinen Chat; der Listener liest das und
übernimmt das Senden.

### Eine Nachricht kommt von Discord

```
boa-channel-discord (als boa)
  fDeliverAnswers                     ← alles, was seit dem letzten Durchgang fertig ist
    exec_client.fReadChat             ← der Chat liegt in einem 0700-Home; nur root liest ihn
    channels.fSendToDiscord           ← "**name:**\n…" als Antwort, in Teilen von 2000 Zeichen
      discord_markdown.fRenderToMessages
    discord_inbox.fRememberMessage    ← jeden Teil, damit eine Antwort auf irgendeinen davon geroutet wird
    discord_inbox.fRemovePending
  channels.fReadDiscordMessages       ← GET /channels/<id>/messages?after=<id>
    (umgekehrt: Discord antwortet mit den neuesten zuerst)
    fHandleMessage
      author.bot, type                ← seine eigenen Worte und alles, was keine Nachricht ist
      fIsFromTheConfiguredChannel
      fReadCommand                    ← !agents !status !help, beantwortet und erledigt
      fRouteMessage                   ← Antwort, dann @name, dann der ausgewählte
      exec_client.fSendChatMessage(source="discord")
      discord_inbox.fAddPending       ← auf der Platte: ein Neustart darf die Antwort nicht verlieren
  fWriteAfterId                       ← config/discord-after
```

Die Antwort sendet der Listener und nicht der Lauf, aus demselben Grund wie
bei Telegram: Der Lauf ist der eigene Benutzer des Agenten, und die
Zugangsdaten der Kanäle gehören `boa`.

Der erste Durchgang einer frischen Installation fragt nach der neuesten
Nachricht und behält nur ihre ID. Ein leerer Kanal wird mit der niedrigsten
ID markiert, die es gibt, sodass die **erste** Nachricht, die jemand
schreibt, beantwortet wird, statt damit verbraucht zu werden, herauszufinden,
wo man anfangen soll.

### Der Bot zeigt einem Fremden nichts

Der Benutzername eines Bots ist öffentlich: Jeder, der ihn findet, kann einen
Chat mit ihm öffnen. Deshalb vergleicht `fIsFromTheConfiguredChat` die
`chat.id`, die Telegram an jede Nachricht hängt – und die der Absender nicht
fälschen kann –, mit der eingerichteten, und `fHandleMessage` verwirft, was
nicht passt, bevor ein Befehl verteilt und bevor ein Agent gewählt wird.
`fHandleCallback` tut dasselbe für einen Buttondruck. Es wird nichts
zurückgeschickt: Eine Antwort würde dem, der ihn abtastet, bestätigen, dass
der Bot lebt. Es wird auch nichts aufgeschrieben. Früher wurde das Verwerfen
mit der ID des Chats protokolliert, aus dem die Nachricht kam, und das sind
Daten von jemand anderem; es hätte bedeutet, dass diese Installation still
eine Liste derer anlegt, die den Bot gefunden haben. Was bleibt, ist eine
Nachricht, die nie existiert hat.

Der Preis ist real und muss benannt werden: Eine falsch eingerichtete
`chat_id` sieht jetzt genau wie ein Fremder aus, und die eigenen Nachrichten
des Besitzers verschwinden stillschweigend. Die eingerichtete ID wird bei
jedem Start ins Log geschrieben – `Registered 3 command(s) for chat <id>
only` –, und das ist die Zahl, mit der man vergleichen muss. Eine Nachricht
aus dem *eingerichteten* Chat, die keinen Agenten erreicht, wird weiterhin
protokolliert, weil dort der Absender der Besitzer ist und „ich habe ihm
geschrieben, und nichts ist passiert“ sonst nicht von „es ist nie
angekommen“ zu unterscheiden wäre.

Was der Filter nicht abdeckt, und nicht abdecken kann, ist, *wer* innerhalb
des Chats schreibt: Eine `chat_id`, die eine Gruppe nennt, ist eine Gruppe,
deren Mitglieder alle mit den Agenten sprechen können.

Dieselbe Überlegung entscheidet, wohin die Befehlsliste geschrieben wird.
`setMyCommands` nimmt einen Scope, und `default` und `all_private_chats`
gelten für jeden Benutzer von Telegram – eine dort geschriebene Liste ist
also ein Menü, das Fremden gezeigt wird, mit „Server status“ darin, das
ankündigt, dass dahinter eine Maschine steckt, an der sich das Herumstochern
lohnt. Sie könnten nichts davon ausführen, aber ein Schild an einer
verschlossenen Tür ist trotzdem ein Schild. `fSetTelegramCommands` schreibt
die Liste nur in den Scope des eingerichteten Chats und **löscht** bei jeder
Aktualisierung die beiden öffentlichen: Eine Liste, die eine ältere Version
dieses Codes geschrieben hat, lebt auf der Seite von Telegram weiter, bis
etwas sie entfernt. `fHideTelegramPublicProfile` leert die beiden anderen
öffentlichen Strings, `setMyDescription` und `setMyShortDescription`, die
einen leeren Chat unter „What can this bot do?“ füllen.

Sichtbar bleiben der Name des Bots, sein Bild und der Start-Button, den
Telegram in jeden leeren Chat mit einem Bot zeichnet und den keine API
entfernen kann. Ein Druck darauf sendet `/start`, was wie alles andere aus
einem anderen Chat verworfen wird.

### Warum das Menü Werkzeuge enthält und keine Agenten

Telegram zeichnet `/name` neben jeden Eintrag im Befehlsmenü – dieser String
ist der Eintrag, er wird beim Antippen ins Eingabefeld getippt, und keine API
blendet ihn aus. Ein Menü aus Agenten konnte also nie die Liste der Agenten
sein, die jemand sehen wollte, und es wuchs mit der Agentenliste, während es
nichts darüber sagte, wozu der Bot da war.

Das Menü enthält drei Dinge, die der Bot tun kann. Welche Agenten es gibt,
ist eine Frage, und `/agents` beantwortet sie mit Inline-Buttons, auf denen
`os-watcher` steht und sonst nichts, weil der Text eines Buttons Sache des
Bots ist.

Der Rest folgt daraus:

- **Der ausgewählte Agent bleibt haften.** Ein Antippen eines Buttons oder
  das Nennen eines Agenten wählt ihn aus; alles nicht Adressierte geht an ihn,
  bis ein anderer gewählt wird. Den Agenten in jeder Zeile zu nennen ist
  einmal in Ordnung und bei der vierten Nachricht lästig. Die Auswahl liegt in
  `settings`, nicht im Speicher, weil der Dienst bei jedem Update neu startet.
- **Eine Antwort gewinnt weiterhin.** Sie ist eindeutig, und sie ist das, was
  jemand mit einem Handy in der Hand tut. Nichts anderes ändert die Auswahl,
  sodass ein Agent nie ein Gespräch erbt, nur weil er zufällig als Letzter
  gesprochen hat.
- **Ein gelöschter Agent ist nicht mehr ausgewählt.** `fReadSelectedAgent`
  prüft beim Herausgeben die Agentenliste: Niemanden zu erreichen ist besser,
  als den zu erreichen, der seine ID übernommen hat.
- **Der Bot spricht die Sprache der Installation.** Zuerst `agent_language`,
  dieselbe Einstellung, in der die Agenten antworten – seine Zeilen erscheinen
  im selben Gespräch wie ihre.

### Die Seitenleiste zeigt, wer arbeitet

```
alle 5 Sekunden und direkt nach Senden / Jetzt ausführen / Eintreffen einer Antwort
  api.js fRefreshAgentActivity        ← übersprungen, solange der Tab verborgen ist
    GET /api/admin/agents
      web/api.fListAgents
        exec_client.fListRunningAgents          → /run/boa/exec.sock
          exec_daemon.fVerbListRunningAgents
            fListRunningAgentIds      ← ein Durchgang durch /proc, alle Agenten auf einmal
      jeder Agent trägt `running`
    fSetAgentAvatarActivity           ← data-running auf dem Avatar; die Liste
                                        selbst wird nie per Timer neu aufgebaut
      fBuildAgentActivityArc          ← ein abgerundetes SVG-Rechteck über dem Rand
  CSS animiert sein stroke-dashoffset ← die Form steht still, der leuchtende Strich
                                        wandert im Uhrzeigersinn am Umriss entlang
```

### Anmelden

```
POST /login
  views.fLoginPage
    auth.fCountRecentFailures         ← 10 pro 15 Minuten pro Adresse
    auth.fVerifyCredentials           ← argon2id; eine falsche E-Mail wird trotzdem gehasht
    auth.fRecordAttempt
    auth.fLogIn                       ← Session-Cookie, 12 Stunden
```

---

### Eine Sprachnachricht kommt an

`fHandleMessage → fRouteMessage → fEnqueueTelegram → audio_jobs → fRunOneJob → fDownloadTelegram → fTranscribe → fSubmitTranscript → fSendChatMessageLocked → runner`. Die Antwort nutzt die gewöhnliche Zustellung über Telegram; der Webchat fügt das Transkript und einen privaten Player hinzu. Einstellungen → Audio verwendet GET/PUT `/api/admin/audio`; Modell-Downloads verwenden den RPC `install_whisper_model` und fragen den Fortschritt ab, ohne HTTP zu blockieren.

### API Calls

```text
AgentRun.fSendRecordedRequest → BaseProvider request recorder → api_calls.fRecordCall
Tab API Calls → GET /api/admin/agents/<id>/api-calls
  exec_client.fReadApiCalls → exec_daemon.fVerbReadApiCalls → api_calls.fReadCalls
Anfrage aufklappen → GET /api/admin/agents/<id>/api-calls/<call_id>
  exec_client.fReadApiCallBody → api_calls.fReadBodyChunk → gestreamter JSON-Text
  fBeautifyJson → fHighlightJsonElement → sicheres DOM
```

### Samba

```text
create_agent → fIndexAgent → samba.fProvisionAgent → samba/ + [agent-xxx]
GET /agents/<id>/samba → read_samba → samba.fReadSettings
PUT /agents/<id>/samba → write_samba → samba.fSaveSettings
  validieren → geschützte info + testparm → smbpasswd (stdin) → reload/close-share
SMB-Verbindung → root preexec --check-share <id> → Samba-Berechtigungen → uid des Agenten
delete_agent → samba.fRemoveAgent → Linux-Benutzer, Home-Verzeichnis und Index entfernen
--backup → tdbbackup + Server-SID → samba-backup im Archiv
--restore → Dienste stoppen → Benutzer/Daten wiederherstellen → native passdb ersetzen → starten
```

## 5. Übersicht der Einstiegspunkte und Routen

### HTTP

| Route | Methode | Handler | Datei |
|---|---|---|---|
| `/api/admin/rag` | GET, PUT | `fRuntime` | `backend/web/rag_api.py` |
| `/api/admin/rag/models/<vModel>/install` | POST | `fInstallModel` | `backend/web/rag_api.py` |
| `/api/admin/agents/<id>/rag/...` | GET, POST, PUT, DELETE | `fOverview`, `fUpload`, `fUploadPart`, `fDocument`, `fContent`, `fImport`, `fSearch` | `backend/web/rag_api.py` |
| `/login` | GET, POST | `fLoginPage` | `backend/web/views.py` |
| `/logout` | GET, POST | `fLogoutPage` | `backend/web/views.py` |
| `/` | GET | `fDashboardPage` | `backend/web/views.py` |
| `/kanban/` | GET | `fKanbanPage` | `backend/web/views.py` |
| `/tools/` | GET | `fToolsPage` → `/settings/?tab=tools` (bewahrt `family` und `agent`) | `backend/web/views.py` |
| `/settings/` | GET | `fSettingsPage` | `backend/web/views.py` |
| `/api/doc/` | GET | `fGetApiDocPage` | `backend/web/api_doc.py` |
| `/api/doc/openapi.json` | GET | `fGetOpenApiSpec` | `backend/web/api_doc.py` |
| `/api/admin/agent-templates` | GET | `fListAgentTemplates` | `backend/web/api.py` |
| `/api/admin/agent-imports` | POST | `fBeginImport` | `backend/web/agent_io_api.py` |
| `/api/admin/agent-imports/<id>` | GET, DELETE | `fImport` | `backend/web/agent_io_api.py` |
| `/api/admin/agent-imports/<id>/upload` | PUT | `fUploadImport` | `backend/web/agent_io_api.py` |
| `/api/admin/agent-imports/<id>/finish` | POST | `fFinishImport` | `backend/web/agent_io_api.py` |
| `/api/admin/agent-imports/<id>/install` | POST | `fInstallImport` | `backend/web/agent_io_api.py` |
| `/api/admin/agents/<id>/export` | GET | `fExport` | `backend/web/agent_io_api.py` |
| `/api/admin/agents/<id>/export/preview` | GET | `fPreviewExport` | `backend/web/agent_io_api.py` |
| `/api/admin/agents` | GET, POST | `fListAgents` (trägt immer `running` pro Agent), `fCreateAgent` | `backend/web/api.py` |
| `/api/admin/agents?kanban=1` | GET | `fListAgents`, fügt `reads_kanban` pro Agent hinzu | `backend/web/api.py` |
| `/api/admin/agents/<id>` | GET, PUT, DELETE | `fGetAgent`, `fUpdateAgent`, `fDeleteAgent` | `backend/web/api.py` |
| `/api/admin/agents/<id>/run` | POST | `fRunAgentNow` | `backend/web/api.py` |
| `/api/admin/agents/<id>/journal` | GET | `fGetAgentJournal` | `backend/web/api.py` |
| `/api/admin/agents/<id>/samba` | GET, PUT | `fGetAgentSamba`, `fPutAgentSamba` | `backend/web/api.py` |
| `/api/admin/agents/<id>/api-calls` | GET | `fGetAgentApiCalls` | `backend/web/api.py` |
| `/api/admin/agents/<id>/api-calls/<call_id>` | GET | `fGetAgentApiCall` | `backend/web/api.py` |
| `/api/admin/agents/<id>/chat` | GET, POST, DELETE | `fGetChat`, `fSendChatMessage`, `fClearChat` | `backend/web/api.py` |
| `/api/admin/agents/<id>/attachments/<id>` | GET | `fGetChatAttachment` | `backend/web/api.py` |
| `/api/admin/kanban` | GET | `fGetBoard` | `backend/web/api.py` |
| `/api/admin/kanban/cards` | POST | `fCreateCard` | `backend/web/api.py` |
| `/api/admin/kanban/cards/<id>` | PUT, DELETE | `fMoveCard`, `fDeleteCard` | `backend/web/api.py` |
| `/api/admin/kanban/cards/<id>/events` | GET | `fGetCardEvents` | `backend/web/api.py` |
| `/api/admin/kanban/cards/<id>/schedule` | PUT | `fScheduleCard` | `backend/web/api.py` |
| `/api/admin/kanban/deleted` | GET | `fGetDeletedCards` | `backend/web/api.py` |
| `/api/admin/tools` | GET | `fListTools` | `backend/web/api.py` |
| `/api/admin/skills` | GET | `fListSkills` | `backend/web/api.py` |
| `/api/admin/providers` | GET | `fListProviders` | `backend/web/api.py` |
| `/api/admin/themes` | GET | `fListThemes` | `backend/web/api.py` |
| `/themes/<name>.css` | GET | `fThemeStylesheet` | `backend/web/views.py` |
| `/api/admin/channels` | GET | `fListChannels` | `backend/web/api.py` |
| `/api/admin/channels/<name>` | PUT | `fConfigureChannel` | `backend/web/api.py` |
| `/api/admin/audio` | GET, PUT | `fGetAudioSettings`, `fUpdateAudioSettings` | `backend/web/api.py` |
| `/api/admin/audio/models/<vModel>/install` | POST | `fInstallAudioModel` | `backend/web/api.py` |
| `/api/admin/agents/<vAgentId>/audio/<vAudioId>` | GET | `fGetChatAudio` | `backend/web/api.py` |
| `/api/admin/settings` | GET, PUT | `fGetSettings`, `fUpdateSettings` | `backend/web/api.py` |
| `/api/admin/status` | GET | `fGetStatus` | `backend/web/api.py` |

Alles, was eine API ist, liegt unter `/api/`. Alles unter `/api/admin/`
verlangt eine Sitzung.

### Unix-Sockets

| `/run/boa-web/web.sock` | `0750 boa:boa` | gunicorn | Die Anwendung selbst. Nur `boa-proxy` erreicht sie |

| Socket | Modus | Server | Verben |
|---|---|---|---|
| `/run/boa/exec.sock` | `0660 root:boa` | `exec_daemon` | `ping`, `create_agent`, `delete_agent`, `read_agent_info`, `write_agent_info`, `read_system_prompt`, `write_system_prompt`, `read_crontab`, `write_crontab`, `run_now`, `list_running_agents`, `read_samba`, `write_samba`, `read_run_journal`, `read_api_calls`, `read_api_call_body`, `read_usage_summary`, `read_chat`, `read_chat_attachment`, `send_chat_message`, `clear_chat` |
| `/run/boa/agent.sock` | `0666` | `agent_api` | `who_am_i`, `kanban_add_card`, `kanban_move_card`, `kanban_delete_card`, `kanban_list_cards`, `channel_write`, `mail_read`, `mail_delete`, `mail_move`, `mail_forward` |

### Befehlszeile

| Befehl | Datei |
|---|---|
| `runner.py --agent-id NNN [--prompt … or --prompt-on-stdin] [--chat-message … or --chat-message-on-stdin] [--turn-id …] [--dry-run]` | `backend/core/runner.py` |
| `install-update-reinstall-debian.sh --install\|--update\|--reinstall\|--backup [file]\|--restore <file>` | `deploy/` |
| `install-update-reinstall-alpine.sh --install\|--update\|--reinstall\|--backup [file]\|--restore <file>` | `deploy/` |

---

## 6. Auswirkungsanalyse

Was kaputtgeht, wenn du das hier änderst.

| Komponente | Eine Änderung betrifft |
|---|---|
| `paths.fNormalizeAgentId` | **Jeden Pfad im System.** Sie ist die einzige Validierung zwischen Benutzereingabe und einem Dateisystempfad. Sie abzuschwächen, macht aus jeder Agenten-ID eine Path Traversal |
| Konstanten in `paths.py` | Alle vier Dienste, den Installer und die systemd-Units. `/opt/boa` zu ändern bedeutet, neu zu installieren |
| `deploy/haproxy/boa.cfg` | Jede Anfrage. `accept-proxy` muss zu dem passen, was das HAProxy der Maschine sendet: Mit `send-proxy-v2` auf diesem Backend ist es erforderlich, ohne weist der Bind jede Verbindung ab |
| Bind in `backend/web/gunicorn.conf.py` | Muss ein Unix-Socket bleiben. Gunicorn wieder einen Port und ein Zertifikat zu geben, bringt den Fehler PROXY-vor-TLS zurück |
| `exec_protocol.lKnownVerbs` | Die privilegierte Angriffsfläche. Ein Verb hinzuzufügen, fügt einen Weg hinzu, auf dem der Webprozess root um etwas bitten kann. Jede Ergänzung braucht dieselbe Prüfung wie die erste |
| `exec_daemon.fRunPrivilegedCommand` | Jeden privilegierten Befehl. Sie verwendet nie eine Shell; dort `shell=True` einzuführen, würde jeden Agentennamen zu einem Injektionspunkt machen |
| `agent_api.fAuthenticate` | Jede Anfrage eines Agenten an das Board und die Kanäle. Beide Prüfungen müssen bleiben |
| `db.cAppSchema` / `cKanbanSchema` | Bestehende Installationen. Es gibt kein Migrationssystem: Die Schemas verwenden `IF NOT EXISTS`, also **brauchen neue Spalten ausdrücklichen Migrationscode**, keine Änderung am Schema |
| `agent_scripts.cMinimumMinuteStep` | Wie oft sich ein Agent selbst einplanen darf. Es ist das Einzige, was zwischen einem nachlässigen Zeitplan und einer Schleife mit einer Cron-Zeile davor steht |
| `paths.lProtectedAgentFiles` | Welche Dateien in die Schublade wandern, die root gehört. Die Migration des Installers und der Daemon, der einen Agenten anlegt, lesen sie beide, sodass sie sich nicht uneinig sein können, welche das sind |
| `agents.fBuildAgentInfo` | Nur neue Agenten. Bestehende `info.json`-Dateien bleiben unberührt, also brauchen neue Felder einen Lesepfad mit Standardwert |
| `exec_daemon.fVerbWriteAgentInfo` | **Jedes Feld von `info.json`, das ein Speichern überlebt.** Es baut die Datei Schlüssel für Schlüssel neu auf, sodass ein Feld, das es nicht nennt, ein Feld ist, das die Oberfläche stillschweigend verwirft, sobald jemand zum ersten Mal Speichern drückt. Listen werden über `fReadNameList` gelesen, das einen fehlenden Schlüssel („lass das in Ruhe“) von einer leeren Liste („nimm sie alle weg“) unterscheidet: Mit `or` gelesen, stellte das Abhaken des letzten Werkzeugs die vorherige Liste wieder her |
| `skills.fSelectInstalledSkills` | Was einen Prompt erreicht und was `skill.read` öffnet. Sowohl der Index als auch das Werkzeug filtern darüber, sodass eine vom Server gelöschte Fähigkeit nicht mehr erwähnt wird, statt versprochen zu werden und dann zu scheitern |
| Neutrale Form in `providers.base` | Jeden Adapter und den Runner |
| Schnittstelle von `tool_registry` | Jedes Werkzeug in `/opt/boa/tools/`, auch die, die der Benutzer geschrieben hat |
| `telegram_listener.fIsFromTheConfiguredChat` | Wer mit deinen Agenten sprechen darf. Der Benutzername eines Bots ist öffentlich, also ist diese Prüfung die gesamte Autorisierung: Sie abzuschwächen lässt jeden, der den Bot findet, Läufe auf deinem Server starten |
| Signatur von `channels.fSendMessage` | Jeden Aufrufer und die zwei Sender, die zwei Argumente nehmen. `pReplyToMessageId` wird an Telegram und Discord übergeben, die zwei Kanäle, über die ein Mensch antworten kann |
| `discord_markdown.cMaxDiscordLength` | Ob die Antwort eines Agenten überhaupt ankommt. Discord lehnt einen `content` über 2000 Zeichen ab, und es lehnt ab – es kürzt nicht |
| `agent_routing.fMatchNamedAgent` | Wen eine Nachricht erreicht, in **beiden** Listenern. Der längste Treffer ist das, was `@News` und `@News Miner` zu zwei Agenten macht |
| `agent_routing.fBuildStatusReport` | Was /status bei beiden antwortet. Ein Bericht, sodass die beiden sich nicht uneinig sein können, wie viele Dienste es gibt |
| `discord_listener.fIsFromTheConfiguredChannel` | Welchem Kanal die Agenten zuhören. Anders als bei Telegram gibt es keine zweite Prüfung, wer spricht: Wer in diesem Kanal schreiben darf, darf Läufe starten |
| `kanban.lStates` | Das Board, die API, das Frontend und den Prompt jedes Agenten |
| Form der Einträge in `run_journal` | Sowohl den Schreiber (Runner) als auch die Leser (Daemon, Web). Alte Zeilen bleiben in den Journalen: Leser müssen fehlende Felder vertragen |
| `samba` | Lebenszyklus der Agenten, privilegierte API, SMB-Clients und Backup/Wiederherstellung beider Installer. Den Ordnerwächter, die Ableitung von Name und Pfad und den Umgang mit Geheimnissen intakt lassen |
| Eine Datei, die der Daemon aus dem Home-Verzeichnis eines Agenten liest (`runs.jsonl`, `chat.jsonl`, `memory.md`) | Wird nur über `paths.fReadAgentOwnedFile` gelesen. Eine neue Datei, die der Daemon aus einem Home-Verzeichnis liest, muss ebenfalls darüber gehen, sonst liest root, worauf auch immer der Agent ihn zeigen lässt – einen FIFO, der nie antwortet, einen Link auf irgendeine Datei der Maschine |
| Was ein Backup enthält (die `tar`-Zeile von `fDoBackup`) | Neuer Zustand unter `/opt/boa/`, der zur Installation gehört und nicht zum Code, muss dort hinzugefügt werden, sonst verliert ihn eine Wiederherstellung auf einer neuen Maschine |
| Die Kernel-Limits eines Laufs (`runner.cMaxProcesses`, `exec_daemon.cRunTasksMax`, `cRunMemoryMax`) | Ein Werkzeug, das mehr als 1024 Tasks oder 2 GiB braucht, muss sie anheben; ein Browser sind bereits einige Hundert Threads |
| `runner.py` als Pfad | Jeden geplanten Lauf. Cron startet ihn über den Pfad mit fast keiner Umgebung, also setzt der Runner seine eigene Wurzel auf sys.path: Ohne das scheitert `import backend`, und der Traceback geht an die Mail von cron, die auf einem LAN-Rechner nirgendwo ankommt |
| `runner.dAnswerLanguageLines` | Die Zeile, die einem System-Prompt hinzugefügt wird und dem Agenten sagt, in welcher Sprache er antworten soll. IN dieser Sprache geschrieben, und sie sagt, dass sie die eigene Regel des Prompts überstimmt – eine Vorliebe neben einer Regel verliert, gemessen |
| `agent_api.fFilterCardsForAgent` | Was ein Agent als existierend kennen darf. Jedes Lesen des Boards geht hier durch, und der Orchestrator ist die einzige Ausnahme. Stattdessen im Werkzeug zu filtern, würde eine Sicherheitsregel in eine Beschreibung legen, die man dem Modell ausreden kann |
| Auf welcher Seite eine Chatblase sitzt | Wer spricht. Eine Karte ist das, worum der Agent gebeten wurde, also kommt sie nach rechts zu den Nachrichten des Benutzers; der Bericht eines geplanten Laufs ist der Agent, der spricht, also bleibt er links |
| `chat.lToolsWorthReporting` | Welche Werkzeuge einen geplanten Lauf wert machen, in den Chat gestellt zu werden. Alles andere bleibt im Journal: Ein stündlicher Agent würde sonst vierundzwanzig Nachrichten „nichts zu melden“ am Tag posten |
| `chat.lAskingRoles` | Welche Rollen auf eine Antwort warten. Eine Rolle, die eine Gesprächsrunde öffnet und nicht aufgeführt ist, lässt das Eingabefeld offen, während der Agent arbeitet; eine aufgeführte, die nie geschlossen wird, sperrt das Eingabefeld für immer |
| `kanban.cRunNow` | Das Wort, das der Browser, die Agenten und die API alle statt eines Zeitstempels senden. Es irgendwo anders als in `fValidateRunAt` in eine Zeit zu verwandeln, verliert `run_mode` und damit den Unterschied zwischen „jetzt“ und einem gewählten Moment |
| `chat.cReplayedTurns` | Was jede Chatnachricht kostet. Jede erneut vorgespielte Gesprächsrunde wird bei der nächsten Nachricht noch einmal bezahlt, also macht ein höherer Wert lange Gespräche zunehmend teurer |
| `lTextColours` in `TestThemes` | Welche Farben der Kontrasttest misst. Eine Farbe, die als Text gemalt und auf dieser Liste vergessen wird, ist eine Farbe, die nichts prüft |
| Ein Attribut `style=` in irgendeiner Vorlage | Nichts: `style-src` ist `'self'` ohne `unsafe-inline`, also wirft der Browser es weg. Es gibt einen Test, der fehlschlägt, wenn eines auftaucht |
| `.notice-layer` in `app.css` | Wo jede Bestätigung und jeder Fehler der Anwendung erscheint. `position: fixed` ist tragend: `absolute` zentriert im Dokument statt auf dem Bildschirm, und genau diesen Fehler soll die Ebene beheben |
| Kette `.app:has(#vChatPanel…)` und `--status-bar-live-height` in `app.css` | Ob das Textfeld des Chats über der Statusleiste bleibt. Ein Block in dieser Flex-Spalte ohne `min-height: 0` oder eine Höhe von `.chat`, die die aktuelle Leistenhöhe nicht mehr abzieht, lässt die Seite wieder scrollen und setzt das Eingabefeld unter die Leiste |
| `agents.fValidateSchedule` | Ob ein Zeitplan aus einem `.zip` oder einer Vorlage zu einem Befehl in einem als root geschriebenen Crontab werden kann. Sie zu lockern (ein Leerzeichen, ein `#`, ein Zeilenumbruch) macht aus einem Import eine Codeausführung |
| `agent_home.sExcludedTopNames` / `fIsExcluded` | Was ein Export preisgeben und ein Import einschleusen kann: Browsersitzungen, `.ssh`, den Chat. Einen Namen zu entfernen, lässt ihn in beiden Richtungen durch |
| `agent_package.lManifestKeys` / `cFormatVersion` | Jedes exportierte `.zip` und jede Vorlage jedes Repositorys. Ein neuer Schlüssel braucht diese Version, um ihn zu lesen; eine geänderte Bedeutung braucht eine neue Formatnummer |
| `min_support` in `rag_models.json` | Welche Absätze einer geprüften Antwort überleben, für dieses Modell. Erhöht, beginnen treue Absätze zu verschwinden; gesenkt, geht ein Zitat auf eine fremde Passage durch. Was jeder Wert beider Modelle entfernt und durchlässt, steht in der Tabelle neben der Prüfung in `rag_verify.py`: Vor dem Verschieben eines Werts an echten Dokumenten neu messen und die Tabelle aktualisieren |
| `sha256` oder `dimensions` eines Modells in `rag_models.json` | Jede Bibliothek, die damit indexiert wurde. Ein neuer Fingerabdruck ist ein neuer Vektorraum: Jede Bibliothek indexiert bei ihrem nächsten Durchgang alle ihre Dokumente neu (`fFollowNewModel`), was bei einer großen Stunden dauert |
| `rag_embeddings.fCheckServedModel` / das `--alias` in `rag_runtime.fServe` | Ob ein Vektor von einem anderen Modell kommen kann als dem, das seine Bibliothek festhält. Ohne sie speichert ein Auftrag, der über einen Modellwechsel hinweg läuft, Vektoren zweier Modelle in einer Revision |
| `runner.lRagModesThatSearch` / `fFinishRagAnswer` | Ob ein dokumentbasierter oder geprüfter Lauf Text aus den eigenen Gewichten des Modells liefern kann. Einen Modus von der Liste zu entfernen oder die Prüfung auf fehlende Passagen bringt Antworten zurück, hinter denen kein Abruf steht |
| `rag_search.fSource` | Alles, was dem Modell über eine Passage gesagt wird, und worauf ein Zitat verlinkt: Der vorab abgerufene Prompt-Block, `rag.search`, `rag.read` und `fResolveCitations` verwenden es alle. Ein hinzugefügtes Feld braucht außerdem seine Spalte in den drei `SELECT`s, die es speisen |
| `rag_embeddings.EngineUnavailable` | Ob ein Indexierungsfehler Arbeit behält oder verwirft. Für einen Ausfall einen schlichten `ValueError` zu werfen, macht das Dokument zu `error` und löscht seine eingebetteten Chunks; für eine dauerhafte Ablehnung `EngineUnavailable` zu werfen, lässt das Dokument für immer in der Warteschlange |
| `rag_store.cSchema` | Nur Kataloge, die nach der Änderung angelegt werden. Jede bestehende Agentenbibliothek und jedes wiederhergestellte Backup behält die alte Tabelle: Eine neue Spalte braucht außerdem ihren Eintrag in `rag_store.lAddedColumns`, den `fMigrate` anwendet |
| `frontend/static/i18n/en-US.json` | Einen Schlüssel hinzuzufügen, heißt, ihn den anderen vierzehn hinzuzufügen, sonst fällt dieser String auf Englisch zurück. `TestTranslations` schlägt bei einem fehlenden Schlüssel, einem verlorenen `{placeholder}` und einem übersetzten Pfad- oder Werkzeugnamen fehl |

---

## 7. Erweiterungspunkte

### Ein neuer Anbieter

1. Schreib `backend/providers/<name>.py` mit einer Klasse, die
   `base.BaseProvider` erweitert, `cProviderName`, `cDefaultModel` und
   `cDefaultBaseUrl` setzt und `fSendMessages` implementiert.
2. Füge `factory.dProviderRegistry` eine Zeile hinzu.
3. Füge den Namen zu `agents.lSupportedProviders` hinzu.
4. Wenn er keinen Schlüssel braucht, füge ihn zu
   `factory.lSelfHostedProviders` hinzu.
5. Zusätzliche Optionen (wie `thinking` von DeepSeek) kommen in
   `lExtraConfigKeys`; die Factory bildet `reasoning_effort` →
   `pReasoningEffort` automatisch ab.

Führe ihn nicht mit einem bestehenden Adapter zusammen, nur weil der Dialekt
passt. Eine Datei pro Anbieter ist Absicht.

### Ein neues Werkzeug

Leg eine `.py` in `/opt/boa/tools/` an, die Folgendes deklariert:

```python
cToolName = "namespace.verb"
cToolDescription = "What the model is told it does."
dToolSchema = {"type": "object", "properties": {...}, "required": [...]}

def fRunTool(pArguments, pContext):
  return "text the model sees"
```

Es läuft als der aufrufende Agent. Wenn es etwas braucht, das Agenten nicht
erreichen dürfen, füge stattdessen der Agenten-API ein Verb hinzu und rufe es
über `agent_api_client` auf.

Die Datei muss root gehören: Die Anwendung importiert sie als Code.

### Eine neue Fähigkeit

Leg in `/opt/boa/skills/` ein Verzeichnis mit einer `SKILL.md` darin an:

```markdown
---
name: BackupVerification
description: One line. This is what every run pays for.
---

The procedure, at whatever length it needs.
```

Nichts zu registrieren und kein Neustart: `fListSkills` liest das
Verzeichnis, also erscheint sie beim nächsten Laden der Seite in der
Oberfläche. Hak sie bei einem Agenten an, gib diesem Agenten `skill.read`,
und beim nächsten Lauf steht sie in seinem Prompt.

Alles andere im Verzeichnis wird mit der Fähigkeit ausgeliefert. Es ist für
alle lesbar, sodass die Fähigkeit sagen kann „führe `verify.sh` in diesem
Verzeichnis aus“, und der Agent kann es.

Der Name ist der Verzeichnisname: Buchstaben, Ziffern und Bindestriche,
beginnend mit einem Buchstaben. Das `name:` im Kopf ist das, was ein Mensch
in der Liste sieht; der Verzeichnisname ist das, wonach ein Agent fragt.

### Eine neue privilegierte Operation

1. Füge die Verbkonstante zu `exec_protocol` und zu `lKnownVerbs` hinzu.
2. Schreib `fVerb<Name>` in `exec_daemon` und füge es zu `dVerbHandlers`
   hinzu.
3. Füge in `exec_client` einen Wrapper hinzu.

Validiere jedes Argument, bevor es einen Pfad oder eine Befehlszeile
erreicht, und halte das Verb spezifisch. Ein Verb, das allgemein genug ist,
um wiederverwendbar zu sein, ist meist ein Verb, das allgemein genug ist, um
missbraucht zu werden.

### Ein neuer Kanal

Nur Senden:

1. Schreib `fSendTo<Name>` in `channels.py`.
2. Füge es zu `lChannels` und `dChannelSenders` hinzu.
3. Füge seine Felder zu `dChannelFields` in `frontend/static/js/settings.js`
   hinzu, und jedes, das eine Zugangsberechtigung ist, dort zu
   `lSecretChannelFields` und zu `lSecretConfigFields` in `channels.py`.

Auch Empfangen, was es erst zu einem Gespräch macht:

4. Schreib `fRead<Name>Messages` in `channels.py`, das sie mit der ältesten
   zuerst zurückgibt.
5. Schreib `<name>_inbox.py`: zwei Tabellen in `db.cAppSchema` und den
   ausgewählten Agenten in einer Einstellung.
6. Schreib `<name>_listener.py` gegen `agent_routing`, das bereits die
   Agentenliste, den Namensabgleich, die abschließende Antwort und den
   Statusbericht enthält. Was übrig bleibt, ist das Protokoll.
7. Schreib `<name>_texts.py` für die Sätze, die dieser Kanal anders sagt, mit
   Durchfall auf `telegram_texts` für den Rest.
8. `deploy/systemd/boa-channel-<name>.service` und ein Dienst in
   `deploy/openrc/`, der Name
   in `lServices` und an den sieben Stellen, an denen der Debian-Installer
   seine Units nennt, und in `system_info.lBoaServiceNames`. Wenn sein
   OpenRC-Name abweicht, füge die Zuordnung in
   `system_info.dOpenRcServiceNames` hinzu.
9. Sein Schalter in `dChannelSwitches`, sein Schlüssel `chat.source<Name>` in
   den fünfzehn Katalogen und `<name>` in `exec_daemon.lKnownChatSources`.

### Eine neue Sprache

Fünfzehn werden ausgeliefert: `de-DE`, `en-GB`, `en-US`, `es-AR`, `es-ES`,
`fr-FR`, `he-IL`, `hi-IN`, `it-IT`, `ja-JP`, `ko-KR`, `pt-BR`, `pt-PT`,
`ru-RU`, `zh-CN`. Eine sechzehnte sind sieben Stellen, und die Tests nennen jede davon:

1. Kopiere `frontend/static/i18n/en-US.json` und übersetze die Werte.
2. Füge das Tag zu `lSupportedLanguages` in `frontend/static/js/i18n.js`
   hinzu.
3. Füge den drei Auswahlmenüs eine `<option>` hinzu: zwei in
   `frontend/templates/settings.html`, eines in `login.html`, nach Tag.
4. Füge `runner.dAnswerLanguageLines` eine Zeile hinzu, IN dieser Sprache
   geschrieben.
5. Füge `telegram_texts.dTexts` einen Block hinzu und das Tag zu
   `lSupportedLanguages` dieses Moduls, sonst fällt der Bot auf Englisch
   zurück. Füge auch `discord_texts.dTexts` einen hinzu: Es enthält die drei
   Sätze, die Discord anders sagt, und eine Sprache, die dort fehlt, bekommt
   diese drei auf Englisch.
6. Übersetze die Dokumentation aus den en-US-Dateien: `README.<tag>.md` im
   Wurzelverzeichnis, `doc/CODE.<tag>.md` und `doc/MANUAL.<tag>.md`. Füge die
   Sprache der Sprachzeile oben in jedem README hinzu, in alphabetischer
   Reihenfolge des Tags. en-US ist die Quelle jeder anderen Sprache und
   behält die Namen ohne Tag: `README.md`, `doc/CODE.md`, `doc/MANUAL.md`.
7. Wenn sie von rechts nach links geschrieben wird, füge ihr Tag zu
   `lRightToLeftLanguages` in `frontend/static/js/i18n.js` hinzu. Sonst
   nichts: Das Stylesheet verwendet bereits logische Eigenschaften (siehe
   „Von rechts nach links“ oben).

`TestTranslations` in `tests/test_web.py` schlägt fehl bei einem fehlenden
Schlüssel, einem überzähligen, einem leeren String, einem verlorenen
`{placeholder}`, einem übersetzten Pfad- oder Werkzeugnamen, einer
unsortierten Datei, einem Auswahlmenü, das die Sprache nicht anbietet, einer
fehlenden Prompt-Zeile und einem fehlenden Telegram-Block. Bei den sechs
nicht lateinischen Sprachen wird außerdem geprüft, dass sie tatsächlich in
ihrer eigenen Schrift geschrieben sind, weil eine Datei mit englischen
Strings unter einem russischen Namen jede andere Prüfung besteht.
`TestExampleAgents` in `tests/test_tools.py` schlägt fehl bei einer Sprache
ohne ihr README, CODE oder MANUAL oder bei einem README, das nicht auf das
README jeder anderen Sprache verlinkt; `TestTheCodeDocumentsPointAtRealLines`
in `tests/test_web.py` schlägt bei einem CODE fehl, dessen
`file.py:line`-Verweise von denen des englischen abweichen.

Was eine Übersetzung ändern darf: einen Dateinamen, den der englische Text
als BEISPIEL nennt, wie `check-disk.sh`. Nichts sucht nach diesen.

### Ein neuer RAG-Antwortmodus

1. Füge ihn den erlaubten Modi in `rag_settings.fValidateSettings` und dem
   Enum `mode` in `backend/web/rag_api_doc.py` hinzu.
2. Gib ihm seine Regel in `rag_search.fPrompt` und sag dort, was der Runner
   durchsetzt.
3. Füge ihn in `runner.py` zu `lRagModesThatSearch` hinzu, wenn das Modell
   suchen muss, und zu `fCheckRagAnswer` / `fFinishRagAnswer`, wenn seine
   Antworten geprüft werden.
4. Eine `<option>` in `frontend/templates/agent_rag.html`, ihr Rückfall in
   `dRagModeHints` in `rag.js` und `rag.<mode>` plus `rag.modeHint.<mode>` in
   den fünfzehn i18n-Dateien.
5. Tests in `tests/test_rag.py` (`TestRagInAgentRun`), mit dem
   geskripteten Anbieter und einem gefälschten `rag_embeddings.fEmbed`.

### Ein neues Einbettungsmodell

1. Ein Eintrag in `backend/core/rag_models.json`: die GGUF-URL, an einen
   Commit gepinnt (nie an einen Branch), `size` und `sha256` aus der API des
   Repositorys, `dimensions`, `context`, das `pooling`, das seine Model Card
   verlangt, und seine Präfixe für Anfragen und Passagen.
   `TestEmbeddingModelChoice` prüft, dass der Eintrag vollständig ist.
2. Lass es neben der installierten Engine auf der Testbibliothek laufen und
   miss es so, wie die Anwendung es verwendet (der Kommentar über der Tabelle
   in `rag_verify.py` sagt, wie): Sein `min_support` ist der höchste Wert, der
   weniger als 1 % der Zitate auf Passagen eines anderen Themas durchlässt,
   sein `min_similarity` liegt zwischen verwandten und nicht verwandten
   Fragen. Füge seine Zeilen dieser Tabelle hinzu.
3. Sein Spitzenspeicher muss in `MemoryMax` in
   `deploy/systemd/boa-embeddings.service` passen; schreib ihn, und wie viel
   langsamer es als EmbeddingGemma indexiert, als `memory_mb` und
   `relative_indexing_time`.
4. Die Liste in Einstellungen → RAG und die Download-Route kommen aus dem
   Katalog; nur die Tabellen in `doc/MANUAL*.md` und die Enum-Beschreibungen
   in `rag_api_doc.py` brauchen das neue Modell beim Namen.

### Ein neues Feld der Dokumentinformationen

1. Füge die Spalte zu `rag_store.cSchema` und zu `rag_store.lAddedColumns`
   hinzu, sonst haben bestehende Bibliotheken sie nicht.
2. Füge den Schlüssel an seiner Stelle zu `rag_store.lMetadataKeys` hinzu und
   jede Formatprüfung, die er braucht, zu `rag_store.fAction`.
3. Wenn das Modell ihn sehen soll, füge `d.<column>` zu den drei `SELECT`s in
   `rag_search` und das Feld zu `rag_search.fSource` hinzu.
4. Füge ihn dem Schema `metadata` in `backend/web/rag_api_doc.py` hinzu.
5. Füge ihn an seiner Stelle der Feldliste in `frontend/static/js/rag.js`
   hinzu.
6. Füge `rag.<key>` zu den fünfzehn Dateien `frontend/static/i18n/*.json`
   hinzu.
7. Deck ihn in `tests/test_rag.py` ab; der Migrationstest baut bereits einen
   Katalog ohne jede Spalte aus `lAddedColumns`.

### Eine neue Vorlage

Vorlagen leben im Vorlagen-Repository, nicht hier:

1. Ein Ordner `<name>/` in `bunch-of-aigents-templates`, benannt wie das
   `name` der Vorlage (`^[a-z][a-z0-9-]{0,39}$`).
2. `agent.json`: `format` 1, `name`, `description` in den fünfzehn Sprachen,
   `tools`, `schedules`, `limits` und, wenn sie ihre Bibliothek braucht,
   `rag`. Am schnellsten baut man den Agenten hier, exportiert ihn und
   entpackt ihn dort.
3. `system-prompt.md`, auf Englisch, endend mit der Regel über die Sprache
   der Antwort.
4. `README.md`, in en-US, für die Leute, die dieses Repository lesen: wozu
   der Agent da ist, was er tut, was er zuerst braucht, was er nicht tun
   wird, was er mitbringt und wie man ihn installiert. Die Anwendung
   ignoriert es.
5. Führe die Tests dieses Repositorys aus: `TestExampleAgents` liest den
   Checkout neben diesem mit `agent_package` und schlägt fehl bei einer
   Vorlage, die die Anwendung abweisen würde, einem Werkzeug, das es nicht
   gibt, einer fehlenden Sprache oder einem README, das fehlt oder die
   Werkzeuge und Zeitpläne der Vorlage nicht nennt.
6. Eine Zeile in der Vorlagentabelle jedes MANUAL hier, eines pro Sprache,
   und eine mit Link auf ihr README in den drei READMEs dort.

### Eine neue Seite

1. Eine Route in `backend/web/views.py`, die `render_template` zurückgibt.
2. Eine Vorlage, die `app_base.html` erweitert.
3. Ein `<li>` im `nav` von `app_base.html`.
4. Ihr eigenes JS in `frontend/static/js/`, das mit
   `await fWaitForTranslations()` beginnt, bevor es irgendetwas rendert.
