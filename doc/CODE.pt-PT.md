# CODE.md

Referência técnica do Bunch of AIgents. Escrita para ser consultada de forma
cirúrgica: salte para a secção de que precisa, não a leia do princípio ao fim.

## Índice

1. [Arquitetura e decisões de design](#1-arquitetura-e-decisões-de-design)
2. [Mapa de módulos](#2-mapa-de-módulos)
3. [Índice de símbolos-chave](#3-índice-de-símbolos-chave)
4. [Fluxos principais](#4-fluxos-principais)
5. [Mapa de pontos de entrada e rotas](#5-mapa-de-pontos-de-entrada-e-rotas)
6. [Análise de impacto](#6-análise-de-impacto)
7. [Pontos de extensão](#7-pontos-de-extensão)

---

## 1. Arquitetura e decisões de design

Esta é a parte que não se pode deduzir do código, por isso é a parte que vale a
pena ler.

### A premissa

Um agente, aqui, é um modelo de linguagem com uma shell num servidor, acordado
pelo cron, sem ninguém a vigiar. Todas as decisões estruturais decorrem de
levar isso a sério: o modelo acabará por fazer algo que ninguém pretendia, por
isso a pergunta não é como o evitar, mas o que consegue alcançar quando isso
acontecer.

### Um utilizador Linux por agente

O agente `007` é o utilizador de sistema `agent-007`, dono de
`/opt/boa/agents/007/` com o modo `0700`. O isolamento entre agentes é o do
kernel, não uma sandbox escrita em Python. Um agente não consegue ler o prompt
de sistema, o diário ou a chave de API de outro agente porque o sistema de
ficheiros assim o determina.

O próprio `/opt/boa/agents/` é `root:root 0711`: atravessável, não listável. Um
agente não consegue enumerar os outros agentes; só consegue falhar ao abrir os
caminhos que adivinha.

Esta decisão é a razão pela qual `bash.run` não precisa de lista de permitidos.
Uma lista de proibidos numa shell é teatro — tudo o que consiga executar `sh`
consegue executar aquilo que a lista nomeia —, ao passo que uma conta de
utilizador é uma fronteira que o kernel impõe.

### O que um agente não pode reescrever sobre si próprio

A pasta pessoal é do próprio agente, 0700, e é esse o objetivo: a sua memória,
o seu diário, a sua conversa e qualquer script que escreva vivem aí. Há três
ficheiros cuja alteração não lhe compete, e esses ficam FORA da pasta pessoal,
em `/opt/boa/agents-config/xxx/`, que é `root:agent-xxx 0750` debaixo de um pai
`root:root 0711`.

| Ficheiro | Porque não é do agente |
|---|---|
| `info.json` | Que ferramentas lhe foram concedidas e quanto pode gastar |
| `system-prompt.md` | A definição do que é suposto fazer |
| `api-token` | Aquilo com que se identifica perante a API dos agentes |

O que faz isto funcionar não é o dono dos ficheiros: é o do diretório. A
permissão de escrita num diretório é o que decide se um ficheiro dentro dele
pode ser apagado e substituído, por isso um agente que fosse dono do diretório
poderia apagar `info.json` e escrever o seu, fosse quem fosse o dono do
ficheiro. Neste pode entrar e ler, e não pode criar, mudar o nome nem apagar
nada.

**E essa regra aplica-se tanto à gaveta como ao que está dentro dela**, e é
por isso que estes ficheiros já não vivem em `agents/xxx/config/`. Esse caminho
era uma entrada na PASTA PESSOAL, a pasta pessoal é do agente com 0700, e mudar
o nome de uma entrada exige permissão de escrita no pai e mais nada - o modo
daquilo a que se muda o nome nunca é consultado. Assim, o agente não conseguia
editar `info.json` e conseguia fazer isto:

    mv ~/config ~/config-old && mkdir ~/config && echo '...' > ~/config/info.json

e passar a ser lido a partir do substituto. Tirar a gaveta da pasta pessoal põe
todos os diretórios do caminho debaixo do root. Da mudança decorrem duas
coisas:

  - **Já não há recurso à pasta pessoal.** Houve um, para que uma atualização
    não fosse um serviço que deixava de responder antes de a migração correr -
    e esse recurso era ele próprio uma forma de contornar a proteção, já que
    esconder o ficheiro verdadeiro bastava para que fosse lido o do próprio
    agente. O daemon agora migra no arranque, além de o instalador também o
    fazer, por isso não fica nada por cobrir.
  - **Eliminar um agente elimina também a sua configuração.** Já não está
    dentro da pasta pessoal que `userdel --remove` leva consigo, e, deixada para
    trás, seria entregue ao próximo agente que recebesse esse id.

`fOpenProtectedAgentFile` é a segunda resposta à mesma pergunta: abre com
`O_NOFOLLOW` e verifica, no FICHEIRO ABERTO, que se trata de um ficheiro
regular, pertencente ao root e sem permissão de escrita para mais ninguém. É
isso que sobrevive a um chmod equivocado durante uma atualização ou a um
restauro a partir de uma cópia de segurança com o dono errado.

Isto foi medido antes de ser corrigido, numa instalação real: um agente
acrescentou `mail.read` ao seu próprio `info.json` e o daemon privilegiado
passou a indicar a ferramenta como concedida - portanto um agente podia
conceder a si próprio a caixa de correio, os canais, ou subir os seus próprios
tetos. Também podia substituir o seu próprio prompt por «ignora todas as tuas
regras», que ficaria assim em todas as execuções a partir daí.

O isolamento entre agentes não precisa de nada disto: `/opt/boa/agents/` é
`root:root 0711` e cada pasta pessoal é 0700, por isso o kernel já recusa. É
por isso que se mantém mesmo quando uma ferramenta tem um bug.

### O que o root lê da pasta pessoal

O diário, a memória e a conversa são ficheiros do próprio agente: escritos
pelos seus próprios processos, na sua própria pasta pessoal 0700, e lidos pelo
daemon privilegiado como root - que lê aquilo para que for apontado. Medido no
código antes de isto existir: um FIFO chamado `runs.jsonl` prendia para sempre
a thread do daemon que o abria e, como a lista de agentes lê o diário de todos
os agentes, cada pedido posterior dessa lista deixava mais uma thread presa;
uma ligação simbólica chamada `memory.md` que apontasse para qualquer ficheiro
da máquina fazia o root entregar o texto desse ficheiro à interface; e uma
ligação para algo sem fim fazia o root ler até ser morto.

Por isso os três são lidos através de `fReadAgentOwnedFile`, que é o irmão de
`fOpenProtectedAgentFile` para os ficheiros que SÃO do agente: `O_NOFOLLOW`
recusa uma ligação na abertura, `O_NONBLOCK` impede que um FIFO prenda a
abertura até alguém lhe escrever, e as verificações são feitas no descritor
aberto - um ficheiro regular, pertencente ao utilizador do agente - para que
nada possa ser trocado entre a verificação e a leitura. Nunca lê mais do que um
limite, aplicado ao que é lido e não apenas ao que `fstat` indicou, porque o
agente pode acrescentar conteúdo enquanto a leitura decorre: 32 MB para o
diário e para a conversa, lidos a partir do FIM quando o ficheiro é maior, já
que as linhas mais recentes são o que um histórico mostra; 4 MiB para a
memória, o suficiente para o seu máximo de um milhão de caracteres UTF-8. Só os
ficheiros escritos externamente que excedam esse orçamento de leitura recebem
`[truncated]`; `fWrite` rejeita conteúdo demasiado grande antes de substituir o
que quer que seja. Um byte inválido custa uma linha, não a leitura.

O que é recusado é dito, não engolido: `read_run_journal`, `read_chat` e
`read_memory` falham com o motivo, para que um operador saiba que algo nessa
pasta pessoal não é o que a aplicação escreveu. A única exceção é
`read_usage_summary` para todos os agentes, a partir do qual se desenha a barra
lateral: aí, um diário ilegível custa a esse agente os seus totais, com o
motivo ao lado, e a mais ninguém os seus.

### O que viaja na linha de comandos

O daemon arranca uma execução como o agente com `Popen`, e a mensagem que o
dono escreveu - ou o prompt que um cartão vencido constrói - era um dos seus
argumentos: `--chat-message <text>`, `--prompt <text>`. A linha de comandos de
um processo pode ser lida por todos os utilizadores da máquina através de
`/proc/<pid>/cmdline`, e um agente com `bash.run` é um utilizador da máquina.
Medido na máquina de testes Debian: `ps` executado como `agent-001` mostrava a
mensagem que o dono acabara de enviar a `agent-000`, durante todo o tempo de
vida dessa execução, que por omissão chega a cinco minutos.

Por isso o texto segue pela entrada padrão do processo filho e a linha de
comandos leva apenas `--chat-message-on-stdin` ou `--prompt-on-stdin`.
`fStartRunner` é o único sítio que arranca um runner: recusa um texto mais
longo do que `cMaxStdinPayloadBytes` antes de existir qualquer processo, porque
esse limite está abaixo do buffer de 64 KiB de um pipe e uma escrita que cabe
no buffer nunca espera pelo filho - este daemon não espera por runners. Um
filho que já desapareceu quando a escrita acontece, um interpretador que falha
na importação, é um pipe partido e não uma falha do daemon. Do outro lado, o
runner lê o texto com o mesmo limite, recusa uma mensagem de conversa vazia em
vez de responder a uma pergunta que ninguém fez, e, quando recusa, fecha o
turno para o qual foi arrancado, para que a conversa não fique à espera para
sempre. `--prompt` e `--chat-message` mantêm-se, para uma execução arrancada à
mão a partir de um terminal.

### O que uma execução pode fazer à máquina

Os tetos em `info.json` - tokens, passos, segundos, execuções por dia - são
impostos pelo runner, e o runner é um programa que o agente está a conduzir. O
que se aguenta quando é o próprio programa que corre mal é imposto pelo
kernel, em duas camadas.

O runner baixa os seus próprios limites de recursos antes de fazer qualquer
outra coisa, `fApplyResourceLimits`, a partir do ponto de entrada e não de
`fMain` - os testes chamam `fMain` dentro do mesmo processo, e um RLIMIT_NPROC
baixado dentro da sessão de um programador, com milhares de threads já a
correr, impede essa sessão de fazer fork. Todos os processos que a execução
arranca herdam-nos: RLIMIT_NPROC em 1024, contado contra o uid do agente como
um todo, para que uma fork bomb vinda de `bash.run` pare no número e não na
máquina - as threads também contam, e é por isso que não é mais pequeno, já
que um navegador são algumas centenas delas; sem ficheiros core; nenhum
ficheiro acima de 4 GiB. RLIMIT_AS não: o Chromium reserva espaço de
endereçamento às dezenas de gigabytes e não arrancaria. Essa camada é igual em
Debian e em Alpine, e é a única que tem uma execução arrancada pelo próprio
crontab do agente.

Onde o systemd é o PID 1, o daemon acrescenta a segunda: `fStartRunner` põe a
execução num scope transitório próprio, `boa-agent-<id>-<random>.scope` debaixo
de `boa-agents.slice`, com `TasksMax=1024` e `MemoryMax=2G`. `systemd-run
--scope` faz exec para o comando, por isso o pid continua a ser o do runner e
`/proc` continua a mostrar a sua linha de comandos; é `setpriv` que baixa os
privilégios para o agente, porque o systemd-run tem de ser root para criar o
scope. Medido antes de ser assim: uma execução era filha de
`boa-exec.service`, no próprio cgroup do daemon, e um agente descontrolado
gastava o TasksMax do daemon e deixava-o sem conseguir fazer fork. O scope é
também o que termina o que uma execução deixou para trás: `bash.run` envia
sinais ao seu próprio grupo de processos, por isso um comando que chamou
`setsid`, ou um filho em segundo plano de um comando que terminou a tempo,
sobrevivia à execução; `fWatchRunner` espera pela execução e para o seu scope,
o que alcança tudo o que a execução arrancou, para onde quer que se tenha
mudado. Uma execução que foi morta - pelo limite de memória, por um operador -
não escreveu nada à saída, por isso a mesma thread regista o fim no diário e
fecha o turno na conversa; uma execução que saiu por si própria já fez ambas
as coisas, e o turno é verificado em vez de presumido.

### Onde vivem as chaves dos fornecedores

As chaves partilhadas por todos os agentes estão em
`/opt/boa/config/apikeys/<provider>.key`, pertencentes a `boa`, com o diretório
a `0700` e os ficheiros a `0600`.

0750 e 0640 já manteriam os agentes de fora - nenhum utilizador de agente está
no grupo `boa` -, mas isso assenta em que a lista de grupos de cada agente se
mantenha vazia durante toda a vida da instalação, o que está a um
`usermod -aG` de deixar de ser verdade. Um modo que não concede nada ao grupo
não depende disso. `api_keys.fWrite` define ambos os modos em cada escrita e
não apenas na criação, para que um diretório vindo de uma instalação mais
antiga fique fechado da primeira vez que se guarda uma chave.

O diretório chamava-se `keys` até lhe ser mudado o nome: lia-se como «as chaves
desta instalação» e estava a uma gralha de distância do `keys/` por agente
dentro de cada pasta pessoal de agente, que é uma coisa diferente que um agente
*consegue* ler - a sua própria chave, posta lá para que o seu consumo seja
faturado a outra conta. O instalador muda o diretório antigo de sítio no
`--update` e só o apaga quando está vazio.

Nada disto impede um agente de ter a chave do fornecedor em que de facto
corre: a API dos agentes entrega-lha, ele precisa dela para fazer a chamada, e
um agente com `bash.run` poderia imprimi-la. O que impede é que um agente leia
as chaves dos fornecedores que não usa.

### Dez serviços, dois arrancados como root

| Processo | Utilizador | Porque existe |
|---|---|---|
| `boa-proxy` | `boa` | HAProxy: termina o TLS, serve as duas portas |
| `boa-web` | `boa` | Serve a interface e a API, num socket Unix |
| `boa-exec` | `root` | Cria utilizadores e arranca execuções de agentes |
| `boa-samba` | `root` | Autentica sessões SMB e depois serve ficheiros como o agente dono |
| `boa-embeddings` | `boa` | Serve o modelo de vetorização local das bibliotecas de documentos, num socket Unix |
| `boa-rag` | `boa` | Gere a fila de indexação das bibliotecas de documentos |
| `boa-agent-api` | `boa` | Guarda aquilo que os agentes podem usar mas não ler |
| `boa-buzzer` | `boa` | Acorda um agente quando um dos seus cartões vence |
| `boa-channel-telegram` | `boa` | Escuta no Telegram e entrega o que chega a um agente |
| `boa-channel-discord` | `boa` | O mesmo, para um canal do Discord |

As unidades de canal em Debian são `boa-channel-telegram.service` e
`boa-channel-discord.service`; as futuras unidades de canal seguem
`boa-channel-<channel>.service`. O OpenRC mantém `boa-telegram` e
`boa-discord`. `system_info.fServiceName` resolve estes nomes tanto para o
separador do sistema como para os relatórios de estado dos listeners.

`fInstallSystemdUnits` chama `fRetireLegacyChannelUnits` para parar e
desativar cada unidade de canal antiga antes de a apagar e de ativar a sua
substituta. As atualizações repetidas também funcionam quando não existe
nenhuma unidade antiga. Se uma atualização falhar antes de instalar as novas
unidades, `fStartServices` pode voltar a arrancar as antigas durante a
reversão.

Os últimos quatro são `boa` e não root de propósito: cada um deles quer que se
faça algo como o utilizador próprio de um agente - arrancar uma execução,
escrever numa pasta pessoal 0700 - e cada um deles pede ao `boa-exec` que o
faça, em vez de receber o privilégio. Um serviço que pode ser alcançado a
partir de fora, como na prática podem os dois listeners, é o último que o
deveria ter.

### Um ambiente virtual não é relocalizável

`python3 -m venv <path>` escreve `<path>` no shebang de cada script de consola
que mais tarde se instale nele, em `VIRTUAL_ENV` nos scripts de ativação e na
linha `command` de `pyvenv.cfg`. O ambiente é construído em `venv.new` e muda
de nome para `venv`, por isso os três passam a nomear um diretório que já não
existe.

Medido num Debian 13 real e num Alpine 3.24 real: ambas as instalações
terminaram, ambas imprimiram «Installation finished», e ambas deixaram o
`boa-web` a reiniciar a cada cinco segundos com

```
status=203/EXEC - Failed to execute /opt/boa/venv/bin/gunicorn:
No such file or directory
```

O ficheiro estava lá. A sua primeira linha nomeava
`/opt/boa/venv.new/bin/python3`, que não estava.

`fBuildVirtualEnv` tinha uma verificação precisamente para esta classe de
falha, e ela passava, porque executa `bin/python3` - uma LIGAÇÃO SIMBÓLICA para
o interpretador do sistema, que responde de onde quer que esteja. Só um script
de consola tem o caminho gravado. Por isso a verificação agora também executa
`bin/gunicorn --version`, que é o ficheiro que a unidade do serviço executa, e
`fRepointVirtualEnv` reescreve os três caminhos registados enquanto o ambiente
ainda tem o nome de construção. A reescrita é verificada em vez de presumida:
se um pip futuro escrever os seus scripts de consola de outra maneira, o
instalador para aí.

### Uma atualização que falha deixa algo a correr

Três fases, e a ordem é a reparação.

Uma atualização costumava parar os serviços, apagar `webapp/` e só depois
executar o pip. Um pip que falhasse - sem rede, um índice em baixo, uma wheel
que não compilava - deixava uma instalação com os serviços parados e o código
desaparecido: uma máquina que funcionava um minuto antes, à espera de que
alguém reparasse e a recuperasse à mão.

| Fase | O que acontece | O que custa uma falha |
|---|---|---|
| Preparar | Perguntas feitas, dependências instaladas, código transferido, o novo virtualenv CONSTRUÍDO ao lado do que está a correr e verificado quanto à capacidade de importar | Nada. A versão antiga continua a correr, intacta |
| Trocar | Parar, `webapp/` movido para `webapp.previous`, `venv` para `venv.previous`, os novos postos no lugar, arrancar | Reversível: as duas versões anteriores continuam no disco |
| Verificar | `curl` pede à aplicação a página de início de sessão, quinze vezes ao longo de trinta segundos | `fRollBack` repõe ambas e volta a arrancá-las |

Esse `curl` envia o protocolo PROXY apenas no modo `proxied`. No modo
`direct`, o bind não tem `accept-proxy`, por isso um cabeçalho PROXY cai no
handshake TLS e o pedido não recebe resposta nenhuma. Antes era enviado nos
dois modos, o que fazia cada `--install --ports direct` acabar em «did not
answer» sobre uma instalação que estava a servir páginas, e cada `--update`
direto reverter-se a si próprio. Confirmado mudando as duas máquinas de testes
para `direct` e de volta: com a flag ligada ao modo, ambas responderam 200 na
443 e depois na 11443. Um teste executa `fVerifyInstallation` dos dois
instaladores contra um `curl` que regista os seus argumentos, uma vez por
modo, e verifica que a flag está presente num e ausente no outro.

Quando esse `curl` nunca recebe resposta, `fExplainWhyItDoesNotAnswer` escreve
como estava a máquina nesse momento no mesmo registo para o qual o erro
aponta: o que o próprio curl diz - perguntado de novo com `-sS`, para que se
distingam uma ligação recusada, um handshake que falhou e um pedido que
esgotou o tempo, porque `000` não é um código HTTP mas sim o curl a dizer que
nunca recebeu nenhum -, o estado de cada um dos dez serviços, se há alguma
coisa a escutar na porta, e as últimas quinze linhas de `boa-proxy.log`,
`boa-web.log` e do `error.log` do gunicorn. `fReportServiceStates` é a metade
que difere entre os dois: `rc-service ... status` em Alpine,
`systemctl is-active` mais o journal de `boa-web` e de `boa-proxy` em Debian.

Existe porque uma primeira instalação num Alpine acabado de instalar terminou
em «The application did not answer on port 11443 (last code: 000)» e o registo
não tinha mais nada sobre isso - nem que serviço estava em baixo, nem se a
porta estava ocupada, nem uma linha do que o gunicorn tinha impresso. O único
ficheiro que o erro nomeia não conseguia responder à pergunta para a qual era
aberto. O que procurar nele: um serviço que se diz arrancado ao lado de
«nothing is listening on port 11443» é um processo a morrer e a ser
reiniciado, porque um serviço supervisionado que morre no instante em que
arranca é indicado como arrancado pelo comando que o arrancou. Quatro testes
EXECUTAM as duas funções - contra um `curl` que se recusa a ligar, um `ss` que
ocupa a porta e outro que não, e um `rc-service` e um `systemctl` que
respondem «stopped» e devolvem uma falha.

`fRollBack` arranca os serviços numa SUBSHELL, e o `|| true` ao lado não basta
por si só: `fStartServices` chama `fDie` quando um serviço não arranca, `fDie`
chama `exit`, e `exit` termina a shell, seja o que for que esteja escrito ao
lado. Medido num Alpine real: o `boa-proxy` foi deitado abaixo pelo OpenRC
enquanto o `boa-web` oscilava, o arranque dele pela própria reversão perdeu a
corrida pelo lock do serviço, e o instalador morreu DENTRO de `fRollBack`. A
reversão tinha funcionado - a versão anterior estava de volta e a responder -
mas o que foi dito ao operador foi «The boa-proxy service would not start»,
sem uma palavra sobre uma atualização que acabara de ser revertida. Nesse
ponto, o relato do que aconteceu é a única coisa que um operador tem.

A versão anterior é removida por `fFinishUpdate`, e apenas depois de a nova
ter respondido.

`fRollBack` costumava correr num único sítio: quando esse `curl` final
falhava. Entre `fStopServices` e essa verificação há uma dúzia de passos que
podem morrer - um ficheiro de certificado que desapareceu, uma configuração de
proxy que o HAProxy não consegue interpretar, uma unidade que não se instala -
e cada um deles deixava os serviços parados, o código novo no lugar e
`webapp.previous` no disco, sem ninguém para o repor. A mensagem nomeava o que
tinha falhado e não dizia nada sobre a máquina estar em baixo. Por isso
`fDoUpdate` define `vUpdateSwitched` imediatamente antes de parar os serviços,
e `fCleanup` - o trap de EXIT, que corre seja qual for a maneira como o
processo filho termina - reverte quando encontra a flag definida e o código de
saída diferente de zero. As duas saídas da troca limpam-na: o próprio
`fRollBack`, para que o caminho explícito não reverta duas vezes, e
`fFinishUpdate`, porque, depois de a nova versão ter respondido, não há nada
para onde voltar. Medido nas duas máquinas de testes com a chave privada
escondida: «Missing certificate files», «Putting the previous version back»,
todos os serviços de pé e a página de início de sessão a responder 200 com o
código anterior. Um teste executa os verdadeiros `fCleanup`, `fRollBack` e
`fFinishUpdate` de cada instalador através de três saídas: depois da troca,
antes dela e depois do fim.

`--install` e `--reinstall` não têm versão anterior a manter, por isso não têm
fase Trocar nem reversão - mas fazem a fase Verificar. Costumavam terminar em
`fWriteCredentialsFile`, e «Installation finished» foi impresso em duas
máquinas reais cujo serviço web estava a reiniciar a cada cinco segundos: nada
tinha alguma vez perguntado coisa alguma à aplicação. Agora pedem a mesma
página de início de sessão e, quando ela não chega, dizem-no e nomeiam o
registo, porque não há nada na máquina para onde voltar.

O próprio `pip` está fixado numa versão. `--upgrade pip` sem versão
significava que duas atualizações do mesmo código podiam resolver de forma
diferente, que é precisamente o que a fixação dos requisitos pretendia evitar.
O que continua sem estar fixado são as dependências TRANSITIVAS - por isso
`pip freeze` é registado no ambiente e a atualização seguinte imprime o que
mudou, que é a única forma de alguém dar por isso.

### Uma instalação que parou a meio

`fIsInstalled` contava uma máquina como instalada a partir do momento em que
`webapp/backend` e o utilizador `boa` existiam - o que acontece antes do
ambiente virtual, dos certificados, da base de dados e do administrador. Uma
instalação que morria no pip, numa rede que caiu, recebia depois «already
installed» de `--install` e uma morte por aquilo que faltasse em `--update`, e
só `--reinstall --yes` a ultrapassava, sem nada que o dissesse ao operador.

Uma instalação terminada deixa agora `/opt/boa/installed`, escrito por
`fMarkInstalled` apenas depois de `fVerifyInstallation` ter obtido a sua
página: uma instalação que está no lugar e não responde não está terminada, e
uma atualização que foi revertida não é a nova versão. Sem o marcador, as
cinco coisas que uma instalação terminada tem sempre - o código, o
utilizador, `venv/bin/gunicorn`, `db/boa.sqlite` e `certificates/privkey.pem` -
fazem as suas vezes, por isso uma instalação anterior à existência do marcador
continua a contar e recebe o seu marcador na atualização seguinte. Tudo o
resto que `--install` faz já é seguro de fazer duas vezes: o utilizador só é
criado se faltar, o ambiente é construído ao lado do antigo, os certificados
são mantidos quando existem, o administrador é apagado e escrito de novo com a
nova palavra-passe. Assim, uma instalação meio terminada termina-se executando
`--install` mais uma vez, e `--update` diz exatamente isso quando encontra
uma. Pelo caminho, `fGeneratePassword` passou para depois de
`fInstallDependencies` no instalador de Debian, onde estava ao contrário: o
`openssl` tem Priority: optional em Debian, e uma imagem mínima gerava a
palavra-passe antes de o pacote que a gera estar instalado.

### Tudo o que o instalador executa chega ao seu registo

`fLog` escrevia as suas próprias linhas em `install.log` e mais nada. O apt, o
pip, a validação do HAProxy e todos os outros subprocessos escreviam no
terminal, por isso uma instalação falhada deixava um registo com «Installing
the dependencies.» e nem uma palavra do erro do apt que explicava porquê - que
é precisamente o detalhe que alguém abre esse ficheiro para encontrar.

`fStartCapturingOutput` redireciona o stdout e o stderr desta própria shell
para um FIFO que o `tee` copia para o registo e para o terminal. Um FIFO em vez
de `exec > >(tee ...)`, que é exclusivo do bash, e o Alpine arranca sem bash; e
em vez de um pipeline à volta de `fMain`, que o poria numa subshell e
desfaria o arranjo `fMain & wait` que mantém o errexit vivo.

Duas consequências, ambas tiveram de ser tratadas:

`fLog` fazia echo da linha E acrescentava-a ele próprio ao registo. A partir
do momento em que o stdout é um tee que acrescenta a esse mesmo ficheiro, a
segunda escrita é um duplicado: uma instalação de 90 linhas produzia um
registo de 185 linhas, com todas as linhas em duplicado. `fLog` agora só
escreve no ficheiro enquanto a captura não está a correr.

O `tee` mantém o registo aberto pelo INODE. Um `--reinstall` apaga a árvore
inteira, registo incluído, e põe uma cópia nova no lugar - por isso, a partir
desse momento, o `tee` está a acrescentar a um inode sem nome e, com o `fLog`
a já não escrever no ficheiro, isso seria toda a segunda metade da
reinstalação, palavra-passe gerada incluída. `fRestartCapturingOutput` aponta
a captura para o ficheiro que agora existe.

### Dois instaladores, uma aplicação

`deploy/install-update-reinstall-debian.sh` escreve unidades systemd e
**precisa de que o systemd seja o PID 1 da máquina em execução**: um Debian
arrancado com qualquer outra coisa não é um alvo, e o instalador recusa-o em
vez de instalar numa máquina que não arrancaria nada.
`deploy/install-update-reinstall-alpine.sh` escreve serviços OpenRC em
`/etc/init.d/`, a partir de `deploy/openrc/`, e não precisa de nada de
antemão: instala ele próprio o OpenRC quando a máquina não o tem. Ambos
instalam os mesmos dez processos, a mesma árvore em `/opt/boa`, o mesmo
modelo de utilizadores; um teste compara os dois passo a passo e falha quando
um ganha um passo que o outro não tem.

Não estão escritos na mesma linguagem, e isso é deliberado. O de Debian é
bash, como tudo o resto aqui. O de Alpine é shell POSIX, com `#!/bin/sh`,
porque um Alpine acabado de instalar não tem bash: com `#!/bin/bash` o kernel
procuraria um interpretador que não está lá, e

    curl -fsSL <raw-url> | bash -s -- --install

falharia antes de ler uma linha, precisamente na máquina que mais precisa da
instalação numa linha. Sendo POSIX, corre igualmente em BusyBox ash, dash e
bash, por isso o mesmo ficheiro funciona canalizado para `sh` num Alpine nu e
para `bash` num que já o tenha. Continua a instalar o bash - cada agente
recebe uma shell bash -, apenas já não precisa dele para arrancar. O que isso
custa são os arrays, `[[ ]]`, `${var//x/y}` e `<(...)`; `local` mantém-se,
porque as três shells o têm, e o `pipefail` é testado numa subshell antes de
ser ativado, porque o dash não o tem. Um teste recusa cada uma dessas
construções, já que uma funcionalidade da shell que não existe falha no
momento da instalação, na máquina de outra pessoa.

O que o Alpine precisa e o Debian não, e porque nenhum deles é opcional:

| | Porquê |
|---|---|
| `shadow` | O daemon privilegiado chama `useradd --home-dir --create-home --shell`. O `adduser` do BusyBox não tem nenhuma dessas opções, e um agente que não pode ser criado é a aplicação inteira a não funcionar |
| `bash` | A shell que cada agente recebe, e aquilo através do qual `bash.run` corre. O Alpine vem sem ela, e é também por isso que o instalador de Alpine é o único ficheiro deste projeto escrito em shell POSIX e não em bash: `#!/bin/bash` tornaria `curl ... \| sh` impossível na máquina que mais precisa dele |
| `dcron` | Alguma coisa tem de ler os crontabs que o daemon escreve. É também a razão do `-d` mais abaixo |
| `gcc`, `musl-dev`, `libffi-dev`, `python3-dev` | Vários requisitos não publicam nenhuma wheel para musl e são compilados durante a instalação |
| `libcap` | `setcap cap_net_bind_service` no binário do haproxy, no modo `direct`. O systemd concedia isso por serviço com `AmbientCapabilities`; o OpenRC não tem equivalente |

Três coisas que a adaptação teve de mudar no código, cada uma descoberta ao
instalar:

- **`crontab -u <agent>` em vez de baixar para o agente.** O `crontab` do
  Debian é setgid e qualquer utilizador o pode executar; o dcron do Alpine
  instala-o com `4750 root:wheel`, por isso um agente que o execute recebe
  `Permission denied`. As formas de manter o desenho antigo eram pôr todos os
  agentes em `wheel` - o grupo que significa sudo na maioria dos sistemas - ou
  afrouxar um binário setuid do sistema. O daemon é root e pode, em vez disso,
  nomear o utilizador.
- **`-r` ou `-d` ao apagar um.** O Vixie cron apaga um crontab com `-r`; o
  dcron com `-d`, e responde a `-r` com uma mensagem de utilização e o código
  de saída 2. Tentar apenas `-r` deixava para trás o crontab de um agente
  eliminado, ainda a apontar para o runner de um utilizador que já não
  existia. Tentam-se os dois, porque o que decide é o binário instalado, não o
  nome da distribuição.
- **`executable=` em `browser.conf`.** O Playwright não publica nenhuma build
  para musl, por isso, em Alpine, o pacote fica totalmente de fora dos
  requisitos e não há navegador. A linha é lida por
  `browser.fReadConfiguredExecutable` e é onde se nomearia um Chromium do
  sistema, no dia em que houver um Playwright que consiga conduzir um.

Mais uma, descoberta ao olhar para `/proc/<pid>/fd/2` na máquina de testes
Alpine: o `supervise-daemon` envia o stdout e o stderr de um processo para
`/dev/null`, a menos que se lhe diga outra coisa, e nada mais no Alpine os
recolhe - as unidades em Debian têm o journald para isso. Nenhum serviço
escrevia nada em lado nenhum. Cada script OpenRC nomeia agora `output_log` e
`error_log`, um ficheiro por serviço em `/opt/boa/logs/`, criado como `boa` em
`start_pre` para que o logrotate o possa rodar como `boa`, seja quem for que
lá escreva. `fInstallLogRotation`, nos dois instaladores, escreve
`/etc/logrotate.d/boa` para esses ficheiros e para os dois do gunicorn:
semanal, oito guardados, `copytruncate` porque ambos os escritores mantêm o
seu ficheiro aberto, e nunca `install.log`, que é do root e contém a
palavra-passe. A outra metade da mesma descoberta: o separador Sistema
operativo perguntava ao OpenRC pelo `crond`, o cron do BusyBox, enquanto o
instalador executa o `dcron` no seu lugar, por isso um Alpine saudável
indicava o cron como parado. `fPickOpenRcCronService` pergunta pelo primeiro
dos dois que tenha um script de serviço.

E duas que o instalador contorna em vez de corrigir, porque pertencem ao
pacote haproxy do Alpine: não traz `/etc/haproxy/errors/`, nem `/run/haproxy`
para o socket de administração. Ambas as linhas são retiradas da configuração
quando o seu ficheiro ou diretório não existe, o que também está correto numa
máquina em que um administrador os tenha criado. Criar `/run/haproxy` foi a
primeira tentativa, com um script em `/etc/local.d/` para o recriar em cada
arranque: o `local` corre no FIM do arranque, por isso o haproxy já tinha
falhado ao arrancar quando ele aparecia.

Mais uma pertence ao próprio OpenRC: guarda em cache a árvore de dependências
dos serviços e decide se a reconstrói comparando marcas temporais com
`/etc/init.d`. Numa reinstalação, os scripts de serviço são reescritos no
mesmo segundo que a cache, por isso ele mantém a antiga e os serviços
ficam de fora dela - arrancam durante a instalação, porque
`rc-service start` não precisa da árvore, e depois não voltam após um
reinício, porque `openrc default` precisa. `fInstallServices` termina com um
`rc-update -u` incondicional.

### O que cada instalador exige da máquina, e o que instala ele próprio

O instalador de Debian recusa-se a correr onde o systemd não é o PID 1
(`fRequireSystemd`, chamado antes de se instalar o que quer que seja). Tudo o
que configura é arrancado e mantido vivo pelo systemd - as dez unidades, o
HAProxy da máquina, o cron -, por isso, numa máquina assim, a instalação
costumava terminar, indicar sucesso e não servir nada: o `systemctl` está
instalado, responde «System has not been booted with systemd as init system
(PID 1). Can't operate.», e nada lia esse código de saída. O que imprime agora
é como resolver: instalar `systemd systemd-sysv dbus`, criar de novo o
contentor com `/sbin/init` como comando e executar de novo o instalador. Diz
«create again» (criar de novo) em vez de «restart» (reiniciar) porque um
contentor em execução não pode mudar o seu PID 1.

O instalador de Alpine toma a decisão oposta quanto ao OpenRC, porque aí a
peça em falta é uma que ele consegue fornecer: o `openrc` é instalado
juntamente com os outros pacotes - uma imagem de contentor vem sem ele, um
Alpine instalado com `setup-alpine` tem-no - e `fEnsureOpenRcUsable` cria
depois `/run/openrc/softlevel`, que é o ficheiro que o próprio OpenRC nomeia
quando se recusa a mexer num serviço num sistema que não foi ele a arrancar.
Depois disso, os dez serviços arrancam num contentor. O registo diz que não
voltarão por si sós, porque `/run` é um tmpfs e o PID 1 não é o OpenRC.

As duas decisões não são incoerentes: não se consegue pôr o systemd a
funcionar como outra coisa que não o PID 1, e o OpenRC consegue.

### `if ! fMain` desliga o `set -e` para a instalação inteira

Ambos os instaladores terminam com o fMain arrancado como processo filho:

    fMain "$@" &
    vMainPid=$!
    if ! wait "${vMainPid}"; then ...

e não com `if ! fMain "$@"`, que é o que parece e o que costumavam ter. Um
comando na condição de um `if` corre com o errexit suspenso, e a suspensão é
herdada por todas as funções que ele chama e por todas as funções que essas
chamam - o que é a instalação inteira. Medido numa máquina sem systemd: oito
comandos falharam seguidos, cada um imprimiu o seu erro, o script continuou
por cima de todos eles e terminou com «Installation finished». Um processo
filho recupera o errexit, porque a suspensão não sobrevive a um fork. O bash,
o dash e o ash do BusyBox comportam-se todos assim, nas duas metades dessa
frase, e nem um `set -e` dentro da função nem uma subshell o recuperam.

Duas consequências de correr o fMain num filho: `trap fCleanup EXIT` também é
instalado dentro do fMain, porque uma subshell não herda o trap de EXIT do pai
e a árvore transferida em `/tmp` ficaria para trás em cada execução; e o pai
limpa o seu próprio trap antes de sair, para que a linha «Exited with code»
não seja impressa duas vezes.

`fHasTty` é uma correção da mesma família: abre `/dev/tty` e volta a fechá-lo,
em vez de testar `[ -r /dev/tty ]`. O nó de dispositivo é legível pelo modo em
todos os sistemas, por isso esse teste passava em `ssh host ./installer` sem
pty e o `read` que se seguia morria com ENXIO - um processo sem terminal de
controlo não o consegue sequer abrir.

### O haproxy.cfg de origem não é trabalho de ninguém

`fInstallMachineProxy` substitui `/etc/haproxy/haproxy.cfg` quando está no
modo `proxied`, e não mexe sem perguntar primeiro num ficheiro que não tenha
sido ele a escrever - o proxy da máquina pode estar a servir outros sites. O
problema é que o ficheiro que encontra numa máquina acabada de instalar foi lá
posto pelo pacote haproxy, que **este instalador instalou ele próprio** um
minuto antes, em `fInstallDependencies`.

Tratar esse exemplo como trabalho de alguém foi o que deixou parado cada
`--install` simples: sem `--yes`, sem terminal onde responder, e a execução
terminava em «Destructive operation with no terminal to confirm on» depois de
já ter construído a árvore, o virtualenv e os certificados. Medido nas quatro
máquinas de testes, Debian e Alpine por igual, executando exatamente a linha
que o README dá.

`fMachineProxyIsPristine` pergunta ao gestor de pacotes em vez de adivinhar:

- Debian: o md5 que o dpkg registou para esse conffile (`dpkg-query -W -f
  '${Conffiles}'`) contra o md5 do próprio ficheiro.
- Alpine: o hash que o apk registou para esse ficheiro, lido de
  `/lib/apk/db/installed` (a linha `Z:` debaixo de `R:haproxy.cfg`), contra o
  `openssl dgst` do ficheiro. `Q1` é sha1 em base64, `Q2` é sha256.

`apk audit --system` parece a resposta do Alpine e não é: medido em Alpine
3.24, não indica **nada** para um `/etc/haproxy/haproxy.cfg` editado. A
primeira versão desta verificação acreditou nele, e teria substituído o proxy
de alguém sem perguntar - a única coisa que a confirmação existe para evitar.
Testado desde então com o ficheiro do pacote, com uma linha acrescentada e com
o ficheiro que este instalador escreve.

Intacto significa que é substituído com uma linha no registo e sem pergunta
nenhuma. Editado significa o comportamento antigo: deixado em paz num
`--update`; confirmado e guardado como cópia em `.before-boa.<timestamp>` numa
instalação ou numa reinstalação.

### Um só ficheiro para o registo e para a palavra-passe

O instalador escreve `/opt/boa/logs/install.log` e mais nada: o que fez e, no
fim, as credenciais que gerou. Costumava escrever dois ficheiros em /root -
`app-web-install.log` e `app-web-credentials.txt` - e dois ficheiros em dois
sítios são duas coisas para encontrar. `fMigrateInstallFiles` copia o que está
nos antigos para o novo antes de os remover, porque a palavra-passe que lá
está pode ser a única cópia que alguém tem.

Três detalhes seguram isto:

- `fLog` cria o diretório quando não existe. O registo vive dentro da árvore
  que o instalador está a construir, por isso, numa primeira instalação, não
  existe quando a primeira linha é escrita, e um `--reinstall` apaga-o a meio.
- `fRemoveInstallation` copia o registo para o lado antes de
  `rm -rf /opt/boa` e volta a pô-lo no lugar depois, para que uma
  reinstalação não leve consigo o seu próprio registo.
- O ficheiro é `root:root 0600` dentro de um diretório que pertence a `boa`
  com 0750. O `boa` pode fazer-lhe unlink - é isso que significa ser dono do
  diretório - e não consegue ler a palavra-passe que lá está; os agentes não
  estão no grupo `boa` e nem sequer conseguem entrar no diretório.

A página de início de sessão nomeia esse caminho, em
`frontend/templates/login.html`, numa linha própria e colorida com
`--colour-path`. Não está nos quinze ficheiros de tradução: a frase acima
dele é traduzida, o caminho é o mesmo em todo o lado, e um caminho encaixado
a meio de uma frase é um caminho que alguém volta a escrever mal.

### Logótipo circular da aplicação

`frontend/static/img/boa.svg` é uma marca circular azul com três agentes
robóticos, da cintura para cima, de fato preto, camisa branca e gravata
escura. As cabeças têm painéis metálicos claros, articulações mecânicas e
viseiras escuras com olhos azuis. O estilo é ligeiramente ilustrado, com
texturas de tecido suaves e sem lenço de bolso no agente central. As cabeças
ligam-se a pescoços robóticos visíveis; o agente central, maior, está à frente
dos dois agentes laterais, mais pequenos. A ilustração sombreada é um WebP de
512px embutido em SVG, com um recorte circular e transparência fora do
círculo. As figuras mantêm-se opacas e com o mesmo aspeto em todos os temas.
Isto é uma ilustração raster dentro de um contentor SVG, não caminhos
vetoriais. `favicon.svg` contém a mesma ilustração. Mantenha os dois ficheiros
SVG sincronizados. Os URL do início de sessão, da barra lateral e do favicon
usam `v=robot-agents` para renovar as cópias em cache da marca anterior. Os
tamanhos apresentados continuam a ser 30px na página de início de sessão e
24px na barra lateral.

### A interface fala en-US até alguém dizer o contrário

`fGetLanguage` lê a escolha de `localStorage` e, se não encontrar nenhuma,
devolve `en-US`. Antes negociava primeiro com `navigator.languages`, o que
significava que uma instalação nova falava o idioma do primeiro navegador que
a abrisse - o idioma de uma máquina, não uma decisão. A escolha está a um
controlo de distância, no canto da caixa de início de sessão e nas
Definições, e é recordada por navegador.

Viviam dois bugs no mesmo ficheiro, e ambos se manifestavam como «o formulário
de início de sessão não muda de idioma até se mudar duas vezes»:

- `fApplyTranslations` só escrevia uma cadeia quando o ficheiro carregado tinha
  essa chave, e o `textContent` já tinha sido reescrito pelo idioma anterior.
  Assim, mudar para en-US - que não tem ficheiro, `dTranslations` é `{}` - não
  mudava rigorosamente nada, e mudar para um idioma a que faltasse uma chave
  deixava essa chave no idioma anterior. A cadeia original de cada elemento
  traduzido é agora guardada num `WeakMap` da primeira vez que é traduzido, e
  uma chave sem tradução repõe-na.
- `fSetLanguage` guardava a escolha e depois chamava `fLoadTranslations()` sem
  argumentos, o que voltava a ler a escolha do armazenamento. Numa janela
  privada o armazenamento lança uma exceção, a leitura devolve o idioma
  anterior e a página volta a carregar o que já estava a mostrar. Agora passa
  o idioma que lhe foi dado.

`fLoadTranslations` leva um número de sequência, para que duas mudanças em
rápida sucessão não possam chegar fora de ordem e deixar a página num idioma
que ninguém pediu. Três coisas nele estavam erradas, e cada uma mostrava ao
utilizador um idioma que não tinha escolhido:

- O atributo `lang` era definido no INÍCIO, antes de o ficheiro ter sido
  obtido. Um 404 ou um erro de interpretação deixava então no ecrã as cadeias
  do idioma anterior sob o nome do novo idioma: `lang=fr-FR` com texto em
  espanhol. Nada é publicado até o dicionário estar na mão, e `fPublish`
  define os dois em conjunto porque a falha é precisamente os dois serem
  definidos em separado.
- A sequência era verificada ANTES de `await response.json()`. Um CORPO lento
  de um pedido anterior chegava depois de um posterior ter terminado. É
  verificada depois de cada await, porque a sequência pode avançar em
  qualquer um deles.
- Uma falha não dizia nada e deixava a página num estado desconhecido. Recorre
  a en-US e informa através de `fOnLoadFailed`.

### en-US.json é a fonte, e o markup é o recurso

O carregador resolvia `en-US` em curto-circuito como um dicionário vazio, com
o argumento de que o markup já traz o texto en-US. Isso é verdade, e fazia de
`en-US.json` quinhentas chaves de peso morto: distribuído, listado como
catálogo, verificado pelos testes quanto à paridade com os outros treze, e lido
por nada. Corrigir uma gralha nele não mudava nada no ecrã, e a única forma de
o descobrir era experimentar.

Agora é obtido como qualquer outro idioma. O texto do markup continua a ser o
recurso que sempre se disse que era: uma chave que o catálogo não tem, ou um
catálogo que não carrega, continua a deixar uma página legível em vez de uma
página de espaços em branco. O que mudou foi qual dos dois é a fonte.

### Quinhentas chaves não são uma interface traduzida

Quatro tipos de cadeia visível não tinham chave nenhuma, por isso ficavam em
inglês nos catorze idiomas:

| O quê | Como é traduzido agora |
|---|---|
| O título do separador | `data-i18n` em `<title>`, uma chave por página |
| As falhas da própria API | Viajam um `code` e os seus `params`; o navegador escreve a frase em `fDescribeApiError`. `error` fica para o que vem de fora - as palavras de um fornecedor, a recusa de um servidor de correio -, para o qual não se deve inventar uma tradução |
| Descrições dos modelos | Não estão nos catálogos: o `agent.json` de cada modelo traz a sua descrição nos quinze idiomas, e o servidor escolhe a que a interface pede (`agent_package.fPickDescription`) |
| Esquema e descrição do tema | `theme.scheme.<scheme>` e `theme.desc.<id>`, o mesmo acordo. O NOME não é traduzido: um tema é a paleta de alguém com um nome, e traduzir «Nord» não ajudaria ninguém a encontrá-lo |

Um modelo ou um tema que alguém escreva para a sua própria instalação mantém
as suas próprias palavras em vez de desaparecer.

A lista pendente de idiomas na página de início de sessão lista códigos -
`es-ES`, `en-US` - e não nomes de idiomas. Quinze nomes nas suas próprias
línguas tornavam o controlo tão largo como a caixa; o código ocupa 80px, e é o
que alguém que procura o seu idioma identifica mais depressa numa lista de
códigos. Os nomes completos ficam na página de definições, que tem espaço.

### Da direita para a esquerda

O hebraico escreve-se da direita para a esquerda, e uma página disposta da
esquerda para a direita com hebraico lá dentro é uma página que ninguém
consegue ler. Quatro decisões fazem com que a mesma folha de estilos sirva as
duas direções:

**A direção viaja com o idioma.** `fPublish`, em `i18n.js`, define `dir` em
`<html>` no mesmo passo que `lang`, a partir de `lRightToLeftLanguages`, para
que os dois nunca discordem - a falha que a função existe para evitar só com
`lang`. As linhas de grelha e de flex seguem `dir` por si, pelo que a barra
lateral e tudo o que está disposto em linha se espelham sem uma regra própria.

**A folha de estilos diz início e fim, não esquerda e direita.** Cada margem,
preenchimento, borda, `inset` e `text-align` que diga respeito ao fluxo do
texto é uma propriedade lógica (`margin-inline-start`, `inset-inline-end`,
`text-align: start`). O único `left` físico que resta em `app.css` é o anel à
volta do avatar de um agente, que é geometria e não texto.

**O conteúdo mantém a sua própria direção.** O código, os caminhos e os
comandos vão da esquerda para a direita em todos os idiomas
(`code, pre { direction: ltr; unicode-bidi: isolate }`), pelo que um caminho
dentro de uma frase em hebraico não é reordenado. Uma mensagem de conversa, e
cada parágrafo de uma resposta apresentada, tomam a sua direção da sua própria
primeira letra (`unicode-bidi: plaintext`): uma resposta em inglês numa página
em hebraico lê-se da esquerda para a direita, uma em hebraico numa página em
inglês da direita para a esquerda. As caixas de texto onde alguém escreve texto livre seguem a mesma regra, e uma caixa vazia segue a página, pelo que o seu texto de ajuda se lê da direita para a esquerda em hebraico (`dir="auto"` disporia uma caixa vazia da esquerda para a direita, texto de ajuda incluído); o crontab e o endereço de
correio eletrónico levam `dir="ltr"`.

**O que se lê da esquerda para a direita fica isolado dentro de uma frase.** O
algoritmo bidi atribui um caractere neutro ao lado que ele toca, pelo que um
caminho no fim de uma frase em hebraico perdia a barra e o ponto final para as
palavras à volta: "/tmp/x/007/." era apresentado como ".tmp/x/007/ /". Num
idioma da direita para a esquerda, `fPublish` faz passar o dicionário por
`fIsolateLeftToRightRuns`, que envolve cada `{placeholder}` e cada sequência
com uma barra em U+2068 FIRST STRONG ISOLATE ... U+2069 POP DIRECTIONAL
ISOLATE, de modo que o valor que um chamador coloca numa frase fica dentro do
isolado. O que a máquina comunica em Definições → Sistema operativo
(`fLeftToRight` em `settings.js`), uma rota na documentação da API
(`.endpoint-path`), a linha de exemplo do crontab e as contagens nos
separadores e nas colunas são isolados da esquerda para a direita do mesmo
modo; sem isso, uma versão do kernel era apresentada como
"deb13-amd64 · x86_64+6.12.111".

### O ramo de onde se transfere o código

`cRepoBranch` é `main`, o ramo real do repositório. Era `master`, o que só
funcionava porque o GitHub redireciona o nome antigo depois de uma mudança de
nome - um redirecionamento que desaparece no dia em que exista um ramo
`master` real, e que ninguém faz para `--repo-url file:///...`, que é como os
dois instaladores são testados.

### Porque é que a aplicação traz o seu próprio HAProxy

O HAProxy da máquina encaminha para a porta 11443 com `send-proxy-v2`, por isso
um cabeçalho PROXY chega **antes** do handshake TLS. O Gunicorn não o consegue
ler aí: a sua opção `proxy_protocol` interpreta esse cabeçalho enquanto
interpreta o HTTP, o que acontece depois de o TLS ser terminado, por isso os
bytes do cabeçalho caem no handshake e partem-no com `WRONG_VERSION_NUMBER`.
Isto foi descoberto ao implementar, não ao testar.

O HAProxy aceita ambos num único bind - `accept-proxy ssl crt ...` - por isso a
aplicação traz a sua própria instância, que é também o único componente a
escutar numa porta. Em vez disso, o Gunicorn faz bind a um socket Unix, o que
significa que não há forma de entrar na aplicação sem passar pelo proxy, e o
endereço real do cliente sobrevive como `X-Forwarded-For` - sem isso, o limite
de tentativas de início de sessão veria 127.0.0.1 para toda a gente e deixaria
de ser por endereço.

É HAProxy e não nginx porque a implementação já depende do HAProxy: nenhuma
tecnologia nova para um problema que uma existente resolve.

O HAProxy da máquina não deve usar `option ssl-hello-chk` neste backend: o
ClientHello dessa verificação é anterior ao TLS 1.2, por isso falha contra um
bind que o exige e marca o backend como em baixo para sempre. O sintoma é um
503 de um serviço que está a correr perfeitamente, o que vale a pena saber
porque nada nos registos da própria aplicação diz que há algo de errado.

E a verificação tem de bater à porta 11080, não à 11443. Uma verificação TCP
contra o bind TLS liga e desliga sem handshake, e este HAProxy registava cada
uma como «SSL handshake failure» - medido na máquina de testes Debian, 64 075
linhas em dois dias, uma a cada dois segundos, a enterrar no journal tudo o
que fosse real. `check-ssl verify none` foi a primeira tentativa e trocou uma
linha por outra: o fecho abrupto da verificação chegava enquanto o handshake
ainda estava a ser concluído, e cada verificação registava ou isso ou
`ECONNRESET`. Contra a 11080, o mesmo ligar-e-fechar é uma sessão nula que
`option dontlognull` mantém fora do registo, as duas portas pertencem a um só
processo, e o journal ficou em silêncio: zero linhas em trinta segundos, com o
site a responder 200 a partir de fora.

Assim, o backend no HAProxy da máquina é, por inteiro:

```
backend https-out
  mode tcp
  server srv-https-out 127.0.0.1:11443 check port 11080 send-proxy
```

`send-proxy` é o que transporta o endereço do cliente. `check-send-proxy` fica
de fora de propósito: a 11080 não aceita o protocolo PROXY. A versão disto
destinada ao operador está em MANUAL.pt-PT.md, em «Como deve ser o HAProxy da
máquina».

Não fixa nenhum `maxconn`, e isso não é um esquecimento. `maxconn 2048` pede
ao kernel 4131 descritores de ficheiro e o HAProxy sai em vez de arrancar sem
eles: *Cannot raise FD limit to 4131, current limit is 1024 and hard limit is
4096*. Reportado a partir de um LXC Alpine a correr sob OpenWrt num BPI-R3,
cujo limite rígido é 4096: o `boa-proxy` foi reiniciado setenta vezes, nada
chegou a escutar na 11443, e uma primeira instalação terminou em «The
application did not answer on port 11443 (last code: 000)». As duas máquinas
de testes são LXC de Proxmox com um limite rígido de 524288, e é por isso que
nenhuma o mostrou, e `haproxy -c` aceitou o ficheiro em todas elas - a
configuração nunca foi inválida, o processo morria no arranque. Sem `maxconn`,
o HAProxy dimensiona-se a partir dos descritores que consegue de facto ter,
que é o que a sua própria mensagem pede, e `fd-hard-limit 4000` limita o que
ele toma onde o limite é enorme. Medido com um mesmo binário em três limites
rígidos: 4096 dá maxconn 1987, 1024 dá 499, 524288 dá 1987. Um teste arranca o
haproxy real sobre o ficheiro distribuído com um limite rígido de 4096 e exige
que se mantenha de pé, e volta a arrancá-lo com o antigo `maxconn 2048` e
exige que morra - um teste que apenas lia o ficheiro foi a razão por que isto
escapou da primeira vez.

Há três coisas que precisam genuinamente de root: criar um utilizador de
sistema, instalar o crontab de outro utilizador e arrancar um processo como
outro utilizador. Tudo o resto não. Por isso o root vive num pequeno daemon
com um **vocabulário fechado de verbos** sobre um socket Unix, e não há,
deliberadamente, nenhum verbo que signifique «executa este comando». Um
atacante que chegue a esse socket pode criar um agente sem privilégios; não
pode executar código como root.

O socket é `0660 root:boa`, e `SO_PEERCRED` é verificado em cada ligação para
que só o root e o `boa` sejam servidos, diga o modo do ficheiro o que disser
depois de alguma atualização futura.

### Uma alteração tem de vir das próprias páginas deste site

O cookie de sessão é `SameSite=Lax`, o que impede que um pedido de outro site
o leve consigo. Não impede outra ORIGEM no mesmo site: um agente com
`bash.run` pode servir uma página neste mesmo anfitrião, numa porta sua, e uma
ligação para ela a partir de uma resposta na conversa está à distância de um
clique. Um formulário aí a fazer POST para `/api/admin/agents/000/run` é um
pedido do mesmo site, o cookie viaja e a execução arranca; sendo um POST
simples sem corpo, também não há preflight que se atravesse no caminho. Por
isso `fRefuseChangesFromElsewhere`, um `before_request` no blueprint da API,
responde 403 a qualquer POST, PUT, PATCH ou DELETE que não tenha vindo das
próprias páginas deste site: um cabeçalho `Origin` tem de nomear exatamente
este anfitrião e esta porta - `localhost` e `localhost:8080` são duas origens,
e a segunda é precisamente a página que um agente poderia servir - e um
cabeçalho `Sec-Fetch-Site` tem de dizer `same-origin`. Um pedido sem nenhum
dos dois não é de um navegador: é um script ou são os testes, e fica para o
início de sessão julgar, como antes. Um GET não é barrado: não muda nada, e
uma página de outro lado não consegue ler a resposta, porque não há cabeçalhos
CORS que lho permitam.

### A API dos agentes, e porque existe sequer

Há duas coisas que pertencem a `boa` e não podem ser legíveis pelos agentes: a
base de dados do kanban (um agente que a pudesse escrever diretamente poderia
reescrever o histórico de outro agente) e as credenciais dos canais (um token
de bot não é uma mensagem — é autoridade permanente para enviar).

Por isso os agentes chegam a ambas através de `boa-agent-api`, por um segundo
socket Unix que qualquer agente pode abrir. A autorização são duas
verificações independentes:

1. O token apresentado coincide com o SHA-256 guardado do token de um agente.
2. `SO_PEERCRED` diz que o processo que chama pertence ao utilizador *desse* agente.

Qualquer uma sozinha seria mais fraca: um token divulgado é inútil a partir da
conta errada, e ser a conta certa é inútil sem o token.

É um socket Unix e não HTTPS porque não há nada a ganhar com TLS entre dois
processos na mesma máquina, e um certificado autoassinado significaria que
todos os agentes correm com a verificação desativada — o que é pior do que não
ter TLS, porque parece segurança.

### Onde vive o estado, e porque está dividido

| Estado | Onde | Porquê aí |
|---|---|---|
| Configuração do agente | `agents/xxx/info.json` | O agente tem de a ler como ele próprio |
| Histórico do agente | `agents/xxx/runs.jsonl` | O único sítio onde um agente pode escrever |
| Procedimentos partilhados | `skills/<Name>/SKILL.md` (root, 0755) | Lidos por todos os agentes que os recebem, escritos por nenhum |
| Índice de agentes, início de sessão, definições | `db/boa.sqlite` (0700 `boa`) | O processo web precisa dele |
| O quadro | `kanban/kanban.sqlite` (0700 `boa`) | Muitos escritores em simultâneo |

Não há, deliberadamente, **tabelas `runs` nem `usage`**. Um processo de agente
não consegue abrir a base de dados que pertence a `boa`, e conceder-lhe acesso
de escrita permitiria a qualquer agente reescrever o histórico de qualquer
outro. Em vez disso, cada agente acrescenta ao seu próprio diário, e a
aplicação web lê-os através de `boa-exec`. O benefício adicional é que um
agente continua a registar o que fez quando a aplicação web está em baixo.

O quadro é SQLite e não um diretório de ficheiros JSON porque vários agentes a
acordar no mesmo minuto do cron é o caso normal, e só uma transação impede que
duas inserções simultâneas se sobrescrevam uma à outra.

### O que contém uma cópia de segurança

`--backup` escreve um único arquivo com tudo o que a instalação é e o código
não é, e `--restore` põe um no lugar do que uma máquina tem; ambos estão nos
dois instaladores, função a função. A lista é a tabela acima convertida numa
linha de `tar`: as duas bases de dados, as chaves e os canais, os
certificados, todos os agentes com a sua pasta pessoal e os seus ficheiros
protegidos, as competências e as ferramentas. À volta disso, três coisas que um
`tar` de `/opt/boa` faria mal:

- **As bases de dados passam pela API de cópia de segurança do SQLite**,
  `fCopySqliteDatabase`, e não pelo `cp`. Ambas correm em modo WAL, por isso
  uma cópia do ficheiro `.sqlite` perde o que ainda estiver no ficheiro
  `-wal`, e uma cópia feita a meio de uma escrita pode ficar rasgada. O
  `python3` do venv tem o módulo; o comando `sqlite3` não existe em nenhuma das
  distribuições. A mesma razão corta no sentido inverso no restauro: os
  ficheiros `-wal` e `-shm` antigos são removidos antes de o ficheiro
  restaurado ser lido, ou o SQLite aplicar-lhe-ia o registo antigo.
- **Os utilizadores dos agentes viajam pelo nome.** `agents.txt` regista o
  utilizador, o uid e o gid de cada agente, e `fRestoreAgentUsers` cria os que
  faltam, sempre com o mesmo nome e com os mesmos ids quando estes estão
  livres. A propriedade no arquivo é mapeada pelo nome na extração, por isso
  um `boa` ou um `agent-001` com outro uid na máquina nova continua a ser dono
  dos seus ficheiros. Os crontabs vivem no spool do cron, não em `/opt/boa`,
  por isso são lidos com `crontab -l` e repostos com `crontab -u`.
- **Três ficheiros ficam de fora de propósito**: `config/ports.conf`,
  `config/browser.conf` e o `haproxy.cfg` gerado a partir deles descrevem ESTA
  máquina, e um restauro não deve importar as escolhas de outra máquina. O
  registo de instalação viaja como `install.log.backup`, com outro nome para
  que um restauro nunca escreva por cima do registo que está a ser escrito
  nesse momento; as suas linhas de credenciais são acrescentadas ao registo
  atual, porque o início de sessão depois de um restauro é o da cópia de
  segurança.

O restauro é a única ação que substitui dados e não pode ser desfeita, por
isso pede confirmação como uma reinstalação. Ambas as funções são executadas
pelos testes sobre uma árvore real, em bash e em dash: verifica-se o que o
arquivo contém e deixa de fora, a árvore é danificada de todas as maneiras que
um restauro tem de desfazer, e o restauro é verificado ficheiro a ficheiro.

### Uma competência é indexada no prompt e obtida a pedido

A memória de um agente é carregada inteira em cada prompt de sistema, e isso
está certo para uma memória: o seu limite de caracteres é configurável por
agente (8000 por omissão, de 1000 a 1 000 000 permitidos) e é a única coisa que
o agente não consegue voltar a deduzir.

As competências não são assim. Um procedimento é uma página ou duas, um agente
pode receber vários, e a maioria das execuções não precisa de nenhum - a
verificação do disco não precisa do procedimento dos certificados. Carregá-los
como se carrega a memória significaria pagar por todos em cada chamada de cada
execução, e os tetos em `info.json` medem-se em tokens.

Por isso o prompt leva um índice - uma linha por competência, o seu nome e a
sua descrição - e o corpo é obtido com `skill.read`, uma vez, por um agente que
decidiu que precisa dele. Cinco competências custam cerca de 200 tokens por
execução em vez de 10 000, e a que é lida é cobrada uma vez em vez de em cada
chamada.

A descrição no cabeçalho é, portanto, a parte que sustenta o peso: é com base
nela que o agente decide, e é por ela que todas as execuções pagam, seja a
competência lida ou não.

### As competências pertencem ao root, como as ferramentas

Uma ferramenta pertence ao root porque a aplicação a importa como código. Uma
competência não é executada por nada, mas é anteposta ao raciocínio de um
agente que acorda às quatro da manhã sem ninguém a vigiar, o que a torna
exatamente tão sensível como `system-prompt.md` - e esse ficheiro já vive num
diretório que o agente pode ler e não pode escrever.

Por isso não há editor de competências na interface web, nem verbo
privilegiado para escrever uma. As competências escrevem-se no servidor por
SSH. A interface decide que agente recebe qual, que é o mesmo que faz com as
ferramentas.

A outra metade dessa decisão é onde vivem: `/opt/boa/skills/`, fora de
`webapp/`, porque `fDeploySourceCode` faz `rm -rf` a `webapp` e um
procedimento que alguém escreveu neste servidor não é algo que uma atualização
tenha o direito de apagar. O mesmo raciocínio, e o mesmo sítio na árvore, que
`/opt/boa/tools/`.

A aplicação não traz nenhuma. Não há `backend/skills/` e os instaladores não
copiam nada para esse diretório: criam-no vazio, pertencente ao root e com o
modo 0755. Uma competência é um procedimento para UMA instalação - estes
anfitriões, esta cópia de segurança, este certificado -, por isso uma genérica
seria um procedimento que ninguém segue, a ocupar uma linha de cada prompt de
cada execução para o dizer. O diretório estar vazio numa instalação nova é a
funcionalidade a funcionar, não uma peça em falta.


### `deploy/` não é implementado

`/opt/boa/webapp/` contém `backend/` e `frontend/` e mais nada. O diretório
`deploy/` - as unidades, as duas configurações do HAProxy, os modelos de
agente, os catálogos de fornecedores, `requirements.txt` e o próprio
instalador - é material do próprio instalador, e é lido da árvore que o
instalador acabou de transferir para `/tmp`, que é deitada fora quando ele
termina.

Não é só arrumação. Ler as unidades de uma cópia em `/opt/boa` significava
instalar as unidades da versão que estivesse no disco; lê-las da árvore
transferida instala as unidades da versão a ser implementada, que é o único
par sobre o qual se consegue raciocinar. Cada uma dessas leituras chama
primeiro `fRequireSourceCode`, para que um passo que alguma vez corra antes da
transferência falhe com uma frase em vez de copiar de `/deploy/...`.

É também por isso que `gunicorn.conf.py` está em `backend/web/` e não em
`deploy/`: o gunicorn lê-o em cada arranque, por isso tem de ser um ficheiro
que esteja de facto no servidor, e o diretório que está no servidor é o que
contém o código que ele configura.

O que é implementado é `root:root`, diretórios `00755` e ficheiros `0644`,
definido por `fSetCodeModes` e por mais nada. Nada debaixo de `webapp/` é
executado pelo caminho - o daemon executa o runner como
`venv/bin/python3 .../runner.py`, e o mesmo faz o crontab que escreve para
cada agente -, por isso nenhum ficheiro aí precisa do bit de execução. Tinha-o
mesmo assim até isto passar a ser uma só função: `fDeploySourceCode` definia
`0644` e `fCreateDirectoryTree`, que corre depois dele numa atualização, fazia
então `chmod -R 00755` sobre a mesma árvore.

### O Telegram recebe HTML e, em recurso, as palavras

Um modelo escreve markdown. Mostrado em bruto, isso é `**25G free**` com os
asteriscos a meio da frase, que é o que chegava a um telemóvel até isto.

O Telegram apresenta um pequeno subconjunto de HTML - catorze etiquetas,
nenhum atributo digno desse nome, e nenhum cabeçalho, lista ou tabela entre
elas. Por isso `telegram_html` traduz aquilo para que há etiqueta e encontra
uma forma legível para aquilo para que não há: os cabeçalhos passam a negrito
numa linha própria, os itens de lista recebem uma marca, e uma tabela passa a
um bloco `<pre>` preenchido com espaços, que é a única forma de as colunas
ficarem umas debaixo das outras num telemóvel.

Três coisas nele sustentam o peso.

**O escape vem primeiro.** `&`, `<` e `>` são markup para o Telegram, por isso
um agente que reporte `grep <dev> && echo` produz uma mensagem a que o
Telegram responde com um 400 - o que quer dizer uma mensagem que nunca chega.
Cada pedaço de texto passa por `fEscape` antes de qualquer coisa o envolver.
Um href passa por `fEscapeAttribute`, que também faz escape às aspas duplas:
um URL que contivesse umas fecharia o atributo e transformaria o resto de si
próprio em atributos que ninguém escreveu.

**Uma mensagem rejeitada é enviada de novo como texto simples.** O que quer
que o renderizador tenha feito mal, as palavras valem mais do que a
formatação, por isso um 400 é repetido sem `parse_mode` e a linha sai sem
formatação. O recurso regista o que o Telegram disse, porque uma formatação
que se degrada em silêncio para sempre é uma formatação que ninguém corrige.

**Uma resposta que o Telegram rejeita é descartada, e uma que não consegue
receber é guardada durante uma hora.** `fSay` devolve três coisas e não duas:
enviada, não respondida e rejeitada - um 4xx que não seja 429,
`ChannelRejected`, que é o Telegram a dizer que não a esta mensagem e a querer
dizer o mesmo amanhã: o bot bloqueado, o chat desaparecido, o token revogado.
`fDeliverAnswers` costumava manter a linha em qualquer falha e tentar de novo
na passagem seguinte, e a linha está no disco para que um reinício não perca
uma resposta, por isso um bot bloqueado transformava o listener num ciclo sem
fim: a consulta no seu modo rápido, uma leitura da conversa através do daemon
root e até dois pedidos ao Telegram em cada passagem, reinício após reinício.
Uma resposta rejeitada é descartada de imediato com uma linha a dizê-lo, e uma
resposta que o Telegram não tenha aceitado dentro da hora que uma execução
recebe também é descartada, pela mesma razão pela qual o outro ramo desiste de
uma execução que nunca terminou. Nenhuma das duas perde a resposta: está na
conversa do agente na interface web, onde foi escrita primeiro.

Os padrões são os mesmos que `frontend/static/js/markdown.js` usa. Dois
renderizadores em desacordo sobre o que conta como markdown significariam uma
mesma resposta a ler-se de forma diferente nos dois sítios onde é mostrada, e
o sentido de enviar para ambos é que são a mesma conversa.


### O Discord é consultado periodicamente, e uma resposta tem dois mil caracteres

O Discord é o segundo canal através do qual uma pessoa pode responder a um
agente, e a metade que recebe é `discord_listener` - `boa-channel-discord`, o
sétimo serviço. Há quatro coisas que o separam do do Telegram.

**Consulta periodicamente, por REST.**
`GET /channels/<id>/messages?after=<id>`, a cada cinco segundos, e a cada dois
enquanto um agente está a meio de uma resposta. O Gateway é a alternativa
óbvia e não foi a escolhida: é um WebSocket que precisa de heartbeats, de um
protocolo de retoma e de uma dependência que este projeto não tem, e precisa
de que a Message Content Intent esteja ligada no portal de programadores - sem
a qual todas as mensagens chegam com `content` vazio e nada diz porquê. A
consulta periódica também liga para fora, que é o que permite que isto corra
numa LAN sem nada reencaminhado, tal como faz o long poll do Telegram. O que
custa é uma latência medida em segundos, e doze pedidos por minuto contra um
limite de cinquenta por segundo.

**Dois mil caracteres, não quatro mil.** `channels.cMaxMessageLength` é 4096,
que é o teto do Telegram, e o Discord responde 400 a um `content` com mais
de 2000. Uma resposta longa não chegava encurtada - não chegava.
`discord_markdown` corta-a entre linhas em, no máximo, quatro mensagens, e um
bloco delimitado dentro do qual caia um corte é fechado no fim de uma e aberto
de novo no início da seguinte: sem isso, uma metade chega como texto simples e
a outra como um bloco que nunca acaba, o que no Discord engole tudo o que se
diga depois. Cada parte é registada como sendo desse agente, porque uma pessoa
responde à que estiver no seu ecrã.

**Sem botões, e `!` para os comandos.** Carregar num botão e um comando de
barra são ambos *interações*, e uma interação chega pelo Gateway ou por um
endpoint HTTPS que o Discord consiga alcançar. Um canal consultado
periodicamente não vê nenhum dos dois. Por isso `/agents` é `!agents`, uma
mensagem normal, e a lista é uma lista de nomes para escrever em vez de uma
coluna de botões. `/agents` também é aceite, porque quem configurou o bot do
Telegram vai escrevê-lo por hábito.

**A resposta de um agente não menciona ninguém.** Cada mensagem que isto envia
leva `allowed_mentions: {"parse": []}`, por isso um `@everyone` que um modelo
escreva é texto e não uma notificação para um servidor inteiro. `replied_user`
mantém-se ligado: uma resposta deve chegar a quem perguntou. Uma regra no
socket em vez de num prompt, pela mesma razão pela qual a lista de
reencaminhamento de correio o é.

O que o Discord não tem é o silêncio do Telegram perante estranhos. Não há
nenhum `chat_id` com que comparar: o bot pede um canal e lê esse canal, por
isso quem pode falar com os agentes é quem pode escrever nele. Um canal
privado é a configuração que corresponde ao que `fIsFromTheConfiguredChat`
impõe no código - e está indicado no manual, porque é toda a autorização que
há.

O webhook que este canal tinha antes continua lá e continua a enviar. Um
webhook não consegue ler, não consegue responder e não recebe de volta nenhum
id de mensagem, por isso `listen` sobre um webhook é recusado em vez de
oferecido: um interruptor que não faz nada é pior do que nenhum interruptor.

### Um encaminhamento, dois listeners

`agent_routing` contém o que os dois listeners fazem de forma idêntica: que
agentes existem, a leitura de um nome a partir de `@News Miner`, `/news_miner`
ou `@002`, com a correspondência mais longa a ganhar, o que um agente disse
para fechar um turno, e o relatório de estado. O protocolo fica em cada um
deles - um long poll não é uma consulta REST, um teclado inline não é uma
lista de nomes, e uma resposta é `reply_to_message` num e `message_reference`
no outro.

Foi escrito quando o segundo listener o foi, e o relatório de estado é a
razão. Duas cópias dessa resposta seriam duas respostas a «está a correr?», e
a primeira coisa em que discordariam seria quantos serviços há.

O envio não está lá. Fica em cada listener como `fSay`, que é o que permite a
um teste substituir o de um listener e deixar o outro em paz.

### Um navegador, partilhado; um perfil, não

`web.fetch` lê uma página pública e fica por aí: sem sessão, sem formulário,
sem botão. O navegador é a outra coisa, e divide-se em dois:

| | Onde | Quem é o dono |
|---|---|---|
| O navegador | `/opt/boa/playwright/` | root, 0755, uma cópia |
| O perfil | `agents/xxx/browser/profile/` | o agente, 0700, um para cada |

O binário é partilhado porque é um binário e não há nada a isolar nele; uma
cópia por agente seriam 600 MB cada e uma atualização a fazer N vezes. O
perfil não é partilhado, porque contém os cookies: o agente 007 a iniciar
sessão em algo não pode deixar o agente 008 com a sessão iniciada. Essa
separação é a do kernel, a mesma pasta pessoal 0700 em que vive tudo o resto
de um agente - que é precisamente o que um produto de agentes alojado não
consegue oferecer quando todos os seus agentes partilham uma máquina e um
conjunto de sessões.

Daí decorrem três decisões:

**O navegador fica aberto entre chamadas a ferramentas dentro de uma
execução.** `browser.click` atua sobre o que `browser.open` deixou no ecrã, e
uma execução é um único processo da primeira chamada a uma ferramenta à
última, por isso um handle ao nível do módulo é todo o estado de que isso
precisa. O `atexit` fecha-o; sem isso, um agente horário deixa um Chromium
para trás em cada execução e enche a máquina até de manhã.

**O Playwright é importado dentro das funções, nunca ao nível do módulo.** As
ferramentas do navegador aparecem listadas na interface quer tenha sido
instalado um navegador quer não, e um ImportError no topo fá-las-ia
desaparecer dessa lista sem explicação em lado nenhum. Importado tarde, um
navegador em falta é uma frase que diz que comando executar.

**Em modo headless, e só endereços públicos.** O que se quer é a sessão e o
DOM, não uma imagem de uma janela, por isso um ecrã virtual seria uma peça
móvel para nada.

«Só endereços públicos» é imposto por um handler de rotas instalado no
CONTEXTO (`browser.fInstallNetworkPolicy`), não por cada ferramenta. Verificar
o URL em `browser.open` cobria exatamente um endereço por execução: uma página
é livre de redirecionar, e uma página que um agente recebeu ordem de ler é
livre de conter uma ligação, um iframe, uma imagem ou um formulário a apontar
para `127.0.0.1` - e `browser.click` não tinha verificação nenhuma. No
contexto, cobre navegações, redirecionamentos, cliques, submissões e todos os
sub-recursos, e a sexta ferramenta de navegador que alguém escreva recebe-o
sem saber que existe. O que é recusado é nomeado na resposta da ferramenta,
porque, de outra forma, um pedido bloqueado é invisível: a página apresenta-se
sem ele e o agente gasta o seu orçamento a tentar de novo.

Os nomes de anfitrião são resolvidos uma vez por execução e memorizados, o que
limita, mas não elimina, a janela em que um nome poderia resolver para um
endereço público na verificação e para um privado na ligação. Fechá-la exige
que a ligação fique fixada ao endereço que foi verificado, o que o Chromium
não expõe a partir daqui.

Um cookie de sessão continua a desaparecer quando o navegador fecha, neste
como em qualquer navegador. O que sobrevive é o que o site marcou para
sobreviver.

### O que um fornecedor aceita não é o que diz a norma

Dois adaptadores enviavam algo que o seu fornecedor recusa, e em ambos os
casos o resultado foi o mesmo: todas as chamadas a ferramentas através desse
fornecedor falhavam, em todos os modelos, e nada no conjunto de testes deu por
isso porque o conjunto testava as peças e não a ida e volta completa.

| Fornecedor | O que foi enviado | O que voltou |
|---|---|---|
| Ollama | `kanban__list_cards` descodificado de volta para nada | O registo de ferramentas recusou uma ferramenta que não tinha sido concedida ao agente - o nome que acabara de lhe ser oferecido |
| Google | `"additionalProperties": false`, que é JSON Schema correto | `400 - Unknown name "additionalProperties" at 'tools[0].function_declarations[0].parameters'` |

O `function_declarations[].parameters` do Gemini é um SUBCONJUNTO do JSON
Schema e recusa o que não conhece em vez de o ignorar, por isso
`fCleanSchemaForGoogle` filtra o esquema através de uma lista de permitidos,
de forma recursiva. Uma lista de permitidos e não uma lista de proibidos, pela
mesma razão pela qual todas as listas de permitidos aqui o são: de outra
forma, a próxima chave que alguém acrescentasse a um esquema de ferramenta
seria recusada pelo Gemini, quer alguém se tivesse lembrado de a acrescentar a
uma lista de coisas a retirar quer não.

Ambos foram descobertos ao correr o ciclo inteiro - perguntar, chamar uma
ferramenta, responder a essa chamada - contra as APIs reais com chaves reais.
`_/temp/probe-defaults.py` é essa verificação, e é a única coisa que encontra
esta classe de bug: um esquema válido, um nome correto, e um fornecedor que
não o aceita.

### Um ficheiro de adaptador por fornecedor

Vinte e cinco fornecedores, vinte e cinco ficheiros, mesmo que a maioria fale
o mesmo dialeto. Um único adaptador «compatível com OpenAI» parece arrumado
até um desses fornecedores mudar o nome de um campo, e então a correção tem de
ser feita sem partir os outros vinte. Cada ficheiro traz as peculiaridades do
seu próprio fornecedor: o DeepSeek descarta `reasoning_content` antes de o
runner o poder reenviar, o llama.cpp deteta um template de chat sem suporte de
ferramentas, o vLLM transforma um 404 na lista de modelos que de facto serve,
a Cloudflare constrói o seu endereço a partir da credencial.

O que partilham é `base.py`: uma forma de mensagem neutra modelada sobre
chat/completions, porque a maioria deles já a fala, e o adaptador da
Anthropic traduz para blocos de conteúdo.

Também partilham `openai_dialect.py`, e a diferença entre isso e um adaptador
partilhado é precisamente a questão. O módulo do dialeto contém o próprio
pedido - o POST, os erros HTTP que vale a pena nomear, a interpretação da
resposta -, que não é peculiaridade de nenhum fornecedor. As peculiaridades
ficam em cada ficheiro, declaradas como atributos de classe que o módulo lê:

| Atributo | O que decide |
|---|---|
| `cDisplayName` | O nome em todas as mensagens de erro. «zai request failed» não é o que alguém procuraria |
| `cMaxTokensField` | `max_tokens` ou `max_completion_tokens`, consoante a grafia que o fornecedor seguiu |
| `cToolChoiceMode` | `auto`, `any`, ou `omit` para os fornecedores que recusam o campo. `auto` é o que um agente precisa: um modelo forçado a chamar uma ferramenta em todos os turnos nunca termina uma execução |
| `cChatCompletionsPath` | O caminho depois do URL base, para os poucos que não usam o habitual |
| `cAssistantContentWhenEmpty` | O que enviar em vez de um `content` nulo, para um fornecedor cujo esquema recusa null |

### O que mudaram vinte e duas chaves reais

Cada fornecedor aqui foi chamado com uma chave real, recebeu uma pergunta e uma
ferramenta, e depois recebeu a resposta à chamada à ferramenta que fez. Todos
os vinte e dois que têm chave completam essa ida e volta. Sete coisas só
apareceram no segundo passo - aquele a que um teste com uma resposta
pré-fabricada nunca chega - e cada uma é agora uma linha de código com as
palavras do próprio fornecedor ao lado:

- **A Perplexity tinha retirado o endpoint.** `chat/completions` responde 403
  «Sonar is now the Agent API. Use /v1/responses instead of /v1/sonar», por
  isso esse adaptador foi reescrito contra a Responses API, e o fornecedor
  passou de ser um modelo a ser um router sobre 48 deles.

- **Uma chave numa mensagem de erro.** O Gemini era chamado como `?key=...`,
  por isso um 503 dele punha a chave inteira no erro que o utilizador lê e que
  o diário guarda. A chave passou para o cabeçalho `x-goog-api-key`, e
  `base.fRedactCredentials` agora limpa `key=`, `api_key=`, `access_token=` e
  `token=` de todos os erros que qualquer adaptador produza, porque esse modo
  de falha não deve depender de um adaptador se lembrar.
- **O Gemini 3 quer a sua assinatura de pensamento de volta.** Uma conversa
  cujas chamadas a funções voltam sem a assinatura que ele emitiu é recusada
  sem mais, por isso todos os agentes Gemini falhavam no momento em que tinham
  usado uma ferramenta. `ToolCall.dProviderData` leva-a e traz-a, opaca para
  tudo o resto.
- **A Cloudflare recusa um `content` nulo.** Que é exatamente o que uma
  mensagem do assistente contém quando o modelo respondeu com chamadas a
  ferramentas e sem palavras. Recebe `""`; o dialeto continua a enviar null a
  todos os outros, porque null é o que o dialeto especifica.
- **Raciocínio escrito na resposta.** O MiniMax responde com
  `<think>...</think>` no próprio texto. Retirado no módulo do dialeto e não
  num adaptador, porque é o modelo que o faz, por isso o mesmo modelo por trás
  de um gateway também o faz - e só quando a resposta COMEÇA com a etiqueta,
  para que um modelo que escreva sobre HTML mantenha as suas palavras.
- **A Together deixa o nome do canal à frente.** O gpt-oss escreve em canais e
  a Together devolve «finalThe weather in Madrid»; a Groq e a Cerebras, a
  servir o mesmo modelo, não. Retirado em `together.py`, onde pertence uma
  peculiaridade de um único fornecedor.
- **Quatro modelos predefinidos que o fornecedor não servia.** O 20b da
  Fireworks precisa de uma implementação própria, o da Together não é
  serverless, a Moonshot retirou o kimi-k2.5, e o gemini-3.7-flash responde
  503 «experiencing high demand». Um modelo predefinido que falha na primeira
  execução é pior do que um que esteja uma versão atrás.

Cinco adaptadores não o usam de todo, porque a sua API não é essa: os blocos
de conteúdo da Anthropic, o `generateContent` da Google, o `/completion` do
llama.cpp, o chat v2 da Cohere - que recebe as mesmas mensagens mas responde
com texto em blocos, um motivo de fim próprio em maiúsculas e contagens de
tokens aninhadas em `usage.tokens` - e a Perplexity, que retirou
chat/completions por completo e lhe responde com

    403 Sonar is now the Agent API. Use /v1/responses instead of /v1/sonar

por isso esse adaptador fala a Responses API: uma lista `input` em vez de
`messages`, o prompt de sistema como `instructions`, e uma resposta que chega
como itens de saída - um `message` com o seu texto em blocos, ou um
`function_call` - em vez de como uma escolha. Um resultado de ferramenta volta
como um item próprio, `function_call_output`, associado por `call_id`.

Dois nomes são resolvidos antes de qualquer outra coisa os ver, através de
`factory.dProviderAliases`: `gemini` é como a documentação da Google chama à
API e `google` é o que o `info.json` de todos os agentes diz desde a primeira
versão, por isso ambos chegam ao mesmo adaptador e só um deles é alguma vez
guardado.

Qual dos vinte e cinco pode ser atribuído a um agente decide-se em
`fListProviders`, não no navegador: um fornecedor é `selectable` quando é
auto-alojado ou tem a chave guardada. É um filtro sobre o que vale a pena
oferecer, não uma regra - uma chave também pode viver na pasta pessoal do
próprio agente, onde a aplicação web não consegue olhar, por isso a interface
continua a mostrar a um agente o fornecedor que ele já tem definido.

Essa mesma flag decide uma coisa na interface: a caixa **URL base**, tanto no
modelo principal como no de reserva, é mostrada para um fornecedor
auto-alojado e escondida para um de nuvem. `base.fInit` já recorre ao
`cDefaultBaseUrl` do adaptador, por isso, para um fornecedor de nuvem, o campo
fazia uma pergunta que já estava respondida antes de ser feita - e a única
resposta que podia receber que a predefinição não dá é uma errada. Fica
escondido e não esvaziado: uma instalação que põe um proxy à frente de um
fornecedor de nuvem tem esse endereço guardado, e esconder uma caixa não é
razão para deitar fora o que está nela.

Uma coisa que `base.py` esconde de todos eles é o nome de uma ferramenta. Este
projeto chama a uma ferramenta `family.action`; um fornecedor valida o nome de
uma função contra `^[a-zA-Z0-9_-]+$` e recusa o pedido inteiro por causa do
ponto, sem qualquer indicação sobre o campo que estava errado.
`fToolNameToWire` troca o ponto por `__` à saída e `fToolNameFromWire` volta a
trocá-lo à entrada, em todos os adaptadores, por isso o registo de
ferramentas, a interface, o `info.json` e os registos nunca veem a forma
codificada.

### Tetos, não confiança

Cada execução para no primeiro de quatro tetos: tokens, passos, segundos,
execuções por dia. Existem porque um ciclo sem vigilância sobre uma API paga é
uma fatura em aberto e, num modelo auto-alojado, uma GPU que nunca mais volta.
O `max_tokens` de cada pedido encolhe na medida do que a execução já gastou,
para que uma execução não possa exceder o seu orçamento com uma última chamada
cara.

Há quatro coisas que fazem a diferença entre um teto e uma sugestão, e cada
uma delas era a segunda até ser corrigida:

  - **Nenhum mínimo no pedido de tokens.** `max(512, remaining)` pedia 512
    tokens quando o orçamento estava gasto, por isso a um agente com um token
    restante ainda era permitida meia página.
  - **Cada chamada recebe o tempo que RESTA**, não o tempo limite inteiro da
    execução. O próprio `vTimeoutSeconds` do adaptador é ajustado antes de
    cada chamada, em vez de se acrescentar um parâmetro aos vinte e seis
    adaptadores que implementam `fSendMessages`.
  - **O prazo é verificado antes de cada ferramenta**, não uma vez por passo.
    Um lote de seis chamadas a ferramentas que chegasse mesmo antes do prazo
    costumava correr por inteiro, cada uma com o seu próprio tempo limite por
    cima de uma execução que já tinha acabado.
  - **Um relógio monotónico.** `time.time()` mexe quando o NTP o acerta aos
    saltos, e uma execução que começou «no futuro» nunca chega sequer ao seu
    tempo limite.

O que continua sem limite é o prompt. Uma chamada gasta a sua entrada mais a
sua saída e só a saída é limitada aqui, por isso uma conversa longa ultrapassa
o limite à entrada; contá-la significaria correr o tokenizador de cada
fornecedor sobre a conversa antes de cada chamada. A resposta de fecho depois
de um teto também ultrapassa deliberadamente o orçamento, e di-lo onde é
escrita.

### Uma execução de um agente de cada vez

Dois locks, porque há dois tipos de chamador.

O daemon mantém um `threading.Lock` por agente entre «este agente está a
correr?» e «arrancar o processo». Serve cada pedido numa thread própria, por
isso duas chamadas `run_now` com `only_if_idle` eram duas threads de um mesmo
processo sem nada entre elas - e uma varredura de /proc não consegue ver um
processo que ainda não foi criado por fork. Medido: duas chamadas
simultâneas, duas execuções.

O runner obtém um `flock` em `<home>/run.lock` e mantém-no durante toda a vida
do processo. Esse é a autoridade, porque um crontab arranca o runner
diretamente e nunca passa pelo daemon. Não é uma fronteira de permissões - um
agente com `bash.run` pode arrancar o que quiser -; existe para que a
APLICAÇÃO não arranque o mesmo agente duas vezes, gastando dois orçamentos num
só perfil de navegador e numa só conversa.

### Uma execução que nunca arrancou di-lo

O daemon privilegiado arranca o runner com stdin, stdout e stderr em
`/dev/null`. Tudo o que `fLogLine` escreve vai, portanto, para lado nenhum, e
duas falhas costumavam viver inteiramente nessa saída:

- o lock da execução estava ocupado, por isso esta execução não vai acontecer;
- algo falhou antes de `fExecute` escrever `run_started` - um `info.json`
  ilegível, ou um fornecedor cuja chave de API não foi definida, que é de
  longe a mais provável das duas.

Medido numa instalação real: com o lock ocupado, `POST /agents/001/run`
respondia `202 {"started": true}` e nada aparecia no diário, no `journalctl`
ou em ficheiro algum. A mesma falha sob o cron ERA visível, porque o cron
guarda a saída do que arranca - e é por isso que isto durou tanto tempo. O
buraco esteve sempre só no caminho que a interface usa.

`fRecordRunRefused` escreve-a antes no diário, como um fim com o estado
`refused` e sem `run_id`. Cada parte dessa forma sustenta peso:

| Parte | Porquê |
|---|---|
| `kind: run_finished` | O Histórico mostra fins. Um tipo próprio exigiria que a interface o aprendesse, e uma entrada que nada mostra é o mesmo que nenhuma entrada |
| `status: refused` | `failed_runs` conta os fins cujo estado é `failed`. Nada do agente correu, por isso nada do agente falhou |
| sem `run_started` | `runs` e `max_runs_per_day` contam arranques. Um lock ocupado não pode comer uma das execuções do dia por uma execução que não aconteceu |
| `run_id: ""` | Nada arrancou, por isso não há execução a identificar |

Só é escrito quando nada mais o escreveu. Assim que `fExecute` tem um id de
execução, já escreveu `run_started`, e os seus próprios handlers escrevem o
`run_finished` correspondente antes de voltarem a lançar a exceção, por isso
`fMain` verifica `vRun.vRunId` antes de acrescentar um segundo fim para uma
mesma execução. A mesma verificação decide quem fecha o turno da conversa: os
handlers de `fExecute` fecham-no ao registarem o fim, e `fMain` só o fecha
para uma execução que nunca chegou tão longe. Medido antes de ser assim, na
máquina de testes Debian: cada execução que não conseguia chegar ao seu
fornecedor respondia à sua pergunta duas vezes, com a mesma frase.

### O Histórico mostra o mais recente, e não o fazia

`fReadEntries` devolve um diário do mais antigo para o mais recente - di-lo na
sua própria docstring - e `fRenderRunHistory` tirava-lhe
`.slice(0, cShownRuns)`. Isso são as dez execuções MAIS ANTIGAS. Um agente com
mais de dez execuções para trás tinha um Histórico que nunca mais mudava.

Descoberto ao conduzir a aplicação real com um navegador real, que é a única
forma como poderia ter sido descoberto: todos os outros testes de
`dashboard.js` neste projeto leem o ficheiro e procuram nele uma cadeia, e a
cadeia estava lá. Medido numa instalação real, em três idiomas: um agente cuja
execução mais recente acabara de ser recusada por falta de chave de API
mostrava uma falha de fornecedor de quarenta minutos antes, e a recusa nunca
chegava a aparecer.

`.slice(-cShownRuns).reverse()`: as últimas dez, a mais recente no topo, que é
o que diz o cabeçalho por cima da lista.

A tabela de resumo acima dessa lista tinha duas falhas próprias, ambas
descobertas na mesma captura de ecrã: imprimia `last_status` em bruto, por
isso uma página em espanhol dizia «Último estado: refused», e imprimia
`last_run_at` em bruto, por isso um `2026-09-19T03:44:29Z` nu ficava
diretamente por cima de uma lista de marcas temporais já tratadas. Ambos
passam agora pelo que as linhas abaixo já usavam.

### Uma caixa de correio é a única entrada em que qualquer pessoa pode escrever

As quatro ferramentas `mail.*` seguem exatamente os canais: o agente nomeia o
que quer que se faça, e a API dos agentes - que corre como `boa` e guarda as
credenciais - fá-lo. Um agente que conseguisse ler a palavra-passe da caixa de
correio não teria «acesso à caixa de entrada»; teria a conta, todas as
mensagens nela, para sempre, e a capacidade de enviar como o seu dono.

O que é diferente no correio é a direção em que a entrada viaja. Um agente que
lê uma caixa de correio é um agente cujas instruções chegam, em parte, dentro
das mensagens que lê, escritas por qualquer pessoa no mundo. Daí decorrem três
decisões:

  - **O reencaminhamento só é permitido para endereços que o utilizador
    listou**, e essa lista é verificada dentro de `mailbox`, no processo que
    abre a ligação - nunca no prompt. Uma regra num prompt é um conselho; uma
    regra no socket é uma regra. Sem lista, o reencaminhamento é recusado sem
    mais.
  - **Ler não marca nada como visto** (`BODY.PEEK[]` sobre um select só de
    leitura), por isso um agente a olhar para uma caixa de correio não tira à
    pessoa a contagem de não lidas com que ela contava.
  - **Apagar move para o Lixo**, onde a conta tiver um. Aquilo que um agente
    remove com base numa regra escrita no mês passado, uma pessoa ainda
    consegue encontrar. «Esta conta não tem pasta de lixo» e «não foi possível
    ler a lista de pastas» são mantidos separados, porque só o primeiro pode
    acabar num expunge: costumavam chegar a `fDeleteMessage` como a mesma
    cadeia vazia, por isso uma única linha LIST por interpretar transformava
    cada `mail.delete` num apagamento permanente.

### Distribuído com um agente, com muitos oferecidos

A instalação cria exatamente um agente: o orquestrador. Tudo o resto vem do
«+», que oferece três pontos de partida: um agente VAZIO, um `.zip` exportado
de um agente, ou um MODELO do repositório de modelos. Uma instalação que chega
com agentes que ninguém pediu é uma instalação que começa com coisas para
desligar.

Os modelos costumavam vir dentro deste repositório, um ficheiro Markdown cada,
em `backend/agents/examples/`. Agora vivem no seu próprio repositório,
[bunch-of-aigents-templates](https://github.com/nipegun/bunch-of-aigents-templates),
clonado ao lado deste como `../bunch-of-aigents-templates`: um modelo novo
chega a todas as instalações sem uma atualização da aplicação, e uma
instalação pode ser apontada para um fork, ou para um repositório próprio, em
Definições -> Agentes (`templates_repo_url`, `templates_repo_branch`,
verificados por `agent_templates.fValidateRepositoryUrl` e `fValidateBranch`
ao guardar). `agent_templates` transfere o repositório inteiro como o único
`.tar.gz` em que um ramo é servido - o endereço de onde o instalador transfere
a aplicação -, por isso listar os modelos é um único pedido, sem API do GitHub
e sem limite de pedidos. Fica em cache durante cinco minutos por worker web.
Um endereço `file://` com a mesma estrutura
`archive/refs/heads/<branch>.tar.gz` serve uma máquina sem saída para o
exterior.

**Um único formato para tudo o que se torna um agente** (`agent_package`): uma
pasta com `agent.json` e `system-prompt.md` e, opcionalmente, `memory.md`,
`home/...` e `rag/documents.json` com `rag/files/...`. Uma pasta de modelo é
um pacote destes que traz apenas os dois primeiros; um `.zip` exportado é a
mesma estrutura com as opções que o utilizador marcou. Assim, instalar um
modelo e importar um `.zip` são a mesma função, `agent_io.fInstallPackage`, e
tudo o que pode ser exportado pode ser publicado como modelo.

Tudo é verificado antes de existir um agente (`agent_package.fReadPackage`),
porque uma importação que falha a meio deixa um agente que ninguém pediu:

- `agent.json` só pode conter as chaves de `lManifestKeys`, e `format` 1. Uma
  chave desconhecida é recusada em vez de ignorada: é uma gralha num modelo,
  ou um pacote de uma versão mais recente que esta leria mal.
- Não há lugar no formato para `enabled`, para chaves, tokens ou credenciais
  de canais, nem para os canais em que o agente escuta. Um agente importado é
  sempre criado desligado, e um fornecedor viaja apenas como nome, modelo e
  URL base - nunca `api_key_ref`.
- Os horários são cinco campos de cron, mais nada
  (`agents.fValidateSchedule`), e são verificados DE NOVO em
  `exec_daemon.fVerbCreateAgent`. Um horário é escrito no início de uma linha
  de crontab, como root; um que trouxesse " /bin/sh -c ..." ou uma quebra de
  linha seria um comando. Não basta que o processo web verifique: o executor é
  a fronteira.
- As ferramentas só são mantidas quando estão instaladas aqui, e as que ficam
  de fora são listadas (`missing_tools`) para que o utilizador as veja antes
  de confirmar. As competências são passadas como nomes e o executor mantém as
  instaladas, como antes.
- `rag` passa por `rag_settings.fValidateSettings`, como uma escrita a partir
  do separador RAG, e os documentos da biblioteca têm de caber nos limites de
  ficheiro e de armazenamento que o próprio pacote traz.
- Cada caminho da pasta pessoal passa por `agent_home.fValidatePath`:
  relativo, sem `..`, e nunca um nome de topo excluído (mais abaixo).
- Um `.zip` (`ZipSource`) é recusado com um nome de membro que sobe para fora,
  uma ligação, um membro cifrado, um membro que expande mais de 200:1 acima de
  1 MiB, ou mais de 8 GiB no total. Um arquivo de repositório só mantém
  ficheiros regulares; uma ligação nele é ignorada, não seguida.

Criar a partir de um modelo nomeia o MODELO e mais nada. O servidor
transfere-o e lê-o: um pedido que pudesse trazer as suas próprias ferramentas
e o seu próprio horário permitiria ao navegador entregar a um agente uma
permissão que o utilizador nunca marcou. O diálogo põe primeiro o agente
VAZIO, depois o `.zip`, depois os modelos, cujas descrições vêm do
`agent.json` de cada modelo no idioma da interface (`fPickDescription`: esse
idioma ou, na falta dele, en-US).

**Uma importação são três momentos**, porque uma biblioteca pode pesar
centenas de MiB e o HAProxy corta um pedido que não envia nada durante 300
segundos: o navegador carrega o `.zip` em blocos para
`/opt/boa/imports/<id>/` (`boa`, 0700, criado pelos dois instaladores e
listado nos `ReadWritePaths` da unidade web); `fFinishImport` verifica-o por
inteiro e devolve o que instalaria; quando o utilizador confirma,
`fStartImport` instala-o numa thread do processo web, que escreve o seu
progresso em `job.json` para o navegador consultar. Qualquer worker pode
responder à consulta porque o estado é um ficheiro. Um trabalho cuja thread
deixou de escrever durante três minutos lê-se como interrompido: o seu
processo foi reiniciado. Uma falha depois de o agente existir volta a
eliminá-lo (`fInstallPackage`).

**Uma exportação é transmitida em streaming** (`fExportAgent`): o `.zip` é
escrito enquanto é enviado, por isso um agente com uma biblioteca de centenas
de MiB é exportado sem ser mantido em memória. Do crontab só viajam as linhas
que esta aplicação escreveu para executar o agente, como os seus cinco campos
(`fReadSchedules`); qualquer outra linha é um comando que alguém escreveu, e
um pacote que trouxesse comandos executá-los-ia na máquina onde aterra.

**A pasta pessoal é lida e escrita como o agente** (`agent_home`, verbo do
executor `agent_home`): o executor arranca o módulo como o utilizador do
agente, da mesma forma que arranca o worker do RAG, por isso o root nunca
percorre uma árvore que o agente possa reorganizar, e uma ligação plantada na
pasta pessoal não leva a lado nenhum aonde o agente não pudesse já ir. Fica de
fora nas duas direções: o que o sistema lá guarda (`chat.jsonl`, `runs.jsonl`,
os registos de chamadas à API, `run.lock`, `attachments/`), o que tem o seu
próprio lugar no pacote (`memory.md`, `rag/`), o perfil do navegador com as
suas sessões iniciadas, e todas as entradas ocultas no topo da pasta pessoal.
Um `.ssh/authorized_keys` importado seria uma porta de entrada e um `.bashrc`
executa código, e nenhum deles vale o raro uso legítimo.

Um dos modelos, `web-navigator`, não tem crontab. É o do navegador -
abre páginas, inicia sessão, clica e preenche formulários, onde os restantes
leem - e esse trabalho é o que quer que o utilizador acabou de pedir, não algo
para fazer às quatro da manhã. O seu prompt é onde ficam escritas as regras de
que um navegador com sessão precisa: nunca escrever uma credencial, nunca
concluir uma compra ou um envio, e tratar a página como dados e não como
instruções.

`rag-consultant` também não tem crontab: responde a perguntas a partir da sua
própria biblioteca RAG. É o único modelo cujo `agent.json` diz `"rag": {"enabled":
true}`. O runner retém as ferramentas `rag.*` enquanto a biblioteca de um
agente está desligada, por isso, sem isto, o agente seria criado sem
ferramenta nenhuma. O `rag` do pacote chega a `exec_daemon.fVerbCreateAgent`
como `pRag` (o corpo do pedido nunca é lido para isso), onde passa por
`rag_settings.fValidateSettings`, a mesma verificação por que passam as
escritas do separador RAG: um modelo pode ligar a biblioteca e não lhe pode
dar nada que esse separador não pudesse. O seu `max_tokens_per_run` é 40000
porque o runner dimensiona o orçamento de trechos como `max_tokens_per_run`
menos o prompt, o histórico e 4096; com o valor predefinido de 16384 não
haveria espaço para trechos. O seu prompt descreve as ferramentas tal como
são - `rag.read` devolve um trecho e os seus vizinhos, não um documento - e
pede os marcadores `[rag:REF]` que `fResolveCitations` verifica.

### Duas formas de a servir, escolhidas no momento da instalação

Ou 11080 e 11443 em localhost, com um HAProxy à frente em 80 e 443, ou 80 e
443 servidos diretamente. O instalador pergunta, recorda a resposta em
`config/ports.conf`, e uma atualização nunca volta a perguntar nem muda
discretamente as portas em que a máquina escuta.

A diferença não está só nos números: no modo direto, o `accept-proxy` tem de
sair do bind, porque um navegador que liga diretamente à 443 não envia
cabeçalho PROXY e um bind que exija um recusa todos os clientes reais.

No modo `direct`, o HAProxy da própria máquina não é simplesmente deixado em
paz: é retirado. `fRetireMachineProxy` para-o, tira-o de todos os runlevels em
Alpine, desativa-o **e mascara-o** em Debian, e depois apaga
`/etc/haproxy/haproxy.cfg` quando foi este instalador a escrevê-lo, ou move-o
para `haproxy.cfg.before-boa.<date>` quando foi outra pessoa. Pará-lo não
basta por si só: um que fique ativado ocupa a 80 e a 443 no arranque seguinte,
antes de esta aplicação sequer correr, e, sob o systemd, uma atualização de
pacote, o `Wants=` de outra unidade ou um simples `systemctl start` podem
trazer de volta até um desativado. Uma unidade mascarada não pode ser
arrancada por nada, e um haproxy sem `/etc/haproxy/haproxy.cfg` não tem nada a
partir de que arrancar. O que quer que continue a ocupar a 80 ou a 443 depois
disso é nomeado no registo, porque neste modo o proxy não consegue arrancar
sem elas, e descobri-lo a partir de «the application did not answer» meio
minuto depois é uma forma muito pior de o saber.

O que deliberadamente NÃO se faz é remover o pacote haproxy. O `boa-proxy` É
`/usr/sbin/haproxy` - termina o TLS e lê o cabeçalho PROXY à frente do
gunicorn, e no modo `direct` é precisamente o que faz bind à 80 e à 443 -, por
isso purgar o pacote deixaria a aplicação sem nada a escutar, em qualquer dos
modos. O que é retirado é o *serviço* HAProxy da máquina, que é uma coisa
diferente que por acaso usa o mesmo binário. Voltar a `proxied` desmascara a
unidade antes de a ativar, ou o caminho de volta acabaria em «The machine's
HAProxy would not start» por causa de uma máscara que este instalador tinha lá
posto ele próprio.

Medido nas duas máquinas de testes com `--update --ports direct`: a unidade
ficou mascarada em Debian e em nenhum runlevel em Alpine, `/etc/haproxy` ficou
sem configuração, e a aplicação respondeu 200 na 443 e 301 na 80. O caminho de
volta, `--update --ports proxied`, deixou-a de novo ativada e ativa, com 200
na 11443 e na 443. Sete testes EXECUTAM a função contra comandos de serviço
falsos, sobre uma configuração com o marcador e outra sem ele, nos dois modos,
e um deles falha se alguma versão futura chegar a recorrer a `apk del haproxy`
ou `apt-get purge haproxy`.

### Uma confirmação mostra-se onde o utilizador está a olhar

`Settings saved` («Definições guardadas» na interface) costumava ser escrito no
topo da coluna de conteúdo. Isso está bem num painel curto e é inútil num
longo: o botão Guardar no fundo do separador Ferramentas de um agente produzia
uma mensagem vários ecrãs acima, fora do que o navegador estava a desenhar,
por isso guardar parecia não fazer nada.

Agora é um pop-up centrado sobre a coluna de conteúdo, numa camada `fixed` que
é irmã dessa coluna e não filha dela. `fixed` é o essencial: centrar dentro da
coluna cairia no meio do *documento*, o que num separador longo é o mesmo bug
uns ecrãs mais abaixo. A camada para na barra lateral, porque uma mensagem
desenhada por cima da lista de agentes pareceria pertencer à lista de agentes,
e não recebe eventos de ponteiro, por isso nada atrás dela deixa de funcionar
enquanto uma mensagem está visível.

Quanto tempo fica é uma preferência deste navegador (`boa.noticeSeconds`,
Definições → Interface), ao lado do tema e do idioma e pela mesma razão: três
segundos chegam e sobram para uma palavra e não bastam para uma frase, e qual
das duas uma mensagem é depende de quem a está a ler. Os erros são a exceção e
ignoram o número por completo — um erro espera ser fechado, porque é a única
mensagem que tem de continuar lá quando o utilizador volta a olhar para o
ecrã.

Uma mensagem tem três cores, e a terceira existe por causa do que as outras
duas não conseguem dizer. Verde é uma gravação que aconteceu, vermelho é uma
falha, e âmbar é **`No changes to save`** («Não há alterações para guardar»):
carregou-se em Guardar e o formulário continha exatamente o que já está
guardado. Indicar isso a verde é pior do que não dizer nada - «Settings saved»
depois de uma gravação que não escreveu nada é precisamente a frase que
impediria alguém de reparar que a sua edição nunca ficou - e o vermelho
alegaria uma falha onde nada correu mal.

Todos os formulários que guardam verificam-no da mesma maneira: o payload que
*enviariam*, comparado como JSON com o instantâneo tirado quando o formulário
foi preenchido a partir do servidor, ou depois da última gravação. As
definições de um agente constroem esse payload numa só função,
`fCollectAgentPayload`, usada tanto para guardar como para tirar o
instantâneo, porque dois leitores do mesmo formulário que se afastassem um do
outro indicariam «sem alterações» no único campo para o qual um deles nunca
olhou. Os painéis de preferências do navegador já guardavam um instantâneo
assim, para a indicação de «alterações por guardar», e ele responde também a
esta pergunta.

A exceção é um agente **novo**: o seu formulário contém os valores do próprio
modelo e nunca foi guardado, por isso carregar em Guardar escreve-os e passa à
conversa, em vez de dizer que não há nada a fazer.

### A cor é estado, o movimento é atividade

O anel à volta do avatar de um agente transporta dois factos diferentes e
desenha-os em dois canais diferentes, para que nenhum tenha de ser consultado.
Se o agente está ligado é uma cor que não se mexe: verde ou vermelho. Se está
a trabalhar neste momento é movimento: um segmento aceso percorre esse anel
verde no sentido dos ponteiros do relógio. Uma segunda cor estática para
«ocupado» seria uma convenção a aprender, ao passo que algo a rodar se percebe
sem ser ensinado.

É desenhado como um retângulo de cantos arredondados em SVG, colocado
exatamente sobre o contorno, traçado com um tracejado cujo deslocamento é
animado, por isso a **forma fica parada e só a luz se move ao longo dela**. É
essa toda a razão do SVG: rodar um anel em vez disso — um gradiente cónico, um
arco, qualquer coisa sob `transform: rotate` — roda também a forma, e os
cantos deixam de coincidir com o quadrado arredondado por baixo.
`pathLength="100"` normaliza o contorno, por isso a folha de estilos fala em
percentagens do perímetro e nada tem de ser recalculado se o avatar ou o seu
raio mudarem.

Responder a «quem está ocupado?» significa ler a linha de comandos de todos os
processos, o que só o root pode fazer, por isso é um verbo do daemon
privilegiado. Uma única varredura de `/proc` responde por todos os agentes de
uma vez — não uma chamada por agente — e é isso que a torna barata o
suficiente para a barra lateral perguntar a cada cinco segundos. A mesma
varredura sustenta `only_if_idle`, por isso a campainha e a interface não
podem discordar sobre se um agente está a trabalhar.

### Um cartão que vence é anunciado na conversa

A conversa de um agente é o registo de tudo o que foi pedido a esse agente,
não só do que lhe foi escrito. Por isso, quando a campainha arranca uma
execução para um cartão vencido, esse cartão é escrito no `chat.jsonl` do
agente como um turno próprio, e a resposta da execução fecha-o: abrir a
conversa mostra o trabalho a chegar, o que o agente fez com ele e quanto
custou.

Há três decisões que seguram isto.

**É escrito quando a execução arranca, não quando o cartão é criado.** Um
cartão agendado para esta noite e eliminado esta tarde nunca correu, e uma
conversa a dizer que foi entregue seria o registo de algo que não aconteceu. A
campainha só vê cartões que ainda estão no quadro, por isso escrever no
momento do toque é o que torna o anúncio verdadeiro.

**O ficheiro guarda os campos do cartão, não uma frase.** `role: "card"` leva
o id, o título, quem o atribuiu e se foi pedido de imediato; o texto da
mensagem são as próprias instruções do cartão. Todas as palavras à volta deles
são escritas pela interface, no idioma do próprio utilizador — a mesma regra
que faz uma execução parada registar `ceiling: "tokens"` em vez de uma frase
em inglês.

**«Agora» e «às 13:45» têm de ser distinguidos, e no momento em que o agente é
acordado ambos estão no passado.** Por isso o quadro regista qual deles foi
pedido (`run_mode`) em vez de o deduzir depois a partir do relógio, e a
palavra `now` viaja do navegador até `kanban.fValidateRunAt` como palavra,
transformando-se numa marca temporal no único sítio que também regista o que
ela era.

A escrita é tarefa do daemon privilegiado, não da campainha: `chat.jsonl` vive
numa pasta pessoal 0700 que pertence ao agente, e a campainha corre como
`boa`. O daemon faz fork, baixa para o agente, escreve o anúncio e só então
arranca a execução — e, se não for possível escrever na pasta pessoal, a
execução arranca na mesma. O anúncio é o registo do trabalho, não o trabalho.

A falha inversa não é benigna e é tratada ao contrário: se o processo não
puder ser arrancado **depois** de o turno ter sido aberto, o daemon escreve a
falha nesse turno antes de lançar a exceção. Nada mais o fecharia alguma vez,
e um turno aberto não se limita a deixar um cartão sem resposta — fecha para
sempre a caixa de escrita desse agente.

A execução que se segue não é nem uma simples execução agendada nem um turno
de conversa. Escreve a sua resposta de volta na conversa, porque a pergunta
está lá, mas a conversa **não** lhe é reenviada: o seu prompt é o cartão, e
reenviar dez trocas cobraria a cada execução agendada uma conversa que
ninguém está a ter. No runner, essas são duas flags separadas —
`vWritesToChat` e `vIsChat` — e essa distinção é tudo. O corolário é que uma
execução que pare antes de perguntar o que quer que seja ao modelo (um agente
desligado, o teto diário) tem mesmo assim de fechar o turno, ou a interface
espera por uma resposta para sempre e a caixa de escrita fica fechada.

### A documentação da API é uma página desta aplicação

É apresentada a partir da especificação OpenAPI que este projeto constrói, em
vez de carregar o Swagger UI de uma CDN, porque o servidor de produção é uma
máquina de LAN que pode não ter acesso nenhum à internet. Do facto de ser uma
das nossas próprias páginas, e não um widget alheio, decorrem duas coisas.

**Segue o idioma escolhido.** A especificação fica em inglês - é o contrato de
uma API cujos nomes de campos, ids e cadeias de erro estão todos em en-US, e
um `openapi.json` traduzido descreveria uma API que não existe. O que é
traduzido é a página: `fAnnotateSpecForTranslation` pendura uma chave
`data-i18n` em cada pedaço de inglês antes de apresentar, e o navegador
troca-a da mesma forma que faz em todas as outras páginas. Isso mantém as
cadeias nos ficheiros `.json` do frontend, junto de todas as outras, e
funciona também para um leitor anónimo. As chaves são derivadas do texto e do
caminho, em vez de escritas à mão, por isso um endpoint novo traz as suas; uma
chave sem tradução mantém o inglês, que é o que `fApplyTranslations` faz com
uma chave que não conhece.

**Ocupa a coluna que lhe é dada**, como todas as outras páginas. Costumava
manter uma medida de 900px e centrar-se, o que fica bem para prosa e mal para
isto: a página é sobretudo tabelas de parâmetros e blocos de JSON, e estes
estavam a ser espremidos num terço de um ecrã largo com margens vazias de
ambos os lados.

### Os anexos de imagem são uma permissão explícita de ferramenta

`browser.screenshot` guarda um ficheiro; `image.send` anexa-o à resposta
atual. Esta última é uma concessão separada, incluída no modelo web-navigator.
A ferramenta tira um instantâneo do PNG para
`agents/<id>/attachments/<opaque-id>.png`, com um diretório 0700 e um
ficheiro 0600. Sobrescrever mais tarde a captura de ecrã original não altera uma
resposta anterior. `ToolContext.lAttachments` leva as referências até
`AgentRun.fRecordChatAnswer` ou até o seu relatório de falha/execução.

Só o executor lê esses ficheiros privados para o processo web. O seu verbo
`read_chat_attachment` exige uma referência na conversa registada desse
agente, abre cada componente do diretório sem seguir ligações e verifica que a
imagem é um ficheiro regular pertencente ao agente. Lê os PNG em blocos de
1 MiB; as respostas em base64 ficam abaixo do limite RPC existente mesmo para
um anexo de 50 MiB. O endpoint HTTP autenticado transmite os bytes com
`private, no-store`. O frontend constrói URL de imagem locais a partir de IDs,
nunca a partir de URL fornecidos pelo modelo.

O Telegram usa [sendPhoto](https://core.telegram.org/bots/api#sendphoto) para
as imagens elegíveis e [sendDocument](https://core.telegram.org/bots/api#senddocument)
para capturas altas ou grandes, com o PNG original. O ficheiro privado é
carregado como dados multipart; não é necessário nenhum URL público nem acesso
do agente às credenciais do bot. `telegram_deliveries` regista as partes de
texto e de imagem confirmadas de cada turno pendente. As novas tentativas
retomam com a parte em falta, e remover a linha pendente limpa esses pontos de
controlo. As falhas permanentes são comunicadas ao utilizador. As duas caixas
de entrada comparam as marcas temporais UTC do SQLite com a hora Unix;
interpretá-las como hora local fazia expirar entregas recentes durante a hora
de verão.

### Sem passo de build

O frontend são templates Jinja2, CSS simples e JavaScript simples. O alvo de
produção é uma máquina Debian ou Alpine auto-alojada; uma implementação que
precisa de uma toolchain de Node
para mudar uma folha de estilos é uma implementação que apodrece. Pela mesma
razão, `/api/doc/` apresenta a sua própria especificação OpenAPI em vez de
carregar o Swagger UI de uma CDN: um servidor de LAN pode não ter acesso à
internet, e uma documentação que falha sem ele falha precisamente quando
alguém está a depurar.

---

### Transcrição de áudio

Ao arrancar serviços OpenRC, o instalador fecha os descritores 3 e 4 nos comandos `rc-service`. São os pipes de stdout/stderr de SSH que ele guardou: observou-se que o `supervise-daemon` os retinha depois de uma saída bem-sucedida do instalador. A saída normal continua a ser capturada em `install.log`.

`audio_transcription` guarda uma única configuração JSON validada em `settings.audio_transcription`. A OpenAI, a Groq, a Mistral e a Together usam multipart; a Hugging Face e a Cloudflare recebem WAV binário. Reutilizam `api_keys` sem devolver segredos ao navegador. O FFmpeg limita contentores, protocolos, tamanho, duração e tempo de execução. O áudio é dividido em segmentos de 120 segundos (30 segundos para os endpoints em bruto da Hugging Face e da Cloudflare, para não depender de opções de geração de formato longo); o whisper.cpp e a descodificação correm como `boa`, sem shell nem recurso automático a outro fornecedor.

`audio_inbox` persiste o destino, as definições e a transcrição em SQLite. Uma única thread em segundo plano, protegida por um lock de processo, em `boa-channel-telegram` recupera a sua fila depois de um reinício. Um ID de turno reservado permite ao executor confirmar uma submissão repetida antes de verificar se o agente está ocupado. Marcar o trabalho como submetido e inserir `telegram_pending` acontecem numa única transação. O áudio privado vive em `/opt/boa/audio/` (0700, pertencente a boa), exige tanto o início de sessão como uma referência de conversa correspondente para ser reproduzido, e é removido quando os turnos de conversa concluídos são limpos.

Ambos os instaladores compilam o whisper.cpp v1.9.4 depois de verificarem o SHA-256 do arquivo de código-fonte, e transferem o `base`. `whisper_models.json` contém os 30 nomes oficiais, tamanhos e hashes. Só o executor root transfere modelos, através de `install_whisper_model`; URL e caminhos arbitrários são rejeitados. Um ficheiro parcial só fica visível depois da verificação do hash. O root é dono de `whisper/`; o `boa` apenas o lê. As atualizações mantêm os modelos e o áudio; as cópias de segurança incluem o áudio mas excluem os pesos dos modelos. Um interpretador Python em falta é instalado com as dependências antes de se verificar a versão mínima.

### Pedidos em bruto aos fornecedores e o espaço de trabalho do agente

`AgentRun.fSendRecordedRequest` associa um gravador ao fornecedor selecionado
para essa chamada, incluindo as chamadas de reserva e de fecho. Os adaptadores
baseados em Requests usam `BaseProvider.fPostJson`, que regista o mesmo corpo
JSON serializado antes de o enviar. Os clientes dos SDK da OpenAI e da
Anthropic usam hooks de pedido, capturando o corpo preparado, incluindo os
campos do SDK e cada nova tentativa. O gravador nunca guarda cabeçalhos de
autenticação e nunca reconstrói um pedido a partir do histórico da conversa.

`api_calls` escreve um índice em `agents/<id>/api-calls.jsonl` e um corpo
`api-call-<id>.json` completo por pedido, com modo 0600, na pasta pessoal
privada do agente. A retenção remove pedidos inteiros para além dos 100 mais
recentes. O executor só lê ficheiros regulares pertencentes a esse agente,
rejeitando ligações simbólicas e FIFOs. Os corpos viajam em blocos limitados
pelo seu socket; a rota HTTP autenticada transmite o seu texto JSON original
em `body`. O navegador formata os tokens sem interpretar números, por isso os
inteiros grandes e os escapes de cadeias sobrevivem intactos.

O `info.json` protegido guarda `interface.show_api_calls`, por omissão false.
Controla apenas a visibilidade; os pedidos são registados quer o separador
esteja visível quer escondido. `dashboard.js` separa os separadores de
conversa dos separadores de definições e seleciona sempre Chat ao carregar um
agente. Consulta os metadados dos pedidos apenas enquanto API Calls está
aberto, carregando os corpos completos quando os seus detalhes são
expandidos. O cabeçalho das definições identifica o agente pelo id; Executar
agora pertence ao espaço de trabalho, e a eliminação tem o seu próprio painel
dentro de Geral.

A caixa de escrita está fixada logo acima da barra de estado e só `#vChatLog`
faz scroll. Em larguras de computador, `app.css` faz com que `.app` tenha
exatamente a altura de um viewport enquanto a conversa está visível
(`.app:has(#vChatPanel:not([hidden]))`) e passa a altura por uma coluna flex
até `.chat`, por isso não há scroll da página em que o formulário se possa
perder. A 820 px e abaixo, a página volta a deslocar-se como um bloco, e
`.chat` tem um viewport menos `--status-bar-live-height`, que
`api.js:fTrackStatusBarHeight` mantém igual à altura real da barra com um
`ResizeObserver` - num telemóvel a barra parte-se em várias linhas, e um valor
fixo estimado deixava a caixa de texto debaixo dela. Não há linha de ajuda
debaixo da caixa de escrita: `fSetComposerEnabled` escreve-a como segunda
linha do placeholder (como se comporta o Enter, ou que o agente está a
trabalhar), e `fFitChatInputToPlaceholder` mede esse placeholder num gémeo
invisível e define o `min-height` da caixa para que nunca fique cortado. Corre
sempre que o placeholder ou a largura da caixa de escrita mudam
(`fTrackChatInputWidth`). As alturas são definidas através do CSSOM, nunca
através de um atributo `style`, que a CSP descartaria.

### Partilhas Samba por agente

`agents.dDefaultSambaSettings` define a partilha ligada, leitura/escrita,
visível na lista, acesso autenticado, e modos de ficheiro/diretório 0600/0700.
As palavras-passe começam sem estar definidas. `info.json.samba` é
configuração protegida; a palavra-passe só existe na passdb do Samba, privada
do root. Vai para `smbpasswd` pelo stdin, nunca pelo argv, pelo modelo, pelo
objeto devolvido pela API ou pelo `info.json`.

`boa-samba` corre um smbd isolado em TCP 445, com a configuração e o estado
nativo em `/opt/boa/samba/`, pertencente ao root, e os ficheiros de execução
em `/run/boa-samba/`. Não tem serviço homes. O nome de uma partilha é derivado
de `fGetAgentSystemUser`; o seu caminho é sempre `<agent home>/samba`. A
autenticação usa essa conta, e as operações de ficheiros usam o uid desse
agente. O acesso de convidado exige uma definição explícita por agente. O
instalador recusa-se a tomar conta de uma instalação Samba alheia e só
desativa a instância predefinida da distribuição para a instalação própria do
BoA.

O executor cria a pasta depois de criar/indexar um agente e remove a
partilha/conta antes de eliminar o utilizador. Ambos os instaladores
reconciliam os agentes existentes depois de instalar/atualizar/restaurar. Um
lock exclusivo de ficheiro serializa as alterações; `testparm` valida antes da
substituição atómica da configuração. `smbcontrol` recarrega a configuração e
fecha apenas as ligações da partilha alterada. Desativar a partilha de um
agente é independente do interruptor de execução do agente.

A preparação da pasta usa descritores de diretório com `O_NOFOLLOW` e
verificações de propriedade. O Samba recusa ligações dentro da partilha, e uma
guarda preexec do root volta a verificar a raiz da partilha em cada ligação. A
guarda executa o código Python de confiança com `-I`, para que o diretório de
trabalho de um agente não possa fornecer módulos importados.

As cópias de segurança incluem os ficheiros partilhados através do arquivo
normal da pasta pessoal do agente, e as definições através do ficheiro info
protegido. `tdbbackup` tira um instantâneo da base de dados nativa de
palavras-passe enquanto está ativa; a cópia de segurança guarda também o SID
do servidor. O restauro exige o smbd parado, valida uma base de dados
temporária e substitui-a em vez de fundir as credenciais atuais. A exportação
através do antigo formato smbpasswd era rejeitada por alguns RID de contas
nativas e não é usada. `fVerifyInstallation` lê o modo de portas web guardado
para que o restauro verifique a porta HTTPS real, incluindo o modo direto sem
uma flag `--ports` explícita.

Referência: [opções de partilha do Samba](https://www.samba.org/samba/docs/current/man-html/smb.conf.5),
[ferramenta de cópia de segurança TDB](https://www.samba.org/samba/docs/3.6/man-html/tdbbackup.8.html).

### Recuperação local de documentos

O rótulo do separador é `RAG` em todos os idiomas, incluindo os textos de recurso em HTML e JavaScript.

`rag_store` é dono do catálogo por agente (SQLite WAL, FTS5, documentos,
revisões e posições de carregamento). Os nomes originais são metadados; os
nomes dos ficheiros no disco usam identificadores gerados. `rag_extract` lê
PDF/EPUB/TXT/Markdown e invoca localmente o Poppler e o Tesseract para OCR.
Preserva as localizações de página/capítulo e verifica os tamanhos expandidos
dos EPUB antes de os interpretar. `rag_embeddings` usa apenas `AF_UNIX`, com o
caminho fixo `/run/boa-embeddings/engine.sock`: sem nome de anfitrião, proxy
ou recurso à nuvem.

As **Informações do documento** editáveis de um documento são, pela ordem em
que o formulário as mostra (`rag_store.lMetadataKeys`, contra a qual `fAction`
também verifica): ano de publicação, título, subtítulo, autor(es), versão,
idioma e etiquetas. A lista de documentos mostra o subtítulo, quando existe,
logo abaixo do título. O ano é guardado como texto (vazio ou até quatro
algarismos) para que «desconhecido» se mantenha distinto de um número.
`rag_store.fMigrate` acrescenta as colunas listadas em
`rag_store.lAddedColumns`, as introduzidas depois de os catálogos já
existirem (`year` e `subtitle`, até agora): `CREATE TABLE IF NOT EXISTS` nunca
altera uma tabela existente, e tanto as bibliotecas mais antigas como as
cópias de segurança restauradas trazem o esquema antigo. `rag_search.fSource`
põe o subtítulo, o ano, o autor, a versão e o idioma em cada trecho, para que
o modelo consiga distinguir documentos que partilham um título, datar e
atribuir uma citação, e pesar duas edições que discordam, sem uma chamada
extra a `rag.list`. As ligações das citações e a pesquisa na biblioteca
mantêm apenas o título e a localização: nomeiam um sítio, e o subtítulo só
tornaria a ligação mais longa.

`rag_models.json` é o catálogo dos modelos de vetorização: para cada um, o seu
URL fixado e o SHA-256, as dimensões, o contexto, o pooling, os prefixos de
consulta e de trecho, e as duas semelhanças medidas para ele (`min_support`
para o modo verificado, `min_similarity` para o mínimo da pesquisa). Vêm dois:
EmbeddingGemma 300M Q8 (o `default`; 768 dimensões, mean pooling) e
Qwen3-Embedding 0.6B Q8 (1024 dimensões, last-token pooling, uma instrução em
inglês antes de cada consulta e nada antes de um trecho). O que está em uso é
`model` nas definições de execução (`/opt/boa/rag-runtime/settings.json`,
escrito pelo root e legível por todos os agentes), lido através de
`rag_settings.fSelectedModel` e `rag_embeddings.fModel`. `rag_runtime` instala
os pesos - o instalador, o modelo selecionado; o executor, qualquer outro a
pedido (`install_rag_model`, uma transferência de cada vez numa thread, com o
progresso em `rag-runtime/status/<id>.json`) -
e um ficheiro só recebe o seu nome quando o tamanho e o SHA-256 coincidem.
Lança o llama.cpp v0.5.0 com o pooling do modelo e com o id do modelo como
`--alias`. O acesso à rede pertence apenas à instalação. O runtime usa o
tokenizador e os prefixos de recuperação do modelo e rejeita entradas
demasiado grandes. O SQLite guarda texto e vetores; o USearch guarda gerações
HNSW incrementais. Publicar uma revisão muda atomicamente a visibilidade no
catálogo e o nome do índice.

Há um único motor, por isso o modelo é escolhido para a máquina inteira, e é o
executor root que faz a mudança (`rag_exec.fRuntime`): recusa pesos que não
estão no disco, guarda a escolha, move o `min_similarity` de todos os agentes
que ainda estão na recomendação do modelo antigo para a do novo
(`fFollowModelSimilarity`; um valor que alguém escolheu mantém-se) e reinicia
`boa-embeddings`. Nenhum vetor é considerado fiável só com base no ficheiro de
definições. `rag_embeddings.fEmbed` pergunta ao motor que modelo serve
(`/v1/models`, o alias) antes de vetorizar, e lança `EngineUnavailable` quando
não é o esperado ou quando um vetor tem o número errado de dimensões; um
trabalho de indexação passa o modelo com que começou, por isso uma mudança a
meio para o trabalho em vez de misturar dois espaços vetoriais numa só
revisão. Cada documento regista a impressão digital do modelo por trás da sua
revisão publicada (`documents.model`). Na passagem seguinte,
`rag_worker.fWork` vê que o modelo da biblioteca não é o selecionado
(`fFollowNewModel`): descarta os fragmentos das revisões por terminar, volta a
pôr na fila todos os documentos indexados com outro modelo e esquece o índice.
As revisões publicadas ficam. Até chegar a sua vez, um documento é encontrado
apenas pelo FTS5: `fSearch` só constrói classificações vetoriais a partir de
documentos do modelo em uso - através do novo índice, ou comparando os seus
vetores guardados um a um enquanto não houver índice - e acrescenta um
`notice` a dizer quantos documentos estão à espera. O mesmo recurso por
palavras-chave responde a uma pesquisa enquanto o motor reinicia. `rag_verify`
fixa um único modelo para os dois lados da sua comparação e toma o seu limiar
desse modelo.

`boa-rag` corre como boa e pede ao executor existente que lance comandos de
worker fixos. `rag_exec` larga o UID/GID antes de todas as operações sobre
documentos ou SQLite; o root nunca interpreta um livro nem abre o catálogo de
um agente. Os workers usam um lock do sistema operativo, limites de recursos e
estados persistentes. Os RPC de carregamento são blocos de 256 KiB, os de
transferência blocos de 1 MiB; livros inteiros nunca atravessam o protocolo do
executor numa só mensagem. O worker mantém a revisão anterior pesquisável e
retoma os fragmentos concluídos depois de uma interrupção. As definições ficam
na configuração protegida do agente.

Uma falha do motor não é um erro do documento. `rag_embeddings` lança
`EngineUnavailable` (um `ValueError`) quando o socket falha ou o motor
responde 503 enquanto carrega o modelo; qualquer outra recusa continua a ser
um `ValueError` simples. `fIndexDocument` apanha a falha do motor à parte: o
documento volta a `queued` com a MESMA revisão, mantém todos os fragmentos já
vetorizados e mostra o motivo até um trabalho voltar a correr. O comportamento
antigo - `error` e os fragmentos da revisão apagados - perdia horas de um
livro grande em cada `--update`, porque o instalador para `boa-embeddings`
enquanto um worker lançado por `boa-exec` ainda está a correr. `fWork` sonda o
motor (`fIsAvailable`) antes de começar cada documento em fila e termina o
lote perante uma falha do motor; de outra forma, cada passagem do agendador a
cada 5 segundos extrairia ou faria OCR do documento inteiro só para parar no
seu primeiro fragmento.

`rag_search` combina as classificações do FTS5 e as semânticas; as pesquisas
filtradas avaliam o subconjunto selecionado. O runner recupera antes da
chamada de resposta e só concede as três ferramentas RAG só de leitura quando
o RAG está ativado. As fontes são limitadas pelo orçamento de texto
configurado e por uma estimativa conservadora dos tokens da execução. Os
marcadores de citação só resolvem contra fontes efetivamente devolvidas
durante a execução. O fornecedor da resposta pode ser remoto: o processamento
exclusivamente local aplica-se à vetorização.

Os três modos de resposta diferem naquilo que o RUNNER impõe, não apenas no
que o prompt diz. `mixed` deixa o modelo acrescentar conhecimento geral. Em
`documental` e `verified` (`runner.lRagModesThatSearch`), o modelo tem de
chamar ele próprio `rag.search`: `fCheckRagAnswer` devolve, uma vez, uma
resposta final dada sem ela (`cRagSearchFirstPrompt`). A pesquisa do próprio
runner é a última mensagem do utilizador palavra por palavra, e numa conversa
(«e na segunda edição?») isso não encontra nada onde a consulta do modelo,
escrita com a conversa inteira à vista, encontra. Pela mesma razão, uma
pesquisa vazia já não termina a execução documental antes de se perguntar ao
modelo; a garantia passou para o fim: `fFinishRagAnswer` substitui a resposta
de uma execução que não recuperou trecho nenhum por uma frase fixa.
`tool_choice` não é usado para forçar a pesquisa: dos 29 adaptadores, alguns
enviam `auto`, a Cohere não envia nada e a Mistral usa `any`, por isso só o
runner o consegue impor a todos os fornecedores.

`verified` acrescenta `rag_verify`. A resposta é cortada em unidades -
parágrafos, e cada item de lista por si só, com um bloco de código delimitado
associado ao parágrafo anterior e comparado juntamente com ele (a introdução
de um exemplo, sozinha, quase não diz nada, e exemplos fiéis eram removidos
por causa disso); os cabeçalhos, os rótulos curtos terminados em ":" e os separadores estão isentos. Uma
unidade precisa de um `[rag:REF]` entre os trechos recuperados na execução e,
a menos que seja uma referência nua, tem de estar próxima de um deles: a
unidade vetorizada como consulta contra os trechos vetorizados como
documentos, a mesma distância que a pesquisa usa, no `min_support` do modelo
(0,36 para o EmbeddingGemma, 0,44 para o Qwen3-Embedding). A primeira resposta
que falha volta para trás
uma vez com as unidades que falham (`fBuildCorrectionPrompt`); depois disso,
são removidas e uma linha localizada diz quantas. Se não sobrar nada
sustentado, dá a frase fixa; um motor que não se consegue alcançar retém a
resposta (fail closed). As frases fixas (`rag_verify.dFixedTexts`) estão no
idioma em que o prompt de sistema mandou responder, reconhecido pela sua linha
em `dAnswerLanguageLines`, ou em inglês caso contrário. O limite da
verificação está medido e escrito junto da verificação. Em 138 parágrafos
fiéis e 2652 citações a trechos de outro tema, nenhum limiar separa os dois
com qualquer dos modelos; os que estão em uso removem cerca de 6% dos
parágrafos fiéis (sobretudo itens de lista curtos e resumos de uma linha) e
deixam passar menos de 1% dessas citações erradas. Uma citação a um trecho
sobre o mesmo tema passa cerca de um quarto das vezes, e um parágrafo que
contradiz o seu trecho pontua como um fiel: o que a verificação apanha é uma
citação a um trecho sobre outra coisa, e um parágrafo sem fonte.

A cópia de segurança cria instantâneos debaixo de diretórios-pai de
preparação pertencentes ao root, deixa o processo filho do agente fazer uma
cópia de segurança SQLite e criar ligações físicas para os seus ficheiros
imutáveis selecionados, e depois arquiva esse instantâneo. Isto mantém as
gerações WAL e HNSW coerentes e evita que o root percorra uma árvore de
instantâneo que o agente possa trocar. O restauro cancela carregamentos
parciais e volta a pôr em fila as indexações interrompidas. As impressões
digitais dos índices continuam disponíveis para reconstruções.

## 2. Mapa de módulos

| Módulo | Caminho | Responsabilidade | Depende de | Usado por |
|---|---|---|---|---|
| `audio_transcription` | `backend/core/audio_transcription.py` | Definições de voz e motores de reconhecimento | db, api_keys, whisper_runtime | audio_inbox, api |
| `audio_inbox` | `backend/core/audio_inbox.py` | Fila durável, encaminhamento, novas tentativas e reprodução privada | db, exec_client, audio_transcription | telegram_listener, api |
| `whisper_runtime` | `backend/core/whisper_runtime.py` | Catálogo, estado e transferências verificadas de modelos | paths, whisper_models.json | instalador, exec_daemon, api |
| `settings_audio.js` | `frontend/static/js/settings_audio.js` | Formulário de áudio, transferências de modelos e progresso | api.js, i18n.js | settings.js, settings_audio.html |
| `rag_store` | `backend/core/rag_store.py` | Catálogo, carregamentos, revisões e instantâneos | `rag_settings` | `rag_worker, rag_search` |
| `rag_extract` | `backend/core/rag_extract.py` | Extração local de PDF/EPUB/texto e OCR | `rag_embeddings, pypdf, EbookLib` | `rag_worker` |
| `rag_embeddings` | `backend/core/rag_embeddings.py` | Tokenizador e cliente de vetorização por socket local; recusa um vetor de qualquer modelo que não seja o esperado | `rag_settings` | `rag_extract, rag_search, rag_worker, rag_verify` |
| `rag_search` | `backend/core/rag_search.py` | Pesquisa híbrida, publicação HNSW e citações | `rag_store, usearch, numpy` | `runner, tools` |
| `rag_worker` | `backend/core/rag_worker.py` | Trabalhos de indexação duráveis, pertencentes ao agente | `rag_store, rag_extract, rag_search` | `rag_exec` |
| `rag_verify` | `backend/core/rag_verify.py` | Verifica cada parágrafo de uma resposta contra os trechos que cita; as frases RAG fixas em 15 idiomas | `rag_embeddings` | `runner` |
| `rag_exec` | `backend/core/rag_exec.py` | Largada de privilégios e comandos de worker fixos | `paths, rag_settings` | `exec_daemon` |
| `rag_runtime` | `backend/core/rag_runtime.py` | Instalação e transferências verificadas de modelos, motor local, estado e preparação do restauro | `rag_settings, rag_embeddings` | `installers, boa-embeddings, rag_exec, exec_daemon` |
| `rag_models.json` | `backend/core/rag_models.json` | Os modelos de vetorização: pesos, hashes, pooling, prefixos e as semelhanças medidas para cada um | — | `rag_settings` |
| `rag_scheduler` | `backend/core/rag_scheduler.py` | Consulta equitativa da fila | `agents, exec_client` | `boa-rag` |
| `paths` | `backend/core/paths.py` | Todos os caminhos do sistema de ficheiros e a validação dos ids de agente | — | tudo |
| `db` | `backend/core/db.py` | Ligações SQLite e os dois esquemas | `paths` | `agents`, `kanban`, `auth`, `bootstrap` |
| `agents` | `backend/core/agents.py` | Modelo de agente, `info.json` (incluindo as definições Samba), índice de agentes, hashing de tokens | `db`, `paths` | `exec_daemon`, `agent_api`, `api` |
| `bootstrap` | `backend/core/bootstrap.py` | Inicialização na primeira execução | `agents`, `db`, `paths` | instalador |
| `exec_protocol` | `backend/core/exec_protocol.py` | Protocolo de comunicação e lista de verbos | — | `exec_daemon`, `exec_client`, `agent_api` |
| `exec_daemon` | `backend/core/exec_daemon.py` | O daemon privilegiado (root) | `agents`, `paths`, `run_journal`, `api_calls`, `samba` | serviço `boa-exec` |
| `exec_client` | `backend/core/exec_client.py` | Cliente do anterior | `exec_protocol`, `paths` | `web/api` |
| `agent_api` | `backend/core/agent_api.py` | O daemon com que os agentes falam | `agents`, `kanban`, `channels` | serviço `boa-agent-api` |
| `agent_api_client` | `backend/core/agent_api_client.py` | Cliente do anterior | `agent_api`, `exec_protocol` | as ferramentas distribuídas |
| `runner` | `backend/core/runner.py` | Uma execução de agente: o ciclo e os seus tetos | `providers`, `tool_registry`, `run_journal`, `api_calls` | cron, `exec_daemon` |
| `run_journal` | `backend/core/run_journal.py` | `runs.jsonl` por agente | `paths` | `runner`, `exec_daemon` |
| `api_calls` | `backend/core/api_calls.py` | Corpos exatos dos pedidos, índice privado, retenção e leituras limitadas | `paths`, `run_journal` | `runner`, `exec_daemon` |
| `dashboard.js` | `frontend/static/js/dashboard.js` | Espaço de trabalho Chat/API Calls, definições do agente e apresentação diferida dos pedidos | `api.js`, `jsonhighlight.js`, `markdown.js` | `dashboard.html` |
| `chat` | `backend/core/chat.py` | `chat.jsonl` por agente e a conversa reenviada ao modelo | `paths` | `runner`, `exec_daemon` |
| `memory` | `backend/core/memory.py` | `memory.md` por agente, limite de caracteres configurável e escritas completas; carregada no prompt de sistema de cada execução | `agents`, `paths` | `runner`, `exec_daemon`, `web/api`, ferramentas |
| `skills` | `backend/core/skills.py` | Os procedimentos partilhados em `/opt/boa/skills/`, um diretório cada. Interpreta `SKILL.md`, constrói o índice que vai no prompt e diz quais das competências de um agente ainda existem | `paths` | `runner`, `exec_daemon`, `web/api`, `skill.read` |
| `provider_models` | `backend/core/provider_models.py` | Catálogos de modelos a partir de `config/providers/*.json` | `paths` | `web/api` |
| `api_keys` | `backend/core/api_keys.py` | As chaves partilhadas dos fornecedores em `config/apikeys/*.key`, escritas com 0600 num diretório 0700. Nunca devolve uma chave ao navegador, apenas se há uma guardada e os seus quatro últimos caracteres | `paths` | `agent_api`, `web/api` |
| `tool_registry` | `backend/core/tool_registry.py` | Descoberta, permissões e despacho de ferramentas | `paths` | `runner`, `web/api` |
| `attachments` | `backend/core/attachments.py` | Instantâneos PNG privados, IDs opacos, propriedade de ficheiros verificada e leituras limitadas | `paths` | `image_send`, `exec_daemon`, `exec_client`, `telegram_listener` |
| `image_send` | `backend/tools/image_send.py` | Anexa à resposta um PNG próprio através do contexto da ferramenta | `attachments`, `tool_registry` | `runner` |
| `public_url` | `backend/core/public_url.py` | Se um URL que um agente recebeu resolve para um endereço público. Formulado pela positiva com `is_global` mais uma recusa explícita de multicast, porque uma lista de intervalos a recusar é uma lista onde se pode esquecer um - e 100.64.0.0/10 ficou esquecido nela | — | `web.fetch`, `rss.fetch`, `browser` |
| `agent_scripts` | `backend/core/agent_scripts.py` | Scripts que um agente escreve para si próprio, e as linhas de cron que os executam. Valida nomes e horários, e nunca reescreve a linha de despertar | `paths` | `script.*`, `cron.*` |
| `kanban` | `backend/core/kanban.py` | O quadro e o seu histórico | `db` | `agent_api`, `web/api` |
| `channels` | `backend/core/channels.py` | Telegram, Discord, Mattermost, X. Envio para os quatro; leitura para os dois a que se pode responder | `paths`, `telegram_html`, `discord_markdown` | `agent_api`, `web/api`, ambos os listeners |
| `agent_routing` | `backend/core/agent_routing.py` | O que os dois listeners fazem da mesma forma: a lista de agentes, a leitura do nome de um agente a partir de uma mensagem, a resposta fechada de um turno, o relatório de estado | `agents`, `chat`, `exec_client`, `system_info` | `telegram_listener`, `discord_listener` |
| `providers.base` | `backend/providers/base.py` | Interface dos adaptadores e forma de mensagem neutra | — | todos os adaptadores |
| `providers.factory` | `backend/providers/factory.py` | Nome do fornecedor → classe do adaptador | `providers.base` | `runner`, `web/api` |
| `providers.openai_dialect` | `backend/providers/openai_dialect.py` | O pedido chat/completions que os adaptadores do dialeto OpenAI partilham; as peculiaridades ficam em cada adaptador | `providers.base` | a maioria dos adaptadores |
| `providers.*` | `backend/providers/<name>.py` | Um adaptador por fornecedor | `providers.base`, `providers.openai_dialect` | `factory` |
| `web.server` | `backend/web/server.py` | Fábrica Flask, chave de sessão, cabeçalhos de segurança | `db`, `web.*` | gunicorn |
| `deploy/haproxy/boa.cfg` | `deploy/haproxy/boa.cfg` | Terminação TLS, protocolo PROXY, 11080 → 11443 | — | serviço `boa-proxy` |
| `web.auth` | `backend/web/auth.py` | Início de sessão, sessões, limitação de tentativas | `db` | `web.api`, `web.views` |
| `web.api` | `backend/web/api.py` | Tudo o que está em `/api/admin/` | `exec_client`, `kanban`, `channels` | navegador |
| `web.api_doc` | `backend/web/api_doc.py` | Especificação OpenAPI e a sua página. Anota a especificação com chaves i18n apenas para a página, nunca para `openapi.json` | `channels`, `providers.factory` | navegador |
| `web.views` | `backend/web/views.py` | As páginas HTML | `web.auth` | navegador |
| `buzzer` | `backend/core/buzzer.py` | Vigia o quadro e arranca uma execução quando um cartão vence | `kanban`, `exec_client` | serviço `boa-buzzer` |
| `telegram_listener` | `backend/core/telegram_listener.py` | Faz long polling ao Telegram, encaminha cada mensagem para um agente, envia a resposta de volta | `channels`, `exec_client`, `telegram_inbox` | serviço `boa-channel-telegram` |
| `telegram_inbox` | `backend/core/telegram_inbox.py` | Que agente disse o quê no Telegram, e que perguntas ainda estão a ser respondidas. A expiração é calculada em UTC | `db` | `telegram_listener`, `agent_api` |
| `discord_listener` | `backend/core/discord_listener.py` | Consulta periodicamente um canal do Discord, encaminha cada mensagem para um agente, envia a resposta de volta | `agent_routing`, `channels`, `exec_client`, `discord_inbox` | serviço `boa-channel-discord` |
| `discord_inbox` | `backend/core/discord_inbox.py` | As mesmas duas tabelas para o Discord. Separadas das do Telegram: um snowflake é uma cadeia, e um listener não pode conseguir responder às perguntas do outro. A expiração é calculada em UTC | `db` | `discord_listener`, `agent_api` |
| `discord_markdown` | `backend/core/discord_markdown.py` | Markdown convertido no que o Discord apresenta, cortado em mensagens de 2000 caracteres. As tabelas passam a blocos delimitados; um bloco dentro do qual caia um corte é fechado e aberto de novo | `telegram_html` (os padrões de bloco) | `channels` |
| `discord_texts` | `backend/core/discord_texts.py` | As três frases que o Discord diz de forma diferente. Tudo o resto recai em `telegram_texts`, por isso um único catálogo serve os dois bots | `telegram_texts` | `discord_listener` |
| `browser` | `backend/core/browser.py` | O navegador partilhado e o perfil próprio deste agente. Um handle durante toda a execução, fechado pelo `atexit`. Contém a política de rede por que passam todos os pedidos | `paths`, `public_url` | as cinco ferramentas `browser.*` |
| `telegram_html` | `backend/core/telegram_html.py` | Markdown convertido nas catorze etiquetas que o Telegram aceita. Os mesmos padrões que `markdown.js`, para que os dois renderizadores concordem sobre o que é markdown | — | `channels` |
| `telegram_texts` | `backend/core/telegram_texts.py` | O que o bot diz por si próprio, no idioma definido para a instalação | `db` | `telegram_listener` |
| `markdown.js` | `frontend/static/js/markdown.js` | Apresenta a resposta de um agente como nós DOM, nunca como markup | — | `dashboard.js` |
| `jsonhighlight.js` | `frontend/static/js/jsonhighlight.js` | Formata JSON em bruto sem arredondar números e colore-o usando nós DOM seguros | — | `api_doc.html`, `dashboard.html` |
| `themes` | `backend/core/themes.py` | Lista as folhas de estilo em `frontend/themes/` e lê os seus cabeçalhos | `paths` | `web/api`, `web/views` |
| `agent_templates` | `backend/core/agent_templates.py` | Transfere o repositório de modelos (definições `templates_repo_url`, `templates_repo_branch`) como um único `.tar.gz`, guarda-o em cache cinco minutos e lista ou lê os seus modelos | `agent_package`, `db` | `web/api` |
| `agent_package` | `backend/core/agent_package.py` | A forma portátil de um agente: lê um `.zip`, um arquivo de repositório ou uma pasta, e verifica tudo antes de existir um agente | `agent_home`, `agents`, `memory`, `rag_settings`, `rag_store`, `skills` | `agent_templates`, `agent_io` |
| `agent_io` | `backend/core/agent_io.py` | Instala um pacote, corre importações de `.zip` em segundo plano com `job.json`, transmite exportações em streaming | `agent_package`, `exec_client`, `tool_registry` | `web/api`, `web/agent_io_api` |
| `agent_home` | `backend/core/agent_home.py` | Lista, lê e escreve os ficheiros da pasta pessoal de um agente como o agente; o verbo `agent_home` do executor | `paths` | `exec_daemon`, `agent_package` |
| `agent_io_api` | `backend/web/agent_io_api.py` | `/agent-imports/...` e `/agents/<id>/export...` | `agent_io` | `server` |
| `agent_export.js` | `frontend/static/js/agent_export.js` | O separador Exportar: o que cada opção acrescenta, e a ligação de transferência | `api.js` | `dashboard.html` |
| `mailbox` | `backend/core/mailbox.py` | IMAP e SMTP para a caixa de correio configurada. Guarda as credenciais para que os agentes nunca as tenham. Nomeia uma mensagem por UID e UIDVALIDITY, nunca pela sua posição na pasta | `db` | `agent_api` |
| `theme.js` | `frontend/static/js/theme.js` | Acrescenta a folha de estilos do tema escolhido, a partir do head, antes da primeira pintura | — | todas as páginas |
| `night-high-contrast.css` | `frontend/themes/night-high-contrast.css` | Preenche o agente selecionado com cinzento e desenha os separadores selecionados com um contorno fechado unido à linha de base | `app.css` | `theme.js` |
| `settings.js` | `frontend/static/js/settings.js` | Carrega os separadores principais das definições com seletores limitados à sua própria barra de separadores; `fRenderChannelForms` marca os canais configurados com `data-state="good"`, partilhando o estilo do estado das chaves de API e o `--colour-ok` do tema | `api.js`, `i18n.js`, `tools.js`, `app.css` | `settings.html` |
| `tools.js` | `frontend/static/js/tools.js` | Carrega o catálogo dentro de Definições → Ferramentas; mantém o subseparador no parâmetro `family` do URL e atualiza os seus rótulos ao voltar de Interface | `api.js`, `i18n.js` | `settings.js`, `settings_tools.html` |
| `app.css` | `frontend/static/css/app.css` | A classe `system-table` partilha um layout de duas colunas, com 35% para os rótulos, para que os valores da máquina e os estados dos serviços fiquem alinhados; `.chat-attachment img` ocupa 100% da largura do texto, com altura automática e sem limite; `.chat-audio` ajusta-se à largura da mensagem e o seu cabeçalho herda a cor do texto da mensagem | — | `settings.html`, `dashboard.html` |
| `system_info` | `backend/core/system_info.py` | Estado da máquina e nomes dos serviços para o sistema init em execução | `paths` | `web/api`, `agent_routing` |
| `samba` | `backend/core/samba.py` | Ciclo de vida das partilhas, validação, credenciais nativas, pastas protegidas e cópias de segurança | `agents`, `paths`, comandos Samba | `exec_daemon`, instaladores |
| `samba.js` | `frontend/static/js/samba.js` | Formulário Samba diferido, campo secreto e instantâneo por agente | `api.js`, `dashboard.js` | `dashboard.html` |

---

## 3. Índice de símbolos-chave

Apenas símbolos públicos e que sustentam peso. Os números de linha mudam; o
ficheiro e o comportamento são aquilo em que se deve confiar.

### Caminhos e identidade

| Símbolo | Ficheiro:linha | O que faz |
|---|---|---|
| `fNormalizeAgentId` | `backend/core/paths.py:164` | Valida um id de agente e preenche-o com zeros à esquerda. **Todos os caminhos construídos a partir de dados do utilizador passam por aqui.** Lança uma exceção para qualquer coisa fora de 0–999 |
| `fGetAgentHome` | `backend/core/paths.py:179` | `/opt/boa/agents/xxx` |
| `fReadAgentOwnedFile` | `backend/core/paths.py:401` | Como o root lê um ficheiro da pasta pessoal de um agente: no descritor aberto, regular e do próprio agente ou recusado, nunca mais do que um limite. O diário, a conversa e a memória passam todos por aqui |
| `fGetAgentApiTokenPath` | `backend/core/paths.py:485` | Onde vive o token de API de um agente |

### Agentes

| Símbolo | Ficheiro:linha | O que faz |
|---|---|---|
| `fValidateAgentName` | `backend/core/agents.py:71` | 2–40 caracteres, sem metacaracteres de shell |
| `fGetNextFreeAgentId` | `backend/core/agents.py:137` | O id livre mais baixo, a partir do sistema de ficheiros, começando em 001 |
| `fBuildAgentInfo` | `backend/core/agents.py:150` | O `info.json` de um agente novo, com predefinições conservadoras |
| `fWriteAgentInfo` | `backend/core/agents.py:219` | Escrita atómica que preserva a propriedade 0600 |
| `fHashApiToken` | `backend/core/agents.py:256` | SHA-256; o token em bruto nunca é guardado |
| `fFindAgentByApiToken` | `backend/core/agents.py:301` | Transforma um token numa identidade |

### O daemon privilegiado

| Símbolo | Ficheiro:linha | O que faz |
|---|---|---|
| `fIsPeerAllowed` | `backend/core/exec_daemon.py:106` | Só o root e o `boa`, verificado em cada ligação |
| `fRunPrivilegedCommand` | `backend/core/exec_daemon.py:122` | Executa uma lista de comando sem shell, opcionalmente como outro utilizador |
| `fVerbCreateAgent` | `backend/core/exec_daemon.py:396` | Cria o utilizador, a pasta pessoal, a configuração e o token; aplica as ferramentas, os limites, o interruptor e as definições `rag` validadas de um modelo; **reverte perante qualquer falha** |
| `fStartRunner` | `backend/core/exec_daemon.py:304` | O único sítio onde um runner é arrancado como o agente. A mensagem da conversa ou o prompt do cartão segue pela sua entrada padrão, nunca pela linha de comandos |
| `fWatchRunner` | `backend/core/exec_daemon.py:255` | Espera por uma execução: para o seu scope e regista o fim de uma que tenha sido morta |
| `fVerbWriteCrontab` | `backend/core/exec_daemon.py:780` | Instala um crontab como o utilizador próprio do agente |
| `fListRunningAgentIds` | `backend/core/exec_daemon.py` | Uma varredura de `/proc` que nomeia todos os agentes com uma execução em curso. Sustenta tanto `only_if_idle` como o anel a rodar da barra lateral |
| `dVerbHandlers` | `backend/core/exec_daemon.py` | A tabela fechada de verbos. Toda a superfície privilegiada são estas dez linhas |

### A API dos agentes

| Símbolo | Ficheiro:linha | O que faz |
|---|---|---|
| `fAuthenticate` | `backend/core/agent_api.py:121` | O token **e** o `SO_PEERCRED` têm de concordar |
| `fAgentMayUseKanban` | `backend/core/agent_api.py` | Se o quadro está ligado e o agente tem alguma ferramenta de kanban. A metade grosseira |
| `fRequireKanbanTool` | `backend/core/agent_api.py` | Um verbo, uma ferramenta, pelo nome. Todos os handlers faziam a pergunta grosseira, por isso `kanban.list_cards` - uma leitura - chegava a `fDeleteCard` para um agente que pusesse ele próprio o pedido no socket |
| `fRequireOwnCard` | `backend/core/agent_api.py:283` | Um agente só pode alterar cartões que criou ou de que é dono |
| `fVerbChannelWrite` | `backend/core/agent_api.py` | Envia em nome do agente, antepondo o seu nome real |

### O ciclo de execução

| Símbolo | Ficheiro:linha | O que faz |
|---|---|---|
| `AgentRun` | `backend/core/runner.py:336` | Uma conversa limitada |
| `fCheckCeilings` | `backend/core/runner.py` | Devolve o teto que parou a execução, ou vazio para continuar |
| `fSecondsLeft` | `backend/core/runner.py` | O tempo que resta antes do prazo da execução, num relógio monotónico. Cada chamada ao fornecedor e cada ferramenta recebe o que resta, não o teto inteiro |
| `fTakeRunLock` | `backend/core/runner.py` | Um flock em `<home>/run.lock`, mantido durante toda a vida do processo. A única verificação que uma execução arrancada pelo cron também faz |
| `fTrimToByteBudget` | `backend/core/exec_protocol.py` | As entradas mais recentes que cabem num orçamento de bytes, e quantas foram descartadas. Contado em bytes, porque um número de linhas não é um tamanho |
| `fRunWithLimits` | `backend/tools/bash_run.py` | Executa um comando com um teto de bytes aplicado ENQUANTO produz saída, e um prazo que mata o grupo de processos inteiro |
| `fAskForClosingAnswer` | `backend/core/runner.py` | Depois de um teto, pergunta uma vez, sem ferramentas, pela resposta que ficou por dar |
| `fExecute` | `backend/core/runner.py:503` | O ciclo: perguntar, executar ferramentas, devolver os resultados, parar |
| `fSelectAllowedTools` | `backend/core/runner.py:319` | Retém as ferramentas de kanban quando o agente as tem desligadas |
| `fReadStdinArguments` | `backend/core/runner.py:988` | A metade disso que cabe ao runner: lê o texto da entrada padrão, com limite, e recusa uma mensagem de conversa vazia |
| `fApplyResourceLimits` | `backend/core/runner.py:1069` | Baixa os limites de kernel da própria execução antes de arrancar o que quer que seja: processos, ficheiros core, tamanho de ficheiro |
| `fRecordChatAnswer` | `backend/core/runner.py` | Escreve a resposta de volta quando a execução tem um turno para fechar (`vWritesToChat`) |
| `fRecordChatFailure` | `backend/core/runner.py` | Fecha o turno quando mais nada o fará, nomeando o motivo para que a interface o possa traduzir |
| `fAppendCardMessage` | `backend/core/chat.py` | Anuncia um cartão vencido como um turno próprio, com os campos do cartão e sem frases |
| `fBuildCardAnnouncement` | `backend/core/buzzer.py` | O que é dito à conversa: quem o atribuiu e se foi pedido para agora |

### Ferramentas

| Símbolo | Ficheiro:linha | O que faz |
|---|---|---|
| `fGetContext` | `backend/core/browser.py` | Arranca o navegador com o perfil deste agente, ou devolve o que já está a correr |
| `fClose` | `backend/core/browser.py` | Registado com `atexit`. Sem ele, cada execução deixa um Chromium para trás |
| `fIsInstalled` | `backend/core/browser.py` | Se há um navegador para conduzir, para que as ferramentas possam dizer o que executar em vez de lançarem uma exceção |
| `fLoadAllTools` | `backend/core/tool_registry.py:105` | Carrega todas as ferramentas válidas; um ficheiro com problemas é ignorado, não é fatal |
| `fRunTool` | `backend/core/tool_registry.py:138` | Impõe a permissão, devolve `(text, is_error)`; uma ferramenta que lança uma exceção nunca mata uma execução |
| `fGetLimit` | `backend/core/memory.py:53` | Lê o limite de memória protegido por agente, com a predefinição antiga |
| `fValidateContent` | `backend/core/memory.py:71` | Rejeita memória demasiado grande sem descartar texto |
| `fCheckMemoryUpdate` | `backend/web/api.py:127` | Valida a memória e o limite proposto antes de qualquer escrita de definições |
| `fSearch` | `backend/core/rag_search.py:123` | Recuperação híbrida com referências às fontes |
| `fPrompt` | `backend/core/rag_search.py:243` | Os trechos recuperados e a regra do modo de resposta, acrescentados ao prompt de sistema |
| `fVerify` | `backend/core/rag_verify.py:235` | Unidades sem citação recuperada ou diferentes do que citam: devolve o texto mantido e o que foi removido |
| `fSplitUnits` | `backend/core/rag_verify.py:163` | Corta uma resposta em parágrafos e itens de lista, guardando o necessário para a reconstruir |
| `fCheckRagAnswer` | `backend/core/runner.py:681` | Devolve uma resposta final uma vez: ainda sem pesquisa (documental, verificado) ou com parágrafos sem sustentação (verificado) |
| `fFinishRagAnswer` | `backend/core/runner.py:704` | O que é mostrado ao utilizador: frase fixa sem trechos, parágrafos sem sustentação removidos, retida quando não pode ser verificada |
| `fIndexDocument` | `backend/core/rag_worker.py:32` | Extrai, vetoriza e publica uma revisão; `False` quando uma falha do motor a voltou a pôr na fila |
| `fWork` | `backend/core/rag_worker.py:129` | Lote de indexação limitado; espera sem extrair enquanto o motor está em baixo |
| `EngineUnavailable` | `backend/core/rag_embeddings.py:11` | Falha do motor (falha do socket ou 503), distinguida de um pedido recusado |
| `fIsAvailable` | `backend/core/rag_embeddings.py:73` | Sonda barata que o worker executa antes de cada documento: o motor responde, e com o modelo em uso |
| `fCheckServedModel` | `backend/core/rag_embeddings.py:68` | `EngineUnavailable` a menos que o `/v1/models` do motor nomeie o modelo esperado |
| `fSelectedModel` | `backend/core/rag_settings.py:39` | A entrada do catálogo escolhida em Definições → RAG, ou a predefinida quando não há nenhuma guardada ou a guardada é desconhecida |
| `fInstallModel` | `backend/core/rag_runtime.py:76` | Transfere um modelo para um ficheiro privado e só lhe dá o nome depois de o tamanho e o SHA-256 coincidirem |
| `fStartModelDownload` | `backend/core/rag_runtime.py:125` | Põe uma transferência na fila do executor e devolve logo o seu estado |
| `fFollowModelSimilarity` | `backend/core/rag_exec.py:113` | Numa mudança de modelo, passa os agentes que ainda estão no `min_similarity` recomendado do modelo antigo para o do novo |
| `fFollowNewModel` | `backend/core/rag_worker.py:107` | Volta a pôr na fila o que outro modelo indexou, mantendo as revisões publicadas pesquisáveis por palavras |
| `fMigrate` | `backend/core/rag_store.py:83` | Acrescenta, em cada ligação, as `lAddedColumns` que faltam aos catálogos mais antigos (`year`, `subtitle`) |
| `fAction` | `backend/core/rag_store.py:270` | Informações do documento, reindexar, cancelar e eliminar; valida as chaves dos metadados e o ano |
| `fSnapshot` | `backend/core/rag_store.py:334` | Cópia de segurança coerente de documentos/índice |
| `ToolContext` | `backend/core/tool_registry.py:53` | O que é dito a uma ferramenta sobre quem a chama |
| `fStoreImage` | `backend/core/attachments.py` | Copia um PNG da pasta pessoal do agente para um instantâneo privado |
| `fReadImageChunk` | `backend/core/attachments.py` | Lê no máximo 1 MiB, recusando ligações simbólicas, outros donos e ficheiros especiais |
| `fVerbReadChatAttachment` | `backend/core/exec_daemon.py` | Exige uma referência ao anexo na conversa do agente pedido antes de ler |
| `fGetChatAttachment` | `backend/web/api.py` | Transmite o PNG a um utilizador com sessão iniciada, sem URL de ficheiro público nem em cache |
| `fRenderChatAttachments` | `frontend/static/js/dashboard.js` | Mostra as imagens da resposta e um erro quando uma imagem não pode ser carregada |
| `fSetComposerEnabled` | `frontend/static/js/dashboard.js` | Abre ou fecha a caixa de escrita e escreve a segunda linha do placeholder: como se comporta o Enter, ou que o agente está a trabalhar |
| `fFitChatInputToPlaceholder` | `frontend/static/js/dashboard.js` | Faz crescer a caixa de texto até caber o placeholder inteiro, medido num gémeo invisível |
| `fTrackStatusBarHeight` | `frontend/static/js/api.js` | Mantém `--status-bar-live-height` igual à altura real da barra de estado, que o layout da conversa no telemóvel subtrai |
| `fDeliverAnswerParts` | `backend/core/telegram_listener.py` | Retoma a entrega no Telegram a partir da última parte de texto/imagem confirmada |

### Competências

| Símbolo | Ficheiro:linha | O que faz |
|---|---|---|
| `fIsValidSkillName` | `backend/core/skills.py:57` | Um nome, nunca um caminho. Recusa em vez de limpar, como os nomes de modelos e de temas |
| `fParseSkill` | `backend/core/skills.py:77` | O cabeçalho `---` e o corpo |
| `fSelectInstalledSkills` | `backend/core/skills.py:194` | Os nomes da lista de um agente que ainda existem no disco. **Todos os caminhos para a funcionalidade passam por aqui**, por isso uma competência apagada nunca chega a um prompt |
| `fBuildPromptSection` | `backend/core/skills.py:211` | O índice: uma linha por competência, só nomes e descrições. `""` quando o agente não tem nenhuma |
| `fRunTool` | `backend/tools/skill_read.py` | Devolve um corpo, verificado contra o próprio `info.json` do agente |


### Telegram, nos dois sentidos

| Símbolo | Ficheiro:linha | O que faz |
|---|---|---|
| `fReadTelegramUpdates` | `backend/core/channels.py` | Um long poll. A ligação é feita para fora, que é o que permite que isto funcione atrás de um NAT sem nada reencaminhado |
| `fSendToTelegram` | `backend/core/channels.py` | Envia e devolve o `message_id` - a única coisa que torna encaminhável uma resposta posterior |
| `fRedactSecrets` | `backend/core/channels.py` | Retira todas as credenciais de um erro ou de uma linha de registo. `str(RequestException)` cita o URL, e para três dos quatro canais o URL **é** a credencial |
| `fReadConfigForEditing` | `backend/core/channels.py` | O ficheiro de um canal tal como está no disco, para que guardar uma alteração a funda em vez de o substituir |
| `fListConfiguredChannels` | `backend/core/channels.py` | Devolve Discord, Mattermost, Telegram e X por ordem alfabética, com o seu estado e sem segredos; usado pelas Definições e pelas permissões de cada agente |
| `fRouteMessage` | `backend/core/telegram_listener.py` | Para quem é uma mensagem: o agente a quem se respondeu, ou o nomeado com @ |
| `fMatchNamedAgent` | `backend/core/telegram_listener.py` | Correspondência mais longa sobre todos os nomes conhecidos, porque os nomes dos agentes podem conter espaços |
| `fIsFromTheConfiguredChat` | `backend/core/telegram_listener.py` | **Toda a autorização.** Qualquer coisa vinda de outro chat é descartada sem resposta |
| `fDeliverAnswers` | `backend/core/telegram_listener.py` | Envia de volta todos os turnos que fecharam desde a última passagem |
| `fRememberMessage` | `backend/core/telegram_inbox.py` | Associa uma mensagem enviada ao agente que a enviou, podado às últimas centenas |
| `fRouteMessage` | `backend/core/telegram_listener.py` | Para quem é uma mensagem: o agente a quem se respondeu, o nomeado com @ ou /, ou o selecionado |
| `fReadSelectedAgent` | `backend/core/telegram_listener.py` | Com quem é a conversa, verificado contra a lista de agentes para que um agente eliminado deixe de apanhar tudo |
| `fBuildAgentButtons` | `backend/core/telegram_listener.py` | O teclado inline com que /agents responde. O texto de um botão é o bot que o escolhe, ao contrário do do menu de comandos |
| `fBuildStatusReport` | `backend/core/telegram_listener.py` | O que /status diz. Um agente que não consegue ler aparece na lista a dizê-lo, nunca fica de fora |
| `fHandleCallback` | `backend/core/telegram_listener.py` | Um toque num botão de agente: primeiro é respondido, depois o agente é selecionado |
| `fRender` | `backend/core/telegram_html.py` | Markdown para o HTML do Telegram. Os cabeçalhos passam a negrito, as listas a marcas, as tabelas a um bloco monoespaçado - o Telegram não tem etiqueta para nenhum dos três |
| `fEscape` | `backend/core/telegram_html.py` | `&`, `<`, `>`. **Chamado antes de qualquer coisa envolver o texto**, nunca depois |
| `fEscapeAttribute` | `backend/core/telegram_html.py` | O mesmo mais as aspas duplas, para um href. De outra forma, umas aspas num URL fechariam o atributo e inventariam os que vêm depois |
| `fRenderWithinLimit` | `backend/core/telegram_html.py` | Encurta o markdown e volta a apresentá-lo até o HTML caber. Cortar antes o HTML deixaria uma etiqueta meio escrita |

### Discord, nos dois sentidos

| Símbolo | Ficheiro:linha | O que faz |
|---|---|---|
| `fReadDiscordMessages` | `backend/core/channels.py` | Uma consulta. **Inverte o que o Discord devolve**, que vem do mais recente para o mais antigo: responder por essa ordem faria o agente ler uma conversa de trás para a frente |
| `fSendToDiscord` | `backend/core/channels.py` | Envia, em tantas partes quantas o limite de 2000 caracteres exigir, e devolve o id de cada parte |
| `fCallDiscord` | `backend/core/channels.py` | Uma chamada. Um 429 com um `retry_after` curto é aguardado uma vez; qualquer outro 4xx é `ChannelRejected` |
| `fGetDiscordMode` | `backend/core/channels.py` | `"bot"`, `"hook"` ou `""`. Um webhook envia e mais nada |
| `fReadDiscordBotUser` | `backend/core/channels.py` | Que bot é este, escrito no registo uma vez por arranque: quando não chega nada, essa é a primeira pergunta |
| `fRenderToMessages` | `backend/core/discord_markdown.py` | Uma resposta como a lista de mensagens a enviar para ela |
| `fSplit` | `backend/core/discord_markdown.py` | Corta entre linhas, fechando e reabrindo um bloco delimitado dentro do qual caia o corte |
| `fIsFromTheConfiguredChannel` | `backend/core/discord_listener.py` | Todas as mensagens consultadas vieram desse canal por construção; verificado mesmo assim, porque «por construção» é uma propriedade do código de hoje |
| `fReadCommand` | `backend/core/discord_listener.py` | `!agents`, `!status`, `!help`, e as formas com `/`. Só como primeira palavra inteira, ou um agente chamado `status` seria inalcançável |
| `fReadMessageText` | `backend/core/discord_listener.py` | O texto sem a menção ao bot no início: o Discord transforma `@Boa` em `<@123>` antes de mais alguém o ver |
| `fStartFromTheNewestMessage` | `backend/core/discord_listener.py` | Onde começa uma instalação nova. Um bot ligado esta tarde não deve responder a um mês de mensagens do canal |
| `fReadAfterId` / `fWriteAfterId` | `backend/core/discord_listener.py` | A marca, em `config/discord-after`. Um snowflake, não um contador |
| `fRememberMessage` | `backend/core/discord_inbox.py` | Associa uma parte enviada ao agente que a enviou. Podado por ordem de inserção, não por id |

### Partilhado pelos dois listeners

| Símbolo | Ficheiro:linha | O que faz |
|---|---|---|
| `fMatchNamedAgent` | `backend/core/agent_routing.py` | Correspondência mais longa sobre todos os nomes conhecidos. Os prefixos são um argumento: o Telegram aceita `@` e `/`, o Discord acrescenta `!` |
| `fBuildStatusReport` | `backend/core/agent_routing.py` | O que /status diz. Recebe o catálogo do serviço que pergunta e o nome da sua própria unidade, que são as duas únicas coisas que diferem; resolve o nome do serviço do canal para systemd ou OpenRC |
| `fFindClosedAnswer` | `backend/core/agent_routing.py` | O que um agente disse para fechar um turno, lido através do executor |
| `fListAgentNames` | `backend/core/agent_routing.py` | A lista de agentes, a partir do índice: a pasta pessoal de um agente é 0700 e o seu info.json não cabe a um listener abrir |

### Os scripts e o cron próprios de um agente

| Símbolo | Ficheiro:linha | O que faz |
|---|---|---|
| `fValidateScriptName` | `backend/core/agent_scripts.py` | Verifica um nome em vez de o limpar: tudo o que não seja um nome de ficheiro simples é recusado, o que é uma regra em vez de uma regra mais aquilo que a limpeza acabar por fazer |
| `fValidateSchedule` | `backend/core/agent_scripts.py` | A forma de um horário cron, e a única coisa que vale a pena recusar: um trabalho que dispara mais vezes do que alguém pretendia |
| `fIsRunnerLine` | `backend/core/agent_scripts.py` | A linha que acorda o agente. Nunca é reescrita a partir daqui: um agente que a apagasse ficaria calado para sempre, sem forma de dar por isso |
| `fAddCronLine` | `backend/core/agent_scripts.py` | Acrescenta uma linha que executa um dos scripts do próprio agente. O script tem de existir primeiro |
| `fRemoveCronLines` | `backend/core/agent_scripts.py` | Remove todas as linhas que executam um script, e o comentário acima de cada uma |

### Quadro e canais

| Símbolo | Ficheiro:linha | O que faz |
|---|---|---|
| `fAddCard` | `backend/core/kanban.py:132` | O cartão e o primeiro evento numa única transação |
| `fMoveCard` | `backend/core/kanban.py:188` | Movimento mais evento de histórico |
| `fValidateRunAt` | `backend/core/kanban.py:68` | Aceita `"now"`, uma hora do navegador ou uma hora guardada, e normaliza as três |
| `fReadRunMode` | `backend/core/kanban.py:100` | Que tipo de hora foi pedido: `now`, `at`, ou nenhum |
| `fWasRequestedImmediately` | `backend/core/kanban.py` | Se o cartão dizia «agora». Lido de `run_mode`, nunca deduzido do relógio |
| `fAssignCard` | `backend/core/kanban.py` | Entrega um cartão, registando em `assigned_by` quem o entregou |
| `fAgentOwnsCard` | `backend/core/kanban.py:462` | Criador **ou** destinatário |
| `fDeleteCard` | `backend/core/kanban.py:480` | Elimina, mantendo uma linha em `deleted_cards` |
| `fReadMessages` | `backend/core/mailbox.py` | As mensagens mais recentes de uma pasta, só de leitura: nada é marcado como visto |
| `_fParseFolderLine` | `backend/core/mailbox.py` | Uma linha LIST como flags, delimitador e nome. Lança uma exceção em vez de adivinhar: uma listagem ilegível é um erro, não uma conta sem pastas |
| `fListFoldersWithFlags` | `backend/core/mailbox.py` | Todas as pastas com as suas flags SPECIAL-USE |
| `fFindTrashFolder` | `backend/core/mailbox.py` | `\\Trash` primeiro, depois os nomes em nove idiomas. `""` significa que não há nenhuma; uma falha lança uma exceção |
| `fIsForwardAllowed` | `backend/core/mailbox.py` | Se um endereço está na lista do utilizador. Verificado onde está a palavra-passe, nunca num prompt |
| `fListTemplates` | `backend/core/agent_templates.py:134` | Todos os modelos do repositório, resumidos, pelo nome que o utilizador vê; um com problemas aparece com o seu erro |
| `fReadTemplate` | `backend/core/agent_templates.py:151` | A origem de um modelo e o pacote verificado, ou None; recusa um nome que não seja um id simples antes de transferir |
| `fReadPackage` | `backend/core/agent_package.py:418` | Verifica um pacote inteiro - nomes, agent.json, prompt, memória, caminhos da pasta pessoal, biblioteca - e descreve-o |
| `fValidateManifest` | `backend/core/agent_package.py:317` | agent.json: só chaves conhecidas, format 1, horários, ferramentas instaladas aqui, limites, rag, fornecedor sem chave |
| `ZipSource` | `backend/core/agent_package.py:84` | Um `.zip`: recusa nomes que sobem, ligações, cifra, membros de 200:1 e mais de 8 GiB |
| `fReadRepositoryArchive` | `backend/core/agent_package.py:236` | Divide um `.tar.gz` de repositório em pastas de modelo; ignora ligações |
| `fInstallPackage` | `backend/core/agent_io.py:60` | Cria o agente desligado, depois a sua memória, os ficheiros da pasta pessoal e a biblioteca; volta a eliminá-lo em caso de falha |
| `fStartImport` | `backend/core/agent_io.py:265` | Começa a instalar um `.zip` verificado numa thread, uma vez, seja qual for o número de cliques |
| `fExportAgent` | `backend/core/agent_io.py:420` | Produz o `.zip` enquanto é escrito; pasta pessoal e biblioteca transmitidas em streaming |
| `fReadSchedules` | `backend/core/agent_io.py:320` | Só as linhas do crontab que executam o agente, como cinco campos |
| `fValidateSchedule` | `backend/core/agents.py:85` | Cinco campos de cron, uma linha, nada que possa ser um comando |
| `fList` | `backend/core/agent_home.py:86` | Os ficheiros da pasta pessoal que um pacote pode levar, como o agente, excluindo os do sistema e os ocultos |
| `fWrite` | `backend/core/agent_home.py:130` | Escreve um bloco por ordem, sem passar por nenhuma ligação, com modo só para o dono |
| `fBroker` | `backend/core/agent_home.py:170` | Executa uma operação na pasta pessoal como o agente; o verbo `agent_home` do executor |
| `fChooseAgentSource` | `frontend/static/js/api.js` | O diálogo do +: agente vazio, .zip ou modelo |
| `fImportAgentZip` | `frontend/static/js/api.js` | Carregar em blocos, verificar, mostrar, confirmar, instalar, consultar |
| `fLoadExportPreview` | `frontend/static/js/agent_export.js` | O que cada opção de exportação acrescentaria, perguntado sempre que o separador abre |
| `fSource` | `backend/core/rag_search.py:88` | Um trecho tal como o modelo e as citações o veem: ref, localização, título, subtítulo, ano, autor, versão, idioma, texto, ligação |

### A barra lateral

| Símbolo | Ficheiro:linha | O que faz |
|---|---|---|
| `fRenderSidebar` | `frontend/static/js/api.js` | Reconstrói a lista de agentes. Chamado ao carregar a página e depois de uma criação ou eliminação, nunca por temporizador |
| `fPickDifferentModel` | `frontend/static/js/dashboard.js` | O modelo a preencher quando se escolhe um fornecedor. O de reserva evita o do principal: o mesmo fornecedor e o mesmo modelo falham pela mesma razão, sempre |
| `fSetAgentAvatarActivity` | `frontend/static/js/api.js` | Define `data-running` e a dica num avatar, e acrescenta ou remove o arco |
| `fBuildAgentActivityArc` | `frontend/static/js/api.js` | O retângulo arredondado em SVG colocado sobre o contorno, `pathLength="100"` para que a folha de estilos possa falar em percentagens do perímetro |
| `fRefreshAgentActivity` | `frontend/static/js/api.js` | A cada 5 s, volta a pintar apenas os anéis; não corre enquanto o separador está escondido |
| `fDescribeChannelName` / `fDescribeProviderName` | `frontend/static/js/api.js` | O nome com que um canal ou um fornecedor se escreve a si próprio. Não são chaves i18n: DeepSeek é DeepSeek em todos os idiomas |
| `fDescribeTool` / `fDescribeToolArgument` | `frontend/static/js/api.js` | O que uma ferramenta e os seus argumentos dizem, no idioma de quem lê. O esquema fica em inglês: é o que é enviado ao modelo |
| `fRenderToolCheckboxes` | `frontend/static/js/dashboard.js` | Uma caixa por família de ferramentas, construída a partir do que estiver instalado. Move o interruptor do kanban para a caixa do kanban em vez de o reconstruir, para que uma marca feita e ainda não guardada sobreviva ao redesenho |

### Mensagens pop-up

| Símbolo | Ficheiro:linha | O que faz |
|---|---|---|
| `fShowNotice` | `frontend/static/js/api.js` | Põe uma mensagem na camada sobre a coluna de conteúdo. Substitui o que lá estiver, por isso as confirmações nunca se empilham |
| `fShowError` | `frontend/static/js/api.js` | O mesmo, como erro: sem temporizador, fechado à mão |
| `fConfirmLogout` | `frontend/static/js/api.js` | Abre o `fConfirm` no centro do ecrã; só navega para `/logout` depois da confirmação. Cancelar e Escape mantêm a sessão aberta |
| `fHideNotice` | `frontend/static/js/api.js` | Faz desvanecer uma mensagem e remove-a depois, para que não desapareça de repente quando o temporizador se esgota |
| `fGetNoticeSeconds` / `fSetNoticeSeconds` | `frontend/static/js/api.js` | Quanto tempo uma mensagem fica, guardado neste navegador e limitado a 1–30 segundos |
| `fBuildCloseCross` | `frontend/static/js/api.js` | A cruz de fechar como duas linhas SVG. Um carácter `×` é centrado no eixo matemático do tipo de letra e não na sua própria caixa, por isso fica acima do meio do botão, faça o botão o que fizer |

### Realce de JSON

| Símbolo | Ficheiro:linha | O que faz |
|---|---|---|
| `cJsonTokenPattern` | `frontend/static/js/jsonhighlight.js` | Uma única expressão para os quatro tipos de token. Uma cadeia seguida de dois pontos é uma chave, que é a única coisa que distingue um nome de um valor |
| `fHighlightJsonElement` | `frontend/static/js/jsonhighlight.js` | Reconstrói um bloco como spans coloridos e texto simples. Cada carácter do original é emitido exatamente uma vez, por isso o bloco continua a copiar-se como JSON válido |

### Fornecedores

| Símbolo | Ficheiro:linha | O que faz |
|---|---|---|
| `BaseProvider.fSendMessages` | `backend/providers/base.py` | O único método que todos os adaptadores implementam |
| `fNeutralMessagesToOpenAiFormat` | `backend/providers/base.py` | Forma neutra → chat/completions |
| `fToolNameToWire` / `fToolNameFromWire` | `backend/providers/base.py` | `family.action` ↔ `family__action`, porque nenhum fornecedor aceita o ponto |
| `fDescribeHttpError` | `backend/providers/base.py` | Acrescenta a uma falha HTTP simples o que o fornecedor disse |
| `fBuildProvider` | `backend/providers/factory.py` | Configuração → instância do adaptador, com importação diferida |
| `fResolveProviderName` | `backend/providers/factory.py` | Segue os aliases, para que `gemini` e `google` cheguem a um só adaptador |
| `fSendChatCompletion` | `backend/providers/openai_dialect.py` | O pedido chat/completions partilhado, parametrizado pelas peculiaridades de cada adaptador |
| `fNormalizeMessageContent` | `backend/providers/openai_dialect.py` | Achata uma resposta cujo conteúdo chegou em blocos, descartando o raciocínio |

---

### Símbolos de áudio

| Símbolo | Ficheiro:linha | Responsabilidade |
|---|---|---|
| `fTranscribe` | `backend/core/audio_transcription.py:223` | Descodificar, segmentar e transcrever |
| `fEnqueueTelegram` | `backend/core/audio_inbox.py:57` | Persistir o destino antes da transcrição |
| `fRunOneJob` | `backend/core/audio_inbox.py:233` | Processar ou repetir um turno reservado |
| `fDownloadModel` | `backend/core/whisper_runtime.py:134` | Validar o tamanho e o SHA-256 antes da publicação |
| `fGetChatAudio` | `backend/web/api.py:571` | Servir o áudio depois das verificações da sessão e da referência de conversa |

### API Calls

| Símbolo | Ficheiro | Responsabilidade |
|---|---|---|
| `fRecordCall` | `backend/core/api_calls.py` | Persiste um corpo de saída completo antes do envio |
| `fReadBodyChunk` | `backend/core/api_calls.py` | Lê uma parte limitada de um ficheiro de agente validado |
| `fSelectConversationTab` | `frontend/static/js/dashboard.js` | Alterna entre Chat/API Calls e a respetiva consulta periódica |
| `fBeautifyJson` | `frontend/static/js/jsonhighlight.js` | Indenta JSON preservando os valores literais |

### Samba

| Símbolo | Ficheiro | Responsabilidade |
|---|---|---|
| `fProvisionAgent` / `fRemoveAgent` | `backend/core/samba.py` | Ciclo de vida da partilha/conta |
| `fSaveSettings` | `backend/core/samba.py` | Validar, guardar as credenciais e ativar as permissões |
| `fCheckShareDirectory` | `backend/core/samba.py` | Verificação da pasta e da propriedade no momento da ligação |
| `fBackup` / `fRestore` | `backend/core/samba.py` | Cópia de segurança e substituição coerentes das credenciais nativas |
| `fLoadSambaSettings` / `fCollectSambaSettings` | `frontend/static/js/samba.js` | Carregar e guardar sem expor palavras-passe nem descartar outras edições |

## 4. Fluxos principais

### Recuperação de documentos

Os instaladores limpam as antigas árvores RAG dos agentes restaurados antes de
extrair o instantâneo, para que ficheiros WAL do SQLite e gerações de vetores
obsoletos não sobrevivam a um restauro. As definições de execução são
restauradas sem substituir os pesos de modelo instalados.
Os workers despacham no máximo oito documentos, ou começam documentos novos
durante no máximo 90 segundos, por turno; os trabalhos por terminar continuam
duráveis. A resposta da biblioteca expõe as falhas de importação da caixa de
entrada. O OCR local instala as fontes Liberation para os PDF sem fontes
incorporadas. A compilação da vetorização desativa as transferências da
interface web pré-compilada.

Carregamento: `rag_api → exec_client.fRag → rag_exec → rag_worker` como o agente.
Indexação: `boa-rag → exec_daemon → rag_worker.fWork → rag_embeddings.fIsAvailable → extraction → local embeddings → publication`.
Falha do motor durante a indexação: `rag_embeddings.fRequest → EngineUnavailable → fIndexDocument → state queued, chunks kept → fWork ends the batch → next pass resumes at the first missing chunk`.
Transferência de modelo: `settings_rag.js → POST /api/admin/rag/models/<id>/install → exec_client.fInstallRagModel → exec_daemon.fVerbInstallRagModel → rag_runtime.fStartModelDownload → thread fInstallModel → status file ← GET /api/admin/rag (fDescribe) polled every 2 s`.
Mudança de modelo: `settings_rag.js (fConfirmModelChange) → PUT /api/admin/rag → rag_exec.fRuntime → fIsModelInstalled → fSaveRuntimeSettings → fFollowModelSimilarity → restart boa-embeddings → [each library] rag_worker.fWork → fFollowNewModel → fIsAvailable waits for the new alias → fIndexDocument(pModel) → fBuildIndex/fPublish (documents.model)`; entretanto, `fSearch → FTS5 only for the waiting documents → notice`.
Resposta: `AgentRun.fExecute → rag_search.fSearch → bounded passages → configured provider → verified citation links`.
Resposta documental e verificada: `model answers → fCheckRagAnswer (no rag.search yet → cRagSearchFirstPrompt, once) → rag.search → model answers → [verified] rag_verify.fVerify → unbacked units → fBuildCorrectionPrompt, once → model answers → fFinishRagAnswer (no passages → fixed sentence; verified → units removed + count, engine down → withheld) → fResolveCitations`.

### Guardar a memória e o seu limite

`dashboard.js:fSaveAgent` conta pontos de código Unicode e submete `memory` com
`info.limits.max_memory_characters`. `api.fCheckMemoryUpdate` valida contra o
limite proposto (ou lê o guardado) antes de qualquer escrita, por isso aumentar
o limite e guardar um texto mais longo funciona num único pedido. Devolve os
erros traduzidos `memoryTooLong` ou `memoryLimitInvalid` em caso de rejeição.
Depois, `fVerbWriteAgentInfo` persiste o limite e `fVerbWriteMemory` valida
antes de largar os privilégios. `memory.fWrite` volta a verificar a definição
protegida e substitui atomicamente o ficheiro sem o truncar. `memory.append` e
`memory.replace` usam a mesma verificação; o aviso começa acima de 75% do
limite. O formulário deixa disponível para edição o texto colado demasiado
grande.

Os orçamentos de transporte suportam o limite superior: 6 MiB por pedido ao
executor, verificados pelo cliente antes de ligar; 8 MiB por resposta; 4 MiB
por leitura do ficheiro de memória; 16 MiB por corpo HTTP, incluindo clientes
JSON que fazem escape de caracteres Unicode suplementares. Estes são limites
de transporte, não limites do contexto do modelo.

### Criar um agente

```
navegador  POST /api/admin/agents {name}
  web/api.fCreateAgent
    exec_client.fCreateAgent          → socket Unix /run/boa/exec.sock
      exec_daemon.ExecRequestHandler
        fGetPeerCredentials + fIsPeerAllowed    ← recusa todos menos root/boa
        fVerbCreateAgent
          agents.fValidateAgentName
          agents.fGetNextFreeAgentId            ← o mais baixo livre, a partir do sistema de ficheiros
          useradd --home-dir … --create-home
          agents.fWriteAgentInfo                 (0600, pertencente ao agente)
          fWriteAgentFile system-prompt.md        (0600)
          fWriteAgentFile api-token              (0600)
          chmod 0700 na pasta pessoal
          agents.fIndexAgent(…, vApiToken)       ← guarda apenas o SHA-256
        perante qualquer exceção: fRemoveAgentUser       ← nada de agentes criados a meio
```

### Criar um agente a partir de um modelo

```
navegador  GET /api/admin/agent-templates?language=es-ES
  agent_templates.fListTemplates
    fLoadTemplates → fDownloadArchive(<repo>/archive/refs/heads/<branch>.tar.gz)   em cache 5 min
      agent_package.fReadRepositoryArchive                   uma origem por pasta com agent.json
    agent_package.fReadPackage + fSummarise                  por modelo; uma falha aparece com o seu erro
navegador  POST /api/admin/agents {name, template, language}
  api.fCreateAgent
    agent_templates.fReadTemplate(template)                  o servidor volta a lê-lo
    agent_io.fInstallPackage
      exec_client.fCreateAgent(tools, skills, limits, pRag, pSchedules, pEnabled=False)
        exec_daemon.fVerbCreateAgent → agents.fValidateSchedule, de novo
      exec_client.fWriteAgentInfo / fWriteMemory / fAgentHome / fRag   quando o pacote os traz
      em caso de falha: exec_client.fDeleteAgent
```

### Importar um .zip

```
navegador  POST /api/admin/agent-imports {name, size}          → /opt/boa/imports/<id>/package.zip
navegador  PUT  /api/admin/agent-imports/<id>/upload {offset, data}   por ordem, 256 KiB cada
navegador  POST /api/admin/agent-imports/<id>/finish            ZipSource + fReadPackage → resumo
navegador  (mostra o resumo; o utilizador confirma e dá-lhe um nome)
navegador  POST /api/admin/agent-imports/<id>/install           → 202
  agent_io.fStartImport → install.lock (uma vez) → thread fRunImport
    fInstallPackage, a reportar step/done/total em job.json
navegador  GET  /api/admin/agent-imports/<id>                   a cada segundo até installed/failed
```

### Exportar um agente

```
navegador  GET /api/admin/agents/<id>/export/preview            tamanho da memória, ficheiros da pasta pessoal, biblioteca, modelo
navegador  GET /api/admin/agents/<id>/export?memory=1&home=1&provider=1&rag=1   uma ligação de transferência
  agent_io_api.fExport → primeiro bloco produzido antes dos cabeçalhos (os erros continuam em JSON)
    agent_io.fExportAgent
      fBuildManifest ← fReadAgentInfo, fReadCrontab → fReadSchedules
      memory.md ← fReadMemory
      home/... ← exec_client.fAgentHome(list, read) como o agente
      rag/files/... + rag/documents.json ← exec_client.fRag(list, content)
```

### Uma execução agendada

```
cron (o crontab próprio de agent-007)
  runner.py --agent-id 007            ← já a correr como agent-007
    fTakeRunLock                      ← recusado → fRecordRunRefused, e para
    AgentRun.__init__
      fReadOwnInfo / fReadOwnSystemPrompt / fReadOwnApiToken
      fBuildSystemPrompt              ← prompt + memória + índice de competências + idioma
      tool_registry.fLoadAllTools
      fSelectAllowedTools             ← ferramentas de kanban retidas se estiverem desligadas
    fExecute
      run_journal.fCountRunsOn        ← teto diário, a partir do seu próprio diário
      factory.fBuildProvider
      ciclo:
        fCheckCeilings                ← passos, tokens, segundos
        provider.fSendMessages        ← max_tokens encolhe à medida que o orçamento é gasto
        run_journal.fRecordUsage
        se não houver chamadas a ferramentas: parar
        fRunToolCalls                 ← todos os resultados devolvidos num só lote
      fAskForClosingAnswer            ← uma chamada sem ferramentas depois de um teto
                                        de passos ou de tokens, para que o trabalho já
                                        pago se transforme numa resposta
      run_journal.fRecordRunFinished  ← "stopped" quando um teto lhe pôs fim
```

### Um cartão vence

```
boa-buzzer (como boa), a cada 5 segundos
  kanban.fListDueCards              ← dono, run_at ultrapassado, sem toque, não feito
  fRingOne
    fBuildCardAnnouncement          ← assigned_by → nome, run_mode → imediato
    exec_client.fRunNow(prompt, only_if_idle, card)
      exec_daemon.fVerbRunNow                      ← como root
        fIsAgentRunning             ← ocupado: started=False, sem toque, tentar de novo
        fRunAsAgent → chat.fAppendCardMessage      ← anunciado, turno aberto
        Popen runner.py --prompt-on-stdin --turn-id …  ← como agent-007, com o prompt no seu stdin
    kanban.fMarkCardBuzzed          ← só depois de a execução arrancar
  runner.AgentRun (vWritesToChat, não vIsChat)
    fExecute                        ← prompt do cartão, sem conversa reenviada
    fRecordChatAnswer               ← resposta + custo fecham o turno
    fRecordChatFailure              ← ou o motivo por que nada correu
```

### Um agente move um cartão

```
o modelo pede kanban.move_card
  tool_registry.fRunTool              ← recusa se não tiver sido concedida a este agente
    tools/kanban_move_card.fRunTool
      agent_api_client.fCallFromContext   → /run/boa/agent.sock
        agent_api.AgentRequestHandler
          fAuthenticate               ← hash do token + SO_PEERCRED
          fVerbKanbanMoveCard
            fAgentMayUseKanban        ← do lado do servidor, lê info.json
            fRequireOwnCard           ← só criador ou destinatário
            kanban.fMoveCard          ← movimento + evento, uma transação
```

### Um agente envia uma mensagem

```
o modelo pede channel.write
  tools/channel_write.fRunTool
    agent_api_client → agent_api.fVerbChannelWrite
      fAgentMayUseChannel             ← ferramenta concedida E canal concedido
      channels.fSendMessage(prefix="[Agent name]")
        fReadChannelConfig            ← como boa; o agente nunca vê isto
        fSendToTelegram / Discord / Mattermost / X
```


### Chega uma mensagem do Telegram

```
boa-channel-telegram (como boa)
  fRefreshCommands                    ← /agents /status /help, quando mudam
  fDeliverAnswers                     ← tudo o que terminou desde a última passagem
    exec_client.fReadChat             ← a conversa está numa pasta pessoal 0700; só o root a lê
    channels.fSendToTelegram          ← "**name:**\n..." como resposta
    telegram_inbox.fRemovePending
  channels.fReadTelegramUpdates       ← long poll: 25s em repouso, 3s enquanto responde
    fIsFromTheConfiguredChat          ← tudo o resto é descartado, em silêncio
    callback_query -> fHandleCallback ← um toque num botão de agente
      fSelectAgent                    ← a partir daqui, as mensagens sem destinatário vão para ele
    message -> fHandleMessage
      fHandleCommand                  ← /agents /status /help, respondido e pronto
      fRouteMessage                   ← resposta, depois @nome, depois o selecionado
      exec_client.fSendChatMessage(source="telegram")
        exec_daemon.fVerbSendChatMessage
          chat.fAppendMessage(metadata={"source": "telegram"})
          Popen runner.py --chat-message-on-stdin --turn-id   ← a mensagem no seu stdin
      telegram_inbox.fAddPending      ← no disco: um reinício não pode perder a resposta
```

A resposta é enviada pelo listener e não pela execução, pela mesma razão pela
qual o anúncio do cartão é escrito pelo executor: a execução é o utilizador
próprio do agente, e as credenciais do canal pertencem a `boa`. A execução só
escreve na sua conversa; o listener lê-a e faz o envio.

### Chega uma mensagem do Discord

```
boa-channel-discord (como boa)
  fDeliverAnswers                     ← tudo o que terminou desde a última passagem
    exec_client.fReadChat             ← a conversa está numa pasta pessoal 0700; só o root a lê
    channels.fSendToDiscord           ← "**name:**\n…" como resposta, em partes de 2000 caracteres
      discord_markdown.fRenderToMessages
    discord_inbox.fRememberMessage    ← cada parte, para que responder a qualquer delas seja encaminhado
    discord_inbox.fRemovePending
  channels.fReadDiscordMessages       ← GET /channels/<id>/messages?after=<id>
    (invertido: o Discord responde do mais recente para o mais antigo)
    fHandleMessage
      author.bot, type                ← as suas próprias palavras, e tudo o que não seja uma mensagem
      fIsFromTheConfiguredChannel
      fReadCommand                    ← !agents !status !help, respondido e pronto
      fRouteMessage                   ← resposta, depois @nome, depois o selecionado
      exec_client.fSendChatMessage(source="discord")
      discord_inbox.fAddPending       ← no disco: um reinício não pode perder a resposta
  fWriteAfterId                       ← config/discord-after
```

A resposta é enviada pelo listener e não pela execução, pela mesma razão que a
do Telegram: a execução é o utilizador próprio do agente, e as credenciais do
canal pertencem a `boa`.

A primeira passagem de uma instalação nova pede a mensagem mais recente e
guarda apenas o seu id. Um canal vazio é marcado com o id mais baixo que
existe, para que a **primeira** mensagem que alguém escreva seja respondida em
vez de ser gasta a descobrir por onde começar.

### O bot não mostra nada a um estranho

O nome de utilizador de um bot é público: qualquer pessoa que o encontre pode
abrir um chat com ele. Por isso `fIsFromTheConfiguredChat` compara o `chat.id`
que o Telegram põe em cada mensagem - que o remetente não consegue
falsificar - com o configurado, e `fHandleMessage` descarta o que não coincide
antes de despachar um comando e antes de escolher um agente.
`fHandleCallback` faz o mesmo para um toque num botão. Nada é enviado de
volta: responder confirmaria a quem está a sondar que o bot está vivo. Também
nada é registado. O descarte costumava ficar registado com o id do chat de
onde vinha, o que são dados de outra pessoa e teria significado que esta
instalação ia acumulando discretamente uma lista de quem encontrou o bot. O
que resta é uma mensagem que nunca existiu.

O custo é real e vale a pena nomeá-lo: um `chat_id` mal configurado parece
agora exatamente um estranho, e as próprias mensagens do dono desaparecem em
silêncio. O id configurado é escrito no registo em cada arranque -
`Registered 3 command(s) for chat <id> only` - que é o número com que se deve
comparar. Uma mensagem do chat *configurado* que não chega a nenhum agente
continua a ser registada, porque aí o remetente é o dono e «escrevi-lhe e não
aconteceu nada» seria, de outra forma, impossível de distinguir de «nunca
chegou».

O que o filtro não cobre, nem pode cobrir, é *quem* dentro do chat: um
`chat_id` que nomeie um grupo é um grupo em que todos os membros podem falar
com os agentes.

O mesmo raciocínio decide onde é escrita a lista de comandos. `setMyCommands`
recebe um âmbito, e `default` e `all_private_chats` são resolvidos para todos
os utilizadores do Telegram - por isso uma lista escrita aí é um menu mostrado
a estranhos, com «Server status» lá dentro, a anunciar que há por trás disto
uma máquina em que vale a pena mexer. Nunca poderiam executar nada daquilo,
mas um letreiro numa porta trancada não deixa de ser um letreiro.
`fSetTelegramCommands` escreve a lista apenas no âmbito do chat configurado e
**apaga** os dois públicos em cada atualização: uma lista escrita por uma
versão mais antiga deste código continua do lado do Telegram até alguma coisa
a remover. `fHideTelegramPublicProfile` esvazia as outras duas cadeias
públicas, `setMyDescription` e `setMyShortDescription`, que são o que preenche
um chat vazio debaixo de «What can this bot do?».

O que continua visível é o nome do bot, a sua imagem e o botão Start, que o
Telegram desenha em todos os chats vazios com um bot e que nenhuma API
consegue remover. Carregar nele envia `/start`, que é descartado como
qualquer outra coisa vinda de outro chat.

### Porque é que o menu contém ferramentas e não agentes

O Telegram desenha `/name` ao lado de cada entrada do menu de comandos - essa
cadeia é a entrada, é o que fica escrito na caixa quando se toca nela, e
nenhuma API a esconde. Por isso um menu de agentes nunca poderia ser a lista
de agentes que alguém queria ver, e crescia com a lista de agentes sem dizer
nada sobre para que servia o bot.

O menu contém três coisas que o bot sabe fazer. Que agentes existem é uma
pergunta, e `/agents` responde-lhe com botões inline, em que um botão diz
`os-watcher` e mais nada, porque o texto de um botão é o bot que o escolhe.

O resto decorre disso:

- **O agente selecionado fica fixo.** Tocar num botão ou nomear um agente
  seleciona-o; tudo o que não tenha destinatário vai para ele até ser
  escolhido outro. Nomear o agente em cada linha está bem uma vez e cansa à
  quarta mensagem. Vive em `settings`, não em memória, porque o serviço
  reinicia em cada atualização.
- **Uma resposta continua a ganhar.** É inequívoca, e é o que faz quem tem um
  telemóvel na mão. Nada mais muda a seleção, por isso um agente nunca herda
  uma conversa por ser o que por acaso falou em último lugar.
- **Um agente eliminado deixa de estar selecionado.** `fReadSelectedAgent`
  verifica a lista de agentes à saída: não chegar a ninguém é melhor do que
  chegar a quem ficou com o seu id.
- **O bot fala o idioma da instalação.** Primeiro `agent_language`, a mesma
  definição em que os agentes respondem - as linhas dele aparecem na mesma
  conversa que as deles.

### A barra lateral mostra quem está a trabalhar

```
a cada 5 segundos, e logo depois de enviar / executar agora / chegar uma resposta
  api.js fRefreshAgentActivity        ← não corre enquanto o separador está escondido
    GET /api/admin/agents
      web/api.fListAgents
        exec_client.fListRunningAgents          → /run/boa/exec.sock
          exec_daemon.fVerbListRunningAgents
            fListRunningAgentIds      ← uma varredura de /proc, todos os agentes de uma vez
      cada agente leva `running`
    fSetAgentAvatarActivity           ← data-running no avatar; a própria lista
                                        nunca é reconstruída por temporizador
      fBuildAgentActivityArc          ← um retângulo arredondado SVG sobre o contorno
  o CSS anima o seu stroke-dashoffset ← a forma fica parada, o traço aceso percorre
                                        o contorno no sentido dos ponteiros do relógio
```

### Iniciar sessão

```
POST /login
  views.fLoginPage
    auth.fCountRecentFailures         ← 10 por 15 minutos por endereço
    auth.fVerifyCredentials           ← argon2id; um e-mail errado também calcula o hash
    auth.fRecordAttempt
    auth.fLogIn                       ← cookie de sessão, 12 horas
```

---

### Chega uma nota de voz

`fHandleMessage → fRouteMessage → fEnqueueTelegram → audio_jobs → fRunOneJob → fDownloadTelegram → fTranscribe → fSubmitTranscript → fSendChatMessageLocked → runner`. A resposta usa a entrega normal do Telegram; a conversa web acrescenta a transcrição e um leitor privado. Definições → Áudio usa GET/PUT `/api/admin/audio`; as transferências de modelos usam o RPC `install_whisper_model` e consultam o progresso sem bloquear o HTTP.

### API Calls

```text
AgentRun.fSendRecordedRequest → gravador de pedidos do BaseProvider → api_calls.fRecordCall
separador API Calls → GET /api/admin/agents/<id>/api-calls
  exec_client.fReadApiCalls → exec_daemon.fVerbReadApiCalls → api_calls.fReadCalls
expandir pedido → GET /api/admin/agents/<id>/api-calls/<call_id>
  exec_client.fReadApiCallBody → api_calls.fReadBodyChunk → texto JSON transmitido
  fBeautifyJson → fHighlightJsonElement → DOM seguro
```

### Samba

```text
create_agent → fIndexAgent → samba.fProvisionAgent → samba/ + [agent-xxx]
GET /agents/<id>/samba → read_samba → samba.fReadSettings
PUT /agents/<id>/samba → write_samba → samba.fSaveSettings
  validar → info protegido + testparm → smbpasswd (stdin) → reload/close-share
ligação SMB → preexec do root --check-share <id> → permissões do Samba → uid do agente
delete_agent → samba.fRemoveAgent → remover utilizador Linux, pasta pessoal e índice
--backup → tdbbackup + SID do servidor → samba-backup no arquivo
--restore → parar serviços → restaurar utilizadores/dados → substituir a passdb nativa → arrancar
```

## 5. Mapa de pontos de entrada e rotas

### HTTP

| Rota | Método | Handler | Ficheiro |
|---|---|---|---|
| `/api/admin/rag` | GET, PUT | `fRuntime` | `backend/web/rag_api.py` |
| `/api/admin/rag/models/<vModel>/install` | POST | `fInstallModel` | `backend/web/rag_api.py` |
| `/api/admin/agents/<id>/rag/...` | GET, POST, PUT, DELETE | `fOverview`, `fUpload`, `fUploadPart`, `fDocument`, `fContent`, `fImport`, `fSearch` | `backend/web/rag_api.py` |
| `/login` | GET, POST | `fLoginPage` | `backend/web/views.py` |
| `/logout` | GET, POST | `fLogoutPage` | `backend/web/views.py` |
| `/` | GET | `fDashboardPage` | `backend/web/views.py` |
| `/kanban/` | GET | `fKanbanPage` | `backend/web/views.py` |
| `/tools/` | GET | `fToolsPage` → `/settings/?tab=tools` (preserva `family` e `agent`) | `backend/web/views.py` |
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
| `/api/admin/agents` | GET, POST | `fListAgents` (leva sempre `running` por agente), `fCreateAgent` | `backend/web/api.py` |
| `/api/admin/agents?kanban=1` | GET | `fListAgents`, acrescenta `reads_kanban` por agente | `backend/web/api.py` |
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

Tudo o que é API vive em `/api/`. Tudo o que está em `/api/admin/` exige uma
sessão.

### Sockets Unix

| `/run/boa-web/web.sock` | `0750 boa:boa` | gunicorn | A própria aplicação. Só o `boa-proxy` lhe chega |

| Socket | Modo | Servidor | Verbos |
|---|---|---|---|
| `/run/boa/exec.sock` | `0660 root:boa` | `exec_daemon` | `ping`, `create_agent`, `delete_agent`, `read_agent_info`, `write_agent_info`, `read_system_prompt`, `write_system_prompt`, `read_crontab`, `write_crontab`, `run_now`, `list_running_agents`, `read_samba`, `write_samba`, `read_run_journal`, `read_api_calls`, `read_api_call_body`, `read_usage_summary`, `read_chat`, `read_chat_attachment`, `send_chat_message`, `clear_chat` |
| `/run/boa/agent.sock` | `0666` | `agent_api` | `who_am_i`, `kanban_add_card`, `kanban_move_card`, `kanban_delete_card`, `kanban_list_cards`, `channel_write`, `mail_read`, `mail_delete`, `mail_move`, `mail_forward` |

### Linha de comandos

| Comando | Ficheiro |
|---|---|
| `runner.py --agent-id NNN [--prompt … or --prompt-on-stdin] [--chat-message … or --chat-message-on-stdin] [--turn-id …] [--dry-run]` | `backend/core/runner.py` |
| `install-update-reinstall-debian.sh --install\|--update\|--reinstall\|--backup [file]\|--restore <file>` | `deploy/` |
| `install-update-reinstall-alpine.sh --install\|--update\|--reinstall\|--backup [file]\|--restore <file>` | `deploy/` |

---

## 6. Análise de impacto

O que se parte se alterar isto.

| Componente | Alterá-lo afeta |
|---|---|
| `paths.fNormalizeAgentId` | **Todos os caminhos do sistema.** É a única validação entre os dados do utilizador e um caminho do sistema de ficheiros. Enfraquecê-la transforma qualquer id de agente numa travessia de caminhos |
| Constantes de `paths.py` | Os quatro serviços, o instalador e as unidades systemd. Mudar `/opt/boa` significa reinstalar |
| `deploy/haproxy/boa.cfg` | Todos os pedidos. `accept-proxy` tem de corresponder ao que o HAProxy da máquina envia: com `send-proxy-v2` nesse backend é obrigatório, sem ele o bind recusa todas as ligações |
| bind de `backend/web/gunicorn.conf.py` | Tem de continuar a ser um socket Unix. Dar de novo ao gunicorn uma porta e um certificado reintroduz a falha do PROXY antes do TLS |
| `exec_protocol.lKnownVerbs` | A superfície privilegiada. Acrescentar um verbo acrescenta uma forma de o processo web pedir algo ao root. Cada acréscimo precisa do mesmo escrutínio que o primeiro |
| `exec_daemon.fRunPrivilegedCommand` | Todos os comandos privilegiados. Nunca usa uma shell; introduzir aí `shell=True` faria de cada nome de agente um ponto de injeção |
| `agent_api.fAuthenticate` | Todos os pedidos dos agentes ao quadro e aos canais. As duas verificações têm de ficar |
| `db.cAppSchema` / `cKanbanSchema` | As instalações existentes. Não há sistema de migrações: os esquemas usam `IF NOT EXISTS`, por isso **as colunas novas precisam de código de migração explícito**, não de uma edição do esquema |
| `agent_scripts.cMinimumMinuteStep` | Com que frequência um agente se pode agendar a si próprio. É a única coisa entre um horário descuidado e um ciclo com uma linha de cron à frente |
| `paths.lProtectedAgentFiles` | Que ficheiros passam para a gaveta pertencente ao root. A migração do instalador e o daemon que cria um agente leem-na ambos, por isso não podem discordar sobre quais são |
| `agents.fBuildAgentInfo` | Só os agentes novos. Os ficheiros `info.json` existentes não são tocados, por isso os campos novos precisam de um caminho de leitura com predefinição |
| `exec_daemon.fVerbWriteAgentInfo` | **Todos os campos de `info.json` que sobrevivem a uma gravação.** Reconstrói o ficheiro chave a chave, por isso um campo que não nomeie é um campo que a interface descarta em silêncio da primeira vez que alguém carrega em Guardar. As listas são lidas através de `fReadNameList`, que distingue uma chave ausente («não mexer nisto») de uma lista vazia («retirar todas»): lido com `or`, desmarcar a última ferramenta repunha a lista anterior |
| `skills.fSelectInstalledSkills` | O que chega a um prompt e o que `skill.read` abrirá. Tanto o índice como a ferramenta filtram através dela, por isso uma competência apagada do servidor deixa de ser mencionada em vez de ser prometida e depois falhar |
| Forma neutra de `providers.base` | Todos os adaptadores e o runner |
| Interface de `tool_registry` | Todas as ferramentas em `/opt/boa/tools/`, incluindo as que o utilizador escreveu |
| `telegram_listener.fIsFromTheConfiguredChat` | Quem pode falar com os seus agentes. O nome de utilizador de um bot é público, por isso esta verificação é toda a autorização: enfraquecê-la deixa quem quer que encontre o bot arrancar execuções no seu servidor |
| Assinatura de `channels.fSendMessage` | Todos os chamadores, e os dois senders que recebem dois argumentos. `pReplyToMessageId` é passado ao Telegram e ao Discord, que são os dois canais através dos quais uma pessoa pode responder |
| `discord_markdown.cMaxDiscordLength` | Se a resposta de um agente chega de todo. O Discord recusa um `content` com mais de 2000 caracteres, e recusar é o que faz - não truncar |
| `agent_routing.fMatchNamedAgent` | A quem chega uma mensagem, **nos dois** listeners. A correspondência mais longa é o que faz de `@News` e `@News Miner` dois agentes |
| `agent_routing.fBuildStatusReport` | O que /status responde em ambos. Um único relatório, para que os dois não possam discordar sobre quantos serviços há |
| `discord_listener.fIsFromTheConfiguredChannel` | Que canal os agentes escutam. Ao contrário do Telegram, não há segunda verificação sobre quem está a falar: quem pode escrever nesse canal pode arrancar execuções |
| `kanban.lStates` | O quadro, a API, o frontend e o prompt de todos os agentes |
| Forma das entradas de `run_journal` | Tanto o escritor (runner) como os leitores (daemon, web). As linhas antigas ficam nos diários: os leitores têm de tolerar campos em falta |
| `samba` | O ciclo de vida dos agentes, a API privilegiada, os clientes SMB e a cópia de segurança/restauro dos dois instaladores. Mantenha intactos a guarda da pasta, a derivação de nome/caminho e o tratamento dos segredos |
| Um ficheiro que o daemon lê da pasta pessoal de um agente (`runs.jsonl`, `chat.jsonl`, `memory.md`) | Lido apenas através de `paths.fReadAgentOwnedFile`. Um ficheiro novo que o daemon leia de uma pasta pessoal também tem de passar por aí, ou o root lê aquilo para que o agente o apontar - um FIFO que nunca responde, uma ligação para qualquer ficheiro da máquina |
| O que contém uma cópia de segurança (a linha `tar` de `fDoBackup`) | Estado novo debaixo de `/opt/boa/` que seja da instalação e não do código tem de ser acrescentado aí, ou um restauro numa máquina nova perde-o |
| Os limites de kernel de uma execução (`runner.cMaxProcesses`, `exec_daemon.cRunTasksMax`, `cRunMemoryMax`) | Uma ferramenta que precise de mais de 1024 tarefas ou de 2 GiB tem de os subir; um navegador já são algumas centenas de threads |
| `runner.py` como caminho | Todas as execuções agendadas. O cron arranca-o pelo caminho, quase sem ambiente, por isso o runner põe a sua própria raiz no sys.path: sem isso, `import backend` falha e o traceback vai para o correio do cron, que numa máquina de LAN não vai para lado nenhum |
| `runner.dAnswerLanguageLines` | A linha acrescentada a um prompt de sistema que diz ao agente em que idioma responder. Escrita NESSE idioma, e diz que se sobrepõe à regra do próprio prompt - uma preferência ao lado de uma regra perde, está medido |
| `agent_api.fFilterCardsForAgent` | O que um agente pode saber que existe. Todas as leituras do quadro passam por aqui, e o orquestrador é a única exceção. Filtrar na ferramenta em vez disso poria uma regra de segurança numa descrição da qual o modelo pode ser dissuadido |
| De que lado fica um balão da conversa | Quem está a falar. Um cartão é o que se pediu ao agente, por isso vai para a direita com as mensagens do utilizador; o relatório de uma execução agendada é o agente a falar, por isso fica à esquerda |
| `chat.lToolsWorthReporting` | Que ferramentas fazem com que valha a pena pôr uma execução agendada na conversa. Tudo o resto fica no diário: de outra forma, um agente horário publicaria vinte e quatro mensagens «nada a reportar» por dia |
| `chat.lAskingRoles` | Que papéis esperam por uma resposta. Um papel que abre um turno e não está listado deixa a caixa de escrita aberta enquanto o agente trabalha; um que esteja listado mas nunca seja fechado fecha a caixa de escrita para sempre |
| `kanban.cRunNow` | A palavra que o navegador, os agentes e a API enviam em vez de uma marca temporal. Transformá-la numa hora noutro sítio que não `fValidateRunAt` perde `run_mode` e, com ele, a diferença entre «agora» e um momento escolhido |
| `chat.cReplayedTurns` | O que custa cada mensagem da conversa. Cada turno reenviado volta a ser pago na mensagem seguinte, por isso aumentá-lo torna as conversas longas progressivamente mais caras |
| `lTextColours` em `TestThemes` | Que cores o teste de contraste mede. Uma cor pintada como texto e deixada fora dessa lista é uma cor que nada verifica |
| Um atributo `style=` em qualquer template | Nada: `style-src` é `'self'` sem `unsafe-inline`, por isso o navegador deita-o fora. Há um teste que falha se aparecer um |
| `.notice-layer` em `app.css` | Onde aparecem todas as confirmações e todos os erros da aplicação. `position: fixed` sustenta peso: `absolute` centra no documento em vez de no ecrã, que é o bug que a camada existe para corrigir |
| Cadeia `.app:has(#vChatPanel…)` e `--status-bar-live-height` em `app.css` | Se a caixa de texto da conversa fica acima da barra de estado. Um bloco nessa coluna flex sem `min-height: 0`, ou uma altura de `.chat` que deixe de subtrair a altura viva da barra, deixa a página voltar a fazer scroll e põe a caixa de escrita debaixo da barra |
| `agents.fValidateSchedule` | Se um horário vindo de um `.zip` ou de um modelo pode tornar-se um comando num crontab escrito como root. Afrouxá-la (um espaço, um `#`, uma quebra de linha) transforma uma importação em execução de código |
| `agent_home.sExcludedTopNames` / `fIsExcluded` | O que uma exportação pode deixar escapar e uma importação pode plantar: sessões do navegador, `.ssh`, a conversa. Remover um nome deixa-o passar nas duas direções |
| `agent_package.lManifestKeys` / `cFormatVersion` | Todos os `.zip` exportados e todos os modelos de todos os repositórios. Uma chave nova precisa desta versão para ser lida; um significado alterado precisa de um número de formato novo |
| `min_support` em `rag_models.json` | Que parágrafos de uma resposta verificada sobrevivem, para esse modelo. Subido, começam a cair parágrafos fiéis; descido, passa uma citação a um trecho sem relação. O que cada valor dos dois modelos remove e deixa passar está na tabela ao lado da verificação em `rag_verify.py`: volte a medir com documentos reais antes de mexer num valor, e atualize a tabela |
| `sha256` ou `dimensions` de um modelo em `rag_models.json` | Todas as bibliotecas indexadas com ele. Uma impressão digital nova é um espaço vetorial novo: cada biblioteca volta a indexar todos os seus documentos na passagem seguinte (`fFollowNewModel`), o que numa biblioteca grande leva horas |
| `rag_embeddings.fCheckServedModel` / o `--alias` em `rag_runtime.fServe` | Se um vetor pode vir de um modelo diferente do que a sua biblioteca regista. Sem eles, um trabalho que atravesse uma mudança de modelo guarda vetores de dois modelos numa só revisão |
| `runner.lRagModesThatSearch` / `fFinishRagAnswer` | Se uma execução documental ou verificada pode entregar texto vindo dos próprios pesos do modelo. Retirar um modo da lista, ou a verificação de ausência de trechos, traz de volta respostas sem recuperação por trás |
| `rag_search.fSource` | Tudo o que é dito ao modelo sobre um trecho e aquilo para que uma citação aponta: o bloco do prompt pré-recuperado, `rag.search`, `rag.read` e `fResolveCitations` usam-no todos. Um campo que lhe seja acrescentado também precisa da sua coluna nos três `SELECT` que o alimentam |
| `rag_embeddings.EngineUnavailable` | Se uma falha de indexação mantém ou deita fora trabalho. Lançar um `ValueError` simples numa falha do motor põe o documento em `error` e apaga os seus fragmentos vetorizados; lançar `EngineUnavailable` numa recusa permanente deixa o documento na fila para sempre |
| `rag_store.cSchema` | Só os catálogos criados depois da alteração. Todas as bibliotecas de agentes existentes, e todas as cópias de segurança restauradas, mantêm a tabela antiga: uma coluna nova também precisa da sua entrada em `rag_store.lAddedColumns`, que `fMigrate` aplica |
| `frontend/static/i18n/en-US.json` | Acrescentar uma chave significa acrescentá-la aos outros catorze, ou essa cadeia recai no inglês. `TestTranslations` falha perante uma chave em falta, um `{placeholder}` perdido e um caminho ou nome de ferramenta traduzido |

---

## 7. Pontos de extensão

### Um fornecedor novo

1. Escreva `backend/providers/<name>.py` com uma classe que estenda
   `base.BaseProvider`, definindo `cProviderName`, `cDefaultModel`,
   `cDefaultBaseUrl` e implementando `fSendMessages`.
2. Acrescente uma linha a `factory.dProviderRegistry`.
3. Acrescente o nome a `agents.lSupportedProviders`.
4. Se não precisar de chave, acrescente-o a `factory.lSelfHostedProviders`.
5. As opções extra (como o `thinking` do DeepSeek) vão em `lExtraConfigKeys`;
   a fábrica mapeia automaticamente `reasoning_effort` → `pReasoningEffort`.

Não o junte a um adaptador existente só porque o dialeto coincide. Um ficheiro
por fornecedor é deliberado.

### Uma ferramenta nova

Crie um `.py` em `/opt/boa/tools/` que declare:

```python
cToolName = "namespace.verb"
cToolDescription = "What the model is told it does."
dToolSchema = {"type": "object", "properties": {...}, "required": [...]}

def fRunTool(pArguments, pContext):
  return "text the model sees"
```

Corre como o agente que a chama. Se precisar de algo a que os agentes não
podem chegar, acrescente antes um verbo à API dos agentes e chame-o através de
`agent_api_client`.

O ficheiro tem de pertencer ao root: a aplicação importa-o como código.

### Uma competência nova

Crie um diretório em `/opt/boa/skills/` com um `SKILL.md` lá dentro:

```markdown
---
name: BackupVerification
description: One line. This is what every run pays for.
---

The procedure, at whatever length it needs.
```

Nada para registar e sem reinício: `fListSkills` lê o diretório, por isso a
competência aparece na interface no próximo carregamento da página. Marque-a
num agente, dê a esse agente `skill.read`, e ela fica no seu prompt na próxima
execução.

Tudo o resto que estiver no diretório acompanha a competência. É legível por
todos, por isso a competência pode dizer «executa `verify.sh` neste diretório»
e o agente consegue.

O nome é o nome do diretório: letras, algarismos e hífenes, a começar por uma
letra. O `name:` no cabeçalho é o que uma pessoa vê na lista; o nome do
diretório é o que um agente pede.

### Uma operação privilegiada nova

1. Acrescente a constante do verbo a `exec_protocol` e a `lKnownVerbs`.
2. Escreva `fVerb<Name>` em `exec_daemon` e acrescente-o a `dVerbHandlers`.
3. Acrescente um wrapper em `exec_client`.

Valide cada argumento antes de chegar a um caminho ou a uma linha de comandos,
e mantenha o verbo específico. Um verbo suficientemente genérico para ser
reutilizável é normalmente um verbo suficientemente genérico para ser
abusado.

### Um canal novo

Só envio:

1. Escreva `fSendTo<Name>` em `channels.py`.
2. Acrescente-o a `lChannels` e a `dChannelSenders`.
3. Acrescente os seus campos a `dChannelFields` em
   `frontend/static/js/settings.js`, e os que forem credenciais a
   `lSecretChannelFields` aí e a `lSecretConfigFields` em `channels.py`.

Também receção, que é o que faz dele uma conversa:

4. Escreva `fRead<Name>Messages` em `channels.py`, devolvendo as mensagens da
   mais antiga para a mais recente.
5. Escreva `<name>_inbox.py`: duas tabelas em `db.cAppSchema` e o agente
   selecionado numa definição.
6. Escreva `<name>_listener.py` sobre `agent_routing`, que já contém a lista
   de agentes, a correspondência de nomes, a resposta fechada e o relatório de
   estado. O que resta é o protocolo.
7. Escreva `<name>_texts.py` para as frases que esse canal diz de forma
   diferente, recaindo em `telegram_texts` para o resto.
8. `deploy/systemd/boa-channel-<name>.service` e um serviço em
   `deploy/openrc/`, o nome
   em `lServices` e nos sete sítios em que o instalador de Debian nomeia as
   suas unidades, e em `system_info.lBoaServiceNames`. Se o seu nome em OpenRC
   for diferente, acrescente o mapeamento em `system_info.dOpenRcServiceNames`.
9. O seu interruptor em `dChannelSwitches`, a sua chave `chat.source<Name>`
   nos quinze catálogos, e `<name>` em `exec_daemon.lKnownChatSources`.

### Um idioma novo

Vêm quinze: `de-DE`, `en-GB`, `en-US`, `es-AR`, `es-ES`, `fr-FR`, `he-IL`,
`hi-IN`, `it-IT`, `ja-JP`, `ko-KR`, `pt-BR`, `pt-PT`, `ru-RU`, `zh-CN`. Um
décimo sexto são sete sítios, e os testes nomeiam todos eles:

1. Copie `frontend/static/i18n/en-US.json` e traduza os valores.
2. Acrescente a etiqueta a `lSupportedLanguages` em `frontend/static/js/i18n.js`.
3. Acrescente uma `<option>` aos três seletores: dois em
   `frontend/templates/settings.html`, um em `login.html`, por etiqueta.
4. Acrescente uma linha a `runner.dAnswerLanguageLines`, escrita NESSE idioma.
5. Acrescente um bloco a `telegram_texts.dTexts` e a sua etiqueta ao
   `lSupportedLanguages` desse módulo, ou o bot recai no inglês. Acrescente
   também um a `discord_texts.dTexts`: contém as três frases que o Discord diz
   de forma diferente, e um idioma que lá falte recebe essas três em inglês.
6. Traduza a documentação a partir dos ficheiros en-US: `README.<tag>.md` na
   raiz, `doc/CODE.<tag>.md` e `doc/MANUAL.<tag>.md`. Acrescente o idioma à
   linha de idiomas no topo de cada README, por ordem alfabética da etiqueta.
   O en-US é a fonte de todos os outros idiomas e mantém os nomes sem
   etiqueta: `README.md`, `doc/CODE.md`, `doc/MANUAL.md`.
7. Se for escrito da direita para a esquerda, acrescente a sua etiqueta a
   `lRightToLeftLanguages` em `frontend/static/js/i18n.js`. Mais nada: a
   folha de estilos já usa propriedades lógicas (ver «Da direita para a
   esquerda» acima).

`TestTranslations` em `tests/test_web.py` falha perante uma chave em falta,
uma a mais, uma cadeia vazia, um `{placeholder}` perdido, um caminho ou nome
de ferramenta traduzido, um ficheiro não ordenado, um seletor que não ofereça
o idioma, uma linha de prompt em falta e um bloco do Telegram em falta. Os
seis idiomas não latinos são também verificados quanto a estarem de facto
escritos na sua própria escrita, porque um ficheiro de cadeias em inglês sob
um nome russo passa em todas as outras verificações.
`TestExampleAgents` em `tests/test_tools.py` falha perante um idioma sem o seu
README, CODE ou MANUAL, ou um README que não tenha ligação para o README de
todos os outros idiomas; `TestTheCodeDocumentsPointAtRealLines` em
`tests/test_web.py` falha perante um CODE cujas referências `file.py:line`
difiram das do inglês.

O que uma tradução pode alterar: um nome de ficheiro que o texto em inglês dê
como EXEMPLO, como `check-disk.sh`. Nada procura esses.

### Um modo de resposta RAG novo

1. Acrescente-o aos modos permitidos em `rag_settings.fValidateSettings` e ao
   enum `mode` em `backend/web/rag_api_doc.py`.
2. Dê-lhe a sua regra em `rag_search.fPrompt`, dizendo o que o runner impõe.
3. Em `runner.py`, acrescente-o a `lRagModesThatSearch` se o modelo tiver de
   pesquisar, e a `fCheckRagAnswer` / `fFinishRagAnswer` se as suas respostas
   forem verificadas.
4. Uma `<option>` em `frontend/templates/agent_rag.html`, o seu texto de
   recurso em `dRagModeHints` em `rag.js`, e `rag.<mode>` mais
   `rag.modeHint.<mode>` nos quinze ficheiros i18n.
5. Testes em `tests/test_rag.py` (`TestRagInAgentRun`), com o fornecedor com
   guião e um `rag_embeddings.fEmbed` falso.

### Um modelo de vetorização novo

1. Uma entrada em `backend/core/rag_models.json`: o URL do GGUF fixado num
   commit (nunca num ramo), `size` e `sha256` a partir da API do repositório,
   `dimensions`, `context`, o `pooling` que o seu model card pede, e os seus
   prefixos de consulta e de trecho. `TestEmbeddingModelChoice` verifica que a
   entrada está completa.
2. Corra-o ao lado do motor instalado sobre a biblioteca de teste e meça-o da
   forma como a aplicação o usa (o comentário por cima da tabela em
   `rag_verify.py` diz como): o seu `min_support` é o valor mais alto que
   deixa passar menos de 1% de citações a trechos de outro tema, o seu
   `min_similarity` fica entre perguntas relacionadas e não relacionadas.
   Acrescente as suas linhas a essa tabela.
3. O seu pico de memória tem de caber no `MemoryMax` de
   `deploy/systemd/boa-embeddings.service`; escreva-o, e quanto mais lento é a
   indexar do que o EmbeddingGemma, como `memory_mb` e
   `relative_indexing_time`.
4. A lista em Definições → RAG e a rota de transferência vêm do catálogo; só
   as tabelas em `doc/MANUAL*.md` e as descrições do enum em
   `rag_api_doc.py` precisam do novo modelo pelo nome.

### Um campo novo de informações do documento

1. Acrescente a coluna a `rag_store.cSchema` e a `rag_store.lAddedColumns`, ou
   as bibliotecas existentes não a terão.
2. Acrescente a chave, no seu lugar, a `rag_store.lMetadataKeys`, e qualquer
   verificação de formato de que precise a `rag_store.fAction`.
3. Se o modelo a dever ver, acrescente `d.<column>` aos três `SELECT` em
   `rag_search` e o campo a `rag_search.fSource`.
4. Acrescente-a ao esquema `metadata` em `backend/web/rag_api_doc.py`.
5. Acrescente-a, no seu lugar, à lista de campos em `frontend/static/js/rag.js`.
6. Acrescente `rag.<key>` aos quinze ficheiros `frontend/static/i18n/*.json`.
7. Cubra-a em `tests/test_rag.py`; o teste de migração já constrói um
   catálogo sem todas as colunas de `lAddedColumns`.

### Um modelo de agente novo

Os modelos vivem no repositório de modelos, não aqui:

1. Uma pasta `<name>/` em `bunch-of-aigents-templates`, com o mesmo nome que o
   `name` do modelo (`^[a-z][a-z0-9-]{0,39}$`).
2. `agent.json`: `format` 1, `name`, `description` nos quinze idiomas,
   `tools`, `schedules`, `limits` e, se precisar da sua biblioteca, `rag`. A
   forma mais rápida é construir o agente aqui, exportá-lo e descompactá-lo
   lá.
3. `system-prompt.md`, em inglês, a terminar com a regra sobre o idioma da
   resposta.
4. `README.md`, em en-US, para quem lê esse repositório: para que serve o
   agente, o que faz, de que precisa primeiro, o que não fará, com o que vem e
   como instalá-lo. A aplicação ignora-o.
5. Corra os testes deste repositório: `TestExampleAgents` lê o clone ao lado
   deste com `agent_package` e falha perante um modelo que a aplicação
   recusaria, uma ferramenta que não existe, um idioma em falta, ou um README
   que falte ou que não nomeie as ferramentas e os horários do modelo.
6. Uma linha na tabela de modelos de cada MANUAL daqui, um por idioma, e uma
   com ligação para o seu README nos três README de lá.

### Uma página nova

1. Uma rota em `backend/web/views.py` que devolva `render_template`.
2. Um template que estenda `app_base.html`.
3. Um `<li>` no `nav` de `app_base.html`.
4. O seu próprio JS em `frontend/static/js/`, a começar por
   `await fWaitForTranslations()` antes de apresentar o que quer que seja.
