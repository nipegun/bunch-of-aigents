# CODE.md

Referência técnica do Bunch of AIgents. Escrita para ser consultada de forma
cirúrgica: vá direto à seção de que você precisa, não a leia de ponta a ponta.

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

Esta é a parte que não dá para deduzir do código, então é a parte que vale a
pena ler.

### A premissa

Aqui, um agente é um modelo de linguagem com um shell em um servidor, acordado
pelo cron, sem ninguém olhando. Toda decisão estrutural decorre de levar isso a
sério: mais cedo ou mais tarde o modelo vai fazer algo não pretendido, então a
pergunta não é como impedir isso, e sim o que ele consegue alcançar quando
acontecer.

### Um usuário Linux por agente

O agente `007` é o usuário de sistema `agent-007`, dono de `/opt/boa/agents/007/`
com modo `0700`. O isolamento entre agentes é feito pelo kernel, não por uma
sandbox escrita em Python. Um agente não consegue ler o prompt de sistema, o
diário nem a chave de API de outro agente porque o sistema de arquivos não
deixa.

O próprio `/opt/boa/agents/` é `root:root 0711`: dá para atravessá-lo, não para
listá-lo. Um agente não consegue enumerar os outros agentes, só falhar ao abrir
caminhos que ele adivinha.

É por causa dessa decisão que `bash.run` não precisa de lista de permissões. Uma
lista de bloqueio num shell é teatro — qualquer coisa que consiga rodar `sh`
consegue rodar o que quer que a lista cite —, enquanto uma conta de usuário é
uma fronteira que o kernel faz valer.

### O que um agente não pode reescrever sobre si mesmo

O diretório pessoal é do próprio agente, 0700, e é essa a ideia: a memória dele,
o diário, a conversa e qualquer script que ele escreva ficam ali. Três dos seus
arquivos não cabe a ele mudar, e esses ficam FORA do diretório pessoal, em
`/opt/boa/agents-config/xxx/`, que é `root:agent-xxx 0750` sob um pai
`root:root 0711`.

| Arquivo | Por que não é do agente |
|---|---|
| `info.json` | Quais ferramentas lhe foram concedidas e quanto ele pode gastar |
| `system-prompt.md` | A definição do que ele deve fazer |
| `api-token` | Com o que ele se identifica perante a API dos agentes |

O que faz isso funcionar não é o dono dos arquivos: é o dono do diretório. É a
permissão de escrita num diretório que decide se um arquivo dentro dele pode ser
apagado e substituído, então um agente que fosse dono do diretório poderia
apagar `info.json` e escrever o seu próprio, fosse quem fosse o dono do arquivo.
Neste ele pode entrar e ler, e não pode criar, renomear nem apagar nada.

**E essa regra vale tanto para a gaveta quanto para o que está nela**, e é por
isso que esses arquivos não ficam mais em `agents/xxx/config/`. Aquele caminho
era uma entrada no DIRETÓRIO PESSOAL, o diretório pessoal é do agente com 0700,
e renomear uma entrada exige permissão de escrita no pai e nada mais - o modo da
coisa que está sendo renomeada nunca é consultado. Então o agente não conseguia
editar `info.json` e conseguia fazer isto:

    mv ~/config ~/config-old && mkdir ~/config && echo '...' > ~/config/info.json

e passar a ser lido a partir do substituto. Tirar a gaveta do diretório pessoal
coloca todos os diretórios do caminho sob o root. Disso decorrem duas coisas:

  - **Não existe mais fallback para o diretório pessoal.** Existia um, para que
    uma atualização não fosse um serviço que parava de responder antes de a
    migração rodar - e ele mesmo era uma brecha, já que esconder o arquivo real
    bastava para que fosse lido o do próprio agente no lugar. Agora o daemon
    migra na inicialização, além de o instalador fazer isso, então não sobra
    nada a cobrir.
  - **Excluir um agente exclui também a configuração dele.** Ela não fica mais
    dentro do diretório pessoal que `userdel --remove` leva embora e, se
    ficasse para trás, seria entregue ao próximo agente que recebesse aquele
    id.

`fOpenProtectedAgentFile` é a segunda resposta à mesma pergunta: abre com
`O_NOFOLLOW` e verifica no ARQUIVO ABERTO que se trata de um arquivo regular, de
propriedade do root e que ninguém mais pode escrever. É isso que sobrevive a um
chmod errado durante uma atualização ou a uma restauração de um backup com o
dono errado.

Isso foi medido antes de ser corrigido, numa instalação real: um agente
acrescentou `mail.read` ao próprio `info.json` e o daemon privilegiado passou a
informar a ferramenta como concedida - ou seja, um agente podia conceder a si
mesmo a caixa de correio, os canais, ou aumentar os próprios tetos. Também podia
substituir o próprio prompt por “ignore todas as suas regras”, que teria ficado
assim em todas as execuções dali em diante.

O isolamento entre agentes não precisa de nada disso: `/opt/boa/agents/` é
`root:root 0711` e cada diretório pessoal é 0700, então o kernel já recusa. É
por isso que ele se mantém mesmo quando uma ferramenta tem um bug.

### O que o root lê do diretório pessoal

O diário, a memória e o chat são arquivos do próprio agente: escritos pelos
processos dele, no diretório pessoal dele com 0700, e lidos pelo daemon
privilegiado como root - que lê aquilo para onde for apontado. Medido no código
antes de isto existir: um FIFO chamado `runs.jsonl` prendia para sempre a thread
do daemon que o abria e, como a lista de agentes lê o diário de todos os
agentes, cada pedido posterior dessa lista vazava mais uma thread; um link
chamado `memory.md` apontando para qualquer arquivo da máquina fazia o root
entregar o texto desse arquivo à interface; e um link para algo sem fim fazia o
root ler até ser morto.

Por isso os três são lidos com `fReadAgentOwnedFile`, que é o irmão de
`fOpenProtectedAgentFile` para os arquivos que SÃO do agente: `O_NOFOLLOW`
recusa um link já na abertura, `O_NONBLOCK` impede que um FIFO prenda a
abertura até alguém escrever nele, e as verificações são feitas sobre o
descritor aberto - um arquivo regular, de propriedade do usuário do agente -,
de modo que nada pode ser trocado entre a verificação e a leitura. Ele nunca lê
mais do que um limite, aplicado ao que é lido e não só ao que `fstat` disse,
porque o agente pode acrescentar dados enquanto a leitura acontece: 32 MB para o
diário e para o chat, lidos a partir do FIM quando o arquivo é maior, já que as
linhas mais novas são o que um histórico mostra; 4 MiB para a memória, o
bastante para o máximo dela, de um milhão de caracteres UTF-8. Só os arquivos
escritos de fora que excedem esse orçamento de leitura recebem `[truncated]`;
`fWrite` rejeita conteúdo grande demais antes de substituir qualquer coisa. Um
byte ruim custa uma linha, não a leitura.

O que é recusado é dito, não engolido: `read_run_journal`, `read_chat` e
`read_memory` falham com o motivo, para que um operador fique sabendo que algo
naquele diretório pessoal não é o que a aplicação escreveu. A única exceção é
`read_usage_summary` para todos os agentes, de onde a barra lateral é
desenhada: ali, um diário ilegível custa àquele agente os totais dele, com o
motivo ao lado, e a mais ninguém os seus.

### O que viaja na linha de comando

O daemon inicia uma execução como o agente com `Popen`, e a mensagem que o dono
digitou - ou o prompt que um cartão vencido monta - costumava ser um dos
argumentos: `--chat-message <text>`, `--prompt <text>`. A linha de comando de um
processo pode ser lida por qualquer usuário da máquina em
`/proc/<pid>/cmdline`, e um agente com `bash.run` é um usuário da máquina.
Medido na máquina Debian de testes: `ps` rodado como `agent-001` mostrou a
mensagem que o dono tinha acabado de mandar para `agent-000`, enquanto aquela
execução durou, o que por padrão chega a até cinco minutos.

Por isso o texto desce pela entrada padrão do filho e a linha de comando leva só
`--chat-message-on-stdin` ou `--prompt-on-stdin`. `fStartRunner` é o único lugar
que inicia um runner: recusa um texto maior que `cMaxStdinPayloadBytes` antes de
existir qualquer processo, porque esse limite fica abaixo do buffer de 64 KiB de
um pipe e uma escrita que cabe no buffer nunca espera pelo filho - este daemon
não espera por runners. Um filho que já tinha ido embora quando a escrita
acontece, um interpretador que falha na importação, é um pipe quebrado e não uma
falha do daemon. Do outro lado, o runner lê o texto com o mesmo limite, recusa
uma mensagem de chat vazia em vez de responder a uma pergunta que ninguém fez e,
quando recusa, fecha o turno para o qual foi iniciado, para que a conversa não
fique esperando para sempre. `--prompt` e `--chat-message` continuam existindo,
para uma execução iniciada à mão a partir de um terminal.

### O que uma execução pode fazer com a máquina

Os tetos em `info.json` - tokens, passos, segundos, execuções por dia - são
aplicados pelo runner, e o runner é um programa que o agente está conduzindo. O
que se mantém quando o próprio programa é o que deu errado é aplicado pelo
kernel, em duas camadas.

O runner reduz os próprios limites de recursos antes de fazer qualquer outra
coisa, `fApplyResourceLimits`, a partir do ponto de entrada e não de `fMain` -
os testes chamam `fMain` dentro do mesmo processo, e um RLIMIT_NPROC reduzido
dentro da sessão de um desenvolvedor com milhares de threads já rodando impede
essa sessão de fazer fork. Todo processo que a execução inicia os herda:
RLIMIT_NPROC em 1024, contado contra o uid do agente como um todo, de modo que
uma fork bomb vinda de `bash.run` para no número e não na máquina - threads
também contam, e é por isso que ele não é menor, já que um navegador são
algumas centenas delas; nada de core files; nenhum arquivo acima de 4 GiB.
RLIMIT_AS não: o Chromium reserva espaço de endereçamento às dezenas de
gigabytes e não iniciaria. Essa camada é igual no Debian e no Alpine, e é a
única que tem uma execução iniciada pelo próprio crontab do agente.

Onde o systemd é o PID 1, o daemon acrescenta a segunda: `fStartRunner` coloca a
execução num scope transitório próprio, `boa-agent-<id>-<random>.scope` sob
`boa-agents.slice`, com `TasksMax=1024` e `MemoryMax=2G`. `systemd-run --scope`
faz exec no comando, então o pid continua sendo o do runner e `/proc` continua
mostrando a linha de comando dele; quem desce para o agente é o `setpriv`,
porque o systemd-run tem de ser root para criar o scope. Medido antes de ser
assim: uma execução era filha de `boa-exec.service`, no próprio cgroup do
daemon, e um agente descontrolado gastava o TasksMax do daemon e o deixava sem
conseguir fazer fork. O scope também é o que encerra o que uma execução deixou
para trás: `bash.run` sinaliza o próprio grupo de processos, então um comando
que chamou `setsid`, ou um filho em segundo plano de um comando que terminou a
tempo, sobrevivia à execução; `fWatchRunner` espera a execução e para o scope
dela, o que alcança tudo o que a execução iniciou, para onde quer que tenha se
movido. Uma execução que foi morta - pelo limite de memória, por um operador -
não escreveu nada ao sair, então a mesma thread registra o fim no diário e fecha
o turno no chat; uma execução que saiu sozinha já fez as duas coisas, e o turno
é verificado em vez de presumido.

### Onde ficam as chaves dos provedores

As chaves compartilhadas por todos os agentes ficam em
`/opt/boa/config/apikeys/<provider>.key`, de propriedade de `boa`, o diretório
com `0700` e os arquivos com `0600`.

0750 e 0640 já deixariam os agentes de fora - nenhum usuário de agente está no
grupo `boa` -, mas isso depende de a lista de grupos de cada agente continuar
vazia por toda a vida da instalação, e basta um `usermod -aG` para tornar isso
falso. Um modo que não concede nada ao grupo não depende disso.
`api_keys.fWrite` define os dois modos a cada escrita, e não só na criação, de
modo que um diretório que chega de uma instalação mais antiga é fechado na
primeira vez que uma chave é salva.

O diretório se chamava `keys` até ser renomeado: era lido como “as chaves desta
instalação” e estava a um erro de digitação do `keys/` por agente que existe
dentro do diretório pessoal de cada agente, que é outra coisa, que um agente
*pode* ler - a própria chave, colocada ali para cobrá-lo em outra conta. O
instalador transfere o diretório antigo no `--update` e só o apaga quando ele
fica vazio.

Nada disso impede que um agente tenha a chave do provedor em que ele de fato
roda: a API dos agentes entrega essa a ele, ele precisa dela para fazer a
chamada, e um agente com `bash.run` poderia imprimi-la. O que isso impede é um
agente ler as chaves dos provedores que ele não usa.

### Dez serviços, dois iniciados como root

| Processo | Usuário | Por que existe |
|---|---|---|
| `boa-proxy` | `boa` | HAProxy: termina o TLS, atende as duas portas |
| `boa-web` | `boa` | Serve a interface e a API, num socket Unix |
| `boa-exec` | `root` | Cria usuários e inicia as execuções dos agentes |
| `boa-samba` | `root` | Autentica as sessões SMB e depois serve os arquivos como o agente dono deles |
| `boa-embeddings` | `boa` | Serve o modelo de vetorização local das bibliotecas de documentos, num socket Unix |
| `boa-rag` | `boa` | Agenda a fila de indexação das bibliotecas de documentos |
| `boa-agent-api` | `boa` | Guarda o que os agentes podem usar, mas não ler |
| `boa-buzzer` | `boa` | Acorda um agente quando um dos cartões dele vence |
| `boa-channel-telegram` | `boa` | Escuta no Telegram e entrega o que chega a um agente |
| `boa-channel-discord` | `boa` | O mesmo, para um canal do Discord |

No Debian, as unidades dos canais são `boa-channel-telegram.service` e
`boa-channel-discord.service`; as unidades de canais futuros seguem
`boa-channel-<channel>.service`. O OpenRC mantém `boa-telegram` e
`boa-discord`. `system_info.fServiceName` resolve esses nomes tanto para a aba
do sistema quanto para os relatórios de estado dos listeners.

`fInstallSystemdUnits` chama `fRetireLegacyChannelUnits` para parar e
desabilitar cada unidade antiga de canal antes de apagá-la e habilitar a
substituta. Atualizações repetidas também funcionam quando não existe nenhuma
unidade antiga. Se uma atualização falha antes de instalar as unidades novas,
`fStartServices` pode reiniciar as antigas durante o rollback.

Os quatro últimos são `boa`, e não root, de propósito: cada um deles precisa que
algo seja feito como o próprio usuário de um agente - iniciar uma execução,
escrever num diretório pessoal 0700 - e cada um pede ao `boa-exec` que faça isso
em vez de receber o privilégio. Um serviço que pode ser alcançado de fora, como
na prática os dois listeners podem, é o último que deveria tê-lo.

### Um ambiente virtual não é realocável

`python3 -m venv <path>` escreve `<path>` no shebang de todo console script
instalado nele depois, em `VIRTUAL_ENV` nos scripts activate e na linha
`command` de `pyvenv.cfg`. O ambiente é construído em `venv.new` e renomeado
para `venv`, então os três passam a citar um diretório que não existe mais.

Medido num Debian 13 real e num Alpine 3.24 real: as duas instalações
terminaram, as duas imprimiram “Installation finished” e as duas deixaram o
`boa-web` reiniciando a cada cinco segundos com

```
status=203/EXEC - Failed to execute /opt/boa/venv/bin/gunicorn:
No such file or directory
```

O arquivo estava lá. A primeira linha dele citava
`/opt/boa/venv.new/bin/python3`, que não estava.

`fBuildVirtualEnv` tinha uma verificação justamente para esse tipo de falha, e
ela passava, porque roda `bin/python3` - um LINK SIMBÓLICO para o interpretador
do sistema, que responde de onde quer que esteja. Só um console script tem o
caminho gravado dentro. Por isso a verificação agora também roda
`bin/gunicorn --version`, que é o arquivo que a unidade do serviço executa, e
`fRepointVirtualEnv` reescreve os três caminhos registrados enquanto o ambiente
ainda está com o nome de construção. A reescrita é verificada em vez de
presumida: se um pip futuro escrever os console scripts de outro jeito, o
instalador para ali.

### Uma atualização que falha deixa algo rodando

Três etapas, e a ordem é o conserto.

Uma atualização parava os serviços, apagava `webapp/` e só então rodava o pip.
Um pip que falhava - sem rede, um índice fora do ar, um wheel que não
compilava - deixava uma instalação com os serviços parados e o código apagado:
uma máquina que estava funcionando um minuto antes, precisando que alguém
percebesse e a recuperasse à mão.

| Etapa | O que acontece | Quanto custa uma falha |
|---|---|---|
| Preparação | Perguntas feitas, dependências instaladas, código baixado, o novo virtualenv CONSTRUÍDO ao lado do que está rodando e verificado que importa | Nada. A versão antiga continua rodando, intocada |
| Troca | Parar, `webapp/` movido para `webapp.previous`, `venv` para `venv.previous`, os novos colocados no lugar, iniciar | Reversível: as duas versões anteriores continuam no disco |
| Verificação | `curl` pede à aplicação a página de login, quinze vezes ao longo de trinta segundos | `fRollBack` coloca as duas de volta e as inicia de novo |

Esse `curl` envia PROXY protocol só no modo `proxied`. No modo `direct` o bind
não tem `accept-proxy`, então um cabeçalho PROXY cai no meio do handshake TLS e
a requisição não recebe resposta nenhuma. Ele era enviado nos dois modos, o que
fazia todo `--install --ports direct` terminar em “did not answer” sobre uma
instalação que estava servindo páginas, e todo `--update` em modo direto se
reverter sozinho. Confirmado passando as duas máquinas de teste para `direct` e
de volta: com a flag amarrada ao modo, as duas responderam 200 na 443 e depois
na 11443. Um teste roda `fVerifyInstallation` dos dois instaladores contra um
`curl` que registra os argumentos, uma vez por modo, e verifica que a flag está
presente num e ausente no outro.

Quando esse `curl` nunca recebe resposta, `fExplainWhyItDoesNotAnswer` escreve
como a máquina estava naquele momento no mesmo log para o qual o erro aponta: o
que o próprio curl diz - perguntado de novo com `-sS`, para distinguir uma
conexão recusada, um handshake que falhou e uma requisição que estourou o
tempo, porque `000` não é um código HTTP, e sim o curl dizendo que nunca
recebeu um -, o estado de cada um dos dez serviços, se há alguma coisa
escutando na porta e as últimas quinze linhas de `boa-proxy.log`, `boa-web.log`
e do `error.log` do gunicorn. `fReportServiceStates` é a metade que difere
entre os dois: `rc-service ... status` no Alpine, `systemctl is-active` mais o
journal de `boa-web` e `boa-proxy` no Debian.

Ela existe porque uma primeira instalação num Alpine recém-instalado terminou em
“The application did not answer on port 11443 (last code: 000)” e o log não
tinha mais nada sobre isso - nem qual serviço estava parado, nem se a porta
estava ocupada, nem uma linha do que o gunicorn tinha impresso. O único arquivo
que o erro cita não conseguia responder à pergunta para a qual estava sendo
aberto. O que procurar nele: um serviço que se diz iniciado ao lado de “nothing
is listening on port 11443” é um processo morrendo e sendo reiniciado, porque
um serviço supervisionado que morre no instante em que inicia é informado como
iniciado pelo comando que o iniciou. Quatro testes EXECUTAM as duas funções -
contra um `curl` que se recusa a conectar, um `ss` que ocupa a porta e outro
que não ocupa, e um `rc-service` e um `systemctl` que respondem “stopped” e
retornam uma falha.

`fRollBack` inicia os serviços num SUBSHELL, e o `|| true` ao lado não basta
sozinho: `fStartServices` chama `fDie` quando um serviço não sobe, `fDie` chama
`exit`, e `exit` encerra o shell não importa o que esteja escrito ao lado.
Medido num Alpine real: o `boa-proxy` foi derrubado pelo OpenRC enquanto o
`boa-web` oscilava, o início dele feito pelo próprio rollback perdeu a corrida
pelo lock do serviço, e o instalador morreu DENTRO de `fRollBack`. O rollback
tinha funcionado - a versão anterior estava de volta e respondendo -, mas o que
o operador recebeu foi “The boa-proxy service would not start”, sem uma palavra
sobre uma atualização que acabava de ser revertida. Nesse ponto, o relato do
que aconteceu é a única coisa que um operador tem.

A versão anterior é removida por `fFinishUpdate`, e só depois que a nova
respondeu.

`fRollBack` rodava num lugar só: quando aquele `curl` final falhava. Entre
`fStopServices` e essa verificação há uma dúzia de passos que podem morrer - um
arquivo de certificado que sumiu, uma configuração de proxy que o HAProxy não
consegue interpretar, uma unidade que não instala - e cada um deles deixava os
serviços parados, o código novo no lugar e `webapp.previous` no disco sem
ninguém colocá-lo de volta. A mensagem citava o que tinha falhado e não dizia
nada sobre a máquina estar fora do ar. Por isso `fDoUpdate` define
`vUpdateSwitched` logo antes de parar os serviços, e `fCleanup` - o trap de
EXIT, que roda seja qual for o jeito como o processo filho termina - faz o
rollback quando encontra a flag definida e o código de saída diferente de zero.
As duas saídas da troca a limpam: o próprio `fRollBack`, para que o caminho
explícito não reverta duas vezes, e `fFinishUpdate`, porque depois que a versão
nova respondeu não há para onde voltar. Medido nas duas máquinas de teste com a
chave privada escondida: “Missing certificate files”, “Putting the previous
version back”, todos os serviços no ar e a página de login respondendo 200 com o
código anterior. Um teste roda o `fCleanup`, o `fRollBack` e o `fFinishUpdate`
reais de cada instalador por três saídas: depois da troca, antes dela e depois
da finalização.

`--install` e `--reinstall` não têm versão anterior a preservar, então não têm
Troca nem rollback - mas têm Verificação. Eles terminavam em
`fWriteCredentialsFile`, e “Installation finished” foi impresso em duas máquinas
reais cujo serviço web estava reiniciando a cada cinco segundos: nada nunca
tinha perguntado nada à aplicação. Agora eles pedem a mesma página de login e,
quando ela não vem, dizem isso e citam o log, porque não há nada na máquina
para onde voltar.

O próprio `pip` tem versão fixada. `--upgrade pip` sem versão fazia com que
duas atualizações do mesmo código pudessem resolver de forma diferente, que era
justamente o que fixar as versões dos requisitos queria evitar. O que ainda não
está fixado são as dependências TRANSITIVAS - por isso o `pip freeze` é
registrado dentro do ambiente e a atualização seguinte imprime o que mudou, que
é o único jeito de alguém ficar sabendo.

### Uma instalação que parou no meio

`fIsInstalled` considerava uma máquina instalada assim que `webapp/backend` e o
usuário `boa` existiam - o que acontece antes do ambiente virtual, dos
certificados, do banco de dados e do administrador. Uma instalação que morreu
no pip, numa rede que caiu, recebia então “already installed” do `--install` e
uma morte no que quer que faltasse do `--update`, e só `--reinstall --yes`
passava disso, sem nada que avisasse o operador.

Agora uma instalação terminada deixa `/opt/boa/installed`, escrito por
`fMarkInstalled` só depois que `fVerifyInstallation` recebeu a página: uma
instalação que está no lugar e não responde não está terminada, e uma
atualização que foi revertida não é a versão nova. Sem o marcador, as cinco
coisas que uma instalação terminada sempre tem - o código, o usuário,
`venv/bin/gunicorn`, `db/boa.sqlite` e `certificates/privkey.pem` - fazem as
vezes dele, de modo que uma instalação de antes de o marcador existir continua
contando e recebe o marcador na próxima atualização. Todo o resto que o
`--install` faz já pode ser feito duas vezes com segurança: o usuário só é
criado se faltar, o ambiente é construído ao lado do antigo, os certificados
são mantidos quando existem, o administrador é apagado e escrito de novo com a
senha nova. Então uma instalação feita pela metade é terminada rodando
`--install` mais uma vez, e o `--update` diz exatamente isso quando encontra
uma. De passagem, `fGeneratePassword` passou para depois de
`fInstallDependencies` no instalador do Debian, onde estava ao contrário:
`openssl` tem Priority: optional no Debian, e uma imagem mínima gerava a senha
antes de o pacote que a gera estar instalado.

### Tudo o que o instalador roda chega ao log dele

`fLog` escrevia as próprias linhas em `install.log` e nada mais. O apt, o pip, a
validação do HAProxy e todos os outros subprocessos escreviam no terminal, então
uma instalação que falhava deixava um log com “Installing the dependencies.” e
nem uma palavra do erro do apt que explicava o porquê - que é exatamente o
detalhe que alguém abre esse arquivo para encontrar.

`fStartCapturingOutput` redireciona o stdout e o stderr deste próprio shell para
um FIFO que o `tee` copia para o log e para o terminal. Um FIFO em vez de
`exec > >(tee ...)`, que só existe no bash, e o Alpine começa sem bash, e em vez
de um pipeline em volta de `fMain`, que o colocaria num subshell e desfaria o
arranjo `fMain & wait` que mantém o errexit vivo.

Duas consequências, e as duas tiveram de ser tratadas:

`fLog` fazia echo da linha E a acrescentava ele mesmo ao log. Quando o stdout
passa a ser um tee que acrescenta a esse mesmo arquivo, a segunda escrita é uma
duplicata: uma instalação de 90 linhas produzia um log de 185 linhas, com cada
linha repetida. Agora `fLog` só escreve no arquivo enquanto a captura não está
rodando.

O `tee` mantém o log aberto pelo INODE. Um `--reinstall` apaga a árvore
inteira, log incluído, e coloca uma cópia nova no lugar - então a partir desse
momento o `tee` está acrescentando a um inode sem nome e, com o `fLog` não
escrevendo mais no arquivo, isso seria toda a segunda metade da reinstalação,
senha gerada incluída. `fRestartCapturingOutput` aponta a captura para o arquivo
que existe agora.

### Dois instaladores, uma aplicação

`deploy/install-update-reinstall-debian.sh` escreve unidades do systemd e
**precisa que o systemd seja o PID 1 da máquina em execução**: um Debian
iniciado com qualquer outra coisa não é um alvo, e o instalador o recusa em vez
de instalar numa máquina que não iniciaria nada.
`deploy/install-update-reinstall-alpine.sh` escreve serviços do OpenRC em
`/etc/init.d/`, a partir de `deploy/openrc/`, e não precisa de nada de antemão:
ele mesmo instala o OpenRC quando a máquina não tem. Os dois instalam os mesmos
dez processos, a mesma árvore sob `/opt/boa`, o mesmo modelo de usuários; um
teste compara os dois passo a passo e falha quando um ganha um passo que o outro
não tem.

Eles não são escritos na mesma linguagem, e isso é proposital. O do Debian é
bash, como todo o resto aqui. O do Alpine é shell POSIX, com `#!/bin/sh`, porque
um Alpine recém-instalado não tem bash: com `#!/bin/bash` o kernel procuraria um
interpretador que não está lá, e

    curl -fsSL <raw-url> | bash -s -- --install

falharia antes de ler uma linha, justamente na máquina que mais precisa da
instalação de uma linha. Sendo POSIX, ele roda igualmente no ash do BusyBox, no
dash e no bash, então o mesmo arquivo funciona canalizado para `sh` num Alpine
vazio e para `bash` num que já o tenha. Ele continua instalando o bash - todo
agente recebe um shell bash -, só não precisa mais dele para começar. O que isso
custa são arrays, `[[ ]]`, `${var//x/y}` e `<(...)`; `local` fica, porque os
três shells o têm, e o `pipefail` é testado num subshell antes de ser ativado,
porque o dash não o tem. Um teste recusa cada uma dessas construções, já que um
recurso de shell que não existe falha na hora da instalação, na máquina de
outra pessoa.

O que o Alpine precisa e o Debian não, e por que nenhum deles é opcional:

