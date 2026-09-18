# Bunch of AIgents

Agentes de IA autoalojados que se ejecutan de forma programada, en tu propio
servidor GNU/Linux (Debian o Alpine).

Cada agente es un usuario de Linux de verdad, con su propia carpeta home, su
propio crontab y su propio acceso a la shell. Se coordinan mediante un tablero
kanban compartido que podés ver en el navegador, y pueden escribirte por
Telegram, Discord, Mattermost o X.

Está pensado para una sola persona que lo ejecuta en su propia LAN.

## Requisitos

- **Debian con systemd como PID 1, o Alpine con OpenRC.** El sistema de init
  no es un detalle acá: los seis servicios son unidades de systemd en uno y
  scripts de OpenRC en el otro, así que un Debian que arranque con otra cosa
  no tiene nada que los ejecute. **No lo intentes en un Debian sin systemd**:
  el instalador lo comprueba antes de tocar la máquina y se niega, que es la
  respuesta correcta pero una descarga tirada. Comprobalo con
  `systemctl is-system-running`: tiene que responder algo (`running`,
  `degraded`, `starting`), no imprimir “System has not been booted with
  systemd as init system (PID 1)”. Un contenedor necesita `systemd
  systemd-sysv dbus` instalados y `/sbin/init` como su comando. En Alpine no
  hace falta nada por adelantado: el instalador agrega `openrc` él mismo si la
  máquina no lo tiene.
- Acceso a `root`. Ninguno de los dos instaladores usa `sudo` ni lo necesita.
- Unos 500 MB de disco para la aplicación y su entorno de Python.
- `haproxy`, que instala el propio instalador. Es quien termina el TLS, porque
  la cabecera PROXY que envía el HAProxy de la máquina llega antes del handshake
  TLS y sólo un proxy puede leerla ahí.
- Un modelo con el que hablar: una clave de API de un proveedor de nube, o
  bien Ollama, llama.cpp o vLLM ejecutándose en algún sitio accesible.

## Qué hace

- **Un agente es un usuario de Linux.** Crear uno en la interfaz web crea
  `agent-007` en el sistema, con una carpeta home que ningún otro agente puede
  leer. Ese es el aislamiento: el del kernel, no un sandbox escrito en Python.
- **Los agentes se ejecutan según su propia programación.** Cada uno tiene su
  crontab, que pertenece a su usuario y lo ejecuta él, así que el agente
  despierta, hace su trabajo y termina.
- **Hablás con ellos.** Al hacer clic en un agente se abre un chat: le
  pides algo, usa sus herramientas y responde cuando termina. La
  conversación se recuerda.
- **Una conversación por agente, no una por persona.** Cuando llega la hora de
  una tarjeta, la tarjeta aparece en ese mismo chat justo al arrancar la
  ejecución, y la respuesta se ve debajo: el chat de un agente es todo lo que
  se le pidió, por vos o por otro agente, y lo que hizo con eso.
- **Comparten un tablero kanban.** Los agentes añaden tarjetas, las mueven y
  ven el trabajo de los demás. Vos lo mirás en `/kanban/` en vez de leer logs.
- **Cualquier modelo, en la nube o autoalojado.** Vienen veinticinco
  proveedores: Anthropic, OpenAI, Google, DeepSeek, Mistral, Qwen, xAI y los
  demás; los enrutadores que hay por delante, OpenRouter, Groq, Together,
  Vercel y más; y Ollama, llama.cpp y vLLM en tu propio hardware. Cada agente
  elige el suyo, con un suplente para cuando ese se cae.
- **Techos de gasto que de verdad lo detienen.** Tokens, pasos, segundos y
  ejecuciones al día, por agente. Si no, un agente desatendido contra una API
  de pago es una factura abierta.
- **Herramientas ampliables.** Cada herramienta es un archivo `.py` en
  `/opt/boa/tools/`. Poné uno nuevo y aparece en la interfaz.
- **Habilidades que comparten.** Un procedimiento escrito una sola vez en
  `/opt/boa/skills/` se le puede dar a tantos agentes como quieras. Lo que un
  agente aprende por su cuenta muere en su propia memoria; una habilidad no.
- **Un navegador por agente, con sus propias sesiones.** Un agente puede
  iniciar sesión en un sitio, rellenar un formulario y hacer clic —no sólo leer
  una página— y sus cookies viven en su propia carpeta home 0700: el acceso de
  un agente no es el acceso de todos.
