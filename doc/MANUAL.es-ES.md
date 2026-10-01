# Manual

Cómo usar Bunch of AIgents en el día a día.

## Contenido

1. [Qué hace](#qué-hace)
1. [En qué sistemas funciona](#en-qué-sistemas-funciona)
1. [Si estás en Alpine](#si-estás-en-alpine)
1. [Instalación](#instalación)
1. [Actualizar y reinstalar](#actualizar-y-reinstalar)
1. [Abrirlo](#abrirlo)
1. [Entrar](#entrar)
1. [Primeros pasos](#primeros-pasos)
2. [La interfaz](#la-interfaz)
3. [De dónde sale un agente nuevo](#de-dónde-sale-un-agente-nuevo)
3. [Crear tu primer agente](#crear-tu-primer-agente)
4. [Hablar con un agente](#hablar-con-un-agente)
5. [Configuración del agente](#configuración-del-agente)
5. [Exportar un agente](#exportar-un-agente)
5. [Carpetas compartidas por Samba](#carpetas-compartidas-por-samba)
6. [Darle un modelo a un agente](#darle-un-modelo-a-un-agente)
5. [Escribir un prompt de sistema](#escribir-un-prompt-de-sistema)
6. [Elegir herramientas](#elegir-herramientas)
7. [Darle una habilidad a un agente](#darle-una-habilidad-a-un-agente)
8. [Darle un navegador a un agente](#darle-un-navegador-a-un-agente)
9. [Techos de gasto](#techos-de-gasto)
8. [Programar un agente](#programar-un-agente)
9. [El tablero kanban](#el-tablero-kanban)
10. [Temas](#temas)
11. [Canales](#canales)
12. [El orquestador](#el-orquestador)
13. [Copias de seguridad y restauración](#copias-de-seguridad-y-restauración)
13. [Servicios](#servicios)
13. [Seguridad](#seguridad)
14. [Cuando algo no funciona](#cuando-algo-no-funciona)
1. [Transcripción de audio](#transcripción-de-audio)
1. [Licencia](#licencia)

---

- [Bibliotecas documentales locales (RAG)](#bibliotecas-documentales-locales-rag)

## Qué hace

- **Un agente es un usuario de Linux.** Crear uno en la interfaz web crea
  `agent-007` en el sistema, con una carpeta home que ningún otro agente puede
  leer. Ese es el aislamiento: el del kernel, no un sandbox escrito en Python.
- **Los agentes se ejecutan según su propia programación.** Cada uno tiene su
  crontab, que pertenece a su usuario y lo ejecuta él, así que el agente
  despierta, hace su trabajo y termina.
- **Hablas con ellos.** Al hacer clic en un agente se abre un chat: le
  pides algo, usa sus herramientas y responde cuando termina. La
  conversación se recuerda.
- **Una conversación por agente, no una por persona.** Cuando llega la hora de
  una tarjeta, la tarjeta aparece en ese mismo chat justo al arrancar la
  ejecución, y la respuesta se ve debajo: el chat de un agente es todo lo que
  se le ha pedido, por ti o por otro agente, y lo que hizo con ello.
- **Comparten un tablero kanban.** Los agentes añaden tarjetas, las mueven y
  ven el trabajo de los demás. Tú lo miras en `/kanban/` en vez de leer logs.
- **Cualquier modelo, en la nube o autoalojado.** Vienen veinticinco
  proveedores: Anthropic, OpenAI, Google, DeepSeek, Mistral, Qwen, xAI y los
  demás; los enrutadores que hay por delante, OpenRouter, Groq, Together,
  Vercel y más; y Ollama, llama.cpp y vLLM en tu propio hardware. Cada agente
  elige el suyo, con un suplente para cuando ese se cae.
- **Techos de gasto que de verdad lo detienen.** Tokens, pasos, segundos y
  ejecuciones al día, por agente. Si no, un agente desatendido contra una API
  de pago es una factura abierta.
- **Memoria configurable.** Elige el límite en los ajustes de cada agente,
  entre 1.000 y 1.000.000 de caracteres (8.000 por defecto). Si el texto supera
  el límite, se rechaza el guardado sin recortarlo ni sustituir la memoria anterior.
- **Una biblioteca documental por agente.** Admite libros PDF, EPUB, TXT y
  Markdown. La extracción, el OCR y la vectorización son locales; el agente
  recupera pasajes relevantes y cita sus fuentes. Se configura en **RAG**. El
  modelo de vectorización es EmbeddingGemma 300M por defecto; una máquina con
  procesador y memoria de sobra puede cambiar a Qwen3-Embedding 0.6B en
  **Ajustes → RAG**.
- **Agentes que se pueden mover.** La pestaña **Exportar** de un agente lo
  descarga como un `.zip` (con su memoria, su modelo, su biblioteca y los
  archivos de su carpeta personal si se quiere, nunca con una clave) y **+** lo
  importa en esta instalación o en otra. Los agentes listos para usar salen
  del [repositorio de plantillas](https://github.com/nipegun/bunch-of-aigents-templates).
- **Herramientas ampliables.** Cada herramienta es un archivo `.py` en
  `/opt/boa/tools/`. Pon uno nuevo y aparece en **Ajustes → Herramientas**,
  agrupado en subpestañas como Automatización y Navegador.
- **Habilidades que comparten.** Un procedimiento escrito una sola vez en
  `/opt/boa/skills/` se le puede dar a tantos agentes como quieras. Lo que un
  agente aprende por su cuenta muere en su propia memoria; una habilidad no.
- **Un navegador por agente, con sus propias sesiones.** Un agente puede
  iniciar sesión en un sitio, rellenar un formulario y hacer clic —no sólo leer
  una página— y sus cookies viven en su propia carpeta home 0700: el acceso de
  un agente no es el acceso de todos.
- **Responderles desde Telegram o Discord.** Elige un agente con /agents, o
  responde a un mensaje que te mandó uno, y lo que escribas le llega, arranca
  una ejecución y vuelve contestado a tu móvil. El intercambio entero está
  también en la conversación de ese agente en la interfaz web, las dos
  mitades, así que una sola pantalla sigue mostrándolo todo.
- **Audios de Telegram.** En **Ajustes → Audio** eliges transcripción local con
  whisper.cpp o una API de OpenAI, Groq, Mistral, Together AI, Hugging Face o
  Cloudflare cuya clave ya esté guardada. Ofrece los 30 modelos nativos, con
  descarga bajo demanda. La nota de voz llega como texto al agente al que
  respondes y aparece en su chat web, con reproducción opcional del audio.
- **Una carpeta compartida por agente.** La carpeta `samba/` de cada agente es
  un recurso SMB con el nombre de su usuario de Linux, así que puedes dejarle
  archivos desde Windows, Linux o macOS.
- **Quince idiomas.** Alemán, inglés (Reino Unido y Estados Unidos), español
  (España y Argentina), francés, hebreo, hindi, italiano, japonés, coreano, portugués
  (Brasil y Portugal), ruso y chino simplificado. La interfaz, la línea que les
  dice a tus agentes en qué idioma responder, y lo que dicen los dos bots.

Está pensado para una sola persona que lo ejecuta en su propia LAN.

## En qué sistemas funciona

Dos sistemas, y en los dos el init forma parte del requisito, no es un detalle:

- **Debian con systemd como PID 1.** Los diez servicios son unidades de
  systemd. En un Debian que arranque con otra cosa no hay nada que los
  arranque, así que el instalador comprueba `systemctl is-system-running`
  antes de tocar la máquina y se niega si systemd no está. No lo intentes en
  una máquina así: la respuesta no va a cambiar.
- **Alpine con OpenRC.** Los diez servicios son scripts de OpenRC supervisados
  con `supervise-daemon`. No hay que instalar nada por adelantado: el
  instalador añade `openrc` él mismo cuando la máquina no lo tiene.

En Debian se comprueba con `systemctl is-system-running`: tiene que responder
algo (`running`, `degraded`, `starting`), no imprimir «System has not been
booted with systemd as init system (PID 1)». Un contenedor necesita `systemd
systemd-sysv dbus` instalados y `/sbin/init` como su comando.

Además del sistema de init, necesita:

- Acceso a `root`. Ninguno de los dos instaladores usa `sudo` ni lo necesita.
- Unos 500 MB de disco para la aplicación y su entorno de Python.
- `haproxy`, que instala el propio instalador. Es quien termina el TLS, porque
  la cabecera PROXY que envía el HAProxy de la máquina llega antes del handshake
  TLS y sólo un proxy puede leerla ahí.
- Un modelo con el que hablar: una clave de API de un proveedor de nube, o
  bien Ollama, llama.cpp o vLLM ejecutándose en algún sitio accesible.

El instalador también compila **whisper.cpp v1.9.4** en `/opt/boa/whisper/`,
instala FFmpeg y descarga el modelo multilingüe `base` (unos 142 MiB
adicionales). La compilación, las dependencias del sistema y el navegador
necesitan espacio adicional. Si falta Python, lo instala antes de comprobar su
versión.

Todo lo demás de este manual es igual en los dos.

## Si estás en Alpine

Todos los comandos de este manual que nombran `systemctl` o `journalctl` son
los de Debian. La aplicación es la misma en Alpine; lo que cambia es el sistema
de init y dónde acaban los logs:

| En Debian | En Alpine |
|---|---|
| `systemctl status boa-web` | `rc-service boa-web status`, o `rc-status` para los diez |
| `systemctl restart boa-web` | `rc-service boa-web restart` |
| `journalctl -u boa-web -f` | `tail -f /opt/boa/logs/boa-web.log` |
| `install-update-reinstall-debian.sh` | `install-update-reinstall-alpine.sh` |

Allí falta una funcionalidad, y no va a volver: no hay navegador, porque
Playwright no publica ninguna versión para musl. Las herramientas de navegador
siguen en la lista y lo dicen cuando un agente llama a alguna.

---

## Instalación

Un instalador por distribución, y los dos aceptan las mismas flags. Ejecútalo
como `root`.

### En Debian

> **systemd tiene que estar corriendo en la máquina.** Ejecuta antes
> `systemctl is-system-running`: si imprime «System has not been booted with
> systemd as init system (PID 1). Can't operate.», párate aquí. Cada servicio
> que se instala es una unidad de systemd, así que no habría nada que los
> arrancara, y el instalador se niega por eso en vez de dejarte una
> instalación que no sirve nada.

```bash
curl -fsSL https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-debian.sh \
  | bash -s -- --install --email tu@ejemplo.com
```

Si no tienes `curl` —un Debian mínimo no suele traerlo, ni tampoco `wget`—,
instálalo antes, o la línea de arriba imprime `curl: command not found` y se
queda ahí:

```bash
apt-get update && apt-get install -y curl
```

O descárgalo primero y léelo antes de ejecutarlo, que es mejor costumbre:

```bash
wget https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-debian.sh
less install-update-reinstall-debian.sh
chmod +x install-update-reinstall-debian.sh
./install-update-reinstall-debian.sh --install --email tu@ejemplo.com
```

### En Alpine Linux

Las mismas flags, otro script: escribe servicios de OpenRC en vez de units de
systemd. Una sola línea, con `wget` y canalizada a `sh`, porque un Alpine
recién instalado no tiene `curl` ni bash, y esos dos sí los trae BusyBox:

```bash
wget -qO- https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-alpine.sh \
  | sh -s -- --install --email tu@ejemplo.com
```

En una máquina que sí tenga `curl`, usa `curl -fsSL` en lugar de `wget -qO-`;
y si lo haces, mira esa línea, porque un `curl: not found` canalizado a `sh`
imprime su error y luego **termina con éxito**, sin haber instalado nada.

El instalador está escrito en shell POSIX en vez de en bash por la misma razón
que el `wget`: un Alpine recién instalado no tiene bash al que canalizar con
`| bash -s --`. Él mismo instala bash por el camino —cada agente recibe una
shell bash—, así que en una máquina que ya la tenga, `| bash -s --` funciona
igual de bien.

O descárgalo antes y léelo antes de ejecutarlo:

```bash
wget https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-alpine.sh
less install-update-reinstall-alpine.sh
chmod +x install-update-reinstall-alpine.sh
./install-update-reinstall-alpine.sh --install --email tu@ejemplo.com
```

Una vez en marcha hay dos diferencias, y las dos son cosa del sistema, no una
decisión:

- **No hay navegador.** Playwright no publica compilación para musl y Alpine
  no lo empaqueta, así que `browser.open` y los demás lo dicen cuando un
  agente llama a uno. `web.fetch` y `rss.fetch` funcionan igual que en
  cualquier sitio.
- **`rc-status` en lugar de `systemctl status`**, y `rc-service boa-web
  restart` en vez de `systemctl restart boa-web`. Véase
  [Si estás en Alpine](#si-estás-en-alpine).

En Alpine, los servicios liberan la salida SSH del instalador, así que éste
devuelve el control de la sesión al terminar.

### Qué hace el instalador

1. Crea el usuario de sistema `boa` y el árbol de carpetas bajo `/opt/boa/`.
2. Instala las dependencias de Python en `/opt/boa/venv/`.
3. Genera un certificado TLS autofirmado, salvo que hayas dejado un
   `fullchain.pem` y un `privkey.pem` propios en `/opt/boa/certificates/`.
4. Pregunta si servir la aplicación en 11080/11443 con un HAProxy delante en
   el 80 y el 443, o directamente en el 80 y el 443. Con `--ports
   proxied|direct` se responde de antemano. La respuesta se recuerda, así que
   un `--update` no vuelve a preguntar ni la cambia en silencio. Elegir
   `direct` retira el HAProxy de la máquina: parado, fuera de todos los
   runlevels o enmascarado, y su `/etc/haproxy/haproxy.cfg` borrado si lo
   escribió este instalador o conservado como `haproxy.cfg.before-boa.<fecha>`
   si lo escribió otro, para que nada se quede con el 80 y el 443 en el
   siguiente arranque. El paquete haproxy se queda: el proxy de la propia
   aplicación es ese binario.
5. Crea un agente: `manager`, el orquestador. Todo lo demás es un agente
   vacío, un `.zip` exportado de un agente o una plantilla del
   [repositorio de plantillas](https://github.com/nipegun/bunch-of-aigents-templates)
   (`web-navigator`, `os-watcher`, `mail-watcher` y otros), que se eligen al
   pulsar **+**. La primera opción que se ofrece es el agente vacío.
6. Instala y arranca los servicios que se listan en [Servicios](#servicios):
   units de systemd en Debian, servicios de OpenRC supervisados con
   `supervise-daemon` en Alpine.
7. Escribe lo que ha hecho, y tu contraseña de acceso, en
   `/opt/boa/logs/install.log` (de root, modo 0600).
8. Le pide a la aplicación su página de inicio de sesión antes de decir que ha
   terminado. Si esa página no llega, lo dice, escribe en ese mismo log el
   aspecto que tenía la máquina en ese momento —qué entendió curl de la
   petición, si hay algo escuchando en el puerto, el estado de los servicios y
   las últimas líneas de lo que imprimieron— y nombra el log en vez de dar la
   instalación por buena. Un `--update`, además, deja antes la versión
   anterior funcionando otra vez.

### Dónde está la contraseña

El correo que indiques será el único login. La contraseña se genera sola;
léela con:

```bash
cat /opt/boa/logs/install.log
```

Ese único archivo es las dos cosas: el registro completo de la instalación y
las credenciales que generó. La pantalla de inicio de sesión lo nombra, para
que nadie tenga que acordarse de dónde está.

## Actualizar y reinstalar

```bash
./install-update-reinstall-debian.sh --update      # conserva agentes y datos
./install-update-reinstall-debian.sh --reinstall   # borra todo antes
```

En Alpine son las mismas dos flags, sobre el otro script:

```bash
./install-update-reinstall-alpine.sh --update
./install-update-reinstall-alpine.sh --reinstall
```

`--reinstall` borra todos los agentes, sus carpetas home, sus crontabs y el
tablero kanban. Pide confirmación salvo que pases `--yes`.

Una instalación que murió a medias, por una descarga que falló o una red que
se cayó, se termina ejecutando `--install` otra vez: continúa donde se quedó, y
`--update` lo dice si se encuentra una.

Las otras dos flags, `--backup` y `--restore`, se explican en
[Copias de seguridad y restauración](#copias-de-seguridad-y-restauración).

## Abrirlo

En el modo `proxied`, el predeterminado, el HAProxy propio de la aplicación
escucha en `127.0.0.1:11443` (HTTPS) y `127.0.0.1:11080` (HTTP, que redirige).
Esos puertos no son accesibles desde fuera del servidor: el HAProxy de la
máquina es el que sirve a la LAN, y manda al 11443 con `send-proxy-v2`, así
que la IP real del cliente no se pierde. En el modo `direct` la aplicación
escucha ella misma en el 80 y el 443, sin nada delante.

Con eso puesto, abre:

```
https://tu-servidor/
```

El certificado es autofirmado salvo que hayas dejado certificados propios en
`/opt/boa/certificates/`, así que el navegador te avisará una vez.

### Cómo tiene que estar el HAProxy de la máquina

El backend que apunta a esta aplicación necesita dos cosas:

```
backend https-out
  mode tcp
  server srv-https-out 127.0.0.1:11443 check port 11080 send-proxy
```

- **`send-proxy`**, para que la IP real del cliente llegue a la aplicación. Sin
  él, todas las peticiones parecen venir de 127.0.0.1 y el límite de intentos
  de login deja de ser por dirección.
- **`check port 11080`**, para que el health check llame al puerto HTTP plano
  y no al de TLS. Un check TCP contra el puerto TLS conecta y cuelga sin
  handshake, y el HAProxy de la propia aplicación apunta cada uno como un fallo
  de handshake SSL: una línea cada dos segundos, para siempre. Los dos puertos
  son de un mismo proceso, así que si uno responde el otro está. No añadas
  `check-send-proxy`: 11080 no acepta PROXY protocol.
- **Sin `option ssl-hello-chk`.** Su ClientHello es anterior a TLS 1.2, así que
  un backend que exija TLS 1.2 —este, y cualquier Apache o nginx moderno— falla
  el check y queda marcado como caído para siempre. El síntoma es un 503 de un
  servicio que funciona perfectamente. Un `check` a secas ya comprueba que el
  puerto responde.

## Entrar

Abre `https://tu-servidor/` y entra con el correo que le diste al instalador y
la contraseña que generó. Si no la tienes:

```bash
cat /opt/boa/logs/install.log
```

Ese archivo es el registro completo de la instalación con las credenciales al
final, y la pantalla de inicio de sesión lo nombra justo para este momento.

**Cerrar sesión** abre una confirmación en el centro de la pantalla. Confirma
para salir, o elige **Cancelar** o pulsa Escape para mantener la sesión abierta.

Sólo hay una cuenta. Cambia su contraseña en **Ajustes → Cuenta**.
Para cambiarla te pide también la actual: eso es lo que hace que sea un
cambio tuyo y no de quien encuentre el navegador abierto. Además cierra
de golpe todas las demás sesiones, en todos los demás dispositivos, que
es justo para lo que se cambia una contraseña cuando crees que alguien
más tiene una.

La primera vez que abras la aplicación tras una actualización te pedirá
iniciar sesión otra vez. Las sesiones anteriores a la actualización no
llevan constancia de cuándo se concedieron, y a «no lo puedo saber» se
responde preguntando.

Tras diez intentos fallidos desde la misma dirección, el login se cierra
durante quince minutos, también para las contraseñas correctas.

## Primeros pasos

1. Entra con tu correo y la contraseña generada.
2. Si el agente va a usar un proveedor de nube, guarda antes su clave en
   **Ajustes → Claves de API**: la lista de proveedores sólo ofrece los de
   nube que tienen clave (véase [Claves de API](#claves-de-api)).
3. Pulsa **+** en la barra lateral para crear tu primer agente.
4. Elige su proveedor y su modelo. Para Ollama en la misma máquina, los valores
   por defecto ya son correctos. Para cobrar este agente a otra cuenta, dale
   una clave propia (véase [Darle un modelo a un agente](#darle-un-modelo-a-un-agente)).
5. Escribe su prompt de sistema: para qué sirve y qué significa «terminado».
6. Dale las herramientas que necesite. Empieza por las de kanban.
7. Pulsa **Ejecutar ahora** y mira el tablero.
8. Cuando haga lo que quieres, dale una programación.

## La interfaz

El logo circular azul muestra tres agentes robóticos con paneles faciales
claros, visores oscuros y ojos azules, vestidos con traje negro, camisa blanca
y corbata oscura, de cintura para arriba y con el central más grande. Aparece
en el inicio de sesión, en la barra lateral y en la pestaña del navegador.

La barra lateral de la izquierda lista tus agentes. Cada uno muestra su id, su
nombre, cuántas veces se ha ejecutado y cuántos tokens ha gastado. Todos los
cuadros miden lo mismo de alto, así que un nombre largo se corta con puntos
suspensivos: pasa el ratón por encima para leerlo entero. El cuadro
que rodea al id lleva un contorno verde cuando el agente está activado y rojo
cuando no lo está.

**Cuando un agente está trabajando, un trozo encendido recorre ese contorno
verde en el sentido de las agujas del reloj.** Te dice que el agente está ahora mismo en mitad de una
ejecución, no qué está haciendo, sólo que está haciendo algo. Empieza a girar
en cuanto le envías un mensaje de chat o pulsas **Ejecutar ahora**, y se para
cuando la ejecución termina, venga de ti, de su programación o de una tarjeta
que ha vencido. El contorno se comprueba cada pocos segundos, así que puede ir
un momento por detrás.

Abajo del todo, dos puntos indican si los servicios de fondo están en marcha.
Si alguno está rojo, los agentes no se ejecutarán: mira
[Cuando algo no funciona](#cuando-algo-no-funciona).

El botón **+** crea un agente.

## El agente con el que empiezas

La instalación crea exactamente uno.

**`manager` (agent-000)** coordina a los demás. Parte los objetivos en tarjetas
y las reparte. Viene activado.

Eso es todo, y es a propósito: una instalación que llega con agentes que nadie
pidió es una instalación que empieza con cosas que apagar. Todo lo demás es
una **plantilla** del repositorio de plantillas, o un `.zip` que alguien
exportó, y se propone al pulsar **+**.

## De dónde sale un agente nuevo

Al pulsar **+** se te pregunta por dónde empezar:

| Opción | Qué hace |
|---|---|
| **Agente vacío** | Sin prompt, sin herramientas y sin programación. |
| **Importar desde un archivo .zip** | Un agente exportado desde su pestaña **Exportar**, en esta instalación o en otra. |
| **Importar desde una plantilla de GitHub** | Uno de los agentes del repositorio de plantillas, elegido de una lista. |

El **agente vacío** encabeza la lista, porque es la única respuesta que siempre
vale y todas las demás son un atajo hacia él.

### Plantillas de GitHub

Las plantillas viven en un repositorio propio,
[bunch-of-aigents-templates](https://github.com/nipegun/bunch-of-aigents-templates),
una carpeta cada una, así que una nueva llega a tu instalación sin
actualizarla. Al elegir **Importar desde una plantilla de GitHub**, el
servidor descarga ese repositorio (un único `.tar.gz`, que guarda cinco
minutos) y enumera sus agentes por orden alfabético, cada uno con su
descripción en tu idioma, las familias de herramientas que trae, cada cuánto
se despierta y si activa su biblioteca. Una herramienta que esta instalación
no tiene se deja fuera, y la lista lo dice. Una plantilla que no pasa las
comprobaciones no se ofrece, y una línea dice cuántas se quedaron fuera.

Estas son las plantillas que tiene hoy el repositorio:

| Plantilla | Qué hace |
|---|---|
| **backup-watcher** | Comprueba que las copias de seguridad se hicieron, son recientes y no son sospechosamente pequeñas. |
| **cert-watcher** | Avisa cuando un certificado TLS está a punto de caducar, mientras aún da tiempo. |
| **disk-cleaner** | Encuentra qué está llenando el disco y dice qué se podría quitar. Propone; nunca borra. |
| **kanban-watcher** | Lee el tablero cada mañana entre semana y escribe un resumen corto. |
| **log-watcher** | Lee los registros que le indiques y cuenta lo que es nuevo o lo que se ha vuelto frecuente. |
| **mail-watcher** | Vigila una cuenta de correo y actúa según las reglas que escribas en su prompt. |
| **news-watcher** | Lee los feeds RSS que le pongas en su prompt y cuenta lo que encaje con tus reglas. |
| **os-watcher** | Vigila esta máquina: disco, memoria, swap, carga y si los servicios están en marcha. |
| **rag-consultant** | Responde preguntas con los documentos de su biblioteca RAG, cita el fragmento que respalda cada afirmación y avisa cuando los documentos no cubren algo. |
| **site-watcher** | Comprueba que los sitios que le des responden, responden rápido y siguen diciendo lo que decían. |
| **web-navigator** | Maneja su propio navegador para hacer en un sitio lo que le pidas: buscar, entrar con tu sesión, rellenar un formulario, ir pasando páginas y contarte lo que encontró. |

`web-navigator` y `rag-consultant` no tienen programación horaria: trabajan
cuando se lo pides y la petición ES la tarea. `web-navigator` es también el que
enseña para qué está instalado el
navegador: entra en sitios, pulsa botones y rellena formularios, mientras que
los demás leen páginas. No escribe contraseñas, no compra nada ni pulsa un
botón de enviar: llega hasta ese paso y se para, diciendo qué botón lo
terminaría.

`rag-consultant` responde con su propia biblioteca de documentos, y es la única
plantilla que llega con esa biblioteca activada: sus herramientas se retiran
mientras está desactivada. Antes de que sirva de algo, sube documentos en su
pestaña **RAG** (consulta [Bibliotecas documentales locales](#bibliotecas-documentales-locales-rag))
y elige un modelo. Cada afirmación de sus respuestas enlaza con la página del
documento de la que sale; cuando los documentos no cubren algo, lo dice en vez
de rellenar el hueco. Su límite de tokens (40 000 por ejecución) es más alto que
el de los demás, porque los fragmentos que lee cuentan dentro de él.

Cada plantilla dice, antes de que la eliges, con qué familias de herramientas
viene y cada cuánto se despierta. Una plantilla es un conjunto de permisos
tanto como un prompt: «vigila un buzón» no te dice que llega pudiendo borrar
correo.

Todas las plantillas llegan **apagadas y sin modelo**: elegir una te da su
prompt, sus herramientas y una programación sugerida, y a partir de ahí espera
a que elijas proveedor y la enciendas.

Son puntos de partida. Se puede cambiar el prompt, las herramientas y la
programación, y varias dicen en su propio prompt qué necesitan que se rellene
antes de servir de algo, en vez de fallar a las tres de la mañana.

**Ajustes → Agentes** dice de qué repositorio y de qué rama sale la lista: el
del propio proyecto por defecto, un fork, o uno tuyo con la misma estructura.
Una máquina sin salida a GitHub puede usar una ruta `file://` que contenga
`archive/refs/heads/<rama>.tar.gz`, la misma estructura que acepta el
instalador. Si no se puede acceder al repositorio, la lista dice qué
dirección falló; importar un `.zip` sigue funcionando.

### Importar un .zip

1. Elige el `.zip`. Se sube por partes, con un porcentaje, así que también
   llega una biblioteca de cientos de MiB.
2. El servidor comprueba el paquete entero antes de nada. Nada de lo que trae
   puede ser una ruta que salga de la carpeta personal del agente, un archivo
   oculto como `.ssh` o `.bashrc`, el chat o el registro de ejecuciones, ni
   un horario que lleve un comando. Si algo está mal, se dice qué, y no se
   crea nada.
3. Se muestra lo que traería: su descripción, sus herramientas (y las que
   faltan en esta instalación), sus horarios, y si trae su memoria, archivos
   para su carpeta personal, documentos de la biblioteca o un modelo. Se
   confirma y se le da un nombre.
4. Se instala en segundo plano, con su progreso en pantalla. Los documentos
   de la biblioteca se suben uno a uno y aquí se vuelven a indexar. Si algo
   falla a mitad, el agente se vuelve a borrar en vez de quedarse a medio
   instalar.

Un agente importado también llega **apagado**. Si nombra un proveedor, su
clave hay que configurarla en esta instalación: las claves nunca viajan en
un `.zip`.

Si prefieres que no se pregunte nada, desactiva **Preguntar de dónde parte un
agente nuevo** en **Ajustes → Interfaz**: entonces **+** va directamente a un
agente vacío.

### Ningún agente tiene root

Ninguno, tampoco el orquestador. Ese es todo el modelo de aislamiento, y
conviene dejarlo claro porque decide lo que un agente como `os-watcher` puede
hacer:

- **Mirar no necesita privilegios.** `df`, `free`, `uptime`, `nproc` y
  `systemctl is-active` funcionan como usuario normal. Un agente ve un disco
  llenándose mucho antes de que se llene.
- **Arreglar sí suele necesitarlos, y no los tiene.** Su prompt le dice que
  diga exactamente qué comando haría falta en vez de intentarlo y fallar: una
  tarjeta que dice «hace falta root: journalctl --vacuum-size=200M liberaría
  1,2G» vale más que un intento fallido.

Si quieres que algo se arregle solo, pon ese comando en el crontab de root. Un
agente decidiendo por su cuenta borrar archivos como root no es una
funcionalidad que nadie quiera a las tres de la mañana.

## Crear tu primer agente

Pulsa **+**, elige un agente vacío, un `.zip` o una plantilla, y dale un nombre. Eso crea, en el servidor:

- el usuario de Linux `agent-001`,
- su home en `/opt/boa/agents/001/`, con modo 0700,
- dentro, `info.json`, `system-prompt.md` y un token de API.

El id es el número libre más bajo. El `000` está reservado para el orquestador.

Un agente nuevo empieza con las herramientas de kanban y nada más, y con techos
conservadores. No tiene programación, así que no hace nada hasta que le des una
o pulses **Ejecutar ahora**.

## Hablar con un agente

Haz clic en un agente de la barra lateral y aparece su chat. Escribe lo que
quieres que haga y pulsa Intro; Mayúsculas+Intro hace un salto de línea.

El campo donde escribes se queda quieto, justo encima de la barra de estado del
pie de la página: sólo se desplaza la conversación que tiene encima, así que
nunca queda tapado ni tienes que bajar para alcanzarlo. Mientras está vacío te
recuerda, en gris, qué hace Intro —o que el agente sigue trabajando—, y en un
teléfono estrecho crece una o dos líneas para que ese recordatorio no quede
cortado.

Un mensaje es una ejecución: el agente usa sus herramientas, hace el trabajo y
responde cuando termina. Eso puede tardar minutos, así que el campo de texto se
bloquea mientras trabaja y la respuesta aparece cuando llega. Cada respuesta
muestra lo que costó, en tokens y en pasos.

Las respuestas se muestran con el markdown ya aplicado —encabezados, tablas,
listas, citas y bloques de código—, porque así es como escribe un modelo. Tus
propios mensajes se ven tal como los escribiste. Un enlace sólo es un enlace
si apunta a http o https; cualquier otra cosa se queda como el texto que era.

La conversación se recuerda. Los últimos diez intercambios se le reenvían al
modelo en cada mensaje, así que el agente sabe de qué estabais hablando; por eso
mismo, un hilo largo cuesta más por mensaje que uno corto. **Borrar
conversación** empieza de cero.

Hablar con un agente **no** cuenta para su techo de ejecuciones al día: ese
techo existe para frenar una programación desatendida, no para frenarte a ti
escribiendo. Los techos por ejecución de tokens, pasos y tiempo sí se aplican.

Cada agente tiene su propia conversación, guardada en su propia carpeta home, y
ningún agente puede leer lo que le dijiste a otro.

La conversación no es sólo lo que escribiste tú. Cuando llega la hora de una de
las tarjetas del agente, la tarjeta se publica en ese mismo chat justo al
arrancar la ejecución, y la respuesta aparece debajo: así, abrir un agente
muestra todo lo que se le ha pedido, por ti o por otro agente, y lo que hizo con
ello. Ver [Cuándo se ejecuta una tarjeta](#cuándo-se-ejecuta-una-tarjeta).

### API Calls

El nombre del agente aparece encima de las pestañas Chat y API Calls. Por
defecto sólo se ve **Chat**. Para mostrar la otra pestaña, se abre la llave
inglesa del agente, se selecciona **Interfaz**, se activa **Mostrar la pestaña
API Calls** y se pulsa **Guardar**. La opción se guarda para ese agente en el
servidor. Al abrir o recargar un agente siempre se muestra Chat, aunque API
Calls esté activada.

**API Calls** muestra el JSON enviado: el prompt completo del agente, la
conversación, las definiciones de herramientas y los resultados de herramientas
incluidos en esa solicitud. La más reciente aparece desplegada; las demás se
pueden desplegar para consultarlas. Las nuevas llamadas aparecen durante la
ejecución, incluidos los intentos fallidos, los reintentos de los SDK y las
llamadas al modelo de respaldo. La sangría y los colores facilitan la lectura
sin convertir el contenido en chat ni redondear identificadores numéricos grandes.

Se conservan las últimas 100 solicitudes completas, por separado de la
conversación. Borrar Chat no las elimina. El registro empieza con esta versión;
no se reconstruyen solicitudes anteriores. No se guardan las cabeceras de autenticación.

## Configuración del agente

El encabezado muestra **Configuración del agente 001**, con el identificador
del agente seleccionado. **Ejecutar ahora** aparece sólo en la vista que
contiene Chat y API Calls. Para eliminar un agente, se abre **General → Eliminar
agente** y se confirma su nombre en el diálogo. La eliminación tiene una
sección propia debajo de Identidad.


El chat es lo que aparece al hacer clic en un agente. Todo lo demás —modelo,
herramientas, techos, system prompt, programación— está detrás de la **llave
inglesa** que hay a la derecha del cuadro del agente, en la barra lateral.

## Exportar un agente

La última pestaña de la configuración de un agente, **Exportar**, lo descarga
como un `.zip` que **+ → Importar desde un archivo .zip** puede instalar, en
esta instalación o en otra. Su configuración, su system prompt y sus horarios
van siempre. Cuatro cosas van sólo si las marcas, y cada casilla dice antes
qué añadiría:

| Opción | Qué añade |
|---|---|
| **Memoria** | Su `memory.md`, con cuántos caracteres tiene |
| **Proveedor y modelo** | Qué proveedor y qué modelo usa. Nunca la clave |
| **Documentos de la biblioteca** | Los originales de su biblioteca con su información (título, año...). Se vuelven a indexar donde se importan |
| **Archivos de su carpeta personal** | Sus scripts, su carpeta `samba` y lo demás que guarde en su home. Pueden contener cosas que no compartirías, así que la lista de archivos se muestra antes de descargar |

Algunas cosas no van nunca, marques lo que marques: claves de API, el token
propio del agente, credenciales de los canales, su chat, su registro de
ejecuciones, sus sesiones del navegador y los archivos ocultos de su carpeta
personal. De su crontab sólo viajan los horarios que lanzan al agente, no
otros comandos que alguien haya escrito ahí: un `.zip` que llevara comandos
los ejecutaría en la máquina donde se importe.

## Carpetas compartidas por Samba

Cada agente tiene una carpeta `samba/` en su home, compartida automáticamente
con el nombre de su usuario Linux. Por ejemplo, **agent-001** apunta únicamente
a `/opt/boa/agents/001/samba/`. Cambiar el nombre visible del agente en General
no cambia el recurso. El resto del home y la configuración protegida no se comparten.

1. Abrir la **llave inglesa → Samba** del agente.
2. Introducir una **nueva contraseña Samba** de al menos 8 caracteres, elegir los permisos y pulsar **Guardar**.
3. Abrir la dirección Windows o SMB de la pestaña —`\\servidor\agent-001` en Windows, `smb://servidor/agent-001` en Linux y macOS— e iniciar sesión con el usuario indicado y esa contraseña.

El recurso empieza activado, visible en la lista del servidor y con permisos
de lectura/escritura, sin invitados. Antes de la primera conexión autenticada
hay que establecer su contraseña en esta pestaña. Dejar el campo vacío en los
siguientes guardados conserva la contraseña existente. La credencial Samba es
independiente de la de Linux y no desbloquea el inicio de sesión del usuario Linux.

| Ajuste | Efecto |
|---|---|
| Compartir esta carpeta | Activa o desactiva el recurso sin borrar sus archivos |
| Autenticación | Usuario y contraseña del agente por defecto; invitados sólo si se selecciona expresamente |
| Permisos | Lectura sola o lectura/escritura por SMB; el agente puede seguir trabajando con sus archivos locales |
| Visibilidad y descripción | Aparición en la lista de recursos del servidor y descripción del recurso |
| Permisos de archivos/carpetas nuevos | Modos Unix en octal, inicialmente `0600` / `0700`; los existentes conservan sus permisos |

El nombre y la ruta son fijos. La carpeta sigue siendo privada para su usuario
Linux. Al guardar cambios de acceso, se cierran las conexiones de ese recurso
para aplicar los nuevos permisos al reconectar. Los recursos de otros agentes
siguen disponibles. La contraseña nunca se devuelve en la API ni se guarda en `info.json`.

`--update` crea las carpetas y los recursos Samba de los agentes existentes,
incluido `agent-000`. Al eliminar un
agente desaparecen su recurso y su cuenta Samba, además de su home.
`--backup` / `--restore` conservan los archivos, los ajustes, las contraseñas
Samba y las identidades de las cuentas. La restauración comprueba el modo de
puertos web guardado, también cuando se sirve directamente en el 443.

Samba usa TCP **445**, por separado del proxy web. En Docker hay que publicar
ese puerto expresamente. BoA usa su servicio `boa-samba`, con configuración y
base de contraseñas propias en `/opt/boa/samba/`, y no sustituye la
configuración de otro servidor Samba que ya estuviera instalado: si existe una
instalación Samba ajena a BoA, el instalador no la modifica y se niega a
sustituirla.

## Darle un modelo a un agente

En **LLMs**, elige un proveedor. La lista es corta a propósito: ofrece los
tres proveedores autoalojados, que no necesitan clave, y todos los de nube
cuya clave esté guardada en **Ajustes → Claves de API**. Un proveedor de
nube sin clave llevaría al agente hasta su primera ejecución para fallar
allí, así que no se ofrece. En cuanto guardas su clave, aparece.

Un agente que ya está configurado con un proveedor lo sigue viendo en la
lista aunque le borres la clave, marcado como *(sin clave configurada)*: si
no, el campo mostraría un proveedor que nadie eligió y lo guardaría en el
siguiente clic.

**En hardware tuyo.** Sin clave, y la caja de URL base es donde escucha tu propio servidor.

| Proveedor | Modelos listados | Modelo por defecto |
|---|---|---|
| `ollama` | 23 | `gpt-oss:20b` |
| `llamacpp` | 1 | `local-model` |
| `vllm` | 3 | escribe tú el modelo |

**Empresas que sirven los modelos que construyeron.**

| Proveedor | Modelos listados | Modelo por defecto |
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

**Hosts y enrutadores, que sirven modelos de otros.** Una sola clave llega a muchos modelos; el identificador del modelo dice a cuál.

| Proveedor | Modelos listados | Modelo por defecto |
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

Un proveedor necesita dos valores en la caja de la clave: **Cloudflare
Workers AI** construye su dirección a partir del identificador de cuenta, así
que su clave se escribe `account-id:api-token`, las dos mitades sacadas del
panel de Cloudflare. La caja de **Ajustes → Claves API** lo indica.

El campo del modelo sugiere los que sirve ese proveedor, y filtra la lista a medida que escribes, pero es una caja de texto normal: un modelo publicado esta mañana se escribe y ya está. Esas sugerencias salen de `/opt/boa/config/providers/<proveedor>.json`, que puedes editar en el servidor; una actualización nunca pisa un archivo que hayas cambiado.

Los proveedores autoalojados no necesitan nada más si corren en la misma
máquina.

La **URL base** sólo aparece con `ollama`, `llamacpp` y `vllm`, y es dónde
escucha tu propio servidor: por defecto trae el puerto habitual en esta
máquina, que es lo correcto cuando el modelo corre al lado de la aplicación.
Si eliges un proveedor de nube, el campo desaparece: esa dirección es fija, la
instalación ya la tiene, y lo único que podría hacer ahí una caja de texto es
permitir que una errata rompa un agente que funcionaba. El modelo de reserva
se comporta igual.

Para uno de nube, lo más simple es la pestaña **Claves de API** de Ajustes, que luego usan todos los agentes de ese proveedor. Para darle a este agente en concreto una clave distinta, escríbela en su propio home, como root:

```bash
mkdir -p /opt/boa/agents/001/keys
echo "sk-..." > /opt/boa/agents/001/keys/anthropic.key
chown -R agent-001:agent-001 /opt/boa/agents/001/keys
chmod 700 /opt/boa/agents/001/keys
chmod 600 /opt/boa/agents/001/keys/anthropic.key
```

El nombre del archivo es el nombre del proveedor. Cada agente lee sólo su
propia clave, así que un agente no puede gastar el presupuesto de otro.

### Claves de API

Ajustes tiene una pestaña **Claves de API**: una clave por proveedor de nube,
compartida por todos los agentes que lo usen. Los proveedores autoalojados no
aparecen, porque no necesitan ninguna.

La clave se guarda en `/opt/boa/config/apikeys/<proveedor>.key`. La carpeta es
`0700` y los archivos `0600`, propiedad del usuario de la webapp, así que
ningún agente puede leer ninguno: ni la clave de otro proveedor ni la suya
propia. Cuando un agente se ejecuta, la API de agentes le entrega la clave
**del proveedor con el que ese agente está configurado, y de ningún otro**: un
agente con Ollama no puede pedir la clave de Anthropic.

Las instalaciones anteriores al cambio de nombre tienen sus claves en
`/opt/boa/config/keys/`; `--update` las mueve y elimina la carpeta antigua.

Conviene ser claro sobre qué protege esto y qué no. Un agente que use
legítimamente un proveedor de pago tiene su clave mientras se ejecuta: la
necesita para hacer la llamada, y un agente con `bash.run` podría imprimirla.
Lo que evita el almacén compartido es que un agente recoja las claves de
proveedores que no usa, y mantiene todas las claves fuera de las carpetas home
de los agentes, donde una copia de seguridad descuidada las expondría todas a
la vez.

Para facturar un agente concreto a otra cuenta, pon una clave en el home de ese
agente, en `keys/<proveedor>.key`. Esa gana sobre la compartida.

## Escribir un prompt de sistema

El prompt de sistema es lo que el agente es. Se guarda como `system-prompt.md`
en el home del agente y se edita en la interfaz.

Lo que funciona:

- **Di para qué sirve el agente**, en una o dos frases.
- **Di qué significa «terminado»**. Un agente sin definición de terminado o
  para demasiado pronto o no para nunca.
- **Di qué hacer cuando se atasque.** Sin esto, los modelos se inventan una
  forma de rodear el obstáculo. Basta con «si no puedes hacerlo, dilo en el
  tablero y para».
- **Dile que lea el tablero primero.** Es la única memoria que tiene entre
  ejecuciones.

Lo que no funciona: decirle que no use una herramienta. Si no quieres que use
una herramienta, no se la des: el prompt es una sugerencia, la lista de
herramientas se impone.

## Qué recuerda un agente

Cada agente tiene un `memory.md` en su carpeta home, y ese archivo es lo único
que se lleva de una ejecución a la siguiente. Escribe en él con `memory.append`
cuando aprende algo que merece la pena guardar, y lo ordena con
`memory.replace`.

El archivo entero se carga al empezar cada ejecución, que es lo que lo hace
útil y también lo que lo hace costar: cada carácter se paga en cada llamada al
modelo. En **Ajustes del agente → Memoria → Límite de memoria (caracteres)**,
elige un límite entre 1.000 y 1.000.000 de caracteres. El valor por defecto
es 8.000, también para los agentes existentes. Se avisa al agente para que
ordene su memoria cuando supera el 75 % del límite elegido.

El contador muestra los caracteres usados y el límite, incluidos espacios y
saltos de línea. Puedes aumentar el límite y pegar una memoria mayor en el mismo
guardado. Si el texto supera el límite, no se guarda ningún cambio de esa
petición de ajustes: acorta el texto o aumenta el límite. La memoria anterior se
conserva y los nuevos guardados nunca añaden `[truncated]`. El texto descartado
anteriormente debe pegarse otra vez desde el original. La memoria completa
debe seguir cabiendo en el contexto del modelo junto al prompt, la conversación
y las herramientas.

Cosas que merece la pena guardar: dónde está algo, qué comando resultó ser el
bueno, qué prefieres tú. No el diario de lo que hizo: para eso está el tablero.

Puedes leerla y corregirla en **Memoria**, dentro de la configuración del
agente. Un dato equivocado sobre el que el agente siga actuando merece
arreglarse a mano.

## Bibliotecas documentales locales (RAG)

Cada agente tiene su biblioteca en `/opt/boa/agents/<id>/rag/`. Admite PDF, EPUB,
TXT UTF-8 y Markdown. El instalador prepara el modelo local de vectorización
—EmbeddingGemma 300M Q8 (unos 318 MiB), salvo que se haya elegido otro (véase
[Elegir el modelo de vectorización](#elegir-el-modelo-de-vectorización))—, su
motor llama.cpp y el OCR. La extracción, el OCR y los
vectores de documentos y consultas se calculan en el servidor. Los fragmentos
recuperados se envían al proveedor elegido para responder, también si es un
proveedor en la nube. No existe un proveedor externo para vectorizar.
Instalación, actualización, importación, OCR y copia/restauración comprobados
en Debian 13 y Alpine 3.24, incluido el arranque de servicios tras reiniciar.

1. En **Ajustes → RAG**, comprueba que el motor esté preparado.
2. En la pestaña **RAG** del agente, activa la consulta de
   documentos y guarda los ajustes del agente. La plantilla **rag-consultant**
   llega con la consulta ya activada.
3. Selecciona archivos y pulsa **Subir documentos**. Los archivos grandes se
   transfieren por bloques. También puedes copiar archivos completos a
   `rag/inbox/` y pulsar **Importar archivos de rag/inbox**. Los originales
   importados pasan al almacén gestionado de documentos.
4. Espera al estado **Preparado**. La extracción y vectorización se ejecutan en
   segundo plano; los documentos preparados siguen disponibles. Se muestran
   progreso y errores por documento.
5. Prueba una consulta con **Buscar en la biblioteca** o pregunta al agente en
   su chat habitual. Las citas enlazan a la página del PDF o al EPUB/documento.

Los errores al importar desde `rag/inbox/` aparecen sobre la lista de documentos.
Los originales que fallen permanecen en la carpeta para corregirlos. La indexación
procesa lotes limitados para evitar pausas innecesarias entre libros pequeños.

**Información del documento** permite editar, en este orden, año de
publicación, título, subtítulo, autor/es, versión, idioma y etiquetas. El año
es opcional y admite hasta cuatro cifras. El subtítulo, si lo hay, aparece en
la lista de documentos justo debajo del título. El subtítulo, el año, el autor,
la versión y el idioma viajan con cada fragmento que recupera el agente, para
que pueda distinguir documentos con el mismo título, fechar y atribuir lo que
cita y distinguir ediciones que se contradicen. Al sustituir un archivo, la
versión anterior
sigue disponible hasta que termine la nueva indexación. Si el motor local de
vectores se para mientras se indexa un documento (una actualización, un
reinicio), el documento vuelve a **En cola** con el aviso «Local embeddings are
unavailable» y, cuando el motor vuelve a responder, sigue donde lo dejó; no
hace falta reindexarlo. Reindexar procesa otra vez el documento;
Cancelar detiene el trabajo pendiente; Eliminar lo retira de las búsquedas.
Los filtros de idioma y versión utilizan los metadatos introducidos. En EPUB se
citan capítulos, sin inventar números de página. Los PDF escaneados necesitan
los idiomas de OCR instalados; inglés y español vienen por defecto (`eng+spa`).
Un archivo cifrado, dañado o sin texto extraíble muestra un error.

**Modo de respuesta** decide hasta dónde puede ir el agente más allá de sus
documentos; la línea bajo la lista explica qué hace el modo elegido.

- **Documentos y conocimientos generales**: el agente puede usar ambos, por
  separado.
- **Se requiere respaldo documental**: el agente tiene que buscar en la
  biblioteca antes de responder; una respuesta dada sin buscar se le devuelve
  al modelo una vez. Si en la ejecución no se recuperó ningún fragmento, recibes la
  frase fija «La biblioteca de documentos no contiene información suficiente
  para responder a esta pregunta» en lugar de lo que escribiera el modelo.
- **Sólo documentos (verificado)**: como el anterior, y además cada párrafo y
  cada elemento de lista de la respuesta tiene que citar un fragmento recuperado
  en esa ejecución. Se revisa párrafo a párrafo: sin cita, con una cita a un
  fragmento que no se recuperó, o con un significado lejano al del fragmento que
  cita (medido con el motor local de vectores), se le devuelve la respuesta al
  modelo una vez, con la lista de esos párrafos. Lo que siga sin respaldo después se retira,
  y una última línea dice cuántos párrafos se quitaron. Si no queda nada
  respaldado, llega la frase fija. Si el motor no está disponible para hacer la
  comprobación, la respuesta se retiene en vez de mostrarse sin revisar.

Lo que el modo verificado no puede hacer es demostrar que un párrafo citado
dice exactamente lo mismo que su fragmento. En nuestras mediciones, un párrafo
que contradice su fragmento, o que añade algo del mismo tema, puntúa como uno
fiel; lo que sí detecta es un párrafo que cita un fragmento de otra cosa y un
párrafo sin ninguna fuente. Tampoco acierta siempre en lo que detecta: en
nuestras pruebas retiró unos 6 de cada 100 párrafos fieles —sobre todo
elementos de lista y resúmenes de una línea, que le dan poco que comparar— y
dejó pasar menos de 1 de cada 100 citas a un fragmento de otro tema. Un ejemplo
de código se juzga junto con la frase que lo presenta. Comprueba el pasaje citado
cuando la precisión importe. Las frases fijas salen en el idioma elegido en **Ajustes → Agentes →
Idioma en el que responden los agentes**, y en inglés si no hay ninguno. Las
citas se resuelven sólo a partir de los identificadores recuperados.

Valores iniciales por agente: 128 MiB por archivo, 2.048 MiB de originales,
200.000 fragmentos, 8 resultados y hasta 16.000 caracteres recuperados por
ejecución. Un cálculo conservador por bytes limita también el espacio disponible
junto al prompt y el historial. La **Similitud mínima** inicial es la medida
para el modelo de vectorización en uso —0,20 con EmbeddingGemma, 0,35 con
Qwen3-Embedding—, y la línea bajo el campo dice cuál es. Es una puntuación de
búsqueda, no una probabilidad, y cada modelo tiene su propia escala. Puede aumentarse para restringir
resultados semánticos demasiado amplios. También participa la búsqueda literal.
La API permite configurar la cuota de fragmentos y su tamaño en tokens.

Los ajustes generales controlan los hilos, los trabajos simultáneos y los
idiomas predeterminados de OCR. **Trabajos de indexación simultáneos** es
cuántas bibliotecas de agentes se indexan a la vez (un trabajo por agente, con
sus documentos uno detrás de otro); cada trabajo puede usar hasta 4GB de RAM,
como recuerda la propia etiqueta. No acelera la biblioteca de un solo agente,
porque el motor de vectores atiende una petición a la vez: para vectorizar más
rápido, sube **Hilos de CPU para vectorizar**. El modelo es compartido; las
bibliotecas y permisos son por agente. Tras un reinicio se conservan los documentos terminados y se
reutilizan fragmentos de trabajos interrumpidos. Una reindexación fallida
conserva la última versión publicada. Sólo instalar el modelo requiere
descargarlo; la consulta normal puede funcionar sin Internet. Si falla el motor
local, se informa del fallo y nunca se cambia a un servicio externo de
vectorización.

`boa-embeddings` sirve el modelo mediante un socket Unix y `boa-rag` programa la
cola. Ambos tienen unidades systemd y OpenRC y aparecen en los ajustes del
sistema. Las copias incluyen originales, metadatos e instantáneas consistentes
de SQLite y los índices vectoriales. Incluyen los ajustes del motor, y con
ellos el modelo de vectorización elegido; el binario y los pesos no. Al
restaurar se descarga el modelo elegido si la máquina no lo tiene y, si esa
descarga falla, se avisa y se sigue: el modelo se puede descargar, o elegir
otro, en **Ajustes → RAG**. Las subidas incompletas se cancelan al restaurar
una copia. Una actualización normal conserva las bibliotecas.

### Elegir el modelo de vectorización

El modelo de vectorización convierte cada fragmento y cada pregunta en los
números con los que se busca en la biblioteca. **Ajustes → RAG → Modelo de
vectorización** ofrece dos, y el mismo sirve a todos los agentes:

| | EmbeddingGemma 300M (Q8) | Qwen3-Embedding 0.6B (Q8) |
|---|---|---|
| Descarga | 318 MiB | 610 MiB |
| Memoria del motor en funcionamiento | unos 600 MB | unos 1,1 GB |
| Tiempo de indexación, mismo procesador | 1× | unas 4× |
| Licencia | Gemma Terms of Use | Apache 2.0 |

EmbeddingGemma es el predeterminado y sirve para cualquier máquina.
Qwen3-Embedding es para una máquina con procesador y memoria de sobra: con los
libros de Python en español de la biblioteca de pruebas separó más las preguntas
sobre los libros (0,51-0,79) de las que no tenían nada que ver (0,21 como
mucho) que EmbeddingGemma (0,35-0,67 frente a 0,17), y también los párrafos que
reformulan un fragmento de los que hablan de otra cosa. En la máquina de
pruebas, con dos procesadores, tardó 2,2 segundos por fragmento, frente a 0,5.

Para cambiarlo:

1. Elige el modelo en la lista. Debajo verás su tamaño, su memoria, su
   velocidad y su licencia, y si ya está descargado.
2. Si no lo está, pulsa **Descargar modelo** y espera a que la barra termine.
   La descarga se comprueba contra su SHA-256 publicado antes de usarla.
3. Pulsa **Guardar** y confirma. El motor se reinicia con el nuevo modelo; la
   línea de arriba dice «El motor está cargando este modelo» durante unos
   segundos y después **Preparado**.

Lo que pone en marcha un cambio:

- Todos los documentos de todos los agentes se vuelven a indexar, una
  biblioteca por trabajo de indexación, como si se hubieran subido de nuevo. En
  una biblioteca grande eso tarda horas.
- Hasta que le toca, un documento sigue en la biblioteca y se encuentra por las
  palabras de la pregunta, no por su significado. Una búsqueda durante ese
  tiempo le dice al agente cuántos documentos están esperando, para que no tome
  un fragmento que falta por algo que la biblioteca no trata.
- La **Similitud mínima** de cada agente que conservaba el valor recomendado del
  modelo anterior pasa al del nuevo. Un agente en el que pusiste otro valor lo
  conserva.
- El modo verificado compara párrafos y fragmentos con el modelo en uso, contra
  un umbral medido para él (0,36 con EmbeddingGemma, 0,44 con Qwen3-Embedding).

Los pesos del modelo anterior se quedan en el disco, así que volver a él no
necesita descarga, pero sí vuelve a indexar cada documento que se indexó con el
otro.

## Elegir herramientas

En **Herramientas**, marca las que este agente puede usar. Una herramienta sin
marcar no se le muestra al modelo, y el servidor la rechazaría aunque la
pidiera: esa comprobación se hace en el servidor, no en el prompt.

Éstas son las herramientas que vienen incluidas:

| Herramienta | Qué puede hacer un agente con ella |
|---|---|
| `bash.run` | Ejecutar comandos de shell como su propio usuario sin privilegios |
| `kanban.add_card` | Poner una tarea en el tablero compartido |
| `kanban.assign_card` | Pasarle una de sus propias tarjetas a otro agente |
| `kanban.move_card` | Mover una de sus propias tarjetas entre columnas |
| `kanban.delete_card` | Borrar una de sus propias tarjetas |
| `kanban.list_cards` | Leer el tablero: sus propias tarjetas, o todas en el caso de **manager** |
| `channel.write` | Enviar un mensaje a un canal configurado |
| `web.fetch` | Leer una página web pública |
| `rss.fetch` | Leer un feed RSS o Atom como una lista de entradas |
| `memory.append` | Anotar algo para su yo futuro |
| `memory.replace` | Ordenar lo que recuerda |
| `skill.read` | Leer un procedimiento que se le ha dado |
| `script.write` | Escribir un script en su propia carpeta `scripts/` |
| `script.list` | Listar los scripts que ha escrito |
| `script.delete` | Borrar uno de sus scripts, junto con las líneas de cron que lo ejecutaban |
| `cron.add` | Ejecutar uno de sus scripts de forma programada, en su propio crontab |
| `cron.list` | Leer su propio crontab |
| `cron.remove` | Dejar de ejecutar uno de sus scripts |
| `mail.read` | Leer mensajes del buzón configurado |
| `mail.move` | Archivar un mensaje en otra carpeta de la misma cuenta |
| `mail.delete` | Mandar un mensaje a la papelera de la cuenta |
| `mail.forward` | Reenviar un mensaje a una dirección que hayas permitido |
| `rag.search` | Buscar en su propia biblioteca documental |
| `rag.read` | Leer un fragmento que devolvió una búsqueda |
| `rag.list` | Listar los documentos de su biblioteca |
| `browser.open` | Abrir una página en su propio navegador, conservando las cookies |
| `browser.read` | Leer la página abierta, o sus enlaces |
| `browser.click` | Pulsar un enlace o un botón de ella |
| `browser.type` | Rellenar un campo, enviándolo si hace falta |
| `browser.screenshot` | Guardar una imagen de ella para ti |
| `image.send` | Adjuntar un PNG al chat web y a la respuesta de Telegram cuando la conversación empezó allí. La imagen ocupa todo el ancho interior del mensaje web |

Cada familia tiene su propia caja, con la cuenta de cuántas de esa familia
tiene este agente: «¿puede este agente leer el buzón?» es UNA decisión, y se
dibuja como UNA caja. El interruptor que enciende el tablero kanban para un
agente está al final de la caja **Kanban**, debajo de las herramientas a las
que afecta.

- **`bash.run`** — comandos de shell como el usuario de ese agente. No tiene
  root ni puede conseguirlo. Dásela cuando el agente tenga trabajo real que
  hacer en la máquina.
- **`kanban.*`** — el tablero compartido. Dale al menos `list_cards` y
  `add_card` a cualquier agente que deba ser visible.
- **`channel.write`** — mensajes para ti. Marca también los canales en la pestaña **Canales**.
- **`web.fetch`** — sólo páginas públicas. Las direcciones privadas y de
  loopback se rechazan.
- **`rss.fetch`** — un feed RSS o Atom, como lista de entradas en vez de como
  documento XML. Mucho más barato que traerse el mismo feed con `web.fetch`, y
  le ahorra al agente el trabajo de parsearlo. Las dos están en **Internet**.
- **`script.*` y `cron.*`** — en **Automatización**. El agente escribe un
  script en su propia carpeta `scripts/` y lo programa en su propio crontab,
  para trabajo recurrente que no necesita que piense: el script se ejecuta
  solo, no cuesta tokens, y el agente lee los resultados en su siguiente
  ejecución. Sólo puede programar sus propios scripts, nada más frecuente que
  cada 5 minutos, y nunca puede tocar la línea que lo despierta a él.

Un agente puede hacer muchas cosas dentro de su propio home, y ninguna fuera de
él. No puede ni ver que otro agente existe, mucho menos leer su prompt: la
carpeta de agentes se puede atravesar pero no listar, y cada home es privado de
su propio usuario de Linux, así que eso lo rechaza el kernel y no una
comprobación en Python.

Tampoco puede reescribir **lo que él es**. Las herramientas que tiene
concedidas, sus techos de gasto, su prompt de sistema y su token de API viven
en un cajón dentro de su home que pertenece a root: el agente los lee y no
puede cambiarlos. Los cambias tú; él no. Lo único suyo que puede editar es su
memoria.
- **`mail.*`** — el buzón configurado en **Ajustes → Correo**. Mira más abajo.
- **`skill.read`** — los procedimientos escritos que estén marcados en el panel
  **Habilidades**. Hacen falta las dos cosas: la herramienta aquí y al menos una
  habilidad allí.

### Las herramientas de correo

Son cuatro, y necesitan un buzón IMAP configurado en **Ajustes → Correo**. El
agente nunca ve esa contraseña: dice qué quiere hacer y lo hace la API de
agentes, que es quien la tiene.

| Herramienta | Qué hace |
|---|---|
| `mail.read` | Lee mensajes. **No marca nada como leído**, así que tu contador de no leídos sigue significando lo que significaba. |
| `mail.move` | Archiva un mensaje en otra carpeta de la misma cuenta. La carpeta tiene que existir. |
| `mail.delete` | Manda un mensaje a la papelera de la cuenta, si la tiene. |
| `mail.forward` | Reenvía un mensaje, **sólo a las direcciones que hayas listado**. |

Esta última es la importante. Una bandeja de entrada es la única entrada de un
agente en la que puede escribir cualquiera del mundo, así que `mail.forward` se
comprueba contra tu lista en el servidor, en cada reenvío: no lo hace el
agente, ni una frase escrita en su prompt. Con la lista vacía, el reenvío se
rechaza del todo.

Dale sólo `mail.read` a un agente que únicamente tenga que vigilar. Añade
`mail.move` para archivar, y piénsatelo dos veces antes de dar `mail.delete` y
`mail.forward`.

La casilla de **kanban** del final desactiva el tablero por completo para ese
agente. Sin marcar, no recibe ninguna herramienta de kanban y deja de añadir
tarjetas; es el interruptor para un agente cuyo trabajo no pinta nada en el
tablero.

## Darle una habilidad a un agente

Una habilidad es un procedimiento escrito: cómo se hace aquí un trabajo, paso a
paso. No viene ninguna incluida: una habilidad va de ESTA máquina —estos
equipos, esta copia de seguridad, este certificado—, así que una genérica sería
un procedimiento que no sigue nadie. Las tuyas las escribes en el servidor, como
root:

```bash
mkdir -p /opt/boa/skills/BackupVerification
nano /opt/boa/skills/BackupVerification/SKILL.md
chown -R root:root /opt/boa/skills
chmod 00755 /opt/boa/skills/BackupVerification
chmod 0644 /opt/boa/skills/BackupVerification/SKILL.md
```

El archivo empieza con un nombre y una descripción de una línea entre dos
rayas `---`, y el resto es el procedimiento:

```markdown
---
name: BackupVerification
description: Cómo comprobar que las copias de anoche se hicieron de verdad.
---

1. Leer /var/log/backup.log ...
```

Cada carpeta dentro de `/opt/boa/skills/` aparece entonces como una casilla en
el panel **Habilidades** del agente. Marca una, dale al agente la herramienta
`skill.read` en **Herramientas** y pulsa **Guardar**. Desde su siguiente ejecución el agente sabe que ese
procedimiento existe y puede leerlo cuando le toque ese trabajo.

### Para qué, si ya está el prompt de sistema

Por tres razones, y la tercera es la que importa:

- **El prompt es para lo que sirve un agente; una habilidad es cómo se hace un
  trabajo.** Seis agentes pueden compartir un procedimiento sin que haya seis
  copias que se queden anticuadas por separado.
- **Una habilidad puede ser tan larga como necesite.** Un prompt de sistema se
  paga en cada llamada de cada ejecución, así que tiene que ser corto. Una
  habilidad se paga una vez, en la ejecución que la lee.
- **Lo que un agente aprende por su cuenta muere con él.** Su memoria vive
  dentro de una carpeta que ningún otro agente puede abrir. Una habilidad es el
  sitio donde poner lo que quieres que sepa también el siguiente agente.

### Cómo se escribe una

No hay editor para esto en la interfaz, y es a propósito: lo que dice una
habilidad entra directamente en el razonamiento de un agente que se ejecuta a
las cuatro de la mañana sin nadie mirando, así que pertenece a root, igual que
las herramientas. Se escriben en el servidor:

```bash
mkdir -p /opt/boa/skills/DatabaseBackup
nano /opt/boa/skills/DatabaseBackup/SKILL.md
```

El archivo empieza con una cabecera de dos líneas y luego dice lo que tenga que
decir:

```markdown
---
name: DatabaseBackup
description: Cómo se hace el volcado nocturno y dónde va a parar.
---

# Copia de la base de datos

1. Vuelca con `mysqldump --single-transaction`, nunca bloqueando las tablas.
2. Escríbelo en /srv/backups/, nunca en /tmp.
...
```

La `description` es la línea que más importa. Es la única parte que paga cada
ejecución, y es sobre lo que el agente decide cuando está eligiendo si leer el
resto. «Cómo se hace el volcado nocturno y dónde va a parar» le dice cuándo
aplica; «Cosas de la base de datos» no.

Recarga la página del agente y la habilidad estará en la lista.

Una actualización nunca toca `/opt/boa/skills/`: lo que escribas ahí sigue
siendo tuyo. La interfaz web decide qué agente recibe cada habilidad; no las
edita.

### Una habilidad puede traer sus propios archivos

Todo lo demás que haya en la carpeta viaja con ella:

```
/opt/boa/skills/DatabaseBackup/
  SKILL.md
  dump.sh
  exclude-tables.txt
```

Los agentes pueden leerlos y ejecutarlos, así que el procedimiento puede decir
«ejecuta `dump.sh` de esta carpeta» en vez de detallar cuarenta líneas de shell.
`skill.read` le dice al agente qué archivos hay y dónde están.

### Lo que cuesta

Al prompt sólo van el nombre y la descripción de cada habilidad, unas dos líneas
por habilidad. El cuerpo se carga con `skill.read`, una vez, por un agente que
ha decidido que lo necesita, y sólo entonces. Darle cinco habilidades a un
agente le cuesta un par de cientos de tokens por ejecución, no diez mil, que es
por lo que puedes darle cinco sin pensar en la factura.

### Si borras una habilidad que están usando varios agentes

No se rompe nada, y ningún agente se queda prometiendo algo que no puede
cumplir:

- **Desaparece del prompt** de todos los agentes que la tenían, en su siguiente
  ejecución. A un agente nunca se le habla de un procedimiento que no puede
  leer.
- **Desaparece del panel Habilidades**, así que nadie puede volver a marcarla.
- El nombre **sigue en el `info.json` del agente** hasta que algo lo reescriba,
  así que devolver la carpeta a su sitio restaura la habilidad sin hacer nada
  más.
- Si el agente la pide igualmente —puede recordar el nombre de una ejecución
  anterior—, se le dice que la habilidad está en su lista y ya no está
  instalada, y que no se invente lo que decía.

Una cosa que conviene saber: **pulsar Guardar en ese agente mientras falta la
habilidad la quita de la lista definitivamente.** La interfaz sólo guarda las
habilidades que existen, que es lo que impide que una borrada se quede ahí para
siempre. Devuelve la carpeta a su sitio antes de guardar el agente, o vuelve a
marcar la habilidad después.

## Darle un navegador a un agente

`web.fetch` lee una página pública y nada más: sin iniciar sesión, sin
formularios, sin botones. Si un agente necesita *usar* un sitio en vez de
leerlo, necesita un navegador.

Viene instalado: el instalador lo pregunta una vez, y la respuesta por defecto
es que sí. Son unos 600 MB de Chromium, así que una máquina con poco disco
puede decir que no, y cambiar de idea después en cualquier dirección:

```bash
./install-update-reinstall-debian.sh --update --browser no    # dejarlo fuera
./install-update-reinstall-debian.sh --update --browser yes   # volver a ponerlo
```

La respuesta se recuerda, igual que con los puertos. Después, marca las
herramientas del navegador en el panel **Herramientas** del agente:

Nada de esto vale en Alpine: allí no hay navegador en absoluto, porque
Playwright no publica ninguna versión para musl. Las herramientas siguen en la
lista y lo dicen cuando un agente llama a alguna.

| Herramienta | Qué puede hacer el agente |
|---|---|
| `browser.open` | Ir a una página. Las cookies se conservan |
| `browser.read` | Volver a leer la página abierta, una parte de ella, o sus enlaces |
| `browser.click` | Pulsar un enlace o un botón, por su texto visible o por un selector |
| `browser.type` | Rellenar un campo, pulsando Intro si hace falta |
| `browser.screenshot` | Guardar un PNG en su propia carpeta de descargas |
| `image.send` | Adjuntar un PNG a la respuesta en el chat web y Telegram |


`browser.screenshot` guarda un PNG en el servidor. Para mostrarlo en el chat,
el agente llama después a `image.send` con esa ruta. Activa **image.send** en
**Configuración del agente → Herramientas → Imágenes** y guarda. Los agentes
nuevos creados desde **web-navigator** ya la incluyen; los existentes conservan
sus permisos actuales.

La imagen ocupa todo el ancho interior del mensaje en el chat web, conserva
sus proporciones y muestra su altura completa. También se puede abrir a tamaño completo.
Si la conversación empezó por Telegram, también se envía allí. Las capturas
muy largas o grandes se entregan como documentos PNG. Si falla una subida, se
reintenta la parte pendiente sin repetir el texto ni las imágenes ya entregadas.

Sólo se aceptan PNG de la carpeta personal del agente, de hasta 50 MiB y con
un máximo de 16 por respuesta. Los adjuntos son privados y requieren iniciar
sesión para verlos. Puedes enviar una captura existente pidiéndole al agente
que use `image.send` con la ruta donde la guardó.

### Las sesiones de cada agente son suyas

El navegador en sí es una única copia, en `/opt/boa/playwright/`, propiedad de
root y de sólo lectura para todos los demás. Lo que **no** se comparte es el
perfil:

```
/opt/boa/agents/001/browser/profile/     agent-001, 0700
/opt/boa/agents/002/browser/profile/     agent-002, 0700
```

Un agente que inicia sesión en un sitio sigue dentro **en su siguiente
ejecución**, porque las cookies están en su propio disco. Y ningún otro agente
queda dentro, porque esa carpeta es 0700 y pertenece a su usuario de Linux: se
niega el kernel, no hay ninguna comprobación en Python que se pueda equivocar.
Esa separación es justo lo que un producto alojado no puede ofrecer cuando
todos sus agentes comparten una máquina.

Las cookies de sesión siguen terminando al cerrar el navegador, aquí como en
cualquier otro. Lo que un sitio marca para que persista, persiste.

### Lo que no va a hacer

- **Nada de direcciones privadas.** `browser.open` rechaza `192.168.*`, `127.*`
  y las demás, exactamente igual que `web.fetch`. A un agente que acaba de leer
  una página hostil no se le puede convencer de que abra tu router, y un
  navegador con sesión sería mucho mejor herramienta para eso que un fetch.
- **Nada de pantalla.** Va sin interfaz gráfica. `browser.screenshot` es tu
  forma de ver lo que vio; el agente no puede mirar la imagen.
- **Nada sin las herramientas.** Como con todo lo demás, una herramienta que no
  se le ha dado al agente es una herramienta que no puede llamar, y esa
  comprobación se hace en el servidor.

Si el navegador no se instaló nunca, las herramientas siguen apareciendo en la
lista y responden con el comando que hay que ejecutar. Ni desaparecen ni fallan
en silencio.

## Techos de gasto

Cuatro techos, por agente, y cada ejecución se detiene en el primero que
alcance:

| Techo | Por defecto | Contra qué protege |
|---|---|---|
| Tokens por ejecución | 16384 | Una sola conversación cara |
| Pasos por ejecución | 25 | Un bucle que llama a herramientas sin parar |
| Segundos por ejecución | 300 | Una ejecución que se cuelga |
| Ejecuciones al día | 48 | Una línea de cron demasiado entusiasta |

Esto no es paranoia. Un agente que despierta cada hora contra una API de pago,
sin techo y sin nadie mirando, es una factura que crece mientras duermes.

Súbelos cuando hayas visto lo que el agente gasta de verdad, en su panel de
**Historial**.

### El modelo secundario

En **LLMs**, debajo del principal, hay un segundo proveedor y modelo. Sólo se
usa cuando el principal **falla** —sin clave, sin respuesta, o un modelo que no
existe— y la ejecución continúa con él desde ese mismo paso, reenviándole lo
ocurrido hasta entonces, así que el trabajo ya hecho no se tira.

Se intenta UNA vez por ejecución. Si el secundario también falla, la ejecución
falla: ir probando uno tras otro indefinidamente quemaría los techos durante
una caída y seguiría sin dar nada. El cambio queda escrito en el historial del
agente, porque una ejecución que responde con otro modelo, y que factura a otra
cuenta, tiene que decirlo.

Dejar el proveedor secundario en «ninguno» es lo que viene marcado, y significa
que un fallo detiene la ejecución.

Si eliges como secundario el **mismo proveedor** que el principal, el campo del
modelo se rellena con un modelo *distinto* del catálogo de ese proveedor, no
con el mismo otra vez. Mismo proveedor y mismo modelo no puede responder nada
que el principal no pudiera: fallaría exactamente por el mismo motivo, siempre.
Si aun así escribes la misma pareja a mano, una línea debajo del campo te lo
dice: es tu agente, así que es un aviso y no una prohibición.


Cuando una ejecución se para en su techo de tokens o de pasos, se le pide al
agente una vez más —sin herramientas y con un presupuesto pequeño aparte— la
respuesta que iba a dar, para que una ejecución que gastó todo su presupuesto
recogiendo datos no termine en «voy a revisar el sistema». El chat lo avisa
debajo de la respuesta, porque esa respuesta puede estar incompleta. El techo
de tiempo no tiene esa llamada: la ejecución ya va tarde.

Esa llamada de cierre reenvía toda la conversación, así que en una ejecución
larga con muchas herramientas no sale barata: una ejecución cortada en un techo
de 12 000 tokens acabó midiendo 24 901. El techo de tokens es, por tanto, un
presupuesto para el trabajo, no un máximo estricto de la ejecución. Eso sólo se
gasta si se llega a un techo.

### Lo que el kernel hace cumplir además

Los cuatro techos los hace cumplir la propia ejecución. Otros dos los hace
cumplir el kernel, así que valen cuando la ejecución es lo que ha fallado:
ningún agente puede tener más de 1024 procesos e hilos a la vez, de modo que
una orden que haga fork sin parar se detiene ahí y no en la máquina; y en
Debian cada ejecución vive en un scope propio de systemd con 2 GiB de
memoria, que además termina con lo que la ejecución dejara corriendo en
segundo plano cuando acaba. Una ejecución a la que el límite de memoria mata
aparece en su Historial como fallida y en su chat como un error, como
cualquier otra. Un navegador ya son unos cientos de hilos, y por eso el
número no es menor.

## Programar un agente

En **Cron**, escribe el crontab del agente. Es el crontab propio del
agente, que pertenece a su usuario de Linux y lo ejecuta él, exactamente como
si hubieras hecho `crontab -e` con ese usuario.

Cada hora:

```
0 * * * * /opt/boa/venv/bin/python3 /opt/boa/webapp/backend/core/runner.py --agent-id 001
```

Los días laborables a las 08:00:

```
0 8 * * 1-5 /opt/boa/venv/bin/python3 /opt/boa/webapp/backend/core/runner.py --agent-id 001
```

La interfaz muestra la línea exacta del agente que estás editando, para que la
copies y sólo cambies la hora.

Déjalo vacío para quitar la programación. Desmarca **Activado** para conservar
la programación pero que el agente la ignore.

Si usas un proveedor de pago cuyo precio varía según la hora —DeepSeek cobra
varias veces más en horas pico—, esa decisión se toma aquí.

## El tablero kanban

La página tiene dos pestañas: **Tablero**, que son las tres columnas, y
**Crear tarjeta**, que es el formulario. Cuál está abierta va en la URL, así
que recargar y el botón «atrás» la conservan. Al guardar una tarjeta se vuelve
al tablero.

Tres columnas: **por hacer**, **haciendo** y **hechas**.

El tablero es lo que los agentes usan para dejarse trabajo unos a otros y lo
que tú usas para ver qué ha pasado de verdad. Cada tarjeta lleva su historial:
quién la creó, quién la movió, cuándo y por qué.

Una tarjeta tiene un título y una caja **Qué hay que hacer**. El título la
nombra; en la caja van las instrucciones, y el agente lee las dos cosas. Una
tarjeta asignada a un agente con la caja vacía lo deja adivinando, que es la
razón habitual de que un agente no haga nada con una tarjeta que le han dado.

La otra razón es que el agente no vea el tablero. Un agente lo lee llamando a
`kanban.list_cards` o no lo lee: el tablero nunca se le mete en el prompt, así
que un agente sin esa herramienta no se entera nunca de que la tarjeta existe.
**Asignar a** lo avisa al elegir un agente así. Es un aviso, no un bloqueo: la
tarjeta se crea igual, y basta con marcarle la herramienta en su pestaña
**Herramientas**.

Una tarjeta del tablero muestra quién la creó, a quién está asignada, cuándo
se creó, las dos primeras líneas de su título, las tres primeras de lo que hay
que hacer y **cuándo se ejecuta**. El texto completo de un título o un cuerpo
recortado está en su texto emergente.

Esa última línea es la que merece la pena leer. Una tarjeta sin hora NO va
tarde: no se despierta a nadie por ella, y su agente la encontrará en su
próxima ejecución programada. **Mover a** es cómo mueves una tarjeta a mano:
este tablero no tiene arrastrar y soltar.

Tú puedes añadir, mover y borrar cualquier tarjeta. **Un agente sólo ve y
cambia las suyas**: una tarjeta es de un agente si la creó él o si está
asignada a él.

Eso es un muro, no una preferencia. Un agente no puede enterarse de que existe
el trabajo de otro: ni los títulos, ni cuántas tarjetas hay, ni que hay algo.
Si le pides que mueva una tarjeta que no es suya, le responden que no hay
ninguna tarjeta suya con ese número; y una tarjeta que no existe recibe la
misma frase, porque un rechazo que distinguiera los dos casos sería una forma
de preguntarle al tablero qué hay, un id cada vez.

La excepción es **manager** (el agente 000), el orquestador: su trabajo es
repartir y hacer seguimiento, así que lee el tablero entero. Por eso coordinar
es su trabajo y no el de los demás.

Una confirmación destructiva **no tiene botón predeterminado**: se abre con el
foco en el propio diálogo, así que Intro no hace ni una cosa ni la otra y hay
que decir cuál de las dos. Escape cancela. Para seguir adelante hay que pulsar
el botón rojo.

Una confirmación normal, de las que no destruyen nada, sí se abre con el foco en
su botón de confirmar, con un anillo alrededor, y ahí Intro significa que sí.

Borrar una tarjeta deja una fila que registra que existió y quién la borró, así
que un agente no puede borrar el rastro de lo que estaba haciendo.

## Ajustes

Los ajustes están agrupados en pestañas, y la pestaña va en la URL, así que
recargar o guardar el enlace te devuelve donde estabas:

| Pestaña | Qué hay dentro |
|---|---|
| **Sistema operativo** | Qué máquina es esta, cuánta memoria y disco quedan, y si los cuatro servicios están en marcha, cada uno en verde si está activo y en rojo si no lo está. Leído sin privilegios, igual que lo lee `os-watcher` |
| **Cuenta** | El único correo y la contraseña. Cambiar la contraseña exige la actual |
| **Correo** | SMTP, para cuando algo tenga que llegarte por email |
| **Canales** | Discord, Mattermost, Telegram, X, en orden alfabético: una caja para cada uno, con su propio Guardar |
| **Audio** | Motor de transcripción, proveedor, modelo, descargas, idioma y conservación de audios de Telegram |
| **Herramientas** | Herramientas instaladas, agrupadas en subpestañas como Automatización y Navegador |
| **Agentes** | Ajustes que valen para todos los agentes a la vez, y el repositorio y la rama de los que salen las plantillas. Se guardan en el servidor: una ejecución que arranca por cron no tiene navegador del que leer una preferencia |
| **Chat** | Cómo se comporta el campo de mensaje: si Intro envía, si cada respuesta muestra lo que costó |
| **Kanban** | Cuántas tarjetas muestra cada columna y si listar las borradas recientemente |
| **Interfaz** | Tema, idioma, cuántos segundos se muestra un mensaje emergente y si **+** pregunta de dónde parte un agente nuevo |

En **Sistema operativo**, los estados de los servicios se alinean con la
segunda columna de los datos de la máquina.

### Transcripción de audio

En Alpine, la instalación o actualización devuelve el control de la sesión SSH al terminar; los servicios continúan ejecutándose con OpenRC.

Abre **Settings → Audio**. La configuración se guarda en el servidor y se aplica a las notas de voz y archivos de audio que llegan por Telegram.

1. Elige **Local · whisper.cpp** o **API de un proveedor**. Inicialmente está desactivada.
2. En local, selecciona un modelo y pulsa **Descargar modelo** si falta. El instalador deja listo `base`; la lista incluye los 30 modelos oficiales, los ingleses `.en`, los cuantizados y los modelos `ggml-*.bin` que instales manualmente en `/opt/boa/whisper/models/`. El tamaño y el estado se muestran en pantalla. Los modelos grandes necesitan más RAM y CPU.
3. Con una API, guarda antes su clave en **Claves API**. Aparecen OpenAI, Groq, Mistral, Together AI, Hugging Face y Cloudflare cuando tienen una clave. Elige una sugerencia o escribe el identificador de otro modelo de transcripción del proveedor. Cloudflare ofrece sus dos variantes compatibles de Whisper y usa la credencial `account-id:api-token`.
4. Elige el idioma (`auto` o un código como `es`), la duración máxima y si conservar el audio para reproducirlo; pulsa **Guardar**. Para probarlo, responde por Telegram a un mensaje del agente con una nota de voz. También puedes seleccionar antes el agente con `/agents`.

El límite inicial es de 600 segundos, configurable entre 30 y 3600; el archivo recibido no puede superar 20 MiB. La transcripción se procesa en segundo plano y la cola sobrevive a una actualización. Si el agente está ocupado, el texto espera conservando su destinatario. El nombre de un agente pronunciado dentro del audio no cambia ese destinatario.

En el chat web aparece la transcripción y, si activaste su conservación, un reproductor. Se conserva una copia Ogg para reproducción, accesible sólo tras iniciar sesión. Si se desactiva la conservación, los nuevos mensajes mantienen sólo el texto. Vaciar el chat elimina los audios guardados de los turnos ya procesados. Las copias de seguridad incluyen esos audios; los modelos descargados se conservan durante las actualizaciones pero no se incluyen en la copia. Tras restaurar en otra máquina, descarga desde Audio cualquier modelo adicional que falte.

El motor local procesa el audio en tu servidor. El modo API envía el audio al proveedor elegido y puede generar cargos adicionales, independientes del consumo del modelo del agente. No se cambia automáticamente de local a nube cuando hay un error. Whisper transcribe, no traduce; los modelos `.en` sólo reconocen inglés. Esta función recibe audio de Telegram; el chat web muestra el resultado, sin añadir un botón de grabación.

Para actualizar una instalación existente, ejecuta como root el instalador de tu distribución con `--update`. Instalará FFmpeg, whisper.cpp y el modelo base bajo `/opt/boa/whisper/` sin activar la transcripción hasta que la configures.

### Idiomas

La interfaz viene en quince:

| | | |
|---|---|---|
| Deutsch (Deutschland) | English (United Kingdom) | English (United States) |
| Español (Argentina) | Español (España) | Français (France) |
| עברית (ישראל) | हिन्दी (भारत) | Italiano (Italia) |
| 日本語 (日本) | 한국어 (대한민국) | Português (Brasil) |
| Português (Portugal) | Русский (Россия) | 简体中文 (中国) |

El hebreo se escribe de derecha a izquierda, y al elegirlo se refleja toda la
interfaz: la barra lateral pasa a la derecha y todo lo demás la sigue. El
código, las rutas y los comandos siguen yendo de izquierda a derecha, y cada
mensaje del chat sigue su propio idioma, así que una respuesta en inglés se
lee de izquierda a derecha incluso en una página en hebreo.

En **Ajustes → Interfaz → Idioma** se elige uno, y se guarda en tu navegador,
igual que el tema. Un navegador que no ha elegido nunca recibe lo más parecido
a lo que pide, e inglés si no hay nada parecido.

Otras dos cosas siguen al idioma y NO son una preferencia del navegador,
porque una ejecución que arranca por cron no tiene navegador:

- **Ajustes → Agentes → Idioma en el que responden los agentes** añade una
  línea al prompt de sistema de cada agente, escrita en ese idioma.
- Los **bots de Telegram y de Discord** también lo hablan: sus propias frases,
  el informe de `/status` y el texto de ayuda.

Las preferencias de Chat, Kanban e Interfaz se guardan en tu navegador y no en
el servidor: describen cómo trabajas tú en esta máquina, y es razonable que el
móvil y el escritorio no opinen lo mismo.

## Mensajes emergentes

Cuando se guarda algo, la confirmación aparece en el centro del panel que
estás mirando y luego desaparece sola. Está en medio a propósito: el botón
Guardar del final de una pestaña larga escribía una línea arriba del todo de
la página, varias pantallas por encima de donde estabas mirando, así que
guardar parecía no hacer nada.

En **Ajustes → Interfaz → Segundos que se muestra un mensaje emergente** se
elige cuánto tiempo, entre 1 y 30 segundos. Por defecto son tres: suficiente
para leer «Ajustes guardados» y poco como para no quedarse encima del campo
que ibas a escribir.

Los mensajes de error no hacen caso a ese número. Se quedan hasta que los
cierres, con la «×» o con Escape, porque un error es el único mensaje que
tiene que seguir ahí cuando vuelves a mirar la pantalla.

El color dice cuál de las tres cosas ha pasado:

| Color | Qué significa |
|---|---|
| Verde | Se guardó |
| Ámbar | **No hay cambios que guardar**: pulsaste Guardar y no habías cambiado nada del formulario |
| Rojo | Falló. Dice qué salió mal y espera a que lo cierres |

El ámbar sale en todos los sitios donde puedes pulsar Guardar: en **Ajustes**
(la cuenta, el servidor de correo, las claves de API, los canales y las
preferencias del navegador) y en los ajustes de cada agente. Si pulsas Guardar
dos veces, la segunda te lo dice, en vez de informar de un guardado que no ha
ocurrido. La excepción es un agente recién creado: su formulario tiene los
valores de la plantilla y no se ha guardado nunca, así que Guardar los escribe y
te lleva a su chat.

## Temas

En **Ajustes → Interfaz** se elige la paleta:

| Tema | Qué es |
|---|---|
| **Day** | Grises suaves con las tarjetas más claras, para una habitación con luz |
| **Night** | La paleta oscura, para una habitación a oscuras |
| **Day High Contrast** | Fondo blanco, texto casi negro, bordes duros. Aquí nada se rellena con el color de acento: el cuadro de cada agente en la barra lateral es un contorno, y tu propio mensaje va relleno de una tinta suavizada en vez de azul |
| **Night High Contrast** | Fondo casi negro, texto claro y bordes marcados. El agente seleccionado tiene fondo gris; la pestaña seleccionada lleva un marco cerrado que se une a la línea inferior. Tus mensajes usan un blanco apagado |

Un navegador que no ha elegido nunca arranca con el que coincida con el sistema
operativo, Day o Night, y lo sigue hasta que alguien elija uno. A partir de
ahí la elección se guarda en este navegador, igual que el idioma, así que el
móvil y el escritorio no tienen por qué coincidir.

Un tema es un archivo CSS en `frontend/themes/` del servidor que redefine las
variables `--colour-*`. Dejar un archivo ahí añade un tema: no hay ninguna
lista en el código que actualizar. Su nombre y su descripción salen del
comentario del principio del archivo:

```css
/*
name: Midnight
scheme: dark
description: Cómo se ve, en una línea.
*/

:root {
  color-scheme: dark;
  --colour-page: #101014;
  /* ... todas las --colour-* que define app.css ... */
}
```

Defínelas todas. Una variable que un tema se deje fuera conserva el valor de
app.css, que en un tema claro significa un color de la paleta oscura plantado
en medio.

Los temas que vienen de serie superan todos una relación de contraste de 4,5:1
en cada color con el que pintan texto, y los dos de alto contraste llegan a
7:1, el nivel AAA de la WCAG. Hay un test que falla si alguno deja de hacerlo,
y a cada uno se le exige el listón que su nombre promete. Un tema añadido a mano no pasa por ahí, pero se le aplica la misma
pregunta: un servicio marcado como caído en un rojo que no se lee es un
servicio del que nadie se entera.

## Cuándo se ejecuta una tarjeta

Asignar una tarjeta es la forma de darle trabajo a un agente, y quien convierte
eso en una ejecución es un servicio llamado **buzzer**:

    cada pocos segundos:
      tarjetas con dueño, con una hora ya pasada y sin avisar todavía
        -> arrancar ese agente, salvo que ya esté ejecutando algo
        -> anotar el aviso en la tarjeta

El campo **Cuándo** del formulario decide la hora:

| Opción | Qué pasa |
|---|---|
| **Inmediatamente** | El agente se despierta en cuanto se guarda la tarjeta. Es lo que viene marcado: asignar una tarjeta es pedir el trabajo |
| **Cuando se despierte el agente** | La tarjeta se queda en el tablero. No se despierta a nadie; el agente la encuentra en su siguiente ejecución |
| **Programar para una fecha concreta** | Una hora en UTC. El agente se despierta entonces |

A un agente que ya está trabajando no se le interrumpe. La tarjeta conserva su
turno y se reintenta en la siguiente vuelta, así que una ejecución programada
contra un agente ocupado empieza unos segundos tarde en vez de no empezar, y un
agente nunca tiene dos ejecuciones a la vez. Una tarjeta avisa una sola vez:
para volver a ejecutarla, hay que volver a ponerle hora.

### La tarjeta aparece en el chat del agente

Al arrancar la ejecución, el chat del agente recibe un mensaje que nombra la
tarjeta:

    Tienes una tarea asignada en una tarjeta:

    Id de la tarjeta: 1284
    Título: Renovar los certificados
    Descripción de la tarea: «Ejecuta el instalador con --update y avisa»
    A ejecutar: Inmediatamente

Si la tarjeta se la entregó otro agente, la primera línea dice quién: *manager
te ha asignado una nueva tarjeta*. Si la tarjeta estaba programada en vez de
pedida para ya, la última línea muestra la hora: `a2026m03d31@13:45`, en UTC, la
misma hora que el tablero enseña en esa tarjeta.

El mensaje se escribe **cuando arranca la ejecución**, nunca antes. Una tarjeta
que programas para esta noche y borras esta tarde no deja nada en el chat,
porque nunca se ejecutó nada.

El agente responde debajo, como a cualquier otro mensaje, indicando lo que
costó la ejecución. Hay tres cosas que pueden dejar una línea ahí sin que el
agente haya hecho nada, y cada una dice cuál fue: el agente estaba apagado, ya
había gastado sus ejecuciones del día, o la ejecución no se pudo arrancar.
Ninguna es silenciosa, porque una tarjeta que se anuncia y luego se ignora se
parece exactamente a un agente que no funciona.

Lo que esa ejecución no hace es leer la conversación. Sus instrucciones son la
tarjeta. Lo que dijiste antes en el chat se reenvía sólo cuando escribes tú un
mensaje; si no, cada ejecución programada pagaría una conversación que nadie
está teniendo.

Una tarjeta que se le da al **manager** se trata distinto: se le pide que
decida quién debe hacerla y que pase la tarjeta con `kanban.assign_card`. La
tarjeta conserva su id, sus instrucciones y su historial y cambia de manos, y
el agente al que llega se despierta para ella. Eso es delegar, y no crear una
segunda tarjeta para el mismo trabajo.

## Canales

En **Ajustes → Canales**, configura a dónde pueden escribir los agentes:

| Canal | Qué necesita |
|---|---|
| Discord | un `bot_token` y un `channel_id` para hablar en los dos sentidos, o una URL de webhook para sólo enviar |
| Mattermost | una URL de webhook entrante |
| Telegram | el `bot_token` de BotFather y el `chat_id` |
| X | un `bearer_token` |

Cada canal configurado muestra **Configurado** en verde, con el mismo color
que una clave API guardada. Los canales sin configurar conservan el estado neutro.

Las credenciales se guardan de forma que **ningún agente pueda leerlas**. El
agente le pide al servidor que envíe; el servidor lee el token y envía. El
mensaje llega con el nombre del agente por delante, puesto por el servidor, así
que ningún agente puede hacerse pasar por otro.

Después, en la pestaña **Canales** de cada agente, marca a qué canales puede escribir.
Necesita tanto `channel.write` como el canal en sí.

### Responder a un agente desde Telegram

Telegram y Discord son los dos canales que funcionan también en el otro sentido. Marca
**Permitir responder a los agentes desde Telegram** en sus ajustes, guarda, y ya
puedes escribirles.

El bot tiene tres herramientas en su menú, que son las que ofrece el botón `/`:

| Comando | Qué hace |
|---|---|
| `/agents` | Lista tus agentes como botones. Toca uno para empezar a hablarle |
| `/status` | Servicios, tablero y cada agente con su modelo, herramientas y habilidades |
| `/help` | Esas tres, y las otras dos formas de llegar a un agente |

### Nadie más ve nada de esto

El nombre de usuario del bot es público (cualquiera que lo encuentre puede
abrirlo), así que el menú se escribe **sólo para tu chat**. Otra persona que
abra ese mismo bot se encuentra un chat vacío: ni comandos bajo `/`, ni
descripción, ni nada que pulsar salvo el botón Iniciar, que Telegram dibuja en
todos los bots y que ninguna API puede quitar.

Pulsarlo no hace nada. El listener compara el `chat_id` de cada mensaje con el
que tienes configurado y descarta lo que no coincide, antes de ejecutar ningún
comando y antes de elegir agente.

**Y no se anota nada.** Ni respuesta, ni línea en el registro, ni constancia de
que alguien haya escrito. El id de un chat que no es el tuyo son datos de otra
persona, y guardarlo significaría que tu instalación va reuniendo en silencio
una lista de quién ha encontrado el bot.

El precio es que un `chat_id` mal configurado se parece exactamente a un
desconocido: tus propios mensajes se descartan en silencio. El configurado se
escribe en el registro en cada arranque, que es con lo que puedes compararlo:

```bash
journalctl -u boa-channel-telegram.service | grep "Registered"
```

En Debian, las unidades de canales usan `boa-channel-<canal>.service`.
El instalador con `--update` migra automáticamente los nombres antiguos.
Alpine conserva los nombres de OpenRC `boa-telegram` y `boa-discord`.

El filtro es por **chat**, no por persona. Si el `chat_id` que configuraste es
el de un grupo, cualquier miembro de ese grupo puede hablar con tus agentes.

### Elegir con quién hablas

Toca `/agents`, toca un agente, y responde:

```
Agente os-watcher:

Envíame tus instrucciones...
```

A partir de ahí **todo lo que escribas va a ese agente** hasta que elijas otro.
Puedes hacerle cuatro preguntas seguidas sin nombrar a nadie, que es lo que
convierte esto en una conversación y no en una línea de comandos.

Hay tres formas de que un mensaje vaya dirigido a alguien, en este orden:

1. **Responder a algo que dijo un agente** va a ese agente, esté seleccionado
   quien esté. Responde a su mensaje (deslízalo, o mantenlo pulsado o haz clic derecho y elige Responder), escribe y envía.
2. **Nombrarlo** —`@os-watcher revisa el disco`— va a él *y además* lo deja
   seleccionado. `@001` también vale, y un nombre con espacios también:
   `@News Miner qué hay de nuevo` es un agente, no dos palabras.
3. **Ninguna de las dos** va a quien elegiste la última vez.

Nada más cambia la selección, así que un agente nunca hereda tu conversación
por ser el último que habló. Un agente que borres deja de estar seleccionado en
vez de seguir capturándolo todo.

Mientras no hayas elegido a nadie, un mensaje que no nombre a nadie recibe de
vuelta la lista de agentes, así que nada desaparece sin explicación.

### Lo que vuelve

El agente contesta en Telegram como respuesta a lo que escribiste, con su
nombre en la primera línea:

```
os-watcher:
25G libres de 28G en /, sin cambios desde ayer.
```

**Y el intercambio entero está en el chat de ese agente en la interfaz web**,
tu pregunta y su respuesta, con un `(por Telegram)` al lado de la hora de lo
que mandaste. Una sola pantalla sigue mostrando todo lo que se le pidió al
agente y todo lo que dijo, en el dispositivo en el que se escribiera cada mitad.

Dos cosas con las que contar:

- **Un agente ocupado lo dice.** Si ya está contestando otra cosa, se te pide
  que lo intentes en un momento en vez de ponerte en una cola: una cola
  escondería que el agente va saturado.
- **Sólo se escucha tu chat.** El nombre de un bot es público y cualquiera que
  lo encuentre puede escribirle. Los mensajes de cualquier otro chat se
  descartan sin responder, así que el `chat_id` que configuraste es lo que
  decide quién puede hablar con tus agentes. Si está mal, no pasa nada de nada.

Es long polling, no un webhook: el servidor se conecta hacia fuera a Telegram,
así que no hay que abrir nada a internet para que esto funcione.

Si Telegram no acepta la respuesta, porque bloqueaste al bot, cambió el id del
chat o el token dejó de valer, se descarta de Telegram en el acto, y si no se
puede llegar a Telegram durante una hora también se descarta. Nunca se pierde:
la conversación entera, esa respuesta incluida, está en el chat del agente en
la interfaz web.

### Qué aspecto tiene el mensaje de un agente

Los modelos escriben markdown, y Telegram renderiza un subconjunto pequeño de
HTML, así que los dos se traducen al salir. Lo que llega está formateado, no
lleno de asteriscos:

| Lo que escribe el agente | Lo que ves en el móvil |
|---|---|
| `**25G libres**` | **25G libres** |
| `` `df -h` `` | `df -h` en monoespaciado |
| `# Informe de disco` | una línea en negrita |
| `- elemento` | • elemento |
| una tabla | un bloque monoespaciado, con las columnas alineadas |
| ```` ```bash ```` | un bloque de código |
| `[texto](https://…)` | un enlace |

Telegram no tiene encabezados, ni listas, ni tablas propias, que es por lo que
esas tres se convierten en lo más parecido que se pueda leer en vez de
desaparecer.

Si alguna vez Telegram rechaza el formato, **el mensaje se vuelve a enviar como
texto plano en lugar de perderse**. Las palabras te llegan igual; el log del
servidor dice qué pasó, así que un fallo de formato se ve en vez de degradarse
en silencio para siempre.

Todo lo que dice el bot por su cuenta —la lista de agentes, «está contestando
otra cosa», `/status`— va en el idioma configurado en **Ajustes → Agentes**, el
mismo en el que responden los agentes.

## Responder a un agente desde Discord

Discord funciona igual que Telegram, con un bot tuyo. Cinco minutos de
configuración, una sola vez.

### Crear el bot

1. Abre <https://discord.com/developers/applications> y pulsa **New
   Application**. Ponle el nombre que quieras.
2. **Bot** en la barra lateral, luego **Reset Token**, y copia lo que te
   muestre. Ese es el `bot_token`, y sólo se enseña una vez.
3. **OAuth2 → URL Generator**: marca **bot**, y debajo **View Channels**,
   **Send Messages** y **Read Message History**. Abre la URL que construye y
   añade el bot a tu servidor.
4. En el propio Discord, activa **Ajustes → Avanzado → Modo desarrollador**,
   haz clic derecho en el canal donde quieres a los agentes y **Copiar ID del
   canal**. Ese es el `channel_id`.

No hace falta nada más. En particular **no** hace falta el Message Content
Intent: ese interruptor es para el Gateway, y esto lee el canal por la API
normal.

### Encenderlo

En **Ajustes → Canales → Discord**, pon el token y el id del canal, marca
**Permitir responder a los agentes desde Discord** y guarda. En unos segundos
el log dice qué bot está escuchando y dónde:

```bash
journalctl -u boa-channel-discord.service | grep "Listening"      # Debian
tail /opt/boa/logs/boa-discord.log                # Alpine
```

Los mensajes escritos antes de encenderlo no se contestan: la primera pasada
sólo apunta por dónde va el canal y empieza desde ahí.

### Hablar con un agente

| Orden | Qué hace |
|---|---|
| `!agents` | Lista tus agentes y qué escribir para llegar a cada uno |
| `!status` | Servicios, tablero y cada agente con su modelo, herramientas y habilidades |
| `!help` | Estas tres, y las demás formas de llegar a un agente |

`/agents` también vale, si es lo que te salen escribir los dedos. Aquí no hay
botones ni menú de slash commands: las dos cosas son *interacciones*, y Discord
sólo las entrega por una conexión que esta instalación decide no abrir.

Las tres formas de dirigirse a alguien son las que ya conoces:

1. **Responder a algo que dijo un agente** va a ese agente, esté seleccionado
   quien esté. Clic derecho en su mensaje → Responder, o deslízalo en el móvil.
2. **Nombrar a uno** —`@os-watcher mira el disco`— le llega a él *y* lo deja
   seleccionado. `!os-watcher`, `@001` y `@News Miner qué hay de nuevo` valen
   igual.
3. **Ninguna de las dos** va a quien elegiste la última vez.

### Lo que vuelve

La respuesta llega como contestación a tu pregunta, con el nombre del agente en
negrita en la primera línea, y **la conversación entera está en el chat de ese
agente en la interfaz web**, con un `(por Discord)` al lado de la hora de lo
que enviaste.

Una respuesta larga llega en varios mensajes en vez de cortada: Discord rechaza
todo lo que pase de 2000 caracteres, así que se parte por líneas, en cuatro
mensajes como mucho. Puedes responder a cualquiera de ellos y llega al mismo
agente. Si había más de lo que caben en cuatro, el último acaba en `…`, y el
texto completo está en la interfaz web, que es donde se escribió.

### Quién puede hablar con tus agentes

**Todo el que pueda escribir en ese canal.** Esta es la única diferencia real
con Telegram, y merece un minuto: allí el bot compara el id del chat de cada
mensaje y descarta lo que no cuadra, así que un desconocido que encuentre tu
bot no obtiene nada. Aquí el bot lee un canal, y cualquiera que pueda publicar
en él puede lanzar ejecuciones en tu servidor.

Así que pon a los agentes en un **canal privado**, uno que sólo veas tú, o tú y
la gente de la que te fías. El bot no necesita acceso a nada más.

### Si sólo quieres avisos

Deja el token vacío y pon una **URL de webhook**: **Ajustes del canal →
Integraciones → Webhooks → Nuevo webhook → Copiar URL del webhook**. Con eso
los agentes pueden escribir en el canal y nada más. Escuchar necesita el bot,
así que el interruptor se rechaza sobre un webhook en vez de quedarse sin hacer
nada.

## El orquestador

`agent-000`, llamado **manager**, es el único agente que se crea durante la instalación. Es un agente
normal en todo salvo en que no se puede borrar.

El patrón previsto: dale al manager las herramientas de kanban y un prompt que
le diga que parta los objetivos en tarjetas y se las asigne a otros agentes por
id. Dale a los demás `bash.run` y lo que necesiten, y un prompt que les diga
que trabajen en las tarjetas asignadas a ellos.

Sólo funciona si las tarjetas del manager dicen qué significa «terminado». Una
tarjeta que no lo dice es un deseo, y el agente que la recoja lo decidirá por
su cuenta.

## La pestaña de herramientas

**Ajustes → Herramientas** muestra lo instalado en el servidor. Cada familia es
una subpestaña —Automatización, Navegador, Canales, Correo, Imágenes,
Internet, Kanban, Memoria, Sistema operativo, RAG, Habilidades— con el
número de herramientas que tiene, y cada herramienta tiene su caja con sus
argumentos y lo que significan. La pestaña abierta va en la URL
(`/settings/?tab=tools&family=mail`), así que recargar o guardar el enlace la conserva.
Los enlaces antiguos de `/tools/` redirigen aquí y conservan la familia seleccionada.

Una herramienta cuya familia nadie ha nombrado —un `.py` que alguien dejó en
`/opt/boa/tools/`— va a **Otras**, con su familia escrita en su propia caja.
Sigue siendo una herramienta hasta la interfaz; simplemente no se gana una
pestaña propia, o la fila crecería con cada script suelto.

Qué agente puede usar qué herramienta se decide en la pestaña **Herramientas**
de cada agente, no aquí.

## La documentación de la API

**Documentación de la API**, en la barra lateral, lista todos los endpoints
bajo `/api/`, agrupados por área, con sus parámetros y lo que responden. Se
genera a partir de la propia descripción OpenAPI de esta instalación, así que
no puede desviarse del código: `openapi.json`, enlazado arriba, es lo mismo en
un archivo que le puedes dar a un generador de clientes.

Está en el idioma que hayas elegido en **Ajustes → Interfaz**, igual que el
resto de la interfaz. La especificación en sí se queda en inglés: los nombres
de campo, los ids y los mensajes de error son ingleses en todo el proyecto, y
un `openapi.json` traducido describiría una API que no existe.

Los cuerpos de las peticiones se muestran como JSON coloreado, igual que en un
editor: los nombres de campo de un color, los valores de otro, y las llaves y
las comas atenuadas, porque son andamiaje. Los colores salen del tema que hayas
elegido, y copiar un bloque te sigue dando JSON válido.

La página también se puede leer sin iniciar sesión, sola y sin barra lateral.
Describe la forma de la API, no tus datos.

## Trabajo que no necesita que el agente piense

Hay trabajo recurrente y mecánico: comprobar un certificado, rotar un log,
recoger un número. Despertar a un agente para eso cuesta tokens cada vez, para
llegar a una conclusión a la que un script de shell llega gratis.

Por eso un agente puede escribirse scripts y programarlos. Dale las
herramientas de **Automatización** y podrá:

1. `script.write` — poner un script de shell en su propia carpeta `scripts/`.
2. `cron.add` — ejecutarlo cada cierto tiempo, en su propio crontab.
3. Leer los resultados en su siguiente ejecución y decidir qué significan.

El script se ejecuta con el usuario Linux de ese agente, con los mismos
permisos que tiene él, y **no cuesta ni un token**: es un script de shell, no
una llamada al modelo. Lo que cuesta tokens es que el agente lea la salida
después y decida qué hacer con ella.

Lo que NO puede hacer:

- Programar nada que no sean sus propios scripts. Un comando suelto en un
  crontab es algo que nadie puede revisar después.
- Ejecutar nada más a menudo que cada 5 minutos. Un trabajo cada minuto no es
  una programación.
- Tocar la línea que lo despierta a él. Esa es tuya, en su pestaña **Cron**.

Tú ves las dos mitades: los scripts en su home, y las líneas que los ejecutan
en la pestaña Cron, al lado de la tuya.

## Dónde acaba el informe de una ejecución

Una ejecución que lanzas desde el chat te contesta ahí. Una que arranca por una
tarjeta que vence contesta en el mismo sitio. Una que arranca por el **crontab
del propio agente** no contesta en ningún sitio concreto —nadie le preguntó
nada—, así que:

- **Siempre en Historial**, en **Últimas ejecuciones**: lo que dijo cada una y
  lo que costó. Es donde mirar cuando te preguntes qué ha estado haciendo un
  agente.
- **Y en el chat cuando merece interrumpirte**: la ejecución no terminó, o
  cambió algo que tú verías (una tarjeta, un mensaje a un canal, un buzón). Una
  ejecución que sólo miró se queda en el Historial. Si no, un agente con
  crontab horario te metería veinticuatro mensajes de «nada que informar» al día.

Esos mensajes llevan encima una línea que dice que nadie los pidió, y NUNCA se
reenvían al modelo, así que no te cuestan nada en tu siguiente mensaje.

**Una ejecución que nunca empezó también sale en el historial**, marcada «no
llegó a arrancar». Pulsa **Ejecutar ahora** en un agente al que todavía no le
has puesto la clave de API, o mientras ese agente ya se está ejecutando, y la
línea del historial te dice cuál de las dos cosas fue. Antes la pantalla decía
que la ejecución había empezado y no aparecía nada más, porque el motivo se
escribía en un sitio que nadie lee. Una ejecución que no llegó a arrancar no
gasta una de las ejecuciones del día del agente, y tampoco cuenta como un
fallo suyo: no se ejecutó nada.

## La barra de estado

La franja del final de todas las páginas, que cruza la ventana entera por
debajo también de la barra lateral, habla de la instalación en conjunto:

- **ejecutor** y **API de agentes**, en verde cuando están en marcha. Si alguno
  está en rojo, los agentes no se ejecutarán y nada más en la interfaz te lo va
  a decir.
- **agentes**: cuántos están encendidos de los que hay.
- **tablero**: tarjetas en cada columna.
- **tokens hoy**: todo lo gastado desde medianoche UTC, sumando todos los
  agentes, y en cuántas ejecuciones. Es el número que delata a un agente
  metido en un bucle antes de que lo haga la factura.

En el extremo derecho de la franja, el logo de GitHub y el nombre **nipegun**
abren el repositorio del proyecto, <https://github.com/nipegun/bunch-of-aigents>,
en una pestaña nueva. La cuenta con la que has entrado no se muestra: una
instalación sólo tiene una, así que escribirla no te dice nada que no supieras.

## En qué idioma responden tus agentes

Escribe el prompt de cada agente en el idioma en el que pienses y te responderá
en ese. Eso cubre el chat. Lo que NO cubre es una ejecución que arranca por el
crontab del propio agente: nadie le escribió en ningún idioma, y los prompts de
fábrica están en inglés, así que una instalación en español recibía sus
informes programados en inglés.

**Ajustes → Agentes → Idioma en el que responden los agentes** lo arregla para
todos los agentes a la vez. Añade UNA línea al prompt de sistema de cada uno,
escrita en el idioma que pide, y que dice que tiene prioridad sobre lo que ese
prompt diga de idiomas. Si lo dejas como viene, no cambia nada: cada agente
responde en el idioma de su propio prompt.

Se guarda en el servidor, a diferencia del idioma de esta interfaz, que es una
preferencia de tu navegador. Una ejecución que despierta por cron no tiene
navegador.

## Escribir los prompts en tu idioma

Escribe el prompt de sistema en el idioma en el que pienses. Nada en el sistema
está atado al inglés: el prompt, la memoria, el chat, los títulos de las
tarjetas y los mensajes entre los servicios son UTF-8 de punta a punta, tildes
incluidas.

El prompt por defecto de un agente nuevo viene en inglés, y su última regla le
dice al agente que responda en el idioma en el que esté escrito su prompt.
Reescríbelo entero en tu idioma y esa regla se va con él: el agente sigue el
prompt que tiene, no el que traía.

Los prompts se guardan con líneas enteras, no cortadas a un ancho fijo. La caja
de texto las ajusta en pantalla para que se lean bien, sin meter los saltos de
línea en el archivo: una regla que es una frase se queda en una línea, y
editarla no obliga a recolocar el párrafo entero.

## Copias de seguridad y restauración

Todo lo que hace tuya esta instalación vive en `/opt/boa/` y en los usuarios
de Linux de los agentes. Una orden lo reúne en un único archivo:

```bash
./install-update-reinstall-debian.sh --backup
```

Escribe `/root/boa-backup-<fecha>.tar.gz`, sólo de `root`, con modo 0600, con
los servicios en marcha: no se para nada. Con una ruta lo escribe en otro
sitio: `--backup /mnt/usb/boa.tar.gz`. Dentro: las dos bases de datos,
copiadas con la API de copia de la propia SQLite para que no se pierda nada
que siga en un write-ahead log; las claves de los proveedores, los secretos
de los canales y el secreto de sesión; los certificados; cada agente con su
home, sus archivos protegidos, su usuario de Linux y su crontab; las skills y
las herramientas escritas en este servidor; y el log de instalación, por la
contraseña que guarda. Fuera: el código, el entorno de Python, el navegador y
las dos decisiones propias de esta máquina, el modo de puertos y si tiene
navegador, así que una restauración nunca importa las de otra máquina.

**Trátalo con la misma privacidad que a la máquina.** Guarda todas las claves
de API, todos los tokens de canal y la contraseña de acceso.

Para restaurar, en esta máquina o en una nueva:

```bash
./install-update-reinstall-debian.sh --install       # sólo en una máquina nueva
./install-update-reinstall-debian.sh --restore /root/boa-backup-<fecha>.tar.gz
```

Pide un YES, o acepta `--yes`. Después para los servicios, vuelve a crear los
usuarios de los agentes con los mismos nombres, y los mismos ids cuando están
libres, sustituye las bases de datos, las claves, los certificados, los
agentes, las skills y las herramientas por los del archivo, instala los
crontabs y arranca todo. Entra con el correo y la contraseña de la copia: los
dos se añaden a `/opt/boa/logs/install.log` bajo el encabezado `Credentials
of the restored backup`, y el log completo de la copia queda al lado como
`install.log.restored-<fecha>`.

Un agente que esta máquina tenía y la copia no conserva su home en disco y
desaparece de la interfaz, porque la lista de agentes está en la base de
datos restaurada. En Alpine son las mismas dos flags en
`install-update-reinstall-alpine.sh`.

## Servicios

| Servicio | Se ejecuta como | Qué hace |
|---|---|---|
| `boa-proxy` | `boa` | HAProxy: termina TLS en el 11443, redirige el 11080 y sirve los puertos web |
| `boa-web` | `boa` | La interfaz web y la API, en un socket Unix detrás del proxy |
| `boa-exec` | `root` | Crea usuarios, instala crontabs, lanza ejecuciones |
| `boa-samba` | `root` | Autentica usuarios SMB y sirve cada carpeta samba/ como el usuario de su agente |
| `boa-agent-api` | `boa` | La puerta por la que los agentes llegan al tablero y a los canales |
| `boa-buzzer` | `boa` | Vigila el tablero y despierta a un agente cuando vence una tarjeta |
| `boa-embeddings` | `boa` | Sirve el modelo local de vectorización de las bibliotecas documentales, en un socket Unix |
| `boa-rag` | `boa` | Planifica la cola de indexación de las bibliotecas documentales |
| `boa-channel-telegram.service` | `boa` | Escucha en Telegram, para que puedas responder a un agente desde el móvil |
| `boa-channel-discord.service` | `boa` | Lo mismo para un canal de Discord |

```bash
systemctl status boa-proxy boa-web boa-exec boa-agent-api boa-buzzer \
                 boa-embeddings boa-rag \
                 boa-channel-telegram.service boa-channel-discord.service boa-samba
journalctl -u boa-exec -f
```

Las unidades de canales de Debian usan `boa-channel-<canal>.service`.
Al actualizar con `--update`, las unidades antiguas se detienen y deshabilitan
antes de habilitar las nuevas.

Los mismos procesos se ejecutan en Alpine; allí los servicios de canales
siguen llamándose `boa-telegram` y `boa-discord`. Son servicios de OpenRC
supervisados con `supervise-daemon` y lo que imprime cada uno va a su propio
archivo en `/opt/boa/logs/`, rotado cada semana:

```bash
rc-status
rc-service boa-exec status
tail -f /opt/boa/logs/boa-exec.log
```

## Seguridad

El diseño da por hecho que algún agente acabará haciendo algo que no
pretendías, porque es un modelo de lenguaje con una shell.

- **Cada agente es un usuario de Linux distinto**, y su home es `0700`. Los
  agentes no pueden leer los archivos, los prompts ni las claves de los demás.
- **`/opt/boa/agents/` es `0711`**, así que ningún agente puede siquiera listar
  qué otros agentes existen.
- **Ningún agente se ejecuta como root, nunca.** Sólo `boa-exec` lo hace, y
  acepta una lista cerrada de operaciones por un socket Unix. Entre ellas no
  está «ejecuta este comando».
- **Una ejecución la acota el kernel, no sólo sus techos.** Ningún agente
  puede tener más de 1024 procesos e hilos, así que una fork bomb se para en
  el número; en Debian cada ejecución vive en un scope propio de systemd con
  2 GiB de memoria, que además termina con lo que la ejecución dejara
  corriendo al acabar.
- **Los agentes nunca ven las credenciales de los canales.** Un token de bot no
  es un mensaje: es autoridad permanente para enviar todo lo que ese bot pueda
  enviar. Los agentes le piden a la API de agentes que envíe, y ella envía.
- **Los agentes sólo tocan sus propias tarjetas.** Véase
  [El tablero kanban](#el-tablero-kanban).
- **`web.fetch` rechaza las direcciones privadas**, comprobando la IP resuelta
  y volviendo a comprobarla en cada redirección, para que un agente que lea una
  página hostil no pueda ser convencido de llamar a tu red interna.

Está pensado para una LAN y no debería exponerse a Internet.

## Cuando algo no funciona

**He elegido `--ports direct` y el HAProxy de la máquina ha desaparecido.** No
ha desaparecido: está retirado. Parado, fuera de todos los runlevels en
Alpine, deshabilitado y enmascarado en Debian, y su
`/etc/haproxy/haproxy.cfg` borrado si lo había escrito el instalador, o
conservado como `haproxy.cfg.before-boa.<fecha>` si lo habías escrito tú. En
este modo la aplicación hace bind al 80 y al 443 ella misma, y cualquier otra
cosa que ocupe esos puertos le impide arrancar: un proxy que quedara
habilitado se los llevaría en el siguiente arranque, antes de que la
aplicación llegue a ejecutarse. El paquete `haproxy` sigue instalado a
propósito: `boa-proxy` es `/usr/sbin/haproxy`, y en este modo es lo que sirve
el 80 y el 443.

Para volver atrás, ejecuta el instalador con `--update --ports proxied`:
desenmascara la unidad, vuelve a escribir la configuración de la máquina y la
arranca. Tu archivo anterior, si lo había, sigue al lado con su nombre
`before-boa`.

**`boa-proxy` se reinicia una y otra vez y nada escucha en el 11443.** Lee
`/opt/boa/logs/boa-proxy.log`. Si dice `Cannot raise FD limit to 4131`, el
límite duro de descriptores de archivo de esa máquina es menor que lo que
pidió el proxy: normalmente, un contenedor pequeño. Una instalación hecha
antes de que esto se corrigiera todavía tiene `maxconn 2048` en
`/opt/boa/config/haproxy.cfg`. Ejecutar el instalador con `--update` reescribe
el archivo; para arreglarlo en el momento:

```bash
sed -i 's/^  maxconn 2048$/  fd-hard-limit 4000/' /opt/boa/config/haproxy.cfg
rc-service boa-proxy restart        # systemctl restart boa-proxy en Debian
```

A partir de ahí HAProxy se dimensiona con los descriptores que puede tener de
verdad, que con un límite duro de 4096 son unas 1987 conexiones: muchas más de
las que esto necesita.

**El instalador termina con «Everything is in place but the application does
not answer».** La instalación está puesta y la página nunca llegó. El log ya
contiene el motivo:

```bash
sed -n '/Why it did not answer/,$p' /opt/boa/logs/install.log
```

Ese bloque es el aspecto que tenía la máquina en ese momento: qué entendió
curl de la petición, si hay algo escuchando en el puerto, el estado de los
diez servicios y las últimas líneas de lo que imprimieron el proxy y la
aplicación web. `000` no es un código HTTP: es curl diciendo que no recibió
ninguno. Un servicio que se declara `started` junto a `nothing is listening on
port 11443` es un proceso que muere y vuelve a arrancarse cada pocos segundos,
y su propio log, unas líneas más abajo, dice por qué.

Una actualización que falló aquí ya ha dejado puesta la versión anterior y la
está ejecutando. Una primera instalación no tiene a dónde volver, así que lo
deja todo en su sitio: arregla lo que nombre el bloque y vuelve a ejecutar el
instalador con `--update`.

**El instalador se para diciendo «systemd is not running».** Se está negando
a instalar en una máquina donde systemd no es el PID 1, porque cada servicio que
escribe es una unidad de systemd y no habría nada que los arrancara. Un Debian
normal vale; un contenedor no, salvo que se creara para ejecutar systemd:

```bash
apt-get install -y systemd systemd-sysv dbus dbus-user-session
```

y después volver a crear el contenedor con `/sbin/init` como su comando: un
contenedor que ya está en marcha no puede cambiar su PID 1. En Alpine esto no
aparece: ese instalador añade OpenRC él solo cuando la máquina no lo tiene.

**No pasa nada al pulsar Ejecutar ahora.** Mira los dos puntos del final de la
barra lateral. Si `ejecutor` está rojo:

```bash
systemctl status boa-exec
journalctl -u boa-exec -n 50
```


**El navegador muestra 503 y todos los servicios están en marcha.** El HAProxy
de la máquina ha marcado el backend como caído. Casi siempre es por `option
ssl-hello-chk` en ese backend: su ClientHello es anterior a TLS 1.2 y la
aplicación exige TLS 1.2. Quita esa línea y recarga HAProxy.

**El agente se ejecuta pero no hace nada.** Mira su panel de Historial. Luego
ejecútalo a mano y observa:

```bash
runuser -u agent-001 -- /opt/boa/venv/bin/python3 \
  /opt/boa/webapp/backend/core/runner.py --agent-id 001
```

Añade `--dry-run` para ver qué cargaría —proveedor, herramientas, techos— sin
llamar al modelo.

**Dice que no puede contactar con el modelo.** Con proveedores autoalojados,
comprueba que el servidor está en marcha y que la URL base es correcta. Con los
de nube, comprueba que el archivo de la clave existe en el home del agente y
que le pertenece.

**Dice que una herramienta no está disponible.** Esa herramienta no está
marcada en la página de ese agente. El prompt no puede saltarse eso, que es
justo lo que se busca.

**Han dejado de aparecer tarjetas.** O la casilla de kanban está desmarcada
para ese agente, o `API de agentes` está en rojo al final de la barra lateral:

```bash
systemctl status boa-agent-api
```

**Quiero ver todo lo que hizo un agente.** Su journal está en su propio home:

```bash
cat /opt/boa/agents/001/runs.jsonl
```

Un objeto JSON por línea: cuándo se ejecutó, qué gastó y si terminó.

## Licencia

MIT. Consulta [LICENSE](../LICENSE).