| | Por quê |
|---|---|
| `shadow` | O daemon privilegiado chama `useradd --home-dir --create-home --shell`. O `adduser` do BusyBox não tem nenhuma dessas opções, e um agente que não pode ser criado é a aplicação inteira sem funcionar |
| `bash` | O shell que todo agente recebe, e aquilo por onde `bash.run` roda. O Alpine vem sem ele, e é também por isso que o instalador do Alpine é o único arquivo deste projeto escrito em shell POSIX e não em bash: `#!/bin/bash` tornaria `curl ... \| sh` impossível justo na máquina que mais precisa |
| `dcron` | Alguma coisa tem de ler os crontabs que o daemon escreve. É também o motivo do `-d` abaixo |
| `gcc`, `musl-dev`, `libffi-dev`, `python3-dev` | Vários requisitos não publicam wheel para musl e são compilados durante a instalação |
| `libcap` | `setcap cap_net_bind_service` no binário do haproxy, no modo `direct`. O systemd concedia isso por serviço com `AmbientCapabilities`; o OpenRC não tem equivalente |

Três coisas que a adaptação para o Alpine teve de mudar no código, cada uma
descoberta ao instalar:

- **`crontab -u <agent>` em vez de descer para o agente.** O `crontab` do Debian
  é setgid e qualquer usuário pode rodá-lo; o dcron do Alpine o distribui com
  `4750 root:wheel`, então um agente que o roda recebe `Permission denied`. Os
  jeitos de manter a forma antiga eram colocar todos os agentes em `wheel` - o
  grupo que significa sudo na maioria dos sistemas - ou afrouxar um binário
  setuid do sistema. O daemon é root e pode, em vez disso, indicar o usuário.
- **`-r` ou `-d` ao apagar um.** O Vixie cron apaga um crontab com `-r`; o dcron
  com `-d`, e responde a `-r` com uma mensagem de uso e código de saída 2.
  Tentar só `-r` deixava para trás o crontab de um agente excluído, ainda
  apontando para o runner de um usuário que não existia mais. Os dois são
  tentados, porque o que decide é o binário instalado, não o nome da
  distribuição.
- **`executable=` em `browser.conf`.** O Playwright não publica build para musl,
  então no Alpine o pacote fica totalmente fora dos requisitos e não há
  navegador. A linha é lida por `browser.fReadConfiguredExecutable` e é onde um
  Chromium do sistema seria indicado, no dia em que houver um Playwright capaz
  de controlá-lo.

Mais uma, encontrada olhando `/proc/<pid>/fd/2` na máquina Alpine de testes: o
`supervise-daemon` manda o stdout e o stderr de um processo para `/dev/null` a
não ser que lhe digam o contrário, e nada mais no Alpine os recolhe - as
unidades no Debian têm o journald para isso. Nenhum serviço escrevia
nada em lugar nenhum. Cada script do OpenRC agora indica `output_log` e
`error_log`, um arquivo por serviço sob `/opt/boa/logs/`, criado como `boa` em
`start_pre` para que o logrotate possa rotacioná-lo como `boa`, seja quem for
que escreva nele. `fInstallLogRotation`, nos dois instaladores, escreve
`/etc/logrotate.d/boa` para esses arquivos e para os dois do gunicorn: semanal,
oito guardados, `copytruncate` porque os dois escritores mantêm o arquivo
aberto, e nunca `install.log`, que é do root e guarda a senha. A outra metade
da mesma descoberta: a aba Sistema operacional perguntava ao OpenRC pelo
`crond`, o cron do BusyBox, enquanto o instalador roda o `dcron` no lugar dele,
então um Alpine saudável informava o cron como parado.
`fPickOpenRcCronService` pergunta pelo primeiro dos dois que tiver um script de
serviço.

E duas que o instalador contorna em vez de corrigir, porque pertencem ao pacote
haproxy do Alpine: ele não traz `/etc/haproxy/errors/` nem `/run/haproxy` para o
socket de administração. As duas linhas são retiradas da configuração quando o
arquivo ou o diretório delas não está lá, o que também é correto numa máquina
onde um administrador os criou. Criar `/run/haproxy` foi a primeira tentativa,
com um script em `/etc/local.d/` para recriá-lo a cada boot: o `local` roda no
FIM do boot, então o haproxy já tinha falhado ao iniciar quando ele aparecia.

Mais uma pertence ao próprio OpenRC: ele guarda em cache a árvore de
dependências dos serviços e decide se a reconstrói comparando timestamps com
`/etc/init.d`. Numa reinstalação os scripts de serviço são sobrescritos dentro
do mesmo segundo que o cache, então ele mantém o antigo e os serviços ficam
de fora - eles iniciam durante a instalação, porque `rc-service start` não
precisa da árvore, e depois não voltam após um reboot, porque `openrc default`
precisa. `fInstallServices` termina com um `rc-update -u` incondicional.

### O que cada instalador exige da máquina, e o que ele mesmo instala

O instalador do Debian se recusa a rodar onde o systemd não é o PID 1
(`fRequireSystemd`, chamado antes de qualquer coisa ser instalada). Tudo o que
ele configura é iniciado e mantido vivo pelo systemd - as dez unidades, o
HAProxy da máquina, o cron -, então numa máquina assim a instalação terminava,
informava sucesso e não servia nada: o `systemctl` está instalado, responde
“System has not been booted with systemd as init system (PID 1). Can't
operate.”, e nada lia esse código de saída. O que ele imprime agora é como
resolver: instalar `systemd systemd-sysv dbus`, criar o contêiner de novo com
`/sbin/init` como comando, rodar o instalador de novo. Ele diz “create again”
(criar de novo) e não “restart” (reiniciar) porque um contêiner em execução não
pode mudar o PID 1 dele.

O instalador do Alpine toma a decisão oposta sobre o OpenRC, porque ali a peça
que falta é uma que ele pode fornecer: `openrc` é instalado junto com os outros
pacotes - uma imagem de contêiner vem sem ele, um Alpine instalado com
`setup-alpine` o tem - e `fEnsureOpenRcUsable` então cria
`/run/openrc/softlevel`, que é o arquivo que o próprio OpenRC cita quando se
recusa a mexer num serviço num sistema que ele não iniciou. Depois disso os dez
serviços iniciam num contêiner. O log avisa que eles não vão voltar sozinhos,
porque `/run` é um tmpfs e o PID 1 não é o OpenRC.

As duas decisões não são incoerentes: não há como fazer o systemd funcionar
como outra coisa que não o PID 1, e o OpenRC, sim.

### `if ! fMain` desliga o `set -e` na instalação inteira

Os dois instaladores terminam com o fMain iniciado como processo filho:

    fMain "$@" &
    vMainPid=$!
    if ! wait "${vMainPid}"; then ...

e não com `if ! fMain "$@"`, que é o que parece e o que eles tinham antes. Um
comando na condição de um `if` roda com o errexit suspenso, e a suspensão é
herdada por toda função que ele chama e por toda função que essas chamam - ou
seja, a instalação inteira. Medido numa máquina sem systemd: oito comandos
falharam em sequência, cada um imprimiu o seu erro, o script passou por todos
eles e terminou com “Installation finished”. Um processo filho recupera o
errexit, porque a suspensão não sobrevive a um fork. O bash, o dash e o ash do
BusyBox se comportam todos assim, nas duas metades dessa frase, e nem um
`set -e` dentro da função nem um subshell o recuperam.

Duas consequências de rodar o fMain num filho: `trap fCleanup EXIT` também é
instalado dentro do fMain, porque um subshell não herda o trap de EXIT do pai e
a árvore baixada sob `/tmp` ficaria para trás a cada execução; e o pai limpa o
próprio trap antes de sair, para que a linha “Exited with code” não seja
impressa duas vezes.

`fHasTty` é uma correção da mesma família: ele abre `/dev/tty` e o fecha de
novo, em vez de testar `[ -r /dev/tty ]`. Pelo modo, o nó do dispositivo é
legível em todo sistema, então esse teste passava em `ssh host ./installer` sem
pty e o `read` que vinha depois morria com ENXIO - um processo sem terminal de
controle simplesmente não consegue abri-lo.

### O haproxy.cfg de fábrica não é trabalho de ninguém

`fInstallMachineProxy` substitui `/etc/haproxy/haproxy.cfg` quando está no modo
`proxied`, e não mexe num arquivo que não escreveu sem perguntar antes - o proxy
da máquina pode estar atendendo outros sites. O problema é que o arquivo que ele
encontra numa máquina recém-instalada foi colocado ali pelo pacote haproxy, que
**este próprio instalador instalou** um minuto antes, em `fInstallDependencies`.

Tratar esse exemplo como trabalho de alguém é o que fazia todo `--install`
simples parar de vez: sem `--yes`, sem terminal para responder, e a execução
terminava em “Destructive operation with no terminal to confirm on” depois de já
ter construído a árvore, o virtualenv e os certificados. Medido nas quatro
máquinas de teste, Debian e Alpine igualmente, rodando exatamente a linha que o
README dá.

`fMachineProxyIsPristine` pergunta ao gerenciador de pacotes em vez de
adivinhar:

- Debian: o md5 que o dpkg registrou para esse conffile
  (`dpkg-query -W -f '${Conffiles}'`) contra o md5 do próprio arquivo.
- Alpine: o hash que o apk registrou para esse arquivo, lido de
  `/lib/apk/db/installed` (a linha `Z:` sob `R:haproxy.cfg`), contra o
  `openssl dgst` do arquivo. `Q1` é sha1 em base64, `Q2` é sha256.

`apk audit --system` parece ser a resposta do Alpine e não é: medido no Alpine
3.24, ele não informa **nada** para um `/etc/haproxy/haproxy.cfg` editado. A
primeira versão desta verificação acreditou nele, e teria substituído o proxy de
alguém sem perguntar - justamente a única coisa que a confirmação existe para
impedir. Testado desde então com o arquivo do pacote, com uma linha acrescentada
a ele e com o arquivo que este instalador escreve.

Intacto significa que ele é substituído com uma linha no log e nenhuma pergunta.
Editado significa o comportamento antigo: deixado como está num `--update`,
confirmado e copiado para `.before-boa.<timestamp>` numa instalação ou numa
reinstalação.

### Um arquivo para o log e para a senha

O instalador escreve `/opt/boa/logs/install.log` e nada mais: o que ele fez e,
no final, as credenciais que gerou. Antes ele escrevia dois arquivos em /root -
`app-web-install.log` e `app-web-credentials.txt` -, e dois arquivos em dois
lugares são duas coisas para encontrar. `fMigrateInstallFiles` copia o que há
nos antigos para o novo antes de removê-los, porque a senha que está ali pode
ser a única cópia que alguém tem.

Três detalhes sustentam isso:

- `fLog` cria o diretório quando ele não existe. O log fica dentro da árvore que
  o instalador está construindo, então numa primeira instalação ele não existe
  quando a primeira linha é escrita, e um `--reinstall` o apaga no meio do
  caminho.
- `fRemoveInstallation` copia o log para um lado antes de `rm -rf /opt/boa` e o
  coloca de volta depois, para que uma reinstalação não leve embora o próprio
  registro.
- O arquivo é `root:root 0600` dentro de um diretório que pertence a `boa` com
  0750. `boa` pode apagá-lo - é isso que ser dono do diretório significa - e não
  pode ler a senha que está nele; os agentes não estão no grupo `boa` e nem
  conseguem entrar no diretório.

A página de login cita esse caminho, em `frontend/templates/login.html`, numa
linha própria e colorido com `--colour-path`. Ele não está nos quinze arquivos
de tradução: a frase acima dele é traduzida, o caminho é o mesmo em todo lugar,
e um caminho enfiado no meio de uma frase é um caminho que alguém vai redigitar
errado.

### Logotipo circular da aplicação

`frontend/static/img/boa.svg` é uma marca circular azul com três agentes
robóticos, da cintura para cima, de terno preto, camisa branca e gravata escura.
As cabeças deles têm painéis metálicos claros, articulações mecânicas e
viseiras escuras com olhos azuis. O estilo é levemente ilustrado, com texturas
suaves de tecido e sem lenço de bolso no agente central. As cabeças se ligam a
pescoços robóticos visíveis; o agente central, maior, fica na frente dos dois
agentes laterais, menores. A arte sombreada é um WebP de 512px embutido em SVG,
com recorte circular e transparência fora do círculo. As figuras continuam
opacas e mantêm a mesma aparência em todos os temas. É uma arte raster dentro de
um contêiner SVG, não caminhos vetoriais.
`favicon.svg` contém a mesma arte. Mantenha os dois arquivos SVG sincronizados.
As URLs do login, da barra lateral e do favicon usam `v=robot-agents` para
renovar as cópias em cache da marca anterior. Os tamanhos exibidos continuam
sendo 30px na página de login e 24px na barra lateral.

### A interface fala en-US até alguém dizer o contrário

`fGetLanguage` lê a escolha de `localStorage` e, não encontrando nenhuma,
devolve `en-US`. Antes ele negociava primeiro com `navigator.languages`, o que
fazia uma instalação nova falar o idioma do primeiro navegador que a abrisse -
o idioma de uma máquina, não uma decisão. A escolha está a um controle de
distância, no canto da caixa de login e em Configurações, e é lembrada por
navegador.

Dois bugs moravam no mesmo arquivo e os dois apareciam como “o formulário de
login só muda de idioma quando você o muda duas vezes”:

- `fApplyTranslations` só escrevia uma string quando o arquivo carregado tinha
  aquela chave, e o `textContent` já tinha sido sobrescrito pelo idioma
  anterior. Então mudar para en-US - que não tem arquivo, `dTranslations` é
  `{}` - não mudava nada, e mudar para um idioma ao qual faltasse uma chave
  deixava essa chave no idioma de antes. Agora a string original de cada
  elemento traduzido é guardada num `WeakMap` na primeira vez que ele é
  traduzido, e uma chave sem tradução a restaura.
- `fSetLanguage` guardava a escolha e depois chamava `fLoadTranslations()` sem
  argumento, que lia a escolha de volta do armazenamento. Numa janela privada o
  armazenamento lança uma exceção, a leitura devolve o idioma anterior e a
  página recarrega o que já estava mostrando. Agora ele passa o idioma que
  recebeu.

`fLoadTranslations` leva um número de sequência, para que duas mudanças em
rápida sucessão não cheguem fora de ordem e deixem a página num idioma que
ninguém pediu. Três coisas nele estavam erradas, e cada uma mostrava ao usuário
um idioma que ele não tinha escolhido:

- O atributo `lang` era definido no INÍCIO, antes de o arquivo ter sido buscado.
  Um 404 ou um erro de parse deixavam então as strings do idioma anterior na
  tela sob o nome do idioma novo: `lang=fr-FR` com texto em espanhol. Nada é
  publicado até o dicionário estar em mãos, e `fPublish` define os dois juntos
  porque a falha é exatamente os dois serem definidos separadamente.
- A sequência era verificada ANTES de `await response.json()`. Um CORPO lento de
  uma requisição anterior chegava depois que uma posterior já tinha terminado.
  Ela é verificada depois de cada await, porque a sequência pode mudar em
  qualquer um deles.
- Uma falha não dizia nada e deixava a página num estado desconhecido. Agora ela
  recorre ao en-US e informa por `fOnLoadFailed`.

### en-US.json é a fonte, e a marcação é o fallback

O carregador desviava o `en-US` para um dicionário vazio, com o argumento de que
a marcação já traz o texto em en-US. Isso é verdade, e fazia do `en-US.json`
quinhentas chaves de peso morto: distribuído, listado como catálogo, verificado
pelos testes quanto à paridade com os outros treze, e lido por nada. Corrigir um
erro de digitação nele não mudava nada na tela, e o único jeito de descobrir
isso era tentando.

Agora ele é buscado como qualquer outro idioma. O texto da marcação continua
sendo o fallback que sempre se disse que era: uma chave que o catálogo não tem,
ou um catálogo que não carrega, ainda deixa uma página legível em vez de uma
página de lacunas. O que mudou é qual dos dois é a fonte.

### Quinhentas chaves não são uma interface traduzida

Quatro tipos de string visível não tinham chave nenhuma, então ficavam em
inglês nos quinze idiomas:

| O quê | Como é traduzido agora |
|---|---|
| O título da aba | `data-i18n` em `<title>`, uma chave por página |
| As falhas da própria API | Viajam um `code` e os seus `params`; o navegador escreve a frase em `fDescribeApiError`. `error` fica para o que veio de fora - as palavras de um provedor, a recusa de um servidor de e-mail -, para o qual não se deveria inventar uma tradução |
| Descrições de modelos de agente | Fora dos catálogos: o `agent.json` de cada modelo traz a descrição nos quinze idiomas, e o servidor escolhe a que a interface pede (`agent_package.fPickDescription`) |
| Esquema e descrição do tema | `theme.scheme.<scheme>` e `theme.desc.<id>`, o mesmo acordo. O NOME não é traduzido: um tema é a paleta de alguém com um nome, e traduzir “Nord” não ajudaria ninguém a encontrá-lo |

Um modelo de agente ou um tema que alguém escreve para a própria instalação mantém as
próprias palavras em vez de desaparecer.

O seletor de idioma da página de login lista códigos - `es-ES`, `en-US` - e não
nomes de idiomas. Quinze nomes, cada um no próprio idioma, deixavam o controle
tão largo quanto a caixa; o código ocupa 80px, e é o que alguém que procura o
próprio idioma encontra mais rápido numa lista de códigos. Os nomes completos
ficam na página de configurações, que tem espaço.

### Da direita para a esquerda

O hebraico se escreve da direita para a esquerda, e uma página montada da
esquerda para a direita com hebraico dentro é uma página que ninguém consegue
ler. Quatro decisões fazem uma única folha de estilos servir às duas direções:

**A direção viaja com o idioma.** `fPublish`, em `i18n.js`, define `dir` em
`<html>` no mesmo passo que `lang`, a partir de `lRightToLeftLanguages`, de
modo que os dois nunca discordam - a falha que a função existe para evitar só
com `lang`. As linhas de grid e de flex seguem `dir` por conta própria, então a
barra lateral e tudo o que está disposto em linha se espelham sem uma regra
própria.

**A folha de estilos diz início e fim, não esquerda e direita.** Toda margem,
todo preenchimento, borda, `inset` e `text-align` que diz respeito ao fluxo do
texto é uma propriedade lógica (`margin-inline-start`, `inset-inline-end`,
`text-align: start`). O único `left` físico que resta em `app.css` é o anel em
volta do avatar de um agente, que é geometria e não texto.

**O conteúdo mantém a própria direção.** Código, caminhos e comandos vão da
esquerda para a direita em todos os idiomas
(`code, pre { direction: ltr; unicode-bidi: isolate }`), então um caminho dentro
de uma frase em hebraico não é reordenado. Uma mensagem do chat, e cada
parágrafo de uma resposta renderizada, tomam a direção da própria primeira
letra (`unicode-bidi: plaintext`): uma resposta em inglês numa página em
hebraico se lê da esquerda para a direita, uma em hebraico numa página em
inglês, da direita para a esquerda. As caixas de texto em que alguém escreve texto livre seguem a mesma regra, e uma caixa vazia segue a página, de modo que o texto de ajuda dela é lido da direita para a esquerda em hebraico (`dir="auto"` colocaria uma caixa vazia da esquerda para a direita, texto de ajuda incluído); o crontab e o endereço de
e-mail levam `dir="ltr"`.

**O que se lê da esquerda para a direita fica isolado dentro de uma frase.** O
algoritmo bidi atribui um caractere neutro ao lado em que ele encosta, de modo
que um caminho no fim de uma frase em hebraico perdia a barra e o ponto final
para as palavras ao redor: "/tmp/x/007/." era exibido como ".tmp/x/007/ /". Em
um idioma escrito da direita para a esquerda, `fPublish` passa o dicionário
por `fIsolateLeftToRightRuns`, que envolve cada `{placeholder}` e cada trecho
com uma barra em U+2068 FIRST STRONG ISOLATE ... U+2069 POP DIRECTIONAL
ISOLATE, de modo que o valor que um chamador coloca numa frase fique dentro do
isolado. O que a máquina informa em Configurações → Sistema operacional
(`fLeftToRight` em `settings.js`), uma rota na documentação da API
(`.endpoint-path`), a linha de exemplo do crontab e as contagens nas abas e
nas colunas são isolados da esquerda para a direita do mesmo modo; sem isso,
uma versão de kernel era exibida como "deb13-amd64 · x86_64+6.12.111".

### O branch de onde o código é baixado

`cRepoBranch` é `main`, o branch real do repositório. Era `master`, o que só
funcionava porque o GitHub redireciona o nome antigo depois de uma renomeação -
um redirecionamento que deixa de existir no dia em que houver um branch `master`
de verdade, e que ninguém faz para `--repo-url file:///...`, que é como os dois
instaladores são testados.

### Por que a aplicação traz o próprio HAProxy

O HAProxy da máquina encaminha para a porta 11443 com `send-proxy-v2`, então um
cabeçalho PROXY chega **antes** do handshake TLS. O Gunicorn não consegue lê-lo
ali: a opção `proxy_protocol` dele interpreta esse cabeçalho ao interpretar o
HTTP, o que acontece depois de o TLS ser terminado, então os bytes do cabeçalho
caem no handshake e o quebram com `WRONG_VERSION_NUMBER`. Isso foi descoberto ao
implantar, não ao testar.

O HAProxy aceita os dois num mesmo bind - `accept-proxy ssl crt ...` -, então a
aplicação traz a própria instância, que é também o único componente escutando
numa porta. O Gunicorn, em vez disso, faz bind num socket Unix, o que significa
que não há caminho para dentro da aplicação que não passe pelo proxy, e o
endereço real do cliente sobrevive como `X-Forwarded-For` - sem ele, o limite de
tentativas do login veria 127.0.0.1 para todo mundo e deixaria de ser por
endereço.

É HAProxy e não nginx porque a implantação já depende do HAProxy: nada de
tecnologia nova para um problema que uma existente resolve.

O HAProxy da máquina não deve usar `option ssl-hello-chk` neste backend: o
ClientHello dessa verificação é anterior ao TLS 1.2, então ela falha contra um
bind que o exige e marca o backend como fora do ar para sempre. O sintoma é um
503 de um serviço que está rodando perfeitamente, o que vale a pena saber
porque nada nos logs da própria aplicação diz que há algo errado.

E a verificação tem de bater na 11080, não na 11443. Uma verificação TCP contra
o bind TLS conecta e desliga sem handshake, e este HAProxy registrava cada uma
como “SSL handshake failure” - medido na máquina Debian de testes, 64.075 linhas
em dois dias, uma a cada dois segundos, enterrando no journal qualquer coisa
real. `check-ssl verify none` foi tentado primeiro e trocou uma linha por outra:
o fechamento abrupto da verificação chegava enquanto o handshake ainda estava
sendo concluído, e cada verificação registrava isso ou `ECONNRESET`. Contra a
11080 o mesmo conectar-e-fechar é uma sessão nula que `option dontlognull`
mantém fora do log, as duas portas pertencem a um mesmo processo, e o journal
ficou em silêncio: zero linhas em trinta segundos com o site respondendo 200 de
fora.

Então o backend no HAProxy da máquina é, completo:

```
backend https-out
  mode tcp
  server srv-https-out 127.0.0.1:11443 check port 11080 send-proxy
```

`send-proxy` é o que leva o endereço do cliente. `check-send-proxy` fica de fora
de propósito: a 11080 não aceita o PROXY protocol. A versão disto voltada ao
operador está no MANUAL.pt-BR.md, em “Como deve ser o HAProxy da máquina”.

Ele não fixa nenhum `maxconn`, e isso não é descuido. `maxconn 2048` pede ao
kernel 4131 descritores de arquivo e o HAProxy sai em vez de iniciar sem eles:
*Cannot raise FD limit to 4131, current limit is 1024 and hard limit is 4096*.
Relatado a partir de um LXC Alpine rodando sob OpenWrt num BPI-R3, cujo limite
rígido é 4096: o `boa-proxy` foi reiniciado setenta vezes, nada nunca escutou
na 11443, e uma primeira instalação terminou em “The application did not answer
on port 11443 (last code: 000)”. As duas máquinas de teste são LXCs do Proxmox
com limite rígido de 524288, e é por isso que nenhuma delas mostrou o problema,
e `haproxy -c` aceitou o arquivo em todas - a configuração nunca foi inválida, o
processo morria na inicialização. Sem `maxconn`, o HAProxy se dimensiona a
partir dos descritores que de fato pode ter, que é o que a própria mensagem
dele pede, e `fd-hard-limit 4000` limita o que ele pega onde o limite é enorme.
Medido com um mesmo binário em três limites rígidos: 4096 dá maxconn 1987, 1024
dá 499, 524288 dá 1987. Um teste inicia o haproxy real com o arquivo distribuído
sob um limite rígido de 4096 e exige que ele continue no ar, e o inicia de novo
com o antigo `maxconn 2048` e exige que ele morra - um teste que só lia o
arquivo foi justamente o que deixou isso passar.

Três coisas precisam de root de verdade: criar um usuário de sistema, instalar o
crontab de outro usuário e iniciar um processo como outro usuário. Todo o resto
não precisa. Por isso o root vive num pequeno daemon com um **vocabulário
fechado de verbos** sobre um socket Unix, e de propósito não existe nenhum verbo
que signifique “rode este comando”. Um atacante que alcance esse socket pode
criar um agente sem privilégios; não pode rodar código como root.

O socket é `0660 root:boa`, e `SO_PEERCRED` é verificado em cada conexão para
que só o root e `boa` sejam atendidos, diga o que disser o modo do arquivo
depois de alguma atualização futura.

### Uma mudança tem de vir das próprias páginas deste site

O cookie de sessão é `SameSite=Lax`, o que impede que uma requisição vinda de
outro site o leve. Não impede outra ORIGEM no mesmo site: um agente com
`bash.run` pode servir uma página neste mesmo host, numa porta própria, e um
link para ela numa resposta do chat está a um clique de distância. Um
formulário ali que faça POST para `/api/admin/agents/000/run` é uma requisição
same-site, o cookie viaja e a execução começa; sendo um POST simples sem corpo,
nenhum preflight fica no caminho também. Por isso
`fRefuseChangesFromElsewhere`, um `before_request` no blueprint da API, responde
403 a qualquer POST, PUT, PATCH ou DELETE que não tenha vindo das próprias
páginas deste site: um cabeçalho `Origin` tem de citar exatamente este host e
esta porta - `localhost` e `localhost:8080` são duas origens, e a segunda é
exatamente a página que um agente poderia servir - e um cabeçalho
`Sec-Fetch-Site` tem de dizer `same-origin`. Uma requisição sem nenhum dos dois
não é de um navegador, é um script ou os testes, e fica para o login julgar,
como antes. Um GET não é barrado: não muda nada, e uma página de outro lugar não
consegue ler a resposta, porque não há cabeçalhos CORS que permitam isso.

### A API dos agentes, e por que ela sequer existe

Duas coisas pertencem a `boa` e não podem ser legíveis pelos agentes: o banco de
dados do kanban (um agente que pudesse escrevê-lo diretamente poderia reescrever
o histórico de outro agente) e as credenciais dos canais (um token de bot não é
uma mensagem — é autoridade permanente para enviar).

Por isso os agentes chegam aos dois pelo `boa-agent-api`, por um segundo socket
Unix que todo agente pode abrir. A autorização são duas verificações
independentes:

1. O token apresentado bate com o SHA-256 armazenado do token de algum agente.
2. `SO_PEERCRED` diz que o processo que chama pertence ao usuário *daquele*
   agente.

Qualquer uma sozinha seria mais fraca: um token vazado é inútil na conta
errada, e ser a conta certa é inútil sem o token.

É um socket Unix e não HTTPS porque não há nada a ganhar com TLS entre dois
processos numa mesma máquina, e um certificado autoassinado significaria que
todo agente roda com a verificação desativada — o que é pior do que não ter
TLS, porque parece segurança.

### Onde fica o estado, e por que ele é dividido

| Estado | Onde | Por que ali |
|---|---|---|
| Configuração do agente | `agents/xxx/info.json` | O agente precisa lê-la como ele mesmo |
| Histórico do agente | `agents/xxx/runs.jsonl` | O único lugar onde um agente pode escrever |
| Procedimentos compartilhados | `skills/<Name>/SKILL.md` (root, 0755) | Lidos por todo agente que os recebe, escritos por nenhum |
| Índice de agentes, login, configurações | `db/boa.sqlite` (0700 `boa`) | O processo web precisa dele |
| O quadro | `kanban/kanban.sqlite` (0700 `boa`) | Muitos escritores simultâneos |