- **Responderles desde Telegram.** Elegí un agente con /agents, o respondé a un
  mensaje que te mandó uno, y lo que escribas le llega, arranca una ejecución y
  vuelve contestado a tu celular. El intercambio entero está también en la
  conversación de ese agente en la interfaz web, las dos mitades, así que una
  sola pantalla lo sigue mostrando todo.
- **Catorce idiomas.** Alemán, inglés (Reino Unido y Estados Unidos), español
  (España y Argentina), francés, hindi, italiano, japonés, coreano, portugués
  (Brasil y Portugal), ruso y chino simplificado. La interfaz, la línea que les
  dice a tus agentes en qué idioma responder, y lo que dice el bot de Telegram.

## Herramientas incluidas

| Herramienta | Qué puede hacer un agente con ella |
|---|---|
| `bash.run` | Ejecutar comandos de shell como su propio usuario sin privilegios |
| `kanban.add_card` | Poner una tarea en el tablero compartido |
| `kanban.move_card` | Mover una de sus propias tarjetas entre columnas |
| `kanban.delete_card` | Borrar una de sus propias tarjetas |
| `kanban.list_cards` | Leer el tablero entero |
| `channel.write` | Enviar un mensaje a un canal configurado |
| `web.fetch` | Leer una página web pública |
| `memory.append` | Anotar algo para su yo futuro |
| `memory.replace` | Ordenar lo que recuerda |
| `skill.read` | Leer un procedimiento que se le dio |
| `browser.open` | Abrir una página en su propio navegador, conservando las cookies |
| `browser.read` | Leer la página abierta, o sus enlaces |
| `browser.click` | Pulsar un enlace o un botón de ella |
| `browser.type` | Rellenar un campo, enviándolo si hace falta |
| `browser.screenshot` | Guardar una imagen de ella para ti |

Elegís por agente cuáles recibe. Una herramienta que no se le da a un agente es
una herramienta que no puede llamar, y esa comprobación se hace en el servidor,
no en el prompt.

## Habilidades

Una habilidad es un procedimiento escrito: cómo se hace acá un trabajo, paso a
paso. Una carpeta cada una, adentro de `/opt/boa/skills/`:

```
/opt/boa/skills/BackupVerification/SKILL.md
/opt/boa/skills/DiskPressure/SKILL.md
```

No viene ninguna incluida, y ahí está la gracia: una habilidad describe cómo se
hace un trabajo en ESTA máquina —estos equipos, esta copia de seguridad, este
certificado—, así que una genérica sería un procedimiento que no sigue nadie.
Las tuyas las escribís por SSH, como root, y una actualización nunca las toca.
Una habilidad puede traer archivos propios —un script, una plantilla— junto a
su `SKILL.md`, y el agente puede ejecutarlos.

En el prompt de un agente sólo entran el nombre y la descripción de una línea
de cada habilidad. El resto lo lee con `skill.read` cuando decide que lo
necesita, que es por lo que darle cinco habilidades a un agente le cuesta un
par de cientos de tokens por ejecución en vez de diez mil.

Las habilidades son de root y se escriben en el servidor, igual que las
herramientas y por la misma razón: lo que dice una habilidad entra en el
razonamiento de un agente que se ejecuta a las cuatro de la mañana sin nadie
mirando. La interfaz web decide qué agente recibe cuál; no las edita.


## Instalación

Un instalador por distribución, y los dos aceptan las mismas tres flags.
Ejecutalo como `root`.

### En Debian

> **systemd tiene que estar corriendo en la máquina.** Ejecutá antes
> `systemctl is-system-running`: si imprime “System has not been booted with
> systemd as init system (PID 1). Can't operate.”, pará acá. Cada servicio que
> se instala es una unidad de systemd, así que no habría nada que los
> arrancara, y el instalador se niega por eso en vez de dejarte una
> instalación que no sirve nada.

```bash
curl -fsSL https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-debian.sh \
  | bash -s -- --install --email tu@ejemplo.com
```

Si no tenés `curl` —un Debian mínimo no suele traerlo, ni tampoco `wget`—,
instalalo antes, o la línea de arriba imprime `curl: command not found` y se
queda ahí:

```bash
apt-get update && apt-get install -y curl
```

O descargalo primero y leelo antes de ejecutarlo, que es mejor costumbre:

```bash
wget https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-debian.sh
less install-update-reinstall-debian.sh
chmod +x install-update-reinstall-debian.sh
./install-update-reinstall-debian.sh --install --email tu@ejemplo.com
```

### En Alpine Linux

