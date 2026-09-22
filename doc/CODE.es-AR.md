# CODE.md

Referencia técnica de Bunch of AIgents. Escrita para consultarse de forma
quirúrgica: salta a la sección que necesites, no lo leas de principio a fin.

## Índice

1. [Arquitectura y decisiones de diseño](#1-arquitectura-y-decisiones-de-diseño)
2. [Mapa de módulos](#2-mapa-de-módulos)
3. [Índice de símbolos clave](#3-índice-de-símbolos-clave)
4. [Flujos principales](#4-flujos-principales)
5. [Mapa de entradas y rutas](#5-mapa-de-entradas-y-rutas)
6. [Análisis de impacto](#6-análisis-de-impacto)
7. [Puntos de extensión](#7-puntos-de-extensión)

---

## 1. Arquitectura y decisiones de diseño

Esta es la parte que no se puede deducir del código, así que es la que merece
la pena leer.

### La premisa

Aquí un agente es un modelo de lenguaje con una shell en un servidor,
despertado por cron y sin nadie mirando. Todas las decisiones estructurales
salen de tomarse eso en serio: el modelo acabará haciendo algo no previsto, así
que la pregunta no es cómo impedirlo, sino a qué puede llegar cuando ocurra.

### Un usuario de Linux por agente

El agente `007` es el usuario de sistema `agent-007`, propietario de
`/opt/boa/agents/007/` con modo `0700`. El aislamiento entre agentes es el del
kernel, no un sandbox escrito en Python. Un agente no puede leer el prompt, el
historial ni la clave de API de otro agente porque lo dice el sistema de
archivos.

`/opt/boa/agents/` es a su vez `root:root 0711`: atravesable, no listable. Un
agente no puede enumerar a los demás, sólo fallar al abrir rutas que adivine.

Esta decisión es la razón de que `bash.run` no necesite lista blanca. Una lista
negra sobre una shell es teatro —cualquier cosa que pueda ejecutar `sh` puede
ejecutar lo que la lista nombre—, mientras que una cuenta de usuario es una
frontera que impone el kernel.

### Lo que un agente NO puede reescribir de sí mismo

El home es del agente, 0700, y eso es lo que se busca: ahí viven su memoria, su
journal, su conversación y cualquier script que escriba. Tres archivos de
dentro no son asunto suyo, y están FUERA del home, en
`/opt/boa/agents-config/xxx/`, que es `root:agent-xxx 0750` bajo un padre
`root:root 0711`.

| Archivo | Por qué no es del agente |
|---|---|
| `info.json` | Qué herramientas tiene concedidas y cuánto puede gastar |
| `system-prompt.md` | La definición de lo que se supone que hace |
| `api-token` | Con qué se identifica ante la API de agentes |

Lo que hace que esto funcione NO es de quién son los archivos: es de quién es
el DIRECTORIO. El permiso de escritura de un directorio es lo que decide si un
archivo de dentro se puede borrar y reemplazar, así que un agente dueño del
directorio podría borrar `info.json` y escribir el suyo fuera de quien fuera el
archivo. Puede entrar y leer; no puede crear, renombrar ni borrar nada ahí.

**Y esa regla vale para el cajón igual que para lo que hay dentro**, que es
por lo que ya no viven en `agents/xxx/config/`. Esa ruta era una entrada del
HOME, el home es del agente a 0700, y renombrar una entrada sólo exige
permiso de escritura en el padre: el modo de lo que se renombra no se
consulta nunca. Así que el agente no podía editar `info.json` y sí podía
hacer esto:

    mv ~/config ~/config-old && mkdir ~/config && echo '...' > ~/config/info.json

y que se leyera el sustituto. Sacar el cajón del home deja todos los
directorios del camino en manos de root. Del traslado se siguen dos cosas:

  - **Ya no hay respaldo al home.** Lo había, para que una actualización no
    fuera un servicio que deja de responder antes de que corra la migración, y
    era en sí mismo la vía de escape: bastaba con esconder el archivo real
    para que se leyera el del agente. Ahora el daemon migra al arrancar,
    además de hacerlo el instalador, así que no queda nada que cubrir.
  - **Borrar un agente borra también su configuración.** Ya no está dentro del
    home que se lleva `userdel --remove`, y dejarla ahí sería entregársela al
    siguiente agente que reciba ese id.

`fOpenProtectedAgentFile` es la segunda respuesta a la misma pregunta: abre con
`O_NOFOLLOW` y comprueba SOBRE EL ARCHIVO ABIERTO que es un archivo regular, de
root, y que nadie más puede escribirlo. Eso es lo que sobrevive a un chmod
equivocado durante una actualización o a una restauración con el dueño mal.

Se midió antes de arreglarlo, en una instalación real: un agente se añadió
`mail.read` a su propio `info.json` y el daemon privilegiado lo dio por
concedido, o sea que podía concederse el buzón, los canales o subirse sus
techos. Y podía reemplazar su prompt por «ignora todas tus reglas», que se
habría quedado así en todas sus ejecuciones siguientes.

El aislamiento ENTRE agentes no necesita nada de esto: `/opt/boa/agents/` es
`root:root 0711` y cada home es 0700, así que ya lo rechaza el kernel. Por eso
sigue siendo cierto aunque una herramienta tenga un fallo.

### Lo que root lee del home

El diario, la memoria y el chat son archivos del propio agente: los escriben
sus propios procesos, en su propio home 0700, y los lee el demonio
privilegiado como root, que lee lo que le pongan adelante. Medido sobre el
código anterior a esto: un FIFO llamado `runs.jsonl` dejaba colgado para
siempre el hilo del demonio que lo abría, y como la lista de agentes lee el
diario de todos, cada pedido posterior de esa lista perdía un hilo más; un
enlace llamado `memory.md` que apuntara a cualquier archivo de la máquina
hacía que root entregara ese archivo a la interfaz; y un enlace a algo sin
final hacía que root leyera hasta que lo mataran.

Así que los tres se leen con `fReadAgentOwnedFile`, que es el hermano de
`fOpenProtectedAgentFile` para los archivos que SÍ son del agente:
`O_NOFOLLOW` rechaza un enlace en la propia apertura, `O_NONBLOCK` impide que
un FIFO retenga la apertura hasta que alguien escriba en él, y las
comprobaciones se hacen sobre el descriptor abierto - archivo normal, propiedad
del usuario del agente - así que nada puede cambiarse entre la comprobación y
la lectura. Nunca lee más de un tope, aplicado a lo que se lee y no sólo a lo
que dijo `fstat`, porque el agente puede seguir agregando mientras se lee:
32 MB para el diario y para el chat, leídos desde el FINAL cuando el archivo
es mayor, porque las líneas más nuevas son las que muestra un historial; 1 MB
para la memoria, cortada con la misma marca `[truncated]` que deja `fWrite`.
Un byte malo cuesta una línea, no la lectura.

Lo que se rechaza se dice, no se traga: `read_run_journal`, `read_chat` y
`read_memory` fallan con el motivo, para que el operador sepa que algo de ese
home no lo escribió la aplicación. La única excepción es `read_usage_summary`
para todos los agentes, de donde se dibuja la barra lateral: ahí un diario
ilegible le cuesta a ese agente sus totales, con el motivo al lado, y a nadie
más los suyos.

### Lo que viaja en la línea de órdenes

El demonio arranca una ejecución como el agente con `Popen`, y el mensaje que
el dueño había escrito, o el prompt que construye una tarjeta vencida, era uno
de sus argumentos: `--chat-message <texto>`, `--prompt <texto>`. La línea de
órdenes de un proceso la puede leer cualquier usuario de la máquina a través
de `/proc/<pid>/cmdline`, y un agente con `bash.run` es un usuario de la
máquina. Medido en el Debian de pruebas: `ps` ejecutado como `agent-001`
mostró el mensaje que el dueño acababa de mandar a `agent-000`, durante toda
la vida de esa ejecución, que por defecto es de hasta cinco minutos.

Así que el texto va por la entrada estándar del hijo y la línea de órdenes
sólo lleva `--chat-message-on-stdin` o `--prompt-on-stdin`. `fStartRunner` es
el único lugar que arranca un runner: rechaza un texto más largo que
`cMaxStdinPayloadBytes` antes de que exista proceso alguno, porque ese tope
está por debajo de los 64 KiB del búfer de una tubería y una escritura que
entra en el búfer nunca espera al hijo; este demonio no espera a los runners.
Un hijo que ya no está cuando llega la escritura, un intérprete que falla al
importar, es una tubería rota y no un fallo del demonio. Del otro lado, el
runner lee el texto con el mismo tope, rechaza un mensaje de chat vacío en
vez de responder a una pregunta que nadie hizo, y cierra el turno para el que
se lo arrancó cuando rechaza, para que la conversación no se quede esperando
para siempre. `--prompt` y `--chat-message` se quedan, para una ejecución
arrancada a mano desde una terminal.

### Lo que una ejecución puede hacerle a la máquina

Los techos de `info.json` - tokens, pasos, segundos, ejecuciones al día - los
hace cumplir el runner, y el runner es un programa que el agente maneja. Lo
que se cumple cuando el programa es lo que ha fallado lo hace cumplir el
kernel, en dos capas.

El runner baja sus propios límites de recursos antes de hacer nada,
`fApplyResourceLimits`, desde el punto de entrada y no desde `fMain`: las
pruebas llaman a `fMain` en el mismo proceso, y un RLIMIT_NPROC bajado
dentro de la sesión de un desarrollador con miles de hilos ya corriendo deja
esa sesión sin poder hacer fork. Todo proceso que arranca la ejecución los
hereda: RLIMIT_NPROC a 1024, contado sobre el uid del agente en conjunto,
así que una fork bomb desde `bash.run` se para en el número y no en la
máquina; los hilos también cuentan, y por eso no es menor, porque un
navegador son unos cientos de ellos; sin archivos core; ningún archivo de
más de 4 GiB. RLIMIT_AS no: Chromium reserva espacio de direcciones por
decenas de gigabytes y no arrancaría. Esa capa es la misma en Debian y en
Alpine, y es la única que tiene una ejecución arrancada por el crontab del
propio agente.

Donde systemd es PID 1 el demonio agrega la segunda: `fStartRunner` mete la
ejecución en un scope transitorio propio, `boa-agent-<id>-<aleatorio>.scope`
bajo `boa-agents.slice`, con `TasksMax=1024` y `MemoryMax=2G`. `systemd-run
--scope` hace exec de la orden, así que el pid sigue siendo el del runner y
`/proc` sigue mostrando su línea de órdenes; `setpriv` es lo que baja al
agente, porque systemd-run tiene que ser root para crear el scope. Medido
antes de que fuera así: una ejecución era hija de `boa-exec.service`, en el
cgroup del propio demonio, y un agente desbocado gastaba el TasksMax del
demonio y lo dejaba sin poder hacer fork. El scope es también lo que termina
con lo que una ejecución dejó atrás: `bash.run` señala su propio grupo de
procesos, así que una orden que llamara a `setsid`, o un hijo en segundo
plano de una que acabó a tiempo, sobrevivía a la ejecución; `fWatchRunner`
espera a la ejecución y para su scope, que alcanza todo lo que la ejecución
arrancó se haya movido donde se haya movido. Una ejecución a la que mataron
- el límite de memoria, un operador - no escribió nada al salir, así que el
mismo hilo apunta el fin en el diario y cierra el turno en el chat; una que
salió por su cuenta ya hizo las dos cosas, y el turno se comprueba en vez de
suponerse.

### Dónde viven las claves de los proveedores

Las claves que comparten todos los agentes están en
`/opt/boa/config/apikeys/<proveedor>.key`, propiedad de `boa`, la carpeta en
`0700` y los archivos en `0600`.

Con 0750 y 0640 los agentes ya quedarían afuera, porque ningún usuario de
agente está en el grupo `boa`, pero eso depende de que la lista de grupos de
cada agente siga vacía durante toda la vida de la instalación, y está a un
`usermod -aG` de dejar de ser cierto. Un modo que no le da nada al grupo no
depende de eso. `api_keys.fWrite` fija ambos modos en cada escritura, y no
sólo al crear, así que una carpeta que viene de una instalación vieja queda
cerrada la primera vez que se guarda una clave.

La carpeta se llamaba `keys` hasta que se renombró: se leía como «las llaves
de esta instalación» y estaba a una errata de la `keys/` que cada agente tiene
en su home, que es otra cosa y que el agente SÍ puede leer: su propia clave,
puesta ahí para facturarlo a otra cuenta. El instalador mueve la carpeta
vieja con `--update` y sólo la borra cuando queda vacía.

Nada de esto impide que un agente tenga la clave del proveedor con el que se
ejecuta: la API de agentes se la entrega, la necesita para hacer la llamada, y
un agente con `bash.run` podría imprimirla. Lo que impide es que lea las
claves de los proveedores que no usa.

### Siete procesos, uno con privilegios

| Proceso | Usuario | Por qué existe |
|---|---|---|
| `boa-proxy` | `boa` | HAProxy: termina TLS y sirve los dos puertos |
| `boa-web` | `boa` | Sirve la interfaz y la API, en un socket Unix |
| `boa-exec` | `root` | El único componente con privilegios |
| `boa-agent-api` | `boa` | Guarda lo que los agentes pueden usar pero no leer |
| `boa-buzzer` | `boa` | Despierta a un agente cuando vence una de sus tarjetas |
| `boa-telegram` | `boa` | Escucha en Telegram y le entrega a un agente lo que llega |
| `boa-discord` | `boa` | Lo mismo, para un canal de Discord |

Los cuatro últimos son `boa` y no root a propósito: los cuatro quieren que se
haga algo como el usuario propio de un agente —lanzar una ejecución, escribir
en un home 0700— y los cuatro se lo piden a `boa-exec` en vez de recibir el
privilegio. Un servicio al que se puede llegar desde fuera, como en la práctica
ocurre con los dos listeners, es el último que debería tenerlo.

### Un entorno virtual no es reubicable

`python3 -m venv <ruta>` escribe `<ruta>` en el shebang de cada script de
consola que se instale después dentro de él, en la línea `VIRTUAL_ENV` de los
scripts de activación y en la línea `command` de `pyvenv.cfg`. El entorno se
construye en `venv.new` y se renombra a `venv`, así que las tres cosas acaban
nombrando un directorio que ya no existe.

Medido en un Debian 13 real y en un Alpine 3.24 real: las dos instalaciones
terminaron, las dos imprimieron “Installation finished” y las dos dejaron
`boa-web` reiniciándose cada cinco segundos con

```
status=203/EXEC - Failed to execute /opt/boa/venv/bin/gunicorn:
No such file or directory
```

El archivo estaba ahí. Su primera línea nombraba
`/opt/boa/venv.new/bin/python3`, que no.

`fBuildVirtualEnv` tenía una comprobación para exactamente esta clase de fallo
y la pasó, porque ejecuta `bin/python3`, que es un ENLACE SIMBÓLICO al
intérprete del sistema y responde desde donde esté. Sólo un script de consola
lleva la ruta grabada. Por eso la comprobación ejecuta ahora también
`bin/gunicorn --version`, que es el archivo que ejecuta la unidad de servicio,
y `fRepointVirtualEnv` reescribe las tres rutas guardadas mientras el entorno
sigue con su nombre de construcción. La reescritura se comprueba en vez de
darse por hecha: si un pip futuro escribe sus scripts de consola de otra
forma, el instalador se para ahí.

### Una actualización que falla deja algo funcionando

Tres etapas, y el orden es la reparación.

Una actualización paraba los servicios, borraba `webapp/` y sólo entonces
ejecutaba pip. Un pip que fallaba —sin red, un índice caído, una rueda que no
compila— dejaba una instalación con los servicios parados y el código
borrado: una máquina que funcionaba hace un minuto y que necesita que alguien
se dé cuenta y la recupere a mano.

| Etapa | Qué pasa | Qué cuesta un fallo |
|---|---|---|
| Preparar | Se hacen las preguntas, se instalan las dependencias, se descarga el código, y el virtualenv nuevo se CONSTRUYE al lado del que está funcionando y se comprueba que importa | Nada. La versión anterior sigue funcionando y sin tocar |
| Cambiar | Parar, `webapp/` pasa a `webapp.previous`, `venv` a `venv.previous`, se ponen los nuevos, arrancar | Deshacible: las dos versiones anteriores siguen en disco |
| Verificar | `curl` le pide a la aplicación la página de inicio de sesión, quince veces en treinta segundos | `fRollBack` devuelve las dos y las arranca otra vez |

Ese `curl` envía PROXY protocol sólo en modo `proxied`. En modo `direct` el
bind no lleva `accept-proxy`, así que una cabecera PROXY cae en medio del
handshake TLS y la petición no obtiene respuesta alguna. Se enviaba en los dos
modos, con lo que todo `--install --ports direct` terminaba en «did not
answer» sobre una instalación que servía páginas, y todo `--update` en modo
directo se deshacía a sí mismo. Comprobado pasando las dos máquinas de pruebas
a `direct` y de vuelta: con la opción atada al modo, las dos respondieron 200
en el 443 y después en el 11443. Una prueba ejecuta `fVerifyInstallation` de
los dos instaladores contra un `curl` que graba sus argumentos, una vez por
modo, y comprueba que la opción está en uno y falta en el otro.

Cuando ese `curl` no recibe respuesta, `fExplainWhyItDoesNotAnswer` escribe
qué aspecto tenía la máquina en ese momento, y lo escribe en el mismo archivo
al que apunta el error: qué dice el propio curl —preguntado otra vez con
`-sS`, para distinguir una conexión rechazada de un handshake fallido y de una
petición que expira, porque `000` no es un código HTTP sino curl diciendo que
nunca recibió ninguno—, el estado de cada uno de los siete servicios, si hay
algo escuchando en el puerto, y las últimas quince líneas de `boa-proxy.log`,
`boa-web.log` y el `error.log` de gunicorn. `fReportServiceStates` es la mitad
que cambia entre los dos: `rc-service ... status` en Alpine, `systemctl
is-active` más el diario de `boa-web` y `boa-proxy` en Debian.

Existe porque una primera instalación en un Alpine recién puesto terminó en
“The application did not answer on port 11443 (last code: 000)” y el log no
contenía nada más al respecto: ni qué servicio estaba caído, ni si el puerto
estaba ocupado, ni una sola línea de lo que había impreso gunicorn. El único
archivo que nombra el error no podía responder a la pregunta por la que se
abría. Qué buscar en él: un servicio que se declara arrancado junto a “nothing
is listening on port 11443” es un proceso que muere y vuelve a arrancarse,
porque un servicio supervisado que muere apenas arranca lo da por arrancado la
propia orden que lo arrancó. Cuatro pruebas EJECUTAN las dos funciones: contra
un `curl` que se niega a conectar, contra un `ss` que ocupa el puerto y otro
que no, y contra un `rc-service` y un `systemctl` que contestan “stopped” y
devuelven un fallo.

`fRollBack` arranca los servicios en una SUBSHELL, y el `|| true` de al lado
no basta por sí solo: `fStartServices` llama a `fDie` cuando un servicio no
levanta, `fDie` llama a `exit`, y `exit` termina la shell se escriba lo que se
escriba al lado. Medido en un Alpine real: OpenRC tiró `boa-proxy` mientras
`boa-web` daba tumbos, el arranque que hace el propio rollback perdió la
carrera por el cerrojo del servicio, y el instalador murió DENTRO de
`fRollBack`. El rollback había funcionado —la versión anterior estaba de
vuelta y respondiendo—, pero lo que se le dijo al operador fue “The boa-proxy
service would not start”, sin una palabra sobre que se acababa de deshacer una
actualización. A esas alturas el relato de lo que pasó es lo único que tiene
el operador.

La versión anterior la borra `fFinishUpdate`, y sólo después de que la nueva
haya respondido.

`fRollBack` corría en un solo lugar: cuando fallaba ese `curl` final. Entre
`fStopServices` y esa comprobación hay una docena de pasos que pueden morir -
un archivo de certificado que falta, una configuración de proxy que HAProxy no
acepta, un servicio que no se instala - y cada uno dejaba los servicios
parados, el código nuevo puesto y `webapp.previous` en disco sin nadie que lo
devolviera. El mensaje decía qué había fallado y ni una palabra de que la
máquina estaba caída. Así que `fDoUpdate` pone `vUpdateSwitched` justo antes
de parar los servicios, y `fCleanup` - el trap de EXIT, que corre termine como
termine el proceso hijo - deshace el cambio cuando encuentra la marca puesta y
un código de salida distinto de cero. Las dos salidas del cambio la quitan: el
propio `fRollBack`, para que el camino explícito no deshaga dos veces, y
`fFinishUpdate`, porque una vez que la versión nueva respondió no queda nada
a lo que volver. Medido en las dos máquinas de pruebas con la clave privada
escondida: «Missing certificate files», «Putting the previous version back»,
los siete servicios arriba y la página de inicio de sesión respondiendo 200 con
el código anterior. Una prueba ejecuta los `fCleanup`, `fRollBack` y
`fFinishUpdate` reales de cada instalador en tres salidas: después del cambio,
antes, y después del final.

`--install` y `--reinstall` no tienen versión anterior que guardar, así que no
tienen etapa de Cambiar ni rollback, pero sí Verifican. Antes terminaban en
`fWriteCredentialsFile`, y “Installation finished” se imprimió en dos máquinas
reales cuyo servicio web se reiniciaba cada cinco segundos: nadie le había
preguntado nunca nada a la aplicación. Ahora piden la misma página de inicio
de sesión, y cuando no llega lo dicen y nombran el log, porque en esa máquina
no hay nada a lo que volver.

`pip` está fijado. `--upgrade pip` sin versión significaba que dos
actualizaciones del mismo código podían resolver distinto, que es justo para
lo que se fijaban los requisitos. Lo que sigue sin fijarse son las
dependencias TRANSITIVAS: por eso se guarda un `pip freeze` en el entorno y la
siguiente actualización imprime lo que se movió, que es la única forma de que
alguien se entere.

### Una instalación que se quedó a medias

`fIsInstalled` daba una máquina por instalada en cuanto existían
`webapp/backend` y el usuario `boa`, que es antes del entorno virtual, de los
certificados, de la base de datos y del administrador. Una instalación que
moría en pip, con una red que se cae, recibía después «already installed» de
`--install` y una muerte en lo que faltara de `--update`, y sólo
`--reinstall --yes` la sacaba, sin que nada se lo dijera al operador.

Una instalación terminada deja ahora `/opt/boa/installed`, que escribe
`fMarkInstalled` sólo después de que `fVerifyInstallation` haya recibido su
página: una instalación que está puesta y no responde no está terminada, y
una actualización que se deshizo no es la versión nueva. Sin la marca, las
cuatro cosas que una instalación terminada siempre tiene, el código, el
usuario, `venv/bin/gunicorn`, `db/boa.sqlite` y `certificates/privkey.pem`,
hacen de marca, así que una instalación anterior a que existiera sigue
contando y recibe la suya en la siguiente actualización. Todo lo demás que
hace `--install` ya es seguro hacerlo dos veces: el usuario se crea sólo si
falta, el entorno se construye al lado del viejo, los certificados se
conservan si están, el administrador se borra y se escribe otra vez con la
contraseña nueva. Así que una instalación a medias se termina ejecutando
`--install` otra vez, y `--update` dice exactamente eso cuando se encuentra
una. De paso, `fGeneratePassword` pasó a ir después de
`fInstallDependencies` en el instalador de Debian, donde iba al revés:
`openssl` es Priority: optional en Debian, y una imagen mínima generaba la
contraseña antes de instalar el paquete que la genera.

### Todo lo que ejecuta el instalador llega a su log

`fLog` escribía sus propias líneas en `install.log` y nada más. apt, pip, la
validación de HAProxy y cualquier otro subproceso escribían en la terminal, así
que una instalación fallida dejaba un log con «Installing the dependencies.» y
ni una palabra del error de apt que lo explicaba, que es exactamente el detalle
por el que alguien abre ese archivo.

`fStartCapturingOutput` redirige la salida y el error de esta shell a un FIFO
que `tee` copia al log y a la terminal. Un FIFO y no `exec > >(tee ...)`, que
es sólo de bash y Alpine arranca sin bash, ni una tubería alrededor de `fMain`,
que lo metería en una subshell y desharía el `fMain & wait` que mantiene
errexit vivo.

Dos consecuencias, y hubo que resolver las dos:

`fLog` imprimía la línea Y la añadía él mismo al log. En cuanto la salida
estándar es un `tee` que añade a ese mismo archivo, la segunda escritura es un
duplicado: una instalación de 90 líneas producía un log de 185, con cada línea
dos veces. Ahora `fLog` escribe en el archivo sólo mientras la captura no está
en marcha.

`tee` mantiene el log abierto por INODO. Un `--reinstall` borra el árbol
entero, log incluido, y vuelve a dejar una copia nueva, así que desde ese
momento `tee` añade a un inodo que ya no tiene nombre; y con `fLog` sin
escribir en el archivo, eso sería toda la segunda mitad de la reinstalación,
con la contraseña generada dentro. `fRestartCapturingOutput` apunta la captura
al archivo que existe ahora.

### Dos instaladores, una sola aplicación

`deploy/install-update-reinstall-debian.sh` escribe units de systemd, y
**necesita que systemd sea el PID 1 de la máquina en marcha**: un Debian
arrancado con otra cosa no es un destino válido, y el instalador lo rechaza en
vez de instalar en una máquina donde no arrancaría nada.
`deploy/install-update-reinstall-alpine.sh` escribe servicios de OpenRC en
`/etc/init.d/`, a partir de `deploy/openrc/`, y no necesita nada por
adelantado: instala OpenRC él mismo cuando la máquina no lo tiene. Los dos instalan los mismos seis
procesos, el mismo árbol bajo `/opt/boa` y el mismo modelo de usuarios; un test
compara los dos paso a paso y falla en cuanto uno gana un paso que el otro no
tiene.

No están escritos en el mismo lenguaje, y es a propósito. El de Debian es bash,
como todo lo demás aquí. El de Alpine es shell POSIX, con `#!/bin/sh`, porque
un Alpine recién instalado no tiene bash: con `#!/bin/bash` el kernel buscaría
un intérprete que no está, y

    curl -fsSL <raw-url> | bash -s -- --install

fallaría antes de leer una línea, justo en la máquina que más necesita la
instalación de una sola línea. Siendo POSIX corre igual bajo BusyBox ash, dash
y bash, así que el mismo archivo funciona canalizado a `sh` en un Alpine pelado
y a `bash` en uno que ya la tenga. Sigue instalando bash —cada agente recibe una
shell bash—, sólo que ya no la necesita para arrancar. Lo que eso cuesta son los
arrays, `[[ ]]`, `${var//x/y}` y `<(...)`; `local` se queda, porque las tres
shells lo tienen, y `pipefail` se pide en una subshell antes de activarlo,
porque dash no lo tiene. Un test rechaza cada una de esas construcciones, ya que
una función de shell que no está falla en el momento de instalar, en la máquina
de otro.

Lo que Alpine necesita y Debian no, y por qué ninguno sobra:

| | Por qué |
|---|---|
| `shadow` | El daemon privilegiado llama a `useradd --home-dir --create-home --shell`. El `adduser` de BusyBox no tiene ninguna de esas opciones, y un agente que no se puede crear es la aplicación entera sin funcionar |
| `bash` | Es la shell que recibe cada agente y por la que pasa `bash.run`. Alpine viene sin ella, que es también por lo que el instalador de Alpine es el único archivo del proyecto escrito en shell POSIX y no en bash: con `#!/bin/bash`, el `curl ... \| sh` sería imposible justo en la máquina que más lo necesita |
| `dcron` | Algo tiene que leer los crontabs que escribe el daemon. También es el motivo del `-d` de más abajo |
| `gcc`, `musl-dev`, `libffi-dev`, `python3-dev` | Varias dependencias no publican rueda para musl y se compilan durante la instalación |
| `libcap` | `setcap cap_net_bind_service` sobre el binario de haproxy, en modo `direct`. systemd lo daba por servicio con `AmbientCapabilities`; OpenRC no tiene equivalente |

Tres cosas hubo que cambiarlas en el código, y las tres se encontraron
instalando:

- **`crontab -u <agente>` en vez de bajar a ser el agente.** El `crontab` de
  Debian es setgid y lo puede ejecutar cualquier usuario; el dcron de Alpine
  viene `4750 root:wheel`, así que un agente que lo ejecuta recibe
  `Permission denied`. Mantener la forma anterior obligaba a meter a cada
  agente en `wheel` (el grupo que en casi todos los sistemas significa sudo) o
  a relajar un binario setuid del sistema. El daemon es root y puede nombrar
  al usuario en vez de eso.
- **`-r` o `-d` al borrarlo.** Vixie cron borra un crontab con `-r`; dcron con
  `-d`, y a `-r` responde con el modo de empleo y código 2. Probar sólo `-r`
  dejaba atrás el crontab de un agente borrado, apuntando todavía al runner de
  un usuario que ya no existía. Se prueban los dos, porque lo que decide es el
  binario instalado, no el nombre de la distribución.
- **`executable=` en `browser.conf`.** Playwright no publica compilación para
  musl, así que en Alpine el paquete se deja fuera de las dependencias y no hay
  navegador. Esa línea la lee `browser.fReadConfiguredExecutable` y es donde se
  nombraría un Chromium del sistema el día que exista un Playwright capaz de
  manejarlo.

Una más, encontrada mirando `/proc/<pid>/fd/2` en el Alpine de pruebas:
`supervise-daemon` manda la salida estándar y la de error de un proceso a
`/dev/null` si no se le dice otra cosa, y en Alpine nada más las recoge; las
unidades de Debian tienen journald para eso. Los siete servicios no
escribían nada en ninguna parte. Cada script de OpenRC nombra ahora
`output_log` y `error_log`, un archivo por servicio en `/opt/boa/logs/`,
creado como `boa` en `start_pre` para que logrotate pueda rotarlo como
`boa` sea quien sea el que escribe. `fInstallLogRotation`, en los dos
instaladores, escribe `/etc/logrotate.d/boa` para esos archivos y para los
dos de gunicorn: semanal, ocho conservados, `copytruncate` porque los dos
escritores mantienen el archivo abierto, y nunca `install.log`, que es de
root y guarda la contraseña. La otra mitad del mismo hallazgo: la pestaña
de sistema preguntaba a OpenRC por `crond`, el cron de BusyBox, cuando el
instalador pone `dcron` en su lugar, así que un Alpine sano decía que el
cron estaba parado. `fPickOpenRcCronService` pregunta por el primero de
los dos que tenga script de servicio.

Y otras dos las esquiva el instalador en vez de arreglarlas, porque son del
paquete haproxy de Alpine: no trae `/etc/haproxy/errors/` ni `/run/haproxy`
para el socket de administración. Las dos líneas se quitan de la configuración
cuando su archivo o su directorio no existe, que además es lo correcto en una
máquina donde el administrador sí los creó. Crear `/run/haproxy` se probó
primero, con un script en `/etc/local.d/` que lo rehiciera en cada arranque:
`local` se ejecuta al FINAL del arranque, así que haproxy ya había fallado
antes de que el directorio apareciera.

Hay una más que es del propio OpenRC: cachea el árbol de dependencias de los
servicios y decide si rehacerlo comparando marcas de tiempo con `/etc/init.d`.
En una reinstalación los scripts de servicio se sobrescriben dentro del mismo
segundo que la caché, así que la da por vigente y los siete servicios se quedan
fuera de ella: arrancan durante la instalación, porque `rc-service start` no
necesita el árbol, y luego no vuelven tras un reinicio, porque `openrc default`
sí. `fInstallServices` termina con un `rc-update -u` incondicional.

### Lo que cada instalador exige de la máquina, y lo que se instala él solo

El instalador de Debian se niega a ejecutarse donde systemd no es PID 1
(`fRequireSystemd`, llamado antes de instalar absolutamente nada). Todo lo que
monta lo arranca y lo mantiene vivo systemd - las siete unidades, el HAProxy de
la máquina, cron -, así que en una máquina así la instalación terminaba,
informaba de éxito y no servía nada: `systemctl` está instalado, responde
“System has not been booted with systemd as init system (PID 1). Can't
operate.” y nadie leía ese código de salida. Lo que imprime ahora es cómo
arreglarlo: instalar `systemd systemd-sysv dbus`, volver a crear el contenedor
con `/sbin/init` como comando y lanzar el instalador otra vez. Dice “volver a
crear” y no “reiniciar” porque un contenedor en marcha no puede cambiar su
PID 1.

El instalador de Alpine toma la decisión contraria con OpenRC, porque allí la
pieza que falta sí puede ponerla él: `openrc` se instala junto con el resto de
paquetes - una imagen de contenedor no lo trae, un Alpine instalado con
`setup-alpine` sí -, y `fEnsureOpenRcUsable` crea después
`/run/openrc/softlevel`, que es el archivo que el propio OpenRC nombra cuando
se niega a tocar un servicio en un sistema que él no arrancó. Con eso, los seis
servicios arrancan dentro de un contenedor. El log avisa de que no volverán
solos, porque `/run` es un tmpfs y PID 1 no es OpenRC.

Los dos no se contradicen: a systemd no se le puede hacer funcionar siendo otra
cosa que PID 1, y a OpenRC sí.

### `if ! fMain` apaga `set -e` en toda la instalación

Los dos instaladores terminan lanzando fMain como proceso hijo:

    fMain "$@" &
    vMainPid=$!
    if ! wait "${vMainPid}"; then ...

y no con `if ! fMain "$@"`, que es a lo que se parece y lo que tenían antes. Un
comando en la condición de un `if` se ejecuta con errexit suspendido, y esa
suspensión la heredan todas las funciones que llame, y las que llamen esas: la
instalación entera. Medido en una máquina sin systemd: ocho órdenes fallaron
seguidas, cada una imprimió su error, el script siguió adelante y terminó
diciendo “Installation finished”. Un proceso hijo recupera errexit, porque la
suspensión no sobrevive al fork. bash, dash y BusyBox ash se comportan igual en
las dos mitades de esa frase, y no lo recuperan ni un `set -e` dentro de la
función ni una subshell.

Dos consecuencias de ejecutar fMain en un hijo: el `trap fCleanup EXIT` se pone
también DENTRO de fMain, porque una subshell no hereda el trap EXIT de su padre
y el árbol descargado en `/tmp` se quedaría sin borrar en cada ejecución; y el
padre quita su propio trap antes de salir, para que la línea “Exited with code”
no salga dos veces.

`fHasTty` es un arreglo de la misma familia: abre `/dev/tty` y lo vuelve a
cerrar, en vez de comprobar `[ -r /dev/tty ]`. El nodo de dispositivo es
legible por modo en cualquier sistema, así que esa comprobación pasaba con
`ssh host ./installer` sin pty y el `read` que venía detrás moría con ENXIO: un
proceso sin terminal de control no puede abrirlo siquiera.

### El haproxy.cfg del paquete no es el trabajo de nadie

`fInstallMachineProxy` sustituye `/etc/haproxy/haproxy.cfg` cuando está en
modo `proxied`, y no toca un archivo que no haya escrito él sin preguntar
antes: el proxy de la máquina puede estar sirviendo otros sitios. El problema
es que el archivo que encuentra en una máquina recién instalada lo puso el
paquete haproxy, que **lo instaló este mismo instalador** un minuto antes, en
`fInstallDependencies`.

Tratar ese ejemplo como el trabajo de alguien es lo que dejaba muerto
cualquier `--install` normal: sin `--yes`, sin terminal donde contestar, y la
ejecución terminaba en «Destructive operation with no terminal to confirm on»
habiendo construido ya el árbol, el virtualenv y los certificados. Medido en
las cuatro máquinas de prueba, tanto Debian como Alpine, ejecutando
exactamente la línea que da el README.

`fMachineProxyIsPristine` se lo pregunta al gestor de paquetes en vez de
adivinarlo:

- Debian: el md5 que dpkg guardó para ese conffile (`dpkg-query -W -f
  '${Conffiles}'`) contra el md5 del propio archivo.
- Alpine: el hash que apk guardó de ese archivo, leído de
  `/lib/apk/db/installed` (la línea `Z:` bajo `R:haproxy.cfg`), contra
  `openssl dgst` del archivo. `Q1` es sha1 en base64; `Q2`, sha256.

`apk audit --system` parece la respuesta en Alpine y no lo es: medido en
Alpine 3.24, no informa de **nada** cuando `/etc/haproxy/haproxy.cfg` está
editado. La primera versión de esta comprobación se fiaba de él, y habría
sustituido el proxy de alguien sin preguntar, que es justo lo único que la
confirmación existe para evitar. Probado después con el archivo del paquete,
con una línea añadida y con el archivo que escribe este instalador.

Intacto significa que se sustituye con una línea en el log y sin preguntas.
Editado significa lo de antes: se deja en paz en un `--update`, y se confirma
y se copia a `.before-boa.<marca de tiempo>` en un install o un reinstall.

### Un solo archivo para el log y la contraseña

El instalador escribe `/opt/boa/logs/install.log` y nada más: lo que hizo y,
al final, las credenciales que generó. Antes escribía dos archivos en /root
-`app-web-install.log` y `app-web-credentials.txt`- y dos archivos en dos
sitios son dos cosas que buscar. `fMigrateInstallFiles` copia lo que haya en
los antiguos dentro del nuevo antes de borrarlos, porque la contraseña que
contienen puede ser la única copia que tenga nadie.

Tres detalles lo sostienen:

- `fLog` crea el directorio cuando no está. El log vive dentro del árbol que
  el instalador está construyendo, así que en una primera instalación no
  existe cuando se escribe la primera línea, y un `--reinstall` lo borra a
  mitad de camino.
- `fRemoveInstallation` aparta el log antes del `rm -rf /opt/boa` y lo
  devuelve después, para que un reinstall no se lleve por delante su propio
  registro.
- El archivo es `root:root 0600` dentro de un directorio de `boa` a 0750.
  `boa` puede borrarlo -eso es lo que significa ser dueño del directorio- y no
  puede leer la contraseña que hay dentro; los agentes no están en el grupo
  `boa` y no pueden ni entrar en el directorio.

La pantalla de inicio de sesión nombra esa ruta, en
`frontend/templates/login.html`, en una línea propia y coloreada con
`--colour-path`. No está en los catorce archivos de traducción: la frase de
encima sí se traduce, la ruta es la misma en todas partes, y una ruta metida
en mitad de una frase es una ruta que alguien teclea mal.

### La interfaz habla en-US hasta que alguien diga otra cosa

`fGetLanguage` lee la elección de `localStorage` y, si no hay ninguna,
devuelve `en-US`. Antes negociaba primero con `navigator.languages`, lo que
significaba que una instalación nueva hablaba el idioma del primer navegador
que la abriera: el idioma de una máquina, no una decisión. La elección está a
un control de distancia, en la esquina de la tarjeta de inicio de sesión y en
Ajustes, y se recuerda por navegador.

Dos fallos vivían en ese mismo archivo, y los dos se veían como «el formulario
de inicio de sesión no cambia de idioma hasta que lo cambias dos veces»:

- `fApplyTranslations` escribía una cadena sólo cuando el archivo cargado
  tenía esa clave, y `textContent` ya lo había sobrescrito el idioma anterior.
  Así que cambiar a en-US -que no tiene archivo, `dTranslations` es `{}`- no
  cambiaba nada, y cambiar a un idioma al que le falta una clave dejaba esa
  clave en el idioma anterior. Ahora la cadena original de cada elemento
  traducido se guarda en un `WeakMap` la primera vez que se traduce, y una
  clave sin traducción la restaura.
- `fSetLanguage` guardaba la elección y llamaba a `fLoadTranslations()` sin
  argumento, que volvía a leer la elección del almacenamiento. En una ventana
  privada el guardado lanza excepción, la lectura devuelve el idioma anterior
  y la página recarga el que ya estaba mostrando. Ahora pasa el idioma que le
  han dado.

`fLoadTranslations` lleva un número de secuencia, para que dos cambios
seguidos no puedan llegar desordenados y dejar la página en un idioma que
nadie pidió. Tres cosas suyas estaban mal, y cada una le enseñaba al usuario
un idioma que no había elegido:

- El atributo `lang` se ponía ARRIBA, antes de haber traído el archivo. Un 404
  o un error de análisis dejaba entonces las cadenas del idioma anterior en
  pantalla bajo el nombre del nuevo: `lang=fr-FR` con texto en español. Ya no
  se publica nada hasta tener el diccionario en la mano, y `fPublish` pone los
  dos a la vez porque el fallo es justamente que se separen.
- La secuencia se comprobaba ANTES de `await response.json()`. Un CUERPO lento
  de una petición anterior aterrizaba después de que una posterior hubiera
  terminado. Ahora se comprueba después de cada await, porque la secuencia
  puede moverse en cualquiera de ellos.
- Un fallo no decía nada y dejaba la página en un estado desconocido. Ahora
  cae a en-US y avisa por `fOnLoadFailed`.

### en-US.json es la fuente, y el marcado es el respaldo

El cargador cortocircuitaba `en-US` a un diccionario vacío, con el argumento
de que el marcado ya lleva el texto en en-US. Es cierto, y convertía
`en-US.json` en quinientas claves de peso muerto: se distribuía, figuraba como
catálogo, las pruebas comprobaban su paridad con los otros trece, y no lo leía
nadie. Corregir una errata ahí no cambiaba nada en pantalla, y la única forma
de averiguarlo era probar.

Ahora se pide como cualquier otro idioma. El texto del marcado se queda como
el respaldo que siempre se dijo que era: una clave que el catálogo no tenga, o
un catálogo que no cargue, siguen dejando una página legible en vez de una
página en blanco. Lo que cambió es cuál de los dos es la fuente.

### Quinientas claves no son una interfaz traducida

Cuatro clases de texto visible no llevaban ninguna clave, así que se quedaban
en inglés en los catorce idiomas:

| Qué | Cómo se traduce ahora |
|---|---|
| El título de la pestaña | `data-i18n` en `<title>`, una clave por página |
| Los fallos propios de la API | Viajan un `code` y sus `params`; el navegador escribe la frase en `fDescribeApiError`. `error` se queda para lo que viene de fuera —las palabras de un proveedor, el rechazo de un servidor de correo—, a lo que no hay que inventarle una traducción |
| Descripciones de los agentes de ejemplo | `template.desc.<id>`, con el inglés del propio archivo como respaldo, exactamente como funciona la descripción de una herramienta |
| Esquema y descripción de los temas | `theme.scheme.<esquema>` y `theme.desc.<id>`, con el mismo trato. El NOMBRE no se traduce: un tema es la paleta de alguien con un nombre, y traducir «Nord» no ayudaría a nadie a encontrarlo |

Las dos últimas significan que un ejemplo o un tema que alguien escriba para
su propia instalación conserva sus palabras en vez de desaparecer.

El desplegable de idioma de la página de inicio de sesión lista códigos
-`es-ES`, `en-US`- y no nombres de idioma. Catorce nombres, cada uno en su idioma,
dejaban el control tan ancho como la tarjeta; el código ocupa 80px, y es lo
que antes distingue quien busca el suyo en una lista de códigos. Los nombres
completos se quedan en la página de ajustes, que tiene sitio.

### La rama de la que se descarga el código

`cRepoBranch` es `main`, que es la rama real del repositorio. Era `master`, y
funcionaba sólo porque GitHub redirige el nombre antiguo después de un cambio
de nombre: una redirección que desaparece el día que exista una rama `master`
de verdad, y que nadie hace por `--repo-url file:///...`, que es como se prueban
los dos instaladores.

### Por qué la aplicación trae su propio HAProxy

El HAProxy de la máquina reenvía al puerto 11443 con `send-proxy-v2`, así que
la cabecera PROXY llega **antes** del handshake TLS. Gunicorn no puede leerla
ahí: su opción `proxy_protocol` interpreta esa cabecera mientras interpreta
HTTP, que ocurre después de terminar el TLS, así que los bytes de la cabecera
caen dentro del handshake y lo rompen con `WRONG_VERSION_NUMBER`. Esto se
descubrió desplegando, no probando.

HAProxy acepta las dos cosas en un mismo bind —`accept-proxy ssl crt ...`—, así
que la aplicación trae su propia instancia, que además es el único componente
que escucha en un puerto. Gunicorn escucha en un socket Unix, lo que significa
que no hay forma de llegar a la aplicación sin pasar por el proxy, y que la IP
real del cliente sobrevive en `X-Forwarded-For`: sin ella, el límite de intentos
de login vería 127.0.0.1 para todo el mundo y dejaría de ser por dirección.

Es HAProxy y no nginx porque el despliegue ya depende de HAProxy: ninguna
tecnología nueva para un problema que resuelve una que ya está.

El HAProxy de la máquina no debe usar `option ssl-hello-chk` en este backend: el
ClientHello de ese check es anterior a TLS 1.2, así que falla contra un bind que
lo exige y marca el backend como caído para siempre. El síntoma es un 503 de un
servicio que funciona perfectamente, y conviene saberlo porque en los logs de la
propia aplicación no aparece nada raro.

Y el check tiene que llamar al 11080, no al 11443. Un check TCP contra el bind
TLS conecta y cuelga sin handshake, y este HAProxy apuntaba cada uno como «SSL
handshake failure»: medido en el Debian de pruebas, 64.075 líneas en dos días,
una cada dos segundos, enterrando cualquier cosa real en el journal. Primero
se probó `check-ssl verify none`, y cambió una línea por otra: el cierre
brusco del check llegaba con el handshake aún terminándose, y cada check
apuntaba eso o un `ECONNRESET`. Contra el 11080 el mismo conectar-y-colgar es
una sesión nula que `option dontlognull` deja fuera del log, los dos puertos
son de un mismo proceso, y el journal se quedó en silencio: cero líneas en
treinta segundos con el sitio respondiendo 200 desde fuera.

No fija ningún `maxconn`, y eso no es un descuido. `maxconn 2048` le pide al
núcleo 4131 descriptores de archivo, y HAProxy prefiere no arrancar antes que
quedarse sin ellos: *Cannot raise FD limit to 4131, current limit is 1024 and
hard limit is 4096*. Lo reportó un LXC de Alpine corriendo bajo OpenWrt en una
BPI-R3, cuyo límite duro es 4096: `boa-proxy` se reinició setenta veces
seguidas, nunca hubo nada escuchando en el 11443, y una primera instalación
terminó en “The application did not answer on port 11443 (last code: 000)”.
Las dos máquinas de pruebas son LXC de Proxmox con un límite duro de 524288,
que es la razón de que ninguna lo mostrara nunca, y `haproxy -c` aceptaba el
archivo en todas ellas: la configuración nunca fue inválida, el proceso moría
al arrancar. Sin `maxconn`, HAProxy se dimensiona con los descriptores que
puede tener de verdad, que es lo que pide su propio mensaje, y
`fd-hard-limit 4000` acota lo que toma donde el límite es enorme. Medido con
un mismo binario a tres límites duros: 4096 da maxconn 1987, 1024 da 499,
524288 da 1987. Una prueba arranca el haproxy real con el archivo que se
publica bajo un límite duro de 4096 y exige que siga en pie, y lo arranca de
nuevo con el viejo `maxconn 2048` y exige que muera: una prueba que sólo leía el
archivo es justamente lo que dejó pasar esto.

Tres cosas necesitan root de verdad: crear un usuario de sistema, instalar el
crontab de otro usuario y lanzar un proceso como otro usuario. Todo lo demás,
no. Así que root vive en un único daemon pequeño con un **vocabulario cerrado
de verbos** sobre un socket Unix, y a propósito no hay ningún verbo que
signifique «ejecuta este comando». Quien llegue a ese socket puede crear un
agente sin privilegios; no puede ejecutar código como root.

El socket es `0660 root:boa`, y en cada conexión se comprueba `SO_PEERCRED`
para que sólo se atienda a root y a `boa`, diga lo que diga el modo del archivo
después de alguna actualización futura.

### Un cambio tiene que venir de las páginas de este sitio

La cookie de sesión es `SameSite=Lax`, que impide que una petición desde
otro sitio la lleve. No deja fuera a otro ORIGEN del mismo sitio: un agente
con `bash.run` puede servir una página en esta misma máquina, en un puerto
suyo, y un enlace a ella desde una respuesta del chat está a un clic. Un
formulario ahí que envíe a `/api/admin/agents/000/run` es una petición del
mismo sitio, la cookie viaja y la ejecución arranca; al ser un POST simple
sin cuerpo, tampoco hay preflight que se interponga. Así que
`fRefuseChangesFromElsewhere`, un `before_request` del blueprint de la API,
contesta 403 a cualquier POST, PUT, PATCH o DELETE que no venga de las
páginas de este sitio: una cabecera `Origin` tiene que nombrar exactamente
este host y este puerto, `localhost` y `localhost:8080` son dos orígenes y
el segundo es justo la página que un agente podría servir, y una cabecera
`Sec-Fetch-Site` tiene que decir `same-origin`. Una petición sin ninguna de
las dos no es de un navegador, es un script o las pruebas, y la juzga el
login, como antes. Un GET no se filtra: no cambia nada, y una página de
otro sitio no puede leer la respuesta, porque no hay cabeceras CORS que se
lo permitan.

### La API de agentes, y por qué existe

Dos cosas pertenecen a `boa` y no deben ser legibles por los agentes: la base
de datos del kanban (un agente que pudiera escribirla directamente podría
reescribir el historial de otro) y las credenciales de los canales (un token de
bot no es un mensaje: es autoridad permanente para enviar).

Por eso los agentes llegan a ambas a través de `boa-agent-api`, por un segundo
socket Unix que cualquier agente puede abrir. La autorización son dos
comprobaciones independientes:

1. El token presentado coincide con el SHA-256 guardado del token de algún
   agente.
2. `SO_PEERCRED` dice que el proceso que llama pertenece al usuario de *ese*
   agente.

Cualquiera de las dos por separado sería más débil: un token filtrado no sirve
desde la cuenta equivocada, y estar en la cuenta correcta no sirve sin el
token.

Es un socket Unix y no HTTPS porque no se gana nada con un handshake TLS entre
dos procesos de la misma máquina, y un certificado autofirmado obligaría a cada
agente a ejecutarse con la verificación desactivada, que es peor que no tener
TLS porque parece seguridad.

### Dónde vive el estado, y por qué está repartido

| Estado | Dónde | Por qué ahí |
|---|---|---|
| Configuración del agente | `agents/xxx/info.json` | El agente debe leerlo como él mismo |
| Historial del agente | `agents/xxx/runs.jsonl` | El único sitio donde un agente puede escribir |
| Procedimientos compartidos | `skills/<Nombre>/SKILL.md` (root, 0755) | Los lee todo agente al que se le dan, no los escribe ninguno |
| Índice de agentes, login, ajustes | `db/boa.sqlite` (0700 `boa`) | Lo necesita el proceso web |
| El tablero | `kanban/kanban.sqlite` (0700 `boa`) | Muchos escritores concurrentes |

A propósito **no hay tablas `runs` ni `usage`**. Un proceso de agente no puede
abrir la base de datos de `boa`, y darle permiso de escritura permitiría que
cualquier agente reescribiera el historial de otro. En su lugar, cada agente
agrega líneas a su propio journal, y la aplicación web los lee a través de
`boa-exec`. El beneficio colateral es que un agente sigue registrando lo que
hizo aunque la aplicación web esté caída.

El tablero es SQLite y no una carpeta de archivos JSON porque que varios
agentes despierten en el mismo minuto de cron es lo normal, y sólo una
transacción evita que dos adiciones simultáneas se pisen.

### Lo que guarda una copia de seguridad

`--backup` escribe un único archivo con todo lo que la instalación es y el
código no, y `--restore` lo pone en el lugar de lo que tenga una máquina; los
dos están en los dos instaladores, función por función. La lista es la tabla
de arriba convertida en una línea de `tar`: las dos bases de datos, las claves
y los canales, los certificados, cada agente con su home y sus archivos
protegidos, las skills y las herramientas. Alrededor, tres cosas que un `tar`
de `/opt/boa` haría mal:

- **Las bases de datos pasan por la API de copia de SQLite**,
  `fCopySqliteDatabase`, y no por `cp`. Las dos van en modo WAL, así que una
  copia del archivo `.sqlite` se pierde lo que siga en el `-wal`, y una copia
  tomada en mitad de una escritura puede quedar rota. El `python3` del venv
  tiene el módulo; la orden `sqlite3` no está en ninguna de las dos
  distribuciones. El mismo motivo corta al revés al restaurar: los `-wal` y
  `-shm` viejos se borran antes de que se lea el archivo restaurado, o SQLite
  le aplicaría el log viejo.
- **Los usuarios de los agentes viajan por nombre.** `agents.txt` apunta el
  usuario, el uid y el gid de cada agente, y `fRestoreAgentUsers` crea los
  que faltan siempre con el mismo nombre y con los mismos ids cuando están
  libres. La propiedad dentro del archivo se resuelve por nombre al extraer,
  así que un `boa` o un `agent-001` con otro uid en la máquina nueva sigue
  siendo dueño de sus archivos. Los crontabs viven en el spool del cron, no
  en `/opt/boa`, así que se sacan con `crontab -l` y se devuelven con
  `crontab -u`.
- **Tres archivos se dejan fuera a propósito**: `config/ports.conf`,
  `config/browser.conf` y el `haproxy.cfg` que se genera a partir de ellos
  describen ESTA máquina, y una restauración no debe importar las decisiones
  de otra. El log de instalación viaja como `install.log.backup`, con otro
  nombre para que una restauración nunca escriba encima del log que se está
  escribiendo en ese momento; sus líneas de credenciales se agregan al log
  actual, porque el acceso después de restaurar es el de la copia.

La restauración es la única acción que sustituye datos y no se puede
deshacer, así que confirma como lo hace una reinstalación. Las dos funciones
las ejecutan las pruebas sobre un árbol real, con bash y con dash: se
comprueba qué guarda el archivo y qué deja fuera, se estropea el árbol de
todas las maneras que una restauración tiene que deshacer, y se comprueba la
restauración archivo por archivo.

### Una habilidad se indexa en el prompt y se carga bajo demanda

La memoria de un agente se carga entera en el prompt de sistema de cada
ejecución, y para una memoria eso está bien: tiene un tope de 8000 caracteres y
es lo único que el agente no puede volver a deducir.

Las habilidades no son así. Un procedimiento ocupa una o dos páginas, a un
agente se le pueden dar varias, y la mayoría de las ejecuciones no necesitan
ninguna: la revisión del disco no necesita el procedimiento del certificado.
Cargarlas como se carga la memoria significaría pagarlas todas en cada llamada
de cada ejecución, y los techos de `info.json` se miden en tokens.

Así que el prompt lleva un índice —una línea por habilidad, su nombre y su
descripción— y el cuerpo se carga con `skill.read`, una vez, por un agente que
decidió que lo necesita. Cinco habilidades cuestan unos 200 tokens por ejecución
en vez de 10000, y la que se lee se cobra una vez en lugar de en cada llamada.

Por eso la descripción de la cabecera es la parte que carga el peso: es sobre lo
que el agente decide, y es lo que paga cada ejecución tanto si la habilidad se
lee como si no.

### Las habilidades son de root, igual que las herramientas

Una herramienta es de root porque la aplicación la importa como código. Una
habilidad no la ejecuta nada, pero se antepone al razonamiento de un agente que
se despierta a las cuatro de la mañana sin nadie mirando, lo que la hace tan
sensible como `system-prompt.md` —y ese archivo ya vive en una carpeta que el
agente puede leer y no puede escribir.

Así que no hay editor de habilidades en la interfaz web, ni un verbo privilegiado
para escribir una. Las habilidades se escriben en el servidor por SSH. La
interfaz decide qué agente recibe cuál, que es lo mismo que hace con las
herramientas.

La otra mitad de esa decisión es dónde viven: `/opt/boa/skills/`, fuera de
`webapp/`, porque `fDeploySourceCode` hace `rm -rf` sobre `webapp` y un
procedimiento que alguien escribió en este servidor no es algo que una
actualización tenga derecho a borrar. El mismo razonamiento, y el mismo sitio en
el árbol, que `/opt/boa/tools/`.

La aplicación no trae ninguna. No existe `backend/skills/` y los instaladores
no copian nada en esa carpeta: la crean vacía, de root y 0755. Una habilidad es
un procedimiento para UNA instalación —estos equipos, esta copia de seguridad,
este certificado—, así que una genérica sería un procedimiento que no sigue
nadie, ocupando una línea de cada prompt de cada ejecución para decirlo. Que la
carpeta esté vacía en una instalación recién hecha es la función haciendo su
trabajo, no una pieza que falta.


### `deploy/` no se despliega

En `/opt/boa/webapp/` están `backend/` y `frontend/`, y nada más. La carpeta
`deploy/` (las units, las dos configuraciones de HAProxy, las plantillas de
agente, los catálogos de proveedores, `requirements.txt` y el propio
instalador) es material del instalador, y se lee del árbol que el instalador
acaba de descargar en `/tmp`, que se borra al terminar.

No es sólo limpieza. Leer las units de una copia dentro de `/opt/boa`
significaba instalar las units de la versión que hubiera en el disco; leerlas
del árbol descargado instala las de la versión que se está desplegando, que
es la única pareja sobre la que se puede razonar. Cada una de esas lecturas
llama antes a `fRequireSourceCode`, así que un paso que algún día se ejecute
antes de la descarga falla con una frase en vez de copiar desde
`/deploy/...`.

Es también la razón de que `gunicorn.conf.py` esté en `backend/web/` y no en
`deploy/`: gunicorn lo lee en cada arranque, así que tiene que ser un archivo
que esté de verdad en el servidor, y la carpeta que está en el servidor es la
del código que configura.

Lo que se despliega es `root:root`, las carpetas en `00755` y los archivos en
`0644`, fijados por `fSetCodeModes` y por nadie más. Nada de lo que hay bajo
`webapp/` se ejecuta por ruta: el daemon lanza el runner como
`venv/bin/python3 .../runner.py`, y el crontab que escribe para cada agente
dice lo mismo, así que ningún archivo de ahí necesita el bit de ejecución. Lo
tenía igual hasta que esto fue UNA función: `fDeploySourceCode` ponía `0644` y
`fCreateDirectoryTree`, que se ejecuta después en un update, hacía
`chmod -R 00755` sobre el mismo árbol.

### Telegram recibe HTML, y si lo rechaza, recibe las palabras

Un modelo escribe markdown. Mostrado en crudo, eso es `**25G libres**` con los
asteriscos en mitad de la frase, que es lo que llegaba al móvil hasta ahora.

Telegram renderiza un subconjunto pequeño de HTML: catorce etiquetas, ningún
atributo digno de ese nombre, y ni encabezados ni listas ni tablas entre ellas.
Así que `telegram_html` traduce aquello para lo que hay etiqueta y busca una
forma legible para lo que no: los encabezados pasan a negrita en su propia
línea, los elementos de lista reciben una viñeta, y una tabla se convierte en un
bloque `<pre>` con relleno, que es la única manera de que las columnas queden
una debajo de otra en un móvil.

Dos cosas de este módulo sostienen todo lo demás.

**El escapado va primero.** Para Telegram, `&`, `<` y `>` son marcado, así que
un agente que informe de `grep <dev> && echo` produce un mensaje al que Telegram
responde con un 400 —es decir, un mensaje que no llega nunca—. Todo texto pasa
por `fEscape` antes de que nada lo envuelva. Un href pasa por
`fEscapeAttribute`, que además escapa la comilla doble: una URL que la contenga
cerraría el atributo y convertiría el resto de sí misma en atributos que no
escribió nadie.

**Un mensaje rechazado se vuelve a enviar como texto plano.** Se equivoque en lo
que se equivoque el renderizador, las palabras valen más que el formato, así que
un 400 se reintenta sin `parse_mode` y la línea sale sin formatear. El respaldo
registra lo que dijo Telegram, porque un formato que se degrada en silencio para
siempre es un formato que no arregla nadie.

**Una respuesta que Telegram rechaza se descarta, y una que no puede recibir se
guarda una hora.** `fSay` devuelve tres cosas y no dos: enviado, sin
respuesta, y rechazado, un 4xx que no sea 429, `ChannelRejected`, que es
Telegram diciendo que no a este mensaje y diciéndolo también mañana: el bot
bloqueado, el chat desaparecido, el token revocado. `fDeliverAnswers` conservaba
la fila ante cualquier fallo y lo reintentaba en la pasada siguiente, y la fila
está en disco para que un reinicio no pierda una respuesta, así que un bot
bloqueado convertía al listener en un bucle sin fin: el sondeo en su modo
rápido, una lectura del chat a través del demonio root y hasta dos peticiones
a Telegram en cada pasada, reinicio tras reinicio. Una respuesta rechazada se
descarta en el acto con una línea que lo dice, y una que Telegram no ha
recibido en la hora que se le da a una ejecución se descarta también, por el
mismo motivo por el que la otra rama se rinde con una ejecución que nunca
terminó. Ninguna de las dos pierde la respuesta: está en la conversación del
agente en la interfaz web, donde se escribió primero.

Los patrones son los mismos que usa `frontend/static/js/markdown.js`. Que dos
renderizadores no se pusieran de acuerdo en qué cuenta como markdown
significaría que una misma respuesta se lee distinta en los dos sitios donde se
muestra, y la gracia de mandarla a los dos es que son la misma conversación.


### Discord se consulta, y una respuesta son dos mil caracteres

Discord es el segundo canal por el que una persona puede contestarle a un
agente, y la mitad que recibe es `discord_listener`: `boa-discord`, el séptimo
servicio. Hay cuatro cosas que lo separan del de Telegram.

**Consulta, por REST.** `GET /channels/<id>/messages?after=<id>`, cada cinco
segundos, y cada dos mientras un agente está contestando. La alternativa obvia
era el Gateway y se descartó: es un WebSocket que necesita latidos, un
protocolo de reanudación y una dependencia que este proyecto no tiene, y exige
activar el Message Content Intent en el portal de desarrolladores —sin eso
todos los mensajes llegan con el `content` vacío y nada dice por qué—. Consultar
además conecta hacia fuera, que es lo que permite que esto funcione en una LAN
sin nada redirigido, igual que el long poll de Telegram. Lo que cuesta es una
latencia de segundos y doce pedidos por minuto frente a un límite de
cincuenta por segundo.

**Dos mil caracteres, no cuatro mil.** `channels.cMaxMessageLength` vale 4096,
que es el techo de Telegram, y Discord responde 400 a cualquier `content` de
más de 2000. Una respuesta larga no llegaba recortada: no llegaba.
`discord_markdown` la corta por líneas en cuatro mensajes como mucho, y un
bloque de código dentro del que caiga el corte se cierra al final de uno y se
vuelve a abrir al principio del siguiente: sin eso, una mitad llega como texto
plano y la otra como un bloque que no termina nunca, que en Discord se traga
todo lo que se diga después. Cada parte queda registrada como de ese agente,
porque una persona responde a la que tiene en pantalla.

**Sin botones, y `!` para las órdenes.** Pulsar un botón y usar un slash command
son las dos *interacciones*, y una interacción llega por el Gateway o por un
endpoint HTTPS al que Discord pueda llegar. Un canal consultado no ve ninguna
de las dos. Así que `/agents` es `!agents`, un mensaje corriente, y la lista de
agentes es una lista de nombres para escribir en vez de una columna de botones.
`/agents` también se acepta, porque quien montó el bot de Telegram lo va a
escribir por costumbre.

**La respuesta de un agente no menciona a nadie.** Todos los mensajes que se
envían llevan `allowed_mentions: {"parse": []}`, así que un `@everyone` escrito
por un modelo es texto y no una notificación a un servidor entero.
`replied_user` se deja activado: una respuesta debería llegarle a quien
preguntó. Es una regla en el socket y no en el prompt, por la misma razón que
lo es la lista de reenvío del correo.

Lo que Discord no tiene es el silencio de Telegram ante los desconocidos. No
hay un `chat_id` con el que comparar: el bot pide un canal y lee ese canal, así
que quien puede hablar con los agentes es quien puede escribir en él. Un canal
privado es la configuración que equivale a lo que `fIsFromTheConfiguredChat`
impone por código, y el manual lo dice, porque es toda la autorización que hay.

El webhook que este canal ya tenía sigue ahí y sigue enviando. Un webhook no
puede leer, no puede responder y no devuelve el id del mensaje, así que activar
`listen` sobre uno se rechaza en vez de ofrecerse: un interruptor que no hace
nada es peor que no tener interruptor.

### Un solo enrutado, dos listeners

`agent_routing` guarda lo que los dos listeners hacen igual: qué agentes hay,
sacar un nombre de `@News Miner`, de `/news_miner` o de `@002` con la
coincidencia más larga ganando, qué dijo un agente para cerrar un turno, y el
informe de estado. El protocolo se queda en cada uno —un long poll no es una
consulta REST, un teclado en línea no es una lista de nombres, y una respuesta
es `reply_to_message` en uno y `message_reference` en el otro—.

Se escribió cuando se escribió el segundo listener, y el motivo es el informe
de estado. Dos copias de esa respuesta serían dos respuestas a «¿está
funcionando?», y lo primero en lo que no coincidirían es en cuántos servicios
hay.

Enviar no está ahí. Se queda en cada listener como `fSay`, que es lo que
permite que un test sustituya el de uno y deje el otro en paz.

### Un navegador, compartido; un perfil, no

`web.fetch` lee una página pública y ahí se acaba: sin sesión, sin formulario,
sin botón. El navegador es la otra cosa, y se parte en dos:

| | Dónde | De quién es |
|---|---|---|
| El navegador | `/opt/boa/playwright/` | root, 0755, una sola copia |
| El perfil | `agents/xxx/browser/profile/` | del agente, 0700, uno cada uno |

El binario se comparte porque es un binario y no hay nada que aislar en él; una
copia por agente serían 600 MB cada una y una actualización que hacer N veces.
El perfil no se comparte, porque es donde están las cookies: que el agente 007
inicie sesión en algo no puede dejar dentro al 008. Esa separación es la del
kernel, la misma carpeta home 0700 en la que vive todo lo demás de un agente, y
es exactamente lo que un producto de agentes alojado no puede ofrecer cuando
todos sus agentes comparten una máquina y un juego de sesiones.

De ahí salen tres decisiones:

**El navegador sigue abierto entre llamadas a herramientas dentro de una
ejecución.** `browser.click` actúa sobre lo que dejó `browser.open` en pantalla,
y una ejecución es un solo proceso desde la primera llamada hasta la última, así
que una variable de módulo es todo el estado que hace falta. `atexit` lo cierra;
sin eso, un agente que se ejecuta cada hora deja un Chromium por ejecución y
llena la máquina por la mañana.

**Playwright se importa dentro de las funciones, nunca a nivel de módulo.** Las
herramientas del navegador aparecen en la interfaz haya navegador o no, y un
ImportError arriba las haría desaparecer de esa lista sin explicación en ningún
sitio. Importado tarde, un navegador que falta es una frase que dice qué comando
ejecutar.

**Sin interfaz gráfica, y sólo direcciones públicas.** Lo que se quiere es la
sesión y el DOM, no una foto de una ventana, así que una pantalla virtual sería
una pieza móvil más para nada. Y `browser.open` pasa por
`public_url.fCheckUrlIsPublic` igual que `web.fetch`: si no, a un agente que lee
una página hostil se le podría decir que abra el panel del router, y un navegador
con sesión es mucho mejor herramienta para eso que un fetch.

Una cookie de sesión sigue desapareciendo al cerrar el navegador, aquí como en
cualquier otro. Lo que sobrevive es lo que el sitio marcó para sobrevivir.

### Lo que un proveedor acepta no es lo que dice el estándar

Dos adaptadores enviaban algo que su proveedor rechaza, y en los dos casos el
resultado era el mismo: toda llamada a herramienta por ese proveedor fallaba,
en todos los modelos, y la batería no lo veía porque probaba las piezas y no
el ciclo entero.

| Proveedor | Qué se enviaba | Qué respondía |
|---|---|---|
| Ollama | `kanban__list_cards` sin decodificar de vuelta | El registro rechazaba una herramienta que el agente no tenía concedida: justamente la que se le acababa de ofrecer |
| Google | `"additionalProperties": false`, que es JSON Schema correcto | `400 - Unknown name "additionalProperties" at 'tools[0].function_declarations[0].parameters'` |

El `function_declarations[].parameters` de Gemini es un SUBCONJUNTO de JSON
Schema y rechaza lo que no conoce en vez de ignorarlo, así que
`fCleanSchemaForGoogle` filtra el esquema con una lista de permitidos, de forma
recursiva. Lista de permitidos y no de prohibidos, por la misma razón que
todas las de aquí: la próxima clave que alguien añada a un esquema de
herramienta la rechazaría Gemini tanto si alguien se acordó de añadirla a una
lista de cosas que quitar como si no.

Los dos se encontraron ejecutando el ciclo completo —preguntar, llamar a una
herramienta y responder a esa llamada— contra las APIs reales con claves
reales. `_/temp/probe-defaults.py` es esa comprobación, y es lo único que
encuentra esta clase de fallo: un esquema válido, un nombre correcto y un
proveedor que no lo acepta.

### Un archivo de adaptador por proveedor

Veinticinco proveedores, veinticinco archivos, aunque la mayoría hable el mismo
dialecto. Un único adaptador «compatible con OpenAI» parece limpio hasta que
uno de esos proveedores cambiá el nombre de un campo, y entonces hay que
arreglarlo sin romper a los otros veinte. Cada archivo lleva las
particularidades de su proveedor: DeepSeek descarta `reasoning_content` antes
de que el runner pueda reenviarlo, llama.cpp detecta una plantilla de chat sin
soporte de herramientas, vLLM convierte un 404 en la lista de modelos que sí
sirve, Cloudflare construye su dirección a partir de la credencial.

Lo que comparten es `base.py`: una forma de mensaje neutra modelada sobre
chat/completions, porque casi todos ya la hablan, y el adaptador de Anthropic
traduce a bloques de contenido.

También comparten `openai_dialect.py`, y la diferencia entre eso y un
adaptador compartido es justo el motivo de que exista. El módulo del dialecto
tiene la petición en sí (el POST, los errores HTTP que merece la pena nombrar,
el parseo de la respuesta), que no es la particularidad de ningún proveedor.
Las particularidades se quedan en cada archivo, declaradas como atributos de
clase que el módulo lee:

| Atributo | Qué decide |
|---|---|
| `cDisplayName` | El nombre en cada mensaje de error. «zai request failed» no es lo que nadie buscaría |
| `cMaxTokensField` | `max_tokens` o `max_completion_tokens`, según qué grafía siguió el proveedor |
| `cToolChoiceMode` | `auto`, `any`, u `omit` para los proveedores que rechazan el campo. `auto` es lo que un agente necesita: un modelo obligado a llamar a una herramienta en cada turno nunca termina una ejecución |
| `cChatCompletionsPath` | La ruta después de la URL base, para los pocos que no usan la habitual |
| `cAssistantContentWhenEmpty` | Qué enviar en lugar de un `content` nulo, para un proveedor cuyo esquema rechaza el nulo |

### Lo que cambiaron veintidós claves reales

A cada proveedor se le llamó con una clave real, se le hizo una pregunta, se le
dio una herramienta y después se le entregó la respuesta a la llamada que hizo.
Los veintidós que tienen clave completan ese ciclo. Siete cosas sólo aparecieron
en el segundo paso, el que una prueba con una respuesta enlatada nunca alcanza,
y cada una es ahora una línea de código con las palabras del propio proveedor al
lado:

- **Perplexity había retirado el endpoint.** A `chat/completions` responde 403
  «Sonar is now the Agent API. Use /v1/responses instead of /v1/sonar», así que
  ese adaptador se reescribió contra la Responses API, y el proveedor pasó de
  ser un modelo a ser un enrutador sobre 48.

- **Una clave dentro de un mensaje de error.** A Gemini se le llamaba con
  `?key=...`, así que un 503 suyo metía la clave entera en el error que lee el
  usuario y que guarda el diario. La clave pasó a la cabecera `x-goog-api-key`,
  y `base.fRedactCredentials` limpia ahora `key=`, `api_key=`, `access_token=` y
  `token=` de cualquier error de cualquier adaptador, porque ese fallo no debe
  depender de que un adaptador se acuerde.
- **Gemini 3 quiere de vuelta su firma de pensamiento.** Rechaza de plano una
  conversación cuyas llamadas a función vuelven sin la firma que él emitió, así
  que cada agente con Gemini fallaba en cuanto usaba una herramienta.
  `ToolCall.dProviderData` la lleva y la trae, opaca para todo lo demás.
- **Cloudflare rechaza un `content` nulo.** Que es justo lo que lleva un mensaje
  del asistente cuando el modelo respondió con llamadas a herramientas y
  ninguna palabra. Recibe `""`; el dialecto sigue enviando nulo a los demás,
  porque el nulo es lo que el dialecto especifica.
- **Razonamiento escrito dentro de la respuesta.** MiniMax responde con
  `<think>...</think>` en el propio texto. Se quita en el módulo del dialecto y
  no en un adaptador, porque lo hace el modelo, así que el mismo modelo tras una
  pasarela hace lo mismo; y sólo cuando la respuesta EMPIEZA por la etiqueta,
  para que un modelo que escribe sobre HTML conserve sus palabras.
- **Together deja el nombre del canal delante.** gpt-oss escribe por canales y
  Together devuelve «finalThe weather in Madrid»; Groq y Cerebras, sirviendo el
  mismo modelo, no. Se quita en `together.py`, que es donde va la
  particularidad de un proveedor.
- **Cuatro modelos por defecto que el proveedor no servía.** El 20b de
  Fireworks necesita su propio despliegue, el de Together no es serverless,
  Moonshot retiró kimi-k2.5, y gemini-3.7-flash responde 503 «experiencing high
  demand». Un modelo por defecto que falla en la primera ejecución es peor que
  uno una versión por detrás.

Cinco adaptadores no lo usan en absoluto, porque su API no es esa: los
bloques de contenido de Anthropic, el `generateContent` de Google, el
`/completion` de llama.cpp, el chat v2 de Cohere (que recibe los mismos
mensajes pero responde con el texto en bloques, un motivo de fin en mayúsculas
propio y los recuentos de tokens anidados bajo `usage.tokens`) y Perplexity,
que retiró chat/completions del todo y a esa petición responde

    403 Sonar is now the Agent API. Use /v1/responses instead of /v1/sonar

así que ese adaptador habla la Responses API: una lista `input` en vez de
`messages`, el prompt de sistema como `instructions`, y una respuesta que llega
como elementos de salida - un `message` con su texto en bloques, o un
`function_call` - en lugar de como una elección. El resultado de una
herramienta vuelve como un elemento propio, `function_call_output`, emparejado
por `call_id`.

Dos nombres se resuelven antes de que nada más los vea, a través de
`factory.dProviderAliases`: `gemini` es como llama Google a su API en su
documentación y `google` es lo que dice el `info.json` de cada agente desde la
primera versión, así que los dos llegan al mismo adaptador y sólo uno de ellos
se guarda.

A cuáles de los veinticinco se puede configurar un agente lo decide
`fListProviders`, no el navegador: un proveedor es `selectable` si es
autoalojado o si tiene clave guardada. Es un filtro sobre lo que merece la pena
ofrecer, no una regla: la clave también puede vivir en el home del propio
agente, donde la webapp no puede mirar, así que la interfaz le sigue mostrando
al agente el proveedor que ya tiene puesto.

Esa misma marca decide una cosa en la interfaz: el campo **URL base**, tanto
en el modelo principal como en el de reserva, se muestra con un proveedor
autoalojado y se oculta con uno de nube. `base.fInit` ya recurre al
`cDefaultBaseUrl` del adaptador, así que con un proveedor de nube el campo
preguntaba algo que estaba respondido antes de preguntarlo, y la única
respuesta distinta de la de fábrica que admitía era una equivocada. Se oculta,
no se vacía: una instalación que pone un proxy adelante de un proveedor de
nube tiene esa dirección guardada, y esconder una caja no es motivo para tirar
lo que hay adentro.

Algo que `base.py` les oculta a todos es el nombre de una herramienta. Este
proyecto llama a una herramienta `familia.accion`; un proveedor valida el
nombre de una función contra `^[a-zA-Z0-9_-]+$` y rechaza la petición entera
por el punto, sin decir qué campo estaba mal. `fToolNameToWire` cambia el
punto por `__` al salir y `fToolNameFromWire` lo deshace al entrar, en todos
los adaptadores, así que el registro, la interfaz, el `info.json` y los
registros nunca ven la forma codificada.

### Techos, no confianza

Cada ejecución se detiene en el primero de cuatro techos: tokens, pasos,
segundos y ejecuciones al día. Existen porque un bucle desatendido contra una
API de pago es una factura abierta y, contra un modelo autoalojado, una GPU que
no vuelve. El `max_tokens` de cada petición se encoge con lo que la ejecución ya
ha gastado, para que no pueda superar su presupuesto con una última llamada
cara.

Cuatro cosas separan un techo de una sugerencia, y cada una de ellas era lo
segundo hasta que se arregló:

  - **Sin suelo en la petición de tokens.** `max(512, restante)` pedía 512
    tokens con el presupuesto agotado, así que a un agente al que le quedaba
    un token se le permitía media página.
  - **Cada llamada recibe el tiempo que QUEDA**, no el timeout completo de la
    ejecución. Se mueve el `vTimeoutSeconds` del propio adaptador antes de
    cada llamada, en vez de añadir un parámetro a los veintiséis adaptadores
    que implementan `fSendMessages`.
  - **El plazo se comprueba antes de cada herramienta**, no una vez por paso.
    Un lote de seis llamadas que llegaba justo antes del plazo se ejecutaba
    entero, cada una con su propio timeout encima de una ejecución ya vencida.
  - **Un reloj monótono.** `time.time()` se mueve cuando NTP lo ajusta, y una
    ejecución que empezó «en el futuro» no alcanza nunca su timeout.

Lo que sigue sin acotarse es el prompt. Una llamada gasta su entrada más su
salida y aquí sólo se limita la salida, así que una conversación larga se pasa
por el lado de la entrada; contarlo exigiría pasar el tokenizador de cada
proveedor por la conversación antes de cada llamada. La respuesta de cierre
tras un techo también se sale del presupuesto a propósito, y así está escrito
donde se hace.

### Una sola ejecución de cada agente a la vez

Dos cerrojos, porque hay dos clases de llamador.

El daemon mantiene un `threading.Lock` por agente entre «¿está corriendo?» y
«arranca el proceso». Atiende cada petición en su propio hilo, así que dos
llamadas a `run_now` con `only_if_idle` eran dos hilos de un mismo proceso sin
nada entre medias, y un barrido de /proc no ve un proceso que todavía no se ha
bifurcado. Medido: dos llamadas simultáneas, dos ejecuciones.

El runner toma un `flock` sobre `<home>/run.lock` y lo sostiene lo que dure el
proceso. Ese es el que manda, porque un crontab arranca el runner directamente
y no pasa por el daemon. No es una frontera de permisos —un agente con
`bash.run` arranca lo que quiera—: existe para que la APLICACIÓN no arranque
dos veces el mismo agente, gastando dos presupuestos sobre un solo perfil de
navegador y una sola conversación.

### Una ejecución que nunca empezó lo dice

El demonio privilegiado arranca el runner con la entrada, la salida y el error
en `/dev/null`. Todo lo que escribe `fLogLine` va, por tanto, a ninguna parte,
y había dos fallos que vivían enteros en esa salida:

- el cerrojo estaba tomado, así que esta ejecución no va a ocurrir;
- algo falló antes de que `fExecute` escribiera `run_started`: un `info.json`
  ilegible, o un proveedor cuya clave de API no se ha puesto todavía, que de
  los dos es con diferencia el más probable.

Medido en una instalación real: con el cerrojo tomado, `POST /agents/001/run`
respondía `202 {"started": true}` y no aparecía nada en el diario, ni en
`journalctl`, ni en ningún archivo. El mismo fallo lanzado por cron SÍ se veía,
porque cron guarda la salida de lo que arranca, y por eso esto duró lo que
duró: el agujero estaba sólo en el camino que usa la interfaz.

`fRecordRunRefused` lo escribe en el diario, como un fin con estado `refused` y
sin `run_id`. Cada parte de esa forma está ahí por algo:

| Parte | Por qué |
|---|---|
| `kind: run_finished` | El historial pinta los fines. Un tipo propio obligaría a la interfaz a aprenderlo, y una entrada que nadie pinta es lo mismo que ninguna entrada |
| `status: refused` | `failed_runs` cuenta los fines cuyo estado es `failed`. No se ejecutó nada del agente, así que nada del agente falló |
| sin `run_started` | `runs` y `max_runs_per_day` cuentan los comienzos. Un cerrojo tomado no puede gastar una de las ejecuciones del día por algo que no se ejecutó |
| `run_id: ""` | No empezó nada, así que no hay ejecución que identificar |

Se escribe sólo cuando no lo ha escrito nadie más. En cuanto `fExecute` tiene
un identificador de ejecución ya ha escrito `run_started`, y sus propios
manejadores escriben el `run_finished` que le corresponde antes de relanzar el
error, así que `fMain` mira `vRun.vRunId` antes de añadir un segundo fin para
una sola ejecución. La misma comprobación decide quién cierra el turno del chat:
los manejadores de `fExecute` lo cierran al apuntar el fin, y `fMain` sólo lo
cierra cuando la ejecución no llegó tan lejos. Medido antes de que fuera así,
en el Debian de pruebas: cada ejecución que no alcanzaba a su proveedor
contestaba dos veces la misma pregunta, con la misma frase.

### El historial muestra lo más reciente, y no lo hacía

`fReadEntries` devuelve el diario de más antiguo a más reciente —lo dice en su
propia documentación— y `fRenderRunHistory` cogía `.slice(0, cShownRuns)` de
ahí. Eso son las diez ejecuciones MÁS VIEJAS. Un agente con más de diez
ejecuciones a la espalda tenía un historial que ya no cambiaba nunca.

Encontrado conduciendo la aplicación real con un navegador real, que es la
única forma en que podía encontrarse: todas las demás pruebas de
`dashboard.js` en este proyecto leen el archivo y buscan una cadena dentro, y
la cadena estaba. Medido en una instalación real, en tres idiomas: un agente
cuya última ejecución acababa de ser rechazada por falta de clave de API
mostraba un fallo de proveedor de cuarenta minutos antes, y el rechazo no
aparecía por ninguna parte.

`.slice(-cShownRuns).reverse()`: las diez últimas, la más reciente arriba, que
es lo que promete el encabezado de la lista.

La tabla de resumen que hay encima de esa lista tenía dos fallos propios, los
dos encontrados en la misma captura: imprimía `last_status` crudo, así que una
página en español decía «Último estado: refused», e imprimía `last_run_at`
crudo, así que un `2026-09-19T03:44:29Z` pelado quedaba justo encima de una
lista de fechas ya limpias. Las dos cosas pasan ahora por lo mismo que ya
usaban las filas de abajo.

### Un buzón es la única entrada en la que puede escribir cualquiera

Las cuatro herramientas `mail.*` siguen exactamente el modelo de los canales:
el agente dice qué quiere que se haga y lo hace la API de agentes, que corre
como `boa` y es quien tiene las credenciales. Un agente que pudiera leer la
contraseña del buzón no tendría «acceso a la bandeja»: tendría la cuenta, todos
sus mensajes, para siempre, y la capacidad de enviar como su dueño.

Lo que el correo tiene de distinto es la dirección por la que entra. Un agente
que lee un buzón es un agente cuyas instrucciones llegan, en parte, dentro de
los mensajes que lee, escritos por cualquiera del mundo. De ahí salen tres
decisiones:

  - **Reenviar sólo a las direcciones que el usuario haya listado**, y esa
    lista se comprueba dentro de `mailbox`, en el proceso que abre la conexión;
    nunca en el prompt. Una regla en un prompt es un consejo; una regla en el
    socket es una regla. Sin lista, el reenvío se rechaza del todo.
  - **Leer no marca nada como leído** (`BODY.PEEK[]` sobre una carpeta abierta
    en sólo lectura), así que un agente que mira el buzón no le quita a la
    persona el contador de no leídos en el que se estaba apoyando.
  - **Borrar mueve a la papelera** si la cuenta tiene una. Lo que un agente
    quita por una regla escrita el mes pasado, una persona todavía lo puede
    encontrar. «Esta cuenta no tiene papelera» y «no se pudo leer la lista de
    carpetas» se mantienen separados, porque sólo el primero puede terminar en
    un borrado definitivo: antes llegaban a `fDeleteMessage` como la misma
    cadena vacía, así que una sola línea LIST mal interpretada convertía cada
    `mail.delete` en un borrado permanente.

### Se instala con un agente, se ofrecen muchos

La instalación crea exactamente un agente: el orquestador. Todo lo demás son
EJEMPLOS, en `backend/agents/examples/`, un archivo Markdown cada uno, que se proponen
al pulsar «+». Una instalación que llega con agentes que nadie pidió es una
instalación que empieza con cosas que apagar.

El cuerpo del archivo ES el prompt de sistema y la cabecera son líneas
`clave: valor` entre dos `---`. Esa forma sale de lo que vale una plantilla: lo
útil de un agente es su prompt, y un prompt es texto, así que el archivo se
edita como un documento y no como una estructura de datos. Dejar un archivo en
esa carpeta añade un ejemplo, igual que con los temas y las herramientas, y por
el mismo motivo: ninguna lista en el código que mantener al día.

Crear desde un ejemplo manda el NOMBRE de la plantilla y nada más. El archivo
lo lee el servidor: una petición que pudiera traer sus propias herramientas y
su propia programación dejaría que el navegador le diera a un agente un permiso
que el usuario nunca marcó.

El diálogo pone PRIMERO el agente vacío y los ejemplos debajo. Cada ejemplo es
un atajo hacia el vacío, y quien ya sabe lo que quiere no debería leerse el
catálogo entero para llegar a la opción simple. Los ejemplos conservan el orden
que devuelve `fListTemplates`, que es el del nombre que se lee.

Uno de ellos, `web-navigator`, no tiene crontab. Es el ejemplo del navegador
(abre páginas, entra con sesión, aprieta y llena formularios, mientras el resto
leen) y ese trabajo es lo que el usuario acaba de pedir, no algo que hacer a
las cuatro de la mañana. Su prompt es donde están escritas las reglas que
necesita un navegador con sesión: nunca escribir una credencial, nunca
completar una compra ni un envío, y tratar la página como datos y no como
instrucciones.

### Dos formas de servirlo, elegidas al instalar

O bien 11080 y 11443 en localhost con un HAProxy delante en el 80 y el 443, o
bien el 80 y el 443 servidos directamente. El instalador pregunta, guarda la
respuesta en `config/ports.conf`, y una actualización no vuelve a preguntar ni
cambia en silencio los puertos en los que escucha la máquina.

La diferencia no son sólo los números: en modo directo hay que quitar
`accept-proxy` del bind, porque un navegador que llega directo al 443 no manda
cabecera PROXY y un bind que la exige rechaza a todos los clientes reales.

En modo `direct` el HAProxy de la máquina no se deja simplemente en paz: se
retira. `fRetireMachineProxy` lo para, lo saca de todos los runlevels en
Alpine, lo deshabilita **y lo enmascara** en Debian, y después borra
`/etc/haproxy/haproxy.cfg` si lo escribió este instalador, o lo mueve a
`haproxy.cfg.before-boa.<fecha>` si lo escribió otro. Pararlo no basta por sí
solo: uno que quede habilitado se queda con el 80 y el 443 en el siguiente
arranque, antes de que esta aplicación llegue a ejecutarse, y bajo systemd una
actualización del paquete, el `Wants=` de otra unidad o un simple `systemctl
start` levantan incluso uno deshabilitado. Una unidad enmascarada no la puede
arrancar nada, y haproxy sin `/etc/haproxy/haproxy.cfg` no tiene de dónde
arrancar. Lo que siga ocupando el 80 o el 443 después de todo eso se nombra en
el log, porque en este modo el proxy no puede arrancar sin ellos y enterarse
medio minuto después por “the application did not answer” es una manera mucho
peor de averiguarlo.

Lo que deliberadamente NO se hace es desinstalar el paquete haproxy.
`boa-proxy` ES `/usr/sbin/haproxy` —termina TLS y lee la cabecera PROXY
delante de gunicorn, y en modo `direct` es justo lo que hace bind al 80 y al
443—, así que purgar el paquete dejaría la aplicación sin nada escuchando, en
los dos modos. Lo que se retira es el *servicio* HAProxy de la máquina, que es
otra cosa que resulta usar el mismo binario. Volver a `proxied` desenmascara la
unidad antes de habilitarla; si no, la vuelta terminaría en «The machine's
HAProxy would not start» por una máscara que había puesto este mismo
instalador.

Medido en las dos máquinas de pruebas con `--update --ports direct`: la unidad
quedó enmascarada en Debian y sin ningún runlevel en Alpine, `/etc/haproxy` se
quedó sin configuración, y la aplicación respondió 200 en el 443 y 301 en el
80. La vuelta, `--update --ports proxied`, la dejó otra vez habilitada y activa
con 200 en el 11443 y en el 443. Siete pruebas EJECUTAN la función contra
órdenes de servicio falsas, con una configuración con el marcador y otra sin
él, en los dos modos, y una de ellas falla si una versión futura llega a
escribir `apk del haproxy` o `apt-get purge haproxy`.

### Una confirmación se muestra donde el usuario está mirando

«Ajustes guardados» se escribía arriba del todo de la columna de contenido. Eso vale
en un panel corto y no sirve de nada en uno largo: el botón Guardar del final
de la pestaña Herramientas de un agente producía un mensaje varias pantallas
por encima, fuera de lo que el navegador estaba dibujando, así que guardar
parecía no hacer nada.

Ahora es un mensaje emergente centrado sobre la columna de contenido, en una
capa `fixed` que es HERMANA de esa columna y no hija suya. Lo de `fixed` es lo
importante: centrar dentro de la columna caería en el centro del *documento*,
que en una pestaña larga es el mismo fallo unas pantallas más abajo. La capa
se detiene en la barra lateral, porque un mensaje dibujado sobre la lista de
agentes parecería pertenecer a la lista de agentes, y no recibe clics, así que
nada de lo que hay detrás deja de funcionar mientras hay un mensaje.

Cuánto se muestra es una preferencia de este navegador
(`boa.noticeSeconds`, Ajustes → Interfaz), junto al tema y al idioma y por el
mismo motivo: tres segundos sobran para una palabra y faltan para una frase, y
cuál de las dos es un mensaje depende de quién lo lea. Los errores son la
excepción y no hacen caso a ese número: un error espera a que lo cierren,
porque es el único mensaje que tiene que seguir ahí cuando el usuario vuelve a
mirar la pantalla.

Un mensaje tiene tres colores, y el tercero existe por lo que los otros dos NO
pueden decir. El verde es un guardado que ocurrió, el rojo es un fallo, y el
ámbar es **«No hay cambios que guardar»**: se apretó Guardar y el formulario
tenía exactamente lo que ya está guardado. Decir eso en verde es peor que no
decir nada («Ajustes guardados» después de un guardado que no escribió nada es
justo la frase que impediría darse cuenta de que la edición nunca entró), y el
rojo afirmaría un fallo donde no falló nada.

Todos los formularios que guardan lo comprueban igual: se compara, en JSON, lo
que enviarían con la instantánea tomada cuando el formulario se llenó con lo
que mandó el servidor, o después del último guardado. Los ajustes de un agente
arman ese envío en una sola función, `fCollectAgentPayload`, que se usa tanto
para guardar como para tomar la instantánea, porque dos lectores del mismo
formulario que se separaran dirían «no hay cambios» justo en el campo que uno
de los dos no mira. Los paneles de preferencias del navegador ya guardaban una
instantánea así, para el aviso de «cambios sin guardar», y sirve también para
esto.

La excepción es un agente NUEVO: su formulario tiene los valores del ejemplo y
nunca se guardó, así que apretar Guardar los escribe y pasa al chat en vez de
decir que no hay nada que hacer.

### El color es el estado, el movimiento es la actividad

El contorno que rodea al avatar de un agente lleva dos hechos distintos y los
dibuja por dos canales distintos, para que ninguno de los dos haya que
consultarlo. Que el agente esté encendido o apagado es un color que no se
mueve: verde o rojo. Que esté trabajando ahora mismo es movimiento: un trozo
encendido recorre ese contorno verde en el sentido de las agujas del reloj. Un
segundo color fijo para «ocupado» sería una convención que aprender, mientras
que algo que gira se entiende sin que nadie lo explique.

Se dibuja como un rectángulo redondeado SVG colocado exactamente sobre el
borde, trazado con una línea discontinua cuyo desplazamiento se anima, así que
**la forma se queda quieta y sólo la luz se mueve por ella**. Ese es el motivo
de usar SVG: girar un anillo (un gradiente cónico, un arco, cualquier cosa bajo
`transform: rotate`) gira también la forma, y las esquinas dejan de coincidir
con el cuadrado redondeado de debajo. `pathLength="100"` normaliza el contorno,
de modo que la hoja de estilos habla en porcentajes del perímetro y no hay que
recalcular nada si cambian el avatar o su radio.

Responder a «¿quién está ocupado?» obliga a leer la línea de comandos de todos
los procesos, cosa que sólo puede hacer root, así que es un verbo del daemon
privilegiado. Una sola pasada por `/proc` responde por todos los agentes a la
vez (no una llamada por agente), y eso es lo que la hace lo bastante barata
como para que la barra lateral la pida cada cinco segundos. Esa misma pasada
sostiene `only_if_idle`, así que el buzzer y la interfaz no pueden discrepar
sobre si un agente está trabajando.

### Una tarjeta que vence se anuncia en la conversación

El chat de un agente es el registro de todo lo que se le ha pedido a ese
agente, no sólo de lo que alguien le escribió. Por eso, cuando el buzzer
arranca la ejecución de una tarjeta vencida, esa tarjeta se escribe en el
`chat.jsonl` del agente como un turno propio, y la respuesta de la ejecución lo
cierra: abrir la conversación muestra el trabajo llegando, lo que el agente
hizo con él y lo que costó.

Hay tres decisiones que lo sostienen.

**Se escribe cuando arranca la ejecución, no cuando se crea la tarjeta.** Una
tarjeta programada para esta noche y borrada esta tarde nunca se ejecutó, y una
conversación diciendo que se entregó sería el registro de algo que no ocurrió.
El buzzer sólo ve tarjetas que siguen en el tablero, así que escribir en el
momento del timbre es lo que hace que el anuncio sea cierto.

**El archivo guarda los campos de la tarjeta, no una frase.** `role: "card"`
lleva el id, el título, quién la asignó y si se pidió para ya; el texto del
mensaje son las instrucciones de la propia tarjeta. Todas las palabras que hay
alrededor las pone la interfaz, en el idioma del usuario: la misma regla que
hace que una ejecución cortada guarde `ceiling: "tokens"` y no una frase en
inglés.

**«Ya» y «a las 13:45» hay que distinguirlos, y cuando se despierta al agente
las dos horas están en el pasado.** Por eso el tablero guarda cuál de las dos se
pidió (`run_mode`) en vez de deducirlo después comparando con el reloj, y la
palabra `now` viaja desde el navegador hasta `kanban.fValidateRunAt` como
palabra, convirtiéndose en una hora en el único sitio que además anota qué era.

Escribirlo es trabajo del daemon privilegiado y no del buzzer: `chat.jsonl` vive
en una carpeta 0700 del agente, y el buzzer corre como `boa`. El daemon hace
fork, baja privilegios al agente, escribe el anuncio y sólo entonces arranca la
ejecución; y si no se puede escribir en la carpeta, la ejecución arranca igual.
El anuncio es el registro del trabajo, no el trabajo.

El fallo contrario no es inofensivo y se trata al revés: si el proceso no se
puede arrancar **después** de haber abierto el turno, el daemon escribe el fallo
en ese turno antes de propagar el error. Nada más lo cerraría, y un turno
abierto no deja sólo una tarjeta sin responder: deja el cuadro de escribir de
ese agente cerrado para siempre.

La ejecución que viene después no es ni una ejecución programada normal ni un
turno de chat. Escribe su respuesta en el chat, porque la pregunta está ahí,
pero **no** se le reenvía la conversación: su prompt es la tarjeta, y reenviar
diez intercambios cobraría a cada ejecución programada una conversación que
nadie está teniendo. En el runner son dos banderas distintas —`vWritesToChat` y
`vIsChat`— y esa distinción es todo el asunto. El corolario: una ejecución que
para antes de preguntar nada al modelo (agente apagado, techo diario) tiene que
cerrar el turno igualmente, o la interfaz espera una respuesta para siempre y el
cuadro de escribir se queda cerrado.

### La documentación de la API es una página de esta aplicación

Se renderiza a partir del spec OpenAPI que construye este proyecto, en vez de
cargar Swagger UI desde un CDN, porque el servidor de producción es una máquina
de la LAN que puede no tener salida a Internet. De que sea una página nuestra y
no un widget ajeno salen dos cosas.

**Sigue el idioma elegido.** El spec se queda en inglés: es el contrato de una
API cuyos nombres de campo, ids y mensajes de error son todos en-US, y un
`openapi.json` traducido describiría una API que no existe. Lo que se traduce
es la PÁGINA: `fAnnotateSpecForTranslation` le cuelga una clave `data-i18n` a
cada trozo de inglés antes de renderizar, y el navegador la cambia igual que en
cualquier otra página. Así las cadenas siguen en los `.json` del frontend, al
lado de todas las demás, y funciona también para un lector anónimo. Las claves
se derivan del texto y de la ruta, no se escriben a mano, así que un endpoint
nuevo trae las suyas; una clave sin traducción se queda en inglés, que es lo
que hace `fApplyTranslations` con una clave que no conoce.

**Ocupa la columna entera**, como cualquier otra página. Antes mantenía una
medida de 900px y se centraba, que se lee bien en prosa y mal aquí: la página
es sobre todo tablas de parámetros y bloques de JSON, y se estaban metiendo en
un tercio de una pantalla ancha con los márgenes vacíos a los lados.

### Los adjuntos de imagen requieren un permiso de herramienta

`browser.screenshot` guarda un archivo; `image.send` lo adjunta a la respuesta.
Es un permiso separado, incluido en la plantilla web-navigator. La herramienta
copia el PNG a `agents/<id>/attachments/<id-opaco>.png`, con directorio 0700 y
archivo 0600. Sobrescribir la captura original no cambia una respuesta anterior.
`ToolContext.lAttachments` lleva las referencias a `AgentRun.fRecordChatAnswer`
y a los informes de fallo o de ejecuciones sin pregunta previa.

Sólo el ejecutor lee esos archivos privados para la aplicación web. El verbo
`read_chat_attachment` exige una referencia en el chat del agente, abre cada
componente del directorio sin seguir enlaces y comprueba que sea un archivo
regular propiedad de ese agente. Lee bloques de 1 MiB; las respuestas base64
respetan el límite del protocolo incluso para adjuntos de 50 MiB. El endpoint
HTTP exige sesión y transmite el PNG con `private, no-store`. El frontend
construye las URL locales con los identificadores, nunca con URL del modelo.

Telegram usa [sendPhoto](https://core.telegram.org/bots/api#sendphoto) cuando
la imagen cumple sus límites y [sendDocument](https://core.telegram.org/bots/api#senddocument)
para capturas largas o grandes, conservando el PNG original. Se suben los bytes
como multipart; no hace falta publicar el archivo ni dar el token del bot al
agente. `telegram_deliveries` registra cada parte de texto o imagen entregada.
Los reintentos continúan por la parte pendiente; borrar la fila pendiente borra
también esos registros. Los fallos permanentes se comunican al usuario.
Telegram y Discord comparan las fechas UTC de SQLite con segundos Unix;
interpretarlas como hora local hacía caducar envíos recientes durante el horario de verano.

### Sin paso de compilación

El frontend son plantillas Jinja2, CSS plano y JavaScript plano. El destino de
producción es una máquina Debian o Alpine autoalojada; un despliegue que
necesita una
cadena de herramientas de Node para cambiar una hoja de estilos es un
despliegue que se pudre. Por lo mismo, `/api/doc/` renderiza su propia
especificación OpenAPI en vez de cargar Swagger UI desde una CDN: un servidor
de LAN puede no tener salida a Internet, y una documentación que falla sin ella
falla justo cuando alguien está depurando.

---

### Transcripción de audio

Al arrancar servicios con OpenRC, el instalador cierra los descriptores 3 y 4 de los comandos `rc-service`. Son las copias de stdout/stderr de su sesión SSH: se comprobó que `supervise-daemon` las heredaba y mantenía abierta la conexión después de terminar correctamente. La salida normal sigue registrándose en `install.log`.

`audio_transcription` guarda una única configuración JSON validada en `settings.audio_transcription`. Los adaptadores de OpenAI, Groq, Mistral y Together usan multipart; Hugging Face y Cloudflare reciben WAV binario. Reutilizan `api_keys` y nunca devuelven secretos al navegador. FFmpeg limita formatos, protocolos, tamaño, duración y tiempo de ejecución. El audio se divide en segmentos de 120 segundos (30 segundos para los endpoints binarios de Hugging Face y Cloudflare, sin depender de opciones de generación para audios largos); whisper.cpp y los decodificadores se ejecutan como `boa`, sin shell ni cambio automático de proveedor.

`audio_inbox` conserva destino, configuración y transcripción en SQLite. Un hilo de `boa-telegram`, protegido por un bloqueo de proceso, recupera la cola al reiniciar. El turno reservado permite reconocer una petición repetida al ejecutor antes de comprobar si el agente está ocupado. Registrar el envío terminado y añadir `telegram_pending` forman una única transacción. El audio privado vive en `/opt/boa/audio/` (0700, propietario boa), se sirve sólo con sesión y referencia en el chat, y se elimina al vaciar los turnos procesados del chat.

Ambos instaladores compilan whisper.cpp v1.9.4, verificando el SHA-256 del archivo fuente, y descargan `base`. `whisper_models.json` recoge los 30 nombres, tamaños y hashes oficiales. Sólo el ejecutor root puede descargar modelos mediante `install_whisper_model`; no admite URL ni ruta arbitrarias. Escribe un archivo parcial y sólo lo publica tras verificar el hash. `whisper/` pertenece a root; `boa` únicamente lee los modelos. Las actualizaciones conservan modelos y audios; las copias incluyen los audios pero no los modelos. Un Python ausente se instala con las dependencias antes de comprobar la versión mínima.

## 2. Mapa de módulos

| Módulo | Ruta | Responsabilidad | Depende de | Usado por |
|---|---|---|---|---|
| `audio_transcription` | `backend/core/audio_transcription.py` | Configuración y motores de voz | db, api_keys, whisper_runtime | audio_inbox, api |
| `audio_inbox` | `backend/core/audio_inbox.py` | Cola persistente, destino, reintentos y reproducción privada | db, exec_client, audio_transcription | telegram_listener, api |
| `whisper_runtime` | `backend/core/whisper_runtime.py` | Catálogo, estado y descarga verificada de modelos | paths, whisper_models.json | installer, exec_daemon, api |
| `settings_audio.js` | `frontend/static/js/settings_audio.js` | Formulario Audio, descarga y progreso | api.js, i18n.js | settings.js, settings_audio.html |
| `paths` | `backend/core/paths.py` | Todas las rutas y la validación de ids de agente | — | todo |
| `db` | `backend/core/db.py` | Conexiones SQLite y los dos esquemas | `paths` | `agents`, `kanban`, `auth`, `bootstrap` |
| `agents` | `backend/core/agents.py` | Modelo de agente, `info.json`, índice, hash de tokens | `db`, `paths` | `exec_daemon`, `agent_api`, `api` |
| `bootstrap` | `backend/core/bootstrap.py` | Inicialización de primera ejecución | `agents`, `db`, `paths` | instalador |
| `exec_protocol` | `backend/core/exec_protocol.py` | Protocolo y lista de verbos | — | `exec_daemon`, `exec_client`, `agent_api` |
| `exec_daemon` | `backend/core/exec_daemon.py` | El daemon con privilegios (root) | `agents`, `paths`, `run_journal` | servicio `boa-exec` |
| `exec_client` | `backend/core/exec_client.py` | Cliente del anterior | `exec_protocol`, `paths` | `web/api` |
| `agent_api` | `backend/core/agent_api.py` | El daemon con el que hablan los agentes | `agents`, `kanban`, `channels` | servicio `boa-agent-api` |
| `agent_api_client` | `backend/core/agent_api_client.py` | Cliente del anterior | `agent_api`, `exec_protocol` | las herramientas incluidas |
| `runner` | `backend/core/runner.py` | Una ejecución: el bucle y sus techos | `providers`, `tool_registry`, `run_journal` | cron, `exec_daemon` |
| `run_journal` | `backend/core/run_journal.py` | El `runs.jsonl` de cada agente | `paths` | `runner`, `exec_daemon` |
| `chat` | `backend/core/chat.py` | El `chat.jsonl` de cada agente y la conversación que se le reenvía al modelo | `paths` | `runner`, `exec_daemon` |
| `memory` | `backend/core/memory.py` | El `memory.md` de cada agente, que entra en el prompt de sistema de cada ejecución | `paths` | `runner`, `exec_daemon`, herramientas |
| `skills` | `backend/core/skills.py` | Los procedimientos compartidos de `/opt/boa/skills/`, una carpeta cada uno. Parsea el `SKILL.md`, construye el índice que va al prompt y dice cuáles de las habilidades de un agente siguen existiendo | `paths` | `runner`, `exec_daemon`, `web/api`, `skill.read` |
| `provider_models` | `backend/core/provider_models.py` | Catálogos de modelos de `config/providers/*.json` | `paths` | `web/api` |
| `api_keys` | `backend/core/api_keys.py` | Las claves compartidas de los proveedores, en `config/apikeys/*.key`, escritas en 0600 dentro de una carpeta 0700. Nunca devuelve una clave al navegador, sólo si hay una guardada y sus últimos cuatro caracteres | `paths` | `agent_api`, `web/api` |
| `tool_registry` | `backend/core/tool_registry.py` | Descubrimiento, permisos y despacho de herramientas | `paths` | `runner`, `web/api` |
| `attachments` | `backend/core/attachments.py` | Copias privadas de PNG, identificadores opacos, comprobación de propietario y lecturas acotadas | `paths` | `image_send`, `exec_daemon`, `exec_client`, `telegram_listener` |
| `image_send` | `backend/tools/image_send.py` | Adjunta un PNG del agente a la respuesta mediante el contexto de herramientas | `attachments`, `tool_registry` | `runner` |
| `public_url` | `backend/core/public_url.py` | Si una URL que le han dado a un agente resuelve a una dirección pública. Formulado en positivo con `is_global` más un rechazo explícito de multicast, porque una lista de rangos a rechazar es una lista a la que se le olvida uno: se le había olvidado 100.64.0.0/10 | — | `web.fetch`, `rss.fetch`, `browser` |
| `agent_scripts` | `backend/core/agent_scripts.py` | Los scripts que un agente se escribe y las líneas de cron que los ejecutan. Valida nombres y horarios, y NUNCA reescribe la línea de despertar | `paths` | `script.*`, `cron.*` |
| `kanban` | `backend/core/kanban.py` | El tablero y su historial | `db` | `agent_api`, `web/api` |
| `channels` | `backend/core/channels.py` | Telegram, Discord, Mattermost, X. Enviar, para los cuatro; leer, para los dos a los que se puede contestar | `paths`, `telegram_html`, `discord_markdown` | `agent_api`, `web/api`, los dos listeners |
| `agent_routing` | `backend/core/agent_routing.py` | Lo que los dos listeners hacen igual: la lista de agentes, sacar el nombre de un agente de un mensaje, la respuesta con la que se cerró un turno y el informe de estado | `agents`, `chat`, `exec_client` | `telegram_listener`, `discord_listener` |
| `providers.base` | `backend/providers/base.py` | Interfaz de adaptador y forma neutra de mensaje | — | todos los adaptadores |
| `providers.factory` | `backend/providers/factory.py` | Nombre de proveedor → clase de adaptador | `providers.base` | `runner`, `web/api` |
| `providers.openai_dialect` | `backend/providers/openai_dialect.py` | La petición chat/completions que comparten los adaptadores del dialecto de OpenAI; las particularidades se quedan en cada adaptador | `providers.base` | casi todos los adaptadores |
| `providers.*` | `backend/providers/<nombre>.py` | Un adaptador por proveedor | `providers.base`, `providers.openai_dialect` | `factory` |
| `web.server` | `backend/web/server.py` | Fábrica Flask, clave de sesión, cabeceras de seguridad | `db`, `web.*` | gunicorn |
| `deploy/haproxy/boa.cfg` | `deploy/haproxy/boa.cfg` | Terminación TLS, PROXY protocol, 11080 → 11443 | — | servicio `boa-proxy` |
| `web.auth` | `backend/web/auth.py` | Login, sesiones, límite de intentos | `db` | `web.api`, `web.views` |
| `web.api` | `backend/web/api.py` | Todo lo que hay bajo `/api/admin/` | `exec_client`, `kanban`, `channels` | navegador |
| `web.api_doc` | `backend/web/api_doc.py` | Especificación OpenAPI y su página. Anota el spec con claves i18n sólo para la página, nunca para `openapi.json` | `channels`, `providers.factory` | navegador |
| `web.views` | `backend/web/views.py` | Las páginas HTML | `web.auth` | navegador |
| `buzzer` | `backend/core/buzzer.py` | Vigila el tablero y lanza una ejecución cuando una tarjeta vence | `kanban`, `exec_client` | servicio `boa-buzzer` |
| `telegram_listener` | `backend/core/telegram_listener.py` | Hace long-polling a Telegram, dirige cada mensaje a un agente y devuelve la respuesta | `channels`, `exec_client`, `telegram_inbox` | servicio `boa-telegram` |
| `telegram_inbox` | `backend/core/telegram_inbox.py` | Qué agente dijo qué en Telegram, y qué preguntas siguen sin respuesta. La caducidad se calcula en UTC | `db` | `telegram_listener`, `agent_api` |
| `discord_listener` | `backend/core/discord_listener.py` | Consulta un canal de Discord, dirige cada mensaje a un agente y devuelve la respuesta | `agent_routing`, `channels`, `exec_client`, `discord_inbox` | servicio `boa-discord` |
| `discord_inbox` | `backend/core/discord_inbox.py` | Las mismas dos tablas para Discord. Separadas de las de Telegram: un snowflake es una cadena, y un listener no debe poder contestar las preguntas del otro. La caducidad se calcula en UTC | `db` | `discord_listener`, `agent_api` |
| `discord_markdown` | `backend/core/discord_markdown.py` | Markdown a lo que Discord sí pinta, troceado en mensajes de 2000 caracteres. Las tablas se vuelven bloques de código; un bloque dentro del que caiga el corte se cierra y se vuelve a abrir | `telegram_html` (los patrones de bloque) | `channels` |
| `discord_texts` | `backend/core/discord_texts.py` | Las tres frases que Discord dice de otra manera. Todo lo demás cae en `telegram_texts`, así que un solo catálogo sirve a los dos bots | `telegram_texts` | `discord_listener` |
| `browser` | `backend/core/browser.py` | El navegador compartido y el perfil propio de cada agente. Un único manejador durante toda la ejecución, cerrado por `atexit`. Lleva la política de red por la que pasa cada petición | `paths`, `public_url` | las cinco herramientas `browser.*` |
| `telegram_html` | `backend/core/telegram_html.py` | Markdown a las catorce etiquetas que Telegram acepta. Los mismos patrones que `markdown.js`, para que los dos renderizadores coincidan en qué es markdown | — | `channels` |
| `telegram_texts` | `backend/core/telegram_texts.py` | Lo que dice el bot por su cuenta, en el idioma configurado en la instalación | `db` | `telegram_listener` |
| `markdown.js` | `frontend/static/js/markdown.js` | Pinta la respuesta de un agente como nodos del DOM, nunca como marcado | — | `dashboard.js` |
| `jsonhighlight.js` | `frontend/static/js/jsonhighlight.js` | Colorea los bloques de esquema de la página de documentación. Nodos del DOM, nunca marcado | — | `api_doc.html` |
| `agent_templates` | `backend/core/agent_templates.py` | Lee los agentes de ejemplo de `backend/agents/examples/`, un Markdown por agente; los archivos, identificadores y nombres predeterminados usan guiones, incluidos `kanban-watcher` y `web-navigator` | — | `web/api` |
| `mailbox` | `backend/core/mailbox.py` | IMAP y SMTP del buzón configurado. Tiene las credenciales para que los agentes no las tengan. Nombra un mensaje por UID y UIDVALIDITY, nunca por su posición en la carpeta | `db` | `agent_api` |
| `themes` | `backend/core/themes.py` | Lista las hojas de estilo de `frontend/themes/` y lee sus cabeceras | `paths` | `web/api`, `web/views` |
| `theme.js` | `frontend/static/js/theme.js` | Añade la hoja del tema elegido, desde el head, antes del primer pintado | — | todas las páginas |
| `night-high-contrast.css` | `frontend/themes/night-high-contrast.css` | Rellena de gris el agente seleccionado y dibuja las pestañas seleccionadas con un marco cerrado unido a la línea inferior | `app.css` | `theme.js` |
| `settings.js` | `frontend/static/js/settings.js` | Carga las pestañas principales con selectores limitados a su propia barra; `fRenderChannelForms` marca los canales configurados con `data-state="good"`, compartiendo el estilo del estado de las claves API y el `--colour-ok` del tema | `api.js`, `i18n.js`, `tools.js`, `app.css` | `settings.html` |
| `tools.js` | `frontend/static/js/tools.js` | Carga el catálogo dentro de Ajustes → Herramientas; conserva la subpestaña con `family` en la URL y repinta sus textos al volver desde Interfaz | `api.js`, `i18n.js` | `settings.js`, `settings_tools.html` |
| `app.css` | `frontend/static/css/app.css` | La clase `system-table` usa dos columnas compartidas, con el 35 % para las etiquetas, para alinear los datos de la máquina y los estados de sus servicios; `.chat-attachment img` ocupa el 100 % del ancho del texto, con altura automática y sin límite de altura; `.chat-audio` se ajusta al ancho del mensaje y su título hereda el color del texto | — | `settings.html`, `dashboard.html` |
| `system_info` | `backend/core/system_info.py` | Cómo se ve la máquina, leído sin privilegios | `paths` | `web/api` |

---

## 3. Índice de símbolos clave

Sólo los públicos o los que sostienen el diseño. Los números de línea se
mueven; lo fiable son el archivo y el comportamiento.

### Rutas e identidad

| Símbolo | Archivo:línea | Qué hace |
|---|---|---|
| `fNormalizeAgentId` | `backend/core/paths.py:155` | Valida un id de agente y lo rellena con ceros. **Toda ruta construida a partir de datos del usuario pasa por aquí.** Lanza excepción fuera de 0–999 |
| `fGetAgentHome` | `backend/core/paths.py:170` | `/opt/boa/agents/xxx` |
| `fReadAgentOwnedFile` | `backend/core/paths.py:392` | Cómo lee root un archivo del home de un agente: sobre el descriptor abierto, normal y del agente o rechazado, nunca más de un tope. El diario, el chat y la memoria pasan por acá |
| `fGetAgentApiTokenPath` | `backend/core/paths.py:476` | Dónde vive el token de API de un agente |

### Agentes

| Símbolo | Archivo:línea | Qué hace |
|---|---|---|
| `fValidateAgentName` | `backend/core/agents.py:53` | 2–40 caracteres, sin metacaracteres de shell |
| `fGetNextFreeAgentId` | `backend/core/agents.py:100` | El id libre más bajo, leído del sistema de archivos, desde 001 |
| `fBuildAgentInfo` | `backend/core/agents.py:113` | El `info.json` de un agente nuevo, con valores conservadores |
| `fWriteAgentInfo` | `backend/core/agents.py:179` | Escritura atómica conservando propiedad y modo 0600 |
| `fHashApiToken` | `backend/core/agents.py:216` | SHA-256; el token en claro nunca se guarda |
| `fFindAgentByApiToken` | `backend/core/agents.py:261` | Convierte un token en una identidad |

### El daemon con privilegios

| Símbolo | Archivo:línea | Qué hace |
|---|---|---|
| `fIsPeerAllowed` | `backend/core/exec_daemon.py:102` | Sólo root y `boa`, comprobado en cada conexión |
| `fRunPrivilegedCommand` | `backend/core/exec_daemon.py:118` | Ejecutá una lista de comando sin shell, opcionalmente como otro usuario |
| `fVerbCreateAgent` | `backend/core/exec_daemon.py:392` | Crea usuario, home, configuración y token; **deshace todo si algo falla** |
| `fStartRunner` | `backend/core/exec_daemon.py:300` | El único lugar que arranca un runner como el agente. El mensaje del chat o el prompt de la tarjeta van por su entrada estándar, nunca por la línea de órdenes |
| `fWatchRunner` | `backend/core/exec_daemon.py:251` | Espera a una ejecución: para su scope y apunta el fin de una a la que mataron |
| `fVerbWriteCrontab` | `backend/core/exec_daemon.py:748` | Instala un crontab como el propio usuario del agente |
| `fListRunningAgentIds` | `backend/core/exec_daemon.py` | Una sola pasada por `/proc` que nombra a todos los agentes con una ejecución en vuelo. Sostiene tanto `only_if_idle` como el contorno que gira en la barra lateral |
| `dVerbHandlers` | `backend/core/exec_daemon.py` | La tabla cerrada de verbos. Toda la superficie privilegiada son esas diez filas |

### La API de agentes

| Símbolo | Archivo:línea | Qué hace |
|---|---|---|
| `fAuthenticate` | `backend/core/agent_api.py:121` | El token **y** `SO_PEERCRED` deben coincidir |
| `fAgentMayUseKanban` | `backend/core/agent_api.py` | Si el tablero está activado y el agente tiene alguna herramienta de kanban. La mitad gruesa |
| `fRequireKanbanTool` | `backend/core/agent_api.py` | Un verbo, una herramienta, por nombre. Todos los handlers hacían la pregunta gruesa, así que `kanban.list_cards` —una lectura— llegaba a `fDeleteCard` para un agente que construyera la petición del socket por su cuenta |
| `fRequireOwnCard` | `backend/core/agent_api.py:283` | Un agente sólo puede cambiar tarjetas que creó o que le pertenecen |
| `fVerbChannelWrite` | `backend/core/agent_api.py` | Envía en nombre del agente, anteponiendo su nombre real |

### El bucle de ejecución

| Símbolo | Archivo:línea | Qué hace |
|---|---|---|
| `AgentRun` | `backend/core/runner.py:314` | Una conversación acotada |
| `fCheckCeilings` | `backend/core/runner.py` | Devuelve qué techo paró la ejecución, o vacío para seguir |
| `fSecondsLeft` | `backend/core/runner.py` | Tiempo que queda antes del plazo de la ejecución, con reloj monótono. Cada llamada al proveedor y cada herramienta reciben lo que queda, no el techo entero |
| `fTakeRunLock` | `backend/core/runner.py` | Un flock sobre `<home>/run.lock`, sostenido lo que dure el proceso. La única comprobación que también hace una ejecución lanzada por cron |
| `fTrimToByteBudget` | `backend/core/exec_protocol.py` | Las entradas más nuevas que caben en un presupuesto de bytes, y cuántas se descartaron. Se cuenta en bytes porque un número de líneas no es un tamaño |
| `fRunWithLimits` | `backend/tools/bash_run.py` | Ejecuta un comando con un techo de bytes aplicado MIENTRAS produce salida, y un plazo que mata al grupo de procesos entero |
| `fAskForClosingAnswer` | `backend/core/runner.py` | Tras un techo, pide una vez más y sin herramientas la respuesta que quedó a medias |
| `fExecute` | `backend/core/runner.py:462` | El bucle: preguntar, ejecutar herramientas, devolver resultados, parar |
| `fSelectAllowedTools` | `backend/core/runner.py:301` | Retira las herramientas de kanban si el agente lo tiene desactivado |
| `fReadStdinArguments` | `backend/core/runner.py:849` | La mitad del runner: lee el texto de la entrada estándar, con tope, y rechaza un mensaje de chat vacío |
| `fApplyResourceLimits` | `backend/core/runner.py:930` | Baja los límites de kernel de la propia ejecución antes de arrancar nada: procesos, archivos core, tamaño de archivo |
| `fRecordChatAnswer` | `backend/core/runner.py` | Escribe la respuesta cuando la ejecución tiene un turno que cerrar (`vWritesToChat`) |
| `fRecordChatFailure` | `backend/core/runner.py` | Cierra el turno cuando nada más lo hará, nombrando el motivo para que la interfaz lo traduzca |
| `fAppendCardMessage` | `backend/core/chat.py` | Anuncia una tarjeta vencida como un turno propio, con sus campos y sin frases |
| `fBuildCardAnnouncement` | `backend/core/buzzer.py` | Lo que se le cuenta al chat: quién la asignó y si se pidió para ya |

### Herramientas

| Símbolo | Archivo:línea | Qué hace |
|---|---|---|
| `fGetContext` | `backend/core/browser.py` | Arranca el navegador sobre el perfil de este agente, o devuelve el que ya está en marcha |
| `fClose` | `backend/core/browser.py` | Registrada con `atexit`. Sin ella cada ejecución deja un Chromium detrás |
| `fIsInstalled` | `backend/core/browser.py` | Si hay un navegador que manejar, para que las herramientas digan qué ejecutar en vez de lanzar una excepción |
| `fLoadAllTools` | `backend/core/tool_registry.py:103` | Carga todas las válidas; un archivo roto se omite, no es fatal |
| `fRunTool` | `backend/core/tool_registry.py:136` | Comprobá permisos y devuelve `(texto, es_error)`; una herramienta que lanza excepción nunca mata la ejecución |
| `ToolContext` | `backend/core/tool_registry.py:53` | Lo que se le dice a una herramienta sobre quién la llama |
| `fStoreImage` | `backend/core/attachments.py` | Copia un PNG de la carpeta del agente a un adjunto privado |
| `fReadImageChunk` | `backend/core/attachments.py` | Lee hasta 1 MiB; rechaza enlaces, otros propietarios y archivos especiales |
| `fVerbReadChatAttachment` | `backend/core/exec_daemon.py` | Exige que el chat del agente solicitado haga referencia al adjunto |
| `fGetChatAttachment` | `backend/web/api.py` | Transmite el PNG a un usuario con sesión, sin URL pública ni caché |
| `fRenderChatAttachments` | `frontend/static/js/dashboard.js` | Muestra las imágenes de la respuesta y avisa si alguna no se puede cargar |
| `fDeliverAnswerParts` | `backend/core/telegram_listener.py` | Reanuda el envío a Telegram desde la última parte entregada |

### Habilidades

| Símbolo | Archivo:línea | Qué hace |
|---|---|---|
| `fIsValidSkillName` | `backend/core/skills.py:57` | Un nombre, nunca una ruta. Refuta en vez de limpiar, igual que los nombres de plantilla y de tema |
| `fParseSkill` | `backend/core/skills.py:77` | La cabecera entre `---` y el cuerpo. Mismo parser que `agent_templates.fParseTemplate` |
| `fSelectInstalledSkills` | `backend/core/skills.py:194` | Los nombres de la lista de un agente que todavía existen en disco. **Todos los caminos hacia esta funcionalidad pasan por acá**, así que una habilidad borrada nunca llega a un prompt |
| `fBuildPromptSection` | `backend/core/skills.py:211` | El índice: una línea por habilidad, sólo nombres y descripciones. `""` cuando el agente no tiene ninguna |
| `fRunTool` | `backend/tools/skill_read.py` | Devuelve un cuerpo, comprobado contra el propio `info.json` del agente |


### Telegram, en los dos sentidos

| Símbolo | Archivo:línea | Qué hace |
|---|---|---|
| `fReadTelegramUpdates` | `backend/core/channels.py` | Un long poll. La conexión se hace hacia fuera, que es lo que permite que esto funcione detrás de un NAT sin abrir nada |
| `fSendToTelegram` | `backend/core/channels.py` | Envía, y devuelve el `message_id`: lo único que hace que una respuesta posterior se pueda dirigir |
| `fRedactSecrets` | `backend/core/channels.py` | Quita toda credencial de un error o de una línea de log. `str(RequestException)` cita la URL, y en tres de los cuatro canales la URL **es** la credencial |
| `fReadConfigForEditing` | `backend/core/channels.py` | El archivo de un canal tal como está en disco, para que guardar un cambio lo fusione en vez de reemplazarlo |
| `fListConfiguredChannels` | `backend/core/channels.py` | Devuelve Discord, Mattermost, Telegram y X en orden alfabético, con su estado y sin secretos; lo usan Ajustes y los permisos de cada agente |
| `fRouteMessage` | `backend/core/telegram_listener.py` | Para quién es un mensaje: el agente al que se responde, o el nombrado con @ |
| `fMatchNamedAgent` | `backend/core/telegram_listener.py` | Coincidencia más larga contra todos los nombres, porque un nombre de agente puede llevar espacios |
| `fIsFromTheConfiguredChat` | `backend/core/telegram_listener.py` | **Toda la autorización.** Lo que venga de otro chat se descarta sin responder |
| `fDeliverAnswers` | `backend/core/telegram_listener.py` | Devuelve todos los turnos que se hayan cerrado desde la pasada anterior |
| `fRememberMessage` | `backend/core/telegram_inbox.py` | Ata un mensaje enviado al agente que lo envió, podado a los últimos cientos |
| `fRouteMessage` | `backend/core/telegram_listener.py` | Para quién es un mensaje: el agente al que se responde, el nombrado con @ o /, o el seleccionado |
| `fReadSelectedAgent` | `backend/core/telegram_listener.py` | Con quién es la conversación, comprobado contra la plantilla para que un agente borrado deje de capturarlo todo |
| `fBuildAgentButtons` | `backend/core/telegram_listener.py` | El teclado inline con el que responde /agents. El texto de un botón sí lo elige el bot; el del menú de comandos no |
| `fBuildStatusReport` | `backend/core/telegram_listener.py` | Lo que dice /status. Un agente que no puede leer se lista diciéndolo, nunca se omite |
| `fHandleCallback` | `backend/core/telegram_listener.py` | Una pulsación en el botón de un agente: primero se confirma, después se selecciona |
| `fRender` | `backend/core/telegram_html.py` | Markdown al HTML de Telegram. Los encabezados pasan a negrita, las listas a viñetas y las tablas a un bloque monoespaciado: Telegram no tiene etiqueta para ninguna de las tres |
| `fEscape` | `backend/core/telegram_html.py` | `&`, `<`, `>`. **Se llama antes de que nada envuelva el texto**, nunca después |
| `fEscapeAttribute` | `backend/core/telegram_html.py` | Lo mismo más la comilla doble, para un href. Una comilla en una URL cerraría el atributo e inventaría los siguientes |
| `fRenderWithinLimit` | `backend/core/telegram_html.py` | Acorta el markdown y vuelve a renderizar hasta que el HTML quepa. Recortar el HTML dejaría una etiqueta a medio escribir |

### Discord, en los dos sentidos

| Símbolo | Archivo:línea | Qué hace |
|---|---|---|
| `fReadDiscordMessages` | `backend/core/channels.py` | Una consulta. **Invierte lo que devuelve Discord**, que es lo más nuevo primero: contestar en ese orden le haría leer al agente una conversación al revés |
| `fSendToDiscord` | `backend/core/channels.py` | Envía, en tantas partes como haga falta por el límite de 2000 caracteres, y devuelve el id de todas |
| `fCallDiscord` | `backend/core/channels.py` | Una llamada. Un 429 con un `retry_after` corto se espera una vez; cualquier otro 4xx es `ChannelRejected` |
| `fGetDiscordMode` | `backend/core/channels.py` | `"bot"`, `"hook"` o `""`. Un webhook envía y nada más |
| `fReadDiscordBotUser` | `backend/core/channels.py` | Qué bot es este, escrito en el log una vez por arranque: cuando no llega nada, esa es la primera pregunta |
| `fRenderToMessages` | `backend/core/discord_markdown.py` | Una respuesta, como la lista de mensajes que hay que enviar para ella |
| `fSplit` | `backend/core/discord_markdown.py` | Corta por líneas, cerrando y reabriendo el bloque de código dentro del que caiga el corte |
| `fIsFromTheConfiguredChannel` | `backend/core/discord_listener.py` | Todo mensaje consultado viene de ese canal por construcción; se comprueba igualmente, porque «por construcción» es una propiedad del código de hoy |
| `fReadCommand` | `backend/core/discord_listener.py` | `!agents`, `!status`, `!help`, y las formas con `/`. Sólo si son la primera palabra entera, o un agente llamado `status` sería inalcanzable |
| `fReadMessageText` | `backend/core/discord_listener.py` | El texto sin la mención al bot delante: Discord convierte `@Boa` en `<@123>` antes de que nadie más lo vea |
| `fStartFromTheNewestMessage` | `backend/core/discord_listener.py` | Por dónde empieza una instalación recién hecha. Un bot encendido esta tarde no debe contestar un mes de canal |
| `fReadAfterId` / `fWriteAfterId` | `backend/core/discord_listener.py` | La marca, en `config/discord-after`. Un snowflake, no un contador |
| `fRememberMessage` | `backend/core/discord_inbox.py` | Ata una parte enviada al agente que la envió. Se poda por orden de inserción, no por id |

### Lo que comparten los dos listeners

| Símbolo | Archivo:línea | Qué hace |
|---|---|---|
| `fMatchNamedAgent` | `backend/core/agent_routing.py` | Coincidencia más larga sobre todos los nombres conocidos. Los prefijos son un argumento: Telegram acepta `@` y `/`, Discord añade `!` |
| `fBuildStatusReport` | `backend/core/agent_routing.py` | Lo que dice /status. Recibe el catálogo de frases del servicio que pregunta y el nombre de su unidad, que son las dos únicas cosas que cambian |
| `fFindClosedAnswer` | `backend/core/agent_routing.py` | Lo que dijo un agente al cerrar un turno, leído a través del ejecutor |
| `fListAgentNames` | `backend/core/agent_routing.py` | La lista de agentes, sacada del índice: el home de un agente es 0700 y su info.json no es de un listener |

### Los scripts y el cron de un agente

| Símbolo | Archivo:línea | Qué hace |
|---|---|---|
| `fValidateScriptName` | `backend/core/agent_scripts.py` | COMPRUEBA el nombre en vez de limpiarlo: lo que no sea un nombre de archivo llano se rechaza, que es UNA regla en vez de una regla más lo que la limpieza acabe haciendo |
| `fValidateSchedule` | `backend/core/agent_scripts.py` | La forma de un horario de cron, y lo único que merece rechazarse: un trabajo que se dispara más veces de lo que nadie quería |
| `fIsRunnerLine` | `backend/core/agent_scripts.py` | La línea que despierta al agente. NUNCA se reescribe desde aquí: un agente que la borrara se quedaría mudo para siempre y sin forma de enterarse |
| `fAddCronLine` | `backend/core/agent_scripts.py` | Añade una línea que ejecuta uno de los scripts del propio agente. El script tiene que existir antes |
| `fRemoveCronLines` | `backend/core/agent_scripts.py` | Quita todas las líneas que ejecutan un script, y el comentario de encima de cada una |

### Tablero y canales

| Símbolo | Archivo:línea | Qué hace |
|---|---|---|
| `fAddCard` | `backend/core/kanban.py:132` | Tarjeta y primer evento en una sola transacción |
| `fMoveCard` | `backend/core/kanban.py:188` | Movimiento más evento de historial |
| `fValidateRunAt` | `backend/core/kanban.py:68` | Acepta `"now"`, una hora del navegador o una hora guardada, y normaliza las tres |
| `fReadRunMode` | `backend/core/kanban.py:100` | Qué clase de hora se pidió: `now`, `at` o ninguna |
| `fWasRequestedImmediately` | `backend/core/kanban.py` | Si la tarjeta decía «ya». Se lee de `run_mode`, nunca se deduce del reloj |
| `fAssignCard` | `backend/core/kanban.py` | Entrega una tarjeta, anotando en `assigned_by` quién la entregó |
| `fAgentOwnsCard` | `backend/core/kanban.py:462` | Creador **o** asignado |
| `fDeleteCard` | `backend/core/kanban.py:480` | Borra, dejando una fila en `deleted_cards` |
| `fReadMessages` | `backend/core/mailbox.py` | Los mensajes más nuevos de una carpeta, en sólo lectura: no marca nada como leído |
| `_fParseFolderLine` | `backend/core/mailbox.py` | Una línea LIST como flags, delimitador y nombre. Lanza excepción en vez de adivinar: una lista ilegible es un error, no una cuenta sin carpetas |
| `fListFoldersWithFlags` | `backend/core/mailbox.py` | Cada carpeta con sus flags SPECIAL-USE |
| `fFindTrashFolder` | `backend/core/mailbox.py` | Primero `\\Trash`, después los nombres en nueve idiomas. `""` significa que no hay; un fallo lanza excepción |
| `fIsForwardAllowed` | `backend/core/mailbox.py` | Si una dirección está en la lista del usuario. Se comprueba donde está la contraseña, nunca en un prompt |
| `fListTemplates` | `backend/core/agent_templates.py` | Todos los agentes de ejemplo, ordenados por el nombre que se ve |
| `fParseTemplate` | `backend/core/agent_templates.py` | Cabecera `clave: valor` entre dos `---`; el cuerpo es el prompt |

### La barra lateral

| Símbolo | Archivo:línea | Qué hace |
|---|---|---|
| `fRenderSidebar` | `frontend/static/js/api.js` | Reconstruye la lista de agentes. Se llama al cargar la página y tras crear o borrar, nunca en un temporizador |
| `fPickDifferentModel` | `frontend/static/js/dashboard.js` | El modelo que se rellena al elegir proveedor. El secundario evita el del principal: mismo proveedor y mismo modelo falla por el mismo motivo, siempre |
| `fSetAgentAvatarActivity` | `frontend/static/js/api.js` | Pone `data-running` y el texto emergente en un avatar, y añade o quita el trazo |
| `fBuildAgentActivityArc` | `frontend/static/js/api.js` | El rect redondeado SVG colocado sobre el borde, con `pathLength="100"` para que la hoja de estilos hable en porcentajes del perímetro |
| `fRefreshAgentActivity` | `frontend/static/js/api.js` | Cada 5 s repinta sólo los contornos; se salta mientras la pestaña está oculta |
| `fDescribeChannelName` / `fDescribeProviderName` | `frontend/static/js/api.js` | El nombre con el que se llama a sí mismo un canal o un proveedor. NO son claves i18n: DeepSeek es DeepSeek en todos los idiomas |
| `fDescribeTool` / `fDescribeToolArgument` | `frontend/static/js/api.js` | Lo que dice una herramienta y sus argumentos, en el idioma del lector. El esquema se queda en inglés: es lo que se le manda al modelo |
| `fRenderToolCheckboxes` | `frontend/static/js/dashboard.js` | Una caja por familia de herramientas, construida con lo que haya instalado. MUEVE el interruptor del kanban a la caja de kanban en vez de recrearlo, para que una casilla marcada y sin guardar sobreviva al repintado |

### Mensajes emergentes

| Símbolo | Archivo:línea | Qué hace |
|---|---|---|
| `fShowNotice` | `frontend/static/js/api.js` | Pone un mensaje en la capa que hay sobre la columna de contenido. Sustituye al que hubiera, así que las confirmaciones nunca se apilan |
| `fShowError` | `frontend/static/js/api.js` | Lo mismo, como error: sin temporizador, se cierra a mano |
| `fConfirmLogout` | `frontend/static/js/api.js` | Abre `fConfirm` en el centro de la pantalla; sólo navega a `/logout` al confirmar. Cancelar o Escape mantienen la sesión abierta |
| `fHideNotice` | `frontend/static/js/api.js` | Lo desvanece y luego lo quita, para que no se apague de golpe justo cuando se acaba el tiempo |
| `fGetNoticeSeconds` / `fSetNoticeSeconds` | `frontend/static/js/api.js` | Cuánto se muestra un mensaje, guardado en este navegador y acotado entre 1 y 30 segundos |
| `fBuildCloseCross` | `frontend/static/js/api.js` | La cruz de cerrar, como dos líneas SVG. El carácter «×» está centrado sobre el eje matemático de la fuente y no dentro de su caja, así que queda por encima del centro del botón haga lo que haga el botón |

### Coloreado del JSON

| Símbolo | Archivo:línea | Qué hace |
|---|---|---|
| `cJsonTokenPattern` | `frontend/static/js/jsonhighlight.js` | Una sola expresión para los cuatro tipos de token. Una cadena seguida de dos puntos es una clave, que es lo ÚNICO que distingue un nombre de un valor |
| `fHighlightJsonElement` | `frontend/static/js/jsonhighlight.js` | Reconstruye un bloque como spans de color y texto plano. Cada carácter del original se emite exactamente una vez, así que el bloque se sigue copiando como JSON válido |

### Proveedores

| Símbolo | Archivo:línea | Qué hace |
|---|---|---|
| `BaseProvider.fSendMessages` | `backend/providers/base.py` | El único método que implementa cada adaptador |
| `fNeutralMessagesToOpenAiFormat` | `backend/providers/base.py` | Forma neutra → chat/completions |
| `fToolNameToWire` / `fToolNameFromWire` | `backend/providers/base.py` | `familia.accion` ↔ `familia__accion`, porque ningún proveedor acepta el punto |
| `fDescribeHttpError` | `backend/providers/base.py` | Añade lo que dijo el proveedor a un fallo HTTP pelado |
| `fBuildProvider` | `backend/providers/factory.py` | Configuración → instancia de adaptador, importando de forma perezosa |
| `fResolveProviderName` | `backend/providers/factory.py` | Sigue los alias, de modo que `gemini` y `google` llegan a un único adaptador |
| `fSendChatCompletion` | `backend/providers/openai_dialect.py` | La petición chat/completions compartida, parametrizada por las particularidades de cada adaptador |
| `fNormalizeMessageContent` | `backend/providers/openai_dialect.py` | Aplana una respuesta cuyo contenido llegó en bloques, descartando el razonamiento |

---

### Símbolos de audio

| Símbolo | Archivo:línea | Responsabilidad |
|---|---|---|
| `fTranscribe` | `backend/core/audio_transcription.py:223` | Decodifica, segmenta y transcribe |
| `fEnqueueTelegram` | `backend/core/audio_inbox.py:57` | Guarda el destinatario antes de transcribir |
| `fRunOneJob` | `backend/core/audio_inbox.py:233` | Procesa o reintenta un turno reservado |
| `fDownloadModel` | `backend/core/whisper_runtime.py:134` | Valida tamaño y SHA-256 antes de publicar |
| `fGetChatAudio` | `backend/web/api.py:457` | Reproduce audio con sesión y referencia de chat |

## 4. Flujos principales

### Crear un agente

```
navegador  POST /api/admin/agents {name}
  web/api.fCreateAgent
    exec_client.fCreateAgent          → socket Unix /run/boa/exec.sock
      exec_daemon.ExecRequestHandler
        fGetPeerCredentials + fIsPeerAllowed    ← rechaza a todo lo que no sea root/boa
        fVerbCreateAgent
          agents.fValidateAgentName
          agents.fGetNextFreeAgentId            ← el más bajo libre, del sistema de archivos
          useradd --home-dir … --create-home
          agents.fWriteAgentInfo                 (0600, propiedad del agente)
          fWriteAgentFile system-prompt.md        (0600)
          fWriteAgentFile api-token              (0600)
          chmod 0700 sobre el home
          agents.fIndexAgent(…, vApiToken)       ← guarda sólo el SHA-256
        ante cualquier excepción: fRemoveAgentUser  ← nada de agentes a medio crear
```

### Una ejecución programada

```
cron (el crontab propio de agent-007)
  runner.py --agent-id 007            ← ya se ejecuta como agent-007
    fTakeRunLock                      ← rechazada → fRecordRunRefused, y para
    AgentRun.__init__
      fReadOwnInfo / fReadOwnSystemPrompt / fReadOwnApiToken
      fBuildSystemPrompt              ← prompt + memoria + índice de habilidades + idioma
      tool_registry.fLoadAllTools
      fSelectAllowedTools             ← retira kanban si está desactivado
    fExecute
      run_journal.fCountRunsOn        ← techo diario, de su propio journal
      factory.fBuildProvider
      bucle:
        fCheckCeilings                ← pasos, tokens, segundos
        provider.fSendMessages        ← max_tokens se encoge con lo gastado
        run_journal.fRecordUsage
        si no hay llamadas a herramientas: parar
        fRunToolCalls                 ← todos los resultados se devuelven juntos
      fAskForClosingAnswer            ← una llamada sin herramientas tras el
                                        techo de pasos o de tokens, para que
                                        lo ya pagado acabe en una respuesta
      run_journal.fRecordRunFinished  ← «stopped» si lo cortó un techo
```

### Una tarjeta vence

```
boa-buzzer (como boa), cada 5 segundos
  kanban.fListDueCards              ← con dueño, run_at pasado, sin timbre, sin terminar
  fRingOne
    fBuildCardAnnouncement          ← assigned_by → nombre, run_mode → immediate
    exec_client.fRunNow(prompt, only_if_idle, card)
      exec_daemon.fVerbRunNow                      ← como root
        fIsAgentRunning             ← ocupado: started=False, sin timbre, se reintenta
        fRunAsAgent → chat.fAppendCardMessage      ← anunciada, turno abierto
        Popen runner.py --prompt-on-stdin --turn-id …  ← como agent-007, el prompt por su stdin
    kanban.fMarkCardBuzzed          ← sólo después de que la ejecución arrancó
  runner.AgentRun (vWritesToChat, no vIsChat)
    fExecute                        ← prompt de la tarjeta, sin reenviar conversación
    fRecordChatAnswer               ← respuesta y coste cierran el turno
    fRecordChatFailure              ← o el motivo por el que no se ejecutó nada
```

### Un agente mueve una tarjeta

```
el modelo pide kanban.move_card
  tool_registry.fRunTool              ← rechaza si no se le concedió a este agente
    tools/kanban_move_card.fRunTool
      agent_api_client.fCallFromContext   → /run/boa/agent.sock
        agent_api.AgentRequestHandler
          fAuthenticate               ← hash del token + SO_PEERCRED
          fVerbKanbanMoveCard
            fAgentMayUseKanban        ← en el servidor, leyendo info.json
            fRequireOwnCard           ← sólo creador o asignado
            kanban.fMoveCard          ← movimiento + evento, una transacción
```

### Un agente envía un mensaje

```
el modelo pide channel.write
  tools/channel_write.fRunTool
    agent_api_client → agent_api.fVerbChannelWrite
      fAgentMayUseChannel             ← herramienta concedida Y canal concedido
      channels.fSendMessage(prefijo="[Nombre del agente]")
        fReadChannelConfig            ← como boa; el agente nunca ve esto
        fSendToTelegram / Discord / Mattermost / X
```


### Llega un mensaje desde Telegram

```
boa-telegram (como boa)
  fRefreshCommands                    ← /agents /status /help, cuando cambian
  fDeliverAnswers                     ← lo que haya terminado desde la última pasada
    exec_client.fReadChat             ← el chat está en un home 0700; sólo root lo lee
    channels.fSendToTelegram          ← "**nombre:**\n..." como respuesta
    telegram_inbox.fRemovePending
  channels.fReadTelegramUpdates       ← long poll: 25s en reposo, 3s mientras se contesta
    fIsFromTheConfiguredChat          ← lo demás se descarta, en silencio
    callback_query -> fHandleCallback ← una pulsación en el botón de un agente
      fSelectAgent                    ← desde aquí, lo que no vaya dirigido va ahí
    message -> fHandleMessage
      fHandleCommand                  ← /agents /status /help, respondidos y listo
      fRouteMessage                   ← reply, luego @nombre, luego el seleccionado
      exec_client.fSendChatMessage(source="telegram")
        exec_daemon.fVerbSendChatMessage
          chat.fAppendMessage(metadata={"source": "telegram"})
          Popen runner.py --chat-message-on-stdin --turn-id   ← el mensaje por su stdin
      telegram_inbox.fAddPending      ← en disco: un reinicio no puede perder la respuesta
```

La respuesta la envía el listener y no la ejecución, por la misma razón por la
que el anuncio de una tarjeta lo escribe el ejecutor: la ejecución corre como el
usuario del agente, y las credenciales del canal son de `boa`. La ejecución sólo
escribe en su chat; el listener lo lee y se encarga de enviarlo.

### Llega un mensaje desde Discord

```
boa-discord (como boa)
  fDeliverAnswers                     ← todo lo que ha terminado desde la pasada anterior
    exec_client.fReadChat             ← la conversación está en un home 0700; sólo root lo lee
    channels.fSendToDiscord           ← «**nombre:**\n…» como respuesta, en partes de 2000 caracteres
      discord_markdown.fRenderToMessages
    discord_inbox.fRememberMessage    ← todas las partes, para que responder a cualquiera enrute
    discord_inbox.fRemovePending
  channels.fReadDiscordMessages       ← GET /channels/<id>/messages?after=<id>
    (invertidos: Discord contesta lo más nuevo primero)
    fHandleMessage
      author.bot, type                ← lo que dijo él mismo, y todo lo que no es un mensaje
      fIsFromTheConfiguredChannel
      fReadCommand                    ← !agents !status !help, contestados y listo
      fRouteMessage                   ← respuesta, luego @nombre, luego el seleccionado
      exec_client.fSendChatMessage(source="discord")
      discord_inbox.fAddPending       ← en disco: un reinicio no puede perder la respuesta
  fWriteAfterId                       ← config/discord-after
```

La respuesta la envía el listener y no la ejecución, por lo mismo que en
Telegram: la ejecución es el usuario propio del agente, y las credenciales del
canal son de `boa`.

La primera pasada de una instalación recién hecha pide el mensaje más nuevo y
se queda sólo con su id. Un canal vacío se marca con el id más bajo que existe,
para que el **primer** mensaje que alguien escriba se conteste en vez de
gastarse en averiguar por dónde empezar.

### El bot no le muestra nada a un desconocido

El nombre de usuario de un bot es público: cualquiera que lo encuentre puede
abrir un chat con él. Por eso `fIsFromTheConfiguredChat` compara el `chat.id`
que Telegram pone en cada mensaje (y que el remitente no puede falsificar) con
el configurado, y `fHandleMessage` descarta lo que no coincide antes de
despachar ningún comando y antes de elegir agente. `fHandleCallback` hace lo
mismo con la pulsación de un botón. No se responde nada: contestar
confirmaría que el bot está vivo a quien lo esté sondeando. Tampoco se anota
nada. El descarte se registraba con el id del chat del que venía, que son datos
de otra persona y que habrían supuesto que esta instalación fuera juntando en
silencio una lista de quién encontró el bot. Lo que queda es un mensaje que
nunca existió.

El precio es real y conviene decirlo: un `chat_id` mal configurado se parece
ahora exactamente a un desconocido, y los mensajes del propio dueño se
desvanecen en silencio. El id configurado se escribe en el registro en cada
arranque («Registered 3 command(s) for chat <id> only»), que es el número con
el que comparar. Un mensaje del chat CONFIGURADO que no llega a ningún agente
sí se sigue registrando, porque ahí quien escribe es el dueño y «le escribí y
no pasó nada» no se distingue de «nunca llegó».

Lo que el filtro NO cubre, y no puede, es QUIÉN dentro del chat: un `chat_id`
que apunta a un grupo es un grupo en el que cualquier miembro puede hablar con
los agentes.

El mismo razonamiento decide dónde se escribe la lista de comandos.
`setMyCommands` recibe un ámbito, y `default` y `all_private_chats` los
resuelve cualquier usuario de Telegram, así que una lista escrita ahí es un
menú que se les muestra a los desconocidos, con «Estado del servidor» adentro,
anunciando que atrás hay una máquina que merece un empujón. Nunca podrían
ejecutar nada de eso, pero un cartel en una puerta cerrada sigue siendo un
cartel. `fSetTelegramCommands` escribe la lista sólo en el ámbito del chat
configurado y **borra** los dos públicos en cada refresco: una lista escrita
por una versión anterior de este código vive del lado de Telegram hasta que
algo la elimina. `fHideTelegramPublicProfile` vacía las otras dos cadenas
públicas, `setMyDescription` y `setMyShortDescription`, que son las que llenan
el chat vacío abajo de «¿Qué puede hacer este bot?».

Lo que se sigue viendo es el nombre del bot, su foto y el botón Iniciar, que
Telegram dibuja en todo chat vacío con un bot y que ninguna API puede sacar.
Apretarlo manda `/start`, que se descarta como cualquier otra cosa que venga
de otro chat.

### Por qué el menú lleva herramientas y no agentes

Telegram dibuja `/nombre` junto a cada entrada del menú de comandos —esa cadena
es la entrada, es lo que se escribe en el campo al tocarla, y no hay API que la
oculte—. Así que un menú de agentes nunca podría ser la lista de agentes que
alguien quería mirar, y encima crecía con la plantilla sin decir nada sobre para
qué servía el bot.

El menú lleva tres cosas que el bot sabe hacer. Qué agentes hay es una pregunta,
y `/agents` la responde con botones inline, donde un botón dice `os-watcher` y
nada más, porque el texto de un botón sí lo elige el bot.

Lo demás se deduce de ahí:

- **El agente seleccionado es persistente.** Tocar un botón o nombrar a un
  agente lo elige; todo lo que no vaya dirigido a nadie va ahí hasta que se
  elija otro. Nombrar al agente en cada línea está bien una vez y cansa al
  cuarto mensaje. Vive en `settings`, no en memoria, porque el servicio se
  reinicia en cada actualización.
- **Un reply sigue ganando.** No tiene ambigüedad, y es lo que hace alguien con
  un móvil en la mano. Nada más cambia la selección, así que un agente nunca
  hereda una conversación por ser el último que habló.
- **Un agente borrado deja de estar seleccionado.** `fReadSelectedAgent`
  comprueba la plantilla a la salida: llegar a nadie es mejor que llegar a quien
  haya heredado su id.
- **El bot habla el idioma de la instalación.** `agent_language` primero, el
  mismo ajuste con el que responden los agentes: sus líneas aparecen en la misma
  conversación que las de ellos.

### La barra lateral muestra quién está trabajando

```
cada 5 segundos, y justo después de enviar / ejecutar ahora / llegar respuesta
  api.js fRefreshAgentActivity        ← se salta mientras la pestaña está oculta
    GET /api/admin/agents
      web/api.fListAgents
        exec_client.fListRunningAgents          → /run/boa/exec.sock
          exec_daemon.fVerbListRunningAgents
            fListRunningAgentIds      ← una pasada por /proc, todos a la vez
      cada agente lleva `running`
    fSetAgentAvatarActivity           ← data-running en el avatar; la lista en
                                        sí nunca se reconstruye por temporizador
      fBuildAgentActivityArc          ← un rect redondeado SVG sobre el borde
  el CSS anima su stroke-dashoffset   ← la forma se queda quieta y el trazo
                                        encendido recorre el contorno
```

### Iniciar sesión

```
POST /login
  views.fLoginPage
    auth.fCountRecentFailures         ← 10 cada 15 minutos por dirección
    auth.fVerifyCredentials           ← argon2id; un correo erróneo también hashea
    auth.fRecordAttempt
    auth.fLogIn                       ← cookie de sesión, 12 horas
```

---

### Llega una nota de voz

`fHandleMessage → fRouteMessage → fEnqueueTelegram → audio_jobs → fRunOneJob → fDownloadTelegram → fTranscribe → fSubmitTranscript → fSendChatMessageLocked → runner`. La respuesta usa la entrega habitual de Telegram; el chat web añade transcripción y reproductor privado. Settings → Audio usa GET/PUT `/api/admin/audio`; descargar un modelo usa el RPC `install_whisper_model` y consulta su progreso sin bloquear la petición HTTP.

## 5. Mapa de entradas y rutas

### HTTP

| Ruta | Método | Handler | Archivo |
|---|---|---|---|
| `/login` | GET, POST | `fLoginPage` | `backend/web/views.py` |
| `/logout` | GET, POST | `fLogoutPage` | `backend/web/views.py` |
| `/` | GET | `fDashboardPage` | `backend/web/views.py` |
| `/kanban/` | GET | `fKanbanPage` | `backend/web/views.py` |
| `/tools/` | GET | `fToolsPage` → `/settings/?tab=tools` (conserva `family` y `agent`) | `backend/web/views.py` |
| `/settings/` | GET | `fSettingsPage` | `backend/web/views.py` |
| `/api/doc/` | GET | `fGetApiDocPage` | `backend/web/api_doc.py` |
| `/api/doc/openapi.json` | GET | `fGetOpenApiSpec` | `backend/web/api_doc.py` |
| `/api/admin/agent-templates` | GET | `fListAgentTemplates` | `backend/web/api.py` |
| `/api/admin/agents` | GET, POST | `fListAgents` (siempre lleva `running` por agente), `fCreateAgent` | `backend/web/api.py` |
| `/api/admin/agents?kanban=1` | GET | `fListAgents`, añade `reads_kanban` por agente | `backend/web/api.py` |
| `/api/admin/agents/<id>` | GET, PUT, DELETE | `fGetAgent`, `fUpdateAgent`, `fDeleteAgent` | `backend/web/api.py` |
| `/api/admin/agents/<id>/run` | POST | `fRunAgentNow` | `backend/web/api.py` |
| `/api/admin/agents/<id>/journal` | GET | `fGetAgentJournal` | `backend/web/api.py` |
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
| `/themes/<nombre>.css` | GET | `fThemeStylesheet` | `backend/web/views.py` |
| `/api/admin/channels` | GET | `fListChannels` | `backend/web/api.py` |
| `/api/admin/channels/<nombre>` | PUT | `fConfigureChannel` | `backend/web/api.py` |
| `/api/admin/audio` | GET, PUT | `fGetAudioSettings`, `fUpdateAudioSettings` | `backend/web/api.py` |
| `/api/admin/audio/models/<vModel>/install` | POST | `fInstallAudioModel` | `backend/web/api.py` |
| `/api/admin/agents/<vAgentId>/audio/<vAudioId>` | GET | `fGetChatAudio` | `backend/web/api.py` |
| `/api/admin/settings` | GET, PUT | `fGetSettings`, `fUpdateSettings` | `backend/web/api.py` |
| `/api/admin/status` | GET | `fGetStatus` | `backend/web/api.py` |

Todo lo que es API vive bajo `/api/`. Todo lo que hay bajo `/api/admin/`
requiere sesión.

### Sockets Unix

| `/run/boa-web/web.sock` | `0750 boa:boa` | gunicorn | La propia aplicación. Sólo `boa-proxy` llega a él |

| Socket | Modo | Servidor | Verbos |
|---|---|---|---|
| `/run/boa/exec.sock` | `0660 root:boa` | `exec_daemon` | `ping`, `create_agent`, `delete_agent`, `read_agent_info`, `write_agent_info`, `read_system_prompt`, `write_system_prompt`, `read_crontab`, `write_crontab`, `run_now`, `list_running_agents`, `read_run_journal`, `read_usage_summary`, `read_chat`, `read_chat_attachment`, `send_chat_message`, `clear_chat` |
| `/run/boa/agent.sock` | `0666` | `agent_api` | `who_am_i`, `kanban_add_card`, `kanban_move_card`, `kanban_delete_card`, `kanban_list_cards`, `channel_write`, `mail_read`, `mail_delete`, `mail_move`, `mail_forward` |

### Línea de comandos

| Comando | Archivo |
|---|---|
| `runner.py --agent-id NNN [--prompt … o --prompt-on-stdin] [--chat-message … o --chat-message-on-stdin] [--turn-id …] [--dry-run]` | `backend/core/runner.py` |
| `install-update-reinstall-debian.sh --install\|--update\|--reinstall\|--backup [file]\|--restore <file>` | `deploy/` |
| `install-update-reinstall-alpine.sh --install\|--update\|--reinstall\|--backup [file]\|--restore <file>` | `deploy/` |

---

## 6. Análisis de impacto

Qué se rompe si tocas esto.

| Componente | Cambiarlo afecta a |
|---|---|
| `paths.fNormalizeAgentId` | **Todas las rutas del sistema.** Es la única validación entre la entrada del usuario y una ruta del sistema de archivos. Debilitarla convierte cualquier id de agente en un salto de directorio |
| Constantes de `paths.py` | Los cuatro servicios, el instalador y las unidades de systemd. Cambiar `/opt/boa` implica reinstalar |
| `deploy/haproxy/boa.cfg` | Todas las peticiones. El `accept-proxy` tiene que coincidir con lo que envía el HAProxy de la máquina: con `send-proxy-v2` en ese backend hace falta, y sin él el bind rechaza todas las conexiones |
| El bind de `backend/web/gunicorn.conf.py` | Debe seguir siendo un socket Unix. Volver a darle a gunicorn un puerto y un certificado reintroduce el fallo de PROXY antes de TLS |
| `exec_protocol.lKnownVerbs` | La superficie privilegiada. Añadir un verbo agrega una forma de que el proceso web le pida algo a root. Cada añadido merece el mismo escrutinio que el primero |
| `exec_daemon.fRunPrivilegedCommand` | Todos los comandos privilegiados. Nunca usa shell; introducir `shell=True` ahí convertiría cada nombre de agente en un punto de inyección |
| `agent_api.fAuthenticate` | Todas las peticiones de agentes al tablero y a los canales. Las dos comprobaciones deben quedarse |
| `db.cAppSchema` / `cKanbanSchema` | Las instalaciones existentes. No hay sistema de migraciones: los esquemas usan `IF NOT EXISTS`, así que **las columnas nuevas necesitan código de migración explícito**, no una edición del esquema |
| `agent_scripts.cMinimumMinuteStep` | Cada cuánto puede programarse un agente a sí mismo. Es lo único que hay entre un horario descuidado y un bucle con una línea de cron delante |
| `paths.lProtectedAgentFiles` | Qué archivos se mueven al cajón de root. Los leen el instalador y el daemon que crea un agente, así que no pueden discrepar sobre cuáles son |
| `agents.fBuildAgentInfo` | Sólo a los agentes nuevos. Los `info.json` existentes no se tocan, así que los campos nuevos necesitan un valor por defecto al leerlos |
| `exec_daemon.fVerbWriteAgentInfo` | **A todos los campos de `info.json` que sobreviven a un guardado.** Reconstruye el archivo clave por clave, así que un campo que no nombre es un campo que la interfaz descarta en silencio la primera vez que alguien aprieta Guardar. Las listas se leen con `fReadNameList`, que distingue una clave ausente («no cambies esto») de una lista vacía («sacá todo»): leídas con `or`, desmarcar la última herramienta restauraba la lista anterior |
| `skills.fSelectInstalledSkills` | A lo que llega a un prompt y a lo que `skill.read` va a abrir. Tanto el índice como la herramienta filtran por acá, así que una habilidad borrada del servidor deja de mencionarse en vez de prometerse y después fallar |
| Forma neutra de `providers.base` | Todos los adaptadores y el runner |
| Interfaz de `tool_registry` | Todas las herramientas de `/opt/boa/tools/`, incluidas las que haya escrito el usuario |
| `telegram_listener.fIsFromTheConfiguredChat` | A quién se le permite hablar con tus agentes. El nombre de un bot es público, así que esta comprobación es toda la autorización: debilitarla deja que cualquiera que encuentre el bot lance ejecuciones en tu servidor |
| Firma de `channels.fSendMessage` | A todos los que la llaman, y a los dos emisores que aceptan dos argumentos. `pReplyToMessageId` se le pasa a Telegram y a Discord, que son los dos canales a los que una persona puede contestar |
| `discord_markdown.cMaxDiscordLength` | A si la respuesta de un agente llega siquiera. Discord rechaza un `content` de más de 2000 caracteres, y lo que hace es rechazarlo, no recortarlo |
| `agent_routing.fMatchNamedAgent` | A quién le llega un mensaje, en **los dos** listeners. La coincidencia más larga es lo que hace que `@News` y `@News Miner` sean dos agentes |
| `agent_routing.fBuildStatusReport` | A lo que contesta /status en los dos. Un solo informe, para que los dos no puedan discrepar sobre cuántos servicios hay |
| `discord_listener.fIsFromTheConfiguredChannel` | A qué canal escuchan los agentes. A diferencia de Telegram no hay una segunda comprobación sobre quién habla: quien pueda escribir en ese canal puede lanzar ejecuciones |
| `kanban.lStates` | El tablero, la API, el frontend y el prompt de cada agente |
| Forma de las entradas de `run_journal` | Tanto al que escribe (runner) como a los que leen (daemon, web). Las líneas viejas siguen en los journals: los lectores deben tolerar campos que falten |
| Un archivo que el demonio lee del home de un agente (`runs.jsonl`, `chat.jsonl`, `memory.md`) | Se lee sólo a través de `paths.fReadAgentOwnedFile`. Un archivo nuevo que el demonio lea de un home tiene que pasar también por ahí, o root lee lo que el agente le ponga adelante: un FIFO que nunca contesta, un enlace a cualquier archivo de la máquina |
| Lo que guarda una copia de seguridad (la línea de `tar` de `fDoBackup`) | Un estado nuevo bajo `/opt/boa/` que sea de la instalación y no del código hay que agregarlo ahí, o una restauración en una máquina nueva lo pierde |
| Los límites de kernel de una ejecución (`runner.cMaxProcesses`, `exec_daemon.cRunTasksMax`, `cRunMemoryMax`) | Una herramienta que necesite más de 1024 tareas o 2 GiB tiene que subirlos; un navegador ya son unos cientos de hilos |
| `runner.py` lanzado por ruta | Todas las ejecuciones programadas. Cron lo arranca por ruta y casi sin entorno, así que el runner pone su propia raíz en sys.path: sin eso, `import backend` falla y el traceback va al correo de cron, que en una máquina de LAN no va a ningún sitio |
| `runner.dAnswerLanguageLines` | La línea que se añade al prompt de sistema diciendo en qué idioma responder. Escrita EN ese idioma, y dice que anula la regla del propio prompt: una preferencia al lado de una regla pierde, medido |
| `agent_api.fFilterCardsForAgent` | Qué puede saber un agente que existe. Toda lectura del tablero pasa por ahí, y el orquestador es la única excepción. Filtrar en la herramienta sería poner una regla de seguridad en una descripción de la que se puede convencer al modelo |
| De qué lado va una burbuja del chat | Quién habla. Una tarjeta es lo que se le pidió al agente, así que va a la derecha con los mensajes del usuario; el informe de una ejecución programada es el agente hablando, así que se queda a la izquierda |
| `chat.lToolsWorthReporting` | Qué herramientas hacen que una ejecución programada merezca ir al chat. Lo demás se queda en el journal: un agente horario metería si no doce mensajes de «nada que informar» al día |
| `chat.lAskingRoles` | Qué roles esperan respuesta. Un rol que abre un turno y no está en la lista deja el cuadro de escribir abierto mientras el agente trabaja; uno que está y nunca se cierra lo deja cerrado para siempre |
| `kanban.cRunNow` | La palabra que el navegador, los agentes y la API envían en vez de una hora. Convertirla en hora en cualquier sitio que no sea `fValidateRunAt` pierde `run_mode`, y con él la diferencia entre «ya» y un momento elegido |
| `chat.cReplayedTurns` | Lo que cuesta cada mensaje del chat. Cada intercambio reenviado se vuelve a pagar en el mensaje siguiente, así que subirlo encarece progresivamente las conversaciones largas |
| `lTextColours` en `TestThemes` | Qué colores mide el test de contraste. Un color que se pinta como texto y no está en esa lista es un color que nadie comprueba |
| Un atributo `style=` en cualquier plantilla | Nada: `style-src` es `'self'` sin `unsafe-inline`, así que el navegador lo tira. Hay un test que falla si aparece uno |
| `.notice-layer` en `app.css` | Dónde aparece cada confirmación y cada error de la aplicación. `position: fixed` es lo que lo sostiene: `absolute` centraría en el documento en vez de en la pantalla, que es justo el fallo por el que existe la capa |
| `frontend/static/i18n/en-US.json` | Agregar una clave obliga a agregarla en los otros trece, o esa cadena se queda en inglés. `TestTranslations` falla si falta una clave, si se pierde un `{placeholder}` o si se tradujo una ruta o el nombre de una herramienta |

---

## 7. Puntos de extensión

### Un proveedor nuevo

1. Escribí `backend/providers/<nombre>.py` con una clase que extienda
   `base.BaseProvider`, defina `cProviderName`, `cDefaultModel`,
   `cDefaultBaseUrl` e implemente `fSendMessages`.
2. Agregá una fila a `factory.dProviderRegistry`.
3. Agregá el nombre a `agents.lSupportedProviders`.
4. Si no necesita clave, añádelo a `factory.lSelfHostedProviders`.
5. Las opciones propias (como el `thinking` de DeepSeek) van en
   `lExtraConfigKeys`; la fábrica convierte `reasoning_effort` →
   `pReasoningEffort` automáticamente.

No lo fusiones con un adaptador existente porque el dialecto coincida. Un
archivo por proveedor es deliberado.

### Una herramienta nueva

Crea un `.py` en `/opt/boa/tools/` que declare:

```python
cToolName = "espacio.verbo"
cToolDescription = "Lo que se le dice al modelo que hace."
dToolSchema = {"type": "object", "properties": {...}, "required": [...]}

def fRunTool(pArguments, pContext):
  return "texto que ve el modelo"
```

Se ejecuta como el agente que llama. Si necesita algo a lo que los agentes no
pueden llegar, agregá un verbo a la API de agentes y llámalo con
`agent_api_client`.

El archivo debe pertenecer a root: la aplicación lo importa como código.

### Una habilidad nueva

Creá una carpeta en `/opt/boa/skills/` con un `SKILL.md` adentro:

```markdown
---
name: BackupVerification
description: Una línea. Esto es lo que paga cada ejecución.
---

El procedimiento, con la extensión que necesite.
```

No hay nada que registrar ni que reiniciar: `fListSkills` lee la carpeta, así
que aparece en la interfaz al recargar la página. Marcala en un agente, dale a
ese agente `skill.read`, y va a estar en su prompt en la siguiente ejecución.

Todo lo demás que haya en la carpeta viaja con la habilidad. Es legible por
todos, así que la habilidad puede decir «ejecutá `verify.sh` de esta carpeta» y
el agente puede hacerlo.

El nombre es el de la carpeta: letras, dígitos y guiones, empezando por una
letra. El `name:` de la cabecera es lo que ve una persona en la lista; el nombre
de la carpeta es lo que pide un agente.

### Una operación privilegiada nueva

1. Agregá la constante del verbo a `exec_protocol` y a `lKnownVerbs`.
2. Escribí `fVerb<Nombre>` en `exec_daemon` y añádelo a `dVerbHandlers`.
3. Agregá un envoltorio en `exec_client`.

Valida todos los argumentos antes de que lleguen a una ruta o a una línea de
comandos, y mantén el verbo específico. Un verbo lo bastante general como para
reutilizarse suele ser lo bastante general como para abusarse.

### Un canal nuevo

Sólo para enviar:

1. Escribí `fSendTo<Nombre>` en `channels.py`.
2. Agregalo a `lChannels` y a `dChannelSenders`.
3. Agregá sus campos a `dChannelFields` en `frontend/static/js/settings.js`, y
   los que sean credenciales a `lSecretChannelFields` ahí y a
   `lSecretConfigFields` en `channels.py`.

Para recibir también, que es lo que lo convierte en una conversación:

4. Escribí `fRead<Nombre>Messages` en `channels.py`, devolviendo los mensajes
   del más viejo al más nuevo.
5. Escribí `<nombre>_inbox.py`: dos tablas en `db.cAppSchema` y el agente
   seleccionado en un ajuste.
6. Escribí `<nombre>_listener.py` apoyado en `agent_routing`, que ya tiene la
   lista de agentes, la coincidencia por nombre, la respuesta cerrada y el
   informe de estado. Lo que queda es el protocolo.
7. Escribí `<nombre>_texts.py` con las frases que ese canal diga de otra
   manera, cayendo en `telegram_texts` para el resto.
8. Un archivo de servicio en `deploy/systemd/` y otro en `deploy/openrc/`, el
   nombre en `lServices` y en los siete lugares donde el instalador de Debian
   nombra sus unidades, y en `system_info.lBoaServiceNames`.
9. Su interruptor en `dChannelSwitches`, su clave `chat.source<Nombre>` en los
   catorce catálogos, y `<nombre>` en `exec_daemon.lKnownChatSources`.

### Un idioma nuevo

Se distribuyen catorce: `de-DE`, `en-GB`, `en-US`, `es-AR`, `es-ES`, `fr-FR`,
`hi-IN`, `it-IT`, `ja-JP`, `ko-KR`, `pt-BR`, `pt-PT`, `ru-RU`, `zh-CN`. Un
decimoquinto son cinco lugares, y los tests los nombran a todos:

1. Copiá `frontend/static/i18n/en-US.json` y traducí los valores.
2. Agregá la etiqueta a `lSupportedLanguages` en `frontend/static/js/i18n.js`.
3. Agregá un `<option>` a los tres selectores: dos en
   `frontend/templates/settings.html` y uno en `login.html`, por etiqueta.
4. Agregá una línea a `runner.dAnswerLanguageLines`, escrita EN ese idioma.
5. Agregá un bloque a `telegram_texts.dTexts` y su etiqueta al
   `lSupportedLanguages` de ese módulo, o el bot se queda en inglés. Agregá
   también uno a `discord_texts.dTexts`: ahí están las tres frases que Discord
   dice de otra manera, y un idioma que falte recibe esas tres en inglés.

`TestTranslations`, en `tests/test_web.py`, falla si falta una clave, si sobra,
si hay una cadena vacía, si se pierde un `{placeholder}`, si se tradujo una
ruta o el nombre de una herramienta, si el archivo no está ordenado, si un
selector no ofrece el idioma, si falta la línea del prompt o si falta el bloque
de Telegram. De los cinco idiomas que no usan el alfabeto latino se comprueba
además que estén escritos de verdad en su propia escritura, porque un archivo
de cadenas en inglés bajo un nombre ruso pasa todas las demás comprobaciones.

Lo que una traducción SÍ puede cambiar: un nombre de archivo que el texto en
inglés da como EJEMPLO, como `check-disk.sh`. Nada los busca.

### Una página nueva

1. Una ruta en `backend/web/views.py` que devuelva `render_template`.
2. Una plantilla que extienda `app_base.html`.
3. Un `<li>` en el `nav` de `app_base.html`.
4. Su propio JS en `frontend/static/js/`, empezando por
   `await fWaitForTranslations()` antes de renderizar nada.
