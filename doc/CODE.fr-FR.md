# CODE.md

Référence technique de Bunch of AIgents. Écrite pour être consultée de façon
chirurgicale : allez directement à la section dont vous avez besoin, ne la
lisez pas de bout en bout.

## Index

1. [Architecture et décisions de conception](#1-architecture-et-décisions-de-conception)
2. [Carte des modules](#2-carte-des-modules)
3. [Index des symboles clés](#3-index-des-symboles-clés)
4. [Flux principaux](#4-flux-principaux)
5. [Carte des points d'entrée et des routes](#5-carte-des-points-dentrée-et-des-routes)
6. [Analyse d'impact](#6-analyse-dimpact)
7. [Points d'extension](#7-points-dextension)

---

## 1. Architecture et décisions de conception

C'est la partie qu'on ne peut pas déduire du code, et donc celle qui vaut la
peine d'être lue.

### La prémisse

Un agent, ici, est un modèle de langage doté d'un shell sur un serveur, réveillé
par cron, sans personne pour le surveiller. Chaque décision structurelle découle
du fait de prendre cela au sérieux : le modèle finira par faire quelque chose
d'imprévu, donc la question n'est pas de savoir comment l'en empêcher, mais ce
qu'il peut atteindre quand cela arrive.

### Un utilisateur Linux par agent

L'agent `007` est l'utilisateur système `agent-007`, propriétaire de
`/opt/boa/agents/007/` en mode `0700`. L'isolation entre agents est celle du
noyau, pas un bac à sable écrit en Python. Un agent ne peut pas lire le prompt
système, le journal ou la clé d'API d'un autre agent, parce que le système de
fichiers l'interdit.

`/opt/boa/agents/` lui-même est en `root:root 0711` : traversable, pas
listable. Un agent ne peut pas énumérer les autres agents, seulement échouer à
ouvrir des chemins qu'il devine.

C'est grâce à cette décision que `bash.run` n'a besoin d'aucune liste blanche.
Une liste noire sur un shell relève du théâtre — tout ce qui peut lancer `sh`
peut lancer tout ce que la liste nomme — alors qu'un compte utilisateur est une
frontière que le noyau fait respecter.

### Ce qu'un agent ne peut pas réécrire de lui-même

Le répertoire personnel appartient à l'agent, en 0700, et c'est tout l'intérêt :
sa mémoire, son journal, sa conversation et tout script qu'il écrit y vivent.
Trois fichiers qui le concernent ne sont pas à lui de modifier, et ils sont
EN DEHORS du répertoire personnel, dans `/opt/boa/agents-config/xxx/`, qui est
en `root:agent-xxx 0750` sous un parent en `root:root 0711`.

| Fichier | Pourquoi il n'appartient pas à l'agent |
|---|---|
| `info.json` | Les outils qui lui ont été accordés et ce qu'il peut dépenser |
| `system-prompt.md` | La définition de ce qu'il est censé faire |
| `api-token` | Ce avec quoi il s'identifie auprès de l'API des agents |

Ce qui fait fonctionner cela n'est pas le propriétaire des fichiers : c'est
celui du répertoire. Le droit d'écriture sur un répertoire est ce qui décide si
un fichier qu'il contient peut être supprimé et remplacé, si bien qu'un agent
propriétaire du répertoire pourrait supprimer `info.json` et écrire le sien,
quel que soit le propriétaire du fichier. Il peut entrer dans celui-ci et le
lire, et il ne peut rien y créer, renommer ni supprimer.

**Et cette règle s'applique au tiroir autant qu'à ce qu'il contient**, c'est
pourquoi ces fichiers ne vivent plus dans `agents/xxx/config/`. Ce chemin était
une entrée du répertoire PERSONNEL, ce répertoire appartient à l'agent en 0700,
et renommer une entrée exige le droit d'écriture sur le parent et rien
d'autre - le mode de ce qui est renommé n'est jamais consulté. L'agent ne
pouvait donc pas modifier `info.json`, mais il pouvait faire ceci :

    mv ~/config ~/config-old && mkdir ~/config && echo '...' > ~/config/info.json

et être lu depuis le substitut. Sortir le tiroir du répertoire personnel place
chaque répertoire du chemin sous root. Deux choses découlent de ce
déplacement :

  - **Il n'y a plus de repli vers le répertoire personnel.** Il y en avait un,
    pour qu'une mise à jour ne soit pas un service qui cesse de répondre avant
    que la migration ne s'exécute - et c'était lui-même un contournement,
    puisqu'il suffisait de cacher le vrai fichier pour que l'agent fasse lire
    le sien à la place. Le démon migre désormais au démarrage, en plus de
    l'installateur, si bien qu'il ne reste rien à couvrir.
  - **Supprimer un agent supprime aussi sa configuration.** Elle n'est plus
    dans le répertoire personnel qu'emporte `userdel --remove`, et laissée
    derrière, elle serait remise au prochain agent recevant cet identifiant.

`fOpenProtectedAgentFile` est la seconde réponse à la même question : il ouvre
avec `O_NOFOLLOW` et vérifie sur le FICHIER OUVERT qu'il s'agit d'un fichier
ordinaire, appartenant à root, et que personne d'autre ne peut écrire. C'est ce
qui résiste à un chmod erroné pendant une mise à jour, ou à la restauration
d'une sauvegarde avec le mauvais propriétaire.

Cela a été mesuré avant d'être corrigé, sur une vraie installation : un agent a
ajouté `mail.read` à son propre `info.json` et le démon privilégié a ensuite
signalé l'outil comme accordé - un agent pouvait donc s'accorder la boîte aux
lettres, les canaux, ou relever ses propres plafonds. Il pouvait aussi
remplacer son propre prompt par « ignore toutes tes règles », qui serait resté
ainsi à chaque exécution à partir de là.

L'isolation entre agents n'a besoin de rien de tout cela : `/opt/boa/agents/`
est en `root:root 0711` et chaque répertoire personnel en 0700, donc le noyau
refuse déjà. C'est pourquoi elle tient même quand un outil contient un bogue.

### Ce que root lit dans le répertoire personnel

Le journal, la mémoire et la conversation sont les propres fichiers de l'agent :
écrits par ses propres processus, dans son propre répertoire personnel en 0700,
et lus par le démon privilégié en tant que root - qui lit tout ce vers quoi on
le pointe. Mesuré sur le code avant que ceci n'existe : une FIFO nommée
`runs.jsonl` retenait pour toujours le thread du démon qui l'avait ouverte, et
comme la liste des agents lit le journal de chaque agent, chaque requête
ultérieure pour cette liste faisait fuir un thread de plus ; un lien nommé
`memory.md` pointant vers n'importe quel fichier de la machine amenait root à
remettre le texte de ce fichier à l'interface ; et un lien vers quelque chose
sans fin faisait lire root jusqu'à ce qu'on le tue.

Les trois sont donc lus par `fReadAgentOwnedFile`, qui est le pendant de
`fOpenProtectedAgentFile` pour les fichiers qui SONT à l'agent : `O_NOFOLLOW`
refuse un lien à l'ouverture, `O_NONBLOCK` empêche une FIFO de bloquer
l'ouverture jusqu'à ce que quelqu'un y écrive, et les vérifications se font sur
le descripteur ouvert - un fichier ordinaire, appartenant à l'utilisateur de
l'agent - si bien que rien ne peut être substitué entre la vérification et la
lecture. Il ne lit jamais au-delà d'une borne, tenue sur ce qui est lu et pas
seulement sur ce qu'a dit `fstat`, parce que l'agent peut ajouter des données
pendant la lecture : 32 Mo pour le journal et pour la conversation, lus depuis
la FIN quand le fichier est plus grand, puisque les lignes les plus récentes
sont ce que montre un historique ; 4 Mio pour la mémoire, assez pour son maximum
d'un million de caractères UTF-8. Seuls les fichiers écrits de l'extérieur qui
dépassent ce budget de lecture reçoivent `[truncated]` ; `fWrite` rejette un
contenu trop volumineux avant de remplacer quoi que ce soit. Un octet invalide
coûte une ligne, pas la lecture.

Ce qui est refusé est dit, pas avalé : `read_run_journal`, `read_chat` et
`read_memory` échouent en donnant la raison, si bien qu'un opérateur apprend que
quelque chose dans ce répertoire personnel n'est pas ce que l'application a
écrit. La seule exception est `read_usage_summary` pour tous les agents, à
partir duquel la barre latérale est dessinée : là, un journal illisible coûte
ses totaux à cet agent, avec la raison à côté, et à personne d'autre les siens.

### Ce qui passe par la ligne de commande

Le démon lance une exécution en tant qu'agent avec `Popen`, et le message que le
propriétaire avait tapé - ou le prompt que construit une carte arrivée à
échéance - était autrefois l'un de ses arguments : `--chat-message <text>`,
`--prompt <text>`. La ligne de commande d'un processus est lisible par tout
utilisateur de la machine via `/proc/<pid>/cmdline`, et un agent doté de
`bash.run` est un utilisateur de la machine. Mesuré sur la machine de test
Debian : `ps` lancé en tant qu'`agent-001` montrait le message que le
propriétaire venait d'envoyer à `agent-000`, pendant toute la durée de vie de
cette exécution, c'est-à-dire par défaut jusqu'à cinq minutes.

Le texte passe donc par l'entrée standard de l'enfant et la ligne de commande
ne porte que `--chat-message-on-stdin` ou `--prompt-on-stdin`. `fStartRunner`
est le seul endroit qui lance un runner : il refuse un texte plus long que
`cMaxStdinPayloadBytes` avant qu'aucun processus n'existe, parce que cette
borne est inférieure au tampon de 64 Kio d'un pipe et qu'une écriture qui tient
dans le tampon n'attend jamais l'enfant - ce démon n'attend pas les runners. Un
enfant déjà disparu au moment de l'écriture, un interpréteur qui échoue à
l'import, c'est un pipe cassé et pas un échec du démon. De l'autre côté, le
runner lit le texte avec la même borne, refuse un message de conversation vide
plutôt que de répondre à une question que personne n'a posée, et clôt le tour
pour lequel il a été lancé quand il refuse, pour que la conversation n'attende
pas éternellement. `--prompt` et `--chat-message` restent, pour une exécution
lancée à la main depuis un terminal.

### Ce qu'une exécution peut faire à la machine

Les plafonds de `info.json` - jetons, étapes, secondes, exécutions par jour -
sont appliqués par le runner, et le runner est un programme que l'agent pilote.
Ce qui tient quand c'est le programme lui-même qui a déraillé est appliqué par
le noyau, en deux couches.

Le runner abaisse ses propres limites de ressources avant de faire quoi que ce
soit d'autre, `fApplyResourceLimits`, depuis le point d'entrée et non depuis
`fMain` - les tests appellent `fMain` dans le même processus, et un
RLIMIT_NPROC abaissé dans la session d'un développeur où tournent déjà des
milliers de threads empêche cette session de forker. Chaque processus lancé par
l'exécution en hérite : RLIMIT_NPROC à 1024, compté sur l'uid de l'agent dans
son ensemble, si bien qu'une fork bomb lancée par `bash.run` s'arrête à ce
nombre et non à la machine - les threads comptent aussi, c'est pourquoi la
limite n'est pas plus basse, un navigateur en représentant quelques centaines ;
pas de fichiers core ; aucun fichier au-delà de 4 Gio. Pas de RLIMIT_AS :
Chromium réserve de l'espace d'adressage par dizaines de gigaoctets et ne
démarrerait pas. Cette couche est la même sur Debian et sur Alpine, et c'est la
seule dont dispose une exécution lancée par le propre crontab de l'agent.

Là où systemd est le PID 1, le démon ajoute la seconde : `fStartRunner` place
l'exécution dans un scope transitoire qui lui est propre,
`boa-agent-<id>-<random>.scope` sous `boa-agents.slice`, avec `TasksMax=1024`
et `MemoryMax=2G`. `systemd-run --scope` fait un exec vers la commande, donc le
pid reste celui du runner et `/proc` montre toujours sa ligne de commande ;
c'est `setpriv` qui descend vers l'agent, parce que systemd-run doit être root
pour créer le scope. Mesuré avant qu'il en soit ainsi : une exécution était un
enfant de `boa-exec.service`, dans le propre cgroup du démon, et un agent
emballé épuisait le TasksMax du démon et le laissait incapable de forker. Le
scope est aussi ce qui met fin à ce qu'une exécution a laissé derrière elle :
`bash.run` envoie son signal à son propre groupe de processus, si bien qu'une
commande qui appelait `setsid`, ou un enfant en arrière-plan d'une commande
terminée à temps, survivait à l'exécution ; `fWatchRunner` attend l'exécution et
arrête son scope, ce qui atteint tout ce que l'exécution a lancé, où que cela
se soit déplacé. Une exécution tuée - par la limite de mémoire, par un
opérateur - n'a rien écrit en sortant, donc le même thread consigne la fin dans
le journal et clôt le tour dans la conversation ; une exécution sortie d'elle-même
a déjà fait les deux, et le tour est vérifié plutôt que supposé.

### Où vivent les clés des fournisseurs

Les clés partagées par tous les agents sont dans
`/opt/boa/config/apikeys/<provider>.key`, propriété de `boa`, le répertoire en
`0700` et les fichiers en `0600`.

0750 et 0640 tiendraient déjà les agents à l'écart - aucun utilisateur d'agent
n'est dans le groupe `boa` - mais cela suppose que la liste de groupes de chaque
agent reste vide pendant toute la vie de l'installation, ce qui n'est qu'à un
`usermod -aG` d'être faux. Un mode qui n'accorde rien au groupe n'en dépend
pas. `api_keys.fWrite` fixe les deux modes à chaque écriture et pas seulement à
la création, si bien qu'un répertoire venu d'une installation plus ancienne est
verrouillé la première fois qu'une clé est enregistrée.

Le répertoire s'appelait `keys` jusqu'à ce qu'il soit renommé : on le lisait
comme « les clés de cette installation » et il n'était qu'à une faute de frappe
du `keys/` propre à chaque agent dans son répertoire personnel, qui est une
autre chose, qu'un agent *peut* lire - sa propre clé, placée là pour le
facturer à un autre compte. L'installateur déplace l'ancien répertoire lors
d'un `--update` et ne le supprime qu'une fois vide.

Rien de tout cela n'empêche un agent de détenir la clé du fournisseur sur lequel
il tourne réellement : l'API des agents la lui remet, il en a besoin pour faire
l'appel, et un agent doté de `bash.run` pourrait l'afficher. Ce que cela
empêche, c'est qu'un agent lise les clés des fournisseurs qu'il n'utilise pas.

### Dix services, dont deux lancés en root

| Processus | Utilisateur | Pourquoi il existe |
|---|---|---|
| `boa-proxy` | `boa` | HAProxy : termine le TLS, sert les deux ports |
| `boa-web` | `boa` | Sert l'interface et l'API, sur une socket Unix |
| `boa-exec` | `root` | Crée les utilisateurs et lance les exécutions des agents |
| `boa-samba` | `root` | Authentifie les sessions SMB, puis sert les fichiers en tant qu'agent propriétaire |
| `boa-embeddings` | `boa` | Sert le modèle de vectorisation local des bibliothèques documentaires, sur un socket Unix |
| `boa-rag` | `boa` | Ordonnance la file d'indexation des bibliothèques documentaires |
| `boa-agent-api` | `boa` | Détient ce que les agents peuvent utiliser mais pas lire |
| `boa-buzzer` | `boa` | Réveille un agent quand l'une de ses cartes arrive à échéance |
| `boa-channel-telegram` | `boa` | Écoute Telegram et remet ce qui arrive à un agent |
| `boa-channel-discord` | `boa` | La même chose, pour un canal Discord |

Sur Debian, les unités des canaux sont `boa-channel-telegram.service` et
`boa-channel-discord.service` ; les futures unités de canaux suivront
`boa-channel-<channel>.service`. OpenRC conserve `boa-telegram` et
`boa-discord`. `system_info.fServiceName` résout ces noms à la fois pour
l'onglet Système d'exploitation et pour les rapports d'état des écouteurs.

`fInstallSystemdUnits` appelle `fRetireLegacyChannelUnits` pour arrêter et
désactiver chaque ancienne unité de canal avant de la supprimer et d'activer
celle qui la remplace. Les mises à jour répétées fonctionnent aussi quand
aucune ancienne unité n'existe. Si une mise à jour échoue avant d'installer
les nouvelles unités, `fStartServices` peut redémarrer les anciennes pendant
le retour arrière.

Les quatre derniers sont `boa` et non root à dessein : chacun d'eux a besoin
que quelque chose soit fait sous l'utilisateur propre d'un agent - lancer une
exécution, écrire dans un répertoire personnel en 0700 - et chacun demande à
`boa-exec` de le faire plutôt que de recevoir le privilège. Un service
joignable depuis l'extérieur, comme le sont en pratique les deux écouteurs, est
le dernier qui devrait le détenir.

### Un environnement virtuel n'est pas déplaçable

`python3 -m venv <path>` écrit `<path>` dans le shebang de chaque script
console installé ensuite dedans, dans `VIRTUAL_ENV` des scripts d'activation,
et dans la ligne `command` de `pyvenv.cfg`. L'environnement est construit dans
`venv.new` puis renommé en `venv`, si bien que les trois nomment alors un
répertoire qui n'existe plus.

Mesuré sur un vrai Debian 13 et un vrai Alpine 3.24 : les deux installations
sont allées au bout, les deux ont affiché « Installation finished », et les deux
ont laissé `boa-web` redémarrer toutes les cinq secondes avec

```
status=203/EXEC - Failed to execute /opt/boa/venv/bin/gunicorn:
No such file or directory
```

Le fichier était là. Sa première ligne nommait `/opt/boa/venv.new/bin/python3`,
qui, lui, n'y était pas.

`fBuildVirtualEnv` avait une vérification pour exactement cette classe
d'échec, et elle passait, parce qu'elle lance `bin/python3` - un LIEN
SYMBOLIQUE vers l'interpréteur du système, qui répond d'où qu'il se trouve.
Seul un script console a le chemin gravé en dur. La vérification lance donc
aussi `bin/gunicorn --version`, qui est le fichier qu'exécute l'unité du
service, et `fRepointVirtualEnv` réécrit les trois chemins enregistrés pendant
que l'environnement porte encore son nom de construction. La réécriture est
vérifiée plutôt que supposée : si un futur pip écrit ses scripts console d'une
autre façon, l'installateur s'arrête là.

### Une mise à jour qui échoue laisse quelque chose en marche

Trois étapes, et c'est leur ordre qui répare.

Une mise à jour arrêtait autrefois les services, supprimait `webapp/` et ne
lançait pip qu'ensuite. Un pip qui échouait - pas de réseau, un index en panne,
une wheel qui refusait de se construire - laissait une installation aux
services arrêtés et au code disparu : une machine qui marchait une minute plus
tôt, et qui avait besoin que quelqu'un s'en aperçoive et la récupère à la main.

| Étape | Ce qui se passe | Ce que coûte un échec |
|---|---|---|
| Préparation | Questions posées, dépendances installées, code téléchargé, le nouveau virtualenv CONSTRUIT à côté de celui qui tourne et vérifié pour s'assurer qu'il importe | Rien. L'ancienne version tourne toujours, intacte |
| Bascule | Arrêt, `webapp/` déplacé vers `webapp.previous`, `venv` vers `venv.previous`, les nouveaux mis en place, démarrage | Réversible : les deux versions précédentes sont toujours sur le disque |
| Vérification | `curl` demande la page de connexion à l'application, quinze fois en trente secondes | `fRollBack` remet les deux en place et les redémarre |

Ce `curl` n'envoie le protocole PROXY qu'en mode `proxied`. En mode `direct`, le
bind n'a pas d'`accept-proxy`, si bien qu'un en-tête PROXY atterrit dans la
négociation TLS et que la requête ne reçoit aucune réponse. Il était autrefois
envoyé dans les deux modes, ce qui faisait finir chaque
`--install --ports direct` sur « did not answer » face à une installation qui
servait bien des pages, et revenir en arrière chaque `--update` en mode direct.
Confirmé en faisant passer les deux machines de test en `direct` puis en les
remettant : avec l'option liée au mode, les deux ont répondu 200 sur 443, puis
sur 11443. Un test lance `fVerifyInstallation` des deux installateurs contre un
`curl` qui enregistre ses arguments, une fois par mode, et vérifie que l'option
est présente dans l'un et absente dans l'autre.

Quand ce `curl` n'obtient jamais de réponse, `fExplainWhyItDoesNotAnswer` écrit
l'état de la machine à cet instant dans le log même que désigne l'erreur : ce
que curl dit lui-même - interrogé de nouveau avec `-sS`, pour distinguer une
connexion refusée, une négociation qui a échoué et une requête arrivée à
expiration, car `000` n'est pas un code HTTP mais curl disant qu'il n'en a
jamais reçu - l'état de chacun des dix services, si quoi que ce soit écoute
sur le port, et les quinze dernières lignes de `boa-proxy.log`, `boa-web.log`
et de l'`error.log` de gunicorn. `fReportServiceStates` est la moitié qui
diffère entre les deux : `rc-service ... status` sur Alpine,
`systemctl is-active` plus le journal de `boa-web` et de `boa-proxy` sur
Debian.

Elle existe parce qu'une première installation sur un Alpine tout neuf s'est
terminée sur « The application did not answer on port 11443 (last code: 000) »
et que le log ne contenait rien d'autre à ce sujet - ni quel service était
arrêté, ni si le port était occupé, ni une seule ligne de ce que gunicorn avait
affiché. Le seul fichier que nomme l'erreur ne pouvait pas répondre à la
question pour laquelle on l'ouvrait. Ce qu'il faut y chercher : un service qui
se dit démarré à côté de « nothing is listening on port 11443 » est un processus
qui meurt et est relancé, parce qu'un service supervisé qui meurt à l'instant
où il démarre est signalé comme démarré par la commande qui l'a lancé. Quatre
tests EXÉCUTENT les deux fonctions - contre un `curl` qui refuse de se
connecter, un `ss` qui tient le port et un autre qui ne le tient pas, et un
`rc-service` et un `systemctl` qui répondent « stopped » et renvoient un échec.

`fRollBack` démarre les services dans un SOUS-SHELL, et le `|| true` à côté ne
suffit pas à lui seul : `fStartServices` appelle `fDie` quand un service refuse
de démarrer, `fDie` appelle `exit`, et `exit` termine le shell quoi qu'il y ait
d'écrit à côté. Mesuré sur un vrai Alpine : `boa-proxy` a été arrêté par OpenRC
pendant que `boa-web` faisait du yo-yo, le démarrage lancé par le retour arrière
lui-même a perdu la course pour le verrou du service, et l'installateur est mort
À L'INTÉRIEUR de `fRollBack`. Le retour arrière avait fonctionné - la version
précédente était revenue et répondait - mais ce qu'on a dit à l'opérateur,
c'était « The boa-proxy service would not start », sans un mot sur le fait
qu'une mise à jour venait d'être annulée. À ce stade, le récit de ce qui s'est
passé est la seule chose dont dispose un opérateur.

La version précédente est supprimée par `fFinishUpdate`, et seulement après que
la nouvelle a répondu.

`fRollBack` ne s'exécutait autrefois qu'à un seul endroit : quand ce `curl`
final échouait. Entre `fStopServices` et cette vérification, il y a une dizaine
d'étapes qui peuvent mourir - un fichier de certificat disparu, une
configuration de proxy que HAProxy refuse d'analyser, une unité qui refuse de
s'installer - et chacune laissait les services arrêtés, le nouveau code en place
et `webapp.previous` sur le disque sans personne pour le remettre. Le message
nommait ce qui avait échoué et ne disait rien du fait que la machine était
hors service. `fDoUpdate` positionne donc `vUpdateSwitched` juste avant
d'arrêter les services, et `fCleanup` - le trap EXIT, qui s'exécute quelle que
soit la façon dont le processus enfant se termine - revient en arrière quand il
trouve l'indicateur positionné et un code de sortie non nul. Les deux sorties
de la bascule l'effacent : `fRollBack` lui-même, pour que le chemin explicite
ne revienne pas deux fois en arrière, et `fFinishUpdate`, parce qu'une fois que
la nouvelle version a répondu il n'y a plus rien vers quoi revenir. Mesuré sur
les deux machines de test avec la clé privée cachée :
« Missing certificate files », « Putting the previous version back », tous les
services en marche et la page de connexion répondant 200 sur le code précédent. Un test exécute les vrais
`fCleanup`, `fRollBack` et `fFinishUpdate` de chaque installateur à travers
trois sorties : après la bascule, avant elle, et après la finalisation.

`--install` et `--reinstall` n'ont aucune version précédente à garder, ils n'ont
donc ni Bascule ni retour arrière - mais ils ont bien la Vérification. Ils se
terminaient autrefois sur `fWriteCredentialsFile`, et « Installation finished »
a été affiché sur deux vraies machines dont le service web redémarrait toutes
les cinq secondes : rien n'avait jamais rien demandé à l'application. Ils
demandent désormais la même page de connexion, et quand elle ne vient pas ils le
disent et nomment le log, parce qu'il n'y a rien sur la machine vers quoi
revenir.

`pip` lui-même est épinglé. `--upgrade pip` sans version voulait dire que deux
mises à jour du même code pouvaient se résoudre différemment, ce qui est
précisément ce qu'épingler les dépendances devait éviter. Ce qui n'est toujours
pas épinglé, ce sont les dépendances TRANSITIVES - c'est pourquoi `pip freeze`
est enregistré dans l'environnement et que la mise à jour suivante affiche ce
qui a bougé, seule façon pour quiconque de s'en apercevoir.

### Une installation interrompue à mi-chemin

`fIsInstalled` comptait une machine comme installée dès que `webapp/backend`
et l'utilisateur `boa` existaient - c'est-à-dire avant l'environnement virtuel,
les certificats, la base de données et l'administrateur. Une installation morte
pendant pip, sur un réseau qui avait lâché, recevait alors « already installed »
de `--install` et une mort sur ce qui manquait de `--update`, et seul
`--reinstall --yes` passait outre, sans que rien ne le dise à l'opérateur.

Une installation terminée laisse désormais `/opt/boa/installed`, écrit par
`fMarkInstalled` seulement après que `fVerifyInstallation` a obtenu sa page :
une installation en place qui ne répond pas n'est pas terminée, et une mise à
jour qui est revenue en arrière n'est pas la nouvelle version. Sans le marqueur,
les cinq choses qu'une installation terminée possède toujours - le code,
l'utilisateur, `venv/bin/gunicorn`, `db/boa.sqlite` et
`certificates/privkey.pem` - en tiennent lieu, si bien qu'une installation
antérieure à l'existence du marqueur compte toujours et reçoit son marqueur à
la mise à jour suivante. Tout le reste de ce que fait `--install` peut déjà être
fait deux fois sans risque : l'utilisateur n'est créé que s'il manque,
l'environnement est construit à côté de l'ancien, les certificats sont
conservés quand ils sont présents, l'administrateur est supprimé puis réécrit
avec le nouveau mot de passe. Une installation à moitié finie se termine donc
en relançant `--install` une fois de plus, et `--update` dit exactement cela
quand il en trouve une. Au passage, `fGeneratePassword` a été déplacé après
`fInstallDependencies` dans l'installateur Debian, où c'était l'inverse :
`openssl` est en Priority: optional sur Debian, et une image minimale générait
le mot de passe avant que le paquet qui le génère ne soit installé.

### Tout ce que lance l'installateur arrive dans son log

`fLog` écrivait ses propres lignes dans `install.log` et rien d'autre. apt, pip,
la validation de HAProxy et tous les autres sous-processus écrivaient sur le
terminal, si bien qu'une installation ratée laissait un log contenant
« Installing the dependencies. » et pas un mot de l'erreur d'apt qui expliquait
pourquoi - ce qui est précisément le détail que l'on cherche en ouvrant ce
fichier.

`fStartCapturingOutput` redirige la sortie standard et la sortie d'erreur de
ce shell lui-même vers une FIFO que `tee` copie dans le log et sur le terminal.
Une FIFO plutôt que `exec > >(tee ...)`, qui n'existe qu'en bash alors
qu'Alpine démarre sans bash, et plutôt qu'un pipeline autour de `fMain`, qui le
placerait dans un sous-shell et déferait l'arrangement `fMain & wait` qui garde
errexit en vie.

Deux conséquences, qu'il a fallu traiter toutes les deux :

`fLog` affichait la ligne ET l'ajoutait lui-même au log. Dès que la sortie
standard est un tee qui ajoute à ce même fichier, la seconde écriture est un
doublon : une installation de 90 lignes produisait un log de 185 lignes où
chaque ligne figurait deux fois. `fLog` n'écrit désormais dans le fichier que
tant que la capture n'est pas active.

`tee` garde le log ouvert par INODE. Un `--reinstall` supprime toute
l'arborescence, log compris, et remet une copie neuve - si bien qu'à partir de
ce moment `tee` ajoute à un inode sans nom, et comme `fLog` n'écrit plus dans
le fichier, ce serait toute la seconde moitié de la réinstallation, mot de passe
généré compris. `fRestartCapturingOutput` dirige la capture vers le fichier qui
existe maintenant.

### Deux installateurs, une seule application

`deploy/install-update-reinstall-debian.sh` écrit des unités systemd, et **a
besoin que systemd soit le PID 1 de la machine en marche** : un Debian démarré
avec autre chose n'est pas une cible, et l'installateur le refuse plutôt que
d'installer sur une machine qui ne démarrerait rien.
`deploy/install-update-reinstall-alpine.sh` écrit des services OpenRC dans
`/etc/init.d/`, à partir de `deploy/openrc/`, et n'a besoin de rien au
préalable : il installe OpenRC lui-même quand la machine n'en a pas. Les deux
installent les mêmes dix processus, la même arborescence sous `/opt/boa`, le
même modèle d'utilisateurs ; un test compare les deux étape par étape et
échoue quand l'un acquiert une étape que l'autre n'a pas.

Ils ne sont pas écrits dans le même langage, et c'est voulu. Celui de Debian
est en bash, comme tout le reste ici. Celui d'Alpine est en shell POSIX, avec
`#!/bin/sh`, parce qu'un Alpine tout neuf n'a pas bash : avec `#!/bin/bash`, le
noyau chercherait un interpréteur qui n'existe pas, et

    curl -fsSL <raw-url> | bash -s -- --install

échouerait avant de lire une seule ligne, sur la machine qui a le plus besoin de
l'installation en une ligne. En POSIX, il tourne aussi bien sous BusyBox ash
que sous dash et bash, si bien que le même fichier fonctionne envoyé par pipe
dans `sh` sur un Alpine nu et dans `bash` sur un Alpine qui l'a déjà. Il
installe toujours bash - chaque agent reçoit un shell bash - il n'en a
simplement plus besoin pour démarrer. Ce que cela coûte : les tableaux, `[[ ]]`,
`${var//x/y}` et `<(...)` ; `local` reste, parce que les trois shells l'ont, et
`pipefail` est d'abord testé dans un sous-shell avant d'être activé, parce que
dash ne l'a pas. Un test refuse chacune de ces constructions, puisqu'une
fonctionnalité de shell absente échoue au moment de l'installation, sur la
machine de quelqu'un d'autre.

Ce dont Alpine a besoin et pas Debian, et pourquoi aucun n'est facultatif :

| | Pourquoi |
|---|---|
| `shadow` | Le démon privilégié appelle `useradd --home-dir --create-home --shell`. L'`adduser` de BusyBox n'a aucune de ces options, et un agent qui ne peut pas être créé, c'est toute l'application qui ne marche pas |
| `bash` | Le shell que reçoit chaque agent, et ce par quoi passe `bash.run`. Alpine est livré sans lui, et c'est aussi pourquoi l'installateur d'Alpine est le seul fichier de ce projet écrit en shell POSIX plutôt qu'en bash : `#!/bin/bash` rendrait `curl ... \| sh` impossible sur la machine qui en a le plus besoin |
| `dcron` | Il faut bien que quelque chose lise les crontabs qu'écrit le démon. C'est aussi la raison du `-d` plus bas |
| `gcc`, `musl-dev`, `libffi-dev`, `python3-dev` | Plusieurs dépendances ne publient pas de wheel musl et sont compilées pendant l'installation |
| `libcap` | `setcap cap_net_bind_service` sur le binaire haproxy, en mode `direct`. systemd accordait cela service par service avec `AmbientCapabilities` ; OpenRC n'a pas d'équivalent |

Trois choses que le portage a dû changer dans le code, chacune découverte en
installant :

- **`crontab -u <agent>` au lieu de descendre vers l'agent.** Le `crontab` de
  Debian est setgid et n'importe quel utilisateur peut le lancer ; dcron sur
  Alpine le livre en `4750 root:wheel`, si bien qu'un agent qui le lance reçoit
  `Permission denied`. Les moyens de garder l'ancienne forme étaient de mettre
  chaque agent dans `wheel` - le groupe qui signifie sudo sur la plupart des
  systèmes - ou d'assouplir un binaire setuid du système. Le démon est root et
  peut nommer l'utilisateur à la place.
- **`-r` ou `-d` pour en supprimer un.** Vixie cron supprime un crontab avec
  `-r` ; dcron avec `-d`, et répond à `-r` par un message d'usage et le code de
  sortie 2. N'essayer que `-r` laissait derrière lui le crontab d'un agent
  supprimé, pointant toujours vers le runner d'un utilisateur qui n'existait
  plus. Les deux sont essayés, parce que ce qui décide, c'est le binaire
  installé, pas le nom de la distribution.
- **`executable=` dans `browser.conf`.** Playwright ne publie pas de build musl,
  donc sur Alpine le paquet est entièrement retiré des dépendances et il n'y a
  pas de navigateur. La ligne est lue par
  `browser.fReadConfiguredExecutable` et c'est là qu'on nommerait un Chromium du
  système, le jour où il existera un Playwright capable d'en piloter un.

Une de plus, trouvée en regardant `/proc/<pid>/fd/2` sur la machine de test
Alpine : `supervise-daemon` envoie la sortie standard et la sortie d'erreur
d'un processus vers `/dev/null` sauf indication contraire, et rien d'autre sur
Alpine ne les recueille - les unités de Debian ont journald pour cela. Aucun
service n'écrivait rien nulle part. Chaque script OpenRC nomme désormais
`output_log` et `error_log`, un fichier par service sous `/opt/boa/logs/`, créé
en tant que `boa` dans `start_pre` pour que logrotate puisse le faire tourner
en tant que `boa`, quel que soit celui qui y écrit. `fInstallLogRotation`, dans
les deux installateurs, écrit `/etc/logrotate.d/boa` pour ces fichiers et pour
les deux de gunicorn : rotation hebdomadaire, huit conservés, `copytruncate`
parce que les deux écrivains gardent leur fichier ouvert, et jamais
`install.log`, qui appartient à root et contient le mot de passe. L'autre
moitié de la même découverte : l'onglet Système d'exploitation interrogeait OpenRC sur
`crond`, le cron de BusyBox, alors que l'installateur fait tourner `dcron` à sa
place, si bien qu'un Alpine en bonne santé signalait cron arrêté.
`fPickOpenRcCronService` interroge le premier des deux qui a un script de
service.

Et deux que l'installateur contourne plutôt que de les corriger, parce qu'ils
relèvent du paquet haproxy d'Alpine : il ne fournit pas `/etc/haproxy/errors/`,
ni `/run/haproxy` pour la socket d'administration. Les deux lignes sont retirées
de la configuration quand leur fichier ou leur répertoire n'existe pas, ce qui
est également correct sur une machine où un administrateur les a bien créés.
Créer `/run/haproxy` a été essayé en premier, avec un script dans
`/etc/local.d/` pour le recréer à chaque démarrage : `local` s'exécute à la FIN
du démarrage, si bien que haproxy avait déjà échoué à démarrer au moment où le
répertoire apparaissait.

Une autre encore relève d'OpenRC lui-même : il met en cache l'arbre des
dépendances des services et décide s'il doit le reconstruire en comparant des
horodatages avec `/etc/init.d`. Lors d'une réinstallation, les scripts de
service sont réécrits dans la même seconde que le cache, si bien qu'il garde
l'ancien et que les services en restent exclus - ils démarrent pendant
l'installation, parce que `rc-service start` n'a pas besoin de l'arbre, puis ne
reviennent pas après un redémarrage, parce que `openrc default`, lui, en a
besoin. `fInstallServices` se termine par un `rc-update -u` inconditionnel.

### Ce que chaque installateur exige de la machine, et ce qu'il installe lui-même

L'installateur Debian refuse de s'exécuter là où systemd n'est pas le PID 1
(`fRequireSystemd`, appelé avant que quoi que ce soit ne soit installé). Tout
ce qu'il met en place est démarré et maintenu en vie par systemd - les dix
unités, le HAProxy de la machine, cron - si bien que sur une telle machine
l'installation se terminait autrefois, annonçait un succès et ne servait rien :
`systemctl` est installé, il répond « System has not been booted with systemd
as init system (PID 1). Can't operate. », et rien ne lisait ce code de sortie.
Ce qu'il affiche maintenant, c'est comment corriger : installer
`systemd systemd-sysv dbus`, recréer le conteneur avec `/sbin/init` comme
commande, relancer l'installateur. Il dit « recréer » plutôt que « redémarrer »
parce qu'un conteneur en marche ne peut pas changer de PID 1.

L'installateur Alpine prend la décision inverse au sujet d'OpenRC, parce que là
la pièce manquante est une pièce qu'il peut fournir : `openrc` est installé
avec les autres paquets - une image de conteneur est livrée sans lui, un Alpine
installé avec `setup-alpine` l'a - et `fEnsureOpenRcUsable` crée ensuite
`/run/openrc/softlevel`, qui est le fichier que nomme OpenRC lui-même quand il
refuse de toucher à un service sur un système qu'il n'a pas démarré. Les dix
services démarrent ensuite dans un conteneur. Le log indique qu'ils ne
reviendront pas d'eux-mêmes, parce que `/run` est un tmpfs et que le PID 1 n'est
pas OpenRC.

Les deux ne sont pas incohérents : on ne peut pas faire fonctionner systemd
autrement que comme PID 1, alors qu'on le peut avec OpenRC.

### `if ! fMain` désactive `set -e` pour toute l'installation

Les deux installateurs se terminent avec fMain lancé comme processus enfant :

    fMain "$@" &
    vMainPid=$!
    if ! wait "${vMainPid}"; then ...

et non avec `if ! fMain "$@"`, qui est ce qu'on croirait lire et ce qu'ils
avaient autrefois. Une commande dans la condition d'un `if` s'exécute avec
errexit suspendu, et la suspension est héritée par chaque fonction qu'elle
appelle et par chaque fonction que celles-ci appellent - c'est-à-dire toute
l'installation. Mesuré sur une machine sans systemd : huit commandes ont échoué
d'affilée, chacune a affiché son erreur, le script a continué au-delà de toutes
et s'est terminé sur « Installation finished ». Un processus enfant récupère
errexit, parce que la suspension ne survit pas à un fork. bash, dash et BusyBox
ash se comportent tous ainsi, pour les deux moitiés de cette phrase, et ni un
`set -e` à l'intérieur de la fonction ni un sous-shell ne le récupèrent.

Deux conséquences de l'exécution de fMain dans un enfant : `trap fCleanup EXIT`
est aussi installé à l'intérieur de fMain, parce qu'un sous-shell n'hérite pas
du trap EXIT de son parent et que l'arborescence téléchargée sous `/tmp` serait
laissée derrière à chaque exécution ; et le parent efface son propre trap avant
de sortir, pour que la ligne « Exited with code » ne soit pas affichée deux
fois.

`fHasTty` est une correction de la même famille : il ouvre `/dev/tty` et le
referme, plutôt que de tester `[ -r /dev/tty ]`. Le nœud de périphérique est
lisible d'après son mode sur tous les systèmes, si bien que ce test passait sous
`ssh host ./installer` sans pty et que le `read` qui suivait mourait avec
ENXIO - un processus sans terminal de contrôle ne peut pas l'ouvrir du tout.

### Le haproxy.cfg d'origine n'est l'œuvre de personne

`fInstallMachineProxy` remplace `/etc/haproxy/haproxy.cfg` quand il est en mode
`proxied`, et il ne touchera pas à un fichier qu'il n'a pas écrit sans demander
d'abord - le proxy de la machine porte peut-être d'autres sites. Le hic, c'est
que le fichier qu'il trouve sur une machine neuve a été mis là par le paquet
haproxy, que **cet installateur a installé lui-même** une minute plus tôt dans
`fInstallDependencies`.

Traiter cet exemple comme l'œuvre de quelqu'un, c'est ce qui arrêtait net chaque
`--install` ordinaire : pas de `--yes`, pas de terminal pour répondre, et
l'exécution se terminait sur « Destructive operation with no terminal to
confirm on » après avoir déjà construit l'arborescence, le virtualenv et les
certificats. Mesuré sur les quatre machines de test, Debian comme Alpine, en
lançant exactement la ligne que donne le README.

`fMachineProxyIsPristine` interroge le gestionnaire de paquets au lieu de
deviner :

- Debian : le md5 que dpkg a enregistré pour ce conffile
  (`dpkg-query -W -f '${Conffiles}'`) comparé au md5 du fichier lui-même.
- Alpine : le hash qu'apk a enregistré pour ce fichier, lu dans
  `/lib/apk/db/installed` (la ligne `Z:` sous `R:haproxy.cfg`), comparé à
  l'`openssl dgst` du fichier. `Q1` est du sha1 en base64, `Q2` du sha256.

`apk audit --system` ressemble à la réponse d'Alpine et ne l'est pas : mesuré
sur Alpine 3.24, il ne signale **rien** pour un `/etc/haproxy/haproxy.cfg`
modifié. La première version de cette vérification le croyait, et aurait
remplacé le proxy de quelqu'un sans demander - la seule chose que la
confirmation existe pour empêcher. Testé depuis avec le fichier du paquet, avec
une ligne ajoutée, et avec le fichier qu'écrit cet installateur.

D'origine signifie qu'il est remplacé avec une ligne dans le log et sans
question. Modifié signifie l'ancien comportement : laissé tel quel lors d'un
`--update`, confirmé et sauvegardé dans `.before-boa.<timestamp>` lors d'une
installation ou d'une réinstallation.

### Un seul fichier pour le log et le mot de passe

L'installateur écrit `/opt/boa/logs/install.log` et rien d'autre : ce qu'il a
fait et, à la fin, les identifiants qu'il a générés. Il écrivait autrefois deux
fichiers dans /root - `app-web-install.log` et `app-web-credentials.txt` - et
deux fichiers à deux endroits, ce sont deux choses à trouver.
`fMigrateInstallFiles` copie le contenu des anciens dans le nouveau avant de
les supprimer, parce que le mot de passe qu'ils contiennent est peut-être la
seule copie que quiconque possède.

Trois détails font tenir l'ensemble :

- `fLog` crée le répertoire quand il n'existe pas. Le log vit à l'intérieur de
  l'arborescence que l'installateur est en train de construire, donc lors d'une
  première installation il n'existe pas quand la première ligne est écrite, et
  un `--reinstall` le supprime en cours de route.
- `fRemoveInstallation` met le log de côté avant `rm -rf /opt/boa` et le remet
  ensuite, pour qu'une réinstallation n'emporte pas son propre historique.
- Le fichier est en `root:root 0600` dans un répertoire appartenant à `boa`
  en 0750. `boa` peut le supprimer - c'est ce que signifie posséder le
  répertoire - et ne peut pas y lire le mot de passe ; les agents ne sont pas
  dans le groupe `boa` et ne peuvent même pas entrer dans le répertoire.

La page de connexion nomme ce chemin, dans `frontend/templates/login.html`, sur
une ligne à part et colorée avec `--colour-path`. Il ne figure pas dans les
quinze fichiers de traduction : la phrase au-dessus est traduite, le chemin
est le même partout, et un chemin coupé au milieu d'une phrase est un chemin que
quelqu'un recopie mal.

### Logo circulaire de l'application

`frontend/static/img/boa.svg` est un emblème circulaire bleu représentant trois
agents robotiques en buste, en costume noir, chemise blanche et cravate sombre.
Leurs têtes ont des panneaux métalliques clairs, des articulations mécaniques et
des visières sombres aux yeux bleus. Le style est légèrement illustré, avec des
textures de tissu lisses et sans pochette sur l'agent central. Leurs têtes se
rattachent à des cous robotiques visibles ; l'agent central, plus grand, se
tient devant les deux agents latéraux, plus petits. L'illustration ombrée est
un WebP de 512 px intégré dans le SVG, avec un détourage circulaire et de la
transparence hors du cercle. Les personnages restent opaques et gardent la même
apparence d'un thème à l'autre. Il s'agit d'une illustration matricielle dans
un conteneur SVG, pas de tracés vectoriels.
`favicon.svg` contient la même illustration. Gardez les deux fichiers SVG
synchronisés. Les URL de la connexion, de la barre latérale et du favicon
utilisent `v=robot-agents` pour rafraîchir les copies en cache de l'emblème
précédent. Les tailles affichées restent de 30 px sur la page de connexion et
de 24 px dans la barre latérale.

### L'interface parle en-US jusqu'à ce que quelqu'un en décide autrement

`fGetLanguage` lit le choix dans `localStorage` et, s'il n'en trouve aucun,
renvoie `en-US`. Il négociait autrefois d'abord avec `navigator.languages`, ce
qui voulait dire qu'une nouvelle installation parlait la langue du premier
navigateur qui l'ouvrait - la langue d'une machine, pas une décision. Le choix
est à un contrôle de distance, dans le coin du cadre de connexion et dans les
Réglages, et il est mémorisé par navigateur.

Deux bogues vivaient dans le même fichier et se manifestaient tous deux par
« le formulaire de connexion ne change de langue qu'au bout de deux
changements » :

- `fApplyTranslations` n'écrivait une chaîne que lorsque le fichier chargé avait
  cette clé, et `textContent` avait déjà été écrasé par la langue précédente.
  Passer à en-US - qui n'a pas de fichier, `dTranslations` vaut `{}` - ne
  changeait donc rien du tout, et passer à une langue à laquelle manquait une
  clé laissait cette clé dans la langue d'avant. La chaîne d'origine de chaque
  élément traduit est désormais conservée dans une `WeakMap` la première fois
  qu'il est traduit, et une clé sans traduction la restaure.
- `fSetLanguage` enregistrait le choix puis appelait `fLoadTranslations()` sans
  argument, ce qui relisait le choix depuis le stockage. Dans une fenêtre de
  navigation privée, le stockage lève une exception, la lecture renvoie la
  langue précédente, et la page recharge ce qu'elle affichait déjà. Il passe
  maintenant la langue qu'on lui a donnée.

`fLoadTranslations` porte un numéro de séquence, pour que deux changements
rapprochés ne puissent pas arriver dans le désordre et laisser la page dans une
langue que personne n'a demandée. Trois choses y étaient fausses, et chacune
montrait à l'utilisateur une langue qu'il n'avait pas choisie :

- L'attribut `lang` était posé au DÉBUT, avant que le fichier ait été récupéré.
  Un 404 ou une erreur d'analyse laissait alors à l'écran les chaînes de la
  langue précédente sous le nom de la nouvelle : `lang=fr-FR` avec un texte en
  espagnol. Rien n'est publié tant que le dictionnaire n'est pas en main, et
  `fPublish` pose les deux ensemble, parce que l'échec consiste précisément à
  ce que les deux soient posés séparément.
- La séquence était vérifiée AVANT `await response.json()`. Un CORPS lent
  d'une requête antérieure arrivait après qu'une requête ultérieure avait
  fini. Elle est vérifiée après chaque await, parce que la séquence peut bouger
  pendant n'importe lequel d'entre eux.
- Un échec ne disait rien et laissait la page dans un état inconnu. Il se
  rabat désormais sur en-US et le signale par `fOnLoadFailed`.

### en-US.json est la source, et le balisage est le repli

Le chargeur court-circuitait `en-US` vers un dictionnaire vide, au motif que le
balisage porte déjà le texte en-US. C'est vrai, et cela faisait de
`en-US.json` cinq cents clés de poids mort : livrées, listées comme catalogue,
vérifiées par les tests pour leur parité avec les treize autres, et lues par
rien. Y corriger une coquille ne changeait rien à l'écran, et la seule façon de
s'en apercevoir était d'essayer.

Il est maintenant récupéré comme n'importe quelle autre langue. Le texte du
balisage reste le repli qu'il a toujours été censé être : une clé absente du
catalogue, ou un catalogue qui refuse de se charger, laisse toujours une page
lisible plutôt qu'une page de blancs. Ce qui a changé, c'est lequel des deux
est la source.

### Cinq cents clés ne font pas une interface traduite

Quatre sortes de chaînes visibles ne portaient aucune clé, si bien qu'elles
restaient en anglais dans les quatorze langues :

| Quoi | Comment c'est traduit maintenant |
|---|---|
| Le titre de l'onglet | `data-i18n` sur `<title>`, une clé par page |
| Les échecs propres à l'API | Un `code` et ses `params` voyagent ; le navigateur écrit la phrase dans `fDescribeApiError`. `error` reste pour ce qui vient de l'extérieur - les mots d'un fournisseur, le refus d'un serveur de messagerie - pour lesquels il ne faut pas inventer de traduction |
| Les descriptions des modèles | Pas dans les catalogues : l'`agent.json` de chaque modèle porte sa description dans les quinze langues, et le serveur choisit celle que demande l'interface (`agent_package.fPickDescription`) |
| Le schéma et la description des thèmes | `theme.scheme.<scheme>` et `theme.desc.<id>`, même marché. Le NOM n'est pas traduit : un thème est la palette de quelqu'un, avec un nom, et traduire « Nord » n'aiderait personne à le trouver |

Un modèle ou un thème que quelqu'un écrit pour sa propre installation garde ses
propres mots au lieu de disparaître.

Le menu déroulant des langues sur la page de connexion liste des codes -
`es-ES`, `en-US` - et non des noms de langues. Quinze noms dans leur propre
langue rendaient le contrôle aussi large que le cadre ; le code fait 80 px, et
c'est ce que repère le plus vite, dans une liste de codes, quelqu'un qui cherche
sa propre langue. Les noms complets restent sur la page des réglages, qui a la
place.

### De droite à gauche

L'hébreu s'écrit de droite à gauche, et une page mise en page de gauche à
droite qui contient de l'hébreu est une page que personne ne peut lire. Quatre
décisions font que la même feuille de style sert les deux sens :

**Le sens voyage avec la langue.** `fPublish` dans `i18n.js` fixe `dir` sur
`<html>` dans la même étape que `lang`, à partir de `lRightToLeftLanguages`,
de sorte que les deux ne peuvent jamais diverger - l'échec que la fonction
existe pour empêcher pour `lang` seul. Les lignes grid et flex suivent `dir`
d'elles-mêmes, si bien que la barre latérale et tout ce qui est disposé en
ligne se retournent sans règle propre.

**La feuille de style dit début et fin, pas gauche et droite.** Chaque marge,
chaque remplissage, chaque bordure, `inset` et `text-align` qui concerne le
flux du texte est une propriété logique (`margin-inline-start`,
`inset-inline-end`, `text-align: start`). Le seul `left` physique qui reste
dans `app.css` est l'anneau autour de l'avatar d'un agent, qui est de la
géométrie et non du texte.

**Le contenu garde son propre sens.** Le code, les chemins et les commandes
sont de gauche à droite dans toutes les langues
(`code, pre { direction: ltr; unicode-bidi: isolate }`), si bien qu'un chemin
à l'intérieur d'une phrase en hébreu n'est pas réordonné. Un message de chat,
et chaque paragraphe d'une réponse rendue, prennent leur sens de leur propre
première lettre (`unicode-bidi: plaintext`) : une réponse en anglais sur une
page en hébreu se lit de gauche à droite, une réponse en hébreu sur une page en
anglais de droite à gauche. Les zones de texte où l'on écrit du texte libre suivent la même règle, et une zone vide suit la page, si bien que son texte indicatif se lit de droite à gauche en hébreu (`dir="auto"` disposerait une zone vide de gauche à droite, texte indicatif compris) ; le crontab et l'adresse e-mail
portent `dir="ltr"`.

**Ce qui se lit de gauche à droite est isolé à l'intérieur d'une phrase.** L'algorithme bidi attribue un caractère neutre au côté qu'il touche, si bien qu'un chemin à la fin d'une phrase en hébreu perdait sa barre oblique et son point au profit des mots voisins : "/tmp/x/007/." s'affichait ".tmp/x/007/ /". Dans une langue qui s'écrit de droite à gauche, `fPublish` fait passer le dictionnaire par `fIsolateLeftToRightRuns`, qui entoure chaque `{placeholder}` et chaque suite contenant une barre oblique de U+2068 FIRST STRONG ISOLATE ... U+2069 POP DIRECTIONAL ISOLATE, de sorte que la valeur qu'un appelant place dans une phrase tombe à l'intérieur de l'isolat. Ce que la machine rapporte sous Réglages → Système d'exploitation (`fLeftToRight` dans `settings.js`), une route dans la documentation de l'API (`.endpoint-path`), l'exemple de ligne crontab et les compteurs des onglets et des colonnes sont isolés de gauche à droite de la même façon ; sans cela, une version du noyau s'affichait "deb13-amd64 · x86_64+6.12.111".

### La branche depuis laquelle le code est téléchargé

`cRepoBranch` vaut `main`, la vraie branche du dépôt. C'était `master`, qui ne
fonctionnait que parce que GitHub redirige l'ancien nom après un renommage - une
redirection qui disparaît le jour où une vraie branche `master` existe, et que
personne n'effectue pour `--repo-url file:///...`, qui est la façon dont les
deux installateurs sont testés.

### Pourquoi l'application embarque son propre HAProxy

Le HAProxy de la machine transmet vers le port 11443 avec `send-proxy-v2`, si
bien qu'un en-tête PROXY arrive **avant** la négociation TLS. Gunicorn ne peut
pas le lire à cet endroit : son option `proxy_protocol` analyse cet en-tête en
analysant le HTTP, ce qui se produit après la terminaison du TLS, si bien que
les octets de l'en-tête atterrissent dans la négociation et la cassent avec
`WRONG_VERSION_NUMBER`. Cela a été découvert en déployant, pas en testant.

HAProxy accepte les deux sur un même bind - `accept-proxy ssl crt ...` - donc
l'application apporte sa propre instance, qui est aussi le seul composant à
écouter sur un port. Gunicorn se lie à une socket Unix à la place, ce qui veut
dire qu'il n'existe aucune entrée dans l'application qui ne passe pas par le
proxy, et l'adresse réelle du client survit sous forme de `X-Forwarded-For` -
sans elle, la limitation du rythme des connexions verrait 127.0.0.1 pour tout
le monde et cesserait d'être par adresse.

C'est HAProxy plutôt que nginx parce que le déploiement dépend déjà de
HAProxy : pas de nouvelle technologie pour un problème qu'une technologie
existante résout.

Le HAProxy de la machine ne doit pas utiliser `option ssl-hello-chk` sur ce
backend : le ClientHello de cette vérification est antérieur à TLS 1.2, il
échoue donc contre un bind qui l'exige et marque le backend comme hors service
pour toujours. Le symptôme est un 503 venant d'un service qui tourne
parfaitement, ce qu'il vaut la peine de savoir parce que rien dans les logs de
l'application elle-même ne dit que quelque chose ne va pas.

Et la vérification doit frapper à 11080, pas à 11443. Une vérification TCP
contre le bind TLS se connecte et raccroche sans négociation, et ce HAProxy
consignait chacune comme « SSL handshake failure » - mesuré sur la machine de
test Debian, 64 075 lignes en deux jours, une toutes les deux secondes, qui
enfouissaient tout ce qui était réel dans le journal. `check-ssl verify none` a
été essayé en premier et a échangé une ligne contre une autre : la fermeture
brutale de la vérification arrivait pendant que la négociation était encore en
train de se terminer, et chaque vérification consignait soit cela, soit
`ECONNRESET`. Contre 11080, la même connexion suivie d'une fermeture est une
session nulle que `option dontlognull` garde hors du log, les deux ports
appartiennent à un seul processus, et le journal s'est tu : zéro ligne en
trente secondes, avec le site répondant 200 depuis l'extérieur.

Le backend sur le HAProxy de la machine est donc, en entier :

```
backend https-out
  mode tcp
  server srv-https-out 127.0.0.1:11443 check port 11080 send-proxy
```

`send-proxy` est ce qui porte l'adresse du client. `check-send-proxy` est
laissé de côté exprès : 11080 n'accepte pas le protocole PROXY. La version de
ceci destinée à l'opérateur se trouve dans MANUAL.fr-FR.md, sous « À quoi doit
ressembler le HAProxy de la machine ».

Il ne fixe aucun `maxconn`, et ce n'est pas un oubli. `maxconn 2048` demande au
noyau 4131 descripteurs de fichiers et HAProxy sort plutôt que de démarrer sans
eux : *Cannot raise FD limit to 4131, current limit is 1024 and hard limit is
4096*. Signalé depuis un LXC Alpine tournant sous OpenWrt sur un BPI-R3, dont
la limite dure est 4096 : `boa-proxy` a été relancé soixante-dix fois, rien
n'a jamais écouté sur 11443, et une première installation s'est terminée sur
« The application did not answer on port 11443 (last code: 000) ». Les deux
machines de test sont des LXC Proxmox avec une limite dure de 524 288, c'est
pourquoi aucune ne l'a jamais montré, et `haproxy -c` acceptait le fichier sur
chacune d'elles - la configuration n'a jamais été invalide, c'est le processus
qui mourait au démarrage. Sans `maxconn`, HAProxy se dimensionne d'après les
descripteurs qu'il peut réellement avoir, ce qui est précisément ce que demande
son propre message, et `fd-hard-limit 4000` plafonne ce qu'il prend là où la
limite est énorme. Mesuré avec un même binaire sous trois limites dures : 4096
donne un maxconn de 1987, 1024 donne 499, 524 288 donne 1987. Un test démarre le
vrai haproxy sur le fichier livré sous une limite dure de 4096 et exige qu'il
reste en marche, puis le redémarre avec l'ancien `maxconn 2048` et exige qu'il
meure - un test qui se contentait de lire le fichier, c'est justement ce qui
avait laissé passer cela.

Trois choses ont réellement besoin de root : créer un utilisateur système,
installer le crontab d'un autre utilisateur, et lancer un processus en tant
qu'un autre utilisateur. Rien d'autre n'en a besoin. Root vit donc dans un petit
démon doté d'un **vocabulaire fermé de verbes** sur une socket Unix, et il n'y a
délibérément aucun verbe signifiant « exécute cette commande ». Un attaquant qui
atteint cette socket peut créer un agent non privilégié ; il ne peut pas
exécuter de code en tant que root.

La socket est en `0660 root:boa`, et `SO_PEERCRED` est vérifié à chaque
connexion pour que seuls root et `boa` soient servis, quel que soit le mode du
fichier après une future mise à jour.

### Un changement doit venir des propres pages de ce site

Le cookie de session est `SameSite=Lax`, ce qui empêche une requête venue d'un
autre site de le porter. Cela n'écarte pas une autre ORIGINE du même site : un
agent doté de `bash.run` peut servir une page sur cet hôte même, sur un port à
lui, et un lien vers elle dans une réponse de conversation n'est qu'à un clic.
Un formulaire de cette page qui poste vers `/api/admin/agents/000/run` est une
requête du même site, le cookie voyage, et l'exécution démarre ; étant un
simple POST sans corps, aucune requête preflight ne lui barre la route non
plus. `fRefuseChangesFromElsewhere`, un `before_request` sur le blueprint de
l'API, répond donc 403 à tout POST, PUT, PATCH ou DELETE qui ne vient pas des
propres pages de ce site : un en-tête `Origin` doit nommer exactement cet hôte
et ce port - `localhost` et `localhost:8080` sont deux origines, et la seconde
est exactement la page qu'un agent pourrait servir - et un en-tête
`Sec-Fetch-Site` doit dire `same-origin`. Une requête qui n'a ni l'un ni l'autre
ne vient pas d'un navigateur ; c'est un script ou les tests, et elle est
laissée au jugement de la connexion, comme avant. Un GET n'est pas filtré : il
ne change rien, et une page venue d'ailleurs ne peut pas lire la réponse, parce
qu'aucun en-tête CORS ne le lui permet.

### L'API des agents, et la raison même de son existence

Deux choses appartiennent à `boa` et ne doivent pas être lisibles par les
agents : la base de données du kanban (un agent qui pourrait y écrire
directement pourrait réécrire l'historique d'un autre agent) et les
identifiants des canaux (un jeton de bot n'est pas un message — c'est une
autorité permanente pour envoyer).

Les agents atteignent donc les deux par `boa-agent-api`, sur une seconde socket
Unix que chaque agent peut ouvrir. L'autorisation repose sur deux vérifications
indépendantes :

1. Le jeton présenté correspond au SHA-256 enregistré du jeton d'un agent.
2. `SO_PEERCRED` indique que le processus appelant appartient à l'utilisateur
   de *cet* agent.

Chacune seule serait plus faible : un jeton divulgué est inutile depuis le
mauvais compte, et être le bon compte est inutile sans le jeton.

C'est une socket Unix plutôt que HTTPS parce qu'il n'y a rien à gagner au TLS
entre deux processus sur une même machine, et qu'un certificat autosigné
voudrait dire que chaque agent tourne avec la vérification désactivée — ce qui
est pire que pas de TLS du tout, parce que cela ressemble à de la sécurité.

### Où vit l'état, et pourquoi il est réparti

| État | Où | Pourquoi là |
|---|---|---|
| Configuration de l'agent | `agents/xxx/info.json` | L'agent doit la lire en tant que lui-même |
| Historique de l'agent | `agents/xxx/runs.jsonl` | Le seul endroit où un agent peut écrire |
| Procédures partagées | `skills/<Name>/SKILL.md` (root, 0755) | Lues par chaque agent qui les a reçues, écrites par aucun |
| Index des agents, connexion, réglages | `db/boa.sqlite` (0700 `boa`) | Le processus web en a besoin |
| Le tableau | `kanban/kanban.sqlite` (0700 `boa`) | De nombreux écrivains simultanés |

Il n'y a délibérément **aucune table `runs` ni `usage`**. Un processus d'agent
ne peut pas ouvrir la base de données appartenant à `boa`, et lui accorder
l'accès en écriture permettrait à n'importe quel agent de réécrire l'historique
de n'importe quel autre. Chaque agent ajoute plutôt à son propre journal, et
l'application web lit ces journaux par l'intermédiaire de `boa-exec`. L'avantage
secondaire est qu'un agent consigne encore ce qu'il a fait quand l'application
web est arrêtée.

Le tableau est en SQLite et non un répertoire de fichiers JSON parce que
plusieurs agents qui se réveillent à la même minute de cron, c'est le cas
normal, et que seule une transaction empêche deux ajouts simultanés de
s'écraser l'un l'autre.

### Ce que contient une sauvegarde

`--backup` écrit une archive unique de tout ce qu'est l'installation et que le
code n'est pas, et `--restore` en met une à la place de ce qu'a une machine ;
les deux se trouvent dans les deux installateurs, fonction pour fonction. La
liste est le tableau ci-dessus transformé en ligne de `tar` : les deux bases de
données, les clés et les canaux, les certificats, chaque agent avec son
répertoire personnel et ses fichiers protégés, les compétences et les outils.
Autour d'elle, trois choses qu'un `tar` de `/opt/boa` ferait mal :

- **Les bases de données passent par l'API de sauvegarde de SQLite**,
  `fCopySqliteDatabase`, et non par `cp`. Les deux tournent en mode WAL, donc
  une copie du fichier `.sqlite` manque tout ce qui se trouve encore dans le
  fichier `-wal`, et une copie prise en pleine écriture peut être déchirée. Le
  `python3` du venv a le module ; la commande `sqlite3` n'existe sur aucune des
  deux distributions. La même raison joue en sens inverse à la restauration :
  les anciens fichiers `-wal` et `-shm` sont supprimés avant que le fichier
  restauré ne soit lu, sinon SQLite lui appliquerait l'ancien journal.
- **Les utilisateurs des agents voyagent par leur nom.** `agents.txt`
  enregistre l'utilisateur, l'uid et le gid de chaque agent, et
  `fRestoreAgentUsers` crée ceux qui manquent, toujours avec le même nom et
  avec les mêmes identifiants quand ils sont libres. La propriété dans
  l'archive est associée par nom à l'extraction, si bien qu'un `boa` ou un
  `agent-001` ayant un autre uid sur la nouvelle machine possède toujours ses
  fichiers. Les crontabs vivent dans le spool de cron, pas sous `/opt/boa`,
  donc ils sont lus avec `crontab -l` et remis en place avec `crontab -u`.
- **Trois fichiers sont laissés de côté exprès** : `config/ports.conf`,
  `config/browser.conf` et le `haproxy.cfg` généré à partir d'eux décrivent
  CETTE machine, et une restauration ne doit pas importer les choix d'une autre
  machine. Le log d'installation voyage sous le nom `install.log.backup`, un
  autre nom pour qu'une restauration n'écrase jamais le log en cours
  d'écriture à ce moment-là ; ses lignes d'identifiants sont ajoutées au log
  actuel, parce que la connexion après une restauration est celle de la
  sauvegarde.

La restauration est la seule action qui remplace des données et ne peut pas
être annulée, elle demande donc confirmation comme le fait une
réinstallation. Les deux fonctions sont exécutées par les tests sur une vraie
arborescence, sous bash et sous dash : on vérifie ce que l'archive contient et
ce qu'elle laisse de côté, l'arborescence est abîmée de toutes les façons
qu'une restauration doit défaire, et la restauration est vérifiée fichier par
fichier.

### Une compétence est indexée dans le prompt et récupérée à la demande

La mémoire d'un agent est chargée en entier dans chaque prompt système, et
c'est ce qui convient à une mémoire : sa limite de caractères est configurable
par agent (8 000 par défaut, de 1 000 à 1 000 000 autorisés) et c'est la seule
chose que l'agent ne peut pas retrouver par lui-même.

Les compétences ne sont pas ainsi. Une procédure fait une page ou deux, un agent
peut en recevoir plusieurs, et la plupart des exécutions n'en ont besoin
d'aucune - la vérification du disque n'a pas besoin de la procédure des
certificats. Les charger comme la mémoire est chargée voudrait dire les payer
toutes à chaque appel de chaque exécution, et les plafonds de `info.json` se
mesurent en jetons.

Le prompt porte donc un index - une ligne par compétence, son nom et sa
description - et le corps est récupéré avec `skill.read`, une fois, par un
agent qui a décidé qu'il en avait besoin. Cinq compétences coûtent environ
200 jetons par exécution au lieu de 10 000, et celle qui est lue est facturée
une fois plutôt qu'à chaque appel.

La description de l'en-tête est donc la partie porteuse : c'est sur elle que
l'agent décide, et c'est ce que paie chaque exécution, que la compétence soit
lue ou non.

### Les compétences appartiennent à root, comme les outils

Un outil appartient à root parce que l'application l'importe comme du code. Une
compétence n'est exécutée par rien, mais elle est placée en tête du
raisonnement d'un agent qui se réveille à quatre heures du matin sans personne
pour le surveiller, ce qui la rend exactement aussi sensible que
`system-prompt.md` - et ce fichier vit déjà dans un répertoire que l'agent peut
lire et ne peut pas écrire.

Il n'y a donc pas d'éditeur de compétences dans l'interface web, ni de verbe
privilégié pour en écrire une. Les compétences s'écrivent sur le serveur par
SSH. L'interface décide quel agent reçoit lesquelles, ce qui est la même chose
qu'elle fait pour les outils.

L'autre moitié de cette décision, c'est l'endroit où elles vivent :
`/opt/boa/skills/`, en dehors de `webapp/`, parce que `fDeploySourceCode` fait
un `rm -rf` sur `webapp` et qu'une procédure que quelqu'un a écrite sur ce
serveur n'est pas quelque chose qu'une mise à jour a le droit de supprimer. Même
raisonnement, même place dans l'arborescence, que `/opt/boa/tools/`.

L'application n'en livre aucune. Il n'y a pas de `backend/skills/` et les
installateurs ne copient rien dans ce répertoire : ils le créent vide,
appartenant à root, en 0755. Une compétence est une procédure pour UNE
installation - ces hôtes, cette sauvegarde, ce certificat - donc une compétence
générique serait une procédure que personne ne suit, occupant une ligne de
chaque prompt de chaque exécution pour le dire. Que le répertoire soit vide sur
une installation neuve, c'est la fonctionnalité qui marche, pas une pièce qui
manque.


### `deploy/` n'est pas déployé

`/opt/boa/webapp/` contient `backend/` et `frontend/` et rien d'autre. Le
répertoire `deploy/` - les unités, les deux configurations HAProxy, les modèles
d'agents, les catalogues de fournisseurs, `requirements.txt` et l'installateur
lui-même - est le matériel propre de l'installateur, et il est lu depuis
l'arborescence que l'installateur vient de télécharger dans `/tmp`, qui est
jetée quand il se termine.

Ce n'est pas qu'une question d'ordre. Lire les unités depuis une copie sous
`/opt/boa` voulait dire installer les unités de la version qui se trouvait sur
le disque, quelle qu'elle soit ; les lire depuis l'arborescence téléchargée
installe les unités de la version en cours de déploiement, qui est la seule
paire sur laquelle on puisse raisonner. Chacune de ces lectures appelle
d'abord `fRequireSourceCode`, si bien qu'une étape qui s'exécuterait un jour
avant le téléchargement échoue avec une phrase au lieu de copier depuis
`/deploy/...`.

C'est aussi pourquoi `gunicorn.conf.py` se trouve dans `backend/web/` plutôt
que dans `deploy/` : gunicorn le lit à chaque démarrage, il doit donc être un
fichier réellement présent sur le serveur, et le répertoire présent sur le
serveur est celui qui contient le code qu'il configure.

Ce qui est déployé est en `root:root`, répertoires en `00755` et fichiers en
`0644`, fixés par `fSetCodeModes` et par rien d'autre. Rien sous `webapp/` n'est
exécuté par son chemin - le démon lance le runner sous la forme
`venv/bin/python3 .../runner.py`, et le crontab qu'il écrit pour chaque agent
fait de même - donc aucun fichier à cet endroit n'a besoin du bit
d'exécution. Il l'avait pourtant jusqu'à ce que ce soit une seule fonction :
`fDeploySourceCode` fixait `0644`, puis `fCreateDirectoryTree`, qui s'exécute
après lui lors d'une mise à jour, faisait `chmod -R 00755` sur la même
arborescence.

### Telegram reçoit du HTML, et se rabat sur les mots

Un modèle écrit du markdown. Affiché brut, cela donne `**25G free**` avec les
astérisques au milieu de la phrase, ce qui est arrivé sur les téléphones
jusqu'à ceci.

Telegram affiche un petit sous-ensemble de HTML - quatorze balises, pas
d'attributs dignes de ce nom, et aucun titre, liste ni tableau parmi elles.
`telegram_html` traduit donc ce pour quoi il existe une balise et trouve une
forme lisible pour le reste : les titres deviennent du gras sur leur propre
ligne, les éléments de liste reçoivent une puce, et un tableau devient un bloc
`<pre>` complété d'espaces, qui est la seule façon de garder les colonnes
alignées les unes sous les autres sur un téléphone.

Trois choses y sont porteuses.

**L'échappement vient en premier.** `&`, `<` et `>` sont du balisage pour
Telegram, si bien qu'un agent qui rapporte `grep <dev> && echo` produit un
message auquel Telegram répond par un 400 - c'est-à-dire un message qui
n'arrive jamais. Chaque morceau de texte passe par `fEscape` avant que quoi que
ce soit ne l'enveloppe. Un href passe par `fEscapeAttribute`, qui échappe aussi
le guillemet double : une URL qui en contiendrait un fermerait l'attribut et
transformerait le reste d'elle-même en attributs que personne n'a écrits.

**Un message rejeté est renvoyé en texte brut.** Quoi que le moteur de rendu ait
raté, les mots valent plus que la mise en forme, donc un 400 est retenté sans
`parse_mode` et la ligne part sans mise en forme. Le repli consigne ce qu'a dit
Telegram, parce qu'une mise en forme qui se dégrade en silence pour toujours est
une mise en forme que personne ne corrige.

**Une réponse que Telegram rejette est abandonnée, et une qu'il ne peut pas
prendre est gardée une heure.** `fSay` renvoie trois choses et non deux :
envoyé, sans réponse, et rejeté - un 4xx autre que 429, `ChannelRejected`, qui
est Telegram disant non à ce message et le pensant encore demain : le bot
bloqué, la conversation disparue, le jeton révoqué. `fDeliverAnswers` gardait
autrefois la ligne à chaque échec et réessayait au passage suivant, et la ligne
est sur le disque pour qu'un redémarrage ne perde pas une réponse, si bien
qu'un bot bloqué transformait l'écouteur en boucle sans fin : l'interrogation
en mode rapide, une lecture de la conversation par le démon root et jusqu'à
deux requêtes à Telegram à chaque passage, à travers tous les redémarrages.
Une réponse rejetée est abandonnée tout de suite avec une ligne qui le dit, et
une réponse que Telegram n'a pas prise dans l'heure accordée à une exécution
est abandonnée aussi, pour la même raison que l'autre branche renonce à une
exécution qui n'a jamais fini. Aucune des deux ne perd la réponse : elle se
trouve dans la conversation de l'agent dans l'interface web, où elle a été
écrite en premier.

Les motifs sont les mêmes que ceux qu'utilise
`frontend/static/js/markdown.js`. Deux moteurs de rendu en désaccord sur ce qui
compte comme du markdown voudraient dire qu'une même réponse se lit
différemment aux deux endroits où elle est affichée, et tout l'intérêt
d'envoyer les deux est qu'il s'agit de la même conversation.


### Discord est interrogé, et une réponse fait deux mille caractères

Discord est le second canal par lequel une personne peut répondre à un agent,
et la moitié qui reçoit est `discord_listener` - `boa-channel-discord`, le
septième service. Quatre choses le distinguent de celui de Telegram.

**Il interroge, en REST.** `GET /channels/<id>/messages?after=<id>`, toutes les
cinq secondes, et toutes les deux pendant qu'un agent est en train de répondre.
La Gateway est l'alternative évidente et n'a pas été retenue : c'est un
WebSocket qui exige des heartbeats, un protocole de reprise et une dépendance
que ce projet n'a pas, et elle exige que le Message Content Intent soit activé
dans le portail des développeurs - faute de quoi chaque message arrive avec un
`content` vide et rien ne dit pourquoi. L'interrogation se connecte aussi vers
l'extérieur, ce qui permet à ceci de tourner sur un LAN sans rien de redirigé,
exactement comme le long poll de Telegram. Ce que cela coûte, c'est une latence
qui se mesure en secondes, et douze requêtes par minute face à une limite de
cinquante par seconde.

**Deux mille caractères, pas quatre mille.** `channels.cMaxMessageLength` vaut
4096, qui est le plafond de Telegram, et Discord répond 400 à un `content` de
plus de 2000. Une longue réponse n'arrivait pas raccourcie - elle n'arrivait
pas. `discord_markdown` la coupe entre des lignes en quatre messages au plus,
et un bloc délimité dans lequel tombe une coupure est fermé à la fin de l'un et
rouvert au début du suivant : sans cela, une moitié arrive en texte brut et
l'autre comme un bloc qui ne finit jamais, ce qui, dans Discord, avale tout ce
qui est dit ensuite. Chaque partie est enregistrée comme appartenant à cet
agent, parce qu'une personne répond à celle qui se trouve sur son écran.

**Pas de boutons, et `!` pour les commandes.** Un appui sur un bouton et une
commande slash sont tous deux des *interactions*, et une interaction arrive par
la Gateway ou par un point d'entrée HTTPS que Discord peut atteindre. Un canal
interrogé ne voit ni l'un ni l'autre. `/agents` est donc `!agents`, un message
ordinaire, et la liste est une liste de noms à taper plutôt qu'une colonne de
boutons. `/agents` est accepté aussi, parce que quiconque a configuré le bot
Telegram le tapera par habitude.

**La réponse d'un agent ne mentionne personne.** Chaque message envoyé par
ceci porte `allowed_mentions: {"parse": []}`, si bien qu'un `@everyone` écrit
par un modèle est du texte et non une notification à tout un serveur.
`replied_user` reste activé : une réponse doit atteindre la personne qui a
posé la question. Une règle au niveau de la socket plutôt que dans un prompt,
pour la même raison que la liste de transfert du courrier en est une.

Ce que Discord n'a pas, c'est le silence de Telegram envers les inconnus. Il
n'y a pas de `chat_id` auquel comparer : le bot demande un canal et lit ce
canal, donc ceux qui peuvent parler aux agents sont ceux qui peuvent y écrire.
Un canal privé est la configuration qui correspond à ce que
`fIsFromTheConfiguredChat` impose dans le code - et c'est indiqué dans le
manuel, parce que c'est là toute l'autorisation.

Le webhook qu'avait ce canal auparavant est toujours là et envoie toujours. Un
webhook ne peut pas lire, ne peut pas répondre et ne reçoit en retour aucun
identifiant de message, donc `listen` sur un webhook est refusé plutôt que
proposé : un interrupteur qui ne fait rien est pire que pas d'interrupteur.

### Un routage, deux écouteurs

`agent_routing` contient ce que les deux écouteurs font de façon identique :
quels agents existent, lire un nom dans `@News Miner`, `/news_miner` ou `@002`
où la correspondance la plus longue l'emporte, ce qu'un agent a dit pour clore
un tour, et le rapport d'état. Le protocole reste dans chacun d'eux - un long
poll n'est pas une interrogation REST, un clavier inline n'est pas une liste de
noms, et une réponse est `reply_to_message` dans l'un et `message_reference`
dans l'autre.

Il a été écrit en même temps que le second écouteur, et le rapport d'état en
est la raison. Deux copies de cette réponse feraient deux réponses à « est-ce
que ça tourne », et la première chose sur laquelle elles divergeraient serait le
nombre de services.

L'envoi n'y est pas. Il reste dans chaque écouteur sous la forme de `fSay`, ce
qui permet à un test de remplacer celui d'un écouteur et de laisser l'autre
tranquille.

### Un navigateur, partagé ; un profil, non

`web.fetch` lit une page publique et s'arrête là : pas de session, pas de
formulaire, pas de bouton. Le navigateur est l'autre chose, et il se divise en
deux :

| | Où | À qui il appartient |
|---|---|---|
| Le navigateur | `/opt/boa/playwright/` | root, 0755, une seule copie |
| Le profil | `agents/xxx/browser/profile/` | l'agent, 0700, un chacun |

Le binaire est partagé parce que c'est un binaire et qu'il n'y a rien à isoler
à son sujet ; une copie par agent ferait 600 Mo chacune et une mise à jour à
faire N fois. Le profil n'est pas partagé, parce qu'il contient les cookies :
l'agent 007 qui se connecte à quelque chose ne doit pas laisser l'agent 008
connecté. Cette séparation est celle du noyau, le même répertoire personnel en
0700 où vit tout le reste d'un agent - ce qui est précisément ce qu'un produit
d'agents hébergé ne peut pas offrir quand tous ses agents partagent une seule
machine et un seul ensemble de sessions.

Trois décisions en découlent :

**Le navigateur reste ouvert d'un appel d'outil à l'autre au sein d'une
exécution.** `browser.click` agit sur ce que `browser.open` a laissé à l'écran,
et une exécution est un seul processus du premier appel d'outil au dernier,
donc une poignée au niveau du module est tout l'état nécessaire. `atexit` le
ferme ; sans cela, un agent horaire laisse un Chromium derrière lui à chaque
exécution et remplit la machine d'ici le matin.

**Playwright est importé à l'intérieur des fonctions, jamais au niveau du
module.** Les outils de navigateur sont listés dans l'interface qu'un
navigateur ait été installé ou non, et une ImportError en tête de fichier les
ferait disparaître de cette liste sans aucune explication nulle part. Importé
tardivement, un navigateur manquant devient une phrase disant quelle commande
lancer.

**Headless, et adresses publiques seulement.** Ce qu'on veut, c'est la session
et le DOM, pas l'image d'une fenêtre, donc un affichage virtuel serait une pièce
mobile pour rien.

« Adresses publiques seulement » est imposé par un gestionnaire de routes
installé sur le CONTEXTE (`browser.fInstallNetworkPolicy`), et non par chaque
outil. Vérifier l'URL dans `browser.open` couvrait exactement une adresse par
exécution : une page est libre de rediriger, et une page qu'on a dit à un agent
de lire est libre de contenir un lien, une iframe, une image ou un formulaire
pointant vers `127.0.0.1` - et `browser.click` n'avait aucune vérification du
tout. Sur le contexte, cela couvre les navigations, les redirections, les clics,
les soumissions et chaque sous-ressource, et le sixième outil de navigateur que
quelqu'un écrira en bénéficiera sans savoir que cela existe. Ce qui est refusé
est nommé dans la réponse de l'outil, parce qu'une requête bloquée est sinon
invisible : la page s'affiche sans elle et l'agent dépense son budget à
réessayer.

Les noms d'hôte sont résolus une fois par exécution et mémorisés, ce qui borne
plutôt que supprime la fenêtre pendant laquelle un nom pourrait se résoudre en
adresse publique pour la vérification et en adresse privée pour la connexion.
Fermer cette fenêtre exige que la connexion soit épinglée à l'adresse
vérifiée, ce que Chromium n'expose pas depuis ici.

Un cookie de session disparaît toujours à la fermeture du navigateur, ici comme
dans tous les navigateurs. Ce qui survit, c'est ce que le site a marqué pour
survivre.

### Ce qu'accepte un fournisseur n'est pas ce que dit la norme

Deux adaptateurs envoyaient quelque chose que leur fournisseur refuse, et dans
les deux cas le résultat était le même : chaque appel d'outil passant par ce
fournisseur échouait, sur chaque modèle, et rien dans la suite de tests ne s'en
apercevait parce que la suite testait les pièces plutôt que l'aller-retour.

| Fournisseur | Ce qui était envoyé | Ce qui revenait |
|---|---|---|
| Ollama | `kanban__list_cards` décodé en rien du tout | Le registre refusait un outil qui n'avait pas été accordé à l'agent - le nom qu'on venait de lui proposer |
| Google | `"additionalProperties": false`, qui est du JSON Schema correct | `400 - Unknown name "additionalProperties" at 'tools[0].function_declarations[0].parameters'` |

Le `function_declarations[].parameters` de Gemini est un SOUS-ENSEMBLE de JSON
Schema et refuse ce qu'il ne connaît pas au lieu de l'ignorer, si bien que
`fCleanSchemaForGoogle` filtre le schéma à travers une liste blanche, de façon
récursive. Une liste blanche et non une liste noire, pour la raison qui fait de
chaque liste blanche ici une liste blanche : la prochaine clé que quelqu'un
ajoutera à un schéma d'outil serait sinon refusée par Gemini, que quelqu'un ait
pensé ou non à l'ajouter à une liste de choses à retirer.

Les deux ont été trouvés en exécutant le cycle complet - demander, appeler un
outil, répondre à cet appel - contre les vraies API avec de vraies clés.
`_/temp/probe-defaults.py` est cette vérification, et c'est la seule chose qui
trouve cette classe de bogue : un schéma valide, un nom correct, et un
fournisseur qui refuse de le prendre.

### Un fichier d'adaptateur par fournisseur

Vingt-cinq fournisseurs, vingt-cinq fichiers, même si la plupart parlent le
même dialecte. Un unique adaptateur « compatible OpenAI » a l'air propre jusqu'à
ce que l'un de ces fournisseurs change un nom de champ, et alors la correction
doit être faite sans casser les vingt autres. Chaque fichier porte les
particularités de son propre fournisseur : DeepSeek abandonne
`reasoning_content` avant que le runner puisse le rejouer, llama.cpp détecte un
modèle de chat sans prise en charge des outils, vLLM transforme un 404 en liste
des modèles qu'il sert bien, Cloudflare construit son adresse à partir de
l'identifiant.

Ce qu'ils partagent, c'est `base.py` : une forme de message neutre calquée sur
chat/completions, parce que la plupart la parlent déjà, et l'adaptateur
Anthropic la traduit en blocs de contenu.

Ils partagent aussi `openai_dialect.py`, et la différence entre cela et un
adaptateur partagé est tout l'enjeu. Le module de dialecte contient la requête
elle-même - le POST, les erreurs HTTP qui méritent d'être nommées, l'analyse de
la réponse - qui n'est la particularité d'aucun fournisseur. Les particularités
restent dans chaque fichier, déclarées comme des attributs de classe que le
module lit :

| Attribut | Ce qu'il décide |
|---|---|
| `cDisplayName` | Le nom dans chaque message d'erreur. « zai request failed » n'est pas ce que quiconque chercherait |
| `cMaxTokensField` | `max_tokens` ou `max_completion_tokens`, selon l'orthographe qu'a suivie le fournisseur |
| `cToolChoiceMode` | `auto`, `any`, ou `omit` pour les fournisseurs qui refusent le champ. `auto` est ce dont un agent a besoin : un modèle forcé d'appeler un outil à chaque tour ne termine jamais une exécution |
| `cChatCompletionsPath` | Le chemin après l'URL de base, pour les quelques-uns qui n'utilisent pas l'habituel |
| `cAssistantContentWhenEmpty` | Ce qu'il faut envoyer à la place d'un `content` nul, pour un fournisseur dont le schéma refuse null |

### Ce qu'ont changé vingt-deux vraies clés

Chaque fournisseur ici a été appelé avec une vraie clé, s'est vu poser une
question, donner un outil, puis remettre la réponse à l'appel d'outil qu'il
avait fait. Les vingt-deux qui ont une clé bouclent cet aller-retour. Sept
choses ne sont apparues qu'à la seconde étape - celle qu'un test avec une
réponse préfabriquée n'atteint jamais - et chacune est maintenant une ligne de
code avec les propres mots du fournisseur à côté :

- **Perplexity avait retiré le point d'entrée.** `chat/completions` répond 403
  « Sonar is now the Agent API. Use /v1/responses instead of /v1/sonar », donc
  cet adaptateur a été réécrit sur l'API Responses, et le fournisseur est passé
  du statut d'un modèle à celui d'un routeur vers 48 modèles.

- **Une clé dans un message d'erreur.** Gemini était appelé avec `?key=...`, si
  bien qu'un 503 de sa part plaçait la clé entière dans l'erreur que lit
  l'utilisateur et que garde le journal. La clé est passée dans l'en-tête
  `x-goog-api-key`, et `base.fRedactCredentials` efface désormais `key=`,
  `api_key=`, `access_token=` et `token=` de chaque erreur que produit
  n'importe quel adaptateur, parce que ce mode d'échec ne devrait pas dépendre
  de la mémoire d'un seul adaptateur.
- **Gemini 3 veut qu'on lui rende sa signature de pensée.** Une conversation
  dont les appels de fonction reviennent sans la signature qu'il a émise est
  refusée d'emblée, si bien que chaque agent Gemini échouait dès qu'il avait
  utilisé un outil. `ToolCall.dProviderData` la transporte à l'aller et au
  retour, opaque pour tout le reste.
- **Cloudflare refuse un `content` nul.** C'est exactement ce que contient un
  message d'assistant quand le modèle a répondu par des appels d'outils et sans
  aucun mot. Il reçoit `""` ; le dialecte continue d'envoyer null à tous les
  autres, parce que null est ce que spécifie le dialecte.
- **Le raisonnement écrit dans la réponse.** MiniMax répond avec
  `<think>...</think>` dans le texte lui-même. Retiré dans le module de dialecte
  et non dans un adaptateur, parce que c'est le modèle qui le fait, et que le
  même modèle derrière une passerelle le fait aussi - et seulement quand la
  réponse COMMENCE par la balise, pour qu'un modèle qui écrit sur le HTML garde
  ses mots.
- **Together laisse le nom du canal devant.** gpt-oss écrit dans des canaux et
  Together renvoie « finalThe weather in Madrid » ; Groq et Cerebras, qui
  servent le même modèle, non. Retiré dans `together.py`, là où doit se trouver
  une particularité d'un seul fournisseur.
- **Quatre modèles par défaut que le fournisseur refusait de servir.** Le 20b
  de Fireworks exige son propre déploiement, celui de Together n'est pas
  serverless, Moonshot a retiré kimi-k2.5, et gemini-3.7-flash répond 503
  « experiencing high demand ». Un modèle par défaut qui échoue à la première
  exécution est pire qu'un modèle en retard d'une version.

Cinq adaptateurs ne l'utilisent pas du tout, parce que leur API n'est pas
celle-là : les blocs de contenu d'Anthropic, le `generateContent` de Google, le
`/completion` de llama.cpp, le chat v2 de Cohere - qui prend les mêmes messages
mais répond avec du texte en blocs, une raison de fin en majuscules qui lui est
propre, et des comptes de jetons imbriqués sous `usage.tokens` - et Perplexity,
qui a entièrement retiré chat/completions et y répond par

    403 Sonar is now the Agent API. Use /v1/responses instead of /v1/sonar

si bien que cet adaptateur parle l'API Responses : une liste `input` au lieu de
`messages`, le prompt système sous forme d'`instructions`, et une réponse qui
arrive sous forme d'éléments de sortie - un `message` avec son texte en blocs,
ou un `function_call` - plutôt que sous forme de choix. Un résultat d'outil
repart comme un élément à part entière, `function_call_output`, apparié par
`call_id`.

Deux noms sont résolus avant que quoi que ce soit d'autre ne les voie, par
`factory.dProviderAliases` : `gemini` est le nom que la documentation de Google
donne à l'API et `google` est ce que dit l'`info.json` de chaque agent depuis la
première version, donc les deux atteignent le même adaptateur et un seul des
deux est jamais enregistré.

Lequel des vingt-cinq peut être attribué à un agent se décide dans
`fListProviders`, pas dans le navigateur : un fournisseur est `selectable`
quand il est auto-hébergé ou que sa clé est enregistrée. C'est un filtre sur ce
qui vaut la peine d'être proposé, pas une règle - une clé peut aussi vivre dans
le propre répertoire personnel de l'agent, où l'application web ne peut pas
regarder, si bien que l'interface montre toujours à un agent le fournisseur
auquel il est déjà associé.

Ce même indicateur décide d'une chose dans l'interface : la case **URL de
base**, pour le modèle principal comme pour le modèle de secours, est affichée
pour un fournisseur auto-hébergé et masquée pour un fournisseur cloud.
`base.fInit` se rabat déjà sur le `cDefaultBaseUrl` de l'adaptateur, si bien que
pour un fournisseur cloud le champ posait une question qui avait reçu sa
réponse avant d'être posée - et la seule réponse qu'il pouvait recevoir que la
valeur par défaut ne donne pas était une mauvaise réponse. Il est masqué et non
vidé : une installation qui place un proxy devant un fournisseur cloud a cette
adresse enregistrée, et masquer une case n'est pas une raison de jeter ce
qu'elle contient.

Une chose que `base.py` cache à tous, c'est le nom d'un outil. Ce projet nomme
un outil `family.action` ; un fournisseur valide le nom d'une fonction contre
`^[a-zA-Z0-9_-]+$` et refuse toute la requête à cause du point, sans indiquer
quel champ était fautif. `fToolNameToWire` remplace le point par `__` à
l'aller et `fToolNameFromWire` le remet au retour, dans chaque adaptateur, si
bien que le registre, l'interface, `info.json` et les logs ne voient jamais la
forme encodée.

### Des plafonds, pas de la confiance

Chaque exécution s'arrête au premier de quatre plafonds : jetons, étapes,
secondes, exécutions par jour. Ils existent parce qu'une boucle sans
surveillance sur une API payante est une facture ouverte et, sur un modèle
auto-hébergé, un GPU qui ne revient jamais. Le `max_tokens` de chaque requête
diminue de ce que l'exécution a déjà dépensé, si bien qu'une exécution ne peut
pas dépasser son budget d'un dernier appel coûteux.

Quatre choses font la différence entre un plafond et une suggestion, et
chacune a été l'une ou l'autre jusqu'à ce qu'elle soit corrigée :

  - **Pas de plancher sous la demande de jetons.** `max(512, remaining)`
    demandait 512 jetons quand le budget était épuisé, si bien qu'un agent à
    qui il restait un jeton avait encore droit à une demi-page.
  - **Chaque appel reçoit le temps qui RESTE**, et non tout le délai de
    l'exécution. Le `vTimeoutSeconds` propre à l'adaptateur est ajusté avant
    chaque appel, plutôt que d'ajouter un paramètre aux vingt-six adaptateurs
    qui implémentent `fSendMessages`.
  - **L'échéance est vérifiée avant chaque outil**, et non une fois par étape.
    Un lot de six appels d'outils arrivant juste avant l'échéance s'exécutait
    autrefois en entier, chacun avec son propre délai, en plus d'une exécution
    déjà terminée.
  - **Une horloge monotone.** `time.time()` bouge quand NTP la fait sauter, et
    une exécution qui a démarré « dans le futur » n'atteint jamais son délai.

Ce qui n'est toujours pas borné, c'est le prompt. Un appel dépense son entrée
plus sa sortie et seule la sortie est plafonnée ici, si bien qu'une longue
conversation déborde à l'entrée ; la compter voudrait dire passer le tokeniseur
propre à chaque fournisseur sur la conversation avant chaque appel. La réponse
de clôture après un plafond dépasse aussi délibérément le budget, et le dit là
où elle est écrite.

### Une seule exécution d'un agent à la fois

Deux verrous, parce qu'il y a deux sortes d'appelants.

Le démon tient un `threading.Lock` par agent entre « cet agent est-il en
train de tourner » et « lancer le processus ». Il sert chaque requête dans son
propre thread, si bien que deux appels `run_now` avec `only_if_idle` étaient
deux threads d'un même processus sans rien entre eux - et un balayage de /proc
ne peut pas voir un processus qui n'a pas encore été forké. Mesuré : deux
appels simultanés, deux exécutions.

Le runner prend un `flock` sur `<home>/run.lock` et le garde pendant toute la
durée du processus. C'est celui-ci qui fait autorité, parce qu'un crontab lance
le runner directement et ne passe jamais par le démon. Ce n'est pas une
frontière de permissions - un agent doté de `bash.run` peut lancer ce qu'il
veut - il existe pour que l'APPLICATION ne lance pas deux fois le même agent,
dépensant deux budgets sur un seul profil de navigateur et une seule
conversation.

### Une exécution qui n'a jamais démarré le dit

Le démon privilégié lance le runner avec stdin, stdout et stderr sur
`/dev/null`. Tout ce qu'écrit `fLogLine` ne va donc nulle part, et deux échecs
vivaient autrefois entièrement dans cette sortie :

- le verrou d'exécution était pris, donc cette exécution n'a pas lieu ;
- quelque chose a échoué avant que `fExecute` n'écrive `run_started` - un
  `info.json` illisible, ou un fournisseur dont la clé d'API n'a pas été
  définie, ce qui est de loin le plus probable des deux.

Mesuré sur une vraie installation : avec le verrou pris,
`POST /agents/001/run` répondait `202 {"started": true}` et rien n'apparaissait
dans le journal, dans `journalctl`, ni dans aucun fichier. Le même échec sous
cron ÉTAIT visible, parce que cron garde la sortie de ce qu'il lance - c'est
pourquoi cela a duré aussi longtemps. Le trou n'a jamais existé que sur le
chemin qu'utilise l'interface.

`fRecordRunRefused` l'écrit plutôt dans le journal, comme une fin avec le
statut `refused` et sans `run_id`. Chaque partie de cette forme est porteuse :

| Partie | Pourquoi |
|---|---|
| `kind: run_finished` | L'Historique affiche les fins. Un type à part demanderait que l'interface l'apprenne, et une entrée que rien n'affiche équivaut à pas d'entrée |
| `status: refused` | `failed_runs` compte les fins dont le statut est `failed`. Rien de l'agent n'a tourné, donc rien de l'agent n'a échoué |
| pas de `run_started` | `runs` et `max_runs_per_day` comptent les démarrages. Un verrou pris ne doit pas consommer une des exécutions du jour pour une exécution qui n'a pas eu lieu |
| `run_id: ""` | Rien n'a démarré, il n'y a donc aucune exécution à identifier |

Écrit seulement quand rien d'autre ne l'a écrit. Dès que `fExecute` a un
identifiant d'exécution, il a déjà écrit `run_started`, et ses propres
gestionnaires écrivent le `run_finished` correspondant avant de relancer
l'exception, si bien que `fMain` vérifie `vRun.vRunId` avant d'ajouter une
seconde fin pour une même exécution. La même vérification décide qui clôt le
tour de conversation : les gestionnaires de `fExecute` le closent en
consignant la fin, et `fMain` ne le clôt que pour une exécution qui n'est
jamais allée aussi loin. Mesuré avant qu'il en soit ainsi, sur la machine de
test Debian : chaque exécution qui ne pouvait pas joindre son fournisseur
répondait deux fois à sa question, avec la même phrase.

### L'Historique montre le plus récent, et ce n'était pas le cas

`fReadEntries` renvoie un journal du plus ancien au plus récent - sa propre
docstring le dit - et `fRenderRunHistory` en prenait `.slice(0, cShownRuns)`.
Ce sont les dix exécutions les plus ANCIENNES. Un agent ayant plus de dix
exécutions derrière lui avait un Historique qui ne changeait plus jamais.

Trouvé en pilotant la vraie application avec un vrai navigateur, qui est la
seule façon dont on pouvait le trouver : tous les autres tests de
`dashboard.js` dans ce projet lisent le fichier et y cherchent une chaîne, et
la chaîne y était. Mesuré sur une vraie installation, dans trois langues : un
agent dont l'exécution la plus récente venait d'être refusée faute de clé
d'API affichait un échec de fournisseur datant de quarante minutes plus tôt, et
le refus n'apparaissait jamais.

`.slice(-cShownRuns).reverse()` : les dix dernières, la plus récente en haut,
ce que dit le titre au-dessus de la liste.

Le tableau récapitulatif au-dessus de cette liste avait deux défauts à lui,
tous deux trouvés sur la même capture d'écran : il affichait `last_status`
brut, si bien qu'une page en espagnol affichait « Último estado: refused », et
il affichait `last_run_at` brut, si bien qu'un `2026-09-19T03:44:29Z` nu
trônait juste au-dessus d'une liste d'horodatages mis en forme. Les deux passent
désormais par ce qu'utilisaient déjà les lignes en dessous.

### Une boîte aux lettres est la seule entrée dans laquelle n'importe qui peut écrire

Les quatre outils `mail.*` suivent exactement les canaux : l'agent nomme ce
qu'il veut voir fait, et l'API des agents - qui tourne en tant que `boa` et
détient les identifiants - le fait. Un agent qui pourrait lire le mot de passe
de la boîte aux lettres n'aurait pas « accès à la boîte de réception » ; il
aurait le compte, chaque message qu'il contient, pour toujours, et la capacité
d'envoyer au nom de son propriétaire.

Ce qui diffère avec le courrier, c'est le sens dans lequel voyage l'entrée. Un
agent qui lit une boîte aux lettres est un agent dont les instructions
arrivent, en partie, à l'intérieur des messages qu'il lit, écrits par
n'importe qui dans le monde. Trois décisions en découlent :

  - **Le transfert n'est autorisé que vers les adresses que l'utilisateur a
    listées**, et cette liste est vérifiée dans `mailbox`, dans le processus qui
    ouvre la connexion - jamais dans le prompt. Une règle dans un prompt est un
    conseil ; une règle au niveau de la socket est une règle. Sans liste, le
    transfert est refusé d'emblée.
  - **Lire ne marque rien comme lu** (`BODY.PEEK[]` sur une sélection en
    lecture seule), si bien qu'un agent qui regarde une boîte aux lettres
    n'enlève pas le compteur de non-lus sur lequel comptait la personne.
  - **Supprimer déplace vers la corbeille** quand le compte en a une. Ce qu'un
    agent retire en vertu d'une règle écrite le mois dernier, une personne peut
    encore le retrouver. « Ce compte n'a pas de dossier corbeille » et « la
    liste des dossiers n'a pas pu être lue » sont tenus séparés, parce que seul
    le premier peut finir en expunge : ils arrivaient autrefois à
    `fDeleteMessage` sous la forme de la même chaîne vide, si bien qu'une seule
    ligne LIST non analysée transformait chaque `mail.delete` en suppression
    définitive.

### Livré avec un seul agent, en proposant beaucoup

L'installation crée exactement un agent : l'orchestrateur. Tout le reste vient
du « + », qui propose trois points de départ : un agent VIDE, un `.zip` exporté
depuis un agent, ou un MODÈLE du dépôt de modèles. Une installation qui arrive
avec des agents que personne n'a demandés est une installation qui commence par
des choses à éteindre.

Les modèles étaient autrefois livrés dans ce dépôt, un fichier Markdown chacun
dans `backend/agents/examples/`. Ils vivent maintenant dans leur propre dépôt,
[bunch-of-aigents-templates](https://github.com/nipegun/bunch-of-aigents-templates),
cloné à côté de celui-ci sous `../bunch-of-aigents-templates` : un nouveau
modèle atteint chaque installation sans mise à jour de l'application, et une
installation peut être dirigée vers un fork, ou vers un dépôt à elle, dans
Réglages -> Agents (`templates_repo_url`, `templates_repo_branch`, vérifiés par
`agent_templates.fValidateRepositoryUrl` et `fValidateBranch` à
l'enregistrement). `agent_templates` télécharge le dépôt entier sous la forme
de l'unique `.tar.gz` sous lequel une branche est servie - l'adresse depuis
laquelle l'installateur télécharge l'application - si bien que lister les
modèles est une seule requête, sans API GitHub et sans limite de débit. Il est
mis en cache cinq minutes par worker web. Une adresse `file://` avec la même
disposition `archive/refs/heads/<branch>.tar.gz` sert une machine sans accès
vers l'extérieur.

**Un seul format pour tout ce qui devient un agent** (`agent_package`) : un
dossier avec `agent.json` et `system-prompt.md`, et en option `memory.md`,
`home/...` et `rag/documents.json` avec `rag/files/...`. Un dossier de modèle
est un tel paquet qui ne porte que les deux premiers ; un `.zip` exporté a la
même disposition avec les options que l'utilisateur a cochées. Installer un
modèle et importer un `.zip` sont donc la même fonction,
`agent_io.fInstallPackage`, et tout ce qui peut être exporté peut être publié
comme modèle.

Tout est vérifié avant qu'un agent n'existe (`agent_package.fReadPackage`),
parce qu'une importation qui échoue à mi-chemin laisse un agent que personne
n'a demandé :

- `agent.json` ne peut contenir que les clés de `lManifestKeys`, et `format` 1.
  Une clé inconnue est refusée plutôt qu'ignorée : c'est une coquille dans un
  modèle, ou un paquet d'une version plus récente que celle-ci lirait mal.
- Il n'y a de place dans le format ni pour `enabled`, ni pour des clés, des
  jetons ou des identifiants de canaux, ni pour les canaux que l'agent écoute.
  Un agent importé est toujours créé éteint, et un fournisseur ne voyage que
  sous forme de nom, de modèle et d'URL de base - `api_key_ref` jamais.
- Les horaires sont cinq champs cron, rien d'autre (`agents.fValidateSchedule`),
  et sont vérifiés DE NOUVEAU dans `exec_daemon.fVerbCreateAgent`. Un horaire
  est écrit au début d'une ligne de crontab, en tant que root ; un horaire qui
  porterait « /bin/sh -c ... » ou un saut de ligne serait une commande. Que le
  processus web vérifie ne suffit pas : c'est l'exécuteur qui est la frontière.
- Les outils ne sont gardés que s'ils sont installés ici, et ceux qui sont
  écartés sont listés (`missing_tools`) pour que l'utilisateur les voie avant de
  confirmer. Les compétences sont passées par leur nom et l'exécuteur garde
  celles qui sont installées, comme avant.
- `rag` passe par `rag_settings.fValidateSettings`, comme une écriture depuis
  l'onglet RAG, et les documents de la bibliothèque doivent tenir dans les
  limites de fichier et de stockage qu'apporte le paquet lui-même.
- Chaque chemin du répertoire personnel passe par `agent_home.fValidatePath` :
  relatif, sans `..`, et jamais un nom de premier niveau exclu (voir plus bas).
- Un `.zip` (`ZipSource`) est refusé s'il contient un nom de membre qui
  remonte hors de l'arborescence, un lien, un membre chiffré, un membre qui se
  décompresse à plus de 200:1 au-delà de 1 Mio, ou plus de 8 Gio au total. Une
  archive de dépôt ne garde que les fichiers ordinaires ; un lien qu'elle
  contient est ignoré, pas suivi.

Créer depuis un modèle nomme le MODÈLE et rien d'autre. Le serveur le
télécharge et le lit : une requête qui pourrait porter ses propres outils et
son propre horaire permettrait au navigateur de remettre à un agent une
permission que l'utilisateur n'a jamais cochée. La boîte de dialogue met
l'agent VIDE en premier, puis le `.zip`, puis les modèles, dont les
descriptions viennent de l'`agent.json` de chaque modèle dans la langue de
l'interface (`fPickDescription` : cette langue, sinon en-US).

**Une importation se fait en trois temps**, parce qu'une bibliothèque peut
peser des centaines de Mio et que HAProxy abandonne une requête qui n'envoie
rien pendant 300 secondes : le navigateur envoie le `.zip` par blocs dans
`/opt/boa/imports/<id>/` (`boa`, 0700, créé par les deux installateurs et listé
dans les `ReadWritePaths` de l'unité web) ; `fFinishImport` le vérifie en entier
et renvoie ce qu'il installerait ; une fois que l'utilisateur confirme,
`fStartImport` l'installe dans un thread du processus web, qui écrit sa
progression dans `job.json` pour que le navigateur l'interroge. N'importe quel
worker peut répondre à l'interrogation parce que l'état est un fichier. Une
tâche dont le thread a cessé d'écrire depuis trois minutes est lue comme
interrompue : son processus a été redémarré. Un échec survenu après que
l'agent existe le supprime de nouveau (`fInstallPackage`).

**Une exportation est envoyée en flux** (`fExportAgent`) : le `.zip` est écrit
pendant qu'il est envoyé, si bien qu'un agent doté d'une bibliothèque de
centaines de Mio est exporté sans être tenu en mémoire. Du crontab ne voyagent
que les lignes que cette application a écrites pour lancer l'agent, sous la
forme de leurs cinq champs (`fReadSchedules`) ; toute autre ligne est une
commande que quelqu'un a tapée, et un paquet qui porterait des commandes les
exécuterait sur la machine où il atterrit.

**Le répertoire personnel est lu et écrit en tant qu'agent** (`agent_home`,
verbe de l'exécuteur `agent_home`) : l'exécuteur lance le module sous
l'utilisateur de l'agent, comme il lance le worker RAG, si bien que root ne
parcourt jamais une arborescence que l'agent peut réorganiser, et qu'un lien
planté dans le répertoire personnel ne mène nulle part où l'agent ne pouvait
pas déjà aller. Laissés de côté dans les deux sens : ce que le système y garde
(`chat.jsonl`, `runs.jsonl`, les enregistrements d'appels API, `run.lock`,
`attachments/`), ce qui a sa propre place dans le paquet (`memory.md`, `rag/`),
le profil de navigateur avec ses sessions connectées, et chaque entrée cachée
au premier niveau du répertoire personnel. Un `.ssh/authorized_keys` importé
serait une porte d'entrée et un `.bashrc` exécute du code, et ni l'un ni
l'autre ne vaut le rare usage légitime.

L'un des modèles, `web-navigator`, n'a pas de crontab. C'est celui du
navigateur - il ouvre des pages, se connecte, clique et remplit des
formulaires, là où les autres lisent - et ce travail est ce que l'utilisateur
vient de demander, pas quelque chose à faire à quatre heures du matin. Son
prompt est l'endroit où sont écrites les règles dont a besoin un navigateur doté
d'une session : ne jamais taper un identifiant, ne jamais finaliser un achat ou
un envoi, et traiter la page comme des données plutôt que comme des
instructions.

`rag-consultant` n'a pas de crontab non plus : il répond aux questions à partir
de sa propre bibliothèque RAG. C'est le seul modèle dont l'`agent.json` dit
`"rag": {"enabled": true}`. Le runner retient les outils `rag.*` tant que la
bibliothèque d'un agent est désactivée, donc sans cela l'agent serait créé sans
aucun outil. Le `rag` du paquet atteint `exec_daemon.fVerbCreateAgent` sous la
forme de `pRag` (le corps de la requête n'est jamais lu pour cela), où il passe
par `rag_settings.fValidateSettings`, la même vérification que celle par
laquelle passent les écritures de l'onglet RAG : un modèle peut activer la
bibliothèque et ne peut rien lui donner que cet onglet ne pourrait pas. Son
`max_tokens_per_run` vaut 40000 parce que le runner dimensionne le budget des
passages comme `max_tokens_per_run` moins le prompt, l'historique et 4096 ;
avec la valeur par défaut de 16384, il n'y aurait pas de place pour les
passages. Son prompt décrit les outils tels qu'ils sont - `rag.read` renvoie un
passage et ses voisins, pas un document - et demande les marqueurs `[rag:REF]`
que vérifie `fResolveCitations`.

### Deux façons de la servir, choisies à l'installation

Soit 11080 et 11443 sur localhost avec un HAProxy devant sur 80 et 443, soit 80
et 443 servis directement. L'installateur pose la question, mémorise la réponse
dans `config/ports.conf`, et une mise à jour ne la repose jamais, ni ne change
en douce les ports sur lesquels écoute la machine.

La différence ne tient pas qu'aux numéros : `accept-proxy` doit être retiré du
bind en mode direct, parce qu'un navigateur qui se connecte directement à 443
n'envoie aucun en-tête PROXY et qu'un bind qui en exige un refuse tous les vrais
clients.

En mode `direct`, le HAProxy propre à la machine n'est pas simplement laissé
tranquille : il est mis à la retraite. `fRetireMachineProxy` l'arrête, le retire
de chaque runlevel sur Alpine, le désactive **et le masque** sur Debian, puis
supprime `/etc/haproxy/haproxy.cfg` quand c'est cet installateur qui l'a écrit,
ou le déplace vers `haproxy.cfg.before-boa.<date>` quand c'est quelqu'un
d'autre. L'arrêter ne suffit pas : s'il reste activé, il prend 80 et 443 au
démarrage suivant, avant même que cette application ne tourne, et sous systemd
une mise à niveau de paquet, le `Wants=` d'une autre unité ou un simple
`systemctl start` peuvent ramener même une unité désactivée. Une unité masquée
ne peut être démarrée par rien, et haproxy sans `/etc/haproxy/haproxy.cfg` n'a
rien à partir de quoi démarrer. Tout ce qui occupe encore 80 ou 443 après cela
est nommé dans le log, parce que dans ce mode le proxy ne peut pas démarrer
sans eux, et le déduire de « the application did not answer » une demi-minute
plus tard est une bien pire façon de l'apprendre.

Ce qui n'est délibérément PAS fait, c'est supprimer le paquet haproxy.
`boa-proxy` EST `/usr/sbin/haproxy` - il termine le TLS et lit l'en-tête PROXY
devant gunicorn, et en mode `direct` c'est lui-même qui se lie à 80 et 443 -
donc purger le paquet laisserait l'application sans rien qui écoute du tout,
dans l'un comme dans l'autre mode. Ce qui est mis à la retraite, c'est le
*service* HAProxy de la machine, qui est une autre chose utilisant par hasard le
même binaire. Revenir à `proxied` démasque l'unité avant de l'activer, sinon le
retour se terminerait sur « The machine's HAProxy would not start » à cause
d'un masque que cet installateur avait lui-même posé.

Mesuré sur les deux machines de test avec `--update --ports direct` : l'unité a
fini masquée sur Debian et dans aucun runlevel sur Alpine, `/etc/haproxy` a été
laissé sans configuration, et l'application a répondu 200 sur 443 et 301 sur 80.
Le retour, `--update --ports proxied`, l'a laissée de nouveau activée et active,
avec 200 sur 11443 et sur 443. Sept tests EXÉCUTENT la fonction contre de
fausses commandes de service, sur une configuration avec le marqueur et une
sans, dans les deux modes, et l'un d'eux échoue si une future version se met un
jour à recourir à `apk del haproxy` ou `apt-get purge haproxy`.

### Une confirmation s'affiche là où regarde l'utilisateur

« Réglages enregistrés » s'écrivait autrefois tout en haut de la colonne de
contenu. Cela va sur un panneau court et ne sert à rien sur un long : le bouton
Enregistrer en bas de l'onglet Outils d'un agent produisait un message
plusieurs écrans plus haut, hors de ce que le navigateur dessinait, si bien
qu'enregistrer avait l'air de ne rien faire.

C'est maintenant un message contextuel centré sur la colonne de contenu, sur une
couche `fixed` qui est une sœur de cette colonne plutôt qu'une fille. `fixed`
est tout l'enjeu : centrer à l'intérieur de la colonne atterrirait au milieu du
*document*, ce qui, sur un onglet long, est le même bogue quelques écrans plus
bas. La couche s'arrête à la barre latérale, parce qu'un message dessiné
par-dessus la liste des agents aurait l'air d'appartenir à la liste des agents,
et elle ne reçoit aucun événement de pointeur, si bien que rien derrière elle ne
cesse de fonctionner pendant qu'un message est affiché.

Sa durée d'affichage est une préférence de ce navigateur (`boa.noticeSeconds`,
Réglages → Interface), à côté du thème et de la langue et pour la même raison :
trois secondes, c'est largement assez pour un mot et pas assez pour une phrase,
et ce qu'est un message, l'un ou l'autre, dépend de qui le lit. Les erreurs
sont l'exception et ignorent complètement ce nombre — une erreur attend qu'on
la ferme, parce que c'est le seul message qui doit encore être là quand
l'utilisateur revient regarder l'écran.

Un message a trois couleurs, et la troisième existe à cause de ce que les deux
autres ne peuvent pas dire. Le vert est un enregistrement qui a eu lieu, le
rouge un échec, et l'ambre est **« Aucune modification à enregistrer »** : on a
appuyé sur Enregistrer et le formulaire contenait exactement ce qui est déjà
stocké. Le signaler en vert est pire que ne rien dire - « Réglages
enregistrés » après un enregistrement qui n'a rien écrit est précisément la
phrase qui empêcherait quelqu'un de remarquer que sa modification n'a jamais
été prise en compte - et le rouge prétendrait à un échec là où rien ne s'est mal
passé.

Chaque formulaire qui enregistre le vérifie de la même façon : la charge utile
qu'il *enverrait*, comparée en JSON à l'instantané pris quand le formulaire a
été rempli depuis le serveur, ou après le dernier enregistrement. Les réglages
d'un agent construisent cette charge utile dans une seule fonction,
`fCollectAgentPayload`, utilisée à la fois pour enregistrer et pour prendre
l'instantané, parce que deux lecteurs du même formulaire qui divergeraient
signaleraient « aucune modification » sur le champ que l'un d'eux n'a jamais
regardé. Les panneaux de préférences du navigateur gardaient déjà un tel
instantané, pour l'indication « modifications non enregistrées », et il répond
aussi à cette question.

L'exception est un **nouvel** agent : son formulaire contient les valeurs
propres au modèle et n'a jamais été enregistré, donc appuyer sur Enregistrer les
écrit et passe à la conversation plutôt que de dire qu'il n'y a rien à faire.

### La couleur est l'état, le mouvement est l'activité

L'anneau autour de l'avatar d'un agent porte deux faits différents et les
dessine sur deux canaux différents, pour qu'aucun n'ait besoin d'être déchiffré.
Que l'agent soit allumé est une couleur qui ne bouge pas : vert ou rouge. Qu'il
soit en train de travailler en ce moment est un mouvement : un segment lumineux
parcourt cet anneau vert dans le sens des aiguilles d'une montre. Une seconde
couleur statique pour « occupé » serait une convention à apprendre, alors que
quelque chose qui tourne se comprend sans qu'on l'enseigne.

Il est dessiné comme un rectangle arrondi SVG posé exactement sur la bordure,
tracé avec un pointillé dont le décalage est animé, si bien que **la forme reste
immobile et seule la lumière se déplace le long d'elle**. C'est toute la raison
du SVG : faire tourner un anneau à la place — un dégradé conique, un arc,
n'importe quoi sous `transform: rotate` — fait aussi tourner la forme, et les
coins cessent de s'aligner sur le carré arrondi en dessous. `pathLength="100"`
normalise le contour, si bien que la feuille de style parle en pourcentages du
périmètre et que rien n'a besoin d'être recalculé si l'avatar ou son rayon
change.

Répondre à « qui est occupé ? » veut dire lire la ligne de commande de chaque
processus, ce que seul root peut faire, c'est donc un verbe du démon
privilégié. Un seul balayage de `/proc` répond pour tous les agents à la fois —
pas un appel par agent — et c'est ce qui le rend assez bon marché pour que la
barre latérale le demande toutes les cinq secondes. Le même balayage sert de
base à `only_if_idle`, si bien que le buzzer et l'interface ne peuvent pas être
en désaccord sur le fait qu'un agent travaille.

### Une carte qui arrive à échéance est annoncée dans la conversation

La conversation d'un agent est le registre de tout ce qu'on a demandé à cet
agent de faire, pas seulement de ce qu'on lui a tapé. Quand le buzzer lance une
exécution pour une carte arrivée à échéance, cette carte est donc écrite dans
le `chat.jsonl` de l'agent comme un tour à part entière, et la réponse de
l'exécution le clôt : ouvrir la conversation montre le travail qui arrive, ce
que l'agent en a fait et ce que cela a coûté.

Trois décisions font tenir l'ensemble.

**C'est écrit quand l'exécution démarre, pas quand la carte est créée.** Une
carte planifiée pour ce soir et supprimée cet après-midi ne s'est jamais
exécutée, et une conversation disant qu'elle a été remise serait le registre de
quelque chose qui n'a pas eu lieu. Le buzzer ne voit jamais que des cartes
encore sur le tableau, donc écrire au moment du réveil est ce qui rend
l'annonce vraie.

**Le fichier stocke les champs de la carte, pas une phrase.** `role: "card"`
porte l'identifiant, le titre, qui l'a attribuée et si elle a été demandée tout
de suite ; le texte du message est constitué des propres instructions de la
carte. Chaque mot autour d'elles est écrit par l'interface, dans la langue de
l'utilisateur — la même règle qui fait qu'une exécution arrêtée consigne
`ceiling: "tokens"` plutôt qu'une phrase en anglais.

**« Maintenant » et « à 13:45 » doivent être distingués, et au moment où l'agent
est réveillé, les deux sont dans le passé.** Le tableau consigne donc ce qui a
été demandé (`run_mode`) au lieu de le déduire après coup de l'horloge, et le
mot `now` voyage du navigateur jusqu'à `kanban.fValidateRunAt` sous forme de
mot, et ne devient un horodatage qu'à l'unique endroit qui consigne aussi ce
qu'il était.

L'écriture est le travail du démon privilégié, pas du buzzer : `chat.jsonl` vit
dans un répertoire personnel en 0700 appartenant à l'agent, et le buzzer tourne
en tant que `boa`. Le démon forke, descend vers l'agent, écrit l'annonce et
seulement ensuite lance l'exécution — et si le répertoire personnel n'est pas
accessible en écriture, l'exécution démarre quand même. L'annonce est le
registre du travail, pas le travail.

L'échec inverse n'est pas bénin et il est traité dans l'autre sens : si le
processus ne peut pas être lancé **après** l'ouverture du tour, le démon écrit
l'échec dans ce tour avant de lever l'exception. Rien d'autre ne le fermerait
jamais, et un tour ouvert ne se contente pas de laisser une carte sans
réponse — il ferme définitivement la zone de message pour cet agent.

L'exécution qui suit n'est ni une simple exécution planifiée ni un tour de
conversation. Elle écrit sa réponse dans la conversation, parce que la question
s'y trouve, mais la conversation ne lui est **pas** rejouée : son prompt est la
carte, et rejouer dix échanges facturerait à chaque exécution planifiée une
conversation que personne n'est en train d'avoir. Dans le runner, ce sont deux
indicateurs distincts — `vWritesToChat` et `vIsChat` — et toute l'affaire tient
dans cette distinction. Le corollaire est qu'une exécution qui s'arrête avant
d'avoir demandé quoi que ce soit au modèle (un agent éteint, le plafond
quotidien) doit quand même clore le tour, sinon l'interface attend une réponse
pour toujours et la zone de message reste fermée.

### La documentation de l'API est une page de cette application

Elle s'affiche à partir de la spécification OpenAPI que construit ce projet,
plutôt qu'en chargeant Swagger UI depuis un CDN, parce que le serveur de
production est une machine du LAN qui peut n'avoir aucun accès sortant à
Internet. Deux choses découlent du fait qu'il s'agisse d'une de nos propres
pages plutôt que d'un widget étranger.

Elle **suit la langue choisie**. La spécification reste en anglais - c'est le
contrat d'une API dont les noms de champs, les identifiants et les chaînes
d'erreur sont tous en en-US, et un `openapi.json` traduit décrirait une API qui
n'existe pas. Ce qui est traduit, c'est la page : `fAnnotateSpecForTranslation`
accroche une clé `data-i18n` à chaque morceau d'anglais avant le rendu, et le
navigateur la remplace de la même façon que sur toutes les autres pages. Cela
garde les chaînes dans les fichiers `.json` du frontend à côté de toutes les
autres, et cela fonctionne aussi pour un lecteur anonyme. Les clés sont dérivées
du texte et du chemin plutôt qu'écrites à la main, si bien qu'un nouveau point
d'entrée apporte les siennes ; une clé sans traduction garde l'anglais, ce que
fait `fApplyTranslations` d'une clé qu'il ne connaît pas.

Elle **remplit la colonne qu'on lui donne**, comme toutes les autres pages. Elle
gardait autrefois une largeur de 900 px et se centrait, ce qui se lit bien pour
de la prose et mal pour ceci : la page est surtout faite de tableaux de
paramètres et de blocs de JSON, et ceux-ci étaient comprimés dans un tiers d'un
écran large avec des marges vides de chaque côté.

### Les pièces jointes d'images sont une permission d'outil explicite

`browser.screenshot` enregistre un fichier ; `image.send` le joint à la réponse
en cours. Ce dernier est une autorisation distincte, incluse dans le modèle
web-navigator. L'outil fait un instantané du PNG dans
`agents/<id>/attachments/<opaque-id>.png` avec un répertoire en 0700 et un
fichier en 0600. Écraser plus tard la capture d'origine ne change pas une
réponse antérieure. `ToolContext.lAttachments` porte les références jusqu'à
`AgentRun.fRecordChatAnswer` ou jusqu'à son rapport d'échec ou d'exécution.

Seul l'exécuteur lit ces fichiers privés pour le processus web. Son verbe
`read_chat_attachment` exige une référence dans la conversation enregistrée de
cet agent, ouvre chaque composant de répertoire sans suivre les liens, et
vérifie que l'image est un fichier ordinaire appartenant à l'agent. Il lit les
PNG par blocs de 1 Mio ; les réponses en base64 restent sous la limite RPC
existante même pour une pièce jointe de 50 Mio. Le point d'entrée HTTP
authentifié envoie les octets en flux avec `private, no-store`. Le frontend
construit les URL d'images locales à partir d'identifiants, jamais à partir
d'URL fournies par le modèle.

Telegram utilise [sendPhoto](https://core.telegram.org/bots/api#sendphoto) pour
les images éligibles et [sendDocument](https://core.telegram.org/bots/api#senddocument)
pour les captures hautes ou volumineuses, avec le PNG d'origine. Le fichier
privé est envoyé en données multipart ; aucune URL publique ni aucun accès de
l'agent aux identifiants du bot n'est nécessaire. `telegram_deliveries`
consigne les parties de texte et d'image acquittées pour chaque tour en
attente. Les nouvelles tentatives reprennent avec la partie manquante, et
supprimer la ligne en attente efface ces points de reprise. Les échecs
définitifs sont signalés à l'utilisateur. Les deux boîtes de réception comparent
les horodatages UTC de SQLite au temps Unix ; les interpréter comme une heure
locale faisait expirer des livraisons récentes pendant l'heure d'été.

### Pas d'étape de build

Le frontend, ce sont des templates Jinja2, du CSS simple et du JavaScript
simple. La cible de production est une machine Debian ou Alpine auto-hébergée ;
un déploiement qui a besoin d'une chaîne d'outils Node pour modifier une feuille
de style est un déploiement qui pourrit. Pour la même raison, `/api/doc/` affiche
sa propre spécification OpenAPI plutôt que de charger Swagger UI depuis un CDN :
un serveur du LAN peut n'avoir aucun accès sortant à Internet, et une
documentation qui échoue sans lui échoue précisément quand quelqu'un est en
train de déboguer.

---

### Transcription audio

Lorsqu'il démarre les services OpenRC, l'installateur ferme les descripteurs 3 et 4 sur les commandes `rc-service`. Ce sont ses pipes sauvegardés de sortie standard et d'erreur SSH : on a observé que `supervise-daemon` les gardait après une sortie réussie de l'installateur. La sortie ordinaire est toujours capturée dans `install.log`.

`audio_transcription` stocke une configuration JSON validée unique dans `settings.audio_transcription`. OpenAI, Groq, Mistral et Together utilisent du multipart ; Hugging Face et Cloudflare reçoivent du WAV binaire. Ils réutilisent `api_keys` sans renvoyer de secrets au navigateur. FFmpeg borne les conteneurs, les protocoles, la taille, la durée et le temps d'exécution. L'audio est découpé en segments de 120 secondes (30 secondes pour les points d'entrée bruts de Hugging Face et de Cloudflare, pour ne pas dépendre d'options de génération longue) ; whisper.cpp et le décodage tournent en tant que `boa`, sans shell ni repli automatique vers un fournisseur.

`audio_inbox` conserve la destination, les réglages et la transcription dans SQLite. Un unique thread d'arrière-plan, verrouillé par processus, dans `boa-channel-telegram` récupère sa file d'attente après un redémarrage. Un identifiant de tour réservé permet à l'exécuteur d'acquitter une soumission répétée avant de vérifier si l'agent est occupé. Marquer la tâche comme soumise et insérer `telegram_pending` se font dans une seule transaction. L'audio privé vit dans `/opt/boa/audio/` (0700, appartenant à boa), exige à la fois une connexion et une référence de conversation correspondante pour être lu, et est supprimé quand les tours de conversation terminés sont effacés.

Les deux installateurs compilent whisper.cpp v1.9.4 après avoir vérifié le SHA-256 de l'archive source, et téléchargent `base`. `whisper_models.json` contient les 30 noms officiels, tailles et hashes. Seul l'exécuteur root télécharge des modèles, par `install_whisper_model` ; les URL et chemins arbitraires sont rejetés. Un fichier partiel ne devient visible qu'après vérification du hash. Root possède `whisper/` ; `boa` ne fait que le lire. Les mises à jour conservent les modèles et l'audio ; les sauvegardes incluent l'audio mais excluent les poids des modèles. Un interpréteur Python manquant est installé avec les dépendances avant la vérification de la version minimale.

### Requêtes brutes aux fournisseurs et espace de travail de l'agent

`AgentRun.fSendRecordedRequest` attache un enregistreur au fournisseur
sélectionné pour cet appel, y compris les appels de secours et de clôture. Les
adaptateurs basés sur Requests utilisent `BaseProvider.fPostJson`, qui
enregistre le même corps JSON sérialisé avant de l'envoyer. Les clients des SDK
OpenAI et Anthropic utilisent des hooks de requête, qui capturent le corps
préparé, y compris les champs du SDK et chaque nouvelle tentative.
L'enregistreur ne stocke jamais les en-têtes d'authentification et ne
reconstruit jamais une requête à partir de l'historique de conversation.

`api_calls` écrit un index dans `agents/<id>/api-calls.jsonl` et un corps
complet `api-call-<id>.json` par requête, en mode 0600 dans le répertoire
personnel privé de l'agent. La rétention supprime les requêtes entières au-delà
des 100 dernières. L'exécuteur ne lit que des fichiers ordinaires appartenant à
cet agent, en rejetant les liens symboliques et les FIFO. Les corps voyagent
par blocs bornés sur sa socket ; la route HTTP authentifiée envoie en flux leur
texte JSON d'origine sous `body`. Le navigateur met en forme les jetons sans
analyser les nombres, si bien que les grands entiers et les échappements de
chaînes survivent intacts.

Le `info.json` protégé stocke `interface.show_api_calls`, faux par défaut. Il
ne contrôle que la visibilité ; les requêtes sont enregistrées que l'onglet soit
visible ou masqué. `dashboard.js` sépare les onglets de conversation des onglets
de réglages et sélectionne toujours Conversation au chargement d'un agent. Il
n'interroge les métadonnées des requêtes que lorsque API Calls est ouvert, et ne
charge les corps complets que lorsque leurs détails sont dépliés. Le titre des
réglages identifie l'agent par son identifiant ; Exécuter maintenant appartient
à l'espace de travail, et la suppression a son propre panneau dans Général.

La zone de message est épinglée juste au-dessus de la barre d'état et seul
`#vChatLog` défile. Sur les largeurs de bureau, `app.css` donne à `.app`
exactement la hauteur d'une fenêtre pendant que la conversation est affichée
(`.app:has(#vChatPanel:not([hidden]))`) et transmet la hauteur le long d'une
colonne flex jusqu'à `.chat`, si bien qu'il n'y a pas de défilement de page où
perdre le formulaire. À 820 px et en dessous, la page défile de nouveau comme un
bloc, et `.chat` fait une hauteur de fenêtre moins `--status-bar-live-height`,
que `api.js:fTrackStatusBarHeight` maintient égal à la hauteur réelle de la
barre avec un `ResizeObserver` - sur un téléphone, la barre passe sur plusieurs
lignes, et une estimation fixe laissait la zone de texte en dessous d'elle. Il
n'y a pas de ligne d'aide sous la zone de message : `fSetComposerEnabled`
l'écrit comme seconde ligne du texte indicatif (comment se comporte Entrée, ou
le fait que l'agent travaille), et `fFitChatInputToPlaceholder` mesure ce texte
indicatif sur un jumeau invisible et fixe le `min-height` de la zone pour qu'il
ne soit jamais coupé. Il s'exécute chaque fois que le texte indicatif ou la
largeur de la zone de message change (`fTrackChatInputWidth`). Les hauteurs
sont fixées par le CSSOM, jamais par un attribut `style`, que la CSP
supprimerait.

### Partages Samba par agent

`agents.dDefaultSambaSettings` définit le partage activé, en lecture/écriture,
visible dans la liste, avec accès authentifié, et des modes de fichier et de
répertoire 0600/0700. Les mots de passe ne sont pas définis au départ.
`info.json.samba` est une configuration protégée ; le mot de passe n'existe que
dans la passdb de Samba, privée à root. Il est transmis à `smbpasswd` par
l'entrée standard, jamais par argv, le modèle, l'objet renvoyé par l'API ou
`info.json`.

`boa-samba` fait tourner un smbd isolé sur TCP 445, avec sa configuration et son
état natif dans `/opt/boa/samba/`, qui appartient à root, et ses fichiers
d'exécution dans `/run/boa-samba/`. Il n'a pas de service homes. Le nom d'un
partage est dérivé de `fGetAgentSystemUser` ; son chemin est toujours
`<agent home>/samba`. L'authentification utilise ce compte, et les opérations
sur les fichiers utilisent l'uid de cet agent. L'accès invité exige un réglage
explicite par agent. L'installateur refuse de prendre le contrôle d'une
installation Samba sans rapport et ne désactive l'instance par défaut de la
distribution que pour la propre installation de BoA.

L'exécuteur crée le dossier après avoir créé ou indexé un agent, et supprime le
partage et le compte avant de supprimer l'utilisateur. Les deux installateurs
réconcilient les agents existants après une installation, une mise à jour ou
une restauration. Un verrou exclusif sur fichier sérialise les modifications ;
`testparm` valide avant le remplacement atomique de la configuration.
`smbcontrol` recharge la configuration et ne ferme que les connexions du partage
modifié. Désactiver le partage d'un agent est indépendant de l'interrupteur
d'exécution de l'agent.

La préparation du dossier utilise des descripteurs de répertoire avec
`O_NOFOLLOW` et des vérifications de propriétaire. Samba refuse les liens à
l'intérieur du partage, et une garde preexec root vérifie de nouveau la racine
du partage à chaque connexion. La garde exécute le code Python de confiance
avec `-I`, si bien que le répertoire de travail d'un agent ne peut pas fournir
de modules importés.

Les sauvegardes incluent les fichiers partagés par l'archive normale du
répertoire personnel de l'agent, et les réglages par le fichier info protégé.
`tdbbackup` prend un instantané de la base de mots de passe native pendant
qu'elle est en service ; la sauvegarde garde aussi le SID du serveur. La
restauration exige que smbd soit arrêté, valide une base temporaire et la
remplace plutôt que de fusionner les identifiants actuels. L'exportation par
l'ancien format smbpasswd était rejetée par certains RID de comptes natifs et
n'est pas utilisée. `fVerifyInstallation` lit le mode de ports web enregistré
pour que la restauration vérifie le port HTTPS réel, y compris en mode direct
sans option `--ports` explicite.

Référence : [options de partage Samba](https://www.samba.org/samba/docs/current/man-html/smb.conf.5),
[outil de sauvegarde TDB](https://www.samba.org/samba/docs/3.6/man-html/tdbbackup.8.html).

### Recherche documentaire locale

Le libellé de l'onglet est `RAG` dans toutes les langues, y compris dans les
replis HTML et JavaScript.

`rag_store` possède le catalogue par agent (SQLite WAL, FTS5, documents,
révisions et décalages d'envoi). Les noms d'origine sont des métadonnées ; les
noms de fichiers sur le disque utilisent des identifiants générés.
`rag_extract` lit les PDF, EPUB, TXT et Markdown, et invoque Poppler et
Tesseract en local pour l'OCR. Il conserve les emplacements de page et de
chapitre et vérifie la taille décompressée des EPUB avant de les analyser.
`rag_embeddings` n'utilise que `AF_UNIX`, avec le chemin fixe
`/run/boa-embeddings/engine.sock` : pas de nom d'hôte, de proxy ni de repli
vers le cloud.

Les **Informations du document** modifiables sont, dans l'ordre où le
formulaire les affiche (`rag_store.lMetadataKeys`, contre lequel `fAction`
vérifie aussi) : année de publication, titre, sous-titre, auteur(s), version,
langue et étiquettes. La liste des documents affiche le sous-titre, quand il y
en a un, juste sous le titre. L'année est stockée comme texte (vide ou jusqu'à
quatre chiffres) pour que « inconnue » reste distinct d'un nombre.
`rag_store.fMigrate` ajoute les colonnes listées dans
`rag_store.lAddedColumns`, celles introduites après que des catalogues
existaient déjà (`year` et `subtitle` jusqu'ici) : `CREATE TABLE IF NOT EXISTS`
ne modifie jamais une table existante, et les bibliothèques anciennes comme les
sauvegardes restaurées portent l'ancien schéma. `rag_search.fSource` place le
sous-titre, l'année, l'auteur, la version et la langue sur chaque passage, si
bien que le modèle peut distinguer des documents qui partagent un titre, dater
et attribuer une citation, et peser deux éditions en désaccord, sans appel
supplémentaire à `rag.list`. Les liens de citation et la recherche dans la
bibliothèque ne gardent que le titre et l'emplacement : ils nomment un endroit,
et le sous-titre ne ferait qu'allonger le lien.

`rag_models.json` est le catalogue des modèles de vectorisation : pour chacun,
son URL et son SHA-256 épinglés, ses dimensions, son contexte, son pooling, ses
préfixes de requête et de passage, et les deux similarités mesurées pour lui
(`min_support` pour le mode vérifié, `min_similarity` pour le seuil de
recherche). Deux sont livrés : EmbeddingGemma 300M Q8 (le `default` ;
768 dimensions, mean pooling) et Qwen3-Embedding 0.6B Q8 (1024 dimensions,
last-token pooling, une instruction en anglais avant chaque requête et rien
avant un passage). Celui qui est utilisé est `model` dans les réglages
d'exécution (`/opt/boa/rag-runtime/settings.json`, écrit par root et lisible
par tous les agents), lu par `rag_settings.fSelectedModel` et
`rag_embeddings.fModel`. `rag_runtime` installe les poids - l'installateur le
modèle sélectionné, l'exécuteur n'importe quel autre sur demande
(`install_rag_model`, un téléchargement à la fois dans un thread, sa
progression dans `rag-runtime/status/<id>.json`) - et un fichier ne reçoit son
nom qu'une fois que sa taille et son SHA-256 correspondent. Il lance llama.cpp
v0.5.0 avec le pooling du modèle et l'identifiant du modèle comme `--alias`.
L'accès au réseau n'appartient qu'à l'installation. Le runtime utilise le
tokeniseur et les préfixes de recherche du modèle, et rejette une entrée trop
grande. SQLite stocke le texte et les vecteurs ; USearch stocke des
générations HNSW incrémentales. Publier une révision bascule atomiquement la
visibilité dans le catalogue et le nom de l'index.

Il n'y a qu'un moteur, donc le modèle est choisi pour toute la machine, et
c'est l'exécuteur root qui fait le changement (`rag_exec.fRuntime`) : il refuse
des poids qui ne sont pas sur le disque, enregistre le choix, fait passer le
`min_similarity` de chaque agent encore sur la recommandation de l'ancien
modèle à celle du nouveau (`fFollowModelSimilarity` ; une valeur que quelqu'un
a choisie reste) et redémarre `boa-embeddings`. Aucun vecteur n'est jugé fiable
sur la seule foi du fichier de réglages. `rag_embeddings.fEmbed` demande au
moteur quel modèle il sert (`/v1/models`, l'alias) avant de vectoriser, et lève
`EngineUnavailable` quand ce n'est pas celui attendu ou quand un vecteur n'a pas
le bon nombre de dimensions ; une tâche d'indexation transmet le modèle avec
lequel elle a commencé, si bien qu'un changement en cours de route arrête la
tâche au lieu de mélanger deux espaces vectoriels dans une même révision.
Chaque document consigne l'empreinte du modèle qui se trouve derrière sa
révision publiée (`documents.model`). À son passage suivant,
`rag_worker.fWork` voit que le modèle de la bibliothèque n'est pas celui qui
est sélectionné (`fFollowNewModel`) : il abandonne les fragments des révisions
inachevées, remet en file chaque document indexé avec un autre modèle et oublie
l'index. Les révisions publiées restent. Jusqu'à ce que son tour vienne, un
document n'est trouvé que par FTS5 : `fSearch` ne construit les rangs
vectoriels qu'à partir des documents du modèle en usage - par le nouvel index,
ou en comparant leurs vecteurs stockés un par un tant qu'il n'y en a pas - et
ajoute un `notice` disant combien de documents attendent. Le même repli par mots
clés répond à une recherche pendant que le moteur redémarre. `rag_verify`
épingle un même modèle pour les deux côtés de sa comparaison et prend son seuil
de ce modèle.

`boa-rag` tourne en tant que boa et demande à l'exécuteur existant de lancer des
commandes de worker fixes. `rag_exec` abandonne l'UID et le GID avant toute
opération sur les documents ou sur SQLite ; root n'analyse jamais un livre et
n'ouvre jamais le catalogue d'un agent. Les workers utilisent un verrou du
système, des limites de ressources et des états persistants. Les RPC d'envoi se
font par blocs de 256 Kio, les téléchargements par blocs de 1 Mio ; des livres
entiers ne traversent jamais le protocole de l'exécuteur en un seul message. Le
worker garde la révision précédente consultable et reprend les fragments
terminés après une interruption. Les réglages restent dans la configuration
protégée de l'agent.

Une panne du moteur n'est pas une erreur de document. `rag_embeddings` lève
`EngineUnavailable` (une `ValueError`) quand la socket échoue ou que le moteur
répond 503 pendant qu'il charge le modèle ; tout autre refus reste une simple
`ValueError`. `fIndexDocument` traite la panne à part : le document revient à
`queued` avec la MÊME révision, garde chaque fragment déjà vectorisé et affiche
la raison jusqu'à ce qu'une tâche tourne de nouveau. L'ancien comportement -
`error` et les fragments de la révision supprimés - faisait perdre des heures
d'un gros livre à chaque `--update`, parce que l'installateur arrête
`boa-embeddings` pendant qu'un worker lancé par `boa-exec` tourne encore.
`fWork` sonde le moteur (`fIsAvailable`) avant de commencer chaque document en
file et termine le lot en cas de panne ; sinon, chaque passage de 5 secondes du
planificateur extrairait ou passerait à l'OCR tout le document juste pour
s'arrêter à son premier fragment.

`rag_search` combine les rangs FTS5 et sémantiques ; les recherches filtrées
évaluent le sous-ensemble sélectionné. Le runner effectue une recherche avant
l'appel de réponse et n'accorde les trois outils RAG en lecture seule que
lorsque le RAG est activé. Les sources sont bornées par le budget de texte
configuré et par une estimation prudente des jetons de l'exécution. Les
marqueurs de citation ne se résolvent que vers des sources réellement renvoyées
pendant l'exécution. Le fournisseur qui répond peut être distant : le
traitement uniquement local s'applique à la vectorisation.

Les trois modes de réponse diffèrent par ce que le RUNNER impose, pas seulement
par ce que dit le prompt. `mixed` laisse le modèle ajouter des connaissances
générales. En `documental` et `verified` (`runner.lRagModesThatSearch`), le
modèle doit appeler `rag.search` lui-même : `fCheckRagAnswer` renvoie, une
fois, une réponse finale donnée sans cet appel (`cRagSearchFirstPrompt`). La
recherche propre du runner est le dernier message de l'utilisateur mot pour
mot, et dans une conversation (« et dans la deuxième édition ? ») elle ne trouve
rien là où la requête du modèle, écrite avec toute la conversation sous les
yeux, trouve. Pour la même raison, une recherche vide ne termine plus
l'exécution documentaire avant que le modèle ne soit interrogé ; la garantie a
été déplacée à la fin : `fFinishRagAnswer` remplace la réponse d'une exécution
qui n'a récupéré aucun passage par une phrase fixe. `tool_choice` n'est pas
utilisé pour forcer la recherche : parmi les 29 adaptateurs, certains envoient
`auto`, Cohere n'envoie rien et Mistral utilise `any`, si bien que seul le
runner peut l'imposer à tous les fournisseurs.

`verified` ajoute `rag_verify`. La réponse est découpée en unités - les
paragraphes, et chaque élément de liste séparément, un bloc de code délimité
étant rattaché au paragraphe qui le précède et comparé avec lui (l'introduction
d'un exemple ne dit presque rien à elle seule, et des exemples fidèles étaient
retirés à cause de cela) ; les titres, les libellés courts se terminant par
« : » et les séparateurs en sont exemptés. Une unité a besoin d'un `[rag:REF]`
parmi les passages récupérés pendant l'exécution et, sauf si c'est une simple
référence, doit être proche de l'un d'eux : l'unité vectorisée comme requête
contre les passages vectorisés comme documents, la même distance que celle
qu'utilise la recherche, au `min_support` du modèle (0,36 pour EmbeddingGemma,
0,44 pour Qwen3-Embedding). La première réponse en échec est renvoyée une fois
avec les unités fautives (`fBuildCorrectionPrompt`) ; après cela, elles sont
retirées et une ligne localisée dit combien. S'il ne reste rien d'appuyé, on
obtient la phrase fixe ; un moteur injoignable retient la réponse (échec
fermé). Les phrases fixes (`rag_verify.dFixedTexts`) sont dans la langue dans
laquelle le prompt système a demandé de répondre, reconnue par sa ligne dans
`dAnswerLanguageLines`, et en anglais sinon. La limite de la vérification est
mesurée et écrite à côté de la vérification. Sur 138 paragraphes fidèles et
2 652 citations vers des passages d'un autre sujet, aucun seuil ne sépare les
deux, avec aucun des deux modèles ; ceux qui sont utilisés retirent environ 6 %
des paragraphes fidèles (surtout des éléments de liste courts et des résumés
d'une ligne) et laissent passer moins de 1 % de ces citations erronées. Une
citation vers un passage du même sujet passe environ une fois sur quatre, et un
paragraphe qui contredit son passage obtient le même score qu'un paragraphe
fidèle : ce que la vérification attrape, c'est une citation vers un passage qui
parle d'autre chose, et un paragraphe sans source.

La sauvegarde crée des instantanés sous des parents de préparation appartenant à
root, laisse l'enfant de l'agent prendre une sauvegarde SQLite et créer des
liens physiques vers ses fichiers immuables sélectionnés, puis archive cet
instantané. Cela garde les générations WAL et HNSW cohérentes et évite que root
parcoure une arborescence d'instantané que l'agent pourrait permuter. La
restauration annule les envois partiels et remet en file les indexations
interrompues. Les empreintes d'index restent disponibles pour les
reconstructions.

## 2. Carte des modules

| Module | Chemin | Responsabilité | Dépend de | Utilisé par |
|---|---|---|---|---|
| `audio_transcription` | `backend/core/audio_transcription.py` | Réglages de la parole et moteurs de reconnaissance | db, api_keys, whisper_runtime | audio_inbox, api |
| `audio_inbox` | `backend/core/audio_inbox.py` | File durable, routage, nouvelles tentatives et lecture privée | db, exec_client, audio_transcription | telegram_listener, api |
| `whisper_runtime` | `backend/core/whisper_runtime.py` | Catalogue, état et téléchargements vérifiés des modèles | paths, whisper_models.json | installateur, exec_daemon, api |
| `settings_audio.js` | `frontend/static/js/settings_audio.js` | Formulaire audio, téléchargements de modèles et progression | api.js, i18n.js | settings.js, settings_audio.html |
| `rag_store` | `backend/core/rag_store.py` | Catalogue, envois, révisions et instantanés | `rag_settings` | `rag_worker, rag_search` |
| `rag_extract` | `backend/core/rag_extract.py` | Extraction locale de PDF, EPUB et texte, et OCR | `rag_embeddings, pypdf, EbookLib` | `rag_worker` |
| `rag_embeddings` | `backend/core/rag_embeddings.py` | Client local par socket pour le tokeniseur et la vectorisation ; refuse un vecteur venant de tout autre modèle que celui attendu | `rag_settings` | `rag_extract, rag_search, rag_worker, rag_verify` |
| `rag_search` | `backend/core/rag_search.py` | Recherche hybride, publication HNSW et citations | `rag_store, usearch, numpy` | `runner, tools` |
| `rag_worker` | `backend/core/rag_worker.py` | Tâches d'indexation durables appartenant à l'agent | `rag_store, rag_extract, rag_search` | `rag_exec` |
| `rag_verify` | `backend/core/rag_verify.py` | Vérifie chaque paragraphe d'une réponse contre les passages qu'il cite ; les phrases RAG fixes en 15 langues | `rag_embeddings` | `runner` |
| `rag_exec` | `backend/core/rag_exec.py` | Abandon des privilèges et commandes de worker fixes | `paths, rag_settings` | `exec_daemon` |
| `rag_runtime` | `backend/core/rag_runtime.py` | Installation et téléchargements vérifiés des modèles, moteur local, état et préparation de la restauration | `rag_settings, rag_embeddings` | `installers, boa-embeddings, rag_exec, exec_daemon` |
| `rag_models.json` | `backend/core/rag_models.json` | Les modèles de vectorisation : poids, hashes, pooling, préfixes et similarités mesurées pour chacun | — | `rag_settings` |
| `rag_scheduler` | `backend/core/rag_scheduler.py` | Interrogation équitable de la file | `agents, exec_client` | `boa-rag` |
| `paths` | `backend/core/paths.py` | Tous les chemins du système de fichiers et la validation des identifiants d'agents | — | tout |
| `db` | `backend/core/db.py` | Connexions SQLite et les deux schémas | `paths` | `agents`, `kanban`, `auth`, `bootstrap` |
| `agents` | `backend/core/agents.py` | Modèle d'agent, `info.json` (y compris les réglages Samba), index des agents, hachage des jetons | `db`, `paths` | `exec_daemon`, `agent_api`, `api` |
| `bootstrap` | `backend/core/bootstrap.py` | Initialisation au premier lancement | `agents`, `db`, `paths` | installateur |
| `exec_protocol` | `backend/core/exec_protocol.py` | Protocole de communication et liste des verbes | — | `exec_daemon`, `exec_client`, `agent_api` |
| `exec_daemon` | `backend/core/exec_daemon.py` | Le démon privilégié (root) | `agents`, `paths`, `run_journal`, `api_calls`, `samba` | service `boa-exec` |
| `exec_client` | `backend/core/exec_client.py` | Client du précédent | `exec_protocol`, `paths` | `web/api` |
| `agent_api` | `backend/core/agent_api.py` | Le démon auquel parlent les agents | `agents`, `kanban`, `channels` | service `boa-agent-api` |
| `agent_api_client` | `backend/core/agent_api_client.py` | Client du précédent | `agent_api`, `exec_protocol` | les outils livrés |
| `runner` | `backend/core/runner.py` | Une exécution d'agent : la boucle et ses plafonds | `providers`, `tool_registry`, `run_journal`, `api_calls` | cron, `exec_daemon` |
| `run_journal` | `backend/core/run_journal.py` | Le `runs.jsonl` de chaque agent | `paths` | `runner`, `exec_daemon` |
| `api_calls` | `backend/core/api_calls.py` | Corps exacts des requêtes, index privé, rétention et lectures bornées | `paths`, `run_journal` | `runner`, `exec_daemon` |
| `dashboard.js` | `frontend/static/js/dashboard.js` | Espace de travail Conversation/API Calls, réglages de l'agent et affichage paresseux des requêtes | `api.js`, `jsonhighlight.js`, `markdown.js` | `dashboard.html` |
| `chat` | `backend/core/chat.py` | Le `chat.jsonl` de chaque agent et la conversation rejouée au modèle | `paths` | `runner`, `exec_daemon` |
| `memory` | `backend/core/memory.py` | Le `memory.md` de chaque agent, limite de caractères configurable et écritures complètes ; chargé dans le prompt système de chaque exécution | `agents`, `paths` | `runner`, `exec_daemon`, `web/api`, outils |
| `skills` | `backend/core/skills.py` | Les procédures partagées de `/opt/boa/skills/`, un répertoire chacune. Analyse `SKILL.md`, construit l'index qui va dans le prompt, et dit lesquelles des compétences d'un agent existent encore | `paths` | `runner`, `exec_daemon`, `web/api`, `skill.read` |
| `provider_models` | `backend/core/provider_models.py` | Catalogues de modèles depuis `config/providers/*.json` | `paths` | `web/api` |
| `api_keys` | `backend/core/api_keys.py` | Les clés partagées des fournisseurs dans `config/apikeys/*.key`, écrites en 0600 dans un répertoire en 0700. Ne renvoie jamais une clé au navigateur, seulement si une clé est enregistrée et ses quatre derniers caractères | `paths` | `agent_api`, `web/api` |
| `tool_registry` | `backend/core/tool_registry.py` | Découverte, permissions et distribution des outils | `paths` | `runner`, `web/api` |
| `attachments` | `backend/core/attachments.py` | Instantanés PNG privés, identifiants opaques, propriété des fichiers vérifiée et lectures bornées | `paths` | `image_send`, `exec_daemon`, `exec_client`, `telegram_listener` |
| `image_send` | `backend/tools/image_send.py` | Joint un PNG possédé par l'agent à la réponse, via le contexte de l'outil | `attachments`, `tool_registry` | `runner` |
| `public_url` | `backend/core/public_url.py` | Si une URL donnée à un agent se résout en adresse publique. Formulé positivement avec `is_global` plus un refus explicite du multicast, parce qu'une liste de plages à refuser est une liste où l'on en oublie une - et 100.64.0.0/10 y avait été oubliée | — | `web.fetch`, `rss.fetch`, `browser` |
| `agent_scripts` | `backend/core/agent_scripts.py` | Les scripts qu'un agent écrit pour lui-même, et les lignes de cron qui les lancent. Valide les noms et les horaires, et ne réécrit jamais la ligne de réveil | `paths` | `script.*`, `cron.*` |
| `kanban` | `backend/core/kanban.py` | Le tableau et son historique | `db` | `agent_api`, `web/api` |
| `channels` | `backend/core/channels.py` | Telegram, Discord, Mattermost, X. L'envoi pour les quatre ; la lecture pour les deux auxquels on peut répondre | `paths`, `telegram_html`, `discord_markdown` | `agent_api`, `web/api`, les deux écouteurs |
| `agent_routing` | `backend/core/agent_routing.py` | Ce que les deux écouteurs font de la même façon : la liste des agents, la lecture du nom d'un agent dans un message, la réponse de clôture d'un tour, le rapport d'état | `agents`, `chat`, `exec_client`, `system_info` | `telegram_listener`, `discord_listener` |
| `providers.base` | `backend/providers/base.py` | Interface des adaptateurs et forme de message neutre | — | chaque adaptateur |
| `providers.factory` | `backend/providers/factory.py` | Nom du fournisseur → classe d'adaptateur | `providers.base` | `runner`, `web/api` |
| `providers.openai_dialect` | `backend/providers/openai_dialect.py` | La requête chat/completions que partagent les adaptateurs du dialecte OpenAI ; les particularités restent dans chaque adaptateur | `providers.base` | la plupart des adaptateurs |
| `providers.*` | `backend/providers/<name>.py` | Un adaptateur par fournisseur | `providers.base`, `providers.openai_dialect` | `factory` |
| `web.server` | `backend/web/server.py` | Fabrique Flask, clé de session, en-têtes de sécurité | `db`, `web.*` | gunicorn |
| `deploy/haproxy/boa.cfg` | `deploy/haproxy/boa.cfg` | Terminaison TLS, protocole PROXY, 11080 → 11443 | — | service `boa-proxy` |
| `web.auth` | `backend/web/auth.py` | Connexion, sessions, limitation du rythme | `db` | `web.api`, `web.views` |
| `web.api` | `backend/web/api.py` | Tout ce qui se trouve sous `/api/admin/` | `exec_client`, `kanban`, `channels` | navigateur |
| `web.api_doc` | `backend/web/api_doc.py` | Spécification OpenAPI et sa page. Annote la spécification avec des clés i18n pour la page seulement, jamais pour `openapi.json` | `channels`, `providers.factory` | navigateur |
| `web.views` | `backend/web/views.py` | Les pages HTML | `web.auth` | navigateur |
| `buzzer` | `backend/core/buzzer.py` | Surveille le tableau et lance une exécution quand une carte arrive à échéance | `kanban`, `exec_client` | service `boa-buzzer` |
| `telegram_listener` | `backend/core/telegram_listener.py` | Interroge Telegram en long poll, achemine chaque message vers un agent, renvoie la réponse | `channels`, `exec_client`, `telegram_inbox` | service `boa-channel-telegram` |
| `telegram_inbox` | `backend/core/telegram_inbox.py` | Quel agent a dit quoi sur Telegram, et à quelles questions une réponse est encore en cours. L'expiration est calculée en UTC | `db` | `telegram_listener`, `agent_api` |
| `discord_listener` | `backend/core/discord_listener.py` | Interroge un canal Discord, achemine chaque message vers un agent, renvoie la réponse | `agent_routing`, `channels`, `exec_client`, `discord_inbox` | service `boa-channel-discord` |
| `discord_inbox` | `backend/core/discord_inbox.py` | Les deux mêmes tables pour Discord. Séparées de celles de Telegram : un snowflake est une chaîne, et un écouteur ne doit pas pouvoir répondre aux questions de l'autre. L'expiration est calculée en UTC | `db` | `discord_listener`, `agent_api` |
| `discord_markdown` | `backend/core/discord_markdown.py` | Le Markdown converti en ce qu'affiche Discord, coupé en messages de 2000 caractères. Les tableaux deviennent des blocs délimités ; un bloc dans lequel tombe une coupure est fermé puis rouvert | `telegram_html` (les motifs de blocs) | `channels` |
| `discord_texts` | `backend/core/discord_texts.py` | Les trois phrases que Discord dit autrement. Tout le reste retombe sur `telegram_texts`, si bien qu'un seul catalogue sert les deux bots | `telegram_texts` | `discord_listener` |
| `browser` | `backend/core/browser.py` | Le navigateur partagé et le profil propre à cet agent. Une poignée pour la durée d'une exécution, fermée par `atexit`. Porte la politique réseau par laquelle passe chaque requête | `paths`, `public_url` | les cinq outils `browser.*` |
| `telegram_html` | `backend/core/telegram_html.py` | Le Markdown converti dans les quatorze balises qu'accepte Telegram. Mêmes motifs que `markdown.js`, pour que les deux moteurs de rendu s'accordent sur ce qu'est le markdown | — | `channels` |
| `telegram_texts` | `backend/core/telegram_texts.py` | Ce que le bot dit lui-même, dans la langue choisie pour l'installation | `db` | `telegram_listener` |
| `markdown.js` | `frontend/static/js/markdown.js` | Affiche la réponse d'un agent sous forme de nœuds DOM, jamais de balisage | — | `dashboard.js` |
| `jsonhighlight.js` | `frontend/static/js/jsonhighlight.js` | Met en forme du JSON brut sans arrondir les nombres et le colore avec des nœuds DOM sûrs | — | `api_doc.html`, `dashboard.html` |
| `themes` | `backend/core/themes.py` | Liste les feuilles de style de `frontend/themes/` et lit leurs en-têtes | `paths` | `web/api`, `web/views` |
| `agent_templates` | `backend/core/agent_templates.py` | Télécharge le dépôt de modèles (réglages `templates_repo_url`, `templates_repo_branch`) en un seul `.tar.gz`, le met en cache cinq minutes et liste ou lit ses modèles | `agent_package`, `db` | `web/api` |
| `agent_package` | `backend/core/agent_package.py` | La forme portable d'un agent : lit un `.zip`, une archive de dépôt ou un dossier, et vérifie tout avant qu'un agent n'existe | `agent_home`, `agents`, `memory`, `rag_settings`, `rag_store`, `skills` | `agent_templates`, `agent_io` |
| `agent_io` | `backend/core/agent_io.py` | Installe un paquet, exécute les importations de `.zip` en arrière-plan avec `job.json`, envoie les exportations en flux | `agent_package`, `exec_client`, `tool_registry` | `web/api`, `web/agent_io_api` |
| `agent_home` | `backend/core/agent_home.py` | Liste, lit et écrit les fichiers du répertoire personnel d'un agent en tant qu'agent ; le verbe `agent_home` de l'exécuteur | `paths` | `exec_daemon`, `agent_package` |
| `agent_io_api` | `backend/web/agent_io_api.py` | `/agent-imports/...` et `/agents/<id>/export...` | `agent_io` | `server` |
| `agent_export.js` | `frontend/static/js/agent_export.js` | L'onglet Exporter : ce qu'ajoute chaque option, et le lien de téléchargement | `api.js` | `dashboard.html` |
| `mailbox` | `backend/core/mailbox.py` | IMAP et SMTP pour la boîte aux lettres configurée. Détient les identifiants pour que les agents ne les détiennent jamais. Désigne un message par son UID et son UIDVALIDITY, jamais par sa position dans le dossier | `db` | `agent_api` |
| `theme.js` | `frontend/static/js/theme.js` | Ajoute la feuille de style du thème choisi, depuis le head, avant le premier affichage | — | chaque page |
| `night-high-contrast.css` | `frontend/themes/night-high-contrast.css` | Remplit de gris l'agent sélectionné et dessine les onglets sélectionnés avec un contour fermé raccordé à la ligne de base | `app.css` | `theme.js` |
| `settings.js` | `frontend/static/js/settings.js` | Charge les onglets principaux des réglages avec des sélecteurs limités à leur propre barre d'onglets ; `fRenderChannelForms` marque les canaux configurés avec `data-state="good"`, en partageant le style d'état des clés d'API et le `--colour-ok` du thème | `api.js`, `i18n.js`, `tools.js`, `app.css` | `settings.html` |
| `tools.js` | `frontend/static/js/tools.js` | Charge le catalogue dans Réglages → Outils ; garde le sous-onglet dans le paramètre `family` de l'URL et rafraîchit ses libellés au retour depuis Interface | `api.js`, `i18n.js` | `settings.js`, `settings_tools.html` |
| `app.css` | `frontend/static/css/app.css` | La classe `system-table` partage une mise en page à deux colonnes, avec 35 % pour les libellés, pour que les valeurs de la machine et les états des services s'alignent ; `.chat-attachment img` remplit 100 % de la largeur du texte avec une hauteur automatique et non plafonnée ; `.chat-audio` s'adapte à la largeur du message et son titre hérite de la couleur du texte du message | — | `settings.html`, `dashboard.html` |
| `system_info` | `backend/core/system_info.py` | État de la machine et noms des services pour le système d'init en cours | `paths` | `web/api`, `agent_routing` |
| `samba` | `backend/core/samba.py` | Cycle de vie des partages, validation, identifiants natifs, dossiers protégés et sauvegardes | `agents`, `paths`, commandes Samba | `exec_daemon`, installateurs |
| `samba.js` | `frontend/static/js/samba.js` | Formulaire Samba chargé à la demande, saisie secrète et instantané par agent | `api.js`, `dashboard.js` | `dashboard.html` |

---

## 3. Index des symboles clés

Seulement les symboles publics et porteurs. Les numéros de ligne bougent ; le
fichier et le comportement sont ce à quoi il faut se fier.

### Chemins et identité

| Symbole | Fichier:ligne | Ce qu'il fait |
|---|---|---|
| `fNormalizeAgentId` | `backend/core/paths.py:164` | Valide un identifiant d'agent et le complète par des zéros. **Chaque chemin construit à partir d'une entrée utilisateur passe par là.** Lève une exception pour tout ce qui sort de 0–999 |
| `fGetAgentHome` | `backend/core/paths.py:179` | `/opt/boa/agents/xxx` |
| `fReadAgentOwnedFile` | `backend/core/paths.py:401` | Comment root lit un fichier du répertoire personnel d'un agent : sur le descripteur ouvert, ordinaire et appartenant à l'agent ou refusé, jamais au-delà d'une borne. Le journal, la conversation et la mémoire passent tous par là |
| `fGetAgentApiTokenPath` | `backend/core/paths.py:485` | Où vit le jeton d'API d'un agent |

### Agents

| Symbole | Fichier:ligne | Ce qu'il fait |
|---|---|---|
| `fValidateAgentName` | `backend/core/agents.py:71` | 2 à 40 caractères, aucun métacaractère de shell |
| `fGetNextFreeAgentId` | `backend/core/agents.py:137` | Le plus petit identifiant libre d'après le système de fichiers, à partir de 001 |
| `fBuildAgentInfo` | `backend/core/agents.py:150` | L'`info.json` d'un nouvel agent, avec des valeurs par défaut prudentes |
| `fWriteAgentInfo` | `backend/core/agents.py:219` | Écriture atomique qui préserve la propriété en 0600 |
| `fHashApiToken` | `backend/core/agents.py:256` | SHA-256 ; le jeton brut n'est jamais stocké |
| `fFindAgentByApiToken` | `backend/core/agents.py:301` | Transforme un jeton en identité |

### Le démon privilégié

| Symbole | Fichier:ligne | Ce qu'il fait |
|---|---|---|
| `fIsPeerAllowed` | `backend/core/exec_daemon.py:106` | Seulement root et `boa`, vérifié à chaque connexion |
| `fRunPrivilegedCommand` | `backend/core/exec_daemon.py:122` | Exécute une liste de commande sans shell, éventuellement en tant qu'un autre utilisateur |
| `fVerbCreateAgent` | `backend/core/exec_daemon.py:396` | Crée l'utilisateur, le répertoire personnel, la configuration, le jeton ; applique les outils, les limites, l'interrupteur et les réglages `rag` validés d'un modèle ; **revient en arrière à la moindre erreur** |
| `fStartRunner` | `backend/core/exec_daemon.py:304` | Le seul endroit où un runner est lancé en tant qu'agent. Le message de conversation ou le prompt de la carte passe par son entrée standard, jamais par la ligne de commande |
| `fWatchRunner` | `backend/core/exec_daemon.py:255` | Attend une exécution : arrête son scope, et consigne la fin d'une exécution qui a été tuée |
| `fVerbWriteCrontab` | `backend/core/exec_daemon.py:780` | Installe un crontab sous l'utilisateur propre à l'agent |
| `fListRunningAgentIds` | `backend/core/exec_daemon.py` | Un seul balayage de `/proc` qui nomme chaque agent ayant une exécution en cours. Sert de base à la fois à `only_if_idle` et à l'anneau tournant de la barre latérale |
| `dVerbHandlers` | `backend/core/exec_daemon.py` | La table fermée des verbes. Toute la surface privilégiée tient dans ces dix lignes |

### L'API des agents

| Symbole | Fichier:ligne | Ce qu'il fait |
|---|---|---|
| `fAuthenticate` | `backend/core/agent_api.py:121` | Le jeton **et** `SO_PEERCRED` doivent concorder |
| `fAgentMayUseKanban` | `backend/core/agent_api.py` | Si le tableau est activé et que l'agent détient au moins un outil kanban. La moitié grossière |
| `fRequireKanbanTool` | `backend/core/agent_api.py` | Un verbe, un outil, par son nom. Chaque gestionnaire posait autrefois la question grossière, si bien que `kanban.list_cards` - une lecture - atteignait `fDeleteCard` pour un agent qui plaçait lui-même la requête sur la socket |
| `fRequireOwnCard` | `backend/core/agent_api.py:283` | Un agent ne peut modifier que les cartes qu'il a créées ou qu'il possède |
| `fVerbChannelWrite` | `backend/core/agent_api.py` | Envoie au nom de l'agent, en préfixant son vrai nom |

### La boucle d'exécution

| Symbole | Fichier:ligne | Ce qu'il fait |
|---|---|---|
| `AgentRun` | `backend/core/runner.py:336` | Une conversation bornée |
| `fCheckCeilings` | `backend/core/runner.py` | Renvoie le plafond qui a arrêté l'exécution, ou une valeur vide pour continuer |
| `fSecondsLeft` | `backend/core/runner.py` | Le temps restant avant l'échéance de l'exécution, sur une horloge monotone. Chaque appel au fournisseur et chaque outil reçoit ce qui reste, pas tout le plafond |
| `fTakeRunLock` | `backend/core/runner.py` | Un flock sur `<home>/run.lock`, tenu pendant toute la durée du processus. La seule vérification que fait aussi une exécution lancée par cron |
| `fTrimToByteBudget` | `backend/core/exec_protocol.py` | Les entrées les plus récentes qui tiennent dans un budget d'octets, et combien ont été écartées. Compté en octets, parce qu'un nombre de lignes n'est pas une taille |
| `fRunWithLimits` | `backend/tools/bash_run.py` | Exécute une commande avec un plafond d'octets appliqué PENDANT qu'elle produit sa sortie, et une échéance qui tue tout le groupe de processus |
| `fAskForClosingAnswer` | `backend/core/runner.py` | Après un plafond, demande une fois, sans outils, la réponse qu'il a été empêché de donner |
| `fExecute` | `backend/core/runner.py:503` | La boucle : demander, exécuter les outils, renvoyer le résultat, s'arrêter |
| `fSelectAllowedTools` | `backend/core/runner.py:319` | Retient les outils kanban quand l'agent les a désactivés |
| `fReadStdinArguments` | `backend/core/runner.py:988` | La moitié runner de cela : lit le texte sur l'entrée standard, de façon bornée, et refuse un message de conversation vide |
| `fApplyResourceLimits` | `backend/core/runner.py:1069` | Abaisse les propres limites noyau de l'exécution avant que quoi que ce soit ne soit lancé : processus, fichiers core, taille des fichiers |
| `fRecordChatAnswer` | `backend/core/runner.py` | Écrit la réponse quand l'exécution a un tour à clore (`vWritesToChat`) |
| `fRecordChatFailure` | `backend/core/runner.py` | Clôt le tour quand rien d'autre ne le fera, en nommant la raison pour que l'interface puisse la traduire |
| `fAppendCardMessage` | `backend/core/chat.py` | Annonce une carte arrivée à échéance comme un tour à part entière, avec les champs de la carte et aucune phrase |
| `fBuildCardAnnouncement` | `backend/core/buzzer.py` | Ce qu'on dit à la conversation : qui l'a attribuée, et si elle a été demandée pour maintenant |

### Outils

| Symbole | Fichier:ligne | Ce qu'il fait |
|---|---|---|
| `fGetContext` | `backend/core/browser.py` | Démarre le navigateur sur le profil de cet agent, ou renvoie celui qui tourne déjà |
| `fClose` | `backend/core/browser.py` | Enregistré avec `atexit`. Sans lui, chaque exécution laisse un Chromium derrière elle |
| `fIsInstalled` | `backend/core/browser.py` | S'il y a un navigateur à piloter, pour que les outils puissent dire quoi lancer au lieu de lever une exception |
| `fLoadAllTools` | `backend/core/tool_registry.py:105` | Charge chaque outil valide ; un fichier cassé est ignoré, pas fatal |
| `fRunTool` | `backend/core/tool_registry.py:138` | Applique la permission, renvoie `(text, is_error)` ; un outil qui lève une exception ne tue jamais une exécution |
| `fGetLimit` | `backend/core/memory.py:53` | Lit la limite de mémoire protégée de chaque agent, avec la valeur par défaut historique |
| `fValidateContent` | `backend/core/memory.py:71` | Rejette une mémoire trop grande sans jeter de texte |
| `fCheckMemoryUpdate` | `backend/web/api.py:127` | Valide la mémoire et la limite proposée avant toute écriture des réglages |
| `fSearch` | `backend/core/rag_search.py:123` | Recherche hybride avec références aux sources |
| `fPrompt` | `backend/core/rag_search.py:243` | Les passages récupérés et la règle du mode de réponse, ajoutés au prompt système |
| `fVerify` | `backend/core/rag_verify.py:235` | Les unités sans citation récupérée ou qui ne ressemblent pas à ce qu'elles citent : renvoie le texte gardé et ce qui a été retiré |
| `fSplitUnits` | `backend/core/rag_verify.py:163` | Découpe une réponse en paragraphes et éléments de liste, en gardant ce qu'il faut pour la reconstruire |
| `fCheckRagAnswer` | `backend/core/runner.py:681` | Renvoie une fois une réponse finale : pas encore de recherche (documental, verified) ou paragraphes non appuyés (verified) |
| `fFinishRagAnswer` | `backend/core/runner.py:704` | Ce qu'on montre à l'utilisateur : phrase fixe s'il n'y a pas de passages, paragraphes non appuyés retirés, réponse retenue quand elle ne peut pas être vérifiée |
| `fIndexDocument` | `backend/core/rag_worker.py:32` | Extrait, vectorise et publie une révision ; `False` quand une panne du moteur l'a remise en file |
| `fWork` | `backend/core/rag_worker.py:129` | Lot d'indexation borné ; attend sans extraire tant que le moteur est arrêté |
| `EngineUnavailable` | `backend/core/rag_embeddings.py:11` | Panne du moteur (échec de la socket ou 503), distinguée d'une requête refusée |
| `fIsAvailable` | `backend/core/rag_embeddings.py:73` | Sonde peu coûteuse que le worker lance avant chaque document : le moteur répond, et avec le modèle en usage |
| `fCheckServedModel` | `backend/core/rag_embeddings.py:68` | `EngineUnavailable` sauf si le `/v1/models` du moteur nomme le modèle attendu |
| `fSelectedModel` | `backend/core/rag_settings.py:39` | L'entrée du catalogue choisie dans Réglages → RAG, celle par défaut quand aucune n'est enregistrée ou qu'une inconnue l'est |
| `fInstallModel` | `backend/core/rag_runtime.py:76` | Télécharge un modèle dans un fichier privé et ne le nomme qu'une fois que sa taille et son SHA-256 correspondent |
| `fStartModelDownload` | `backend/core/rag_runtime.py:125` | Met un téléchargement en file dans l'exécuteur et renvoie aussitôt son état |
| `fFollowModelSimilarity` | `backend/core/rag_exec.py:113` | Lors d'un changement de modèle, fait passer les agents encore sur l'ancien `min_similarity` recommandé au nouveau |
| `fFollowNewModel` | `backend/core/rag_worker.py:107` | Remet en file ce qu'un autre modèle a indexé, en gardant les révisions publiées consultables par mots |
| `fMigrate` | `backend/core/rag_store.py:83` | Ajoute à chaque connexion les `lAddedColumns` absentes des catalogues plus anciens (`year`, `subtitle`) |
| `fAction` | `backend/core/rag_store.py:270` | Informations du document, réindexation, annulation et suppression ; valide les clés des métadonnées et l'année |
| `fSnapshot` | `backend/core/rag_store.py:334` | Sauvegarde cohérente des documents et de l'index |
| `ToolContext` | `backend/core/tool_registry.py:53` | Ce qu'on dit à un outil sur celui qui l'appelle |
| `fStoreImage` | `backend/core/attachments.py` | Copie un PNG du répertoire personnel de l'agent dans un instantané privé |
| `fReadImageChunk` | `backend/core/attachments.py` | Lit au plus 1 Mio, en refusant les liens symboliques, les autres propriétaires et les fichiers spéciaux |
| `fVerbReadChatAttachment` | `backend/core/exec_daemon.py` | Exige une référence de pièce jointe dans la conversation de l'agent demandé avant de lire |
| `fGetChatAttachment` | `backend/web/api.py` | Envoie en flux le PNG à un utilisateur connecté, sans URL de fichier publique ni mise en cache |
| `fRenderChatAttachments` | `frontend/static/js/dashboard.js` | Affiche les images de la réponse, et une erreur quand une image ne peut pas être chargée |
| `fSetComposerEnabled` | `frontend/static/js/dashboard.js` | Ouvre ou ferme la zone de message et écrit la seconde ligne du texte indicatif : comment se comporte Entrée, ou le fait que l'agent travaille |
| `fFitChatInputToPlaceholder` | `frontend/static/js/dashboard.js` | Agrandit la zone de texte jusqu'à ce que tout son texte indicatif tienne, mesuré sur un jumeau invisible |
| `fTrackStatusBarHeight` | `frontend/static/js/api.js` | Maintient `--status-bar-live-height` égal à la hauteur réelle de la barre d'état, que soustrait la mise en page de la conversation sur téléphone |
| `fDeliverAnswerParts` | `backend/core/telegram_listener.py` | Reprend la livraison Telegram à partir de la dernière partie de texte ou d'image acquittée |

### Compétences

| Symbole | Fichier:ligne | Ce qu'il fait |
|---|---|---|
| `fIsValidSkillName` | `backend/core/skills.py:57` | Un nom, jamais un chemin. Refuse plutôt que de nettoyer, comme pour les noms de modèles et de thèmes |
| `fParseSkill` | `backend/core/skills.py:77` | L'en-tête `---` et le corps |
| `fSelectInstalledSkills` | `backend/core/skills.py:194` | Les noms de la liste d'un agent qui existent encore sur le disque. **Chaque chemin d'accès à la fonctionnalité passe par là**, si bien qu'une compétence supprimée n'atteint jamais un prompt |
| `fBuildPromptSection` | `backend/core/skills.py:211` | L'index : une ligne par compétence, noms et descriptions seulement. `""` quand l'agent n'en a aucune |
| `fRunTool` | `backend/tools/skill_read.py` | Renvoie un corps, vérifié contre le propre `info.json` de l'agent |


### Telegram, dans les deux sens

| Symbole | Fichier:ligne | Ce qu'il fait |
|---|---|---|
| `fReadTelegramUpdates` | `backend/core/channels.py` | Un long poll. La connexion est établie vers l'extérieur, ce qui permet à cela de fonctionner derrière un NAT sans rien de redirigé |
| `fSendToTelegram` | `backend/core/channels.py` | Envoie, et renvoie le `message_id` - la seule chose qui permet d'acheminer une réponse ultérieure |
| `fRedactSecrets` | `backend/core/channels.py` | Retire chaque identifiant d'une erreur ou d'une ligne de log. `str(RequestException)` cite l'URL, et pour trois des quatre canaux l'URL **est** l'identifiant |
| `fReadConfigForEditing` | `backend/core/channels.py` | Le fichier d'un canal tel qu'il est sur le disque, pour qu'enregistrer une modification fusionne au lieu de remplacer |
| `fListConfiguredChannels` | `backend/core/channels.py` | Renvoie Discord, Mattermost, Telegram et X par ordre alphabétique, avec leur état et sans secrets ; utilisé par les Réglages et par les permissions de chaque agent |
| `fRouteMessage` | `backend/core/telegram_listener.py` | À qui s'adresse un message : l'agent auquel on répond, ou celui nommé avec @ |
| `fMatchNamedAgent` | `backend/core/telegram_listener.py` | Correspondance la plus longue sur chaque nom connu, parce que les noms d'agents peuvent contenir des espaces |
| `fIsFromTheConfiguredChat` | `backend/core/telegram_listener.py` | **Toute l'autorisation.** Tout ce qui vient d'une autre conversation est abandonné sans réponse |
| `fDeliverAnswers` | `backend/core/telegram_listener.py` | Renvoie chaque tour qui s'est clos depuis le passage précédent |
| `fRememberMessage` | `backend/core/telegram_inbox.py` | Relie un message envoyé à l'agent qui l'a envoyé, élagué aux quelques centaines derniers |
| `fRouteMessage` | `backend/core/telegram_listener.py` | À qui s'adresse un message : l'agent auquel on répond, celui nommé avec @ ou /, ou celui sélectionné |
| `fReadSelectedAgent` | `backend/core/telegram_listener.py` | Avec qui se tient la conversation, vérifié contre la liste des agents pour qu'un agent supprimé cesse de tout intercepter |
| `fBuildAgentButtons` | `backend/core/telegram_listener.py` | Le clavier inline par lequel répond /agents. Le texte d'un bouton est au choix du bot, ce qui n'est pas le cas de celui du menu des commandes |
| `fBuildStatusReport` | `backend/core/telegram_listener.py` | Ce que dit /status. Un agent qu'il ne peut pas lire est listé en le disant, jamais omis |
| `fHandleCallback` | `backend/core/telegram_listener.py` | Un appui sur un bouton d'agent : on y répond d'abord, puis l'agent est sélectionné |
| `fRender` | `backend/core/telegram_html.py` | Du Markdown vers le HTML de Telegram. Les titres deviennent du gras, les listes des puces, les tableaux un bloc à chasse fixe - Telegram n'a de balise pour aucun des trois |
| `fEscape` | `backend/core/telegram_html.py` | `&`, `<`, `>`. **Appelé avant que quoi que ce soit n'enveloppe le texte**, jamais après |
| `fEscapeAttribute` | `backend/core/telegram_html.py` | La même chose plus le guillemet double, pour un href. Un guillemet dans une URL fermerait sinon l'attribut et inventerait ceux qui suivent |
| `fRenderWithinLimit` | `backend/core/telegram_html.py` | Raccourcit le markdown et refait le rendu jusqu'à ce que le HTML tienne. Couper le HTML à la place laisserait une balise à moitié écrite |

### Discord, dans les deux sens

| Symbole | Fichier:ligne | Ce qu'il fait |
|---|---|---|
| `fReadDiscordMessages` | `backend/core/channels.py` | Une interrogation. **Inverse ce que renvoie Discord**, qui met le plus récent en premier : répondre dans cet ordre ferait lire à l'agent une conversation à l'envers |
| `fSendToDiscord` | `backend/core/channels.py` | Envoie, en autant de parties que l'exige la limite de 2000 caractères, et renvoie l'identifiant de chaque partie |
| `fCallDiscord` | `backend/core/channels.py` | Un appel. Un 429 avec un `retry_after` court est attendu une fois ; tout autre 4xx est `ChannelRejected` |
| `fGetDiscordMode` | `backend/core/channels.py` | `"bot"`, `"hook"` ou `""`. Un webhook envoie et rien d'autre |
| `fReadDiscordBotUser` | `backend/core/channels.py` | Quel bot c'est, écrit dans le log une fois par démarrage : quand rien n'arrive, c'est la première question |
| `fRenderToMessages` | `backend/core/discord_markdown.py` | Une réponse sous la forme de la liste des messages à envoyer pour elle |
| `fSplit` | `backend/core/discord_markdown.py` | Coupe entre les lignes, en fermant et en rouvrant un bloc délimité dans lequel tombe la coupure |
| `fIsFromTheConfiguredChannel` | `backend/core/discord_listener.py` | Chaque message interrogé vient de ce canal par construction ; vérifié quand même, parce que « par construction » est une propriété du code d'aujourd'hui |
| `fReadCommand` | `backend/core/discord_listener.py` | `!agents`, `!status`, `!help`, et les formes en `/`. Seulement comme premier mot entier, sinon un agent appelé `status` serait injoignable |
| `fReadMessageText` | `backend/core/discord_listener.py` | Le texte, débarrassé en tête d'une mention du bot : Discord transforme `@Boa` en `<@123>` avant que quiconque d'autre ne le voie |
| `fStartFromTheNewestMessage` | `backend/core/discord_listener.py` | Là où commence une installation neuve. Un bot activé cet après-midi ne doit pas répondre à un mois de canal |
| `fReadAfterId` / `fWriteAfterId` | `backend/core/discord_listener.py` | La marque, dans `config/discord-after`. Un snowflake, pas un compteur |
| `fRememberMessage` | `backend/core/discord_inbox.py` | Relie une partie envoyée à l'agent qui l'a envoyée. Élagué par ordre d'insertion, pas par identifiant |

### Partagé par les deux écouteurs

| Symbole | Fichier:ligne | Ce qu'il fait |
|---|---|---|
| `fMatchNamedAgent` | `backend/core/agent_routing.py` | Correspondance la plus longue sur chaque nom connu. Les préfixes sont un argument : Telegram prend `@` et `/`, Discord ajoute `!` |
| `fBuildStatusReport` | `backend/core/agent_routing.py` | Ce que dit /status. Prend le catalogue du service qui pose la question et son propre nom d'unité, les deux seules choses qui diffèrent ; résout le nom du service du canal pour systemd ou OpenRC |
| `fFindClosedAnswer` | `backend/core/agent_routing.py` | Ce qu'un agent a dit pour clore un tour, lu par l'intermédiaire de l'exécuteur |
| `fListAgentNames` | `backend/core/agent_routing.py` | La liste des agents, depuis l'index : le répertoire personnel d'un agent est en 0700 et son info.json n'est pas à un écouteur d'ouvrir |

### Scripts et cron propres à un agent

| Symbole | Fichier:ligne | Ce qu'il fait |
|---|---|---|
| `fValidateScriptName` | `backend/core/agent_scripts.py` | Vérifie un nom plutôt que de le nettoyer : tout ce qui n'est pas un simple nom de fichier est refusé, ce qui fait une règle au lieu d'une règle plus ce que le nettoyage finit par faire |
| `fValidateSchedule` | `backend/core/agent_scripts.py` | La forme d'un horaire cron, et la seule chose qui vaille la peine d'être refusée : une tâche qui se déclenche plus souvent que ce que quiconque voulait |
| `fIsRunnerLine` | `backend/core/agent_scripts.py` | La ligne qui réveille l'agent. Jamais réécrite d'ici : un agent qui la supprimerait se tairait pour toujours sans aucun moyen de s'en apercevoir |
| `fAddCronLine` | `backend/core/agent_scripts.py` | Ajoute une ligne qui lance l'un des propres scripts de l'agent. Le script doit exister d'abord |
| `fRemoveCronLines` | `backend/core/agent_scripts.py` | Retire chaque ligne qui lance un script, et le commentaire au-dessus de chacune |

### Tableau et canaux

| Symbole | Fichier:ligne | Ce qu'il fait |
|---|---|---|
| `fAddCard` | `backend/core/kanban.py:132` | La carte et le premier événement dans une seule transaction |
| `fMoveCard` | `backend/core/kanban.py:188` | Déplacement plus événement d'historique |
| `fValidateRunAt` | `backend/core/kanban.py:68` | Accepte `"now"`, une heure du navigateur ou une heure stockée, et normalise les trois |
| `fReadRunMode` | `backend/core/kanban.py:100` | Quel type d'heure a été demandé : `now`, `at`, ou aucun |
| `fWasRequestedImmediately` | `backend/core/kanban.py` | Si la carte disait « maintenant ». Lu dans `run_mode`, jamais déduit de l'horloge |
| `fAssignCard` | `backend/core/kanban.py` | Remet une carte, en consignant dans `assigned_by` qui l'a remise |
| `fAgentOwnsCard` | `backend/core/kanban.py:462` | Créateur **ou** attributaire |
| `fDeleteCard` | `backend/core/kanban.py:480` | Supprime, en gardant une ligne dans `deleted_cards` |
| `fReadMessages` | `backend/core/mailbox.py` | Les messages les plus récents d'un dossier, en lecture seule : rien n'est marqué comme lu |
| `_fParseFolderLine` | `backend/core/mailbox.py` | Une ligne LIST sous forme d'indicateurs, de délimiteur et de nom. Lève une exception plutôt que de deviner : une liste illisible est une erreur, pas un compte sans dossiers |
| `fListFoldersWithFlags` | `backend/core/mailbox.py` | Chaque dossier avec ses indicateurs SPECIAL-USE |
| `fFindTrashFolder` | `backend/core/mailbox.py` | `\\Trash` d'abord, puis les noms en neuf langues. `""` signifie qu'il n'y en a pas ; un échec lève une exception |
| `fIsForwardAllowed` | `backend/core/mailbox.py` | Si une adresse figure sur la liste de l'utilisateur. Vérifié là où se trouve le mot de passe, jamais dans un prompt |
| `fListTemplates` | `backend/core/agent_templates.py:134` | Chaque modèle du dépôt, résumé, sous le nom que voit l'utilisateur ; un modèle cassé avec son erreur |
| `fReadTemplate` | `backend/core/agent_templates.py:151` | La source et le paquet vérifié d'un modèle, ou None ; refuse avant de télécharger un nom qui n'est pas un simple identifiant |
| `fReadPackage` | `backend/core/agent_package.py:418` | Vérifie un paquet entier - noms, agent.json, prompt, mémoire, chemins du répertoire personnel, bibliothèque - et le décrit |
| `fValidateManifest` | `backend/core/agent_package.py:317` | agent.json : clés connues seulement, format 1, horaires, outils installés ici, limites, rag, fournisseur sans clé |
| `ZipSource` | `backend/core/agent_package.py:84` | Un `.zip` : refuse les noms qui remontent, les liens, le chiffrement, les membres à 200:1 et plus de 8 Gio |
| `fReadRepositoryArchive` | `backend/core/agent_package.py:236` | Découpe le `.tar.gz` d'un dépôt en dossiers de modèles ; ignore les liens |
| `fInstallPackage` | `backend/core/agent_io.py:60` | Crée l'agent éteint, puis sa mémoire, les fichiers de son répertoire personnel et sa bibliothèque ; le supprime de nouveau en cas d'échec |
| `fStartImport` | `backend/core/agent_io.py:265` | Lance l'installation d'un `.zip` vérifié dans un thread, une seule fois, quel que soit le nombre de clics |
| `fExportAgent` | `backend/core/agent_io.py:420` | Produit le `.zip` pendant qu'il est écrit ; répertoire personnel et bibliothèque envoyés en flux |
| `fReadSchedules` | `backend/core/agent_io.py:320` | Seulement les lignes du crontab qui lancent l'agent, sous forme de cinq champs |
| `fValidateSchedule` | `backend/core/agents.py:85` | Cinq champs cron, une ligne, rien qui puisse être une commande |
| `fList` | `backend/core/agent_home.py:86` | Les fichiers du répertoire personnel qu'un paquet peut porter, en tant qu'agent, en excluant ceux du système et les fichiers cachés |
| `fWrite` | `backend/core/agent_home.py:130` | Écrit un bloc dans l'ordre, sans passer par aucun lien, en mode réservé au propriétaire |
| `fBroker` | `backend/core/agent_home.py:170` | Exécute une opération sur le répertoire personnel en tant qu'agent ; le verbe `agent_home` de l'exécuteur |
| `fChooseAgentSource` | `frontend/static/js/api.js` | La boîte de dialogue du + : agent vide, .zip ou modèle |
| `fImportAgentZip` | `frontend/static/js/api.js` | Envoi par blocs, vérification, affichage, confirmation, installation, interrogation |
| `fLoadExportPreview` | `frontend/static/js/agent_export.js` | Ce qu'ajouterait chaque option d'exportation, demandé à chaque ouverture de l'onglet |
| `fSource` | `backend/core/rag_search.py:88` | Un passage tel que le voient le modèle et les citations : ref, emplacement, titre, sous-titre, année, auteur, version, langue, texte, lien |

### La barre latérale

| Symbole | Fichier:ligne | Ce qu'il fait |
|---|---|---|
| `fRenderSidebar` | `frontend/static/js/api.js` | Reconstruit la liste des agents. Appelé au chargement de la page et après une création ou une suppression, jamais sur une minuterie |
| `fPickDifferentModel` | `frontend/static/js/dashboard.js` | Le modèle à remplir quand un fournisseur est choisi. Le modèle de secours évite celui du principal : même fournisseur et même modèle échouent pour la même raison, à chaque fois |
| `fSetAgentAvatarActivity` | `frontend/static/js/api.js` | Pose `data-running` et l'infobulle sur un avatar, et ajoute ou retire l'arc |
| `fBuildAgentActivityArc` | `frontend/static/js/api.js` | Le rectangle arrondi SVG posé sur la bordure, `pathLength="100"` pour que la feuille de style puisse parler en pourcentages du périmètre |
| `fRefreshAgentActivity` | `frontend/static/js/api.js` | Toutes les 5 s, ne repeint que les anneaux ; sauté tant que l'onglet est masqué |
| `fDescribeChannelName` / `fDescribeProviderName` | `frontend/static/js/api.js` | Le nom sous lequel un canal ou un fournisseur s'écrit lui-même. Pas de clés i18n : DeepSeek est DeepSeek dans toutes les langues |
| `fDescribeTool` / `fDescribeToolArgument` | `frontend/static/js/api.js` | Ce que disent un outil et ses arguments, dans la langue du lecteur. Le schéma reste en anglais : c'est ce qu'on envoie au modèle |
| `fRenderToolCheckboxes` | `frontend/static/js/dashboard.js` | Une case par famille d'outils, construite à partir de ce qui est installé. Déplace l'interrupteur kanban dans la case kanban au lieu de le reconstruire, pour qu'une coche faite et pas encore enregistrée survive au redessin |

### Messages contextuels

| Symbole | Fichier:ligne | Ce qu'il fait |
|---|---|---|
| `fShowNotice` | `frontend/static/js/api.js` | Place un message sur la couche au-dessus de la colonne de contenu. Remplace ce qui s'y trouvait, si bien que les confirmations ne s'empilent jamais |
| `fShowError` | `frontend/static/js/api.js` | La même chose, en tant qu'erreur : pas de minuterie, fermé à la main |
| `fConfirmLogout` | `frontend/static/js/api.js` | Ouvre `fConfirm` au centre de l'écran ; ne navigue vers `/logout` qu'après confirmation. Annuler et Échap gardent la session ouverte |
| `fHideNotice` | `frontend/static/js/api.js` | Fait disparaître un message en fondu puis le retire, pour qu'il ne s'évanouisse pas d'un coup quand la minuterie arrive à zéro |
| `fGetNoticeSeconds` / `fSetNoticeSeconds` | `frontend/static/js/api.js` | Combien de temps reste un message, gardé dans ce navigateur et borné entre 1 et 30 secondes |
| `fBuildCloseCross` | `frontend/static/js/api.js` | La croix de fermeture sous forme de deux lignes SVG. Un caractère `×` est centré sur l'axe mathématique de la police plutôt que dans sa propre boîte, si bien qu'il se place au-dessus du milieu du bouton quoi que fasse le bouton |

### Coloration du JSON

| Symbole | Fichier:ligne | Ce qu'il fait |
|---|---|---|
| `cJsonTokenPattern` | `frontend/static/js/jsonhighlight.js` | Une seule expression pour les quatre sortes de jetons. Une chaîne suivie de deux-points est une clé, ce qui est la seule chose qui distingue un nom d'une valeur |
| `fHighlightJsonElement` | `frontend/static/js/jsonhighlight.js` | Reconstruit un bloc en spans colorés et en texte simple. Chaque caractère de l'original est émis exactement une fois, si bien que le bloc se copie toujours en JSON valide |

### Fournisseurs

| Symbole | Fichier:ligne | Ce qu'il fait |
|---|---|---|
| `BaseProvider.fSendMessages` | `backend/providers/base.py` | La seule méthode que chaque adaptateur implémente |
| `fNeutralMessagesToOpenAiFormat` | `backend/providers/base.py` | Forme neutre → chat/completions |
| `fToolNameToWire` / `fToolNameFromWire` | `backend/providers/base.py` | `family.action` ↔ `family__action`, parce qu'aucun fournisseur n'accepte le point |
| `fDescribeHttpError` | `backend/providers/base.py` | Ajoute ce qu'a dit le fournisseur à un simple échec HTTP |
| `fBuildProvider` | `backend/providers/factory.py` | Configuration → instance d'adaptateur, avec import paresseux |
| `fResolveProviderName` | `backend/providers/factory.py` | Suit les alias, si bien que `gemini` et `google` atteignent un même adaptateur |
| `fSendChatCompletion` | `backend/providers/openai_dialect.py` | La requête chat/completions partagée, paramétrée par les particularités de chaque adaptateur |
| `fNormalizeMessageContent` | `backend/providers/openai_dialect.py` | Aplatit une réponse dont le contenu est arrivé en blocs, en laissant tomber le raisonnement |

---

### Symboles audio

| Symbole | Fichier:ligne | Responsabilité |
|---|---|---|
| `fTranscribe` | `backend/core/audio_transcription.py:223` | Décoder, segmenter et transcrire |
| `fEnqueueTelegram` | `backend/core/audio_inbox.py:57` | Conserver la destination avant la transcription |
| `fRunOneJob` | `backend/core/audio_inbox.py:233` | Traiter ou retenter un tour réservé |
| `fDownloadModel` | `backend/core/whisper_runtime.py:134` | Valider la taille et le SHA-256 avant la publication |
| `fGetChatAudio` | `backend/web/api.py:571` | Servir l'audio après les vérifications de session et de référence de conversation |

### API Calls

| Symbole | Fichier | Responsabilité |
|---|---|---|
| `fRecordCall` | `backend/core/api_calls.py` | Conserve un corps sortant complet avant l'envoi |
| `fReadBodyChunk` | `backend/core/api_calls.py` | Lit une partie bornée d'un fichier d'agent validé |
| `fSelectConversationTab` | `frontend/static/js/dashboard.js` | Bascule entre Conversation et API Calls, et leurs interrogations |
| `fBeautifyJson` | `frontend/static/js/jsonhighlight.js` | Indente le JSON en préservant les valeurs littérales |

### Samba

| Symbole | Fichier | Responsabilité |
|---|---|---|
| `fProvisionAgent` / `fRemoveAgent` | `backend/core/samba.py` | Cycle de vie du partage et du compte |
| `fSaveSettings` | `backend/core/samba.py` | Valider, enregistrer les identifiants et activer les permissions |
| `fCheckShareDirectory` | `backend/core/samba.py` | Vérification du dossier et du propriétaire au moment de la connexion |
| `fBackup` / `fRestore` | `backend/core/samba.py` | Sauvegarde et remplacement cohérents des identifiants natifs |
| `fLoadSambaSettings` / `fCollectSambaSettings` | `frontend/static/js/samba.js` | Charger et enregistrer sans exposer les mots de passe ni jeter les autres modifications |

## 4. Flux principaux

### Recherche documentaire

Les installateurs vident les anciennes arborescences RAG des agents restaurés
avant d'extraire l'instantané, si bien que des fichiers WAL SQLite et des
générations de vecteurs périmés ne peuvent pas survivre à une restauration. Les
réglages d'exécution sont restaurés sans remplacer les poids de modèles
installés. Les workers traitent au plus huit documents, ou démarrent de nouveaux
documents pendant au plus 90 secondes, par tour ; les tâches inachevées restent
durables. La réponse de la bibliothèque expose les échecs d'importation depuis
l'inbox. L'OCR local installe les polices Liberation pour les PDF dépourvus de
polices intégrées. La compilation du moteur de vectorisation désactive le
téléchargement de l'interface web précompilée.

Envoi : `rag_api → exec_client.fRag → rag_exec → rag_worker` en tant qu'agent.
Indexation : `boa-rag → exec_daemon → rag_worker.fWork → rag_embeddings.fIsAvailable → extraction → local embeddings → publication`.
Panne du moteur pendant l'indexation : `rag_embeddings.fRequest → EngineUnavailable → fIndexDocument → state queued, chunks kept → fWork ends the batch → next pass resumes at the first missing chunk`.
Téléchargement d'un modèle : `settings_rag.js → POST /api/admin/rag/models/<id>/install → exec_client.fInstallRagModel → exec_daemon.fVerbInstallRagModel → rag_runtime.fStartModelDownload → thread fInstallModel → status file ← GET /api/admin/rag (fDescribe) polled every 2 s`.
Changement de modèle : `settings_rag.js (fConfirmModelChange) → PUT /api/admin/rag → rag_exec.fRuntime → fIsModelInstalled → fSaveRuntimeSettings → fFollowModelSimilarity → restart boa-embeddings → [each library] rag_worker.fWork → fFollowNewModel → fIsAvailable waits for the new alias → fIndexDocument(pModel) → fBuildIndex/fPublish (documents.model)` ; pendant ce temps, `fSearch → FTS5 only for the waiting documents → notice`.
Réponse : `AgentRun.fExecute → rag_search.fSearch → bounded passages → configured provider → verified citation links`.
Réponse documentaire et vérifiée : `model answers → fCheckRagAnswer (no rag.search yet → cRagSearchFirstPrompt, once) → rag.search → model answers → [verified] rag_verify.fVerify → unbacked units → fBuildCorrectionPrompt, once → model answers → fFinishRagAnswer (no passages → fixed sentence; verified → units removed + count, engine down → withheld) → fResolveCitations`.

### Enregistrement de la mémoire et de sa limite

`dashboard.js:fSaveAgent` compte les points de code Unicode et soumet `memory`
avec `info.limits.max_memory_characters`. `api.fCheckMemoryUpdate` valide par
rapport à la limite proposée (ou lit celle qui est enregistrée) avant toute
écriture, si bien qu'augmenter la limite et enregistrer un texte plus long
fonctionne en une seule requête. Il renvoie les erreurs traduites
`memoryTooLong` ou `memoryLimitInvalid` en cas de rejet. Ensuite,
`fVerbWriteAgentInfo` enregistre la limite et `fVerbWriteMemory` valide avant
d'abandonner les privilèges. `memory.fWrite` vérifie de nouveau le réglage
protégé et remplace atomiquement le fichier sans le tronquer. `memory.append` et
`memory.replace` utilisent la même vérification ; l'avertissement commence
au-delà de 75 % de la limite. Le formulaire laisse le texte collé trop long
disponible pour être modifié.

Les budgets de transport permettent la borne supérieure : 6 Mio par requête à
l'exécuteur, vérifiés par le client avant la connexion ; 8 Mio par réponse ;
4 Mio par lecture du fichier de mémoire ; 16 Mio par corps HTTP, y compris pour
les clients JSON qui échappent les caractères Unicode supplémentaires. Ce sont
des limites de transport, pas des limites de contexte du modèle.

### Création d'un agent

```
navigateur  POST /api/admin/agents {name}
  web/api.fCreateAgent
    exec_client.fCreateAgent          → socket Unix /run/boa/exec.sock
      exec_daemon.ExecRequestHandler
        fGetPeerCredentials + fIsPeerAllowed    ← refuse tout le monde sauf root/boa
        fVerbCreateAgent
          agents.fValidateAgentName
          agents.fGetNextFreeAgentId            ← le plus petit libre, d'après le système de fichiers
          useradd --home-dir … --create-home
          agents.fWriteAgentInfo                 (0600, appartenant à l'agent)
          fWriteAgentFile system-prompt.md        (0600)
          fWriteAgentFile api-token              (0600)
          chmod 0700 sur le répertoire personnel
          agents.fIndexAgent(…, vApiToken)       ← ne stocke que le SHA-256
        à la moindre exception : fRemoveAgentUser  ← pas d'agents à moitié créés
```

### Création d'un agent depuis un modèle

```
navigateur  GET /api/admin/agent-templates?language=es-ES
  agent_templates.fListTemplates
    fLoadTemplates → fDownloadArchive(<repo>/archive/refs/heads/<branch>.tar.gz)   en cache 5 min
      agent_package.fReadRepositoryArchive                   une source par dossier contenant agent.json
    agent_package.fReadPackage + fSummarise                  par modèle ; un échec est listé avec son erreur
navigateur  POST /api/admin/agents {name, template, language}
  api.fCreateAgent
    agent_templates.fReadTemplate(template)                  le serveur le relit
    agent_io.fInstallPackage
      exec_client.fCreateAgent(tools, skills, limits, pRag, pSchedules, pEnabled=False)
        exec_daemon.fVerbCreateAgent → agents.fValidateSchedule, de nouveau
      exec_client.fWriteAgentInfo / fWriteMemory / fAgentHome / fRag   quand le paquet les porte
      en cas d'échec : exec_client.fDeleteAgent
```

### Importation d'un .zip

```
navigateur  POST /api/admin/agent-imports {name, size}          → /opt/boa/imports/<id>/package.zip
navigateur  PUT  /api/admin/agent-imports/<id>/upload {offset, data}   dans l'ordre, 256 Kio chacun
navigateur  POST /api/admin/agent-imports/<id>/finish            ZipSource + fReadPackage → résumé
navigateur  (affiche le résumé ; l'utilisateur confirme et le nomme)
navigateur  POST /api/admin/agent-imports/<id>/install           → 202
  agent_io.fStartImport → install.lock (une fois) → thread fRunImport
    fInstallPackage, qui consigne step/done/total dans job.json
navigateur  GET  /api/admin/agent-imports/<id>                   chaque seconde jusqu'à installed/failed
```

### Exportation d'un agent

```
navigateur  GET /api/admin/agents/<id>/export/preview            taille de la mémoire, fichiers du répertoire personnel, bibliothèque, modèle
navigateur  GET /api/admin/agents/<id>/export?memory=1&home=1&provider=1&rag=1   un lien de téléchargement
  agent_io_api.fExport → premier bloc produit avant les en-têtes (les erreurs restent en JSON)
    agent_io.fExportAgent
      fBuildManifest ← fReadAgentInfo, fReadCrontab → fReadSchedules
      memory.md ← fReadMemory
      home/... ← exec_client.fAgentHome(list, read) en tant qu'agent
      rag/files/... + rag/documents.json ← exec_client.fRag(list, content)
```

### Une exécution planifiée

```
cron (le propre crontab d'agent-007)
  runner.py --agent-id 007            ← tourne déjà en tant qu'agent-007
    fTakeRunLock                      ← refusé → fRecordRunRefused, et arrêt
    AgentRun.__init__
      fReadOwnInfo / fReadOwnSystemPrompt / fReadOwnApiToken
      fBuildSystemPrompt              ← prompt + mémoire + index des compétences + langue
      tool_registry.fLoadAllTools
      fSelectAllowedTools             ← outils kanban retenus s'ils sont désactivés
    fExecute
      run_journal.fCountRunsOn        ← plafond quotidien, d'après son propre journal
      factory.fBuildProvider
      boucle :
        fCheckCeilings                ← étapes, jetons, secondes
        provider.fSendMessages        ← max_tokens diminue à mesure que le budget est dépensé
        run_journal.fRecordUsage
        si aucun appel d'outil : arrêt
        fRunToolCalls                 ← tous les résultats renvoyés en un seul lot
      fAskForClosingAnswer            ← un appel sans outils après un plafond
                                        d'étapes ou de jetons, pour que le travail
                                        déjà payé devienne une réponse
      run_journal.fRecordRunFinished  ← "stopped" quand un plafond l'a terminée
```

### Une carte arrive à échéance

```
boa-buzzer (en tant que boa), toutes les 5 secondes
  kanban.fListDueCards              ← propriétaire, run_at dépassé, pas encore réveillée, pas terminée
  fRingOne
    fBuildCardAnnouncement          ← assigned_by → nom, run_mode → immédiat
    exec_client.fRunNow(prompt, only_if_idle, card)
      exec_daemon.fVerbRunNow                      ← en tant que root
        fIsAgentRunning             ← occupé : started=False, pas de réveil, on réessaie
        fRunAsAgent → chat.fAppendCardMessage      ← annoncée, tour ouvert
        Popen runner.py --prompt-on-stdin --turn-id …  ← en tant qu'agent-007, le prompt sur son stdin
    kanban.fMarkCardBuzzed          ← seulement après le démarrage de l'exécution
  runner.AgentRun (vWritesToChat, pas vIsChat)
    fExecute                        ← prompt de la carte, aucune conversation rejouée
    fRecordChatAnswer               ← réponse + coût closent le tour
    fRecordChatFailure              ← ou la raison pour laquelle rien n'a tourné
```

### Un agent déplace une carte

```
le modèle demande kanban.move_card
  tool_registry.fRunTool              ← refuse s'il n'est pas accordé à cet agent
    tools/kanban_move_card.fRunTool
      agent_api_client.fCallFromContext   → /run/boa/agent.sock
        agent_api.AgentRequestHandler
          fAuthenticate               ← hash du jeton + SO_PEERCRED
          fVerbKanbanMoveCard
            fAgentMayUseKanban        ← côté serveur, lit info.json
            fRequireOwnCard           ← créateur ou attributaire seulement
            kanban.fMoveCard          ← déplacement + événement, une transaction
```

### Un agent envoie un message

```
le modèle demande channel.write
  tools/channel_write.fRunTool
    agent_api_client → agent_api.fVerbChannelWrite
      fAgentMayUseChannel             ← outil accordé ET canal accordé
      channels.fSendMessage(prefix="[Agent name]")
        fReadChannelConfig            ← en tant que boa ; l'agent ne voit jamais ceci
        fSendToTelegram / Discord / Mattermost / X
```


### Un message arrive de Telegram

```
boa-channel-telegram (en tant que boa)
  fRefreshCommands                    ← /agents /status /help, quand elles changent
  fDeliverAnswers                     ← tout ce qui s'est terminé depuis le passage précédent
    exec_client.fReadChat             ← la conversation est dans un répertoire personnel en 0700 ; seul root la lit
    channels.fSendToTelegram          ← "**name:**\n..." en réponse
    telegram_inbox.fRemovePending
  channels.fReadTelegramUpdates       ← long poll : 25 s au repos, 3 s pendant une réponse
    fIsFromTheConfiguredChat          ← tout le reste est abandonné, en silence
    callback_query -> fHandleCallback ← un appui sur un bouton d'agent
      fSelectAgent                    ← dès lors, les messages sans destinataire vont là
    message -> fHandleMessage
      fHandleCommand                  ← /agents /status /help, répondu et terminé
      fRouteMessage                   ← réponse, puis @nom, puis celui qui est sélectionné
      exec_client.fSendChatMessage(source="telegram")
        exec_daemon.fVerbSendChatMessage
          chat.fAppendMessage(metadata={"source": "telegram"})
          Popen runner.py --chat-message-on-stdin --turn-id   ← le message sur son stdin
      telegram_inbox.fAddPending      ← sur le disque : un redémarrage ne doit pas perdre la réponse
```

La réponse est envoyée par l'écouteur et non par l'exécution, pour la même raison
que l'annonce de la carte est écrite par l'exécuteur : l'exécution tourne sous
l'utilisateur propre à l'agent, et les identifiants du canal appartiennent à
`boa`. L'exécution ne fait qu'écrire dans sa conversation ; l'écouteur la lit et
se charge de l'envoi.

### Un message arrive de Discord

```
boa-channel-discord (en tant que boa)
  fDeliverAnswers                     ← tout ce qui s'est terminé depuis le passage précédent
    exec_client.fReadChat             ← la conversation est dans un répertoire personnel en 0700 ; seul root la lit
    channels.fSendToDiscord           ← "**name:**\n…" en réponse, en parties de 2000 caractères
      discord_markdown.fRenderToMessages
    discord_inbox.fRememberMessage    ← chaque partie, pour que répondre à n'importe laquelle soit acheminé
    discord_inbox.fRemovePending
  channels.fReadDiscordMessages       ← GET /channels/<id>/messages?after=<id>
    (inversé : Discord répond le plus récent en premier)
    fHandleMessage
      author.bot, type                ← ses propres mots, et tout ce qui n'est pas un message
      fIsFromTheConfiguredChannel
      fReadCommand                    ← !agents !status !help, répondu et terminé
      fRouteMessage                   ← réponse, puis @nom, puis celui qui est sélectionné
      exec_client.fSendChatMessage(source="discord")
      discord_inbox.fAddPending       ← sur le disque : un redémarrage ne doit pas perdre la réponse
  fWriteAfterId                       ← config/discord-after
```

La réponse est envoyée par l'écouteur et non par l'exécution, pour la même raison
que celle de Telegram : l'exécution tourne sous l'utilisateur propre à l'agent,
et les identifiants du canal appartiennent à `boa`.

Le premier passage d'une installation neuve demande le message le plus récent
et n'en garde que l'identifiant. Un canal vide est marqué avec le plus petit
identifiant qui soit, si bien qu'on répond au **premier** message que quelqu'un
écrit au lieu de le consommer pour déterminer où commencer.

### Le bot ne montre rien à un inconnu

Le nom d'utilisateur d'un bot est public : quiconque le trouve peut ouvrir une
conversation avec lui. `fIsFromTheConfiguredChat` compare donc le `chat.id` que
Telegram place sur chaque message - que l'expéditeur ne peut pas falsifier - à
celui qui est configuré, et `fHandleMessage` abandonne ce qui ne correspond pas
avant qu'une commande ne soit distribuée et avant qu'un agent ne soit choisi.
`fHandleCallback` fait de même pour un appui sur un bouton. Rien n'est renvoyé :
répondre confirmerait que le bot est vivant à quiconque est en train de le
sonder. Rien n'est consigné non plus. L'abandon était autrefois consigné avec
l'identifiant de la conversation d'où il venait, ce qui est la donnée de
quelqu'un d'autre et aurait signifié que cette installation accumulait en
silence une liste de ceux qui ont trouvé le bot. Ce qui reste, c'est un message
qui n'a jamais existé.

Le coût est réel et mérite d'être nommé : un `chat_id` mal configuré ressemble
désormais exactement à un inconnu, et les propres messages du propriétaire
disparaissent en silence. L'identifiant configuré est écrit dans le log à
chaque démarrage - `Registered 3 command(s) for chat <id> only` - et c'est le
nombre auquel comparer. Un message venant de la conversation *configurée* qui
n'atteint aucun agent est toujours consigné, parce que là l'expéditeur est le
propriétaire, et « je lui ai écrit et rien ne s'est passé » serait sinon
impossible à distinguer de « ce n'est jamais arrivé ».

Ce que le filtre ne couvre pas, et ne peut pas couvrir, c'est *qui* à
l'intérieur de la conversation : un `chat_id` qui désigne un groupe est un groupe
dont chaque membre peut parler aux agents.

Le même raisonnement décide de l'endroit où est écrite la liste des commandes.
`setMyCommands` prend une portée, et `default` et `all_private_chats` sont
résolues pour chaque utilisateur de Telegram - si bien qu'une liste écrite là
est un menu montré à des inconnus, avec « Server status » dedans, qui annonce
qu'il y a derrière une machine qui vaut la peine d'être titillée. Ils ne
pourraient jamais rien en exécuter, mais un panneau sur une porte verrouillée
reste un panneau. `fSetTelegramCommands` écrit la liste dans la seule portée de
la conversation configurée et **supprime** les deux portées publiques à chaque
rafraîchissement : une liste écrite par une version plus ancienne de ce code
vit du côté de Telegram jusqu'à ce que quelque chose la retire.
`fHideTelegramPublicProfile` vide les deux autres chaînes publiques,
`setMyDescription` et `setMyShortDescription`, qui sont ce qui remplit une
conversation vide sous « What can this bot do? ».

Ce qui reste visible, c'est le nom du bot, son image et le bouton Start, que
Telegram dessine dans chaque conversation vide avec un bot et qu'aucune API ne
peut retirer. Appuyer dessus envoie `/start`, qui est abandonné comme tout ce
qui vient d'une autre conversation.

### Pourquoi le menu contient des outils et non des agents

Telegram dessine `/name` à côté de chaque entrée du menu des commandes - cette
chaîne est l'entrée, c'est ce qui est tapé dans la zone quand on appuie
dessus, et aucune API ne la cache. Un menu d'agents ne pouvait donc jamais être
la liste des agents que quelqu'un voulait voir, et il grandissait avec la liste
des agents sans rien dire de ce à quoi servait le bot.

Le menu contient trois choses que le bot sait faire. Quels agents existent est
une question, et `/agents` y répond avec des boutons inline, où un bouton dit
`os-watcher` et rien d'autre, parce que le texte d'un bouton est au choix du
bot.

Le reste en découle :

- **L'agent sélectionné reste sélectionné.** Appuyer sur un bouton ou nommer un
  agent le choisit ; tout ce qui n'a pas de destinataire va vers lui jusqu'à ce
  qu'un autre soit choisi. Nommer l'agent à chaque ligne passe une fois et
  devient pénible dès le quatrième message. Cela vit dans `settings`, pas en
  mémoire, parce que le service redémarre à chaque mise à jour.
- **Une réponse l'emporte toujours.** Elle est sans ambiguïté, et c'est ce que
  fait quelqu'un qui tient un téléphone. Rien d'autre ne change la sélection, si
  bien qu'un agent n'hérite jamais d'une conversation pour avoir été celui qui a
  parlé en dernier.
- **Un agent supprimé cesse d'être sélectionné.** `fReadSelectedAgent` vérifie
  la liste des agents en sortant : n'atteindre personne vaut mieux qu'atteindre
  celui qui a pris son identifiant.
- **Le bot parle la langue de l'installation.** `agent_language` d'abord, le
  même réglage que celui dans lequel répondent les agents - ses lignes
  apparaissent dans la même conversation que les leurs.

### La barre latérale montre qui travaille

```
toutes les 5 secondes, et juste après un envoi / exécuter maintenant / l'arrivée d'une réponse
  api.js fRefreshAgentActivity        ← sauté tant que l'onglet est masqué
    GET /api/admin/agents
      web/api.fListAgents
        exec_client.fListRunningAgents          → /run/boa/exec.sock
          exec_daemon.fVerbListRunningAgents
            fListRunningAgentIds      ← un seul balayage de /proc, tous les agents à la fois
      chaque agent porte `running`
    fSetAgentAvatarActivity           ← data-running sur l'avatar ; la liste
                                        elle-même n'est jamais reconstruite sur minuterie
      fBuildAgentActivityArc          ← un rectangle arrondi SVG sur la bordure
  le CSS anime son stroke-dashoffset  ← la forme reste immobile, le trait lumineux
                                        parcourt le contour dans le sens horaire
```

### Connexion

```
POST /login
  views.fLoginPage
    auth.fCountRecentFailures         ← 10 par tranche de 15 minutes et par adresse
    auth.fVerifyCredentials           ← argon2id ; un e-mail erroné est quand même haché
    auth.fRecordAttempt
    auth.fLogIn                       ← cookie de session, 12 heures
```

---

### Un message vocal arrive

`fHandleMessage → fRouteMessage → fEnqueueTelegram → audio_jobs → fRunOneJob → fDownloadTelegram → fTranscribe → fSubmitTranscript → fSendChatMessageLocked → runner`. La réponse utilise la livraison Telegram ordinaire ; la conversation web ajoute la transcription et un lecteur privé. Réglages → Audio utilise GET/PUT `/api/admin/audio` ; les téléchargements de modèles utilisent le RPC `install_whisper_model` et interrogent la progression sans bloquer le HTTP.

### API Calls

```text
AgentRun.fSendRecordedRequest → enregistreur de requêtes de BaseProvider → api_calls.fRecordCall
onglet API Calls → GET /api/admin/agents/<id>/api-calls
  exec_client.fReadApiCalls → exec_daemon.fVerbReadApiCalls → api_calls.fReadCalls
déplier une requête → GET /api/admin/agents/<id>/api-calls/<call_id>
  exec_client.fReadApiCallBody → api_calls.fReadBodyChunk → texte JSON envoyé en flux
  fBeautifyJson → fHighlightJsonElement → DOM sûr
```

### Samba

```text
create_agent → fIndexAgent → samba.fProvisionAgent → samba/ + [agent-xxx]
GET /agents/<id>/samba → read_samba → samba.fReadSettings
PUT /agents/<id>/samba → write_samba → samba.fSaveSettings
  validation → info protégé + testparm → smbpasswd (stdin) → reload/close-share
connexion SMB → root preexec --check-share <id> → permissions Samba → uid de l'agent
delete_agent → samba.fRemoveAgent → suppression de l'utilisateur Linux, du répertoire personnel et de l'index
--backup → tdbbackup + SID du serveur → samba-backup dans l'archive
--restore → arrêt des services → restauration des utilisateurs/données → remplacement de la passdb native → démarrage
```

## 5. Carte des points d'entrée et des routes

### HTTP

| Route | Méthode | Gestionnaire | Fichier |
|---|---|---|---|
| `/api/admin/rag` | GET, PUT | `fRuntime` | `backend/web/rag_api.py` |
| `/api/admin/rag/models/<vModel>/install` | POST | `fInstallModel` | `backend/web/rag_api.py` |
| `/api/admin/agents/<id>/rag/...` | GET, POST, PUT, DELETE | `fOverview`, `fUpload`, `fUploadPart`, `fDocument`, `fContent`, `fImport`, `fSearch` | `backend/web/rag_api.py` |
| `/login` | GET, POST | `fLoginPage` | `backend/web/views.py` |
| `/logout` | GET, POST | `fLogoutPage` | `backend/web/views.py` |
| `/` | GET | `fDashboardPage` | `backend/web/views.py` |
| `/kanban/` | GET | `fKanbanPage` | `backend/web/views.py` |
| `/tools/` | GET | `fToolsPage` → `/settings/?tab=tools` (préserve `family` et `agent`) | `backend/web/views.py` |
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
| `/api/admin/agents` | GET, POST | `fListAgents` (porte toujours `running` pour chaque agent), `fCreateAgent` | `backend/web/api.py` |
| `/api/admin/agents?kanban=1` | GET | `fListAgents`, ajoute `reads_kanban` pour chaque agent | `backend/web/api.py` |
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

Tout ce qui est une API vit sous `/api/`. Tout ce qui se trouve sous
`/api/admin/` exige une session.

### Sockets Unix

| `/run/boa-web/web.sock` | `0750 boa:boa` | gunicorn | L'application elle-même. Seul `boa-proxy` l'atteint |

| Socket | Mode | Serveur | Verbes |
|---|---|---|---|
| `/run/boa/exec.sock` | `0660 root:boa` | `exec_daemon` | `ping`, `create_agent`, `delete_agent`, `read_agent_info`, `write_agent_info`, `read_system_prompt`, `write_system_prompt`, `read_crontab`, `write_crontab`, `run_now`, `list_running_agents`, `read_samba`, `write_samba`, `read_run_journal`, `read_api_calls`, `read_api_call_body`, `read_usage_summary`, `read_chat`, `read_chat_attachment`, `send_chat_message`, `clear_chat` |
| `/run/boa/agent.sock` | `0666` | `agent_api` | `who_am_i`, `kanban_add_card`, `kanban_move_card`, `kanban_delete_card`, `kanban_list_cards`, `channel_write`, `mail_read`, `mail_delete`, `mail_move`, `mail_forward` |

### Ligne de commande

| Commande | Fichier |
|---|---|
| `runner.py --agent-id NNN [--prompt … or --prompt-on-stdin] [--chat-message … or --chat-message-on-stdin] [--turn-id …] [--dry-run]` | `backend/core/runner.py` |
| `install-update-reinstall-debian.sh --install\|--update\|--reinstall\|--backup [file]\|--restore <file>` | `deploy/` |
| `install-update-reinstall-alpine.sh --install\|--update\|--reinstall\|--backup [file]\|--restore <file>` | `deploy/` |

---

## 6. Analyse d'impact

Ce qui casse si vous modifiez ces éléments.

| Composant | Le modifier affecte |
|---|---|
| `paths.fNormalizeAgentId` | **Chaque chemin du système.** C'est la seule validation entre une entrée utilisateur et un chemin du système de fichiers. L'affaiblir transforme n'importe quel identifiant d'agent en traversée de répertoires |
| Constantes de `paths.py` | Les quatre services, l'installateur et les unités systemd. Changer `/opt/boa` implique de réinstaller |
| `deploy/haproxy/boa.cfg` | Chaque requête. `accept-proxy` doit correspondre à ce qu'envoie le HAProxy de la machine : avec `send-proxy-v2` sur ce backend il est obligatoire, sans lui le bind refuse toutes les connexions |
| Le bind de `backend/web/gunicorn.conf.py` | Doit rester une socket Unix. Redonner à gunicorn un port et un certificat réintroduit l'échec du PROXY avant le TLS |
| `exec_protocol.lKnownVerbs` | La surface privilégiée. Ajouter un verbe ajoute un moyen pour le processus web de demander quelque chose à root. Chaque ajout demande le même examen que le premier |
| `exec_daemon.fRunPrivilegedCommand` | Chaque commande privilégiée. Elle n'utilise jamais de shell ; y introduire `shell=True` ferait de chaque nom d'agent un point d'injection |
| `agent_api.fAuthenticate` | Chaque requête d'agent vers le tableau et les canaux. Les deux vérifications doivent rester |
| `db.cAppSchema` / `cKanbanSchema` | Les installations existantes. Il n'y a pas de système de migration : les schémas utilisent `IF NOT EXISTS`, donc **les nouvelles colonnes demandent un code de migration explicite**, pas une modification du schéma |
| `agent_scripts.cMinimumMinuteStep` | La fréquence à laquelle un agent peut se planifier lui-même. C'est la seule chose qui sépare un horaire négligent d'une boucle précédée d'une ligne de cron |
| `paths.lProtectedAgentFiles` | Quels fichiers vont dans le tiroir appartenant à root. La migration de l'installateur et le démon qui crée un agent le lisent tous deux, si bien qu'ils ne peuvent pas être en désaccord sur la liste |
| `agents.fBuildAgentInfo` | Seulement les nouveaux agents. Les fichiers `info.json` existants ne sont pas touchés, donc les nouveaux champs ont besoin d'un chemin de lecture par défaut |
| `exec_daemon.fVerbWriteAgentInfo` | **Chaque champ de `info.json` qui survit à un enregistrement.** Il reconstruit le fichier clé par clé, si bien qu'un champ qu'il ne nomme pas est un champ que l'interface supprime en silence la première fois que quelqu'un appuie sur Enregistrer. Les listes sont lues par `fReadNameList`, qui distingue une clé absente (« n'y touche pas ») d'une liste vide (« retire-les toutes ») : lu avec `or`, décocher le dernier outil restaurait la liste précédente |
| `skills.fSelectInstalledSkills` | Ce qui atteint un prompt et ce que `skill.read` acceptera d'ouvrir. L'index comme l'outil filtrent par là, si bien qu'une compétence supprimée du serveur cesse d'être mentionnée au lieu d'être promise puis d'échouer |
| La forme neutre de `providers.base` | Chaque adaptateur et le runner |
| L'interface de `tool_registry` | Chaque outil de `/opt/boa/tools/`, y compris ceux que l'utilisateur a écrits |
| `telegram_listener.fIsFromTheConfiguredChat` | Qui peut parler à vos agents. Le nom d'utilisateur d'un bot est public, donc cette vérification est toute l'autorisation : l'affaiblir permet à quiconque trouve le bot de lancer des exécutions sur votre serveur |
| La signature de `channels.fSendMessage` | Chaque appelant, et les deux expéditeurs qui prennent deux arguments. `pReplyToMessageId` est transmis à Telegram et Discord, les deux canaux par lesquels une personne peut répondre |
| `discord_markdown.cMaxDiscordLength` | Si la réponse d'un agent arrive tout court. Discord refuse un `content` de plus de 2000 caractères, et c'est un refus qu'il oppose - pas une troncature |
| `agent_routing.fMatchNamedAgent` | Qui un message atteint, dans **les deux** écouteurs. La correspondance la plus longue est ce qui fait de `@News` et `@News Miner` deux agents |
| `agent_routing.fBuildStatusReport` | Ce que /status répond sur les deux. Un seul rapport, si bien que les deux ne peuvent pas être en désaccord sur le nombre de services |
| `discord_listener.fIsFromTheConfiguredChannel` | Quel canal écoutent les agents. Contrairement à Telegram, il n'y a pas de seconde vérification sur qui parle : quiconque peut écrire dans ce canal peut lancer des exécutions |
| `kanban.lStates` | Le tableau, l'API, le frontend et le prompt de chaque agent |
| La forme des entrées de `run_journal` | L'écrivain (runner) comme les lecteurs (démon, web). Les anciennes lignes restent dans les journaux : les lecteurs doivent tolérer des champs manquants |
| `samba` | Le cycle de vie des agents, l'API privilégiée, les clients SMB et la sauvegarde/restauration des deux installateurs. Gardez intacts la garde du dossier, la dérivation du nom et du chemin, et le traitement des secrets |
| Un fichier que le démon lit dans le répertoire personnel d'un agent (`runs.jsonl`, `chat.jsonl`, `memory.md`) | Lu uniquement par `paths.fReadAgentOwnedFile`. Un nouveau fichier que le démon lit dans un répertoire personnel doit aussi passer par là, sinon root lit tout ce vers quoi l'agent le pointe - une FIFO qui ne répond jamais, un lien vers n'importe quel fichier de la machine |
| Ce que contient une sauvegarde (la ligne `tar` de `fDoBackup`) | Un nouvel état sous `/opt/boa/` qui appartient à l'installation et non au code doit y être ajouté, sinon une restauration sur une nouvelle machine le perd |
| Les limites noyau d'une exécution (`runner.cMaxProcesses`, `exec_daemon.cRunTasksMax`, `cRunMemoryMax`) | Un outil qui a besoin de plus de 1024 tâches ou de 2 Gio doit les relever ; un navigateur représente déjà quelques centaines de threads |
| `runner.py` en tant que chemin | Chaque exécution planifiée. Cron le lance par son chemin avec presque aucun environnement, donc le runner place sa propre racine dans sys.path : sans cela, `import backend` échoue et la trace part dans le courrier de cron, qui sur une machine du LAN ne va nulle part |
| `runner.dAnswerLanguageLines` | La ligne ajoutée à un prompt système pour dire à l'agent dans quelle langue répondre. Écrite DANS cette langue, et elle dit qu'elle prévaut sur la propre règle du prompt - une préférence à côté d'une règle perd, c'est mesuré |
| `agent_api.fFilterCardsForAgent` | Ce dont un agent peut savoir l'existence. Chaque lecture du tableau passe par là, et l'orchestrateur est la seule exception. Filtrer dans l'outil à la place placerait une règle de sécurité dans une description dont on peut dissuader le modèle |
| Le côté où se place une bulle de conversation | Qui parle. Une carte est ce qu'on a demandé à l'agent de faire, elle va donc à droite avec les messages de l'utilisateur ; le rapport d'une exécution planifiée, c'est l'agent qui parle, il reste donc à gauche |
| `chat.lToolsWorthReporting` | Quels outils rendent une exécution planifiée digne d'apparaître dans la conversation. Tout le reste reste dans le journal : sinon un agent horaire publierait vingt-quatre messages « rien à signaler » par jour |
| `chat.lAskingRoles` | Quels rôles attendent une réponse. Un rôle qui ouvre un tour et n'est pas listé laisse la zone de message ouverte pendant que l'agent travaille ; un rôle listé mais jamais clos ferme la zone de message pour toujours |
| `kanban.cRunNow` | Le mot qu'envoient le navigateur, les agents et l'API à la place d'un horodatage. Le transformer en heure ailleurs que dans `fValidateRunAt` perd `run_mode`, et avec lui la différence entre « maintenant » et un moment choisi |
| `chat.cReplayedTurns` | Ce que coûte chaque message de conversation. Chaque tour rejoué est payé de nouveau au message suivant, donc l'augmenter rend les longues conversations de plus en plus chères |
| `lTextColours` dans `TestThemes` | Quelles couleurs mesure le test de contraste. Une couleur utilisée pour du texte et absente de cette liste est une couleur que rien ne vérifie |
| Un attribut `style=` dans n'importe quel template | Rien : `style-src` vaut `'self'` sans `unsafe-inline`, donc le navigateur le jette. Il existe un test qui échoue s'il en apparaît un |
| `.notice-layer` dans `app.css` | L'endroit où apparaissent chaque confirmation et chaque erreur de l'application. `position: fixed` est porteur : `absolute` centre dans le document au lieu de l'écran, ce qui est précisément le bogue que la couche existe pour corriger |
| La chaîne `.app:has(#vChatPanel…)` et `--status-bar-live-height` dans `app.css` | Si la zone de texte de la conversation reste au-dessus de la barre d'état. Un bloc de cette colonne flex sans `min-height: 0`, ou une hauteur de `.chat` qui cesse de soustraire la hauteur réelle de la barre, laisse de nouveau la page défiler et place la zone de message sous la barre |
| `agents.fValidateSchedule` | Si un horaire venu d'un `.zip` ou d'un modèle peut devenir une commande dans un crontab écrit en tant que root. L'assouplir (un espace, un `#`, un saut de ligne) transforme une importation en exécution de code |
| `agent_home.sExcludedTopNames` / `fIsExcluded` | Ce qu'une exportation peut divulguer et ce qu'une importation peut implanter : sessions de navigateur, `.ssh`, la conversation. Retirer un nom le laisse passer dans les deux sens |
| `agent_package.lManifestKeys` / `cFormatVersion` | Chaque `.zip` exporté et chaque modèle de chaque dépôt. Une nouvelle clé a besoin de cette version pour être lue ; un sens modifié a besoin d'un nouveau numéro de format |
| `min_support` dans `rag_models.json` | Quels paragraphes d'une réponse vérifiée survivent, pour ce modèle. Relevé, des paragraphes fidèles commencent à disparaître ; abaissé, une citation vers un passage sans rapport passe. Ce que chaque valeur des deux modèles retire et laisse passer figure dans le tableau à côté de la vérification dans `rag_verify.py` : mesurez de nouveau sur de vrais documents avant de bouger une valeur, et mettez le tableau à jour |
| `sha256` ou `dimensions` d'un modèle dans `rag_models.json` | Chaque bibliothèque indexée avec lui. Une nouvelle empreinte est un nouvel espace vectoriel : chaque bibliothèque réindexe tous ses documents à son passage suivant (`fFollowNewModel`), ce qui, sur une grande bibliothèque, prend des heures |
| `rag_embeddings.fCheckServedModel` / le `--alias` dans `rag_runtime.fServe` | Si un vecteur peut venir d'un autre modèle que celui que consigne sa bibliothèque. Sans eux, une tâche qui tourne pendant un changement de modèle stocke des vecteurs de deux modèles dans une même révision |
| `runner.lRagModesThatSearch` / `fFinishRagAnswer` | Si une exécution documentaire ou vérifiée peut livrer du texte venu des propres poids du modèle. Retirer un mode de la liste, ou la vérification de l'absence de passages, ramène des réponses sans aucune recherche derrière elles |
| `rag_search.fSource` | Tout ce qu'on dit au modèle sur un passage et ce vers quoi pointe une citation : le bloc de prompt pré-récupéré, `rag.search`, `rag.read` et `fResolveCitations` l'utilisent tous. Un champ qu'on y ajoute a aussi besoin de sa colonne dans les trois `SELECT` qui l'alimentent |
| `rag_embeddings.EngineUnavailable` | Si un échec d'indexation garde ou jette le travail. Lever une simple `ValueError` pour une panne fait passer le document en `error` et supprime ses fragments vectorisés ; lever `EngineUnavailable` pour un refus définitif laisse le document en file pour toujours |
| `rag_store.cSchema` | Seulement les catalogues créés après la modification. Chaque bibliothèque d'agent existante, et chaque sauvegarde restaurée, garde l'ancienne table : une nouvelle colonne a aussi besoin de son entrée dans `rag_store.lAddedColumns`, qu'applique `fMigrate` |
| `frontend/static/i18n/en-US.json` | Ajouter une clé implique de l'ajouter aux quatorze autres, sinon cette chaîne retombe sur l'anglais. `TestTranslations` échoue pour une clé manquante, un `{placeholder}` perdu, et un chemin ou un nom d'outil traduit |

---

## 7. Points d'extension

### Un nouveau fournisseur

1. Écrivez `backend/providers/<name>.py` avec une classe qui étend
   `base.BaseProvider`, définit `cProviderName`, `cDefaultModel`,
   `cDefaultBaseUrl` et implémente `fSendMessages`.
2. Ajoutez une ligne à `factory.dProviderRegistry`.
3. Ajoutez le nom à `agents.lSupportedProviders`.
4. S'il n'a besoin d'aucune clé, ajoutez-le à `factory.lSelfHostedProviders`.
5. Les options supplémentaires (comme le `thinking` de DeepSeek) vont dans
   `lExtraConfigKeys` ; la fabrique associe automatiquement `reasoning_effort` →
   `pReasoningEffort`.

Ne le fusionnez pas dans un adaptateur existant sous prétexte que le dialecte
correspond. Un fichier par fournisseur est un choix délibéré.

### Un nouvel outil

Créez un `.py` dans `/opt/boa/tools/` qui déclare :

```python
cToolName = "namespace.verb"
cToolDescription = "What the model is told it does."
dToolSchema = {"type": "object", "properties": {...}, "required": [...]}

def fRunTool(pArguments, pContext):
  return "text the model sees"
```

Il s'exécute en tant que l'agent appelant. S'il a besoin de quelque chose que
les agents ne peuvent pas atteindre, ajoutez plutôt un verbe à l'API des agents
et appelez-le par `agent_api_client`.

Le fichier doit appartenir à root : l'application l'importe comme du code.

### Une nouvelle compétence

Créez un répertoire dans `/opt/boa/skills/` avec un `SKILL.md` dedans :

```markdown
---
name: BackupVerification
description: One line. This is what every run pays for.
---

The procedure, at whatever length it needs.
```

Rien à enregistrer et pas de redémarrage : `fListSkills` lit le répertoire, si
bien qu'elle apparaît dans l'interface au chargement de page suivant. Cochez-la
sur un agent, donnez à cet agent `skill.read`, et elle se trouve dans son prompt
à l'exécution suivante.

Tout le reste du répertoire est livré avec la compétence. Il est lisible par
tous, donc la compétence peut dire « lance `verify.sh` dans ce répertoire » et
l'agent le peut.

Le nom est le nom du répertoire : lettres, chiffres et tirets, en commençant par
une lettre. Le `name:` de l'en-tête est ce qu'une personne voit dans la liste ;
le nom du répertoire est ce que demande un agent.

### Une nouvelle opération privilégiée

1. Ajoutez la constante du verbe à `exec_protocol` et à `lKnownVerbs`.
2. Écrivez `fVerb<Name>` dans `exec_daemon` et ajoutez-le à `dVerbHandlers`.
3. Ajoutez une enveloppe dans `exec_client`.

Validez chaque argument avant qu'il n'atteigne un chemin ou une ligne de
commande, et gardez le verbe spécifique. Un verbe assez général pour être
réutilisable est d'habitude un verbe assez général pour être détourné.

### Un nouveau canal

Envoi seulement :

1. Écrivez `fSendTo<Name>` dans `channels.py`.
2. Ajoutez-le à `lChannels` et à `dChannelSenders`.
3. Ajoutez ses champs à `dChannelFields` dans `frontend/static/js/settings.js`,
   et ceux qui sont des identifiants à `lSecretChannelFields` dans ce même
   fichier ainsi qu'à `lSecretConfigFields` dans `channels.py`.

Réception aussi, ce qui en fait une conversation :

4. Écrivez `fRead<Name>Messages` dans `channels.py`, en les renvoyant du plus
   ancien au plus récent.
5. Écrivez `<name>_inbox.py` : deux tables dans `db.cAppSchema` et l'agent
   sélectionné dans un réglage.
6. Écrivez `<name>_listener.py` sur la base d'`agent_routing`, qui contient déjà
   la liste des agents, la correspondance des noms, la réponse de clôture et le
   rapport d'état. Ce qui reste, c'est le protocole.
7. Écrivez `<name>_texts.py` pour les phrases que ce canal dit autrement, en
   retombant sur `telegram_texts` pour le reste.
8. `deploy/systemd/boa-channel-<name>.service` et un service dans
   `deploy/openrc/`, le nom
   dans `lServices` et aux sept endroits où l'installateur Debian nomme ses
   unités, ainsi que dans `system_info.lBoaServiceNames`. Si son nom OpenRC
   diffère, ajoutez la correspondance dans `system_info.dOpenRcServiceNames`.
9. Son interrupteur dans `dChannelSwitches`, sa clé `chat.source<Name>` dans les
   quinze catalogues, et `<name>` dans `exec_daemon.lKnownChatSources`.

### Une nouvelle langue

Quinze sont livrées : `de-DE`, `en-GB`, `en-US`, `es-AR`, `es-ES`, `fr-FR`,
`he-IL`, `hi-IN`, `it-IT`, `ja-JP`, `ko-KR`, `pt-BR`, `pt-PT`, `ru-RU`,
`zh-CN`. Une seizième représente sept endroits, et les tests les nomment tous :

1. Copiez `frontend/static/i18n/en-US.json` et traduisez les valeurs.
2. Ajoutez l'étiquette à `lSupportedLanguages` dans
   `frontend/static/js/i18n.js`.
3. Ajoutez une `<option>` aux trois sélecteurs : deux dans
   `frontend/templates/settings.html`, un dans `login.html`, par étiquette.
4. Ajoutez une ligne à `runner.dAnswerLanguageLines`, écrite DANS cette langue.
5. Ajoutez un bloc à `telegram_texts.dTexts` et son étiquette au
   `lSupportedLanguages` de ce module, sinon le bot retombe sur l'anglais.
   Ajoutez-en un aussi à `discord_texts.dTexts` : il contient les trois phrases
   que Discord dit autrement, et une langue qui en est absente reçoit ces trois
   phrases en anglais.
6. Traduisez la documentation à partir des fichiers en-US : `README.<tag>.md` à
   la racine, `doc/CODE.<tag>.md` et `doc/MANUAL.<tag>.md`. Ajoutez la langue à
   la ligne des langues en haut de chaque README, dans l'ordre alphabétique des
   étiquettes. en-US est la source de toutes les autres langues et garde les
   noms sans étiquette : `README.md`, `doc/CODE.md`, `doc/MANUAL.md`.
7. Si elle s'écrit de droite à gauche, ajoutez son étiquette à
   `lRightToLeftLanguages` dans `frontend/static/js/i18n.js`. Rien d'autre : la
   feuille de style utilise déjà des propriétés logiques (voir « De droite à
   gauche » plus haut).

`TestTranslations` dans `tests/test_web.py` échoue pour une clé manquante, une
clé en trop, une chaîne vide, un `{placeholder}` perdu, un chemin ou un nom
d'outil traduit, un fichier non trié, un sélecteur qui ne propose pas la
langue, une ligne de prompt manquante et un bloc Telegram manquant. Les six
langues non latines sont aussi vérifiées pour s'assurer qu'elles sont bien
écrites dans leur propre écriture, parce qu'un fichier de chaînes anglaises
sous un nom russe passe toutes les autres vérifications. `TestExampleAgents`
dans `tests/test_tools.py` échoue pour une langue sans son README, son CODE ou
son MANUAL, ou pour un README qui ne pointe pas vers le README de chacune des
autres langues ; `TestTheCodeDocumentsPointAtRealLines` dans
`tests/test_web.py` échoue pour un CODE dont les références `file.py:line`
diffèrent de celles de l'anglais.

Ce qu'une traduction peut changer : un nom de fichier que le texte anglais donne
en EXEMPLE, comme `check-disk.sh`. Rien ne les recherche.

### Un nouveau mode de réponse RAG

1. Ajoutez-le aux modes autorisés dans `rag_settings.fValidateSettings` et à
   l'énumération `mode` dans `backend/web/rag_api_doc.py`.
2. Donnez-lui sa règle dans `rag_search.fPrompt`, en disant ce qu'impose le
   runner.
3. Dans `runner.py`, ajoutez-le à `lRagModesThatSearch` si le modèle doit
   chercher, et à `fCheckRagAnswer` / `fFinishRagAnswer` si ses réponses sont
   vérifiées.
4. Une `<option>` dans `frontend/templates/agent_rag.html`, son repli dans
   `dRagModeHints` dans `rag.js`, et `rag.<mode>` plus `rag.modeHint.<mode>`
   dans les quinze fichiers i18n.
5. Des tests dans `tests/test_rag.py` (`TestRagInAgentRun`), avec le
   fournisseur scripté et un faux `rag_embeddings.fEmbed`.

### Un nouveau modèle de vectorisation

1. Une entrée dans `backend/core/rag_models.json` : l'URL du GGUF épinglée sur
   un commit (jamais sur une branche), `size` et `sha256` depuis l'API du
   dépôt, `dimensions`, `context`, le `pooling` que demande sa fiche de modèle,
   et ses préfixes de requête et de passage. `TestEmbeddingModelChoice` vérifie
   que l'entrée est complète.
2. Faites-le tourner à côté du moteur installé sur la bibliothèque de test et
   mesurez-le comme l'application l'utilise (le commentaire au-dessus du
   tableau dans `rag_verify.py` explique comment) : son `min_support` est la
   valeur la plus haute qui laisse passer moins de 1 % des citations vers des
   passages d'un autre sujet, son `min_similarity` se situe entre les questions
   liées et les questions sans rapport. Ajoutez ses lignes à ce tableau.
3. Son pic de mémoire doit tenir dans le `MemoryMax` de
   `deploy/systemd/boa-embeddings.service` ; écrivez-le, ainsi que la lenteur de
   son indexation par rapport à EmbeddingGemma, sous `memory_mb` et
   `relative_indexing_time`.
4. La liste de Réglages → RAG et la route de téléchargement viennent du
   catalogue ; seuls les tableaux de `doc/MANUAL*.md` et les descriptions de
   l'énumération dans `rag_api_doc.py` ont besoin du nouveau modèle par son nom.

### Un nouveau champ d'informations du document

1. Ajoutez la colonne à `rag_store.cSchema` et à `rag_store.lAddedColumns`,
   sinon les bibliothèques existantes ne l'auront pas.
2. Ajoutez la clé, à sa place, à `rag_store.lMetadataKeys`, et toute
   vérification de format dont elle a besoin à `rag_store.fAction`.
3. Si le modèle doit la voir, ajoutez `d.<column>` aux trois `SELECT` de
   `rag_search` et le champ à `rag_search.fSource`.
4. Ajoutez-la au schéma `metadata` dans `backend/web/rag_api_doc.py`.
5. Ajoutez-la, à sa place, à la liste des champs dans
   `frontend/static/js/rag.js`.
6. Ajoutez `rag.<key>` aux quinze fichiers `frontend/static/i18n/*.json`.
7. Couvrez-la dans `tests/test_rag.py` ; le test de migration construit déjà un
   catalogue sans aucune des colonnes de `lAddedColumns`.

### Un nouveau modèle d'agent

Les modèles vivent dans le dépôt de modèles, pas ici :

1. Un dossier `<name>/` dans `bunch-of-aigents-templates`, nommé comme le
   `name` du modèle (`^[a-z][a-z0-9-]{0,39}$`).
2. `agent.json` : `format` 1, `name`, `description` dans les quinze langues,
   `tools`, `schedules`, `limits` et, s'il a besoin de sa bibliothèque, `rag`.
   Le plus rapide est de construire l'agent ici, de l'exporter et de le
   décompresser là-bas.
3. `system-prompt.md`, en anglais, terminé par la règle sur la langue de la
   réponse.
4. `README.md`, en en-US, pour ceux qui lisent ce dépôt : à quoi sert l'agent,
   ce qu'il fait, ce dont il a besoin d'abord, ce qu'il ne fera pas, ce avec
   quoi il est livré et comment l'installer. L'application l'ignore.
5. Lancez les tests de ce dépôt-ci : `TestExampleAgents` lit le clone voisin de
   celui-ci avec `agent_package` et échoue pour un modèle que l'application
   refuserait, un outil qui n'existe pas, une langue manquante, ou un README
   absent ou qui ne nomme pas les outils et les horaires du modèle.
6. Une ligne dans le tableau des modèles de chaque MANUAL d'ici, une par langue,
   et une, avec un lien vers son README, dans les trois README de là-bas.

### Une nouvelle page

1. Une route dans `backend/web/views.py` qui renvoie `render_template`.
2. Un template qui étend `app_base.html`.
3. Un `<li>` dans le `nav` de `app_base.html`.
4. Son propre JS dans `frontend/static/js/`, qui commence par
   `await fWaitForTranslations()` avant d'afficher quoi que ce soit.