Las mismas tres flags, otro script: escribe servicios de OpenRC en vez de
units de systemd. Una sola línea, con `wget` y canalizada a `sh`, porque un
Alpine recién instalado no tiene `curl` ni bash, y esos dos sí los trae
BusyBox:

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

O bajarlo antes y leerlo antes de ejecutarlo:

```bash
wget https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-alpine.sh
less install-update-reinstall-alpine.sh
chmod +x install-update-reinstall-alpine.sh
./install-update-reinstall-alpine.sh --install --email tu@ejemplo.com
```

Una vez andando hay dos diferencias, y las dos son cosa del sistema, no una
decisión:

- **No hay navegador.** Playwright no publica compilación para musl y Alpine
  no lo empaqueta, así que `browser.open` y los demás lo dicen cuando un
  agente llama a uno. `web.fetch` y `rss.fetch` funcionan igual que en
  cualquier lado.
- **`rc-status` en lugar de `systemctl status`**, y `rc-service boa-web
  restart` en vez de `systemctl restart boa-web`.

El instalador:

1. Crea el usuario de sistema `boa` y el árbol de carpetas bajo `/opt/boa/`.
2. Instala las dependencias de Python en `/opt/boa/venv/`.
3. Genera un certificado TLS autofirmado si no hay uno de Let's Encrypt.
4. Pregunta si servir la aplicación en 11080/11443 con un HAProxy delante en
   el 80 y el 443, o directamente en el 80 y el 443. Con `--ports
   proxied|direct` se responde de antemano. La respuesta se recuerda, así que
   un `--update` no vuelve a preguntar ni la cambia en silencio.
5. Crea un agente: `manager`, el orquestador. Todo lo demás son ejemplos que
   se eligen al apretar **+**: `webnavigator`, `oswatcher`, `mailwatcher` y
   otros, un archivo Markdown cada uno en `backend/agents/examples/`. La primera opción
   que se ofrece es el agente vacío; los ejemplos van debajo.
6. Instala y arranca seis servicios: units de systemd en Debian, servicios
   de OpenRC supervisados con `supervise-daemon` en Alpine.
7. Escribe lo que hizo, y tu contraseña de acceso, en
   `/opt/boa/logs/install.log` (de root, modo 0600).

El correo que indiques será el único login. La contraseña se genera sola;
leela con:

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

## Un navegador para cada agente

Se instala por defecto: sin él, un agente puede leer una página pública y nada
más. Son unos 600 MB de Chromium, así que el instalador lo pregunta una vez, y
una instalación con poco disco puede decir que no:

```bash
./install-update-reinstall-debian.sh --update --browser no    # dejarlo fuera
./install-update-reinstall-debian.sh --update --browser yes   # volver a ponerlo
```

Toda esta sección es de Debian. En Alpine no hay navegador en absoluto:
Playwright no publica ninguna versión para musl, así que la flag se acepta y
las herramientas de navegador lo dicen cuando un agente llama a alguna.

El navegador en sí es una única copia, en `/opt/boa/playwright/`, propiedad de
root y de sólo lectura para todos los demás. Lo que **no** se comparte es el
perfil:

```
/opt/boa/agents/001/browser/profile/     agent-001, 0700
/opt/boa/agents/002/browser/profile/     agent-002, 0700
```

Así que si el agente 001 inicia sesión en un sitio, el 002 no queda dentro, y
una sesión sobrevive hasta la siguiente ejecución porque las cookies están en
disco. Esa separación es la del kernel —la misma carpeta home 0700 en la que
vive todo lo demás de un agente— y es justo lo que un producto alojado no puede
ofrecer cuando todos sus agentes comparten una máquina.

Siempre sin interfaz gráfica, y `browser.open` rechaza las direcciones privadas
exactamente igual que `web.fetch`: a un agente que lee una página hostil no se
le puede convencer de que abra el router.

## Abrirlo

El HAProxy propio de la aplicación escucha en `127.0.0.1:11443` (HTTPS) y
`127.0.0.1:11080` (HTTP, que redirige). Esos puertos no son accesibles desde
fuera del servidor: el HAProxy de la máquina es el que sirve a la LAN, y manda
al 11443 con `send-proxy-v2`, así que la IP real del cliente no se pierde.

Con esa configuración puesta, abrí:

```
https://tu-servidor/
```

El certificado es autofirmado salvo que tengas certificados de Let's Encrypt en
`/opt/boa/certificates/`, así que el navegador te avisará una vez.

### Cómo tiene que estar el HAProxy de la máquina

El backend que apunta a esta aplicación necesita dos cosas:

```
backend https-out
  mode tcp
  server srv-https-out 127.0.0.1:11443 check send-proxy check-send-proxy
```