De propósito, **não existem tabelas `runs` nem `usage`**. Um processo de agente
não consegue abrir o banco de dados que pertence a `boa`, e conceder acesso de
escrita a ele deixaria qualquer agente reescrever o histórico de qualquer outro.
Em vez disso, cada agente acrescenta ao próprio diário, e a aplicação web os lê
por meio do `boa-exec`. O benefício colateral é que um agente continua
registrando o que fez quando a aplicação web está fora do ar.

O quadro é SQLite e não um diretório de arquivos JSON porque vários agentes
acordando no mesmo minuto do cron é o caso normal, e só uma transação impede que
duas inclusões simultâneas sobrescrevam uma à outra.

### O que um backup guarda

`--backup` escreve um único arquivo tar com tudo o que a instalação é e o código
não é, e `--restore` coloca um no lugar do que a máquina tem; os dois estão nos
dois instaladores, função por função. A lista é a tabela acima transformada numa
linha de `tar`: os dois bancos de dados, as chaves e os canais, os certificados,
todo agente com o diretório pessoal e os arquivos protegidos dele, as
habilidades e as ferramentas. Em volta disso, três coisas que um `tar` de
`/opt/boa` faria errado:

- **Os bancos de dados passam pela API de backup do SQLite**,
  `fCopySqliteDatabase`, e não pelo `cp`. Os dois rodam em modo WAL, então uma
  cópia do arquivo `.sqlite` perde o que ainda está no arquivo `-wal`, e uma
  cópia feita no meio de uma escrita pode sair rasgada. O `python3` do venv tem
  o módulo; o comando `sqlite3` não está em nenhuma das duas distribuições. O
  mesmo motivo vale ao contrário na restauração: os arquivos `-wal` e `-shm`
  antigos são removidos antes de o arquivo restaurado ser lido, ou o SQLite
  aplicaria o log antigo a ele.
- **Os usuários dos agentes viajam pelo nome.** `agents.txt` registra o usuário,
  o uid e o gid de cada agente, e `fRestoreAgentUsers` cria os que faltam,
  sempre com o mesmo nome e com os mesmos ids quando estão livres. A propriedade
  no arquivo tar é mapeada pelo nome na extração, então um `boa` ou um
  `agent-001` com outro uid na máquina nova continua dono dos próprios
  arquivos. Os crontabs ficam no spool do cron, não sob `/opt/boa`, então são
  lidos com `crontab -l` e devolvidos com `crontab -u`.
- **Três arquivos ficam de fora de propósito**: `config/ports.conf`,
  `config/browser.conf` e o `haproxy.cfg` gerado a partir deles descrevem ESTA
  máquina, e uma restauração não deve importar as escolhas de outra máquina. O
  log de instalação viaja como `install.log.backup`, com outro nome para que
  uma restauração nunca escreva por cima do log que está sendo escrito naquele
  momento; as linhas de credenciais dele são acrescentadas ao log atual, porque
  o login depois de uma restauração é o do backup.

A restauração é a única ação que substitui dados e não pode ser desfeita, então
ela pede confirmação como uma reinstalação. As duas funções são executadas pelos
testes sobre uma árvore real, no bash e no dash: o arquivo tar é verificado
quanto ao que contém e ao que deixa de fora, a árvore é danificada de todas as
formas que uma restauração tem de desfazer, e a restauração é verificada arquivo
por arquivo.

### Uma habilidade é indexada no prompt e buscada sob demanda

A memória de um agente é carregada inteira em todo prompt de sistema, e isso é o
certo para uma memória: o limite de caracteres dela é configurável por agente
(8.000 por padrão, de 1.000 a 1.000.000 permitidos) e ela é a única coisa que o
agente não consegue deduzir de novo.

As habilidades não são assim. Um procedimento tem uma ou duas páginas, um agente
pode receber vários, e a maioria das execuções não precisa de nenhum - a
verificação de disco não precisa do procedimento dos certificados. Carregá-las
do jeito que a memória é carregada significaria pagar por todas em cada chamada
de cada execução, e os tetos em `info.json` são medidos em tokens.

Por isso o prompt leva um índice - uma linha por habilidade, com o nome e a
descrição - e o corpo é buscado com `skill.read`, uma vez, por um agente que
decidiu que precisa dele. Cinco habilidades custam cerca de 200 tokens por
execução em vez de 10.000, e a que é lida é cobrada uma vez em vez de em cada
chamada.

A descrição no cabeçalho é, portanto, a parte que sustenta tudo: é com base nela
que o agente decide, e é por ela que toda execução paga, seja a habilidade lida
ou não.

### As habilidades pertencem ao root, como as ferramentas

Uma ferramenta pertence ao root porque a aplicação a importa como código. Uma
habilidade não é executada por nada, mas é colocada à frente do raciocínio de um
agente que acorda às quatro da manhã sem ninguém olhando, o que a torna
exatamente tão sensível quanto `system-prompt.md` - e esse arquivo já fica num
diretório que o agente pode ler e não pode escrever.

Por isso não há editor de habilidades na interface web, nem verbo privilegiado
para escrever uma. As habilidades são escritas no servidor por SSH. A interface
decide qual agente recebe qual, que é o mesmo que ela faz com as ferramentas.

A outra metade dessa decisão é onde elas ficam: `/opt/boa/skills/`, fora de
`webapp/`, porque `fDeploySourceCode` faz `rm -rf` em `webapp` e um procedimento
que alguém escreveu neste servidor não é algo que uma atualização tenha o
direito de apagar. Mesmo raciocínio, mesmo lugar na árvore, que
`/opt/boa/tools/`.

A aplicação não traz nenhuma. Não existe `backend/skills/` e os instaladores não
copiam nada para esse diretório: eles o criam vazio, do root e com 0755. Uma
habilidade é um procedimento para UMA instalação - estes hosts, este backup,
este certificado -, então uma genérica seria um procedimento que ninguém segue,
ocupando uma linha de cada prompt de cada execução para dizer isso. O diretório
estar vazio numa instalação nova é o recurso funcionando, não uma peça faltando.


### `deploy/` não é implantado

`/opt/boa/webapp/` contém `backend/` e `frontend/` e nada mais. O diretório
`deploy/` - as unidades, as duas configurações do HAProxy, os modelos de
agentes, os catálogos de provedores, `requirements.txt` e o próprio instalador -
é material do próprio instalador, e é lido da árvore que o instalador acabou de
baixar em `/tmp`, que é jogada fora quando ele sai.

Isso não é só arrumação. Ler as unidades de uma cópia sob `/opt/boa` significava
instalar as unidades da versão que estivesse no disco; lê-las da árvore baixada
instala as unidades da versão que está sendo implantada, que é o único par sobre
o qual dá para raciocinar. Cada uma dessas leituras chama `fRequireSourceCode`
antes, então um passo que alguma vez rode antes do download falha com uma frase
em vez de copiar de `/deploy/...`.

É também por isso que `gunicorn.conf.py` fica em `backend/web/` e não em
`deploy/`: o gunicorn o lê a cada início, então ele tem de ser um arquivo que de
fato está no servidor, e o diretório que está no servidor é o que contém o
código que ele configura.

O que é implantado é `root:root`, diretórios `00755` e arquivos `0644`,
definidos por `fSetCodeModes` e por nada mais. Nada sob `webapp/` é executado
pelo caminho - o daemon roda o runner como `venv/bin/python3 .../runner.py`, e o
crontab que ele escreve para cada agente também -, então nenhum arquivo ali
precisa do bit de execução. Mesmo assim eles o tinham, até isso virar uma
função só: `fDeploySourceCode` definia `0644` e `fCreateDirectoryTree`, que roda
depois dela numa atualização, fazia em seguida `chmod -R 00755` sobre a mesma
árvore.

### O Telegram recebe HTML e, na falta dele, as palavras

Um modelo escreve markdown. Mostrado cru, isso é `**25G free**` com os
asteriscos no meio da frase, que é o que chegava ao celular até isto existir.

O Telegram renderiza um pequeno subconjunto de HTML - catorze tags, nenhum
atributo digno do nome e, entre elas, nenhum título, lista ou tabela. Por isso
`telegram_html` traduz aquilo para o que existe uma tag e encontra uma forma
legível para o que não existe: títulos viram negrito numa linha própria, itens
de lista ganham um marcador, e uma tabela vira um bloco `<pre>` com
preenchimento, que é o único jeito de as colunas ficarem umas embaixo das outras
num celular.

Três coisas nele são estruturais.

**O escape vem primeiro.** `&`, `<` e `>` são marcação para o Telegram, então um
agente que informa `grep <dev> && echo` produz uma mensagem que o Telegram
responde com um 400 - ou seja, uma mensagem que nunca chega. Todo pedaço de
texto passa por `fEscape` antes que qualquer coisa o envolva. Um href passa por
`fEscapeAttribute`, que também escapa as aspas duplas: uma URL que contivesse
uma fecharia o atributo e transformaria o resto dela em atributos que ninguém
escreveu.

**Uma mensagem rejeitada é enviada de novo como texto puro.** Seja lá o que o
renderizador tenha errado, as palavras valem mais do que a formatação, então um
400 é tentado de novo sem `parse_mode` e a linha sai sem formatação. O fallback
registra o que o Telegram disse, porque uma formatação que se degrada em
silêncio para sempre é uma formatação que ninguém conserta.

**Uma resposta que o Telegram rejeita é descartada, e uma que ele não consegue
receber é guardada por uma hora.** `fSay` devolve três coisas e não duas:
enviada, sem resposta e rejeitada - um 4xx que não seja 429, `ChannelRejected`,
que é o Telegram dizendo não a esta mensagem e mantendo o não amanhã também: o
bot bloqueado, o chat que sumiu, o token revogado. `fDeliverAnswers` mantinha a
linha diante de qualquer falha e tentava de novo na passada seguinte, e a linha
fica no disco para que um reinício não perca uma resposta, então um bot
bloqueado transformava o listener num loop sem fim: o polling no modo rápido,
uma leitura do chat pelo daemon root e até duas requisições ao Telegram a cada
passada, sobrevivendo a todo reinício. Uma resposta rejeitada é descartada na
hora com uma linha dizendo isso, e uma resposta que o Telegram não aceitou
dentro da hora que uma execução recebe também é descartada, pelo mesmo motivo
pelo qual o outro ramo desiste de uma execução que nunca terminou. Nenhum dos
dois perde a resposta: ela está na conversa do agente na interface web, onde
foi escrita primeiro.

Os padrões são os mesmos que `frontend/static/js/markdown.js` usa. Dois
renderizadores discordando sobre o que conta como markdown fariam uma mesma
resposta ser lida de forma diferente nos dois lugares onde é mostrada, e o
sentido de mandar para os dois é que eles são a mesma conversa.


### O Discord é consultado por polling, e uma resposta tem dois mil caracteres

O Discord é o segundo canal pelo qual uma pessoa pode responder a um agente, e a
metade que recebe é `discord_listener` - `boa-channel-discord`, o sétimo
serviço. Quatro coisas o separam do listener do Telegram.

**Ele faz polling, por REST.** `GET /channels/<id>/messages?after=<id>`, a cada
cinco segundos, e a cada dois enquanto um agente está no meio de uma resposta. O
Gateway é a alternativa óbvia e não foi a escolhida: é um WebSocket que precisa
de heartbeats, de um protocolo de retomada e de uma dependência que este projeto
não tem, e exige o Message Content Intent ativado no portal de
desenvolvedores - sem o qual toda mensagem chega com `content` vazio e nada diz
por quê. O polling também conecta para fora, que é o que permite que isto rode
numa LAN sem nada redirecionado, exatamente como o long poll do Telegram. O que
ele custa é uma latência medida em segundos, e doze requisições por minuto
contra um limite de cinquenta por segundo.

**Dois mil caracteres, não quatro mil.** `channels.cMaxMessageLength` é 4096,
que é o teto do Telegram, e o Discord responde 400 a um `content` com mais de 2000.
Uma resposta longa não chegava encurtada - não chegava.
`discord_markdown` a corta entre linhas em no máximo quatro mensagens, e um
bloco de código delimitado dentro do qual um corte caia é fechado no fim de uma
e aberto de novo no início da seguinte: sem isso, uma metade chega como texto
puro e a outra como um bloco que nunca termina, o que no Discord engole tudo o
que for dito depois. Cada parte é registrada como sendo daquele agente, porque
uma pessoa responde a qualquer uma que estiver na tela dela.

**Sem botões, e `!` para comandos.** Um clique num botão e um comando de barra
são ambos *interações*, e uma interação chega pelo Gateway ou por um endpoint
HTTPS que o Discord consiga alcançar. Um canal consultado por polling não vê
nenhum dos dois. Por isso `/agents` é `!agents`, uma mensagem comum, e a lista
de agentes é uma lista de nomes para digitar em vez de uma coluna de botões.
`/agents` também é aceito, porque quem configurou o bot do Telegram vai
digitá-lo por hábito.

**A resposta de um agente não menciona ninguém.** Toda mensagem que isto envia
leva `allowed_mentions: {"parse": []}`, então um `@everyone` que um modelo
escreva é texto e não uma notificação para um servidor inteiro. `replied_user`
continua ligado: uma resposta deve alcançar a pessoa que perguntou. Uma regra no
socket e não num prompt, pelo mesmo motivo pelo qual a lista de encaminhamento
de e-mail também é.

O que o Discord não tem é o silêncio do Telegram diante de estranhos. Não há
`chat_id` com o qual comparar: o bot pede um canal e lê esse canal, então quem
pode falar com os agentes é quem pode escrever nele. Um canal privado é a
configuração que corresponde ao que `fIsFromTheConfiguredChat` impõe no
código - e isso é dito no manual, porque é a autorização inteira.

O webhook que este canal tinha antes continua lá e continua enviando. Um webhook
não lê, não responde e não recebe de volta nenhum id de mensagem, então `listen`
sobre um webhook é recusado em vez de oferecido: um interruptor que não faz nada
é pior do que nenhum interruptor.

### Um roteamento, dois listeners

`agent_routing` reúne o que os dois listeners fazem de forma idêntica: quais
agentes existem, ler um nome a partir de `@News Miner`, `/news_miner` ou `@002`
com a correspondência mais longa vencendo, o que um agente disse para fechar um
turno, e o relatório de estado. O protocolo fica em cada um deles - um long poll
não é um polling REST, um teclado inline não é uma lista de nomes, e uma
resposta é `reply_to_message` num e `message_reference` no outro.

Ele foi escrito junto com o segundo listener, e o relatório de estado é o
motivo. Duas cópias dessa resposta seriam duas respostas para “está rodando?”, e
a primeira coisa sobre a qual elas discordariam é quantos serviços existem.

O envio não está ali. Ele fica em cada listener como `fSay`, que é o que permite
a um teste substituir o de um listener e deixar o outro em paz.

### Um navegador, compartilhado; um perfil, não

`web.fetch` lê uma página pública e para por aí: sem sessão, sem formulário, sem
botão. O navegador é a outra coisa, e ele se divide em dois:

| | Onde | De quem é |
|---|---|---|
| O navegador | `/opt/boa/playwright/` | root, 0755, uma cópia |
| O perfil | `agents/xxx/browser/profile/` | do agente, 0700, um para cada |

O binário é compartilhado porque é um binário e não há nada a isolar nele; uma
cópia por agente seriam 600 MB cada uma e uma atualização para fazer N vezes. O
perfil não é compartilhado, porque guarda os cookies: o agente 007 entrar em
algum lugar não pode deixar o agente 008 logado. Essa separação é feita pelo
kernel, o mesmo diretório pessoal 0700 onde fica todo o resto de um agente - que
é justamente o que um produto de agentes hospedado não consegue oferecer quando
todos os seus agentes compartilham uma máquina e um conjunto de sessões.

Daí decorrem três decisões:

**O navegador fica aberto entre chamadas de ferramentas dentro de uma
execução.** `browser.click` age sobre o que `browser.open` deixou na tela, e uma
execução é um processo só da primeira chamada de ferramenta à última, então um
handle no nível do módulo é todo o estado de que isso precisa. `atexit` o fecha;
sem isso, um agente que roda de hora em hora deixa um Chromium para trás a cada
execução e enche a máquina até de manhã.

**O Playwright é importado dentro das funções, nunca no escopo do módulo.** As
ferramentas de navegador são listadas na interface tendo ou não um navegador
instalado, e um ImportError no topo as faria sumir dessa lista sem explicação em
lugar nenhum. Importado tarde, um navegador ausente é uma frase dizendo qual
comando rodar.

**Headless, e só endereços públicos.** O que se quer é a sessão e o DOM, não uma
imagem de uma janela, então um display virtual seria uma peça móvel à toa.

“Só endereços públicos” é imposto por um route handler instalado no CONTEXTO
(`browser.fInstallNetworkPolicy`), não por cada ferramenta. Verificar a URL em
`browser.open` cobria exatamente um endereço por execução: uma página é livre
para redirecionar, e uma página que um agente foi mandado ler é livre para
conter um link, um iframe, uma imagem ou um formulário apontando para
`127.0.0.1` - e `browser.click` não tinha verificação nenhuma. No contexto, isso
cobre navegações, redirecionamentos, cliques, envios de formulário e todo
sub-recurso, e a sexta ferramenta de navegador que alguém escrever recebe isso
sem saber que existe. O que é recusado é citado na resposta da ferramenta,
porque de outro modo uma requisição bloqueada é invisível: a página é
renderizada sem ela e o agente gasta o orçamento tentando de novo.

Os nomes de host são resolvidos uma vez por execução e lembrados, o que limita,
mas não elimina, a janela em que um nome poderia resolver para um endereço
público na verificação e para um privado na conexão. Fechá-la exige que a
conexão fique presa ao endereço que foi verificado, algo que o Chromium não
expõe daqui.

Um cookie de sessão continua desaparecendo quando o navegador fecha, neste como
em qualquer navegador. O que sobrevive é o que o site marcou para sobreviver.

### O que um provedor aceita não é o que o padrão diz

Dois adaptadores enviavam algo que o provedor deles recusa, e nos dois casos o
resultado foi o mesmo: toda chamada de ferramenta por aquele provedor falhava,
em todos os modelos, e nada na suíte de testes percebia, porque a suíte testava
as peças e não a ida e volta.

| Provedor | O que foi enviado | O que voltou |
|---|---|---|
| Ollama | `kanban__list_cards` decodificado de volta para nada | O registro recusou uma ferramenta que não tinha sido concedida ao agente - o nome que acabava de lhe ser oferecido |
| Google | `"additionalProperties": false`, que é JSON Schema correto | `400 - Unknown name "additionalProperties" at 'tools[0].function_declarations[0].parameters'` |

O `function_declarations[].parameters` do Gemini é um SUBCONJUNTO do JSON Schema
e recusa o que não conhece em vez de ignorar, então `fCleanSchemaForGoogle`
filtra o schema por uma lista de permissões, recursivamente. Uma lista de
permissões e não uma lista de bloqueio, pelo motivo pelo qual toda lista de
permissões aqui é uma: do contrário, a próxima chave que alguém acrescentar ao
schema de uma ferramenta seria recusada pelo Gemini, alguém tendo lembrado ou
não de acrescentá-la a uma lista de coisas a remover.

Os dois foram encontrados rodando o ciclo inteiro - perguntar, chamar uma
ferramenta, responder a essa chamada - contra as APIs reais com chaves reais.
`_/temp/probe-defaults.py` é essa verificação, e é a única coisa que encontra
esse tipo de bug: um schema que é válido, um nome que está correto e um
provedor que não o aceita.

### Um arquivo de adaptador por provedor

Vinte e cinco provedores, vinte e cinco arquivos, mesmo que a maioria fale o
mesmo dialeto. Um único adaptador “compatível com OpenAI” parece arrumado até
que um desses provedores mude o nome de um campo, e aí a correção tem de ser
feita sem quebrar os outros vinte. Cada arquivo carrega as peculiaridades do
seu provedor: o DeepSeek descarta `reasoning_content` antes que o runner possa
reenviá-lo, o llama.cpp detecta um chat template sem suporte a ferramentas, o
vLLM transforma um 404 na lista dos modelos que ele de fato serve, o Cloudflare
monta o endereço a partir da credencial.

O que eles compartilham é `base.py`: um formato neutro de mensagem modelado em
chat/completions, porque a maioria já o fala, e o adaptador da Anthropic o
traduz para content blocks.

Eles também compartilham `openai_dialect.py`, e a diferença entre isso e um
adaptador compartilhado é justamente a questão. O módulo do dialeto contém a
requisição em si - o POST, os erros HTTP que vale a pena nomear, a
interpretação da resposta -, que não é peculiaridade de nenhum provedor. As
peculiaridades ficam em cada arquivo, declaradas como atributos de classe que o
módulo lê:

| Atributo | O que ele decide |
|---|---|
| `cDisplayName` | O nome em toda mensagem de erro. “zai request failed” não é o que alguém procuraria |
| `cMaxTokensField` | `max_tokens` ou `max_completion_tokens`, dependendo de qual grafia o provedor seguiu |
| `cToolChoiceMode` | `auto`, `any`, ou `omit` para os provedores que recusam o campo. `auto` é o que um agente precisa: um modelo forçado a chamar uma ferramenta a cada turno nunca termina uma execução |
| `cChatCompletionsPath` | O caminho depois da URL base, para os poucos que não usam o habitual |
| `cAssistantContentWhenEmpty` | O que enviar no lugar de um `content` nulo, para um provedor cujo schema recusa null |

### O que vinte e duas chaves reais mudaram

Todo provedor daqui foi chamado com uma chave real, recebeu uma pergunta, recebeu
uma ferramenta e depois recebeu a resposta à chamada de ferramenta que fez. Os
vinte e dois que têm chave completam essa ida e volta. Sete coisas só
apareceram no segundo passo -
aquele a que um teste com resposta pronta nunca chega - e cada uma agora é uma
linha de código com as palavras do próprio provedor ao lado:

- **A Perplexity tinha aposentado o endpoint.** `chat/completions` responde 403
  “Sonar is now the Agent API. Use /v1/responses instead of /v1/sonar”, então
  esse adaptador foi reescrito contra a Responses API, e o provedor deixou de
  ser um modelo para ser um roteador sobre 48 deles.

- **Uma chave numa mensagem de erro.** O Gemini era chamado como `?key=...`,
  então um 503 dele colocava a chave inteira no erro que o usuário lê e que o
  diário guarda. A chave passou para o cabeçalho `x-goog-api-key`, e
  `base.fRedactCredentials` agora remove `key=`, `api_key=`, `access_token=` e
  `token=` de todo erro que qualquer adaptador produz, porque esse modo de
  falha não deveria depender de um adaptador lembrar.
- **O Gemini 3 quer a thought signature de volta.** Uma conversa cujas chamadas
  de função voltam sem a assinatura que ele emitiu é recusada de cara, então
  todo agente Gemini falhava assim que usava uma ferramenta.
  `ToolCall.dProviderData` a leva e a traz, opaca para todo o resto.
- **O Cloudflare recusa um `content` nulo.** Que é exatamente o que uma mensagem
  do assistente contém quando o modelo respondeu com chamadas de ferramentas e
  nenhuma palavra. Ele recebe `""`; o dialeto continua mandando null para todos
  os outros, porque null é o que o dialeto especifica.
- **Raciocínio escrito dentro da resposta.** O MiniMax responde com
  `<think>...</think>` no próprio texto. Removido no módulo do dialeto e não num
  adaptador, porque é o modelo que faz isso, então o mesmo modelo atrás de um
  gateway também faz - e só quando a resposta COMEÇA com a tag, para que um
  modelo escrevendo sobre HTML mantenha as palavras.
- **A Together deixa o nome do canal na frente.** O gpt-oss escreve em canais e
  a Together devolve “finalThe weather in Madrid”; a Groq e a Cerebras, servindo
  o mesmo modelo, não. Removido em `together.py`, onde fica uma peculiaridade de
  um único provedor.
- **Quatro modelos padrão que o provedor não servia.** O 20b da Fireworks
  precisa de um deployment próprio, o da Together não é serverless, a Moonshot
  aposentou o kimi-k2.5, e o gemini-3.7-flash responde 503 “experiencing high
  demand”. Um padrão que falha na primeira execução é pior do que um padrão uma
  versão atrás.

Cinco adaptadores não o usam de jeito nenhum, porque a API deles não é essa: os
content blocks da Anthropic, o `generateContent` do Google, o `/completion` do
llama.cpp, o chat v2 da Cohere - que aceita as mesmas mensagens, mas responde
com texto em blocos, um finish reason próprio em maiúsculas e contagens de
tokens aninhadas sob `usage.tokens` - e a Perplexity, que aposentou o
chat/completions de vez e responde a ele com

    403 Sonar is now the Agent API. Use /v1/responses instead of /v1/sonar

por isso esse adaptador fala a Responses API: uma lista `input` em vez de
`messages`, o prompt de sistema como `instructions`, e uma resposta que chega
como itens de saída - uma `message` com o texto em blocos, ou uma
`function_call` - em vez de como uma choice. O resultado de uma ferramenta volta
como um item próprio, `function_call_output`, associado por `call_id`.

Dois nomes são resolvidos antes que qualquer outra coisa os veja, por meio de
`factory.dProviderAliases`: `gemini` é como a documentação do Google chama a API
e `google` é o que o `info.json` de todo agente diz desde a primeira versão,
então os dois chegam ao mesmo adaptador e só um deles é armazenado.

Qual dos vinte e cinco pode ser configurado num agente é decidido em
`fListProviders`, não no navegador: um provedor é `selectable` quando é
auto-hospedado ou quando a chave dele está armazenada. É um filtro sobre o que
vale a pena oferecer, não uma regra - uma chave também pode ficar no próprio
diretório pessoal do agente, onde a aplicação web não consegue olhar, então a
interface continua mostrando a um agente o provedor que ele já tem configurado.

Essa mesma flag decide uma coisa na interface: a caixa **URL base**, tanto no
modelo principal quanto no reserva, é mostrada para um provedor auto-hospedado e
escondida para um de nuvem. `base.fInit` já recorre ao `cDefaultBaseUrl` do
adaptador, então, para um provedor de nuvem, o campo fazia uma pergunta que já
estava respondida antes de ser feita - e a única resposta que ele poderia
receber que o padrão não dá é uma errada. Ela é escondida e não esvaziada: uma
instalação que coloca um proxy na frente de um provedor de nuvem tem esse
endereço armazenado, e esconder uma caixa não é motivo para descartar o que há
nela.

Uma coisa que `base.py` esconde de todos eles é o nome de uma ferramenta. Este
projeto chama uma ferramenta de `family.action`; um provedor valida o nome de
uma função contra `^[a-zA-Z0-9_-]+$` e recusa a requisição inteira por causa do
ponto, sem nenhuma pista de qual campo estava errado. `fToolNameToWire` troca o
ponto por `__` na saída e `fToolNameFromWire` o destroca na entrada, em todos os
adaptadores, de modo que o registro, a interface, `info.json` e os logs nunca
veem a forma codificada.

### Tetos, não confiança

Toda execução para no primeiro de quatro tetos: tokens, passos, segundos,
execuções por dia. Eles existem porque um loop sem supervisão numa API paga é
uma fatura aberta e, num modelo auto-hospedado, uma GPU que nunca volta. O
`max_tokens` de cada requisição diminui conforme o que a execução já gastou,
então uma execução não consegue estourar o orçamento com uma última chamada
cara.

Quatro coisas fazem a diferença entre um teto e uma sugestão, e cada uma delas
estava do lado errado dessa diferença até ser corrigida:

  - **Nenhum piso sob o pedido de tokens.** `max(512, remaining)` pedia 512
    tokens quando o orçamento estava gasto, então um agente com um token
    restante ainda podia escrever meia página.
  - **Cada chamada recebe o tempo que RESTA**, não o timeout inteiro da
    execução. O próprio `vTimeoutSeconds` do adaptador é ajustado antes de cada
    chamada, em vez de acrescentar um parâmetro aos vinte e seis adaptadores
    que implementam `fSendMessages`.
  - **O prazo é verificado antes de cada ferramenta**, não uma vez por passo. Um
    lote de seis chamadas de ferramentas que chegava logo antes do prazo rodava
    inteiro, cada uma com o próprio timeout, por cima de uma execução que já
    tinha acabado.
  - **Um relógio monotônico.** `time.time()` se move quando o NTP o ajusta aos
    saltos, e uma execução que começou “no futuro” nunca chega ao timeout.

