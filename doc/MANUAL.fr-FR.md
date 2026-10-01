# Manuel

Comment utiliser Bunch of AIgents au quotidien.

## Sommaire

1. [Ce qu'il fait](#ce-quil-fait)
1. [Sur quoi il tourne](#sur-quoi-il-tourne)
1. [Si vous êtes sous Alpine](#si-vous-êtes-sous-alpine)
1. [Installation](#installation)
1. [Mise à jour et réinstallation](#mise-à-jour-et-réinstallation)
1. [Ouvrir l'application](#ouvrir-lapplication)
1. [Se connecter](#se-connecter)
1. [Premier démarrage](#premier-démarrage)
2. [L'interface](#linterface)
3. [D'où part un nouvel agent](#doù-part-un-nouvel-agent)
3. [Créer votre premier agent](#créer-votre-premier-agent)
4. [Parler à un agent](#parler-à-un-agent)
5. [Réglages de l'agent](#réglages-de-lagent)
5. [Exporter un agent](#exporter-un-agent)
5. [Dossiers partagés Samba](#dossiers-partagés-samba)
6. [Donner un modèle à un agent](#donner-un-modèle-à-un-agent)
5. [Écrire un prompt système](#écrire-un-prompt-système)
6. [Choisir les outils](#choisir-les-outils)
7. [Donner une compétence à un agent](#donner-une-compétence-à-un-agent)
8. [Donner un navigateur à un agent](#donner-un-navigateur-à-un-agent)
9. [Plafonds de dépense](#plafonds-de-dépense)
8. [Planifier un agent](#planifier-un-agent)
9. [Le tableau kanban](#le-tableau-kanban)
10. [Thèmes](#thèmes)
11. [Canaux](#canaux)
12. [L'orchestrateur](#lorchestrateur)
13. [Sauvegarder et restaurer](#sauvegarder-et-restaurer)
13. [Services](#services)
13. [Sécurité](#sécurité)
14. [Quand quelque chose ne fonctionne pas](#quand-quelque-chose-ne-fonctionne-pas)
1. [Transcription audio](#transcription-audio)
1. [Licence](#licence)

---

- [Bibliothèques documentaires locales (RAG)](#bibliothèques-documentaires-locales-rag)

## Ce qu'il fait

- **Un agent est un utilisateur Linux.** En créer un dans l'interface web crée
  `agent-007` sur le système, avec un répertoire personnel qu'aucun autre agent
  ne peut lire. L'isolation, c'est cela : celle du noyau, pas un bac à sable
  écrit en Python.
- **Les agents s'exécutent selon leur propre planification.** Chacun a son
  propre crontab, possédé et exécuté par son propre utilisateur : un agent se
  réveille, fait son travail et s'arrête.
- **Vous leur parlez.** Cliquer sur un agent ouvre une conversation :
  demandez-lui de faire quelque chose, il utilise ses outils et répond quand il
  a terminé. La conversation est conservée.
- **Une conversation par agent, pas une par personne.** Une carte qui arrive à
  échéance est publiée dans cette même conversation au moment où l'exécution
  démarre, et la réponse apparaît en dessous : la conversation d'un agent
  contient donc tout ce qu'on lui a demandé - vous ou un autre agent - et ce
  qu'il en a fait.
- **Ils partagent un tableau kanban.** Les agents ajoutent des cartes, les
  déplacent et voient le travail des autres. Vous suivez tout sur `/kanban/` au
  lieu de lire des journaux.
- **N'importe quel modèle, cloud ou auto-hébergé.** Vingt-cinq fournisseurs
  sont inclus - Anthropic, OpenAI, Google, DeepSeek, Mistral, Qwen, xAI et les
  autres ; les routeurs placés devant eux, OpenRouter, Groq, Together, Vercel et
  d'autres ; et Ollama, llama.cpp et vLLM sur votre propre matériel. Chaque
  agent choisit le sien, avec un modèle de secours pour quand celui-ci est en
  panne.
- **Des plafonds de dépense qui l'arrêtent vraiment.** Jetons, étapes, secondes
  et exécutions par jour, par agent. Sans eux, un agent sans surveillance sur
  une API payante est une facture ouverte.
- **Mémoire configurable.** Choisissez la limite de mémoire de chaque agent dans
  ses réglages, de 1 000 à 1 000 000 de caractères (8 000 par défaut). Les
  écritures trop longues sont refusées sans couper le texte ni remplacer la
  mémoire enregistrée.
- **Une bibliothèque documentaire par agent.** Importez des livres en PDF, EPUB,
  TXT ou Markdown. L'extraction, l'OCR et la vectorisation restent locales ; les
  agents récupèrent les passages pertinents et citent leurs sources.
  Configurez-la sous **RAG**. Le modèle de vectorisation est EmbeddingGemma 300M
  par défaut ; une machine qui a du processeur et de la mémoire à revendre peut
  passer à Qwen3-Embedding 0.6B sous **Réglages → RAG**.
- **Des agents que vous pouvez déplacer.** L'onglet **Exporter** d'un agent le
  télécharge sous forme de `.zip` - avec, si vous le voulez, sa mémoire, son
  modèle, sa bibliothèque et les fichiers de son répertoire personnel, jamais
  avec une clé - et **+** l'importe ici ou sur une autre installation. Des
  agents tout prêts viennent du
  [dépôt de modèles](https://github.com/nipegun/bunch-of-aigents-templates).
- **Des outils que vous pouvez étendre.** Chaque outil est un fichier `.py` dans
  `/opt/boa/tools/`. Déposez-en un nouveau et il apparaît sous
  **Réglages → Outils**, regroupé en sous-onglets comme Automatisation et
  Navigateur.
- **Des compétences qu'ils partagent.** Une procédure écrite une seule fois dans
  `/opt/boa/skills/` peut être donnée à autant d'agents que vous le voulez. Ce
  qu'un agent apprend tout seul meurt dans sa propre mémoire ; une compétence,
  non.
- **Un navigateur chacun, avec ses propres sessions.** Un agent peut se
  connecter à un site, remplir un formulaire et cliquer - pas seulement lire une
  page - et ses cookies vivent dans son propre répertoire personnel en 0700 :
  la connexion d'un agent n'est pas celle de tous les agents.
- **Répondez-leur depuis Telegram ou Discord.** Choisissez un agent avec
  /agents, ou répondez à un message que l'un d'eux vous a envoyé : ce que vous
  écrivez lui parvient, lance une exécution et revient avec la réponse sur
  votre téléphone. Tout l'échange figure aussi dans la conversation de cet
  agent dans l'interface web, dans les deux sens, si bien qu'un seul écran
  montre toujours tout.
- **L'audio de Telegram.** **Réglages → Audio** permet de choisir whisper.cpp
  en local, ou OpenAI, Groq, Mistral, Together AI, Hugging Face ou Cloudflare
  avec une clé d'API déjà enregistrée. Les 30 modèles natifs sont proposés,
  téléchargés à la demande. Une réponse vocale parvient à son agent d'origine
  sous forme de texte et apparaît dans la conversation web, avec une lecture
  audio facultative.
- **Un dossier partagé chacun.** Le dossier `samba/` de chaque agent est un
  partage SMB qui porte le nom de son utilisateur Linux : vous pouvez y déposer
  des fichiers depuis Windows, Linux ou macOS.
- **Quinze langues.** Allemand, anglais (Royaume-Uni et États-Unis), espagnol
  (Espagne et Argentine), français, hébreu, hindi, italien, japonais, coréen, portugais
  (Brésil et Portugal), russe et chinois simplifié. L'interface, la ligne qui
  indique à vos agents dans quelle langue répondre, et ce que disent les deux
  bots.

Il est conçu pour une seule personne qui le fait tourner sur son propre réseau
local.

## Sur quoi il tourne

Deux systèmes, et sur chacun d'eux le système d'init fait partie de
l'exigence, ce n'est pas un détail :

- **Debian avec systemd comme PID 1.** Les dix services sont des unités
  systemd. Sur une Debian qui démarre avec autre chose, rien ne peut les lancer :
  l'installateur vérifie donc `systemctl is-system-running` avant de toucher à
  la machine et refuse si systemd n'est pas là. N'essayez pas sur une telle
  machine : la réponse ne changera pas.
- **Alpine avec OpenRC.** Les dix services sont des scripts OpenRC supervisés
  par `supervise-daemon`. Rien n'est à installer à l'avance - l'installateur
  ajoute lui-même `openrc` quand la machine n'en a pas.

Vérifiez-le sous Debian avec `systemctl is-system-running` : la commande doit
répondre (`running`, `degraded`, `starting`), et non afficher « System has not
been booted with systemd as init system (PID 1) ». Un conteneur a besoin de
`systemd systemd-sysv dbus` installés et de `/sbin/init` comme commande.

En plus du système d'init, il lui faut :

- Un accès `root`. Aucun des deux installateurs n'utilise `sudo`, et aucun n'en
  a besoin.
- Environ 500 Mo de disque pour l'application et son environnement Python.
- `haproxy`, installé par l'installateur. Il termine le TLS, parce que l'en-tête
  PROXY qu'envoie le HAProxy de la machine arrive avant la négociation TLS et
  que seul un proxy peut le lire à cet endroit.
- Un modèle à qui parler : soit une clé d'API d'un fournisseur cloud, soit
  Ollama, llama.cpp ou vLLM qui tourne quelque part où vous pouvez le joindre.

L'installateur compile aussi **whisper.cpp v1.9.4** dans `/opt/boa/whisper/`,
installe FFmpeg et télécharge le modèle multilingue `base` (environ 142 Mio de
plus). La compilation, les dépendances système et le navigateur demandent de
l'espace disque supplémentaire. Un interpréteur Python manquant est installé
avant que sa version soit vérifiée.

Tout le reste de ce manuel est identique sur les deux.

## Si vous êtes sous Alpine

Toutes les commandes de ce manuel qui mentionnent `systemctl` ou `journalctl`
sont celles de Debian. L'application est la même sous Alpine ; ce qui change,
c'est le système d'init et l'endroit où vont les journaux :

| Sous Debian | Sous Alpine |
|---|---|
| `systemctl status boa-web` | `rc-service boa-web status`, ou `rc-status` pour les dix |
| `systemctl restart boa-web` | `rc-service boa-web restart` |
| `journalctl -u boa-web -f` | `tail -f /opt/boa/logs/boa-web.log` |
| `install-update-reinstall-debian.sh` | `install-update-reinstall-alpine.sh` |

Une fonctionnalité y manque et ne reviendra pas : il n'y a pas de navigateur,
parce que Playwright ne publie aucune version pour musl. Les outils de
navigateur restent dans la liste et le signalent quand un agent en appelle un.

---

## Installation

Un installateur par distribution, et les deux acceptent les mêmes options.
Exécutez-le en tant que `root`.

### Sous Debian

> **systemd doit tourner sur la machine.** Lancez d'abord
> `systemctl is-system-running` : s'il affiche « System has not been booted with
> systemd as init system (PID 1). Can't operate. », arrêtez-vous là. Chaque
> service installé est une unité systemd, rien ne pourrait donc les démarrer, et
> l'installateur refuse pour cette raison plutôt que de vous laisser une
> installation qui ne sert rien.

```bash
curl -fsSL https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-debian.sh \
  | bash -s -- --install --email you@example.com
```

Si `curl` n'est pas installé - une Debian minimale n'a souvent ni lui ni
`wget` - installez-le d'abord, sinon la ligne ci-dessus affiche `curl: command
not found` et s'arrête :

```bash
apt-get update && apt-get install -y curl
```

Ou téléchargez d'abord l'installateur et lisez-le avant de l'exécuter, ce qui
est la meilleure habitude :

```bash
wget https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-debian.sh
less install-update-reinstall-debian.sh
chmod +x install-update-reinstall-debian.sh
./install-update-reinstall-debian.sh --install --email you@example.com
```

### Sous Alpine Linux

Les mêmes options, un autre script : il écrit des services OpenRC au lieu
d'unités systemd. Une seule ligne, avec `wget` et redirigée vers `sh`, parce
qu'une Alpine fraîchement installée n'a ni `curl` ni bash, alors que `wget` et
`sh` sont tous deux fournis par BusyBox :

```bash
wget -qO- https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-alpine.sh \
  | sh -s -- --install --email you@example.com
```

Utilisez `curl -fsSL` à la place de `wget -qO-` sur une machine qui l'a - et
surveillez cette ligne si vous le faites, parce que `curl: not found` redirigé
vers `sh` affiche son erreur puis **réussit**, sans avoir rien installé.

L'installateur est écrit en shell POSIX plutôt qu'en bash pour la même raison
que le `wget` : une Alpine fraîchement installée n'a pas de bash que
`| bash -s --` puisse atteindre. Il installe bash au passage - chaque agent
reçoit un shell bash - donc sur une machine qui en a déjà un, `| bash -s --`
fonctionne tout aussi bien.

Ou téléchargez-le d'abord et lisez-le avant de l'exécuter :

```bash
wget https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-alpine.sh
less install-update-reinstall-alpine.sh
chmod +x install-update-reinstall-alpine.sh
./install-update-reinstall-alpine.sh --install --email you@example.com
```

Deux choses diffèrent une fois qu'il tourne, et les deux sont le fait du
système, pas une décision :

- **Pas de navigateur.** Playwright ne publie aucune version pour musl et
  Alpine n'en empaquette aucune, donc `browser.open` et les autres le signalent
  quand un agent en appelle un. `web.fetch` et `rss.fetch` fonctionnent comme
  partout ailleurs.
- **`rc-status` au lieu de `systemctl status`**, et
  `rc-service boa-web restart` à la place de `systemctl restart boa-web`. Voir
  [Si vous êtes sous Alpine](#si-vous-êtes-sous-alpine).

Sous Alpine, les services libèrent la sortie SSH de l'installateur, si bien
que l'installateur rend la main à la session quand il a terminé.

### Ce que fait l'installateur

1. Crée l'utilisateur système `boa` et l'arborescence sous `/opt/boa/`.
2. Installe les dépendances Python dans `/opt/boa/venv/`.
3. Génère un certificat TLS autosigné, sauf si vous avez laissé un
   `fullchain.pem` et un `privkey.pem` à vous dans `/opt/boa/certificates/`.
4. Demande s'il faut servir l'application sur 11080/11443 derrière un HAProxy
   sur 80 et 443, ou directement sur 80 et 443. Passez `--ports proxied|direct`
   pour répondre à l'avance. La réponse est mémorisée, donc `--update` ne repose
   jamais la question et ne la change pas en douce. Choisir `direct` met à la
   retraite le HAProxy propre de la machine - arrêté, retiré de tous les
   runlevels ou masqué, et son `/etc/haproxy/haproxy.cfg` supprimé si c'est cet
   installateur qui l'a écrit, conservé sous le nom
   `haproxy.cfg.before-boa.<date>` si c'est quelqu'un d'autre - pour que rien ne
   prenne 80 et 443 au prochain démarrage. Le paquet haproxy lui-même reste : le
   proxy propre de l'application, c'est ce binaire.
5. Crée un seul agent : `manager`, l'orchestrateur. Tout le reste est un agent
   vide, un `.zip` exporté d'un agent, ou un modèle du
   [dépôt de modèles](https://github.com/nipegun/bunch-of-aigents-templates) -
   `web-navigator`, `os-watcher`, `mail-watcher` et d'autres - choisi quand vous
   appuyez sur **+**. L'agent vide est le premier choix proposé.
6. Installe et démarre les services listés sous [Services](#services) : des
   unités systemd sous Debian, des services OpenRC supervisés par
   `supervise-daemon` sous Alpine.
7. Écrit ce qu'il a fait, ainsi que votre mot de passe de connexion, dans
   `/opt/boa/logs/install.log` (root, mode 0600).
8. Demande à l'application sa page de connexion avant de dire qu'il a terminé.
   Si la page ne vient pas, il le dit, écrit dans ce même journal l'état de la
   machine à ce moment-là - ce que curl a obtenu de la requête, si quelque chose
   écoute sur le port, l'état des services et les dernières lignes de ce qu'ils
   ont affiché - et nomme le journal au lieu d'annoncer un succès. Un `--update`
   remet aussi d'abord la version précédente en place.

### Où se trouve le mot de passe

L'adresse e-mail que vous donnez est le seul identifiant de connexion. Le mot de
passe est généré pour vous ; lisez-le avec :

```bash
cat /opt/boa/logs/install.log
```

Ce seul fichier est les deux à la fois : le journal complet de l'installation
et les identifiants qu'elle a générés. La page de connexion le nomme, pour que
personne n'ait à se souvenir de son emplacement.

## Mise à jour et réinstallation

```bash
./install-update-reinstall-debian.sh --update      # conserve les agents et les données
./install-update-reinstall-debian.sh --reinstall   # supprime tout d'abord
```

Sous Alpine, ce sont les deux mêmes options, sur l'autre script :

```bash
./install-update-reinstall-alpine.sh --update
./install-update-reinstall-alpine.sh --reinstall
```

`--reinstall` supprime tous les agents, les répertoires personnels, les
crontabs et le tableau kanban. Il demande une confirmation sauf si vous passez
`--yes`.

Une installation morte à mi-chemin - un téléchargement qui a échoué, un réseau
qui a lâché - se termine en relançant `--install` : elle reprend là où elle
s'était arrêtée, et `--update` le signale s'il en trouve une.

Les deux autres options, `--backup` et `--restore`, sont expliquées dans
[Sauvegarder et restaurer](#sauvegarder-et-restaurer).

## Ouvrir l'application

Dans le mode par défaut `proxied`, le HAProxy propre de l'application écoute
sur `127.0.0.1:11443` (HTTPS) et `127.0.0.1:11080` (HTTP, qui redirige). Ces
ports ne sont pas joignables depuis l'extérieur du serveur : c'est le HAProxy
propre de la machine qui sert le réseau local, et il transmet vers 11443 avec
`send-proxy-v2` pour que la véritable adresse du client survive. En mode
`direct`, l'application écoute elle-même sur 80 et 443, sans rien devant.

Une fois cela en place, ouvrez :

```
https://your-server/
```

Le certificat est autosigné, sauf si vous avez laissé vos propres certificats
dans `/opt/boa/certificates/`, donc le navigateur vous avertira une fois.

### À quoi doit ressembler le HAProxy de la machine

Le backend qui pointe vers cette application a besoin de deux choses :

```
backend https-out
  mode tcp
  server srv-https-out 127.0.0.1:11443 check port 11080 send-proxy
```

- **`send-proxy`**, pour que la véritable adresse du client atteigne
  l'application. Sans lui, chaque requête semble venir de 127.0.0.1 et la
  limitation des tentatives de connexion cesse de s'appliquer par adresse.
- **`check port 11080`**, pour que le contrôle de santé frappe au port HTTP en
  clair et non au port TLS. Un contrôle TCP sur le port TLS se connecte et
  raccroche sans négociation, et le HAProxy propre de l'application enregistre
  chacun comme un échec de négociation SSL : une ligne toutes les deux
  secondes, pour toujours. Les deux ports appartiennent à un même processus,
  donc si l'un répond, l'autre est là. N'ajoutez pas `check-send-proxy` :
  11080 n'accepte pas le protocole PROXY.
- **Aucune `option ssl-hello-chk`.** Son ClientHello est antérieur à TLS 1.2,
  donc un backend qui exige TLS 1.2 - celui-ci, et tout Apache ou nginx
  moderne - échoue au contrôle et reste marqué hors service pour toujours. Le
  symptôme est un 503 venant d'un service qui fonctionne parfaitement. Un
  simple `check` vérifie déjà que le port répond.

## Se connecter

Ouvrez `https://your-server/` et connectez-vous avec l'adresse e-mail que vous
avez donnée à l'installateur et le mot de passe qu'il a généré. Si vous ne
l'avez pas :

```bash
cat /opt/boa/logs/install.log
```

Ce fichier est le journal complet de l'installation, avec les identifiants à la
fin, et la page de connexion le nomme précisément pour ce moment-là.

**Se déconnecter** ouvre une confirmation au centre de l'écran. Confirmez pour
mettre fin à la session, ou choisissez **Annuler** ou appuyez sur Échap pour
rester connecté.

Il y a un seul compte. Changez son mot de passe sous **Réglages → Compte**. Le
changer demande aussi le mot de passe actuel : c'est ce qui en fait un
changement fait par vous plutôt que par quiconque trouverait le navigateur
ouvert. Cela met aussi fin à toutes les autres sessions, sur tous les autres
appareils, d'un coup - et c'est tout l'intérêt de le changer quand vous pensez
que quelqu'un d'autre en a une.

La première fois que vous ouvrez l'application après une mise à jour, elle
vous demande de vous reconnecter. Les sessions antérieures à la mise à jour ne
gardent aucune trace du moment où elles ont été accordées, et à « je ne peux
pas le savoir », on répond en demandant.

Après dix tentatives échouées depuis la même adresse, la connexion est fermée
pendant quinze minutes, y compris pour les mots de passe corrects.

## Premier démarrage

1. Connectez-vous avec votre e-mail et le mot de passe généré.
2. Si l'agent doit utiliser un fournisseur cloud, enregistrez d'abord sa clé
   sous **Réglages → Clés d'API** : la liste des fournisseurs ne propose que
   les fournisseurs cloud qui ont une clé (voir [Clés d'API](#clés-dapi)).
3. Appuyez sur **+** dans la barre latérale pour créer votre premier agent.
4. Choisissez son fournisseur et son modèle. Pour Ollama sur la même machine,
   les valeurs par défaut sont déjà les bonnes. Pour facturer cet agent-là sur
   un autre compte, donnez-lui sa propre clé (voir
   [Donner un modèle à un agent](#donner-un-modèle-à-un-agent)).
5. Écrivez son prompt système : à quoi il sert, et ce que « terminé » veut
   dire.
6. Donnez-lui les outils dont il a besoin. Commencez par ceux du kanban.
7. Appuyez sur **Exécuter maintenant** et regardez le tableau.
8. Quand il fait ce que vous voulez, donnez-lui une planification.

## L'interface

Le logo bleu circulaire montre trois agents robotiques aux panneaux faciaux
clairs, aux visières sombres et aux yeux bleus, en costume noir, chemise
blanche et cravate sombre. On les voit à partir de la taille, avec un agent
central plus grand. Le logo apparaît sur la page de connexion, dans la barre
latérale et dans l'onglet du navigateur.

La barre latérale, à gauche, liste vos agents. Chacun affiche son identifiant,
son nom, combien de fois il s'est exécuté et combien de jetons il a dépensés.
Toutes les cases ont la même hauteur, donc un nom long est coupé par des points
de suspension - survolez-le pour le lire en entier. Le carré autour de
l'identifiant est cerclé de vert quand l'agent est allumé et de rouge quand il
ne l'est pas.

**Quand un agent travaille, un segment lumineux parcourt cet anneau vert dans
le sens des aiguilles d'une montre.** Il vous indique que l'agent est en pleine
exécution à cet instant - pas ce qu'il fait, seulement qu'il fait quelque
chose. Il se met à tourner dès que vous lui envoyez un message dans la
conversation ou que vous appuyez sur **Exécuter maintenant**, et s'arrête
quand l'exécution se termine, qu'elle vienne de vous, de sa planification ou
d'une carte arrivée à échéance. L'anneau est vérifié toutes les quelques
secondes, il peut donc avoir un léger retard.

En bas de la barre latérale, deux points indiquent si les services en
arrière-plan tournent. Si l'un des deux est rouge, les agents ne s'exécuteront
pas — voir
[Quand quelque chose ne fonctionne pas](#quand-quelque-chose-ne-fonctionne-pas).

Le bouton **+** crée un agent.

## L'agent de départ

L'installation en crée exactement un.

**`manager` (agent-000)** coordonne les autres. Il découpe les objectifs en
cartes et les distribue. Il est allumé dès le départ.

C'est délibérément tout : une installation qui arrive avec des agents que
personne n'a demandés est une installation qui commence par des choses à
éteindre. Tout le reste est un **modèle** du dépôt de modèles, ou un `.zip` que
quelqu'un a exporté, proposé quand vous appuyez sur **+**.

## D'où part un nouvel agent

Appuyez sur **+** et on vous demande d'où partir :

| Choix | Ce qu'il fait |
|---|---|
| **Agent vide** | Aucun prompt, aucun outil, aucune planification. À vous de l'écrire. |
| **Importer depuis un fichier .zip** | Un agent exporté depuis son onglet **Exporter**, ici ou sur une autre installation. |
| **Importer depuis un modèle GitHub** | Un des agents du dépôt de modèles, choisi dans une liste. |

L'**agent vide** est en tête de liste, parce que c'est la seule réponse
toujours juste et que toutes les autres ne sont qu'un raccourci pour y arriver.

### Modèles depuis GitHub

Les modèles vivent dans un dépôt à part,
[bunch-of-aigents-templates](https://github.com/nipegun/bunch-of-aigents-templates),
un dossier chacun, si bien qu'un nouveau modèle arrive sur votre installation
sans qu'il faille la mettre à jour. Quand vous choisissez **Importer depuis un
modèle GitHub**, le serveur télécharge ce dépôt (un seul `.tar.gz`, conservé
cinq minutes) et liste ses agents par ordre alphabétique, chacun avec sa
description dans votre langue, les familles d'outils qu'il apporte, la
fréquence à laquelle il se réveille et s'il active sa bibliothèque. Un outil
que cette installation n'a pas est laissé de côté, et la liste le signale. Un
modèle qui échoue aux vérifications n'est pas proposé, et une ligne indique
combien ont été écartés.

Voici les modèles que contient le dépôt aujourd'hui :

| Modèle | Ce qu'il fait |
|---|---|
| **backup-watcher** | Vérifie que vos sauvegardes ont tourné, qu'elles sont récentes et qu'elles ne sont pas étrangement petites. |
| **cert-watcher** | Prévient quand un certificat TLS est sur le point d'expirer, tant qu'il est encore temps. |
| **disk-cleaner** | Trouve ce qui remplit le disque et dit ce qui pourrait partir. Propose ; ne supprime jamais. |
| **kanban-watcher** | Lit le tableau chaque matin de semaine et écrit un court résumé. |
| **log-watcher** | Lit les journaux que vous lui indiquez et signale ce qui est nouveau ou devenu fréquent. |
| **mail-watcher** | Surveille une boîte aux lettres et agit sur ce qui arrive, en suivant les règles que vous écrivez dans son prompt. |
| **news-watcher** | Lit les flux RSS que vous listez dans son prompt et signale ce qui correspond à vos règles. |
| **os-watcher** | Surveille cette machine : disque, mémoire, swap, charge, et si les services tournent. |
| **rag-consultant** | Répond aux questions à partir des documents de sa bibliothèque RAG, en citant le passage qui étaye chaque affirmation, et le dit quand les documents ne couvrent pas un sujet. |
| **site-watcher** | Vérifie que les sites que vous listez répondent, répondent vite, et disent encore ce qu'ils disaient. |
| **web-navigator** | Pilote son propre navigateur pour faire ce que vous demandez sur un site : chercher, se connecter, remplir un formulaire, cliquer de page en page, et rapporter ce qu'il a trouvé. |

`web-navigator` et `rag-consultant` n'ont pas de planification : ils
travaillent quand vous le leur demandez, et la demande est la tâche.
`web-navigator` est aussi celui qui montre à quoi sert le navigateur installé -
il se connecte, clique et remplit des formulaires, là où les autres lisent des
pages. Il ne tapera pas de mot de passe, n'achètera rien et n'appuiera pas sur
un bouton d'envoi : il arrive à cette étape et s'arrête, en disant quel bouton
terminerait le travail.

`rag-consultant` répond à partir de sa propre bibliothèque documentaire, et
c'est le seul modèle qui arrive avec cette bibliothèque activée : ses outils
lui sont retirés tant que la bibliothèque est désactivée. Avant qu'il serve à
quoi que ce soit, importez des documents dans son onglet **RAG** (voir
[Bibliothèques documentaires locales](#bibliothèques-documentaires-locales-rag))
et choisissez un modèle. Chaque affirmation de ses réponses renvoie à la page
du document d'où elle vient ; quand les documents ne couvrent pas un sujet, il
le dit au lieu de combler le vide. Son plafond de jetons (40 000 par
exécution) est plus élevé que celui des autres, parce que les passages qu'il
lit y sont décomptés.

Chaque modèle indique, avant que vous le choisissiez, quelles familles
d'outils il apporte et à quelle fréquence il se réveille. Un modèle est un
ensemble de permissions autant qu'un prompt : « surveille une boîte aux
lettres » ne vous dit pas qu'il arrive capable de supprimer du courrier.

Chaque modèle arrive **éteint et sans modèle de langage** : en choisir un vous
donne son prompt, ses outils et une planification suggérée, puis il attend que
vous choisissiez un fournisseur et que vous l'allumiez.

Ce sont des points de départ. Changez le prompt, les outils, la planification -
tout - et plusieurs d'entre eux disent dans leur propre prompt ce que vous
devez remplir avant qu'ils servent à quelque chose, plutôt que d'échouer à
trois heures du matin.

**Réglages → Agents** indique de quel dépôt et de quelle branche vient la
liste : celui du projet par défaut, ou un fork, ou l'un des vôtres avec la même
structure. Une machine sans accès à GitHub peut utiliser un chemin `file://`
contenant `archive/refs/heads/<branch>.tar.gz`, la même structure que celle
qu'accepte l'installateur. Quand le dépôt est injoignable, la liste indique
quelle adresse a échoué ; l'importation d'un `.zip` continue de fonctionner.

### Importer un .zip

1. Choisissez le `.zip`. Il est envoyé par morceaux, avec un pourcentage, si
   bien qu'une bibliothèque de plusieurs centaines de Mio arrive elle aussi.
2. Le serveur vérifie le paquet entier avant toute autre chose. Rien dedans ne
   peut être un chemin qui sort du répertoire personnel de l'agent, un fichier
   caché comme `.ssh` ou `.bashrc`, la conversation ou le journal
   d'exécutions, ni une planification qui porte une commande. Quand quelque
   chose ne va pas, on vous dit quoi, et rien n'est créé.
3. On vous montre ce qu'il apporterait : sa description, ses outils (et ceux
   qui manquent à cette installation), ses planifications, et s'il apporte sa
   mémoire, des fichiers pour son répertoire personnel, des documents de
   bibliothèque ou un modèle. Confirmez, et donnez-lui un nom.
4. Il s'installe en arrière-plan, avec sa progression à l'écran. Les documents
   de la bibliothèque sont envoyés un par un et réindexés ici. Si quelque
   chose échoue en cours de route, l'agent est supprimé à nouveau plutôt que
   laissé à moitié installé.

Un agent importé arrive **éteint**, lui aussi. S'il nomme un fournisseur, sa
clé doit être définie sur cette installation : les clés ne voyagent jamais dans
un `.zip`.

Si vous préférez qu'on ne vous demande rien, décochez **Demander d'où part un
nouvel agent** sous **Réglages → Interface** : **+** va alors directement à un
agent vide.

### Aucun agent n'a root

Pas un seul, l'orchestrateur compris. C'est tout le modèle d'isolation, et il
vaut la peine d'être clair là-dessus, parce que c'est lui qui décide de ce
qu'un agent comme `os-watcher` peut faire :

- **Regarder ne demande aucun privilège.** `df`, `free`, `uptime`, `nproc`,
  `systemctl is-active` fonctionnent tous en simple utilisateur. Un agent peut
  voir un disque se remplir bien avant qu'il soit plein.
- **Réparer en demande généralement, et il n'en a pas.** Les prompts lui
  disent d'indiquer exactement ce qu'il exécuterait au lieu d'essayer et
  d'échouer : une carte disant « root nécessaire : journalctl
  --vacuum-size=200M libérerait environ 1,2 G » vaut mieux qu'une tentative
  ratée.

Si vous voulez qu'une chose soit réparée automatiquement, mettez cette commande
dans le crontab propre de root. Un agent qui décide tout seul de supprimer des
fichiers en tant que root n'est une fonctionnalité que personne ne veut à
trois heures du matin.

## Créer votre premier agent

Appuyez sur **+**, choisissez un agent vide, un `.zip` ou un modèle, et
donnez-lui un nom. Cela crée, sur le serveur :

- l'utilisateur Linux `agent-001`,
- son répertoire personnel dans `/opt/boa/agents/001/`, en mode 0700,
- `info.json`, `system-prompt.md` et un jeton d'API à l'intérieur.

L'identifiant est le plus petit numéro libre. `000` est réservé à
l'orchestrateur.

Un nouvel agent démarre avec les outils du kanban et rien d'autre, et avec des
plafonds prudents. Il n'a pas de planification, il ne fait donc rien tant que
vous ne lui en donnez pas une ou que vous n'appuyez pas sur **Exécuter
maintenant**.

## Parler à un agent

Cliquez sur un agent dans la barre latérale et vous obtenez sa conversation.
Tapez ce que vous voulez qu'il fasse et appuyez sur Entrée ; Maj+Entrée
commence une nouvelle ligne.

La zone de saisie reste en place, juste au-dessus de la barre d'état en bas de
la page : seule la conversation au-dessus défile, donc elle n'est jamais
masquée et vous n'avez jamais à descendre pour l'atteindre. Tant qu'elle est
vide, elle vous rappelle, en gris, comment se comporte Entrée - ou que l'agent
travaille encore - et sur un téléphone étroit elle s'agrandit d'une ligne ou
deux pour que ce rappel ne soit jamais coupé.

Un message est une exécution : l'agent utilise ses outils, fait le travail et
répond quand il a terminé. Cela peut prendre des minutes, donc la zone de
rédaction est désactivée pendant qu'il travaille et la réponse apparaît quand
elle arrive. Chaque réponse affiche ce qu'elle a coûté, en jetons et en
étapes.

Les réponses sont rendues en markdown - titres, tableaux, listes, citations et
blocs de code - parce que c'est ainsi qu'un modèle écrit. Vos propres messages
sont affichés exactement comme vous les avez tapés. Un lien n'est un lien que
s'il pointe vers http ou https ; tout le reste reste le texte qu'il était.

La conversation est conservée. Les dix derniers échanges sont renvoyés au
modèle à chaque message, pour que l'agent sache de quoi vous parliez - et c'est
pourquoi un long fil coûte plus cher par message qu'un court. **Vider la
conversation** repart de zéro.

Parler à un agent ne compte **pas** dans son plafond d'exécutions par jour : ce
plafond existe pour arrêter une planification sans surveillance, pas pour vous
empêcher de taper. Les plafonds par exécution sur les jetons, les étapes et le
temps s'appliquent, eux.

Chaque agent a sa propre conversation, stockée dans son propre répertoire
personnel, et aucun agent ne peut lire ce que vous avez dit à un autre.

La conversation n'est pas seulement ce que vous avez tapé. Quand l'une des
cartes de l'agent arrive à échéance, la carte est publiée dans cette même
conversation au moment où l'exécution démarre, et la réponse de l'exécution
apparaît en dessous - si bien qu'ouvrir un agent montre tout ce qu'on lui a
demandé, vous ou un autre agent, et ce qu'il en a fait. Voir
[Quand une carte s'exécute](#quand-une-carte-sexécute).

### API Calls

Le nom de l'agent apparaît au-dessus des onglets Conversation et API Calls.
Seul **Conversation** est visible par défaut. Pour afficher l'autre onglet,
ouvrez la clé à molette de l'agent, sélectionnez **Interface**, cochez
**Afficher l’onglet API Calls** et appuyez sur **Enregistrer**. Le choix est
enregistré pour cet agent sur le serveur. Ouvrir ou recharger un agent commence
toujours sur Conversation, même quand API Calls est activé.

**API Calls** montre le JSON réellement envoyé, y compris le prompt complet de
l'agent, la conversation, les définitions d'outils et les résultats d'outils
envoyés dans cette requête. La requête la plus récente est dépliée ; dépliez un
autre appel pour l'examiner. Les nouveaux appels apparaissent pendant que
l'agent s'exécute, y compris les requêtes en échec, les nouvelles tentatives du
SDK et les appels à son modèle de secours. L'indentation et les couleurs
rendent le JSON lisible sans l'afficher comme une conversation ni arrondir les
grands identifiants numériques.

Les 100 dernières requêtes complètes sont conservées à part de la conversation.
Vider la conversation ne les efface pas. L'enregistrement commence avec cette
version ; les requêtes antérieures ne peuvent pas être reconstituées. Les
en-têtes d'authentification ne sont pas enregistrés.

## Réglages de l'agent

L'en-tête affiche **Configuration de l’agent 001**, avec l'identifiant de
l'agent sélectionné. **Exécuter maintenant** n'apparaît que dans l'espace de
travail qui contient Conversation et API Calls. Pour supprimer un agent, ouvrez
**Général → Supprimer l’agent** et confirmez son nom dans la boîte de dialogue.
La suppression est une section à part, sous Identité.


La conversation, c'est ce que vous obtenez en cliquant sur un agent. Tout le
reste - modèle, outils, plafonds, prompt système, planification - se trouve
derrière la **clé à molette**, à droite de la case de l'agent dans la barre
latérale.

## Exporter un agent

Le dernier onglet des réglages d'un agent, **Exporter**, le télécharge sous
forme de `.zip` que **+ → Importer depuis un fichier .zip** peut installer, ici
ou sur une autre installation. Sa configuration, son prompt système et ses
planifications y figurent toujours. Quatre choses n'y figurent que si vous les
cochez, et chaque case dit à l'avance ce qu'elle ajouterait :

| Option | Ce qu'elle ajoute |
|---|---|
| **Mémoire** | Son `memory.md`, avec le nombre de caractères qu'il contient |
| **Fournisseur et modèle** | Quel fournisseur et quel modèle il utilise. Jamais la clé |
| **Documents de la bibliothèque** | Les originaux de sa bibliothèque avec leurs informations (titre, année...). Ils sont réindexés là où ils sont importés |
| **Fichiers de son dossier personnel** | Ses scripts, son dossier `samba` et tout ce qu'il garde d'autre dans son répertoire personnel. Ils peuvent contenir des choses que vous ne partageriez pas, donc la liste des fichiers est affichée avant le téléchargement |

Certaines choses n'y figurent jamais, quoi que vous cochiez : les clés d'API, le
jeton propre de l'agent, les identifiants des canaux, sa conversation, son
journal d'exécutions, ses sessions de navigateur et les fichiers cachés de son
répertoire personnel. De son crontab, seules les planifications qui lancent
l'agent voyagent, pas les autres commandes que quelqu'un y aurait tapées : un
`.zip` qui transporterait des commandes les exécuterait sur la machine où il
est importé.

## Dossiers partagés Samba

Chaque agent a un dossier `samba/` dans son répertoire personnel, exporté
automatiquement sous son nom d'utilisateur Linux. Par exemple, le partage
**agent-001** ne pointe que vers `/opt/boa/agents/001/samba/`. Renommer l'agent
dans Général ne renomme pas le partage. Le reste de son répertoire personnel et
sa configuration protégée ne sont pas exportés.

1. Ouvrez **clé à molette → Samba** de l'agent.
2. Saisissez un **nouveau mot de passe Samba** d'au moins 8 caractères, choisissez les autorisations et appuyez sur **Enregistrer**.
3. Ouvrez l'adresse Windows ou SMB affichée dans l'onglet - `\\server\agent-001` sous Windows, `smb://server/agent-001` sous Linux et macOS - et connectez-vous avec le nom d'utilisateur affiché et ce mot de passe.

Le partage démarre activé, visible dans la liste des partages du serveur et
configuré en lecture/écriture, avec l'accès invité désactivé. Avant sa
première connexion authentifiée, définissez son mot de passe dans cet onglet.
Un champ de mot de passe laissé vide lors des enregistrements suivants conserve
le mot de passe existant. Les identifiants Samba sont distincts des
identifiants de connexion Linux ; les définir ne déverrouille pas le compte
Linux de l'agent.

| Réglage | Effet |
|---|---|
| Partager ce dossier | Active ou désactive cette ressource sans supprimer ses fichiers |
| Authentification | Utilisateur et mot de passe de l'agent par défaut ; accès invité seulement s'il est choisi explicitement |
| Autorisations | Lecture seule ou lecture/écriture via SMB ; l'agent peut toujours travailler sur ses propres fichiers locaux |
| Visibilité et description | S'il apparaît dans la liste des partages du serveur, et sa description |
| Droits des nouveaux fichiers/dossiers | Modes Unix en octal, initialement `0600` / `0700` ; les fichiers existants gardent leurs modes |

Le nom et le chemin du partage sont fixes. Le dossier reste privé pour son
propriétaire Linux. Enregistrer des réglages d'accès modifiés ferme les
connexions existantes de ce partage, pour que les clients se reconnectent avec
les nouvelles autorisations. Les partages des autres agents restent actifs. Le
mot de passe lui-même n'est jamais renvoyé par l'API ni stocké dans
`info.json`.

`--update` ajoute les dossiers et les partages Samba aux agents existants,
`agent-000` compris. Supprimer un agent retire
son partage et son compte Samba en même temps que son répertoire personnel.
`--backup` / `--restore` préservent les données partagées, les réglages, les
mots de passe Samba et les identités des comptes. La restauration vérifie le
mode de ports web enregistré, y compris pour les installations qui servent
directement le 443.

Samba utilise le port TCP **445**, indépendamment du proxy web. Sous Docker, ce
port doit être publié explicitement. BoA fait tourner son propre service
`boa-samba`, avec sa propre configuration et sa propre base de mots de passe
sous `/opt/boa/samba/` ; il n'écrasera ni ne s'appropriera la configuration
d'un autre serveur Samba, et l'installateur refuse de prendre le contrôle d'une
installation Samba existante qu'il ne gère pas.

## Donner un modèle à un agent

Sous **LLM**, choisissez un fournisseur. La liste est courte exprès : elle
propose les trois fournisseurs auto-hébergés, qui n'ont besoin d'aucune clé, et
tous les fournisseurs cloud dont la clé est définie dans
**Réglages → Clés d'API**. Un fournisseur cloud sans clé mènerait l'agent
jusqu'à sa première exécution et échouerait là, donc il n'est pas proposé.
Définissez sa clé et il apparaît.

Un agent déjà configuré avec un fournisseur continue de le voir dans la liste
même si sa clé est retirée, marqué *(aucune clé configurée)* - sinon la case
afficherait un fournisseur que personne n'a choisi et l'enregistrerait au clic
suivant.

**Sur votre propre matériel.** Pas de clé, et la case URL de base indique où écoute votre propre serveur.

| Fournisseur | Modèles listés | Modèle par défaut |
|---|---|---|
| `ollama` | 23 | `gpt-oss:20b` |
| `llamacpp` | 1 | `local-model` |
| `vllm` | 3 | vous nommez le modèle |

**Les entreprises qui servent les modèles qu'elles ont construits.**

| Fournisseur | Modèles listés | Modèle par défaut |
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

**Hébergeurs et routeurs, qui servent des modèles construits par d'autres.** Une seule clé donne accès à de nombreux modèles ; l'identifiant du modèle indique lequel.

| Fournisseur | Modèles listés | Modèle par défaut |
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

Un fournisseur demande deux valeurs dans la case de la clé : **Cloudflare
Workers AI** construit son adresse à partir de l'identifiant du compte, donc sa
clé s'écrit `account-id:api-token`, les deux moitiés venant du tableau de bord
Cloudflare. La case de **Réglages → Clés d'API** l'indique.

Le champ du modèle suggère ce que sert ce fournisseur, et filtre la liste à mesure que vous tapez - mais c'est une zone de texte normale, donc un modèle sorti ce matin peut simplement y être tapé. Ces suggestions viennent de `/opt/boa/config/providers/<provider>.json`, que vous pouvez modifier sur le serveur ; une mise à jour n'écrase jamais un fichier que vous avez changé.

Les fournisseurs auto-hébergés n'ont besoin de rien d'autre s'ils tournent sur
la même machine.

**URL de base** n'apparaît que pour `ollama`, `llamacpp` et `vllm`, et c'est
l'adresse où écoute votre propre serveur - la valeur par défaut est le port
habituel sur cette machine, ce qui est juste quand le modèle tourne à côté de
l'application. Choisissez un fournisseur cloud et la case disparaît : cette
adresse est fixe, cette installation la connaît déjà, et la seule chose qu'une
case pourrait faire là serait de laisser une faute de frappe casser un agent
qui fonctionne. Le modèle de secours fonctionne de la même façon.

Pour un fournisseur cloud, le chemin le plus simple est l'onglet **Clés d'API** des Réglages, que tous les agents de ce fournisseur utilisent alors. Pour donner à cet agent-là une clé différente, écrivez-la dans son propre répertoire personnel, en tant que root :

```bash
mkdir -p /opt/boa/agents/001/keys
echo "sk-..." > /opt/boa/agents/001/keys/anthropic.key
chown -R agent-001:agent-001 /opt/boa/agents/001/keys
chmod 700 /opt/boa/agents/001/keys
chmod 600 /opt/boa/agents/001/keys/anthropic.key
```

Le nom du fichier est le nom du fournisseur. Chaque agent ne lit que sa propre
clé, donc un agent ne peut pas dépenser le budget d'un autre.

### Clés d'API

Les Réglages ont un onglet **Clés d'API** : une clé par fournisseur cloud,
partagée par tous les agents qui l'utilisent. Les fournisseurs auto-hébergés
n'y figurent pas, parce qu'ils n'en ont pas besoin.

Une clé est stockée dans `/opt/boa/config/apikeys/<provider>.key`. Le
répertoire est en `0700` et les fichiers en `0600`, tous appartenant à
l'utilisateur web, donc aucun agent ne peut en lire aucun : ni la clé d'un
autre fournisseur, ni la sienne. Quand un agent s'exécute, l'API des agents lui
remet la clé **du fournisseur avec lequel cet agent est configuré, et d'aucun
autre** : un agent sur Ollama ne peut pas demander la clé d'Anthropic.

Les installations faites avant que ce répertoire soit renommé gardent leurs
clés dans `/opt/boa/config/keys/` ; `--update` les déplace et supprime l'ancien
répertoire.

Il vaut la peine d'être clair sur ce que cela protège et ne protège pas. Un
agent qui utilise légitimement un fournisseur payant détient sa clé pendant
qu'il s'exécute - il en a besoin pour faire l'appel, et un agent qui a
`bash.run` pourrait l'afficher. Ce qu'empêche le stockage partagé, c'est qu'un
agent collecte les clés de fournisseurs qu'il n'utilise pas, et il garde toutes
les clés hors des répertoires personnels des agents, où une seule sauvegarde
égarée les exposerait toutes d'un coup.

Pour facturer un agent sur un autre compte, mettez une clé dans son propre
répertoire personnel, dans `keys/<provider>.key`. Celle-là l'emporte sur la clé
partagée.

## Écrire un prompt système

Le prompt système, c'est ce qu'est l'agent. Il est stocké sous
`system-prompt.md` dans le répertoire personnel de l'agent et vous le modifiez
dans l'interface.

Ce qui marche :

- **Dites à quoi sert l'agent**, en une ou deux phrases.
- **Dites ce que « terminé » veut dire.** Un agent sans définition de
  « terminé » s'arrête soit trop tôt, soit jamais.
- **Dites quoi faire en cas de blocage.** Sans cela, les modèles inventent un
  moyen de contourner l'obstacle. « Si vous ne pouvez pas le faire, dites-le
  sur le tableau et arrêtez-vous » suffit.
- **Dites-lui de lire le tableau en premier.** C'est la seule mémoire qu'il a
  d'une exécution à l'autre.

Ce qui ne marche pas : lui dire de ne pas utiliser un outil. Si vous ne voulez
pas qu'il utilise un outil, ne lui donnez pas l'outil — le prompt est une
suggestion, la liste d'outils est imposée.

## Ce dont un agent se souvient

Chaque agent a un `memory.md` dans son répertoire personnel, et ce fichier est
la seule chose qu'il emporte d'une exécution à la suivante. Il y écrit avec
`memory.append` quand il apprend quelque chose qui mérite d'être gardé, et il
le range avec `memory.replace`.

Le fichier entier est chargé au début de chaque exécution, ce qui le rend utile
et aussi ce qui le rend coûteux : chaque caractère est payé à chaque appel au
modèle. Sous **Réglages de l'agent → Mémoire → Limite de mémoire
(caractères)**, choisissez une limite de 1 000 à 1 000 000 de caractères. La
valeur par défaut est 8 000, y compris pour les agents existants. On demande à
l'agent de ranger sa mémoire au-delà de 75 % de sa limite.

Le compteur affiche le nombre actuel et la limite choisie, espaces et sauts de
ligne compris. Vous pouvez augmenter la limite et coller une mémoire plus
grande dans le même enregistrement. Si le texte dépasse la limite choisie, rien
de cette demande de réglages n'est enregistré : raccourcissez le texte ou
relevez la limite. La mémoire précédente reste intacte ; les nouvelles
écritures n'ajoutent jamais `[truncated]`. Le texte écarté auparavant doit être
recollé depuis l'original. La mémoire complète doit toujours tenir dans le
contexte du modèle choisi, avec le prompt, la conversation et les outils.

Ce qu'il est bon de garder : où se trouve quelque chose, ce qu'une commande
s'est révélée être, ce que vous préférez. Pas le journal de ce qu'il a fait -
c'est le rôle du tableau.

Vous pouvez la lire et la corriger vous-même sous **Mémoire** dans les réglages
de l'agent. Un fait faux sur lequel un agent continue d'agir mérite d'être
corrigé à la main.

## Bibliothèques documentaires locales (RAG)

Chaque agent a sa propre bibliothèque sous `/opt/boa/agents/<id>/rag/`. Les
fichiers PDF, EPUB, TXT en UTF-8 et Markdown sont pris en charge. L'installateur
prépare le modèle de vectorisation local - EmbeddingGemma 300M Q8 (environ
318 Mio), sauf si un autre a été choisi (voir [Choisir le modèle de vectorisation](#choisir-le-modèle-de-vectorisation)) -
son moteur llama.cpp et l'OCR.
L'extraction, l'OCR, la vectorisation des documents et celle des requêtes
s'exécutent sur ce serveur. Les passages récupérés sont envoyés au fournisseur
de réponse choisi pour l'agent, y compris aux fournisseurs cloud s'ils sont
configurés. Aucun point d'accès de vectorisation externe n'est disponible.
L'installation, les mises à jour, l'importation de documents, l'OCR et la
sauvegarde/restauration ont été vérifiées sous Debian 13 et Alpine 3.24, y
compris le démarrage des services après un redémarrage.

1. Ouvrez **Réglages → RAG** et vérifiez que le moteur local est prêt.
2. Ouvrez l'onglet **RAG** d'un agent, activez la recherche documentaire et
   enregistrez l'agent. Le modèle **rag-consultant** arrive avec la recherche
   documentaire déjà activée.
3. Choisissez des fichiers et cliquez sur **Importer des documents**. Les gros
   fichiers voyagent par morceaux. Vous pouvez aussi copier des fichiers
   complets dans `rag/inbox/` et cliquer sur **Importer les fichiers de
   rag/inbox**. Les originaux importés sont déplacés dans le stockage de
   documents géré.
4. Attendez **Prêt**. L'extraction et la vectorisation s'exécutent en
   arrière-plan ; les autres documents prêts restent consultables. La page
   affiche la progression et les erreurs.
5. Testez une question avec **Rechercher dans la bibliothèque**, ou posez-la à
   l'agent dans sa conversation habituelle. Les citations renvoient à la page du
   PDF source ou au document EPUB ou d'origine.

Les erreurs d'importation depuis `rag/inbox/` apparaissent au-dessus de la liste
des documents. Les originaux en échec restent dans la boîte de réception pour
être corrigés. L'indexation traite des lots limités, pour que les petits
documents n'attendent pas toute une rotation de l'ordonnanceur entre chaque
livre.

Les champs **Informations du document** modifient, dans cet ordre, l'année de
publication, le titre, le sous-titre, le ou les auteurs, la version, la langue
et les étiquettes. L'année est facultative et accepte jusqu'à quatre chiffres.
Le sous-titre, quand il y en a un, s'affiche dans la liste des documents juste
sous le titre. Le sous-titre, l'année, l'auteur, la version et la langue
accompagnent chaque passage que l'agent récupère, pour qu'il puisse distinguer
des documents de même titre, dater et attribuer ce qu'il cite, et distinguer
des éditions qui se contredisent. Remplacer un fichier conserve le document
consultable précédent
jusqu'à ce que le nouveau ait fini d'être indexé. Si le moteur de vectorisation
local s'arrête pendant l'indexation d'un document (une mise à jour, un
redémarrage), le document repasse à **En attente** avec le message « Local
embeddings are unavailable » et, dès que le moteur répond de nouveau, reprend là
où il s'était arrêté ; il n'y a rien à réindexer. Réindexer reconstruit un document ; Annuler arrête son travail
en attente ; Supprimer le retire des recherches futures. Les filtres de langue
et de version utilisent les métadonnées que vous avez saisies. Les citations
d'EPUB identifient des chapitres, pas des numéros de page inventés. Les PDF
numérisés ont besoin que les langues d'OCR soient installées sur le serveur ;
l'anglais et l'espagnol sont installés par défaut (`eng+spa`). Les fichiers non
pris en charge ou chiffrés signalent une erreur au lieu d'un index vide réussi.

**Mode de réponse** décide jusqu'où l'agent peut aller au-delà de ses
documents ; la ligne sous la liste dit ce que fait le mode choisi.

- **Documents et connaissances générales** : l'agent peut utiliser les deux, en
  les gardant séparés.
- **Sources documentaires requises** : l'agent doit lui-même chercher dans la
  bibliothèque avant de répondre ; une réponse donnée sans recherche lui est
  renvoyée une fois. Si l'exécution n'a récupéré aucun passage, vous obtenez la
  phrase fixe « The document library does not contain enough information to
  answer this question » (la bibliothèque documentaire ne contient pas assez
  d'informations pour répondre à cette question) au lieu de ce que le modèle a
  écrit.
- **Documents uniquement (vérifié)** : comme le précédent, et chaque paragraphe
  et chaque élément de liste de la réponse doit citer un passage récupéré
  pendant cette exécution. Chaque paragraphe est contrôlé : l'absence de
  citation, la citation d'un passage qui n'a pas été récupéré, ou un sens
  éloigné du passage cité (mesuré avec le moteur de vectorisation local)
  renvoie la réponse une fois avec la liste de ces paragraphes. Ce qui n'est
  toujours pas étayé après cela est retiré, et une dernière ligne dit combien de
  paragraphes ont disparu. S'il ne reste rien d'étayé, vous obtenez la phrase
  fixe. Si le moteur ne peut pas être joint pour faire le contrôle, la réponse
  est retenue plutôt qu'affichée sans contrôle.

Ce que le mode vérifié ne peut pas faire, c'est prouver qu'un paragraphe cité
dit exactement ce que dit son passage. Dans nos mesures, un paragraphe qui
contredit son passage, ou qui ajoute quelque chose sur le même sujet, obtient
le même score qu'un paragraphe fidèle ; ce que le contrôle attrape, c'est un
paragraphe qui cite un passage portant sur autre chose, et un paragraphe sans
aucune source. Il n'est pas exact non plus, dans un sens comme dans l'autre :
dans nos tests, il a retiré environ 6 paragraphes fidèles sur 100 - surtout des
éléments de liste courts et des résumés d'une ligne, qui lui donnent peu à
comparer - et a laissé passer moins de 1 citation sur 100 vers un passage
portant sur un autre sujet. Un exemple de code est jugé avec la phrase qui
l'introduit. Relisez le passage cité quand l'exactitude compte. Les phrases
fixes sont écrites dans la langue choisie sous **Réglages → Agents → Langue
dans laquelle les agents répondent**, et en anglais si aucune ne l'est.
Les citations ne sont résolues qu'à partir des identifiants de sources récupérés.

Valeurs par défaut par agent : 128 Mio par fichier, 2 048 Mio de documents
originaux, 200 000 fragments, 8 résultats et jusqu'à 16 000 caractères de texte
récupéré par exécution. Un budget d'octets prudent limite aussi ce qui tient à
côté du prompt et de l'historique.
La **Similarité minimale** commence à la valeur mesurée pour le modèle de
vectorisation utilisé - 0,20 pour EmbeddingGemma, 0,35 pour Qwen3-Embedding -
et la ligne sous le champ indique laquelle. C'est un score de recherche, pas une
probabilité, et chaque modèle a sa propre échelle. Augmentez-la si les
résultats sémantiques sont trop larges. Les correspondances littérales
participent aussi.
L'API expose en plus les quotas de fragments et la taille des fragments en
jetons.

Les réglages globaux contrôlent les threads de vectorisation, les indexations
simultanées et les langues d'OCR par défaut. **Indexations simultanées** est le
nombre de bibliothèques d'agents indexées en même temps (une tâche par agent,
ses documents l'un après l'autre) ; chaque tâche peut utiliser jusqu'à 4 Go de
RAM, ce que le libellé vous rappelle. Cela n'accélère pas la bibliothèque d'un
seul agent : le moteur de vectorisation répond à une requête à la fois. Pour
vectoriser plus vite, augmentez plutôt **Threads CPU de vectorisation**. Le
modèle est partagé ; les bibliothèques et les permissions sont propres à chaque
agent.
Le traitement reprend après un redémarrage, en conservant les documents
terminés et les fragments réutilisables des tâches interrompues. Une
réindexation qui échoue conserve la dernière version publiée. Seule
l'installation du modèle demande un téléchargement ; la recherche normale peut
fonctionner sans Internet. Un moteur local indisponible est signalé, jamais
remplacé par un service de vectorisation externe.

`boa-embeddings` sert le modèle via un socket Unix ; `boa-rag` ordonnance la
file d'attente. Les deux ont des unités systemd et OpenRC et apparaissent dans
les réglages système. Les sauvegardes incluent les originaux des documents, les
métadonnées et des instantanés cohérents de SQLite et de l'index vectoriel. Les
réglages d'exécution sont inclus, et avec eux le modèle de vectorisation
choisi ; les binaires des modèles et les poids téléchargés ne le sont pas. Une
restauration télécharge le modèle choisi quand la machine ne l'a pas, et si ce
téléchargement échoue, elle le signale et continue : le modèle peut alors être
téléchargé, ou un autre choisi, dans **Réglages → RAG**. Les envois encore en
cours sont annulés dans une sauvegarde restaurée. Les bibliothèques indexées
survivent à une mise à jour normale.

### Choisir le modèle de vectorisation

Le modèle de vectorisation transforme chaque passage et chaque question en
nombres qui servent à chercher dans la bibliothèque.
**Réglages → RAG → Modèle de vectorisation** en propose deux, et le même sert
tous les agents :

| | EmbeddingGemma 300M (Q8) | Qwen3-Embedding 0.6B (Q8) |
|---|---|---|
| Téléchargement | 318 Mio | 610 Mio |
| Mémoire du moteur en fonctionnement | environ 600 Mo | environ 1,1 Go |
| Temps d'indexation, même processeur | 1× | environ 4× |
| Licence | Gemma Terms of Use | Apache 2.0 |

EmbeddingGemma est le choix par défaut et convient à n'importe quelle machine.
Qwen3-Embedding est destiné à une machine qui a du processeur et de la mémoire à
revendre : sur les livres de Python en espagnol de la bibliothèque de test, il
a tenu les questions sur les livres (0,51-0,79) plus éloignées des questions
sans rapport (0,21 au plus) qu'EmbeddingGemma (0,35-0,67 contre 0,17), et les
paragraphes qui reformulent un passage plus éloignés des paragraphes portant
sur autre chose. Sur la machine de test à deux processeurs, il a mis
2,2 secondes par fragment, contre 0,5.

Pour le changer :

1. Choisissez le modèle dans la liste. En dessous, vous voyez sa taille, sa
   mémoire, sa vitesse et sa licence, et s'il est téléchargé.
2. S'il ne l'est pas, cliquez sur **Télécharger le modèle** et attendez que la
   barre arrive au bout. Le téléchargement est vérifié avec son SHA-256 publié
   avant d'être utilisé.
3. Cliquez sur **Enregistrer** et confirmez. Le moteur redémarre avec le
   nouveau modèle ; la ligne du haut affiche « Le moteur charge ce modèle »
   pendant quelques secondes, puis **Prêt**.

Ce qu'un changement met en mouvement :

- Chaque document de chaque agent est réindexé, une bibliothèque par tâche
  d'indexation, comme le serait un nouvel envoi. Sur une grande bibliothèque,
  cela prend des heures.
- Tant que son tour n'est pas venu, un document reste dans la bibliothèque et
  il est trouvé par les mots d'une question, pas par le sens. Une recherche
  pendant ce temps indique à l'agent combien de documents attendent, pour
  qu'un passage manquant ne soit pas pris pour une question que la
  bibliothèque ne couvre pas.
- La **Similarité minimale** de chaque agent qui avait encore la valeur
  recommandée de l'ancien modèle passe à celle du nouveau. Un agent pour lequel
  vous avez défini une autre valeur la conserve.
- Le mode vérifié compare paragraphes et passages avec le modèle utilisé, par
  rapport à un seuil mesuré pour lui (0,36 pour EmbeddingGemma, 0,44 pour
  Qwen3-Embedding).

Les poids du modèle précédent restent sur le disque, donc revenir en arrière ne
demande aucun téléchargement - mais cela réindexe bien tous les documents qui
avaient été indexés avec l'autre.

## Choisir les outils

Sous **Outils**, cochez ce que cet agent a le droit d'utiliser. Un outil qui
n'est pas coché n'est pas montré au modèle et serait refusé par le serveur même
s'il était demandé : cette vérification se fait sur le serveur plutôt que dans
le prompt.

Voici les outils fournis avec l'application :

| Outil | Ce qu'un agent peut en faire |
|---|---|
| `bash.run` | Exécuter des commandes shell sous son propre utilisateur non privilégié |
| `kanban.add_card` | Mettre une tâche sur le tableau partagé |
| `kanban.assign_card` | Confier l'une de ses propres cartes à un autre agent |
| `kanban.move_card` | Déplacer l'une de ses propres cartes d'une colonne à l'autre |
| `kanban.delete_card` | Retirer l'une de ses propres cartes |
| `kanban.list_cards` | Lire le tableau : ses propres cartes, ou toutes les cartes pour **manager** |
| `channel.write` | Envoyer un message à un canal configuré |
| `web.fetch` | Lire une page web publique |
| `rss.fetch` | Lire un flux RSS ou Atom sous forme de liste d'entrées |
| `memory.append` | Noter quelque chose pour lui-même, pour plus tard |
| `memory.replace` | Faire le ménage dans ce dont il se souvient |
| `skill.read` | Lire une procédure qui lui a été donnée |
| `script.write` | Écrire un script dans son propre répertoire `scripts/` |
| `script.list` | Lister les scripts qu'il a écrits |
| `script.delete` | Retirer l'un de ses scripts, avec les lignes cron qui le lançaient |
| `cron.add` | Lancer l'un de ses scripts selon une planification, dans son propre crontab |
| `cron.list` | Lire son propre crontab |
| `cron.remove` | Arrêter de lancer l'un de ses scripts |
| `mail.read` | Lire les messages de la boîte aux lettres configurée |
| `mail.move` | Classer un message dans un autre dossier du même compte |
| `mail.delete` | Envoyer un message à la corbeille du compte |
| `mail.forward` | Transférer un message à une adresse que vous avez autorisée |
| `rag.search` | Chercher dans sa propre bibliothèque documentaire |
| `rag.read` | Lire un fragment renvoyé par une recherche |
| `rag.list` | Lister les documents de sa bibliothèque |
| `browser.open` | Ouvrir une page dans son propre navigateur, en gardant les cookies |
| `browser.read` | Lire la page ouverte, ou ses liens |
| `browser.click` | Y cliquer sur un lien ou un bouton |
| `browser.type` | Remplir un champ, en le soumettant si besoin |
| `browser.screenshot` | En enregistrer une image pour vous |
| `image.send` | Joindre un PNG à la conversation web et à la réponse Telegram quand la conversation a commencé là-bas. Les images remplissent la zone de texte du message web |

Chaque famille a sa propre case, avec le nombre d'outils de cette famille dont
dispose cet agent : « cet agent peut-il lire la boîte aux lettres ? » est une
seule décision, et elle est dessinée comme une seule case. L'interrupteur qui
active le tableau kanban pour un agent se trouve au pied de la case **Kanban**,
sous les outils qu'il gouverne.

- **`bash.run`** — des commandes shell sous l'utilisateur de cet agent. Il n'a
  pas root et ne peut pas l'obtenir. Donnez-le quand l'agent a un vrai travail
  à faire sur la machine.
- **`kanban.*`** — le tableau partagé. Donnez au moins `list_cards` et
  `add_card` à tout agent dont le travail doit être visible.
- **`channel.write`** — des messages pour vous. Cochez aussi les canaux dans l'onglet **Canaux**.
- **`web.fetch`** — des pages publiques seulement. Les adresses privées et de
  bouclage sont refusées.
- **`rss.fetch`** — un flux RSS ou Atom, sous forme de liste d'entrées plutôt
  que de document XML. Bien moins cher que de récupérer le même flux avec
  `web.fetch`, et cela épargne l'analyse à l'agent. Les deux se trouvent sous
  **Internet**.
- **`script.*` et `cron.*`** — sous **Automatisation**. L'agent écrit un script
  dans son propre répertoire `scripts/` et le planifie dans son propre crontab,
  pour un travail récurrent qui n'a pas besoin qu'il réfléchisse : le script
  tourne tout seul, ne coûte aucun jeton, et l'agent lit les résultats à sa
  prochaine exécution. Il ne peut planifier que ses propres scripts, jamais plus
  souvent que toutes les 5 minutes, et il ne peut jamais toucher la ligne qui
  le réveille.

Un agent peut faire beaucoup de choses dans son propre répertoire personnel, et
rien du tout en dehors. Il ne peut pas voir qu'un autre agent existe, et encore
moins lire son prompt : le répertoire des agents est traversable mais pas
listable, et chaque répertoire personnel est privé pour son propre utilisateur
Linux, c'est donc le noyau qui refuse, et non une vérification en Python.

Il ne peut pas non plus réécrire **ce qu'il est**. Ses outils accordés, ses
plafonds de dépense, son prompt système et son jeton d'API vivent dans un
tiroir à l'intérieur de son répertoire personnel qui appartient à root :
l'agent les lit et ne peut pas les changer. Vous les changez ; lui, non. La
seule chose le concernant qu'il peut modifier, c'est sa mémoire.
- **`mail.*`** — la boîte aux lettres configurée sous **Réglages → E-mail**. Voir ci-dessous.
- **`skill.read`** — les procédures écrites cochées dans le panneau
  **Compétences**. Il faut les deux : l'outil ici et au moins une compétence
  là-bas.

### Les outils de messagerie

Il y en a quatre, et ils ont besoin d'une boîte aux lettres IMAP configurée sous
**Réglages → E-mail**. L'agent ne voit jamais ce mot de passe : il dit ce qu'il
veut faire, et l'API des agents, qui détient les identifiants, le fait.

| Outil | Ce qu'il fait |
|---|---|
| `mail.read` | Lit les messages. **Ne marque rien comme lu**, donc votre propre compteur de non-lus garde le sens qu'il avait. |
| `mail.move` | Classe un message dans un autre dossier du même compte. Le dossier doit exister. |
| `mail.delete` | Envoie un message à la corbeille du compte, s'il y en a une. |
| `mail.forward` | Transfère un message, **uniquement aux adresses que vous avez listées**. |

C'est ce dernier qui compte. Une boîte de réception est la seule entrée d'un
agent sur laquelle n'importe qui au monde peut écrire, donc `mail.forward` est
vérifié par le serveur par rapport à votre liste à chaque transfert, sans
exception - pas par l'agent, et pas par quelque chose d'écrit dans son prompt.
Avec la liste vide, le transfert est refusé d'emblée.

Donnez `mail.read` seul à un agent qui n'a qu'à surveiller. Ajoutez
`mail.move` pour le classement, et réfléchissez à deux fois avant
`mail.delete` et `mail.forward`.

La case **kanban** en bas désactive complètement le tableau pour cet agent.
Décochée, il ne reçoit aucun outil kanban et cesse d'ajouter des cartes : c'est
l'interrupteur à utiliser pour un agent dont le travail n'a pas sa place sur le
tableau.

## Donner une compétence à un agent

Une compétence est une procédure écrite : comment un travail se fait ici,
étape par étape. Aucune n'est fournie avec l'application : une compétence porte
sur CETTE machine - ces hôtes, cette sauvegarde, ce certificat - donc une
compétence générique serait une procédure que personne ne suit. Vous écrivez
les vôtres sur le serveur, en tant que root :

```bash
mkdir -p /opt/boa/skills/BackupVerification
nano /opt/boa/skills/BackupVerification/SKILL.md
chown -R root:root /opt/boa/skills
chmod 00755 /opt/boa/skills/BackupVerification
chmod 0644 /opt/boa/skills/BackupVerification/SKILL.md
```

Le fichier commence par un nom et une description d'une ligne entre deux lignes
`---`, et le reste est la procédure :

```markdown
---
name: BackupVerification
description: Comment vérifier que les sauvegardes de la nuit dernière ont vraiment tourné.
---

1. Lire /var/log/backup.log ...
```

Chaque répertoire sous `/opt/boa/skills/` apparaît alors comme une case dans le
panneau **Compétences** de l'agent. Cochez-en une, donnez à l'agent l'outil
`skill.read` sous **Outils**, et appuyez sur **Enregistrer**. Dès sa prochaine exécution, l'agent sait que cette procédure existe et peut la lire
quand le travail se présente.

### Pourquoi s'en donner la peine, alors qu'il y a déjà le prompt système

Trois raisons, et la troisième est celle qui compte :

- **Le prompt, c'est ce à quoi sert un agent ; une compétence, c'est comment
  un travail se fait.** Six agents peuvent partager une procédure sans que six
  copies se périment chacune de son côté.
- **Une compétence peut être aussi longue qu'il le faut.** Un prompt système se
  paie à chaque appel de chaque exécution, il doit donc rester court. Une
  compétence se paie une fois, par l'exécution qui la lit.
- **Ce qu'un agent apprend tout seul meurt avec lui.** Sa mémoire vit dans un
  répertoire personnel qu'aucun autre agent ne peut ouvrir. Une compétence est
  l'endroit où mettre ce que vous voulez que l'agent suivant sache aussi.

### En écrire une

Il n'y a pas d'éditeur pour cela dans l'interface, et c'est voulu : ce que dit
une compétence entre directement dans le raisonnement d'un agent qui s'exécute
à quatre heures du matin sans personne pour le surveiller, elle appartient donc
à root, comme les outils. Vous les écrivez sur le serveur :

```bash
mkdir -p /opt/boa/skills/DatabaseBackup
nano /opt/boa/skills/DatabaseBackup/SKILL.md
```

Le fichier commence par un en-tête de deux lignes, puis dit tout ce qu'il a à
dire :

```markdown
---
name: DatabaseBackup
description: Comment le dump nocturne est réalisé et où il va.
---

# Sauvegarde de la base de données

1. Faire le dump avec `mysqldump --single-transaction`, jamais avec le verrouillage des tables.
2. L'écrire dans /srv/backups/, jamais dans /tmp.
...
```

La `description` est la ligne qui compte le plus. C'est la seule partie que
paie chaque exécution, et c'est sur elle que l'agent se décide quand il choisit
de lire ou non le reste. « Comment le dump nocturne est réalisé et où il va »
lui dit quand cela s'applique ; « Trucs de base de données » non.

Rechargez la page de l'agent et la compétence est dans la liste.

Une mise à jour ne touche jamais `/opt/boa/skills/` : ce que vous y écrivez
reste à vous. L'interface web décide quel agent reçoit quelle compétence ; elle
ne les modifie pas.

### Une compétence peut apporter ses propres fichiers

Tout le reste du répertoire voyage avec elle :

```
/opt/boa/skills/DatabaseBackup/
  SKILL.md
  dump.sh
  exclude-tables.txt
```

Les agents peuvent les lire et les exécuter, donc la procédure peut dire
« lancez `dump.sh` dans ce répertoire » au lieu de détailler quarante lignes de
shell. `skill.read` indique à l'agent quels fichiers sont là et où.

### Ce que cela coûte

Seuls le nom et la description de chaque compétence vont dans le prompt -
environ deux lignes chacune. Le corps est récupéré avec `skill.read`, une fois,
par un agent qui a décidé qu'il en a besoin, et seulement à ce moment-là.
Donner cinq compétences à un agent lui coûte quelques centaines de jetons par
exécution, pas dix mille, et c'est pourquoi vous pouvez lui en donner cinq sans
penser à la facture.

### Si vous supprimez une compétence que des agents utilisent

Rien ne casse, et aucun agent ne se retrouve à promettre quelque chose qu'il ne
peut pas tenir :

- Elle **disparaît du prompt** de chaque agent qui l'avait, à sa prochaine
  exécution. On ne parle jamais à un agent d'une procédure qu'il ne peut pas
  lire.
- Elle **disparaît du panneau Compétences**, donc personne ne peut la cocher de
  nouveau.
- Le nom **reste dans le `info.json` de l'agent** jusqu'à ce que quelque chose
  le réécrive, donc remettre le répertoire en place restaure la compétence sans
  rien d'autre à faire.
- Si l'agent la demande quand même - il peut se souvenir du nom d'une
  exécution précédente - on lui répond que la compétence est sur sa liste mais
  n'est plus installée, et on lui dit de ne pas deviner ce qu'elle disait.

Une chose à savoir : **appuyer sur Enregistrer pour cet agent pendant que la
compétence manque la retire de la liste pour de bon.** L'interface n'enregistre
que les compétences qui existent, et c'est ce qui empêche une compétence
supprimée de traîner éternellement. Remettez le répertoire en place avant
d'enregistrer l'agent, ou recochez la compétence ensuite.

## Donner un navigateur à un agent

`web.fetch` lit une page publique et rien d'autre : pas de connexion, pas de
formulaire, pas de bouton. Si un agent a besoin d'*utiliser* un site plutôt que
de le lire, il lui faut un navigateur.

Il est installé d'office : l'installateur pose la question une fois, et oui est
la réponse par défaut. Il s'agit d'environ 600 Mo de Chromium, donc une machine
à court de disque peut refuser, et changer d'avis plus tard dans un sens comme
dans l'autre :

```bash
./install-update-reinstall-debian.sh --update --browser no    # le laisser de côté
./install-update-reinstall-debian.sh --update --browser yes   # le remettre
```

La réponse est mémorisée, comme pour les ports. Cochez ensuite les outils de
navigateur dans le panneau **Outils** de l'agent :

Rien de tout cela ne s'applique sous Alpine : il n'y a pas de navigateur du
tout, parce que Playwright ne publie aucune version pour musl. Les outils
restent dans la liste et le signalent quand un agent en appelle un.

| Outil | Ce que l'agent peut faire |
|---|---|
| `browser.open` | Aller sur une page. Les cookies sont conservés |
| `browser.read` | Relire la page ouverte, une partie de celle-ci, ou ses liens |
| `browser.click` | Cliquer sur un lien ou un bouton, par son texte visible ou par un sélecteur |
| `browser.type` | Remplir un champ, en appuyant éventuellement sur Entrée |
| `browser.screenshot` | Enregistrer un PNG dans son propre répertoire de téléchargements |
| `image.send` | Joindre un PNG à la réponse dans la conversation web et sur Telegram |


`browser.screenshot` enregistre un PNG sur le serveur. Pour l'afficher dans la
conversation, l'agent appelle ensuite `image.send` avec ce chemin. Accordez
**image.send** sous **Réglages de l'agent → Outils → Images**, puis
enregistrez. Les nouveaux agents créés à partir de **web-navigator** l'incluent
déjà ; les agents existants gardent leurs autorisations actuelles.

L'image remplit la zone de texte du message dans la conversation web, en
conservant ses proportions et toute sa hauteur. Elle peut aussi être ouverte à
sa taille d'origine. Quand la conversation a commencé sur Telegram, elle y est
aussi envoyée. Les captures hautes ou volumineuses sont livrées sous forme de
documents PNG. Un envoi qui échoue réessaie la partie manquante sans répéter le
texte ni les images déjà arrivés.

Seuls les fichiers PNG situés dans le répertoire personnel de cet agent sont
acceptés, jusqu'à 50 Mio chacun et 16 par réponse. Les pièces jointes restent
privées et ne peuvent être vues qu'avec une session ouverte. Une capture
existante peut être envoyée en demandant à l'agent d'utiliser `image.send` avec
son chemin enregistré.

### Les sessions de chaque agent lui appartiennent

Le navigateur lui-même est une seule copie, dans `/opt/boa/playwright/`, qui
appartient à root et est en lecture seule pour tous les autres. Ce qui n'est
**pas** partagé, c'est le profil :

```
/opt/boa/agents/001/browser/profile/     agent-001, 0700
/opt/boa/agents/002/browser/profile/     agent-002, 0700
```

Un agent qui se connecte à un site reste connecté **à sa prochaine
exécution**, parce que les cookies sont sur son propre disque. Et aucun autre
agent n'est connecté, parce que ce répertoire est en 0700 et appartient à son
utilisateur Linux - c'est le noyau qui refuse, il n'y a pas de vérification en
Python qui pourrait se tromper. Cette séparation est ce qu'un produit hébergé
ne peut pas offrir quand tous ses agents partagent une même machine.

Les cookies de session prennent quand même fin à la fermeture du navigateur,
ici comme dans n'importe quel navigateur. Ce qu'un site marque comme persistant
persiste.

### Ce qu'il ne fera pas

- **Pas d'adresses privées.** `browser.open` refuse `192.168.*`, `127.*` et les
  autres, exactement comme `web.fetch`. Un agent qui vient de lire une page
  hostile ne doit pas pouvoir être convaincu d'ouvrir votre routeur, et un
  navigateur avec une session serait un bien meilleur outil pour cela qu'une
  simple récupération de page.
- **Pas d'écran.** Il est headless. `browser.screenshot` est le moyen de voir
  ce qu'il a vu ; l'agent lui-même ne peut pas regarder l'image.
- **Rien sans les outils.** Comme pour tout le reste, un outil que l'agent n'a
  pas reçu est un outil qu'il ne peut pas appeler, et cette vérification se
  fait sur le serveur.

Si le navigateur n'a jamais été installé, les outils apparaissent quand même
dans la liste et répondent avec la commande à exécuter. Ils ne disparaissent
pas, et ils n'échouent pas en silence.

## Plafonds de dépense

Quatre plafonds, par agent, et chaque exécution s'arrête au premier qu'elle
atteint :

| Plafond | Par défaut | Ce contre quoi il protège |
|---|---|---|
| Jetons par exécution | 16384 | Une seule conversation coûteuse |
| Étapes par exécution | 25 | Une boucle qui appelle des outils sans fin |
| Secondes par exécution | 300 | Une exécution qui se bloque |
| Exécutions par jour | 48 | Une ligne cron trop zélée |

Ce n'est pas de la paranoïa. Un agent qui se réveille toutes les heures sur une
API payante, sans plafond et sans personne pour le surveiller, est une facture
qui grossit pendant que vous dormez.

Relevez-les une fois que vous avez vu ce que l'agent consomme réellement, dans
son panneau **Historique**.

### Le modèle de secours

Sous **LLM**, il y a un second fournisseur et un second modèle, sous le
premier. Ils ne servent que quand le principal **échoue** - pas de clé, pas de
réponse, un modèle qui n'existe pas - et l'exécution continue avec eux à partir
de la même étape, en rejouant ce qui s'est passé jusque-là, pour que le travail
déjà fait ne soit pas jeté.

On l'essaie **une fois par exécution**. Si le secours échoue aussi,
l'exécution échoue : essayer chacun à tour de rôle indéfiniment brûlerait les
plafonds pendant une panne, sans rien avoir à montrer au bout. Le basculement
est écrit dans l'historique de l'agent, parce qu'une exécution qui répond
discrètement avec un autre modèle, et facture un autre compte, doit le dire.

Laisser le fournisseur de secours sur **aucun** est le réglage par défaut, et
signifie qu'un échec met fin à l'exécution.

Choisissez le **même fournisseur** pour le secours et la case du modèle se
remplit avec un modèle *différent* du catalogue de ce fournisseur, pas le même
à nouveau. Le même fournisseur avec le même modèle ne peut rien répondre que le
principal n'aurait pu répondre : il échouerait exactement pour la même raison,
à chaque fois. Si vous retapez quand même la paire à l'identique, une ligne
sous le champ le signale - c'est votre agent, donc c'est un avertissement et
non un refus.


Quand une exécution s'arrête à son plafond de jetons ou d'étapes, on demande
une dernière fois à l'agent - sans outils, avec un petit budget à part - la
réponse qu'il s'apprêtait à donner, pour qu'une exécution qui a dépensé tout
son budget à rassembler des faits ne se termine pas sur « Je vais vérifier le
système ». La conversation le signale sous la réponse, parce que cette réponse
peut être tronquée. Le plafond de temps n'a pas droit à cet appel : l'exécution
est déjà en retard.

Cet appel de clôture renvoie toute la conversation, donc sur une longue
exécution riche en outils il n'est pas bon marché : une exécution arrêtée à un
plafond de 12 000 jetons a été mesurée finissant à 24 901. Le plafond de jetons
est donc un budget pour le travail, pas un maximum strict pour l'exécution.
Rien n'est dépensé de cette façon à moins qu'un plafond ait été atteint.

### Ce que le noyau impose en plus

Les quatre plafonds sont appliqués par l'exécution elle-même. Deux autres sont
appliqués par le noyau, et tiennent donc quand c'est l'exécution elle-même qui
a déraillé : aucun agent ne peut avoir plus de 1 024 processus et threads à la
fois, donc une commande qui se duplique sans fin s'arrête là et non en
saturant la machine ; et sous Debian, chaque exécution vit dans son propre
scope systemd avec 2 Gio de mémoire, ce qui met aussi fin, quand elle se
termine, à ce que l'exécution a laissé tourner en arrière-plan. Une exécution
tuée par la limite de mémoire est signalée comme échouée dans son Historique et
comme une erreur dans sa conversation, comme n'importe quelle autre. Un
navigateur, c'est déjà quelques centaines de threads, et c'est pourquoi le
nombre n'est pas plus petit.

## Planifier un agent

Sous **Cron**, écrivez le crontab de l'agent. C'est le crontab propre de
l'agent, possédé et exécuté par son propre utilisateur Linux, exactement comme
si vous aviez lancé `crontab -e` sous cet utilisateur.

Toutes les heures :

```
0 * * * * /opt/boa/venv/bin/python3 /opt/boa/webapp/backend/core/runner.py --agent-id 001
```

Du lundi au vendredi à 8 h 00 :

```
0 8 * * 1-5 /opt/boa/venv/bin/python3 /opt/boa/webapp/backend/core/runner.py --agent-id 001
```

L'interface affiche la ligne exacte pour l'agent que vous modifiez, vous pouvez
donc la copier et ne changer que l'horaire.

Laissez-le vide pour supprimer la planification. Décochez **Allumé** pour
garder la planification tout en faisant en sorte que l'agent l'ignore.

Si vous utilisez un fournisseur payant dont les tarifs varient selon l'heure —
DeepSeek facture plusieurs fois plus cher aux heures de pointe — c'est ici que
ce choix se fait.

## Le tableau kanban

La page a deux onglets : **Tableau**, qui contient les trois colonnes, et
**Créer une carte**, qui est le formulaire. L'onglet ouvert figure dans l'URL,
donc un rechargement et le bouton Précédent le conservent. Enregistrer une
carte vous ramène au tableau.

Trois colonnes : **à faire**, **en cours**, **terminé**.

Le tableau est ce que les agents utilisent pour se laisser du travail les uns
aux autres, et ce que vous utilisez pour voir ce qui s'est réellement passé.
Chaque carte porte son historique : qui l'a créée, qui l'a déplacée, quand et
pourquoi.

Une carte a un titre et une case **Ce qu'il faut faire**. Le titre la nomme ;
la case est l'endroit où vont les instructions, et un agent lit les deux. Une
carte attribuée à un agent sans rien dans la case le laisse deviner, et c'est
la raison habituelle pour laquelle un agent ne fait rien d'une carte qu'on lui
a confiée.

L'autre raison est que l'agent ne peut pas voir le tableau du tout. Un agent le
lit en appelant `kanban.list_cards` ou pas du tout - le tableau n'est jamais
mis dans son prompt - donc un agent sans cet outil n'apprend jamais que la
carte existe. **Attribuer à** le signale quand vous choisissez un tel agent.
C'est un avertissement, pas un blocage : la carte est quand même créée, et
cocher l'outil dans l'onglet **Outils** de l'agent suffit.

Une carte sur le tableau montre qui l'a faite, qui l'a en charge, quand elle a
été faite, les deux premières lignes de son titre, les trois premières de ce
qu'il y a à faire, et **quand elle s'exécute**. L'intégralité d'un titre ou
d'un corps tronqué se trouve dans son infobulle.

Cette dernière ligne est celle qui vaut la peine d'être lue. Une carte sans
heure n'est pas en retard : personne n'est réveillé pour elle, et son agent la
trouvera à sa prochaine exécution planifiée. **Déplacer vers** est la façon de
déplacer une carte à la main - ce tableau n'a pas de glisser-déposer.

Vous pouvez ajouter, déplacer et supprimer n'importe quelle carte. **Un agent ne
voit et ne modifie que les siennes** : une carte appartient à un agent s'il l'a
créée ou si elle lui est attribuée.

C'est un mur, pas une préférence. Un agent ne peut absolument pas apprendre que
le travail d'un autre agent existe - ni les titres, ni leur nombre, ni même
qu'il y a quelque chose. Demandez à un agent de déplacer une carte qui n'est
pas la sienne et on lui répond qu'il n'a aucune carte de ce genre ; une carte
qui n'existe pas reçoit la même phrase, parce qu'un refus qui distinguerait les
deux cas serait une façon de demander au tableau ce qu'il contient, un
identifiant à la fois.

L'exception est **manager** (agent 000), l'orchestrateur : son travail est de
distribuer le travail et d'en assurer le suivi, il lit donc tout le tableau.
C'est pourquoi la coordination est son travail et celui de personne d'autre.

Une confirmation destructrice n'a **aucun bouton par défaut** : elle s'ouvre
avec le focus sur la boîte de dialogue elle-même, donc Entrée ne fait ni l'un
ni l'autre et vous devez dire ce que vous voulez. Échap annule. Cliquez sur le
bouton rouge pour continuer.

Une confirmation ordinaire, qui ne détruit rien, s'ouvre bien avec le focus sur
son bouton de confirmation, entouré d'un anneau, où Entrée veut dire oui.

Supprimer une carte laisse une ligne qui enregistre qu'elle a existé et qui l'a
supprimée, pour qu'un agent ne puisse pas effacer les traces de ce qu'il
faisait.

## Réglages

Les réglages sont regroupés en onglets, et l'onglet figure dans l'URL, donc un
rechargement ou un favori vous ramène là où vous étiez :

| Onglet | Ce qu'il contient |
|---|---|
| **Système d'exploitation** | Ce qu'est cette machine, combien de mémoire et de disque il reste, et si les quatre services tournent - chacun en vert quand il est actif et en rouge quand il ne l'est pas. Lu sans aucun privilège, exactement comme le lit `os-watcher` |
| **Compte** | L'unique adresse e-mail et le mot de passe. Changer le mot de passe demande l'actuel |
| **E-mail** | SMTP, pour quand quelque chose doit vous parvenir par courrier |
| **Canaux** | Discord, Mattermost, Telegram, X, par ordre alphabétique - une case chacun, avec son propre bouton Enregistrer |
| **Audio** | Moteur de transcription, fournisseur, téléchargement des modèles, langue et conservation de l'audio Telegram |
| **Outils** | Les outils installés, regroupés en sous-onglets comme Automatisation et Navigateur |
| **Agents** | Les réglages de tous les agents à la fois, et le dépôt et la branche d'où viennent les modèles. Gardés sur le serveur : une exécution lancée par cron n'a pas de navigateur où lire une préférence |
| **Conversation** | Comment se comporte la zone de message : si Entrée envoie, si chaque réponse affiche ce qu'elle a coûté |
| **Kanban** | Combien de cartes chaque colonne affiche, et s'il faut lister celles qui ont été supprimées récemment |
| **Interface** | Thème, langue, combien de temps reste affiché un message contextuel, et si **+** demande d'où part un nouvel agent |

Sous **Système d'exploitation**, l'état des services s'aligne sur la deuxième
colonne de **Cette machine**.

Les préférences Conversation, Kanban et Interface sont gardées dans votre
navigateur plutôt que sur le serveur : elles décrivent votre façon de
travailler sur cette machine, et un téléphone et un ordinateur de bureau
peuvent raisonnablement ne pas être d'accord.

### Transcription audio

Sous Alpine, l'installation et les mises à jour rendent la main à la session SSH une fois terminées ; OpenRC maintient les services en marche.

Ouvrez **Réglages → Audio**. Ces réglages sont stockés sur le serveur et s'appliquent aux messages vocaux et aux fichiers audio reçus par Telegram.

1. Choisissez **Local · whisper.cpp** ou **API d’un fournisseur**. La transcription démarre désactivée.
2. Pour la reconnaissance locale, choisissez un modèle et cliquez sur **Télécharger le modèle** si nécessaire. L'installateur prépare `base` ; le sélecteur propose les 30 modèles officiels, y compris les variantes anglaises `.en` et les variantes quantifiées, plus les modèles `ggml-*.bin` installés à la main dans `/opt/boa/whisper/models/`. La taille et l'état d'installation sont affichés. Les modèles plus grands demandent plus de mémoire et de temps CPU.
3. Pour une API, enregistrez d'abord sa clé sous **Clés d'API**. OpenAI, Groq, Mistral, Together AI, Hugging Face et Cloudflare apparaissent quand une clé est enregistrée. Choisissez une suggestion ou saisissez un autre identifiant de modèle de transcription de ce fournisseur. Cloudflare propose ses deux variantes de Whisper prises en charge et utilise un identifiant de la forme `account-id:api-token`.
4. Choisissez la langue (`auto` ou un code comme `en`), la durée maximale et s'il faut conserver l'audio pour l'écouter ; cliquez sur **Enregistrer**. Répondez au message Telegram d'un agent par un message vocal pour l'essayer. Vous pouvez aussi sélectionner l'agent d'abord avec `/agents`.

La limite initiale est de 600 secondes, configurable de 30 à 3 600 ; le fichier reçu ne peut pas dépasser 20 Mio. Le traitement se fait en arrière-plan et sa file d'attente survit à une mise à jour. Un agent occupé reçoit le texte enregistré quand il est disponible. Un nom d'agent prononcé dans l'enregistrement ne change pas sa destination.

La conversation web affiche la transcription et, quand la conservation est activée, un lecteur. Une copie Ogg pour la lecture est gardée derrière la connexion. Désactiver la conservation ne garde que le texte pour les nouveaux messages. Vider une conversation supprime l'audio enregistré des tâches terminées. Les sauvegardes incluent cet audio ; les modèles téléchargés survivent aux mises à jour mais ne sont pas sauvegardés. Après une restauration sur une autre machine, téléchargez depuis Audio tout modèle supplémentaire manquant.

La reconnaissance locale traite l'audio sur votre serveur. La reconnaissance par API l'envoie au fournisseur choisi et peut entraîner des frais distincts de l'utilisation du modèle de l'agent. Un échec local ne bascule jamais automatiquement vers un fournisseur cloud. Whisper transcrit, il ne traduit pas ; les modèles `.en` ne comprennent que l'anglais. L'audio entre par Telegram ; la conversation web affiche le résultat sans ajouter de bouton d'enregistrement.

Pour une installation existante, exécutez l'installateur de votre distribution en tant que root avec `--update`. Il installe FFmpeg, whisper.cpp et le modèle base sous `/opt/boa/whisper/` ; la transcription reste désactivée jusqu'à ce qu'elle soit configurée.

### Langues

L'interface est fournie en quinze langues :

| | | |
|---|---|---|
| Deutsch (Deutschland) | English (United Kingdom) | English (United States) |
| Español (Argentina) | Español (España) | Français (France) |
| עברית (ישראל) | हिन्दी (भारत) | Italiano (Italia) |
| 日本語 (日本) | 한국어 (대한민국) | Português (Brasil) |
| Português (Portugal) | Русский (Россия) | 简体中文 (中国) |

L'hébreu s'écrit de droite à gauche, et le choisir retourne toute l'interface :
la barre latérale passe à droite et tout le reste suit. Le code, les chemins et
les commandes restent de gauche à droite, et chaque message du chat suit sa
propre langue, de sorte qu'une réponse en anglais se lit toujours de gauche à
droite sur une page en hébreu.

**Réglages → Interface → Langue** en choisit une, et elle est gardée dans votre
navigateur, comme le thème. Un navigateur qui n'a jamais choisi reçoit la
correspondance la plus proche de ce qu'il demande, et l'anglais quand il n'y en
a aucune.

Deux autres choses suivent la langue et ne sont **pas** une préférence du
navigateur, parce qu'une exécution lancée par cron n'a pas de navigateur :

- **Réglages → Agents → Langue dans laquelle les agents répondent** ajoute une
  ligne au prompt système de chaque agent, écrite dans cette langue.
- Les **bots Telegram et Discord** la parlent aussi : leurs propres phrases, le
  rapport `/status`
  et le texte d'aide.

## Messages contextuels

Quand quelque chose est enregistré, la confirmation apparaît au milieu du
panneau que vous regardez, puis s'en va d'elle-même. Elle est délibérément sur
votre chemin : le bouton Enregistrer en bas d'un long onglet produisait
autrefois une ligne tout en haut de la page, plusieurs écrans au-dessus de
l'endroit où vous regardiez, si bien qu'enregistrer semblait n'avoir rien fait
du tout.

**Réglages → Interface → Secondes d'affichage d'un message contextuel** règle
la durée, entre 1 et 30 secondes. Trois est la valeur par défaut : assez long
pour lire « Réglages enregistrés », assez court pour ne pas rester par-dessus la
case où vous alliez taper.

Les messages d'erreur ignorent ce nombre. Ils restent jusqu'à ce que vous les
fermiez, avec le `×` ou avec Échap, parce qu'une erreur est le seul message qui
doit encore être là quand vous reportez les yeux sur l'écran.

La couleur dit laquelle de trois choses s'est produite :

| Couleur | Ce qu'elle signifie |
|---|---|
| Vert | C'est enregistré |
| Ambre | **Aucune modification à enregistrer** - vous avez appuyé sur Enregistrer et rien n'avait changé dans le formulaire |
| Rouge | Ça a échoué. Dit ce qui n'a pas marché, et attend d'être fermé |

L'ambre s'applique partout où vous pouvez appuyer sur Enregistrer :
**Réglages** - le compte, le serveur de messagerie, les clés d'API, les canaux
et les préférences du navigateur - et les réglages propres d'un agent. Appuyer
deux fois sur Enregistrer vous le dit la seconde fois, au lieu d'annoncer un
enregistrement qui n'a pas eu lieu. Un agent tout neuf est l'exception : son
formulaire contient les valeurs du modèle et n'a jamais été enregistré, donc
Enregistrer les écrit et vous emmène à sa conversation.

## Thèmes

**Réglages → Interface** choisit la palette :

| Thème | Ce que c'est |
|---|---|
| **Day** | Gris doux avec des cartes plus claires, pour une pièce éclairée |
| **Night** | La palette sombre, pour une pièce sombre |
| **Day High Contrast** | Fond blanc, texte presque noir, bordures nettes. Ici, rien n'est rempli avec la couleur d'accent : la case d'un agent dans la barre latérale est un contour, et votre propre message est rempli d'une encre adoucie au lieu de bleu |
| **Night High Contrast** | Fond presque noir, texte clair et bordures nettes. L'agent sélectionné a un remplissage gris ; les onglets sélectionnés ont un contour fermé relié à la ligne du dessous. Vos propres messages utilisent un blanc atténué |

Un navigateur qui n'a jamais choisi commence sur celui des thèmes Day et Night
qui correspond au système d'exploitation, et le suit jusqu'à ce que quelqu'un
en choisisse un. Ensuite, le choix est stocké dans ce navigateur, comme la
langue, pour qu'un téléphone et un ordinateur de bureau n'aient pas à être
d'accord.

Un thème est un fichier CSS dans `frontend/themes/` sur le serveur, qui
redéfinit les variables `--colour-*`. Déposer un fichier là ajoute un thème -
il n'y a aucune liste à mettre à jour dans le code. Son nom et sa description
viennent du commentaire en haut du fichier :

```css
/*
name: Midnight
scheme: dark
description: À quoi il ressemble, en une ligne.
*/

:root {
  color-scheme: dark;
  --colour-page: #101014;
  /* ... chaque --colour-* que définit app.css ... */
}
```

Définissez-les toutes. Une variable qu'un thème omet garde la valeur
d'app.css - ce qui, sur un thème clair, veut dire une couleur de la palette
sombre laissée en plein milieu.

Chaque thème fourni ici dépasse un contraste de 4,5:1 pour chaque couleur dans
laquelle il peint du texte, et les deux thèmes à contraste élevé dépassent
7:1 - WCAG AAA. Un test échoue si l'un d'eux cesse de le faire, en le tenant au niveau que son nom revendique. Un thème ajouté
à la main n'y est pas tenu, mais la même question s'applique à lui : un service
marqué arrêté dans un rouge que personne ne peut lire est un service que
personne ne remarque.

## Quand une carte s'exécute

Attribuer une carte est la façon de donner du travail à un agent, et c'est un
service **buzzer** qui transforme cela en exécution :

    toutes les quelques secondes :
      cartes avec un propriétaire, une heure déjà passée et pas encore de buzz
        -> démarrer cet agent, sauf s'il tourne déjà
        -> enregistrer le buzz sur la carte

**Quand**, dans le formulaire d'ajout de carte, décide de l'heure :

| Choix | Ce qui se passe |
|---|---|
| **Immédiatement** | L'agent est réveillé dès que la carte est enregistrée. C'est le choix par défaut : attribuer une carte, c'est demander le travail |
| **Quand l'agent se réveille** | La carte attend sur le tableau. Personne n'est réveillé ; l'agent la trouve à sa prochaine exécution à lui |
| **Planifier à une heure donnée** | Une heure en UTC. L'agent est réveillé à ce moment-là |

Un agent qui travaille déjà n'est pas interrompu. La carte garde son tour et
est retentée au passage suivant, donc une exécution planifiée pour un agent
occupé démarre quelques secondes en retard plutôt que pas du tout, et un agent
n'a jamais deux exécutions à la fois. Une carte ne sonne qu'une fois : pour la
relancer, redéfinissez son heure.

### La carte apparaît dans la conversation de l'agent

Quand l'exécution démarre, la conversation de l'agent reçoit un message qui
nomme la carte :

    Une tâche vous a été attribuée sur une carte :

    Identifiant de la carte : 1284
    Titre : Renouveler les certificats
    En quoi consiste la tâche : « Lancer l'installateur avec --update et faire un rapport »
    À exécuter : Immédiatement

Si c'est un autre agent qui a confié la carte, la première ligne dit qui :
*manager vous a attribué une nouvelle carte*. Si la carte a été planifiée
plutôt que demandée tout de suite, la dernière ligne montre l'heure à la
place : `a2026m03d31@13:45`, en UTC, la même heure que celle que le tableau
affiche sur la carte.

Le message est écrit **quand l'exécution démarre**, jamais avant. Une carte que
vous planifiez pour ce soir et supprimez cet après-midi ne laisse rien dans la
conversation, parce que rien n'a jamais tourné.

L'agent répond en dessous comme à n'importe quel autre message, avec ce qu'a
coûté l'exécution. Trois choses peuvent mettre une ligne là sans que l'agent ait
rien fait, et chacune dit laquelle c'était : l'agent était éteint, il avait
déjà épuisé ses exécutions du jour, ou l'exécution n'a pas pu démarrer du tout.
Aucune n'est silencieuse, parce qu'une carte annoncée puis ignorée ressemble
exactement à un agent qui ne fonctionne pas.

Une chose que cette exécution ne fait pas, c'est lire la conversation. Ses
instructions, c'est la carte. Ce que vous avez dit plus tôt dans la
conversation n'est rejoué que quand vous envoyez vous-même un message - sinon
chaque exécution planifiée serait facturée pour une conversation que personne
n'est en train d'avoir.

Une carte confiée à **manager** est traitée différemment : on lui dit de
décider qui doit faire le travail et de transmettre la carte avec
`kanban.assign_card`. La carte garde son identifiant, ses instructions et son
historique et change de mains, et l'agent sur lequel elle atterrit est réveillé
pour elle. C'est de la délégation - pas une deuxième carte pour le même
travail.

## Canaux

Sous **Réglages → Canaux**, configurez où les agents peuvent écrire :

| Canal | Ce dont il a besoin |
|---|---|
| Discord | un `bot_token` et un `channel_id` pour communiquer dans les deux sens, ou une URL de webhook pour seulement envoyer |
| Mattermost | une URL de webhook entrant |
| Telegram | le `bot_token` donné par BotFather, et le `chat_id` |
| X | un `bearer_token` |

Chaque canal configuré affiche **Configuré** en vert, de la même couleur qu'une
clé d'API enregistrée. Les canaux sans configuration gardent leur état neutre.

Les identifiants sont stockés de façon qu'**aucun agent ne puisse les lire**. Un
agent demande au serveur d'envoyer ; le serveur lit le jeton et envoie. Le
message arrive préfixé du nom de l'agent, ajouté par le serveur, si bien
qu'aucun agent ne peut se faire passer pour un autre.

Ensuite, dans l'onglet **Canaux** de chaque agent, cochez les canaux qu'il a le droit d'utiliser. Il lui
faut à la fois `channel.write` et le canal lui-même.

### Répondre à un agent depuis Telegram

Telegram et Discord sont les deux canaux qui fonctionnent aussi dans l'autre sens. Cochez **Me laisser
répondre aux agents depuis Telegram** dans ses réglages, enregistrez, et vous pouvez répondre.

Le bot a trois outils dans son menu, et ce sont eux que propose le bouton `/` :

| Commande | Ce qu'elle fait |
|---|---|
| `/agents` | Liste vos agents sous forme de boutons. Touchez-en un pour commencer à lui parler |
| `/status` | Les services, le tableau et chaque agent avec son modèle, ses outils et ses compétences |
| `/help` | Ces trois commandes, et les deux autres façons de joindre un agent |

### Personne d'autre n'en voit rien

Le nom d'utilisateur du bot est public - quiconque le trouve peut l'ouvrir -
donc le menu est écrit **uniquement pour votre conversation**. Quelqu'un d'autre
qui ouvre le même bot voit une conversation vide : aucune commande sous `/`,
aucune description, rien à presser à part le bouton Démarrer, que Telegram
dessine dans chaque bot et qu'aucune API ne peut retirer.

Appuyer dessus ne fait rien. L'écouteur compare le `chat_id` de chaque message
avec celui de vos réglages et jette ce qui ne correspond pas, avant qu'aucune
commande ne s'exécute et avant qu'aucun agent ne soit choisi.

**Et rien n'est consigné.** Aucune réponse, aucune ligne dans le journal, aucune
trace que quelqu'un a écrit. L'identifiant d'une conversation qui n'est pas la
vôtre est une donnée qui appartient à quelqu'un d'autre, et la conserver
reviendrait à laisser votre installation dresser discrètement une liste de ceux
qui ont trouvé le bot.

Le prix à payer, c'est qu'un `chat_id` mal défini ressemble exactement à un
inconnu : vos propres messages sont jetés en silence. Celui qui est configuré
est écrit dans le journal à chaque démarrage, et c'est avec lui qu'il faut
comparer :

```bash
journalctl -u boa-channel-telegram.service | grep "Registered"
```

Sous Debian, les unités des canaux utilisent `boa-channel-<channel>.service`.
Lancez l'installateur avec `--update` pour migrer automatiquement les anciens
noms d'unités. Alpine garde ses noms OpenRC `boa-telegram` et `boa-discord`.

Le filtre s'applique par **conversation**, pas par personne. Si le `chat_id` que
vous avez configuré est un groupe, chaque membre de ce groupe peut parler à vos
agents.

### Choisir à qui vous parlez

Touchez `/agents`, touchez un agent, et il répond :

```
Agente os-watcher:

Envíame tus instrucciones...
```

À partir de là, **tout ce que vous écrivez va à cet agent** jusqu'à ce que vous
en choisissiez un autre. Vous pouvez poser quatre questions d'affilée sans
nommer personne, et c'est ce qui en fait une conversation plutôt qu'une ligne
de commande.

Trois façons de vous adresser à quelqu'un, dans cet ordre :

1. **Répondre à quelque chose qu'un agent a dit** va à cet agent, quel que soit
   celui qui est sélectionné. Répondez à son message (faites-le glisser, ou appuyez longuement dessus ou faites un clic droit et choisissez Répondre), écrivez, envoyez.
2. **En nommer un** - `@os-watcher check the disk` - va à lui *et* en fait
   l'agent sélectionné. `@001` fonctionne aussi, de même qu'un nom contenant un
   espace : `@News Miner what is new` est un seul agent, pas deux mots.
3. **Ni l'un ni l'autre** va à celui que vous avez choisi en dernier.

Rien d'autre ne change la sélection, si bien qu'un agent n'hérite jamais de
votre conversation simplement parce qu'il est celui qui a parlé en dernier. Un
agent que vous supprimez cesse d'être sélectionné au lieu de continuer à tout
recevoir.

Tant que vous n'avez choisi personne, un message qui ne nomme personne reçoit
en retour la liste des agents, si bien que rien ne disparaît jamais sans
explication.

### Ce qui revient

L'agent répond dans Telegram en réponse à ce que vous avez écrit, avec son nom
sur la première ligne :

```
os-watcher:
25G free of 28G on /, unchanged since yesterday.
```

**Et tout l'échange figure dans la conversation de cet agent dans l'interface
web**, votre question et sa réponse, avec `(via Telegram)` à côté de l'heure sur
ce que vous avez envoyé. Un seul écran montre toujours tout ce qu'on a demandé à
l'agent et tout ce qu'il a dit, quel que soit l'appareil sur lequel chaque
moitié a été tapée.

Deux choses à prévoir :

- **Un agent occupé le dit.** S'il est déjà en train de répondre à autre chose,
  on vous dit de réessayer dans un instant au lieu de vous mettre dans une file
  d'attente - une file d'attente cacherait qu'un agent prend du retard.
- **Seule votre conversation est écoutée.** Le nom d'utilisateur d'un bot est
  public et quiconque le trouve peut lui écrire. Les messages de toute autre
  conversation sont jetés sans réponse, donc c'est le `chat_id` que vous avez
  configuré qui décide qui peut parler à vos agents. Trompez-vous et il ne se
  passe rien du tout.

C'est du long polling, pas un webhook : le serveur se connecte vers Telegram,
donc rien n'a besoin d'être ouvert sur Internet pour que cela fonctionne.

Si Telegram refuse la réponse - vous avez bloqué le bot, l'identifiant de la
conversation a changé, le jeton n'est plus valide - elle est abandonnée pour
Telegram aussitôt, et si Telegram reste injoignable pendant une heure, elle est
abandonnée aussi. Elle n'est jamais perdue : toute la conversation, cette
réponse comprise, se trouve dans la conversation de l'agent dans l'interface
web.

### À quoi ressemble le message d'un agent

Les modèles écrivent en markdown, et Telegram affiche un petit sous-ensemble de
HTML, donc l'un est traduit en l'autre à la sortie. Ce qui arrive est mis en
forme, pas truffé d'astérisques :

| Ce que l'agent écrit | Ce que vous voyez sur votre téléphone |
|---|---|
| `**25G free**` | **25G free** |
| `` `df -h` `` | `df -h` en chasse fixe |
| `# Disk report` | une ligne en gras |
| `- item` | • item |
| un tableau | un bloc en chasse fixe, colonnes alignées |
| ```` ```bash ```` | un bloc de code |
| `[text](https://…)` | un lien |

Telegram n'a ni titres, ni listes, ni tableaux à lui, et c'est pourquoi ces
trois éléments deviennent la chose lisible la plus proche au lieu de
disparaître.

Si Telegram refuse un jour la mise en forme, **le message est renvoyé en texte
brut plutôt que d'être perdu**. Vous recevez les mots dans tous les cas ; le
journal du serveur dit ce qui s'est passé, si bien qu'un bogue de mise en forme
se voit au lieu de se dégrader en silence pour toujours.

Tout ce que le bot dit lui-même - la liste des agents, « encore en train de
répondre à autre chose », `/status` - est dans la langue définie sous
**Réglages → Agents**, celle dans laquelle répondent les agents.

## Répondre à un agent depuis Discord

Discord fonctionne de la même façon que Telegram, avec un bot à vous. Cinq
minutes de configuration, une seule fois.

### Créer le bot

1. Ouvrez <https://discord.com/developers/applications> et appuyez sur **New
   Application**. Donnez-lui le nom que vous voulez.
2. **Bot** dans la barre latérale, puis **Reset Token**, et copiez ce qui
   s'affiche. C'est le `bot_token`, et il n'est montré qu'une fois.
3. **OAuth2 → URL Generator** : cochez **bot** et, en dessous, **View
   Channels**, **Send Messages** et **Read Message History**. Ouvrez l'URL
   qu'il construit et ajoutez le bot à votre serveur.
4. Dans Discord lui-même, activez **Paramètres → Avancés → Mode développeur**,
   puis faites un clic droit sur le salon où vous voulez les agents et
   choisissez **Copier l'identifiant du salon**. C'est le `channel_id`.

Il ne faut rien d'autre. En particulier, vous n'avez **pas** besoin du Message
Content Intent : cet interrupteur concerne la Gateway, et ceci lit le salon via
l'API ordinaire.

### L'activer

Sous **Réglages → Canaux → Discord**, remplissez le jeton et l'identifiant du
salon, cochez **Me laisser répondre aux agents depuis Discord**, et
enregistrez. En quelques secondes, le journal indique quel bot écoute et où :

```bash
journalctl -u boa-channel-discord.service | grep "Listening"      # Debian
tail /opt/boa/logs/boa-discord.log                # Alpine
```

Les messages écrits avant que vous l'activiez ne reçoivent pas de réponse : le
premier passage note où en est le salon et part de là.

### Parler à un agent

| Commande | Ce qu'elle fait |
|---|---|
| `!agents` | Liste vos agents et ce qu'il faut taper pour joindre chacun d'eux |
| `!status` | Les services, le tableau et chaque agent avec son modèle, ses outils et ses compétences |
| `!help` | Ces trois commandes, et les autres façons de joindre un agent |

`/agents` fonctionne aussi, si c'est ce que vos doigts tapent. Il n'y a ici ni
boutons ni menu de commandes slash : ce sont tous deux des *interactions*, que
Discord ne livre que par une connexion que cette installation, délibérément,
n'ouvre pas.

Les trois façons de vous adresser à quelqu'un sont celles que vous connaissez
déjà :

1. **Répondre à quelque chose qu'un agent a dit** va à cet agent, quel que soit
   celui qui est sélectionné. Clic droit sur son message → Répondre, ou faites-le
   glisser sur un téléphone.
2. **En nommer un** - `@os-watcher check the disk` - va à lui *et* en fait
   l'agent sélectionné. `!os-watcher`, `@001` et `@News Miner what is new`
   fonctionnent tous.
3. **Ni l'un ni l'autre** va à celui que vous avez choisi en dernier.

### Ce qui revient

La réponse arrive en réponse à votre question, avec le nom de l'agent en gras
sur la première ligne, et **tout l'échange figure dans la conversation de cet
agent dans l'interface web**, avec `(via Discord)` à côté de l'heure sur ce que
vous avez envoyé.

Une longue réponse arrive en plusieurs messages plutôt qu'en un seul tronqué :
Discord refuse tout ce qui dépasse 2 000 caractères, donc une réponse est
découpée entre les lignes, en quatre messages au plus. Vous pouvez répondre à
n'importe lequel d'entre eux, et cela parvient au même agent. S'il y avait de
quoi remplir plus de quatre messages, le dernier se termine par `…` - et
l'intégralité se trouve dans l'interface web, là où elle a été écrite.

### Qui peut parler à vos agents

**Tous ceux qui peuvent écrire dans ce salon.** C'est la seule vraie différence
avec Telegram, et elle mérite une minute de votre temps : là-bas, le bot
compare l'identifiant de conversation de chaque message et jette ce qui ne
correspond pas, si bien qu'un inconnu qui trouve votre bot n'obtient rien. Ici,
le bot lit un salon, et quiconque peut y publier peut lancer des exécutions sur
votre serveur.

Mettez donc les agents dans un **salon privé** - un salon que vous seul, ou
vous et les personnes en qui vous avez confiance, pouvez voir. Le bot n'a
besoin d'accéder à rien d'autre.

### Si vous ne voulez que des alertes

Laissez le jeton vide et définissez plutôt une **URL de webhook** :
**Paramètres du salon → Intégrations → Webhooks → Nouveau webhook → Copier
l'URL du webhook**. Les agents peuvent alors écrire dans le salon, et c'est
tout. L'écoute a besoin du bot, donc l'interrupteur est refusé avec un webhook
plutôt que de ne rien faire.

## L'orchestrateur

`agent-000`, appelé **manager**, est le seul agent créé à l'installation. C'est un agent
normal à tous égards, sauf qu'il ne peut pas être supprimé.

Le schéma prévu : donnez au manager les outils du kanban et un prompt qui lui
dit de découper les objectifs en cartes et de les attribuer à d'autres agents
par leur identifiant. Donnez aux autres agents `bash.run` et tout ce dont ils
ont besoin d'autre, et un prompt qui leur dit de travailler sur les cartes qui
leur sont attribuées.

Cela ne marche que si les cartes du manager disent ce que « terminé » veut
dire. Une carte qui ne le dit pas est un vœu, et l'agent qui la prend décidera
par lui-même.

## L'onglet Outils

**Réglages → Outils** montre ce qui est installé sur le serveur. Chaque famille
est un sous-onglet - Automatisation, Navigateur, Canaux, E-mail, Images,
Internet, Kanban, Mémoire, Système d'exploitation, RAG, Compétences - avec le
nombre d'outils qu'elle contient, et
chaque outil a sa case avec ses arguments et leur signification. L'onglet
ouvert figure dans l'URL (`/settings/?tab=tools&family=mail`), donc un rechargement ou un favori le conserve.
Les anciens liens `/tools/` redirigent ici et gardent la famille sélectionnée.

Un outil dont personne n'a nommé la famille - un `.py` que quelqu'un a déposé
dans `/opt/boa/tools/` - va dans **Autres**, avec sa famille écrite sur sa
propre case. C'est quand même un outil à part entière jusqu'à l'interface ; il
ne mérite simplement pas un onglet à lui, sinon la rangée grandirait avec
chaque script ponctuel.

L'agent qui peut utiliser tel ou tel outil se règle dans l'onglet **Outils**
propre à chaque agent, pas ici.

## La documentation de l'API

**Documentation de l'API**, dans la barre latérale, liste chaque point d'accès
sous `/api/`, regroupé par domaine, avec ses paramètres et ce qu'il répond. Elle
est générée à partir de la propre description OpenAPI de cette installation,
donc elle ne peut pas s'écarter du code : `openapi.json`, lié en haut de la
page, est la même chose sous forme de fichier que vous pouvez donner à un
générateur de clients.

Elle est dans la langue que vous avez choisie dans **Réglages → Interface**,
comme le reste de l'interface. La spécification elle-même reste en anglais :
les noms de champs, les identifiants et les chaînes d'erreur sont en anglais
partout dans ce projet, et un `openapi.json` traduit décrirait une API qui
n'existe pas.

Les corps de requête sont affichés en JSON coloré, comme les montre un éditeur :
les noms de champs d'une couleur, les valeurs d'une autre, et les accolades et
virgules atténuées parce qu'elles ne sont que de l'échafaudage. Les couleurs
viennent du thème que vous avez choisi, et copier un bloc donne toujours du
JSON valide.

La page est aussi lisible sans se connecter, seule, sans la barre latérale. Elle
décrit la forme de l'API, aucune de vos données.

## Le travail qui n'a pas besoin que l'agent réfléchisse

Certains travaux sont récurrents et mécaniques : vérifier un certificat, faire
tourner un journal, relever un nombre. Réveiller un agent pour cela coûte des
jetons à chaque fois, pour arriver à une conclusion qu'un script shell atteint
gratuitement.

Un agent peut donc écrire des scripts pour lui-même et les planifier.
Donnez-lui les outils **Automatisation** et il peut :

1. `script.write` — mettre un script shell dans son propre répertoire
   `scripts/`.
2. `cron.add` — le lancer selon une planification, dans son propre crontab.
3. Lire les résultats à sa prochaine exécution, et décider de ce qu'ils
   signifient.

Le script s'exécute sous l'utilisateur Linux de cet agent, avec les mêmes
permissions que l'agent, et **il ne coûte aucun jeton** - c'est un script
shell, pas un appel à un modèle. Ce qui coûte des jetons, c'est que l'agent
lise la sortie ensuite et décide quoi en faire.

Ce qu'il n'a pas le droit de faire :

- Planifier autre chose que ses propres scripts. Une commande libre dans un
  crontab est quelque chose que personne ne peut relire après coup.
- S'exécuter plus souvent que toutes les 5 minutes. Une tâche chaque minute
  n'est pas une planification.
- Toucher la ligne qui le réveille. Celle-là est à vous, dans son onglet
  **Cron**.

Vous voyez les deux moitiés : les scripts dans son répertoire personnel, et les
lignes qui les lancent dans l'onglet Cron, à côté des vôtres.

## Où aboutit le rapport d'une exécution

Une exécution que vous lancez depuis la conversation vous y répond. Une
exécution lancée par une carte arrivée à échéance répond au même endroit. Une
exécution lancée par le **propre crontab** de l'agent ne répond nulle part en
particulier - personne ne lui a rien demandé - donc :

- **Toujours dans l'Historique**, sous **Dernières exécutions** : ce que chaque
  exécution a dit, avec ce qu'elle a coûté. C'est là qu'il faut regarder quand
  vous vous demandez ce qu'un agent a fait.
- **Dans la conversation aussi, quand cela vaut la peine de vous
  interrompre** : l'exécution n'a pas abouti, ou elle a changé quelque chose
  que vous verriez - une carte, un message dans un canal, une boîte aux
  lettres. Une exécution qui s'est contentée de regarder reste dans
  l'Historique. Sinon, un agent avec un crontab horaire publierait vingt-quatre
  messages « rien à signaler » par jour dans la conversation.

Ces messages indiquent au-dessus d'eux que personne ne les a demandés, et ils
ne sont jamais renvoyés au modèle, donc ils ne coûtent rien à votre prochain
message.

**Une exécution qui n'a jamais démarré figure aussi dans l'Historique**,
marquée « non démarrée ». Appuyez sur **Exécuter maintenant** pour un agent
dont la clé d'API n'est pas encore définie, ou alors que l'agent est déjà en
train de s'exécuter, et la ligne dans l'Historique vous dit lequel des deux cas
c'était. Avant, l'écran disait que l'exécution avait démarré et rien d'autre
n'apparaissait jamais, parce que la raison était écrite à un endroit que rien
ne lit. Une exécution qui n'a pas démarré ne compte pas dans les exécutions du
jour de l'agent, et n'est pas non plus comptée comme un échec de l'agent : rien
n'en a tourné.

## La barre d'état

La bande au bas de chaque page, qui court sur toute la largeur de la fenêtre,
sous la barre latérale aussi, concerne l'installation dans son ensemble :

- **exécuteur** et **API des agents**, en vert quand ils tournent. Si l'un des
  deux est rouge, les agents ne s'exécuteront pas et rien d'autre dans
  l'interface ne vous le dira.
- **agents** : combien sont allumés sur combien il en existe.
- **tableau** : les cartes de chaque colonne.
- **jetons aujourd'hui** : tout ce qui a été dépensé depuis minuit UTC, pour
  tous les agents, et en combien d'exécutions. C'est le nombre qui montre
  qu'un agent est parti en boucle avant que la facture ne le fasse.

À l'extrémité droite de la bande, le logo GitHub et le nom **nipegun** ouvrent
le dépôt du projet, <https://github.com/nipegun/bunch-of-aigents>, dans un
nouvel onglet. Le compte avec lequel vous êtes connecté n'est pas affiché : une
installation n'en a jamais qu'un, donc l'afficher ne vous apprendrait rien que
vous ne sachiez déjà.

## Dans quelle langue vos agents répondent

Écrivez le prompt de chaque agent dans la langue dans laquelle vous pensez, et
il répondra dans celle-ci. Cela couvre la conversation. Cela ne couvre pas une
exécution lancée par le propre crontab de l'agent : personne ne lui a écrit
dans aucune langue, et les prompts fournis sont en anglais - si bien qu'une
installation utilisée en espagnol recevait ses rapports planifiés en anglais.

**Réglages → Agents → Langue dans laquelle les agents répondent** règle cela
pour tous les agents à la fois. Le réglage ajoute une ligne au prompt système
de chaque agent, écrite dans la langue qu'il demande, qui dit qu'elle prime sur
tout ce que le prompt dit au sujet des langues. Laissez-le sur la valeur par
défaut et rien ne change : chaque agent répond dans la langue de son propre
prompt.

Il est gardé sur le serveur, contrairement à la langue de cette interface, qui
est une préférence de votre navigateur. Une exécution réveillée par cron n'a
pas de navigateur.

## Écrire les prompts dans votre propre langue

Écrivez le prompt système dans la langue dans laquelle vous pensez. Rien dans le
système n'est lié à l'anglais : le prompt, la mémoire, la conversation, les
titres des cartes et les messages entre les services sont tous en UTF-8 de bout
en bout, accents compris.

Le prompt par défaut que reçoit un nouvel agent est en anglais, et sa dernière
règle dit à l'agent de répondre dans la langue dans laquelle son prompt est
écrit. Réécrivez le tout dans votre langue et cette règle suit - l'agent
suivra le prompt qu'il a, pas celui avec lequel il a commencé.

Les prompts sont stockés en lignes entières, sans retour à la ligne à une
colonne fixe. La zone de texte les replie à l'écran pour qu'ils restent
lisibles, sans mettre les sauts de ligne dans le fichier : une règle qui tient
en une phrase reste sur une ligne, et la modifier ne veut pas dire remettre en
forme tout un paragraphe.

## Sauvegarder et restaurer

Tout ce qui fait que cette installation est la vôtre vit sous `/opt/boa/` et
dans les utilisateurs Linux des agents. Une seule commande rassemble tout dans
une seule archive :

```bash
./install-update-reinstall-debian.sh --backup
```

Elle écrit `/root/boa-backup-<date>.tar.gz`, réservé à `root`, en mode 0600,
avec les services en marche - rien ne s'arrête. Passez un chemin pour l'écrire
ailleurs : `--backup /mnt/usb/boa.tar.gz`. Dedans : les deux bases de données,
copiées via l'API de sauvegarde propre à SQLite pour que rien de ce qui se
trouve encore dans un journal d'écriture anticipée (WAL) ne soit oublié ; les
clés des fournisseurs, les secrets des canaux et le secret de session ; les
certificats ; chaque agent avec son répertoire personnel, ses fichiers protégés,
son utilisateur Linux et son crontab ; les compétences et les outils écrits sur
ce serveur ; et le journal d'installation, pour le mot de passe qu'il contient.
Pas dedans : le code, l'environnement Python, le navigateur, et les deux choix
propres à cette machine - le mode de ports et la présence ou non d'un
navigateur - pour qu'une restauration n'importe jamais ceux d'une autre
machine.

**Gardez-la aussi privée que la machine.** Elle contient toutes les clés d'API,
tous les jetons des canaux et le mot de passe de connexion.

Pour restaurer, sur cette machine ou sur une nouvelle :

```bash
./install-update-reinstall-debian.sh --install       # sur une nouvelle machine uniquement
./install-update-reinstall-debian.sh --restore /root/boa-backup-<date>.tar.gz
```

Elle demande un YES, ou accepte `--yes`. Ensuite, elle arrête les services,
recrée les utilisateurs des agents avec les mêmes noms, et les mêmes
identifiants quand ils sont libres, remplace les bases de données, les clés,
les certificats, les agents, les compétences et les outils par ceux de
l'archive, installe les crontabs, et démarre tout. Connectez-vous avec l'e-mail
et le mot de passe de la sauvegarde : les deux sont ajoutés à
`/opt/boa/logs/install.log` sous l'intitulé `Credentials of the restored
backup`, et le journal complet de la sauvegarde est conservé à côté sous le nom
`install.log.restored-<date>`.

Un agent que cette machine avait et que la sauvegarde n'a pas garde son
répertoire personnel sur le disque et disparaît de l'interface, parce que la
liste des agents se trouve dans la base de données restaurée. Sous Alpine, ce
sont les deux mêmes options, sur `install-update-reinstall-alpine.sh`.

## Services

| Service | S'exécute sous | Ce qu'il fait |
|---|---|---|
| `boa-proxy` | `boa` | HAProxy : termine le TLS sur 11443, redirige 11080, et sert les ports web |
| `boa-web` | `boa` | L'interface web et l'API, sur un socket Unix derrière le proxy |
| `boa-exec` | `root` | Crée les utilisateurs, installe les crontabs, lance les exécutions des agents |
| `boa-samba` | `root` | Authentifie les utilisateurs SMB et sert chaque dossier samba/ sous l'utilisateur de son agent |
| `boa-agent-api` | `boa` | La porte qu'utilisent les agents pour atteindre le tableau et les canaux |
| `boa-buzzer` | `boa` | Surveille le tableau et réveille un agent quand une carte arrive à échéance |
| `boa-embeddings` | `boa` | Sert le modèle de vectorisation local des bibliothèques documentaires, sur un socket Unix |
| `boa-rag` | `boa` | Ordonnance la file d'indexation des bibliothèques documentaires |
| `boa-channel-telegram.service` | `boa` | Écoute Telegram, pour que vous puissiez répondre à un agent depuis votre téléphone |
| `boa-channel-discord.service` | `boa` | La même chose pour un salon Discord |

```bash
systemctl status boa-proxy boa-web boa-exec boa-agent-api boa-buzzer \
                 boa-embeddings boa-rag \
                 boa-channel-telegram.service boa-channel-discord.service boa-samba
journalctl -u boa-exec -f
```

Sous Debian, les unités des canaux utilisent `boa-channel-<channel>.service`.
Une mise à jour avec `--update` arrête et désactive les anciennes unités des
canaux avant d'activer les nouvelles.

Les mêmes processus tournent sous Alpine ; ses services de canaux restent
`boa-telegram` et `boa-discord`. Ce sont des services OpenRC supervisés par
`supervise-daemon`, et ce que chacun affiche va dans son propre fichier sous
`/opt/boa/logs/`, avec une rotation hebdomadaire :

```bash
rc-status
rc-service boa-exec status
tail -f /opt/boa/logs/boa-exec.log
```

## Sécurité

La conception part du principe qu'un agent finira par faire quelque chose que
vous n'aviez pas prévu, parce que c'est un modèle de langage avec un shell.

- **Chaque agent est un utilisateur Linux distinct**, et son répertoire
  personnel est en `0700`. Les agents ne peuvent pas lire les fichiers, les
  prompts ou les clés d'API les uns des autres.
- **`/opt/boa/agents/` est en `0711`**, donc aucun agent ne peut même lister
  quels autres agents existent.
- **Aucun agent ne s'exécute jamais en tant que root.** Seul `boa-exec` le
  fait, et il accepte une liste fermée d'opérations via un socket Unix. Il n'y
  a pas de « exécute cette commande » parmi elles.
- **Une exécution est bornée par le noyau, pas seulement par ses plafonds.**
  Aucun agent ne peut avoir plus de 1 024 processus et threads, donc une fork
  bomb s'arrête à ce nombre ; sous Debian, chaque exécution vit dans son propre
  scope systemd avec 2 Gio de mémoire, ce qui met aussi fin, quand elle se
  termine, à ce que l'exécution a laissé tourner.
- **Les agents ne voient jamais les identifiants des canaux.** Un jeton de bot
  n'est pas un message : c'est une autorisation permanente d'envoyer tout ce que
  ce bot peut envoyer. Les agents demandent à l'API des agents d'envoyer, et
  c'est elle qui envoie.
- **Les agents ne touchent qu'à leurs propres cartes.** Voir [Le tableau kanban](#le-tableau-kanban).
- **`web.fetch` refuse les adresses privées**, en vérifiant l'IP résolue et en
  la revérifiant à chaque redirection, donc on ne peut pas dire à un agent qui
  lit une page hostile d'appeler votre réseau interne.

Il est destiné à un réseau local et ne doit pas être exposé à Internet.

## Quand quelque chose ne fonctionne pas

**J'ai choisi `--ports direct` et le HAProxy de la machine a disparu.** Il n'a
pas disparu, il est à la retraite : arrêté, retiré de tous les runlevels sous
Alpine, désactivé et masqué sous Debian, et son `/etc/haproxy/haproxy.cfg`
supprimé si c'est l'installateur qui l'avait écrit, ou conservé sous le nom
`haproxy.cfg.before-boa.<date>` si c'était vous. Dans ce mode, l'application se
lie elle-même à 80 et 443, et tout autre programme qui occupe ces ports
l'empêche purement et simplement de démarrer - un proxy laissé activé les
prendrait au prochain démarrage, avant même que l'application ne tourne. Le
paquet `haproxy` reste installé exprès : `boa-proxy` est `/usr/sbin/haproxy`,
et dans ce mode c'est lui qui sert 80 et 443.

Pour revenir en arrière, lancez l'installateur avec `--update --ports proxied` :
il démasque l'unité, réécrit la configuration de la machine et la démarre.
Votre ancien fichier, s'il y en avait un, est toujours à côté sous son nom
`before-boa`.

**`boa-proxy` redémarre en boucle et rien n'écoute sur 11443.** Lisez
`/opt/boa/logs/boa-proxy.log`. S'il dit `Cannot raise FD limit to 4131`, la
limite stricte de descripteurs de fichiers de cette machine est inférieure à ce
que le proxy a demandé - un petit conteneur, en général. Une installation faite
avant que ce soit corrigé a encore `maxconn 2048` dans
`/opt/boa/config/haproxy.cfg`. Lancer l'installateur avec `--update` réécrit le
fichier ; pour le corriger sur-le-champ :

```bash
sed -i 's/^  maxconn 2048$/  fd-hard-limit 4000/' /opt/boa/config/haproxy.cfg
rc-service boa-proxy restart        # systemctl restart boa-proxy sous Debian
```

HAProxy se dimensionne alors d'après les descripteurs qu'il peut réellement
avoir, ce qui, avec une limite stricte de 4 096, fait environ 1 987 connexions -
bien plus que ce dont il aura jamais besoin.

**L'installateur se termine par « Everything is in place but the application
does not answer ».** L'installation est là et aucune page n'est jamais revenue.
Le journal contient déjà la raison :

```bash
sed -n '/Why it did not answer/,$p' /opt/boa/logs/install.log
```

Ce bloc décrit l'état de la machine à ce moment-là : ce que curl a obtenu de la
requête, si quelque chose écoute sur le port, l'état des dix services, et les
dernières lignes de ce qu'ont affiché le proxy et l'application web. `000`
n'est pas un code HTTP - c'est curl qui dit qu'il n'en a jamais reçu. Un
service qui se dit `started` à côté de `nothing is listening on port
11443` est un processus qui meurt et redémarre toutes les quelques secondes, et
son propre journal, quelques lignes plus bas, dit pourquoi.

Une mise à jour qui a échoué à ce stade a déjà remis en place la version
précédente et la fait tourner. Une première installation n'a rien vers quoi
revenir, elle laisse donc tout en place : corrigez ce que nomme le bloc et
relancez l'installateur avec `--update`.

**L'installateur s'arrête avec « systemd is not running ».** Il refuse
d'installer sur une machine où systemd n'est pas le PID 1, parce que chaque
service qu'il écrit est une unité systemd et que rien ne pourrait les démarrer.
Une Debian normale convient ; un conteneur, non, à moins qu'il n'ait été créé
pour faire tourner systemd :

```bash
apt-get install -y systemd systemd-sysv dbus dbus-user-session
```

puis recréez le conteneur avec `/sbin/init` comme commande - un conteneur déjà
en marche ne peut pas changer son PID 1. Sous Alpine, la question ne se pose
pas : cet installateur ajoute lui-même OpenRC quand la machine n'en a pas.

**Il ne se passe rien quand j'appuie sur Exécuter maintenant.** Regardez les
deux points en bas de la barre latérale. Si `exécuteur` est rouge :

```bash
systemctl status boa-exec
journalctl -u boa-exec -n 50
```


**Le navigateur affiche 503 et les services tournent tous.** Le HAProxy de la
machine a marqué le backend comme hors service. Presque toujours, c'est à cause
de `option ssl-hello-chk` sur ce backend : son ClientHello est antérieur à
TLS 1.2 et l'application l'exige. Retirez cette ligne et rechargez HAProxy.

**Un agent s'exécute mais ne fait rien.** Regardez son panneau Historique. Puis
lancez-le à la main et observez :

```bash
runuser -u agent-001 -- /opt/boa/venv/bin/python3 \
  /opt/boa/webapp/backend/core/runner.py --agent-id 001
```

Ajoutez `--dry-run` pour voir ce qu'il chargerait — fournisseur, outils,
plafonds — sans appeler le modèle.

**Il dit qu'il ne peut pas joindre le modèle.** Pour les fournisseurs
auto-hébergés, vérifiez que le serveur tourne et que l'URL de base est
correcte. Pour les fournisseurs cloud, vérifiez que le fichier de clé existe
dans le répertoire personnel de l'agent et qu'il appartient à cet agent.

**Il dit qu'un outil ne lui est pas disponible.** L'outil n'est pas coché sur
la page de cet agent. Le prompt ne peut pas passer outre, et c'est tout
l'intérêt.

**Les cartes ont cessé d'apparaître.** Soit la case kanban est décochée pour cet
agent, soit `API des agents` est en rouge en bas de la barre latérale :

```bash
systemctl status boa-agent-api
```

**Je veux voir tout ce qu'un agent a fait.** Son journal se trouve dans son
propre répertoire personnel :

```bash
cat /opt/boa/agents/001/runs.jsonl
```

Un objet JSON par ligne : quand il s'est exécuté, ce qu'il a dépensé, s'il a
terminé.

## Licence

MIT. Voir [LICENSE](../LICENSE).