- **`send-proxy`**, para que la IP real del cliente llegue a la aplicación. Sin
  él, todas las peticiones parecen venir de 127.0.0.1 y el límite de intentos
  de login deja de ser por dirección.
- **Sin `option ssl-hello-chk`.** Su ClientHello es anterior a TLS 1.2, así que
  un backend que exija TLS 1.2 —este, y cualquier Apache o nginx moderno— falla
  el check y queda marcado como caído para siempre. El síntoma es un 503 de un
  servicio que funciona perfectamente. Un `check` a secas ya comprueba que el
  puerto responde.

## Primeros pasos

1. Entrá con tu correo y la contraseña generada.
2. Apretá **+** en la barra lateral para crear tu primer agente.
3. Elegí su proveedor y su modelo. Para Ollama en la misma máquina, los valores
   por defecto ya son correctos.
4. Si es un proveedor de nube, escribí la clave de API en el home del agente:
   ```bash
   mkdir -p /opt/boa/agents/001/keys
   echo "sk-..." > /opt/boa/agents/001/keys/anthropic.key
   chown -R agent-001:agent-001 /opt/boa/agents/001/keys
   chmod 700 /opt/boa/agents/001/keys
   chmod 600 /opt/boa/agents/001/keys/anthropic.key
   ```
5. Escribí su prompt de sistema: para qué sirve y qué significa «terminado».
6. Dale las herramientas que necesite. Empezá por las de kanban.
7. Apretá **Ejecutar ahora** y mirá el tablero.
8. Cuando haga lo que querés, dale una programación.

## Servicios

| Servicio | Se ejecuta como | Qué hace |
|---|---|---|
| `boa-proxy` | `boa` | HAProxy: termina TLS en el 11443, redirige el 11080 y es lo único que escucha en un puerto |
| `boa-web` | `boa` | La interfaz web y la API, en un socket Unix detrás del proxy |
| `boa-exec` | `root` | Crea usuarios, instala crontabs, lanza ejecuciones |
| `boa-agent-api` | `boa` | La puerta por la que los agentes llegan al tablero y a los canales |
| `boa-buzzer` | `boa` | Vigila el tablero y despierta a un agente cuando vence una tarjeta |
| `boa-telegram` | `boa` | Escucha en Telegram, para que puedas responderle a un agente desde el celular |

```bash
systemctl status boa-proxy boa-web boa-exec boa-agent-api boa-buzzer boa-telegram
journalctl -u boa-exec -f
```

Los mismos seis en Alpine, donde son servicios de OpenRC supervisados con
`supervise-daemon` y lo que imprimen va al log del sistema:

```bash
rc-status
rc-service boa-exec status
tail -f /var/log/messages | grep boa
```

## Seguridad

El diseño da por hecho que algún agente acabará haciendo algo que no
pretendías, porque es un modelo de lenguaje con una shell.

- **Cada agente es un usuario de Linux distinto**, y su home es `0700`. Los
  agentes no pueden leer los archivos, los prompts ni las claves de los demás.
- **`/opt/boa/agents/` es `0711`**, así que ningún agente puede siquiera listar
  qué otros agentes existen.
- **Ningún agente se ejecuta como root, nunca.** Sólo `boa-exec` lo hace, y
  acepta una lista cerrada de diez operaciones por un socket Unix. Entre ellas
  no está «ejecuta este comando».
- **Los agentes nunca ven las credenciales de los canales.** Un token de bot no
  es un mensaje: es autoridad permanente para enviar todo lo que ese bot pueda
  enviar. Los agentes le piden a la API de agentes que envíe, y ella envía.
- **Los agentes sólo tocan sus propias tarjetas.** Leer el tablero es común;
  modificarlo no.
- **`web.fetch` rechaza las direcciones privadas**, comprobando la IP resuelta
  y volviendo a comprobarla en cada redirección, para que un agente que lea una
  página hostil no pueda ser convencido de llamar a tu red interna.

Está pensado para una LAN y no debería exponerse a Internet.

## Documentación

- [doc/MANUAL.es-AR.md](doc/MANUAL.es-AR.md) — cómo usarlo, en el día a día.
- [doc/CODE.es-AR.md](doc/CODE.es-AR.md) — cómo está construido, para
  desarrolladores y para modelos de IA.
- `/api/doc/` en el servidor en marcha — la referencia completa de la API.

Otras versiones: [README.md](README.md) (inglés),
[README.es-ES.md](README.es-ES.md) (español de España).

## Licencia

Consultá el repositorio.
