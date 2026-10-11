# Manual

Como usar o Bunch of AIgents no dia a dia.

## Índice

1. [O que faz](#o-que-faz)
1. [Onde corre](#onde-corre)
1. [Se estiver em Alpine](#se-estiver-em-alpine)
1. [Instalação](#instalação)
1. [Atualizar e reinstalar](#atualizar-e-reinstalar)
1. [Abrir a aplicação](#abrir-a-aplicação)
1. [Iniciar sessão](#iniciar-sessão)
1. [Primeiro arranque](#primeiro-arranque)
2. [A interface](#a-interface)
3. [De onde vem um novo agente](#de-onde-vem-um-novo-agente)
3. [Criar o seu primeiro agente](#criar-o-seu-primeiro-agente)
4. [Falar com um agente](#falar-com-um-agente)
5. [Definições do agente](#definições-do-agente)
5. [Exportar um agente](#exportar-um-agente)
5. [Pastas partilhadas Samba](#pastas-partilhadas-samba)
6. [Dar um modelo a um agente](#dar-um-modelo-a-um-agente)
5. [Escrever um prompt de sistema](#escrever-um-prompt-de-sistema)
6. [Escolher ferramentas](#escolher-ferramentas)
7. [Dar uma competência a um agente](#dar-uma-competência-a-um-agente)
8. [Dar um navegador a um agente](#dar-um-navegador-a-um-agente)
9. [Tetos de gasto](#tetos-de-gasto)
8. [Agendar um agente](#agendar-um-agente)
9. [O quadro kanban](#o-quadro-kanban)
10. [Temas](#temas)
1. [Configuração dos canais](#channel-setup)
1. [Telegram](#telegram)
1. [Discord](#discord-setup)
1. [Slack](#slack)
1. [Mattermost](#mattermost)
1. [X](#x)
12. [O orquestrador](#o-orquestrador)
13. [Cópias de segurança e restauro](#cópias-de-segurança-e-restauro)
13. [Serviços](#serviços)
13. [Segurança](#segurança)
14. [Quando algo não funciona](#quando-algo-não-funciona)
1. [Transcrição de áudio](#transcrição-de-áudio)
1. [Licença](#licença)

---

- [Bibliotecas locais de documentos (RAG)](#bibliotecas-locais-de-documentos-rag)

## O que faz

- **Um agente é um utilizador Linux.** Criar um na interface web cria
  `agent-007` no sistema, com uma pasta pessoal que nenhum outro agente
  consegue ler. Esse é o isolamento: o do kernel, não uma sandbox escrita em
  Python.
- **Os agentes correm segundo o seu próprio horário.** Cada um tem o seu
  próprio crontab, que pertence ao seu próprio utilizador e é executado por
  ele, por isso um agente acorda, faz o seu trabalho e termina.
- **Pode falar com eles.** Clicar num agente abre uma conversa: peça-lhe que faça
  algo e ele usa as suas ferramentas e responde quando terminar. A conversa
  fica memorizada.
- **Uma conversa por agente, não uma por pessoa.** Um cartão cuja hora chega é
  publicado nessa mesma conversa quando a execução começa, e a resposta aparece
  por baixo dele, por isso a conversa de um agente é tudo o que lhe pediram que
  fizesse - por si ou por outro agente - e o que fez a esse respeito.
- **Partilham um quadro kanban.** Os agentes acrescentam cartões, movem-nos e
  veem o trabalho uns dos outros. Pode acompanhar tudo em `/kanban/` em vez de
  ler logs.
- **Qualquer modelo, na nuvem ou auto-alojado.** Vêm incluídos vinte e cinco
  fornecedores - Anthropic, OpenAI, Google, DeepSeek, Mistral, Qwen, xAI e os
  restantes; os routers que estão à frente deles, OpenRouter, Groq, Together,
  Vercel e outros; e Ollama, llama.cpp e vLLM no seu próprio hardware. Cada
  agente escolhe o seu, com um modelo de reserva para quando esse estiver em
  baixo.
- **Tetos de gasto que travam mesmo.** Tokens, passos, segundos e execuções
  por dia, por agente. Sem eles, um agente sem supervisão numa API paga é uma
  fatura em aberto.
- **Memória configurável.** Escolha o limite de memória de cada agente nas suas
  definições, de 1000 a 1 000 000 de caracteres (8000 por predefinição). As
  escritas demasiado grandes são rejeitadas sem cortar o texto nem substituir a
  memória guardada.
- **Uma biblioteca de documentos por agente.** Carregue livros em PDF, EPUB, TXT
  ou Markdown. A extração, o OCR e a vetorização ficam locais; os agentes
  recuperam as passagens relevantes e citam as suas fontes. Configure-a em
  **RAG**. O modelo de vetorização é o EmbeddingGemma 300M por predefinição;
  uma máquina com processador e memória de sobra pode mudar para o
  Qwen3-Embedding 0.6B em **Definições → RAG**.
- **Agentes que pode levar para outro lado.** O separador **Exportar** de um
  agente transfere-o como `.zip` - opcionalmente com a sua memória, o seu
  modelo, a sua biblioteca e os ficheiros da sua pasta pessoal, nunca com uma
  chave - e o **+** importa-o aqui ou noutra instalação. Os agentes já prontos
  vêm do
  [repositório de modelos](https://github.com/nipegun/bunch-of-aigents-templates).
- **Ferramentas que pode alargar.** Cada ferramenta é um ficheiro `.py` em
  `/opt/boa/tools/`. Coloque lá um novo e ele aparece em **Definições →
  Ferramentas**, agrupado em subseparadores como Automação e Navegador.
- **Competências que partilham.** Um procedimento escrito uma vez em
  `/opt/boa/skills/` pode ser dado a tantos agentes quantos quiser. O que um
  agente aprende sozinho morre na sua própria memória; uma competência não.
- **Um navegador para cada um, com as suas próprias sessões.** Um agente pode
  iniciar sessão num site, preencher um formulário e clicar - não apenas ler
  uma página - e os seus cookies vivem na sua própria pasta pessoal 0700, por
  isso a sessão iniciada por um agente não é a sessão de todos os agentes.
- **Converse por Telegram, Discord, X, Slack ou Mattermost.** Liste os agentes com
  `/agents` no Telegram, `/boa agents` no Slack ou `!agents` no Discord e
  Mattermost. Fale com um agente ou responda à mensagem dele para iniciar
  uma execução. Os dois lados também aparecem no chat web do agente.
- **Áudio do Telegram.** **Definições → Áudio** seleciona o whisper.cpp local
  ou OpenAI, Groq, Mistral, Together AI, Hugging Face ou Cloudflare, usando uma
  chave de API já guardada. São oferecidos os 30 modelos nativos, com
  transferência a pedido. Uma resposta de voz chega ao agente original como
  texto e aparece na conversa web, com reprodução opcional do áudio.
- **Uma pasta partilhada para cada um.** A pasta `samba/` de cada agente é uma
  partilha SMB com o nome do seu utilizador Linux, por isso pode lá deixar
  ficheiros a partir de Windows, Linux ou macOS.
- **Quinze idiomas.** Alemão, inglês (Reino Unido e EUA), espanhol (Espanha e
  Argentina), francês, hebraico, hindi, italiano, japonês, coreano, português (Brasil e
  Portugal), russo e chinês simplificado. A interface, a linha que diz aos seus
  agentes em que idioma devem responder, e o que dizem os bots dos canais.

Foi feito para uma pessoa que o executa na sua própria LAN.

## Onde corre

Dois sistemas, e em cada um deles o init faz parte do requisito, não é um
pormenor:

- **Debian com systemd como PID 1.** Os treze serviços são unidades systemd.
  Num Debian que arranca com outra coisa qualquer não há nada que os inicie,
  por isso o instalador verifica `systemctl is-system-running` antes de tocar
  na máquina e recusa-se se o systemd não estiver lá. Não o tente numa máquina
  assim: a resposta não vai mudar.
- **Alpine com OpenRC.** Os treze serviços são scripts OpenRC supervisionados
  com `supervise-daemon`. Não é preciso instalar nada antecipadamente - o
  próprio instalador acrescenta o `openrc` quando a máquina não o tem.

Verifique-o em Debian com `systemctl is-system-running`: tem de responder
(`running`, `degraded`, `starting`), e não imprimir «System has not been booted
with systemd as init system (PID 1)». Um contentor precisa de `systemd
systemd-sysv dbus` instalados e de `/sbin/init` como comando.

Além do sistema de init, precisa de:

- Acesso de `root`. Nenhum dos instaladores usa `sudo`, nem precisa dele.
- Cerca de 500 MB de disco para a aplicação e o seu ambiente Python.
- `haproxy`, instalado pelo instalador. Termina o TLS, porque o cabeçalho PROXY
  que o HAProxy da máquina envia chega antes do handshake TLS e só um proxy o
  consegue ler nesse ponto.
- Um modelo com que falar: ou uma chave de API de um fornecedor na nuvem, ou
  Ollama, llama.cpp ou vLLM a correr num sítio a que consiga chegar.

O instalador também compila o **whisper.cpp v1.9.4** em `/opt/boa/whisper/`,
instala o FFmpeg e transfere o modelo multilingue `base` (cerca de 142 MiB
adicionais). A compilação, as dependências do sistema e o navegador precisam de
espaço em disco adicional. Se faltar o interpretador de Python, é instalado
antes de se verificar a sua versão.

Tudo o resto neste manual é igual nos dois.

## Se estiver em Alpine

Todos os comandos deste manual que referem `systemctl` ou `journalctl` são os
de Debian. A aplicação é a mesma em Alpine; o que muda é o sistema de init e o
sítio para onde vão os logs:

| Em Debian | Em Alpine |
|---|---|
| `systemctl status boa-web` | `rc-service boa-web status`, ou `rc-status` para os dez |
| `systemctl restart boa-web` | `rc-service boa-web restart` |
| `journalctl -u boa-web -f` | `tail -f /opt/boa/logs/boa-web.log` |
| `install-update-reinstall-debian.sh` | `install-update-reinstall-alpine.sh` |

Falta lá uma funcionalidade, e não vai voltar: não há navegador, porque o
Playwright não publica nenhuma build para musl. As ferramentas de navegador
ficam na lista e dizem-no quando um agente chama uma delas.

---

## Instalação

Um instalador por distribuição, e ambos aceitam as mesmas flags. Execute-o como
`root`.

### Em Debian

> **O systemd tem de estar a correr na máquina.** Execute primeiro `systemctl
> is-system-running`: se imprimir «System has not been booted with systemd as
> init system (PID 1). Can't operate.», pare aqui. Todos os serviços que isto
> instala são unidades systemd, por isso não haveria nada que os iniciasse, e o
> instalador recusa-se por essa razão em vez de o deixar com uma instalação que
> não serve nada.

```bash
curl -fsSL https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-debian.sh \
  | bash -s -- --install --email you@example.com
```

Se o `curl` não estiver instalado - um Debian mínimo muitas vezes não tem nem
esse nem o `wget` - instale-o primeiro, ou a linha acima imprime `curl: command
not found` e para:

```bash
apt-get update && apt-get install -y curl
```

Ou transfira primeiro o instalador e leia-o antes de o executar, que é o melhor
hábito:

```bash
wget https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-debian.sh
less install-update-reinstall-debian.sh
chmod +x install-update-reinstall-debian.sh
./install-update-reinstall-debian.sh --install --email you@example.com
```

### Em Alpine Linux

As mesmas flags, um script diferente: escreve serviços OpenRC em vez de
unidades systemd. Uma linha, com `wget` e canalizada para `sh`, porque um
Alpine acabado de instalar não tem nem `curl` nem bash, e esses dois são os do
BusyBox:

```bash
wget -qO- https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-alpine.sh \
  | sh -s -- --install --email you@example.com
```

Use `curl -fsSL` em vez de `wget -qO-` numa máquina que o tenha - e, se o
fizer, vigie essa linha, porque `curl: not found` canalizado para `sh` imprime
o seu erro e depois **termina com êxito**, sem ter instalado nada.

O instalador é shell POSIX e não bash pela mesma razão que o `wget`: um Alpine
acabado de instalar não tem nenhum bash a que o `| bash -s --` possa chegar.
Instala o bash pelo caminho - cada agente recebe uma shell bash - por isso,
numa máquina que já o tenha, `| bash -s --` funciona igualmente bem.

Ou transfira-o primeiro e leia-o antes de o executar:

```bash
wget https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-alpine.sh
less install-update-reinstall-alpine.sh
chmod +x install-update-reinstall-alpine.sh
./install-update-reinstall-alpine.sh --install --email you@example.com
```

Há duas coisas que mudam quando está a funcionar, e ambas são obra do sistema,
não de uma decisão:

- **Sem navegador.** O Playwright não publica nenhuma build para musl e o
  Alpine não empacota nenhuma, por isso `browser.open` e as restantes dizem-no
  quando um agente chama uma delas. `web.fetch` e `rss.fetch` funcionam como em
  qualquer outro lado.
- **`rc-status` em vez de `systemctl status`**, e `rc-service boa-web
  restart` em vez de `systemctl restart boa-web`. Veja
  [Se estiver em Alpine](#se-estiver-em-alpine).

Em Alpine, os serviços libertam a saída SSH do instalador, por isso o
instalador devolve o controlo da sessão quando termina.

### O que o instalador faz

1. Cria o utilizador de sistema `boa` e a árvore em `/opt/boa/`.
2. Instala as dependências de Python em `/opt/boa/venv/`.
3. Gera um certificado TLS autoassinado, a não ser que tenha deixado um
   `fullchain.pem` e um `privkey.pem` seus em `/opt/boa/certificates/`.
4. Pergunta se deve servir a aplicação em 11080/11443 atrás de um HAProxy em
   80 e 443, ou diretamente em 80 e 443. Passe `--ports proxied|direct` para
   responder antecipadamente. A resposta fica guardada, por isso `--update`
   nunca volta a perguntar nem a muda às escondidas. Escolher `direct` retira
   de serviço o HAProxy da própria máquina - parado, fora de todos os runlevels
   ou mascarado, e o seu `/etc/haproxy/haproxy.cfg` apagado se foi este
   instalador que o escreveu, ou guardado como
   `haproxy.cfg.before-boa.<date>` se foi outra pessoa - para que nada ocupe o
   80 e o 443 no arranque seguinte. O pacote haproxy em si fica: o proxy da
   própria aplicação é esse binário.
5. Cria um agente: `manager`, o orquestrador. Todos os outros são um agente
   vazio, um `.zip` exportado de um agente ou um modelo do
   [repositório de modelos](https://github.com/nipegun/bunch-of-aigents-templates) -
   `web-navigator`, `os-watcher`, `mail-watcher` e outros - escolhido quando
   carrega em **+**. O agente vazio é a primeira opção oferecida.
6. Instala e inicia os serviços indicados em [Serviços](#serviços): unidades
   systemd em Debian, serviços OpenRC supervisionados com `supervise-daemon`
   em Alpine.
7. Escreve o que fez, e a sua palavra-passe de início de sessão, em
   `/opt/boa/logs/install.log` (root, modo 0600).
8. Pede à aplicação a sua página de início de sessão antes de dizer que
   terminou. Se a página não chegar, di-lo, escreve nesse mesmo log o estado da
   máquina naquele momento - o que o curl fez do pedido, se há alguma coisa a
   escutar na porta, o estado dos serviços e as últimas linhas do que
   imprimiram - e indica o log em vez de anunciar êxito. Um `--update` também
   repõe primeiro a versão anterior.

### Onde está a palavra-passe

O endereço de e-mail que indicar é o único início de sessão. A palavra-passe é
gerada para si; leia-a com:

```bash
cat /opt/boa/logs/install.log
```

Esse único ficheiro é as duas coisas: o log completo da instalação e as
credenciais que ela gerou. A página de início de sessão indica-o, para que
ninguém tenha de se lembrar de onde está.

## Atualizar e reinstalar

```bash
./install-update-reinstall-debian.sh --update      # mantém os agentes e os dados
./install-update-reinstall-debian.sh --reinstall   # apaga tudo primeiro
```

Em Alpine são as mesmas duas flags, no outro script:

```bash
./install-update-reinstall-alpine.sh --update
./install-update-reinstall-alpine.sh --reinstall
```

`--reinstall` apaga todos os agentes, pastas pessoais, crontabs e o quadro
kanban. Pede confirmação, a não ser que passe `--yes`.

Uma instalação que morreu a meio - uma transferência que falhou, uma rede que
caiu - termina-se executando `--install` outra vez: retoma onde parou, e
`--update` avisa se encontrar uma.

As flags de cópia de segurança, `--backup` e `--restore`, são explicadas em
[Cópias de segurança e restauro](#cópias-de-segurança-e-restauro).

## Abrir a aplicação

No modo predefinido `proxied`, o HAProxy da própria aplicação escuta em
`127.0.0.1:11443` (HTTPS) e `127.0.0.1:11080` (HTTP, que redireciona). Essas
portas não são acessíveis de fora do servidor: é o HAProxy da própria máquina
que serve a LAN, e reencaminha para o 11443 com `send-proxy-v2` para que o
endereço real do cliente sobreviva. No modo `direct` a própria aplicação escuta
no 80 e no 443, sem nada à frente.

Com isso no sítio, abra:

```
https://your-server/
```

O certificado é autoassinado, a não ser que tenha deixado certificados seus em
`/opt/boa/certificates/`, por isso o navegador vai avisá-lo uma vez. Antes de escrever a palavra-passe, confirme a impressão digital dele como explicado abaixo.

### Confirmar o certificado

Ninguém se responsabiliza por um certificado autoassinado. Na primeira ligação, o navegador não consegue distinguir o certificado deste servidor de um que outra pessoa da sua rede apresente no lugar dele; por isso o aviso sozinho não prova nada, mas a impressão digital prova. No próprio servidor, a partir da consola ou por SSH, execute como `root`:

```bash
boa fingerprint
```

Mostra os nomes do certificado e a impressão digital SHA-256. O instalador também mostra a impressão digital no fim de cada instalação, atualização, reinstalação ou restauro, e escreve-a em `/opt/boa/logs/install.log`. No navegador, abra os detalhes do certificado a partir da página do aviso ou do cadeado e compare a impressão digital SHA-256 com essa. Escreva a palavra-passe só se coincidirem. Para deixar de ver o aviso, importe `/opt/boa/certificates/fullchain.pem` para os certificados de confiança do navegador ou do sistema operativo, depois de as impressões digitais coincidirem.

Os certificados novos levam os nomes da máquina, `localhost` e os endereços dela, e estão marcados como certificados de servidor. Uma instalação anterior mantém o certificado que tem. Para gerar um novo, apague `fullchain.pem` e `privkey.pem` de `/opt/boa/certificates/` e execute `--update`; a impressão digital muda, por isso confirme-a outra vez.

### Como deve ser o HAProxy da máquina

O backend que aponta para esta aplicação precisa de duas coisas:

```
backend https-out
  mode tcp
  server srv-https-out 127.0.0.1:11443 check port 11080 send-proxy
```

- **`send-proxy`**, para que o endereço real do cliente chegue à aplicação. Sem
  ele, todos os pedidos parecem vir de 127.0.0.1 e o limite de tentativas de
  início de sessão deixa de ser por endereço.
- **`check port 11080`**, para que a verificação de saúde bata à porta HTTP
  simples e não à de TLS. Uma verificação TCP contra a porta TLS liga-se e
  desliga sem handshake, e o HAProxy da própria aplicação regista cada uma
  como uma falha de handshake SSL: uma linha a cada dois segundos, para
  sempre. As duas portas pertencem a um só processo, por isso se uma responde
  a outra está lá. Não acrescente `check-send-proxy`: o 11080 não aceita o
  protocolo PROXY.
- **Nada de `option ssl-hello-chk`.** O seu ClientHello é anterior ao TLS 1.2,
  por isso um backend que exige TLS 1.2 - este, e qualquer Apache ou nginx
  moderno - falha a verificação e fica marcado como em baixo para sempre. O
  sintoma é um 503 vindo de um serviço que está a funcionar perfeitamente. Um
  `check` simples já verifica que a porta responde.

## Iniciar sessão

Abra `https://your-server/` e inicie sessão com o endereço de e-mail que deu ao
instalador e a palavra-passe que ele gerou. Se não a tiver:

```bash
cat /opt/boa/logs/install.log
```

Esse ficheiro é o log completo da instalação, com as credenciais no fim, e a
página de início de sessão indica-o precisamente para este momento.

**Terminar sessão** abre uma confirmação no centro do ecrã. Confirme para
terminar a sessão, ou escolha **Cancelar** ou carregue em Escape para continuar
com a sessão iniciada.

Há uma única conta. Altere a sua palavra-passe em **Definições → Conta**.
Alterá-la pede também a atual: é isso que faz dela uma alteração feita por si
e não por quem encontrar o navegador aberto. Também termina todas as outras
sessões, em todos os outros dispositivos, de uma só vez - que é precisamente o
objetivo de a alterar quando acha que mais alguém a tem.

Da primeira vez que abrir a aplicação depois de uma atualização, ela pede-lhe
que inicie sessão outra vez. As sessões de antes da atualização não guardam
registo de quando foram concedidas, e a resposta a «não sei dizer» é
perguntar.

Depois de dez tentativas falhadas a partir do mesmo endereço, o início de
sessão fica fechado durante quinze minutos, também para palavras-passe
corretas. Depois de cem tentativas falhadas de todos os endereços juntos nesses quinze minutos, fica fechado para toda a gente até a contagem descer: o endereço vem de um cabeçalho que qualquer programa do servidor pode escrever, por isso um limite só por endereço poderia ser contornado mudando de endereço.

### Redefinir a palavra-passe pelo terminal

Instalação, reinstalação e atualizações instalam `/usr/local/bin/boa`. Para redefinir a conta web pelo terminal do servidor, execute como `root`:

```bash
boa passwd
```

O comando pede a nova palavra-passe duas vezes sem exibi-la. Ela precisa ter pelo menos 8 caracteres. O e-mail permanece igual e todas as sessões existentes são revogadas imediatamente; não é necessário saber a palavra-passe anterior nem reiniciar serviços.

Uma entrada JSON chamada `administrator_password_changed` é acrescentada a `/opt/boa/logs/install.log`, com data UTC, e-mail e a nova palavra-passe legível. O conteúdo anterior é preservado. O ficheiro continua `root:root 0600`; se estiver ausente, é recriado. Consulte a última entrada correspondente para recuperar as credenciais.

Para automatizar, `boa passwd --password-stdin` lê uma linha UTF-8 da entrada padrão, até 64 KiB. A palavra-passe nunca aparece como argumento do comando nem na saída de sucesso.

## Primeiro arranque

1. Inicie sessão com o seu e-mail e a palavra-passe gerada.
2. Se o agente for usar um fornecedor na nuvem, guarde primeiro a sua chave em
   **Definições → Chaves de API**: a lista de fornecedores só oferece
   fornecedores na nuvem que tenham chave (veja [Chaves de API](#chaves-de-api)).
3. Carregue em **+** na barra lateral para criar o seu primeiro agente.
4. Escolha o fornecedor e o modelo. Para o Ollama na mesma máquina, os valores
   predefinidos já estão certos. Para faturar só este agente a outra conta,
   dê-lhe uma chave própria (veja
   [Dar um modelo a um agente](#dar-um-modelo-a-um-agente)).
5. Escreva o seu prompt de sistema: para que serve e o que significa
   «concluído».
6. Dê-lhe as ferramentas de que precisa. Comece pelas do kanban.
7. Carregue em **Executar agora** e acompanhe o quadro.
8. Quando fizer o que quer, dê-lhe um horário.

## A interface

O logótipo azul circular mostra três agentes robóticos com painéis faciais
claros, viseiras escuras e olhos azuis, de fato preto, camisa branca e gravata
escura. Aparecem da cintura para cima, com um agente central maior. O logótipo
aparece na página de início de sessão, na barra lateral e no separador do
navegador.

A barra lateral à esquerda lista os seus agentes. Cada um mostra o seu id, o
seu nome, quantas vezes correu e quantos tokens gastou. Todas as caixas têm a
mesma altura, por isso um nome comprido é cortado com reticências - passe o
rato por cima para o ler por inteiro. O quadrado à volta do
id tem um contorno verde quando o agente está ativado e vermelho quando não
está.

**Quando um agente está a trabalhar, um segmento aceso percorre esse anel verde
no sentido dos ponteiros do relógio.** Diz-lhe
que o agente está a meio de uma execução neste preciso momento - não o que está
a fazer, apenas que está a fazer alguma coisa. Começa a girar assim que lhe
envia uma mensagem na conversa ou carrega em **Executar agora**, e para quando
a execução termina, quer a execução tenha vindo de si, do seu horário ou de um
cartão cuja hora chegou. O anel é verificado a cada poucos segundos, por isso
pode ficar um instante atrasado.

No fundo da barra lateral, dois pontos mostram se os serviços em segundo plano
estão a correr. Se algum deles estiver vermelho, os agentes não vão correr —
veja [Quando algo não funciona](#quando-algo-não-funciona).

O botão **+** cria um agente.

## O agente com que começa

A instalação cria exatamente um.

**`manager` (agent-000)** coordena os outros. Divide objetivos em cartões e
distribui-os. Está ativado desde o início.

Isso é tudo, e de propósito: uma instalação que chega com agentes que ninguém
pediu é uma instalação que começa com coisas para desligar. Tudo o resto é um
**modelo** do repositório de modelos, ou um `.zip` que alguém exportou,
oferecidos quando carrega em **+**.

## De onde vem um novo agente

Carregue em **+** e é-lhe perguntado de onde quer partir:

| Opção | O que faz |
|---|---|
| **Agente vazio** | Sem prompt, sem ferramentas, sem horário. Escreve-o você. |
| **Importar de um ficheiro .zip** | Um agente exportado a partir do seu separador **Exportar**, aqui ou noutra instalação. |
| **Importar de um modelo do GitHub** | Um dos agentes do repositório de modelos, escolhido de uma lista. |

O **agente vazio** encabeça a lista, porque é a única resposta que está sempre
certa e todas as outras são um atalho para ela.

### Modelos do GitHub

Os modelos (templates) vivem num repositório próprio,
[bunch-of-aigents-templates](https://github.com/nipegun/bunch-of-aigents-templates),
uma pasta para cada um, por isso um modelo novo chega à sua instalação sem a
atualizar. Quando escolhe **Importar de um modelo do GitHub**, o servidor
transfere esse repositório (um `.tar.gz`, guardado durante cinco minutos) e
lista os seus agentes por ordem alfabética, cada um com a sua descrição no seu
idioma, as famílias de ferramentas que traz, com que frequência acorda e se
liga a sua biblioteca. Uma ferramenta que esta instalação não tenha fica de
fora, e a lista di-lo. Um modelo que não passe as verificações não é oferecido,
e uma linha diz quantos ficaram de fora.

Estes são os modelos que o repositório contém hoje:

| Modelo | O que faz |
|---|---|
| **backup-watcher** | Verifica que as suas cópias de segurança correram, são recentes e não são suspeitosamente pequenas. |
| **cert-watcher** | Avisa quando um certificado TLS está prestes a expirar, enquanto ainda há tempo. |
| **disk-cleaner** | Descobre o que está a encher o disco e diz o que poderia sair. Propõe; nunca apaga. |
| **kanban-watcher** | Lê o quadro todas as manhãs dos dias úteis e escreve um resumo curto. |
| **log-watcher** | Lê os logs que lhe indicar e relata o que é novo ou passou a ser frequente. |
| **mail-watcher** | Vigia uma caixa de correio e age sobre o que chega, seguindo as regras que escrever no seu prompt. |
| **news-watcher** | Lê os feeds RSS que indicar no seu prompt e relata o que corresponde às suas regras. |
| **os-watcher** | Vigia esta máquina: disco, memória, swap, carga e se os serviços estão a funcionar. |
| **rag-consultant** | Responde a perguntas a partir dos documentos da sua biblioteca RAG, citando a passagem que sustenta cada afirmação, e di-lo quando os documentos não cobrem algo. |
| **site-watcher** | Verifica que os sites que indicar respondem, respondem depressa e continuam a dizer o que diziam. |
| **web-navigator** | Conduz o seu próprio navegador para fazer o que lhe pedir num site: pesquisar, iniciar sessão, preencher um formulário, ir clicando e relatar o que encontrou. |

O `web-navigator` e o `rag-consultant` não têm horário: trabalham quando lhes
pede, e o pedido é a tarefa. O `web-navigator` é também o que mostra para que
está
instalado o navegador - inicia sessão, clica e preenche formulários, onde os
outros leem páginas. Não escreve palavras-passe, não compra nada nem carrega
num botão de envio: chega a esse passo e para, dizendo que botão terminaria o
trabalho.

O `rag-consultant` responde a partir da sua própria biblioteca de documentos, e
é o único modelo que chega com essa biblioteca ligada: as suas ferramentas
ficam retidas enquanto a biblioteca está desligada. Antes de ter alguma
utilidade, carregue documentos no seu separador **RAG** (veja
[Bibliotecas locais de documentos](#bibliotecas-locais-de-documentos-rag)) e
escolha um modelo. Cada afirmação das suas respostas tem uma ligação para a
página do documento de onde vem; quando os documentos não cobrem algo, di-lo em
vez de preencher a lacuna. O seu teto de tokens (40 000 por execução) é mais
alto do que o dos outros, porque as passagens que lê contam para ele.

Cada modelo diz, antes de o escolher, que famílias de ferramentas traz e com que
frequência acorda. Um modelo é tanto um conjunto de permissões como um prompt:
«vigia uma caixa de correio» não lhe diz que chega capaz de apagar correio.

Todos os modelos chegam **desligados e sem modelo de IA**: escolher um dá-lhe o
seu prompt, as suas ferramentas e um horário sugerido, e depois fica à espera
que escolha um fornecedor e o ligue. O seu agendamento entra no crontab quando o fizer.

São pontos de partida. Altere o prompt, as ferramentas, o horário - tudo - e
vários deles dizem no seu próprio prompt o que precisam que preencha antes de
terem alguma utilidade, em vez de falharem às três da manhã.

**Definições → Agentes** diz de que repositório e ramo vem a lista: o do
próprio projeto por predefinição, ou um fork, ou um seu com a mesma estrutura.
Uma máquina sem saída para o GitHub pode usar um caminho `file://` que contenha
`archive/refs/heads/<branch>.tar.gz`, a mesma estrutura que o instalador aceita.
Quando o repositório não está acessível, a lista diz que endereço falhou;
importar um `.zip` continua a funcionar. Os redirecionamentos só são seguidos para endereços `https://`, e para outro servidor só se for público; assim, um repositório não consegue enviar o servidor para uma máquina da sua rede. O arquivo de um repositório pode ter no máximo 20 000 ficheiros e descomprimir no máximo 256 MiB.

### Importar um .zip

1. Escolha o `.zip`. É carregado aos bocados, com uma percentagem, para que
   uma biblioteca de centenas de MiB também chegue ao destino.
2. O servidor verifica o pacote inteiro antes de mais nada. Nada nele pode ser
   um caminho para fora da pasta pessoal do agente, um ficheiro oculto como
   `.ssh` ou `.bashrc`, a conversa ou o diário de execuções, ou um horário que
   traga um comando. Quando algo está mal, é-lhe dito o quê, e não é criado
   nada.
3. É-lhe mostrado o que traria: a sua descrição, as suas ferramentas (e as que
   faltam nesta instalação), os seus horários, e se traz a sua memória,
   ficheiros para a pasta pessoal, documentos da biblioteca ou um modelo.
   Confirme e dê-lhe um nome.
4. Instala-se em segundo plano, com o progresso no ecrã. Os documentos da
   biblioteca são carregados um a um e indexados de novo aqui. Se algo falhar a
   meio, o agente volta a ser eliminado em vez de ficar meio instalado.

Um `.zip` que enumere mais de 24 016 entradas, pastas incluídas, é recusado antes de se ler o que quer que seja dele: nenhum agente pode levar mais do que isso. Nem um que se expandiria para mais de 200 vezes o seu tamanho depois de passar os 64 MiB, ou cujas entradas declarem mais dados do que o ficheiro contém.

Um agente importado também chega **desligado**. Se indicar um fornecedor, a
respetiva chave tem de ser definida nesta instalação: as chaves nunca viajam
num `.zip`. Os seus agendamentos esperam com ele: o separador **Cron** mostra-os, e entram no seu crontab da primeira vez que o ligar. Os agendamentos de um pacote não podem disparar com mais frequência do que a cada 5 minutos, nem somar mais de 288 arranques por dia.

Se preferir que não lhe perguntem nada, desligue **Perguntar de onde parte um
novo agente** em **Definições → Interface**: o **+** passa então a ir
diretamente para um agente vazio.

### Nenhum agente tem root

Nenhum, nem sequer o orquestrador. Esse é todo o modelo de isolamento, e vale a
pena deixá-lo claro porque decide o que um agente como o `os-watcher` pode
fazer:

- **Observar não exige privilégios.** `df`, `free`, `uptime`, `nproc`,
  `systemctl is-active` funcionam todos como utilizador comum. Um agente
  consegue ver um disco a encher muito antes de ficar cheio.
- **Corrigir normalmente exige, e ele não os tem.** Os prompts dizem-lhe que
  indique exatamente o que executaria em vez de tentar e falhar: um cartão que
  diga «needs root: journalctl --vacuum-size=200M would free about 1.2G»
  (precisa de root: libertaria cerca de 1,2G) vale mais do que uma tentativa
  falhada.

Se quiser que algo se corrija automaticamente, ponha esse comando no crontab do
próprio root. Um agente a decidir sozinho apagar ficheiros como root não é uma
funcionalidade que alguém queira às três da manhã.

## Criar o seu primeiro agente

Carregue em **+**, escolha um agente vazio, um `.zip` ou um modelo, e dê-lhe um
nome. Isso cria, no servidor:

- o utilizador Linux `agent-001`,
- a sua pasta pessoal em `/opt/boa/agents/001/`, modo 0700,
- `info.json`, `system-prompt.md` e um token de API lá dentro.

O id é o número livre mais baixo. O `000` está reservado para o orquestrador.

Um agente novo começa com as ferramentas do kanban e mais nada, e com tetos
conservadores. Não tem horário, por isso não faz nada até lhe dar um ou
carregar em **Executar agora**.

## Falar com um agente

Clique num agente na barra lateral e obtém a sua conversa. Escreva o que quer
que ele faça e carregue em Enter; Shift+Enter começa uma nova linha.

A caixa onde escreve fica fixa, mesmo por cima da barra de estado no fundo da
página: só a conversa acima dela se desloca, por isso nunca fica escondida e
nunca tem de deslocar a página para baixo para chegar a ela. Enquanto está
vazia, lembra-lhe, a cinzento, como se comporta o Enter - ou que o agente
ainda está a trabalhar - e num telemóvel estreito cresce uma ou duas linhas
para que esse lembrete nunca fique cortado.

Uma mensagem é uma execução: o agente usa as suas ferramentas, faz o trabalho
e responde quando termina. Isso pode demorar minutos, por isso a caixa de
escrita fica desativada enquanto ele trabalha e a resposta aparece quando
chega. Cada resposta mostra quanto custou, em tokens e passos.

As respostas são apresentadas como markdown - títulos, tabelas, listas,
citações e blocos de código - porque é assim que um modelo escreve. As suas
próprias mensagens são mostradas exatamente como as escreveu. Uma ligação só é
ligação quando aponta para http ou https; tudo o resto fica como o texto que
era.

A conversa fica memorizada. As últimas dez trocas são reenviadas ao modelo em
cada mensagem, para que o agente saiba de que estavam a falar - e por isso uma
conversa longa custa mais por mensagem do que uma curta. **Limpar conversa**
recomeça do zero.

Falar com um agente **não** conta para o seu teto de execuções por dia: esse
teto existe para travar um horário sem supervisão, não para o impedir de
escrever. Os tetos por execução de tokens, passos e tempo aplicam-se.

Cada agente tem a sua própria conversa, guardada na sua própria pasta pessoal,
e nenhum agente consegue ler o que disse a outro.

A conversa não é só o que escreveu. Quando chega a hora de um dos cartões do
agente, o cartão é publicado nessa mesma conversa no momento em que a execução
começa, e a resposta da execução aparece por baixo dele - por isso abrir um
agente mostra tudo o que lhe pediram que fizesse, por si ou por outro agente, e
o que fez a esse respeito. Veja
[Quando um cartão é executado](#quando-um-cartão-é-executado).

### API Calls

O nome do agente aparece por cima dos separadores Chat e API Calls. Só o
**Chat** está visível por predefinição. Para mostrar o outro separador, abra a
chave inglesa do agente, selecione **Interface**, ligue **Mostrar o separador
API Calls** e carregue em **Guardar**. A escolha fica guardada no servidor para
este agente. Abrir ou recarregar um agente começa sempre em Chat, mesmo quando
API Calls está ativado.

**API Calls** mostra o JSON enviado: prompt completo, conversa, definições das ferramentas e resultados. Expanda uma pedido para carregá-la; todas começam fechadas. As entradas incluem falhas, novas tentativas do SDK e chamadas ao modelo de reserva. O visualizador aceita 2 MiB por pedido; corpos maiores permanecem no disco. JSON grande aparece como texto simples, preservando os números.

Os últimos 100 pedidos completos são guardados à parte da conversa. Limpar o
Chat não os apaga. O registo começa com esta versão; os pedidos anteriores não
podem ser reconstruídos. Os cabeçalhos de autenticação não são registados.

## Definições do agente

O título mostra **Configuração do agente 001**, com o id do agente selecionado.
**Executar agora** só aparece na área de trabalho que contém Chat e API Calls.
Para eliminar um agente, abra **Geral → Eliminar agente** e confirme o seu nome
na caixa de diálogo. A eliminação é uma secção à parte, por baixo de
Identidade.


A conversa é o que obtém ao clicar num agente. Tudo o resto - modelo,
ferramentas, tetos, prompt de sistema, horário - está por trás da **chave
inglesa** à direita da caixa do agente na barra lateral.

## Exportar um agente

O último separador das definições de um agente, **Exportar**, transfere-o como
um `.zip` que **+ → Importar de um ficheiro .zip** consegue instalar, aqui ou
noutra instalação. A sua configuração, o seu prompt de sistema e os seus
horários vão sempre. Quatro coisas só vão se as marcar, e cada caixa diz
antecipadamente o que acrescentaria:

| Opção | O que acrescenta |
|---|---|
| **Memória** | O seu `memory.md`, com quantos caracteres contém |
| **Fornecedor e modelo** | Que fornecedor e que modelo usa. Nunca a chave |
| **Documentos da biblioteca** | Os originais da sua biblioteca com as respetivas informações (título, ano...). São indexados de novo onde forem importados |
| **Ficheiros da pasta pessoal** | Os seus scripts, a sua pasta `samba` e tudo o resto que guarde na pasta pessoal. Podem conter coisas que não partilharia, por isso a lista de ficheiros é mostrada antes de transferir |

Há coisas que nunca vão, marque o que marcar: chaves de API, o token do próprio
agente, credenciais de canais, a sua conversa, o seu diário de execuções, as
suas sessões de navegador e os ficheiros ocultos da sua pasta pessoal. Do seu
crontab só viajam os horários que executam o agente, não outros comandos que
alguém lá tenha escrito: um `.zip` que levasse comandos executá-los-ia na
máquina para onde fosse importado. As chaves próprias do agente, na pasta `keys/`, nem sequer são propostas entre os ficheiros do home dele, e um `.zip` que traga uma pasta `keys/` é recusado na importação.

## Pastas partilhadas Samba

Cada agente tem uma pasta `samba/` na sua pasta pessoal, exportada
automaticamente com o nome do seu utilizador Linux. Por exemplo, a partilha
**agent-001** aponta apenas para `/opt/boa/agents/001/samba/`. Mudar o nome ao
agente em Geral não muda o nome da partilha. O resto da sua pasta pessoal e a
sua configuração protegida não são exportados.

1. Abra a **chave inglesa → Samba** do agente.
2. Introduza uma **Nova palavra-passe Samba** com pelo menos 8 caracteres, escolha as permissões e carregue em **Guardar**.
3. Abra o endereço Windows ou SMB mostrado no separador - `\\server\agent-001` em Windows, `smb://server/agent-001` em Linux e macOS - e inicie sessão com o nome de utilizador apresentado e essa palavra-passe.

A partilha começa ativada, visível na lista de partilhas do servidor e
configurada para acesso de leitura e escrita, com o acesso de convidado
desligado. Antes da sua primeira ligação autenticada, defina a sua
palavra-passe neste separador. Um campo de palavra-passe em branco em
gravações posteriores mantém a palavra-passe existente. As credenciais Samba
são independentes das credenciais de início de sessão Linux; defini-las não
desbloqueia a conta Linux do agente.

| Definição | Efeito |
|---|---|
| Partilhar esta pasta | Liga ou desliga este recurso sem apagar os seus ficheiros |
| Autenticação | Nome de utilizador e palavra-passe do agente por predefinição; acesso de convidado só quando é selecionado explicitamente |
| Permissões | Só de leitura ou leitura e escrita através de SMB; o agente continua a poder trabalhar com os seus próprios ficheiros locais |
| Visibilidade e descrição | Se aparece na lista de partilhas do servidor, e a sua descrição |
| Permissões dos novos ficheiros/pastas | Modos Unix em octal, inicialmente `0600` / `0700`; os ficheiros existentes mantêm os seus modos |

O nome da partilha e o caminho são fixos. A pasta continua privada para o seu
dono Linux. Guardar alterações nas definições de acesso fecha as ligações
existentes a esta partilha, para que os clientes voltem a ligar-se com as novas
permissões. As partilhas dos outros agentes continuam ativas. A palavra-passe
em si nunca é devolvida pela API nem guardada em `info.json`.

`--update` acrescenta pastas e partilhas Samba aos agentes existentes,
`agent-000` incluído. Eliminar um agente remove
a sua partilha e a sua conta Samba juntamente com a sua pasta pessoal.
`--backup` / `--restore` preservam os dados partilhados, as definições, as
palavras-passe Samba e as identidades das contas.
O restauro verifica o modo de portas web guardado, incluindo instalações que servem o 443 diretamente.

O Samba usa a porta TCP **445**, independentemente do proxy web. Em Docker, esta
porta tem de ser publicada explicitamente. O BoA corre o seu próprio serviço
`boa-samba`, com a sua própria configuração e base de dados de palavras-passe
em `/opt/boa/samba/`; não substitui nem toma conta da configuração de outro
servidor Samba, e o instalador recusa-se a tomar conta de uma instalação Samba
existente que não gere.

## Dar um modelo a um agente

Em **LLMs**, escolha um fornecedor. A lista é curta de propósito: oferece os
três fornecedores auto-alojados, que não precisam de chave, e todos os
fornecedores na nuvem cuja chave esteja definida em **Definições → Chaves de
API**. Um fornecedor na nuvem sem chave levaria o agente até à sua primeira
execução e falharia aí, por isso não é oferecido. Defina a sua chave e ele
aparece.

Um agente já configurado com um fornecedor continua a vê-lo na lista mesmo que
a sua chave seja removida, marcado como *(sem chave configurada)* - caso
contrário, a caixa mostraria um fornecedor que ninguém escolheu e guardá-lo-ia
no clique seguinte.

**No seu próprio hardware.** Sem chave, e a caixa URL base é onde o seu próprio servidor escuta.

| Fornecedor | Modelos listados | Modelo predefinido |
|---|---|---|
| `ollama` | 23 | `gpt-oss:20b` |
| `llamacpp` | 1 | `local-model` |
| `vllm` | 3 | indica você o modelo |

**Empresas que servem os modelos que elas próprias criaram.**

| Fornecedor | Modelos listados | Modelo predefinido |
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

**Alojamentos e routers, que servem modelos criados por outros.** Uma chave chega a muitos modelos; o id do modelo indica qual.

| Fornecedor | Modelos listados | Modelo predefinido |
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

Há um fornecedor que precisa de dois valores na caixa da chave: o **Cloudflare
Workers AI** constrói o seu endereço a partir do id da conta, por isso a sua
chave escreve-se `account-id:api-token`, com as duas metades tiradas do painel
da Cloudflare. A caixa em **Definições → Chaves de API** di-lo.

O campo do modelo sugere o que esse fornecedor serve, e filtra a lista à medida que escreve - mas é uma caixa de texto normal, por isso um modelo lançado esta manhã pode simplesmente ser escrito à mão. Essas sugestões vêm de `/opt/boa/config/providers/<provider>.json`, que pode editar no servidor; uma atualização nunca substitui um ficheiro que tenha alterado.

Os fornecedores auto-alojados não precisam de mais nada se correrem na mesma
máquina.

**URL base** só aparece para `ollama`, `llamacpp` e `vllm`, e é onde o seu
próprio servidor escuta - o valor predefinido é a porta habitual nesta
máquina, que está certo quando o modelo corre ao lado da aplicação. Escolha um
fornecedor na nuvem e a caixa desaparece: esse endereço é fixo, esta
instalação já o tem, e a única coisa que uma caixa ali poderia fazer era
deixar que um erro de escrita estragasse um agente que funciona. O modelo de
reserva funciona da mesma maneira.

Para um fornecedor na nuvem, o caminho mais simples é o separador **Chaves de API** nas Definições, que todos os agentes desse fornecedor passam então a usar. Para dar a este agente uma chave diferente, escreva-a na sua própria pasta pessoal, como root:

```bash
mkdir -p /opt/boa/agents/001/keys
echo "sk-..." > /opt/boa/agents/001/keys/anthropic.key
chown -R agent-001:agent-001 /opt/boa/agents/001/keys
chmod 700 /opt/boa/agents/001/keys
chmod 600 /opt/boa/agents/001/keys/anthropic.key
```

O nome do ficheiro é o nome do fornecedor. Cada agente lê apenas a sua própria
chave, por isso um agente não pode gastar o orçamento de outro.

### Chaves de API

As Definições têm um separador **Chaves de API**: uma chave por fornecedor na
nuvem, partilhada por todos os agentes que o usam. Os fornecedores
auto-alojados não aparecem, porque não precisam de nenhuma.

Uma chave é guardada em `/opt/boa/config/apikeys/<provider>.key`. A pasta é
`0700` e os ficheiros `0600`, ambos pertencentes ao utilizador web, por isso
nenhum agente consegue ler nenhum deles: nem a chave de outro fornecedor, nem a
sua própria. Quando um agente corre, a API dos agentes entrega-lhe a chave
**do fornecedor com que esse agente está configurado, e de nenhum outro**: um
agente no Ollama não pode pedir a chave da Anthropic.

As instalações feitas antes de esta pasta mudar de nome guardam as chaves em
`/opt/boa/config/keys/`; `--update` passa-as para a nova e remove a pasta
antiga.

Vale a pena ser claro sobre o que isso protege e o que não protege. Um agente
que usa legitimamente um fornecedor pago tem a sua chave enquanto corre -
precisa dela para fazer a chamada, e um agente com `bash.run` poderia
imprimi-la. O que o armazenamento partilhado impede é que um agente recolha as
chaves de fornecedores que não usa, e mantém todas as chaves fora das pastas
pessoais dos agentes, onde uma única cópia de segurança perdida as exporia
todas de uma vez.

Para faturar um agente a outra conta, ponha uma chave na pasta pessoal desse
agente em `keys/<provider>.key`. Essa tem prioridade sobre a partilhada.

## Escrever um prompt de sistema

O prompt de sistema é o que o agente é. Fica guardado como `system-prompt.md`
na pasta pessoal do agente e edita-o na interface.

O que funciona:

- **Diga para que serve o agente**, numa ou duas frases.
- **Diga o que significa «concluído».** Um agente sem definição de concluído
  ou para cedo demais ou nunca para.
- **Diga o que fazer quando estiver bloqueado.** Sem isto, os modelos inventam
  uma forma de contornar o obstáculo. «Se não conseguires fazê-lo, di-lo no
  quadro e para» é suficiente.
- **Diga-lhe que leia primeiro o quadro.** É a única memória que tem entre
  execuções.

O que não funciona: dizer-lhe que não use uma ferramenta. Se não quer que use
uma ferramenta, não lha dê — o prompt é uma sugestão, a lista de ferramentas é
imposta.

## O que um agente recorda

Cada agente tem um `memory.md` na sua pasta pessoal, e esse ficheiro é a única
coisa que leva de uma execução para a seguinte. Escreve nele com
`memory.append` quando aprende algo que vale a pena guardar, e arruma-o com
`memory.replace`.

O ficheiro inteiro é carregado no início de cada execução, que é o que o torna
útil e também o que o torna caro: cada carácter é pago em cada chamada ao
modelo. Em **Definições do agente → Memória → Limite de memória
(caracteres)**, escolha um limite de 1000 a 1 000 000 de caracteres. O valor
predefinido é 8000, também para os agentes existentes. Pede-se ao agente que
arrume a sua memória acima de 75% do seu limite.

O contador mostra a contagem atual e o limite selecionado, incluindo espaços e
quebras de linha. Pode aumentar o limite e colar uma memória maior na mesma
gravação. Se o texto exceder o limite selecionado, não é guardado nada desse
pedido de definições: encurte o texto ou aumente o limite. A memória anterior
fica intacta; as novas escritas nunca acrescentam `[truncated]`. O texto
descartado anteriormente tem de ser colado outra vez a partir do original. A
memória completa continua a ter de caber no contexto do modelo escolhido,
juntamente com o prompt, a conversa e as ferramentas.

Coisas boas para guardar: onde está alguma coisa, o que afinal era um comando,
o que prefere. Não o diário do que fez - isso é o quadro.

Pode lê-la e corrigi-la você mesmo em **Memória**, nas definições do agente.
Vale a pena corrigir à mão um facto errado com base no qual um agente continua
a agir.

## Bibliotecas locais de documentos (RAG)

Cada agente tem a sua própria biblioteca em `/opt/boa/agents/<id>/rag/`. São
suportados ficheiros PDF, EPUB, TXT em UTF-8 e Markdown. O instalador prepara o
modelo de vetorização local - EmbeddingGemma 300M Q8 (cerca de 318 MiB), a não
ser que tenha sido escolhido outro (veja
[Escolher o modelo de vetorização](#escolher-o-modelo-de-vetorização)) -, o seu
motor llama.cpp e o OCR.
A extração, o OCR, a vetorização dos documentos e a das perguntas correm neste
servidor. As passagens recuperadas são enviadas ao fornecedor de respostas
selecionado para o agente, incluindo fornecedores na nuvem quando estiverem
configurados. Não há nenhum endpoint de vetorização externo disponível. A
instalação, as atualizações, a importação de documentos, o OCR e a cópia de
segurança e o restauro foram verificados em Debian 13 e Alpine 3.24, incluindo
o arranque dos serviços depois de reiniciar.

1. Abra **Definições → RAG** e verifique que o motor local está pronto.
2. Abra o separador **RAG** de um agente, ative a recuperação e guarde o agente.
   O modelo **rag-consultant** chega com a recuperação já ativada.
3. Escolha ficheiros e clique em **Carregar documentos**. Os ficheiros grandes
   viajam aos bocados. Em alternativa, copie ficheiros completos para
   `rag/inbox/` e clique em **Importar ficheiros de rag/inbox**. Os originais
   importados passam para o armazém de documentos gerido.
4. Espere por **Pronto**. A extração e a vetorização correm em segundo plano;
   os outros documentos prontos continuam pesquisáveis. A página mostra o
   progresso e os erros.
5. Teste uma pergunta com **Pesquisar na biblioteca**, ou pergunte ao agente na
   sua conversa normal. As citações têm ligação para a página do PDF de origem
   ou para o EPUB/documento original.

Os erros ao importar de `rag/inbox/` aparecem por cima da lista de documentos.
Os originais que falharam ficam na pasta de entrada para serem corrigidos. A
indexação processa lotes limitados, para que os documentos pequenos não tenham
de esperar uma rotação inteira do escalonador entre cada livro. Um documento longo também não monopoliza o indexador: ao fim de uns noventa segundos volta à fila com o que já foi extraído e vetorizado, e a passagem seguinte continua a partir daí, de modo que entretanto chega a vez das bibliotecas dos outros agentes. O indexador corre com os mesmos 2 GiB de memória e 1024 tarefas de uma execução.

Os controlos de **Informações do documento** editam, por esta ordem, o ano de
publicação, o título, o subtítulo, o(s) autor(es), a versão, o idioma e as
etiquetas. O ano é opcional e aceita até quatro algarismos. O subtítulo, quando
existe, é mostrado na lista de documentos logo por baixo do título. O
subtítulo, o ano, o autor, a versão e o idioma viajam com cada passagem que o
agente recupera, para que ele consiga distinguir documentos com o mesmo
título, datar e atribuir o que cita, e distinguir edições que não coincidem.
Substituir um ficheiro mantém o documento pesquisável anterior
até que o novo termine de ser indexado. Se o motor local de vetorização parar
enquanto um documento está a ser indexado (uma atualização, um reinício), o
documento volta a **Na fila** com a mensagem «Local embeddings are
unavailable» e, quando o motor voltar a responder, continua onde parou; não há
nada para reindexar. Reindexar reconstrói um documento; Cancelar para o seu
trabalho pendente;
Eliminar retira-o das pesquisas futuras. Os filtros de idioma e de versão
usam os metadados que introduziu. As citações de EPUB identificam capítulos,
não números de página inventados. Os PDF digitalizados precisam de idiomas de
OCR instalados no servidor; o inglês e o espanhol vêm instalados por
predefinição (`eng+spa`). Os ficheiros não suportados ou cifrados dão um erro
em vez de um índice vazio com êxito.

O **Modo de resposta** decide até onde o agente pode ir para além dos seus
documentos; a linha por baixo da lista diz o que faz o modo escolhido.

- **Documentos e conhecimento geral**: o agente pode usar ambos, mantidos à
  parte.
- **Exigir fontes documentais**: o agente tem de pesquisar ele próprio na
  biblioteca antes de responder; uma resposta dada sem pesquisar é-lhe
  devolvida uma vez. Se a execução não recuperou nenhuma passagem, recebe a
  frase fixa «A biblioteca de documentos não contém informação suficiente para
  responder a esta pergunta» em vez do que o modelo tiver escrito.
- **Apenas documentos (verificado)**: como o anterior, e cada parágrafo e cada
  elemento de lista da resposta tem de citar uma passagem recuperada nessa
  execução. Cada parágrafo é verificado: a falta de citação, uma citação de uma
  passagem que não foi recuperada ou um sentido distante da passagem que cita
  (medido com o motor local de vetorização) devolve a resposta uma vez com a
  lista desses parágrafos. O que continuar sem suporte depois disso é
  retirado, e uma última linha diz quantos parágrafos saíram. Se não restar
  nada com suporte, recebe a frase fixa. Se não for possível contactar o motor
  para fazer a verificação, a resposta é retida em vez de ser mostrada sem
  verificação.

O que o modo verificado não consegue fazer é provar que um parágrafo citado diz
exatamente o que a sua passagem diz. Nas nossas medições, um parágrafo que
contradiz a sua passagem, ou que acrescenta algo sobre o mesmo tema, pontua
como um fiel; o que a verificação apanha é um parágrafo que cita uma passagem
sobre outra coisa, e um parágrafo sem fonte nenhuma. Também não é exato em
nenhum dos sentidos: nos nossos testes retirou cerca de 6 em cada 100
parágrafos fiéis - sobretudo elementos de lista curtos e resumos de uma linha,
que lhe dão pouco para comparar - e deixou passar menos de 1 em cada 100
citações de uma passagem sobre outro tema. Um exemplo de código é avaliado
juntamente com a frase que o introduz. Reveja a passagem citada quando a
exatidão importar. As frases fixas são escritas no idioma escolhido em
**Definições → Agentes → Idioma em que os agentes respondem**, e em inglês
quando não há nenhum escolhido.
As citações só são resolvidas a partir de identificadores de fontes
recuperadas.

Valores predefinidos por agente: 128 MiB por ficheiro, 2048 MiB de documentos
originais, 200 000 fragmentos, 8 resultados e até 16 000 caracteres de texto
recuperado por execução. Um orçamento conservador de bytes limita também o que
cabe ao lado do prompt e do histórico.
A **Semelhança mínima** começa no valor medido para o modelo de vetorização em
uso - 0,20 para o EmbeddingGemma, 0,35 para o Qwen3-Embedding - e a linha por
baixo do campo diz qual é. É uma pontuação de pesquisa, não uma probabilidade,
e cada modelo tem a sua própria escala. Aumente-a se os resultados semânticos
forem demasiado amplos.
As correspondências literais também participam.
A API expõe ainda quotas de fragmentos e o tamanho em tokens dos fragmentos.

As definições globais controlam as threads de vetorização, as indexações
simultâneas e os idiomas de OCR predefinidos. **Indexações simultâneas** é
quantas bibliotecas de agentes são indexadas ao mesmo tempo (uma tarefa por
agente, com os seus documentos um atrás do outro); cada tarefa pode usar até
4GB de RAM, o que o rótulo lhe lembra. Não acelera a biblioteca de um agente: o
motor de vetorização responde a um pedido de cada vez. Para vetorizar mais
depressa, aumente antes **Threads de CPU para vetorização**. O modelo é
partilhado; as bibliotecas e as permissões são por agente.
O processamento retoma depois de reinícios, mantendo os documentos concluídos
e os fragmentos reutilizáveis das tarefas interrompidas. Uma reindexação
falhada mantém a última versão publicada. Só a instalação do modelo precisa de
uma transferência; a recuperação normal pode correr sem Internet. Um motor
local indisponível é comunicado, e nunca substituído por um serviço de
vetorização externo.

O `boa-embeddings` serve o modelo através de um socket Unix; o `boa-rag` gere a
fila. Ambos têm unidades systemd e OpenRC e aparecem nas definições do sistema.
As cópias de segurança incluem os originais dos documentos, os metadados e
instantâneos consistentes do SQLite e do índice vetorial. As definições de
execução estão incluídas, e com elas o modelo de vetorização escolhido; os
binários do modelo e os pesos transferidos não. Um restauro transfere o modelo
escolhido quando a máquina não o tem, e se essa transferência falhar di-lo e
continua: o modelo pode então ser transferido, ou escolhido outro, em
**Definições → RAG**. Os carregamentos ainda em curso são cancelados numa cópia
de segurança restaurada. As bibliotecas indexadas sobrevivem a uma atualização
normal.

### Escolher o modelo de vetorização

O modelo de vetorização transforma cada passagem e cada pergunta nos números
pelos quais a biblioteca é pesquisada. **Definições → RAG → Modelo de
vetorização** oferece dois, e o mesmo serve todos os agentes:

| | EmbeddingGemma 300M (Q8) | Qwen3-Embedding 0.6B (Q8) |
|---|---|---|
| Transferência | 318 MiB | 610 MiB |
| Memória do motor enquanto corre | cerca de 600 MB | cerca de 1,1 GB |
| Tempo de indexação, mesmo processador | 1× | cerca de 4× |
| Licença | Gemma Terms of Use | Apache 2.0 |

O EmbeddingGemma é o predefinido e serve qualquer máquina. O Qwen3-Embedding é
para uma máquina com processador e memória de sobra: nos livros de Python em
espanhol da biblioteca de teste, manteve as perguntas sobre os livros
(0,51-0,79) mais afastadas das que não tinham nada a ver (0,21 no máximo) do
que o EmbeddingGemma (0,35-0,67 contra 0,17), e os parágrafos que reformulam
uma passagem mais afastados dos parágrafos sobre outra coisa. Na máquina de
teste com dois processadores demorou 2,2 segundos por fragmento, contra 0,5.

Para o mudar:

1. Escolha o modelo na lista. Por baixo vê o seu tamanho, a sua memória, a sua
   velocidade e a sua licença, e se já está transferido.
2. Se não estiver, clique em **Descarregar modelo** e espere que a barra
   termine. A transferência é verificada contra o seu SHA-256 publicado antes
   de ser usada.
3. Clique em **Guardar** e confirme. O motor reinicia com o novo modelo; a
   linha de cima diz «O motor está a carregar este modelo» durante alguns
   segundos e depois **Pronto**.

O que uma mudança põe em marcha:

- Todos os documentos de todos os agentes são indexados de novo, uma
  biblioteca por tarefa de indexação, como seria um carregamento novo. Numa
  biblioteca grande isso demora horas.
- Até chegar a sua vez, um documento fica na biblioteca e é encontrado pelas
  palavras de uma pergunta, não pelo sentido. Uma pesquisa durante esse tempo
  diz ao agente quantos documentos estão à espera, para que uma passagem em
  falta não seja tomada como a biblioteca não cobrir a pergunta.
- A **Semelhança mínima** de todos os agentes que ainda tinham o valor
  recomendado do modelo antigo passa para o do novo modelo. Um agente em que
  tenha definido outro valor mantém-no.
- O modo verificado compara parágrafos e passagens com o modelo em uso, contra
  um limiar medido para ele (0,36 para o EmbeddingGemma, 0,44 para o
  Qwen3-Embedding).

Os pesos do modelo anterior ficam no disco, por isso voltar atrás não precisa
de transferência - mas volta a indexar todos os documentos que foram indexados
com o outro.

## Escolher ferramentas

Em **Ferramentas**, marque o que este agente pode usar. Uma ferramenta que não
esteja marcada não é mostrada ao modelo e seria recusada pelo servidor mesmo
que a pedisse: essa verificação corre no servidor e não no prompt.

Estas são as ferramentas que vêm incluídas:

| Ferramenta | O que um agente pode fazer com ela |
|---|---|
| `bash.run` | Executar comandos de shell como o seu próprio utilizador sem privilégios |
| `kanban.add_card` | Pôr uma tarefa no quadro partilhado |
| `kanban.assign_card` | Passar um dos seus próprios cartões a outro agente |
| `kanban.move_card` | Mover um dos seus próprios cartões entre colunas |
| `kanban.delete_card` | Retirar um dos seus próprios cartões |
| `kanban.list_cards` | Ler o quadro: os seus próprios cartões, ou todos os cartões no caso do **manager** |
| `channel.write` | Enviar uma mensagem para um canal configurado |
| `x.post` | Pedir para publicar um texto no perfil do X. Aprova cada publicação por mensagem privada antes de ela sair |
| `web.fetch` | Ler uma página web pública |
| `rss.fetch` | Ler um feed RSS ou Atom como uma lista de entradas |
| `memory.append` | Apontar algo para o seu eu futuro |
| `memory.replace` | Arrumar o que recorda |
| `skill.read` | Ler um procedimento que lhe foi dado |
| `script.write` | Escrever um script na sua própria pasta `scripts/` |
| `script.list` | Listar os scripts que escreveu |
| `script.delete` | Retirar um dos seus scripts, com as linhas de cron que o executavam |
| `cron.add` | Acrescentar ao próprio crontab uma linha que executa um dos seus scripts segundo um horário. Não remove nada |
| `cron.list` | Ler o seu próprio crontab |
| `cron.remove` | Retirar as linhas que executam um dos seus scripts, e nada mais |
| `mail.read` | Ler mensagens da caixa de correio configurada |
| `mail.move` | Arquivar uma mensagem noutra pasta da mesma conta |
| `mail.delete` | Enviar uma mensagem para o Lixo da conta |
| `mail.forward` | Reencaminhar uma mensagem para um endereço que autorizou |
| `rag.search` | Pesquisar na sua própria biblioteca de documentos |
| `rag.read` | Ler um fragmento devolvido por uma pesquisa |
| `rag.list` | Listar os documentos da sua biblioteca |
| `browser.open` | Abrir uma página no seu próprio navegador, mantendo os cookies |
| `browser.read` | Ler a página aberta, ou as suas ligações |
| `browser.click` | Clicar numa ligação ou num botão dessa página |
| `browser.type` | Preencher um campo, submetendo opcionalmente |
| `browser.screenshot` | Guardar uma imagem dela para si |
| `image.send` | Anexar um PNG à conversa web e à resposta do Telegram, Discord, X, Mattermost ou Slack quando a conversa começou aí. As imagens ocupam a área de texto da mensagem web |

Cada família tem uma caixa própria, com a contagem de quantas ferramentas
dessa família este agente tem: «este agente pode ler a caixa de correio?» é uma
só decisão, e é desenhada como uma só caixa. O interruptor que liga o quadro
kanban para um agente fica no fundo da caixa **Kanban**, por baixo das
ferramentas que governa.

- **`bash.run`** — comandos de shell como o utilizador desse agente. Não tem
  root e não o consegue obter. Dê-a quando o agente tiver trabalho real a
  fazer na máquina.
- **`kanban.*`** — o quadro partilhado. Dê pelo menos `list_cards` e
  `add_card` a tudo o que deva ser visível.
- **`channel.write`** — mensagens para si. Marque também os canais no separador **Canais**.
- **`web.fetch`** — apenas páginas públicas. Os endereços privados e de
  loopback são recusados.
- **`rss.fetch`** — um feed RSS ou Atom, como uma lista de entradas em vez do
  documento XML. Muito mais barato do que obter o mesmo feed com `web.fetch`, e
  poupa ao agente a análise. As duas vivem em **Internet**.
- **`script.*` e `cron.*`** — em **Automação**. O agente escreve um script na
  sua própria pasta `scripts/` e agenda-o no seu próprio crontab, para
  trabalho recorrente que não exige que pense: o script corre sozinho, não
  custa tokens, e o agente lê os resultados na sua execução seguinte. Só pode
  agendar os seus próprios scripts, nada com mais frequência do que de 5 em 5
  minutos, e nunca pode tocar na linha que o acorda.

Um agente pode fazer muita coisa dentro da sua própria pasta pessoal, e nada
mesmo fora dela. Não consegue ver que outro agente existe, quanto mais ler o
seu prompt: a pasta dos agentes é atravessável mas não listável e cada pasta
pessoal é privada para o seu próprio utilizador Linux, por isso é o kernel a
recusar e não uma verificação em Python.

Também não consegue reescrever **o que é**. As ferramentas que lhe foram
concedidas, os seus tetos de gasto, o seu prompt de sistema e o seu token de
API vivem numa gaveta dentro da sua pasta pessoal que pertence ao root: o
agente lê-os e não os consegue alterar. Quem os altera é você; ele não. A única
coisa sobre si próprio que pode editar é a sua memória.
- **`mail.*`** — a caixa de correio configurada em **Definições → E-mail**.
  Veja mais abaixo.
- **`skill.read`** — os procedimentos escritos marcados no painel
  **Competências**. Precisa das duas coisas: a ferramenta aqui e pelo menos
  uma competência lá.

### As ferramentas de correio

São quatro, e precisam de uma caixa de correio IMAP configurada em
**Definições → E-mail**. O agente nunca vê essa palavra-passe: diz o que quer
que seja feito e a API dos agentes, que guarda as credenciais, fá-lo.

| Ferramenta | O que faz |
|---|---|
| `mail.read` | Lê mensagens. **Não marca nada como lido**, por isso a sua própria contagem de não lidas continua a significar o que significava. |
| `mail.move` | Arquiva uma mensagem noutra pasta da mesma conta. A pasta tem de existir. |
| `mail.delete` | Envia uma mensagem para o Lixo da conta, quando existe. |
| `mail.forward` | Reencaminha uma mensagem, **apenas para os endereços que indicou**. |

Esta última é a importante. Uma caixa de entrada é a única entrada de um agente
para a qual qualquer pessoa no mundo pode escrever, por isso `mail.forward` é
verificado contra a sua lista pelo servidor em cada reencaminhamento, um a um -
não pelo agente, nem por algo escrito no seu prompt. Com a lista vazia, o
reencaminhamento é recusado logo à partida. Os nomes de pasta e o texto de pesquisa seguem para o servidor de correio como texto imprimível comum: uma quebra de linha ou qualquer outro carácter de controlo é recusado antes de contactar o servidor, porque nessa ligação seria um segundo comando.

Dê `mail.read` sozinha a um agente que só tem de vigiar. Acrescente `mail.move`
para arquivar, e pense duas vezes antes de `mail.delete` e `mail.forward`.

A caixa de seleção **kanban** no fundo desliga por completo o quadro para este
agente. Desmarcada, o agente não recebe nenhuma ferramenta de kanban e deixa de
acrescentar cartões, que é o interruptor a usar para um agente cujo trabalho
não pertence ao quadro.

## Dar uma competência a um agente

Uma competência (skill) é um procedimento escrito: como se faz um trabalho
aqui, passo a passo. A aplicação não traz nenhuma: uma competência é sobre ESTA
máquina - estes anfitriões, esta cópia de segurança, este certificado - por isso
uma genérica seria um procedimento que ninguém segue. Escreve as suas no
servidor, como root:

```bash
mkdir -p /opt/boa/skills/BackupVerification
nano /opt/boa/skills/BackupVerification/SKILL.md
chown -R root:root /opt/boa/skills
chmod 00755 /opt/boa/skills/BackupVerification
chmod 0644 /opt/boa/skills/BackupVerification/SKILL.md
```

O ficheiro começa com um nome e uma descrição de uma linha entre duas linhas
`---`, e o resto é o procedimento:

```markdown
---
name: BackupVerification
description: How to check that last night's backups actually ran.
---

1. Read /var/log/backup.log ...
```

Cada pasta em `/opt/boa/skills/` aparece então como uma caixa de seleção no
painel **Competências** do agente. Marque uma, dê ao agente a ferramenta
`skill.read` em **Ferramentas** e carregue em **Guardar**. A partir da sua
execução seguinte, o agente sabe que esse procedimento existe e pode lê-lo
quando o trabalho surgir.

### Para quê, se já existe o prompt de sistema

Três razões, e a terceira é a que importa:

- **O prompt é para que serve um agente; uma competência é como se faz um
  trabalho.** Seis agentes podem partilhar um procedimento sem que seis cópias
  dele fiquem desatualizadas cada uma à sua maneira.
- **Uma competência pode ser tão longa quanto precisar.** Um prompt de sistema
  é pago em cada chamada de cada execução, por isso tem de se manter curto. Uma
  competência é paga uma vez, pela execução que a lê.
- **O que um agente aprende sozinho morre com ele.** A sua memória vive dentro
  de uma pasta pessoal que nenhum outro agente consegue abrir. Uma competência
  é o sítio onde pôr o que quer que o agente seguinte também saiba.

### Escrever uma

Não há nenhum editor para isto na interface, de propósito: o que uma
competência diz entra diretamente no raciocínio de um agente que corre às
quatro da manhã sem ninguém a ver, por isso pertence ao root, tal como as
ferramentas. Escreve-as no servidor:

```bash
mkdir -p /opt/boa/skills/DatabaseBackup
nano /opt/boa/skills/DatabaseBackup/SKILL.md
```

O ficheiro começa com um cabeçalho de duas linhas e depois diz o que tiver de
dizer:

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

A `description` é a linha que mais importa. É a única parte que todas as
execuções pagam, e é com base nela que o agente decide se vai ler o resto.
«How the nightly dump is taken and where it goes» (como se faz o dump noturno e
para onde vai) diz-lhe quando isto se aplica; «Database stuff» (coisas da base
de dados) não.

Recarregue a página do agente e a competência está na lista.

Uma atualização nunca toca em `/opt/boa/skills/`: o que lá escrever continua a
ser seu. A interface web decide que agente recebe que competência; não as
edita.

### Uma competência pode trazer os seus próprios ficheiros

Tudo o resto que estiver na pasta viaja com ela:

```
/opt/boa/skills/DatabaseBackup/
  SKILL.md
  dump.sh
  exclude-tables.txt
```

Os agentes podem lê-los e executá-los, por isso o procedimento pode dizer
«executa o `dump.sh` desta pasta» em vez de explicar quarenta linhas de shell.
`skill.read` diz ao agente que ficheiros estão lá e onde.

### Quanto custa

Só o nome e a descrição de cada competência entram no prompt - cerca de duas
linhas cada. O corpo é obtido com `skill.read`, uma vez, por um agente que
decidiu que precisa dele, e só nessa altura. Dar cinco competências a um agente
custa-lhe umas duas centenas de tokens por execução, não dez mil, e é por isso
que lhe pode dar cinco sem pensar na fatura.

### Se eliminar uma competência que os agentes estão a usar

Nada se parte, e nenhum agente fica a prometer algo que não pode cumprir:

- **Desaparece do prompt** de todos os agentes que a tinham, na sua execução
  seguinte. Nunca se fala a um agente de um procedimento que ele não consegue
  ler.
- **Desaparece do painel Competências**, por isso ninguém a pode voltar a
  marcar.
- O nome **fica no `info.json` do agente** até que algo o reescreva, por isso
  repor a pasta restaura a competência sem mais nada a fazer.
- Se o agente a pedir mesmo assim - pode lembrar-se do nome de uma execução
  anterior - é-lhe dito que a competência está na sua lista mas já não está
  instalada, e que não tente adivinhar o que dizia.

Uma coisa a saber: **carregar em Guardar nesse agente enquanto a competência
está em falta retira-a da lista de vez.** A interface só guarda competências
que existem, que é o que impede que uma eliminada fique por lá para sempre.
Reponha a pasta antes de guardar o agente, ou volte a marcar a competência
depois.

## Dar um navegador a um agente

`web.fetch` lê uma página pública e mais nada: sem início de sessão, sem
formulário, sem botão. Se um agente precisar de *usar* um site em vez de o ler,
precisa de um navegador.

Vem instalado: o instalador pergunta uma vez, e sim é a resposta predefinida.
São cerca de 600 MB de Chromium, por isso uma máquina com pouco disco pode
recusá-lo, e mudar de ideias mais tarde num sentido ou no outro:

```bash
./install-update-reinstall-debian.sh --update --browser no    # deixa-o de fora
./install-update-reinstall-debian.sh --update --browser yes   # volta a acrescentá-lo
```

A resposta fica guardada, tal como a das portas. Depois, marque as ferramentas
de navegador no painel **Ferramentas** do agente:

Nada disto se aplica em Alpine: lá não há navegador nenhum, porque o Playwright
não publica nenhuma build para musl. As ferramentas ficam na lista e dizem-no
quando um agente chama uma delas.

| Ferramenta | O que o agente pode fazer |
|---|---|
| `browser.open` | Ir a uma página. Os cookies são mantidos |
| `browser.read` | Ler outra vez a página aberta, uma parte dela, ou as suas ligações |
| `browser.click` | Clicar numa ligação ou num botão, pelo seu texto visível ou por um seletor |
| `browser.type` | Preencher um campo, carregando opcionalmente em Enter |
| `browser.screenshot` | Guardar um PNG na sua própria pasta de transferências |
| `image.send` | Anexar um PNG à resposta na conversa web e no Telegram, Discord, X, Mattermost ou Slack |


`browser.screenshot` guarda um PNG no servidor. Para o mostrar na conversa, o
agente chama depois `image.send` com esse caminho. Conceda **image.send** em
**Definições do agente → Ferramentas → Imagens** e depois guarde. Os agentes
novos criados a partir do **web-navigator** já a incluem; os agentes existentes
mantêm as permissões que têm.

A imagem ocupa a área de texto da mensagem na conversa web, mantendo a sua
proporção e a altura completa. Também pode ser aberta no seu tamanho original.
Quando a conversa começou no Telegram, Discord, X, Mattermost ou Slack, é enviada também para lá. As capturas
altas ou grandes são entregues como documentos PNG. Um envio falhado volta a
tentar a parte em falta sem repetir o texto nem as imagens que já chegaram.

Só são aceites ficheiros PNG dentro da pasta pessoal desse agente, até 50 MiB
cada e 16 por resposta. Os anexos ficam privados e exigem uma sessão iniciada
para serem vistos. Uma captura já existente pode ser enviada pedindo ao agente
que use `image.send` com o caminho onde foi guardada.

### As sessões de cada agente são só suas

O navegador em si é uma única cópia, em `/opt/boa/playwright/`, que pertence ao
root e é só de leitura para todos os outros. O que **não** é partilhado é o
perfil:

```
/opt/boa/agents/001/browser/profile/     agent-001, 0700
/opt/boa/agents/002/browser/profile/     agent-002, 0700
```

Um agente que inicia sessão num site continua com a sessão iniciada **na sua
execução seguinte**, porque os cookies estão no seu próprio disco. E nenhum
outro agente fica com a sessão iniciada, porque essa pasta é 0700 e pertence ao
seu utilizador Linux - é o kernel que recusa, não há nenhuma verificação em
Python que possa falhar. Essa separação é precisamente o que um produto
alojado não consegue oferecer quando todos os seus agentes partilham uma
máquina.

Os cookies de sessão continuam a terminar quando o navegador fecha, aqui como
em qualquer navegador. O que um site marca para persistir, persiste.

### O que não faz

- **Nada de endereços privados.** `browser.open` recusa `192.168.*`, `127.*` e
  os restantes, exatamente como faz `web.fetch`. Um agente que acabou de ler
  uma página hostil não pode ser convencido a abrir o seu router, e um
  navegador com sessão seria uma ferramenta muito melhor para isso do que um
  simples pedido.
- **Sem ecrã.** Funciona sem interface gráfica (headless). `browser.screenshot`
  é a forma de ver o que ele viu; o próprio agente não consegue olhar para a
  imagem.
- **Nada sem as ferramentas.** Como em tudo o resto, uma ferramenta que não foi
  dada ao agente é uma ferramenta que ele não consegue chamar, e essa
  verificação está no servidor.
- **Sem transferências.** Uma transferência iniciada por uma página é recusada, por isso nenhuma página decide quantos ficheiros ou bytes vão parar ao home do agente. `browser.screenshot` continua a guardar as suas imagens.

Se o navegador nunca foi instalado, as ferramentas continuam a aparecer na
lista e respondem com o comando a executar. Não desaparecem, e não falham em
silêncio.

## Tetos de gasto

Quatro tetos, por agente, e cada execução para no primeiro que atingir:

| Teto | Predefinição | Contra o que protege |
|---|---|---|
| Tokens por execução | 16384 | Uma única conversa cara |
| Passos por execução | 25 | Um ciclo que chama ferramentas para sempre |
| Segundos por execução | 300 | Uma execução que fica pendurada |
| Execuções por dia | 48 | Uma linha de cron demasiado entusiasta |

Isto não é paranoia. Um agente que acorda de hora a hora numa API paga, sem
teto e sem ninguém a vigiar, é uma fatura que cresce enquanto dorme.

O BoA guarda ele próprio a contagem de execuções por dia, onde o agente não lhe chega: um agente não consegue recuperar o seu dia editando o próprio histórico. Se essa contagem não puder ser lida (porque o `boa-agent-api` está parado), uma execução agendada não começa.

Aumente-os depois de ver o que o agente realmente usa, no seu painel
**Histórico**.

### O modelo de reserva

Em **LLMs** há um segundo fornecedor e modelo, por baixo do primeiro. Só é
usado quando o principal **falha** - sem chave, sem resposta, um modelo que não
existe - e a execução continua com ele a partir do mesmo passo, reenviando o
que aconteceu até ali, para que o trabalho já feito não seja deitado fora.

É tentado **uma vez por execução**. Se o de reserva também falhar, a execução
falha: tentar um e outro alternadamente para sempre queimaria os tetos numa
falha de serviço e continuaria sem nada para mostrar. A passagem para o de
reserva fica escrita no histórico do agente, porque uma execução que responde
discretamente com outro modelo, e fatura a outra conta, tem de o dizer.

Deixar o fornecedor de reserva em **nenhum** é a predefinição, e significa que
uma falha termina a execução.

Escolha o **mesmo fornecedor** para a reserva e a caixa do modelo preenche-se
com um modelo *diferente* do catálogo desse fornecedor, não o mesmo outra vez.
O mesmo fornecedor e o mesmo modelo não conseguem responder a nada a que o
principal não conseguisse: falhariam exatamente pela mesma razão, sempre. Se
mesmo assim escrever o par igual, uma linha por baixo do campo di-lo - o agente
é seu, por isso é um aviso e não uma recusa.


Quando uma execução para no seu teto de tokens ou de passos, pede-se ao agente
mais uma vez - sem ferramentas, com um pequeno orçamento próprio - a resposta
que estava prestes a dar, para que uma execução que gastou todo o orçamento a
reunir factos não acabe em «vou verificar o sistema». A conversa indica-o por
baixo da resposta, porque essa resposta pode ficar cortada. O teto de tempo não
tem direito a essa chamada: a execução já vai atrasada.

O limite de tokens cobre cada pedido inteiro, prompt incluído. Antes de enviar um pedido, o seu prompt é estimado a partir do tamanho - e, quando o fornecedor já respondeu, a partir do que esse fornecedor contou de facto - e o pedido só sai se esse prompt e algum espaço para responder couberem no que resta. A chamada de fecho só é feita se também couber: depois do limite de tokens raramente há espaço para ela, e a execução termina com o que o agente tinha escrito. Assim uma execução fica dentro do limite, a menos do erro de uma estimativa.

### O que o kernel impõe por cima

Os quatro limites são aplicados pela própria execução. Outros dois são aplicados pelo kernel, e por isso mantêm-se quando é a execução que corre mal: nenhum agente pode ter mais de 1024 processos e threads ao mesmo tempo, pelo que um comando que se bifurca sem fim para aí e não na máquina; e cada execução vive num cgroup próprio com 2 GiB de memória - um scope do systemd no Debian, um cgroup que o executor prepara no Alpine -, que além disso termina o que a execução deixou a correr em segundo plano ao acabar. Os mesmos dois limites valem para uma execução que o crontab inicia, para os scripts agendados e para a indexação da biblioteca. Uma execução morta pelo limite de memória aparece no Histórico como falhada e no chat como erro, como qualquer outra. Um navegador já são algumas centenas de threads, e é por isso que o número não é menor. Num Alpine cujos cgroups não podem ser delegados, só o primeiro limite se mantém, e o registo do `boa-exec` di-lo.

## Agendar um agente

Em **Cron**, escreva o crontab do agente. É o crontab do próprio agente, que
pertence ao seu próprio utilizador Linux e é executado por ele, exatamente como
se tivesse executado `crontab -e` como esse utilizador.

De hora a hora:

```
0 * * * * /opt/boa/venv/bin/python3 /opt/boa/webapp/backend/core/runner.py --agent-id 001
```

Todos os dias úteis às 08:00:

```
0 8 * * 1-5 /opt/boa/venv/bin/python3 /opt/boa/webapp/backend/core/runner.py --agent-id 001
```

A interface mostra a linha exata para o agente que está a editar, por isso pode
copiá-la e alterar apenas o horário.

Estas linhas não executam o agente sem proteção. O runner que uma linha inicia repara que o cron o iniciou fora do cgroup de uma execução, pede a execução ao executor e termina, pelo que uma execução agendada tem os mesmos limites de memória e tarefas de uma iniciada a partir da interface. Um agente não pode escrever linhas próprias: no Debian o instalador só deixa o root e o grupo `crontab` executar `/usr/bin/crontab`, e no Alpine já pertence ao root.

Deixe-o vazio para remover o horário. Desmarque **Ligado** para manter o
horário mas fazer com que o agente o ignore.

Se usar um fornecedor pago cujo preço varia com a hora — a DeepSeek cobra
várias vezes mais nas horas de ponta — é aqui que essa escolha se faz.

## O quadro kanban

A página tem dois separadores: **Quadro**, que são as três colunas, e **Criar
cartão**, que é o formulário. O que está aberto fica no URL, por isso um
recarregamento e o botão de retroceder mantêm-no. Guardar um cartão leva-o de
volta ao quadro.

Três colunas: **por fazer**, **em curso**, **feito**.

O quadro é o que os agentes usam para deixar trabalho uns aos outros e o que
você usa para ver o que realmente aconteceu. Cada cartão leva consigo o seu
histórico: quem o criou, quem o moveu, quando e porquê.

Um cartão tem um título e uma caixa **O que fazer**. O título dá-lhe nome; a
caixa é onde vão as instruções, e um agente lê ambos. Um cartão atribuído a um
agente sem nada na caixa deixa-o a adivinhar, que é a razão habitual pela qual
um agente não faz nada com um cartão que lhe foi entregue.

A outra razão é o agente não conseguir ver o quadro de todo. Um agente lê-o
chamando `kanban.list_cards` ou não o lê - o quadro nunca é posto no seu
prompt - por isso um agente sem essa ferramenta nunca fica a saber que o cartão
existe. **Atribuir a** avisa disso quando escolhe um agente assim. É um aviso,
não um bloqueio: o cartão é criado na mesma, e basta marcar a ferramenta no
separador **Ferramentas** do agente.

Um cartão no quadro mostra quem o fez, quem o tem, quando foi feito, as duas
primeiras linhas do seu título, as três primeiras do que há a fazer, e
**quando é executado**. O título ou corpo completos, quando cortados, estão na
sua dica.

Essa última linha é a que vale a pena ler. Um cartão sem hora não está
atrasado: ninguém é acordado por causa dele, e o seu agente vai encontrá-lo na
sua próxima execução agendada. **Mover para** é como move um cartão à mão -
este quadro não tem arrastar.

Pode acrescentar, mover e eliminar qualquer cartão. **Um agente só vê e altera
os seus**: um cartão é de um agente se foi ele que o criou ou se lhe está
atribuído.

Isso é uma parede, não uma preferência. Um agente não consegue saber sequer
que existe trabalho de outro agente - nem os títulos, nem quantos são, nem que
há alguma coisa ali. Peça a um agente que mova um cartão que não é seu e é-lhe
dito que não existe nenhum cartão seu com esse id; um cartão que não existe
recebe a mesma frase, porque uma recusa que distinguisse os dois casos seria uma
forma de perguntar ao quadro o que tem, um id de cada vez.

A exceção é o **manager** (agente 000), o orquestrador: o seu trabalho é
distribuir tarefas e acompanhá-las, por isso lê o quadro inteiro. É por isso
que a coordenação é trabalho dele e de mais ninguém.

Uma confirmação destrutiva **não tem botão predefinido**: abre com o foco na
própria caixa de diálogo, por isso o Enter não faz nem uma coisa nem outra e
tem de dizer qual das duas quer. Escape cancela. Clique no botão vermelho para
avançar.

Uma confirmação normal, que não destrói nada, abre de facto com o foco no seu
botão de confirmar, com contorno, onde Enter significa sim.

Eliminar um cartão deixa uma linha a registar que ele existiu e quem o
eliminou, para que um agente não consiga apagar as provas do que estava a
fazer.

## Definições

As definições estão agrupadas em separadores, e o separador fica no URL, por
isso um recarregamento ou um marcador levam-no para onde estava:

| Separador | O que contém |
|---|---|
| **Sistema operativo** | O que é esta máquina, quanta memória e disco restam, e se os quatro serviços estão a funcionar - cada um a verde quando está ativo e a vermelho quando não está. Lido sem privilégios, da mesma forma que o `os-watcher` o lê |
| **Conta** | O único endereço de e-mail e a palavra-passe. Alterar a palavra-passe exige a atual |
| **E-mail** | SMTP, para quando algo precisa de lhe chegar por correio |
| **Canais** | Discord, Mattermost, Slack, Telegram, X, por ordem alfabética - uma caixa para cada um, com o seu próprio botão Guardar |
| **Áudio** | Motor de transcrição, fornecedor, transferência de modelos, idioma e conservação do áudio do Telegram |
| **Ferramentas** | Ferramentas instaladas, agrupadas em subseparadores como Automação e Navegador |
| **Agentes** | Definições para todos os agentes de uma vez, e o repositório e o ramo de onde vêm os modelos. Guardadas no servidor: uma execução iniciada pelo cron não tem navegador onde ler uma preferência |
| **Conversa** | Como se comporta a caixa de mensagem: se o Enter envia, se cada resposta mostra quanto custou |
| **Kanban** | Quantos cartões mostra cada coluna, e se lista os eliminados recentemente |
| **Interface** | Tema, idioma, quanto tempo fica uma mensagem pop-up, e se o **+** pergunta de onde parte um novo agente |

Em **Sistema operativo**, os estados dos serviços alinham com a segunda coluna
de **Esta máquina**.

As preferências de Conversa, Kanban e Interface ficam guardadas no seu
navegador e não no servidor: descrevem como trabalha nesta máquina, e um
telemóvel e um computador de secretária podem, com razão, não estar de acordo.

### Transcrição de áudio

Em Alpine, a instalação e as atualizações devolvem o controlo da sessão SSH quando terminam; o OpenRC mantém os serviços a correr.

Abra **Definições → Áudio**. Estas definições ficam guardadas no servidor e aplicam-se às notas de voz e aos ficheiros de áudio recebidos através do Telegram.

1. Escolha **Local · whisper.cpp** ou **API de um fornecedor**. A transcrição começa desativada.
2. Para o reconhecimento local, escolha um modelo e clique em **Descarregar modelo** se for preciso. O instalador prepara o `base`; o seletor oferece os 30 modelos oficiais, incluindo as variantes `.en` só para inglês e as quantizadas, além dos modelos `ggml-*.bin` instalados manualmente em `/opt/boa/whisper/models/`. São mostrados o tamanho e o estado da instalação. Os modelos maiores precisam de mais memória e tempo de CPU.
3. Para uma API, guarde primeiro a sua chave em **Chaves de API**. OpenAI, Groq, Mistral, Together AI, Hugging Face e Cloudflare aparecem quando há uma chave guardada. Escolha uma sugestão ou introduza outro identificador de modelo de transcrição desse fornecedor. A Cloudflare oferece as suas duas variantes de Whisper suportadas e usa uma credencial `account-id:api-token`.
4. Escolha o idioma (`auto` ou um código como `en`), a duração máxima e se deve guardar o áudio para reprodução; clique em **Guardar**. Responda a uma mensagem de um agente no Telegram com uma nota de voz para experimentar. Também pode selecionar primeiro o agente com `/agents`.

O limite inicial é de 600 segundos, configurável de 30 a 3600; o ficheiro recebido não pode exceder 20 MiB. O processamento acontece em segundo plano e a sua fila sobrevive a uma atualização. Um agente ocupado recebe o texto guardado quando estiver disponível. Um nome de agente dito dentro da gravação não altera o seu destino.

A conversa web mostra a transcrição e, quando a conservação está ativada, um leitor. Fica guardada uma cópia Ogg para reprodução, acessível apenas com sessão iniciada. Desativar a conservação mantém apenas o texto nas mensagens novas. Limpar uma conversa remove o áudio guardado das tarefas concluídas. As cópias de segurança incluem esse áudio; os modelos transferidos sobrevivem às atualizações mas não entram na cópia de segurança. Depois de restaurar noutra máquina, transfira a partir de Áudio qualquer modelo adicional que falte.

O reconhecimento local processa o áudio no seu servidor. O reconhecimento por API envia-o ao fornecedor selecionado e pode implicar custos à parte do uso do modelo do agente. Uma falha local nunca passa automaticamente para um fornecedor na nuvem. O Whisper transcreve em vez de traduzir; os modelos `.en` só entendem inglês. A entrada de áudio é feita pelo Telegram; a conversa web mostra o resultado sem acrescentar um botão de gravação.

Numa instalação existente, execute o instalador da sua distribuição como root com `--update`. Instala o FFmpeg, o whisper.cpp e o modelo base em `/opt/boa/whisper/`; a transcrição fica desativada até ser configurada.

### Idiomas

A interface vem em quinze:

| | | |
|---|---|---|
| Deutsch (Deutschland) | English (United Kingdom) | English (United States) |
| Español (Argentina) | Español (España) | Français (France) |
| עברית (ישראל) | हिन्दी (भारत) | Italiano (Italia) |
| 日本語 (日本) | 한국어 (대한민국) | Português (Brasil) |
| Português (Portugal) | Русский (Россия) | 简体中文 (中国) |

O hebraico escreve-se da direita para a esquerda, e escolhê-lo espelha toda a
interface: a barra lateral passa para a direita e tudo o resto a acompanha. O
código, os caminhos e os comandos continuam da esquerda para a direita, e cada
mensagem de conversa segue o seu próprio idioma, pelo que uma resposta em
inglês continua a ler-se da esquerda para a direita numa página em hebraico.

**Definições → Interface → Idioma** escolhe um, e fica guardado no seu
navegador, tal como o tema. Um navegador que nunca escolheu fica com o mais
próximo do que pede, e com inglês quando não há nenhum.

Há outras duas coisas que seguem o idioma e que **não** são uma preferência do
navegador, porque uma execução iniciada pelo cron não tem navegador:

- **Definições → Agentes → Idioma em que os agentes respondem** acrescenta uma
  linha ao prompt de sistema de cada agente, escrita nesse idioma.
- Os **bots do Telegram, Discord, X, Mattermost e Slack** também o falam: as suas próprias frases,
  o relatório de `/status`
  e o texto de ajuda.

## Mensagens pop-up

Quando algo é guardado, a confirmação aparece no meio do painel que está a ver
e depois desaparece sozinha. Está de propósito no caminho: o botão Guardar no
fundo de um separador comprido produzia antes uma linha no topo da página,
vários ecrãs acima de onde estava a olhar, por isso guardar parecia não ter
feito nada.

**Definições → Interface → Segundos que uma mensagem pop-up fica no ecrã**
define quanto tempo, entre 1 e 30 segundos. Três é o valor predefinido: tempo
suficiente para ler «Definições guardadas», e curto o suficiente para não ficar
por cima da caixa onde ia escrever.

As mensagens de erro ignoram esse número. Ficam até as fechar, com o `×` ou com
Escape, porque um erro é a única mensagem que ainda tem de lá estar quando
voltar a olhar para o ecrã.

A cor diz qual de três coisas aconteceu:

| Cor | O que significa |
|---|---|
| Verde | Foi guardado |
| Âmbar | **Não há alterações para guardar** - carregou em Guardar e nada no formulário tinha mudado |
| Vermelho | Falhou. Diz o que correu mal, e espera ser fechada |

A âmbar aplica-se em todo o lado onde se pode carregar em Guardar:
**Definições** - a conta, o servidor de correio, as chaves de API, os canais e
as preferências do navegador - e as definições próprias de um agente. Carregar
em Guardar duas vezes di-lo da segunda vez, em vez de anunciar uma gravação que
não aconteceu. Um agente acabado de criar é a exceção: o seu formulário contém
os valores do modelo e nunca foi guardado, por isso Guardar escreve-os e leva-o
para a sua conversa.

## Temas

**Definições → Interface** escolhe a paleta:

| Tema | O que é |
|---|---|
| **Day** | Cinzentos suaves com cartões mais claros, para uma sala iluminada |
| **Night** | A paleta escura, para uma sala às escuras |
| **Day High Contrast** | Fundo branco, texto quase preto, contornos duros. Aqui nada é preenchido com a cor de destaque: a caixa de um agente na barra lateral é um contorno, e a sua própria mensagem é preenchida com uma tinta suavizada em vez de azul |
| **Night High Contrast** | Fundo quase preto, texto claro e contornos duros. O agente selecionado tem um preenchimento cinzento; os separadores selecionados têm um contorno fechado ligado à linha de baixo. As suas próprias mensagens usam um branco atenuado |

Um navegador que nunca escolheu começa no que, de Day e Night, corresponder ao
sistema operativo, e segue-o até alguém escolher um. A partir daí a escolha
fica guardada neste navegador, tal como o idioma, por isso um telemóvel e um
computador de secretária não têm de estar de acordo.

Um tema é um ficheiro CSS em `frontend/themes/` no servidor que redefine as
variáveis `--colour-*`. Colocar lá um ficheiro acrescenta um tema - não há
nenhuma lista no código para atualizar. O seu nome e a sua descrição vêm do
comentário no topo do ficheiro:

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

Defina todas. Uma variável que um tema deixe de fora mantém o valor de
app.css - o que, num tema claro, significa uma cor da paleta escura esquecida
no meio dele.

Todos os temas incluídos aqui ultrapassam um contraste de 4,5:1 em todas as
cores em que pintam texto, e os dois de alto contraste ultrapassam 7:1 - WCAG
AAA. Há um teste que falha se algum deixar de o cumprir, medido pela fasquia
que o seu nome promete. Um tema acrescentado
à mão não está sujeito a isso, mas a mesma pergunta aplica-se-lhe: um serviço
marcado como em baixo num vermelho que ninguém consegue ler é um serviço em que
ninguém repara.

## Quando um cartão é executado

Atribuir um cartão é a forma de dar trabalho a um agente, e é um serviço
**buzzer** que transforma isso numa execução:

    a cada poucos segundos:
      cartões com dono, uma hora que já passou e ainda sem aviso
        -> iniciar esse agente, a não ser que já esteja a correr
        -> registar o aviso no cartão

**Quando**, no formulário de acrescentar cartão, decide a hora:

| Opção | O que acontece |
|---|---|
| **Imediatamente** | O agente é acordado assim que o cartão é guardado. É a predefinição: atribuir um cartão é pedir o trabalho |
| **Quando o agente acordar** | O cartão espera no quadro. Ninguém é acordado; o agente encontra-o na sua próxima execução por iniciativa própria |
| **Agendar para uma hora** | Uma hora em UTC. O agente é acordado nessa altura |

Um agente que já está a trabalhar não é interrompido. O cartão mantém a sua vez
e volta a ser tentado na passagem seguinte, por isso uma execução agendada para
um agente ocupado começa uns segundos atrasada em vez de não começar, e um
agente nunca tem duas execuções ao mesmo tempo. Um cartão só dá um aviso: para
o executar outra vez, volte a definir-lhe a hora.

### O cartão aparece na conversa do agente

Quando a execução começa, a conversa do agente recebe uma mensagem que
identifica o cartão:

    Foi-lhe atribuída uma tarefa num cartão:

    ID do cartão: 1284
    Título: Renovar os certificados
    Em que consiste: “Executar o instalador com --update e relatar”
    A executar: Imediatamente

Se foi outro agente a entregar o cartão, a primeira linha diz quem: *manager
atribuiu-lhe um novo cartão*. Se o cartão foi agendado em vez de pedido de
imediato, a última linha mostra antes a hora: `a2026m03d31@13:45`, em UTC, a
mesma hora que o quadro mostra no cartão.

A mensagem é escrita **quando a execução começa**, nunca antes. Um cartão que
agende para esta noite e elimine esta tarde não deixa nada na conversa, porque
nunca correu nada.

O agente responde por baixo como a qualquer outra mensagem, com o que a
execução custou. Há três coisas que podem pôr ali uma linha sem que o agente
tenha feito nada, e cada uma diz qual foi: o agente estava desligado, já tinha
gastado as execuções do dia, ou a execução nem sequer pôde ser iniciada. Nenhuma
delas é silenciosa, porque um cartão que foi anunciado e depois ignorado parece
exatamente um agente que não está a funcionar.

Uma coisa que esta execução não faz é ler a conversa. As suas instruções são o
cartão. O que disse antes na conversa só é reenviado quando é você a enviar uma
mensagem - caso contrário, cada execução agendada pagaria por uma conversa que
ninguém está a ter.

Um cartão entregue ao **manager** é tratado de outra forma: é-lhe dito que
decida quem deve fazer o trabalho e que passe o cartão com
`kanban.assign_card`. O cartão mantém o seu id, as suas instruções e o seu
histórico e muda de mãos, e o agente a quem chega é acordado por causa dele.
Isso é delegação - não um segundo cartão para o mesmo trabalho.

<a id="channel-setup"></a>

## Canais

Em **Definições → Canais**, configure para onde os agentes podem escrever:

| Canal | Do que precisa |
|---|---|
| Discord | um `bot_token` e um `channel_id` para falar nos dois sentidos, ou um URL de webhook só para enviar |
| Mattermost | `server_url`, `bot_token` e `channel_id` para conversar; `webhook_url` apenas para avisos |
| Slack | `bot_token` e `channel_id`; receber também exige `app_token` e Socket Mode |
| Telegram | o `bot_token` do BotFather, e o `chat_id` |
| X | `client_id`, `client_secret`, OAuth 2.0, `recipient_id` |

Cada canal configurado mostra **Configurado** a verde, com a mesma cor de uma
chave de API guardada. Os canais sem configuração mantêm o seu estado neutro.

As credenciais são guardadas de forma a que **nenhum agente as consiga ler**.
Um agente pede ao servidor que envie; o servidor lê o token e envia. A mensagem
chega precedida do nome do agente, acrescentado pelo servidor, para que nenhum
agente se possa fazer passar por outro.

Depois, no separador **Canais** de cada agente, marque que canais pode usar. Precisa das duas coisas:
`channel.write` e o próprio canal.

### Antes de conectar um canal

1. Termine de instalar o BoA, entre e configure um fornecedor e um modelo funcionais no separador **LLMs** do agente. Ative o agente em **Geral** e confirme a resposta no chat web. Os exemplos usam `manager`, presente numa instalação nova; substitua esse nome se o alterou.
2. Crie seu próprio bot ou aplicação e o destino seguindo os passos abaixo. O token é diferente da chave de API do modelo de linguagem. O BoA armazena um destino por tipo de canal. Telegram, Discord, Slack, Mattermost e X permitem conversar; o X recebe mensagens privadas do interlocutor configurado e pode publicar no perfil quando solicitado explicitamente.
3. Para notificações separadas, permita `channel.write` em **Ferramentas** e selecione o destino no separador **Canais** do agente. O BoA entrega automaticamente as respostas às conversas recebidas. Para anexar PNG, permita também `image.send` e forneça um PNG existente na pasta pessoal do agente.

Os instaladores criam e iniciam os serviços de escuta no Debian e no Alpine. Depois de inserir as credenciais, ative a receção em **Definições → Canais** e pressione **Guardar** na caixa do canal. O indicador verde confirma que a configuração foi guardada; faça também o teste de mensagens. Os campos secretos guardados aparecem vazios ou mascarados; deixá-los vazios preserva os valores.

Use apenas uma instalação do BoA escutando por bot ou aplicação Slack. Estas integrações abrem conexões de saída para seus serviços; não precisam de URL pública do BoA, encaminhamento de portas de entrada ou certificado HTTPS público.

<a id="responder-a-um-agente-a-partir-do-telegram"></a>

## Telegram

### Criar o bot e obter o ID do chat

1. Abra a conta oficial [@BotFather](https://t.me/BotFather) no Telegram, envie `/newbot` e escolha um nome e um nome de utilizador exclusivo terminado em `bot`. Copie o token recebido: ele é `bot_token`. O [guia de criação de bots do Telegram](https://core.telegram.org/bots/features#creating-a-new-bot) explica esses campos.
2. Abra o novo bot pelo link do BotFather, pressione **Iniciar** e envie uma mensagem curta. Comece com uma conversa privada. Mantenha a escuta do Telegram no BoA desativada enquanto obtém o ID.
3. Em um terminal do servidor BoA, execute o comando abaixo e cole o token quando solicitado; a entrada fica oculta. Ele usa a API [getUpdates](https://core.telegram.org/bots/api#getupdates) do Telegram e mostra o ID, tipo e nome de cada chat com mensagem pendente. Copie o ID numérico da sua conversa, incluindo o sinal de menos se houver, para `chat_id`. Não é o nome de utilizador do bot nem seu token.

```bash
/opt/boa/venv/bin/python3 -c '
import getpass
import requests
vToken = getpass.getpass("bot_token: ")
try:
  dResult = requests.get(
    "https://api.telegram.org/bot" + vToken + "/getUpdates",
    params={"timeout": 0, "allowed_updates": "[\"message\"]"}, timeout=20).json()
except (requests.RequestException, ValueError):
  raise SystemExit("Cannot read Telegram updates.")
if not dResult.get("ok"):
  raise SystemExit(dResult.get("description", "Telegram error."))
if not dResult.get("result"):
  print("Send a new message to your bot, then run this command again.")
for dUpdate in dResult.get("result", []):
  dChat = dUpdate.get("message", {}).get("chat", {})
  if dChat:
    print(dChat["id"], dChat.get("type", ""),
          dChat.get("title") or dChat.get("first_name", ""))
'
```

Se nenhum chat aparecer, envie outra mensagem e repita o comando. Para um grupo, adicione o bot e envie `/help@nome_de_usuario_do_bot` no grupo; depois obtenha o ID próprio do grupo da mesma forma. Para receber mensagens normais do grupo, use `/setprivacy` no BotFather, selecione o bot, escolha **Disable**, remova o bot do grupo e adicione-o novamente. Todos os membros do grupo configurado podem falar com seus agentes. O [guia do modo de privacidade](https://core.telegram.org/bots/features#privacy-mode) explica quais mensagens chegam aos bots.

### Ativar e verificar o Telegram

1. Abra **Definições → Canais → Telegram**, preencha `bot_token` e `chat_id`, marque **Deixar que eu responda aos agentes pelo Telegram** e pressione **Guardar**.
2. Nesse mesmo chat do Telegram, envie `/agents`. O bot deve mostrar a lista de agentes. Depois envie `@manager Responda com BOA-OK` e confira a resposta ali e no chat web do `manager`. Responda à mensagem do bot com outra pergunta para verificar a continuação.
3. Para testar uma notificação de saída, conceda `channel.write` e Telegram como explicado acima e peça explicitamente ao agente no chat web que envie `BOA-OK` ao Telegram usando `channel.write`.

Se não responder, confira se pressionou **Iniciar**, se o bot não está bloqueado e se copiou o `chat_id` correto. `401` aponta para o token; `409` pode indicar outro programa consultando as mensagens ou um webhook antigo. Pare o outro consumidor; ao reutilizar um bot, remova o webhook com [deleteWebhook](https://core.telegram.org/bots/api#deletewebhook) antes das consultas ou crie um bot dedicado. No Debian consulte `journalctl -u boa-channel-telegram.service -f`; no Alpine, `tail -f /opt/boa/logs/boa-telegram.log`.

### Comandos

| Comando | O que faz |
|---|---|
| `/agents` | Lista os seus agentes como botões. Toque num para começar a falar com ele |
| `/status` | Serviços, quadro e todos os agentes com o seu modelo, ferramentas e competências |
| `/help` | Estes três, e as outras duas formas de chegar a um agente |

### Mais ninguém vê nada disto

O nome de utilizador do bot é público - qualquer pessoa que o encontre pode
abri-lo - por isso o menu é escrito **apenas para a sua conversa**. Outra
pessoa que abra o mesmo bot vê uma conversa vazia: sem comandos em `/`, sem
descrição, nada em que carregar a não ser o botão Start, que o Telegram desenha
em todos os bots e que nenhuma API consegue remover.

Carregar nele não faz nada. O listener compara o `chat_id` de cada mensagem com
o das suas definições e descarta o que não coincidir, antes de correr qualquer
comando e antes de se escolher qualquer agente.

**E não fica nada escrito.** Nem resposta, nem linha no log, nem registo de que
alguém tenha escrito. O id de uma conversa que não é sua são dados de outra
pessoa, e guardá-lo significaria a sua instalação a construir discretamente
uma lista de quem encontrou o bot.

O preço é que um `chat_id` mal definido parece exatamente um desconhecido: as
suas próprias mensagens são descartadas em silêncio. O configurado é escrito no
log em cada arranque, e é com isso que se pode comparar:

```bash
journalctl -u boa-channel-telegram.service | grep "Registered"
```

Em Debian, as unidades dos canais usam `boa-channel-<channel>.service`. Execute
o instalador com `--update` para migrar automaticamente os nomes antigos das
unidades. O Alpine mantém os seus nomes OpenRC `boa-telegram`, `boa-discord`, `boa-slack`, `boa-mattermost`, `boa-x`.

O filtro é por **conversa**, não por pessoa. Se o `chat_id` que configurou for
um grupo, todos os membros desse grupo podem falar com os seus agentes.

### Escolher com quem está a falar

Toque em `/agents`, toque num agente, e ele responde:

```
Agente os-watcher:

Envíame tus instrucciones...
```

A partir daí, **tudo o que escrever vai para esse agente** até escolher outro.
Pode fazer quatro perguntas seguidas sem nomear ninguém, que é o que faz disto
uma conversa e não uma linha de comandos.

Três formas de se dirigir a alguém, por esta ordem:

1. **Responder a algo que um agente disse** vai para esse agente, seja qual for
   o que estiver selecionado. Responda à mensagem dele (deslize-a, ou mantenha-a premida ou clique com o botão direito e escolha Responder), escreva, envie.
2. **Nomear um** - `@os-watcher check the disk` - vai para ele *e* torna-o o
   selecionado. `@001` também funciona, tal como um nome com um espaço:
   `@News Miner what is new` é um agente, não duas palavras.
3. **Nenhuma das duas** vai para o último que escolheu.

Mais nada altera a seleção, por isso um agente nunca herda a sua conversa por
ter sido, por acaso, o último a falar. Um agente que elimine deixa de estar
selecionado em vez de continuar a apanhar tudo.

Enquanto não tiver escolhido ninguém, uma mensagem que não nomeie ninguém
recebe de volta a lista de agentes, por isso nunca nada desaparece sem uma
explicação.

### O que volta

O agente responde no Telegram como resposta ao que escreveu, com o seu nome na
primeira linha:

```
os-watcher:
25G free of 28G on /, unchanged since yesterday.
```

**E a troca inteira fica na conversa desse agente na interface web**, a sua
pergunta e a resposta dele, com `(via Telegram)` ao lado da hora no que enviou.
Um único ecrã continua a mostrar tudo o que se pediu ao agente e tudo o que ele
disse, seja qual for o dispositivo em que cada metade foi escrita.

Duas coisas com que contar:

- **Um agente ocupado di-lo.** Se já estiver a responder a alguma coisa, é-lhe
  dito que tente outra vez daqui a um momento em vez de ser posto numa fila -
  uma fila esconderia que um agente está a ficar para trás.
- **Só a sua conversa é escutada.** O nome de utilizador de um bot é público e
  qualquer pessoa que o encontre lhe pode escrever. As mensagens de qualquer
  outra conversa são descartadas sem resposta, por isso o `chat_id` que
  configurou é o que decide quem pode falar com os seus agentes. Se o
  configurar mal, não acontece absolutamente nada.

É long polling, não um webhook: o servidor liga-se para fora, ao Telegram, por
isso não é preciso abrir nada à Internet para isto funcionar.

Se o Telegram não aceitar a resposta - bloqueou o bot, o id da conversa mudou,
o token deixou de ser válido - ela é descartada do Telegram de imediato, e se
não for possível contactar o Telegram durante uma hora também é descartada.
Nunca se perde: a conversa inteira, essa resposta incluída, está na conversa do
agente na interface web.

### Como é a mensagem de um agente

Os modelos escrevem markdown, e o Telegram apresenta um pequeno subconjunto de
HTML, por isso os dois são traduzidos à saída. O que chega vem formatado, não
com asteriscos:

| O que o agente escreve | O que vê no seu telemóvel |
|---|---|
| `**25G free**` | **25G free** |
| `` `df -h` `` | `df -h` em monoespaçado |
| `# Disk report` | uma linha a negrito |
| `- item` | • item |
| uma tabela | um bloco monoespaçado, com as colunas alinhadas |
| ```` ```bash ```` | um bloco de código |
| `[text](https://…)` | uma ligação |

O Telegram não tem títulos, listas nem tabelas próprios, e é por isso que esses
três se tornam na coisa legível mais próxima em vez de desaparecerem.

Se alguma vez o Telegram recusar a formatação, **a mensagem é enviada outra vez
como texto simples em vez de se perder**. Recebe as palavras de qualquer forma;
o log do servidor diz o que aconteceu, para que um erro de formatação se note em
vez de ir degradando discretamente para sempre.

Tudo o que o próprio bot diz - a lista de agentes, «ainda está a responder a
outra coisa», `/status` - está no idioma definido em **Definições → Agentes**, o
mesmo em que os agentes respondem.

<a id="discord-setup"></a>

## Responder a um agente a partir do Discord

O Discord funciona da mesma forma que o Telegram, com um bot seu. Cinco minutos
de configuração, uma única vez.

### Criar o bot

1. Abra o [Discord Developer Portal](https://discord.com/developers/applications), escolha **New Application** e dê um nome. É necessário dispor de um servidor onde possa instalar aplicações.
2. Abra **Bot → Reset Token**, conclua a verificação solicitada e copie o token para `bot_token` do BoA. É o token do bot, não Application ID, Public Key nem Client Secret.
3. Em **Installation**, ative **Guild Install**. Em **OAuth2 → URL Generator**, selecione o escopo `bot` e **View Channels**, **Send Messages**, **Read Message History**, **Attach Files**. Abra a URL gerada, escolha seu servidor e autorize o bot. O [guia de instalação do Discord](https://docs.discord.com/developers/quick-start/getting-started) explica a instalação no servidor e as permissões.
4. Crie ou escolha um canal de texto e confira se suas permissões específicas permitem ao bot esses quatro acessos. No Discord, ative **Configurações de utilizador → Avançado → Modo desenvolvedor**, clique com o botão direito no canal e escolha **Copiar ID do canal**. Coloque esse número em `channel_id`, não o ID do servidor. Veja as [instruções de IDs do Discord](https://support.discord.com/hc/en-us/articles/206346498-Where-can-I-find-my-User-Server-Message-ID).

Em **Discord Developer Portal → Bot → Privileged Gateway Intents**, ative **Message Content Intent** e guarde. As consultas HTTP também exigem essa permissão. Ao ativar a escuta no BoA, guardar verifica o bot, o canal e a permissão; um erro mantém a configuração anterior.

As imagens PNG anexadas por um agente são enviadas para o Discord; o bot precisa de **Attach Files**. Se uma imagem não puder ser entregue, um aviso remete para a conversa web. As partes de texto e imagem confirmadas são registadas separadamente, permitindo que novas tentativas e reinícios continuem pelas partes restantes. Mudar o bot ou o destino inicia um novo cursor e limpa o agente selecionado; as mensagens anteriores do canal não são novamente processadas.

### Ligá-lo

Em **Definições → Canais → Discord**, preencha o token e o id do canal, marque
**Deixar que eu responda aos agentes pelo Discord** e guarde. Em poucos
segundos o log diz que bot está a escutar e onde:

```bash
journalctl -u boa-channel-discord.service | grep "Listening"      # Debian
tail /opt/boa/logs/boa-discord.log                # Alpine
```

As mensagens escritas antes de o ligar não recebem resposta: a primeira
passagem anota onde está o canal e começa a partir daí.

### Primeiro teste e problemas comuns de configuração

Depois de guardar e aguardar a conexão do serviço, envie uma mensagem **nova** com `!agents` pela sua conta humana no canal configurado. Depois envie `@manager Responda com BOA-OK` e confira a resposta no Discord e no BoA. Digite `@manager` como texto: é o nome do agente do BoA, não uma menção do Discord ao bot. Responda à mensagem dele para continuar.

Se o gravação ou receção falhar, confira **Message Content Intent**, o token do bot, `channel_id` e as permissões específicas do canal. PNGs exigem **Attach Files**. Um webhook permite alertas de saída, mas não recebe instruções. Para um envio separado, conceda `channel.write` e Discord ao agente e peça pelo chat web que envie `BOA-OK` ao Discord.

### Falar com um agente

| Comando | O que faz |
|---|---|
| `!agents` | Lista os seus agentes e o que escrever para chegar a cada um |
| `!status` | Serviços, quadro e todos os agentes com o seu modelo, ferramentas e competências |
| `!help` | Estes três, e as outras formas de chegar a um agente |

`/agents` também funciona, se for isso que os seus dedos escrevem. Aqui não há
botões nem menu de comandos com barra: ambos são *interactions*, que o Discord
só entrega através de uma ligação que esta instalação, de propósito, não abre.

As três formas de se dirigir a alguém são as que já conhece:

1. **Responder a algo que um agente disse** vai para esse agente, seja qual for
   o que estiver selecionado. Clique com o botão direito na mensagem → Reply,
   ou deslize-a num telemóvel.
2. **Nomear um** - `@os-watcher check the disk` - vai para ele *e* torna-o o
   selecionado. `!os-watcher`, `@001` e `@News Miner what is new` funcionam
   todos.
3. **Nenhuma das duas** vai para o último que escolheu.

### O que volta

A resposta chega como resposta à sua pergunta, com o nome do agente a negrito
na primeira linha, e **a troca inteira fica na conversa desse agente na
interface web**, com `(via Discord)` ao lado da hora no que enviou.

Uma resposta longa chega em várias mensagens em vez de numa só cortada: o
Discord recusa qualquer coisa acima de 2000 caracteres, por isso uma resposta é
dividida entre linhas, em no máximo quatro mensagens. Pode responder a qualquer
uma delas e chega ao mesmo agente. Se houver mais do que o equivalente a quatro
mensagens, a última termina em `…` - e a resposta inteira está na interface
web, onde foi escrita.

### Quem pode falar com os seus agentes

**Toda a gente que possa escrever nesse canal.** Esta é a única diferença real
em relação ao Telegram, e vale um minuto do seu tempo: lá, o bot compara o id
da conversa de cada mensagem e descarta o que não coincidir, por isso um
desconhecido que encontre o seu bot não obtém nada. Aqui o bot lê um canal, e
qualquer pessoa que possa publicar nele pode iniciar execuções no seu servidor.

Por isso, ponha os agentes num **canal privado** - um que só você, ou você e as
pessoas em quem confia, consigam ver. O bot não precisa de acesso a mais nada.

### Se só quiser alertas

Deixe o token vazio e defina antes um **URL de webhook**: **Channel Settings →
Integrations → Webhooks → New Webhook → Copy Webhook URL**. Os agentes podem
então escrever no canal, e é tudo. Escutar exige o bot, por isso o interruptor
é recusado com um webhook em vez de não fazer nada.

## Slack

### Criar e instalar a aplicação

1. Abra [Slack Apps](https://api.slack.com/apps), escolha **Create New App → From a manifest**, selecione seu espaço de trabalho e cole o JSON de [deploy/slack-app-manifest.json](../deploy/slack-app-manifest.json). Continue com **Next → Create**. O manifesto configura o bot, `/boa`, os eventos e as permissões. Veja o [guia de manifestos do Slack](https://docs.slack.dev/app-manifests/configuring-apps-with-app-manifests/).
2. Abra **OAuth & Permissions**. Em **OAuth Tokens**, pressione **Install to Workspace** ou **Install to &lt;nome do espaço de trabalho&gt;** e depois **Allow**. A mesma ação pode aparecer em **Install App**. Se o espaço de trabalho exigir aprovação, seu administrador deve aprovar a instalação. Não é necessário programar um callback OAuth.
3. Volte a **OAuth & Permissions** e copie **Bot User OAuth Token**, iniciado por `xoxb-`, para `bot_token` do BoA. **Client Secret** e **Signing Secret** são outros valores.

### Ativar a receção de mensagens

1. Em **Basic Information → App-Level Tokens → Generate Token and Scopes**, dê um nome ao token, adicione `connections:write` e pressione **Generate**. Copie o token `xapp-` para `app_token`.
2. Abra **Socket Mode** e confira se **Enable Socket Mode** está ativado. Em **Event Subscriptions**, verifique os eventos do bot `message.channels`, `message.groups` e `message.im`. O manifesto incluído já os configura; essa conexão não precisa de **Request URL**. O [guia de Socket Mode do Slack](https://docs.slack.dev/apis/events-api/using-socket-mode/) explica o token da aplicação e a conexão.
3. Crie ou abra o canal no Slack e use `/invite @BoA` (ou o nome escolhido para o bot). Clique no nome do canal e procure **Channel ID** nos detalhes, normalmente no fim de **About**. Também é possível copiar o link do canal: seu identificador é o componente `C…` ou `G…`, não o identificador `T…` do espaço de trabalho. Salve-o em `channel_id`; não use `#nome-do-canal`.

### Configurar o BoA e fazer o primeiro teste

Em **Definições → Canais → Slack**, insira os três valores:

| Campo do BoA | Valor a copiar |
|---|---|
| `bot_token` | **Bot User OAuth Token** (`xoxb-…`) |
| `app_token` | **App-Level Token** com `connections:write` (`xapp-…`) |
| `channel_id` | ID do canal com o bot (`C…` ou `G…`) |

Marque **Deixar que eu responda aos agentes pelo Slack** e pressione **Guardar**. O BoA verifica os tokens, o acesso ao canal e a conexão Socket Mode. Para apenas notificações, guarde `bot_token` e `channel_id` com a escuta desativada.

Envie `/boa agents` nesse canal. Quando a lista aparecer, envie `@manager Responda com BOA-OK` como mensagem normal. Abra a conversa em thread para ver a resposta e faça outra pergunta ali sem repetir o nome do agente. Confira o mesmo diálogo no chat web do BoA. Para um envio separado, conceda `channel.write` e Slack ao agente e peça explicitamente pelo chat web que envie `BOA-OK` ao Slack.

### Se o Slack não responder

- **Botão de instalação ausente:** confira o espaço de trabalho e os escopos do manifesto em **OAuth & Permissions → Bot Token Scopes**: `channels:history`, `channels:read`, `chat:write`, `commands`, `files:read`, `files:write`, `groups:history`, `groups:read`, `im:history`, `im:read`. Veja também **Install App**. Após mudar os escopos, reinstale a aplicação no espaço de trabalho para concedê-los.
- **`/boa` desconhecido:** confira `/boa` em **Slash Commands**, a instalação da aplicação e o espaço de trabalho onde digitou o comando.
- **`invalid_auth` ou `missing_scope`:** confira os dois tipos de token e os escopos necessários; reinstale após mudar permissões.
- **`not_in_channel` ou `channel_not_found`:** convide o bot e verifique o ID; canais privados também exigem convite.
- **Envia, mas não recebe:** confira a opção de escuta, Socket Mode, `app_token`, os eventos assinados e se há somente uma instalação escutando.

### Entrega e registos do serviço

Use `/boa agents`, `/boa status` e `/boa help`, ou `!agents`, `!status` e `!help`. Inicie uma tarefa com `@nome a sua instrução` ou `/boa @nome a sua instrução`. As respostas ficam na conversa encadeada; cada utilizador tem o seu próprio agente selecionado. Só é aceite o canal configurado, e qualquer pessoa que possa escrever nele pode iniciar agentes. As mensagens recebidas fornecem texto; os agentes podem devolver imagens PNG. A conversa também aparece no chat web com a indicação de origem Slack.

Socket Mode usa uma ligação de saída através do SDK do Slack com versão fixada. A entrada é guardada antes da confirmação de receção. Os identificadores de eventos evitam execuções duplicadas após novas tentativas ou reinícios. As partes entregues e as etapas de carregamento são persistidas; os limites de frequência respeitam a espera indicada pelo Slack. O texto é dividido em até quatro mensagens de 4000 caracteres com blocos de código fechados; a resposta completa permanece no chat web. Entradas não processadas e respostas pendentes expiram após uma hora. Mantenha apenas um listener ativo por aplicação Slack.

```bash
journalctl -u boa-channel-slack.service -f   # Debian
tail -f /opt/boa/logs/boa-slack.log           # Alpine
```

## Mattermost

### Preparar o servidor e o bot

Precisa de um servidor Mattermost acessível pelo BoA e de uma conta com permissões System Admin para criar o bot. O BoA liga-se ao Mattermost, mas não instala esse servidor. Se não tiver um, siga o [guia de instalação do Mattermost](https://docs.mattermost.com/deployment-guide/server/linux/deploy-tar).

1. No Mattermost, abra **System Console → Integrations → Bot Accounts**, ative **Enable Bot Account Creation** e guarde.
2. Abra **Product menu → Integrations → Bot Accounts → Add Bot Account**. Escolha um nome de utilizador como `boa` e nome de exibição `BoA`, mantenha o papel **Member** e selecione **Create Bot Account**.
3. Copie o **Access Token** gerado antes de fechar a confirmação: é o `bot_token` do BoA, não o Token ID. Um token pessoal de uma conta humana comum não é aceito para escutar. O [guia de contas bot](https://docs.mattermost.com/developers/integrate/reference/bot-accounts) explica a criação e a participação.
4. No menu da equipa, use **Invite People → Invite Member** para adicionar o bot à equipa e depois **Add Members** para colocá-lo no canal escolhido. Ser membro do canal também é necessário para enviar ficheiros.
5. Abra os detalhes do canal com **View Info** e copie seu **Channel ID**. Tem 26 caracteres; o nome do canal e o ID da equipa são valores diferentes.

### Configurar o BoA e testar a conexão

Abra **Definições → Canais → Mattermost** e preencha:

| Campo | Valor |
|---|---|
| `server_url` | URL base do seu Mattermost, por exemplo `https://chat.example.org`, incluindo o subcaminho do proxy se houver |
| `bot_token` | Access Token da conta bot |
| `channel_id` | ID do canal onde está o bot |

Marque **Deixar que eu responda aos agentes pelo Mattermost** e pressione **Guardar**. O BoA valida bot, canal e participação antes de guardar. Não precisa de callback OAuth, registro de comandos de barra ou encaminhamento de portas de entrada para o BoA: o serviço consulta a API REST do Mattermost.

Para mudar mais tarde o BoA para outro servidor Mattermost, escreva novamente o `bot_token` na mesma gravação que o novo `server_url`. Um token guardado nunca é enviado para um servidor diferente daquele para o qual foi guardado; sem ele, a gravação é recusada e nada muda.

Envie uma nova mensagem `!agents` da sua conta humana nesse canal e depois `@manager Responda com BOA-OK`. A resposta aparece na thread e no chat web do agente. Continue nessa thread sem repetir o nome. `!status` e `!help` também estão disponíveis; são comandos de texto normais, não comandos de barra do Mattermost. Cada utilizador tem seu próprio agente selecionado e qualquer pessoa que possa escrever no canal configurado pode iniciar execuções.

Para um teste de envio separado, conceda `channel.write` e Mattermost nos separadores **Ferramentas** e **Canais** do agente, depois peça pelo chat web que envie `BOA-OK` ao Mattermost. Para uma imagem, permita também `image.send` e peça para anexar um PNG existente na pasta pessoal. As mensagens recebidas trazem texto; as respostas podem conter PNGs.

### Webhooks de saída e solução de problemas

Para apenas avisos, crie **Integrations → Incoming Webhooks → Add Incoming Webhook**, escolha o canal e copie a URL em `webhook_url` do BoA. Deixe `bot_token` vazio e a escuta desativada. Os campos opcionais `channel` e `username` substituem os valores do webhook somente quando o Mattermost permite. Um webhook não recebe instruções; um token de bot configurado tem prioridade.

Se o bot não responder, confira a escuta, a URL base, o ID do canal e a participação. `401` normalmente indica token inválido, `403` falta de acesso; falhas de PNG podem indicar falta de permissão para envio de ficheiros ou de participação. Para erros TLS, faça o host BoA confiar no certificado do Mattermost. Salvar configurações de escuta inválidas preserva a configuração anterior.

Apenas uma instalação BoA deve escutar o mesmo bot e canal. A primeira ativação e a reativação explícita ignoram mensagens existentes; reinícios normais preservam o ponto de leitura. Entradas e respostas pendentes expiram após uma hora. Textos longos se dividem em no máximo quatro mensagens de 4000 caracteres; a resposta completa fica no chat web. Consulte os registos:

```bash
journalctl -u boa-channel-mattermost.service -f   # Debian
tail -f /opt/boa/logs/boa-mattermost.log           # Alpine
```


## X

O X permite conversas privadas com uma conta configurada e publicações de texto solicitadas explicitamente no perfil autorizado. Precisa de duas contas X diferentes para mensagens diretas, um aplicação no [console de desenvolvedores](https://console.x.com/) e créditos de API. Confira os [preços atuais](https://docs.x.com/x-api/getting-started/pricing) e defina um limite de gastos; o BoA nunca compra créditos. A conta de desenvolvedor pode ser dona do aplicação enquanto outra autoriza o BoA. Menções públicas, grupos e X Chat cifrado não são fontes de entrada desta integração.

1. Crie um aplicação com **New App / Create App** e descreva sua integração pessoal do BoA. Em **User authentication settings → Set up**, escolha **Web App, Automated App or Bot** para OAuth 2.0. Se for exigido um site, use a URL pública do projeto. Registe exatamente a URL de retorno mostrada em **Definições → Canais → X**, incluindo HTTPS, host e caminho. O navegador precisa alcançar o BoA na LAN ao voltar; não é preciso abrir uma porta pública de entrada.
2. Copie **Client ID** e **Client Secret** para `client_id` e `client_secret` e clique em **Guardar**. O **Bearer Token** do aplicação não os substitui. Para permitir publicações, marque **Permitir publicações no perfil do X, cada uma aprovada por mensagem direta** antes de guardar e autorizar. Autorizar X também salva as credenciais e a permissão de publicar antes de iniciar OAuth; a receção fica desligada até você ativá-la após a autorização.
3. Clique em **Autorizar X**, entre na conta que o BoA usará e autorize o aplicação. O BoA solicita `tweet.read`, `users.read`, `dm.read`, `dm.write`, `media.write` e `offline.access`; publicar exige também `tweet.write`. Este último permite publicar, enquanto `offline.access` permite renovar tokens automaticamente. Confira a conta autorizada ao voltar. Se habilitar publicações depois, autorize novamente.
4. Digite o @utilizador da sua conta humana em **Nome de utilizador do destinatário no X**, clique em **Procurar ID do destinatário** para preencher `recipient_id`, marque **Receber mensagens diretas da conta configurada** e **Guardar**. Essa conta precisa ser diferente da conta do BoA e aceitar suas mensagens diretas. Só mensagens individuais de texto desse interlocutor podem iniciar agentes.
5. Na conta humana, envie `!agents` para a conta do BoA e depois `@manager Reply with BOA-OK`. Configure antes o modelo do manager conforme os pré-requisitos comuns dos canais. Aguarde cerca de um minuto para a receção. As próximas mensagens mantêm o agente escolhido até você indicar outro. `!help` e `!status` também funcionam. Para testar uma imagem, conceda `image.send` e peça um PNG já existente na home do agente, com até 5 MiB. Ele chega em privado e continua disponível no chat web.
6. Os avisos enviados com `channel.write` são mensagens diretas privadas: conceda a ferramenta e o X nos separadores **Ferramentas** e **Canais** do agente. `channel.write` nunca publica; as publicações no perfil são a ferramenta `x.post`, explicada abaixo.

**Publicações no perfil.** Um agente com a ferramenta `x.post` e o X entre os seus canais pode pedir para publicar um texto, e apenas pedir. O BoA guarda o texto exato e envia-o à conta destinatária por mensagem direta, com um código de utilização única. A partir dessa conta, responda `!post CÓDIGO` para publicar ou `!discard CÓDIGO` para descartar; um código só serve uma vez e expira ao fim de 60 minutos. O pedido fica ligado à conta autorizada e à destinatária, por isso um código deixa de servir depois de autorizar de novo ou de mudar o destinatário. Pedir exige a opção de publicações, a autorização com `tweet.write` e a receção ativa, porque a resposta chega como mensagem direta. O BoA coloca o nome do agente à frente e envia o texto completo; o X verifica os limites de caracteres. Nunca corta uma publicação nem a transforma num fio. Se o X não confirmar uma publicação, o BoA não a volta a publicar: verifique o perfil.

Mantenha apenas um listener por conta e interlocutor. Ativar a receção começa com mensagens novas; reiniciar o serviço preserva o ponto de leitura. A API permite 15 leituras de mensagens diretas a cada 15 minutos: o BoA consulta a cada 65 segundos e respeita os períodos de espera. As respostas usam texto simples; as longas ocupam até quatro mensagens diretas.

Se a autorização falhar, confira a URL de retorno exata, Client ID/Secret, permissões e créditos da API. HTTP 402 indica problema de créditos ou limite de gastos; 403 exige conferir permissões e aceitação de mensagens; 429 significa aguardar. Autorize novamente após revogação ou falha de renovação. Se a confirmação de envio se perder, o BoA evita repetir automaticamente: confira o X antes de pedir outro envio. Consulte estes logs para falhas de entrega; a resposta completa permanece no chat web.

Os créditos podem ser comprados ou concedidos por uma promoção elegível; confira os [incentivos gratuitos atuais](https://docs.x.com/x-api/getting-started/free-credits). Dependendo do tempo de resposta da API do X, a receção pode levar mais de um minuto.

```bash
journalctl -u boa-channel-x.service -f   # Debian
tail -f /opt/boa/logs/boa-x.log          # Alpine
```


## O orquestrador

O `agent-000`, chamado **manager**, é o único agente criado durante a instalação. É um agente
normal em todos os aspetos, exceto que não pode ser eliminado.

O padrão pensado: dê ao manager as ferramentas do kanban e um prompt que lhe
diga para dividir objetivos em cartões e atribuí-los a outros agentes pelo id.
Dê aos outros agentes `bash.run` e o que mais precisarem, e um prompt que lhes
diga para trabalharem nos cartões que lhes forem atribuídos.

Só funciona se os cartões do manager disserem o que significa «concluído». Um
cartão que não o diz é um desejo, e o agente que lhe pegar vai decidir por si
mesmo.

## O separador de ferramentas

**Definições → Ferramentas** mostra o que está instalado no servidor. Cada
família é um subseparador - Automação, Navegador, Canais, E-mail, Imagens,
Internet, Kanban, Memória, Sistema operativo, RAG, Competências - com o número de ferramentas que contém, e
cada ferramenta tem a sua caixa com os seus argumentos e o que significam. O
separador aberto fica no URL (`/settings/?tab=tools&family=mail`), por isso um
recarregamento ou um marcador mantêm-no.
As ligações antigas para `/tools/` redirecionam para aqui e mantêm a família
selecionada.

Uma ferramenta cuja família ninguém nomeou - um `.py` que alguém deixou em
`/opt/boa/tools/` - vai para **Outros**, com a sua família escrita na sua
própria caixa. Continua a ser uma ferramenta em tudo até à interface; só não
ganha um separador próprio, ou a fila cresceria com cada script avulso.

Que agente pode usar que ferramenta define-se no separador **Ferramentas** de
cada agente, não aqui.

## A documentação da API

**Documentação da API**, na barra lateral, lista todos os endpoints em
`/api/`, agrupados por área, com os seus parâmetros e o que respondem. É
gerada a partir da própria descrição OpenAPI desta instalação, por isso não
pode divergir do código: o `openapi.json`, com ligação no topo, é a mesma coisa
em forma de ficheiro que pode entregar a um gerador de clientes.

Está no idioma que escolheu em **Definições → Interface**, como o resto da
interface. A especificação em si fica em inglês: os nomes dos campos, os ids e
as mensagens de erro estão em inglês em todo este projeto, e um
`openapi.json` traduzido descreveria uma API que não existe.

Os corpos dos pedidos são mostrados como JSON colorido, da forma como um
editor os mostra: os nomes dos campos numa cor, os valores noutra, e as
chavetas e as vírgulas esbatidas porque são andaimes. As cores vêm do tema que
escolheu, e copiar um bloco continua a dar-lhe JSON válido.

A página também se pode ler sem iniciar sessão, sozinha, sem a barra lateral.
Descreve a forma da API, não nenhum dos seus dados.

## Trabalho que não exige que o agente pense

Há trabalho recorrente e mecânico: verificar um certificado, rodar um log,
recolher um número. Acordar um agente para isso custa tokens de cada vez, para
chegar a uma conclusão a que um script de shell chega sem custo nenhum.

Por isso, um agente pode escrever scripts para si próprio e agendá-los. Dê-lhe
as ferramentas de **Automação** e ele pode:

1. `script.write` — pôr um script de shell na sua própria pasta `scripts/`.
2. `cron.add` — executá-lo segundo um horário, no seu próprio crontab.
3. Ler os resultados na sua execução seguinte, e decidir o que significam.

O script corre como o utilizador Linux desse agente, com as mesmas permissões
que o agente tem, e **não custa token nenhum** - é um script de shell, não uma
chamada a um modelo. O que custa tokens é o agente ler a saída depois e decidir
o que fazer com ela. Corre num cgroup próprio, com os mesmos 2 GiB de memória e 1024 tarefas de uma execução, e é terminado se ainda estiver a correr ao fim de uma hora; uma linha que dispara enquanto ainda corre não inicia uma segunda cópia.

O que não pode fazer:

- Agendar outra coisa que não os seus próprios scripts. Um comando livre num
  crontab é algo que ninguém consegue rever depois.
- Correr com mais frequência do que de 5 em 5 minutos. Uma tarefa a cada
  minuto não é um horário.
- Tocar na linha que o acorda. Essa é sua, no separador **Cron** dele.

Vê as duas metades: os scripts na pasta pessoal dele, e as linhas que os
executam no separador Cron, ao lado das suas.

### Scripts

Cada agente tem a sua pasta `~/scripts/` em `/opt/boa/agents/<id>/scripts/`, incluindo agentes existentes após uma atualização. O prompt de sistema efetivo indica que deve guardar ali os scripts, procurar os existentes antes de criar novos e executá-los a partir dessa pasta.

Abra **Scripts** nas definições do agente. As linhas mostram apenas nomes, por ordem alfabética por predefinição. **Ordenar por** também ordena por tamanho ou última modificação, nos dois sentidos. **Mostrar código** expande o código; **Ocultar código** aparece junto ao nome e por baixo do código. Use **Editar código** e **Guardar script** para editar. Ocultar o código ou mudar a ordem mantém o rascunho.

Use **Novo script**, introduza nome e código e prima **Criar script**. Cada gravação aplica-se imediatamente, atribui o ficheiro ao agente e define permissões de execução `0700`; guardar não o executa. O código tem de ser texto UTF-8 até 64 KiB; nomes novos têm até 64 letras, números, pontos, hífenes ou sublinhados e começam com letra ou número. Criar nunca substitui um nome existente. Se o agente alterar o ficheiro durante a edição, a revisão antiga é recusada e o rascunho é mantido.

## Onde acaba o relatório de uma execução

Uma execução que inicia a partir da conversa responde-lhe aí. Uma execução
iniciada por um cartão cuja hora chegou responde no mesmo sítio. Uma execução
iniciada pelo **próprio crontab** do agente não responde em sítio nenhum em
particular - ninguém lhe perguntou nada - por isso:

- **Sempre no Histórico**, em **Últimas execuções**: o que cada execução disse,
  com o que custou. É aqui que deve procurar quando se pergunta o que um
  agente tem andado a fazer.
- **Também na conversa, quando vale a pena interrompê-lo**: a execução não
  terminou, ou alterou algo que iria ver - um cartão, uma mensagem num canal,
  uma caixa de correio. Uma execução que só observou coisas fica no Histórico.
  Caso contrário, um agente com um crontab de hora a hora publicaria vinte e quatro
  mensagens de «nada a relatar» por dia na conversa.

Essas mensagens indicam por cima que ninguém as pediu, e nunca são reenviadas
ao modelo, por isso não custam nada na sua mensagem seguinte.

**Uma execução que nunca começou também está no Histórico**, marcada como «não
chegou a começar». Carregue em **Executar agora** num agente cuja chave de API
ainda não está definida, ou enquanto o agente já está a correr, e a linha no
Histórico diz-lhe qual das duas situações foi. Antes, o ecrã dizia que a
execução tinha começado e nunca mais aparecia nada, porque a razão era escrita
num sítio que nada lê. Uma execução que não começou não conta para as
execuções do dia do agente, nem é contada como uma falha do agente: nada dela
correu.

## A barra de estado

A faixa ao longo do fundo de todas as páginas, que ocupa a largura toda da
janela, também por baixo da barra lateral, diz respeito à instalação como um
todo:

- **executor** e **API dos agentes**, a verde quando estão a correr. Se algum
  estiver vermelho, os agentes não vão correr e mais nada na interface lho vai
  dizer.
- **agentes**: quantos estão ligados de entre quantos existem.
- **quadro**: cartões em cada coluna.
- **tokens hoje**: tudo o que se gastou desde a meia-noite UTC, em todos os
  agentes, e quantas execuções foram precisas. Este é o número que mostra que
  um agente entrou em ciclo antes de a fatura o mostrar.

Na ponta direita da faixa, o símbolo do GitHub e o nome **nipegun** abrem o
repositório do projeto, <https://github.com/nipegun/bunch-of-aigents>, num novo
separador. A conta com que iniciou sessão não é mostrada: uma instalação só tem
uma, por isso mostrá-la não diz nada que não soubesse já.

## Em que idioma respondem os seus agentes

Escreva o prompt de cada agente no idioma em que pensa e ele responde nesse
idioma. Isso cobre a conversa. Não cobre uma execução iniciada pelo próprio
crontab do agente: ninguém lhe escreveu em idioma nenhum, e os prompts
incluídos estão em inglês - por isso uma instalação a funcionar em espanhol
recebia os seus relatórios agendados em inglês.

**Definições → Agentes → Idioma em que os agentes respondem** resolve isso para
todos os agentes de uma vez. Acrescenta uma linha ao prompt de sistema de cada
agente, escrita no idioma que pede, a dizer que se sobrepõe ao que quer que o
prompt diga sobre idiomas. Deixe-o no valor predefinido e nada muda: cada
agente responde no idioma do seu próprio prompt.

Fica guardado no servidor, ao contrário do idioma desta interface, que é uma
preferência do seu navegador. Uma execução acordada pelo cron não tem
navegador.

## Escrever prompts no seu próprio idioma

Escreva o prompt de sistema no idioma em que pensa. Nada no sistema está preso
ao inglês: o prompt, a memória, a conversa, os títulos dos cartões e as
mensagens entre os serviços são todos UTF-8 de uma ponta à outra, acentos
incluídos.

O prompt predefinido que um agente novo recebe está em inglês, e a sua última
regra diz ao agente que responda no idioma em que o seu prompt está escrito.
Reescreva-o todo no seu idioma e essa regra vai junto - o agente segue o prompt
que tem, não aquele com que começou.

Os prompts são guardados com linhas inteiras, sem quebra numa coluna fixa. A
caixa de texto quebra-as no ecrã para que se mantenham legíveis, sem pôr as
quebras de linha no ficheiro: uma regra que é uma frase continua a ser uma
linha, e editá-la não obriga a voltar a quebrar um parágrafo.

## Cópias de segurança e restauro

Tudo o que faz desta instalação a sua vive em `/opt/boa/` e nos utilizadores
Linux dos agentes. Um único comando reúne tudo num único arquivo:

```bash
./install-update-reinstall-debian.sh --backup
```

Escreve `/root/boa-backup-<date>.tar.gz`, só para o `root`, modo 0600, com os
serviços a correr - nada para. Passe um caminho para o escrever noutro sítio:
`--backup /mnt/usb/boa.tar.gz`. Lá dentro: as duas bases de dados, copiadas
através da própria API de cópia de segurança do SQLite para que nada que ainda
esteja num write-ahead log se perca; as chaves dos fornecedores, os segredos
dos canais e o segredo das sessões; os certificados; todos os agentes com a sua
pasta pessoal, os seus ficheiros protegidos, o seu utilizador Linux e o seu
crontab; as competências e as ferramentas escritas neste servidor; e o log da
instalação, por causa da palavra-passe que contém. Não está lá dentro: o
código, o ambiente Python, o navegador, e as duas escolhas próprias desta
máquina - o modo de portas e se tem navegador - para que um restauro nunca
importe as de outra máquina.

Um caminho seu tem de estar numa pasta que pertença a `root` e na qual nenhum outro utilizador possa escrever, e o mesmo vale para cada pasta acima: `/root` ou um disco montado pelo root, por exemplo, mas não `/tmp`. O arquivo é privado desde o primeiro byte e nunca é escrito por cima de um ficheiro existente nem através de uma ligação.

**Proteja o arquivo tanto como a própria máquina.** Contém todas as chaves de
API, todos os tokens dos canais e a palavra-passe de início de sessão.

Para restaurar, nesta máquina ou numa nova:

```bash
./install-update-reinstall-debian.sh --install       # só numa máquina nova
./install-update-reinstall-debian.sh --restore /root/boa-backup-<date>.tar.gz
```

Pede um YES, ou aceita `--yes`. Depois para os serviços, volta a criar os
utilizadores dos agentes com os mesmos nomes, e os mesmos ids quando estão
livres, substitui as bases de dados, as chaves, os certificados, os agentes, as
competências e as ferramentas pelos do arquivo, instala os crontabs e inicia
tudo. Inicie sessão com o e-mail e a palavra-passe da cópia de segurança: ambos
são acrescentados a `/opt/boa/logs/install.log` sob o título `Credentials of
the restored backup`, e o log inteiro da cópia de segurança fica guardado ao
lado como `install.log.restored-<date>`.

Um agente que esta máquina tinha e a cópia de segurança não tem mantém a sua
pasta pessoal no disco e desaparece da interface, porque a lista de agentes
está na base de dados restaurada. Em Alpine são as mesmas duas flags em
`install-update-reinstall-alpine.sh`.

### Desinstalar

Execute como `root`. `--purge` para todos os serviços do BoA, remove todas as unidades `boa-*` (serviços OpenRC no Alpine), apaga `/opt/boa/`, as contas `boa` e `agent-*` e os respetivos crontabs. Não faz perguntas nem cria uma cópia de segurança.

```bash
./install-update-reinstall-debian.sh --purge
./install-update-reinstall-debian.sh --uninstall
./install-update-reinstall-alpine.sh --purge
./install-update-reinstall-alpine.sh --uninstall
```

`--uninstall` cria primeiro `/root/boa-uninstall-<date>.<id>/` com permissões 0700. Contém o ficheiro portátil `backup.tar.gz`, uma cópia completa `installation.tar.gz` (incluindo código, dependências, modelos e registos), `system.tar.gz`, os registos das contas e os crontabs. Os ficheiros têm permissões 0600. Verifica os arquivos e o formato de restauro portátil antes de apagar qualquer coisa; uma falha na cópia interrompe a remoção.

Noutra máquina, execute `--install` e depois `--restore` com `backup.tar.gz`. Os outros ficheiros preservam o estado específico da máquina para recuperação; a importação portátil mantém o código e as portas do destino. Ambas as opções de remoção funcionam sem `--yes` e mantêm os nomes atuais dos instaladores.

## Serviços

| Serviço | Corre como | O que faz |
|---|---|---|
| `boa-proxy` | `boa` | HAProxy: termina o TLS no 11443, redireciona o 11080 e serve as portas web |
| `boa-web` | `boa` | A interface web e a API, num socket Unix por trás do proxy |
| `boa-exec` | `root` | Cria utilizadores, instala crontabs, inicia as execuções dos agentes |
| `boa-samba` | `root` | Autentica os utilizadores SMB e serve cada pasta samba/ como o utilizador do respetivo agente |
| `boa-agent-api` | `boa` | A porta que os agentes usam para chegar ao quadro e aos canais |
| `boa-buzzer` | `boa` | Vigia o quadro e acorda um agente quando chega a hora de um cartão |
| `boa-embeddings` | `boa` | Serve o modelo de vetorização local das bibliotecas de documentos, num socket Unix |
| `boa-rag` | `boa` | Gere a fila de indexação das bibliotecas de documentos |
| `boa-channel-telegram.service` | `boa` | Escuta no Telegram, para que possa responder a um agente a partir do seu telemóvel |
| `boa-channel-discord.service` | `boa` | O mesmo para um canal do Discord |
| `boa-channel-slack.service` | `boa` | O mesmo para um canal do Slack |
| `boa-channel-mattermost.service` | `boa` | O mesmo para um canal do Mattermost |
| `boa-channel-x.service` | `boa` | Conversas privadas do X |

```bash
systemctl status boa-proxy boa-web boa-exec boa-agent-api boa-buzzer \
                 boa-embeddings boa-rag \
                 boa-channel-telegram.service boa-channel-discord.service boa-channel-slack.service boa-channel-mattermost.service boa-channel-x.service boa-samba
journalctl -u boa-exec -f
```

As unidades dos canais em Debian usam `boa-channel-<channel>.service`.
Atualizar com `--update` para e desativa as unidades antigas dos canais antes
de ativar as novas.

Os mesmos processos correm em Alpine; os seus serviços de canais continuam a
ser `boa-telegram`, `boa-discord`, `boa-slack`, `boa-mattermost`, `boa-x`. São serviços OpenRC supervisionados com
`supervise-daemon`, e o que cada um imprime vai para o seu próprio ficheiro em
`/opt/boa/logs/`, rodado semanalmente:

```bash
rc-status
rc-service boa-exec status
tail -f /opt/boa/logs/boa-exec.log
```

## Segurança

As chaves partilhadas ficam restritas à origem HTTPS padrão do fornecedor. Gateways personalizados precisam de uma chave por agente. Respostas pendentes do Telegram e Discord são descartadas quando o bot ou destino muda; permanecem na conversa web. As ferramentas do navegador verificam os destinos WebSocket e bloqueiam service workers.

Restaure apenas backups confiáveis. A validação rejeita caminhos do código instalado e crontabs que não pertencem aos agentes; um manifesto não é uma assinatura. Definições antigas pertencentes ao agente precisam ser recuperadas de uma cópia confiável. Os instaladores aceitam `--commit` e `--source-sha256`; use um hash obtido independentemente para verificar a origem do código.

O desenho parte do princípio de que um agente acabará por fazer algo que não
pretendia, porque é um modelo de linguagem com uma shell.

- **Cada agente é um utilizador Linux separado**, e a sua pasta pessoal é
  `0700`. Os agentes não conseguem ler os ficheiros, os prompts nem as chaves
  de API uns dos outros.
- **`/opt/boa/agents/` é `0711`**, por isso nenhum agente consegue sequer
  listar que outros agentes existem.
- **Nenhum agente corre como root, nunca.** Só o `boa-exec` o faz, e aceita uma
  lista fechada de operações através de um socket Unix. Entre elas não há
  nenhum «executa este comando».
- **Uma execução é limitada pelo kernel, não só pelos seus limites.** Nenhum agente pode ter mais de 1024 processos e threads, pelo que uma fork bomb para nesse número; cada execução vive num cgroup próprio com 2 GiB de memória - um scope do systemd no Debian, um cgroup que o executor prepara no Alpine -, que além disso termina o que a execução deixou a correr ao acabar. Execuções iniciadas pelo cron, scripts agendados e a indexação das bibliotecas têm os mesmos limites, e os agentes não podem escrever linhas de cron próprias.
- **Os agentes nunca veem as credenciais dos canais.** Um token de bot não é
  uma mensagem: é autoridade permanente para enviar tudo o que esse bot pode
  enviar. Os agentes pedem à API dos agentes que envie, e ela envia.
- **Os agentes só tocam nos seus próprios cartões.** Veja
  [O quadro kanban](#o-quadro-kanban).
- **`web.fetch` recusa endereços privados**, verificando o IP resolvido e
  voltando a verificar em cada redirecionamento, para que não se possa mandar
  um agente que lê uma página hostil chamar a sua rede interna.
- **Um servidor lento não consegue reter uma execução.** `web.fetch` e `rss.fetch` param no seu `timeout_seconds`, contado sobre a obtenção inteira, ou no fim da execução se este chegar antes, por mais devagar que o servidor envie a resposta.
- **Um agente não consegue repor os seus próprios limites.** O BoA conta as execuções por dia na sua própria base de dados, não no histórico do agente, e o bloqueio que garante uma única execução de um agente de cada vez pertence ao root. Nada no home do agente desfaz qualquer um deles.
- **Os registos são do root.** `/opt/boa/logs/` pertence a `root`, grupo `boa`, modo 0750. Os serviços escrevem aí nos próprios ficheiros e não conseguem substituir `install.log` nem nenhum outro ficheiro que o root escreva.
- **Uma publicação pública precisa de si.** Um agente com `x.post` apenas pede; a publicação sai quando responde ao código dele por mensagem direta a partir da conta destinatária.
- **No Alpine, só o `boa-proxy` escuta em 80 e 443.** No modo `direct`, o `supervise-daemon` dá a capability apenas a esse serviço; já não está no binário do haproxy, onde qualquer utilizador a podia usar.

Foi pensado para uma LAN e não deve ser exposto à Internet.

## Quando algo não funciona

**Escolhi `--ports direct` e o HAProxy da máquina desapareceu.** Não
desapareceu, foi retirado de serviço: parado, fora de todos os runlevels em
Alpine, desativado e mascarado em Debian, e o seu `/etc/haproxy/haproxy.cfg`
apagado se tinha sido o instalador a escrevê-lo, ou guardado como
`haproxy.cfg.before-boa.<date>` se tinha sido você. Neste modo, a própria
aplicação ocupa o 80 e o 443, e qualquer outra coisa que tenha essas portas
impede-a de sequer arrancar - um proxy deixado ativado ficaria com elas no
arranque seguinte, antes de a aplicação chegar a correr. O pacote `haproxy`
continua instalado de propósito: o `boa-proxy` é o `/usr/sbin/haproxy`, e neste
modo é ele que serve o 80 e o 443.

Para voltar atrás, execute o instalador com `--update --ports proxied`: tira a
máscara à unidade, volta a escrever a configuração da máquina e inicia-a. O seu
ficheiro antigo, se havia um, continua ao lado, com o seu nome `before-boa`.

**O `boa-proxy` reinicia uma e outra vez e nada escuta no 11443.** Leia
`/opt/boa/logs/boa-proxy.log`. Se disser `Cannot raise FD limit to 4131`, o
limite rígido de descritores de ficheiro desta máquina é inferior ao que o
proxy pediu - normalmente, um contentor pequeno. Uma instalação feita antes de
isto ser corrigido ainda tem `maxconn 2048` em `/opt/boa/config/haproxy.cfg`.
Executar o instalador com `--update` reescreve o ficheiro; para o corrigir na
hora:

```bash
sed -i 's/^  maxconn 2048$/  fd-hard-limit 4000/' /opt/boa/config/haproxy.cfg
rc-service boa-proxy restart        # systemctl restart boa-proxy em Debian
```

O HAProxy dimensiona-se então a partir dos descritores que pode realmente ter,
o que, com um limite rígido de 4096, dá cerca de 1987 ligações - muito mais do
que isto alguma vez precisa.

**O instalador termina com «Everything is in place but the application does
not answer».** A instalação está feita e uma página nunca chegou a voltar. O
log já contém a razão:

```bash
sed -n '/Why it did not answer/,$p' /opt/boa/logs/install.log
```

Esse bloco é o estado da máquina naquele momento: o que o curl fez do pedido,
se há alguma coisa a escutar na porta, o estado dos treze serviços e as últimas
linhas do que o proxy e a aplicação web imprimiram. `000` não é um código HTTP -
é o curl a dizer que nunca recebeu nenhum. Um serviço que se declara `started`
ao lado de `nothing is listening on port 11443` é um processo que morre e é
reiniciado a cada poucos segundos, e o seu próprio log, umas linhas mais
abaixo, diz porquê.

Uma atualização que falhou aqui já repôs a versão anterior e está a executá-la.
Uma primeira instalação não tem para onde voltar, por isso deixa tudo no
sítio: corrija o que o bloco indicar e execute o instalador outra vez com
`--update`.

**O instalador para com «systemd is not running».** Está a recusar-se a
instalar numa máquina onde o systemd não é o PID 1, porque todos os serviços
que escreve são unidades systemd e não haveria nada que os iniciasse. Um Debian
normal serve; um contentor não, a não ser que tenha sido criado para correr o
systemd:

```bash
apt-get install -y systemd systemd-sysv dbus dbus-user-session
```

e depois volte a criar o contentor com `/sbin/init` como comando - um
contentor que já está a correr não pode mudar o seu PID 1. Em Alpine isto não
acontece: esse instalador acrescenta ele próprio o OpenRC quando a máquina não
o tem.

**Não acontece nada quando carrego em Executar agora.** Olhe para os dois
pontos no fundo da barra lateral. Se o `executor` estiver vermelho:

```bash
systemctl status boa-exec
journalctl -u boa-exec -n 50
```


**O navegador mostra 503 e os serviços estão todos a correr.** O HAProxy da
máquina marcou o backend como em baixo. Quase sempre, a causa é `option
ssl-hello-chk` nesse backend: o seu ClientHello é anterior ao TLS 1.2 e a
aplicação exige-o. Retire essa linha e recarregue o HAProxy.

**Um agente corre mas não faz nada.** Veja o seu painel Histórico. Depois
execute-o à mão e acompanhe:

```bash
runuser -u agent-001 -- /opt/boa/venv/bin/python3 \
  /opt/boa/webapp/backend/core/runner.py --agent-id 001
```

Acrescente `--dry-run` para ver o que carregaria — fornecedor, ferramentas,
tetos — sem chamar o modelo.

**Diz que não consegue chegar ao modelo.** Para fornecedores auto-alojados,
verifique que o servidor está a funcionar e que o URL base está certo. Para os
da nuvem, verifique que o ficheiro da chave existe na pasta pessoal do agente e
que pertence a esse agente.

**Diz que uma ferramenta não está disponível para ele.** A ferramenta não está
marcada na página desse agente. O prompt não consegue contornar isso, e é
precisamente essa a ideia.

**Os cartões deixaram de aparecer.** Ou a caixa de seleção do kanban está
desmarcada para esse agente, ou a `agent API` («API dos agentes») está vermelha
no fundo da barra lateral:

```bash
systemctl status boa-agent-api
```

**Quero ver tudo o que um agente fez.** O seu diário está na sua própria pasta
pessoal:

```bash
cat /opt/boa/agents/001/runs.jsonl
```

Um objeto JSON por linha: quando correu, o que gastou, se terminou.

## Licença

PolyForm Noncommercial License 1.0.0. Pode usar, modificar e partilhar o BoA
para qualquer fim não comercial: uso pessoal, estudo, investigação, projetos
de passatempo e a utilização por instituições de solidariedade,
estabelecimentos de ensino, organismos públicos de investigação e instituições
governamentais. Qualquer utilização comercial exige uma licença separada.
Veja [LICENSE](../LICENSE).