O que ainda não está limitado é o prompt. Uma chamada gasta a entrada mais a
saída e só a saída é limitada aqui, então uma conversa longa estoura na
entrada; contá-la significaria rodar o tokenizador de cada provedor sobre a
conversa antes de cada chamada. A resposta de encerramento depois de um teto
também fica, de propósito, acima do orçamento, e isso é dito onde ela é
escrita.

### Uma execução de cada agente por vez

Dois locks, porque há dois tipos de chamador.

O daemon mantém um `threading.Lock` por agente entre “este agente está rodando?”
e “iniciar o processo”. Ele atende cada requisição numa thread própria, então
duas chamadas `run_now` com `only_if_idle` eram duas threads de um mesmo
processo sem nada entre elas - e uma varredura de /proc não consegue ver um
processo que ainda não passou pelo fork. Medido: duas chamadas simultâneas, duas
execuções.

O runner pega um `flock` em `<home>/run.lock` e o mantém durante todo o
processo. Esse é a autoridade, porque um crontab inicia o runner diretamente e
nunca passa pelo daemon. Ele não é uma fronteira de permissão - um agente com
`bash.run` pode iniciar o que quiser -; existe para que a APLICAÇÃO não inicie o
mesmo agente duas vezes, gastando dois orçamentos num só perfil de navegador e
numa só conversa.

### Uma execução que nunca começou diz isso

O daemon privilegiado inicia o runner com stdin, stdout e stderr em
`/dev/null`. Tudo o que `fLogLine` escreve, portanto, não vai para lugar nenhum,
e duas falhas viviam inteiramente nessa saída:

- o lock da execução estava ocupado, então esta execução não vai acontecer;
- algo falhou antes de `fExecute` escrever `run_started` - um `info.json`
  ilegível, ou um provedor cuja chave de API não foi definida, que é de longe o
  mais provável dos dois.

Medido numa instalação real: com o lock ocupado, `POST /agents/001/run`
respondeu `202 {"started": true}` e nada apareceu no diário, no `journalctl` nem
em arquivo nenhum. A mesma falha sob o cron ERA visível, porque o cron guarda a
saída do que inicia - e é por isso que isso durou tanto quanto durou. O buraco
só existia no caminho que a interface usa.

`fRecordRunRefused` passa a escrever isso no diário, como um fim com status
`refused` e sem `run_id`. Cada parte desse formato é estrutural:

| Parte | Por quê |
|---|---|
| `kind: run_finished` | O Histórico renderiza fins. Um kind próprio exigiria que a interface o aprendesse, e uma entrada que nada renderiza é o mesmo que nenhuma entrada |
| `status: refused` | `failed_runs` conta os fins cujo status é `failed`. Nada do agente rodou, então nada do agente falhou |
| sem `run_started` | `runs` e `max_runs_per_day` contam inícios. Um lock ocupado não pode comer uma das execuções do dia por uma execução que não aconteceu |
| `run_id: ""` | Nada começou, então não há execução a identificar |

Escrito só quando nada mais o escreveu. Quando `fExecute` tem um id de execução,
ele já escreveu `run_started`, e os próprios handlers dele escrevem o
`run_finished` correspondente antes de relançar a exceção, então `fMain`
verifica `vRun.vRunId` antes de acrescentar um segundo fim para uma mesma
execução. A mesma verificação decide quem fecha o turno do chat: os handlers de
`fExecute` o fecham ao registrar o fim, e `fMain` o fecha só para uma execução
que nunca chegou até ali. Medido antes de ser assim, na máquina Debian de
testes: toda execução que não conseguia alcançar o provedor respondia à pergunta
duas vezes, com a mesma frase.

### O Histórico mostra o mais recente, e não mostrava

`fReadEntries` devolve um diário do mais antigo para o mais novo - a própria
docstring diz isso - e `fRenderRunHistory` pegava `.slice(0, cShownRuns)` dele.
Ou seja, as dez execuções MAIS ANTIGAS. Um agente com mais de dez execuções no
passado tinha um Histórico que nunca mais mudava.

Encontrado conduzindo a aplicação real com um navegador real, que é o único
jeito de isso ser encontrado: todos os outros testes de `dashboard.js` neste
projeto leem o arquivo e procuram uma string nele, e a string estava lá. Medido
numa instalação real, em três idiomas: um agente cuja execução mais recente
tinha acabado de ser recusada por falta de chave de API mostrava uma falha do
provedor de quarenta minutos antes, e a recusa nunca aparecia.

`.slice(-cShownRuns).reverse()`: as dez últimas, a mais nova no topo, que é o
que diz o título acima da lista.

A tabela de resumo acima dessa lista tinha dois defeitos próprios, os dois
encontrados na mesma captura de tela: ela imprimia `last_status` cru, então uma
página em espanhol dizia “Último estado: refused”, e imprimia `last_run_at` cru,
então um `2026-09-19T03:44:29Z` nu ficava logo acima de uma lista de timestamps
formatados. Os dois agora passam pelo que as linhas abaixo deles já usavam.

### Uma caixa de correio é a única entrada em que qualquer um pode escrever

As quatro ferramentas `mail.*` seguem exatamente os canais: o agente diz o que
quer que seja feito, e a API dos agentes - que roda como `boa` e guarda as
credenciais - faz. Um agente que pudesse ler a senha da caixa de correio não
teria “acesso à caixa de entrada”; teria a conta, todas as mensagens dela, para
sempre, e a capacidade de enviar como o dono.

O que o e-mail tem de diferente é a direção em que a entrada viaja. Um agente
que lê uma caixa de correio é um agente cujas instruções chegam, em parte,
dentro das mensagens que ele lê, escritas por qualquer pessoa no mundo. Daí
decorrem três decisões:

  - **Encaminhar só é permitido para endereços que o usuário listou**, e essa
    lista é verificada dentro de `mailbox`, no processo que abre a conexão -
    nunca no prompt. Uma regra num prompt é um conselho; uma regra no socket é
    uma regra. Sem lista, encaminhar é recusado de saída.
  - **Ler não marca nada como visto** (`BODY.PEEK[]` sobre um select somente
    leitura), para que um agente olhando uma caixa de correio não tire a
    contagem de não lidas com que a pessoa contava.
  - **Excluir move para a Lixeira** onde a conta tem uma. O que um agente
    remove por uma regra escrita no mês passado, uma pessoa ainda consegue
    encontrar. “Esta conta não tem pasta de lixeira” e “a lista de pastas não
    pôde ser lida” são mantidos separados, porque só o primeiro pode terminar
    num expunge: os dois chegavam a `fDeleteMessage` como a mesma string vazia,
    então uma linha LIST não interpretada transformava todo `mail.delete` num
    permanente.

### Vem com um agente, oferece muitos

A instalação cria exatamente um agente: o orquestrador. Todo o resto vem do “+”,
que oferece três pontos de partida: um agente VAZIO, um `.zip` exportado de um
agente, ou um MODELO do repositório de modelos. Uma instalação que chega com
agentes que ninguém pediu é uma que já começa com coisas para desligar.

