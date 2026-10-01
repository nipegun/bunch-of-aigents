# Manuale

Come usare Bunch of AIgents, giorno per giorno.

## Indice

1. [Che cosa fa](#che-cosa-fa)
1. [Su che cosa gira](#su-che-cosa-gira)
1. [Se usi Alpine](#se-usi-alpine)
1. [Installazione](#installazione)
1. [Aggiornare e reinstallare](#aggiornare-e-reinstallare)
1. [Aprire l'applicazione](#aprire-lapplicazione)
1. [Accedere](#accedere)
1. [Primi passi](#primi-passi)
2. [L'interfaccia](#linterfaccia)
3. [Da dove viene un nuovo agente](#da-dove-viene-un-nuovo-agente)
3. [Creare il tuo primo agente](#creare-il-tuo-primo-agente)
4. [Parlare con un agente](#parlare-con-un-agente)
5. [Impostazioni dell'agente](#impostazioni-dellagente)
5. [Esportare un agente](#esportare-un-agente)
5. [Cartelle condivise Samba](#cartelle-condivise-samba)
6. [Dare un modello a un agente](#dare-un-modello-a-un-agente)
5. [Scrivere un prompt di sistema](#scrivere-un-prompt-di-sistema)
6. [Scegliere gli strumenti](#scegliere-gli-strumenti)
7. [Dare una competenza a un agente](#dare-una-competenza-a-un-agente)
8. [Dare un browser a un agente](#dare-un-browser-a-un-agente)
9. [Tetti di spesa](#tetti-di-spesa)
8. [Pianificare un agente](#pianificare-un-agente)
9. [La bacheca kanban](#la-bacheca-kanban)
10. [Temi](#temi)
11. [Canali](#canali)
12. [L'orchestratore](#lorchestratore)
13. [Backup e ripristino](#backup-e-ripristino)
13. [Servizi](#servizi)
13. [Sicurezza](#sicurezza)
14. [Quando qualcosa non funziona](#quando-qualcosa-non-funziona)
1. [Trascrizione audio](#trascrizione-audio)
1. [Licenza](#licenza)

---

- [Biblioteche documentali locali (RAG)](#biblioteche-documentali-locali-rag)

## Che cosa fa

- **Un agente è un utente Linux.** Crearne uno nell'interfaccia web crea
  `agent-007` sul sistema, con una home che nessun altro agente può leggere.
  Questo è l'isolamento: quello del kernel, non una sandbox scritta in Python.
- **Gli agenti girano secondo i propri orari.** Ognuno ha il suo crontab, di
  proprietà del suo utente ed eseguito da lui, quindi un agente si sveglia, fa
  il suo lavoro ed esce.
- **Ci parli.** Facendo clic su un agente si apre una chat: chiedigli di fare
  qualcosa e lui usa i suoi strumenti e risponde quando ha finito. La
  conversazione viene ricordata.
- **Una conversazione per agente, non una per persona.** Una scheda che arriva
  a scadenza viene pubblicata in quella stessa chat quando parte l'esecuzione, e
  la risposta compare sotto, quindi la chat di un agente è tutto quello che gli
  è stato chiesto di fare - da te o da un altro agente - e quello che ne ha
  fatto.
- **Condividono una bacheca kanban.** Gli agenti aggiungono schede, le spostano
  e vedono il lavoro gli uni degli altri. Tu guardi su `/kanban/` invece di
  leggere i log.
- **Qualsiasi modello, cloud o self-hosted.** Sono inclusi venticinque provider -
  Anthropic, OpenAI, Google, DeepSeek, Mistral, Qwen, xAI e gli altri; i router
  che stanno loro davanti, OpenRouter, Groq, Together, Vercel e altri ancora; e
  Ollama, llama.cpp e vLLM sul tuo hardware. Ogni agente sceglie il suo, con un
  modello di riserva per quando quello non risponde.
- **Tetti di spesa che lo fermano davvero.** Token, passi, secondi ed
  esecuzioni al giorno, per agente. Altrimenti un agente incustodito su un'API a
  pagamento è una fattura aperta.
- **Memoria configurabile.** Scegli il limite di memoria di ciascun agente nelle
  sue impostazioni, da 1.000 a 1.000.000 di caratteri (8.000 per impostazione
  predefinita). Le scritture troppo grandi vengono rifiutate senza tagliare il
  testo né sostituire la memoria salvata.
- **Una biblioteca documentale per agente.** Carica libri in PDF, EPUB, TXT o
  Markdown. Estrazione, OCR e vettorizzazione restano in locale; gli agenti
  recuperano i passaggi pertinenti e citano le loro fonti. Si configura in
  **RAG**. Il modello di vettorizzazione è EmbeddingGemma 300M per impostazione
  predefinita; una macchina con processore e memoria in abbondanza può passare a
  Qwen3-Embedding 0.6B in **Impostazioni → RAG**.
- **Agenti che puoi spostare.** La scheda **Esporta** di un agente lo scarica
  come `.zip` - a scelta con la sua memoria, il suo modello, la sua biblioteca e
  i file della sua home, mai con una chiave - e **+** lo importa qui o su
  un'altra installazione. Gli agenti già pronti vengono dal
  [repository dei modelli](https://github.com/nipegun/bunch-of-aigents-templates).
- **Strumenti che puoi estendere.** Ogni strumento è un file `.py` in
  `/opt/boa/tools/`. Mettine dentro uno nuovo e compare in **Impostazioni →
  Strumenti**, raggruppato in sottoschede come Automazione e Browser.
- **Competenze condivise.** Una procedura scritta una volta in
  `/opt/boa/skills/` si può dare a quanti agenti vuoi. Quello che un agente
  impara da solo muore nella sua memoria; una competenza no.
- **Un browser ciascuno, con le sue sessioni.** Un agente può accedere a un
  sito, compilare un modulo e fare clic - non solo leggere una pagina - e i suoi
  cookie vivono nella sua home 0700, quindi l'accesso di un agente non è
  l'accesso di tutti gli agenti.
- **Rispondi loro da Telegram o Discord.** Scegli un agente con /agents, o
  rispondi a un messaggio che uno di loro ti ha mandato, e quello che scrivi gli
  arriva, avvia un'esecuzione e torna con la risposta sul tuo telefono. L'intero
  scambio sta anche nella conversazione di quell'agente nell'interfaccia web,
  tutte e due le metà, così una sola schermata continua a mostrare tutto.
- **Audio da Telegram.** **Impostazioni → Audio** sceglie whisper.cpp in locale
  oppure OpenAI, Groq, Mistral, Together AI, Hugging Face o Cloudflare usando
  una chiave API già salvata. Vengono offerti tutti i 30 modelli nativi, da
  scaricare su richiesta. Una risposta vocale arriva al suo agente originale
  come testo e compare nella chat web, con la riproduzione dell'audio
  facoltativa.
- **Una cartella condivisa ciascuno.** La cartella `samba/` di ogni agente è una
  condivisione SMB che porta il nome del suo utente Linux, così puoi metterci
  file da Windows, Linux o macOS.
- **Quindici lingue.** Tedesco, inglese (Regno Unito e Stati Uniti), spagnolo
  (Spagna e Argentina), francese, ebraico, hindi, italiano, giapponese, coreano,
  portoghese (Brasile e Portogallo), russo e cinese semplificato. L'interfaccia,
  la riga che dice ai tuoi agenti in che lingua rispondere, e quello che dicono
  i due bot.

È pensato per una sola persona che lo usa sulla propria LAN.

## Su che cosa gira

Due sistemi, e su ciascuno il sistema di init fa parte del requisito, non è un
dettaglio:

- **Debian con systemd come PID 1.** I dieci servizi sono unità systemd. Su un
  Debian che si avvia con qualsiasi altra cosa non c'è niente che li avvii,
  quindi l'installer controlla `systemctl is-system-running` prima di toccare la
  macchina e si rifiuta se systemd non c'è. Non provarci su una macchina del
  genere: la risposta non cambierà.
- **Alpine con OpenRC.** I dieci servizi sono script OpenRC supervisionati con
  `supervise-daemon`. Non bisogna installare nulla in anticipo: l'installer
  aggiunge `openrc` da solo quando la macchina non ce l'ha.

Su Debian controllalo con `systemctl is-system-running`: deve rispondere
(`running`, `degraded`, `starting`), non stampare «System has not been booted
with systemd as init system (PID 1)». Un container ha bisogno di `systemd
systemd-sysv dbus` installati e di `/sbin/init` come comando.

Oltre al sistema di init, servono:

- Accesso `root`. Nessuno dei due installer usa `sudo`, e nessuno dei due ne ha
  bisogno.
- Circa 500 MB di disco per l'applicazione e il suo ambiente Python.
- `haproxy`, installato dall'installer. Termina il TLS, perché l'intestazione
  PROXY che manda l'HAProxy della macchina arriva prima dell'handshake TLS e lì
  solo un proxy può leggerla.
- Un modello con cui parlare: o una chiave API di un provider cloud, oppure
  Ollama, llama.cpp o vLLM in esecuzione in un punto che puoi raggiungere.

L'installer compila anche **whisper.cpp v1.9.4** in `/opt/boa/whisper/`,
installa FFmpeg e scarica il modello multilingue `base` (circa 142 MiB in più).
La compilazione, le dipendenze di sistema e il browser richiedono altro spazio
su disco. Se manca l'interprete Python, viene installato prima di controllarne
la versione.

Tutto il resto di questo manuale è uguale su entrambi.

## Se usi Alpine

Ogni comando di questo manuale che nomina `systemctl` o `journalctl` è quello di
Debian. L'applicazione è la stessa su Alpine; quello che cambia è il sistema di
init e dove vanno i log:

| Su Debian | Su Alpine |
|---|---|
| `systemctl status boa-web` | `rc-service boa-web status`, oppure `rc-status` per tutti e dieci |
| `systemctl restart boa-web` | `rc-service boa-web restart` |
| `journalctl -u boa-web -f` | `tail -f /opt/boa/logs/boa-web.log` |
| `install-update-reinstall-debian.sh` | `install-update-reinstall-alpine.sh` |

Lì manca una funzione, e non tornerà: non c'è il browser, perché Playwright non
pubblica alcuna build per musl. Gli strumenti del browser restano nell'elenco e
lo dicono quando un agente ne chiama uno.

---

## Installazione

Un installer per distribuzione, ed entrambi accettano le stesse flag. Eseguilo
come `root`.

### Su Debian

> **systemd deve essere in esecuzione sulla macchina.** Esegui prima
> `systemctl is-system-running`: se stampa «System has not been booted with
> systemd as init system (PID 1). Can't operate.», fermati qui. Ogni servizio
> che installa è un'unità systemd, quindi non ci sarebbe niente ad avviarli, e
> l'installer si rifiuta per questo motivo invece di lasciarti un'installazione
> che non serve nulla.

```bash
curl -fsSL https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-debian.sh \
  | bash -s -- --install --email you@example.com
```

Se `curl` non è installato - un Debian minimale spesso non ha né lui né
`wget` - installalo prima, altrimenti la riga qui sopra stampa `curl: command not
found` e si ferma:

```bash
apt-get update && apt-get install -y curl
```

Oppure scarica prima l'installer e leggilo prima di eseguirlo, che è
l'abitudine migliore:

```bash
wget https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-debian.sh
less install-update-reinstall-debian.sh
chmod +x install-update-reinstall-debian.sh
./install-update-reinstall-debian.sh --install --email you@example.com
```

### Su Alpine Linux

Le stesse flag, uno script diverso: scrive servizi OpenRC invece di unità
systemd. Una sola riga, con `wget` e in pipe verso `sh`, perché un Alpine appena
installato non ha né `curl` né bash, mentre quei due li fornisce BusyBox:

```bash
wget -qO- https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-alpine.sh \
  | sh -s -- --install --email you@example.com
```

Usa `curl -fsSL` al posto di `wget -qO-` su una macchina che ce l'ha - e in quel
caso tieni d'occhio quella riga, perché `curl: not found` in pipe verso `sh`
stampa il suo errore e poi **riesce**, senza aver installato nulla.

L'installer è scritto in shell POSIX e non in bash per lo stesso motivo del
`wget`: un Alpine appena installato non ha un bash a cui `| bash -s --` possa
arrivare. Installa bash strada facendo - ogni agente riceve una shell bash -
quindi su una macchina che ce l'ha già, `| bash -s --` funziona altrettanto
bene.

Oppure scaricalo prima e leggilo prima di eseguirlo:

```bash
wget https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-alpine.sh
less install-update-reinstall-alpine.sh
chmod +x install-update-reinstall-alpine.sh
./install-update-reinstall-alpine.sh --install --email you@example.com
```

Una volta in funzione cambiano due cose, ed entrambe dipendono dal sistema, non
da una decisione:

- **Niente browser.** Playwright non pubblica alcuna build per musl e Alpine non
  ne pacchettizza nessuna, quindi `browser.open` e gli altri lo dicono quando un
  agente ne chiama uno. `web.fetch` e `rss.fetch` funzionano come ovunque.
- **`rc-status` invece di `systemctl status`**, e `rc-service boa-web
  restart` al posto di `systemctl restart boa-web`. Vedi
  [Se usi Alpine](#se-usi-alpine).

Su Alpine i servizi rilasciano l'output SSH dell'installer, quindi l'installer
restituisce il controllo della sessione quando finisce.

### Che cosa fa l'installer

1. Crea l'utente di sistema `boa` e l'albero sotto `/opt/boa/`.
2. Installa le dipendenze Python in `/opt/boa/venv/`.
3. Genera un certificato TLS autofirmato, a meno che tu non abbia lasciato un
   `fullchain.pem` e un `privkey.pem` tuoi in `/opt/boa/certificates/`.
4. Chiede se servire l'applicazione su 11080/11443 dietro un HAProxy su 80 e
   443, oppure direttamente su 80 e 443. Passa `--ports proxied|direct` per
   rispondere in anticipo. La risposta viene ricordata, quindi `--update` non la
   chiede più né la cambia di nascosto. Scegliere `direct` manda in pensione
   l'HAProxy della macchina stessa - fermato, tolto da ogni runlevel o
   mascherato, e il suo `/etc/haproxy/haproxy.cfg` cancellato se l'ha scritto
   questo installer, conservato come `haproxy.cfg.before-boa.<date>` se l'ha
   scritto qualcun altro - così che niente occupi 80 e 443 al prossimo avvio. Il
   pacchetto haproxy invece resta: il proxy dell'applicazione è proprio quel
   binario.
5. Crea un agente: `manager`, l'orchestratore. Tutto il resto è un agente
   vuoto, un `.zip` esportato da un agente o un modello del
   [repository dei modelli](https://github.com/nipegun/bunch-of-aigents-templates) -
   `web-navigator`, `os-watcher`, `mail-watcher` e altri - scelto quando premi
   **+**. L'agente vuoto è la prima scelta proposta.
6. Installa e avvia i servizi elencati in [Servizi](#servizi): unità systemd
   su Debian, servizi OpenRC supervisionati con `supervise-daemon` su Alpine.
7. Scrive quello che ha fatto, e la tua password di accesso, in
   `/opt/boa/logs/install.log` (root, modo 0600).
8. Chiede all'applicazione la sua pagina di accesso prima di dire che ha finito.
   Se la pagina non arriva, lo dice, scrive in quello stesso log com'era la
   macchina in quel momento - che cosa ha ricavato curl dalla richiesta, se c'è
   qualcosa in ascolto sulla porta, lo stato dei servizi e le ultime righe di
   quello che hanno stampato - e nomina il log invece di annunciare il successo.
   Un `--update`, prima, rimette anche al suo posto la versione precedente.

### Dove si trova la password

L'indirizzo email che indichi è l'unico accesso. La password viene generata per
te; leggila con:

```bash
cat /opt/boa/logs/install.log
```

Quell'unico file è entrambe le cose: il log completo dell'installazione e le
credenziali che ha generato. La pagina di accesso lo nomina, così nessuno deve
ricordarsi dove si trova.

## Aggiornare e reinstallare

```bash
./install-update-reinstall-debian.sh --update      # mantiene agenti e dati
./install-update-reinstall-debian.sh --reinstall   # prima cancella tutto
```

Su Alpine sono le stesse due flag, sull'altro script:

```bash
./install-update-reinstall-alpine.sh --update
./install-update-reinstall-alpine.sh --reinstall
```

`--reinstall` cancella ogni agente, ogni home, ogni crontab e la bacheca kanban.
Chiede conferma a meno che tu non passi `--yes`.

Un'installazione morta a metà - un download fallito, una rete caduta - si
completa eseguendo di nuovo `--install`: riprende da dove si era fermata, e
`--update` lo dice se ne trova una.

Le altre due flag, `--backup` e `--restore`, sono spiegate in
[Backup e ripristino](#backup-e-ripristino).

## Aprire l'applicazione

Nella modalità predefinita `proxied`, l'HAProxy dell'applicazione ascolta su
`127.0.0.1:11443` (HTTPS) e `127.0.0.1:11080` (HTTP, che reindirizza). Queste
porte non sono raggiungibili dall'esterno del server: è l'HAProxy della
macchina a servire la LAN, e inoltra a 11443 con `send-proxy-v2` in modo che
l'indirizzo reale del client sopravviva. In modalità `direct` l'applicazione
ascolta lei stessa su 80 e 443, senza niente davanti.

Con questo a posto, apri:

```
https://your-server/
```

Il certificato è autofirmato, a meno che tu non abbia lasciato certificati tuoi
in `/opt/boa/certificates/`, quindi il browser ti avviserà una volta.

### Come deve essere l'HAProxy della macchina

Il backend che punta a questa applicazione ha bisogno di due cose:

```
backend https-out
  mode tcp
  server srv-https-out 127.0.0.1:11443 check port 11080 send-proxy
```

- **`send-proxy`**, perché l'indirizzo reale del client arrivi
  all'applicazione. Senza, ogni richiesta sembra arrivare da 127.0.0.1 e il
  limite di tentativi di accesso smette di essere per indirizzo.
- **`check port 11080`**, perché il controllo di salute bussi alla porta HTTP in
  chiaro e non a quella TLS. Un controllo TCP sulla porta TLS si connette e
  riattacca senza handshake, e l'HAProxy dell'applicazione registra ciascuno
  come un fallimento dell'handshake SSL: una riga ogni due secondi, per sempre.
  Le due porte appartengono a un solo processo, quindi se una risponde c'è anche
  l'altra. Non aggiungere `check-send-proxy`: 11080 non accetta il protocollo
  PROXY.
- **Niente `option ssl-hello-chk`.** Il suo ClientHello è anteriore a TLS 1.2,
  quindi un backend che richiede TLS 1.2 - questo, e qualsiasi Apache o nginx
  moderno - non supera il controllo e viene segnato come giù per sempre. Il
  sintomo è un 503 da un servizio che funziona perfettamente. Un semplice
  `check` verifica già che la porta risponda.

## Accedere

Apri `https://your-server/` e accedi con l'indirizzo email che hai dato
all'installer e la password che ha generato. Se non ce l'hai:

```bash
cat /opt/boa/logs/install.log
```

Quel file è l'intero log dell'installazione con le credenziali in fondo, e la
pagina di accesso lo nomina proprio per questo momento.

**Esci** apre una conferma al centro dello schermo. Conferma per chiudere la
sessione, oppure scegli **Annulla** o premi Esc per restare collegato.

C'è un solo account. Cambia la sua password in **Impostazioni → Account**.
Cambiarla richiede anche quella attuale: è questo che la rende una modifica
fatta da te e non da chiunque trovi il browser aperto. Chiude inoltre ogni altra
sessione, su ogni altro dispositivo, all'istante - ed è proprio questo lo scopo
di cambiarla quando pensi che qualcun altro ne abbia una.

La prima volta che apri l'applicazione dopo un aggiornamento, ti chiede di
accedere di nuovo. Le sessioni di prima dell'aggiornamento non portano traccia
di quando sono state concesse, e a «non lo so dire» si risponde chiedendo.

Dopo dieci tentativi falliti dallo stesso indirizzo l'accesso viene chiuso per
quindici minuti, anche per le password corrette.

## Primi passi

1. Accedi con la tua email e la password generata.
2. Se l'agente userà un provider cloud, salva prima la sua chiave in
   **Impostazioni → Chiavi API**: l'elenco dei provider propone solo i provider
   cloud che hanno una chiave (vedi [Chiavi API](#chiavi-api)).
3. Premi **+** nella barra laterale per creare il tuo primo agente.
4. Scegli il suo provider e il suo modello. Per Ollama sulla stessa macchina, i
   valori predefiniti sono già giusti. Per addebitare questo singolo agente a un
   altro account, dagli una chiave tutta sua (vedi
   [Dare un modello a un agente](#dare-un-modello-a-un-agente)).
5. Scrivi il suo prompt di sistema: a che cosa serve, e che cosa significa
   «fatto».
6. Dagli gli strumenti di cui ha bisogno. Comincia con quelli del kanban.
7. Premi **Esegui ora** e guarda la bacheca.
8. Quando fa quello che vuoi, dagli una pianificazione.

## L'interfaccia

Il logo circolare blu mostra tre agenti robotici con pannelli facciali chiari,
visiere scure e occhi blu, in abito nero, camicia bianca e cravatta scura.
Compaiono dalla vita in su, con un agente centrale più grande. Il logo compare
nella pagina di accesso, nella barra laterale e nella scheda del browser.

La barra laterale a sinistra elenca i tuoi agenti. Ognuno mostra il suo id, il
suo nome, quante volte è stato eseguito e quanti token ha speso. Tutti i
riquadri hanno la stessa altezza, quindi un nome lungo viene tagliato con i
puntini di sospensione - passaci sopra con il mouse per leggerlo per intero. Il
quadrato intorno all'id è cerchiato di verde quando l'agente è acceso e di
rosso quando non lo è.

**Quando un agente sta lavorando, un segmento illuminato percorre in senso
orario quell'anello verde.** Ti dice che l'agente è nel mezzo di un'esecuzione
proprio adesso - non che cosa sta facendo, solo che sta facendo qualcosa.
Comincia a girare appena gli mandi un messaggio in chat o premi **Esegui ora**,
e si ferma quando l'esecuzione finisce, che l'esecuzione venga da te, dalla sua
pianificazione o da una scheda arrivata a scadenza. L'anello viene controllato
ogni pochi secondi, quindi può restare un attimo indietro.

In fondo alla barra laterale, due puntini mostrano se i servizi in background
sono in esecuzione. Se uno dei due è rosso, gli agenti non verranno eseguiti —
vedi [Quando qualcosa non funziona](#quando-qualcosa-non-funziona).

Il pulsante **+** crea un agente.

## L'agente con cui si parte

L'installazione ne crea esattamente uno.

**`manager` (agent-000)** coordina gli altri. Scompone gli obiettivi in schede
e le distribuisce. È acceso fin dall'inizio.

Ed è volutamente tutto qui: un'installazione che arriva con agenti che nessuno
ha chiesto è un'installazione che parte con cose da spegnere. Tutto il resto è un
**modello** del repository dei modelli, o un `.zip` che qualcuno ha esportato,
proposto quando premi **+**.

## Da dove viene un nuovo agente

Premi **+** e ti viene chiesto da dove partire:

| Scelta | Che cosa fa |
|---|---|
| **Agente vuoto** | Nessun prompt, nessuno strumento, nessuna pianificazione. Scrivilo tu. |
| **Importa da un file .zip** | Un agente esportato dalla sua scheda **Esporta**, qui o su un'altra installazione. |
| **Importa da un modello GitHub** | Uno degli agenti del repository dei modelli, scelto da un elenco. |

L'**agente vuoto** è in cima all'elenco, perché è l'unica risposta sempre giusta
e ogni altra è una scorciatoia per arrivarci.

### Modelli da GitHub

I modelli vivono in un repository tutto loro,
[bunch-of-aigents-templates](https://github.com/nipegun/bunch-of-aigents-templates),
una cartella ciascuno, così uno nuovo arriva alla tua installazione senza
doverla aggiornare. Quando scegli **Importa da un modello GitHub**, il server
scarica quel repository (un unico `.tar.gz`, conservato per cinque minuti) ed
elenca i suoi agenti in ordine alfabetico, ognuno con la sua descrizione nella
tua lingua, le famiglie di strumenti con cui arriva, ogni quanto si sveglia e se
attiva la sua biblioteca. Uno strumento che questa installazione non ha viene
escluso, e l'elenco lo dice. Un modello che non supera i controlli non viene
proposto, e una riga dice quanti ne sono stati esclusi.

Questi sono i modelli che il repository contiene oggi:

| Modello | Che cosa fa |
|---|---|
| **backup-watcher** | Controlla che i tuoi backup siano stati eseguiti, siano recenti e non siano sospettosamente piccoli. |
| **cert-watcher** | Avvisa quando un certificato TLS sta per scadere, finché c'è ancora tempo. |
| **disk-cleaner** | Trova che cosa sta riempiendo il disco e dice che cosa si potrebbe togliere. Propone; non cancella mai. |
| **kanban-watcher** | Legge la bacheca ogni mattina dei giorni feriali e scrive un breve riassunto. |
| **log-watcher** | Legge i log che gli indichi e segnala che cosa è nuovo o è diventato frequente. |
| **mail-watcher** | Sorveglia una casella di posta e agisce su quello che arriva, seguendo le regole che scrivi nel suo prompt. |
| **news-watcher** | Legge i feed RSS che elenchi nel suo prompt e segnala quello che corrisponde alle tue regole. |
| **os-watcher** | Sorveglia questa macchina: disco, memoria, swap, carico, e se i servizi sono attivi. |
| **rag-consultant** | Risponde alle domande a partire dai documenti della sua biblioteca RAG, citando il passaggio dietro ogni affermazione, e lo dice quando i documenti non coprono qualcosa. |
| **site-watcher** | Controlla che i siti che elenchi rispondano, rispondano in fretta e dicano ancora quello che dicevano prima. |
| **web-navigator** | Guida il suo browser per fare quello che chiedi su un sito: cercare, accedere, compilare un modulo, cliccare da una pagina all'altra, e riferire che cosa ha trovato. |

`web-navigator` e `rag-consultant` non hanno una pianificazione: lavorano quando
glielo chiedi, e la richiesta è il compito. `web-navigator` è anche quello che
mostra a che cosa serve il browser installato - accede, clicca e compila moduli,
mentre gli altri leggono pagine. Non scriverà una password, non comprerà niente
e non premerà un pulsante di invio: arriva a quel passo e si ferma, dicendo
quale pulsante concluderebbe il lavoro.

`rag-consultant` risponde dalla sua biblioteca documentale, ed è l'unico modello
che arriva con quella biblioteca attivata: i suoi strumenti restano bloccati
finché la biblioteca è spenta. Prima che serva a qualcosa, carica dei documenti
nella sua scheda **RAG** (vedi
[Biblioteche documentali locali](#biblioteche-documentali-locali-rag)) e scegli
un modello linguistico. Ogni affermazione nelle sue risposte rimanda alla
pagina del documento da cui viene; quando i documenti non coprono qualcosa, lo
dice invece di riempire il vuoto. Il suo tetto di token (40.000 per esecuzione)
è più alto di quello degli altri, perché i passaggi che legge contano nel tetto.

Ogni modello dice, prima che tu lo scelga, con quali famiglie di strumenti
arriva e ogni quanto si sveglia. Un modello è un insieme di permessi tanto
quanto è un prompt: «sorveglia una casella di posta» non ti dice che arriva in
grado di cancellare la posta.

Ogni modello arriva **spento e senza modello linguistico**: sceglierne uno ti
dà il suo prompt, i suoi strumenti e una pianificazione suggerita, e poi aspetta
che tu scelga un provider e lo accenda.

Sono punti di partenza. Cambia il prompt, gli strumenti, la pianificazione -
tutto quanto - e parecchi di loro dicono nel loro stesso prompt che cosa devi
completare prima che servano a qualcosa, invece di fallire alle tre del
mattino.

**Impostazioni → Agenti** indica da quale repository e da quale branch viene
l'elenco: per impostazione predefinita quello del progetto, oppure un fork,
oppure uno tuo con la stessa struttura. Una macchina senza accesso a GitHub può
usare un percorso `file://` che contiene `archive/refs/heads/<branch>.tar.gz`,
la stessa struttura che accetta l'installer. Quando il repository non è
raggiungibile, l'elenco dice quale indirizzo ha fallito; importare un `.zip`
continua a funzionare.

### Importare un .zip

1. Scegli il `.zip`. Viene caricato a pezzi, con una percentuale, così arriva a
   destinazione anche una biblioteca di centinaia di MiB.
2. Il server controlla l'intero pacchetto prima di qualsiasi altra cosa. Niente
   al suo interno può essere un percorso che esce dalla home dell'agente, un
   file nascosto come `.ssh` o `.bashrc`, la chat o il registro delle
   esecuzioni, o una pianificazione che porta con sé un comando. Quando qualcosa
   non va ti viene detto che cosa, e non viene creato nulla.
3. Ti viene mostrato che cosa porterebbe: la sua descrizione, i suoi strumenti
   (e quelli che mancano a questa installazione), i suoi orari, e se porta la
   sua memoria, file per la sua home, documenti della biblioteca o un modello.
   Conferma e dagli un nome.
4. Si installa in background, con l'avanzamento sullo schermo. I documenti della
   biblioteca vengono caricati uno per uno e indicizzati di nuovo qui. Se
   qualcosa fallisce a metà, l'agente viene eliminato di nuovo invece di restare
   installato a metà.

Anche un agente importato arriva **spento**. Se nomina un provider, la sua
chiave va impostata su questa installazione: le chiavi non viaggiano mai in un
`.zip`.

Se preferisci che non ti venga chiesto nulla, disattiva **Chiedere da dove parte
un nuovo agente** in **Impostazioni → Interfaccia**: **+** allora va dritto a un
agente vuoto.

### Nessun agente ha root

Nemmeno uno, orchestratore compreso. Questo è l'intero modello di isolamento, e
conviene averlo chiaro perché decide che cosa può fare un agente come
`os-watcher`:

- **Guardare non richiede privilegi.** `df`, `free`, `uptime`, `nproc`,
  `systemctl is-active` funzionano tutti come utente normale. Un agente può
  vedere un disco che si riempie molto prima che sia pieno.
- **Riparare di solito li richiede, e lui non li ha.** I prompt gli dicono di
  indicare esattamente che cosa eseguirebbe invece di provarci e fallire: una
  scheda che dice «serve root: journalctl --vacuum-size=200M libererebbe circa
  1,2G» vale più di un tentativo fallito.

Se vuoi che qualcosa venga riparato automaticamente, metti quel comando nel
crontab di root. Un agente che decide da solo di cancellare file come root non è
una funzione che qualcuno voglia alle tre del mattino.

## Creare il tuo primo agente

Premi **+**, scegli un agente vuoto, un `.zip` o un modello, e dagli un nome.
Questo crea, sul server:

- l'utente Linux `agent-001`,
- la sua home in `/opt/boa/agents/001/`, modo 0700,
- `info.json`, `system-prompt.md` e un token API al suo interno.

L'id è il numero libero più basso. `000` è riservato all'orchestratore.

Un nuovo agente parte con gli strumenti del kanban e nient'altro, e con tetti
prudenti. Non ha una pianificazione, quindi non fa niente finché non gliene dai
una o premi **Esegui ora**.

## Parlare con un agente

Fai clic su un agente nella barra laterale e ottieni la sua chat. Scrivi che
cosa vuoi che faccia e premi Invio; Maiusc+Invio va a capo.

La casella in cui scrivi resta ferma, subito sopra la barra di stato in fondo
alla pagina: scorre solo la conversazione sopra di essa, quindi non è mai
nascosta e non devi mai scorrere in giù per raggiungerla. Finché è vuota ti
ricorda, in grigio, come si comporta Invio - o che l'agente sta ancora
lavorando - e su un telefono stretto si allarga di una o due righe perché quel
promemoria non venga mai tagliato.

Un messaggio è un'esecuzione: l'agente usa i suoi strumenti, fa il lavoro e
risponde quando ha finito. Può volerci qualche minuto, quindi la casella di
scrittura è disattivata mentre lavora e la risposta compare quando arriva. Ogni
risposta mostra quanto è costata, in token e passi.

Le risposte vengono visualizzate come markdown - titoli, tabelle, elenchi,
citazioni e blocchi di codice - perché è così che scrive un modello. I tuoi
messaggi vengono mostrati esattamente come li hai scritti. Un link è un link
solo quando punta a http o https; qualsiasi altra cosa resta il testo che era.

La conversazione viene ricordata. Gli ultimi dieci scambi vengono ripassati al
modello a ogni messaggio, così l'agente sa di che cosa stavate parlando - e così
un thread lungo costa di più per messaggio di uno corto. **Svuota la
conversazione** ricomincia da capo.

Parlare con un agente **non** conta per il suo tetto di esecuzioni al giorno:
quel tetto esiste per fermare una pianificazione incustodita, non per impedirti
di scrivere. I tetti per esecuzione su token, passi e tempo invece si
applicano.

Ogni agente ha la sua conversazione, salvata nella sua home, e nessun agente può
leggere quello che hai detto a un altro.

La conversazione non è solo quello che hai scritto. Quando una delle schede
dell'agente arriva a scadenza, la scheda viene pubblicata in quella stessa chat
nel momento in cui parte l'esecuzione, e la risposta dell'esecuzione compare
sotto - così aprire un agente mostra tutto quello che gli è stato chiesto di
fare, da te o da un altro agente, e quello che ne ha fatto. Vedi
[Quando una scheda viene eseguita](#quando-una-scheda-viene-eseguita).

### API Calls

Il nome dell'agente compare sopra le schede Chat e API Calls. Per impostazione
predefinita è visibile solo **Chat**. Per mostrare l'altra scheda, apri la
chiave inglese dell'agente, seleziona **Interfaccia**, attiva **Mostra la scheda
API Calls** e premi **Salva**. La scelta viene salvata per questo agente sul
server. Aprire o ricaricare un agente parte sempre da Chat, anche quando API
Calls è attiva.

**API Calls** mostra il JSON effettivamente inviato, compresi il prompt completo
dell'agente, la conversazione, le definizioni degli strumenti e i risultati
degli strumenti mandati in quella richiesta. La richiesta più recente è espansa;
espandi un'altra chiamata per esaminarla. Le nuove chiamate compaiono mentre
l'agente lavora, comprese le richieste fallite, i nuovi tentativi dell'SDK e le
chiamate al suo modello di riserva. Rientri e colori rendono leggibile il JSON
senza visualizzarlo come chat né arrotondare i grandi identificatori numerici.

Le ultime 100 richieste complete vengono conservate separatamente dalla
conversazione. Svuotare la Chat non le cancella. La registrazione comincia con
questa versione; le richieste precedenti non si possono ricostruire. Le
intestazioni di autenticazione non vengono registrate.

## Impostazioni dell'agente

Il titolo mostra **Impostazioni dell’agente 001**, con l'id dell'agente
selezionato. **Esegui ora** compare solo nell'area di lavoro che contiene Chat e
API Calls. Per eliminare un agente, apri **Generale → Elimina agente** e conferma
il suo nome nella finestra di dialogo. L'eliminazione è una sezione separata
sotto Identità.


La chat è quello che ottieni facendo clic su un agente. Tutto il resto -
modello, strumenti, tetti, prompt di sistema, pianificazione - sta dietro la
**chiave inglese** a destra del riquadro dell'agente nella barra laterale.

## Esportare un agente

L'ultima scheda delle impostazioni di un agente, **Esporta**, lo scarica come
`.zip` che **+ → Importa da un file .zip** può installare, qui o su un'altra
installazione. La sua configurazione, il suo prompt di sistema e i suoi orari ci
vanno sempre. Quattro cose ci vanno solo se le spunti, e ogni casella dice in
anticipo che cosa aggiungerebbe:

| Opzione | Che cosa aggiunge |
|---|---|
| **Memoria** | Il suo `memory.md`, con quanti caratteri contiene |
| **Provider e modello** | Quale provider e quale modello usa. Mai la chiave |
| **Documenti della biblioteca** | Gli originali della sua biblioteca con le loro informazioni (titolo, anno...). Vengono indicizzati di nuovo dove vengono importati |
| **File della sua cartella personale** | I suoi script, la sua cartella `samba` e qualsiasi altra cosa tenga nella sua home. Possono contenere cose che non condivideresti, quindi l'elenco dei file viene mostrato prima che tu scarichi |

Alcune cose non ci vanno mai, qualunque cosa spunti: le chiavi API, il token
dell'agente, le credenziali dei canali, la sua chat, il suo registro delle
esecuzioni, le sue sessioni del browser e i file nascosti della sua home. Dal
suo crontab viaggiano solo gli orari che avviano l'agente, non altri comandi che
qualcuno ci abbia scritto: un `.zip` che portasse comandi li eseguirebbe sulla
macchina in cui viene importato.

## Cartelle condivise Samba

Ogni agente ha una cartella `samba/` nella sua home, esportata automaticamente
con il suo nome utente Linux. Per esempio, la condivisione **agent-001** punta
solo a `/opt/boa/agents/001/samba/`. Rinominare l'agente in Generale non
rinomina la condivisione. Il resto della sua home e la sua configurazione
protetta non vengono esportati.

1. Apri **chiave inglese → Samba** dell'agente.
2. In **Nuova password Samba** inserisci una password di almeno 8 caratteri, scegli i permessi e premi **Salva**.
3. Apri l'indirizzo Windows o SMB mostrato nella scheda - `\\server\agent-001` su Windows, `smb://server/agent-001` su Linux e macOS - e accedi con il nome utente mostrato e quella password.

La condivisione parte attivata, visibile nell'elenco delle condivisioni del
server e configurata per lettura e scrittura, con l'accesso ospite disattivato.
Prima della sua prima connessione autenticata, imposta la sua password in
questa scheda. Nei salvataggi successivi, un campo password vuoto mantiene la
password esistente. Le credenziali Samba sono separate dalle credenziali di
accesso a Linux; impostarle non sblocca l'account Linux dell'agente.

| Impostazione | Effetto |
|---|---|
| Condividi questa cartella | Attiva o disattiva questa risorsa senza cancellarne i file |
| Autenticazione | Nome utente e password dell'agente per impostazione predefinita; accesso ospite solo se selezionato esplicitamente |
| Permessi | Sola lettura o lettura e scrittura via SMB; l'agente può comunque lavorare sui suoi file locali |
| Visibilità e descrizione | Se compare nell'elenco delle condivisioni del server, e la sua descrizione |
| Permessi dei nuovi file e delle nuove cartelle | Modi Unix in ottale, inizialmente `0600` / `0700`; i file esistenti mantengono i loro modi |

Il nome e il percorso della condivisione sono fissi. La cartella resta privata
per il suo proprietario Linux. Salvare impostazioni di accesso modificate chiude
le connessioni esistenti di questa condivisione, così i client si riconnettono
con i nuovi permessi. Le condivisioni degli altri agenti restano attive. La
password stessa non viene mai restituita dall'API né salvata in `info.json`.

`--update` aggiunge cartelle e condivisioni Samba agli agenti esistenti,
`agent-000` compreso. Eliminare un agente rimuove la sua condivisione e il suo
account Samba insieme alla sua home. `--backup` / `--restore` conservano i dati
condivisi, le impostazioni, le password Samba e le identità degli account. Il
ripristino controlla la modalità delle porte web salvata, comprese le
installazioni che servono direttamente la 443.

Samba usa la porta TCP **445**, indipendentemente dal proxy web. In Docker
questa porta va pubblicata esplicitamente. BoA esegue un suo servizio
`boa-samba`, con una sua configurazione e un suo database delle password sotto
`/opt/boa/samba/`; non sovrascrive né si appropria della configurazione di un
altro server Samba, e l'installer si rifiuta di prendere il controllo di
un'installazione Samba esistente che non gestisce lui.

## Dare un modello a un agente

In **LLM**, scegli un provider. L'elenco è corto apposta: propone i tre
provider self-hosted, che non hanno bisogno di chiave, e ogni provider cloud la
cui chiave è impostata in **Impostazioni → Chiavi API**. Un provider cloud senza
chiave porterebbe l'agente fino alla sua prima esecuzione e lì fallirebbe,
quindi non viene proposto. Imposta la sua chiave e compare.

Un agente già configurato con un provider continua a vederlo nell'elenco anche
se la sua chiave viene rimossa, con l'indicazione *(nessuna chiave
configurata)* - altrimenti la casella mostrerebbe un provider che nessuno ha
scelto e lo salverebbe al clic successivo.

**Su hardware tuo.** Nessuna chiave, e la casella URL di base è dove ascolta il tuo server.

| Provider | Modelli elencati | Modello predefinito |
|---|---|---|
| `ollama` | 23 | `gpt-oss:20b` |
| `llamacpp` | 1 | `local-model` |
| `vllm` | 3 | il modello lo indichi tu |

**Aziende che servono i modelli che hanno costruito.**

| Provider | Modelli elencati | Modello predefinito |
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

**Host e router, che servono modelli costruiti da altri.** Una sola chiave raggiunge molti modelli; l'id del modello indica quale.

| Provider | Modelli elencati | Modello predefinito |
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

Un provider ha bisogno di due valori nella casella della chiave: **Cloudflare
Workers AI** costruisce il suo indirizzo a partire dall'id dell'account, quindi
la sua chiave si scrive `account-id:api-token`, con entrambe le metà prese dal
pannello di Cloudflare. La casella in **Impostazioni → Chiavi API** lo dice.

Il campo del modello suggerisce quello che serve quel provider, e filtra l'elenco mentre scrivi - ma è una normale casella di testo, quindi un modello uscito stamattina si può semplicemente scrivere. Quei suggerimenti vengono da `/opt/boa/config/providers/<provider>.json`, che puoi modificare sul server; un aggiornamento non sovrascrive mai un file che hai cambiato.

I provider self-hosted non hanno bisogno d'altro se girano sulla stessa
macchina.

**URL di base** compare solo per `ollama`, `llamacpp` e `vllm`, ed è dove
ascolta il tuo server - il valore predefinito è la porta abituale su questa
macchina, che è giusta quando il modello gira accanto all'applicazione. Scegli
un provider cloud e la casella sparisce: quell'indirizzo è fisso, questa
installazione ce l'ha già, e l'unica cosa che una casella lì potrebbe fare è
lasciare che un errore di battitura rompa un agente funzionante. Il modello di
riserva funziona allo stesso modo.

Per un provider cloud, la strada più semplice è la scheda **Chiavi API** nelle Impostazioni, che poi usano tutti gli agenti su quel provider. Per dare a questo singolo agente una chiave diversa, scrivila nella sua home, come root:

```bash
mkdir -p /opt/boa/agents/001/keys
echo "sk-..." > /opt/boa/agents/001/keys/anthropic.key
chown -R agent-001:agent-001 /opt/boa/agents/001/keys
chmod 700 /opt/boa/agents/001/keys
chmod 600 /opt/boa/agents/001/keys/anthropic.key
```

Il nome del file è il nome del provider. Ogni agente legge solo la sua chiave,
quindi un agente non può spendere il budget di un altro.

### Chiavi API

Le Impostazioni hanno una scheda **Chiavi API**: una chiave per ogni provider
cloud, condivisa da tutti gli agenti che lo usano. I provider self-hosted non
sono elencati, perché non ne hanno bisogno.

Una chiave viene salvata in `/opt/boa/config/apikeys/<provider>.key`. La
directory è `0700` e i file `0600`, tutti di proprietà dell'utente web, quindi
nessun agente può leggerne nessuno: né la chiave di un altro provider, né la
propria. Quando un agente viene eseguito, l'API degli agenti gli consegna la
chiave **del provider con cui quell'agente è configurato, e di nessun altro**:
un agente su Ollama non può chiedere la chiave di Anthropic.

Le installazioni fatte prima che questa directory venisse rinominata tengono le
loro chiavi in `/opt/boa/config/keys/`; `--update` le sposta e rimuove la
vecchia directory.

Conviene essere chiari su che cosa questo protegge e che cosa no. Un agente che
usa legittimamente un provider a pagamento tiene la sua chiave mentre gira - gli
serve per fare la chiamata, e un agente con `bash.run` potrebbe stamparla.
Quello che l'archivio condiviso impedisce è che un agente raccolga le chiavi di
provider che non usa, e tiene tutte le chiavi fuori dalle home degli agenti,
dove un solo backup finito nel posto sbagliato le esporrebbe tutte insieme.

Per addebitare un agente a un altro account, metti una chiave nella home di
quell'agente in `keys/<provider>.key`. Quella prevale su quella condivisa.

## Scrivere un prompt di sistema

Il prompt di sistema è ciò che l'agente è. Viene salvato come `system-prompt.md`
nella home dell'agente e lo modifichi nell'interfaccia.

Che cosa funziona:

- **Di' a che cosa serve l'agente**, in una o due frasi.
- **Di' che cosa significa «fatto».** Un agente senza una definizione di «fatto»
  o si ferma troppo presto o non si ferma mai.
- **Di' che cosa fare quando è bloccato.** Senza questo, i modelli si inventano
  un modo per aggirare l'ostacolo. «Se non puoi farlo, dillo sulla bacheca e
  fermati» basta.
- **Digli di leggere prima la bacheca.** È l'unica memoria che ha tra
  un'esecuzione e l'altra.

Che cosa non funziona: dirgli di non usare uno strumento. Se non vuoi che usi
uno strumento, non darglielo — il prompt è un suggerimento, l'elenco degli
strumenti viene fatto rispettare.

## Che cosa ricorda un agente

Ogni agente ha un `memory.md` nella sua home, e quel file è l'unica cosa che si
porta da un'esecuzione all'altra. Ci scrive con `memory.append` quando impara
qualcosa che vale la pena tenere, e lo riordina con `memory.replace`.

L'intero file viene caricato all'inizio di ogni esecuzione, ed è questo che lo
rende utile e anche ciò che lo fa costare: ogni carattere viene pagato a ogni
chiamata al modello. In **Impostazioni dell'agente → Memoria → Limite della
memoria (caratteri)** scegli un limite da 1.000 a 1.000.000 di caratteri. Il
valore predefinito è 8.000, anche per gli agenti esistenti. All'agente viene
chiesto di riordinare la sua memoria quando supera il 75% del limite.

Il contatore mostra il conteggio attuale e il limite selezionato, spazi e a capo
compresi. Puoi aumentare il limite e incollare una memoria più grande nello
stesso salvataggio. Se il testo supera il limite selezionato, di quella
richiesta di impostazioni non viene salvato nulla: accorcia il testo o alza il
limite. La memoria precedente resta intatta; le nuove scritture non aggiungono
mai `[truncated]`. Il testo scartato in precedenza va incollato di nuovo
dall'originale. L'intera memoria deve comunque entrare nel contesto del modello
scelto insieme al prompt, alla conversazione e agli strumenti.

Cose buone da tenere: dove sta una cosa, com'era davvero un comando, che cosa
preferisci tu. Non il diario di quello che ha fatto - a quello serve la bacheca.

Puoi leggerla e correggerla tu stesso in **Memoria** nelle impostazioni
dell'agente. Un fatto sbagliato su cui un agente continua ad agire vale la pena
di correggerlo a mano.

## Biblioteche documentali locali (RAG)

Ogni agente ha la sua biblioteca sotto `/opt/boa/agents/<id>/rag/`. Sono
supportati file PDF, EPUB, TXT in UTF-8 e Markdown. L'installer prepara il
modello di vettorizzazione locale - EmbeddingGemma 300M Q8 (circa 318 MiB), a
meno che non ne sia stato scelto un altro (vedi
[Scegliere il modello di vettorizzazione](#scegliere-il-modello-di-vettorizzazione)) -
il suo motore llama.cpp e l'OCR.
Estrazione, OCR, vettorizzazione dei documenti e vettorizzazione delle domande
avvengono su questo server. I passaggi recuperati vengono inviati al provider di
risposta selezionato per l'agente, compresi i provider cloud quando sono
configurati. Non è disponibile alcun endpoint di vettorizzazione esterno.
Installazione, aggiornamenti, importazione dei documenti, OCR e
backup/ripristino sono stati verificati su Debian 13 e Alpine 3.24, compreso
l'avvio dei servizi dopo un riavvio.

1. Apri **Impostazioni → RAG** e controlla che il motore locale sia pronto.
2. Apri la scheda **RAG** di un agente, attiva il recupero e salva l'agente. Il
   modello **rag-consultant** arriva con il recupero già attivato.
3. Scegli i file e fai clic su **Carica documenti**. I file grandi viaggiano a
   blocchi. In alternativa, copia dei file completi in `rag/inbox/` e fai clic
   su **Importa file da rag/inbox**. Gli originali importati vengono spostati
   nell'archivio dei documenti gestito.
4. Aspetta **Pronto**. Estrazione e vettorizzazione avvengono in background; gli
   altri documenti pronti restano consultabili. La pagina mostra l'avanzamento e
   gli errori.
5. Prova una domanda con **Cerca nella biblioteca**, oppure chiedi all'agente
   nella sua chat normale. Le citazioni rimandano alla pagina del PDF di origine
   o all'EPUB/documento originale.

Gli errori di importazione da `rag/inbox/` compaiono sopra l'elenco dei
documenti. Gli originali falliti restano nella inbox per essere corretti.
L'indicizzazione elabora lotti di dimensione limitata, così i documenti piccoli
non devono aspettare un giro dello scheduler tra un libro e l'altro.

I controlli di **Informazioni del documento** modificano, in quest'ordine, anno
di pubblicazione, titolo, sottotitolo, autore/i, versione, lingua ed etichette.
L'anno è facoltativo e accetta fino a quattro cifre. Il sottotitolo, quando c'è,
viene mostrato nell'elenco dei documenti subito sotto il titolo. Sottotitolo,
anno, autore, versione e lingua viaggiano con ogni passaggio che l'agente
recupera, così può distinguere documenti con lo stesso titolo, datare e
attribuire quello che cita, e distinguere edizioni in disaccordo tra loro.
Sostituire un file mantiene consultabile il documento precedente
finché il nuovo non ha finito l'indicizzazione. Se il motore di vettorizzazione
locale si ferma mentre un documento viene indicizzato (un aggiornamento, un
riavvio), il documento torna a **In coda** con il messaggio «Local embeddings
are unavailable» e, quando il motore risponde di nuovo, continua da dove si era
fermato; non c'è niente da reindicizzare. Reindicizza ricostruisce un documento; Annulla ferma il suo lavoro
in sospeso; Elimina lo toglie dalle ricerche future. I filtri per lingua e
versione usano i metadati che hai inserito. Le citazioni EPUB identificano i
capitoli, non numeri di pagina inventati. I PDF scansionati richiedono le lingue
OCR installate sul server; inglese e spagnolo sono installati per impostazione
predefinita (`eng+spa`). I file non supportati o cifrati segnalano un errore
invece di un indice vuoto dato per riuscito.

**Modalità di risposta** decide fin dove l'agente può andare oltre i suoi
documenti; la riga sotto l'elenco dice che cosa fa la modalità scelta.

- **Documenti e conoscenze generali**: l'agente può usare entrambi, tenuti
  separati.
- **Sono richieste fonti documentali**: l'agente deve cercare lui stesso nella
  biblioteca prima di rispondere; una risposta data senza cercare gli viene
  rimandata indietro una volta. Se l'esecuzione non ha recuperato nessun
  passaggio, ottieni la frase fissa «The document library does not contain
  enough information to answer this question» (in italiano: «La biblioteca di
  documenti non contiene informazioni sufficienti per rispondere a questa
  domanda») invece di quello che ha scritto il modello.
- **Solo documenti (verificato)**: come la precedente, e in più ogni paragrafo e
  ogni voce di elenco della risposta deve citare un passaggio recuperato in
  quell'esecuzione. Ogni paragrafo viene controllato: nessuna citazione, una
  citazione a un passaggio che non è stato recuperato, o un significato lontano
  dal passaggio che cita (misurato con il motore di vettorizzazione locale)
  rimandano indietro la risposta una volta, con l'elenco di quei paragrafi.
  Quello che dopo è ancora senza sostegno viene rimosso, e un'ultima riga dice
  quanti paragrafi sono stati tolti. Se non resta niente di sostenuto, ottieni
  la frase fissa. Se il motore non è raggiungibile per fare il controllo, la
  risposta viene trattenuta invece di essere mostrata senza controllo.

Quello che la modalità verificata non può fare è dimostrare che un paragrafo
citato dica esattamente quello che dice il suo passaggio. Nelle nostre
misurazioni un paragrafo che contraddice il suo passaggio, o che aggiunge
qualcosa sullo stesso argomento, ottiene lo stesso punteggio di uno fedele;
quello che il controllo coglie è un paragrafo che cita un passaggio su
qualcos'altro, e un paragrafo senza alcuna fonte. Non è esatto in nessuna delle
due direzioni: nei nostri test ha rimosso circa 6 paragrafi fedeli su 100 -
soprattutto voci di elenco brevi e riassunti di una riga, che gli danno poco da
confrontare - e ha lasciato passare meno di 1 citazione su 100 a un passaggio su
un altro argomento. Un esempio di codice viene giudicato insieme alla frase che
lo introduce. Rivedi il passaggio citato quando l'accuratezza conta. Le frasi
fisse sono scritte nella lingua scelta in **Impostazioni → Agenti → Lingua in
cui rispondono gli agenti**, e in inglese quando non ne è scelta nessuna.
Le citazioni vengono risolte solo a partire dagli identificatori delle fonti
recuperate.

Valori predefiniti per agente: 128 MiB per file, 2.048 MiB di documenti
originali, 200.000 frammenti, 8 risultati e fino a 16.000 caratteri di testo
recuperato per esecuzione. Un budget prudente in byte limita inoltre quello che
entra accanto al prompt e alla cronologia. La **Somiglianza minima** parte dal
valore misurato per il modello di vettorizzazione in uso - 0,20 per
EmbeddingGemma, 0,35 per Qwen3-Embedding - e la riga sotto il campo dice quale
sia. È un punteggio di ricerca, non una probabilità, e ogni modello ha la sua
scala. Aumentala se i risultati semantici sono troppo ampi.
Partecipano anche le corrispondenze letterali.
L'API espone inoltre le quote di frammenti e la dimensione dei frammenti in
token.

Le impostazioni globali controllano i thread di vettorizzazione, le
indicizzazioni simultanee e le lingue OCR predefinite. **Indicizzazioni
simultanee** è il numero di biblioteche di agenti indicizzate nello stesso
momento (un lavoro per agente, con i suoi documenti uno dopo l'altro); ogni
lavoro può usare fino a 4GB di RAM, come ti ricorda l'etichetta. Non accelera la
biblioteca di un singolo agente: il motore di vettorizzazione risponde a una
richiesta alla volta. Per vettorizzare più in fretta, alza invece **Thread CPU
per i vettori**. Il modello è condiviso; biblioteche e permessi sono per agente.
L'elaborazione riprende dopo i riavvii, mantenendo i documenti completati
e i frammenti riutilizzabili dei lavori interrotti. Una reindicizzazione fallita
mantiene l'ultima versione pubblicata. Solo l'installazione del modello richiede
un download; il normale recupero può funzionare senza Internet. Un motore locale
non disponibile viene segnalato, mai sostituito con un servizio di
vettorizzazione esterno.

`boa-embeddings` serve il modello attraverso un socket Unix; `boa-rag` gestisce
la coda. Entrambi hanno unità systemd e OpenRC e compaiono nelle impostazioni di
sistema. I backup includono gli originali dei documenti, i metadati e istantanee
coerenti di SQLite e dell'indice vettoriale. Le impostazioni di esecuzione sono
incluse, e con loro il modello di vettorizzazione scelto; i binari dei modelli e
i pesi scaricati no. Un ripristino scarica il modello scelto quando la macchina
non ce l'ha, e se quel download fallisce lo dice e va avanti: il modello si può
poi scaricare, o sceglierne un altro, in **Impostazioni → RAG**. In un backup
ripristinato, i caricamenti ancora in corso vengono annullati. Le biblioteche
indicizzate sopravvivono a un normale aggiornamento.

### Scegliere il modello di vettorizzazione

Il modello di vettorizzazione trasforma ogni passaggio e ogni domanda nei numeri
con cui si cerca nella biblioteca. **Impostazioni → RAG → Modello di
vettorizzazione** ne propone due, e lo stesso serve tutti gli agenti:

| | EmbeddingGemma 300M (Q8) | Qwen3-Embedding 0.6B (Q8) |
|---|---|---|
| Da scaricare | 318 MiB | 610 MiB |
| Memoria del motore mentre gira | circa 600 MB | circa 1,1 GB |
| Tempo di indicizzazione, stesso processore | 1× | circa 4× |
| Licenza | Gemma Terms of Use | Apache 2.0 |

EmbeddingGemma è quello predefinito e va bene per qualsiasi macchina.
Qwen3-Embedding è per una macchina con processore e memoria in abbondanza: sui
libri di Python in spagnolo della biblioteca di prova ha tenuto le domande sui
libri (0,51-0,79) più lontane da quelle non pertinenti (0,21 al massimo) di
quanto abbia fatto EmbeddingGemma (0,35-0,67 contro 0,17), e i paragrafi che
riformulano un passaggio più lontani dai paragrafi su qualcos'altro. Sulla
macchina di prova con due processori ha impiegato 2,2 secondi per frammento,
contro 0,5.

Per cambiarlo:

1. Scegli il modello nell'elenco. Sotto vedi la sua dimensione, la sua memoria,
   la sua velocità e la sua licenza, e se è già scaricato.
2. Se non lo è, fai clic su **Scarica il modello** e aspetta che la barra
   finisca. Il download viene verificato rispetto al suo SHA-256 pubblicato
   prima di essere usato.
3. Fai clic su **Salva** e conferma. Il motore si riavvia con il nuovo modello;
   la riga in alto dice «Il motore sta caricando questo modello» per qualche
   secondo e poi **Pronto**.

Che cosa mette in moto un cambio:

- Ogni documento di ogni agente viene indicizzato di nuovo, una biblioteca per
  lavoro di indicizzazione, come succederebbe con un nuovo caricamento. Su una
  biblioteca grande servono ore.
- Finché non arriva il suo turno, un documento resta nella biblioteca e viene
  trovato tramite le parole di una domanda, non tramite il significato. Una
  ricerca in quel periodo dice all'agente quanti documenti sono in attesa, così
  un passaggio mancante non viene scambiato per una biblioteca che non copre la
  domanda.
- La **Somiglianza minima** di ogni agente che aveva ancora il valore
  consigliato del vecchio modello passa a quello del nuovo modello. Un agente in
  cui hai impostato un altro valore lo mantiene.
- La modalità verificata confronta paragrafi e passaggi con il modello in uso,
  rispetto a una soglia misurata per esso (0,36 per EmbeddingGemma, 0,44 per
  Qwen3-Embedding).

I pesi del modello precedente restano su disco, quindi tornare indietro non
richiede alcun download - ma reindicizza di nuovo ogni documento che era stato
indicizzato con l'altro.

## Scegliere gli strumenti

In **Strumenti**, spunta quello che questo agente può usare. Uno strumento non
spuntato non viene mostrato al modello e verrebbe rifiutato dal server anche se
richiesto: quel controllo avviene sul server e non nel prompt.

Questi sono gli strumenti inclusi:

| Strumento | Che cosa ci può fare un agente |
|---|---|
| `bash.run` | Eseguire comandi di shell come il suo utente non privilegiato |
| `kanban.add_card` | Mettere un compito sulla bacheca condivisa |
| `kanban.assign_card` | Passare una delle sue schede a un altro agente |
| `kanban.move_card` | Spostare una delle sue schede tra le colonne |
| `kanban.delete_card` | Togliere una delle sue schede |
| `kanban.list_cards` | Leggere la bacheca: le sue schede, o tutte le schede nel caso di **manager** |
| `channel.write` | Mandare un messaggio a un canale configurato |
| `web.fetch` | Leggere una pagina web pubblica |
| `rss.fetch` | Leggere un feed RSS o Atom come elenco di voci |
| `memory.append` | Annotare qualcosa per il suo io futuro |
| `memory.replace` | Fare ordine in quello che ricorda |
| `skill.read` | Leggere una procedura che gli è stata data |
| `script.write` | Scrivere uno script nella sua directory `scripts/` |
| `script.list` | Elencare gli script che ha scritto |
| `script.delete` | Togliere uno dei suoi script, con le righe di cron che lo eseguivano |
| `cron.add` | Eseguire uno dei suoi script a orari prestabiliti, nel suo crontab |
| `cron.list` | Leggere il suo crontab |
| `cron.remove` | Smettere di eseguire uno dei suoi script |
| `mail.read` | Leggere i messaggi della casella di posta configurata |
| `mail.move` | Archiviare un messaggio in un'altra cartella dello stesso account |
| `mail.delete` | Mandare un messaggio nel cestino dell'account |
| `mail.forward` | Inoltrare un messaggio a un indirizzo che hai autorizzato |
| `rag.search` | Cercare nella sua biblioteca documentale |
| `rag.read` | Leggere un frammento restituito da una ricerca |
| `rag.list` | Elencare i documenti della sua biblioteca |
| `browser.open` | Aprire una pagina nel suo browser, conservando i cookie |
| `browser.read` | Leggere la pagina aperta, o i suoi link |
| `browser.click` | Fare clic su un link o su un pulsante della pagina |
| `browser.type` | Compilare un campo, eventualmente inviandolo |
| `browser.screenshot` | Salvarne un'immagine per te |
| `image.send` | Allegare un PNG alla chat web e alla risposta su Telegram quando la conversazione è iniziata lì. Le immagini riempiono l'area di testo del messaggio web |

Ogni famiglia ha un riquadro tutto suo, con il conteggio di quanti strumenti di
quella famiglia ha questo agente: «questo agente può leggere la casella di
posta?» è una sola decisione, e viene disegnata come un solo riquadro.
L'interruttore che attiva la bacheca kanban per un agente sta in fondo al
riquadro **Kanban**, sotto gli strumenti che governa.

- **`bash.run`** — comandi di shell come utente di quell'agente. Non ha root e
  non può ottenerlo. Daglielo quando l'agente ha davvero del lavoro da fare
  sulla macchina.
- **`kanban.*`** — la bacheca condivisa. Dai almeno `list_cards` e `add_card` a
  tutto quello che deve essere visibile.
- **`channel.write`** — messaggi per te. Spunta anche i canali nella scheda
  **Canali**.
- **`web.fetch`** — solo pagine pubbliche. Gli indirizzi privati e di loopback
  vengono rifiutati.
- **`rss.fetch`** — un feed RSS o Atom, come elenco di voci invece che come
  documento XML. Costa molto meno che scaricare lo stesso feed con `web.fetch`,
  e risparmia all'agente l'analisi. Entrambi stanno sotto **Internet**.
- **`script.*` e `cron.*`** — sotto **Automazione**. L'agente scrive uno script
  nella sua directory `scripts/` e lo pianifica nel suo crontab, per il lavoro
  ricorrente che non richiede di pensare: lo script gira da solo, non costa
  token, e l'agente ne legge i risultati alla sua esecuzione successiva. Può
  pianificare solo i suoi script, niente più spesso di ogni 5 minuti, e non può
  mai toccare la riga che lo sveglia.

Un agente può fare moltissimo dentro la sua home, e niente del tutto fuori. Non
può vedere che esiste un altro agente, figuriamoci leggerne il prompt: la
directory degli agenti è attraversabile ma non elencabile e ogni home è privata
del suo utente Linux, quindi è il kernel a rifiutare, non un controllo in
Python.

Non può nemmeno riscrivere **ciò che è**. I suoi strumenti concessi, i suoi
tetti di spesa, il suo prompt di sistema e il suo token API vivono in un
cassetto dentro la sua home che appartiene a root: l'agente li legge e non può
cambiarli. Li cambi tu; lui no. L'unica cosa di sé che può modificare è la sua
memoria.
- **`mail.*`** — la casella di posta configurata in **Impostazioni → Email**.
  Vedi sotto.
- **`skill.read`** — le procedure scritte spuntate nel pannello **Competenze**.
  Servono entrambe le cose: lo strumento qui e almeno una competenza lì.

### Gli strumenti di posta

Sono quattro, e hanno bisogno di una casella IMAP configurata in
**Impostazioni → Email**. L'agente non vede mai quella password: dice che cosa
vuole fare e l'API degli agenti, che custodisce le credenziali, lo fa.

| Strumento | Che cosa fa |
|---|---|
| `mail.read` | Legge i messaggi. **Non segna nulla come visto**, quindi il tuo conteggio dei non letti continua a significare quello che significava. |
| `mail.move` | Archivia un messaggio in un'altra cartella dello stesso account. La cartella deve esistere. |
| `mail.delete` | Manda un messaggio nel cestino dell'account, dove ce n'è uno. |
| `mail.forward` | Inoltra un messaggio, **solo agli indirizzi che hai elencato**. |

Quest'ultimo è quello importante. Una casella di posta è l'unico input di un
agente in cui chiunque al mondo può scrivere, quindi `mail.forward` viene
confrontato con il tuo elenco dal server a ogni singolo inoltro - non
dall'agente, e non da qualcosa scritto nel suo prompt. Con l'elenco vuoto,
l'inoltro viene rifiutato del tutto.

Dai solo `mail.read` a un agente che deve soltanto sorvegliare. Aggiungi
`mail.move` per archiviare, e pensaci due volte prima di `mail.delete` e
`mail.forward`.

La casella **kanban** in fondo spegne del tutto la bacheca per questo agente.
Senza la spunta non riceve alcuno strumento kanban e smette di aggiungere
schede, ed è l'interruttore da usare per un agente il cui lavoro non appartiene
alla bacheca.

## Dare una competenza a un agente

Una competenza è una procedura scritta: come si fa qui un certo lavoro, passo
per passo. L'applicazione non ne include nessuna: una competenza riguarda QUESTA
macchina - questi host, questo backup, questo certificato - quindi una generica
sarebbe una procedura che nessuno segue. Le scrivi tu sul server, come root:

```bash
mkdir -p /opt/boa/skills/BackupVerification
nano /opt/boa/skills/BackupVerification/SKILL.md
chown -R root:root /opt/boa/skills
chmod 00755 /opt/boa/skills/BackupVerification
chmod 0644 /opt/boa/skills/BackupVerification/SKILL.md
```

Il file comincia con un nome e una descrizione di una riga tra due righe `---`,
e il resto è la procedura:

```markdown
---
name: BackupVerification
description: How to check that last night's backups actually ran.
---

1. Read /var/log/backup.log ...
```

Ogni directory sotto `/opt/boa/skills/` compare poi come casella di spunta nel
pannello **Competenze** dell'agente. Spuntane una, dai all'agente lo strumento
`skill.read` in **Strumenti**, e premi **Salva**. Dalla sua esecuzione successiva l'agente sa che quella procedura esiste e può
leggerla quando arriva il lavoro.

### Perché preoccuparsene, se c'è già il prompt di sistema

Tre motivi, e il terzo è quello che conta:

- **Il prompt è a che cosa serve un agente; una competenza è come si fa un
  lavoro.** Sei agenti possono condividere una procedura senza che sei copie
  diventino obsolete ciascuna per conto suo.
- **Una competenza può essere lunga quanto serve.** Un prompt di sistema si
  paga a ogni chiamata di ogni esecuzione, quindi deve restare corto. Una
  competenza si paga una volta, dall'esecuzione che la legge.
- **Quello che un agente impara da solo muore con lui.** La sua memoria vive
  dentro una home che nessun altro agente può aprire. Una competenza è il posto
  dove mettere quello che vuoi che sappia anche il prossimo agente.

### Scriverne una

Nell'interfaccia non c'è un editor per questo, apposta: quello che dice una
competenza va dritto nel ragionamento di un agente che gira alle quattro del
mattino senza nessuno che guardi, quindi appartiene a root, come gli strumenti.
Le scrivi sul server:

```bash
mkdir -p /opt/boa/skills/DatabaseBackup
nano /opt/boa/skills/DatabaseBackup/SKILL.md
```

Il file comincia con un'intestazione di due righe e poi dice tutto quello che
deve dire:

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

La `description` è la riga che conta di più. È l'unica parte che ogni
esecuzione paga, ed è quella su cui l'agente decide quando sta scegliendo se
leggere il resto. «How the nightly dump is taken and where it goes» gli dice
quando si applica; «Database stuff» no.

Ricarica la pagina dell'agente e la competenza è nell'elenco.

Un aggiornamento non tocca mai `/opt/boa/skills/`: quello che ci scrivi resta
tuo. L'interfaccia web decide quale agente riceve quale competenza; non le
modifica.

### Una competenza può portare i suoi file

Qualsiasi altra cosa nella directory viaggia con lei:

```
/opt/boa/skills/DatabaseBackup/
  SKILL.md
  dump.sh
  exclude-tables.txt
```

Gli agenti possono leggerli ed eseguirli, quindi la procedura può dire «esegui
`dump.sh` in questa directory» invece di scrivere per esteso quaranta righe di
shell. `skill.read` dice all'agente quali file ci sono e dove.

### Quanto costa

Nel prompt entrano solo il nome e la descrizione di ogni competenza - circa due
righe ciascuna. Il corpo viene recuperato con `skill.read`, una volta, da un
agente che ha deciso di averne bisogno, e solo allora. Dare cinque competenze a
un agente gli costa un paio di centinaia di token per esecuzione, non diecimila,
ed è per questo che puoi dargliene cinque senza pensare alla bolletta.

### Se elimini una competenza che gli agenti stanno usando

Non si rompe niente, e nessun agente resta a promettere qualcosa che non può
mantenere:

- **Sparisce dal prompt** di ogni agente che ce l'aveva, alla loro esecuzione
  successiva. A un agente non viene mai detto di una procedura che non può
  leggere.
- **Sparisce dal pannello Competenze**, quindi nessuno può spuntarla di nuovo.
- Il nome **resta nell'`info.json` dell'agente** finché qualcosa non lo
  riscrive, quindi rimettere a posto la directory ripristina la competenza senza
  nient'altro da fare.
- Se l'agente la chiede comunque - può ricordarne il nome da un'esecuzione
  precedente - gli viene detto che la competenza è nel suo elenco ma non è più
  installata, e di non tirare a indovinare che cosa diceva.

Una cosa da sapere: **premere Salva su quell'agente mentre la competenza manca
la toglie dall'elenco per sempre.** L'interfaccia salva solo le competenze che
esistono, ed è questo che impedisce a una competenza eliminata di restare lì per
sempre. Rimetti a posto la directory prima di salvare l'agente, o spunta di
nuovo la competenza dopo.

## Dare un browser a un agente

`web.fetch` legge una pagina pubblica e nient'altro: niente accesso, niente
modulo, niente pulsante. Se un agente ha bisogno di *usare* un sito invece di
leggerlo, gli serve un browser.

Arriva già installato: l'installer lo chiede una volta, e la risposta
predefinita è sì. Sono circa 600 MB di Chromium, quindi una macchina a corto di
disco può rifiutare, e cambiare idea più avanti in un senso o nell'altro:

```bash
./install-update-reinstall-debian.sh --update --browser no    # lo lascia fuori
./install-update-reinstall-debian.sh --update --browser yes   # lo rimette
```

La risposta viene ricordata, come le porte. Poi spunta gli strumenti del browser
nel pannello **Strumenti** dell'agente:

Niente di tutto questo vale su Alpine: lì il browser non c'è proprio, perché
Playwright non pubblica alcuna build per musl. Gli strumenti restano nell'elenco
e lo dicono quando un agente ne chiama uno.

| Strumento | Che cosa può fare l'agente |
|---|---|
| `browser.open` | Andare a una pagina. I cookie vengono conservati |
| `browser.read` | Rileggere la pagina aperta, una sua parte, o i suoi link |
| `browser.click` | Fare clic su un link o su un pulsante, tramite il testo visibile o un selettore |
| `browser.type` | Compilare un campo, eventualmente premendo Invio |
| `browser.screenshot` | Salvare un PNG nella sua directory dei download |
| `image.send` | Allegare un PNG alla risposta nella chat web e su Telegram |


`browser.screenshot` salva un PNG sul server. Per mostrarlo nella chat, l'agente
chiama poi `image.send` con quel percorso. Concedi **image.send** in
**Impostazioni dell'agente → Strumenti → Immagini**, poi salva. I nuovi agenti
creati da **web-navigator** lo includono già; gli agenti esistenti mantengono i
permessi che hanno.

L'immagine riempie l'area di testo del messaggio nella chat web, mantenendo le
sue proporzioni e la sua altezza completa. Si può anche aprire alla sua
dimensione originale. Quando la conversazione è iniziata su Telegram, viene
mandata anche lì. Le catture alte o grandi vengono consegnate come documenti
PNG. Un caricamento fallito riprova la parte mancante senza ripetere il testo o
le immagini già arrivati.

Vengono accettati solo file PNG dentro la home di quell'agente, fino a 50 MiB
ciascuno e 16 per risposta. Gli allegati restano privati e per vederli serve una
sessione autenticata. Uno screenshot esistente si può mandare chiedendo
all'agente di usare `image.send` con il percorso in cui è salvato.

### Le sessioni di ogni agente sono sue

Il browser in sé è una sola copia, in `/opt/boa/playwright/`, di proprietà di
root e in sola lettura per tutti gli altri. Quello che **non** è condiviso è il
profilo:

```
/opt/boa/agents/001/browser/profile/     agent-001, 0700
/opt/boa/agents/002/browser/profile/     agent-002, 0700
```

Un agente che accede a un sito resta collegato **alla sua esecuzione
successiva**, perché i cookie sono sul suo disco. E nessun altro agente è
collegato, perché quella directory è 0700 e appartiene al suo utente Linux -
rifiuta il kernel, non c'è nessun controllo in Python da sbagliare. Questa
separazione è proprio quello che un prodotto ospitato non può offrire quando
tutti i suoi agenti condividono una sola macchina.

I cookie di sessione finiscono comunque quando il browser si chiude, qui come in
qualsiasi browser. Quello che un sito segna come persistente, persiste.

### Che cosa non fa

- **Niente indirizzi privati.** `browser.open` rifiuta `192.168.*`, `127.*` e
  gli altri, esattamente come fa `web.fetch`. Un agente che ha appena letto una
  pagina ostile non deve poter essere convinto ad aprire il tuo router, e per
  farlo un browser con una sessione sarebbe uno strumento molto migliore di un
  semplice fetch.
- **Niente schermo.** È headless. `browser.screenshot` è il modo in cui vedi
  quello che ha visto; l'agente stesso non può guardare l'immagine.
- **Niente senza gli strumenti.** Come per tutto il resto, uno strumento che non
  è stato dato all'agente è uno strumento che non può chiamare, e quel controllo
  sta sul server.

Se il browser non è mai stato installato, gli strumenti compaiono comunque
nell'elenco e rispondono con il comando da eseguire. Non spariscono, e non
falliscono in silenzio.

## Tetti di spesa

Quattro tetti, per agente, e ogni esecuzione si ferma al primo che raggiunge:

| Tetto | Predefinito | Da che cosa protegge |
|---|---|---|
| Token per esecuzione | 16384 | Una singola conversazione costosa |
| Passi per esecuzione | 25 | Un ciclo che chiama strumenti all'infinito |
| Secondi per esecuzione | 300 | Un'esecuzione che si blocca |
| Esecuzioni al giorno | 48 | Una riga di cron troppo zelante |

Non sono paranoia. Un agente che si sveglia ogni ora su un'API a pagamento,
senza tetti e senza nessuno che guardi, è una fattura che cresce mentre dormi.

Alzali quando hai visto quanto consuma davvero l'agente, nel suo pannello
**Cronologia**.

### Il modello di riserva

In **LLM** c'è un secondo provider con il suo modello, sotto il primo. Viene
usato solo quando quello principale **fallisce** - nessuna chiave, nessuna
risposta, un modello che non c'è - e l'esecuzione prosegue con esso dallo
stesso passo, ripassandogli quello che è successo fin lì, così il lavoro già
fatto non viene buttato.

Viene provato **una volta per esecuzione**. Se fallisce anche la riserva,
l'esecuzione fallisce: provarli a turno all'infinito brucerebbe i tetti durante
un disservizio senza avere comunque niente da mostrare. Il passaggio alla
riserva viene scritto nella cronologia dell'agente, perché un'esecuzione che
risponde di nascosto con un modello diverso, e addebita a un altro account, deve
dirlo.

Lasciare il provider di riserva su **nessuno** è il valore predefinito, e
significa che un fallimento chiude l'esecuzione.

Scegli lo **stesso provider** per la riserva e la casella del modello si riempie
con un modello *diverso* dal catalogo di quel provider, non di nuovo lo stesso.
Lo stesso provider con lo stesso modello non può rispondere a nulla che non
potesse già il principale: fallirebbe esattamente per lo stesso motivo, ogni
volta. Se comunque riscrivi la coppia rendendola identica, una riga sotto il
campo lo dice - l'agente è tuo, quindi è un avviso e non un rifiuto.


Quando un'esecuzione si ferma al suo tetto di token o di passi, all'agente viene
chiesta ancora una volta - senza strumenti, con un piccolo budget tutto suo - la
risposta che stava per dare, così un'esecuzione che ha speso tutto il suo budget
a raccogliere fatti non finisce con «Ora controllo il sistema». La chat lo dice
sotto la risposta, perché quella risposta può essere troncata. Il tetto di tempo
non ha questa chiamata: l'esecuzione è già in ritardo.

Quella chiamata di chiusura rimanda l'intera conversazione, quindi in
un'esecuzione lunga e piena di strumenti non è economica: un'esecuzione fermata
a un tetto di 12000 token è stata misurata mentre finiva a 24901. Il tetto di
token è quindi un budget per il lavoro, non un massimo rigido per l'esecuzione.
In questo modo non si spende nulla a meno che non sia stato raggiunto un tetto.

### Che cosa impone il kernel in più

I quattro tetti li fa rispettare l'esecuzione stessa. Altri due li fa rispettare
il kernel, quindi reggono quando è proprio l'esecuzione ad andare storta: nessun
agente può avere più di 1024 processi e thread contemporaneamente, quindi un
comando che si biforca senza fine si ferma lì e non al limite della macchina; e
su Debian ogni esecuzione vive in uno scope systemd tutto suo con 2 GiB di
memoria, che quando finisce chiude anche quello che l'esecuzione ha lasciato in
esecuzione in background. Un'esecuzione uccisa dal limite di memoria viene
riportata nella sua Cronologia come fallita e nella sua chat come errore, come
qualsiasi altra. Un browser è già qualche centinaio di thread, ed è per questo
che il numero non è più piccolo.

## Pianificare un agente

In **Cron**, scrivi il crontab dell'agente. È il crontab dell'agente stesso, di
proprietà del suo utente Linux ed eseguito da lui, esattamente come se avessi
eseguito `crontab -e` come quell'utente.

Ogni ora:

```
0 * * * * /opt/boa/venv/bin/python3 /opt/boa/webapp/backend/core/runner.py --agent-id 001
```

Ogni giorno feriale alle 08:00:

```
0 8 * * 1-5 /opt/boa/venv/bin/python3 /opt/boa/webapp/backend/core/runner.py --agent-id 001
```

L'interfaccia mostra la riga esatta per l'agente che stai modificando, così puoi
copiarla e cambiare solo l'orario.

Lascialo vuoto per togliere la pianificazione. Togli la spunta da **Acceso** per
mantenere la pianificazione ma far sì che l'agente la ignori.

Se usi un provider a pagamento i cui prezzi variano con l'ora — DeepSeek fa
pagare parecchio di più nelle ore di punta — è qui che si fa quella scelta.

## La bacheca kanban

La pagina ha due schede: **Bacheca**, che sono le tre colonne, e **Crea
scheda**, che è il modulo. Quale delle due è aperta sta nell'URL, così un
ricaricamento e il pulsante Indietro la mantengono. Salvare una scheda ti
riporta alla bacheca.

Tre colonne: **da fare**, **in corso**, **fatto**.

La bacheca è ciò che gli agenti usano per lasciarsi lavoro a vicenda e ciò che
usi tu per vedere che cosa è successo davvero. Ogni scheda porta con sé la sua
storia: chi l'ha creata, chi l'ha spostata, quando e perché.

Una scheda ha un titolo e una casella **Che cosa fare**. Il titolo le dà un
nome; la casella è dove vanno le istruzioni, e un agente legge entrambi. Una
scheda assegnata a un agente con la casella vuota lo lascia a indovinare, ed è
il motivo abituale per cui un agente non fa niente con una scheda che gli è
stata passata.

L'altro motivo è che l'agente non vede proprio la bacheca. Un agente la legge
chiamando `kanban.list_cards` o non la legge affatto - la bacheca non viene mai
messa nel suo prompt - quindi un agente senza quello strumento non scopre mai
che la scheda esiste. **Assegna a** lo dice quando scegli un agente del genere.
È un avviso, non un blocco: la scheda viene creata comunque, e basta spuntare lo
strumento nella scheda **Strumenti** dell'agente.

Una scheda sulla bacheca mostra chi l'ha fatta, chi ce l'ha, quando è stata
fatta, le prime due righe del suo titolo, le prime tre di quello che c'è da
fare, e **quando viene eseguita**. Un titolo o un corpo tagliati si leggono per
intero nel loro tooltip.

Quest'ultima riga è quella che vale la pena leggere. Una scheda senza orario non
è in ritardo: nessuno viene svegliato per lei, e il suo agente la troverà alla
sua prossima esecuzione programmata. **Sposta in** è il modo per spostare una
scheda a mano - questa bacheca non ha il trascinamento.

Puoi aggiungere, spostare ed eliminare qualsiasi scheda. **Un agente vede e
cambia solo le sue**: una scheda è di un agente se l'ha creata lui o se è
assegnata a lui.

È un muro, non una preferenza. Un agente non può sapere nemmeno che il lavoro di
un altro agente esiste - non i titoli, non quante sono, non che lì ci sia
qualcosa. Chiedi a un agente di spostare una scheda che non è sua e gli viene
detto che tra le sue non esiste una scheda del genere; una scheda che non esiste
riceve la stessa frase, perché un rifiuto che distinguesse i due casi sarebbe un
modo per chiedere alla bacheca che cosa contiene, un id alla volta.

L'eccezione è **manager** (agente 000), l'orchestratore: il suo lavoro è
distribuire compiti e seguirli, quindi legge tutta la bacheca. Ecco perché il
coordinamento è compito suo e di nessun altro.

Una conferma distruttiva **non ha un pulsante predefinito**: si apre con il
focus sulla finestra di dialogo stessa, quindi Invio non fa né l'una né l'altra
cosa e devi dire quale intendi. Esc annulla. Fai clic sul pulsante rosso per
procedere.

Una conferma normale, che non distrugge niente, si apre invece con il focus sul
suo pulsante di conferma, cerchiato, dove Invio significa sì.

Eliminare una scheda lascia una riga che registra che esisteva e chi l'ha
eliminata, così un agente non può cancellare le prove di quello che stava
facendo.

## Impostazioni

Le impostazioni sono raggruppate in schede, e la scheda sta nell'URL, così un
ricaricamento o un segnalibro ti riportano dove eri:

| Scheda | Che cosa contiene |
|---|---|
| **Sistema operativo** | Che macchina è questa, quanta memoria e quanto disco restano, e se i quattro servizi sono attivi - ciascuno verde quando è attivo e rosso quando non lo è. Letto senza privilegi, nello stesso modo in cui lo legge `os-watcher` |
| **Account** | L'unico indirizzo email e la password. Per cambiare la password serve quella attuale |
| **Email** | SMTP, per quando qualcosa deve raggiungerti per posta |
| **Canali** | Discord, Mattermost, Telegram, X, in ordine alfabetico - un riquadro ciascuno, con il suo pulsante Salva |
| **Audio** | Motore di trascrizione, provider, download dei modelli, lingua e conservazione dell'audio di Telegram |
| **Strumenti** | Gli strumenti installati, raggruppati in sottoschede come Automazione e Browser |
| **Agenti** | Impostazioni per tutti gli agenti insieme, e il repository e il branch da cui vengono i modelli. Tenute sul server: un'esecuzione avviata da cron non ha un browser da cui leggere una preferenza |
| **Chat** | Come si comporta la casella dei messaggi: se Invio invia, se ogni risposta mostra quanto è costata |
| **Kanban** | Quante schede mostra ogni colonna, e se elencare quelle eliminate di recente |
| **Interfaccia** | Tema, lingua, quanto resta a schermo un messaggio a comparsa, e se **+** chiede da dove parte un nuovo agente |

In **Sistema operativo**, gli stati dei servizi sono allineati con la seconda
colonna di **Questa macchina**.

Le preferenze di Chat, Kanban e Interfaccia sono tenute nel tuo browser invece
che sul server: descrivono come lavori su questa macchina, e un telefono e un
computer fisso possono ragionevolmente non essere d'accordo.

### Trascrizione audio

Su Alpine, installazione e aggiornamenti restituiscono il controllo della sessione SSH quando finiscono; OpenRC mantiene in esecuzione i servizi.

Apri **Impostazioni → Audio**. Queste impostazioni sono salvate sul server e si applicano ai messaggi vocali e ai file audio ricevuti tramite Telegram.

1. Scegli **Locale · whisper.cpp** o **API di un fornitore**. La trascrizione parte disattivata.
2. Per il riconoscimento locale, scegli un modello e fai clic su **Scarica modello** se serve. L'installer prepara `base`; il selettore propone tutti i 30 modelli ufficiali, comprese le varianti solo inglese `.en` e quelle quantizzate, più i modelli `ggml-*.bin` installati a mano in `/opt/boa/whisper/models/`. Vengono mostrati la dimensione e lo stato di installazione. I modelli più grandi richiedono più memoria e più tempo di CPU.
3. Per un'API, salva prima la sua chiave in **Chiavi API**. OpenAI, Groq, Mistral, Together AI, Hugging Face e Cloudflare compaiono quando una chiave è salvata. Scegli un suggerimento o inserisci un altro identificatore di modello di trascrizione di quel provider. Cloudflare propone le sue due varianti di Whisper supportate e usa una credenziale `account-id:api-token`.
4. Scegli la lingua (`auto` o un codice come `en`), la durata massima e se conservare l'audio per riprodurlo; fai clic su **Salva**. Per provarlo, rispondi al messaggio Telegram di un agente con un messaggio vocale. Puoi anche selezionare prima l'agente con `/agents`.

Il limite iniziale è di 600 secondi, configurabile da 30 a 3600; il file ricevuto non può superare 20 MiB. L'elaborazione avviene in background e la sua coda sopravvive a un aggiornamento. Un agente occupato riceve il testo salvato quando è disponibile. Il nome di un agente pronunciato dentro la registrazione non cambia la sua destinazione.

La chat web mostra la trascrizione e, quando la conservazione è attiva, un lettore. Una copia Ogg per la riproduzione viene conservata dietro l'accesso. Disattivare la conservazione mantiene solo il testo per i nuovi messaggi. Svuotare una chat rimuove l'audio salvato dei lavori completati. I backup includono quell'audio; i modelli scaricati sopravvivono agli aggiornamenti ma non entrano nel backup. Dopo un ripristino su un'altra macchina, scarica da Audio gli eventuali modelli aggiuntivi mancanti.

Il riconoscimento locale elabora l'audio sul tuo server. Il riconoscimento via API lo invia al provider selezionato e può comportare costi separati dall'uso del modello dell'agente. Un fallimento locale non passa mai automaticamente a un provider cloud. Whisper trascrive, non traduce; i modelli `.en` capiscono solo l'inglese. L'audio entra tramite Telegram; la chat web mostra il risultato senza aggiungere un pulsante di registrazione.

Per un'installazione esistente, esegui come root l'installer della tua distribuzione con `--update`. Installa FFmpeg, whisper.cpp e il modello base sotto `/opt/boa/whisper/`; la trascrizione resta disattivata finché non viene configurata.

### Lingue

L'interfaccia è disponibile in quindici:

| | | |
|---|---|---|
| Deutsch (Deutschland) | English (United Kingdom) | English (United States) |
| Español (Argentina) | Español (España) | Français (France) |
| עברית (ישראל) | हिन्दी (भारत) | Italiano (Italia) |
| 日本語 (日本) | 한국어 (대한민국) | Português (Brasil) |
| Português (Portugal) | Русский (Россия) | 简体中文 (中国) |

L'ebraico si scrive da destra a sinistra, e sceglierlo specchia l'intera
interfaccia: la barra laterale passa a destra e tutto il resto segue.
Codice, percorsi e comandi restano da sinistra a destra, e ogni messaggio
della chat segue la propria lingua, così una risposta in inglese si legge
ancora da sinistra a destra su una pagina in ebraico.

**Impostazioni → Interfaccia → Lingua** ne sceglie una, e viene tenuta nel tuo
browser, come il tema. Un browser che non ha mai scelto riceve quella più vicina
a quella che chiede, e l'inglese quando non ce n'è nessuna.

Altre due cose seguono la lingua e **non** sono una preferenza del browser,
perché un'esecuzione avviata da cron non ha un browser:

- **Impostazioni → Agenti → Lingua in cui rispondono gli agenti** aggiunge una
  riga al prompt di sistema di ogni agente, scritta in quella lingua.
- Anche i **bot di Telegram e di Discord** la parlano: le loro frasi, il
  resoconto di `/status`
  e il testo di aiuto.

## Messaggi a comparsa

Quando qualcosa viene salvato, la conferma compare al centro del pannello che
stai guardando e poi se ne va da sola. Sta volutamente in mezzo: il pulsante
Salva in fondo a una scheda lunga un tempo produceva una riga in cima alla
pagina, parecchie schermate sopra il punto in cui stavi guardando, quindi
salvare sembrava non aver fatto proprio niente.

**Impostazioni → Interfaccia → Secondi di permanenza di un messaggio a
comparsa** stabilisce quanto a lungo, tra 1 e 30 secondi. Tre è il valore
predefinito: abbastanza per leggere `Settings saved` («Impostazioni salvate»),
abbastanza poco da non restare sopra la casella in cui stavi per scrivere.

I messaggi di errore ignorano quel numero. Restano finché non li chiudi, con la
`×` o con Esc, perché un errore è l'unico messaggio che deve essere ancora lì
quando torni a guardare lo schermo.

Il colore dice quale di tre cose è successa:

| Colore | Che cosa significa |
|---|---|
| Verde | È stato salvato |
| Ambra | **Nessuna modifica da salvare** - hai premuto Salva e nel modulo non era cambiato niente |
| Rosso | Non è riuscito. Dice che cosa è andato storto, e aspetta di essere chiuso |

Quello ambra vale ovunque si possa premere Salva: **Impostazioni** - l'account,
il server di posta, le chiavi API, i canali e le preferenze del browser - e le
impostazioni di un agente. Se premi Salva due volte, la seconda volta te lo
dice, invece di annunciare un salvataggio che non è avvenuto. Un agente appena
creato è l'eccezione: il suo modulo contiene i valori di partenza del modello e
non è mai stato salvato, quindi Salva li scrive e ti porta alla sua chat.

## Temi

**Impostazioni → Interfaccia** sceglie la tavolozza:

| Tema | Che cos'è |
|---|---|
| **Day** | Grigi morbidi con schede più chiare, per una stanza illuminata |
| **Night** | La tavolozza scura, per una stanza buia |
| **Day High Contrast** | Sfondo bianco, testo quasi nero, bordi netti. Qui niente è riempito con il colore d'accento: il riquadro di un agente nella barra laterale è un contorno, e il tuo messaggio è riempito con un inchiostro attenuato invece che di blu |
| **Night High Contrast** | Sfondo quasi nero, testo chiaro e bordi netti. L'agente selezionato ha un riempimento grigio; le schede selezionate hanno un contorno chiuso unito alla linea sottostante. I tuoi messaggi usano un bianco attenuato |

Un browser che non ha mai scelto parte da quello tra Day e Night che corrisponde
al sistema operativo, e lo segue finché qualcuno non ne sceglie uno. Da lì in
poi la scelta viene salvata in questo browser, come la lingua, così un telefono e
un computer fisso non devono per forza essere d'accordo.

Un tema è un file CSS in `frontend/themes/` sul server che ridefinisce le
variabili `--colour-*`. Mettere un file lì aggiunge un tema - nel codice non c'è
nessun elenco da aggiornare. Il suo nome e la sua descrizione vengono dal
commento in cima al file:

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

Definiscile tutte. Una variabile che un tema tralascia mantiene il valore di
app.css - il che, in un tema chiaro, significa un colore della tavolozza scura
lasciato lì in mezzo.

Ogni tema incluso supera un contrasto di 4,5:1 per ogni colore con cui dipinge
il testo, e i due ad alto contrasto superano 7:1 - WCAG AAA. C'è un test che
fallisce se uno smette di farlo, misurato con l'asticella che dichiara il suo
nome. Un tema aggiunto a mano non è tenuto a questo, ma la stessa domanda vale
anche per lui: un servizio segnato come giù in un rosso che nessuno riesce a
leggere è un servizio che nessuno nota.

## Quando una scheda viene eseguita

Assegnare una scheda è il modo in cui dai lavoro a un agente, ed è un servizio
**buzzer** a trasformarlo in un'esecuzione:

    ogni pochi secondi:
      schede con un proprietario, un orario già passato e ancora nessun buzz
        -> avvia quell'agente, a meno che non sia già in esecuzione
        -> registra il buzz sulla scheda

**Quando** nel modulo di aggiunta di una scheda decide l'orario:

| Scelta | Che cosa succede |
|---|---|
| **Subito** | L'agente viene svegliato appena la scheda viene salvata. È il valore predefinito: assegnare una scheda è chiedere il lavoro |
| **Quando l'agente si sveglia** | La scheda aspetta sulla bacheca. Nessuno viene svegliato; l'agente la trova alla sua prossima esecuzione autonoma |
| **Programma per un orario preciso** | Un orario in UTC. L'agente viene svegliato allora |

Un agente che sta già lavorando non viene interrotto. La scheda mantiene il suo
turno e viene ritentata al passaggio successivo, quindi un'esecuzione
programmata per un agente occupato parte con qualche secondo di ritardo invece
di non partire affatto, e un agente non ha mai due esecuzioni
contemporaneamente. Una scheda riceve il buzz una sola volta: per eseguirla di
nuovo, reimpostane l'orario.

### La scheda compare nella chat dell'agente

Quando parte l'esecuzione, la chat dell'agente riceve un messaggio che nomina la
scheda:

    Ti è stato assegnato un compito su una scheda:

    ID della scheda: 1284
    Titolo: Rinnovare i certificati
    In che cosa consiste: «Esegui l'installer con --update e riferisci»
    Da eseguire: Subito

Se la scheda l'ha passata un altro agente, la prima riga dice chi: *manager ti
ha assegnato una nuova scheda*. Se la scheda era programmata invece che chiesta
subito, l'ultima riga mostra invece l'orario: `a2026m03d31@13:45`, in UTC, lo
stesso orario che la bacheca mostra sulla scheda.

Il messaggio viene scritto **quando parte l'esecuzione**, mai prima. Una scheda
che programmi per stanotte ed elimini oggi pomeriggio non lascia niente nella
chat, perché non è mai stato eseguito niente.

L'agente risponde sotto come a qualsiasi altro messaggio, con quanto è costata
l'esecuzione. Tre cose possono mettere lì una riga senza che l'agente abbia
fatto niente, e ognuna dice quale è stata: l'agente era spento, aveva già
esaurito le sue esecuzioni della giornata, oppure l'esecuzione non è potuta
partire affatto. Nessuna di queste è silenziosa, perché una scheda annunciata e
poi ignorata sembra esattamente un agente che non funziona.

Una cosa che questa esecuzione non fa è leggere la conversazione. Le sue
istruzioni sono la scheda. Quello che hai detto prima nella chat viene ripassato
solo quando mandi tu un messaggio - altrimenti ogni esecuzione programmata
pagherebbe per una conversazione che nessuno sta facendo.

Una scheda passata a **manager** viene trattata in modo diverso: gli viene detto
di decidere chi deve fare il lavoro e di passare la scheda con
`kanban.assign_card`. La scheda mantiene il suo id, le sue istruzioni e la sua
storia e cambia di mano, e l'agente su cui atterra viene svegliato per
occuparsene. Questa è delega - non una seconda scheda per lo stesso lavoro.

## Canali

In **Impostazioni → Canali**, configura dove possono scrivere gli agenti:

| Canale | Che cosa richiede |
|---|---|
| Discord | un `bot_token` e un `channel_id` per parlare in entrambe le direzioni, oppure un URL di webhook per inviare soltanto |
| Mattermost | un URL di webhook in entrata |
| Telegram | `bot_token` da BotFather, e `chat_id` |
| X | un `bearer_token` |

Ogni canale configurato mostra **Configurato** in verde, con lo stesso colore di
una chiave API salvata. I canali senza configurazione mantengono il loro stato
neutro.

Le credenziali vengono salvate in modo che **nessun agente possa leggerle**. Un
agente chiede al server di inviare; il server legge il token e invia. Il
messaggio arriva preceduto dal nome dell'agente, aggiunto dal server, così
nessun agente può fingersi un altro.

Poi, nella scheda **Canali** di ogni agente, spunta quali canali può usare. Ha
bisogno sia di `channel.write` sia del canale stesso.

### Rispondere a un agente da Telegram

Telegram e Discord sono i due canali che funzionano anche nell'altro senso. Spunta **Permettimi di rispondere
agli agenti da Telegram** nelle sue impostazioni, salva, e puoi rispondere.

Il bot ha tre strumenti nel suo menu, e sono quelli che propone il pulsante `/`:

| Comando | Che cosa fa |
|---|---|
| `/agents` | Elenca i tuoi agenti come pulsanti. Toccane uno per cominciare a parlarci |
| `/status` | Servizi, bacheca e ogni agente con il suo modello, i suoi strumenti e le sue competenze |
| `/help` | Questi tre, e gli altri due modi per raggiungere un agente |

### Nessun altro ne vede nulla

Il nome utente del bot è pubblico - chiunque lo trovi può aprirlo - quindi il
menu viene scritto **solo per la tua chat**. Qualcun altro che apre lo stesso bot
vede una chat vuota: nessun comando sotto `/`, nessuna descrizione, niente da
premere tranne il pulsante Avvia, che Telegram disegna in ogni bot e che nessuna
API può togliere.

Premerlo non fa niente. Il listener confronta il `chat_id` di ogni messaggio con
quello delle tue impostazioni e scarta quello che non corrisponde, prima che
venga eseguito qualsiasi comando e prima che venga scelto qualsiasi agente.

**E non viene annotato niente.** Nessuna risposta, nessuna riga nel log, nessuna
traccia che qualcuno abbia scritto. L'id di una chat che non è la tua è un dato
di qualcun altro, e conservarlo significherebbe che la tua installazione
costruisce in silenzio un elenco di chi ha trovato il bot.

Il prezzo è che un `chat_id` impostato male sembra esattamente uno sconosciuto: i
tuoi messaggi vengono scartati in silenzio. Quello configurato viene scritto nel
log a ogni avvio, ed è con quello che puoi confrontare:

```bash
journalctl -u boa-channel-telegram.service | grep "Registered"
```

Su Debian, le unità dei canali usano `boa-channel-<channel>.service`. Esegui
l'installer con `--update` per migrare automaticamente i vecchi nomi delle unità.
Alpine mantiene i suoi nomi OpenRC `boa-telegram` e `boa-discord`.

Il filtro è per **chat**, non per persona. Se il `chat_id` che hai configurato è
un gruppo, ogni membro di quel gruppo può parlare con i tuoi agenti.

### Scegliere con chi parli

Tocca `/agents`, tocca un agente, e lui risponde:

```
Agente os-watcher:

Envíame tus instrucciones...
```

Da lì in poi **tutto quello che scrivi va a quell'agente** finché non ne scegli
un altro. Puoi fare quattro domande di fila senza nominare nessuno, ed è questo
che la rende una conversazione invece di una riga di comando.

Tre modi per rivolgersi a qualcuno, in quest'ordine:

1. **Rispondere a qualcosa che ha detto un agente** va a quell'agente, chiunque
   altro sia selezionato. Rispondi al suo messaggio (scorrilo, oppure tienilo premuto o fai clic destro e scegli Rispondi), scrivi, invia.
2. **Nominarne uno** - `@os-watcher check the disk` - va a lui *e* lo rende
   quello selezionato. Funziona anche `@001`, e anche un nome con uno spazio:
   `@News Miner what is new` è un solo agente, non due parole.
3. **Né l'uno né l'altro** va a chi hai scelto per ultimo.

Nient'altro cambia la selezione, quindi un agente non eredita mai la tua
conversazione solo perché è stato l'ultimo a parlare. Un agente che elimini
smette di essere selezionato invece di continuare a raccogliere tutto.

Finché non hai scelto nessuno, un messaggio che non nomina nessuno riceve in
risposta l'elenco degli agenti, così niente sparisce mai senza una spiegazione.

### Che cosa torna indietro

L'agente risponde su Telegram come risposta a quello che hai scritto, con il suo
nome nella prima riga:

```
os-watcher:
25G free of 28G on /, unchanged since yesterday.
```

**E l'intero scambio sta nella chat di quell'agente nell'interfaccia web**, la
tua domanda e la sua risposta, con `(via Telegram)` accanto all'ora su quello che
hai mandato. Una sola schermata continua a mostrare tutto quello che è stato
chiesto all'agente e tutto quello che ha detto, su qualunque dispositivo sia
stata scritta ciascuna metà.

Due cose da aspettarsi:

- **Un agente occupato lo dice.** Se sta già rispondendo a qualcosa, ti viene
  detto di riprovare tra un momento invece di essere messo in coda - una coda
  nasconderebbe che un agente sta restando indietro.
- **Viene ascoltata solo la tua chat.** Il nome utente di un bot è pubblico e
  chiunque lo trovi può scrivergli. I messaggi da qualsiasi altra chat vengono
  scartati senza risposta, quindi è il `chat_id` che hai configurato a decidere
  chi può parlare con i tuoi agenti. Se lo sbagli non succede proprio niente.

È long polling, non un webhook: è il server a connettersi verso Telegram, quindi
non bisogna aprire niente verso Internet perché funzioni.

Se Telegram non accetta la risposta - hai bloccato il bot, l'id della chat è
cambiato, il token non è più valido - si rinuncia subito a mandarla su
Telegram, e se Telegram non è raggiungibile per un'ora si rinuncia comunque. Non
va mai persa: l'intera conversazione, risposta compresa, sta nella chat
dell'agente nell'interfaccia web.

### Com'è fatto il messaggio di un agente

I modelli scrivono in markdown, e Telegram visualizza un piccolo sottoinsieme di
HTML, quindi l'uno viene tradotto nell'altro in uscita. Quello che arriva è
formattato, non pieno di asterischi:

| Che cosa scrive l'agente | Che cosa vedi sul telefono |
|---|---|
| `**25G free**` | **25G free** |
| `` `df -h` `` | `df -h` a spaziatura fissa |
| `# Disk report` | una riga in grassetto |
| `- item` | • item |
| una tabella | un blocco a spaziatura fissa, con le colonne allineate |
| ```` ```bash ```` | un blocco di codice |
| `[text](https://…)` | un link |

Telegram non ha titoli, elenchi o tabelle propri, ed è per questo che quei tre
diventano la cosa leggibile più vicina invece di sparire.

Se un giorno Telegram rifiuta la formattazione, **il messaggio viene rimandato
come testo semplice invece di andare perso**. Le parole le ricevi comunque; il
log del server dice che cosa è successo, così un bug di formattazione si nota
invece di degradare in silenzio per sempre.

Tutto quello che il bot dice di suo - l'elenco degli agenti, «sta ancora
rispondendo a qualcos'altro», `/status` - è nella lingua impostata in
**Impostazioni → Agenti**, la stessa in cui rispondono gli agenti.

## Rispondere a un agente da Discord

Discord funziona allo stesso modo di Telegram, con un bot tutto tuo. Cinque
minuti di configurazione, una volta sola.

### Creare il bot

1. Apri <https://discord.com/developers/applications> e premi **New
   Application**. Chiamala come vuoi.
2. **Bot** nella barra laterale, poi **Reset Token**, e copia quello che ti
   mostra. Quello è il `bot_token`, e viene mostrato una sola volta.
3. **OAuth2 → URL Generator**: spunta **bot**, e sotto **View Channels**,
   **Send Messages** e **Read Message History**. Apri l'URL che costruisce e
   aggiungi il bot al tuo server.
4. In Discord stesso, attiva **Impostazioni → Avanzate → Modalità
   sviluppatore**, poi fai clic destro sul canale in cui vuoi gli agenti e
   scegli **Copia ID canale**. Quello è il `channel_id`.

Non serve nient'altro. In particolare **non** ti serve il Message Content
Intent: quell'interruttore è per il Gateway, e questo legge il canale tramite la
normale API.

### Attivarlo

In **Impostazioni → Canali → Discord**, compila il token e l'id del canale,
spunta **Permettimi di rispondere agli agenti da Discord**, e salva. Nel giro di
pochi secondi il log dice quale bot è in ascolto e dove:

```bash
journalctl -u boa-channel-discord.service | grep "Listening"      # Debian
tail /opt/boa/logs/boa-discord.log                # Alpine
```

I messaggi scritti prima di attivarlo non ricevono risposta: il primo passaggio
annota a che punto è il canale e parte da lì.

### Parlare con un agente

| Comando | Che cosa fa |
|---|---|
| `!agents` | Elenca i tuoi agenti e che cosa scrivere per raggiungere ciascuno |
| `!status` | Servizi, bacheca e ogni agente con il suo modello, i suoi strumenti e le sue competenze |
| `!help` | Questi tre, e gli altri modi per raggiungere un agente |

Funziona anche `/agents`, se è quello che scrivono le tue dita. Qui non ci sono
pulsanti né menu di comandi slash: entrambi sono *interazioni*, che Discord
consegna solo tramite una connessione che questa installazione volutamente non
apre.

I tre modi per rivolgersi a qualcuno sono quelli che conosci già:

1. **Rispondere a qualcosa che ha detto un agente** va a quell'agente,
   chiunque altro sia selezionato. Clic destro sul suo messaggio → Rispondi, o
   scorrilo su un telefono.
2. **Nominarne uno** - `@os-watcher check the disk` - va a lui *e* lo rende
   quello selezionato. Funzionano `!os-watcher`, `@001` e
   `@News Miner what is new`.
3. **Né l'uno né l'altro** va a chi hai scelto per ultimo.

### Che cosa torna indietro

La risposta arriva come risposta alla tua domanda, con il nome dell'agente in
grassetto nella prima riga, e **l'intero scambio sta nella chat di quell'agente
nell'interfaccia web** con `(via Discord)` accanto all'ora su quello che hai
mandato.

Una risposta lunga arriva in più messaggi invece che in uno troncato: Discord
rifiuta tutto ciò che supera i 2000 caratteri, quindi una risposta viene divisa
tra una riga e l'altra, in al massimo quattro messaggi. Puoi rispondere a uno
qualsiasi e arriva allo stesso agente. Se c'era più di quanto stia in quattro
messaggi, l'ultimo finisce con `…` - e il testo completo sta nell'interfaccia
web, dove è stato scritto.

### Chi può parlare con i tuoi agenti

**Chiunque possa scrivere in quel canale.** Questa è l'unica vera differenza
rispetto a Telegram, e vale un minuto del tuo tempo: lì il bot confronta l'id
della chat di ogni messaggio e scarta quello che non corrisponde, quindi uno
sconosciuto che trova il tuo bot non ottiene niente. Qui il bot legge un canale,
e chiunque possa pubblicarci può avviare esecuzioni sul tuo server.

Quindi metti gli agenti in un **canale privato** - uno che solo tu, o tu e le
persone di cui ti fidi, potete vedere. Il bot non ha bisogno di accedere a
nient'altro.

### Se vuoi solo gli avvisi

Lascia vuoto il token e imposta invece un **URL di webhook**: **Impostazioni del
canale → Integrazioni → Webhook → Nuovo webhook → Copia URL webhook**. Gli agenti
possono allora scrivere nel canale e basta. Per ascoltare serve il bot, quindi
l'interruttore viene rifiutato con un webhook invece di non fare niente.

## L'orchestratore

`agent-000`, chiamato **manager**, è l'unico agente creato al momento
dell'installazione. È un agente normale sotto ogni aspetto, tranne che non può
essere eliminato.

Lo schema previsto: dai al manager gli strumenti del kanban e un prompt che gli
dica di scomporre gli obiettivi in schede e di assegnarle ad altri agenti
tramite id. Dai agli altri agenti `bash.run` e qualsiasi altra cosa serva loro, e
un prompt che dica loro di lavorare sulle schede che vengono assegnate a loro.

Funziona solo se le schede del manager dicono che cosa significa «fatto». Una
scheda che non lo dice è un desiderio, e l'agente che la prende deciderà da
solo.

## La scheda Strumenti

**Impostazioni → Strumenti** mostra che cosa è installato sul server. Ogni
famiglia è una sottoscheda - Automazione, Browser, Canali, Email, Immagini,
Internet, Kanban, Memoria, Sistema operativo, RAG, Competenze - con il numero di
strumenti che contiene, e ogni strumento ha il suo riquadro con i suoi argomenti
e il loro significato. La scheda aperta sta nell'URL
(`/settings/?tab=tools&family=mail`), così un ricaricamento o un segnalibro la
mantengono. I vecchi link `/tools/` reindirizzano qui e mantengono la famiglia
selezionata.

Uno strumento la cui famiglia nessuno ha nominato - un `.py` che qualcuno ha
messo in `/opt/boa/tools/` - finisce in **Altri**, con la sua famiglia scritta
nel suo riquadro. Resta uno strumento a tutti gli effetti, fino
all'interfaccia; semplicemente non si guadagna una scheda tutta sua, altrimenti
la riga crescerebbe con ogni script estemporaneo.

Quale agente può usare quale strumento si imposta nella scheda **Strumenti** di
ciascun agente, non qui.

## La documentazione dell'API

**Documentazione dell'API** nella barra laterale elenca ogni endpoint sotto
`/api/`, raggruppato per area, con i suoi parametri e quello che risponde. È
generata dalla descrizione OpenAPI di questa stessa installazione, quindi non
può discostarsi dal codice: `openapi.json`, linkato in alto, è la stessa cosa
sotto forma di file che puoi dare a un generatore di client.

È nella lingua che hai scelto in **Impostazioni → Interfaccia**, come il resto
dell'interfaccia. La specifica in sé resta in inglese: nomi dei campi, id e
stringhe di errore sono in inglese ovunque in questo progetto, e un
`openapi.json` tradotto descriverebbe un'API che non esiste.

I corpi delle richieste sono mostrati come JSON colorato, come li mostra un
editor: i nomi dei campi in un colore, i valori in un altro, e le parentesi
graffe e le virgole attenuate perché sono impalcatura. I colori vengono dal tema
che hai scelto, e copiare un blocco ti dà comunque un JSON valido.

La pagina si può leggere anche senza accedere, da sola, senza la barra laterale.
Descrive la forma dell'API, non i tuoi dati.

## Lavoro che non richiede all'agente di pensare

Certo lavoro è ricorrente e meccanico: controllare un certificato, ruotare un
log, raccogliere un numero. Svegliare un agente per questo costa token ogni
volta, per arrivare a una conclusione a cui uno script di shell arriva gratis.

Quindi un agente può scrivere script per sé e pianificarli. Dagli gli strumenti
di **Automazione** e può:

1. `script.write` — mettere uno script di shell nella sua directory `scripts/`.
2. `cron.add` — eseguirlo a orari prestabiliti, nel suo crontab.
3. Leggere i risultati alla sua esecuzione successiva, e decidere che cosa
   significano.

Lo script gira come utente Linux di quell'agente, con gli stessi permessi che ha
l'agente, e **non costa nessun token** - è uno script di shell, non una chiamata
al modello. Quello che costa token è l'agente che dopo legge l'output e decide
che cosa farne.

Che cosa non può fare:

- Pianificare qualcosa che non siano i suoi script. Un comando libero in un
  crontab è qualcosa che nessuno può verificare dopo.
- Girare più spesso di ogni 5 minuti. Un lavoro ogni minuto non è una
  pianificazione.
- Toccare la riga che lo sveglia. Quella è tua, nella sua scheda **Cron**.

Vedi entrambe le metà: gli script nella sua home, e le righe che li eseguono
nella scheda Cron accanto alle tue.

## Dove finisce il resoconto di un'esecuzione

Un'esecuzione che avvii dalla chat ti risponde lì. Un'esecuzione avviata da una
scheda arrivata a scadenza risponde nello stesso posto. Un'esecuzione avviata
dal **crontab dell'agente stesso** non risponde in nessun posto in particolare -
nessuno gli ha chiesto niente - quindi:

- **Sempre in Cronologia**, sotto **Ultime esecuzioni**: che cosa ha detto ogni
  esecuzione, con quanto è costata. È qui che devi guardare quando ti chiedi che
  cosa ha fatto un agente.
- **Anche nella chat, quando vale la pena interromperti**: l'esecuzione non è
  finita, o ha cambiato qualcosa che vedresti - una scheda, un messaggio su un
  canale, una casella di posta. Un'esecuzione che si è limitata a guardare resta
  in Cronologia. Altrimenti un agente con un crontab orario pubblicherebbe nella
  conversazione ventiquattro messaggi «niente da segnalare» al giorno.

Quei messaggi dicono in testa che nessuno li ha chiesti, e non vengono mai
ripassati al modello, quindi non costano niente al tuo prossimo messaggio.

**Anche un'esecuzione che non è mai partita sta in Cronologia**, segnata come
«non avviata». Premi **Esegui ora** su un agente la cui chiave API non è ancora
impostata, o mentre l'agente è già in esecuzione, e la riga in Cronologia ti
dice quale dei due casi era. Prima, lo schermo diceva che l'esecuzione era
partita e non compariva mai nient'altro, perché il motivo veniva scritto in un
posto che nessuno legge. Un'esecuzione che non è partita non conta tra le
esecuzioni del giorno dell'agente, e non viene contata nemmeno come un
fallimento dell'agente: non ne è stato eseguito niente.

## La barra di stato

La striscia lungo il fondo di ogni pagina, che occupa tutta la larghezza della
finestra anche sotto la barra laterale, riguarda l'installazione nel suo
insieme:

- **esecutore** e **API degli agenti**, verdi quando sono in esecuzione. Se uno
  dei due è rosso, gli agenti non verranno eseguiti e nient'altro
  nell'interfaccia te lo dirà.
- **agenti**: quanti sono accesi su quanti ne esistono.
- **bacheca**: le schede in ogni colonna.
- **token oggi**: tutto quello che è stato speso dalla mezzanotte UTC, su tutti
  gli agenti, e quante esecuzioni ci sono volute. È il numero che mostra che un
  agente è entrato in un ciclo prima che lo mostri la fattura.

All'estremità destra della striscia, il logo di GitHub e il nome **nipegun**
aprono il repository del progetto, <https://github.com/nipegun/bunch-of-aigents>,
in una nuova scheda. L'account con cui hai effettuato l'accesso non viene
mostrato: un'installazione ne ha sempre e solo uno, quindi stamparlo non direbbe
niente che tu non sappia già.

## In che lingua rispondono i tuoi agenti

Scrivi il prompt di ogni agente nella lingua in cui pensi e ti risponderà in
quella. Questo copre la chat. Non copre un'esecuzione avviata dal crontab
dell'agente stesso: nessuno gli ha scritto in nessuna lingua, e i prompt inclusi
sono in inglese - così un'installazione che funzionava in spagnolo riceveva i
suoi resoconti programmati in inglese.

**Impostazioni → Agenti → Lingua in cui rispondono gli agenti** risolve il
problema per tutti gli agenti insieme. Aggiunge una riga al prompt di sistema di
ogni agente, scritta nella lingua che richiede, che dice che prevale su
qualunque cosa il prompt dica sulle lingue. Lasciala sul valore predefinito e
non cambia niente: ogni agente risponde nella lingua del suo prompt.

Viene tenuta sul server, a differenza della lingua di questa interfaccia, che è
una preferenza del tuo browser. Un'esecuzione svegliata da cron non ha un
browser.

## Scrivere i prompt nella tua lingua

Scrivi il prompt di sistema nella lingua in cui pensi. Niente nel sistema è
legato all'inglese: il prompt, la memoria, la chat, i titoli delle schede e i
messaggi tra i servizi sono tutti UTF-8 da un capo all'altro, accenti compresi.

Il prompt predefinito che riceve un nuovo agente è in inglese, e la sua ultima
regola dice all'agente di rispondere nella lingua in cui è scritto il suo
prompt. Riscrivilo tutto nella tua lingua e quella regola se ne va con il resto -
l'agente seguirà il prompt che ha, non quello con cui ha cominciato.

I prompt vengono salvati con righe intere, non mandati a capo a una colonna
fissa. La casella di testo li manda a capo sullo schermo perché restino
leggibili, senza mettere gli a capo nel file: una regola che è una frase resta
una riga, e modificarla non significa rifare gli a capo di un paragrafo.

## Backup e ripristino

Tutto quello che rende tua questa installazione vive sotto `/opt/boa/` e negli
utenti Linux degli agenti. Un solo comando lo raccoglie in un unico archivio:

```bash
./install-update-reinstall-debian.sh --backup
```

Scrive `/root/boa-backup-<date>.tar.gz`, solo `root`, modo 0600, con i servizi
in esecuzione - non si ferma niente. Passa un percorso per scriverlo altrove:
`--backup /mnt/usb/boa.tar.gz`. Dentro: entrambi i database, copiati tramite
l'API di backup di SQLite stessa, così non si perde niente che sia ancora in un
write-ahead log; le chiavi dei provider, i segreti dei canali e il segreto delle
sessioni; i certificati; ogni agente con la sua home, i suoi file protetti, il
suo utente Linux e il suo crontab; le competenze e gli strumenti scritti su
questo server; e il log di installazione, per la password che contiene. Non
dentro: il codice, l'ambiente Python, il browser, e le due scelte proprie di
questa macchina - la modalità delle porte e se ha un browser - così un
ripristino non importa mai quelle di un'altra macchina.

**Tienilo privato quanto la macchina.** Contiene ogni chiave API, ogni token dei
canali e la password di accesso.

Per ripristinare, su questa macchina o su una nuova:

```bash
./install-update-reinstall-debian.sh --install       # solo su una macchina nuova
./install-update-reinstall-debian.sh --restore /root/boa-backup-<date>.tar.gz
```

Chiede un YES, oppure accetta `--yes`. Poi ferma i servizi, ricrea gli utenti
degli agenti con gli stessi nomi, e gli stessi id quando sono liberi, sostituisce
i database, le chiavi, i certificati, gli agenti, le competenze e gli strumenti
con quelli dell'archivio, installa i crontab, e avvia tutto. Accedi con l'email e
la password del backup: entrambe vengono aggiunte a `/opt/boa/logs/install.log`
sotto l'intestazione `Credentials of the restored
backup`, e l'intero log del backup viene conservato accanto come
`install.log.restored-<date>`.

Un agente che questa macchina aveva e il backup no mantiene la sua home su disco
e sparisce dall'interfaccia, perché l'elenco degli agenti sta nel database
ripristinato. Su Alpine sono le stesse due flag su
`install-update-reinstall-alpine.sh`.

## Servizi

| Servizio | Gira come | Che cosa fa |
|---|---|---|
| `boa-proxy` | `boa` | HAProxy: termina il TLS su 11443, reindirizza 11080 e serve le porte web |
| `boa-web` | `boa` | L'interfaccia web e l'API, su un socket Unix dietro il proxy |
| `boa-exec` | `root` | Crea gli utenti, installa i crontab, avvia le esecuzioni degli agenti |
| `boa-samba` | `root` | Autentica gli utenti SMB e serve ogni cartella samba/ come il suo utente agente |
| `boa-agent-api` | `boa` | La porta che gli agenti usano per raggiungere la bacheca e i canali |
| `boa-buzzer` | `boa` | Sorveglia la bacheca e sveglia un agente quando una scheda arriva a scadenza |
| `boa-embeddings` | `boa` | Serve il modello di vettorizzazione locale delle biblioteche documentali, su un socket Unix |
| `boa-rag` | `boa` | Gestisce la coda di indicizzazione delle biblioteche documentali |
| `boa-channel-telegram.service` | `boa` | Ascolta su Telegram, così puoi rispondere a un agente dal telefono |
| `boa-channel-discord.service` | `boa` | Lo stesso per un canale Discord |

```bash
systemctl status boa-proxy boa-web boa-exec boa-agent-api boa-buzzer \
                 boa-embeddings boa-rag \
                 boa-channel-telegram.service boa-channel-discord.service boa-samba
journalctl -u boa-exec -f
```

Su Debian le unità dei canali usano `boa-channel-<channel>.service`. Aggiornare
con `--update` ferma e disabilita le vecchie unità dei canali prima di abilitare
le nuove.

Gli stessi processi girano su Alpine; i suoi servizi dei canali restano
`boa-telegram` e `boa-discord`. Sono servizi OpenRC supervisionati con
`supervise-daemon`, e quello che ciascuno stampa va in un suo file sotto
`/opt/boa/logs/`, ruotato ogni settimana:

```bash
rc-status
rc-service boa-exec status
tail -f /opt/boa/logs/boa-exec.log
```

## Sicurezza

Il progetto parte dal presupposto che un agente prima o poi farà qualcosa che non
intendevi, perché è un modello linguistico con una shell.

- **Ogni agente è un utente Linux separato**, e la sua home è `0700`. Gli agenti
  non possono leggere i file, i prompt o le chiavi API gli uni degli altri.
- **`/opt/boa/agents/` è `0711`**, quindi nessun agente può nemmeno elencare
  quali altri agenti esistono.
- **Nessun agente gira come root, mai.** Lo fa solo `boa-exec`, e accetta un
  elenco chiuso di operazioni attraverso un socket Unix. Tra queste non c'è
  nessun «esegui questo comando».
- **Un'esecuzione è limitata dal kernel, non solo dai suoi tetti.** Nessun
  agente può avere più di 1024 processi e thread, quindi una fork bomb si ferma a
  quel numero; su Debian ogni esecuzione vive in uno scope systemd tutto suo con
  2 GiB di memoria, che quando finisce chiude anche quello che l'esecuzione ha
  lasciato in esecuzione.
- **Gli agenti non vedono mai le credenziali dei canali.** Un token di bot non è
  un messaggio: è un'autorizzazione permanente a mandare qualsiasi cosa quel bot
  possa mandare. Gli agenti chiedono all'API degli agenti di inviare, ed è lei a
  inviare.
- **Gli agenti toccano solo le loro schede.** Vedi
  [La bacheca kanban](#la-bacheca-kanban).
- **`web.fetch` rifiuta gli indirizzi privati**, controllando l'IP risolto e
  ricontrollando a ogni reindirizzamento, così a un agente che legge una pagina
  ostile non si può far chiamare la tua rete interna.

È pensato per una LAN e non va esposto a Internet.

## Quando qualcosa non funziona

**Ho scelto `--ports direct` e l'HAProxy della macchina è sparito.** Non è
sparito, è in pensione: fermato, tolto da ogni runlevel su Alpine, disabilitato e
mascherato su Debian, e il suo `/etc/haproxy/haproxy.cfg` cancellato se l'aveva
scritto l'installer, o conservato come `haproxy.cfg.before-boa.<date>` se l'avevi
scritto tu. In questa modalità l'applicazione occupa lei stessa 80 e 443, e
qualsiasi altra cosa che tenga quelle porte le impedisce del tutto di avviarsi -
un proxy lasciato abilitato le prenderebbe al prossimo avvio, prima ancora che
l'applicazione parta. Il pacchetto `haproxy` è ancora installato apposta:
`boa-proxy` è `/usr/sbin/haproxy`, e in questa modalità è lui a servire 80 e 443.

Per tornare indietro, esegui l'installer con `--update --ports proxied`:
smaschera l'unità, riscrive la configurazione della macchina e la avvia. Il tuo
vecchio file, se ce n'era uno, è ancora lì accanto con il suo nome `before-boa`.

**`boa-proxy` si riavvia di continuo e niente ascolta su 11443.** Leggi
`/opt/boa/logs/boa-proxy.log`. Se dice `Cannot raise FD limit to 4131`, il
limite rigido dei descrittori di file di questa macchina è più basso di quello
che il proxy ha chiesto - di solito, un container piccolo. Un'installazione
fatta prima che questo venisse corretto ha ancora `maxconn 2048` in
`/opt/boa/config/haproxy.cfg`. Eseguire l'installer con `--update` riscrive il
file; per sistemarlo sul momento:

```bash
sed -i 's/^  maxconn 2048$/  fd-hard-limit 4000/' /opt/boa/config/haproxy.cfg
rc-service boa-proxy restart        # systemctl restart boa-proxy su Debian
```

HAProxy allora si dimensiona in base ai descrittori che può davvero avere, che
con un limite rigido di 4096 sono circa 1987 connessioni - molte più di quante
ne servano mai.

**L'installer finisce con «Everything is in place but the application does not
answer».** L'installazione c'è e una pagina non è mai tornata indietro. Il log
contiene già il motivo:

```bash
sed -n '/Why it did not answer/,$p' /opt/boa/logs/install.log
```

Quel blocco è com'era la macchina in quel momento: che cosa ha ricavato curl
dalla richiesta, se c'è qualcosa in ascolto sulla porta, lo stato di tutti e dieci
i servizi, e le ultime righe di quello che hanno stampato il proxy e
l'applicazione web. `000` non è un codice HTTP - è curl che dice di non averne
mai ricevuto uno. Un servizio che si dichiara `started` accanto a `nothing is
listening on port 11443` è un processo che muore e viene riavviato ogni pochi
secondi, e il suo log, qualche riga più sotto, dice perché.

Un aggiornamento che è fallito qui ha già rimesso al suo posto la versione
precedente e la sta eseguendo. Una prima installazione non ha niente a cui
tornare, quindi lascia tutto dov'è: sistema quello che il blocco nomina ed esegui
di nuovo l'installer con `--update`.

**L'installer si ferma con «systemd is not running».** Si sta rifiutando di
installare su una macchina dove systemd non è il PID 1, perché ogni servizio che
scrive è un'unità systemd e non ci sarebbe niente ad avviarli. Un Debian normale
va bene; un container no, a meno che non sia stato creato per eseguire systemd:

```bash
apt-get install -y systemd systemd-sysv dbus dbus-user-session
```

e poi ricrea il container con `/sbin/init` come comando - un container già in
esecuzione non può cambiare il suo PID 1. Su Alpine questo non succede:
quell'installer aggiunge OpenRC da solo quando la macchina non ce l'ha.

**Non succede niente quando premo Esegui ora.** Guarda i due puntini in fondo
alla barra laterale. Se `executor` («esecutore») è rosso:

```bash
systemctl status boa-exec
journalctl -u boa-exec -n 50
```


**Il browser mostra 503 e i servizi sono tutti in esecuzione.** L'HAProxy della
macchina ha segnato il backend come giù. Quasi sempre è colpa di `option
ssl-hello-chk` su quel backend: il suo ClientHello è anteriore a TLS 1.2 e
l'applicazione lo richiede. Togli quella riga e ricarica HAProxy.

**Un agente gira ma non fa niente.** Controlla il suo pannello Cronologia. Poi
eseguilo a mano e guarda:

```bash
runuser -u agent-001 -- /opt/boa/venv/bin/python3 \
  /opt/boa/webapp/backend/core/runner.py --agent-id 001
```

Aggiungi `--dry-run` per vedere che cosa caricherebbe — provider, strumenti,
tetti — senza chiamare il modello.

**Dice che non riesce a raggiungere il modello.** Per i provider self-hosted,
controlla che il server sia attivo e che l'URL di base sia giusto. Per quelli
cloud, controlla che il file della chiave esista nella home dell'agente e sia di
proprietà di quell'agente.

**Dice che uno strumento non gli è disponibile.** Lo strumento non è spuntato
nella pagina di quell'agente. Il prompt non può scavalcarlo, ed è proprio questo
il punto.

**Le schede hanno smesso di comparire.** O la casella kanban è senza spunta per
quell'agente, oppure `agent API` («API degli agenti») è rossa in fondo alla
barra laterale:

```bash
systemctl status boa-agent-api
```

**Voglio vedere tutto quello che ha fatto un agente.** Il suo registro sta nella
sua home:

```bash
cat /opt/boa/agents/001/runs.jsonl
```

Un oggetto JSON per riga: quando è stato eseguito, che cosa ha speso, se ha
finito.

## Licenza

MIT. Vedi [LICENSE](../LICENSE).
