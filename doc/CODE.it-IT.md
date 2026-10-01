# CODE.md

Riferimento tecnico di Bunch of AIgents. Scritto per essere letto in modo
chirurgico: salta alla sezione che ti serve, non leggerlo dall'inizio alla fine.

## Indice

1. [Architettura e decisioni di progettazione](#1-architettura-e-decisioni-di-progettazione)
2. [Mappa dei moduli](#2-mappa-dei-moduli)
3. [Indice dei simboli chiave](#3-indice-dei-simboli-chiave)
4. [Flussi principali](#4-flussi-principali)
5. [Punto di ingresso e mappa delle rotte](#5-punto-di-ingresso-e-mappa-delle-rotte)
6. [Analisi di impatto](#6-analisi-di-impatto)
7. [Punti di estensione](#7-punti-di-estensione)

---

## 1. Architettura e decisioni di progettazione

Questa è la parte che non si può ricavare dal codice, quindi è la parte che vale
la pena leggere.

### La premessa

Un agente, qui, è un modello linguistico con una shell su un server, svegliato
da cron, senza nessuno che lo guardi. Ogni decisione strutturale discende dal
prendere sul serio questo fatto: prima o poi il modello farà qualcosa di non
voluto, quindi la domanda non è come impedirlo, ma che cosa può raggiungere
quando succede.

### Un utente Linux per agente

L'agente `007` è l'utente di sistema `agent-007`, proprietario di
`/opt/boa/agents/007/` con modo `0700`. L'isolamento tra agenti è quello del
kernel, non una sandbox scritta in Python. Un agente non può leggere il prompt
di sistema, il giornale o la chiave API di un altro agente perché lo dice il
filesystem.

`/opt/boa/agents/` stesso è `root:root 0711`: attraversabile, non elencabile.
Un agente non può enumerare gli altri agenti, può solo fallire nell'aprire i
percorsi che indovina.

È per questa decisione che `bash.run` non ha bisogno di una lista di
autorizzazioni. Una lista di blocco su una shell è teatro — qualunque cosa possa
eseguire `sh` può eseguire qualsiasi cosa la lista nomini — mentre un account
utente è un confine che fa rispettare il kernel.

### Che cosa un agente non può riscrivere di sé

La home è dell'agente, 0700, ed è proprio questo il punto: la sua memoria, il
suo giornale, la sua conversazione e ogni script che scrive vivono lì. Tre file
di quella home non spetta a lui cambiarli, e stanno FUORI dalla home, in
`/opt/boa/agents-config/xxx/`, che è `root:agent-xxx 0750` sotto un padre
`root:root 0711`.

| File | Perché non è dell'agente |
|---|---|
| `info.json` | Quali strumenti gli sono stati concessi e quanto può spendere |
| `system-prompt.md` | La definizione di che cosa deve fare |
| `api-token` | Ciò con cui si identifica davanti all'API degli agenti |

Quello che fa funzionare tutto questo non è il proprietario dei file: è quello
della directory. Il permesso di scrittura su una directory è ciò che decide se
un file al suo interno può essere eliminato e sostituito, quindi un agente
proprietario della directory potrebbe eliminare `info.json` e scrivere il suo,
chiunque fosse il proprietario del file. In questa può entrare e leggere, e non
può creare, rinominare o eliminare niente.

**E questa regola vale per il cassetto quanto per ciò che contiene**, ed è il
motivo per cui questi file non vivono più in `agents/xxx/config/`. Quel percorso
era una voce nella HOME, la home è dell'agente con 0700, e rinominare una voce
richiede il permesso di scrittura sul padre e nient'altro - il modo della cosa
rinominata non viene mai consultato. Quindi l'agente non poteva modificare
`info.json` e poteva fare questo:

    mv ~/config ~/config-old && mkdir ~/config && echo '...' > ~/config/info.json

ed essere letto dal sostituto. Spostare il cassetto fuori dalla home mette sotto
root ogni directory lungo il percorso. Dallo spostamento discendono due cose:

  - **Non c'è più nessun ripiego sulla home.** Prima c'era, affinché un
    aggiornamento non fosse un servizio che smetteva di rispondere prima che
    girasse la migrazione - ed era esso stesso un aggiramento, perché bastava
    nascondere il file vero per far leggere quello dell'agente. Ora il demone
    migra all'avvio, oltre a farlo il programma di installazione, quindi non
    resta nulla da coprire.
  - **Eliminare un agente elimina anche la sua configurazione.** Non sta più
    dentro la home che `userdel --remove` si porta via e, se restasse lì,
    verrebbe consegnata al prossimo agente a cui fosse dato quell'id.

`fOpenProtectedAgentFile` è la seconda risposta alla stessa domanda: apre con
`O_NOFOLLOW` e verifica sul FILE APERTO che sia un file regolare, di proprietà
di root e scrivibile da nessun altro. È ciò che sopravvive a un chmod sbagliato
durante un aggiornamento o a un ripristino da un backup con il proprietario
sbagliato.

Questo è stato misurato prima di essere corretto, su un'installazione reale: un
agente ha aggiunto `mail.read` al proprio `info.json` e il demone privilegiato
ha poi riportato lo strumento come concesso - quindi un agente poteva concedersi
la casella di posta, i canali, o alzarsi i propri tetti. Poteva anche sostituire
il proprio prompt con «ignora tutte le tue regole», che sarebbe rimasto così in
ogni esecuzione da quel momento in poi.

L'isolamento tra agenti non ha bisogno di niente di tutto questo:
`/opt/boa/agents/` è `root:root 0711` e ogni home è 0700, quindi il kernel
rifiuta già. Per questo regge anche quando uno strumento ha un bug.

### Che cosa legge root dalla home

Il giornale, la memoria e la chat sono file dell'agente: scritti dai suoi
processi, nella sua home 0700, e letti dal demone privilegiato come root - che
legge qualunque cosa gli si indichi. Misurato sul codice prima che questo
esistesse: una FIFO chiamata `runs.jsonl` teneva bloccato per sempre il thread
del demone che la apriva e, siccome l'elenco degli agenti legge il giornale di
ogni agente, ogni richiesta successiva di quell'elenco perdeva un thread in più;
un link chiamato `memory.md` che puntava a un file qualsiasi della macchina
faceva sì che root consegnasse all'interfaccia il testo di quel file; e un link
a qualcosa senza fine faceva leggere root finché non veniva ucciso.

Così tutti e tre vengono letti tramite `fReadAgentOwnedFile`, che è il fratello
di `fOpenProtectedAgentFile` per i file che SONO dell'agente: `O_NOFOLLOW`
rifiuta un link all'apertura, `O_NONBLOCK` impedisce a una FIFO di tenere
bloccata l'apertura finché qualcuno non ci scrive, e i controlli si fanno sul
descrittore aperto - un file regolare, di proprietà dell'utente dell'agente -
così niente può essere scambiato tra il controllo e la lettura. Non legge mai
oltre un limite, applicato su ciò che viene letto e non solo su ciò che ha detto
`fstat`, perché l'agente può aggiungere righe mentre la lettura è in corso:
32 MB per il giornale e per la chat, letti dalla FINE quando il file è più
grande, perché le righe più recenti sono quelle che una cronologia mostra; 4 MiB
per la memoria, sufficienti per il suo massimo di un milione di caratteri UTF-8.
Solo i file scritti dall'esterno che superano quel budget di lettura ricevono
`[truncated]`; `fWrite` rifiuta il contenuto troppo grande prima di sostituire qualsiasi cosa. Un byte sbagliato costa una riga, non la lettura.

Ciò che viene rifiutato viene detto, non inghiottito: `read_run_journal`,
`read_chat` e `read_memory` falliscono con il motivo, così un operatore viene a
sapere che qualcosa in quella home non è ciò che ha scritto l'applicazione.
L'unica eccezione è `read_usage_summary` per tutti gli agenti, da cui si disegna
la barra laterale: lì un giornale illeggibile costa a quell'agente i suoi
totali, con il motivo accanto, e a nessun altro i propri.

### Che cosa viaggia sulla riga di comando

Il demone avvia un'esecuzione come l'agente con `Popen`, e il messaggio che il
proprietario aveva scritto - o il prompt che costruisce una scheda scaduta -
era uno dei suoi argomenti: `--chat-message <text>`, `--prompt <text>`. La riga
di comando di un processo è leggibile da qualsiasi utente della macchina
attraverso `/proc/<pid>/cmdline`, e un agente con `bash.run` è un utente della
macchina. Misurato sulla macchina Debian di prova: `ps` eseguito come
`agent-001` mostrava il messaggio che il proprietario aveva appena mandato ad
`agent-000`, per tutta la durata di quell'esecuzione, che per impostazione
predefinita arriva fino a cinque minuti.

Così il testo scende per lo standard input del figlio e la riga di comando porta
solo `--chat-message-on-stdin` o `--prompt-on-stdin`. `fStartRunner` è l'unico
posto che avvia un runner: rifiuta un testo più lungo di
`cMaxStdinPayloadBytes` prima che esista alcun processo, perché quel limite è
sotto il buffer di 64 KiB di una pipe e una scrittura che sta nel buffer non
aspetta mai il figlio - questo demone non aspetta i runner. Un figlio che non
c'è già più quando avviene la scrittura, un interprete che fallisce
all'import, è una pipe rotta e non un fallimento del demone. Dall'altra parte
il runner legge il testo con lo stesso limite, rifiuta un messaggio di chat
vuoto invece di rispondere a una domanda che nessuno ha fatto, e chiude il
turno per cui era stato avviato quando rifiuta, così la conversazione non
aspetta per sempre. `--prompt` e `--chat-message` restano, per un'esecuzione
avviata a mano da un terminale.

### Che cosa può fare un'esecuzione alla macchina

I tetti in `info.json` - token, passi, secondi, esecuzioni al giorno - li fa
rispettare il runner, e il runner è un programma che l'agente sta pilotando.
Ciò che regge quando è proprio il programma ad andare storto lo fa rispettare
il kernel, in due livelli.

Il runner abbassa i propri limiti di risorse prima di fare qualunque altra
cosa, `fApplyResourceLimits`, dal punto di ingresso e non da `fMain` - i test
chiamano `fMain` nello stesso processo, e un RLIMIT_NPROC abbassato dentro la
sessione di uno sviluppatore con migliaia di thread già in esecuzione impedisce
a quella sessione di fare fork. Ogni processo che l'esecuzione avvia li eredita:
RLIMIT_NPROC a 1024, contato sull'uid dell'agente nel suo insieme, così una fork
bomb da `bash.run` si ferma a quel numero e non alla macchina - contano anche i
thread, ed è per questo che non è più basso, visto che un browser ne ha qualche
centinaio; nessun file core; nessun file oltre i 4 GiB. Non RLIMIT_AS: Chromium
riserva spazio di indirizzamento a decine di gigabyte e non partirebbe. Questo
livello è lo stesso su Debian e su Alpine, ed è l'unico che ha un'esecuzione
avviata dal crontab dell'agente stesso.

Dove systemd è il PID 1 il demone aggiunge il secondo: `fStartRunner` mette
l'esecuzione in uno scope transitorio tutto suo,
`boa-agent-<id>-<random>.scope` sotto `boa-agents.slice`, con `TasksMax=1024` e
`MemoryMax=2G`. `systemd-run --scope` fa exec nel comando, quindi il pid è
ancora quello del runner e `/proc` mostra ancora la sua riga di comando;
`setpriv` è ciò che scende all'agente, perché systemd-run deve essere root per
creare lo scope. Misurato prima che fosse così: un'esecuzione era figlia di
`boa-exec.service`, nel cgroup del demone stesso, e un agente fuori controllo
consumava il TasksMax del demone e lo lasciava incapace di fare fork. Lo scope
è anche ciò che chiude quanto un'esecuzione si è lasciata dietro: `bash.run`
manda i segnali al proprio gruppo di processi, quindi un comando che aveva
chiamato `setsid`, o un figlio in background di uno che era finito in tempo,
sopravviveva all'esecuzione; `fWatchRunner` aspetta l'esecuzione e ferma il suo
scope, che raggiunge tutto ciò che l'esecuzione ha avviato, ovunque si sia
spostato. Un'esecuzione che è stata uccisa - dal limite di memoria, da un
operatore - non ha scritto nulla uscendo, quindi lo stesso thread registra la
fine nel giornale e chiude il turno nella chat; un'esecuzione che è uscita da
sola ha già fatto entrambe le cose, e il turno viene verificato invece di
essere dato per scontato.

### Dove vivono le chiavi dei provider

Le chiavi condivise da tutti gli agenti sono in
`/opt/boa/config/apikeys/<provider>.key`, di proprietà di `boa`, la directory
`0700` e i file `0600`.

0750 e 0640 terrebbero già fuori gli agenti - nessun utente agente è nel gruppo
`boa` - ma questo si regge sul fatto che l'elenco dei gruppi di ogni agente
resti vuoto per tutta la vita dell'installazione, e basta un `usermod -aG` per
renderlo falso. Un modo che non concede nulla al gruppo non dipende da questo.
`api_keys.fWrite` imposta entrambi i modi a ogni scrittura e non solo alla
creazione, così una directory che arriva da un'installazione più vecchia viene
chiusa la prima volta che si salva una chiave.

La directory si chiamava `keys` finché non è stata rinominata: si leggeva come
«le chiavi di questa installazione» e stava a un errore di battitura dalla
`keys/` per agente dentro la home di ogni agente, che è un'altra cosa e che un
agente *può* leggere - la sua chiave, messa lì per addebitarlo a un altro
account. Il programma di installazione sposta la vecchia directory con
`--update` e la elimina solo quando è vuota.

Niente di tutto questo impedisce a un agente di avere la chiave del provider su
cui gira davvero: l'API degli agenti gli consegna quella, gli serve per fare la
chiamata, e un agente con `bash.run` potrebbe stamparla. Quello che impedisce è
che un agente legga le chiavi dei provider che non usa.

### Dieci servizi, due avviati come root

| Processo | Utente | Perché esiste |
|---|---|---|
| `boa-proxy` | `boa` | HAProxy: termina il TLS, serve entrambe le porte |
| `boa-web` | `boa` | Serve l'interfaccia e l'API, su un socket Unix |
| `boa-exec` | `root` | Crea gli utenti e avvia le esecuzioni degli agenti |
| `boa-samba` | `root` | Autentica le sessioni SMB, poi serve i file come l'agente proprietario |
| `boa-embeddings` | `boa` | Serve il modello di vettorizzazione locale delle biblioteche documentali, su un socket Unix |
| `boa-rag` | `boa` | Gestisce la coda di indicizzazione delle biblioteche documentali |
| `boa-agent-api` | `boa` | Custodisce ciò che gli agenti possono usare ma non leggere |
| `boa-buzzer` | `boa` | Sveglia un agente quando scade una delle sue schede |
| `boa-channel-telegram` | `boa` | Ascolta su Telegram e consegna a un agente ciò che arriva |
| `boa-channel-discord` | `boa` | Lo stesso, per un canale Discord |

Su Debian le unità dei canali sono `boa-channel-telegram.service` e
`boa-channel-discord.service`; le unità dei canali futuri seguono
`boa-channel-<channel>.service`. OpenRC mantiene `boa-telegram` e
`boa-discord`. `system_info.fServiceName` risolve questi nomi sia per la
scheda del sistema sia per i rapporti di stato dei listener.

`fInstallSystemdUnits` chiama `fRetireLegacyChannelUnits` per fermare e
disabilitare ogni vecchia unità di canale prima di eliminarla e abilitare la
sua sostituta. Gli aggiornamenti ripetuti funzionano anche quando non esiste
nessuna unità vecchia. Se un aggiornamento fallisce prima di installare le
nuove unità, `fStartServices` può riavviare quelle vecchie durante il rollback.

Gli ultimi quattro sono `boa` e non root di proposito: ognuno di loro vuole che
qualcosa venga fatto come l'utente dell'agente - avviare un'esecuzione,
scrivere in una home 0700 - e ognuno chiede a `boa-exec` di farlo invece di
ricevere il privilegio. Un servizio raggiungibile dall'esterno, come di fatto
lo sono i due listener, è l'ultimo che dovrebbe detenerlo.

### Un ambiente virtuale non è rilocabile

`python3 -m venv <path>` scrive `<path>` nello shebang di ogni script di
console installato in seguito al suo interno, in `VIRTUAL_ENV` negli script di
attivazione e nella riga `command` di `pyvenv.cfg`. L'ambiente viene costruito
in `venv.new` e rinominato in `venv`, quindi tutti e tre nominano poi una
directory che non c'è più.

Misurato su un Debian 13 reale e su un Alpine 3.24 reale: entrambe le
installazioni si sono completate, entrambe hanno stampato «Installation
finished», ed entrambe hanno lasciato `boa-web` a riavviarsi ogni cinque
secondi con

```
status=203/EXEC - Failed to execute /opt/boa/venv/bin/gunicorn:
No such file or directory
```

Il file c'era. La sua prima riga nominava `/opt/boa/venv.new/bin/python3`, che
non c'era.

`fBuildVirtualEnv` aveva un controllo proprio per questa classe di guasti, e
passava, perché esegue `bin/python3` - un SYMLINK all'interprete di sistema,
che risponde da dovunque si trovi. Solo uno script di console ha il percorso
scritto dentro. Così ora il controllo esegue anche `bin/gunicorn --version`,
che è il file che esegue l'unità del servizio, e `fRepointVirtualEnv` riscrive
tutti e tre i percorsi registrati mentre l'ambiente ha ancora il suo nome di
costruzione. La riscrittura viene verificata invece di essere data per
scontata: se un pip futuro scrive i suoi script di console in un altro modo, il
programma di installazione si ferma lì.

### Un aggiornamento che fallisce lascia qualcosa in esecuzione

Tre fasi, e l'ordine è la riparazione.

Prima un aggiornamento fermava i servizi, eliminava `webapp/` e solo dopo
eseguiva pip. Un pip che falliva - niente rete, un indice giù, una wheel che
non si compilava - lasciava un'installazione con i servizi fermi e il codice
sparito: una macchina che un minuto prima funzionava, e che aveva bisogno che
qualcuno se ne accorgesse e la recuperasse a mano.

| Fase | Che cosa succede | Quanto costa un fallimento |
|---|---|---|
| Preparazione | Domande poste, dipendenze installate, codice scaricato, il nuovo virtualenv COSTRUITO accanto a quello in esecuzione e verificato che importi | Niente. La vecchia versione è ancora in esecuzione e intatta |
| Scambio | Stop, `webapp/` spostata in `webapp.previous`, `venv` in `venv.previous`, i nuovi messi al loro posto, avvio | Annullabile: entrambe le versioni precedenti sono ancora su disco |
| Verifica | `curl` chiede all'applicazione la pagina di accesso, quindici volte in trenta secondi | `fRollBack` rimette a posto entrambe e le avvia di nuovo |

Quel `curl` manda il PROXY protocol solo in modalità `proxied`. In modalità
`direct` il bind non ha `accept-proxy`, quindi un'intestazione PROXY finisce
nell'handshake TLS e la richiesta non riceve nessuna risposta. Prima veniva
mandato in entrambe le modalità, il che faceva finire ogni `--install --ports
direct` con «did not answer» su un'installazione che stava servendo pagine, e
faceva annullare da solo ogni `--update` in modalità diretta. Confermato
passando entrambe le macchine di prova a `direct` e ritorno: con il flag legato
alla modalità, entrambe hanno risposto 200 sulla 443 e poi sulla 11443. Un test
esegue `fVerifyInstallation` di entrambi i programmi di installazione contro un
`curl` che registra i suoi argomenti, una volta per modalità, e verifica che il
flag ci sia in una e manchi nell'altra.

Quando quel `curl` non riceve mai una risposta, `fExplainWhyItDoesNotAnswer`
scrive com'era la macchina in quel momento nello stesso log a cui rimanda
l'errore: che cosa dice curl stesso - interrogato di nuovo con `-sS`, così da
distinguere una connessione rifiutata, un handshake fallito e una richiesta
scaduta, perché `000` non è un codice HTTP ma curl che dice di non averne mai
ricevuto uno - lo stato di ciascuno dei dieci servizi, se c'è qualcosa in
ascolto sulla porta, e le ultime quindici righe di `boa-proxy.log`,
`boa-web.log` e dell'`error.log` di gunicorn. `fReportServiceStates` è la metà
che cambia tra i due: `rc-service ... status` su Alpine, `systemctl is-active`
più il journal di `boa-web` e `boa-proxy` su Debian.

Esiste perché una prima installazione su un Alpine appena installato è finita
con «The application did not answer on port 11443 (last code: 000)» e il log
non conteneva nient'altro in proposito - né quale servizio fosse giù, né se la
porta fosse occupata, né una sola riga di ciò che gunicorn aveva stampato.
L'unico file che l'errore nomina non poteva rispondere alla domanda per cui lo
si apriva. Che cosa cercarci: un servizio che si dichiara avviato accanto a
«nothing is listening on port 11443» è un processo che muore e viene
riavviato, perché un servizio supervisionato che muore nell'istante in cui
parte viene riportato come avviato dal comando che lo ha avviato. Quattro test
ESEGUONO entrambe le funzioni - contro un `curl` che rifiuta di connettersi, un
`ss` che tiene occupata la porta e uno che non lo fa, e un `rc-service` e un
`systemctl` che rispondono «stopped» e restituiscono un fallimento.

`fRollBack` avvia i servizi in una SUBSHELL, e il `|| true` accanto non basta
da solo: `fStartServices` chiama `fDie` quando un servizio non vuole partire,
`fDie` chiama `exit`, e `exit` termina la shell qualunque cosa ci sia scritto
accanto. Misurato su un Alpine reale: `boa-proxy` era stato fermato da OpenRC
mentre `boa-web` continuava a cadere e ripartire, l'avvio dello stesso fatto
dal rollback ha perso la corsa per il lock del servizio, e il programma di
installazione è morto DENTRO `fRollBack`. Il rollback aveva funzionato - la
versione precedente era tornata e rispondeva - ma all'operatore è stato detto
«The boa-proxy service would not start», senza una parola sul fatto che un
aggiornamento era appena stato annullato. A quel punto il resoconto di quanto
è successo è l'unica cosa che un operatore ha.

La versione precedente viene rimossa da `fFinishUpdate`, e solo dopo che quella
nuova ha risposto.

Prima `fRollBack` girava in un solo punto: quando falliva quel `curl` finale.
Tra `fStopServices` e quel controllo ci sono una dozzina di passi che possono
morire - un file di certificato scomparso, una configurazione del proxy che
HAProxy non riesce ad analizzare, un'unità che non si installa - e ognuno di
essi lasciava i servizi fermi, il codice nuovo al suo posto e
`webapp.previous` su disco senza che nessuno lo rimettesse a posto. Il
messaggio nominava ciò che era fallito e non diceva niente della macchina
ferma. Così `fDoUpdate` imposta `vUpdateSwitched` appena prima di fermare i
servizi, e `fCleanup` - la trap di EXIT, che gira in qualunque modo finisca il
processo figlio - fa il rollback quando trova il flag impostato e il codice di
uscita diverso da zero. Le due uscite dallo scambio lo azzerano: `fRollBack`
stesso, così il percorso esplicito non fa il rollback due volte, e
`fFinishUpdate`, perché una volta che la nuova versione ha risposto non c'è
niente a cui tornare. Misurato su entrambe le macchine di prova con la chiave
privata nascosta: «Missing certificate files», «Putting the previous version
back», tutti i servizi su e la pagina di accesso che risponde 200 sul codice
precedente. Un test esegue i veri `fCleanup`, `fRollBack` e `fFinishUpdate` di
ciascun programma di installazione attraverso tre uscite: dopo lo scambio,
prima di esso e dopo la fine.

`--install` e `--reinstall` non hanno una versione precedente da conservare,
quindi non hanno né Scambio né rollback - ma la Verifica sì. Prima finivano in
`fWriteCredentialsFile`, e «Installation finished» è stato stampato su due
macchine reali il cui servizio web si riavviava ogni cinque secondi: nessuno
aveva mai chiesto niente all'applicazione. Ora chiedono la stessa pagina di
accesso e, quando non arriva, lo dicono e nominano il log, perché sulla
macchina non c'è niente a cui tornare.

`pip` stesso è bloccato a una versione. `--upgrade pip` senza versione
significava che due aggiornamenti dello stesso codice potevano risolversi in
modo diverso, che è proprio ciò che bloccare le versioni dei requisiti doveva
evitare. Quello che ancora non è bloccato sono le dipendenze TRANSITIVE -
così `pip freeze` viene registrato nell'ambiente e l'aggiornamento successivo
stampa che cosa è cambiato, che è l'unico modo in cui qualcuno se ne
accorgerebbe.

### Un'installazione che si è fermata a metà

`fIsInstalled` considerava installata una macchina nel momento in cui
esistevano `webapp/backend` e l'utente `boa` - il che avviene prima
dell'ambiente virtuale, dei certificati, del database e dell'amministratore.
Un'installazione morta a pip, su una rete caduta, riceveva poi «already
installed» da `--install` e una morte su qualunque cosa mancasse da
`--update`, e solo `--reinstall --yes` riusciva a superarla, senza che niente
lo dicesse all'operatore.

Ora un'installazione finita lascia `/opt/boa/installed`, scritto da
`fMarkInstalled` solo dopo che `fVerifyInstallation` ha ottenuto la sua
pagina: un'installazione che è al suo posto e non risponde non è finita, e un
aggiornamento che ha fatto il rollback non è la nuova versione. Senza il
marcatore, le cinque cose che un'installazione finita ha sempre - il codice,
l'utente, `venv/bin/gunicorn`, `db/boa.sqlite` e `certificates/privkey.pem` -
ne fanno le veci, così un'installazione di prima che il marcatore esistesse
conta ancora e riceve il suo marcatore al prossimo aggiornamento. Tutto il
resto di ciò che fa `--install` si può già fare due volte senza rischi:
l'utente viene creato solo se manca, l'ambiente viene costruito accanto a
quello vecchio, i certificati vengono conservati quando ci sono,
l'amministratore viene eliminato e riscritto con la nuova password. Così
un'installazione lasciata a metà si finisce eseguendo `--install` ancora una
volta, e `--update` dice esattamente questo quando ne trova una. Strada
facendo, `fGeneratePassword` si è spostato dopo `fInstallDependencies` nel
programma di installazione di Debian, dove era al contrario: `openssl` è
Priority: optional su Debian, e un'immagine minimale generava la password
prima che fosse installato il pacchetto che la genera.

### Tutto ciò che il programma di installazione esegue arriva al suo log

`fLog` scriveva le proprie righe in `install.log` e nient'altro. apt, pip, la
validazione di HAProxy e ogni altro sottoprocesso scrivevano sul terminale,
quindi un'installazione fallita lasciava un log che conteneva «Installing the
dependencies.» e non una parola dell'errore di apt che spiegava il perché -
che è esattamente il dettaglio per cui qualcuno apre quel file.

`fStartCapturingOutput` redirige lo stdout e lo stderr di questa stessa shell
in una FIFO che `tee` copia nel log e sul terminale. Una FIFO invece di
`exec > >(tee ...)`, che è solo di bash, e Alpine parte senza bash, e invece di
una pipeline attorno a `fMain`, che la metterebbe in una subshell e
disferebbe la disposizione `fMain & wait` che tiene vivo errexit.

Due conseguenze, entrambe da gestire:

`fLog` faceva echo della riga E la aggiungeva lui stesso al log. Una volta che
lo stdout è un tee che aggiunge a quello stesso file, la seconda scrittura è un
duplicato: un'installazione di 90 righe produceva un log di 185 righe con ogni
riga ripetuta due volte. Ora `fLog` scrive nel file solo mentre la cattura non
è attiva.

`tee` tiene aperto il log per INODE. Un `--reinstall` elimina l'intero albero,
log compreso, e rimette una copia nuova - quindi da quel momento `tee` sta
aggiungendo a un inode senza nome e, con `fLog` che non scrive più nel file,
quella sarebbe l'intera seconda metà della reinstallazione, password generata
compresa. `fRestartCapturingOutput` punta la cattura al file che ora esiste.

### Due programmi di installazione, un'applicazione

`deploy/install-update-reinstall-debian.sh` scrive unità systemd, e **ha
bisogno che systemd sia il PID 1 della macchina in esecuzione**: un Debian
avviato con qualsiasi altra cosa non è un obiettivo, e il programma di
installazione lo rifiuta invece di installare su una macchina che non
avvierebbe niente.
`deploy/install-update-reinstall-alpine.sh` scrive servizi OpenRC in
`/etc/init.d/`, a partire da `deploy/openrc/`, e non ha bisogno di niente in
anticipo: installa OpenRC da sé quando la macchina non ce l'ha. Entrambi installano gli stessi dieci processi,
lo stesso albero sotto `/opt/boa`, lo stesso modello di utenti; un test
confronta i due passo per passo e fallisce quando a uno cresce un passo che
l'altro non ha.

Non sono scritti nello stesso linguaggio, ed è voluto. Quello di Debian è bash,
come tutto il resto qui. Quello di Alpine è shell POSIX, con `#!/bin/sh`,
perché un Alpine appena installato non ha bash: con `#!/bin/bash` il kernel
cercherebbe un interprete che non c'è, e

    curl -fsSL <raw-url> | bash -s -- --install

fallirebbe prima di leggere una riga, proprio sulla macchina che più ha bisogno
dell'installazione in una riga. Essendo POSIX gira allo stesso modo sotto
BusyBox ash, dash e bash, quindi lo stesso file funziona passato in pipe a `sh`
su un Alpine spoglio e a `bash` su uno che ce l'ha già. Installa comunque
bash - a ogni agente viene data una shell bash - solo che non ne ha più bisogno
per partire. Quello che costa sono gli array, `[[ ]]`, `${var//x/y}` e `<(...)`;
`local` resta, perché ce l'hanno tutte e tre le shell, e `pipefail` viene
chiesto in una subshell prima di essere impostato, perché dash non ce l'ha. Un
test rifiuta ognuno di quei costrutti, dato che una funzionalità della shell
che non c'è fallisce al momento dell'installazione sulla macchina di qualcun
altro.

Che cosa serve ad Alpine che a Debian non serve, e perché nessuna di queste
cose è facoltativa:

| | Perché |
|---|---|
| `shadow` | Il demone privilegiato chiama `useradd --home-dir --create-home --shell`. L'`adduser` di BusyBox non ha nessuna di quelle opzioni, e un agente che non si può creare è l'intera applicazione che non funziona |
| `bash` | La shell che viene data a ogni agente, e quella attraverso cui passa `bash.run`. Alpine arriva senza, ed è anche il motivo per cui il programma di installazione di Alpine è l'unico file di questo progetto scritto in shell POSIX invece che in bash: `#!/bin/bash` renderebbe impossibile `curl ... \| sh` proprio sulla macchina che ne ha più bisogno |
| `dcron` | Qualcosa deve leggere i crontab che scrive il demone. È anche il motivo del `-d` più sotto |
| `gcc`, `musl-dev`, `libffi-dev`, `python3-dev` | Diversi requisiti non pubblicano nessuna wheel per musl e vengono compilati durante l'installazione |
| `libcap` | `setcap cap_net_bind_service` sul binario di haproxy, in modalità `direct`. systemd lo concedeva per servizio con `AmbientCapabilities`; OpenRC non ha un equivalente |

Tre cose che il port ha dovuto cambiare nel codice, ognuna scoperta
installando:

- **`crontab -u <agent>` invece di scendere all'agente.** Il `crontab` di
  Debian è setgid e qualsiasi utente può eseguirlo; il dcron di Alpine lo
  distribuisce `4750 root:wheel`, quindi un agente che lo esegue riceve
  `Permission denied`. I modi per mantenere la vecchia forma erano mettere ogni
  agente in `wheel` - il gruppo che sulla maggior parte dei sistemi significa
  sudo - o allentare un binario setuid del sistema. Il demone è root e può
  invece nominare l'utente.
- **`-r` o `-d` quando se ne elimina uno.** Vixie cron elimina un crontab con
  `-r`; dcron con `-d`, e a `-r` risponde con un messaggio d'uso e il codice di
  uscita 2. Provare solo `-r` lasciava dietro di sé il crontab di un agente
  eliminato, che puntava ancora al runner di un utente che non esisteva più. Si
  provano entrambi, perché a deciderlo è il binario installato, non il nome
  della distribuzione.
- **`executable=` in `browser.conf`.** Playwright non pubblica nessuna build
  per musl, quindi su Alpine il pacchetto viene escluso del tutto dai requisiti
  e non c'è nessun browser. La riga viene letta da
  `browser.fReadConfiguredExecutable` ed è dove verrebbe nominato un Chromium
  di sistema, il giorno in cui ci sarà un Playwright capace di pilotarne uno.

Un'altra, scoperta guardando `/proc/<pid>/fd/2` sulla macchina Alpine di
prova: `supervise-daemon` manda lo stdout e lo stderr di un processo a
`/dev/null` a meno che non gli si dica altrimenti, e su Alpine nient'altro li
raccoglie - le unità su Debian hanno journald per questo. Nessun servizio
scriveva niente da nessuna parte. Ora ogni script OpenRC nomina
`output_log` ed `error_log`, un file per servizio sotto `/opt/boa/logs/`,
creato come `boa` in `start_pre` così che logrotate possa ruotarlo come `boa`
chiunque ci scriva. `fInstallLogRotation`, in entrambi i programmi di
installazione, scrive `/etc/logrotate.d/boa` per quei file e per i due di
gunicorn: settimanale, otto conservati, `copytruncate` perché entrambi gli
scrittori tengono il loro file aperto, e mai `install.log`, che è di root e
contiene la password. L'altra metà della stessa scoperta: la scheda Sistema
operativo chiedeva a OpenRC di `crond`, il cron di BusyBox, mentre il
programma di installazione esegue `dcron` al suo posto, quindi un Alpine sano
riportava cron fermo. `fPickOpenRcCronService` chiede del primo dei due che ha
uno script di servizio.

E due che il programma di installazione aggira invece di correggere, perché
appartengono al pacchetto haproxy di Alpine: non distribuisce nessun
`/etc/haproxy/errors/`, né `/run/haproxy` per il socket di amministrazione.
Entrambe le righe vengono tolte dalla configurazione quando il loro file o la
loro directory non c'è, il che è corretto anche su una macchina dove un
amministratore li ha creati. Creare `/run/haproxy` è stato il primo tentativo,
con uno script in `/etc/local.d/` per ricrearlo a ogni avvio: `local` gira
alla FINE dell'avvio, quindi haproxy era già fallito nell'avviarsi quando la
directory compariva.

Un'altra appartiene a OpenRC stesso: mette in cache l'albero delle dipendenze
dei servizi e decide se ricostruirlo confrontando le marche temporali con
`/etc/init.d`. In una reinstallazione gli script dei servizi vengono
sovrascritti nello stesso secondo della cache, quindi tiene quella vecchia e
i servizi ne restano fuori - partono durante l'installazione, perché
`rc-service start` non ha bisogno dell'albero, e poi non tornano dopo un
riavvio, perché `openrc default` sì. `fInstallServices` finisce con un
`rc-update -u` incondizionato.

### Che cosa pretende dalla macchina ciascun programma di installazione, e che cosa installa da sé

Il programma di installazione di Debian si rifiuta di girare dove systemd non
è il PID 1 (`fRequireSystemd`, chiamato prima che venga installato qualsiasi
cosa). Tutto ciò che configura viene avviato e tenuto in vita da systemd - le
dieci unità, l'HAProxy della macchina, cron - quindi su una macchina così prima
l'installazione finiva, riportava successo e non serviva niente: `systemctl` è
installato, risponde «System has not been booted with systemd as init system
(PID 1). Can't operate.», e nessuno leggeva quel codice di uscita. Ora quello
che stampa è come rimediare: installare `systemd systemd-sysv dbus`, creare di
nuovo il contenitore con `/sbin/init` come comando, eseguire di nuovo il
programma di installazione. Dice «creare di nuovo» e non «riavviare» perché un
contenitore in esecuzione non può cambiare il suo PID 1.

Il programma di installazione di Alpine prende la decisione opposta riguardo a
OpenRC, perché lì il pezzo mancante è uno che può fornire lui: `openrc` viene
installato insieme agli altri pacchetti - un'immagine di contenitore arriva
senza, un Alpine installato con `setup-alpine` ce l'ha - e
`fEnsureOpenRcUsable` crea poi `/run/openrc/softlevel`, che è il file che
OpenRC stesso nomina quando si rifiuta di toccare un servizio su un sistema
che non ha avviato lui. Dopo questo i dieci servizi partono in un
contenitore. Il log dice che non torneranno da soli, perché `/run` è un tmpfs
e il PID 1 non è OpenRC.

Le due cose non sono incoerenti: systemd non si può far funzionare come
nient'altro che il PID 1, e OpenRC sì.

### `if ! fMain` disattiva `set -e` per l'intera installazione

Entrambi i programmi di installazione finiscono con fMain avviato come
processo figlio:

    fMain "$@" &
    vMainPid=$!
    if ! wait "${vMainPid}"; then ...

e non con `if ! fMain "$@"`, che è ciò che sembra e ciò che avevano prima. Un
comando nella condizione di un `if` gira con errexit sospeso, e la sospensione
viene ereditata da ogni funzione che chiama e da ogni funzione che quelle
chiamano - cioè l'intera installazione. Misurato su una macchina senza
systemd: otto comandi sono falliti di fila, ognuno ha stampato il suo errore,
lo script è andato avanti oltre tutti loro ed è finito con «Installation
finished». Un processo figlio riottiene errexit, perché la sospensione non
sopravvive a un fork. bash, dash e BusyBox ash si comportano tutti così, in
entrambe le metà di quella frase, e né un `set -e` dentro la funzione né una
subshell lo recuperano.

Due conseguenze dell'eseguire fMain in un figlio: `trap fCleanup EXIT` viene
installata anche dentro fMain, perché una subshell non eredita la trap di EXIT
del padre e l'albero scaricato sotto `/tmp` resterebbe lì a ogni esecuzione;
e il padre azzera la propria trap prima di uscire, così la riga «Exited with
code» non viene stampata due volte.

`fHasTty` è una correzione della stessa famiglia: apre `/dev/tty` e lo chiude
di nuovo, invece di verificare `[ -r /dev/tty ]`. Il nodo del dispositivo è
leggibile per modo su ogni sistema, quindi quel test passava sotto `ssh host
./installer` senza pty e il `read` che seguiva moriva con ENXIO - un processo
senza terminale di controllo non può proprio aprirlo.

### L'haproxy.cfg di serie non è il lavoro di qualcuno

`fInstallMachineProxy` sostituisce `/etc/haproxy/haproxy.cfg` quando è in
modalità `proxied`, e non tocca un file che non ha scritto lui senza chiedere
prima - il proxy della macchina potrebbe servire altri siti. Il problema è che
il file che trova su una macchina appena installata ce l'ha messo il pacchetto
haproxy, che **questo programma di installazione ha installato lui stesso** un
minuto prima in `fInstallDependencies`.

Trattare quell'esempio come il lavoro di qualcuno è ciò che fermava di colpo
ogni semplice `--install`: nessun `--yes`, nessun terminale su cui rispondere,
e l'esecuzione finiva con «Destructive operation with no terminal to confirm
on» dopo aver già costruito l'albero, il virtualenv e i certificati. Misurato
su tutte e quattro le macchine di prova, Debian e Alpine allo stesso modo,
eseguendo esattamente la riga che dà il README.

`fMachineProxyIsPristine` chiede al gestore di pacchetti invece di tirare a
indovinare:

- Debian: l'md5 che dpkg ha registrato per quel conffile (`dpkg-query -W -f
  '${Conffiles}'`) contro l'md5 del file stesso.
- Alpine: l'hash che apk ha registrato per quel file, letto da
  `/lib/apk/db/installed` (la riga `Z:` sotto `R:haproxy.cfg`), contro
  `openssl dgst` del file. `Q1` è sha1 in base64, `Q2` è sha256.

`apk audit --system` sembra la risposta di Alpine e non lo è: misurato su
Alpine 3.24, non riporta **niente** per un `/etc/haproxy/haproxy.cfg`
modificato. La prima versione di questo controllo gli ha creduto, e avrebbe
sostituito il proxy di qualcuno senza chiedere - l'unica cosa che la conferma
esiste per impedire. Provato da allora con il file del pacchetto, con una riga
aggiunta e con il file che scrive questo programma di installazione.

Intatto significa che viene sostituito con una riga nel log e nessuna domanda.
Modificato significa il comportamento di prima: lasciato stare in un
`--update`, confermato e salvato come copia in `.before-boa.<timestamp>` in
un'installazione o in una reinstallazione.

### Un solo file per il log e la password

Il programma di installazione scrive `/opt/boa/logs/install.log` e
nient'altro: ciò che ha fatto e, alla fine, le credenziali che ha generato.
Prima scriveva due file in /root - `app-web-install.log` e
`app-web-credentials.txt` - e due file in due posti sono due cose da trovare.
`fMigrateInstallFiles` copia ciò che c'è in quelli vecchi in quello nuovo prima
di rimuoverli, perché la password lì dentro potrebbe essere l'unica copia che
qualcuno ha.

Tre dettagli tengono insieme il tutto:

- `fLog` crea la directory quando non c'è. Il log vive dentro l'albero che il
  programma di installazione sta costruendo, quindi in una prima installazione
  non esiste quando viene scritta la prima riga, e un `--reinstall` lo elimina
  a metà strada.
- `fRemoveInstallation` copia il log da parte prima di `rm -rf /opt/boa` e lo
  rimette dopo, così una reinstallazione non si porta via il proprio registro.
- Il file è `root:root 0600` dentro una directory di proprietà di `boa` con 0750.
  `boa` può fare unlink - è ciò che significa essere proprietario della
  directory - e non può leggere la password che contiene; gli agenti non sono
  nel gruppo `boa` e non possono nemmeno entrare nella directory.

La pagina di accesso nomina quel percorso, in `frontend/templates/login.html`,
su una riga a sé e colorato con `--colour-path`. Non è nei quindici file di
traduzione: la frase sopra è tradotta, il percorso è lo stesso ovunque, e un
percorso spezzato in mezzo a una frase è un percorso che qualcuno ribatte
sbagliato.

### Logo circolare dell'applicazione

`frontend/static/img/boa.svg` è un marchio circolare blu con tre agenti
robotici a mezzo busto in abito nero, camicia bianca e cravatta scura. Le loro
teste hanno pannelli metallici chiari, giunture meccaniche e visiere scure con
occhi blu. Lo stile è leggermente illustrato, con texture morbide dei tessuti e
nessun fazzoletto nel taschino dell'agente centrale. Le teste si collegano a
colli robotici visibili; l'agente centrale, più grande, sta davanti ai due
agenti laterali più piccoli. L'illustrazione ombreggiata è un WebP di 512px
incorporato in un SVG, con un ritaglio circolare e trasparenza fuori dal
cerchio. Le figure restano opache e mantengono lo stesso aspetto in tutti i
temi. Si tratta di un'illustrazione raster dentro un contenitore SVG, non di
tracciati vettoriali.
`favicon.svg` contiene la stessa illustrazione. Tieni sincronizzati entrambi i
file SVG. Gli URL dell'accesso, della barra laterale e della favicon usano
`v=robot-agents` per aggiornare le copie in cache del marchio precedente. Le
dimensioni mostrate restano 30px nella pagina di accesso e 24px nella barra
laterale.

### L'interfaccia parla en-US finché qualcuno non dice altrimenti

`fGetLanguage` legge la scelta da `localStorage` e, se non ne trova, restituisce
`en-US`. Prima negoziava con `navigator.languages`, il che significava che una
nuova installazione parlava la lingua del primo browser che la apriva - la
lingua di una macchina, non una decisione. La scelta è a un controllo di
distanza, nell'angolo del riquadro di accesso e nelle Impostazioni, e viene
ricordata per browser.

Nello stesso file vivevano due bug, ed entrambi si manifestavano come «il
modulo di accesso non cambia lingua finché non la cambi due volte»:

- `fApplyTranslations` scriveva una stringa solo quando il file caricato aveva
  quella chiave, e `textContent` era già stato sovrascritto dalla lingua
  precedente. Così passare a en-US - che non ha file, `dTranslations` è `{}` -
  non cambiava assolutamente niente, e passare a una lingua a cui mancava una
  chiave lasciava quella chiave nella lingua di prima. Ora la stringa originale
  di ogni elemento tradotto viene conservata in una `WeakMap` la prima volta
  che viene tradotta, e una chiave senza traduzione la ripristina.
- `fSetLanguage` salvava la scelta e poi chiamava `fLoadTranslations()` senza
  argomenti, che rileggeva la scelta dalla memoria. In una finestra privata la
  memoria lancia un'eccezione, la lettura restituisce la lingua precedente, e
  la pagina ricarica ciò che stava già mostrando. Ora passa la lingua che ha
  ricevuto.

`fLoadTranslations` porta un numero di sequenza, così che due cambi in rapida
successione non possano arrivare fuori ordine e lasciare la pagina in una
lingua che nessuno ha chiesto. Tre cose al riguardo erano sbagliate, e ognuna
mostrava all'utente una lingua che non aveva scelto:

- L'attributo `lang` veniva impostato all'INIZIO, prima che il file fosse
  stato scaricato. Un 404 o un errore di parsing lasciavano allora sullo
  schermo le stringhe della lingua precedente sotto il nome di quella nuova:
  `lang=fr-FR` con testo spagnolo. Non viene pubblicato niente finché il
  dizionario non è in mano, e `fPublish` imposta le due cose insieme perché il
  guasto è proprio che vengano impostate separatamente.
- La sequenza veniva verificata PRIMA di `await response.json()`. Un CORPO
  lento di una richiesta precedente arrivava dopo che una successiva era
  finita. Ora viene verificata dopo ogni await, perché la sequenza può
  spostarsi in corrispondenza di ciascuno.
- Un fallimento non diceva niente e lasciava la pagina in uno stato
  sconosciuto. Ora ricade su en-US e lo segnala tramite `fOnLoadFailed`.

### en-US.json è la fonte, e il markup è il ripiego

Il caricatore cortocircuitava `en-US` a un dizionario vuoto, sulla base del
fatto che il markup porta già il testo en-US. È vero, e rendeva `en-US.json`
cinquecento chiavi di peso morto: distribuito, elencato come catalogo,
verificato dai test per la parità con gli altri tredici, e letto da niente.
Correggerci un refuso non cambiava niente sullo schermo, e l'unico modo per
scoprirlo era provare.

Ora viene scaricato come qualsiasi altra lingua. Il testo del markup resta il
ripiego che è sempre stato descritto come tale: una chiave che il catalogo non
ha, o un catalogo che non si carica, lascia comunque una pagina leggibile
invece di una pagina di spazi vuoti. Quello che è cambiato è quale dei due è la
fonte.

### Cinquecento chiavi non sono un'interfaccia tradotta

Quattro tipi di stringa visibile non avevano nessuna chiave, quindi restavano
in inglese in tutte e quattordici le lingue:

| Cosa | Come viene tradotto ora |
|---|---|
| Il titolo della scheda del browser | `data-i18n` su `<title>`, una chiave per pagina |
| I fallimenti dell'API stessa | Viaggiano un `code` e i suoi `params`; il browser scrive la frase in `fDescribeApiError`. `error` resta per ciò che viene da fuori - le parole di un provider, il rifiuto di un server di posta - per cui non si dovrebbe inventare una traduzione |
| Descrizioni dei template | Non nei cataloghi: l'`agent.json` di ogni template porta la sua descrizione nelle quindici lingue, e il server sceglie quella che l'interfaccia chiede (`agent_package.fPickDescription`) |
| Schema e descrizione del tema | `theme.scheme.<scheme>` e `theme.desc.<id>`, stesso accordo. Il NOME non viene tradotto: un tema è la tavolozza di qualcuno con un nome, e tradurre «Nord» non aiuterebbe nessuno a trovarlo |

Un template o un tema che qualcuno scrive per la propria installazione
mantiene le proprie parole invece di sparire.

Il menu a tendina della lingua nella pagina di accesso elenca codici - `es-ES`,
`en-US` - e non nomi di lingue. Quindici nomi nelle rispettive lingue
rendevano il controllo largo quanto il riquadro; il codice occupa 80px, ed è
ciò che chi cerca la propria lingua individua più in fretta in un elenco di
codici. I nomi completi restano nella pagina delle impostazioni, che ha lo
spazio.

### Da destra a sinistra

L'ebraico si scrive da destra a sinistra, e una pagina impaginata da sinistra a
destra con dentro dell'ebraico è una pagina che nessuno riesce a leggere. Quattro
decisioni fanno servire entrambe le direzioni da un solo foglio di stile:

**La direzione viaggia con la lingua.** `fPublish` in `i18n.js` imposta `dir`
su `<html>` nello stesso passo di `lang`, a partire da `lRightToLeftLanguages`,
così i due non possono mai discordare - il guasto che la funzione esiste per
prevenire per il solo `lang`. Le righe grid e flex seguono `dir` da sole, perciò
la barra laterale e tutto ciò che è disposto in riga si specchiano senza una
regola propria.

**Il foglio di stile dice inizio e fine, non sinistra e destra.** Ogni margin,
padding, border, `inset` e `text-align` che riguarda il flusso del testo è una
proprietà logica (`margin-inline-start`, `inset-inline-end`,
`text-align: start`). L'unico `left` fisico rimasto in `app.css` è l'anello
attorno all'avatar di un agente, che è geometria e non testo.

**Il contenuto mantiene la propria direzione.** Codice, percorsi e comandi
vanno da sinistra a destra in ogni lingua
(`code, pre { direction: ltr; unicode-bidi: isolate }`), così un percorso dentro
una frase ebraica non viene riordinato. Un messaggio di chat, e ogni paragrafo
di una risposta resa, prendono la direzione dalla propria prima lettera
(`unicode-bidi: plaintext`): una risposta in inglese su una pagina ebraica si
legge da sinistra a destra, una in ebraico su una pagina inglese da destra a
sinistra. Le caselle di testo in cui si scrive testo libero seguono la stessa regola, e una casella vuota segue la pagina, così il suo testo di suggerimento in ebraico si legge da destra a sinistra (`dir="auto"` disporrebbe una casella vuota da sinistra a destra, suggerimento compreso); il crontab e l'indirizzo email portano
`dir="ltr"`.

**Ciò che si legge da sinistra a destra è isolato dentro una frase.** L'algoritmo bidi assegna un carattere neutro a quale dei due lati tocca, così un percorso alla fine di una frase ebraica perdeva la barra e il punto a favore delle parole intorno: "/tmp/x/007/." veniva mostrato come ".tmp/x/007/ /". In una lingua da destra a sinistra `fPublish` fa passare il dizionario attraverso `fIsolateLeftToRightRuns`, che avvolge ogni `{placeholder}` e ogni sequenza che contiene una barra in U+2068 FIRST STRONG ISOLATE ... U+2069 POP DIRECTIONAL ISOLATE, così il valore che un chiamante inserisce in una frase finisce dentro l'isolato. Ciò che la macchina riporta sotto Impostazioni → Sistema operativo (`fLeftToRight` in `settings.js`), una rotta nella documentazione dell'API (`.endpoint-path`), la riga di crontab d'esempio e i conteggi su schede e colonne sono isolati da sinistra a destra allo stesso modo; senza questo una versione del kernel veniva mostrata come "deb13-amd64 · x86_64+6.12.111".

### Il branch da cui si scarica il codice

`cRepoBranch` è `main`, il vero branch del repository. Era `master`, che
funzionava solo perché GitHub reindirizza il vecchio nome dopo una
rinomina - un reindirizzamento che sparisce il giorno in cui esiste un vero
branch `master`, e che nessuno esegue per `--repo-url file:///...`, che è il
modo in cui vengono provati entrambi i programmi di installazione.

### Perché l'applicazione porta con sé il proprio HAProxy

L'HAProxy della macchina inoltra alla porta 11443 con `send-proxy-v2`, quindi
un'intestazione PROXY arriva **prima** dell'handshake TLS. Gunicorn lì non può
leggerla: la sua opzione `proxy_protocol` analizza quell'intestazione mentre
analizza l'HTTP, il che avviene dopo che il TLS è stato terminato, quindi i
byte dell'intestazione finiscono nell'handshake e lo rompono con
`WRONG_VERSION_NUMBER`. Questo è stato scoperto facendo il deploy, non
provando.

HAProxy accetta entrambe le cose su un solo bind - `accept-proxy ssl crt ...` -
quindi l'applicazione porta la propria istanza, che è anche l'unico componente
in ascolto su una porta. Gunicorn invece fa il bind su un socket Unix, il che
significa che non c'è nessuna via d'accesso all'applicazione che non passi dal
proxy, e il vero indirizzo del client sopravvive come `X-Forwarded-For` - senza
di esso, il limite di frequenza dell'accesso vedrebbe 127.0.0.1 per tutti e
smetterebbe di essere per indirizzo.

È HAProxy e non nginx perché il deploy dipende già da HAProxy: nessuna
tecnologia nuova per un problema che ne risolve già una esistente.

L'HAProxy della macchina non deve usare `option ssl-hello-chk` su questo
backend: il ClientHello di quel controllo è anteriore a TLS 1.2, quindi
fallisce contro un bind che lo richiede e marca il backend come giù per
sempre. Il sintomo è un 503 da un servizio che funziona perfettamente, il che
vale la pena sapere perché niente nei log dell'applicazione stessa dice che
qualcosa non va.

E il controllo deve bussare alla 11080, non alla 11443. Un controllo TCP
contro il bind TLS si connette e riattacca senza handshake, e questo HAProxy
registrava ognuno come «SSL handshake failure» - misurato sulla macchina Debian
di prova, 64.075 righe in due giorni, una ogni due secondi, che seppellivano
qualsiasi cosa reale nel journal. `check-ssl verify none` è stato il primo
tentativo e ha scambiato una riga con un'altra: la chiusura brusca del
controllo arrivava mentre l'handshake era ancora in via di completamento, e
ogni controllo registrava o quello o `ECONNRESET`. Contro la 11080 la stessa
connessione-e-chiusura è una sessione nulla che `option dontlognull` tiene
fuori dal log, entrambe le porte appartengono a un solo processo, e il journal
è diventato silenzioso: zero righe in trenta secondi con il sito che
rispondeva 200 dall'esterno.

Quindi il backend sull'HAProxy della macchina è, per intero:

```
backend https-out
  mode tcp
  server srv-https-out 127.0.0.1:11443 check port 11080 send-proxy
```

`send-proxy` è ciò che porta l'indirizzo del client. `check-send-proxy` è
lasciato fuori di proposito: la 11080 non accetta il PROXY protocol. La
versione di questo destinata all'operatore è in MANUAL.it-IT.md, sotto «Come
deve essere l'HAProxy della macchina».

Non fissa nessun `maxconn`, e non è una svista. `maxconn 2048` chiede al
kernel 4131 descrittori di file e HAProxy esce invece di partire senza:
*Cannot raise FD limit to 4131, current limit is 1024 and hard limit is
4096*. Segnalato da un LXC Alpine che gira sotto OpenWrt su un BPI-R3, il cui
limite rigido è 4096: `boa-proxy` è stato riavviato settanta volte, niente è
mai stato in ascolto sulla 11443, e una prima installazione è finita con «The
application did not answer on port 11443 (last code: 000)». Entrambe le
macchine di prova sono LXC di Proxmox con un limite rigido di 524288, ed è per
questo che nessuna delle due l'ha mai mostrato, e `haproxy -c` ha accettato il
file su ognuna di esse - la configurazione non è mai stata non valida, il
processo moriva all'avvio. Senza `maxconn`, HAProxy si dimensiona in base ai
descrittori che può davvero avere, che è ciò che chiede il suo stesso
messaggio, e `fd-hard-limit 4000` limita quanto ne prende dove il limite è
enorme. Misurato con un solo binario a tre limiti rigidi: 4096 dà maxconn
1987, 1024 dà 499, 524288 dà 1987. Un test avvia il vero haproxy sul file
distribuito sotto un limite rigido di 4096 e richiede che resti su, e lo avvia
di nuovo con il vecchio `maxconn 2048` e richiede che muoia - un test che si
limitava a leggere il file è il modo in cui la cosa era sfuggita in primo
luogo.

Tre cose hanno davvero bisogno di root: creare un utente di sistema,
installare il crontab di un altro utente e avviare un processo come un altro
utente. Tutto il resto no. Così root vive in un piccolo demone con un
**vocabolario chiuso di verbi** su un socket Unix, e di proposito non c'è
nessun verbo che significhi «esegui questo comando». Un attaccante che
raggiunge quel socket può creare un agente non privilegiato; non può eseguire
codice come root.

Il socket è `0660 root:boa`, e `SO_PEERCRED` viene verificato su ogni
connessione così che vengano serviti solo root e `boa`, qualunque cosa dica il
modo del file dopo qualche aggiornamento futuro.

### Una modifica deve venire dalle pagine di questo stesso sito

Il cookie di sessione è `SameSite=Lax`, il che impedisce a una richiesta da un
altro sito di portarlo con sé. Non tiene fuori però un'altra ORIGINE sullo
stesso sito: un agente con `bash.run` può servire una pagina proprio su questo
host, su una porta tutta sua, e un link a essa in una risposta della chat è a
un clic di distanza. Un modulo lì che fa POST a `/api/admin/agents/000/run` è
una richiesta dello stesso sito, il cookie viaggia, e l'esecuzione parte;
essendo un semplice POST senza corpo, nemmeno un preflight le sbarra la
strada. Così `fRefuseChangesFromElsewhere`, un `before_request` sul blueprint
dell'API, risponde 403 a qualsiasi POST, PUT, PATCH o DELETE che non sia
venuto dalle pagine di questo stesso sito: un'intestazione `Origin` deve
nominare esattamente questo host e questa porta - `localhost` e
`localhost:8080` sono due origini, e la seconda è proprio la pagina che un
agente potrebbe servire - e un'intestazione `Sec-Fetch-Site` deve dire
`same-origin`. Una richiesta senza nessuna delle due non è di un browser, è di
uno script o dei test, e viene lasciata al giudizio dell'accesso, come prima.
Un GET non viene filtrato: non cambia niente, e una pagina di altrove non può
leggere la risposta, perché non ci sono intestazioni CORS che glielo
permettano.

### L'API degli agenti, e perché esiste

Due cose appartengono a `boa` e non devono essere leggibili dagli agenti: il
database del kanban (un agente che potesse scriverci direttamente potrebbe
riscrivere la cronologia di un altro agente) e le credenziali dei canali (un
token di bot non è un messaggio — è un'autorità permanente di inviare).

Così gli agenti raggiungono entrambe le cose tramite `boa-agent-api`, su un
secondo socket Unix che ogni agente può aprire. L'autorizzazione consiste in
due controlli indipendenti:

1. Il token presentato corrisponde allo SHA-256 memorizzato del token di
   qualche agente.
2. `SO_PEERCRED` dice che il processo chiamante appartiene all'utente di
   *quello stesso* agente.

Ognuno dei due da solo sarebbe più debole: un token trapelato è inutile
dall'account sbagliato, ed essere l'account giusto è inutile senza il token.

È un socket Unix e non HTTPS perché non c'è niente da guadagnare dal TLS tra
due processi sulla stessa macchina, e un certificato autofirmato
significherebbe che ogni agente gira con la verifica disattivata — il che è
peggio di nessun TLS, perché sembra sicurezza.

### Dove vive lo stato, e perché è diviso

| Stato | Dove | Perché lì |
|---|---|---|
| Configurazione dell'agente | `agents/xxx/info.json` | L'agente deve leggerla come se stesso |
| Cronologia dell'agente | `agents/xxx/runs.jsonl` | L'unico posto dove un agente può scrivere |
| Procedure condivise | `skills/<Name>/SKILL.md` (root, 0755) | Lette da ogni agente a cui sono date, scritte da nessuno |
| Indice degli agenti, accesso, impostazioni | `db/boa.sqlite` (0700 `boa`) | Serve al processo web |
| La bacheca | `kanban/kanban.sqlite` (0700 `boa`) | Molti scrittori concorrenti |

Di proposito **non ci sono tabelle `runs` né `usage`**. Un processo agente non
può aprire il database di proprietà di `boa`, e concedergli l'accesso in
scrittura permetterebbe a qualsiasi agente di riscrivere la cronologia di
qualsiasi altro. Ogni agente aggiunge invece righe al proprio giornale, e
l'applicazione web li legge tramite `boa-exec`. Il vantaggio collaterale è che
un agente registra comunque ciò che ha fatto quando l'applicazione web è giù.

La bacheca è SQLite e non una directory di file JSON perché diversi agenti che
si svegliano nello stesso minuto di cron sono il caso normale, e solo una
transazione impedisce a due aggiunte simultanee di sovrascriversi a vicenda.

### Che cosa contiene un backup

`--backup` scrive un archivio di tutto ciò che è l'installazione e non è il
codice, e `--restore` ne mette uno al posto di ciò che ha una macchina;
entrambi sono in entrambi i programmi di installazione, funzione per funzione.
L'elenco è la tabella qui sopra trasformata in una riga di `tar`: i due
database, le chiavi e i canali, i certificati, ogni agente con la sua home e i
suoi file protetti, le competenze e gli strumenti. Attorno a esso, tre cose che
un `tar` di `/opt/boa` sbaglierebbe:

- **I database passano dall'API di backup di SQLite**, `fCopySqliteDatabase`,
  e non da `cp`. Entrambi girano in modalità WAL, quindi una copia del file
  `.sqlite` perde ciò che è ancora nel file `-wal`, e una copia presa a metà
  di una scrittura può essere lacerata. Il `python3` del venv ha il modulo; il
  comando `sqlite3` non c'è in nessuna delle due distribuzioni. La stessa
  ragione vale al contrario nel ripristino: i vecchi file `-wal` e `-shm`
  vengono rimossi prima che il file ripristinato venga letto, altrimenti SQLite
  gli applicherebbe il vecchio log.
- **Gli utenti degli agenti viaggiano per nome.** `agents.txt` registra
  l'utente, l'uid e il gid di ogni agente, e `fRestoreAgentUsers` crea quelli
  mancanti sempre con lo stesso nome e con gli stessi id quando sono liberi.
  La proprietà nell'archivio viene mappata per nome all'estrazione, così un
  `boa` o un `agent-001` con un altro uid sulla nuova macchina resta
  proprietario dei suoi file. I crontab vivono nello spool di cron, non sotto
  `/opt/boa`, quindi vengono letti con `crontab -l` e rimessi a posto con
  `crontab -u`.
- **Tre file vengono lasciati fuori di proposito**: `config/ports.conf`,
  `config/browser.conf` e l'`haproxy.cfg` generato a partire da essi
  descrivono QUESTA macchina, e un ripristino non deve importare le scelte di
  un'altra macchina. Il log di installazione viaggia come
  `install.log.backup`, con un altro nome così che un ripristino non scriva mai
  sopra il log che si sta scrivendo in quel momento; le sue righe di
  credenziali vengono aggiunte al log attuale, perché l'accesso dopo un
  ripristino è quello del backup.

Il ripristino è l'unica azione che sostituisce dati e non si può annullare,
quindi chiede conferma come fa una reinstallazione. Entrambe le funzioni
vengono eseguite dai test su un albero reale, sotto bash e sotto dash:
dell'archivio si verifica ciò che contiene e ciò che lascia fuori, l'albero
viene danneggiato in tutti i modi che un ripristino deve annullare, e il
ripristino viene verificato file per file.

### Una competenza è indicizzata nel prompt e recuperata su richiesta

La memoria di un agente viene caricata per intero in ogni prompt di sistema, ed
è giusto per una memoria: il suo limite di caratteri è configurabile per agente
(8.000 per impostazione predefinita, 1.000–1.000.000 consentiti) ed è l'unica
cosa che l'agente non può ricostruire.

Le competenze non sono così. Una procedura è una o due pagine, a un agente se
ne possono dare diverse, e la maggior parte delle esecuzioni non ne ha bisogno
di nessuna - il controllo del disco non ha bisogno della procedura dei
certificati. Caricarle come si carica la memoria vorrebbe dire pagarle tutte a
ogni chiamata di ogni esecuzione, e i tetti in `info.json` si misurano in
token.

Così il prompt porta un indice - una riga per competenza, il suo nome e la sua
descrizione - e il corpo viene recuperato con `skill.read`, una volta, da un
agente che ha deciso di averne bisogno. Cinque competenze costano circa 200
token per esecuzione invece di 10000, e quella che viene letta si paga una
volta invece che a ogni chiamata.

La descrizione nell'intestazione è quindi la parte portante: è ciò su cui
l'agente decide, ed è ciò che ogni esecuzione paga, che la competenza venga
letta o no.

### Le competenze appartengono a root, come gli strumenti

Uno strumento è di proprietà di root perché l'applicazione lo importa come
codice. Una competenza non viene eseguita da niente, ma viene anteposta al
ragionamento di un agente che si sveglia alle quattro del mattino senza
nessuno che lo guardi, il che la rende esattamente sensibile quanto
`system-prompt.md` - e quel file vive già in una directory che l'agente può
leggere e non può scrivere.

Così nell'interfaccia web non c'è nessun editor di competenze, né un verbo
privilegiato per scriverne una. Le competenze si scrivono sul server via SSH.
L'interfaccia decide quale agente riceve quale, che è la stessa cosa che fa
per gli strumenti.

L'altra metà di quella decisione è dove vivono: `/opt/boa/skills/`, fuori da
`webapp/`, perché `fDeploySourceCode` fa `rm -rf` su `webapp` e una procedura
che qualcuno ha scritto su questo server non è qualcosa che un aggiornamento
abbia il diritto di eliminare. Stesso ragionamento, stesso posto nell'albero,
di `/opt/boa/tools/`.

L'applicazione non ne distribuisce nessuna. Non c'è `backend/skills/` e i
programmi di installazione non copiano niente in quella directory: la creano
vuota, di proprietà di root e 0755. Una competenza è una procedura per UNA
installazione - questi host, questo backup, questo certificato - quindi una
generica sarebbe una procedura che nessuno segue, e che occupa una riga di ogni
prompt di ogni esecuzione per dirlo. Che la directory sia vuota in
un'installazione nuova è la funzionalità che funziona, non un pezzo che manca.


### `deploy/` non viene distribuito

`/opt/boa/webapp/` contiene `backend/` e `frontend/` e nient'altro. La
directory `deploy/` - le unità, le due configurazioni di HAProxy, i template
degli agenti, i cataloghi dei provider, `requirements.txt` e lo stesso
programma di installazione - è materiale proprio del programma di
installazione, e viene letta dall'albero che il programma di installazione ha
appena scaricato in `/tmp`, che viene buttato via quando esce.

Non è solo ordine. Leggere le unità da una copia sotto `/opt/boa` significava
installare le unità di qualunque versione si trovasse su disco; leggerle
dall'albero scaricato installa le unità della versione che si sta distribuendo,
che è l'unica coppia su cui si possa ragionare. Ognuna di quelle letture chiama
prima `fRequireSourceCode`, così un passo che dovesse mai girare prima del
download fallisce con una frase invece di copiare da `/deploy/...`.

È anche il motivo per cui `gunicorn.conf.py` sta in `backend/web/` invece che
in `deploy/`: gunicorn lo legge a ogni avvio, quindi deve essere un file che
sta davvero sul server, e la directory che sta sul server è quella che contiene
il codice che configura.

Ciò che viene distribuito è `root:root`, directory `00755` e file `0644`,
impostati da `fSetCodeModes` e da nient'altro. Niente sotto `webapp/` viene
eseguito per percorso - il demone esegue il runner come
`venv/bin/python3 .../runner.py`, e così fa il crontab che scrive per ogni
agente - quindi nessun file lì ha bisogno del bit di esecuzione. Lo aveva
comunque finché questa non è diventata un'unica funzione: `fDeploySourceCode`
impostava `0644` e `fCreateDirectoryTree`, che gira dopo di esso in un
aggiornamento, faceva poi `chmod -R 00755` sullo stesso albero.

### Telegram riceve HTML, e ripiega sulle parole

Un modello scrive markdown. Mostrato grezzo, è `**25G free**` con gli
asterischi in mezzo alla frase, che è ciò che arrivava su un telefono fino a
questo.

Telegram rende un piccolo sottoinsieme di HTML - quattordici tag, nessun
attributo degno di questo nome, e nessun titolo, elenco o tabella fra di essi.
Così `telegram_html` traduce ciò per cui esiste un tag e trova una forma
leggibile per ciò per cui non esiste: i titoli diventano grassetto su una riga
a sé, le voci di elenco ricevono un punto elenco, e una tabella diventa un
blocco `<pre>` con spaziatura, che è l'unico modo in cui le colonne restano
una sotto l'altra su un telefono.

Tre cose al riguardo sono portanti.

**L'escape viene per primo.** `&`, `<` e `>` sono markup per Telegram, quindi
un agente che riporta `grep <dev> && echo` produce un messaggio a cui Telegram
risponde con un 400 - cioè un messaggio che non arriva mai. Ogni pezzo di testo
passa per `fEscape` prima che qualcosa lo avvolga. Un href passa per
`fEscapeAttribute`, che fa l'escape anche delle virgolette doppie: un URL che
ne contenesse una chiuderebbe l'attributo e trasformerebbe il resto di sé in
attributi che nessuno ha scritto.

**Un messaggio rifiutato viene rimandato come testo semplice.** Qualunque cosa
il renderer abbia sbagliato, le parole valgono più della formattazione, quindi
un 400 viene riprovato senza `parse_mode` e la riga esce senza formattazione.
Il ripiego registra nel log ciò che ha detto Telegram, perché una
formattazione che si degrada in silenzio per sempre è una formattazione che
nessuno corregge.

**Una risposta che Telegram rifiuta viene scartata, e una che non riesce a
prendere viene conservata per un'ora.** `fSay` restituisce tre cose e non due:
inviato, senza risposta, e rifiutato - un 4xx diverso da 429,
`ChannelRejected`, che è Telegram che dice di no a questo messaggio e lo dirà
anche domani: il bot bloccato, la chat sparita, il token revocato.
`fDeliverAnswers` prima conservava la riga a ogni fallimento e riprovava al
passaggio successivo, e la riga sta su disco così che un riavvio non perda una
risposta, quindi un bot bloccato trasformava il listener in un ciclo che non
finiva mai: il polling in modalità rapida, una lettura della chat tramite il
demone root e fino a due richieste a Telegram a ogni passaggio, oltre ogni
riavvio. Una risposta rifiutata viene scartata subito con una riga che lo
dice, e anche una risposta che Telegram non ha preso entro l'ora che si dà a
un'esecuzione viene scartata, per la stessa ragione per cui l'altro ramo
rinuncia a un'esecuzione che non è mai finita. Nessuno dei due perde la
risposta: è nella conversazione dell'agente nell'interfaccia web, dove è stata
scritta per prima.

I pattern sono gli stessi che usa `frontend/static/js/markdown.js`. Due
renderer in disaccordo su che cosa conta come markdown vorrebbero dire una
stessa risposta che si legge diversamente nei due posti in cui viene mostrata,
e il senso di inviarle entrambe è che sono la stessa conversazione.


### Discord è interrogato a intervalli, e una risposta è di duemila caratteri

Discord è il secondo canale attraverso cui una persona può rispondere a un
agente, e la metà che riceve è `discord_listener` - `boa-channel-discord`, il settimo servizio.
Quattro cose lo separano da quello di Telegram.

**Interroga a intervalli, via REST.** `GET /channels/<id>/messages?after=<id>`,
ogni cinque secondi e ogni due mentre un agente sta rispondendo. Il Gateway è
l'alternativa ovvia e non è stato scelto: è un WebSocket che ha bisogno di
heartbeat, di un protocollo di ripresa e di una dipendenza che questo progetto
non ha, e richiede che il Message Content Intent sia attivato nel portale degli
sviluppatori - senza il quale ogni messaggio arriva con `content` vuoto e
niente dice perché. Il polling, inoltre, si connette verso l'esterno, il che
permette a tutto questo di girare su una LAN senza niente inoltrato,
esattamente come fa il long poll di Telegram. Quello che costa è una latenza
misurata in secondi, e dodici richieste al minuto contro un limite di
cinquanta al secondo.

**Duemila caratteri, non quattromila.** `channels.cMaxMessageLength` è 4096,
che è il tetto di Telegram, e Discord risponde 400 a un `content` più lungo
di 2000. Una risposta lunga non arrivava accorciata - non arrivava.
`discord_markdown` la taglia tra una riga e l'altra in al massimo quattro messaggi, e un blocco
delimitato dentro cui cade un taglio viene chiuso alla fine di uno e riaperto
all'inizio del successivo: senza questo, una metà arriva come testo semplice e
l'altra come un blocco che non finisce mai, il che in Discord inghiotte tutto
ciò che viene detto dopo. Ogni parte viene registrata come di quell'agente,
perché una persona risponde a quella che ha sullo schermo.

**Niente pulsanti, e `!` per i comandi.** La pressione di un pulsante e uno
slash command sono entrambi *interazioni*, e un'interazione arriva tramite il
Gateway o tramite un endpoint HTTPS che Discord può raggiungere. Un canale
interrogato a intervalli non vede né l'una né l'altro. Così `/agents` è
`!agents`, un messaggio normale, e l'elenco è una lista di nomi da scrivere
invece di una colonna di pulsanti. Viene accettato anche `/agents`, perché chi
ha configurato il bot di Telegram lo scriverà per abitudine.

**La risposta di un agente non menziona nessuno.** Ogni messaggio che questo
invia porta `allowed_mentions: {"parse": []}`, così un `@everyone` scritto da
un modello è testo e non una notifica a un intero server. `replied_user` resta
attivo: una risposta deve raggiungere la persona che ha chiesto. Una regola al
socket e non in un prompt, per la stessa ragione per cui lo è l'elenco di
inoltro della posta.

Quello che Discord non ha è il silenzio di Telegram verso gli sconosciuti. Non
c'è nessun `chat_id` con cui confrontare: il bot chiede un canale e legge quel
canale, quindi chi può parlare con gli agenti è chi può scriverci. Un canale
privato è la configurazione che corrisponde a ciò che
`fIsFromTheConfiguredChat` impone nel codice - ed è nominato nel manuale,
perché è tutta l'autorizzazione che c'è.

Il webhook che questo canale aveva prima c'è ancora e manda ancora. Un webhook
non può leggere, non può rispondere e non riceve indietro nessun id di
messaggio, quindi `listen` su un webhook viene rifiutato invece che offerto: un
interruttore che non fa niente è peggio di nessun interruttore.

### Un solo instradamento, due listener

`agent_routing` contiene ciò che entrambi i listener fanno allo stesso modo:
quali agenti esistono, la lettura di un nome da `@News Miner`, `/news_miner` o
`@002` con la corrispondenza più lunga che vince, che cosa ha detto un agente
per chiudere un turno, e il rapporto di stato. Il protocollo resta in ciascuno
di essi - un long poll non è un polling REST, una tastiera inline non è una
lista di nomi, e una risposta è `reply_to_message` in uno e
`message_reference` nell'altro.

È stato scritto quando è stato scritto il secondo listener, e il rapporto di
stato ne è il motivo. Due copie di quella risposta sarebbero due risposte a «è
in esecuzione?», e la prima cosa su cui sarebbero in disaccordo è quanti
servizi ci sono.

L'invio non sta lì. Resta in ciascun listener come `fSay`, il che permette a un
test di sostituire quello di un listener e lasciare stare l'altro.

### Un browser, condiviso; un profilo, no

`web.fetch` legge una pagina pubblica e si ferma lì: niente sessione, niente
modulo, niente pulsante. Il browser è l'altra cosa, e si divide in due:

| | Dove | Di chi è |
|---|---|---|
| Il browser | `/opt/boa/playwright/` | root, 0755, una copia |
| Il profilo | `agents/xxx/browser/profile/` | l'agente, 0700, uno ciascuno |

Il binario è condiviso perché è un binario e non c'è niente da isolare al suo
riguardo; una copia per agente sarebbe 600 MB ciascuna e un aggiornamento da
fare N volte. Il profilo non è condiviso, perché contiene i cookie: l'agente
007 che accede a qualcosa non deve lasciare l'agente 008 con la sessione
aperta. Quella separazione è del kernel, la stessa home 0700 in cui vive tutto
il resto di un agente - che è esattamente ciò che un prodotto di agenti in
hosting non può offrire quando tutti i suoi agenti condividono una macchina e
un insieme di sessioni.

Ne discendono tre decisioni:

**Il browser resta aperto tra una chiamata di strumento e l'altra all'interno
di un'esecuzione.** `browser.click` agisce su ciò che `browser.open` ha
lasciato sullo schermo, e un'esecuzione è un solo processo dalla prima
chiamata di strumento all'ultima, quindi un handle a livello di modulo è tutto
lo stato che serve. `atexit` lo chiude; senza, un agente orario lascia un
Chromium dietro di sé a ogni esecuzione e riempie la macchina entro il
mattino.

**Playwright viene importato dentro le funzioni, mai a livello di modulo.** Gli
strumenti del browser vengono elencati nell'interfaccia che un browser sia
stato installato o no, e un ImportError in cima li farebbe sparire da
quell'elenco senza nessuna spiegazione da nessuna parte. Importato tardi, un
browser mancante è una frase che dice quale comando eseguire.

**Headless, e solo indirizzi pubblici.** Quello che si vuole è la sessione e il
DOM, non un'immagine di una finestra, quindi un display virtuale sarebbe un
pezzo in movimento per niente.

«Solo indirizzi pubblici» viene imposto da un gestore di rotte installato sul
CONTESTO (`browser.fInstallNetworkPolicy`), non da ciascuno strumento.
Verificare l'URL in `browser.open` copriva esattamente un indirizzo per
esecuzione: una pagina è libera di reindirizzare, e una pagina che a un agente
è stato detto di leggere è libera di contenere un link, un iframe, un'immagine
o un modulo che puntano a `127.0.0.1` - e `browser.click` non aveva nessun
controllo. Sul contesto copre navigazioni, reindirizzamenti, clic, invii di
moduli e ogni sottorisorsa, e il sesto strumento di browser che qualcuno
scriverà lo riceve senza sapere che esiste. Ciò che viene rifiutato viene
nominato nella risposta dello strumento, perché altrimenti una richiesta
bloccata è invisibile: la pagina viene resa senza di essa e l'agente spende il
suo budget a riprovare.

I nomi host vengono risolti una volta per esecuzione e ricordati, il che
limita invece di eliminare la finestra in cui un nome potrebbe risolversi in un
indirizzo pubblico per il controllo e in uno privato per la connessione.
Chiuderla richiede che la connessione sia fissata all'indirizzo verificato,
cosa che Chromium da qui non espone.

Un cookie di sessione sparisce comunque quando il browser si chiude, in questo
come in ogni browser. Ciò che sopravvive è ciò che il sito ha marcato per
sopravvivere.

### Ciò che un provider accetta non è ciò che dice lo standard

Due adattatori mandavano qualcosa che il loro provider rifiuta, e in entrambi i
casi il risultato era lo stesso: ogni chiamata di strumento tramite quel
provider falliva, su ogni modello, e niente nella suite di test se ne accorgeva
perché la suite verificava i pezzi invece del giro completo.

| Provider | Che cosa veniva inviato | Che cosa tornava |
|---|---|---|
| Ollama | `kanban__list_cards` decodificato di nuovo in niente | Il registro rifiutava uno strumento che non era stato concesso all'agente - il nome che gli era appena stato offerto |
| Google | `"additionalProperties": false`, che è JSON Schema corretto | `400 - Unknown name "additionalProperties" at 'tools[0].function_declarations[0].parameters'` |

Il `function_declarations[].parameters` di Gemini è un SOTTOINSIEME di JSON
Schema e rifiuta ciò che non conosce invece di ignorarlo, quindi
`fCleanSchemaForGoogle` filtra lo schema attraverso una lista di
autorizzazioni, ricorsivamente. Una lista di autorizzazioni e non una lista di
blocco, per la ragione per cui qui ogni lista di autorizzazioni è tale: la
prossima chiave che qualcuno aggiunge a uno schema di strumento verrebbe
altrimenti rifiutata da Gemini, che qualcuno si sia ricordato o no di
aggiungerla a un elenco di cose da togliere.

Entrambi sono stati scoperti eseguendo l'intero ciclo - chiedere, chiamare uno
strumento, rispondere a quella chiamata - contro le API reali con chiavi reali.
`_/temp/probe-defaults.py` è quella verifica, ed è l'unica cosa che trova
questa classe di bug: uno schema valido, un nome corretto, e un provider che
non lo accetta.

### Un file di adattatore per provider

Venticinque provider, venticinque file, anche se la maggior parte parla lo
stesso dialetto. Un unico adattatore «compatibile con OpenAI» sembra ordinato
finché uno di quei provider non cambia il nome di un campo, e allora la
correzione va fatta senza rompere gli altri venti. Ogni file porta con sé le
stranezze del proprio provider: DeepSeek scarta `reasoning_content` prima che
il runner possa riprodurlo, llama.cpp rileva un template di chat senza supporto
per gli strumenti, vLLM trasforma un 404 nell'elenco dei modelli che serve
davvero, Cloudflare costruisce il proprio indirizzo a partire dalla
credenziale.

Ciò che condividono è `base.py`: una forma neutra dei messaggi modellata su
chat/completions, perché la maggior parte di loro la parla già, e l'adattatore
di Anthropic la traduce in blocchi di contenuto.

Condividono anche `openai_dialect.py`, e la differenza tra questo e un
adattatore condiviso è proprio il punto. Il modulo del dialetto contiene la
richiesta in sé - il POST, gli errori HTTP che vale la pena nominare, il
parsing della risposta - che non è una stranezza di nessun provider. Le
stranezze restano in ciascun file, dichiarate come attributi di classe che il
modulo legge:

| Attributo | Che cosa decide |
|---|---|
| `cDisplayName` | Il nome in ogni messaggio di errore. «zai request failed» non è ciò che qualcuno cercherebbe |
| `cMaxTokensField` | `max_tokens` o `max_completion_tokens`, a seconda della grafia che ha seguito il provider |
| `cToolChoiceMode` | `auto`, `any`, oppure `omit` per i provider che rifiutano il campo. `auto` è ciò di cui un agente ha bisogno: un modello costretto a chiamare uno strumento a ogni turno non finisce mai un'esecuzione |
| `cChatCompletionsPath` | Il percorso dopo l'URL di base, per i pochi che non usano quello consueto |
| `cAssistantContentWhenEmpty` | Che cosa mandare invece di un `content` nullo, per un provider il cui schema rifiuta null |

### Che cosa hanno cambiato ventidue chiavi reali

Ogni provider qui è stato chiamato con una chiave reale, gli è stata fatta una
domanda, gli è stato dato uno strumento e poi gli è stata consegnata la
risposta alla chiamata di strumento che aveva fatto. Tutti i ventidue che
hanno una chiave completano quel giro. Sette cose sono emerse solo al secondo
passo - quello che un test con una risposta preconfezionata non raggiunge mai -
e ognuna è ora una riga di codice con le parole del provider accanto:

- **Perplexity aveva ritirato l'endpoint.** `chat/completions` risponde 403
  «Sonar is now the Agent API. Use /v1/responses instead of /v1/sonar», quindi
  quell'adattatore è stato riscritto sulla Responses API, e il provider è
  passato dall'essere un modello all'essere un router su 48 modelli.

- **Una chiave in un messaggio di errore.** Gemini veniva chiamato come
  `?key=...`, quindi un suo 503 metteva l'intera chiave nell'errore che
  l'utente legge e che il giornale conserva. La chiave è passata
  nell'intestazione `x-goog-api-key`, e ora `base.fRedactCredentials` ripulisce
  `key=`, `api_key=`, `access_token=` e `token=` da ogni errore prodotto da
  qualsiasi adattatore, perché quel tipo di guasto non dovrebbe dipendere dal
  fatto che un adattatore se ne ricordi.
- **Gemini 3 vuole indietro la sua firma di pensiero.** Una conversazione le
  cui chiamate di funzione tornano senza la firma che ha emesso viene
  rifiutata in blocco, quindi ogni agente Gemini falliva nel momento in cui
  aveva usato uno strumento. `ToolCall.dProviderData` la porta all'andata e al
  ritorno, opaca per tutto il resto.
- **Cloudflare rifiuta un `content` nullo.** Che è esattamente ciò che contiene
  un messaggio dell'assistente quando il modello ha risposto con chiamate di
  strumento e nessuna parola. Riceve `""`; il dialetto continua a mandare null
  a tutti gli altri, perché null è ciò che il dialetto specifica.
- **Ragionamento scritto nella risposta.** MiniMax risponde con
  `<think>...</think>` nel testo stesso. Viene tolto nel modulo del dialetto e
  non in un adattatore, perché lo fa il modello, quindi lo stesso modello
  dietro un gateway lo fa anche lui - e solo quando la risposta INIZIA con il
  tag, così che un modello che scrive di HTML conservi le sue parole.
- **Together lascia davanti il nome del canale.** gpt-oss scrive in canali e
  Together restituisce «finalThe weather in Madrid»; Groq e Cerebras, che
  servono lo stesso modello, no. Viene tolto in `together.py`, dove sta una
  stranezza di un solo provider.
- **Quattro modelli predefiniti che il provider non serviva.** Il 20b di
  Fireworks richiede un deployment proprio, quello di Together non è
  serverless, Moonshot ha ritirato kimi-k2.5, e gemini-3.7-flash risponde 503
  «experiencing high demand». Un predefinito che fallisce alla prima
  esecuzione è peggio di uno indietro di una versione.

Cinque adattatori non lo usano affatto, perché la loro API non è quella: i
blocchi di contenuto di Anthropic, il `generateContent` di Google, il
`/completion` di llama.cpp, la chat v2 di Cohere - che accetta gli stessi
messaggi ma risponde con il testo in blocchi, un motivo di fine tutto suo in
maiuscolo, e i conteggi dei token annidati sotto `usage.tokens` - e
Perplexity, che ha ritirato del tutto chat/completions e risponde con

    403 Sonar is now the Agent API. Use /v1/responses instead of /v1/sonar

quindi quell'adattatore parla la Responses API: un'unica lista `input` invece
di `messages`, il prompt di sistema come `instructions`, e una risposta che
arriva come elementi di output - un `message` con il suo testo in blocchi, o
una `function_call` - invece che come una choice. Il risultato di uno strumento
torna come elemento a sé, `function_call_output`, abbinato tramite `call_id`.

Due nomi vengono risolti prima che qualcos'altro li veda, tramite
`factory.dProviderAliases`: `gemini` è il nome che la documentazione di Google
dà all'API e `google` è ciò che dice l'`info.json` di ogni agente fin dalla
prima versione, quindi entrambi raggiungono lo stesso adattatore e solo uno dei
due viene mai memorizzato.

Su quale dei venticinque si può impostare un agente lo decide
`fListProviders`, non il browser: un provider è `selectable` quando è
self-hosted o la sua chiave è memorizzata. È un filtro su ciò che vale la pena
offrire, non una regola - una chiave può anche vivere nella home dell'agente,
dove l'applicazione web non può guardare, quindi l'interfaccia mostra comunque
a un agente il provider su cui è già impostato.

Quello stesso flag decide una cosa nell'interfaccia: la casella **URL di
base**, sia sul modello principale sia su quello di riserva, viene mostrata per
un provider self-hosted e nascosta per uno cloud. `base.fInit` ricade già su
`cDefaultBaseUrl` dell'adattatore, quindi per un provider cloud il campo faceva
una domanda a cui era già stata data risposta prima di farla - e l'unica
risposta che poteva accettare e che il predefinito non dà è una risposta
sbagliata. Viene nascosta e non svuotata: un'installazione che mette un proxy
davanti a un provider cloud ha quell'indirizzo memorizzato, e nascondere una
casella non è un motivo per scartare ciò che contiene.

Una cosa che `base.py` nasconde a tutti è il nome di uno strumento. Questo
progetto chiama uno strumento `family.action`; un provider convalida il nome di
una funzione contro `^[a-zA-Z0-9_-]+$` e rifiuta l'intera richiesta per via del
punto, senza nessun indizio su quale campo fosse sbagliato. `fToolNameToWire`
sostituisce il punto con `__` all'uscita e `fToolNameFromWire` lo rimette
all'entrata, in ogni adattatore, così il registro, l'interfaccia, `info.json`
e i log non vedono mai la forma codificata.

### Tetti, non fiducia

Ogni esecuzione si ferma al primo di quattro tetti: token, passi, secondi,
esecuzioni al giorno. Esistono perché un ciclo non sorvegliato su un'API a
pagamento è una fattura aperta e, su un modello self-hosted, una GPU che non
torna mai più. `max_tokens` di ogni richiesta si riduce di quanto l'esecuzione
ha già speso, quindi un'esecuzione non può superare il suo budget con
un'ultima chiamata costosa.

Quattro cose fanno la differenza tra un tetto e un suggerimento, e ognuna di
esse è stata un suggerimento finché non è stata corretta:

  - **Nessun pavimento sotto la richiesta di token.** `max(512, remaining)`
    chiedeva 512 token quando il budget era esaurito, quindi a un agente con un
    solo token rimasto era ancora concessa mezza pagina.
  - **Ogni chiamata riceve il tempo che RESTA**, non l'intero timeout
    dell'esecuzione. Il `vTimeoutSeconds` dell'adattatore stesso viene spostato
    prima di ogni chiamata, invece di aggiungere un parametro ai ventisei
    adattatori che implementano `fSendMessages`.
  - **La scadenza viene verificata prima di ogni strumento**, non una volta per
    passo. Un lotto di sei chiamate di strumento che arrivava appena prima
    della scadenza veniva eseguito per intero, ognuna con il suo timeout in
    aggiunta a un'esecuzione che era già finita.
  - **Un orologio monotono.** `time.time()` si sposta quando NTP lo fa
    saltare, e un'esecuzione iniziata «nel futuro» non raggiunge mai il suo
    timeout.

Ciò che ancora non è limitato è il prompt. Una chiamata spende il suo input più
il suo output e qui viene limitato solo l'output, quindi una conversazione
lunga sfora all'entrata; contarlo vorrebbe dire far girare il tokenizzatore di
ogni provider sulla conversazione prima di ogni chiamata. Anche la risposta di
chiusura dopo un tetto è volutamente fuori budget, e lo dice dove è scritta.

### Un'esecuzione di un agente alla volta

Due lock, perché ci sono due tipi di chiamante.

Il demone tiene un `threading.Lock` per agente tra «questo agente è in
esecuzione?» e «avvia il processo». Serve ogni richiesta sul proprio thread,
quindi due chiamate `run_now` con `only_if_idle` erano due thread di un solo
processo senza niente in mezzo - e una scansione di /proc non può vedere un
processo che non è ancora stato creato con fork. Misurato: due chiamate
simultanee, due esecuzioni.

Il runner prende un `flock` su `<home>/run.lock` e lo tiene per tutta la durata
del processo. Quello è l'autorità, perché un crontab avvia il runner
direttamente e non passa mai dal demone. Non è un confine di permessi - un
agente con `bash.run` può avviare tutto ciò che vuole - esiste perché
l'APPLICAZIONE non avvii lo stesso agente due volte, spendendo due budget su un
solo profilo del browser e una sola conversazione.

### Un'esecuzione che non è mai partita lo dice

Il demone privilegiato avvia il runner con stdin, stdout e stderr su
`/dev/null`. Tutto ciò che scrive `fLogLine` quindi non va da nessuna parte, e
due fallimenti vivevano interamente in quell'output:

- il lock dell'esecuzione era preso, quindi questa esecuzione non avviene;
- qualcosa è fallito prima che `fExecute` scrivesse `run_started` - un
  `info.json` illeggibile, o un provider la cui chiave API non è stata
  impostata, che è di gran lunga il più probabile dei due.

Misurato su un'installazione reale: con il lock preso, `POST /agents/001/run`
rispondeva `202 {"started": true}` e non compariva niente nel giornale, in
`journalctl` o in alcun file. Lo stesso fallimento sotto cron ERA visibile,
perché cron conserva l'output di ciò che avvia - ed è per questo che è durato
così a lungo. Il buco è sempre stato solo nel percorso che usa l'interfaccia.

`fRecordRunRefused` lo scrive invece nel giornale, come una fine con stato
`refused` e nessun `run_id`. Ogni parte di quella forma è portante:

| Parte | Perché |
|---|---|
| `kind: run_finished` | La Cronologia rende le fini. Un tipo tutto suo richiederebbe che l'interfaccia lo imparasse, e una voce che niente rende è come nessuna voce |
| `status: refused` | `failed_runs` conta le fini il cui stato è `failed`. Non è girato niente dell'agente, quindi non è fallito niente dell'agente |
| nessun `run_started` | `runs` e `max_runs_per_day` contano gli avvii. Un lock preso non deve consumare una delle esecuzioni del giorno per un'esecuzione che non è avvenuta |
| `run_id: ""` | Non è partito niente, quindi non c'è nessuna esecuzione da identificare |

Scritto solo quando nient'altro lo ha scritto. Una volta che `fExecute` ha un id
di esecuzione ha già scritto `run_started`, e i suoi gestori scrivono il
`run_finished` corrispondente prima di rilanciare l'eccezione, quindi `fMain`
verifica `vRun.vRunId` prima di aggiungere una seconda fine per una stessa
esecuzione. Lo stesso controllo decide chi chiude il turno della chat: i
gestori di `fExecute` lo chiudono mentre registrano la fine, e `fMain` lo chiude
solo per un'esecuzione che non è mai arrivata fin lì. Misurato prima che fosse
così, sulla macchina Debian di prova: ogni esecuzione che non riusciva a
raggiungere il suo provider rispondeva alla sua domanda due volte, con la
stessa frase.

### La cronologia mostra le più recenti, e non lo faceva

`fReadEntries` restituisce un giornale dal più vecchio - lo dice la sua stessa
docstring - e `fRenderRunHistory` ne prendeva `.slice(0, cShownRuns)`. Cioè le
dieci esecuzioni più VECCHIE. Un agente con più di dieci esecuzioni alle spalle
aveva una Cronologia che non cambiava mai più.

Scoperto pilotando l'applicazione reale con un browser reale, che è l'unico
modo in cui si sarebbe potuto scoprire: ogni altro test di `dashboard.js` in
questo progetto legge il file e ci cerca una stringa, e la stringa c'era.
Misurato su un'installazione reale, in tre lingue: un agente la cui esecuzione
più recente era appena stata rifiutata per mancanza di una chiave API mostrava
un fallimento del provider di quaranta minuti prima, e il rifiuto non
compariva per niente.

`.slice(-cShownRuns).reverse()`: le ultime dieci, la più recente in cima, che è
ciò che dice il titolo sopra l'elenco.

La tabella riassuntiva sopra quell'elenco aveva due difetti tutti suoi, entrambi
scoperti nella stessa schermata: stampava `last_status` grezzo, quindi una
pagina in spagnolo diceva «Último estado: refused», e stampava `last_run_at`
grezzo, quindi un nudo `2026-09-19T03:44:29Z` stava proprio sopra un elenco di
marche temporali ripulite. Ora entrambi passano per ciò che le righe sotto di
loro usavano già.

### Una casella di posta è l'unico input in cui chiunque può scrivere

I quattro strumenti `mail.*` seguono esattamente i canali: l'agente dice che
cosa vuole che venga fatto, e l'API degli agenti - che gira come `boa` e
custodisce le credenziali - lo fa. Un agente che potesse leggere la password
della casella non avrebbe «accesso alla posta in arrivo»; avrebbe l'account,
ogni messaggio che contiene, per sempre, e la possibilità di inviare come il
suo proprietario.

Ciò che è diverso nella posta è la direzione in cui viaggia l'input. Un agente
che legge una casella di posta è un agente le cui istruzioni arrivano, in
parte, dentro i messaggi che legge, scritti da chiunque al mondo. Ne
discendono tre decisioni:

  - **L'inoltro è consentito solo agli indirizzi che l'utente ha elencato**, e
    quell'elenco viene verificato dentro `mailbox`, nel processo che apre la
    connessione - mai nel prompt. Una regola in un prompt è un consiglio; una
    regola al socket è una regola. Senza elenco, l'inoltro viene rifiutato in
    blocco.
  - **Leggere non segna niente come visto** (`BODY.PEEK[]` su una select in
    sola lettura), così un agente che guarda una casella non porta via il
    conteggio dei non letti su cui la persona contava.
  - **Eliminare sposta nel Cestino** dove l'account ne ha uno. Ciò che un
    agente rimuove in base a una regola scritta il mese scorso, una persona lo
    può ancora trovare. «Questo account non ha una cartella cestino» e
    «l'elenco delle cartelle non si è potuto leggere» vengono tenuti separati,
    perché solo il primo dei due può finire in un expunge: prima arrivavano a
    `fDeleteMessage` come la stessa stringa vuota, quindi una sola riga LIST
    non analizzata trasformava ogni `mail.delete` in un'eliminazione
    definitiva.

### Arriva con un agente, ne offre molti

L'installazione crea esattamente un agente: l'orchestratore. Tutto il resto
viene da «+», che offre tre punti di partenza: un agente VUOTO, un `.zip`
esportato da un agente, o un TEMPLATE del repository dei template.
Un'installazione che arriva con agenti che nessuno ha chiesto è
un'installazione che comincia con cose da spegnere.

Prima i template venivano distribuiti dentro questo repository, un file
Markdown ciascuno in `backend/agents/examples/`. Ora vivono in un repository
tutto loro,
[bunch-of-aigents-templates](https://github.com/nipegun/bunch-of-aigents-templates),
clonato accanto a questo come `../bunch-of-aigents-templates`: un template
nuovo raggiunge ogni installazione senza un aggiornamento dell'applicazione, e
un'installazione può essere puntata su un fork, o su un repository suo, sotto
Impostazioni -> Agenti (`templates_repo_url`, `templates_repo_branch`,
verificati da `agent_templates.fValidateRepositoryUrl` e `fValidateBranch` al
salvataggio). `agent_templates` scarica l'intero repository come l'unico
`.tar.gz` in cui viene servito un branch - l'indirizzo da cui il programma di
installazione scarica l'applicazione - quindi elencare i template è una sola
richiesta, senza API di GitHub e senza limite di frequenza. Viene tenuto in
cache per cinque minuti per worker web. Un indirizzo `file://` con la stessa
struttura `archive/refs/heads/<branch>.tar.gz` serve una macchina senza
uscita verso l'esterno.

**Un solo formato per tutto ciò che diventa un agente** (`agent_package`): una
cartella con `agent.json` e `system-prompt.md`, e facoltativamente
`memory.md`, `home/...` e `rag/documents.json` con `rag/files/...`. La
cartella di un template è un pacchetto di questo tipo che porta solo i primi
due; un `.zip` esportato è la stessa struttura con le opzioni che l'utente ha
spuntato. Quindi installare un template e importare un `.zip` sono la stessa
funzione, `agent_io.fInstallPackage`, e qualsiasi cosa si possa esportare si
può pubblicare come template.

Tutto viene verificato prima che esista un agente (`agent_package.fReadPackage`),
perché un'importazione che fallisce a metà lascia un agente che nessuno ha
chiesto:

- `agent.json` può contenere solo le chiavi di `lManifestKeys`, e `format` 1.
  Una chiave sconosciuta viene rifiutata invece che ignorata: è un refuso in un
  template, o un pacchetto di una versione più nuova che questa leggerebbe
  male.
- Nel formato non c'è posto per `enabled`, per chiavi, token o credenziali dei
  canali, né per i canali su cui l'agente ascolta. Un agente importato viene
  sempre creato spento, e un provider viaggia solo come nome, modello e URL di
  base - `api_key_ref` mai.
- Le pianificazioni sono cinque campi di cron, nient'altro
  (`agents.fValidateSchedule`), e vengono verificate DI NUOVO in
  `exec_daemon.fVerbCreateAgent`. Una pianificazione viene scritta all'inizio
  di una riga di crontab, come root; una che portasse " /bin/sh -c ..." o
  un'interruzione di riga sarebbe un comando. Che verifichi il processo web non
  basta: il confine è l'esecutore.
- Gli strumenti vengono tenuti solo se installati qui, e quelli scartati vengono
  elencati (`missing_tools`) così che l'utente li veda prima di confermare. Le
  competenze vengono passate come nomi e l'esecutore tiene quelle installate,
  come prima.
- `rag` passa per `rag_settings.fValidateSettings`, come fa una scrittura dalla
  scheda RAG, e i documenti della biblioteca devono rientrare nei limiti di
  file e di archiviazione che porta il pacchetto stesso.
- Ogni percorso della home passa per `agent_home.fValidatePath`: relativo,
  niente `..`, e mai un nome di primo livello escluso (vedi sotto).
- Un `.zip` (`ZipSource`) viene rifiutato se ha un nome di membro che esce
  dalla cartella, un link, un membro cifrato, un membro che si espande più di
  200:1 oltre 1 MiB, o più di 8 GiB in totale. Un archivio di repository tiene
  solo i file regolari; un link al suo interno viene saltato, non seguito.

Creare da un template nomina il TEMPLATE e nient'altro. Il server lo scarica e
lo legge: una richiesta che potesse portare i propri strumenti e la propria
pianificazione permetterebbe al browser di consegnare a un agente un permesso
che l'utente non ha mai spuntato. La finestra di dialogo mette prima l'agente
VUOTO, poi il `.zip`, poi i template, le cui descrizioni vengono
dall'`agent.json` di ciascun template nella lingua dell'interfaccia
(`fPickDescription`: quella lingua, altrimenti en-US).

**Un'importazione sono tre momenti**, perché una biblioteca può pesare
centinaia di MiB e HAProxy fa cadere una richiesta che non manda niente per
300 secondi: il browser carica il `.zip` a blocchi in `/opt/boa/imports/<id>/`
(`boa`, 0700, creato da entrambi i programmi di installazione ed elencato nei
`ReadWritePaths` dell'unità web); `fFinishImport` lo verifica per intero e
restituisce ciò che installerebbe; una volta che l'utente conferma,
`fStartImport` lo installa in un thread del processo web, che scrive il suo
avanzamento in `job.json` perché il browser lo interroghi. Qualsiasi worker
può rispondere all'interrogazione perché lo stato è un file. Un lavoro il cui
thread ha smesso di scrivere per tre minuti risulta interrotto: il suo processo
è stato riavviato. Un fallimento dopo che l'agente esiste lo elimina di nuovo
(`fInstallPackage`).

**Un'esportazione viene trasmessa in streaming** (`fExportAgent`): il `.zip`
viene scritto mentre viene inviato, così un agente con una biblioteca di
centinaia di MiB viene esportato senza essere tenuto in memoria. Del crontab
viaggiano solo le righe che questa applicazione ha scritto per eseguire
l'agente, come i loro cinque campi (`fReadSchedules`); qualsiasi altra riga è
un comando che qualcuno ha scritto, e un pacchetto che portasse comandi li
eseguirebbe sulla macchina su cui arriva.

**La home viene letta e scritta come l'agente** (`agent_home`, verbo
dell'esecutore `agent_home`): l'esecutore avvia il modulo come l'utente
dell'agente, nello stesso modo in cui avvia il worker RAG, così root non
percorre mai un albero che l'agente può riordinare, e un link piantato nella
home non porta da nessuna parte dove l'agente non potesse già andare. Lasciato
fuori in entrambe le direzioni: ciò che il sistema tiene lì (`chat.jsonl`,
`runs.jsonl`, i registri delle chiamate API, `run.lock`, `attachments/`), ciò
che ha un suo posto nel pacchetto (`memory.md`, `rag/`), il profilo del browser
con le sue sessioni aperte, e ogni voce nascosta al primo livello della home.
Un `.ssh/authorized_keys` importato sarebbe una porta d'ingresso e un
`.bashrc` esegue codice, e nessuno dei due vale il raro uso legittimo.

Uno dei template, `web-navigator`, non ha crontab. È quello del browser - apre
pagine, accede, fa clic e compila moduli, dove gli altri leggono - e quel
lavoro è qualunque cosa l'utente abbia appena chiesto, non qualcosa da fare
alle quattro del mattino. Il suo prompt è dove sono scritte le regole di cui ha
bisogno un browser con una sessione: mai scrivere una credenziale, mai
completare un acquisto o un invio, e trattare la pagina come dati e non come
istruzioni.

Neanche `rag-consultant` ha crontab: risponde a domande a partire dalla propria
biblioteca RAG. È l'unico template il cui `agent.json` dice `"rag": {"enabled":
true}`. Il runner trattiene gli strumenti `rag.*` mentre la biblioteca di un
agente è spenta, quindi senza quella riga l'agente verrebbe creato senza
nessuno strumento. Il `rag` del pacchetto raggiunge
`exec_daemon.fVerbCreateAgent` come `pRag` (il corpo della richiesta non viene
mai letto per questo), dove passa per `rag_settings.fValidateSettings`, lo
stesso controllo per cui passano le scritture della scheda RAG: un template può
accendere la biblioteca e non può darle niente che quella scheda non potrebbe
darle. Il suo `max_tokens_per_run` è 40000 perché il runner dimensiona il
budget dei passaggi come `max_tokens_per_run` meno prompt, cronologia e 4096;
con il predefinito 16384 non ci sarebbe spazio per i passaggi. Il suo prompt
descrive gli strumenti per quello che sono - `rag.read` restituisce un
passaggio e i suoi vicini, non un documento - e chiede i marcatori
`[rag:REF]` che `fResolveCitations` verifica.

### Due modi di servirla, scelti al momento dell'installazione

O 11080 e 11443 su localhost con un HAProxy davanti sulla 80 e sulla 443,
oppure 80 e 443 serviti direttamente. Il programma di installazione chiede,
ricorda la risposta in `config/ports.conf`, e un aggiornamento non chiede mai
di nuovo né cambia di nascosto le porte su cui la macchina ascolta.

La differenza non sono solo i numeri: in modalità diretta `accept-proxy` deve
sparire dal bind, perché un browser che si connette direttamente alla 443 non
manda nessuna intestazione PROXY e un bind che ne pretende una rifiuta ogni
client reale.

In modalità `direct` l'HAProxy della macchina non viene semplicemente lasciato
stare: viene ritirato. `fRetireMachineProxy` lo ferma, lo toglie da ogni
runlevel su Alpine, lo disabilita **e lo maschera** su Debian, e poi elimina
`/etc/haproxy/haproxy.cfg` quando l'ha scritto questo programma di
installazione o lo sposta in `haproxy.cfg.before-boa.<date>` quando l'ha
scritto qualcun altro. Fermarlo non basta da solo: uno lasciato abilitato si
prende la 80 e la 443 al prossimo avvio, prima che questa applicazione giri,
e sotto systemd un aggiornamento di pacchetto, il `Wants=` di un'altra unità o
un semplice `systemctl start` possono riportare in vita anche uno
disabilitato. Un'unità mascherata non può essere avviata da niente, e haproxy
senza `/etc/haproxy/haproxy.cfg` non ha niente da cui partire. Qualunque cosa
occupi ancora la 80 o la 443 dopo questo viene nominata nel log, perché in
questa modalità il proxy non può partire senza di esse, e capirlo da «the
application did not answer» mezzo minuto dopo è un modo molto peggiore di
scoprirlo.

Ciò che di proposito NON si fa è rimuovere il pacchetto haproxy. `boa-proxy`
È `/usr/sbin/haproxy` - termina il TLS e legge l'intestazione PROXY davanti a
gunicorn, e in modalità `direct` è proprio ciò che fa il bind sulla 80 e sulla
443 - quindi eliminare il pacchetto lascerebbe l'applicazione senza niente in
ascolto, in nessuna delle due modalità. Ciò che viene ritirato è il *servizio*
HAProxy della macchina, che è un'altra cosa che si trova a usare lo stesso
binario. Tornare a `proxied` smaschera l'unità prima di abilitarla, altrimenti
il ritorno finirebbe con «The machine's HAProxy would not start» per via di
una maschera che questo stesso programma di installazione aveva messo.

Misurato su entrambe le macchine di prova con `--update --ports direct`:
l'unità è finita mascherata su Debian e in nessun runlevel su Alpine,
`/etc/haproxy` è rimasta senza configurazione, e l'applicazione ha risposto 200
sulla 443 e 301 sulla 80. Il ritorno, `--update --ports proxied`, l'ha
lasciata di nuovo abilitata e attiva con 200 sulla 11443 e sulla 443. Sette
test ESEGUONO la funzione contro comandi di servizio finti, su una
configurazione con il marcatore e una senza, in entrambe le modalità, e uno di
essi fallisce se una versione futura dovesse mai ricorrere ad
`apk del haproxy` o `apt-get purge haproxy`.

### Una conferma si mostra dove l'utente sta guardando

Prima `Settings saved` veniva scritto in cima alla colonna del contenuto. Va bene su
un pannello corto ed è inutile su uno lungo: il pulsante Salva in fondo alla
scheda Strumenti di un agente produceva un messaggio diverse schermate più su,
fuori da ciò che il browser stava disegnando, quindi salvare sembrava non fare
niente.

Ora è un messaggio a comparsa centrato sulla colonna del contenuto, su uno
strato `fixed` che è fratello di quella colonna invece che suo figlio. `fixed`
è il punto: centrare dentro la colonna finirebbe in mezzo al *documento*, che
su una scheda lunga è lo stesso bug qualche schermata più in basso. Lo strato
si ferma alla barra laterale, perché un messaggio disegnato sopra l'elenco degli
agenti sembrerebbe appartenere all'elenco degli agenti, e non riceve eventi del
puntatore, così niente di ciò che sta dietro smette di funzionare mentre un
messaggio è visibile.

Quanto resta è una preferenza di questo browser (`boa.noticeSeconds`,
Impostazioni → Interfaccia), accanto al tema e alla lingua e per la stessa
ragione: tre secondi sono tanti per una parola e non bastano per una frase, e
quale delle due sia un messaggio dipende da chi lo legge. Gli errori sono
l'eccezione e ignorano del tutto il numero — un errore aspetta di essere
chiuso, perché è l'unico messaggio che deve essere ancora lì quando l'utente
torna a guardare lo schermo.

Un messaggio ha tre colori, e il terzo esiste per ciò che gli altri due non
possono dire. Il verde è un salvataggio avvenuto, il rosso è un fallimento, e
l'ambra è **`No changes to save`**: è stato premuto Salva e il modulo conteneva
esattamente ciò che è già memorizzato. Riportarlo in verde è peggio che non
dire niente - «Impostazioni salvate» dopo un salvataggio che non ha scritto
niente è l'unica frase che impedirebbe a qualcuno di accorgersi che la sua
modifica non ha mai preso - e il rosso dichiarerebbe un fallimento dove non è
andato storto niente.

Ogni modulo che salva lo verifica nello stesso modo: il payload che
*manderebbe*, confrontato come JSON con l'istantanea presa quando il modulo è
stato riempito dal server, o dopo l'ultimo salvataggio. Le impostazioni di un
agente costruiscono quel payload in una sola funzione, `fCollectAgentPayload`,
usata sia per salvare sia per prendere l'istantanea, perché due lettori dello
stesso modulo che si fossero allontanati riporterebbero «nessuna modifica»
proprio sul campo che uno dei due non ha mai guardato. I pannelli delle
preferenze del browser conservavano già un'istantanea del genere, per
l'avviso «Modifiche non salvate», e risponde anche a questa domanda.

L'eccezione è un agente **nuovo**: il suo modulo contiene i valori del template
stesso e non è mai stato salvato, quindi premere Salva li scrive e passa alla
chat invece di dire che non c'è niente da fare.

### Il colore è stato, il movimento è attività

L'anello attorno all'avatar di un agente porta due fatti diversi e li disegna
su due canali diversi, così che nessuno dei due vada cercato. Se l'agente è
acceso è un colore che non si muove: verde o rosso. Se sta lavorando in questo
momento è movimento: un segmento illuminato percorre in senso orario
quell'anello verde. Un secondo colore statico per «occupato» sarebbe una
convenzione da imparare, mentre qualcosa che gira si capisce senza che lo si
insegni.

È disegnato come un rettangolo SVG con gli angoli arrotondati sovrapposto
esattamente al bordo, tracciato con un tratteggio il cui offset è animato,
così **la forma resta ferma e solo la luce si muove lungo di essa**. È l'intero
motivo dell'SVG: far ruotare invece un anello — un gradiente conico, un arco,
qualsiasi cosa sotto `transform: rotate` — fa girare anche la forma, e gli
angoli smettono di combaciare con il quadrato arrotondato sottostante.
`pathLength="100"` normalizza il contorno, così il foglio di stile parla in
percentuali del perimetro e niente va ricalcolato se l'avatar o il suo raggio
cambiano.

Rispondere a «chi è occupato?» significa leggere la riga di comando di ogni
processo, cosa che può fare solo root, quindi è un verbo del demone
privilegiato. Una sola scansione di `/proc` risponde per tutti gli agenti in
una volta — non una chiamata per agente — ed è ciò che la rende abbastanza
economica perché la barra laterale la chieda ogni cinque secondi. La stessa
scansione sostiene `only_if_idle`, così il buzzer e l'interfaccia non possono
essere in disaccordo sul fatto che un agente stia lavorando.

### Una scheda che scade viene annunciata nella conversazione

La chat di un agente è il registro di tutto ciò che a quell'agente è stato
chiesto di fare, non solo di ciò che gli è stato scritto. Così, quando il
buzzer avvia un'esecuzione per una scheda scaduta, quella scheda viene scritta
nel `chat.jsonl` dell'agente come un turno a sé, e la risposta
dell'esecuzione lo chiude: aprire la conversazione mostra il lavoro che
arriva, ciò che l'agente ne ha fatto e quanto è costato.

Tre decisioni tengono insieme il tutto.

**Viene scritta quando parte l'esecuzione, non quando viene creata la
scheda.** Una scheda programmata per stasera ed eliminata oggi pomeriggio non
è mai stata eseguita, e una conversazione che dicesse che è stata consegnata
sarebbe il registro di qualcosa che non è successo. Il buzzer vede sempre e
solo schede che sono ancora sulla bacheca, quindi scrivere nel momento della
sveglia è ciò che rende vero l'annuncio.

**Il file memorizza i campi della scheda, non una frase.** `role: "card"` porta
l'id, il titolo, chi l'ha assegnata e se è stata chiesta subito; il testo del
messaggio sono le istruzioni stesse della scheda. Ogni parola attorno a essi la
scrive l'interfaccia, nella lingua dell'utente — la stessa regola per cui
un'esecuzione fermata registra `ceiling: "tokens"` invece di una frase in
inglese.

**«Subito» e «alle 13:45» vanno distinti, e quando l'agente viene svegliato
sono entrambi nel passato.** Così la bacheca registra quale dei due è stato
chiesto (`run_mode`) invece di ricavarlo dopo dall'orologio, e la parola `now`
viaggia dal browser a `kanban.fValidateRunAt` come parola, trasformandosi in
una marca temporale nell'unico posto che registra anche che cosa era.

La scrittura è compito del demone privilegiato, non del buzzer: `chat.jsonl`
vive in una home 0700 di proprietà dell'agente, e il buzzer gira come `boa`. Il
demone fa fork, scende all'agente, scrive l'annuncio e solo dopo avvia
l'esecuzione — e se nella home non si può scrivere, l'esecuzione parte
comunque. L'annuncio è il registro del lavoro, non il lavoro.

Il fallimento inverso non è innocuo e viene gestito al contrario: se il
processo non può essere avviato **dopo** che il turno è stato aperto, il demone
scrive il fallimento in quel turno prima di sollevare l'eccezione. Nient'altro
lo chiuderebbe mai, e un turno aperto non lascia semplicemente una scheda
senza risposta — chiude per sempre la casella di composizione per
quell'agente.

L'esecuzione che segue non è né una semplice esecuzione programmata né un
turno di chat. Riscrive la sua risposta nella chat, perché la domanda è lì, ma
la conversazione **non** le viene riproposta: il suo prompt è la scheda, e
riproporre dieci scambi addebiterebbe a ogni esecuzione programmata una
conversazione che nessuno sta facendo. Nel runner quelli sono due flag
separati — `vWritesToChat` e `vIsChat` — e quella distinzione è tutto. Il
corollario è che un'esecuzione che si ferma prima di chiedere qualcosa al
modello (un agente spento, il tetto giornaliero) deve comunque chiudere il
turno, altrimenti l'interfaccia aspetta una risposta per sempre e la casella
di composizione resta chiusa.

### La documentazione dell'API è una pagina di questa applicazione

Viene resa a partire dalla specifica OpenAPI che costruisce questo progetto,
invece di caricare Swagger UI da una CDN, perché il server di produzione è una
macchina della LAN che potrebbe non avere affatto accesso a internet verso
l'esterno. Dal fatto che sia una delle nostre pagine invece di un widget
estraneo discendono due cose.

**Segue la lingua scelta**. La specifica resta in inglese - è il contratto di
un'API i cui nomi di campo, id e stringhe di errore sono tutti en-US, e un
`openapi.json` tradotto descriverebbe un'API che non esiste. Ciò che viene
tradotto è la pagina: `fAnnotateSpecForTranslation` appende una chiave
`data-i18n` a ogni pezzo di inglese prima di rendere, e il browser la sostituisce
nello stesso modo in cui lo fa in ogni altra pagina. Questo tiene le stringhe
nei file `.json` del frontend accanto a tutte le altre, e funziona anche per un
lettore anonimo. Le chiavi sono derivate dal testo e dal percorso invece di
essere scritte a mano, così un endpoint nuovo porta le proprie; una chiave
senza traduzione mantiene l'inglese, che è ciò che `fApplyTranslations` fa con
una chiave che non conosce.

**Riempie la colonna che le viene data**, come ogni altra pagina. Prima
manteneva una misura di 900px e si centrava, il che si legge bene per la prosa
e male per questo: la pagina è fatta soprattutto di tabelle di parametri e
blocchi di JSON, e quelli venivano schiacciati in un terzo di uno schermo largo
con margini vuoti da entrambi i lati.

### Gli allegati di immagine sono un permesso esplicito di strumento

`browser.screenshot` salva un file; `image.send` lo allega alla risposta
corrente. Il secondo è una concessione separata, inclusa nel template
web-navigator. Lo strumento fa un'istantanea del PNG in
`agents/<id>/attachments/<opaque-id>.png` con una directory 0700 e un
file 0600. Sovrascrivere in seguito lo screenshot originale non cambia una risposta
precedente. `ToolContext.lAttachments` porta i riferimenti a
`AgentRun.fRecordChatAnswer` o al suo rapporto di fallimento o di esecuzione.

Solo l'esecutore legge quei file privati per il processo web. Il suo verbo
`read_chat_attachment` richiede un riferimento nella chat registrata di
quell'agente, apre ogni componente di directory senza seguire i link, e
verifica che l'immagine sia un file regolare di proprietà dell'agente. Legge i
PNG a blocchi di 1 MiB; le risposte in base64 restano sotto il limite RPC
esistente anche per un allegato di 50 MiB. L'endpoint HTTP autenticato
trasmette i byte con `private, no-store`. Il frontend costruisce gli URL locali
delle immagini a partire dagli ID, mai da URL forniti dal modello.

Telegram usa [sendPhoto](https://core.telegram.org/bots/api#sendphoto) per le
immagini idonee e [sendDocument](https://core.telegram.org/bots/api#senddocument)
per le catture alte o grandi, con il PNG originale. Il file privato viene
caricato come dati multipart; non servono né un URL pubblico né l'accesso
dell'agente alle credenziali del bot. `telegram_deliveries` registra le parti
di testo e di immagine confermate per ogni turno in attesa. I nuovi tentativi
riprendono dalla parte mancante, e rimuovere la riga in attesa cancella quei
punti di controllo. I fallimenti permanenti vengono segnalati all'utente.
Entrambe le caselle in arrivo confrontano le marche temporali UTC di SQLite con
l'ora Unix; interpretarle come ora locale faceva scadere le consegne recenti
durante l'ora legale.

### Nessun passo di build

Il frontend è fatto di template Jinja2, CSS semplice e JavaScript semplice. Il
bersaglio di produzione è una macchina Debian o Alpine self-hosted; un deploy
che ha bisogno di una toolchain
Node per cambiare un foglio di stile è un deploy che marcisce. Per la stessa
ragione `/api/doc/` rende la propria specifica OpenAPI invece di caricare
Swagger UI da una CDN: un server della LAN potrebbe non avere accesso a
internet verso l'esterno, e una documentazione che fallisce senza di esso
fallisce proprio quando qualcuno sta facendo debug.

---

### Trascrizione audio

Quando avvia i servizi OpenRC, il programma di installazione chiude i descrittori 3 e 4 sui comandi `rc-service`. Sono le sue pipe stdout/stderr SSH salvate: si è osservato che `supervise-daemon` le tratteneva dopo un'uscita riuscita del programma di installazione. L'output ordinario viene comunque catturato in `install.log`.

`audio_transcription` memorizza un'unica configurazione JSON convalidata in `settings.audio_transcription`. OpenAI, Groq, Mistral e Together usano multipart; Hugging Face e Cloudflare ricevono WAV binario. Riutilizzano `api_keys` senza restituire segreti al browser. FFmpeg limita contenitori, protocolli, dimensione, durata e tempo di esecuzione. L'audio viene diviso in segmenti di 120 secondi (30 secondi per gli endpoint grezzi di Hugging Face e Cloudflare, per non dipendere dalle opzioni di generazione per audio lunghi); whisper.cpp e la decodifica girano come `boa`, senza shell e senza ripiego automatico su un altro provider.

`audio_inbox` rende persistenti destinazione, impostazioni e trascrizione in SQLite. Un unico thread in background, protetto da un lock di processo, in `boa-channel-telegram` recupera la sua coda dopo un riavvio. Un ID di turno riservato permette all'esecutore di confermare un invio ripetuto prima di verificare se l'agente è occupato. Marcare il lavoro come inviato e inserire `telegram_pending` avvengono in un'unica transazione. L'audio privato vive in `/opt/boa/audio/` (0700, di proprietà di boa), richiede sia l'accesso sia un riferimento di chat corrispondente per la riproduzione, e viene rimosso quando vengono svuotati i turni di chat completati.

Entrambi i programmi di installazione compilano whisper.cpp v1.9.4 dopo aver verificato lo SHA-256 dell'archivio dei sorgenti e scaricano `base`. `whisper_models.json` contiene tutti i 30 nomi ufficiali, le dimensioni e gli hash. Solo l'esecutore root scarica i modelli tramite `install_whisper_model`; URL e percorsi arbitrari vengono rifiutati. Un file parziale diventa visibile solo dopo la verifica dell'hash. Root è proprietario di `whisper/`; `boa` si limita a leggerlo. Gli aggiornamenti conservano modelli e audio; i backup includono l'audio ma escludono i pesi dei modelli. Un interprete Python mancante viene installato insieme alle dipendenze prima di verificare la versione minima.

### Richieste grezze ai provider e lo spazio di lavoro dell'agente

`AgentRun.fSendRecordedRequest` collega un registratore al provider selezionato
per quella chiamata, comprese le chiamate di riserva e di chiusura. Gli
adattatori basati su requests usano `BaseProvider.fPostJson`, che registra lo
stesso corpo JSON serializzato prima di inviarlo. I client degli SDK di OpenAI
e di Anthropic usano hook di richiesta, catturando il corpo preparato con i
campi dell'SDK e ogni nuovo tentativo. Il registratore non memorizza mai le
intestazioni di autenticazione e non ricostruisce mai una richiesta dalla
cronologia della chat.

`api_calls` scrive un indice in `agents/<id>/api-calls.jsonl` e un corpo
completo `api-call-<id>.json` per richiesta, con modo 0600 nella home privata
dell'agente. La conservazione rimuove le richieste intere oltre le ultime 100.
L'esecutore legge solo file regolari di proprietà di quell'agente, rifiutando
link simbolici e FIFO. I corpi viaggiano a blocchi limitati sul suo socket; la
rotta HTTP autenticata trasmette il loro testo JSON originale sotto `body`. Il
browser formatta i token senza analizzare i numeri, così gli interi grandi e
gli escape delle stringhe sopravvivono intatti.

L'`info.json` protetto memorizza `interface.show_api_calls`, predefinito
false. Controlla solo la visibilità; le richieste vengono registrate che la
scheda sia visibile o nascosta. `dashboard.js` separa le schede della
conversazione dalle schede delle impostazioni e seleziona sempre Chat al
caricamento dell'agente. Interroga i metadati delle richieste solo mentre API
Calls è aperta, caricando i corpi completi quando se ne espandono i dettagli.
Il titolo delle impostazioni identifica l'agente per id; Esegui ora appartiene
allo spazio di lavoro, e l'eliminazione ha un suo pannello dentro Generale.

La casella di composizione è fissata subito sopra la barra di stato e scorre
solo `#vChatLog`. Sulle larghezze desktop `app.css` rende `.app` alta
esattamente una viewport mentre la chat è mostrata
(`.app:has(#vChatPanel:not([hidden]))`) e passa l'altezza lungo una colonna
flex fino a `.chat`, così non c'è nessuno scorrimento di pagina in cui perdere
il modulo. A 820 px e meno la pagina torna a scorrere come un blocco, e
`.chat` è una viewport meno `--status-bar-live-height`, che `api.js:fTrackStatusBarHeight`
mantiene uguale all'altezza reale della barra con un `ResizeObserver` - su un
telefono la barra va a capo su diverse righe, e una stima fissa lasciava la
casella di testo sotto di essa. Non c'è nessuna riga di suggerimento sotto la
casella di composizione: `fSetComposerEnabled` la scrive come seconda riga del
segnaposto (come si comporta Invio, o che l'agente sta lavorando), e
`fFitChatInputToPlaceholder` misura quel segnaposto su un gemello invisibile e
imposta il `min-height` della casella così che non venga mai tagliato. Gira
ogni volta che cambiano il segnaposto o la larghezza della casella di
composizione (`fTrackChatInputWidth`).
Le altezze vengono impostate tramite il CSSOM, mai tramite un attributo
`style`, che la CSP scarterebbe.

### Condivisioni Samba per agente

`agents.dDefaultSambaSettings` definisce condivisione attiva, lettura e
scrittura, visibile nell'elenco, accesso autenticato, e modi 0600/0700 per file
e directory. Le password partono non impostate.
`info.json.samba` è configurazione protetta; la password esiste solo nel
passdb di Samba, privato di root. Va a `smbpasswd` tramite stdin, mai in argv,
nel modello, nell'oggetto restituito dall'API o in `info.json`.

`boa-samba` esegue un smbd isolato sulla TCP 445, con la configurazione e lo
stato nativo in `/opt/boa/samba/`, di proprietà di root, e i file di runtime in
`/run/boa-samba/`. Non ha nessun servizio homes. Il nome di una condivisione
deriva da `fGetAgentSystemUser`; il suo percorso è sempre
`<agent home>/samba`. L'autenticazione usa quell'account, e le operazioni sui
file usano l'uid di quell'agente. L'accesso ospite richiede un'impostazione
esplicita per agente. Il programma di installazione si rifiuta di prendere il
controllo di un'installazione di Samba estranea e disabilita l'istanza
predefinita della distribuzione solo per l'installazione propria di BoA.

L'esecutore crea la cartella dopo aver creato o indicizzato un agente e
rimuove la condivisione e l'account prima di eliminare l'utente. Entrambi i
programmi di installazione riallineano gli agenti esistenti dopo
installazione, aggiornamento o ripristino. Un lock esclusivo su file serializza
le modifiche; `testparm` convalida prima della sostituzione atomica della
configurazione. `smbcontrol` ricarica la configurazione e chiude solo le
connessioni della condivisione modificata. Disattivare la condivisione di un
agente è indipendente dall'interruttore di esecuzione dell'agente.

La preparazione della cartella usa descrittori di directory con `O_NOFOLLOW` e
controlli di proprietà. Samba rifiuta i link dentro la condivisione, e una
guardia preexec di root ricontrolla la radice della condivisione a ogni
connessione. La guardia esegue il codice Python fidato con `-I`, così la
directory di lavoro di un agente non può fornire moduli da importare.

I backup includono i file condivisi tramite il normale archivio della home
dell'agente e le impostazioni tramite il file info protetto. `tdbbackup` fa
un'istantanea del database nativo delle password mentre è in uso; il backup
conserva anche il SID del server. Il ripristino richiede smbd fermo, convalida
un database temporaneo e lo sostituisce invece di fondere le credenziali
attuali. L'esportazione tramite il vecchio formato smbpasswd veniva rifiutata
da alcuni RID di account nativi e non viene usata.
`fVerifyInstallation` legge la modalità delle porte web salvata così che il
ripristino verifichi la vera porta HTTPS, compresa la modalità diretta senza
un flag `--ports` esplicito.

Riferimenti: [opzioni di condivisione di Samba](https://www.samba.org/samba/docs/current/man-html/smb.conf.5),
[strumento di backup TDB](https://www.samba.org/samba/docs/3.6/man-html/tdbbackup.8.html).

### Recupero locale dei documenti

L'etichetta della scheda è `RAG` in tutte le lingue, compresi i ripieghi HTML e JavaScript.

`rag_store` gestisce il catalogo per agente (SQLite WAL, FTS5, documenti,
revisioni e offset di caricamento). I nomi originali sono metadati; i nomi dei
file su disco usano identificatori generati. `rag_extract` legge
PDF/EPUB/TXT/Markdown e invoca Poppler e Tesseract locali per l'OCR. Conserva
le posizioni di pagina e capitolo e verifica le dimensioni espanse degli EPUB
prima del parsing. `rag_embeddings` usa solo `AF_UNIX`, con il fisso
`/run/boa-embeddings/engine.sock`: nessun nome host, proxy o ripiego sul cloud.

Le **Informazioni del documento** modificabili di un documento sono,
nell'ordine in cui le mostra il modulo (`rag_store.lMetadataKeys`, contro cui
verifica anche `fAction`): anno di pubblicazione, titolo, sottotitolo,
autore/i, versione, lingua ed etichette. L'elenco dei documenti mostra il
sottotitolo, quando c'è, subito sotto il titolo. L'anno viene memorizzato come
testo (vuoto o fino a quattro cifre) così che «sconosciuto» resti distinto da
un numero. `rag_store.fMigrate` aggiunge le colonne elencate in
`rag_store.lAddedColumns`, quelle introdotte dopo che i cataloghi esistevano
già (finora `year` e `subtitle`): `CREATE TABLE IF NOT EXISTS` non modifica
mai una tabella esistente, e sia le biblioteche più vecchie sia i backup
ripristinati portano lo schema vecchio. `rag_search.fSource` mette sottotitolo,
anno, autore, versione e lingua su ogni passaggio, così il modello può
distinguere documenti che condividono un titolo, datare e attribuire una
citazione, e soppesare due edizioni in disaccordo, senza una chiamata
`rag.list` in più. I link delle citazioni e la ricerca nella biblioteca tengono
solo il titolo e la posizione: nominano un luogo, e il sottotitolo renderebbe
solo il link più lungo.

`rag_models.json` è il catalogo dei modelli di vettorizzazione: per ognuno il
suo URL fissato e lo SHA-256, le dimensioni, il contesto, il pooling, i
prefissi di query e di passaggio, e le due somiglianze misurate per esso
(`min_support` per la modalità verificata, `min_similarity` per la soglia della
ricerca). Se ne distribuiscono due: EmbeddingGemma 300M Q8 (il `default`; 768
dimensioni, mean pooling) e Qwen3-Embedding 0.6B Q8 (1024 dimensioni,
last-token pooling, un'istruzione in inglese prima di ogni query e niente prima
di un passaggio). Quello in uso è `model` nelle impostazioni di runtime
(`/opt/boa/rag-runtime/settings.json`, scritto da
root e leggibile da ogni agente), letto tramite `rag_settings.fSelectedModel`
e `rag_embeddings.fModel`. `rag_runtime` installa i pesi - il programma di
installazione il modello selezionato, l'esecutore qualsiasi altro su richiesta
(`install_rag_model`, un download alla volta in un thread, con l'avanzamento in
`rag-runtime/status/<id>.json`) - e un file riceve il suo nome solo quando
dimensione e SHA-256 corrispondono. Avvia llama.cpp v0.5.0 con il pooling del
modello e con l'id del modello come `--alias`.
L'accesso alla rete spetta solo all'installazione. Il runtime usa il
tokenizzatore e i prefissi di recupero del modello e rifiuta gli input troppo
grandi. SQLite memorizza testo e vettori; USearch memorizza generazioni HNSW
incrementali. Pubblicare una revisione cambia atomicamente la visibilità nel
catalogo e il nome dell'indice.

C'è un solo motore, quindi il modello si sceglie per tutta la macchina, e il
cambio lo fa l'esecutore root (`rag_exec.fRuntime`): rifiuta pesi che non sono
su disco, salva la scelta, sposta il `min_similarity` di ogni agente ancora
sulla raccomandazione del vecchio modello a quella del nuovo
(`fFollowModelSimilarity`; un valore scelto da qualcuno resta) e riavvia
`boa-embeddings`. Nessun vettore viene considerato affidabile sulla sola base
del file delle impostazioni. `rag_embeddings.fEmbed` chiede al motore quale
modello serve (`/v1/models`, l'alias) prima di vettorizzare, e solleva
`EngineUnavailable` quando non è quello atteso o quando un vettore ha il numero
sbagliato di dimensioni; un lavoro di indicizzazione passa il modello con cui è
partito, così un cambio a metà ferma il lavoro invece di mescolare due spazi
vettoriali in una sola revisione. Ogni documento registra l'impronta del
modello dietro la sua revisione pubblicata (`documents.model`). Al passaggio
successivo `rag_worker.fWork` vede che il modello della biblioteca non è quello
selezionato (`fFollowNewModel`): scarta i frammenti delle revisioni non
finite, rimette in coda ogni documento indicizzato con un altro modello e
dimentica l'indice. Le revisioni pubblicate restano. Finché non arriva il suo
turno, un documento viene trovato solo da FTS5: `fSearch` costruisce i ranghi
vettoriali solo dai documenti del modello in uso - tramite il nuovo indice, o
confrontando i loro vettori memorizzati uno per uno finché l'indice non c'è - e
aggiunge un `notice` che dice quanti documenti sono in attesa. Lo stesso
ripiego per parole chiave risponde a una ricerca mentre il motore si riavvia.
`rag_verify` fissa un solo modello per entrambi i lati del suo confronto e
prende la sua soglia da quel modello.

`boa-rag` gira come boa e chiede all'esecutore esistente di lanciare comandi di
worker fissi. `rag_exec` abbassa UID/GID prima di qualsiasi operazione su
documenti o su SQLite; root non analizza mai un libro né apre il catalogo di un
agente. I worker usano un lock del sistema operativo, limiti di risorse e stati
persistenti. Le RPC di caricamento sono blocchi da 256 KiB, quelle di download
blocchi da 1 MiB; i libri interi non attraversano mai il protocollo
dell'esecutore come un unico messaggio. Il worker mantiene ricercabile la
revisione precedente e riprende i frammenti completati dopo un'interruzione.
Le impostazioni restano nella configurazione protetta dell'agente.

Un'interruzione del motore non è un errore del documento. `rag_embeddings`
solleva `EngineUnavailable` (un `ValueError`) quando il socket fallisce o il
motore risponde 503 mentre carica il modello; qualsiasi altro rifiuto resta un
semplice `ValueError`. `fIndexDocument` intercetta a parte l'interruzione: il
documento torna a `queued` con la STESSA revisione, conserva ogni frammento già
vettorizzato e mostra il motivo finché un lavoro non riparte. Il comportamento
di prima - `error` e i frammenti della revisione eliminati - perdeva ore di un
libro grande a ogni `--update`, perché il programma di installazione ferma
`boa-embeddings` mentre un worker lanciato da `boa-exec` è ancora in
esecuzione. `fWork` sonda il motore (`fIsAvailable`) prima di avviare ogni
documento in coda e termina il lotto in caso di interruzione; altrimenti ogni
passaggio dello scheduler, ogni 5 secondi, estrarrebbe o farebbe l'OCR
dell'intero documento solo per fermarsi al suo primo frammento.

`rag_search` combina i ranghi di FTS5 e quelli semantici; le ricerche filtrate
valutano il sottoinsieme selezionato. Il runner recupera prima della chiamata
di risposta e concede i tre strumenti RAG di sola lettura solo quando il RAG è
attivo. Le fonti sono limitate dal budget di testo configurato e da una stima
prudente dei token dell'esecuzione. I marcatori di citazione si risolvono solo
contro fonti effettivamente restituite durante l'esecuzione. Il provider della
risposta può essere remoto: l'elaborazione solo locale si applica alla
vettorizzazione.

Le tre modalità di risposta differiscono in ciò che impone il RUNNER, non solo
in ciò che dice il prompt. `mixed` permette al modello di aggiungere conoscenze
generali. In `documental` e `verified` (`runner.lRagModesThatSearch`) il
modello deve chiamare `rag.search` da sé: `fCheckRagAnswer` rimanda indietro,
una volta, una risposta finale data senza averla chiamata
(`cRagSearchFirstPrompt`). La ricerca propria del runner è l'ultimo messaggio
dell'utente parola per parola, e in una conversazione («e nella seconda
edizione?») non trova niente dove la query del modello, scritta avendo davanti
tutta la conversazione, trova qualcosa. Per la stessa ragione una ricerca vuota
non termina più l'esecuzione documentale prima che venga interpellato il
modello; la garanzia si è spostata alla fine: `fFinishRagAnswer` sostituisce
con una frase fissa la risposta di un'esecuzione che non ha recuperato nessun
passaggio. `tool_choice` non viene usato per forzare la ricerca: dei 29
adattatori alcuni mandano `auto`, Cohere non manda niente e Mistral usa `any`,
quindi solo il runner può imporla a ogni provider.

`verified` aggiunge `rag_verify`. La risposta viene tagliata in unità -
paragrafi, e ogni voce di elenco per conto suo, con un blocco di codice
delimitato attaccato al paragrafo che lo precede e confrontato insieme a esso
(l'introduzione di un esempio da sola non dice quasi niente, e per questo
venivano rimossi esempi fedeli); sono esenti i titoli, le etichette brevi che finiscono con «:» e i separatori. Un'unità
ha bisogno di un `[rag:REF]` tra i passaggi recuperati nell'esecuzione e, a
meno che non sia un semplice riferimento, deve essere vicina a uno di essi:
l'unità vettorizzata come query contro i passaggi vettorizzati come documenti,
la stessa distanza che usa la ricerca, al `min_support` del modello (0,36 per
EmbeddingGemma, 0,44 per Qwen3-Embedding). La prima risposta che non supera la
verifica torna indietro una volta con le unità che non la superano
(`fBuildCorrectionPrompt`); dopo di che queste vengono rimosse e una riga
localizzata dice quante sono. Se non resta niente di sostenuto si dà la frase
fissa; un motore che non si può raggiungere trattiene la risposta (fail
closed). Le frasi fisse (`rag_verify.dFixedTexts`) sono nella lingua in cui al
prompt di sistema è stato detto di rispondere, riconosciuta dalla sua riga in
`dAnswerLanguageLines`, altrimenti in inglese. Il limite del controllo è
misurato e scritto accanto al controllo. Su 138 paragrafi fedeli e 2.652
citazioni a passaggi di un altro argomento, nessuna soglia separa i due gruppi
con nessuno dei due modelli; quelle in uso rimuovono circa il 6% dei paragrafi
fedeli (soprattutto voci di elenco brevi e riassunti di una riga) e lasciano
passare meno dell'1% di quelle citazioni sbagliate. Una citazione a un
passaggio sullo stesso argomento passa circa un quarto delle volte, e un
paragrafo che contraddice il suo passaggio ottiene un punteggio come uno
fedele: ciò che il controllo intercetta è una citazione a un passaggio che
parla d'altro, e un paragrafo senza fonte.

Il backup crea istantanee sotto cartelle madri di staging di proprietà di
root, lascia che il figlio dell'agente faccia un backup di SQLite e crei hard
link ai suoi file immutabili selezionati, poi archivia quell'istantanea. Questo
mantiene coerenti le generazioni WAL e HNSW ed evita che root percorra un
albero di istantanee che l'agente può scambiare. Il ripristino annulla i
caricamenti parziali e rimette in coda le indicizzazioni interrotte. Le
impronte degli indici restano disponibili per le ricostruzioni.

## 2. Mappa dei moduli

| Modulo | Percorso | Responsabilità | Dipende da | Usato da |
|---|---|---|---|---|
| `audio_transcription` | `backend/core/audio_transcription.py` | Impostazioni vocali e motori di riconoscimento | db, api_keys, whisper_runtime | audio_inbox, api |
| `audio_inbox` | `backend/core/audio_inbox.py` | Coda persistente, instradamento, nuovi tentativi e riproduzione privata | db, exec_client, audio_transcription | telegram_listener, api |
| `whisper_runtime` | `backend/core/whisper_runtime.py` | Catalogo, stato e download verificati dei modelli | paths, whisper_models.json | programma di installazione, exec_daemon, api |
| `settings_audio.js` | `frontend/static/js/settings_audio.js` | Modulo dell'audio, download dei modelli e avanzamento | api.js, i18n.js | settings.js, settings_audio.html |
| `rag_store` | `backend/core/rag_store.py` | Catalogo, caricamenti, revisioni e istantanee | `rag_settings` | `rag_worker, rag_search` |
| `rag_extract` | `backend/core/rag_extract.py` | Estrazione locale di PDF/EPUB/testo e OCR | `rag_embeddings, pypdf, EbookLib` | `rag_worker` |
| `rag_embeddings` | `backend/core/rag_embeddings.py` | Tokenizzatore e client di vettorizzazione sul socket locale; rifiuta un vettore di qualsiasi modello che non sia quello atteso | `rag_settings` | `rag_extract, rag_search, rag_worker, rag_verify` |
| `rag_search` | `backend/core/rag_search.py` | Ricerca ibrida, pubblicazione HNSW e citazioni | `rag_store, usearch, numpy` | `runner, tools` |
| `rag_worker` | `backend/core/rag_worker.py` | Lavori di indicizzazione persistenti di proprietà dell'agente | `rag_store, rag_extract, rag_search` | `rag_exec` |
| `rag_verify` | `backend/core/rag_verify.py` | Verifica ogni paragrafo di una risposta contro i passaggi che cita; le frasi fisse del RAG in 15 lingue | `rag_embeddings` | `runner` |
| `rag_exec` | `backend/core/rag_exec.py` | Abbassamento dei privilegi e comandi fissi dei worker | `paths, rag_settings` | `exec_daemon` |
| `rag_runtime` | `backend/core/rag_runtime.py` | Installazione verificata e download dei modelli, motore locale, stato e preparazione del ripristino | `rag_settings, rag_embeddings` | `installers, boa-embeddings, rag_exec, exec_daemon` |
| `rag_models.json` | `backend/core/rag_models.json` | I modelli di vettorizzazione: pesi, hash, pooling, prefissi e le somiglianze misurate per ciascuno | — | `rag_settings` |
| `rag_scheduler` | `backend/core/rag_scheduler.py` | Interrogazione equa della coda | `agents, exec_client` | `boa-rag` |
| `paths` | `backend/core/paths.py` | Ogni percorso del filesystem e la convalida degli id degli agenti | — | tutto |
| `db` | `backend/core/db.py` | Connessioni SQLite ed entrambi gli schemi | `paths` | `agents`, `kanban`, `auth`, `bootstrap` |
| `agents` | `backend/core/agents.py` | Modello dell'agente, `info.json` (comprese le impostazioni di Samba), indice degli agenti, hashing dei token | `db`, `paths` | `exec_daemon`, `agent_api`, `api` |
| `bootstrap` | `backend/core/bootstrap.py` | Inizializzazione della prima esecuzione | `agents`, `db`, `paths` | programma di installazione |
| `exec_protocol` | `backend/core/exec_protocol.py` | Protocollo di trasmissione ed elenco dei verbi | — | `exec_daemon`, `exec_client`, `agent_api` |
| `exec_daemon` | `backend/core/exec_daemon.py` | Il demone privilegiato (root) | `agents`, `paths`, `run_journal`, `api_calls`, `samba` | servizio `boa-exec` |
| `exec_client` | `backend/core/exec_client.py` | Client del precedente | `exec_protocol`, `paths` | `web/api` |
| `agent_api` | `backend/core/agent_api.py` | Il demone con cui parlano gli agenti | `agents`, `kanban`, `channels` | servizio `boa-agent-api` |
| `agent_api_client` | `backend/core/agent_api_client.py` | Client del precedente | `agent_api`, `exec_protocol` | gli strumenti distribuiti |
| `runner` | `backend/core/runner.py` | Un'esecuzione di un agente: il ciclo e i suoi tetti | `providers`, `tool_registry`, `run_journal`, `api_calls` | cron, `exec_daemon` |
| `run_journal` | `backend/core/run_journal.py` | `runs.jsonl` per agente | `paths` | `runner`, `exec_daemon` |
| `api_calls` | `backend/core/api_calls.py` | Corpi esatti delle richieste, indice privato, conservazione e letture limitate | `paths`, `run_journal` | `runner`, `exec_daemon` |
| `dashboard.js` | `frontend/static/js/dashboard.js` | Spazio di lavoro Chat/API Calls, impostazioni dell'agente e resa differita delle richieste | `api.js`, `jsonhighlight.js`, `markdown.js` | `dashboard.html` |
| `chat` | `backend/core/chat.py` | `chat.jsonl` per agente e la conversazione riproposta al modello | `paths` | `runner`, `exec_daemon` |
| `memory` | `backend/core/memory.py` | `memory.md` per agente, limite di caratteri configurabile e scritture complete; caricata nel prompt di sistema di ogni esecuzione | `agents`, `paths` | `runner`, `exec_daemon`, `web/api`, strumenti |
| `skills` | `backend/core/skills.py` | Le procedure condivise in `/opt/boa/skills/`, una directory ciascuna. Analizza `SKILL.md`, costruisce l'indice che va nel prompt, e dice quali competenze di un agente esistono ancora | `paths` | `runner`, `exec_daemon`, `web/api`, `skill.read` |
| `provider_models` | `backend/core/provider_models.py` | Cataloghi dei modelli da `config/providers/*.json` | `paths` | `web/api` |
| `api_keys` | `backend/core/api_keys.py` | Le chiavi condivise dei provider in `config/apikeys/*.key`, scritte 0600 in una directory 0700. Non restituisce mai una chiave al browser, solo se ce n'è una memorizzata e i suoi ultimi quattro caratteri | `paths` | `agent_api`, `web/api` |
| `tool_registry` | `backend/core/tool_registry.py` | Scoperta, permessi e smistamento degli strumenti | `paths` | `runner`, `web/api` |
| `attachments` | `backend/core/attachments.py` | Istantanee PNG private, ID opachi, proprietà dei file verificata e letture limitate | `paths` | `image_send`, `exec_daemon`, `exec_client`, `telegram_listener` |
| `image_send` | `backend/tools/image_send.py` | Allega alla risposta un PNG di proprietà dell'agente tramite il contesto dello strumento | `attachments`, `tool_registry` | `runner` |
| `public_url` | `backend/core/public_url.py` | Se un URL dato a un agente si risolve in un indirizzo pubblico. Espresso in positivo con `is_global` più un rifiuto esplicito del multicast, perché un elenco di intervalli da rifiutare è un elenco da cui dimenticarne uno - e 100.64.0.0/10 era stato dimenticato | — | `web.fetch`, `rss.fetch`, `browser` |
| `agent_scripts` | `backend/core/agent_scripts.py` | Gli script che un agente scrive per sé, e le righe di cron che li eseguono. Convalida nomi e pianificazioni, e non riscrive mai la riga di risveglio | `paths` | `script.*`, `cron.*` |
| `kanban` | `backend/core/kanban.py` | La bacheca e la sua cronologia | `db` | `agent_api`, `web/api` |
| `channels` | `backend/core/channels.py` | Telegram, Discord, Mattermost, X. Invio per tutti e quattro; lettura per i due a cui si può rispondere | `paths`, `telegram_html`, `discord_markdown` | `agent_api`, `web/api`, entrambi i listener |
| `agent_routing` | `backend/core/agent_routing.py` | Ciò che entrambi i listener fanno allo stesso modo: l'elenco degli agenti, la lettura del nome di un agente da un messaggio, la risposta chiusa di un turno, il rapporto di stato | `agents`, `chat`, `exec_client`, `system_info` | `telegram_listener`, `discord_listener` |
| `providers.base` | `backend/providers/base.py` | Interfaccia degli adattatori e forma neutra dei messaggi | — | ogni adattatore |
| `providers.factory` | `backend/providers/factory.py` | Nome del provider → classe dell'adattatore | `providers.base` | `runner`, `web/api` |
| `providers.openai_dialect` | `backend/providers/openai_dialect.py` | La richiesta chat/completions che condividono gli adattatori del dialetto OpenAI; le stranezze restano in ciascun adattatore | `providers.base` | la maggior parte degli adattatori |
| `providers.*` | `backend/providers/<name>.py` | Un adattatore per provider | `providers.base`, `providers.openai_dialect` | `factory` |
| `web.server` | `backend/web/server.py` | Factory di Flask, chiave di sessione, intestazioni di sicurezza | `db`, `web.*` | gunicorn |
| `deploy/haproxy/boa.cfg` | `deploy/haproxy/boa.cfg` | Terminazione TLS, PROXY protocol, 11080 → 11443 | — | servizio `boa-proxy` |
| `web.auth` | `backend/web/auth.py` | Accesso, sessioni, limitazione di frequenza | `db` | `web.api`, `web.views` |
| `web.api` | `backend/web/api.py` | Tutto ciò che sta sotto `/api/admin/` | `exec_client`, `kanban`, `channels` | browser |
| `web.api_doc` | `backend/web/api_doc.py` | Specifica OpenAPI e la sua pagina. Annota la specifica con chiavi i18n solo per la pagina, mai per `openapi.json` | `channels`, `providers.factory` | browser |
| `web.views` | `backend/web/views.py` | Le pagine HTML | `web.auth` | browser |
| `buzzer` | `backend/core/buzzer.py` | Sorveglia la bacheca e avvia un'esecuzione quando una scheda scade | `kanban`, `exec_client` | servizio `boa-buzzer` |
| `telegram_listener` | `backend/core/telegram_listener.py` | Fa long poll su Telegram, instrada ogni messaggio a un agente, rimanda indietro la risposta | `channels`, `exec_client`, `telegram_inbox` | servizio `boa-channel-telegram` |
| `telegram_inbox` | `backend/core/telegram_inbox.py` | Quale agente ha detto che cosa su Telegram, e a quali domande si sta ancora rispondendo. La scadenza viene calcolata in UTC | `db` | `telegram_listener`, `agent_api` |
| `discord_listener` | `backend/core/discord_listener.py` | Interroga a intervalli un canale Discord, instrada ogni messaggio a un agente, rimanda indietro la risposta | `agent_routing`, `channels`, `exec_client`, `discord_inbox` | servizio `boa-channel-discord` |
| `discord_inbox` | `backend/core/discord_inbox.py` | Le stesse due tabelle per Discord. Separate da quelle di Telegram: uno snowflake è una stringa, e un listener non deve poter rispondere alle domande dell'altro. La scadenza viene calcolata in UTC | `db` | `discord_listener`, `agent_api` |
| `discord_markdown` | `backend/core/discord_markdown.py` | Markdown in ciò che Discord rende, tagliato in messaggi di 2000 caratteri. Le tabelle diventano blocchi delimitati; un blocco dentro cui cade un taglio viene chiuso e riaperto | `telegram_html` (i pattern dei blocchi) | `channels` |
| `discord_texts` | `backend/core/discord_texts.py` | Le tre frasi che Discord dice in modo diverso. Tutto il resto ricade su `telegram_texts`, così un solo catalogo serve entrambi i bot | `telegram_texts` | `discord_listener` |
| `browser` | `backend/core/browser.py` | Il browser condiviso e il profilo proprio di questo agente. Un solo handle per tutta la durata di un'esecuzione, chiuso da `atexit`. Porta la politica di rete per cui passa ogni richiesta | `paths`, `public_url` | i cinque strumenti `browser.*` |
| `telegram_html` | `backend/core/telegram_html.py` | Markdown nei quattordici tag che Telegram accetta. Stessi pattern di `markdown.js`, così entrambi i renderer concordano su che cosa sia il markdown | — | `channels` |
| `telegram_texts` | `backend/core/telegram_texts.py` | Ciò che il bot dice da sé, nella lingua su cui è stata impostata l'installazione | `db` | `telegram_listener` |
| `markdown.js` | `frontend/static/js/markdown.js` | Rende la risposta di un agente come nodi DOM, mai come markup | — | `dashboard.js` |
| `jsonhighlight.js` | `frontend/static/js/jsonhighlight.js` | Formatta JSON grezzo senza arrotondare i numeri e lo colora usando nodi DOM sicuri | — | `api_doc.html`, `dashboard.html` |
| `themes` | `backend/core/themes.py` | Elenca i fogli di stile in `frontend/themes/` e ne legge le intestazioni | `paths` | `web/api`, `web/views` |
| `agent_templates` | `backend/core/agent_templates.py` | Scarica il repository dei template (impostazioni `templates_repo_url`, `templates_repo_branch`) come un unico `.tar.gz`, lo tiene in cache cinque minuti ed elenca o legge i suoi template | `agent_package`, `db` | `web/api` |
| `agent_package` | `backend/core/agent_package.py` | La forma portabile di un agente: legge un `.zip`, un archivio di repository o una cartella, e verifica tutto prima che esista un agente | `agent_home`, `agents`, `memory`, `rag_settings`, `rag_store`, `skills` | `agent_templates`, `agent_io` |
| `agent_io` | `backend/core/agent_io.py` | Installa un pacchetto, esegue in background le importazioni di `.zip` con `job.json`, trasmette in streaming le esportazioni | `agent_package`, `exec_client`, `tool_registry` | `web/api`, `web/agent_io_api` |
| `agent_home` | `backend/core/agent_home.py` | Elenca, legge e scrive i file della home di un agente come l'agente; il verbo `agent_home` dell'esecutore | `paths` | `exec_daemon`, `agent_package` |
| `agent_io_api` | `backend/web/agent_io_api.py` | `/agent-imports/...` e `/agents/<id>/export...` | `agent_io` | `server` |
| `agent_export.js` | `frontend/static/js/agent_export.js` | La scheda Esporta: che cosa aggiunge ogni opzione, e il link di download | `api.js` | `dashboard.html` |
| `mailbox` | `backend/core/mailbox.py` | IMAP e SMTP per la casella di posta configurata. Custodisce le credenziali così che gli agenti non le abbiano mai. Nomina un messaggio per UID e UIDVALIDITY, mai per la sua posizione nella cartella | `db` | `agent_api` |
| `theme.js` | `frontend/static/js/theme.js` | Aggiunge il foglio di stile del tema scelto, dall'head, prima del primo disegno | — | ogni pagina |
| `night-high-contrast.css` | `frontend/themes/night-high-contrast.css` | Riempie di grigio l'agente selezionato e disegna le schede selezionate con un contorno chiuso unito alla linea di base | `app.css` | `theme.js` |
| `settings.js` | `frontend/static/js/settings.js` | Carica le schede principali delle impostazioni con selettori limitati alla propria barra delle schede; `fRenderChannelForms` marca i canali configurati con `data-state="good"`, condividendo lo stile dello stato delle chiavi API e il `--colour-ok` del tema | `api.js`, `i18n.js`, `tools.js`, `app.css` | `settings.html` |
| `tools.js` | `frontend/static/js/tools.js` | Carica il catalogo dentro Impostazioni → Strumenti; tiene la sottoscheda nel parametro `family` dell'URL e ne aggiorna le etichette quando si torna da Interfaccia | `api.js`, `i18n.js` | `settings.js`, `settings_tools.html` |
| `app.css` | `frontend/static/css/app.css` | La classe `system-table` condivide un layout a due colonne, con il 35% per le etichette, così i valori della macchina e gli stati dei servizi si allineano; `.chat-attachment img` riempie il 100% della larghezza del testo con altezza automatica e senza limite; `.chat-audio` si adatta alla larghezza del messaggio e il suo titolo eredita il colore del testo del messaggio | — | `settings.html`, `dashboard.html` |
| `system_info` | `backend/core/system_info.py` | Stato della macchina e nomi dei servizi per il sistema di init in esecuzione | `paths` | `web/api`, `agent_routing` |
| `samba` | `backend/core/samba.py` | Ciclo di vita delle condivisioni, convalida, credenziali native, cartelle protette e backup | `agents`, `paths`, comandi di Samba | `exec_daemon`, programmi di installazione |
| `samba.js` | `frontend/static/js/samba.js` | Modulo Samba caricato su richiesta, campo segreto e istantanea per agente | `api.js`, `dashboard.js` | `dashboard.html` |

---

## 3. Indice dei simboli chiave

Solo simboli pubblici e portanti. I numeri di riga si spostano; il file e il
comportamento sono ciò di cui fidarsi.

### Percorsi e identità

| Simbolo | File:riga | Che cosa fa |
|---|---|---|
| `fNormalizeAgentId` | `backend/core/paths.py:164` | Convalida un id di agente e lo completa con zeri a sinistra. **Ogni percorso costruito a partire da un input dell'utente passa per qui.** Solleva un'eccezione per qualsiasi cosa fuori da 0–999 |
| `fGetAgentHome` | `backend/core/paths.py:179` | `/opt/boa/agents/xxx` |
| `fReadAgentOwnedFile` | `backend/core/paths.py:401` | Come root legge un file della home di un agente: sul descrittore aperto, regolare e dell'agente o rifiutato, mai oltre un limite. Il giornale, la chat e la memoria passano tutti per qui |
| `fGetAgentApiTokenPath` | `backend/core/paths.py:485` | Dove vive il token API di un agente |

### Agenti

| Simbolo | File:riga | Che cosa fa |
|---|---|---|
| `fValidateAgentName` | `backend/core/agents.py:71` | 2–40 caratteri, nessun metacarattere di shell |
| `fGetNextFreeAgentId` | `backend/core/agents.py:137` | L'id libero più basso secondo il filesystem, a partire da 001 |
| `fBuildAgentInfo` | `backend/core/agents.py:150` | L'`info.json` di un agente nuovo, con valori predefiniti prudenti |
| `fWriteAgentInfo` | `backend/core/agents.py:219` | Scrittura atomica che conserva la proprietà 0600 |
| `fHashApiToken` | `backend/core/agents.py:256` | SHA-256; il token in chiaro non viene mai memorizzato |
| `fFindAgentByApiToken` | `backend/core/agents.py:301` | Trasforma un token in un'identità |

### Il demone privilegiato

| Simbolo | File:riga | Che cosa fa |
|---|---|---|
| `fIsPeerAllowed` | `backend/core/exec_daemon.py:106` | Solo root e `boa`, verificato per connessione |
| `fRunPrivilegedCommand` | `backend/core/exec_daemon.py:122` | Esegue una lista di comando senza shell, facoltativamente come un altro utente |
| `fVerbCreateAgent` | `backend/core/exec_daemon.py:396` | Crea utente, home, configurazione, token; applica strumenti, limiti, interruttore e impostazioni `rag` convalidate di un template; **fa il rollback a qualsiasi fallimento** |
| `fStartRunner` | `backend/core/exec_daemon.py:304` | L'unico posto in cui si avvia un runner come l'agente. Il messaggio della chat o il prompt della scheda va sul suo standard input, mai sulla riga di comando |
| `fWatchRunner` | `backend/core/exec_daemon.py:255` | Aspetta un'esecuzione: ferma il suo scope, e registra la fine di una che è stata uccisa |
| `fVerbWriteCrontab` | `backend/core/exec_daemon.py:780` | Installa un crontab come l'utente dell'agente |
| `fListRunningAgentIds` | `backend/core/exec_daemon.py` | Una sola scansione di `/proc` che nomina ogni agente con un'esecuzione in corso. Sostiene sia `only_if_idle` sia l'anello rotante della barra laterale |
| `dVerbHandlers` | `backend/core/exec_daemon.py` | La tabella chiusa dei verbi. L'intera superficie privilegiata sono queste dieci righe |

### L'API degli agenti

| Simbolo | File:riga | Che cosa fa |
|---|---|---|
| `fAuthenticate` | `backend/core/agent_api.py:121` | Token **e** `SO_PEERCRED` devono concordare |
| `fAgentMayUseKanban` | `backend/core/agent_api.py` | Se la bacheca è accesa e l'agente ha almeno uno strumento kanban. La metà grossolana |
| `fRequireKanbanTool` | `backend/core/agent_api.py` | Un verbo, uno strumento, per nome. Prima ogni gestore faceva la domanda grossolana, quindi `kanban.list_cards` - una lettura - arrivava a `fDeleteCard` per un agente che metteva da sé la richiesta sul socket |
| `fRequireOwnCard` | `backend/core/agent_api.py:283` | Un agente può cambiare solo le schede che ha creato o di cui è proprietario |
| `fVerbChannelWrite` | `backend/core/agent_api.py` | Invia per conto dell'agente, anteponendo il suo vero nome |

### Il ciclo dell'esecuzione

| Simbolo | File:riga | Che cosa fa |
|---|---|---|
| `AgentRun` | `backend/core/runner.py:336` | Una conversazione limitata |
| `fCheckCeilings` | `backend/core/runner.py` | Restituisce quale tetto ha fermato l'esecuzione, o vuoto per continuare |
| `fSecondsLeft` | `backend/core/runner.py` | Il tempo che resta prima della scadenza dell'esecuzione, su un orologio monotono. Ogni chiamata al provider e ogni strumento ricevono ciò che resta, non l'intero tetto |
| `fTakeRunLock` | `backend/core/runner.py` | Un flock su `<home>/run.lock`, tenuto per tutta la durata del processo. L'unico controllo che fa anche un'esecuzione avviata da cron |
| `fTrimToByteBudget` | `backend/core/exec_protocol.py` | Le voci più recenti che stanno in un budget di byte, e quante ne sono state scartate. Contato in byte, perché un numero di righe non è una dimensione |
| `fRunWithLimits` | `backend/tools/bash_run.py` | Esegue un comando con un tetto di byte applicato MENTRE produce output, e una scadenza che uccide l'intero gruppo di processi |
| `fAskForClosingAnswer` | `backend/core/runner.py` | Dopo un tetto, chiede una volta, senza strumenti, la risposta che gli era stato impedito di dare |
| `fExecute` | `backend/core/runner.py:503` | Il ciclo: chiedere, eseguire gli strumenti, restituire i risultati, fermarsi |
| `fSelectAllowedTools` | `backend/core/runner.py:319` | Trattiene gli strumenti kanban quando l'agente li ha spenti |
| `fReadStdinArguments` | `backend/core/runner.py:988` | La metà del runner in tutto questo: legge il testo dallo standard input, con un limite, e rifiuta un messaggio di chat vuoto |
| `fApplyResourceLimits` | `backend/core/runner.py:1069` | Abbassa i limiti del kernel dell'esecuzione stessa prima che venga avviato qualsiasi cosa: processi, file core, dimensione dei file |
| `fRecordChatAnswer` | `backend/core/runner.py` | Riscrive la risposta quando l'esecuzione ha un turno da chiudere (`vWritesToChat`) |
| `fRecordChatFailure` | `backend/core/runner.py` | Chiude il turno quando nient'altro lo farà, nominando il motivo così che l'interfaccia possa tradurlo |
| `fAppendCardMessage` | `backend/core/chat.py` | Annuncia una scheda scaduta come un turno a sé, con i campi della scheda e nessuna frase |
| `fBuildCardAnnouncement` | `backend/core/buzzer.py` | Ciò che viene detto alla chat: chi l'ha assegnata, e se è stata chiesta subito |

### Strumenti

| Simbolo | File:riga | Che cosa fa |
|---|---|---|
| `fGetContext` | `backend/core/browser.py` | Avvia il browser sul profilo di questo agente, o restituisce quello già in esecuzione |
| `fClose` | `backend/core/browser.py` | Registrato con `atexit`. Senza, ogni esecuzione lascia dietro di sé un Chromium |
| `fIsInstalled` | `backend/core/browser.py` | Se c'è un browser da pilotare, così gli strumenti possono dire che cosa eseguire invece di sollevare un'eccezione |
| `fLoadAllTools` | `backend/core/tool_registry.py:105` | Carica ogni strumento valido; un file rotto viene saltato, non è fatale |
| `fRunTool` | `backend/core/tool_registry.py:138` | Fa rispettare i permessi, restituisce `(text, is_error)`; uno strumento che solleva un'eccezione non uccide mai un'esecuzione |
| `fGetLimit` | `backend/core/memory.py:53` | Legge il limite protetto della memoria per agente, con il valore predefinito storico |
| `fValidateContent` | `backend/core/memory.py:71` | Rifiuta una memoria troppo grande senza scartare testo |
| `fCheckMemoryUpdate` | `backend/web/api.py:127` | Convalida la memoria e il limite proposto prima di qualsiasi scrittura delle impostazioni |
| `fSearch` | `backend/core/rag_search.py:123` | Recupero ibrido con riferimenti alle fonti |
| `fPrompt` | `backend/core/rag_search.py:243` | I passaggi recuperati e la regola della modalità di risposta, aggiunti al prompt di sistema |
| `fVerify` | `backend/core/rag_verify.py:235` | Unità senza una citazione recuperata o diverse da ciò che citano: restituisce il testo conservato e ciò che è stato rimosso |
| `fSplitUnits` | `backend/core/rag_verify.py:163` | Taglia una risposta in paragrafi e voci di elenco, conservando ciò che serve per ricostruirla |
| `fCheckRagAnswer` | `backend/core/runner.py:681` | Rimanda indietro una volta una risposta finale: ancora nessuna ricerca (documentale, verificata) o paragrafi non sostenuti (verificata) |
| `fFinishRagAnswer` | `backend/core/runner.py:704` | Ciò che viene mostrato all'utente: frase fissa senza passaggi, paragrafi non sostenuti rimossi, trattenuta quando non si può verificare |
| `fIndexDocument` | `backend/core/rag_worker.py:32` | Estrae, vettorizza e pubblica una revisione; `False` quando un'interruzione del motore l'ha rimessa in coda |
| `fWork` | `backend/core/rag_worker.py:129` | Lotto di indicizzazione limitato; aspetta senza estrarre mentre il motore è giù |
| `EngineUnavailable` | `backend/core/rag_embeddings.py:11` | Interruzione del motore (guasto del socket o 503), distinta da una richiesta rifiutata |
| `fIsAvailable` | `backend/core/rag_embeddings.py:73` | Sonda economica che il worker esegue prima di ogni documento: il motore risponde, e con il modello in uso |
| `fCheckServedModel` | `backend/core/rag_embeddings.py:68` | `EngineUnavailable` a meno che il `/v1/models` del motore non nomini il modello atteso |
| `fSelectedModel` | `backend/core/rag_settings.py:39` | La voce del catalogo scelta in Impostazioni → RAG, il predefinito quando non ne è salvata nessuna o una sconosciuta |
| `fInstallModel` | `backend/core/rag_runtime.py:76` | Scarica un modello in un file privato e gli dà il nome solo dopo che dimensione e SHA-256 corrispondono |
| `fStartModelDownload` | `backend/core/rag_runtime.py:125` | Mette in coda un download nell'esecutore e ne restituisce subito lo stato |
| `fFollowModelSimilarity` | `backend/core/rag_exec.py:113` | A un cambio di modello, sposta gli agenti ancora sul vecchio `min_similarity` raccomandato a quello nuovo |
| `fFollowNewModel` | `backend/core/rag_worker.py:107` | Rimette in coda ciò che ha indicizzato un altro modello, mantenendo le revisioni pubblicate ricercabili per parole |
| `fMigrate` | `backend/core/rag_store.py:83` | Aggiunge a ogni connessione le `lAddedColumns` che mancano nei cataloghi più vecchi (`year`, `subtitle`) |
| `fAction` | `backend/core/rag_store.py:270` | Informazioni del documento, reindicizzazione, annullamento ed eliminazione; convalida le chiavi dei metadati e l'anno |
| `fSnapshot` | `backend/core/rag_store.py:334` | Backup coerente di documenti e indice |
| `ToolContext` | `backend/core/tool_registry.py:53` | Ciò che viene detto a uno strumento sul suo chiamante |
| `fStoreImage` | `backend/core/attachments.py` | Copia un PNG dalla home dell'agente in un'istantanea privata |
| `fReadImageChunk` | `backend/core/attachments.py` | Legge al massimo 1 MiB, rifiutando link simbolici, altri proprietari e file speciali |
| `fVerbReadChatAttachment` | `backend/core/exec_daemon.py` | Richiede un riferimento all'allegato nella chat dell'agente richiesto prima di leggere |
| `fGetChatAttachment` | `backend/web/api.py` | Trasmette il PNG a un utente autenticato, senza URL di file pubblico o in cache |
| `fRenderChatAttachments` | `frontend/static/js/dashboard.js` | Mostra le immagini della risposta e un errore quando un'immagine non si può caricare |
| `fSetComposerEnabled` | `frontend/static/js/dashboard.js` | Apre o chiude la casella di composizione e scrive la seconda riga del segnaposto: come si comporta Invio, o che l'agente sta lavorando |
| `fFitChatInputToPlaceholder` | `frontend/static/js/dashboard.js` | Fa crescere la casella di testo finché ci sta tutto il suo segnaposto, misurato su un gemello invisibile |
| `fTrackStatusBarHeight` | `frontend/static/js/api.js` | Mantiene `--status-bar-live-height` uguale all'altezza reale della barra di stato, che il layout della chat su telefono sottrae |
| `fDeliverAnswerParts` | `backend/core/telegram_listener.py` | Riprende la consegna su Telegram dall'ultima parte di testo o immagine confermata |

### Competenze

| Simbolo | File:riga | Che cosa fa |
|---|---|---|
| `fIsValidSkillName` | `backend/core/skills.py:57` | Un nome, mai un percorso. Rifiuta invece di ripulire, come i nomi dei template e dei temi |
| `fParseSkill` | `backend/core/skills.py:77` | L'intestazione `---` e il corpo |
| `fSelectInstalledSkills` | `backend/core/skills.py:194` | I nomi nell'elenco di un agente che esistono ancora su disco. **Ogni percorso verso la funzionalità passa per qui**, così una competenza eliminata non raggiunge mai un prompt |
| `fBuildPromptSection` | `backend/core/skills.py:211` | L'indice: una riga per competenza, solo nomi e descrizioni. `""` quando l'agente non ne ha |
| `fRunTool` | `backend/tools/skill_read.py` | Restituisce un corpo, verificato contro l'`info.json` dell'agente stesso |


### Telegram, nei due sensi

| Simbolo | File:riga | Che cosa fa |
|---|---|---|
| `fReadTelegramUpdates` | `backend/core/channels.py` | Un long poll. La connessione viene fatta verso l'esterno, il che permette a tutto questo di funzionare dietro un NAT senza niente inoltrato |
| `fSendToTelegram` | `backend/core/channels.py` | Invia, e restituisce il `message_id` - l'unica cosa che rende instradabile una risposta successiva |
| `fRedactSecrets` | `backend/core/channels.py` | Rimuove ogni credenziale da un errore o da una riga di log. `str(RequestException)` cita l'URL, e per tre dei quattro canali l'URL **è** la credenziale |
| `fReadConfigForEditing` | `backend/core/channels.py` | Il file di un canale com'è su disco, così salvare una modifica la fonde invece di sostituirlo |
| `fListConfiguredChannels` | `backend/core/channels.py` | Restituisce Discord, Mattermost, Telegram e X in ordine alfabetico, con il loro stato e senza segreti; usato dalle Impostazioni e dai permessi di ogni agente |
| `fRouteMessage` | `backend/core/telegram_listener.py` | Per chi è un messaggio: l'agente a cui si risponde, o quello nominato con @ |
| `fMatchNamedAgent` | `backend/core/telegram_listener.py` | Corrispondenza più lunga su ogni nome conosciuto, perché i nomi degli agenti possono contenere spazi |
| `fIsFromTheConfiguredChat` | `backend/core/telegram_listener.py` | **Tutta l'autorizzazione che c'è.** Qualsiasi cosa da un'altra chat viene scartata senza risposta |
| `fDeliverAnswers` | `backend/core/telegram_listener.py` | Rimanda indietro ogni turno che si è chiuso dall'ultimo passaggio |
| `fRememberMessage` | `backend/core/telegram_inbox.py` | Lega un messaggio inviato all'agente che l'ha inviato, potato alle ultime poche centinaia |
| `fRouteMessage` | `backend/core/telegram_listener.py` | Per chi è un messaggio: l'agente a cui si risponde, quello nominato con @ o /, o quello selezionato |
| `fReadSelectedAgent` | `backend/core/telegram_listener.py` | Con chi è la conversazione, verificato contro l'elenco degli agenti così che un agente eliminato smetta di catturare tutto |
| `fBuildAgentButtons` | `backend/core/telegram_listener.py` | La tastiera inline con cui risponde /agents. Il testo di un pulsante lo sceglie il bot, mentre quello del menu dei comandi no |
| `fBuildStatusReport` | `backend/core/telegram_listener.py` | Ciò che dice /status. Un agente che non riesce a leggere viene elencato dicendolo, mai lasciato fuori |
| `fHandleCallback` | `backend/core/telegram_listener.py` | Un tocco su un pulsante di agente: prima gli si risponde, poi l'agente viene selezionato |
| `fRender` | `backend/core/telegram_html.py` | Markdown nell'HTML di Telegram. I titoli diventano grassetto, gli elenchi punti elenco, le tabelle un blocco a spaziatura fissa - Telegram non ha un tag per nessuna delle tre cose |
| `fEscape` | `backend/core/telegram_html.py` | `&`, `<`, `>`. **Chiamato prima che qualcosa avvolga il testo**, mai dopo |
| `fEscapeAttribute` | `backend/core/telegram_html.py` | Lo stesso più le virgolette doppie, per un href. Altrimenti delle virgolette in un URL chiuderebbero l'attributo e inventerebbero quelli successivi |
| `fRenderWithinLimit` | `backend/core/telegram_html.py` | Accorcia il markdown e rende di nuovo finché l'HTML non ci sta. Tagliare invece l'HTML lascerebbe un tag scritto a metà |

### Discord, nei due sensi

| Simbolo | File:riga | Che cosa fa |
|---|---|---|
| `fReadDiscordMessages` | `backend/core/channels.py` | Un'interrogazione. **Inverte ciò che restituisce Discord**, che è dal più recente: rispondere in quell'ordine farebbe leggere all'agente una conversazione al contrario |
| `fSendToDiscord` | `backend/core/channels.py` | Invia, in tante parti quante ne richiede il limite di 2000 caratteri, e restituisce l'id di ogni parte |
| `fCallDiscord` | `backend/core/channels.py` | Una chiamata. Un 429 con un `retry_after` breve viene atteso dormendo una volta; qualsiasi altro 4xx è `ChannelRejected` |
| `fGetDiscordMode` | `backend/core/channels.py` | `"bot"`, `"hook"` o `""`. Un webhook invia e nient'altro |
| `fReadDiscordBotUser` | `backend/core/channels.py` | Quale bot è questo, scritto nel log una volta per avvio: quando non arriva niente, è la prima domanda |
| `fRenderToMessages` | `backend/core/discord_markdown.py` | Una risposta come l'elenco dei messaggi da inviare per essa |
| `fSplit` | `backend/core/discord_markdown.py` | Taglia tra una riga e l'altra, chiudendo e riaprendo un blocco delimitato dentro cui cade il taglio |
| `fIsFromTheConfiguredChannel` | `backend/core/discord_listener.py` | Ogni messaggio interrogato viene da quel canale per costruzione; verificato comunque, perché «per costruzione» è una proprietà del codice di oggi |
| `fReadCommand` | `backend/core/discord_listener.py` | `!agents`, `!status`, `!help`, e le forme con `/`. Solo come prima parola intera, altrimenti un agente chiamato `status` sarebbe irraggiungibile |
| `fReadMessageText` | `backend/core/discord_listener.py` | Il testo con una menzione del bot tolta dall'inizio: Discord trasforma `@Boa` in `<@123>` prima che chiunque altro lo veda |
| `fStartFromTheNewestMessage` | `backend/core/discord_listener.py` | Da dove parte un'installazione nuova. Un bot acceso oggi pomeriggio non deve rispondere a un mese di canale |
| `fReadAfterId` / `fWriteAfterId` | `backend/core/discord_listener.py` | Il segno, in `config/discord-after`. Uno snowflake, non un contatore |
| `fRememberMessage` | `backend/core/discord_inbox.py` | Lega una parte inviata all'agente che l'ha inviata. Potato per ordine di inserimento, non per id |

### Condivisi da entrambi i listener

| Simbolo | File:riga | Che cosa fa |
|---|---|---|
| `fMatchNamedAgent` | `backend/core/agent_routing.py` | Corrispondenza più lunga su ogni nome conosciuto. I prefissi sono un argomento: Telegram prende `@` e `/`, Discord aggiunge `!` |
| `fBuildStatusReport` | `backend/core/agent_routing.py` | Ciò che dice /status. Prende il catalogo del servizio che chiede e il nome della sua unità, che sono le uniche due cose che cambiano; risolve il nome del servizio del canale per systemd o OpenRC |
| `fFindClosedAnswer` | `backend/core/agent_routing.py` | Ciò che un agente ha detto per chiudere un turno, letto tramite l'esecutore |
| `fListAgentNames` | `backend/core/agent_routing.py` | L'elenco degli agenti, dall'indice: la home di un agente è 0700 e il suo info.json non spetta a un listener aprirlo |

### Gli script e il cron propri di un agente

| Simbolo | File:riga | Che cosa fa |
|---|---|---|
| `fValidateScriptName` | `backend/core/agent_scripts.py` | Verifica un nome invece di ripulirlo: tutto ciò che non è un semplice nome di file viene rifiutato, che è una regola sola invece di una regola più qualunque cosa finisca per fare la pulizia |
| `fValidateSchedule` | `backend/core/agent_scripts.py` | La forma di una pianificazione cron, e l'unica cosa che vale la pena rifiutare: un lavoro che scatta più spesso di quanto qualcuno intendesse |
| `fIsRunnerLine` | `backend/core/agent_scripts.py` | La riga che sveglia l'agente. Mai riscritta da qui: un agente che la eliminasse tacerebbe per sempre senza modo di accorgersene |
| `fAddCronLine` | `backend/core/agent_scripts.py` | Aggiunge una riga che esegue uno degli script dell'agente. Lo script deve esistere prima |
| `fRemoveCronLines` | `backend/core/agent_scripts.py` | Rimuove ogni riga che esegue uno script, e il commento sopra ciascuna |

### Bacheca e canali

| Simbolo | File:riga | Che cosa fa |
|---|---|---|
| `fAddCard` | `backend/core/kanban.py:132` | Scheda e primo evento in un'unica transazione |
| `fMoveCard` | `backend/core/kanban.py:188` | Spostamento più evento nella cronologia |
| `fValidateRunAt` | `backend/core/kanban.py:68` | Accetta `"now"`, un'ora del browser o un'ora memorizzata, e normalizza tutte e tre |
| `fReadRunMode` | `backend/core/kanban.py:100` | Che tipo di ora è stata chiesta: `now`, `at`, o nessuna |
| `fWasRequestedImmediately` | `backend/core/kanban.py` | Se la scheda diceva «subito». Letto da `run_mode`, mai dedotto dall'orologio |
| `fAssignCard` | `backend/core/kanban.py` | Passa una scheda a un altro, registrando chi l'ha passata in `assigned_by` |
| `fAgentOwnsCard` | `backend/core/kanban.py:462` | Creatore **o** assegnatario |
| `fDeleteCard` | `backend/core/kanban.py:480` | Elimina, conservando una riga in `deleted_cards` |
| `fReadMessages` | `backend/core/mailbox.py` | I messaggi più recenti di una cartella, in sola lettura: niente viene segnato come visto |
| `_fParseFolderLine` | `backend/core/mailbox.py` | Una riga LIST come flag, delimitatore e nome. Solleva un'eccezione invece di tirare a indovinare: un elenco illeggibile è un errore, non un account senza cartelle |
| `fListFoldersWithFlags` | `backend/core/mailbox.py` | Ogni cartella con i suoi flag SPECIAL-USE |
| `fFindTrashFolder` | `backend/core/mailbox.py` | Prima `\\Trash`, poi i nomi in nove lingue. `""` significa che non ce n'è nessuna; un fallimento solleva un'eccezione |
| `fIsForwardAllowed` | `backend/core/mailbox.py` | Se un indirizzo è nell'elenco dell'utente. Verificato dove sta la password, mai in un prompt |
| `fListTemplates` | `backend/core/agent_templates.py:134` | Ogni template del repository, riassunto, con il nome che vede l'utente; uno rotto con il suo errore |
| `fReadTemplate` | `backend/core/agent_templates.py:151` | L'origine e il pacchetto verificato di un template, o None; rifiuta un nome che non è un semplice id prima di scaricare |
| `fReadPackage` | `backend/core/agent_package.py:418` | Verifica un pacchetto intero - nomi, agent.json, prompt, memoria, percorsi della home, biblioteca - e lo descrive |
| `fValidateManifest` | `backend/core/agent_package.py:317` | agent.json: solo chiavi conosciute, format 1, pianificazioni, strumenti installati qui, limiti, rag, provider senza chiave |
| `ZipSource` | `backend/core/agent_package.py:84` | Un `.zip`: rifiuta nomi che risalgono, link, cifratura, membri a 200:1 e più di 8 GiB |
| `fReadRepositoryArchive` | `backend/core/agent_package.py:236` | Divide un `.tar.gz` di repository in cartelle di template; salta i link |
| `fInstallPackage` | `backend/core/agent_io.py:60` | Crea l'agente spento, poi la sua memoria, i file della home e la biblioteca; lo elimina di nuovo in caso di fallimento |
| `fStartImport` | `backend/core/agent_io.py:265` | Avvia l'installazione di un `.zip` verificato in un thread, una volta sola, qualunque sia il numero di clic |
| `fExportAgent` | `backend/core/agent_io.py:420` | Produce il `.zip` mentre viene scritto; home e biblioteca trasmesse in streaming |
| `fReadSchedules` | `backend/core/agent_io.py:320` | Solo le righe del crontab che eseguono l'agente, come cinque campi |
| `fValidateSchedule` | `backend/core/agents.py:85` | Cinque campi di cron, una riga, niente che possa essere un comando |
| `fList` | `backend/core/agent_home.py:86` | I file della home che un pacchetto può portare, come l'agente, esclusi quelli di sistema e quelli nascosti |
| `fWrite` | `backend/core/agent_home.py:130` | Scrive un blocco in ordine, senza passare per nessun link, con modo riservato al proprietario |
| `fBroker` | `backend/core/agent_home.py:170` | Esegue un'operazione sulla home come l'agente; il verbo `agent_home` dell'esecutore |
| `fChooseAgentSource` | `frontend/static/js/api.js` | La finestra di dialogo del +: agente vuoto, .zip o template |
| `fImportAgentZip` | `frontend/static/js/api.js` | Caricare a blocchi, verificare, mostrare, confermare, installare, interrogare |
| `fLoadExportPreview` | `frontend/static/js/agent_export.js` | Che cosa aggiungerebbe ogni opzione di esportazione, chiesto ogni volta che si apre la scheda |
| `fSource` | `backend/core/rag_search.py:88` | Un passaggio come lo vedono il modello e le citazioni: riferimento, posizione, titolo, sottotitolo, anno, autore, versione, lingua, testo, link |

### La barra laterale

| Simbolo | File:riga | Che cosa fa |
|---|---|---|
| `fRenderSidebar` | `frontend/static/js/api.js` | Ricostruisce l'elenco degli agenti. Chiamata al caricamento della pagina e dopo una creazione o un'eliminazione, mai con un timer |
| `fPickDifferentModel` | `frontend/static/js/dashboard.js` | Il modello da compilare quando si sceglie un provider. Quello di riserva evita quello del principale: stesso provider e stesso modello falliscono per la stessa ragione, ogni volta |
| `fSetAgentAvatarActivity` | `frontend/static/js/api.js` | Imposta `data-running` e il tooltip su un avatar, e aggiunge o rimuove l'arco |
| `fBuildAgentActivityArc` | `frontend/static/js/api.js` | Il rettangolo SVG arrotondato sovrapposto al bordo, `pathLength="100"` così il foglio di stile può parlare in percentuali del perimetro |
| `fRefreshAgentActivity` | `frontend/static/js/api.js` | Ogni 5 s ridisegna solo gli anelli; saltato mentre la scheda del browser è nascosta |
| `fDescribeChannelName` / `fDescribeProviderName` | `frontend/static/js/api.js` | Il nome con cui si scrive un canale o un provider. Non chiavi i18n: DeepSeek è DeepSeek in ogni lingua |
| `fDescribeTool` / `fDescribeToolArgument` | `frontend/static/js/api.js` | Ciò che dicono uno strumento e i suoi argomenti, nella lingua di chi legge. Lo schema resta in inglese: è ciò che viene mandato al modello |
| `fRenderToolCheckboxes` | `frontend/static/js/dashboard.js` | Un riquadro per famiglia di strumenti, costruito da qualunque cosa sia installata. Sposta l'interruttore del kanban nel riquadro del kanban invece di ricostruirlo, così una spunta messa e non ancora salvata sopravvive al ridisegno |

### Messaggi a comparsa

| Simbolo | File:riga | Che cosa fa |
|---|---|---|
| `fShowNotice` | `frontend/static/js/api.js` | Mette un messaggio sullo strato sopra la colonna del contenuto. Sostituisce qualunque cosa ci fosse, così le conferme non si accumulano mai |
| `fShowError` | `frontend/static/js/api.js` | Lo stesso, come errore: nessun timer, si chiude a mano |
| `fConfirmLogout` | `frontend/static/js/api.js` | Apre `fConfirm` al centro dello schermo; naviga verso `/logout` solo dopo la conferma. Annulla ed Esc mantengono la sessione aperta |
| `fHideNotice` | `frontend/static/js/api.js` | Fa svanire un messaggio e poi lo rimuove, così non sparisce di colpo quando scade il timer |
| `fGetNoticeSeconds` / `fSetNoticeSeconds` | `frontend/static/js/api.js` | Quanto resta un messaggio, conservato in questo browser e limitato a 1–30 secondi |
| `fBuildCloseCross` | `frontend/static/js/api.js` | La croce di chiusura come due linee SVG. Un carattere `×` è centrato sull'asse matematico del font invece che nel proprio riquadro, quindi sta sopra il centro del pulsante qualunque cosa faccia il pulsante |

### Evidenziazione del JSON

| Simbolo | File:riga | Che cosa fa |
|---|---|---|
| `cJsonTokenPattern` | `frontend/static/js/jsonhighlight.js` | Un'unica espressione per tutti e quattro i tipi di token. Una stringa seguita da due punti è una chiave, che è l'unica cosa che distingue un nome da un valore |
| `fHighlightJsonElement` | `frontend/static/js/jsonhighlight.js` | Ricostruisce un blocco come span colorati e testo semplice. Ogni carattere dell'originale viene emesso esattamente una volta, così il blocco si copia ancora come JSON valido |

### Provider

| Simbolo | File:riga | Che cosa fa |
|---|---|---|
| `BaseProvider.fSendMessages` | `backend/providers/base.py` | L'unico metodo che ogni adattatore implementa |
| `fNeutralMessagesToOpenAiFormat` | `backend/providers/base.py` | Forma neutra → chat/completions |
| `fToolNameToWire` / `fToolNameFromWire` | `backend/providers/base.py` | `family.action` ↔ `family__action`, perché nessun provider accetta il punto |
| `fDescribeHttpError` | `backend/providers/base.py` | Aggiunge ciò che ha detto il provider a un fallimento HTTP nudo |
| `fBuildProvider` | `backend/providers/factory.py` | Configurazione → istanza dell'adattatore, con importazione differita |
| `fResolveProviderName` | `backend/providers/factory.py` | Segue gli alias, così `gemini` e `google` raggiungono un solo adattatore |
| `fSendChatCompletion` | `backend/providers/openai_dialect.py` | La richiesta chat/completions condivisa, parametrizzata dalle stranezze di ciascun adattatore |
| `fNormalizeMessageContent` | `backend/providers/openai_dialect.py` | Appiattisce una risposta il cui contenuto è arrivato a blocchi, scartando il ragionamento |

---

### Simboli dell'audio

| Simbolo | File:riga | Responsabilità |
|---|---|---|
| `fTranscribe` | `backend/core/audio_transcription.py:223` | Decodificare, segmentare e trascrivere |
| `fEnqueueTelegram` | `backend/core/audio_inbox.py:57` | Rendere persistente la destinazione prima della trascrizione |
| `fRunOneJob` | `backend/core/audio_inbox.py:233` | Elaborare o ritentare un turno riservato |
| `fDownloadModel` | `backend/core/whisper_runtime.py:134` | Convalidare dimensione e SHA-256 prima della pubblicazione |
| `fGetChatAudio` | `backend/web/api.py:571` | Servire l'audio dopo i controlli della sessione e del riferimento di chat |

### API Calls

| Simbolo | File | Responsabilità |
|---|---|---|
| `fRecordCall` | `backend/core/api_calls.py` | Rende persistente un corpo in uscita completo prima dell'invio |
| `fReadBodyChunk` | `backend/core/api_calls.py` | Legge una parte limitata di un file dell'agente convalidato |
| `fSelectConversationTab` | `frontend/static/js/dashboard.js` | Alterna Chat/API Calls e la loro interrogazione periodica |
| `fBeautifyJson` | `frontend/static/js/jsonhighlight.js` | Indenta il JSON conservando i valori letterali |

### Samba

| Simbolo | File | Responsabilità |
|---|---|---|
| `fProvisionAgent` / `fRemoveAgent` | `backend/core/samba.py` | Ciclo di vita di condivisione e account |
| `fSaveSettings` | `backend/core/samba.py` | Convalidare, salvare le credenziali e attivare i permessi |
| `fCheckShareDirectory` | `backend/core/samba.py` | Verifica della cartella e della proprietà al momento della connessione |
| `fBackup` / `fRestore` | `backend/core/samba.py` | Backup e sostituzione coerenti delle credenziali native |
| `fLoadSambaSettings` / `fCollectSambaSettings` | `frontend/static/js/samba.js` | Caricare e salvare senza esporre le password né scartare altre modifiche |

## 4. Flussi principali

### Recupero dei documenti

I programmi di installazione puliscono i vecchi alberi RAG degli agenti
ripristinati prima di estrarre l'istantanea, così i file WAL di SQLite e le
generazioni di vettori obsoleti non possono sopravvivere a un ripristino. Le
impostazioni di runtime vengono ripristinate senza sostituire i pesi dei
modelli installati. I worker smaltiscono al massimo otto documenti o avviano
documenti nuovi per al massimo 90 secondi per turno; i lavori non finiti
restano persistenti. La risposta della biblioteca espone i fallimenti
dell'importazione dalla inbox. L'OCR locale installa i font Liberation per i
PDF a cui mancano i font incorporati. La compilazione del motore di
vettorizzazione disattiva il download delle interfacce web precompilate.

Caricamento: `rag_api → exec_client.fRag → rag_exec → rag_worker` come l'agente.
Indicizzazione: `boa-rag → exec_daemon → rag_worker.fWork → rag_embeddings.fIsAvailable → extraction → local embeddings → publication`.
Interruzione del motore durante l'indicizzazione: `rag_embeddings.fRequest → EngineUnavailable → fIndexDocument → state queued, chunks kept → fWork ends the batch → next pass resumes at the first missing chunk`.
Download di un modello: `settings_rag.js → POST /api/admin/rag/models/<id>/install → exec_client.fInstallRagModel → exec_daemon.fVerbInstallRagModel → rag_runtime.fStartModelDownload → thread fInstallModel → status file ← GET /api/admin/rag (fDescribe) polled every 2 s`.
Cambio di modello: `settings_rag.js (fConfirmModelChange) → PUT /api/admin/rag → rag_exec.fRuntime → fIsModelInstalled → fSaveRuntimeSettings → fFollowModelSimilarity → restart boa-embeddings → [each library] rag_worker.fWork → fFollowNewModel → fIsAvailable waits for the new alias → fIndexDocument(pModel) → fBuildIndex/fPublish (documents.model)`; nel frattempo `fSearch → FTS5 only for the waiting documents → notice`.
Risposta: `AgentRun.fExecute → rag_search.fSearch → bounded passages → configured provider → verified citation links`.
Risposta documentale e verificata: `model answers → fCheckRagAnswer (no rag.search yet → cRagSearchFirstPrompt, once) → rag.search → model answers → [verified] rag_verify.fVerify → unbacked units → fBuildCorrectionPrompt, once → model answers → fFinishRagAnswer (no passages → fixed sentence; verified → units removed + count, engine down → withheld) → fResolveCitations`.

### Salvare la memoria e il suo limite

`dashboard.js:fSaveAgent` conta i code point Unicode e invia `memory` con
`info.limits.max_memory_characters`. `api.fCheckMemoryUpdate` convalida contro
il limite proposto (o legge quello salvato) prima di qualsiasi scrittura, così
aumentare il limite e salvare un testo più lungo funziona in una sola
richiesta. In caso di rifiuto restituisce gli errori tradotti `memoryTooLong` o
`memoryLimitInvalid`. Poi `fVerbWriteAgentInfo` rende persistente il limite e
`fVerbWriteMemory` convalida prima di abbassare i privilegi. `memory.fWrite`
verifica di nuovo l'impostazione protetta e sostituisce atomicamente il file
senza troncarlo. `memory.append` e `memory.replace` usano lo stesso controllo;
l'avviso comincia sopra il 75% del limite. Il modulo lascia il testo incollato
troppo grande disponibile per la modifica.

I budget di trasporto sostengono il limite superiore: 6 MiB per richiesta
all'esecutore, verificati dal client prima di connettersi; 8 MiB per risposta;
4 MiB per lettura del file della memoria; 16 MiB per corpo HTTP, compresi i
client JSON che fanno l'escape dei caratteri Unicode supplementari. Sono
limiti di trasporto, non limiti del contesto del modello.

### Creare un agente

```
browser  POST /api/admin/agents {name}
  web/api.fCreateAgent
    exec_client.fCreateAgent          → Unix socket /run/boa/exec.sock
      exec_daemon.ExecRequestHandler
        fGetPeerCredentials + fIsPeerAllowed    ← rifiuta chiunque non sia root/boa
        fVerbCreateAgent
          agents.fValidateAgentName
          agents.fGetNextFreeAgentId            ← il più basso libero, dal filesystem
          useradd --home-dir … --create-home
          agents.fWriteAgentInfo                 (0600, di proprietà dell'agente)
          fWriteAgentFile system-prompt.md        (0600)
          fWriteAgentFile api-token              (0600)
          chmod 0700 sulla home
          agents.fIndexAgent(…, vApiToken)       ← memorizza solo lo SHA-256
        a qualsiasi eccezione: fRemoveAgentUser  ← nessun agente creato a metà
```

### Creare un agente da un template

```
browser  GET /api/admin/agent-templates?language=es-ES
  agent_templates.fListTemplates
    fLoadTemplates → fDownloadArchive(<repo>/archive/refs/heads/<branch>.tar.gz)   in cache 5 min
      agent_package.fReadRepositoryArchive                   un'origine per cartella con agent.json
    agent_package.fReadPackage + fSummarise                  per template; un fallimento viene elencato con il suo errore
browser  POST /api/admin/agents {name, template, language}
  api.fCreateAgent
    agent_templates.fReadTemplate(template)                  il server lo rilegge
    agent_io.fInstallPackage
      exec_client.fCreateAgent(tools, skills, limits, pRag, pSchedules, pEnabled=False)
        exec_daemon.fVerbCreateAgent → agents.fValidateSchedule, di nuovo
      exec_client.fWriteAgentInfo / fWriteMemory / fAgentHome / fRag   quando il pacchetto li porta
      in caso di fallimento: exec_client.fDeleteAgent
```

### Importare un .zip

```
browser  POST /api/admin/agent-imports {name, size}          → /opt/boa/imports/<id>/package.zip
browser  PUT  /api/admin/agent-imports/<id>/upload {offset, data}   in ordine, 256 KiB ciascuno
browser  POST /api/admin/agent-imports/<id>/finish            ZipSource + fReadPackage → riepilogo
browser  (mostra il riepilogo; l'utente conferma e gli dà un nome)
browser  POST /api/admin/agent-imports/<id>/install           → 202
  agent_io.fStartImport → install.lock (una volta) → thread fRunImport
    fInstallPackage, che riporta step/done/total in job.json
browser  GET  /api/admin/agent-imports/<id>                   ogni secondo fino a installed/failed
```

### Esportare un agente

```
browser  GET /api/admin/agents/<id>/export/preview            dimensione della memoria, file della home, biblioteca, modello
browser  GET /api/admin/agents/<id>/export?memory=1&home=1&provider=1&rag=1   un link di download
  agent_io_api.fExport → primo blocco prodotto prima delle intestazioni (gli errori restano JSON)
    agent_io.fExportAgent
      fBuildManifest ← fReadAgentInfo, fReadCrontab → fReadSchedules
      memory.md ← fReadMemory
      home/... ← exec_client.fAgentHome(list, read) come l'agente
      rag/files/... + rag/documents.json ← exec_client.fRag(list, content)
```

### Un'esecuzione programmata

```
cron (il crontab proprio di agent-007)
  runner.py --agent-id 007            ← gira già come agent-007
    fTakeRunLock                      ← rifiutato → fRecordRunRefused, e stop
    AgentRun.__init__
      fReadOwnInfo / fReadOwnSystemPrompt / fReadOwnApiToken
      fBuildSystemPrompt              ← prompt + memoria + indice delle competenze + lingua
      tool_registry.fLoadAllTools
      fSelectAllowedTools             ← strumenti kanban trattenuti se spenti
    fExecute
      run_journal.fCountRunsOn        ← tetto giornaliero, dal suo stesso giornale
      factory.fBuildProvider
      ciclo:
        fCheckCeilings                ← passi, token, secondi
        provider.fSendMessages        ← max_tokens si riduce man mano che si spende il budget
        run_journal.fRecordUsage
        se non ci sono chiamate di strumento: stop
        fRunToolCalls                 ← tutti i risultati restituiti in un solo lotto
      fAskForClosingAnswer            ← una chiamata senza strumenti dopo un tetto
                                        di passi o di token, così il lavoro già
                                        pagato si trasforma in una risposta
      run_journal.fRecordRunFinished  ← "stopped" quando l'ha fermata un tetto
```

### Una scheda scade

```
boa-buzzer (come boa), ogni 5 secondi
  kanban.fListDueCards              ← con proprietario, run_at passato, senza sveglia, non fatta
  fRingOne
    fBuildCardAnnouncement          ← assigned_by → nome, run_mode → immediate
    exec_client.fRunNow(prompt, only_if_idle, card)
      exec_daemon.fVerbRunNow                      ← come root
        fIsAgentRunning             ← occupato: started=False, nessuna sveglia, riprova
        fRunAsAgent → chat.fAppendCardMessage      ← annunciata, turno aperto
        Popen runner.py --prompt-on-stdin --turn-id …  ← come agent-007, il prompt sul suo stdin
    kanban.fMarkCardBuzzed          ← solo dopo che l'esecuzione è partita
  runner.AgentRun (vWritesToChat, non vIsChat)
    fExecute                        ← prompt della scheda, nessuna conversazione riproposta
    fRecordChatAnswer               ← risposta + costo chiudono il turno
    fRecordChatFailure              ← oppure il motivo per cui non è girato niente
```

### Un agente sposta una scheda

```
il modello chiede kanban.move_card
  tool_registry.fRunTool              ← rifiuta se non concesso a questo agente
    tools/kanban_move_card.fRunTool
      agent_api_client.fCallFromContext   → /run/boa/agent.sock
        agent_api.AgentRequestHandler
          fAuthenticate               ← hash del token + SO_PEERCRED
          fVerbKanbanMoveCard
            fAgentMayUseKanban        ← lato server, legge info.json
            fRequireOwnCard           ← solo creatore o assegnatario
            kanban.fMoveCard          ← spostamento + evento, un'unica transazione
```

### Un agente invia un messaggio

```
il modello chiede channel.write
  tools/channel_write.fRunTool
    agent_api_client → agent_api.fVerbChannelWrite
      fAgentMayUseChannel             ← strumento concesso E canale concesso
      channels.fSendMessage(prefix="[Agent name]")
        fReadChannelConfig            ← come boa; l'agente non lo vede mai
        fSendToTelegram / Discord / Mattermost / X
```


### Arriva un messaggio da Telegram

```
boa-channel-telegram (come boa)
  fRefreshCommands                    ← /agents /status /help, quando cambiano
  fDeliverAnswers                     ← tutto ciò che è finito dall'ultimo passaggio
    exec_client.fReadChat             ← la chat è in una home 0700; la legge solo root
    channels.fSendToTelegram          ← "**name:**\n..." come risposta
    telegram_inbox.fRemovePending
  channels.fReadTelegramUpdates       ← long poll: 25s a riposo, 3s mentre risponde
    fIsFromTheConfiguredChat          ← tutto il resto viene scartato, in silenzio
    callback_query -> fHandleCallback ← un tocco su un pulsante di agente
      fSelectAgent                    ← da qui in poi, i messaggi senza destinatario vanno lì
    message -> fHandleMessage
      fHandleCommand                  ← /agents /status /help, risposto e chiuso
      fRouteMessage                   ← risposta, poi @nome, poi quello selezionato
      exec_client.fSendChatMessage(source="telegram")
        exec_daemon.fVerbSendChatMessage
          chat.fAppendMessage(metadata={"source": "telegram"})
          Popen runner.py --chat-message-on-stdin --turn-id   ← il messaggio sul suo stdin
      telegram_inbox.fAddPending      ← su disco: un riavvio non deve perdere la risposta
```

La risposta la invia il listener e non l'esecuzione, per la stessa ragione per
cui l'annuncio della scheda lo scrive l'esecutore: l'esecuzione è l'utente
proprio dell'agente, e le credenziali del canale appartengono a `boa`.
L'esecuzione scrive solo nella sua chat; il listener la legge e si occupa
dell'invio.

### Arriva un messaggio da Discord

```
boa-channel-discord (come boa)
  fDeliverAnswers                     ← tutto ciò che è finito dall'ultimo passaggio
    exec_client.fReadChat             ← la chat è in una home 0700; la legge solo root
    channels.fSendToDiscord           ← "**name:**\n…" come risposta, in parti da 2000 caratteri
      discord_markdown.fRenderToMessages
    discord_inbox.fRememberMessage    ← ogni parte, così rispondere a una qualsiasi viene instradato
    discord_inbox.fRemovePending
  channels.fReadDiscordMessages       ← GET /channels/<id>/messages?after=<id>
    (invertito: Discord risponde dal più recente)
    fHandleMessage
      author.bot, type                ← le sue stesse parole, e tutto ciò che non è un messaggio
      fIsFromTheConfiguredChannel
      fReadCommand                    ← !agents !status !help, risposto e chiuso
      fRouteMessage                   ← risposta, poi @nome, poi quello selezionato
      exec_client.fSendChatMessage(source="discord")
      discord_inbox.fAddPending       ← su disco: un riavvio non deve perdere la risposta
  fWriteAfterId                       ← config/discord-after
```

La risposta la invia il listener e non l'esecuzione, per la stessa ragione di
quella di Telegram: l'esecuzione è l'utente proprio dell'agente, e le
credenziali del canale appartengono a `boa`.

Il primo passaggio di un'installazione nuova chiede il messaggio più recente e
ne tiene solo l'id. Un canale vuoto viene marcato con l'id più basso che
esista, così al **primo** messaggio che qualcuno scrive si risponde invece di
spenderlo per capire da dove cominciare.

### Il bot non mostra niente a uno sconosciuto

Il nome utente di un bot è pubblico: chiunque lo trovi può aprire una chat con
lui. Così `fIsFromTheConfiguredChat` confronta il `chat.id` che Telegram mette
su ogni messaggio - che il mittente non può falsificare - con quello
configurato, e `fHandleMessage` scarta ciò che non corrisponde prima che venga
smistato un comando e prima che venga scelto un agente. `fHandleCallback` fa lo
stesso per la pressione di un pulsante. Non viene rimandato indietro niente:
rispondere confermerebbe che il bot è vivo a chiunque lo stia sondando. E non
viene nemmeno annotato niente. Prima lo scarto veniva registrato nel log con
l'id della chat da cui veniva, che è un dato di qualcun altro e avrebbe
significato che questa installazione accumulava in silenzio un elenco di chi ha
trovato il bot. Ciò che resta è un messaggio che non è mai esistito.

Il costo è reale e vale la pena nominarlo: un `chat_id` configurato male ora
sembra esattamente uno sconosciuto, e i messaggi del proprietario stesso
spariscono in silenzio. L'id configurato viene scritto nel log a ogni avvio -
`Registered 3 command(s) for chat <id> only` - ed è il numero con cui
confrontare. Un messaggio dalla chat *configurata* che non raggiunge nessun
agente viene comunque registrato, perché lì il mittente è il proprietario e
«gli ho scritto e non è successo niente» sarebbe altrimenti indistinguibile da
«non è mai arrivato».

Ciò che il filtro non copre, e non può coprire, è *chi* dentro la chat: un
`chat_id` che nomina un gruppo è un gruppo in cui ogni membro può parlare con
gli agenti.

Lo stesso ragionamento decide dove viene scritto l'elenco dei comandi.
`setMyCommands` accetta uno scope, e `default` e `all_private_chats` vengono
risolti per ogni utente di Telegram - quindi un elenco scritto lì è un menu
mostrato agli sconosciuti, con dentro «Server status», che annuncia che dietro
c'è una macchina che vale la pena stuzzicare. Non potrebbero mai eseguirne
niente, ma un cartello su una porta chiusa a chiave è pur sempre un cartello.
`fSetTelegramCommands` scrive l'elenco solo nello scope della chat configurata
ed **elimina** i due pubblici a ogni aggiornamento: un elenco scritto da una
versione più vecchia di questo codice vive dalla parte di Telegram finché
qualcosa non lo rimuove. `fHideTelegramPublicProfile` svuota le altre due
stringhe pubbliche, `setMyDescription` e `setMyShortDescription`, che sono ciò
che riempie una chat vuota sotto «What can this bot do?».

Ciò che resta visibile è il nome del bot, la sua immagine e il pulsante Start,
che Telegram disegna in ogni chat vuota con un bot e che nessuna API può
rimuovere. Premerlo manda `/start`, che viene scartato come qualsiasi altra cosa
da un'altra chat.

### Perché il menu contiene strumenti e non agenti

Telegram disegna `/name` accanto a ogni voce del menu dei comandi - quella
stringa è la voce, è ciò che viene scritto nella casella quando la si tocca, e
nessuna API la nasconde. Quindi un menu di agenti non avrebbe mai potuto essere
l'elenco di agenti che qualcuno voleva guardare, e cresceva con l'elenco degli
agenti senza dire niente di a che cosa servisse il bot.

Il menu contiene tre cose che il bot sa fare. Quali agenti esistono è una
domanda, e `/agents` le risponde con pulsanti inline, dove un pulsante dice
`os-watcher` e nient'altro, perché il testo di un pulsante lo sceglie il bot.

Il resto discende da questo:

- **L'agente selezionato resta selezionato.** Toccare un pulsante o nominare un
  agente lo sceglie; tutto ciò che non ha destinatario va lì finché non se ne
  sceglie un altro. Nominare l'agente su ogni riga va bene una volta ed è
  stancante al quarto messaggio. Vive in `settings`, non in memoria, perché il
  servizio si riavvia a ogni aggiornamento.
- **Una risposta vince comunque.** È inequivocabile, ed è ciò che fa chi tiene
  in mano un telefono. Nient'altro cambia la selezione, così un agente non
  eredita mai una conversazione per il solo fatto di essere quello che ha
  parlato per ultimo.
- **Un agente eliminato smette di essere selezionato.** `fReadSelectedAgent`
  verifica l'elenco degli agenti all'uscita: non raggiungere nessuno è meglio
  che raggiungere chiunque abbia preso il suo id.
- **Il bot parla la lingua dell'installazione.** Prima `agent_language`, la
  stessa impostazione in cui rispondono gli agenti - le sue righe compaiono
  nella stessa conversazione delle loro.

### La barra laterale mostra chi sta lavorando

```
ogni 5 secondi, e subito dopo invio / esegui ora / arrivo di una risposta
  api.js fRefreshAgentActivity        ← saltato mentre la scheda del browser è nascosta
    GET /api/admin/agents
      web/api.fListAgents
        exec_client.fListRunningAgents          → /run/boa/exec.sock
          exec_daemon.fVerbListRunningAgents
            fListRunningAgentIds      ← una sola scansione di /proc, tutti gli agenti insieme
      ogni agente porta `running`
    fSetAgentAvatarActivity           ← data-running sull'avatar; l'elenco
                                        in sé non viene mai ricostruito con un timer
      fBuildAgentActivityArc          ← un rettangolo SVG arrotondato sopra il bordo
  il CSS anima il suo stroke-dashoffset  ← la forma resta ferma, il tratto illuminato
                                           percorre il contorno in senso orario
```

### Accedere

```
POST /login
  views.fLoginPage
    auth.fCountRecentFailures         ← 10 ogni 15 minuti per indirizzo
    auth.fVerifyCredentials           ← argon2id; un'email sbagliata calcola comunque l'hash
    auth.fRecordAttempt
    auth.fLogIn                       ← cookie di sessione, 12 ore
```

---

### Arriva un messaggio vocale

`fHandleMessage → fRouteMessage → fEnqueueTelegram → audio_jobs → fRunOneJob → fDownloadTelegram → fTranscribe → fSubmitTranscript → fSendChatMessageLocked → runner`. La risposta usa la normale consegna su Telegram; la chat web aggiunge la trascrizione e un lettore privato. Impostazioni → Audio usa GET/PUT `/api/admin/audio`; i download dei modelli usano la RPC `install_whisper_model` e interrogano l'avanzamento senza bloccare l'HTTP.

### API Calls

```text
AgentRun.fSendRecordedRequest → registratore di richieste di BaseProvider → api_calls.fRecordCall
scheda API Calls → GET /api/admin/agents/<id>/api-calls
  exec_client.fReadApiCalls → exec_daemon.fVerbReadApiCalls → api_calls.fReadCalls
espansione di una richiesta → GET /api/admin/agents/<id>/api-calls/<call_id>
  exec_client.fReadApiCallBody → api_calls.fReadBodyChunk → testo JSON in streaming
  fBeautifyJson → fHighlightJsonElement → DOM sicuro
```

### Samba

```text
create_agent → fIndexAgent → samba.fProvisionAgent → samba/ + [agent-xxx]
GET /agents/<id>/samba → read_samba → samba.fReadSettings
PUT /agents/<id>/samba → write_samba → samba.fSaveSettings
  convalida → info protetto + testparm → smbpasswd (stdin) → reload/close-share
connessione SMB → root preexec --check-share <id> → permessi Samba → uid dell'agente
delete_agent → samba.fRemoveAgent → rimozione di utente Linux, home e indice
--backup → tdbbackup + SID del server → samba-backup nell'archivio
--restore → stop dei servizi → ripristino di utenti/dati → sostituzione del passdb nativo → avvio
```

## 5. Punto di ingresso e mappa delle rotte

### HTTP

| Rotta | Metodo | Gestore | File |
|---|---|---|---|
| `/api/admin/rag` | GET, PUT | `fRuntime` | `backend/web/rag_api.py` |
| `/api/admin/rag/models/<vModel>/install` | POST | `fInstallModel` | `backend/web/rag_api.py` |
| `/api/admin/agents/<id>/rag/...` | GET, POST, PUT, DELETE | `fOverview`, `fUpload`, `fUploadPart`, `fDocument`, `fContent`, `fImport`, `fSearch` | `backend/web/rag_api.py` |
| `/login` | GET, POST | `fLoginPage` | `backend/web/views.py` |
| `/logout` | GET, POST | `fLogoutPage` | `backend/web/views.py` |
| `/` | GET | `fDashboardPage` | `backend/web/views.py` |
| `/kanban/` | GET | `fKanbanPage` | `backend/web/views.py` |
| `/tools/` | GET | `fToolsPage` → `/settings/?tab=tools` (conserva `family` e `agent`) | `backend/web/views.py` |
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
| `/api/admin/agents` | GET, POST | `fListAgents` (porta sempre `running` per agente), `fCreateAgent` | `backend/web/api.py` |
| `/api/admin/agents?kanban=1` | GET | `fListAgents`, aggiunge `reads_kanban` per agente | `backend/web/api.py` |
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

Tutto ciò che è un'API vive sotto `/api/`. Tutto ciò che sta sotto
`/api/admin/` richiede una sessione.

### Socket Unix

| `/run/boa-web/web.sock` | `0750 boa:boa` | gunicorn | L'applicazione stessa. Solo `boa-proxy` la raggiunge |

| Socket | Modo | Server | Verbi |
|---|---|---|---|
| `/run/boa/exec.sock` | `0660 root:boa` | `exec_daemon` | `ping`, `create_agent`, `delete_agent`, `read_agent_info`, `write_agent_info`, `read_system_prompt`, `write_system_prompt`, `read_crontab`, `write_crontab`, `run_now`, `list_running_agents`, `read_samba`, `write_samba`, `read_run_journal`, `read_api_calls`, `read_api_call_body`, `read_usage_summary`, `read_chat`, `read_chat_attachment`, `send_chat_message`, `clear_chat` |
| `/run/boa/agent.sock` | `0666` | `agent_api` | `who_am_i`, `kanban_add_card`, `kanban_move_card`, `kanban_delete_card`, `kanban_list_cards`, `channel_write`, `mail_read`, `mail_delete`, `mail_move`, `mail_forward` |

### Riga di comando

| Comando | File |
|---|---|
| `runner.py --agent-id NNN [--prompt … or --prompt-on-stdin] [--chat-message … or --chat-message-on-stdin] [--turn-id …] [--dry-run]` | `backend/core/runner.py` |
| `install-update-reinstall-debian.sh --install\|--update\|--reinstall\|--backup [file]\|--restore <file>` | `deploy/` |
| `install-update-reinstall-alpine.sh --install\|--update\|--reinstall\|--backup [file]\|--restore <file>` | `deploy/` |

---

## 6. Analisi di impatto

Che cosa si rompe se cambi questi elementi.

| Componente | Cambiarlo influisce su |
|---|---|
| `paths.fNormalizeAgentId` | **Ogni percorso del sistema.** È l'unica convalida tra l'input dell'utente e un percorso del filesystem. Indebolirla trasforma qualsiasi id di agente in un path traversal |
| Costanti di `paths.py` | Tutti e quattro i servizi, il programma di installazione e le unità systemd. Cambiare `/opt/boa` significa reinstallare |
| `deploy/haproxy/boa.cfg` | Ogni richiesta. `accept-proxy` deve corrispondere a ciò che manda l'HAProxy della macchina: con `send-proxy-v2` su quel backend è obbligatorio, senza il bind rifiuta ogni connessione |
| Il bind di `backend/web/gunicorn.conf.py` | Deve restare un socket Unix. Ridare a gunicorn una porta e un certificato reintroduce il guasto del PROXY prima del TLS |
| `exec_protocol.lKnownVerbs` | La superficie privilegiata. Aggiungere un verbo aggiunge un modo per il processo web di chiedere qualcosa a root. Ogni aggiunta richiede lo stesso esame della prima |
| `exec_daemon.fRunPrivilegedCommand` | Ogni comando privilegiato. Non usa mai una shell; introdurre lì `shell=True` renderebbe ogni nome di agente un punto di iniezione |
| `agent_api.fAuthenticate` | Ogni richiesta di un agente alla bacheca e ai canali. Entrambi i controlli devono restare |
| `db.cAppSchema` / `cKanbanSchema` | Le installazioni esistenti. Non c'è nessun sistema di migrazione: gli schemi usano `IF NOT EXISTS`, quindi **le colonne nuove richiedono codice di migrazione esplicito**, non una modifica dello schema |
| `agent_scripts.cMinimumMinuteStep` | Ogni quanto un agente può programmarsi da sé. È l'unica cosa che c'è tra una pianificazione sbadata e un ciclo con una riga di cron davanti |
| `paths.lProtectedAgentFiles` | Quali file si spostano nel cassetto di proprietà di root. La migrazione del programma di installazione e il demone che crea un agente lo leggono entrambi, così non possono essere in disaccordo su quali siano |
| `agents.fBuildAgentInfo` | Solo gli agenti nuovi. I file `info.json` esistenti non vengono toccati, quindi i campi nuovi hanno bisogno di un percorso di lettura con valore predefinito |
| `exec_daemon.fVerbWriteAgentInfo` | **Ogni campo di `info.json` che sopravvive a un salvataggio.** Ricostruisce il file chiave per chiave, quindi un campo che non nomina è un campo che l'interfaccia scarta in silenzio la prima volta che qualcuno preme Salva. Le liste vengono lette tramite `fReadNameList`, che distingue una chiave assente («lascia stare») da una lista vuota («toglile tutte»): letta con `or`, togliere la spunta all'ultimo strumento ripristinava la lista precedente |
| `skills.fSelectInstalledSkills` | Ciò che arriva a un prompt e ciò che `skill.read` aprirà. Sia l'indice sia lo strumento filtrano attraverso di essa, così una competenza eliminata dal server smette di essere nominata invece di essere promessa e poi fallire |
| Forma neutra di `providers.base` | Ogni adattatore e il runner |
| Interfaccia di `tool_registry` | Ogni strumento in `/opt/boa/tools/`, compresi quelli scritti dall'utente |
| `telegram_listener.fIsFromTheConfiguredChat` | Chi può parlare con i tuoi agenti. Il nome utente di un bot è pubblico, quindi questo controllo è tutta l'autorizzazione che c'è: indebolirlo permette a chiunque trovi il bot di avviare esecuzioni sul tuo server |
| Firma di `channels.fSendMessage` | Ogni chiamante, e i due mittenti che accettano due argomenti. `pReplyToMessageId` viene passato a Telegram e a Discord, che sono i due canali attraverso cui una persona può rispondere |
| `discord_markdown.cMaxDiscordLength` | Se la risposta di un agente arriva o no. Discord rifiuta un `content` di oltre 2000 caratteri, e rifiutare è ciò che fa - non troncare |
| `agent_routing.fMatchNamedAgent` | Chi raggiunge un messaggio, in **entrambi** i listener. La corrispondenza più lunga è ciò che fa di `@News` e `@News Miner` due agenti |
| `agent_routing.fBuildStatusReport` | Che cosa risponde /status su entrambi. Un solo rapporto, così i due non possono essere in disaccordo su quanti servizi ci sono |
| `discord_listener.fIsFromTheConfiguredChannel` | Quale canale ascoltano gli agenti. A differenza di Telegram non c'è un secondo controllo su chi sta parlando: chiunque possa scrivere in quel canale può avviare esecuzioni |
| `kanban.lStates` | La bacheca, l'API, il frontend e il prompt di ogni agente |
| Forma delle voci di `run_journal` | Sia chi scrive (runner) sia chi legge (demone, web). Le righe vecchie restano nei giornali: chi legge deve tollerare campi mancanti |
| `samba` | Ciclo di vita degli agenti, API privilegiata, client SMB e backup/ripristino di entrambi i programmi di installazione. Mantieni intatti la guardia della cartella, la derivazione di nome e percorso e la gestione dei segreti |
| Un file che il demone legge dalla home di un agente (`runs.jsonl`, `chat.jsonl`, `memory.md`) | Letto solo tramite `paths.fReadAgentOwnedFile`. Anche un file nuovo che il demone legga da una home deve passare per lì, altrimenti root legge qualunque cosa l'agente gli indichi - una FIFO che non risponde mai, un link a un file qualsiasi della macchina |
| Ciò che contiene un backup (la riga `tar` di `fDoBackup`) | Lo stato nuovo sotto `/opt/boa/` che appartiene all'installazione e non al codice deve essere aggiunto lì, altrimenti un ripristino su una macchina nuova lo perde |
| I limiti del kernel di un'esecuzione (`runner.cMaxProcesses`, `exec_daemon.cRunTasksMax`, `cRunMemoryMax`) | Uno strumento che abbia bisogno di più di 1024 task o di 2 GiB deve alzarli; un browser è già qualche centinaio di thread |
| `runner.py` come percorso | Ogni esecuzione programmata. Cron lo avvia per percorso quasi senza ambiente, quindi il runner mette la propria radice in sys.path: senza, `import backend` fallisce e il traceback va alla posta di cron, che su una macchina della LAN non va da nessuna parte |
| `runner.dAnswerLanguageLines` | La riga aggiunta a un prompt di sistema che dice all'agente in quale lingua rispondere. Scritta IN quella lingua, e dice che prevale sulla regola del prompt stesso - una preferenza accanto a una regola perde, misurato |
| `agent_api.fFilterCardsForAgent` | Ciò di cui un agente può sapere l'esistenza. Ogni lettura della bacheca passa per qui, e l'orchestratore è l'unica eccezione. Filtrare invece nello strumento metterebbe una regola di sicurezza in una descrizione da cui il modello può essere dissuaso |
| Da che lato sta una nuvoletta della chat | Chi sta parlando. Una scheda è ciò che è stato chiesto all'agente, quindi va a destra con i messaggi dell'utente; il rapporto di un'esecuzione programmata è l'agente che parla, quindi resta a sinistra |
| `chat.lToolsWorthReporting` | Quali strumenti rendono un'esecuzione programmata degna di finire nella chat. Tutto il resto resta nel giornale: altrimenti un agente orario pubblicherebbe ventiquattro messaggi «niente da segnalare» al giorno |
| `chat.lAskingRoles` | Quali ruoli aspettano una risposta. Un ruolo che apre un turno e non è elencato lascia aperta la casella di composizione mentre l'agente lavora; uno elencato ma mai chiuso chiude la casella di composizione per sempre |
| `kanban.cRunNow` | La parola che il browser, gli agenti e l'API mandano tutti invece di una marca temporale. Trasformarla in un'ora in qualunque posto che non sia `fValidateRunAt` perde `run_mode`, e con esso la differenza tra «subito» e un momento scelto |
| `chat.cReplayedTurns` | Quanto costa ogni messaggio della chat. Ogni turno riproposto si paga di nuovo al messaggio successivo, quindi alzarlo rende le conversazioni lunghe progressivamente più care |
| `lTextColours` in `TestThemes` | Quali colori misura il test del contrasto. Un colore usato per il testo e lasciato fuori da quella lista è un colore che niente verifica |
| Un attributo `style=` in qualsiasi template | Niente: `style-src` è `'self'` senza `unsafe-inline`, quindi il browser lo butta via. C'è un test che fallisce se ne compare uno |
| `.notice-layer` in `app.css` | Dove compaiono tutte le conferme e tutti gli errori dell'applicazione. `position: fixed` è portante: `absolute` centra nel documento invece che sullo schermo, che è il bug che lo strato esiste per correggere |
| Catena `.app:has(#vChatPanel…)` e `--status-bar-live-height` in `app.css` | Se la casella di testo della chat resta sopra la barra di stato. Un blocco in quella colonna flex senza `min-height: 0`, o un'altezza di `.chat` che smette di sottrarre l'altezza reale della barra, fa scorrere di nuovo la pagina e mette la casella di composizione sotto la barra |
| `agents.fValidateSchedule` | Se una pianificazione da un `.zip` o da un template può diventare un comando in un crontab scritto come root. Allentarla (uno spazio, un `#`, un'interruzione di riga) trasforma un'importazione in un'esecuzione di codice |
| `agent_home.sExcludedTopNames` / `fIsExcluded` | Ciò che un'esportazione può far trapelare e un'importazione può piantare: sessioni del browser, `.ssh`, la chat. Togliere un nome lo lascia passare in entrambe le direzioni |
| `agent_package.lManifestKeys` / `cFormatVersion` | Ogni `.zip` esportato e ogni template di ogni repository. Una chiave nuova ha bisogno che questa versione la legga; un significato cambiato ha bisogno di un nuovo numero di formato |
| `min_support` in `rag_models.json` | Quali paragrafi di una risposta verificata sopravvivono, per quel modello. Alzato, cominciano ad andarsene paragrafi fedeli; abbassato, passa una citazione a un passaggio non correlato. Che cosa rimuove e che cosa lascia passare ogni valore di entrambi i modelli è nella tabella accanto al controllo in `rag_verify.py`: misura di nuovo su documenti reali prima di spostare un valore, e aggiorna la tabella |
| `sha256` o `dimensions` di un modello in `rag_models.json` | Ogni biblioteca indicizzata con esso. Un'impronta nuova è un nuovo spazio vettoriale: ogni biblioteca indicizza di nuovo tutti i suoi documenti al passaggio successivo (`fFollowNewModel`), il che su una grande richiede ore |
| `rag_embeddings.fCheckServedModel` / il `--alias` in `rag_runtime.fServe` | Se un vettore può venire da un modello diverso da quello che registra la sua biblioteca. Senza di essi, un lavoro che attraversa un cambio di modello memorizza vettori di due modelli in una sola revisione |
| `runner.lRagModesThatSearch` / `fFinishRagAnswer` | Se un'esecuzione documentale o verificata può consegnare testo che viene dai pesi stessi del modello. Togliere una modalità dalla lista, o il controllo dell'assenza di passaggi, riporta risposte senza nessun recupero dietro |
| `rag_search.fSource` | Tutto ciò che viene detto al modello su un passaggio e ciò a cui rimanda una citazione: il blocco del prompt pre-recuperato, `rag.search`, `rag.read` e `fResolveCitations` lo usano tutti. Un campo aggiunto lì ha bisogno anche della sua colonna nelle tre `SELECT` che lo alimentano |
| `rag_embeddings.EngineUnavailable` | Se un fallimento dell'indicizzazione conserva o scarta il lavoro. Sollevare un semplice `ValueError` per un'interruzione trasforma il documento in `error` ed elimina i suoi frammenti vettorizzati; sollevare `EngineUnavailable` per un rifiuto permanente lascia il documento in coda per sempre |
| `rag_store.cSchema` | Solo i cataloghi creati dopo la modifica. Ogni biblioteca di agente esistente, e ogni backup ripristinato, conserva la tabella vecchia: una colonna nuova ha bisogno anche della sua voce in `rag_store.lAddedColumns`, che `fMigrate` applica |
| `frontend/static/i18n/en-US.json` | Aggiungere una chiave significa aggiungerla agli altri quattordici, altrimenti quella stringa ricade sull'inglese. `TestTranslations` fallisce per una chiave mancante, un `{placeholder}` perso e un percorso o un nome di strumento tradotti |

---

## 7. Punti di estensione

### Un nuovo provider

1. Scrivi `backend/providers/<name>.py` con una classe che estende
   `base.BaseProvider`, imposta `cProviderName`, `cDefaultModel`,
   `cDefaultBaseUrl` e implementa `fSendMessages`.
2. Aggiungi una riga a `factory.dProviderRegistry`.
3. Aggiungi il nome ad `agents.lSupportedProviders`.
4. Se non ha bisogno di chiave, aggiungilo a `factory.lSelfHostedProviders`.
5. Le opzioni extra (come `thinking` di DeepSeek) vanno in
   `lExtraConfigKeys`; la factory mappa automaticamente `reasoning_effort` →
   `pReasoningEffort`.

Non fonderlo in un adattatore esistente perché il dialetto coincide. Un file
per provider è voluto.

### Un nuovo strumento

Crea un `.py` in `/opt/boa/tools/` che dichiari:

```python
cToolName = "namespace.verb"
cToolDescription = "What the model is told it does."
dToolSchema = {"type": "object", "properties": {...}, "required": [...]}

def fRunTool(pArguments, pContext):
  return "text the model sees"
```

Gira come l'agente chiamante. Se ha bisogno di qualcosa che gli agenti non
possono raggiungere, aggiungi invece un verbo all'API degli agenti e chiamalo
tramite `agent_api_client`.

Il file deve essere di proprietà di root: l'applicazione lo importa come
codice.

### Una nuova competenza

Crea una directory in `/opt/boa/skills/` con dentro un `SKILL.md`:

```markdown
---
name: BackupVerification
description: One line. This is what every run pays for.
---

The procedure, at whatever length it needs.
```

Niente da registrare e nessun riavvio: `fListSkills` legge la directory, quindi
compare nell'interfaccia al caricamento successivo della pagina. Spuntala su un
agente, dai a quell'agente `skill.read`, e sarà nel suo prompt alla prossima
esecuzione.

Qualsiasi altra cosa nella directory viaggia con la competenza. È leggibile da
tutti, quindi la competenza può dire «esegui `verify.sh` in questa directory»
e l'agente può farlo.

Il nome è il nome della directory: lettere, cifre e trattini, cominciando con
una lettera. Il `name:` nell'intestazione è ciò che una persona vede
nell'elenco; il nome della directory è ciò che chiede un agente.

### Una nuova operazione privilegiata

1. Aggiungi la costante del verbo a `exec_protocol` e a `lKnownVerbs`.
2. Scrivi `fVerb<Name>` in `exec_daemon` e aggiungilo a `dVerbHandlers`.
3. Aggiungi un wrapper in `exec_client`.

Convalida ogni argomento prima che raggiunga un percorso o una riga di comando,
e mantieni il verbo specifico. Un verbo abbastanza generico da essere
riutilizzabile è di solito un verbo abbastanza generico da essere abusato.

### Un nuovo canale

Solo invio:

1. Scrivi `fSendTo<Name>` in `channels.py`.
2. Aggiungilo a `lChannels` e `dChannelSenders`.
3. Aggiungi i suoi campi a `dChannelFields` in
   `frontend/static/js/settings.js`, e quelli che sono credenziali a
   `lSecretChannelFields` lì e a `lSecretConfigFields` in `channels.py`.

Anche ricezione, che è ciò che ne fa una conversazione:

4. Scrivi `fRead<Name>Messages` in `channels.py`, che li restituisca dal più
   vecchio.
5. Scrivi `<name>_inbox.py`: due tabelle in `db.cAppSchema` e l'agente
   selezionato in un'impostazione.
6. Scrivi `<name>_listener.py` su `agent_routing`, che contiene già l'elenco
   degli agenti, la corrispondenza dei nomi, la risposta chiusa e il rapporto
   di stato. Ciò che resta è il protocollo.
7. Scrivi `<name>_texts.py` per le frasi che quel canale dice in modo diverso,
   ricadendo su `telegram_texts` per il resto.
8. `deploy/systemd/boa-channel-<name>.service` e un servizio in
   `deploy/openrc/`, il nome
   in `lServices` e nei sette posti in cui il programma di installazione di
   Debian nomina le sue unità, e in `system_info.lBoaServiceNames`. Se il suo
   nome in OpenRC è diverso, aggiungi la corrispondenza in
   `system_info.dOpenRcServiceNames`.
9. Il suo interruttore in `dChannelSwitches`, la sua chiave
   `chat.source<Name>` nei quindici cataloghi, e `<name>` in
   `exec_daemon.lKnownChatSources`.

### Una nuova lingua

Se ne distribuiscono quindici: `de-DE`, `en-GB`, `en-US`, `es-AR`, `es-ES`,
`fr-FR`, `he-IL`, `hi-IN`, `it-IT`, `ja-JP`, `ko-KR`, `pt-BR`, `pt-PT`,
`ru-RU`, `zh-CN`. Una sedicesima sono sette posti, e i test li nominano tutti:

1. Copia `frontend/static/i18n/en-US.json` e traduci i valori.
2. Aggiungi il tag a `lSupportedLanguages` in `frontend/static/js/i18n.js`.
3. Aggiungi un `<option>` ai tre selettori: due in
   `frontend/templates/settings.html`, uno in `login.html`, per tag.
4. Aggiungi una riga a `runner.dAnswerLanguageLines`, scritta IN quella
   lingua.
5. Aggiungi un blocco a `telegram_texts.dTexts` e il suo tag a
   `lSupportedLanguages` di quel modulo, altrimenti il bot ricade
   sull'inglese. Aggiungine uno anche a `discord_texts.dTexts`: contiene le tre
   frasi che Discord dice in modo diverso, e una lingua che vi manca riceve
   quelle tre in inglese.
6. Traduci la documentazione dai file en-US: `README.<tag>.md` nella radice,
   `doc/CODE.<tag>.md` e `doc/MANUAL.<tag>.md`. Aggiungi la lingua alla riga
   delle lingue in cima a ogni README, in ordine alfabetico di tag.
   en-US è la fonte di tutte le altre lingue e mantiene i nomi senza tag:
   `README.md`, `doc/CODE.md`, `doc/MANUAL.md`.
7. Se si scrive da destra a sinistra, aggiungi il suo tag a
   `lRightToLeftLanguages` in `frontend/static/js/i18n.js`. Nient'altro: il
   foglio di stile usa già proprietà logiche (vedi «Da destra a sinistra» più
   sopra).

`TestTranslations` in `tests/test_web.py` fallisce per una chiave mancante, una
in più, una stringa vuota, un `{placeholder}` perso, un percorso o un nome di
strumento tradotti, un file non ordinato, un selettore che non offre la lingua,
una riga di prompt mancante e un blocco di Telegram mancante. Delle sei
lingue non latine si verifica anche che siano davvero scritte nella loro
scrittura, perché un file di stringhe inglesi sotto un nome russo supera ogni
altro controllo.
`TestExampleAgents` in `tests/test_tools.py` fallisce per una lingua senza il
suo README, CODE o MANUAL, o per un README che non rimanda al README di ogni
altra lingua; `TestTheCodeDocumentsPointAtRealLines` in `tests/test_web.py`
fallisce per un CODE i cui riferimenti `file.py:line` differiscono da quelli
dell'inglese.

Ciò che una traduzione può cambiare: un nome di file che il testo inglese dà
come ESEMPIO, come `check-disk.sh`. Niente li cerca.

### Una nuova modalità di risposta RAG

1. Aggiungila alle modalità consentite in `rag_settings.fValidateSettings` e
   all'enum `mode` in `backend/web/rag_api_doc.py`.
2. Dalle la sua regola in `rag_search.fPrompt`, dicendo ciò che impone il
   runner.
3. In `runner.py`, aggiungila a `lRagModesThatSearch` se il modello deve
   cercare, e a `fCheckRagAnswer` / `fFinishRagAnswer` se le sue risposte
   vengono verificate.
4. Un `<option>` in `frontend/templates/agent_rag.html`, il suo ripiego in
   `dRagModeHints` in `rag.js`, e `rag.<mode>` più `rag.modeHint.<mode>` nei
   quindici file i18n.
5. Test in `tests/test_rag.py` (`TestRagInAgentRun`), con il provider
   scriptato e un `rag_embeddings.fEmbed` finto.

### Un nuovo modello di vettorizzazione

1. Una voce in `backend/core/rag_models.json`: l'URL del GGUF fissato a un
   commit (mai a un branch), `size` e `sha256` dall'API del repository,
   `dimensions`, `context`, il `pooling` che chiede la sua model card, e i suoi
   prefissi di query e di passaggio. `TestEmbeddingModelChoice` verifica che la
   voce sia completa.
2. Fallo girare accanto al motore installato sulla biblioteca di prova e
   misuralo nel modo in cui lo usa l'applicazione (il commento sopra la tabella
   in `rag_verify.py` dice come): il suo `min_support` è il valore più alto che
   lascia passare meno dell'1% delle citazioni a passaggi di un altro
   argomento, il suo `min_similarity` sta tra domande correlate e non
   correlate. Aggiungi le sue righe a quella tabella.
3. Il suo picco di memoria deve stare nel `MemoryMax` di
   `deploy/systemd/boa-embeddings.service`; scrivilo, e quanto più lentamente
   indicizza rispetto a EmbeddingGemma, come `memory_mb` e
   `relative_indexing_time`.
4. L'elenco in Impostazioni → RAG e la rotta di download vengono dal catalogo;
   solo le tabelle in `doc/MANUAL*.md` e le descrizioni dell'enum in
   `rag_api_doc.py` hanno bisogno del nuovo modello per nome.

### Un nuovo campo delle informazioni del documento

1. Aggiungi la colonna a `rag_store.cSchema` e a `rag_store.lAddedColumns`,
   altrimenti le biblioteche esistenti non la avranno.
2. Aggiungi la chiave, al suo posto, a `rag_store.lMetadataKeys`, e qualsiasi
   controllo di formato le serva a `rag_store.fAction`.
3. Se il modello deve vederlo, aggiungi `d.<column>` alle tre `SELECT` in
   `rag_search` e il campo a `rag_search.fSource`.
4. Aggiungilo allo schema `metadata` in `backend/web/rag_api_doc.py`.
5. Aggiungilo, al suo posto, all'elenco dei campi in
   `frontend/static/js/rag.js`.
6. Aggiungi `rag.<key>` ai quindici file `frontend/static/i18n/*.json`.
7. Coprilo in `tests/test_rag.py`; il test di migrazione costruisce già un
   catalogo senza ciascuna delle colonne di `lAddedColumns`.

### Un nuovo template

I template vivono nel repository dei template, non qui:

1. Una cartella `<name>/` in `bunch-of-aigents-templates`, chiamata come il
   `name` del template (`^[a-z][a-z0-9-]{0,39}$`).
2. `agent.json`: `format` 1, `name`, `description` nelle quindici lingue,
   `tools`, `schedules`, `limits` e, se ha bisogno della sua biblioteca, `rag`.
   Il modo più rapido è costruire l'agente qui, esportarlo e decomprimerlo lì.
3. `system-prompt.md`, in inglese, che finisca con la regola sulla lingua della
   risposta.
4. `README.md`, in en-US, per chi legge quel repository: a che cosa serve
   l'agente, che cosa fa, di che cosa ha bisogno prima, che cosa non farà, con
   che cosa arriva e come installarlo. L'applicazione lo ignora.
5. Esegui i test di questo repository: `TestExampleAgents` legge la copia
   clonata accanto a questa con `agent_package` e fallisce per un template che
   l'applicazione rifiuterebbe, uno strumento che non esiste, una lingua
   mancante, o un README che manca o non nomina gli strumenti e le
   pianificazioni del template.
6. Una riga nella tabella dei template di ogni MANUAL di qui, una per lingua, e
   una con il link al suo README nei tre README di lì.

### Una nuova pagina

1. Una rotta in `backend/web/views.py` che restituisce `render_template`.
2. Un template che estende `app_base.html`.
3. Un `<li>` nel `nav` di `app_base.html`.
4. Il suo JS in `frontend/static/js/`, che comincia con
   `await fWaitForTranslations()` prima di rendere qualsiasi cosa.