Os modelos de agente vinham dentro deste repositório, um arquivo Markdown cada
um em `backend/agents/examples/`. Agora eles ficam num repositório próprio,
[bunch-of-aigents-templates](https://github.com/nipegun/bunch-of-aigents-templates),
clonado ao lado deste como `../bunch-of-aigents-templates`: um modelo novo
chega a toda instalação sem atualizar a aplicação, e uma instalação pode ser
apontada para um fork, ou para um repositório próprio, em Configurações ->
Agentes (`templates_repo_url`, `templates_repo_branch`, verificados por
`agent_templates.fValidateRepositoryUrl` e `fValidateBranch` ao salvar).
`agent_templates` baixa o repositório inteiro como o único `.tar.gz` em que um
branch é servido - o endereço de onde o instalador baixa a aplicação -, então
listar os modelos é uma requisição só, sem API do GitHub e sem limite de
taxa. Isso fica em cache por cinco minutos em cada worker web. Um endereço
`file://` com o mesmo layout `archive/refs/heads/<branch>.tar.gz` atende uma
máquina sem saída para fora.

**Um formato para tudo o que vira um agente** (`agent_package`): uma pasta com
`agent.json` e `system-prompt.md` e, opcionalmente, `memory.md`, `home/...` e
`rag/documents.json` com `rag/files/...`. A pasta de um modelo é um pacote
assim que traz só os dois primeiros; um `.zip` exportado é o mesmo layout com as
opções que o usuário marcou. Então instalar um modelo e importar um `.zip` são a
mesma função, `agent_io.fInstallPackage`, e qualquer coisa que possa ser
exportada pode ser publicada como modelo.

Tudo é verificado antes de um agente existir (`agent_package.fReadPackage`),
porque uma importação que falha no meio do caminho deixa um agente que ninguém
pediu:

- `agent.json` só pode conter as chaves de `lManifestKeys`, e `format` 1. Uma
  chave desconhecida é recusada em vez de ignorada: é um erro de digitação num
  modelo, ou um pacote de uma versão mais nova que esta interpretaria errado.
- Não há lugar no formato para `enabled`, para chaves, tokens ou credenciais de
  canais, nem para os canais que o agente escuta. Um agente importado é sempre
  criado desligado, e um provedor viaja só como nome, modelo e URL base -
  `api_key_ref` nunca.
- Os agendamentos são cinco campos do cron, nada mais
  (`agents.fValidateSchedule`), e são verificados DE NOVO em
  `exec_daemon.fVerbCreateAgent`. Um agendamento é escrito no início de uma
  linha de crontab, como root; um que trouxesse " /bin/sh -c ..." ou uma quebra
  de linha seria um comando. A verificação do processo web não basta: o
  executor é a fronteira.
- As ferramentas só são mantidas quando estão instaladas aqui, e as descartadas
  são listadas (`missing_tools`) para que o usuário as veja antes de confirmar.
  As habilidades são passadas como nomes e o executor mantém as instaladas, como
  antes.
- `rag` passa por `rag_settings.fValidateSettings`, como uma escrita da aba RAG,
  e os documentos da biblioteca têm de caber nos limites de arquivo e de
  armazenamento que o próprio pacote traz.
- Todo caminho do diretório pessoal passa por `agent_home.fValidatePath`:
  relativo, sem `..`, e nunca um nome de topo excluído (abaixo).
- Um `.zip` (`ZipSource`) é recusado com um nome de membro que sobe para fora,
  um link, um membro criptografado, um membro que se expande mais de 200:1
  acima de 1 MiB, ou mais de 8 GiB no total. Um arquivo compactado de
  repositório mantém só arquivos regulares; um link nele é pulado, não seguido.

Criar a partir de um modelo indica o MODELO e nada mais. O servidor o baixa e
lê: uma requisição que pudesse trazer as próprias ferramentas e o próprio
agendamento deixaria o navegador entregar a um agente uma permissão que o
usuário nunca marcou. O diálogo coloca o agente VAZIO primeiro, depois o `.zip`,
depois os modelos, cujas descrições vêm do `agent.json` de cada modelo no
idioma da interface (`fPickDescription`: esse idioma, senão en-US).

**Uma importação são três momentos**, porque uma biblioteca pode pesar centenas
de MiB e o HAProxy derruba uma requisição que não envia nada por 300 segundos: o
navegador envia o `.zip` em blocos para `/opt/boa/imports/<id>/` (`boa`, 0700,
criado pelos dois instaladores e listado em `ReadWritePaths` da unidade web);
`fFinishImport` o verifica inteiro e devolve o que ele instalaria; quando o
usuário confirma, `fStartImport` o instala numa thread do processo web, que
escreve o progresso em `job.json` para o navegador consultar. Qualquer worker
pode responder à consulta porque o estado é um arquivo. Um job cuja thread parou
de escrever por três minutos é lido como interrompido: o processo dele foi
reiniciado. Uma falha depois de o agente existir o exclui de novo
(`fInstallPackage`).

**Uma exportação é transmitida em streaming** (`fExportAgent`): o `.zip` é
escrito enquanto é enviado, então um agente com uma biblioteca de centenas de
MiB é exportado sem ser mantido em memória. Do crontab só viajam as linhas que
esta aplicação escreveu para rodar o agente, como os seus cinco campos
(`fReadSchedules`); qualquer outra linha é um comando que alguém digitou, e um
pacote que levasse comandos os rodaria na máquina onde chegasse.

**O diretório pessoal é lido e escrito como o agente** (`agent_home`, verbo do
executor `agent_home`): o executor inicia o módulo como o usuário do agente, do
mesmo jeito que inicia o worker do RAG, de modo que o root nunca percorre uma
árvore que o agente pode rearranjar, e um link plantado no diretório pessoal não
leva a lugar nenhum aonde o agente já não pudesse ir. Ficam de fora nas duas
direções: o que o sistema guarda ali (`chat.jsonl`, `runs.jsonl`, os registros
de chamadas à API, `run.lock`, `attachments/`), o que tem lugar próprio no
pacote (`memory.md`, `rag/`), o perfil do navegador com as sessões logadas, e
toda entrada oculta no topo do diretório pessoal. Um `.ssh/authorized_keys`
importado seria uma porta de entrada e um `.bashrc` roda código, e nenhum dos
dois vale o raro uso legítimo.

Um dos modelos, `web-navigator`, não tem crontab. É o do navegador - ele abre
páginas, faz login, clica e preenche formulários, enquanto os outros leem - e
esse trabalho é o que o usuário acabou de pedir, não algo para fazer às quatro
da manhã. O prompt dele é onde estão escritas as regras de que um navegador com
sessão precisa: nunca digitar uma credencial, nunca concluir uma compra ou um
envio, e tratar a página como dados e não como instruções.

`rag-consultant` também não tem crontab: ele responde a perguntas a partir da
própria biblioteca RAG. É o único modelo cujo `agent.json` diz
`"rag": {"enabled": true}`. O runner retém as ferramentas `rag.*` enquanto a
biblioteca de um agente está desligada, então sem isso o agente seria criado sem
ferramenta nenhuma. O `rag` do pacote chega a `exec_daemon.fVerbCreateAgent`
como `pRag` (o corpo da requisição nunca é lido para isso), onde passa por
`rag_settings.fValidateSettings`, a mesma verificação pela qual passam as
escritas da aba RAG: um modelo pode ligar a biblioteca e não pode dar a ela
nada que essa aba não pudesse. O `max_tokens_per_run` dele é 40000 porque o
runner dimensiona o orçamento de trechos como `max_tokens_per_run` menos prompt,
histórico e 4096; com o padrão de 16384 não sobraria espaço para trechos. O
prompt dele descreve as ferramentas como elas são - `rag.read` devolve um trecho
e os vizinhos dele, não um documento - e pede os marcadores `[rag:REF]` que
`fResolveCitations` verifica.

### Duas formas de servi-la, escolhidas na instalação

Ou 11080 e 11443 em localhost com um HAProxy na frente em 80 e 443, ou 80 e 443
servidos diretamente. O instalador pergunta, guarda a resposta em
`config/ports.conf`, e uma atualização nunca pergunta de novo nem muda em
silêncio as portas em que a máquina escuta.

A diferença não está só nos números: `accept-proxy` tem de sair do bind no modo
direto, porque um navegador que se conecta direto à 443 não envia cabeçalho
PROXY e um bind que exige um recusa todo cliente real.

No modo `direct`, o HAProxy da própria máquina não é simplesmente deixado em
paz: ele é aposentado. `fRetireMachineProxy` o para, tira-o de todos os
runlevels no Alpine, o desabilita **e mascara** no Debian, e depois apaga
`/etc/haproxy/haproxy.cfg` quando foi este instalador que o escreveu, ou o move
para `haproxy.cfg.before-boa.<date>` quando foi outra pessoa. Pará-lo não basta:
um que fique habilitado pega a 80 e a 443 no próximo boot, antes de esta
aplicação sequer rodar, e sob o systemd um upgrade de pacote, o `Wants=` de
outra unidade ou um simples `systemctl start` podem trazer de volta até um
desabilitado. Uma unidade mascarada não pode ser iniciada por nada, e um haproxy
sem `/etc/haproxy/haproxy.cfg` não tem de onde partir. O que ainda ocupar a 80
ou a 443 depois disso é citado no log, porque neste modo o proxy não consegue
iniciar sem elas, e deduzir isso de um “the application did not answer” meio
minuto depois é um jeito muito pior de descobrir.

O que de propósito NÃO é feito é remover o pacote haproxy. O `boa-proxy` É o
`/usr/sbin/haproxy` - ele termina o TLS e lê o cabeçalho PROXY na frente do
gunicorn, e no modo `direct` é justamente ele que faz bind na 80 e na 443 -,
então remover o pacote deixaria a aplicação sem nada escutando, em qualquer um
dos modos. O que é aposentado é o *serviço* HAProxy da máquina, que é outra
coisa que por acaso usa o mesmo binário. Voltar para `proxied` desmascara a
unidade antes de habilitá-la, senão o caminho de volta terminaria em “The
machine's HAProxy would not start” por causa de uma máscara que o próprio
instalador tinha colocado ali.

Medido nas duas máquinas de teste com `--update --ports direct`: a unidade
terminou mascarada no Debian e em nenhum runlevel no Alpine, `/etc/haproxy`
ficou sem configuração, e a aplicação respondeu 200 na 443 e 301 na 80. O
caminho de volta, `--update --ports proxied`, a deixou habilitada e ativa de
novo, com 200 na 11443 e na 443. Sete testes EXECUTAM a função contra comandos
de serviço falsos, sobre uma configuração com o marcador e outra sem, nos dois
modos, e um deles falha se uma versão futura algum dia recorrer a
`apk del haproxy` ou `apt-get purge haproxy`.

### Uma confirmação é mostrada onde o usuário está olhando

“Configurações salvas” era escrito no topo da coluna de conteúdo. Isso funciona
num painel curto e é inútil num longo: o botão Salvar no fim da aba Ferramentas
de um agente produzia uma mensagem várias telas acima dele, fora do que o
navegador estava desenhando, então salvar parecia não fazer nada.

Agora é um pop-up centralizado sobre a coluna de conteúdo, numa camada `fixed`
que é irmã dessa coluna e não filha dela. `fixed` é o ponto central: centralizar
dentro da coluna cairia no meio do *documento*, o que numa aba longa é o mesmo
bug algumas telas mais abaixo. A camada para na barra lateral, porque uma
mensagem desenhada sobre a lista de agentes pareceria pertencer à lista de
agentes, e ela não recebe eventos de ponteiro, então nada atrás dela deixa de
funcionar enquanto uma mensagem está à mostra.

Quanto tempo ela fica é uma preferência deste navegador (`boa.noticeSeconds`,
Configurações → Interface), ao lado do tema e do idioma e pelo mesmo motivo:
três segundos é muito para uma palavra e pouco para uma frase, e qual dos dois
uma mensagem é depende de quem a está lendo. Os erros são a exceção e ignoram
esse número por completo — um erro espera ser fechado, porque é a única
mensagem que tem de continuar lá quando o usuário voltar a olhar para a tela.

Uma mensagem tem três cores, e a terceira existe por causa do que as outras
duas não conseguem dizer. Verde é um salvamento que aconteceu, vermelho é uma
falha, e âmbar é **“Nenhuma alteração para salvar”**: Salvar foi apertado e o
formulário continha exatamente o que já está armazenado. Informar isso em verde
é pior do que não dizer nada - “Configurações salvas” depois de um salvamento
que não escreveu nada é justamente a frase que impediria alguém de perceber que
a sua edição nunca pegou - e o vermelho alegaria uma falha onde nada deu
errado.

Todo formulário que salva verifica isso do mesmo jeito: o payload que ele
*enviaria*, comparado como JSON com o snapshot tirado quando o formulário foi
preenchido a partir do servidor, ou depois do último salvamento. As
configurações de um agente montam esse payload numa só função,
`fCollectAgentPayload`, usada tanto para salvar quanto para tirar o snapshot,
porque dois leitores do mesmo formulário que se distanciassem informariam
“nenhuma alteração” justamente no campo que um deles nunca olhou. Os painéis de
preferências do navegador já guardavam um snapshot assim, para o aviso de
“alterações não salvas”, e ele responde a esta pergunta também.

A exceção é um agente **novo**: o formulário dele contém os valores do próprio
modelo de agente e nunca foi salvo, então apertar Salvar os escreve e segue para
o chat em vez de dizer que não há nada a fazer.

### A cor é estado, o movimento é atividade

O anel em volta do avatar de um agente carrega dois fatos diferentes e os
desenha em dois canais diferentes, para que nenhum precise ser consultado. Se o
agente está ligado é uma cor que não se move: verde ou vermelho. Se ele está
trabalhando agora é movimento: um segmento aceso percorre esse anel verde no
sentido horário. Uma segunda cor estática para “ocupado” seria uma convenção a
aprender, ao passo que algo girando é entendido sem ser ensinado.

Ele é desenhado como um retângulo arredondado em SVG colocado exatamente sobre
a borda, com um traço tracejado cujo offset é animado, de modo que **a forma
fica parada e só a luz se move ao longo dela**. Esse é todo o motivo do SVG:
girar um anel em vez disso — um gradiente cônico, um arco, qualquer coisa sob
`transform: rotate` — gira a forma também, e os cantos deixam de coincidir com o
quadrado arredondado embaixo. `pathLength="100"` normaliza o contorno, então a
folha de estilos fala em porcentagens do perímetro e nada precisa ser
recalculado se o avatar ou o raio dele mudar.

Responder “quem está ocupado?” significa ler a linha de comando de todo
processo, o que só o root pode fazer, então isso é um verbo do daemon
privilegiado. Uma varredura de `/proc` responde por todos os agentes de uma vez
— não uma chamada por agente — e é isso que a torna barata o bastante para a
barra lateral perguntar a cada cinco segundos. A mesma varredura sustenta
`only_if_idle`, então o buzzer e a interface não podem discordar sobre se um
agente está trabalhando.

### Um cartão que vence é anunciado na conversa

O chat de um agente é o registro de tudo o que se pediu àquele agente, não só
do que foi digitado para ele. Por isso, quando o buzzer inicia uma execução por
um cartão vencido, esse cartão é escrito no `chat.jsonl` do agente como um
turno próprio, e a resposta da execução o fecha: abrir a conversa mostra o
trabalho chegando, o que o agente fez a respeito e quanto custou.

Três decisões sustentam isso.

**Ele é escrito quando a execução começa, não quando o cartão é criado.** Um
cartão agendado para hoje à noite e excluído hoje à tarde nunca rodou, e uma
conversa dizendo que ele foi entregue seria o registro de algo que não
aconteceu. O buzzer só vê cartões que ainda estão no quadro, então escrever no
momento do aviso é o que torna o anúncio verdadeiro.

**O arquivo guarda os campos do cartão, não uma frase.** `role: "card"` leva o
id, o título, quem o atribuiu e se ele foi pedido para já; o texto da mensagem
são as próprias instruções do cartão. Cada palavra em volta delas é escrita
pela interface, no idioma do próprio usuário — a mesma regra que faz uma
execução interrompida registrar `ceiling: "tokens"` em vez de uma frase em
inglês.

**“Agora” e “às 13:45” têm de ser distinguidos, e quando o agente é acordado os
dois já estão no passado.** Por isso o quadro registra qual dos dois foi pedido
(`run_mode`) em vez de deduzi-lo depois pelo relógio, e a palavra `now` viaja do
navegador até `kanban.fValidateRunAt` como palavra, virando um timestamp no
único lugar que também registra o que ela era.

A escrita é trabalho do daemon privilegiado, não do buzzer: `chat.jsonl` fica
num diretório pessoal 0700 que pertence ao agente, e o buzzer roda como `boa`. O
daemon faz fork, desce para o agente, escreve o anúncio e só então inicia a
execução — e, se não for possível escrever no diretório pessoal, a execução
começa assim mesmo. O anúncio é o registro do trabalho, não o trabalho.

A falha inversa não é inofensiva e é tratada ao contrário: se o processo não
puder ser iniciado **depois** de o turno ter sido aberto, o daemon escreve a
falha nesse turno antes de lançar a exceção. Nada mais o fecharia, e um turno
aberto não deixa só um cartão sem resposta — ele fecha a caixa de mensagem
daquele agente para sempre.

A execução que vem em seguida não é nem uma execução agendada comum nem um
turno de chat. Ela escreve a resposta de volta no chat, porque a pergunta está
lá, mas a conversa **não** é reenviada para ela: o prompt dela é o cartão, e
reenviar dez trocas cobraria de toda execução agendada uma conversa que ninguém
está tendo. No runner essas são duas flags separadas — `vWritesToChat` e
`vIsChat` — e essa distinção é tudo. O corolário é que uma execução que para
antes de perguntar qualquer coisa ao modelo (um agente desligado, o teto
diário) ainda tem de fechar o turno, ou a interface espera uma resposta para
sempre e a caixa de mensagem continua fechada.

### A documentação da API é uma página desta aplicação

Ela é renderizada a partir da especificação OpenAPI que este projeto monta, em
vez de carregar o Swagger UI de uma CDN, porque o servidor de produção é uma
máquina de LAN que pode não ter saída nenhuma para a internet. Duas coisas
decorrem de ela ser uma das nossas próprias páginas e não um widget de fora.

Ela **segue o idioma escolhido**. A especificação fica em inglês - é o contrato
de uma API cujos nomes de campos, ids e strings de erro são todos en-US, e um
`openapi.json` traduzido descreveria uma API que não existe. O que é traduzido é
a página: `fAnnotateSpecForTranslation` pendura uma chave `data-i18n` em cada
pedaço de inglês antes de renderizar, e o navegador a troca do mesmo jeito que
faz em todas as outras páginas. Isso mantém as strings nos arquivos `.json` do
frontend junto com todas as outras, e funciona também para um leitor anônimo. As
chaves são derivadas do texto e do caminho em vez de escritas à mão, então um
endpoint novo traz as suas; uma chave sem tradução mantém o inglês, que é o que
`fApplyTranslations` faz com uma chave que não conhece.

Ela **ocupa a coluna que recebe**, como todas as outras páginas. Antes ela
mantinha uma largura de 900px e se centralizava, o que funciona bem para prosa e
mal para isto: a página é sobretudo tabelas de parâmetros e blocos de JSON, e
eles estavam sendo espremidos num terço de uma tela larga, com margens vazias
dos dois lados.

### Anexos de imagem são uma permissão explícita de ferramenta

`browser.screenshot` salva um arquivo; `image.send` o anexa à resposta atual.
Esta última é uma concessão separada, incluída no modelo web-navigator. A
ferramenta tira uma cópia do PNG para `agents/<id>/attachments/<opaque-id>.png`,
com diretório 0700 e arquivo 0600. Sobrescrever a captura de tela original
depois não muda uma resposta anterior. `ToolContext.lAttachments` leva as
referências para `AgentRun.fRecordChatAnswer` ou para o relatório de
falha/execução dele.

Só o executor lê esses arquivos privados para o processo web. O verbo
`read_chat_attachment` dele exige uma referência no chat registrado daquele
agente, abre cada componente de diretório sem seguir links e verifica que a
imagem é um arquivo regular de propriedade do agente. Ele lê os PNGs em blocos
de 1 MiB; as respostas em base64 ficam abaixo do limite de RPC existente mesmo
para um anexo de 50 MiB. O endpoint HTTP autenticado transmite os bytes em
streaming com `private, no-store`. O frontend monta as URLs locais das imagens a
partir de IDs, nunca de URLs fornecidas pelo modelo.

O Telegram usa [sendPhoto](https://core.telegram.org/bots/api#sendphoto) para as
imagens elegíveis e [sendDocument](https://core.telegram.org/bots/api#senddocument)
para capturas altas ou grandes, com o PNG original. O arquivo privado é enviado
como dados multipart; não é preciso nenhuma URL pública nem acesso do agente às
credenciais do bot. `telegram_deliveries` registra as partes de texto e de
imagem confirmadas de cada turno pendente. As novas tentativas retomam pela
parte que falta, e remover a linha pendente limpa esses checkpoints. As falhas
permanentes são informadas ao usuário. As duas caixas de entrada comparam os
timestamps UTC do SQLite com o horário Unix; interpretá-los como horário local
fazia entregas recentes expirarem durante o horário de verão.

### Sem etapa de build

O frontend são templates Jinja2, CSS puro e JavaScript puro. O alvo de produção
é uma máquina Debian ou Alpine auto-hospedada; uma implantação que precisa de um
toolchain Node para mudar uma folha de estilos é uma implantação que apodrece.
Pelo mesmo motivo, `/api/doc/` renderiza a própria especificação OpenAPI em vez
de carregar o Swagger UI de uma CDN: um servidor de LAN pode não ter saída para
a internet, e uma documentação que falha sem ela falha exatamente quando alguém
está depurando.

---

### Transcrição de áudio

Ao iniciar os serviços do OpenRC, o instalador fecha os descritores 3 e 4 nos comandos `rc-service`. Eles são os pipes de stdout/stderr do SSH que ele guardou: observou-se que o `supervise-daemon` os retinha depois de o instalador sair com sucesso. A saída comum continua sendo capturada em `install.log`.

`audio_transcription` guarda uma única configuração JSON validada em `settings.audio_transcription`. OpenAI, Groq, Mistral e Together usam multipart; Hugging Face e Cloudflare recebem WAV binário. Eles reutilizam `api_keys` sem devolver segredos ao navegador. O FFmpeg limita contêineres, protocolos, tamanho, duração e tempo de execução. O áudio é dividido em segmentos de 120 segundos (30 segundos para os endpoints crus da Hugging Face e da Cloudflare, para não depender de opções de geração de formato longo); o whisper.cpp e a decodificação rodam como `boa`, sem shell nem fallback automático de provedor.

`audio_inbox` persiste destino, configurações e transcrição no SQLite. Uma única thread em segundo plano, protegida por um lock de processo, em `boa-channel-telegram` recupera a fila depois de um reinício. Um ID de turno reservado permite ao executor confirmar um envio repetido antes de verificar se o agente está ocupado. Marcar o job como enviado e inserir `telegram_pending` acontecem numa só transação. O áudio privado fica em `/opt/boa/audio/` (0700, de propriedade de boa), exige tanto login quanto uma referência correspondente no chat para ser reproduzido, e é removido quando os turnos de chat concluídos são limpos.

Os dois instaladores compilam o whisper.cpp v1.9.4 depois de verificar o SHA-256 do arquivo de código-fonte e baixam o `base`. `whisper_models.json` contém os 30 nomes oficiais, com tamanhos e hashes. Só o executor root baixa modelos, por meio de `install_whisper_model`; URLs e caminhos arbitrários são rejeitados. Um arquivo parcial só fica visível depois da verificação do hash. O root é dono de `whisper/`; `boa` só o lê. As atualizações mantêm modelos e áudios; os backups incluem os áudios, mas excluem os pesos dos modelos. Um interpretador Python ausente é instalado junto com as dependências antes de verificar a versão mínima.

### Requisições cruas aos provedores e o espaço de trabalho do agente

`AgentRun.fSendRecordedRequest` acopla um gravador ao provedor selecionado para
aquela chamada, inclusive as chamadas ao modelo reserva e as de encerramento. Os
adaptadores baseados em Requests usam `BaseProvider.fPostJson`, que grava o
mesmo corpo JSON serializado antes de enviá-lo. Os clientes dos SDKs da OpenAI e
da Anthropic usam hooks de requisição, capturando o corpo preparado, incluindo
os campos do SDK e cada nova tentativa. O gravador nunca guarda cabeçalhos de
autenticação e nunca reconstrói uma requisição a partir do histórico do chat.

`api_calls` escreve um índice em `agents/<id>/api-calls.jsonl` e um corpo
completo `api-call-<id>.json` por requisição, com modo 0600 no diretório pessoal
privado do agente. A retenção remove requisições inteiras além das 100 mais
recentes. O executor só lê arquivos regulares de propriedade daquele agente,
rejeitando links simbólicos e FIFOs. Os corpos viajam em blocos limitados pelo
socket dele; a rota HTTP autenticada transmite o texto JSON original deles em
streaming sob `body`. O navegador formata os tokens sem interpretar números,
então inteiros grandes e escapes de string sobrevivem intactos.

O `info.json` protegido guarda `interface.show_api_calls`, falso por padrão. Ele
controla só a visibilidade; as requisições são gravadas com a aba visível ou
escondida. `dashboard.js` separa as abas de conversa das abas de configuração e
sempre seleciona Chat ao carregar um agente. Ele consulta os metadados das
requisições só enquanto API Calls está aberta, carregando os corpos completos
quando os detalhes deles são expandidos. O título das configurações identifica o
agente pelo id; Executar agora pertence ao espaço de trabalho, e a exclusão tem
um painel próprio dentro de Geral.

A caixa de mensagem fica fixada logo acima da barra de status e só `#vChatLog`
rola. Em larguras de desktop, `app.css` faz `.app` ter exatamente a altura de
uma viewport enquanto o chat é mostrado (`.app:has(#vChatPanel:not([hidden]))`)
e repassa a altura por uma coluna flex até `.chat`, então não há rolagem de
página em que o formulário se perca. De 820 px para baixo a página volta a rolar
como um bloco, e `.chat` é uma viewport menos `--status-bar-live-height`, que
`api.js:fTrackStatusBarHeight` mantém igual à altura real da barra com um
`ResizeObserver` - num celular a barra quebra em várias linhas, e um valor fixo
chutado deixava a caixa de texto embaixo dela. Não há linha de dica sob a caixa
de mensagem: `fSetComposerEnabled` a escreve como a segunda linha do placeholder
(como o Enter se comporta, ou que o agente está trabalhando), e
`fFitChatInputToPlaceholder` mede esse placeholder num gêmeo invisível e define
o `min-height` da caixa para que ele nunca seja cortado. Isso roda sempre que o
placeholder ou a largura da caixa de mensagem muda (`fTrackChatInputWidth`). As
alturas são definidas pelo CSSOM, nunca por um atributo `style`, que a CSP
descartaria.

### Compartilhamentos Samba por agente

`agents.dDefaultSambaSettings` define o compartilhamento ligado, leitura e
gravação, visível na lista, acesso autenticado e modos de arquivo/diretório
0600/0700. As senhas começam sem definição. `info.json.samba` é configuração
protegida; a senha só existe no passdb do Samba, privado do root. Ela vai para o
`smbpasswd` pelo stdin, nunca por argv, pelo modelo, pelo objeto devolvido pela
API ou por `info.json`.

`boa-samba` roda um smbd isolado na porta TCP 445, com configuração e estado
nativo em `/opt/boa/samba/`, que pertence ao root, e arquivos de runtime em
`/run/boa-samba/`. Ele não tem serviço homes. O nome de um compartilhamento é
derivado de `fGetAgentSystemUser`; o caminho dele é sempre `<agent home>/samba`.
A autenticação usa essa conta, e as operações de arquivo usam o uid daquele
agente. O acesso de convidado exige uma configuração explícita por agente. O
instalador se recusa a assumir uma instalação do Samba não relacionada e
desabilita a instância padrão da distribuição só para a própria instalação do
BoA.

O executor cria a pasta depois de criar/indexar um agente e remove o
compartilhamento/conta antes de excluir o usuário. Os dois instaladores
reconciliam os agentes existentes depois de instalação/atualização/restauração.
Um lock exclusivo de arquivo serializa as mudanças; `testparm` valida antes da
substituição atômica da configuração. `smbcontrol` recarrega a configuração e
fecha só as conexões do compartilhamento alterado. Desativar o compartilhamento
de um agente é independente do interruptor de execução do agente.

A preparação da pasta usa descritores de diretório com `O_NOFOLLOW` e
verificações de propriedade. O Samba recusa links dentro do compartilhamento, e
uma guarda preexec do root verifica de novo a raiz do compartilhamento a cada
conexão. A guarda roda o código Python confiável com `-I`, de modo que o
diretório de trabalho de um agente não consegue fornecer módulos importados.

Os backups incluem os arquivos compartilhados por meio do arquivo tar normal do
diretório pessoal do agente e as configurações por meio do arquivo info
protegido. `tdbbackup` tira um snapshot do banco de senhas nativo enquanto ele
está em uso; o backup também guarda o SID do servidor. A restauração exige o
smbd parado, valida um banco temporário e o substitui em vez de mesclar as
credenciais atuais. Exportar pelo antigo formato smbpasswd era rejeitado por
alguns RIDs de contas nativas e não é usado. `fVerifyInstallation` lê o modo de
portas web salvo para que a restauração verifique a porta HTTPS real, inclusive
no modo direto sem uma flag `--ports` explícita.

Referência: [opções de compartilhamento do Samba](https://www.samba.org/samba/docs/current/man-html/smb.conf.5),
[ferramenta de backup do TDB](https://www.samba.org/samba/docs/3.6/man-html/tdbbackup.8.html).

### Recuperação local de documentos

O rótulo da aba é `RAG` em todos os idiomas, inclusive nos fallbacks de HTML e JavaScript.

`rag_store` é dono do catálogo por agente (SQLite WAL, FTS5, documentos,
revisões e offsets de envio). Os nomes originais são metadados; os nomes dos
arquivos em disco usam identificadores gerados. `rag_extract` lê
PDFs/EPUB/TXT/Markdown e chama o Poppler e o Tesseract locais para o OCR. Ele
preserva as localizações de página/capítulo e verifica os tamanhos expandidos
dos EPUB antes de interpretá-los. `rag_embeddings` usa só `AF_UNIX`, com o
caminho fixo `/run/boa-embeddings/engine.sock`: sem nome de host, proxy ou
fallback para a nuvem.

As **Informações do documento** editáveis de um documento são, na ordem em que o
formulário as mostra (`rag_store.lMetadataKeys`, com a qual `fAction` também
confere): ano de publicação, título, subtítulo, autor(es), versão, idioma e
etiquetas. A lista de documentos mostra o subtítulo, quando há um, logo abaixo
do título. O ano é guardado como texto (vazio ou com até quatro dígitos) para
que “desconhecido” continue diferente de um número. `rag_store.fMigrate`
acrescenta as colunas listadas em `rag_store.lAddedColumns`, as introduzidas
depois de já existirem catálogos (`year` e `subtitle` até agora):
`CREATE TABLE IF NOT EXISTS` nunca altera uma tabela existente, e tanto as
bibliotecas mais antigas quanto os backups restaurados trazem o schema antigo.
`rag_search.fSource` coloca subtítulo, ano, autor, versão e idioma em todo
trecho, para que o modelo consiga distinguir documentos que compartilham um
título, datar e atribuir uma citação e ponderar duas edições que discordam, sem
uma chamada extra a `rag.list`. Os links de citação e a busca na biblioteca
mantêm só o título e a localização: eles indicam um lugar, e o subtítulo só
deixaria o link mais longo.

`rag_models.json` é o catálogo de modelos de vetorização: para cada um, a URL
fixada e o SHA-256, as dimensões, o contexto, o pooling, os prefixos de consulta
e de trecho, e as duas similaridades medidas para ele (`min_support` para o modo
verificado, `min_similarity` para o piso da busca). Vêm dois: EmbeddingGemma
300M Q8 (o `default`; 768 dimensões, mean pooling) e Qwen3-Embedding 0.6B Q8
(1024 dimensões, last-token pooling, uma instrução em inglês antes de cada
consulta e nada antes de um trecho). O que está em uso é `model` nas
configurações de runtime (`/opt/boa/rag-runtime/settings.json`, escrito pelo
root e legível por todo agente), lido por `rag_settings.fSelectedModel` e
`rag_embeddings.fModel`. `rag_runtime` instala os pesos - o instalador, o modelo
selecionado; o executor, qualquer outro sob pedido (`install_rag_model`, um
download por vez numa thread, com o progresso em
`rag-runtime/status/<id>.json`) - e um arquivo só recebe o nome definitivo
depois que o tamanho e o SHA-256 conferem. Ele inicia o llama.cpp v0.5.0 com o
pooling do modelo e com o id do modelo como `--alias`. O acesso à rede pertence
só à instalação. O runtime usa o tokenizador e os prefixos de recuperação do
modelo e rejeita entradas grandes demais. O SQLite guarda texto e vetores; o
USearch guarda gerações incrementais de HNSW. Publicar uma revisão troca
atomicamente a visibilidade no catálogo e o nome do índice.

Há um só motor, então o modelo é escolhido para a máquina inteira, e é o
executor root que faz a troca (`rag_exec.fRuntime`): ele recusa pesos que não
estão no disco, salva a escolha, move a `min_similarity` de todo agente que
ainda estava na recomendação do modelo antigo para a do novo
(`fFollowModelSimilarity`; um valor que alguém escolheu fica) e reinicia o
`boa-embeddings`. Nenhum vetor é considerado confiável só com base no arquivo de
configurações. `rag_embeddings.fEmbed` pergunta ao motor qual modelo ele serve
(`/v1/models`, o alias) antes de vetorizar, e lança `EngineUnavailable` quando
não é o esperado ou quando um vetor tem o número errado de dimensões; um job de
indexação passa o modelo com que começou, então uma troca no meio do caminho
para o job em vez de misturar dois espaços vetoriais numa revisão. Cada
documento registra a impressão digital do modelo por trás da revisão publicada
dele (`documents.model`). Na passada seguinte, `rag_worker.fWork` vê que o
modelo da biblioteca não é o selecionado (`fFollowNewModel`): descarta os
trechos das revisões não terminadas, põe de novo na fila todo documento
indexado com outro modelo e esquece o índice. As revisões publicadas ficam. Até
chegar a vez dele, um documento é encontrado só pelo FTS5: `fSearch` monta os
rankings vetoriais apenas a partir dos documentos do modelo em uso - pelo índice
novo, ou comparando os vetores armazenados um a um enquanto não há índice - e
acrescenta um `notice` dizendo quantos documentos estão esperando. O mesmo
fallback por palavras-chave responde a uma busca enquanto o motor reinicia.
`rag_verify` fixa um só modelo para os dois lados da comparação e tira o limiar
desse modelo.

`boa-rag` roda como boa e pede ao executor existente que lance comandos de
worker fixos. `rag_exec` abre mão de UID/GID antes de qualquer operação com
documentos ou com o SQLite; o root nunca interpreta um livro nem abre o catálogo
de um agente. Os workers usam um lock do sistema operacional, limites de
recursos e estados persistentes. As RPCs de envio são blocos de 256 KiB, as de
download, blocos de 1 MiB; livros inteiros nunca atravessam o protocolo do
executor como uma única mensagem. O worker mantém a revisão anterior pesquisável
e retoma os trechos concluídos depois de uma interrupção. As configurações ficam
na configuração protegida do agente.

Uma queda do motor não é um erro do documento. `rag_embeddings` lança
`EngineUnavailable` (um `ValueError`) quando o socket falha ou o motor responde
503 enquanto carrega o modelo; qualquer outra recusa continua sendo um
`ValueError` comum. `fIndexDocument` trata a queda à parte: o documento volta
para `queued` com a MESMA revisão, mantém todos os trechos já vetorizados e
mostra o motivo até um job rodar de novo. O comportamento antigo - `error` e os
trechos da revisão apagados - perdia horas de um livro grande a cada
`--update`, porque o instalador para o `boa-embeddings` enquanto um worker
lançado pelo `boa-exec` ainda está rodando. `fWork` testa o motor
(`fIsAvailable`) antes de começar cada documento na fila e encerra o lote diante
de uma queda; do contrário, cada passada de 5 segundos do agendador extrairia ou
faria o OCR do documento inteiro só para parar no primeiro trecho.

`rag_search` combina os rankings do FTS5 e os semânticos; as buscas filtradas
avaliam o subconjunto selecionado. O runner faz a recuperação antes da chamada
de resposta e concede as três ferramentas RAG somente leitura só quando o RAG
está ativado. As fontes são limitadas pelo orçamento de texto configurado e por
uma estimativa conservadora de tokens da execução. Os marcadores de citação só
se resolvem contra fontes realmente devolvidas durante a execução. O provedor da
resposta pode ser remoto: o processamento só local se aplica à vetorização.

Os três modos de resposta diferem no que o RUNNER impõe, não só no que o prompt
diz. `mixed` deixa o modelo acrescentar conhecimento geral. Em `documental` e
`verified` (`runner.lRagModesThatSearch`) o modelo tem de chamar `rag.search`
ele mesmo: `fCheckRagAnswer` devolve, uma vez, uma resposta final dada sem isso
(`cRagSearchFirstPrompt`). A busca do próprio runner é a última mensagem do
usuário palavra por palavra, e numa conversa (“e na segunda edição?”) isso não
encontra nada onde a consulta do modelo, escrita com a conversa inteira à vista,
encontra. Pelo mesmo motivo, uma busca vazia não encerra mais a execução
documental antes de o modelo ser consultado; a garantia passou para o fim:
`fFinishRagAnswer` substitui a resposta de uma execução que não recuperou trecho
nenhum por uma frase fixa. `tool_choice` não é usado para forçar a busca: dos 29
adaptadores, alguns enviam `auto`, a Cohere não envia nada e a Mistral usa
`any`, então só o runner consegue impor isso a todos os provedores.

`verified` acrescenta `rag_verify`. A resposta é cortada em unidades -
parágrafos, e cada item de lista separado, com um bloco de código delimitado
anexado ao parágrafo anterior e comparado junto com ele (a introdução de um
exemplo sozinha não diz quase nada, e exemplos fiéis eram removidos por isso);
títulos, rótulos curtos terminados em “:” e separadores ficam isentos. Uma
unidade precisa de um `[rag:REF]` entre os trechos recuperados na execução e, a
não ser que seja uma referência solta, tem de estar perto de um deles: a
unidade vetorizada como consulta contra os trechos vetorizados como documentos,
a mesma distância que a busca usa, no `min_support` do modelo (0,36 para o
EmbeddingGemma, 0,44 para o Qwen3-Embedding). A primeira resposta reprovada
volta uma vez com as unidades reprovadas (`fBuildCorrectionPrompt`); depois
disso elas são removidas e uma linha localizada diz quantas. Se não sobrar nada
sustentado, sai a frase fixa; um motor que não pode ser alcançado retém a
resposta (fail closed). As frases fixas (`rag_verify.dFixedTexts`) estão no
idioma em que o prompt de sistema mandou responder, reconhecido pela linha dele
em `dAnswerLanguageLines`, e em inglês nos outros casos. O limite da verificação
é medido e escrito ao lado dela. Em 138 parágrafos fiéis e 2.652 citações a
trechos de outro assunto, nenhum limiar separa os dois com nenhum dos modelos;
os que estão em uso removem cerca de 6% dos parágrafos fiéis (sobretudo itens
curtos de lista e resumos de uma linha) e deixam passar menos de 1% dessas
citações erradas. Uma citação a um trecho do mesmo assunto passa cerca de um
quarto das vezes, e um parágrafo que contradiz o seu trecho pontua como um fiel:
o que a verificação pega é uma citação a um trecho sobre outra coisa, e um
parágrafo sem fonte.

O backup cria snapshots sob diretórios pais de preparação que pertencem ao root,
deixa o processo filho do agente fazer um backup do SQLite e criar hard links
dos arquivos imutáveis selecionados, e depois arquiva esse snapshot. Isso mantém
consistentes o WAL e as gerações do HNSW e evita que o root percorra uma árvore
de snapshot que o agente possa trocar. A restauração cancela envios parciais e
põe de novo na fila as indexações interrompidas. As impressões digitais dos
índices continuam disponíveis para reconstruções.

## 2. Mapa de módulos

| Módulo | Caminho | Responsabilidade | Depende de | Usado por |
|---|---|---|---|---|
| `audio_transcription` | `backend/core/audio_transcription.py` | Configurações de fala e motores de reconhecimento | db, api_keys, whisper_runtime | audio_inbox, api |
| `audio_inbox` | `backend/core/audio_inbox.py` | Fila durável, roteamento, novas tentativas e reprodução privada | db, exec_client, audio_transcription | telegram_listener, api |
| `whisper_runtime` | `backend/core/whisper_runtime.py` | Catálogo, estado e downloads verificados de modelos | paths, whisper_models.json | instalador, exec_daemon, api |
| `settings_audio.js` | `frontend/static/js/settings_audio.js` | Formulário de áudio, downloads de modelos e progresso | api.js, i18n.js | settings.js, settings_audio.html |
| `rag_store` | `backend/core/rag_store.py` | Catálogo, envios, revisões e snapshots | `rag_settings` | `rag_worker, rag_search` |
| `rag_extract` | `backend/core/rag_extract.py` | Extração local de PDF/EPUB/texto e OCR | `rag_embeddings, pypdf, EbookLib` | `rag_worker` |
| `rag_embeddings` | `backend/core/rag_embeddings.py` | Tokenizador e cliente de vetorização via socket local; recusa um vetor de qualquer modelo que não seja o esperado | `rag_settings` | `rag_extract, rag_search, rag_worker, rag_verify` |
| `rag_search` | `backend/core/rag_search.py` | Busca híbrida, publicação do HNSW e citações | `rag_store, usearch, numpy` | `runner, tools` |
| `rag_worker` | `backend/core/rag_worker.py` | Jobs de indexação duráveis, de propriedade do agente | `rag_store, rag_extract, rag_search` | `rag_exec` |
| `rag_verify` | `backend/core/rag_verify.py` | Verifica cada parágrafo de uma resposta contra os trechos que ele cita; as frases fixas do RAG em 15 idiomas | `rag_embeddings` | `runner` |
| `rag_exec` | `backend/core/rag_exec.py` | Descida de privilégios e comandos de worker fixos | `paths, rag_settings` | `exec_daemon` |
| `rag_runtime` | `backend/core/rag_runtime.py` | Instalação e downloads verificados de modelos, motor local, estado e preparação da restauração | `rag_settings, rag_embeddings` | `installers, boa-embeddings, rag_exec, exec_daemon` |
| `rag_models.json` | `backend/core/rag_models.json` | Os modelos de vetorização: pesos, hashes, pooling, prefixos e as similaridades medidas para cada um | — | `rag_settings` |
| `rag_scheduler` | `backend/core/rag_scheduler.py` | Polling justo da fila | `agents, exec_client` | `boa-rag` |
| `paths` | `backend/core/paths.py` | Todos os caminhos do sistema de arquivos e a validação do id de agente | — | tudo |
| `db` | `backend/core/db.py` | Conexões SQLite e os dois schemas | `paths` | `agents`, `kanban`, `auth`, `bootstrap` |
| `agents` | `backend/core/agents.py` | Modelo de dados do agente, `info.json` (incluindo as configurações do Samba), índice de agentes, hash de tokens | `db`, `paths` | `exec_daemon`, `agent_api`, `api` |
| `bootstrap` | `backend/core/bootstrap.py` | Inicialização da primeira execução | `agents`, `db`, `paths` | instalador |
| `exec_protocol` | `backend/core/exec_protocol.py` | Protocolo de comunicação e lista de verbos | — | `exec_daemon`, `exec_client`, `agent_api` |
| `exec_daemon` | `backend/core/exec_daemon.py` | O daemon privilegiado (root) | `agents`, `paths`, `run_journal`, `api_calls`, `samba` | serviço `boa-exec` |
| `exec_client` | `backend/core/exec_client.py` | Cliente do anterior | `exec_protocol`, `paths` | `web/api` |
| `agent_api` | `backend/core/agent_api.py` | O daemon com que os agentes falam | `agents`, `kanban`, `channels` | serviço `boa-agent-api` |
| `agent_api_client` | `backend/core/agent_api_client.py` | Cliente do anterior | `agent_api`, `exec_protocol` | as ferramentas distribuídas |
| `runner` | `backend/core/runner.py` | Uma execução de agente: o loop e os tetos dele | `providers`, `tool_registry`, `run_journal`, `api_calls` | cron, `exec_daemon` |
| `run_journal` | `backend/core/run_journal.py` | `runs.jsonl` por agente | `paths` | `runner`, `exec_daemon` |
| `api_calls` | `backend/core/api_calls.py` | Corpos exatos das requisições, índice privado, retenção e leituras limitadas | `paths`, `run_journal` | `runner`, `exec_daemon` |
| `dashboard.js` | `frontend/static/js/dashboard.js` | Espaço de trabalho Chat/API Calls, configurações do agente e renderização sob demanda das requisições | `api.js`, `jsonhighlight.js`, `markdown.js` | `dashboard.html` |
| `chat` | `backend/core/chat.py` | `chat.jsonl` por agente e a conversa reenviada ao modelo | `paths` | `runner`, `exec_daemon` |
| `memory` | `backend/core/memory.py` | `memory.md` por agente, limite de caracteres configurável e escritas completas; carregada no prompt de sistema de toda execução | `agents`, `paths` | `runner`, `exec_daemon`, `web/api`, ferramentas |
| `skills` | `backend/core/skills.py` | Os procedimentos compartilhados em `/opt/boa/skills/`, um diretório para cada um. Interpreta `SKILL.md`, monta o índice que vai no prompt e diz quais das habilidades de um agente ainda existem | `paths` | `runner`, `exec_daemon`, `web/api`, `skill.read` |
| `provider_models` | `backend/core/provider_models.py` | Catálogos de modelos a partir de `config/providers/*.json` | `paths` | `web/api` |
| `api_keys` | `backend/core/api_keys.py` | As chaves compartilhadas dos provedores em `config/apikeys/*.key`, escritas com 0600 num diretório 0700. Nunca devolve uma chave ao navegador, só se há uma armazenada e os quatro últimos caracteres dela | `paths` | `agent_api`, `web/api` |
| `tool_registry` | `backend/core/tool_registry.py` | Descoberta, permissões e despacho das ferramentas | `paths` | `runner`, `web/api` |
| `attachments` | `backend/core/attachments.py` | Snapshots privados de PNG, IDs opacos, propriedade de arquivo verificada e leituras limitadas | `paths` | `image_send`, `exec_daemon`, `exec_client`, `telegram_listener` |
| `image_send` | `backend/tools/image_send.py` | Anexa à resposta um PNG do próprio agente por meio do contexto da ferramenta | `attachments`, `tool_registry` | `runner` |
| `public_url` | `backend/core/public_url.py` | Se uma URL dada a um agente resolve para um endereço público. Formulado em termos positivos com `is_global` mais uma recusa explícita de multicast, porque uma lista de faixas a recusar é uma lista em que se esquece uma - e 100.64.0.0/10 ficou de fora dela | — | `web.fetch`, `rss.fetch`, `browser` |
| `agent_scripts` | `backend/core/agent_scripts.py` | Scripts que um agente escreve para si mesmo, e as linhas de cron que os rodam. Valida nomes e agendamentos, e nunca reescreve a linha de despertar | `paths` | `script.*`, `cron.*` |
| `kanban` | `backend/core/kanban.py` | O quadro e o histórico dele | `db` | `agent_api`, `web/api` |
| `channels` | `backend/core/channels.py` | Telegram, Discord, Mattermost, X. Envio para os quatro; leitura para os dois aos quais se pode responder | `paths`, `telegram_html`, `discord_markdown` | `agent_api`, `web/api`, os dois listeners |
| `agent_routing` | `backend/core/agent_routing.py` | O que os dois listeners fazem igual: a lista de agentes, ler o nome de um agente numa mensagem, a resposta fechada de um turno, o relatório de estado | `agents`, `chat`, `exec_client`, `system_info` | `telegram_listener`, `discord_listener` |
| `providers.base` | `backend/providers/base.py` | Interface dos adaptadores e formato neutro de mensagem | — | todos os adaptadores |
| `providers.factory` | `backend/providers/factory.py` | Nome do provedor → classe do adaptador | `providers.base` | `runner`, `web/api` |
| `providers.openai_dialect` | `backend/providers/openai_dialect.py` | A requisição chat/completions que os adaptadores do dialeto OpenAI compartilham; as peculiaridades ficam em cada adaptador | `providers.base` | a maioria dos adaptadores |
| `providers.*` | `backend/providers/<name>.py` | Um adaptador por provedor | `providers.base`, `providers.openai_dialect` | `factory` |
| `web.server` | `backend/web/server.py` | Factory do Flask, chave de sessão, cabeçalhos de segurança | `db`, `web.*` | gunicorn |
| `deploy/haproxy/boa.cfg` | `deploy/haproxy/boa.cfg` | Terminação TLS, PROXY protocol, 11080 → 11443 | — | serviço `boa-proxy` |
| `web.auth` | `backend/web/auth.py` | Login, sessões, limite de tentativas | `db` | `web.api`, `web.views` |
| `web.api` | `backend/web/api.py` | Tudo sob `/api/admin/` | `exec_client`, `kanban`, `channels` | navegador |
| `web.api_doc` | `backend/web/api_doc.py` | Especificação OpenAPI e a página dela. Anota a especificação com chaves i18n só para a página, nunca para `openapi.json` | `channels`, `providers.factory` | navegador |
| `web.views` | `backend/web/views.py` | As páginas HTML | `web.auth` | navegador |
| `buzzer` | `backend/core/buzzer.py` | Vigia o quadro e inicia uma execução quando um cartão vence | `kanban`, `exec_client` | serviço `boa-buzzer` |
| `telegram_listener` | `backend/core/telegram_listener.py` | Faz long polling no Telegram, encaminha cada mensagem a um agente, devolve a resposta | `channels`, `exec_client`, `telegram_inbox` | serviço `boa-channel-telegram` |
| `telegram_inbox` | `backend/core/telegram_inbox.py` | Qual agente disse o quê no Telegram, e quais perguntas ainda estão sendo respondidas. A expiração é calculada em UTC | `db` | `telegram_listener`, `agent_api` |
| `discord_listener` | `backend/core/discord_listener.py` | Faz polling de um canal do Discord, encaminha cada mensagem a um agente, devolve a resposta | `agent_routing`, `channels`, `exec_client`, `discord_inbox` | serviço `boa-channel-discord` |
| `discord_inbox` | `backend/core/discord_inbox.py` | As mesmas duas tabelas para o Discord. Separadas das do Telegram: um snowflake é uma string, e um listener não pode conseguir responder às perguntas do outro. A expiração é calculada em UTC | `db` | `discord_listener`, `agent_api` |
| `discord_markdown` | `backend/core/discord_markdown.py` | Markdown convertido no que o Discord renderiza, cortado em mensagens de 2000 caracteres. As tabelas viram blocos delimitados; um bloco dentro do qual cai um corte é fechado e aberto de novo | `telegram_html` (os padrões de bloco) | `channels` |
| `discord_texts` | `backend/core/discord_texts.py` | As três frases que o Discord diz de outro jeito. Todo o resto cai em `telegram_texts`, então um só catálogo serve os dois bots | `telegram_texts` | `discord_listener` |
| `browser` | `backend/core/browser.py` | O navegador compartilhado e o perfil próprio deste agente. Um handle durante toda a execução, fechado pelo `atexit`. Carrega a política de rede pela qual passa toda requisição | `paths`, `public_url` | as cinco ferramentas `browser.*` |
| `telegram_html` | `backend/core/telegram_html.py` | Markdown convertido nas catorze tags que o Telegram aceita. Os mesmos padrões de `markdown.js`, para que os dois renderizadores concordem sobre o que é markdown | — | `channels` |
| `telegram_texts` | `backend/core/telegram_texts.py` | O que o próprio bot diz, no idioma configurado para a instalação | `db` | `telegram_listener` |
| `markdown.js` | `frontend/static/js/markdown.js` | Renderiza a resposta de um agente como nós do DOM, nunca como marcação | — | `dashboard.js` |
| `jsonhighlight.js` | `frontend/static/js/jsonhighlight.js` | Formata JSON cru sem arredondar números e o colore usando nós do DOM seguros | — | `api_doc.html`, `dashboard.html` |
| `themes` | `backend/core/themes.py` | Lista as folhas de estilo em `frontend/themes/` e lê os cabeçalhos delas | `paths` | `web/api`, `web/views` |
| `agent_templates` | `backend/core/agent_templates.py` | Baixa o repositório de modelos (configurações `templates_repo_url`, `templates_repo_branch`) como um único `.tar.gz`, guarda-o em cache por cinco minutos e lista ou lê os modelos dele | `agent_package`, `db` | `web/api` |
| `agent_package` | `backend/core/agent_package.py` | A forma portátil de um agente: lê um `.zip`, um arquivo compactado de repositório ou uma pasta, e verifica tudo antes de um agente existir | `agent_home`, `agents`, `memory`, `rag_settings`, `rag_store`, `skills` | `agent_templates`, `agent_io` |
| `agent_io` | `backend/core/agent_io.py` | Instala um pacote, roda importações de `.zip` em segundo plano com `job.json`, transmite exportações em streaming | `agent_package`, `exec_client`, `tool_registry` | `web/api`, `web/agent_io_api` |
| `agent_home` | `backend/core/agent_home.py` | Lista, lê e escreve os arquivos do diretório pessoal de um agente como o agente; o verbo `agent_home` do executor | `paths` | `exec_daemon`, `agent_package` |
| `agent_io_api` | `backend/web/agent_io_api.py` | `/agent-imports/...` e `/agents/<id>/export...` | `agent_io` | `server` |
| `agent_export.js` | `frontend/static/js/agent_export.js` | A aba Exportar: o que cada opção acrescenta, e o link de download | `api.js` | `dashboard.html` |
| `mailbox` | `backend/core/mailbox.py` | IMAP e SMTP para a caixa de correio configurada. Guarda as credenciais para que os agentes nunca as tenham. Identifica uma mensagem por UID e UIDVALIDITY, nunca pela posição dela na pasta | `db` | `agent_api` |
| `theme.js` | `frontend/static/js/theme.js` | Acrescenta a folha de estilos do tema escolhido, a partir do head, antes da primeira pintura | — | todas as páginas |
| `night-high-contrast.css` | `frontend/themes/night-high-contrast.css` | Preenche o agente selecionado com cinza e desenha as abas selecionadas com um contorno fechado unido à linha de base | `app.css` | `theme.js` |
| `settings.js` | `frontend/static/js/settings.js` | Carrega as abas principais de configurações com seletores restritos à própria barra de abas; `fRenderChannelForms` marca os canais configurados com `data-state="good"`, compartilhando o estilo do estado das chaves de API e o `--colour-ok` do tema | `api.js`, `i18n.js`, `tools.js`, `app.css` | `settings.html` |
| `tools.js` | `frontend/static/js/tools.js` | Carrega o catálogo dentro de Configurações → Ferramentas; mantém a subaba no parâmetro `family` da URL e atualiza os rótulos dela ao voltar de Interface | `api.js`, `i18n.js` | `settings.js`, `settings_tools.html` |
| `app.css` | `frontend/static/css/app.css` | A classe `system-table` compartilha um layout de duas colunas, com 35% para os rótulos, para que os valores da máquina e os estados dos serviços fiquem alinhados; `.chat-attachment img` ocupa 100% da largura do texto, com altura automática e sem limite; `.chat-audio` se ajusta à largura da mensagem e o título dele herda a cor do texto da mensagem | — | `settings.html`, `dashboard.html` |
| `system_info` | `backend/core/system_info.py` | Estado da máquina e nomes dos serviços para o sistema de init em uso | `paths` | `web/api`, `agent_routing` |
| `samba` | `backend/core/samba.py` | Ciclo de vida dos compartilhamentos, validação, credenciais nativas, pastas protegidas e backups | `agents`, `paths`, comandos do Samba | `exec_daemon`, instaladores |
| `samba.js` | `frontend/static/js/samba.js` | Formulário Samba carregado sob demanda, campo secreto e snapshot por agente | `api.js`, `dashboard.js` | `dashboard.html` |

---

## 3. Índice de símbolos-chave

Só os símbolos públicos e estruturais. Os números de linha mudam; o arquivo e o
comportamento são aquilo em que confiar.

### Caminhos e identidade

| Símbolo | Arquivo:linha | O que faz |
|---|---|---|
| `fNormalizeAgentId` | `backend/core/paths.py:164` | Valida um id de agente e o completa com zeros à esquerda. **Todo caminho montado a partir de entrada do usuário passa por aqui.** Lança exceção para qualquer coisa fora de 0–999 |
| `fGetAgentHome` | `backend/core/paths.py:179` | `/opt/boa/agents/xxx` |
| `fReadAgentOwnedFile` | `backend/core/paths.py:401` | Como o root lê um arquivo do diretório pessoal de um agente: sobre o descritor aberto, regular e do próprio agente ou recusado, nunca mais do que um limite. O diário, o chat e a memória passam todos por ele |
| `fGetAgentApiTokenPath` | `backend/core/paths.py:485` | Onde fica o token de API de um agente |

### Agentes

| Símbolo | Arquivo:linha | O que faz |
|---|---|---|
| `fValidateAgentName` | `backend/core/agents.py:71` | 2–40 caracteres, sem metacaracteres de shell |
| `fGetNextFreeAgentId` | `backend/core/agents.py:137` | O menor id livre segundo o sistema de arquivos, começando em 001 |
| `fBuildAgentInfo` | `backend/core/agents.py:150` | O `info.json` de um agente novo, com padrões conservadores |
| `fWriteAgentInfo` | `backend/core/agents.py:219` | Escrita atômica preservando a propriedade 0600 |
| `fHashApiToken` | `backend/core/agents.py:256` | SHA-256; o token cru nunca é armazenado |
| `fFindAgentByApiToken` | `backend/core/agents.py:301` | Transforma um token numa identidade |

### O daemon privilegiado

| Símbolo | Arquivo:linha | O que faz |
|---|---|---|
| `fIsPeerAllowed` | `backend/core/exec_daemon.py:106` | Só o root e `boa`, verificado a cada conexão |
| `fRunPrivilegedCommand` | `backend/core/exec_daemon.py:122` | Roda uma lista de comandos sem shell, opcionalmente como outro usuário |
| `fVerbCreateAgent` | `backend/core/exec_daemon.py:396` | Cria usuário, diretório pessoal, configuração e token; aplica as ferramentas, os limites, o interruptor e as configurações `rag` validadas de um modelo; **desfaz tudo diante de qualquer falha** |
| `fStartRunner` | `backend/core/exec_daemon.py:304` | O único lugar em que um runner é iniciado como o agente. A mensagem do chat ou o prompt do cartão vai pela entrada padrão dele, nunca pela linha de comando |
| `fWatchRunner` | `backend/core/exec_daemon.py:255` | Espera uma execução: para o scope dela e registra o fim de uma que foi morta |
| `fVerbWriteCrontab` | `backend/core/exec_daemon.py:780` | Instala um crontab como o próprio usuário do agente |
| `fListRunningAgentIds` | `backend/core/exec_daemon.py` | Uma varredura de `/proc` que nomeia todo agente com uma execução em andamento. Sustenta tanto `only_if_idle` quanto o anel girando da barra lateral |
| `dVerbHandlers` | `backend/core/exec_daemon.py` | A tabela fechada de verbos. Toda a superfície privilegiada são estas dez linhas |

### A API dos agentes

| Símbolo | Arquivo:linha | O que faz |
|---|---|---|
| `fAuthenticate` | `backend/core/agent_api.py:121` | Token **e** `SO_PEERCRED` têm de concordar |
| `fAgentMayUseKanban` | `backend/core/agent_api.py` | Se o quadro está ligado e o agente tem alguma ferramenta de kanban. A metade grosseira |
| `fRequireKanbanTool` | `backend/core/agent_api.py` | Um verbo, uma ferramenta, pelo nome. Todo handler fazia a pergunta grosseira, então `kanban.list_cards` - uma leitura - chegava a `fDeleteCard` para um agente que pusesse ele mesmo a requisição no socket |
| `fRequireOwnCard` | `backend/core/agent_api.py:283` | Um agente só pode mudar cartões que criou ou de que é dono |
| `fVerbChannelWrite` | `backend/core/agent_api.py` | Envia em nome do agente, prefixando o nome real dele |

### O loop de execução

| Símbolo | Arquivo:linha | O que faz |
|---|---|---|
| `AgentRun` | `backend/core/runner.py:336` | Uma conversa limitada |
| `fCheckCeilings` | `backend/core/runner.py` | Devolve qual teto parou a execução, ou vazio para continuar |
| `fSecondsLeft` | `backend/core/runner.py` | O tempo que resta até o prazo da execução, num relógio monotônico. Cada chamada ao provedor e cada ferramenta recebem o que resta, não o teto inteiro |
| `fTakeRunLock` | `backend/core/runner.py` | Um flock em `<home>/run.lock`, mantido durante todo o processo. A única verificação que uma execução iniciada pelo cron também faz |
| `fTrimToByteBudget` | `backend/core/exec_protocol.py` | As entradas mais novas que cabem num orçamento de bytes, e quantas foram descartadas. Contado em bytes, porque uma contagem de linhas não é um tamanho |
| `fRunWithLimits` | `backend/tools/bash_run.py` | Roda um comando com um teto de bytes aplicado ENQUANTO ele produz saída, e um prazo que mata o grupo de processos inteiro |
| `fAskForClosingAnswer` | `backend/core/runner.py` | Depois de um teto, pede uma vez, sem ferramentas, a resposta que a execução foi impedida de dar |
| `fExecute` | `backend/core/runner.py:503` | O loop: perguntar, rodar ferramentas, devolver os resultados, parar |
| `fSelectAllowedTools` | `backend/core/runner.py:319` | Retém as ferramentas de kanban quando o agente as tem desligadas |
| `fReadStdinArguments` | `backend/core/runner.py:988` | A metade do runner nisso: lê o texto da entrada padrão, com limite, e recusa uma mensagem de chat vazia |
| `fApplyResourceLimits` | `backend/core/runner.py:1069` | Reduz os próprios limites de kernel da execução antes de qualquer coisa ser iniciada: processos, core files, tamanho de arquivo |
| `fRecordChatAnswer` | `backend/core/runner.py` | Escreve a resposta de volta quando a execução tem um turno a fechar (`vWritesToChat`) |
| `fRecordChatFailure` | `backend/core/runner.py` | Fecha o turno quando nada mais o fará, citando o motivo para que a interface possa traduzi-lo |
| `fAppendCardMessage` | `backend/core/chat.py` | Anuncia um cartão vencido como um turno próprio, com os campos do cartão e nenhuma frase |
| `fBuildCardAnnouncement` | `backend/core/buzzer.py` | O que é dito ao chat: quem o atribuiu e se ele foi pedido para agora |

### Ferramentas

| Símbolo | Arquivo:linha | O que faz |
|---|---|---|
| `fGetContext` | `backend/core/browser.py` | Inicia o navegador com o perfil deste agente, ou devolve o que já está rodando |
| `fClose` | `backend/core/browser.py` | Registrado com `atexit`. Sem ele, toda execução deixa um Chromium para trás |
| `fIsInstalled` | `backend/core/browser.py` | Se há um navegador para conduzir, para que as ferramentas possam dizer o que rodar em vez de lançar uma exceção |
| `fLoadAllTools` | `backend/core/tool_registry.py:105` | Carrega toda ferramenta válida; um arquivo quebrado é pulado, não é fatal |
| `fRunTool` | `backend/core/tool_registry.py:138` | Impõe a permissão, devolve `(text, is_error)`; uma ferramenta que lança exceção nunca mata uma execução |
| `fGetLimit` | `backend/core/memory.py:53` | Lê o limite de memória protegido de cada agente, com o padrão legado |
| `fValidateContent` | `backend/core/memory.py:71` | Rejeita memória grande demais sem descartar texto |
| `fCheckMemoryUpdate` | `backend/web/api.py:127` | Valida a memória e o limite proposto antes de qualquer escrita de configurações |
| `fSearch` | `backend/core/rag_search.py:123` | Recuperação híbrida com referências às fontes |
| `fPrompt` | `backend/core/rag_search.py:243` | Os trechos recuperados e a regra do modo de resposta, acrescentados ao prompt de sistema |
| `fVerify` | `backend/core/rag_verify.py:235` | Unidades sem uma citação recuperada ou diferentes do que citam: devolve o texto mantido e o que foi removido |
| `fSplitUnits` | `backend/core/rag_verify.py:163` | Corta uma resposta em parágrafos e itens de lista, guardando o necessário para reconstruí-la |
| `fCheckRagAnswer` | `backend/core/runner.py:681` | Devolve uma resposta final uma vez: ainda sem busca (documental, verificado) ou com parágrafos sem sustentação (verificado) |
| `fFinishRagAnswer` | `backend/core/runner.py:704` | O que o usuário vê: frase fixa sem trechos, parágrafos sem sustentação removidos, retida quando não pode ser verificada |
| `fIndexDocument` | `backend/core/rag_worker.py:32` | Extrai, vetoriza e publica uma revisão; `False` quando uma queda do motor a pôs de novo na fila |
| `fWork` | `backend/core/rag_worker.py:129` | Lote de indexação limitado; espera sem extrair enquanto o motor está fora do ar |
| `EngineUnavailable` | `backend/core/rag_embeddings.py:11` | Queda do motor (falha do socket ou 503), distinguida de uma requisição recusada |
| `fIsAvailable` | `backend/core/rag_embeddings.py:73` | Teste barato que o worker roda antes de cada documento: o motor responde, e com o modelo em uso |
| `fCheckServedModel` | `backend/core/rag_embeddings.py:68` | `EngineUnavailable` a não ser que o `/v1/models` do motor indique o modelo esperado |
| `fSelectedModel` | `backend/core/rag_settings.py:39` | A entrada do catálogo escolhida em Configurações → RAG, o padrão quando nenhuma ou uma desconhecida está salva |
| `fInstallModel` | `backend/core/rag_runtime.py:76` | Baixa um modelo para um arquivo privado e só lhe dá o nome definitivo depois que o tamanho e o SHA-256 conferem |
| `fStartModelDownload` | `backend/core/rag_runtime.py:125` | Põe um download na fila do executor e devolve o estado dele na hora |
| `fFollowModelSimilarity` | `backend/core/rag_exec.py:113` | Numa troca de modelo, move os agentes que ainda estavam na `min_similarity` recomendada antiga para a nova |
| `fFollowNewModel` | `backend/core/rag_worker.py:107` | Põe de novo na fila o que outro modelo indexou, mantendo as revisões publicadas pesquisáveis por palavras |
| `fMigrate` | `backend/core/rag_store.py:83` | Acrescenta as `lAddedColumns` que faltam nos catálogos mais antigos (`year`, `subtitle`) a cada conexão |
| `fAction` | `backend/core/rag_store.py:270` | Informações do documento, reindexar, cancelar e excluir; valida as chaves de metadados e o ano |
| `fSnapshot` | `backend/core/rag_store.py:334` | Backup consistente de documentos/índice |
| `ToolContext` | `backend/core/tool_registry.py:53` | O que uma ferramenta fica sabendo sobre quem a chama |
| `fStoreImage` | `backend/core/attachments.py` | Copia um PNG do diretório pessoal do agente para um snapshot privado |
| `fReadImageChunk` | `backend/core/attachments.py` | Lê no máximo 1 MiB, recusando links simbólicos, outros donos e arquivos especiais |
| `fVerbReadChatAttachment` | `backend/core/exec_daemon.py` | Exige uma referência ao anexo no chat do agente pedido antes de ler |
| `fGetChatAttachment` | `backend/web/api.py` | Transmite o PNG em streaming a um usuário autenticado, sem URL de arquivo pública nem em cache |
| `fRenderChatAttachments` | `frontend/static/js/dashboard.js` | Mostra as imagens da resposta e um erro quando uma imagem não pode ser carregada |
| `fSetComposerEnabled` | `frontend/static/js/dashboard.js` | Abre ou fecha a caixa de mensagem e escreve a segunda linha do placeholder: como o Enter se comporta, ou que o agente está trabalhando |
| `fFitChatInputToPlaceholder` | `frontend/static/js/dashboard.js` | Aumenta a caixa de texto até caber o placeholder inteiro, medido num gêmeo invisível |
| `fTrackStatusBarHeight` | `frontend/static/js/api.js` | Mantém `--status-bar-live-height` igual à altura real da barra de status, que o layout do chat no celular subtrai |
| `fDeliverAnswerParts` | `backend/core/telegram_listener.py` | Retoma a entrega no Telegram a partir da última parte de texto/imagem confirmada |

### Habilidades

| Símbolo | Arquivo:linha | O que faz |
|---|---|---|
| `fIsValidSkillName` | `backend/core/skills.py:57` | Um nome, nunca um caminho. Recusa em vez de limpar, como os nomes de modelos de agente e de temas |
| `fParseSkill` | `backend/core/skills.py:77` | O cabeçalho `---` e o corpo |
| `fSelectInstalledSkills` | `backend/core/skills.py:194` | Os nomes da lista de um agente que ainda existem no disco. **Todo caminho para o recurso passa por aqui**, então uma habilidade excluída nunca chega a um prompt |
| `fBuildPromptSection` | `backend/core/skills.py:211` | O índice: uma linha por habilidade, só nomes e descrições. `""` quando o agente não tem nenhuma |
| `fRunTool` | `backend/tools/skill_read.py` | Devolve um corpo, verificado contra o próprio `info.json` do agente |


### Telegram, nos dois sentidos

| Símbolo | Arquivo:linha | O que faz |
|---|---|---|
| `fReadTelegramUpdates` | `backend/core/channels.py` | Um long poll. A conexão é feita para fora, que é o que permite que isto funcione atrás de um NAT sem nada redirecionado |
| `fSendToTelegram` | `backend/core/channels.py` | Envia e devolve o `message_id` - a única coisa que torna roteável uma resposta posterior |
| `fRedactSecrets` | `backend/core/channels.py` | Remove toda credencial de um erro ou de uma linha de log. `str(RequestException)` cita a URL, e em três dos quatro canais a URL **é** a credencial |
| `fReadConfigForEditing` | `backend/core/channels.py` | O arquivo de um canal como está no disco, para que salvar uma mudança mescle em vez de substituir |
| `fListConfiguredChannels` | `backend/core/channels.py` | Devolve Discord, Mattermost, Telegram e X em ordem alfabética, com o estado deles e sem segredos; usado pelas Configurações e pelas permissões de cada agente |
| `fRouteMessage` | `backend/core/telegram_listener.py` | Para quem é uma mensagem: o agente a quem se respondeu, ou o citado com @ |
| `fMatchNamedAgent` | `backend/core/telegram_listener.py` | Correspondência mais longa sobre todos os nomes conhecidos, porque os nomes dos agentes podem conter espaços |
| `fIsFromTheConfiguredChat` | `backend/core/telegram_listener.py` | **A autorização inteira.** Qualquer coisa vinda de outro chat é descartada sem resposta |
| `fDeliverAnswers` | `backend/core/telegram_listener.py` | Envia de volta todo turno que fechou desde a última passada |
| `fRememberMessage` | `backend/core/telegram_inbox.py` | Liga uma mensagem enviada ao agente que a enviou, podada às últimas poucas centenas |
| `fRouteMessage` | `backend/core/telegram_listener.py` | Para quem é uma mensagem: o agente a quem se respondeu, o citado com @ ou /, ou o selecionado |
| `fReadSelectedAgent` | `backend/core/telegram_listener.py` | Com quem é a conversa, verificado contra a lista de agentes para que um agente excluído pare de capturar tudo |
| `fBuildAgentButtons` | `backend/core/telegram_listener.py` | O teclado inline com que /agents responde. O texto de um botão quem escolhe é o bot, o que não acontece com o do menu de comandos |
| `fBuildStatusReport` | `backend/core/telegram_listener.py` | O que /status diz. Um agente que ele não consegue ler é listado dizendo isso, nunca deixado de fora |
| `fHandleCallback` | `backend/core/telegram_listener.py` | Um toque num botão de agente: respondido primeiro, depois o agente é selecionado |
| `fRender` | `backend/core/telegram_html.py` | Markdown para o HTML do Telegram. Títulos viram negrito, listas viram marcadores, tabelas viram um bloco monoespaçado - o Telegram não tem tag para nenhum dos três |
| `fEscape` | `backend/core/telegram_html.py` | `&`, `<`, `>`. **Chamado antes que qualquer coisa envolva o texto**, nunca depois |
| `fEscapeAttribute` | `backend/core/telegram_html.py` | O mesmo mais as aspas duplas, para um href. Do contrário, aspas numa URL fechariam o atributo e inventariam os seguintes |
| `fRenderWithinLimit` | `backend/core/telegram_html.py` | Encurta o markdown e renderiza de novo até o HTML caber. Cortar o HTML deixaria uma tag escrita pela metade |

### Discord, nos dois sentidos

| Símbolo | Arquivo:linha | O que faz |
|---|---|---|
| `fReadDiscordMessages` | `backend/core/channels.py` | Um polling. **Inverte o que o Discord devolve**, que vem do mais novo para o mais antigo: responder nessa ordem faria o agente ler uma conversa de trás para frente |
| `fSendToDiscord` | `backend/core/channels.py` | Envia, em tantas partes quanto o limite de 2000 caracteres exigir, e devolve o id de cada parte |
| `fCallDiscord` | `backend/core/channels.py` | Uma chamada. Um 429 com um `retry_after` curto é esperado uma vez; qualquer outro 4xx é `ChannelRejected` |
| `fGetDiscordMode` | `backend/core/channels.py` | `"bot"`, `"hook"` ou `""`. Um webhook envia e nada mais |
| `fReadDiscordBotUser` | `backend/core/channels.py` | Qual bot é este, escrito no log uma vez a cada início: quando nada chega, essa é a primeira pergunta |
| `fRenderToMessages` | `backend/core/discord_markdown.py` | Uma resposta como a lista de mensagens a enviar para ela |
| `fSplit` | `backend/core/discord_markdown.py` | Corta entre linhas, fechando e reabrindo um bloco delimitado dentro do qual o corte caia |
| `fIsFromTheConfiguredChannel` | `backend/core/discord_listener.py` | Toda mensagem consultada veio desse canal por construção; verificado mesmo assim, porque “por construção” é uma propriedade do código de hoje |
| `fReadCommand` | `backend/core/discord_listener.py` | `!agents`, `!status`, `!help` e as formas com `/`. Só como a primeira palavra inteira, ou um agente chamado `status` ficaria inalcançável |
| `fReadMessageText` | `backend/core/discord_listener.py` | O texto sem a menção ao bot no começo: o Discord transforma `@Boa` em `<@123>` antes que qualquer outro o veja |
| `fStartFromTheNewestMessage` | `backend/core/discord_listener.py` | Onde uma instalação nova começa. Um bot ligado hoje à tarde não deve responder a um mês do canal |
| `fReadAfterId` / `fWriteAfterId` | `backend/core/discord_listener.py` | A marca, em `config/discord-after`. Um snowflake, não um contador |
| `fRememberMessage` | `backend/core/discord_inbox.py` | Liga uma parte enviada ao agente que a enviou. Podado por ordem de inserção, não por id |

### Compartilhado pelos dois listeners

| Símbolo | Arquivo:linha | O que faz |
|---|---|---|
| `fMatchNamedAgent` | `backend/core/agent_routing.py` | Correspondência mais longa sobre todos os nomes conhecidos. Os prefixos são um argumento: o Telegram aceita `@` e `/`, o Discord acrescenta `!` |
| `fBuildStatusReport` | `backend/core/agent_routing.py` | O que /status diz. Recebe o catálogo do serviço que pergunta e o nome da própria unidade dele, que são as duas únicas coisas que diferem; resolve o nome do serviço do canal para systemd ou OpenRC |
| `fFindClosedAnswer` | `backend/core/agent_routing.py` | O que um agente disse para fechar um turno, lido por meio do executor |
| `fListAgentNames` | `backend/core/agent_routing.py` | A lista de agentes, a partir do índice: o diretório pessoal de um agente é 0700 e o info.json dele não cabe a um listener abrir |

### Os scripts e o cron próprios de um agente

| Símbolo | Arquivo:linha | O que faz |
|---|---|---|
| `fValidateScriptName` | `backend/core/agent_scripts.py` | Verifica um nome em vez de limpá-lo: qualquer coisa que não seja um nome de arquivo simples é recusada, o que é uma regra só em vez de uma regra mais o que quer que a limpeza acabe fazendo |
| `fValidateSchedule` | `backend/core/agent_scripts.py` | A forma de um agendamento do cron, e a única coisa que vale recusar: um job que dispara com mais frequência do que alguém pretendia |
| `fIsRunnerLine` | `backend/core/agent_scripts.py` | A linha que acorda o agente. Nunca reescrita daqui: um agente que a apagasse ficaria em silêncio para sempre sem ter como perceber |
| `fAddCronLine` | `backend/core/agent_scripts.py` | Acrescenta uma linha que roda um dos scripts do próprio agente. O script tem de existir antes |
| `fRemoveCronLines` | `backend/core/agent_scripts.py` | Remove toda linha que roda um script, e o comentário acima de cada uma |

### Quadro e canais

| Símbolo | Arquivo:linha | O que faz |
|---|---|---|
| `fAddCard` | `backend/core/kanban.py:132` | Cartão e primeiro evento numa só transação |
| `fMoveCard` | `backend/core/kanban.py:188` | Movimento mais evento no histórico |
| `fValidateRunAt` | `backend/core/kanban.py:68` | Aceita `"now"`, um horário do navegador ou um horário armazenado, e normaliza os três |
| `fReadRunMode` | `backend/core/kanban.py:100` | Que tipo de horário foi pedido: `now`, `at` ou nenhum |
| `fWasRequestedImmediately` | `backend/core/kanban.py` | Se o cartão disse “agora”. Lido de `run_mode`, nunca deduzido pelo relógio |
| `fAssignCard` | `backend/core/kanban.py` | Passa um cartão adiante, registrando em `assigned_by` quem o passou |
| `fAgentOwnsCard` | `backend/core/kanban.py:462` | Criador **ou** responsável |
| `fDeleteCard` | `backend/core/kanban.py:480` | Exclui, mantendo uma linha em `deleted_cards` |
| `fReadMessages` | `backend/core/mailbox.py` | As mensagens mais novas de uma pasta, somente leitura: nada é marcado como visto |
| `_fParseFolderLine` | `backend/core/mailbox.py` | Uma linha LIST como flags, delimitador e nome. Lança exceção em vez de adivinhar: uma listagem ilegível é um erro, não uma conta sem pastas |
| `fListFoldersWithFlags` | `backend/core/mailbox.py` | Toda pasta com as flags SPECIAL-USE dela |
| `fFindTrashFolder` | `backend/core/mailbox.py` | `\\Trash` primeiro, depois os nomes em nove idiomas. `""` significa que não há nenhuma; uma falha lança exceção |
| `fIsForwardAllowed` | `backend/core/mailbox.py` | Se um endereço está na lista do usuário. Verificado onde a senha está, nunca num prompt |
| `fListTemplates` | `backend/core/agent_templates.py:134` | Todos os modelos do repositório, resumidos, pelo nome que o usuário vê; um quebrado, com o erro dele |
| `fReadTemplate` | `backend/core/agent_templates.py:151` | A origem e o pacote verificado de um modelo, ou None; recusa um nome que não seja um id simples antes de baixar |
| `fReadPackage` | `backend/core/agent_package.py:418` | Verifica um pacote inteiro - nomes, agent.json, prompt, memória, caminhos do diretório pessoal, biblioteca - e o descreve |
| `fValidateManifest` | `backend/core/agent_package.py:317` | agent.json: só chaves conhecidas, format 1, agendamentos, ferramentas instaladas aqui, limites, rag, provedor sem chave |
| `ZipSource` | `backend/core/agent_package.py:84` | Um `.zip`: recusa nomes que sobem, links, criptografia, membros 200:1 e mais de 8 GiB |
| `fReadRepositoryArchive` | `backend/core/agent_package.py:236` | Divide um `.tar.gz` de repositório em pastas de modelos; pula links |
| `fInstallPackage` | `backend/core/agent_io.py:60` | Cria o agente desligado, depois a memória, os arquivos do diretório pessoal e a biblioteca dele; o exclui de novo em caso de falha |
| `fStartImport` | `backend/core/agent_io.py:265` | Começa a instalar um `.zip` verificado numa thread, uma vez, seja qual for o número de cliques |
| `fExportAgent` | `backend/core/agent_io.py:420` | Produz o `.zip` enquanto ele é escrito; diretório pessoal e biblioteca transmitidos em streaming |
| `fReadSchedules` | `backend/core/agent_io.py:320` | Só as linhas do crontab que rodam o agente, como cinco campos |
| `fValidateSchedule` | `backend/core/agents.py:85` | Cinco campos do cron, uma linha, nada que possa ser um comando |
| `fList` | `backend/core/agent_home.py:86` | Os arquivos do diretório pessoal que um pacote pode levar, como o agente, excluindo os do sistema e os ocultos |
| `fWrite` | `backend/core/agent_home.py:130` | Escreve um bloco em ordem, sem passar por link, com modo só para o dono |
| `fBroker` | `backend/core/agent_home.py:170` | Roda uma operação no diretório pessoal como o agente; o verbo `agent_home` do executor |
| `fChooseAgentSource` | `frontend/static/js/api.js` | O diálogo do +: agente vazio, .zip ou modelo |
| `fImportAgentZip` | `frontend/static/js/api.js` | Enviar em blocos, verificar, mostrar, confirmar, instalar, consultar |
| `fLoadExportPreview` | `frontend/static/js/agent_export.js` | O que cada opção de exportação acrescentaria, perguntado toda vez que a aba abre |
| `fSource` | `backend/core/rag_search.py:88` | Um trecho como o modelo e as citações o veem: ref, localização, título, subtítulo, ano, autor, versão, idioma, texto, link |

### A barra lateral

| Símbolo | Arquivo:linha | O que faz |
|---|---|---|
| `fRenderSidebar` | `frontend/static/js/api.js` | Reconstrói a lista de agentes. Chamado ao carregar a página e depois de criar ou excluir, nunca por um timer |
| `fPickDifferentModel` | `frontend/static/js/dashboard.js` | O modelo a preencher quando um provedor é escolhido. O reserva evita o do principal: mesmo provedor e mesmo modelo falham pelo mesmo motivo, sempre |
| `fSetAgentAvatarActivity` | `frontend/static/js/api.js` | Define `data-running` e o tooltip de um avatar, e acrescenta ou remove o arco |
| `fBuildAgentActivityArc` | `frontend/static/js/api.js` | O retângulo arredondado em SVG colocado sobre a borda, com `pathLength="100"` para que a folha de estilos possa falar em porcentagens do perímetro |
| `fRefreshAgentActivity` | `frontend/static/js/api.js` | A cada 5s, redesenha só os anéis; pulado enquanto a aba está escondida |
| `fDescribeChannelName` / `fDescribeProviderName` | `frontend/static/js/api.js` | O nome com que um canal ou um provedor se escreve. Não são chaves i18n: DeepSeek é DeepSeek em todos os idiomas |
| `fDescribeTool` / `fDescribeToolArgument` | `frontend/static/js/api.js` | O que uma ferramenta e os argumentos dela dizem, no idioma de quem lê. O schema fica em inglês: é o que é enviado ao modelo |
| `fRenderToolCheckboxes` | `frontend/static/js/dashboard.js` | Uma caixa por família de ferramentas, montada a partir do que estiver instalado. Move o interruptor do kanban para dentro da caixa do kanban em vez de reconstruí-lo, para que uma marcação feita e ainda não salva sobreviva ao redesenho |

### Mensagens pop-up

| Símbolo | Arquivo:linha | O que faz |
|---|---|---|
| `fShowNotice` | `frontend/static/js/api.js` | Coloca uma mensagem na camada sobre a coluna de conteúdo. Substitui o que estivesse ali, então as confirmações nunca se empilham |
| `fShowError` | `frontend/static/js/api.js` | O mesmo, como erro: sem timer, fechado à mão |
| `fConfirmLogout` | `frontend/static/js/api.js` | Abre `fConfirm` no centro da tela; navega para `/logout` só depois da confirmação. Cancelar e Escape mantêm a sessão aberta |
| `fHideNotice` | `frontend/static/js/api.js` | Esmaece uma mensagem e a remove depois, para que ela não suma de repente quando o timer acaba |
| `fGetNoticeSeconds` / `fSetNoticeSeconds` | `frontend/static/js/api.js` | Quanto tempo uma mensagem fica, guardado neste navegador e limitado a 1–30 segundos |
| `fBuildCloseCross` | `frontend/static/js/api.js` | O X de fechar como duas linhas SVG. Um caractere `×` é centralizado no eixo matemático da fonte e não na própria caixa, então fica acima do meio do botão, faça o botão o que fizer |

### Destaque de JSON

| Símbolo | Arquivo:linha | O que faz |
|---|---|---|
| `cJsonTokenPattern` | `frontend/static/js/jsonhighlight.js` | Uma expressão para os quatro tipos de token. Uma string seguida de dois-pontos é uma chave, que é a única coisa que distingue um nome de um valor |
| `fHighlightJsonElement` | `frontend/static/js/jsonhighlight.js` | Reconstrói um bloco como spans coloridos e texto puro. Cada caractere do original é emitido exatamente uma vez, então o bloco continua sendo copiado como JSON válido |

### Provedores

| Símbolo | Arquivo:linha | O que faz |
|---|---|---|
| `BaseProvider.fSendMessages` | `backend/providers/base.py` | O único método que todo adaptador implementa |
| `fNeutralMessagesToOpenAiFormat` | `backend/providers/base.py` | Formato neutro → chat/completions |
| `fToolNameToWire` / `fToolNameFromWire` | `backend/providers/base.py` | `family.action` ↔ `family__action`, porque nenhum provedor aceita o ponto |
| `fDescribeHttpError` | `backend/providers/base.py` | Acrescenta o que o provedor disse a uma falha HTTP crua |
| `fBuildProvider` | `backend/providers/factory.py` | Configuração → instância do adaptador, importando sob demanda |
| `fResolveProviderName` | `backend/providers/factory.py` | Segue os aliases, para que `gemini` e `google` cheguem ao mesmo adaptador |
| `fSendChatCompletion` | `backend/providers/openai_dialect.py` | A requisição chat/completions compartilhada, parametrizada pelas peculiaridades de cada adaptador |
| `fNormalizeMessageContent` | `backend/providers/openai_dialect.py` | Achata uma resposta cujo conteúdo chegou em blocos, descartando o raciocínio |

---

### Símbolos de áudio

| Símbolo | Arquivo:linha | Responsabilidade |
|---|---|---|
| `fTranscribe` | `backend/core/audio_transcription.py:223` | Decodificar, segmentar e transcrever |
| `fEnqueueTelegram` | `backend/core/audio_inbox.py:57` | Persistir o destino antes da transcrição |
| `fRunOneJob` | `backend/core/audio_inbox.py:233` | Processar ou tentar de novo um turno reservado |
| `fDownloadModel` | `backend/core/whisper_runtime.py:134` | Validar tamanho e SHA-256 antes da publicação |
| `fGetChatAudio` | `backend/web/api.py:571` | Servir o áudio depois das verificações de sessão e de referência no chat |

### API Calls

| Símbolo | Arquivo | Responsabilidade |
|---|---|---|
| `fRecordCall` | `backend/core/api_calls.py` | Persiste um corpo de saída completo antes do envio |
| `fReadBodyChunk` | `backend/core/api_calls.py` | Lê uma parte limitada de um arquivo validado do agente |
| `fSelectConversationTab` | `frontend/static/js/dashboard.js` | Alterna entre Chat/API Calls e o polling de cada uma |
| `fBeautifyJson` | `frontend/static/js/jsonhighlight.js` | Indenta JSON preservando os valores literais |

### Samba

| Símbolo | Arquivo | Responsabilidade |
|---|---|---|
| `fProvisionAgent` / `fRemoveAgent` | `backend/core/samba.py` | Ciclo de vida do compartilhamento/conta |
| `fSaveSettings` | `backend/core/samba.py` | Validar, salvar as credenciais e ativar as permissões |
| `fCheckShareDirectory` | `backend/core/samba.py` | Verificação da pasta e da propriedade no momento da conexão |
| `fBackup` / `fRestore` | `backend/core/samba.py` | Backup e substituição consistentes das credenciais nativas |
| `fLoadSambaSettings` / `fCollectSambaSettings` | `frontend/static/js/samba.js` | Carregar e salvar sem expor senhas nem descartar outras edições |

## 4. Fluxos principais

### Recuperação de documentos

Os instaladores limpam as árvores RAG antigas dos agentes restaurados antes de
extrair o snapshot, para que arquivos WAL velhos do SQLite e gerações de vetores
não sobrevivam a uma restauração. As configurações de runtime são restauradas
sem substituir os pesos de modelos instalados. A cada vez, os workers processam
no máximo oito documentos, ou começam documentos novos por no máximo 90
segundos; os jobs não terminados continuam duráveis. A resposta da biblioteca
expõe as falhas de importação da inbox. O OCR local instala as fontes Liberation
para PDFs sem fontes embutidas. O build de vetorização desativa o download da
interface web pré-compilada.

Envio: `rag_api → exec_client.fRag → rag_exec → rag_worker` como o agente.
Indexação: `boa-rag → exec_daemon → rag_worker.fWork → rag_embeddings.fIsAvailable → extraction → local embeddings → publication`.
Queda do motor durante a indexação: `rag_embeddings.fRequest → EngineUnavailable → fIndexDocument → state queued, chunks kept → fWork ends the batch → next pass resumes at the first missing chunk`.
Download de modelo: `settings_rag.js → POST /api/admin/rag/models/<id>/install → exec_client.fInstallRagModel → exec_daemon.fVerbInstallRagModel → rag_runtime.fStartModelDownload → thread fInstallModel → status file ← GET /api/admin/rag (fDescribe) polled every 2 s`.
Troca de modelo: `settings_rag.js (fConfirmModelChange) → PUT /api/admin/rag → rag_exec.fRuntime → fIsModelInstalled → fSaveRuntimeSettings → fFollowModelSimilarity → restart boa-embeddings → [each library] rag_worker.fWork → fFollowNewModel → fIsAvailable waits for the new alias → fIndexDocument(pModel) → fBuildIndex/fPublish (documents.model)`; enquanto isso, `fSearch → FTS5 only for the waiting documents → notice`.
Resposta: `AgentRun.fExecute → rag_search.fSearch → bounded passages → configured provider → verified citation links`.
Resposta documental e verificada: `model answers → fCheckRagAnswer (no rag.search yet → cRagSearchFirstPrompt, once) → rag.search → model answers → [verified] rag_verify.fVerify → unbacked units → fBuildCorrectionPrompt, once → model answers → fFinishRagAnswer (no passages → fixed sentence; verified → units removed + count, engine down → withheld) → fResolveCitations`.

### Salvar a memória e o limite dela

`dashboard.js:fSaveAgent` conta pontos de código Unicode e envia `memory` com
`info.limits.max_memory_characters`. `api.fCheckMemoryUpdate` valida contra o
limite proposto (ou lê o salvo) antes de qualquer escrita, então aumentar o
limite e salvar um texto mais longo funciona numa só requisição. Em caso de
rejeição, devolve os erros traduzidos `memoryTooLong` ou `memoryLimitInvalid`.
Depois, `fVerbWriteAgentInfo` persiste o limite e `fVerbWriteMemory` valida
antes de abrir mão dos privilégios. `memory.fWrite` verifica de novo a
configuração protegida e substitui o arquivo atomicamente, sem truncamento.
`memory.append` e `memory.replace` usam a mesma verificação; o aviso começa
acima de 75% do limite. O formulário deixa o texto colado grande demais
disponível para edição.

Os orçamentos de transporte comportam o limite superior: 6 MiB por requisição
ao executor, verificados pelo cliente antes de conectar; 8 MiB por resposta;
4 MiB por leitura do arquivo de memória; 16 MiB por corpo HTTP, incluindo
clientes JSON que escapam caracteres Unicode suplementares. Esses são limites de
transporte, não limites de contexto do modelo.

### Criar um agente

```
navegador  POST /api/admin/agents {name}
  web/api.fCreateAgent
    exec_client.fCreateAgent          → socket Unix /run/boa/exec.sock
      exec_daemon.ExecRequestHandler
        fGetPeerCredentials + fIsPeerAllowed    ← recusa qualquer um que não seja root/boa
        fVerbCreateAgent
          agents.fValidateAgentName
          agents.fGetNextFreeAgentId            ← o menor livre, segundo o sistema de arquivos
          useradd --home-dir … --create-home
          agents.fWriteAgentInfo                 (0600, de propriedade do agente)
          fWriteAgentFile system-prompt.md        (0600)
          fWriteAgentFile api-token              (0600)
          chmod 0700 no diretório pessoal
          agents.fIndexAgent(…, vApiToken)       ← guarda só o SHA-256
        diante de qualquer exceção: fRemoveAgentUser  ← nenhum agente criado pela metade
```

### Criar um agente a partir de um modelo

```
navegador  GET /api/admin/agent-templates?language=es-ES
  agent_templates.fListTemplates
    fLoadTemplates → fDownloadArchive(<repo>/archive/refs/heads/<branch>.tar.gz)   em cache por 5 min
      agent_package.fReadRepositoryArchive                   uma fonte por pasta com agent.json
    agent_package.fReadPackage + fSummarise                  por modelo; uma falha é listada com o erro
navegador  POST /api/admin/agents {name, template, language}
  api.fCreateAgent
    agent_templates.fReadTemplate(template)                  o servidor o lê de novo
    agent_io.fInstallPackage
      exec_client.fCreateAgent(tools, skills, limits, pRag, pSchedules, pEnabled=False)
        exec_daemon.fVerbCreateAgent → agents.fValidateSchedule, de novo
      exec_client.fWriteAgentInfo / fWriteMemory / fAgentHome / fRag   quando o pacote os traz
      em caso de falha: exec_client.fDeleteAgent
```

### Importar um .zip

```
navegador  POST /api/admin/agent-imports {name, size}          → /opt/boa/imports/<id>/package.zip
navegador  PUT  /api/admin/agent-imports/<id>/upload {offset, data}   em ordem, 256 KiB cada
navegador  POST /api/admin/agent-imports/<id>/finish            ZipSource + fReadPackage → resumo
navegador  (mostra o resumo; o usuário confirma e dá um nome)
navegador  POST /api/admin/agent-imports/<id>/install           → 202
  agent_io.fStartImport → install.lock (uma vez) → thread fRunImport
    fInstallPackage, informando step/done/total em job.json
navegador  GET  /api/admin/agent-imports/<id>                   a cada segundo até installed/failed
```

### Exportar um agente

```
navegador  GET /api/admin/agents/<id>/export/preview            tamanho da memória, arquivos do diretório pessoal, biblioteca, modelo
navegador  GET /api/admin/agents/<id>/export?memory=1&home=1&provider=1&rag=1   um link de download
  agent_io_api.fExport → primeiro bloco produzido antes dos cabeçalhos (os erros continuam JSON)
    agent_io.fExportAgent
      fBuildManifest ← fReadAgentInfo, fReadCrontab → fReadSchedules
      memory.md ← fReadMemory
      home/... ← exec_client.fAgentHome(list, read) como o agente
      rag/files/... + rag/documents.json ← exec_client.fRag(list, content)
```

### Uma execução agendada

```
cron (o próprio crontab de agent-007)
  runner.py --agent-id 007            ← já rodando como agent-007
    fTakeRunLock                      ← recusado → fRecordRunRefused, e para
    AgentRun.__init__
      fReadOwnInfo / fReadOwnSystemPrompt / fReadOwnApiToken
      fBuildSystemPrompt              ← prompt + memória + índice de habilidades + idioma
      tool_registry.fLoadAllTools
      fSelectAllowedTools             ← ferramentas de kanban retidas se desligadas
    fExecute
      run_journal.fCountRunsOn        ← teto diário, a partir do próprio diário
      factory.fBuildProvider
      loop:
        fCheckCeilings                ← passos, tokens, segundos
        provider.fSendMessages        ← max_tokens diminui conforme o orçamento é gasto
        run_journal.fRecordUsage
        se não houver chamadas de ferramentas: parar
        fRunToolCalls                 ← todos os resultados devolvidos num só lote
      fAskForClosingAnswer            ← uma chamada sem ferramentas depois de um teto
                                        de passos ou de tokens, para que o trabalho
                                        já pago vire uma resposta
      run_journal.fRecordRunFinished  ← "stopped" quando um teto a encerrou
```

### Um cartão vence

```
boa-buzzer (como boa), a cada 5 segundos
  kanban.fListDueCards              ← com dono, run_at passado, sem aviso, não feito
  fRingOne
    fBuildCardAnnouncement          ← assigned_by → nome, run_mode → imediato
    exec_client.fRunNow(prompt, only_if_idle, card)
      exec_daemon.fVerbRunNow                      ← como root
        fIsAgentRunning             ← ocupado: started=False, sem aviso, tentar de novo
        fRunAsAgent → chat.fAppendCardMessage      ← anunciado, turno aberto
        Popen runner.py --prompt-on-stdin --turn-id …  ← como agent-007, o prompt no stdin dele
    kanban.fMarkCardBuzzed          ← só depois de a execução começar
  runner.AgentRun (vWritesToChat, não vIsChat)
    fExecute                        ← prompt do cartão, nenhuma conversa reenviada
    fRecordChatAnswer               ← resposta + custo fecham o turno
    fRecordChatFailure              ← ou o motivo de nada ter rodado
```

### Um agente move um cartão

```
o modelo pede kanban.move_card
  tool_registry.fRunTool              ← recusa se não foi concedida a este agente
    tools/kanban_move_card.fRunTool
      agent_api_client.fCallFromContext   → /run/boa/agent.sock
        agent_api.AgentRequestHandler
          fAuthenticate               ← hash do token + SO_PEERCRED
          fVerbKanbanMoveCard
            fAgentMayUseKanban        ← no servidor, lê info.json
            fRequireOwnCard           ← só criador ou responsável
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
  fDeliverAnswers                     ← tudo o que terminou desde a última passada
    exec_client.fReadChat             ← o chat está num diretório pessoal 0700; só o root o lê
    channels.fSendToTelegram          ← "**name:**\n..." como resposta
    telegram_inbox.fRemovePending
  channels.fReadTelegramUpdates       ← long poll: 25s ocioso, 3s enquanto responde
    fIsFromTheConfiguredChat          ← todo o resto é descartado, em silêncio
    callback_query -> fHandleCallback ← um toque num botão de agente
      fSelectAgent                    ← daqui em diante, as mensagens sem destinatário vão para ele
    message -> fHandleMessage
      fHandleCommand                  ← /agents /status /help, respondido e pronto
      fRouteMessage                   ← resposta, depois @nome, depois o selecionado
      exec_client.fSendChatMessage(source="telegram")
        exec_daemon.fVerbSendChatMessage
          chat.fAppendMessage(metadata={"source": "telegram"})
          Popen runner.py --chat-message-on-stdin --turn-id   ← a mensagem no stdin dele
      telegram_inbox.fAddPending      ← no disco: um reinício não pode perder a resposta
```

A resposta é enviada pelo listener e não pela execução, pelo mesmo motivo pelo
qual o anúncio do cartão é escrito pelo executor: a execução é o próprio usuário
do agente, e as credenciais dos canais pertencem a `boa`. A execução só escreve
no chat dela; o listener lê isso e faz o envio.

### Chega uma mensagem do Discord

```
boa-channel-discord (como boa)
  fDeliverAnswers                     ← tudo o que terminou desde a última passada
    exec_client.fReadChat             ← o chat está num diretório pessoal 0700; só o root o lê
    channels.fSendToDiscord           ← "**name:**\n…" como resposta, em partes de 2000 caracteres
      discord_markdown.fRenderToMessages
    discord_inbox.fRememberMessage    ← cada parte, para que responder a qualquer uma delas seja roteado
    discord_inbox.fRemovePending
  channels.fReadDiscordMessages       ← GET /channels/<id>/messages?after=<id>
    (invertido: o Discord responde do mais novo para o mais antigo)
    fHandleMessage
      author.bot, type                ← as próprias palavras dele, e tudo o que não é mensagem
      fIsFromTheConfiguredChannel
      fReadCommand                    ← !agents !status !help, respondido e pronto
      fRouteMessage                   ← resposta, depois @nome, depois o selecionado
      exec_client.fSendChatMessage(source="discord")
      discord_inbox.fAddPending       ← no disco: um reinício não pode perder a resposta
  fWriteAfterId                       ← config/discord-after
```

A resposta é enviada pelo listener e não pela execução, pelo mesmo motivo que a
do Telegram: a execução é o próprio usuário do agente, e as credenciais dos
canais pertencem a `boa`.

A primeira passada de uma instalação nova pede a mensagem mais recente e guarda
só o id dela. Um canal vazio é marcado com o menor id que existe, para que a
**primeira** mensagem que alguém escrever seja respondida em vez de ser gasta
descobrindo por onde começar.

### O bot não mostra nada a um estranho

O nome de usuário de um bot é público: qualquer pessoa que o encontre pode abrir
um chat com ele. Por isso `fIsFromTheConfiguredChat` compara o `chat.id` que o
Telegram coloca em toda mensagem - que o remetente não consegue forjar - com o
configurado, e `fHandleMessage` descarta o que não bate antes de um comando ser
despachado e antes de um agente ser escolhido. `fHandleCallback` faz o mesmo com
um clique num botão. Nada é enviado de volta: responder confirmaria que o bot
está vivo para quem o está sondando. Nada é anotado também. O descarte era
registrado no log com o id do chat de onde vinha, que é dado de outra pessoa e
significaria esta instalação acumulando em silêncio uma lista de quem encontrou
o bot. O que sobra é uma mensagem que nunca existiu.

O custo é real e vale a pena dizê-lo: um `chat_id` configurado errado agora
parece exatamente um estranho, e as mensagens do próprio dono somem em silêncio.
O id configurado é escrito no log a cada início - `Registered 3 command(s)
for chat <id> only` -, que é o número com o qual comparar. Uma mensagem do chat
*configurado* que não chega a nenhum agente continua sendo registrada, porque
ali o remetente é o dono e “escrevi para ele e nada aconteceu” seria, de outro
modo, indistinguível de “nunca chegou”.

O que o filtro não cobre, e não pode cobrir, é *quem* dentro do chat: um
`chat_id` que indica um grupo é um grupo em que todos os membros podem falar com
os agentes.

O mesmo raciocínio decide onde a lista de comandos é escrita. `setMyCommands`
recebe um escopo, e `default` e `all_private_chats` são resolvidos para todo
usuário do Telegram - então uma lista escrita ali é um menu mostrado a
estranhos, com “Server status” nele, anunciando que há por trás disto uma
máquina que vale a pena cutucar. Eles nunca poderiam rodar nada disso, mas uma
placa numa porta trancada continua sendo uma placa. `fSetTelegramCommands`
escreve a lista só no escopo do chat configurado e **apaga** os dois públicos a
cada atualização: uma lista escrita por uma versão mais antiga deste código fica
do lado do Telegram até algo removê-la. `fHideTelegramPublicProfile` esvazia as
outras duas strings públicas, `setMyDescription` e `setMyShortDescription`, que
são o que preenche um chat vazio sob “What can this bot do?”.

O que continua visível é o nome do bot, a foto dele e o botão Start, que o
Telegram desenha em todo chat vazio com um bot e que nenhuma API consegue
remover. Apertá-lo envia `/start`, que é descartado como qualquer outra coisa
vinda de outro chat.

### Por que o menu contém ferramentas e não agentes

O Telegram desenha `/name` ao lado de cada entrada do menu de comandos - essa
string é a entrada, é o que é digitado na caixa quando ela é tocada, e nenhuma
API a esconde. Então um menu de agentes nunca poderia ser a lista de agentes que
alguém quisesse ver, e ele crescia junto com a lista de agentes sem dizer nada
sobre para que o bot servia.

O menu contém três coisas que o bot pode fazer. Quais agentes existem é uma
pergunta, e `/agents` a responde com botões inline, em que um botão diz
`os-watcher` e nada mais, porque o texto de um botão quem escolhe é o bot.

O resto decorre disso:

- **O agente selecionado fica fixo.** Tocar num botão ou citar um agente o
  escolhe; tudo o que vier sem destinatário vai para ele até outro ser
  escolhido. Citar o agente em cada linha funciona uma vez e cansa na quarta
  mensagem. Ele fica em `settings`, não na memória, porque o serviço reinicia a
  cada atualização.
- **Uma resposta continua vencendo.** Ela não é ambígua, e é o que faz alguém
  com um celular na mão. Nada mais muda a seleção, então um agente nunca herda
  uma conversa por ter sido o último a falar.
- **Um agente excluído deixa de ser o selecionado.** `fReadSelectedAgent`
  confere a lista de agentes na saída: não alcançar ninguém é melhor do que
  alcançar quem quer que tenha ficado com o id dele.
- **O bot fala o idioma da instalação.** `agent_language` primeiro, a mesma
  configuração em que os agentes respondem - as linhas dele aparecem na mesma
  conversa que as deles.

### A barra lateral mostra quem está trabalhando

```
a cada 5 segundos, e logo depois de enviar / executar agora / chegar uma resposta
  api.js fRefreshAgentActivity        ← pulado enquanto a aba está escondida
    GET /api/admin/agents
      web/api.fListAgents
        exec_client.fListRunningAgents          → /run/boa/exec.sock
          exec_daemon.fVerbListRunningAgents
            fListRunningAgentIds      ← uma varredura de /proc, todos os agentes de uma vez
      cada agente leva `running`
    fSetAgentAvatarActivity           ← data-running no avatar; a própria lista
                                        nunca é reconstruída por um timer
      fBuildAgentActivityArc          ← um retângulo arredondado SVG sobre a borda
  o CSS anima o stroke-dashoffset dele  ← a forma fica parada, o traço aceso
                                          percorre o contorno no sentido horário
```

### Login

```
POST /login
  views.fLoginPage
    auth.fCountRecentFailures         ← 10 a cada 15 minutos por endereço
    auth.fVerifyCredentials           ← argon2id; um e-mail errado também passa pelo hash
    auth.fRecordAttempt
    auth.fLogIn                       ← cookie de sessão, 12 horas
```

---

### Chega uma mensagem de voz

`fHandleMessage → fRouteMessage → fEnqueueTelegram → audio_jobs → fRunOneJob → fDownloadTelegram → fTranscribe → fSubmitTranscript → fSendChatMessageLocked → runner`. A resposta usa a entrega comum do Telegram; o chat web acrescenta a transcrição e o player privado. Configurações → Áudio usa GET/PUT `/api/admin/audio`; os downloads de modelos usam a RPC `install_whisper_model` e consultam o progresso sem bloquear o HTTP.

### API Calls

```text
AgentRun.fSendRecordedRequest → gravador de requisições do BaseProvider → api_calls.fRecordCall
aba API Calls → GET /api/admin/agents/<id>/api-calls
  exec_client.fReadApiCalls → exec_daemon.fVerbReadApiCalls → api_calls.fReadCalls
expandir a requisição → GET /api/admin/agents/<id>/api-calls/<call_id>
  exec_client.fReadApiCallBody → api_calls.fReadBodyChunk → texto JSON transmitido em streaming
  fBeautifyJson → fHighlightJsonElement → DOM seguro
```

### Samba

```text
create_agent → fIndexAgent → samba.fProvisionAgent → samba/ + [agent-xxx]
GET /agents/<id>/samba → read_samba → samba.fReadSettings
PUT /agents/<id>/samba → write_samba → samba.fSaveSettings
  validar → info protegido + testparm → smbpasswd (stdin) → reload/close-share
conexão SMB → preexec do root --check-share <id> → permissões do Samba → uid do agente
delete_agent → samba.fRemoveAgent → remover usuário Linux, diretório pessoal e índice
--backup → tdbbackup + SID do servidor → samba-backup no arquivo tar
--restore → parar serviços → restaurar usuários/dados → substituir o passdb nativo → iniciar
```

## 5. Mapa de pontos de entrada e rotas

### HTTP

| Rota | Método | Handler | Arquivo |
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
| `/api/admin/agents` | GET, POST | `fListAgents` (sempre leva `running` por agente), `fCreateAgent` | `backend/web/api.py` |
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

Tudo o que é API fica sob `/api/`. Tudo sob `/api/admin/` exige uma sessão.

### Sockets Unix

| `/run/boa-web/web.sock` | `0750 boa:boa` | gunicorn | A própria aplicação. Só o `boa-proxy` chega a ele |

| Socket | Modo | Servidor | Verbos |
|---|---|---|---|
| `/run/boa/exec.sock` | `0660 root:boa` | `exec_daemon` | `ping`, `create_agent`, `delete_agent`, `read_agent_info`, `write_agent_info`, `read_system_prompt`, `write_system_prompt`, `read_crontab`, `write_crontab`, `run_now`, `list_running_agents`, `read_samba`, `write_samba`, `read_run_journal`, `read_api_calls`, `read_api_call_body`, `read_usage_summary`, `read_chat`, `read_chat_attachment`, `send_chat_message`, `clear_chat` |
| `/run/boa/agent.sock` | `0666` | `agent_api` | `who_am_i`, `kanban_add_card`, `kanban_move_card`, `kanban_delete_card`, `kanban_list_cards`, `channel_write`, `mail_read`, `mail_delete`, `mail_move`, `mail_forward` |

### Linha de comando

| Comando | Arquivo |
|---|---|
| `runner.py --agent-id NNN [--prompt … or --prompt-on-stdin] [--chat-message … or --chat-message-on-stdin] [--turn-id …] [--dry-run]` | `backend/core/runner.py` |
| `install-update-reinstall-debian.sh --install\|--update\|--reinstall\|--backup [file]\|--restore <file>` | `deploy/` |
| `install-update-reinstall-alpine.sh --install\|--update\|--reinstall\|--backup [file]\|--restore <file>` | `deploy/` |

---

## 6. Análise de impacto

O que quebra se você mudar estes itens.

| Componente | Mudá-lo afeta |
|---|---|
| `paths.fNormalizeAgentId` | **Todos os caminhos do sistema.** É a única validação entre a entrada do usuário e um caminho do sistema de arquivos. Enfraquecê-la transforma qualquer id de agente em path traversal |
| Constantes de `paths.py` | Os quatro serviços, o instalador e as unidades do systemd. Mudar `/opt/boa` significa reinstalar |
| `deploy/haproxy/boa.cfg` | Toda requisição. `accept-proxy` tem de corresponder ao que o HAProxy da máquina envia: com `send-proxy-v2` nesse backend ele é obrigatório; sem isso, o bind recusa toda conexão |
| bind de `backend/web/gunicorn.conf.py` | Tem de continuar sendo um socket Unix. Dar de novo ao gunicorn uma porta e um certificado traz de volta a falha do PROXY antes do TLS |
| `exec_protocol.lKnownVerbs` | A superfície privilegiada. Acrescentar um verbo acrescenta uma forma de o processo web pedir algo ao root. Cada acréscimo precisa do mesmo escrutínio que o primeiro |
| `exec_daemon.fRunPrivilegedCommand` | Todo comando privilegiado. Ele nunca usa um shell; introduzir `shell=True` ali faria de todo nome de agente um ponto de injeção |
| `agent_api.fAuthenticate` | Toda requisição de um agente ao quadro e aos canais. As duas verificações têm de continuar |
| `db.cAppSchema` / `cKanbanSchema` | As instalações existentes. Não há sistema de migrações: os schemas usam `IF NOT EXISTS`, então **colunas novas precisam de código de migração explícito**, não de uma edição do schema |
| `agent_scripts.cMinimumMinuteStep` | Com que frequência um agente pode se agendar. É a única coisa entre um agendamento descuidado e um loop com uma linha de cron na frente |
| `paths.lProtectedAgentFiles` | Quais arquivos vão para a gaveta do root. A migração do instalador e o daemon que cria um agente leem essa lista, então não podem discordar sobre quais são |
| `agents.fBuildAgentInfo` | Só os agentes novos. Os arquivos `info.json` existentes não são tocados, então os campos novos precisam de um caminho de leitura com valor padrão |
| `exec_daemon.fVerbWriteAgentInfo` | **Todo campo de `info.json` que sobrevive a um salvamento.** Ele reconstrói o arquivo chave por chave, então um campo que ele não cita é um campo que a interface descarta em silêncio na primeira vez que alguém aperta Salvar. As listas são lidas por `fReadNameList`, que distingue uma chave ausente (“deixe isto como está”) de uma lista vazia (“tire todas”): lido com `or`, desmarcar a última ferramenta restaurava a lista anterior |
| `skills.fSelectInstalledSkills` | O que chega a um prompt e o que `skill.read` vai abrir. Tanto o índice quanto a ferramenta filtram por ela, então uma habilidade apagada do servidor deixa de ser mencionada em vez de ser prometida e depois falhar |
| Formato neutro de `providers.base` | Todos os adaptadores e o runner |
| Interface de `tool_registry` | Toda ferramenta em `/opt/boa/tools/`, inclusive as que o usuário escreveu |
| `telegram_listener.fIsFromTheConfiguredChat` | Quem pode falar com os seus agentes. O nome de usuário de um bot é público, então esta verificação é a autorização inteira: enfraquecê-la deixa qualquer pessoa que encontre o bot iniciar execuções no seu servidor |
| Assinatura de `channels.fSendMessage` | Todo chamador, e os dois remetentes que recebem dois argumentos. `pReplyToMessageId` é passado ao Telegram e ao Discord, que são os dois canais pelos quais uma pessoa pode responder |
| `discord_markdown.cMaxDiscordLength` | Se a resposta de um agente chega ou não. O Discord recusa um `content` acima de 2000 caracteres, e recusar é o que ele faz - não truncar |
| `agent_routing.fMatchNamedAgent` | Quem uma mensagem alcança, nos **dois** listeners. A correspondência mais longa é o que faz de `@News` e `@News Miner` dois agentes |
| `agent_routing.fBuildStatusReport` | O que /status responde nos dois. Um só relatório, para que os dois não possam discordar sobre quantos serviços existem |
| `discord_listener.fIsFromTheConfiguredChannel` | Qual canal os agentes escutam. Diferente do Telegram, não há uma segunda verificação de quem está falando: quem pode escrever nesse canal pode iniciar execuções |
| `kanban.lStates` | O quadro, a API, o frontend e o prompt de todo agente |
| Formato das entradas de `run_journal` | Tanto o escritor (runner) quanto os leitores (daemon, web). As linhas antigas ficam nos diários: os leitores têm de tolerar campos ausentes |
| `samba` | Ciclo de vida dos agentes, API privilegiada, clientes SMB e o backup/restauração dos dois instaladores. Mantenha intactos a guarda da pasta, a derivação de nome/caminho e o tratamento dos segredos |
| Um arquivo que o daemon lê do diretório pessoal de um agente (`runs.jsonl`, `chat.jsonl`, `memory.md`) | Lido só por meio de `paths.fReadAgentOwnedFile`. Um arquivo novo que o daemon leia de um diretório pessoal também tem de passar por ele, ou o root lê aquilo para onde o agente o apontar - um FIFO que nunca responde, um link para qualquer arquivo da máquina |
| O que um backup guarda (a linha de `tar` de `fDoBackup`) | Um estado novo sob `/opt/boa/` que seja da instalação e não do código tem de ser acrescentado ali, ou uma restauração numa máquina nova o perde |
| Os limites de kernel de uma execução (`runner.cMaxProcesses`, `exec_daemon.cRunTasksMax`, `cRunMemoryMax`) | Uma ferramenta que precise de mais de 1024 tarefas ou de 2 GiB tem de aumentá-los; um navegador já são algumas centenas de threads |
| `runner.py` como caminho | Toda execução agendada. O cron o inicia pelo caminho, quase sem ambiente, então o runner coloca a própria raiz no sys.path: sem isso, `import backend` falha e o traceback vai para o e-mail do cron, que numa máquina de LAN não vai para lugar nenhum |
| `runner.dAnswerLanguageLines` | A linha acrescentada a um prompt de sistema dizendo ao agente em que idioma responder. Escrita NESSE idioma, e diz que se sobrepõe à regra do próprio prompt - uma preferência ao lado de uma regra perde, medido |
| `agent_api.fFilterCardsForAgent` | O que um agente pode saber que existe. Toda leitura do quadro passa por ela, e o orquestrador é a única exceção. Filtrar na ferramenta em vez disso colocaria uma regra de segurança numa descrição da qual o modelo pode ser convencido a abrir mão |
| De que lado fica um balão do chat | Quem está falando. Um cartão é o que se pediu ao agente, então vai à direita, com as mensagens do usuário; o relatório de uma execução agendada é o agente falando, então fica à esquerda |
| `chat.lToolsWorthReporting` | Quais ferramentas fazem uma execução agendada merecer ir para o chat. Todo o resto fica no diário: do contrário, um agente de hora em hora postaria vinte e quatro mensagens de “nada a relatar” por dia |
| `chat.lAskingRoles` | Quais papéis esperam uma resposta. Um papel que abre um turno e não está listado deixa a caixa de mensagem aberta enquanto o agente trabalha; um listado mas nunca fechado fecha a caixa de mensagem para sempre |
| `kanban.cRunNow` | A palavra que o navegador, os agentes e a API enviam no lugar de um timestamp. Transformá-la num horário em qualquer lugar que não seja `fValidateRunAt` perde o `run_mode`, e com ele a diferença entre “agora” e um momento escolhido |
| `chat.cReplayedTurns` | Quanto custa cada mensagem de chat. Cada turno reenviado é pago de novo na mensagem seguinte, então aumentá-lo torna as conversas longas progressivamente mais caras |
| `lTextColours` em `TestThemes` | Quais cores o teste de contraste mede. Uma cor pintada como texto e deixada fora dessa lista é uma cor que nada verifica |
| Um atributo `style=` em qualquer template HTML | Nada: `style-src` é `'self'` sem `unsafe-inline`, então o navegador o descarta. Há um teste que falha se aparecer um |
| `.notice-layer` em `app.css` | Onde aparecem todas as confirmações e todos os erros da aplicação. `position: fixed` é estrutural: `absolute` centraliza no documento em vez de na tela, que é o bug que a camada existe para corrigir |
| Cadeia `.app:has(#vChatPanel…)` e `--status-bar-live-height` em `app.css` | Se a caixa de texto do chat continua acima da barra de status. Um bloco nessa coluna flex sem `min-height: 0`, ou uma altura de `.chat` que deixe de subtrair a altura viva da barra, faz a página voltar a rolar e coloca a caixa de mensagem embaixo da barra |
| `agents.fValidateSchedule` | Se um agendamento vindo de um `.zip` ou de um modelo pode virar um comando num crontab escrito como root. Afrouxá-la (um espaço, um `#`, uma quebra de linha) transforma uma importação em execução de código |
| `agent_home.sExcludedTopNames` / `fIsExcluded` | O que uma exportação pode vazar e uma importação pode plantar: sessões do navegador, `.ssh`, o chat. Remover um nome o deixa passar nas duas direções |
| `agent_package.lManifestKeys` / `cFormatVersion` | Todo `.zip` exportado e todo modelo de todo repositório. Uma chave nova precisa que esta versão a leia; um significado alterado precisa de um número de formato novo |
| `min_support` em `rag_models.json` | Quais parágrafos de uma resposta verificada sobrevivem, para aquele modelo. Aumentado, parágrafos fiéis começam a cair; diminuído, uma citação a um trecho sem relação passa. O que cada valor dos dois modelos remove e deixa passar está na tabela ao lado da verificação em `rag_verify.py`: meça de novo com documentos reais antes de mexer num valor, e atualize a tabela |
| `sha256` ou `dimensions` de um modelo em `rag_models.json` | Toda biblioteca indexada com ele. Uma impressão digital nova é um espaço vetorial novo: cada biblioteca indexa de novo todos os documentos na passada seguinte (`fFollowNewModel`), o que numa grande leva horas |
| `rag_embeddings.fCheckServedModel` / o `--alias` em `rag_runtime.fServe` | Se um vetor pode vir de um modelo diferente do que a biblioteca dele registra. Sem eles, um job que atravesse uma troca de modelo guarda vetores de dois modelos numa só revisão |
| `runner.lRagModesThatSearch` / `fFinishRagAnswer` | Se uma execução documental ou verificada pode entregar texto saído dos próprios pesos do modelo. Tirar um modo da lista, ou a verificação de ausência de trechos, traz de volta respostas sem nenhuma recuperação por trás |
| `rag_search.fSource` | Tudo o que é dito ao modelo sobre um trecho e aquilo para o que uma citação aponta: o bloco de prompt pré-recuperado, `rag.search`, `rag.read` e `fResolveCitations` usam todos ele. Um campo acrescentado a ele também precisa da sua coluna nos três `SELECT`s que o alimentam |
| `rag_embeddings.EngineUnavailable` | Se uma falha de indexação mantém ou descarta trabalho. Lançar um `ValueError` comum numa queda transforma o documento em `error` e apaga os trechos já vetorizados dele; lançar `EngineUnavailable` numa recusa permanente deixa o documento na fila para sempre |
| `rag_store.cSchema` | Só os catálogos criados depois da mudança. Toda biblioteca de agente existente, e todo backup restaurado, mantém a tabela antiga: uma coluna nova também precisa da sua entrada em `rag_store.lAddedColumns`, que `fMigrate` aplica |
| `frontend/static/i18n/en-US.json` | Acrescentar uma chave significa acrescentá-la aos outros catorze, ou essa string recorre ao inglês. `TestTranslations` falha com uma chave ausente, um `{placeholder}` perdido e um caminho ou nome de ferramenta traduzido |

---

## 7. Pontos de extensão

### Um provedor novo

1. Escreva `backend/providers/<name>.py` com uma classe que estenda
   `base.BaseProvider`, definindo `cProviderName`, `cDefaultModel`,
   `cDefaultBaseUrl` e implementando `fSendMessages`.
2. Acrescente uma linha a `factory.dProviderRegistry`.
3. Acrescente o nome a `agents.lSupportedProviders`.
4. Se ele não precisar de chave, acrescente-o a `factory.lSelfHostedProviders`.
5. Opções extras (como o `thinking` do DeepSeek) vão em `lExtraConfigKeys`; a
   factory mapeia `reasoning_effort` → `pReasoningEffort` automaticamente.

Não o junte a um adaptador existente só porque o dialeto coincide. Um arquivo
por provedor é proposital.

### Uma ferramenta nova

Crie um `.py` em `/opt/boa/tools/` declarando:

```python
cToolName = "namespace.verb"
cToolDescription = "What the model is told it does."
dToolSchema = {"type": "object", "properties": {...}, "required": [...]}

def fRunTool(pArguments, pContext):
  return "text the model sees"
```

Ela roda como o agente que a chama. Se precisar de algo que os agentes não podem
alcançar, acrescente em vez disso um verbo à API dos agentes e chame-o por meio
de `agent_api_client`.

O arquivo tem de pertencer ao root: a aplicação o importa como código.

### Uma habilidade nova

Crie um diretório em `/opt/boa/skills/` com um `SKILL.md` dentro:

```markdown
---
name: BackupVerification
description: One line. This is what every run pays for.
---

The procedure, at whatever length it needs.
```

Nada a registrar e nenhum reinício: `fListSkills` lê o diretório, então ela
aparece na interface no próximo carregamento da página. Marque-a num agente, dê
a esse agente `skill.read`, e ela estará no prompt dele na próxima execução.

Qualquer outra coisa no diretório vai junto com a habilidade. Ele é legível por
todos, então a habilidade pode dizer “rode `verify.sh` neste diretório” e o
agente consegue.

O nome é o nome do diretório: letras, dígitos e hífens, começando com uma letra.
O `name:` no cabeçalho é o que uma pessoa vê na lista; o nome do diretório é o
que um agente pede.

### Uma operação privilegiada nova

1. Acrescente a constante do verbo a `exec_protocol` e a `lKnownVerbs`.
2. Escreva `fVerb<Name>` em `exec_daemon` e acrescente-o a `dVerbHandlers`.
3. Acrescente um wrapper em `exec_client`.

Valide todo argumento antes que ele chegue a um caminho ou a uma linha de
comando, e mantenha o verbo específico. Um verbo geral o bastante para ser
reutilizável costuma ser um verbo geral o bastante para ser abusado.

### Um canal novo

Só envio:

1. Escreva `fSendTo<Name>` em `channels.py`.
2. Acrescente-o a `lChannels` e `dChannelSenders`.
3. Acrescente os campos dele a `dChannelFields` em
   `frontend/static/js/settings.js`, e os que forem credenciais a
   `lSecretChannelFields` ali e a `lSecretConfigFields` em `channels.py`.

Também recebimento, que é o que o torna uma conversa:

4. Escreva `fRead<Name>Messages` em `channels.py`, devolvendo as mensagens da
   mais antiga para a mais nova.
5. Escreva `<name>_inbox.py`: duas tabelas em `db.cAppSchema` e o agente
   selecionado numa configuração.
6. Escreva `<name>_listener.py` sobre `agent_routing`, que já contém a lista de
   agentes, a correspondência de nomes, a resposta fechada e o relatório de
   estado. O que sobra é o protocolo.
7. Escreva `<name>_texts.py` para as frases que esse canal diz de outro jeito,
   recorrendo a `telegram_texts` para o resto.
8. `deploy/systemd/boa-channel-<name>.service` e um serviço em
   `deploy/openrc/`, o nome
   em `lServices` e nos sete lugares em que o instalador do Debian nomeia as
   suas unidades, e em `system_info.lBoaServiceNames`. Se o nome no OpenRC for
   diferente, acrescente o mapeamento em `system_info.dOpenRcServiceNames`.
9. O interruptor dele em `dChannelSwitches`, a chave `chat.source<Name>` nos
   quinze catálogos, e `<name>` em `exec_daemon.lKnownChatSources`.

### Um idioma novo

Vêm quinze: `de-DE`, `en-GB`, `en-US`, `es-AR`, `es-ES`, `fr-FR`, `he-IL`,
`hi-IN`, `it-IT`, `ja-JP`, `ko-KR`, `pt-BR`, `pt-PT`, `ru-RU`, `zh-CN`. Um décimo
sexto são sete lugares, e os testes citam cada um deles:

1. Copie `frontend/static/i18n/en-US.json` e traduza os valores.
2. Acrescente a tag a `lSupportedLanguages` em `frontend/static/js/i18n.js`.
3. Acrescente uma `<option>` aos três seletores: dois em
   `frontend/templates/settings.html`, um em `login.html`, por tag.
4. Acrescente uma linha a `runner.dAnswerLanguageLines`, escrita NESSE idioma.
5. Acrescente um bloco a `telegram_texts.dTexts` e a tag dele ao
   `lSupportedLanguages` desse módulo, ou o bot recorre ao inglês. Acrescente um
   a `discord_texts.dTexts` também: ele contém as três frases que o Discord diz
   de outro jeito, e um idioma ausente dele recebe essas três em inglês.
6. Traduza a documentação a partir dos arquivos en-US: `README.<tag>.md` na
   raiz, `doc/CODE.<tag>.md` e `doc/MANUAL.<tag>.md`. Acrescente o idioma à
   linha de idiomas no topo de cada README, em ordem alfabética de tag. O en-US
   é a fonte de todos os outros idiomas e mantém os nomes sem tag:
   `README.md`, `doc/CODE.md`, `doc/MANUAL.md`.
7. Se ele é escrito da direita para a esquerda, acrescente a tag dele a
   `lRightToLeftLanguages` em `frontend/static/js/i18n.js`. Mais nada: a folha
   de estilos já usa propriedades lógicas (veja “Da direita para a esquerda”
   acima).

`TestTranslations` em `tests/test_web.py` falha com uma chave ausente, uma a
mais, uma string vazia, um `{placeholder}` perdido, um caminho ou nome de
ferramenta traduzido, um arquivo fora de ordem, um seletor que não oferece o
idioma, uma linha de prompt ausente e um bloco do Telegram ausente. Os seis
idiomas não latinos também são verificados quanto a estarem de fato escritos no
próprio alfabeto, porque um arquivo de strings em inglês sob um nome russo passa
em todas as outras verificações. `TestExampleAgents` em `tests/test_tools.py`
falha com um idioma sem o seu README, CODE ou MANUAL, ou com um README que não
aponta para o README de todos os outros idiomas;
`TestTheCodeDocumentsPointAtRealLines` em `tests/test_web.py` falha com um CODE
cujas referências `file.py:line` diferem das do inglês.

O que uma tradução pode mudar: um nome de arquivo que o texto em inglês dá como
EXEMPLO, como `check-disk.sh`. Nada procura por eles.

### Um modo de resposta RAG novo

1. Acrescente-o aos modos permitidos em `rag_settings.fValidateSettings` e ao
   enum `mode` em `backend/web/rag_api_doc.py`.
2. Dê a ele a sua regra em `rag_search.fPrompt`, dizendo o que o runner impõe.
3. Em `runner.py`, acrescente-o a `lRagModesThatSearch` se o modelo tiver de
   pesquisar, e a `fCheckRagAnswer` / `fFinishRagAnswer` se as respostas dele
   forem verificadas.
4. Uma `<option>` em `frontend/templates/agent_rag.html`, o fallback dele em
   `dRagModeHints` em `rag.js`, e `rag.<mode>` mais `rag.modeHint.<mode>` nos
   quinze arquivos i18n.
5. Testes em `tests/test_rag.py` (`TestRagInAgentRun`), com o provedor
   roteirizado e um `rag_embeddings.fEmbed` falso.

### Um modelo de vetorização novo

1. Uma entrada em `backend/core/rag_models.json`: a URL do GGUF fixada num
   commit (nunca num branch), `size` e `sha256` tirados da API do repositório,
   `dimensions`, `context`, o `pooling` que o model card dele pede, e os
   prefixos de consulta e de trecho dele. `TestEmbeddingModelChoice` verifica
   que a entrada está completa.
2. Rode-o ao lado do motor instalado na biblioteca de teste e meça-o do jeito
   que a aplicação o usa (o comentário acima da tabela em `rag_verify.py` diz
   como): o `min_support` dele é o maior valor que deixa passar menos de 1% das
   citações a trechos de outro assunto, o `min_similarity` dele fica entre
   perguntas relacionadas e não relacionadas. Acrescente as linhas dele a essa
   tabela.
3. O pico de memória dele tem de caber no `MemoryMax` de
   `deploy/systemd/boa-embeddings.service`; escreva-o, e quanto mais devagar ele
   indexa que o EmbeddingGemma, como `memory_mb` e `relative_indexing_time`.
4. A lista em Configurações → RAG e a rota de download vêm do catálogo; só as
   tabelas em `doc/MANUAL*.md` e as descrições do enum em `rag_api_doc.py`
   precisam do modelo novo pelo nome.

### Um campo novo de informações do documento

1. Acrescente a coluna a `rag_store.cSchema` e a `rag_store.lAddedColumns`, ou
   as bibliotecas existentes não a terão.
2. Acrescente a chave, no lugar dela, a `rag_store.lMetadataKeys`, e qualquer
   verificação de formato de que ela precise a `rag_store.fAction`.
3. Se o modelo deve vê-lo, acrescente `d.<column>` aos três `SELECT`s em
   `rag_search` e o campo a `rag_search.fSource`.
4. Acrescente-o ao schema `metadata` em `backend/web/rag_api_doc.py`.
5. Acrescente-o, no lugar dele, à lista de campos em
   `frontend/static/js/rag.js`.
6. Acrescente `rag.<key>` aos quinze arquivos `frontend/static/i18n/*.json`.
7. Cubra-o em `tests/test_rag.py`; o teste de migração já monta um catálogo sem
   cada uma das colunas de `lAddedColumns`.

### Um modelo de agente novo

Os modelos de agente ficam no repositório de modelos, não aqui:

1. Uma pasta `<name>/` em `bunch-of-aigents-templates`, com o mesmo nome que o
   `name` do modelo (`^[a-z][a-z0-9-]{0,39}$`).
2. `agent.json`: `format` 1, `name`, `description` nos quinze idiomas,
   `tools`, `schedules`, `limits` e, se ele precisar da biblioteca, `rag`. O
   jeito mais rápido é montar o agente aqui, exportá-lo e descompactá-lo lá.
3. `system-prompt.md`, em inglês, terminando com a regra sobre o idioma da
   resposta.
4. `README.md`, em en-US, para quem lê aquele repositório: para que serve o
   agente, o que ele faz, do que precisa antes, o que não vai fazer, com o que
   vem e como instalá-lo. A aplicação o ignora.
5. Rode os testes deste repositório: `TestExampleAgents` lê o clone ao lado
   deste com `agent_package` e falha com um modelo que a aplicação recusaria,
   uma ferramenta que não existe, um idioma ausente, ou um README que falta ou
   que não cita as ferramentas e os agendamentos do modelo.
6. Uma linha na tabela de modelos de cada MANUAL daqui, um por idioma, e uma,
   com link para o README dele, nos três READMEs de lá.

### Uma página nova

1. Uma rota em `backend/web/views.py` que devolva `render_template`.
2. Um template que estenda `app_base.html`.
3. Um `<li>` no `nav` de `app_base.html`.
4. O próprio JS dela em `frontend/static/js/`, começando com
   `await fWaitForTranslations()` antes de renderizar qualquer coisa.
