# Manual

Como usar o Bunch of AIgents no dia a dia.

## Sumário

1. [O que ele faz](#o-que-ele-faz)
1. [Onde ele roda](#onde-ele-roda)
1. [Se você usa Alpine](#se-você-usa-alpine)
1. [Instalação](#instalação)
1. [Atualização e reinstalação](#atualização-e-reinstalação)
1. [Como abrir](#como-abrir)
1. [Como entrar](#como-entrar)
1. [Primeiros passos](#primeiros-passos)
2. [A interface](#a-interface)
3. [De onde vem um agente novo](#de-onde-vem-um-agente-novo)
3. [Criando seu primeiro agente](#criando-seu-primeiro-agente)
4. [Conversando com um agente](#conversando-com-um-agente)
5. [Configurações do agente](#configurações-do-agente)
5. [Exportando um agente](#exportando-um-agente)
5. [Pastas compartilhadas do Samba](#pastas-compartilhadas-do-samba)
6. [Dando um modelo a um agente](#dando-um-modelo-a-um-agente)
5. [Escrevendo um prompt de sistema](#escrevendo-um-prompt-de-sistema)
6. [Escolhendo as ferramentas](#escolhendo-as-ferramentas)
7. [Dando uma habilidade a um agente](#dando-uma-habilidade-a-um-agente)
8. [Dando um navegador a um agente](#dando-um-navegador-a-um-agente)
9. [Tetos de gasto](#tetos-de-gasto)
8. [Agendando um agente](#agendando-um-agente)
9. [O quadro kanban](#o-quadro-kanban)
10. [Temas](#temas)
11. [Canais](#canais)
12. [O orquestrador](#o-orquestrador)
13. [Backup e restauração](#backup-e-restauração)
13. [Serviços](#serviços)
13. [Segurança](#segurança)
14. [Quando algo não funciona](#quando-algo-não-funciona)
1. [Transcrição de áudio](#transcrição-de-áudio)
1. [Licença](#licença)

---

- [Bibliotecas locais de documentos (RAG)](#bibliotecas-locais-de-documentos-rag)

## O que ele faz

- **Um agente é um usuário Linux.** Criar um agente na interface web cria
  `agent-007` no sistema, com uma pasta pessoal que nenhum outro agente
  consegue ler. Esse é o isolamento: o do kernel, não uma sandbox escrita em
  Python.
- **Os agentes rodam no próprio horário.** Cada um tem o seu próprio crontab,
  que pertence ao seu próprio usuário e é executado por ele, então um agente
  acorda, faz o trabalho e termina.
- **Você conversa com eles.** Clicar em um agente abre uma conversa: peça a ele
  que faça alguma coisa e ele usa as ferramentas dele e responde quando
  termina. A conversa fica guardada.
- **Uma conversa por agente, não uma por pessoa.** Um cartão que chega ao seu
  horário é publicado nessa mesma conversa quando a execução começa, e a
  resposta aparece embaixo dele, então a conversa de um agente reúne tudo o que
  pediram a ele — você ou outro agente — e o que ele fez a respeito.
- **Eles compartilham um quadro kanban.** Os agentes adicionam cartões, movem
  esses cartões e veem o trabalho uns dos outros. Você acompanha em `/kanban/`
  em vez de ler logs.
- **Qualquer modelo, na nuvem ou auto-hospedado.** Vinte e cinco provedores vêm
  incluídos — Anthropic, OpenAI, Google, DeepSeek, Mistral, Qwen, xAI e os
  demais; os roteadores que ficam na frente deles, OpenRouter, Groq, Together,
  Vercel e outros; e Ollama, llama.cpp e vLLM no seu próprio hardware. Cada
  agente escolhe o seu, com um modelo reserva para quando aquele estiver fora
  do ar.
- **Tetos de gasto que realmente o detêm.** Tokens, passos, segundos e
  execuções por dia, por agente. Sem isso, um agente sem supervisão numa API
  paga é uma fatura em aberto.
- **Memória configurável.** Escolha o limite de memória de cada agente nas
  configurações dele, de 1.000 a 1.000.000 caracteres (8.000 por padrão).
  Gravações grandes demais são rejeitadas sem cortar o texto nem substituir a
  memória salva.
- **Uma biblioteca de documentos por agente.** Envie livros em PDF, EPUB, TXT
  ou Markdown. A extração, o OCR e a vetorização ficam locais; os agentes
  recuperam os trechos relevantes e citam as fontes. Configure em **RAG**. O
  modelo de vetorização é o EmbeddingGemma 300M por padrão; uma máquina com
  processador e memória de sobra pode trocar para o Qwen3-Embedding 0.6B em
  **Configurações → RAG**.
- **Agentes que você pode levar para outro lugar.** A aba **Exportar** de um
  agente baixa esse agente como um `.zip` — opcionalmente com a memória, o
  modelo, a biblioteca e os arquivos da pasta pessoal dele, nunca com uma chave
  — e o **+** o importa aqui ou em outra instalação. Agentes prontos vêm do
  [repositório de modelos](https://github.com/nipegun/bunch-of-aigents-templates).
- **Ferramentas que você pode ampliar.** Cada ferramenta é um arquivo `.py` em
  `/opt/boa/tools/`. Coloque um novo ali e ele aparece em **Configurações →
  Ferramentas**, agrupado em subabas como Automação e Navegador.
- **Habilidades que eles compartilham.** Um procedimento escrito uma vez em
  `/opt/boa/skills/` pode ser dado a quantos agentes você quiser. O que um
  agente aprende sozinho morre na memória dele; uma habilidade, não.
- **Um navegador para cada um, com as próprias sessões.** Um agente pode entrar
  num site, preencher um formulário e clicar — não apenas ler uma página — e os
  cookies dele ficam na pasta pessoal dele, com permissão 0700, então o login de
  um agente não é o login de todos.
- **Responda a eles pelo Telegram ou pelo Discord.** Escolha um agente com
  /agents, ou responda a uma mensagem que um deles enviou a você, e o que você
  escrever chega a ele, inicia uma execução e volta respondido no seu celular.
  A troca inteira também fica na conversa desse agente na interface web, as
  duas metades, então uma única tela continua mostrando tudo.
- **Áudio do Telegram.** **Configurações → Áudio** seleciona o whisper.cpp
  local ou OpenAI, Groq, Mistral, Together AI, Hugging Face ou Cloudflare,
  usando uma chave de API já salva. Todos os 30 modelos nativos são oferecidos,
  com download sob demanda. Uma resposta de voz chega ao agente de origem como
  texto e aparece na conversa web, com reprodução do áudio opcional.
- **Uma pasta compartilhada para cada um.** A pasta `samba/` de cada agente é
  um compartilhamento SMB com o nome do usuário Linux dele, então você pode
  colocar arquivos ali a partir do Windows, do Linux ou do macOS.
- **Quinze idiomas.** Alemão, inglês (Reino Unido e EUA), espanhol (Espanha e
  Argentina), francês, hebraico, hindi, italiano, japonês, coreano, português (Brasil e
  Portugal), russo e chinês simplificado. A interface, a linha que diz aos seus
  agentes em que idioma responder e o que os dois bots dizem.

Ele foi feito para uma pessoa que o roda na sua própria rede local.

## Onde ele roda

Dois sistemas, e em cada um deles o sistema de init faz parte do requisito, não
é um detalhe:

- **Debian com systemd como PID 1.** Os dez serviços são unidades do systemd.
  Num Debian que inicializa com qualquer outra coisa não há nada para
  iniciá-los, então o instalador verifica `systemctl is-system-running` antes de
  mexer na máquina e se recusa a continuar se o systemd não estiver lá. Não
  tente numa máquina assim: a resposta não vai mudar.
- **Alpine com OpenRC.** Os dez serviços são scripts do OpenRC supervisionados
  com `supervise-daemon`. Nada precisa ser instalado antes — o próprio
  instalador adiciona o `openrc` quando a máquina não tem.

Confira no Debian com `systemctl is-system-running`: ele tem de responder
(`running`, `degraded`, `starting`), e não imprimir “System has not been booted
with systemd as init system (PID 1)”. Um contêiner precisa ter `systemd
systemd-sysv dbus` instalados e `/sbin/init` como comando.

Além do sistema de init, ele precisa de:

- Acesso de `root`. Nenhum dos instaladores usa `sudo`, e nenhum precisa dele.
- Cerca de 500 MB de disco para a aplicação e o ambiente Python dela.
- `haproxy`, instalado pelo instalador. Ele faz a terminação do TLS, porque o
  cabeçalho PROXY que o HAProxy da máquina envia chega antes do handshake TLS e
  só um proxy consegue lê-lo nesse ponto.
- Um modelo com quem conversar: ou uma chave de API de um provedor na nuvem, ou
  Ollama, llama.cpp ou vLLM rodando em algum lugar que você consiga alcançar.

O instalador também compila o **whisper.cpp v1.9.4** em `/opt/boa/whisper/`,
instala o FFmpeg e baixa o modelo multilíngue `base` (cerca de 142 MiB a mais).
A compilação, as dependências do sistema e o navegador precisam de espaço em
disco adicional. Se faltar o interpretador Python, ele é instalado antes de a
versão ser verificada.

Todo o resto deste manual é igual nos dois.

## Se você usa Alpine

Todo comando deste manual que cita `systemctl` ou `journalctl` é o do Debian. A
aplicação é a mesma no Alpine; o que muda é o sistema de init e o lugar para
onde vão os logs:

| No Debian | No Alpine |
|---|---|
| `systemctl status boa-web` | `rc-service boa-web status`, ou `rc-status` para os dez |
| `systemctl restart boa-web` | `rc-service boa-web restart` |
| `journalctl -u boa-web -f` | `tail -f /opt/boa/logs/boa-web.log` |
| `install-update-reinstall-debian.sh` | `install-update-reinstall-alpine.sh` |

Um recurso falta ali e não vai voltar: não há navegador, porque o Playwright
não publica nenhuma build para musl. As ferramentas de navegador continuam na
lista e avisam disso quando um agente chama uma delas.

---

## Instalação

Um instalador por distribuição, e os dois aceitam as mesmas flags. Execute-o
como `root`.

### No Debian

> **O systemd tem de estar rodando na máquina.** Execute primeiro
> `systemctl is-system-running`: se ele imprimir “System has not been booted
> with systemd as init system (PID 1). Can't operate.”, pare aqui. Todo serviço
> que isto instala é uma unidade do systemd, então não haveria nada para
> iniciá-los, e o instalador se recusa por esse motivo em vez de deixar você
> com uma instalação que não serve nada.

```bash
curl -fsSL https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-debian.sh \
  | bash -s -- --install --email you@example.com
```

Se o `curl` não estiver instalado — um Debian mínimo muitas vezes não tem nem
ele nem o `wget` —, instale-o primeiro, senão a linha acima imprime
`curl: command not found` e para:

```bash
apt-get update && apt-get install -y curl
```

Ou baixe o instalador primeiro e leia-o antes de executá-lo, que é o hábito
mais saudável:

```bash
wget https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-debian.sh
less install-update-reinstall-debian.sh
chmod +x install-update-reinstall-debian.sh
./install-update-reinstall-debian.sh --install --email you@example.com
```

### No Alpine Linux

As mesmas flags, outro script: ele cria serviços do OpenRC em vez de unidades
do systemd. Uma linha, com `wget` e canalizada para o `sh`, porque um Alpine
recém-instalado não tem nem `curl` nem bash, e esses dois são os do BusyBox:

```bash
wget -qO- https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-alpine.sh \
  | sh -s -- --install --email you@example.com
```

Use `curl -fsSL` no lugar de `wget -qO-` numa máquina que o tenha — e preste
atenção a essa linha se fizer isso, porque um `curl: not found` canalizado para
o `sh` imprime o erro e depois **termina com sucesso**, sem ter instalado nada.

O instalador é shell POSIX, e não bash, pelo mesmo motivo do `wget`: um Alpine
recém-instalado não tem bash para o `| bash -s --` alcançar. Ele instala o bash
no caminho — todo agente recebe uma shell bash —, então numa máquina que já o
tenha, `| bash -s --` funciona igualmente bem.

Ou baixe-o primeiro e leia-o antes de executá-lo:

```bash
wget https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-alpine.sh
less install-update-reinstall-alpine.sh
chmod +x install-update-reinstall-alpine.sh
./install-update-reinstall-alpine.sh --install --email you@example.com
```

Duas coisas são diferentes depois que ele está no ar, e as duas vêm do
sistema, não de uma decisão:

- **Sem navegador.** O Playwright não publica nenhuma build para musl e o
  Alpine não empacota nenhuma, então `browser.open` e as demais avisam disso
  quando um agente chama uma delas. `web.fetch` e `rss.fetch` funcionam como em
  qualquer lugar.
- **`rc-status` em vez de `systemctl status`**, e `rc-service boa-web
  restart` no lugar de `systemctl restart boa-web`. Veja
  [Se você usa Alpine](#se-você-usa-alpine).

No Alpine, os serviços liberam a saída SSH do instalador, então o instalador
devolve o controle da sessão quando termina.

### O que o instalador faz

1. Cria o usuário de sistema `boa` e a árvore em `/opt/boa/`.
2. Instala as dependências Python em `/opt/boa/venv/`.
3. Gera um certificado TLS autoassinado, a menos que você tenha deixado um
   `fullchain.pem` e um `privkey.pem` seus em `/opt/boa/certificates/`.
4. Pergunta se a aplicação deve ser servida em 11080/11443 atrás de um HAProxy
   em 80 e 443, ou diretamente em 80 e 443. Passe `--ports proxied|direct` para
   responder de antemão. A resposta fica guardada, então o `--update` nunca
   pergunta de novo nem a muda sem avisar. Escolher `direct` aposenta o HAProxy
   da própria máquina — parado, fora de todos os runlevels ou mascarado, e com o
   `/etc/haproxy/haproxy.cfg` dele apagado se foi este instalador que o
   escreveu, ou guardado como `haproxy.cfg.before-boa.<date>` se foi outra
   pessoa — para que nada ocupe o 80 e o 443 no próximo boot. O pacote haproxy
   em si continua: o proxy da própria aplicação é esse binário.
5. Cria um agente: `manager`, o orquestrador. Todo o resto é um agente vazio,
   um `.zip` exportado de um agente ou um modelo do
   [repositório de modelos](https://github.com/nipegun/bunch-of-aigents-templates) —
   `web-navigator`, `os-watcher`, `mail-watcher` e outros —, escolhido quando
   você aperta **+**. O agente vazio é a primeira opção oferecida.
6. Instala e inicia os serviços listados em [Serviços](#serviços): unidades do
   systemd no Debian, serviços do OpenRC supervisionados com
   `supervise-daemon` no Alpine.
7. Grava o que fez, e a sua senha de login, em `/opt/boa/logs/install.log`
   (root, modo 0600).
8. Pede à aplicação a página de login antes de dizer que terminou. Se a página
   não vier, ele avisa, grava nesse mesmo log como a máquina estava naquele
   momento — o que o curl entendeu da requisição, se há algo escutando na
   porta, o estado dos serviços e as últimas linhas do que eles imprimiram — e
   indica o log em vez de anunciar sucesso. Um `--update` também restaura
   antes a versão anterior.

### Onde está a senha

O endereço de e-mail que você informa é o único login. A senha é gerada para
você; leia-a com:

```bash
cat /opt/boa/logs/install.log
```

Esse único arquivo é as duas coisas: o log completo da instalação e as
credenciais que ela gerou. A página de login cita esse arquivo, para que
ninguém precise lembrar onde ele está.

## Atualização e reinstalação

```bash
./install-update-reinstall-debian.sh --update      # mantém os agentes e os dados
./install-update-reinstall-debian.sh --reinstall   # apaga tudo antes
```

No Alpine são as mesmas duas flags, no outro script:

```bash
./install-update-reinstall-alpine.sh --update
./install-update-reinstall-alpine.sh --reinstall
```

O `--reinstall` apaga todos os agentes, pastas pessoais, crontabs e o quadro
kanban. Ele pede confirmação, a menos que você passe `--yes`.

Uma instalação que morreu no meio do caminho — um download que falhou, uma
rede que caiu — é concluída executando `--install` de novo: ela retoma de onde
parou, e o `--update` avisa se encontrar uma assim.

As outras duas flags, `--backup` e `--restore`, são explicadas em
[Backup e restauração](#backup-e-restauração).

## Como abrir

No modo padrão `proxied`, o HAProxy da própria aplicação escuta em
`127.0.0.1:11443` (HTTPS) e `127.0.0.1:11080` (HTTP, que redireciona). Essas
portas não são acessíveis de fora do servidor: quem atende a rede local é o
HAProxy da própria máquina, que encaminha para a 11443 com `send-proxy-v2`
para que o endereço real do cliente seja preservado. No modo `direct`, a
aplicação escuta ela mesma em 80 e 443, sem nada na frente.

Com isso pronto, abra:

```
https://your-server/
```

O certificado é autoassinado, a menos que você tenha deixado certificados seus
em `/opt/boa/certificates/`, então o navegador vai mostrar um aviso uma vez.

### Como deve ser o HAProxy da máquina

O backend que aponta para esta aplicação precisa de duas coisas:

```
backend https-out
  mode tcp
  server srv-https-out 127.0.0.1:11443 check port 11080 send-proxy
```

- **`send-proxy`**, para que o endereço real do cliente chegue à aplicação.
  Sem ele, toda requisição parece vir de 127.0.0.1 e o limite de tentativas de
  login deixa de ser por endereço.
- **`check port 11080`**, para que a verificação de saúde bata na porta HTTP
  simples e não na de TLS. Uma verificação TCP contra a porta TLS conecta e
  desliga sem handshake, e o HAProxy da própria aplicação registra cada uma
  como uma falha de handshake SSL: uma linha a cada dois segundos, para sempre.
  As duas portas pertencem a um único processo, então se uma responde, a outra
  está lá. Não adicione `check-send-proxy`: a 11080 não aceita o protocolo
  PROXY.
- **Sem `option ssl-hello-chk`.** O ClientHello dele é anterior ao TLS 1.2,
  então um backend que exige TLS 1.2 — este, e qualquer Apache ou nginx
  moderno — falha na verificação e fica marcado como fora do ar para sempre. O
  sintoma é um 503 de um serviço que está funcionando perfeitamente. Um `check`
  simples já verifica se a porta responde.

## Como entrar

Abra `https://your-server/` e entre com o endereço de e-mail que você informou
ao instalador e a senha que ele gerou. Se você não a tiver:

```bash
cat /opt/boa/logs/install.log
```

Esse arquivo é o log inteiro da instalação, com as credenciais no final, e a
página de login o cita exatamente para este momento.

**Sair** abre uma confirmação no centro da tela. Confirme para encerrar a
sessão, ou escolha **Cancelar** ou aperte Esc para continuar conectado.

Há uma única conta. Mude a senha dela em **Configurações → Conta**. Para
mudá-la, também é pedida a senha atual: é isso que faz da mudança algo feito
por você, e não por quem encontrar o navegador aberto. Ela também encerra todas
as outras sessões, em todos os outros dispositivos, de uma vez — que é
justamente o motivo de mudá-la quando você acha que outra pessoa tem uma.

Na primeira vez que você abre a aplicação depois de uma atualização, ela pede
que você entre de novo. As sessões de antes da atualização não guardam
registro de quando foram concedidas, e a resposta para “não sei dizer” é
perguntar.

Depois de dez tentativas falhas a partir do mesmo endereço, o login fica
fechado por quinze minutos, inclusive para senhas corretas.

## Primeiros passos

1. Entre com o seu e-mail e a senha gerada.
2. Se o agente for usar um provedor na nuvem, salve antes a chave dele em
   **Configurações → Chaves de API**: a lista de provedores só oferece os
   provedores na nuvem que têm uma chave (veja [Chaves de API](#chaves-de-api)).
3. Aperte **+** na barra lateral para criar o seu primeiro agente.
4. Escolha o provedor e o modelo dele. Para o Ollama na mesma máquina, os
   valores padrão já estão certos. Para cobrar só este agente numa conta
   diferente, dê a ele uma chave própria (veja
   [Dando um modelo a um agente](#dando-um-modelo-a-um-agente)).
5. Escreva o prompt de sistema dele: para que ele serve e o que significa
   “concluído”.
6. Dê a ele as ferramentas de que precisa. Comece pelas do kanban.
7. Aperte **Executar agora** e acompanhe o quadro.
8. Quando ele fizer o que você quer, dê a ele um agendamento.

## A interface

O logotipo azul e circular mostra três agentes robóticos com painéis faciais
claros, viseiras escuras e olhos azuis, vestindo ternos pretos, camisas brancas
e gravatas escuras. Eles aparecem da cintura para cima, com um agente central
maior. O logotipo aparece na página de login, na barra lateral e na aba do
navegador.

A barra lateral à esquerda lista os seus agentes. Cada um mostra o id, o nome,
quantas vezes rodou e quantos tokens gastou. Todas as caixas têm a mesma
altura, então um nome longo é cortado com reticências — passe o mouse sobre ele
para ler o nome inteiro. O quadrado em volta do
id tem um contorno verde quando o agente está ligado e vermelho quando não está.

**Quando um agente está trabalhando, um segmento aceso percorre esse anel verde
no sentido horário.** Ele avisa
que o agente está no meio de uma execução neste momento — não o que ele está
fazendo, só que está fazendo alguma coisa. Ele começa a girar assim que você
envia uma mensagem na conversa ou aperta **Executar agora**, e para quando a
execução termina, quer ela tenha vindo de você, do agendamento ou de um cartão
que chegou ao seu horário. O anel é verificado a cada poucos segundos, então
pode ficar um instante atrasado.

Na parte de baixo da barra lateral, dois pontos mostram se os serviços em
segundo plano estão rodando. Se algum deles estiver vermelho, os agentes não
vão rodar — veja [Quando algo não funciona](#quando-algo-não-funciona).

O botão **+** cria um agente.

## O agente com que você começa

A instalação cria exatamente um.

**`manager` (agent-000)** coordena os outros. Ele divide objetivos em cartões e
os distribui. Ele vem ligado desde o início.

É de propósito que seja só isso: uma instalação que chega com agentes que
ninguém pediu é uma instalação que começa com coisas para desligar. Todo o
resto é um **modelo** do repositório de modelos, ou um `.zip` que alguém
exportou, oferecidos quando você aperta **+**.

## De onde vem um agente novo

Aperte **+** e você será perguntado de onde começar:

| Opção | O que faz |
|---|---|
| **Agente vazio** | Sem prompt, sem ferramentas, sem agendamento. Escreva você mesmo. |
| **Importar de um arquivo .zip** | Um agente exportado pela aba **Exportar**, aqui ou em outra instalação. |
| **Importar de um modelo do GitHub** | Um dos agentes do repositório de modelos, escolhido numa lista. |

O **agente vazio** encabeça a lista, porque é a única resposta que está sempre
certa, e todas as outras são um atalho para ela.

### Modelos do GitHub

Os modelos ficam num repositório próprio,
[bunch-of-aigents-templates](https://github.com/nipegun/bunch-of-aigents-templates),
uma pasta para cada um, então um modelo novo chega à sua instalação sem que
você precise atualizá-la. Quando você escolhe **Importar de um modelo do
GitHub**, o servidor baixa esse repositório (um `.tar.gz`, guardado por cinco
minutos) e lista os agentes dele em ordem alfabética, cada um com a descrição
no seu idioma, as famílias de ferramentas com que vem, com que frequência
acorda e se ativa a biblioteca. Uma ferramenta que esta instalação não tem fica
de fora, e a lista avisa. Um modelo que não passa nas verificações não é
oferecido, e uma linha diz quantos ficaram de fora.

Estes são os modelos que o repositório tem hoje:

| Modelo | O que faz |
|---|---|
| **backup-watcher** | Verifica se os seus backups rodaram, se são recentes e se não são suspeitamente pequenos. |
| **cert-watcher** | Avisa quando um certificado TLS está para expirar, enquanto ainda há tempo. |
| **disk-cleaner** | Descobre o que está enchendo o disco e diz o que poderia sair. Propõe; nunca apaga. |
| **kanban-watcher** | Lê o quadro toda manhã de dia útil e escreve um resumo curto. |
| **log-watcher** | Lê os logs para os quais você o direciona e relata o que é novo ou passou a ser frequente. |
| **mail-watcher** | Vigia uma caixa de correio e age sobre o que chega, seguindo as regras que você escreve no prompt dele. |
| **news-watcher** | Lê os feeds RSS que você lista no prompt dele e relata o que corresponde às suas regras. |
| **os-watcher** | Vigia esta máquina: disco, memória, swap, carga e se os serviços estão no ar. |
| **rag-consultant** | Responde a perguntas com os documentos da biblioteca RAG dele, citando o trecho que sustenta cada afirmação, e avisa quando os documentos não cobrem algo. |
| **site-watcher** | Verifica se os sites que você lista respondem, respondem rápido e ainda dizem o que diziam. |
| **web-navigator** | Conduz o próprio navegador para fazer o que você pede num site: pesquisar, entrar, preencher um formulário, navegar pelas páginas e relatar o que encontrou. |

`web-navigator` e `rag-consultant` não têm agendamento: eles trabalham quando
você pede, e o pedido é a tarefa. O `web-navigator` também é o que mostra para
que o navegador está
instalado — ele entra em sites, clica e preenche formulários, enquanto os
outros leem páginas. Ele não digita uma senha, não compra nada e não aperta um
botão de envio: chega a esse passo e para, dizendo qual botão concluiria o
trabalho.

O `rag-consultant` responde a partir da própria biblioteca de documentos, e é o
único modelo que chega com essa biblioteca ativada: as ferramentas dele ficam
retidas enquanto a biblioteca está desativada. Antes que ele sirva para alguma
coisa, envie documentos na aba **RAG** dele (veja
[Bibliotecas locais de documentos](#bibliotecas-locais-de-documentos-rag)) e
escolha um modelo. Cada afirmação nas respostas dele tem um link para a página
do documento de onde ela vem; quando os documentos não cobrem algo, ele avisa
em vez de preencher a lacuna. O teto de tokens dele (40.000 por execução) é
maior que o dos outros, porque os trechos que ele lê contam para esse teto.

Todo modelo diz, antes de você escolhê-lo, com quais famílias de ferramentas
vem e com que frequência acorda. Um modelo é tanto um conjunto de permissões
quanto um prompt: “vigia uma caixa de correio” não diz a você que ele chega
podendo apagar e-mails.

Todo modelo chega **desligado e sem modelo de linguagem**: escolher um dá a
você o prompt, as ferramentas e um agendamento sugerido, e depois ele espera
que você escolha um provedor e o ligue.

Eles são pontos de partida. Mude o prompt, as ferramentas, o agendamento —
tudo — e vários deles dizem no próprio prompt o que precisam que você preencha
antes de servirem para alguma coisa, em vez de falhar às três da manhã.

**Configurações → Agentes** diz de qual repositório e de qual branch vem a
lista: por padrão, o do próprio projeto, ou um fork, ou um seu com a mesma
estrutura. Uma máquina sem saída para o GitHub pode usar um caminho `file://`
contendo `archive/refs/heads/<branch>.tar.gz`, a mesma estrutura que o
instalador aceita. Quando o repositório não pode ser alcançado, a lista diz
qual endereço falhou; importar um `.zip` continua funcionando.

### Importando um .zip

1. Escolha o `.zip`. Ele é enviado em partes, com uma porcentagem, então uma
   biblioteca de centenas de MiB também chega lá.
2. O servidor verifica o pacote inteiro antes de qualquer outra coisa. Nada
   nele pode ser um caminho para fora da pasta pessoal do agente, um arquivo
   oculto como `.ssh` ou `.bashrc`, a conversa ou o diário de execuções, ou um
   agendamento que carregue um comando. Quando algo está errado, você é
   informado do quê, e nada é criado.
3. Você vê o que ele traria: a descrição, as ferramentas (e as que faltam nesta
   instalação), os agendamentos, e se ele traz a memória, arquivos para a pasta
   pessoal, documentos da biblioteca ou um modelo. Confirme e dê um nome a ele.
4. Ele é instalado em segundo plano, com o progresso na tela. Os documentos da
   biblioteca são enviados um por um e indexados de novo aqui. Se algo falhar
   no meio do caminho, o agente é apagado de novo em vez de ficar instalado
   pela metade.

Um agente importado também chega **desligado**. Se ele indicar um provedor, a
chave tem de ser definida nesta instalação: as chaves nunca viajam num `.zip`.

Se você preferir não ser perguntado, desative **Perguntar de onde parte um
novo agente** em **Configurações → Interface**: o **+** então vai direto para
um agente vazio.

### Nenhum agente tem root

Nenhum, nem mesmo o orquestrador. Esse é todo o modelo de isolamento, e vale a
pena deixá-lo claro porque ele decide o que um agente como o `os-watcher` pode
fazer:

- **Observar não exige privilégios.** `df`, `free`, `uptime`, `nproc`,
  `systemctl is-active` funcionam todos como usuário comum. Um agente consegue
  ver um disco enchendo muito antes de ele encher.
- **Consertar geralmente exige, e ele não os tem.** Os prompts dizem a ele que
  informe exatamente o que executaria em vez de tentar e falhar: um cartão
  dizendo “precisa de root: journalctl --vacuum-size=200M liberaria cerca de
  1,2G” vale mais que uma tentativa fracassada.

Se você quer que algo seja consertado automaticamente, coloque esse comando no
crontab do próprio root. Um agente que decide sozinho apagar arquivos como root
não é um recurso que alguém queira às três da manhã.

## Criando seu primeiro agente

Aperte **+**, escolha um agente vazio, um `.zip` ou um modelo, e dê um nome a
ele. Isso cria, no servidor:

- o usuário Linux `agent-001`,
- a pasta pessoal dele em `/opt/boa/agents/001/`, modo 0700,
- `info.json`, `system-prompt.md` e um token de API dentro dela.

O id é o menor número livre. O `000` é reservado para o orquestrador.

Um agente novo começa com as ferramentas do kanban e nada mais, e com tetos
conservadores. Ele não tem agendamento, então não faz nada até você dar um a
ele ou apertar **Executar agora**.

## Conversando com um agente

Clique num agente na barra lateral e você terá a conversa dele. Digite o que
você quer que ele faça e aperte Enter; Shift+Enter começa uma nova linha.

A caixa em que você digita fica parada, logo acima da barra de status no pé da
página: só a conversa acima dela rola, então ela nunca fica escondida e você
nunca precisa rolar para baixo para alcançá-la. Enquanto está vazia, ela lembra
você, em cinza, como o Enter se comporta — ou que o agente ainda está
trabalhando — e num celular estreito ela cresce uma ou duas linhas para que
esse lembrete nunca fique cortado.

Uma mensagem é uma execução: o agente usa as ferramentas dele, faz o trabalho e
responde quando termina. Isso pode levar minutos, então a caixa de mensagem
fica desativada enquanto ele trabalha e a resposta aparece quando chega. Cada
resposta mostra quanto custou, em tokens e passos.

As respostas são renderizadas como markdown — títulos, tabelas, listas,
citações e blocos de código — porque é assim que um modelo escreve. As suas
próprias mensagens aparecem exatamente como você as digitou. Um link só é um
link quando aponta para http ou https; qualquer outra coisa fica como o texto
que era.

A conversa fica guardada. As últimas dez trocas são reenviadas ao modelo a cada
mensagem, para que o agente saiba do que vocês estavam falando — e por isso uma
conversa longa custa mais por mensagem do que uma curta. **Limpar conversa**
recomeça do zero.

Conversar com um agente **não** conta para o teto de execuções por dia dele:
esse teto existe para deter um agendamento sem supervisão, não para impedir
você de digitar. Os tetos por execução de tokens, passos e tempo se aplicam,
sim.

Cada agente tem a sua própria conversa, guardada na própria pasta pessoal, e
nenhum agente consegue ler o que você disse a outro.

A conversa não é só o que você digitou. Quando um dos cartões do agente chega
ao seu horário, o cartão é publicado nessa mesma conversa no momento em que a
execução começa, e a resposta da execução aparece embaixo dele — então abrir um
agente mostra tudo o que pediram a ele, você ou outro agente, e o que ele fez a
respeito. Veja [Quando um cartão é executado](#quando-um-cartão-é-executado).

### API Calls

O nome do agente aparece acima das abas Conversa e API Calls. Só **Conversa**
fica visível por padrão. Para mostrar a outra aba, abra a chave inglesa do
agente, selecione **Interface**, ative **Mostrar a aba API Calls** e aperte
**Salvar**. A escolha é salva para este agente no servidor. Abrir ou recarregar
um agente sempre começa em Conversa, mesmo quando API Calls está ativada.

**API Calls** mostra o JSON que realmente sai, incluindo o prompt completo do
agente, a conversa, as definições das ferramentas e os resultados das
ferramentas enviados naquela requisição. A requisição mais recente aparece
expandida; expanda outra chamada para examiná-la. Chamadas novas aparecem
enquanto o agente roda, incluindo requisições que falharam, novas tentativas do
SDK e chamadas ao modelo reserva dele. A indentação e as cores tornam o JSON
legível sem renderizá-lo como conversa nem arredondar identificadores numéricos
grandes.

As 100 requisições completas mais recentes são guardadas separadamente da
conversa. Limpar a Conversa não as apaga. O registro começa com esta versão; as
requisições anteriores não podem ser reconstruídas. Os cabeçalhos de
autenticação não são registrados.

## Configurações do agente

O título mostra **Configuração do agente 001**, com o id do agente selecionado.
**Executar agora** só aparece no espaço de trabalho que contém Conversa e API
Calls. Para excluir um agente, abra **Geral → Excluir agente** e confirme o
nome dele na caixa de diálogo. A exclusão é uma seção separada, abaixo de
Identidade.


A conversa é o que você obtém clicando num agente. Todo o resto — modelo,
ferramentas, tetos, prompt de sistema, agendamento — fica atrás da **chave
inglesa** à direita da caixa do agente na barra lateral.

## Exportando um agente

A última aba das configurações de um agente, **Exportar**, baixa esse agente
como um `.zip` que **+ → Importar de um arquivo .zip** consegue instalar, aqui
ou em outra instalação. A configuração, o prompt de sistema e os agendamentos
dele sempre vão junto. Quatro coisas só vão se você marcá-las, e cada caixa diz
de antemão o que adicionaria:

| Opção | O que adiciona |
|---|---|
| **Memória** | O `memory.md` dele, com quantos caracteres contém |
| **Provedor e modelo** | Qual provedor e qual modelo ele usa. Nunca a chave |
| **Documentos da biblioteca** | Os originais da biblioteca dele com as suas informações (título, ano...). Eles são indexados de novo onde forem importados |
| **Arquivos da pasta pessoal** | Os scripts dele, a pasta `samba` e o que mais ele guardar na pasta pessoal. Podem conter coisas que você não compartilharia, por isso a lista de arquivos é mostrada antes de você baixar |

Algumas coisas nunca vão, não importa o que você marque: chaves de API, o token
do próprio agente, credenciais de canais, a conversa dele, o diário de
execuções, as sessões do navegador e os arquivos ocultos da pasta pessoal. Do
crontab dele só viajam os agendamentos que executam o agente, não outros
comandos que alguém tenha digitado ali: um `.zip` que levasse comandos os
executaria na máquina em que fosse importado.

## Pastas compartilhadas do Samba

Cada agente tem uma pasta `samba/` na sua pasta pessoal, exportada
automaticamente com o nome de usuário Linux dele. Por exemplo, o
compartilhamento **agent-001** aponta apenas para `/opt/boa/agents/001/samba/`.
Renomear o agente em Geral não renomeia o compartilhamento. O resto da pasta
pessoal e a configuração protegida dele não são exportados.

1. Abra **chave inglesa → Samba** do agente.
2. Digite uma **nova senha Samba** de pelo menos 8 caracteres, escolha as permissões e aperte **Salvar**.
3. Abra o endereço Windows ou SMB mostrado na aba — `\\server\agent-001` no Windows, `smb://server/agent-001` no Linux e no macOS — e entre com o nome de usuário exibido e essa senha.

O compartilhamento começa ativado, visível na lista de compartilhamentos do
servidor e configurado para leitura e gravação, com o acesso de convidado
desativado. Antes da primeira conexão autenticada, defina a senha dele nesta
aba. Um campo de senha em branco nos salvamentos seguintes mantém a senha
existente. As credenciais do Samba são separadas das credenciais de login do
Linux; defini-las não desbloqueia a conta Linux do agente.

| Configuração | Efeito |
|---|---|
| Compartilhar esta pasta | Liga ou desliga este recurso sem apagar os arquivos dele |
| Autenticação | Usuário e senha do agente por padrão; acesso de convidado só quando selecionado explicitamente |
| Permissões | Somente leitura ou leitura e gravação via SMB; o agente continua podendo trabalhar nos próprios arquivos locais |
| Visibilidade e descrição | Se ele aparece na lista de compartilhamentos do servidor, e a descrição dele |
| Permissões dos novos arquivos/pastas | Modos Unix em octal, inicialmente `0600` / `0700`; os arquivos existentes mantêm os seus modos |

O nome e o caminho do compartilhamento são fixos. A pasta continua privada para
o dono Linux dela. Salvar mudanças nas configurações de acesso fecha as
conexões existentes deste compartilhamento, para que os clientes se reconectem
com as novas permissões. Os compartilhamentos dos outros agentes continuam no
ar. A senha em si nunca é devolvida pela API nem guardada em `info.json`.

O `--update` adiciona as pastas e os compartilhamentos do Samba aos agentes
existentes, `agent-000` incluído. Excluir um agente remove
o compartilhamento e a conta Samba dele junto com a pasta pessoal. O
`--backup` / `--restore` preservam os dados compartilhados, as configurações,
as senhas Samba e as identidades das contas. A restauração verifica o modo de
portas web salvo, incluindo instalações que servem a 443 diretamente.

O Samba usa a porta TCP **445**, independentemente do proxy web. No Docker,
essa porta precisa ser publicada explicitamente. O BoA roda o seu próprio
serviço `boa-samba`, com configuração e banco de senhas próprios em
`/opt/boa/samba/`; ele não sobrescreve nem assume a configuração de outro
servidor Samba, e o instalador se recusa a assumir uma instalação Samba
existente que ele não gerencia.

## Dando um modelo a um agente

Em **LLMs**, escolha um provedor. A lista é curta de propósito: ela oferece os
três provedores auto-hospedados, que não precisam de chave, e todo provedor na
nuvem cuja chave esteja definida em **Configurações → Chaves de API**. Um
provedor na nuvem sem chave levaria o agente até a primeira execução e falharia
ali, então ele não é oferecido. Defina a chave dele e ele aparece.

Um agente já configurado com um provedor continua vendo esse provedor na lista
mesmo que a chave dele seja removida, marcado como *(sem chave configurada)* —
do contrário, a caixa mostraria um provedor que ninguém escolheu e o salvaria
no próximo clique.

**No seu próprio hardware.** Sem chave, e a caixa URL base é onde o seu próprio servidor escuta.

| Provedor | Modelos listados | Modelo padrão |
|---|---|---|
| `ollama` | 23 | `gpt-oss:20b` |
| `llamacpp` | 1 | `local-model` |
| `vllm` | 3 | você informa o modelo |

**Empresas que servem os modelos que elas mesmas criaram.**

| Provedor | Modelos listados | Modelo padrão |
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

**Hosts e roteadores, que servem modelos criados por outros.** Uma chave alcança muitos modelos; o id do modelo indica qual.

| Provedor | Modelos listados | Modelo padrão |
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

Um provedor precisa de dois valores na caixa da chave: o **Cloudflare Workers
AI** monta o endereço a partir do id da conta, então a chave dele se escreve
`account-id:api-token`, as duas metades tiradas do painel da Cloudflare. A
caixa em **Configurações → Chaves de API** avisa disso.

O campo do modelo sugere o que aquele provedor serve, e filtra a lista enquanto você digita — mas é uma caixa de texto normal, então um modelo lançado hoje de manhã pode simplesmente ser digitado. Essas sugestões vêm de `/opt/boa/config/providers/<provider>.json`, que você pode editar no servidor; uma atualização nunca sobrescreve um arquivo que você alterou.

Os provedores auto-hospedados não precisam de mais nada se rodam na mesma
máquina.

**URL base** só aparece para `ollama`, `llamacpp` e `vllm`, e é onde o seu
próprio servidor escuta — o padrão é a porta habitual nesta máquina, o que está
certo quando o modelo roda ao lado da aplicação. Escolha um provedor na nuvem e
a caixa some: esse endereço é fixo, esta instalação já o tem, e a única coisa
que uma caixa ali poderia fazer seria deixar um erro de digitação quebrar um
agente que funciona. O modelo reserva funciona do mesmo jeito.

Para um provedor na nuvem, o caminho mais simples é a aba **Chaves de API** em Configurações, que todos os agentes desse provedor passam a usar. Para dar a este agente uma chave diferente, grave-a na pasta pessoal dele, como root:

```bash
mkdir -p /opt/boa/agents/001/keys
echo "sk-..." > /opt/boa/agents/001/keys/anthropic.key
chown -R agent-001:agent-001 /opt/boa/agents/001/keys
chmod 700 /opt/boa/agents/001/keys
chmod 600 /opt/boa/agents/001/keys/anthropic.key
```

O nome do arquivo é o nome do provedor. Cada agente lê só a própria chave,
então um agente não consegue gastar o orçamento de outro.

### Chaves de API

As Configurações têm uma aba **Chaves de API**: uma chave por provedor na
nuvem, compartilhada por todos os agentes que o usam. Os provedores
auto-hospedados não aparecem, porque não precisam de chave.

Uma chave é guardada em `/opt/boa/config/apikeys/<provider>.key`. O diretório
tem modo `0700` e os arquivos `0600`, os dois do usuário web, então nenhum
agente consegue ler nenhum deles: nem a chave de outro provedor, nem a própria.
Quando um agente roda, a API dos agentes entrega a ele a chave **do provedor
com que esse agente está configurado, e de nenhum outro**: um agente no Ollama
não pode pedir a chave da Anthropic.

As instalações feitas antes de esse diretório ser renomeado guardam as chaves
em `/opt/boa/config/keys/`; o `--update` as transfere e remove o diretório
antigo.

Vale a pena deixar claro o que isso protege e o que não protege. Um agente que
usa legitimamente um provedor pago tem a chave dele enquanto roda — ele precisa
dela para fazer a chamada, e um agente com `bash.run` poderia imprimi-la. O que
o armazenamento compartilhado impede é que um agente junte as chaves de
provedores que ele não usa, e ele mantém todas as chaves fora das pastas
pessoais dos agentes, onde um único backup perdido exporia todas de uma vez.

Para cobrar um agente numa conta diferente, coloque uma chave na pasta pessoal
desse agente, em `keys/<provider>.key`. Essa tem prioridade sobre a
compartilhada.

## Escrevendo um prompt de sistema

O prompt de sistema é o que o agente é. Ele fica guardado como
`system-prompt.md` na pasta pessoal do agente, e você o edita na interface.

O que funciona:

- **Diga para que o agente serve**, em uma ou duas frases.
- **Diga o que significa “concluído”.** Um agente sem definição de concluído ou
  para cedo demais ou nunca para.
- **Diga o que fazer quando ele travar.** Sem isso, os modelos inventam um jeito
  de contornar o obstáculo. “Se você não conseguir, diga isso no quadro e pare”
  é suficiente.
- **Diga a ele que leia o quadro primeiro.** É a única memória que ele tem
  entre uma execução e outra.

O que não funciona: dizer a ele que não use uma ferramenta. Se você não quer
que ele use uma ferramenta, não dê a ferramenta a ele — o prompt é uma
sugestão, a lista de ferramentas é imposta.

## O que um agente lembra

Cada agente tem um `memory.md` na sua pasta pessoal, e esse arquivo é a única
coisa que ele leva de uma execução para a seguinte. Ele escreve nele com
`memory.append` quando aprende algo que vale a pena guardar, e o organiza com
`memory.replace`.

O arquivo inteiro é carregado no início de cada execução, e é isso que o torna
útil e também o que o torna caro: cada caractere é pago a cada chamada ao
modelo. Em **Configurações do agente → Memória → Limite de memória
(caracteres)**, escolha um limite de 1.000 a 1.000.000 caracteres. O padrão é
8.000, inclusive para os agentes existentes. O agente é instruído a organizar a
memória quando ela passa de 75% do limite.

O contador mostra a contagem atual e o limite selecionado, incluindo espaços e
quebras de linha. Você pode aumentar o limite e colar uma memória maior no
mesmo salvamento. Se o texto passar do limite selecionado, nada dessa
requisição de configurações é salvo: encurte o texto ou aumente o limite. A
memória anterior fica intacta; as novas gravações nunca acrescentam
`[truncated]`. Um texto descartado anteriormente precisa ser colado de novo a
partir do original. A memória inteira ainda tem de caber no contexto do modelo
escolhido, junto com o prompt, a conversa e as ferramentas.

Coisas boas para guardar: onde algo fica, qual era afinal um comando, o que
você prefere. Não o diário do que ele fez — isso é o quadro.

Você mesmo pode ler e corrigir a memória em **Memória**, nas configurações do
agente. Um fato errado com base no qual um agente continua agindo vale a pena
ser corrigido à mão.

## Bibliotecas locais de documentos (RAG)

Cada agente tem a sua própria biblioteca em `/opt/boa/agents/<id>/rag/`. São
aceitos arquivos PDF, EPUB, TXT em UTF-8 e Markdown. O instalador prepara o
modelo de vetorização local — o EmbeddingGemma 300M Q8 (cerca de 318 MiB), a
menos que outro tenha sido escolhido (veja [Escolhendo o modelo de vetorização](#escolhendo-o-modelo-de-vetorização)) —,
o motor llama.cpp dele e o OCR.
A extração, o OCR, a vetorização dos documentos e a das consultas rodam neste
servidor. Os trechos recuperados são enviados ao provedor de respostas
selecionado para o agente, incluindo provedores na nuvem quando configurados.
Não há nenhum endpoint externo de vetorização disponível. A instalação, as
atualizações, a importação de documentos, o OCR e o backup/restauração foram
verificados no Debian 13 e no Alpine 3.24, incluindo a inicialização dos
serviços depois de reiniciar.

1. Abra **Configurações → RAG** e verifique se o motor local está pronto.
2. Abra a aba **RAG** de um agente, ative a recuperação e salve o agente. O
   modelo **rag-consultant** chega com a recuperação já ativada.
3. Escolha os arquivos e clique em **Enviar documentos**. Os arquivos grandes
   viajam em partes. Outra opção é copiar arquivos completos para
   `rag/inbox/` e clicar em **Importar arquivos de rag/inbox**. Os originais
   importados vão para o armazenamento de documentos gerenciado.
4. Espere por **Pronto**. A extração e a vetorização rodam em segundo plano; os
   outros documentos prontos continuam pesquisáveis. A página mostra o
   progresso e os erros.
5. Teste uma pergunta com **Pesquisar na biblioteca**, ou pergunte ao agente na
   conversa normal dele. As citações têm links para a página do PDF de origem
   ou para o EPUB/documento original.

Os erros ao importar de `rag/inbox/` aparecem acima da lista de documentos. Os
originais que falharam ficam na caixa de entrada para serem corrigidos. A
indexação processa lotes limitados, para que os documentos pequenos não
precisem esperar uma rodada inteira do agendador entre um livro e outro.

Os controles de **Informações do documento** editam, nesta ordem, o ano de
publicação, o título, o subtítulo, o(s) autor(es), a versão, o idioma e as
etiquetas. O ano é opcional e aceita até quatro dígitos. O subtítulo, quando
existe, aparece na lista de documentos logo abaixo do título. Subtítulo, ano,
autor, versão e idioma viajam com cada trecho que o agente recupera, para que
ele consiga distinguir documentos com o mesmo título, datar e atribuir o que
cita, e distinguir edições que não concordam entre si. Substituir um arquivo
mantém o documento pesquisável anterior
até o novo terminar de ser indexado. Se o motor local de vetorização parar
enquanto um documento está sendo indexado (uma atualização, um reinício), o
documento volta para **Na fila** com a mensagem “Local embeddings are
unavailable” e, assim que o motor volta a responder, continua de onde parou; não há nada para reindexar. Reindexar reconstrói um documento; Cancelar interrompe o
trabalho pendente dele; Excluir o remove das pesquisas futuras. Os filtros de
idioma e de versão usam os metadados que você informou. As citações de EPUB
identificam capítulos, não números de página inventados. Os PDFs digitalizados
precisam de idiomas de OCR instalados no servidor; inglês e espanhol vêm
instalados por padrão (`eng+spa`). Arquivos não suportados ou criptografados
informam um erro, em vez de um índice vazio bem-sucedido.

**Modo de resposta** decide até onde o agente pode ir além dos documentos; a
linha abaixo da lista diz o que o modo escolhido faz.

- **Documentos e conhecimento geral**: o agente pode usar os dois, mantidos
  separados.
- **Exigir fontes documentais**: o agente tem de pesquisar na biblioteca ele
  mesmo antes de responder; uma resposta dada sem pesquisar é devolvida a ele
  uma vez. Se a execução não recuperou nenhum trecho, você recebe a frase fixa
  “A biblioteca de documentos não contém informações suficientes para
  responder a esta pergunta” em vez do que o modelo tiver escrito.
- **Somente documentos (verificado)**: como o anterior, e cada parágrafo e cada
  item de lista da resposta tem de citar um trecho recuperado naquela execução.
  Cada parágrafo é verificado: a falta de citação, uma citação a um trecho que
  não foi recuperado ou um sentido distante do trecho citado (medido com o
  motor local de vetorização) devolvem a resposta uma vez com a lista desses
  parágrafos. O que ainda estiver sem respaldo depois disso é removido, e uma
  última linha diz quantos parágrafos saíram. Se não sobrar nada com respaldo,
  você recebe a frase fixa. Se o motor não puder ser alcançado para fazer a
  verificação, a resposta é retida em vez de ser mostrada sem verificação.

O que o modo verificado não consegue é provar que um parágrafo citado diz
exatamente o que o trecho dele diz. Nas nossas medições, um parágrafo que
contradiz o trecho, ou que acrescenta algo sobre o mesmo assunto, pontua como
um fiel; o que a verificação pega é um parágrafo que cita um trecho sobre outra
coisa, e um parágrafo sem fonte nenhuma. Ela também não é exata em nenhum dos
dois sentidos: nos nossos testes, removeu cerca de 6 em cada 100 parágrafos
fiéis — sobretudo itens de lista curtos e resumos de uma linha, que lhe dão
pouco para comparar — e deixou passar menos de 1 em cada 100 citações a um
trecho sobre outro assunto. Um exemplo de código é avaliado junto com a frase
que o introduz. Revise o trecho citado quando a precisão importar. As frases
fixas são escritas no idioma escolhido em **Configurações → Agentes → Idioma
em que os agentes respondem**, e em inglês quando não há nenhum escolhido.
As citações são resolvidas apenas a partir de identificadores de fontes
recuperadas.

Padrões por agente: 128 MiB por arquivo, 2.048 MiB de documentos originais,
200.000 fragmentos, 8 resultados e até 16.000 caracteres de texto recuperado
por execução. Um orçamento conservador de bytes também limita o que cabe ao
lado do prompt e do histórico. A **Similaridade mínima** começa no valor
medido para o modelo de vetorização em uso — 0,20 para o EmbeddingGemma, 0,35
para o Qwen3-Embedding — e a linha abaixo do campo diz qual é. É uma pontuação
de busca, não uma probabilidade, e cada modelo tem a sua própria escala.
Aumente-a se os resultados semânticos forem amplos demais. As correspondências
literais também participam.
A API expõe ainda as cotas de fragmentos e o tamanho dos fragmentos em tokens.

As configurações globais controlam as threads de vetorização, as indexações
simultâneas e os idiomas de OCR padrão. **Indexações simultâneas** é quantas
bibliotecas de agentes são indexadas ao mesmo tempo (uma tarefa por agente, os
documentos dele um depois do outro); cada tarefa pode usar até 4 GB de RAM, o
que o rótulo lembra você. Isso não acelera a biblioteca de um agente: o motor
de vetorização atende uma requisição por vez. Para vetorizar mais rápido,
aumente **Threads de CPU para vetorização**. O modelo é compartilhado; as
bibliotecas e as permissões são por agente.
O processamento retoma depois de reinícios, mantendo os documentos concluídos
e os fragmentos reaproveitáveis de tarefas interrompidas. Uma reindexação que
falha mantém a última versão publicada. Só a instalação do modelo precisa de
download; a recuperação normal pode rodar sem internet. Um motor local
indisponível é informado, e nunca substituído por um serviço externo de
vetorização.

O `boa-embeddings` serve o modelo por um socket Unix; o `boa-rag` agenda a
fila. Os dois têm unidades systemd e OpenRC e aparecem nas configurações do
sistema. Os backups incluem os documentos originais, os metadados e snapshots
consistentes do SQLite e do índice vetorial. As configurações de execução são
incluídas, e com elas o modelo de vetorização escolhido; os binários do modelo
e os pesos baixados, não. Uma restauração baixa o modelo escolhido quando a
máquina não o tem, e se esse download falhar ela avisa e segue em frente: o
modelo pode então ser baixado, ou outro escolhido, em **Configurações → RAG**.
Os envios ainda em andamento são cancelados num backup restaurado. As
bibliotecas indexadas sobrevivem a uma atualização normal.

### Escolhendo o modelo de vetorização

O modelo de vetorização transforma cada trecho e cada pergunta nos números
pelos quais a biblioteca é pesquisada. **Configurações → RAG → Modelo de
vetorização** oferece dois, e o mesmo atende todos os agentes:

| | EmbeddingGemma 300M (Q8) | Qwen3-Embedding 0.6B (Q8) |
|---|---|---|
| Download | 318 MiB | 610 MiB |
| Memória do mecanismo em funcionamento | cerca de 600 MB | cerca de 1,1 GB |
| Tempo de indexação, mesmo processador | 1× | cerca de 4× |
| Licença | Gemma Terms of Use | Apache 2.0 |

O EmbeddingGemma é o padrão e serve para qualquer máquina. O Qwen3-Embedding é
para uma máquina com processador e memória de sobra: com os livros de Python
em espanhol da biblioteca de teste, ele manteve as perguntas sobre os livros
(0,51–0,79) mais distantes das perguntas sem relação (no máximo 0,21) do que o
EmbeddingGemma (0,35–0,67 contra 0,17), e os parágrafos que reformulam um
trecho mais distantes dos parágrafos sobre outra coisa. Na máquina de teste
com dois processadores, ele levou 2,2 segundos por fragmento, contra 0,5.

Para trocá-lo:

1. Escolha o modelo na lista. Abaixo dele você vê o tamanho, a memória, a
   velocidade e a licença, e se ele já foi baixado.
2. Se não foi, clique em **Baixar modelo** e espere a barra terminar. O
   download é conferido com o SHA-256 publicado antes de ser usado.
3. Clique em **Salvar** e confirme. O mecanismo reinicia com o novo modelo; a
   linha no topo diz “O mecanismo está carregando este modelo” por alguns
   segundos e depois **Pronto**.

O que uma troca põe em movimento:

- Todos os documentos de todos os agentes são indexados de novo, uma
  biblioteca por tarefa de indexação, como seria um envio novo. Numa
  biblioteca grande, isso leva horas.
- Até chegar a vez dele, um documento continua na biblioteca e é encontrado
  pelas palavras de uma pergunta, não pelo sentido. Uma busca durante esse
  tempo diz ao agente quantos documentos estão esperando, para que um trecho
  ausente não seja tomado como se a biblioteca não cobrisse a pergunta.
- A **Similaridade mínima** de cada agente que ainda tinha o valor recomendado
  do modelo antigo muda para o do novo modelo. Um agente em que você definiu
  outro valor o mantém.
- O modo verificado compara parágrafos e trechos com o modelo em uso, contra
  um limiar medido para ele (0,36 para o EmbeddingGemma, 0,44 para o
  Qwen3-Embedding).

Os pesos do modelo anterior ficam no disco, então voltar atrás não exige download -
mas exige indexar de novo todos os documentos que foram indexados com o outro.

## Escolhendo as ferramentas

Em **Ferramentas**, marque o que este agente pode usar. Uma ferramenta que não
está marcada não é mostrada ao modelo e seria recusada pelo servidor mesmo que
ele a pedisse: essa verificação roda no servidor, e não no prompt.

Estas são as ferramentas que vêm incluídas:

| Ferramenta | O que um agente pode fazer com ela |
|---|---|
| `bash.run` | Executar comandos de shell como o seu próprio usuário sem privilégios |
| `kanban.add_card` | Colocar uma tarefa no quadro compartilhado |
| `kanban.assign_card` | Passar um dos próprios cartões para outro agente |
| `kanban.move_card` | Mover um dos próprios cartões entre colunas |
| `kanban.delete_card` | Remover um dos próprios cartões |
| `kanban.list_cards` | Ler o quadro: os próprios cartões, ou todos os cartões no caso do **manager** |
| `channel.write` | Enviar uma mensagem para um canal configurado |
| `web.fetch` | Ler uma página web pública |
| `rss.fetch` | Ler um feed RSS ou Atom como uma lista de entradas |
| `memory.append` | Anotar algo para o seu eu futuro |
| `memory.replace` | Organizar o que ele lembra |
| `skill.read` | Ler um procedimento que lhe foi dado |
| `script.write` | Escrever um script no próprio diretório `scripts/` |
| `script.list` | Listar os scripts que escreveu |
| `script.delete` | Remover um dos próprios scripts, com as linhas de cron que o executavam |
| `cron.add` | Executar um dos próprios scripts num agendamento, no próprio crontab |
| `cron.list` | Ler o próprio crontab |
| `cron.remove` | Parar de executar um dos próprios scripts |
| `mail.read` | Ler mensagens da caixa de correio configurada |
| `mail.move` | Arquivar uma mensagem em outra pasta da mesma conta |
| `mail.delete` | Mandar uma mensagem para a Lixeira da conta |
| `mail.forward` | Encaminhar uma mensagem para um endereço que você permitiu |
| `rag.search` | Pesquisar na própria biblioteca de documentos |
| `rag.read` | Ler um fragmento que uma pesquisa devolveu |
| `rag.list` | Listar os documentos da própria biblioteca |
| `browser.open` | Abrir uma página no próprio navegador, mantendo os cookies |
| `browser.read` | Ler a página aberta, ou os links dela |
| `browser.click` | Clicar num link ou num botão dela |
| `browser.type` | Preencher um campo, opcionalmente enviando-o |
| `browser.screenshot` | Salvar uma imagem dela para você |
| `image.send` | Anexar um PNG à conversa web e à resposta no Telegram, quando a conversa começou ali. As imagens ocupam a área de texto da mensagem web |

Cada família ganha uma caixa própria, com a contagem de quantas ferramentas
daquela família este agente tem: “este agente pode ler a caixa de correio?” é
uma única decisão, e é desenhada como uma única caixa. O interruptor que ativa
o quadro kanban para um agente fica no pé da caixa **Kanban**, abaixo das
ferramentas que ele controla.

- **`bash.run`** — comandos de shell como o usuário desse agente. Ele não tem
  root e não consegue obter. Dê esta quando o agente tiver trabalho de verdade
  a fazer na máquina.
- **`kanban.*`** — o quadro compartilhado. Dê pelo menos `list_cards` e
  `add_card` a tudo o que deva ser visível.
- **`channel.write`** — mensagens para você. Marque também os canais na aba **Canais**.
- **`web.fetch`** — só páginas públicas. Endereços privados e de loopback são
  recusados.
- **`rss.fetch`** — um feed RSS ou Atom, como uma lista de entradas em vez do
  documento XML. Muito mais barato do que buscar o mesmo feed com `web.fetch`,
  e poupa o agente de interpretá-lo. As duas ficam em **Internet**.
- **`script.*` e `cron.*`** — em **Automação**. O agente escreve um script no
  próprio diretório `scripts/` e o agenda no próprio crontab, para trabalho
  recorrente que não exige que ele pense: o script roda sozinho, não custa
  tokens, e o agente lê os resultados na próxima execução. Ele só pode agendar
  os próprios scripts, nunca com frequência maior que a cada 5 minutos, e
  nunca pode mexer na linha que o acorda.

Um agente pode fazer muita coisa dentro da própria pasta pessoal, e nada fora
dela. Ele não consegue ver que outro agente existe, muito menos ler o prompt
dele: o diretório dos agentes pode ser atravessado mas não listado, e cada
pasta pessoal é privada do seu próprio usuário Linux, então quem recusa é o
kernel, e não uma verificação em Python.

Ele também não consegue reescrever **o que ele é**. As ferramentas concedidas,
os tetos de gasto, o prompt de sistema e o token de API dele ficam numa gaveta
dentro da pasta pessoal que pertence ao root: o agente os lê e não consegue
alterá-los. Quem os altera é você; ele, não. A única coisa sobre si mesmo que
ele pode editar é a memória.
- **`mail.*`** — a caixa de correio configurada em **Configurações → E-mail**.
  Veja abaixo.
- **`skill.read`** — os procedimentos escritos marcados no painel
  **Habilidades**. Precisa das duas coisas: a ferramenta aqui e pelo menos uma
  habilidade lá.

### As ferramentas de e-mail

São quatro, e elas precisam de uma caixa de correio IMAP configurada em
**Configurações → E-mail**. O agente nunca vê essa senha: ele diz o que quer
que seja feito e a API dos agentes, que guarda as credenciais, faz.

| Ferramenta | O que faz |
|---|---|
| `mail.read` | Lê as mensagens. **Não marca nada como lido**, então a sua própria contagem de não lidas continua significando o que significava. |
| `mail.move` | Arquiva uma mensagem em outra pasta da mesma conta. A pasta tem de existir. |
| `mail.delete` | Manda uma mensagem para a Lixeira da conta, quando existe uma. |
| `mail.forward` | Encaminha uma mensagem, **só para os endereços que você listou**. |

Essa última é a importante. Uma caixa de entrada é a única entrada de um
agente em que qualquer pessoa no mundo pode escrever, então o `mail.forward` é
conferido com a sua lista pelo servidor em cada encaminhamento — não pelo
agente, e não por algo escrito no prompt dele. Com a lista vazia, o
encaminhamento é recusado de cara.

Dê o `mail.read` sozinho a um agente que só tem de vigiar. Acrescente o
`mail.move` para arquivar, e pense duas vezes antes de dar `mail.delete` e
`mail.forward`.

A caixa de seleção **kanban** no pé desliga totalmente o quadro para este
agente. Desmarcada, ele não recebe nenhuma ferramenta de kanban e para de
adicionar cartões, e esse é o interruptor a usar para um agente cujo trabalho
não pertence ao quadro.

## Dando uma habilidade a um agente

Uma habilidade é um procedimento escrito: como uma tarefa é feita aqui, passo a
passo. Nenhuma vem com a aplicação: uma habilidade é sobre ESTA máquina —
estes hosts, este backup, este certificado —, então uma genérica seria um
procedimento que ninguém segue. Você escreve as suas no servidor, como root:

```bash
mkdir -p /opt/boa/skills/BackupVerification
nano /opt/boa/skills/BackupVerification/SKILL.md
chown -R root:root /opt/boa/skills
chmod 00755 /opt/boa/skills/BackupVerification
chmod 0644 /opt/boa/skills/BackupVerification/SKILL.md
```

O arquivo começa com um nome e uma descrição de uma linha entre duas linhas
`---`, e o resto é o procedimento:

```markdown
---
name: BackupVerification
description: How to check that last night's backups actually ran.
---

1. Read /var/log/backup.log ...
```

Cada diretório em `/opt/boa/skills/` aparece então como uma caixa de seleção no
painel **Habilidades** do agente. Marque uma, dê ao agente a ferramenta
`skill.read` em **Ferramentas** e aperte **Salvar**. A partir da próxima execução, o agente sabe que esse procedimento existe e pode lê-lo
quando a tarefa aparecer.

### Por que se dar ao trabalho, se já existe o prompt de sistema

Três motivos, e o terceiro é o que importa:

- **O prompt é para que um agente serve; uma habilidade é como uma tarefa é
  feita.** Seis agentes podem compartilhar um procedimento sem que seis cópias
  dele fiquem desatualizadas cada uma por conta própria.
- **Uma habilidade pode ser tão longa quanto precisar.** Um prompt de sistema é
  pago a cada chamada de cada execução, então ele tem de continuar curto. Uma
  habilidade é paga uma vez, pela execução que a lê.
- **O que um agente aprende sozinho morre com ele.** A memória dele fica dentro
  de uma pasta pessoal que nenhum outro agente consegue abrir. Uma habilidade é
  o lugar para colocar o que você quer que o próximo agente também saiba.

### Escrevendo uma

Não há um editor para isso na interface, de propósito: o que uma habilidade diz
vai direto para o raciocínio de um agente que roda às quatro da manhã sem
ninguém olhando, então ela pertence ao root, como as ferramentas. Você as
escreve no servidor:

```bash
mkdir -p /opt/boa/skills/DatabaseBackup
nano /opt/boa/skills/DatabaseBackup/SKILL.md
```

O arquivo começa com um cabeçalho de duas linhas e depois diz o que precisar
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

A `description` é a linha que mais importa. É a única parte que toda execução
paga, e é com base nela que o agente decide se vai ler o resto. “How the
nightly dump is taken and where it goes” (como o dump noturno é feito e para
onde vai) diz a ele quando isto se aplica; “Database stuff” (coisas de banco de
dados), não.

Recarregue a página do agente e a habilidade estará na lista.

Uma atualização nunca mexe em `/opt/boa/skills/`: o que você escreve ali
continua sendo seu. A interface web decide qual agente recebe qual habilidade;
ela não as edita.

### Uma habilidade pode trazer os próprios arquivos

Tudo o que mais estiver no diretório viaja com ela:

```
/opt/boa/skills/DatabaseBackup/
  SKILL.md
  dump.sh
  exclude-tables.txt
```

Os agentes podem ler e executar esses arquivos, então o procedimento pode dizer
“execute `dump.sh` neste diretório” em vez de detalhar quarenta linhas de
shell. O `skill.read` diz ao agente quais arquivos estão ali e onde.

### Quanto custa

Só o nome e a descrição de cada habilidade vão para o prompt — cerca de duas
linhas cada. O corpo é buscado com `skill.read`, uma vez, por um agente que
decidiu que precisa dele, e só então. Dar cinco habilidades a um agente custa a
ele umas duas centenas de tokens por execução, não dez mil, e é por isso que
você pode dar cinco a ele sem pensar na conta.

### Se você excluir uma habilidade que os agentes estão usando

Nada quebra, e nenhum agente fica prometendo algo que não pode cumprir:

- Ela **desaparece do prompt** de todos os agentes que a tinham, na próxima
  execução deles. Um agente nunca fica sabendo de um procedimento que não
  consegue ler.
- Ela **desaparece do painel Habilidades**, então ninguém consegue marcá-la de
  novo.
- O nome **continua no `info.json` do agente** até que algo o reescreva, então
  colocar o diretório de volta restaura a habilidade sem mais nada a fazer.
- Se o agente pedir por ela mesmo assim — ele pode lembrar o nome de uma
  execução anterior —, é informado de que a habilidade está na lista dele e não
  está mais instalada, e é instruído a não adivinhar o que ela dizia.

Uma coisa a saber: **apertar Salvar nesse agente enquanto a habilidade está
faltando a tira da lista de vez.** A interface só salva habilidades que
existem, e é isso que impede que uma excluída fique por aí para sempre. Coloque
o diretório de volta antes de salvar o agente, ou marque a habilidade de novo
depois.

## Dando um navegador a um agente

O `web.fetch` lê uma página pública e nada mais: nada de login, nada de
formulário, nada de botão. Se um agente precisa *usar* um site em vez de lê-lo,
ele precisa de um navegador.

Ele já vem instalado: o instalador pergunta uma vez, e sim é a resposta padrão.
São cerca de 600 MB de Chromium, então uma máquina com pouco disco pode
recusar, e mudar de ideia depois em qualquer sentido:

```bash
./install-update-reinstall-debian.sh --update --browser no    # deixa o navegador de fora
./install-update-reinstall-debian.sh --update --browser yes   # adiciona de novo
```

A resposta fica guardada, como a das portas. Depois, marque as ferramentas do
navegador no painel **Ferramentas** do agente:

Nada disso se aplica ao Alpine: lá não há navegador nenhum, porque o
Playwright não publica nenhuma build para musl. As ferramentas continuam na
lista e avisam disso quando um agente chama uma delas.

| Ferramenta | O que o agente pode fazer |
|---|---|
| `browser.open` | Ir para uma página. Os cookies são mantidos |
| `browser.read` | Ler de novo a página aberta, uma parte dela ou os links dela |
| `browser.click` | Clicar num link ou botão, pelo texto visível ou por um seletor |
| `browser.type` | Preencher um campo, opcionalmente apertando Enter |
| `browser.screenshot` | Salvar um PNG no próprio diretório de downloads |
| `image.send` | Anexar um PNG à resposta na conversa web e no Telegram |


O `browser.screenshot` salva um PNG no servidor. Para exibi-lo na conversa, o
agente depois chama `image.send` com esse caminho. Conceda **image.send** em
**Configurações do agente → Ferramentas → Imagens** e salve. Os agentes novos
criados a partir do **web-navigator** já a incluem; os agentes existentes
mantêm as permissões que já têm.

A imagem ocupa a área de texto da mensagem na conversa web, preservando a
proporção e a altura inteira. Ela também pode ser aberta no tamanho original.
Quando a conversa começou no Telegram, ela é enviada para lá também. Capturas
altas ou grandes são entregues como documentos PNG. Um envio que falha tenta de
novo a parte que faltou, sem repetir o texto nem as imagens que já chegaram.

Só são aceitos arquivos PNG dentro da pasta pessoal desse agente, de até 50 MiB
cada e 16 por resposta. Os anexos continuam privados e exigem uma sessão
iniciada para serem vistos. Uma captura existente pode ser enviada pedindo ao
agente que use `image.send` com o caminho em que ela foi salva.

### As sessões de cada agente são só dele

O navegador em si é uma única cópia, em `/opt/boa/playwright/`, pertencente ao
root e somente leitura para todos os outros. O que **não** é compartilhado é o
perfil:

```
/opt/boa/agents/001/browser/profile/     agent-001, 0700
/opt/boa/agents/002/browser/profile/     agent-002, 0700
```

Um agente que entra num site continua logado **na próxima execução**, porque os
cookies estão no disco dele. E nenhum outro agente está logado, porque esse
diretório é 0700 e pertence ao usuário Linux dele — quem recusa é o kernel, não
há verificação em Python que possa sair errada. Essa separação é justamente o
que um produto hospedado não consegue oferecer quando todos os agentes dele
compartilham uma única máquina.

Os cookies de sessão continuam terminando quando o navegador fecha, aqui como
em qualquer navegador. O que um site marca para persistir, persiste.

### O que ele não faz

- **Nada de endereços privados.** O `browser.open` recusa `192.168.*`, `127.*`
  e os demais, exatamente como o `web.fetch`. Um agente que acabou de ler uma
  página hostil não pode ser convencido a abrir o seu roteador, e um navegador
  com uma sessão seria uma ferramenta muito melhor para isso do que uma simples
  busca.
- **Nada de tela.** Ele roda sem interface gráfica (headless). O
  `browser.screenshot` é como você vê o que ele viu; o próprio agente não
  consegue olhar a imagem.
- **Nada sem as ferramentas.** Como em todo o resto, uma ferramenta que não foi
  dada ao agente é uma ferramenta que ele não consegue chamar, e essa
  verificação fica no servidor.

Se o navegador nunca foi instalado, as ferramentas continuam aparecendo na
lista e respondem com o comando a executar. Elas não desaparecem, e não falham
em silêncio.

## Tetos de gasto

Quatro tetos, por agente, e toda execução para no primeiro que alcançar:

| Teto | Padrão | Contra o que protege |
|---|---|---|
| Tokens por execução | 16384 | Uma única conversa cara |
| Passos por execução | 25 | Um laço que chama ferramentas para sempre |
| Segundos por execução | 300 | Uma execução que trava |
| Execuções por dia | 48 | Uma linha de cron afoita demais |

Isso não é paranoia. Um agente que acorda de hora em hora numa API paga, sem
teto e sem ninguém olhando, é uma fatura que cresce enquanto você dorme.

Aumente-os depois de ver quanto o agente realmente usa, no painel
**Histórico** dele.

### O modelo reserva

Em **LLMs** há um segundo provedor e modelo, abaixo do primeiro. Ele só é usado
quando o principal **falha** — sem chave, sem resposta, um modelo que não
existe — e a execução continua com ele a partir do mesmo passo, reenviando o
que aconteceu até ali, para que o trabalho já feito não seja jogado fora.

Ele é tentado **uma vez por execução**. Se o reserva também falhar, a execução
falha: tentar um e outro alternadamente para sempre queimaria os tetos numa
pane e, mesmo assim, não teria nada para mostrar. A troca para o reserva fica
registrada no histórico do agente, porque uma execução que responde
discretamente com outro modelo, e cobra em outra conta, tem de dizer isso.

Deixar o provedor reserva em **nenhum** é o padrão, e significa que uma falha
encerra a execução.

Escolha o **mesmo provedor** para o reserva e a caixa do modelo é preenchida
com um modelo *diferente* do catálogo desse provedor, e não o mesmo de novo. O
mesmo provedor com o mesmo modelo não consegue responder nada que o principal
não tenha conseguido: falharia exatamente pelo mesmo motivo, todas as vezes.
Se mesmo assim você digitar o par de volta para que fique idêntico, uma linha
abaixo do campo avisa disso — o agente é seu, então é um aviso e não uma
recusa.


Quando uma execução para no teto de tokens ou de passos, o agente é consultado
mais uma vez — sem ferramentas, com um pequeno orçamento próprio — para dar a
resposta que estava prestes a dar, para que uma execução que gastou todo o
orçamento juntando fatos não termine em “vou verificar o sistema”. A conversa
avisa disso embaixo da resposta, porque essa resposta pode estar cortada. O
teto de tempo não recebe essa chamada: a execução já está atrasada.

Essa chamada de encerramento reenvia a conversa inteira, então numa execução
longa e cheia de ferramentas ela não sai barata: uma execução parada num teto
de 12.000 tokens terminou, numa medição, em 24.901. O teto de tokens é,
portanto, um orçamento para o trabalho, e não um máximo rígido para a
execução. Nada é gasto desse jeito a não ser que um teto tenha sido atingido.

### O que o kernel impõe por cima

Os quatro tetos são impostos pela própria execução. Outros dois são impostos
pelo kernel, então eles se mantêm quando o que deu errado foi a própria
execução: nenhum agente pode ter mais de 1.024 processos e threads ao mesmo
tempo, então um comando que se bifurca sem fim para ali, e não na máquina; e no
Debian cada execução vive num escopo systemd próprio com 2 GiB de memória, o
que também encerra o que quer que a execução tenha deixado rodando em segundo
plano quando termina. Uma execução morta pelo limite de memória aparece no
Histórico dela como falha e na conversa dela como um erro, como qualquer outra.
Um navegador já são algumas centenas de threads, e é por isso que o número não
é menor.

## Agendando um agente

Em **Cron**, escreva o crontab do agente. É o crontab do próprio agente, que
pertence ao seu próprio usuário Linux e é executado por ele, exatamente como se
você tivesse executado `crontab -e` como esse usuário.

De hora em hora:

```
0 * * * * /opt/boa/venv/bin/python3 /opt/boa/webapp/backend/core/runner.py --agent-id 001
```

Todo dia útil às 08:00:

```
0 8 * * 1-5 /opt/boa/venv/bin/python3 /opt/boa/webapp/backend/core/runner.py --agent-id 001
```

A interface mostra a linha exata para o agente que você está editando, então
você pode copiá-la e mudar só o horário.

Deixe vazio para remover o agendamento. Desmarque **Ligado** para manter o
agendamento mas fazer o agente ignorá-lo.

Se você usa um provedor pago cujo preço varia conforme a hora — a DeepSeek
cobra várias vezes mais nos horários de pico —, essa escolha é feita aqui.

## O quadro kanban

A página tem duas abas: **Quadro**, que são as três colunas, e **Criar
cartão**, que é o formulário. Qual delas está aberta fica na URL, então
recarregar a página e o botão de voltar a mantêm. Salvar um cartão leva você de
volta ao quadro.

Três colunas: **a fazer**, **fazendo**, **feito**.

O quadro é o que os agentes usam para deixar trabalho uns para os outros e o
que você usa para ver o que realmente aconteceu. Cada cartão traz o seu
histórico: quem o criou, quem o moveu, quando e por quê.

Um cartão tem um título e uma caixa **O que fazer**. O título dá nome a ele; a
caixa é onde vão as instruções, e um agente lê os dois. Um cartão atribuído a
um agente com a caixa vazia o deixa adivinhando, e esse é o motivo habitual de
um agente não fazer nada com um cartão que lhe foi entregue.

O outro motivo é o agente não conseguir ver o quadro de jeito nenhum. Um agente
o lê chamando `kanban.list_cards`, ou não o lê — o quadro nunca é colocado no
prompt dele —, então um agente sem essa ferramenta nunca fica sabendo que o
cartão existe. **Atribuir
a** avisa disso quando você escolhe um agente assim. É um aviso, não um
bloqueio: o cartão é criado mesmo assim, e basta marcar a ferramenta na aba
**Ferramentas** do agente.

Um cartão no quadro mostra quem o fez, com quem ele está, quando foi feito, as
duas primeiras linhas do título, as três primeiras do que há para fazer e
**quando ele roda**. O título ou o corpo inteiro de um cartão cortado aparece
na dica que surge ao passar o mouse.

Essa última linha é a que vale a pena ler. Um cartão sem horário não está
atrasado: ninguém é acordado por causa dele, e o agente dele vai encontrá-lo na
próxima execução agendada. **Mover para** é como você move um cartão à mão —
este quadro não tem arrastar e soltar.

Você pode adicionar, mover e excluir qualquer cartão. **Um agente vê e altera
só os seus**: um cartão é de um agente se foi ele que o criou ou se ele está
atribuído a ele.

Isso é um muro, não uma preferência. Um agente não consegue nem saber que o
trabalho de outro agente existe — nem os títulos, nem quantos são, nem que há
alguma coisa ali. Peça a um agente que mova um cartão que não é dele e ele
ouvirá que não há nenhum cartão assim que seja dele; um cartão que não existe
recebe a mesma frase, porque uma recusa que distinguisse os dois seria um jeito
de perguntar ao quadro o que há nele, um id de cada vez.

A exceção é o **manager** (agente 000), o orquestrador: o trabalho dele é
distribuir tarefas e acompanhá-las, então ele lê o quadro inteiro. É por isso
que coordenar é trabalho dele e de mais ninguém.

Uma confirmação destrutiva **não tem botão padrão**: ela abre com o foco na
própria caixa de diálogo, então o Enter não faz nem uma coisa nem outra e você
tem de dizer qual das duas quer. Esc cancela. Clique no botão vermelho para
seguir em frente.

Uma confirmação comum, que não destrói nada, abre sim com o foco no botão de
confirmar, contornado, onde Enter quer dizer sim.

Excluir um cartão deixa uma linha registrando que ele existiu e quem o excluiu,
para que um agente não consiga apagar as provas do que estava fazendo.

## Configurações

As configurações estão agrupadas em abas, e a aba fica na URL, então recarregar
a página ou abrir um favorito leva você de volta para onde estava:

| Aba | O que tem nela |
|---|---|
| **Sistema operacional** | O que é esta máquina, quanta memória e quanto disco restam, e se os quatro serviços estão no ar — cada um verde quando ativo e vermelho quando não. Lido sem privilégios, do mesmo jeito que o `os-watcher` lê |
| **Conta** | O único endereço de e-mail e a senha. Mudar a senha exige a atual |
| **E-mail** | SMTP, para quando algo precisa chegar até você por e-mail |
| **Canais** | Discord, Mattermost, Telegram, X, em ordem alfabética — uma caixa para cada um, com o seu próprio Salvar |
| **Áudio** | Motor de transcrição, provedor, download de modelos, idioma e retenção do áudio do Telegram |
| **Ferramentas** | As ferramentas instaladas, agrupadas em subabas como Automação e Navegador |
| **Agentes** | Configurações para todos os agentes de uma vez, e o repositório e o branch de onde vêm os modelos. Guardadas no servidor: uma execução iniciada pelo cron não tem navegador de onde ler uma preferência |
| **Conversa** | Como a caixa de mensagem se comporta: se o Enter envia, se cada resposta mostra quanto custou |
| **Kanban** | Quantos cartões cada coluna mostra, e se os excluídos recentemente devem ser listados |
| **Interface** | Tema, idioma, quanto tempo uma mensagem pop-up fica na tela, e se o **+** pergunta de onde parte um novo agente |

Em **Sistema operacional**, os estados dos serviços ficam alinhados com a
segunda coluna de **Esta máquina**.

As preferências de Conversa, Kanban e Interface ficam guardadas no seu
navegador, e não no servidor: elas descrevem como você trabalha nesta máquina,
e um celular e um computador podem, com razão, discordar.

### Transcrição de áudio

No Alpine, a instalação e as atualizações devolvem o controle da sessão SSH quando terminam; o OpenRC mantém os serviços rodando.

Abra **Configurações → Áudio**. Essas configurações ficam guardadas no servidor e se aplicam às mensagens de voz e aos arquivos de áudio recebidos pelo Telegram.

1. Escolha **Local · whisper.cpp** ou **API de um provedor**. A transcrição começa desativada.
2. Para o reconhecimento local, escolha um modelo e clique em **Baixar modelo**, se necessário. O instalador prepara o `base`; o seletor oferece todos os 30 modelos oficiais, incluindo as variantes `.en` só em inglês e as quantizadas, mais os modelos `ggml-*.bin` instalados manualmente em `/opt/boa/whisper/models/`. O tamanho e o estado da instalação são mostrados. Modelos maiores precisam de mais memória e tempo de CPU.
3. Para uma API, salve antes a chave dela em **Chaves de API**. OpenAI, Groq, Mistral, Together AI, Hugging Face e Cloudflare aparecem quando há uma chave salva. Escolha uma sugestão ou digite outro identificador de modelo de transcrição desse provedor. A Cloudflare oferece as suas duas variantes de Whisper suportadas e usa uma credencial `account-id:api-token`.
4. Escolha o idioma (`auto` ou um código como `en`), a duração máxima e se o áudio deve ser guardado para reprodução; clique em **Salvar**. Responda com uma mensagem de voz a uma mensagem de um agente no Telegram para testar. Você também pode selecionar o agente antes com `/agents`.

O limite inicial é de 600 segundos, configurável de 30 a 3.600; o arquivo recebido não pode passar de 20 MiB. O processamento acontece em segundo plano e a fila sobrevive a uma atualização. Um agente ocupado recebe o texto salvo quando ele estiver disponível. Um nome de agente falado dentro da gravação não muda o destino dela.

A conversa web exibe a transcrição e, quando a retenção está ativada, um player. Uma cópia em Ogg para reprodução é guardada atrás do login. Desativar a retenção guarda só o texto das novas mensagens. Limpar uma conversa remove o áudio salvo das tarefas concluídas. Os backups incluem esse áudio; os modelos baixados sobrevivem às atualizações, mas não entram no backup. Depois de restaurar em outra máquina, baixe em Áudio qualquer modelo adicional que esteja faltando.

O reconhecimento local processa o áudio no seu servidor. O reconhecimento por API o envia ao provedor selecionado e pode gerar cobranças separadas do uso do modelo do agente. Uma falha local nunca passa automaticamente para um provedor na nuvem. O Whisper transcreve, e não traduz; os modelos `.en` só entendem inglês. A entrada de áudio é pelo Telegram; a conversa web exibe o resultado sem acrescentar um botão de gravação.

Numa instalação existente, execute o instalador da sua distribuição como root com `--update`. Ele instala o FFmpeg, o whisper.cpp e o modelo base em `/opt/boa/whisper/`; a transcrição continua desativada até ser configurada.

### Idiomas

A interface vem em quinze:

| | | |
|---|---|---|
| Deutsch (Deutschland) | English (United Kingdom) | English (United States) |
| Español (Argentina) | Español (España) | Français (France) |
| עברית (ישראל) | हिन्दी (भारत) | Italiano (Italia) |
| 日本語 (日本) | 한국어 (대한민국) | Português (Brasil) |
| Português (Portugal) | Русский (Россия) | 简体中文 (中国) |

O hebraico se escreve da direita para a esquerda, e escolhê-lo espelha a
interface inteira: a barra lateral passa para a direita e todo o resto a
acompanha. Código, caminhos e comandos continuam da esquerda para a direita, e
cada mensagem do chat segue o próprio idioma, de modo que uma resposta em inglês
ainda se lê da esquerda para a direita numa página em hebraico.

**Configurações → Interface → Idioma** escolhe um, e ele fica guardado no seu
navegador, como o tema. Um navegador que nunca escolheu recebe o mais próximo
do que ele pede, e inglês quando não há nenhum.

Duas outras coisas seguem o idioma e **não** são uma preferência do navegador,
porque uma execução iniciada pelo cron não tem navegador:

- **Configurações → Agentes → Idioma em que os agentes respondem** acrescenta
  uma linha ao prompt de sistema de todos os agentes, escrita nesse idioma.
- Os **bots do Telegram e do Discord** também falam esse idioma: as próprias
  frases deles, o relatório de `/status`
  e o texto de ajuda.

## Mensagens pop-up

Quando algo é salvo, a confirmação aparece no meio do painel que você está
olhando e depois some sozinha. Ela fica no caminho de propósito: o botão
Salvar no pé de uma aba longa produzia antes uma linha bem no topo da página,
várias telas acima de onde você estava olhando, então salvar parecia não ter
feito nada.

**Configurações → Interface → Segundos que uma mensagem pop-up fica na tela**
define quanto tempo, entre 1 e 30 segundos. Três é o padrão: tempo suficiente
para ler `Settings saved`, e curto o bastante para não ficar em cima da caixa
em que você ia digitar.

As mensagens de erro ignoram esse número. Elas ficam até você fechá-las, com o
`×` ou com Esc, porque um erro é a única mensagem que tem de continuar ali
quando você volta a olhar para a tela.

A cor diz qual de três coisas aconteceu:

| Cor | O que significa |
|---|---|
| Verde | Foi salvo |
| Âmbar | **Nenhuma alteração para salvar** — você apertou Salvar e nada no formulário tinha mudado |
| Vermelho | Falhou. Diz o que deu errado, e espera ser fechada |

A âmbar vale em todo lugar em que você pode apertar Salvar: **Configurações** —
a conta, o servidor de e-mail, as chaves de API, os canais e as preferências do
navegador — e as configurações de cada agente. Apertar Salvar duas vezes avisa
disso na segunda vez, em vez de anunciar um salvamento que não aconteceu. Um
agente recém-criado é a exceção: o formulário dele contém os valores do modelo
e nunca foi salvo, então Salvar grava esses valores e leva você à conversa
dele.

## Temas

**Configurações → Interface** escolhe a paleta:

| Tema | O que é |
|---|---|
| **Day** | Cinzas suaves com cartões mais claros, para um ambiente iluminado |
| **Night** | A paleta escura, para um ambiente escuro |
| **Day High Contrast** | Fundo branco, texto quase preto, bordas marcadas. Nada é preenchido com a cor de destaque aqui: a caixa de um agente na barra lateral é um contorno, e a sua própria mensagem é preenchida com uma tinta suavizada em vez de azul |
| **Night High Contrast** | Fundo quase preto, texto claro e bordas marcadas. O agente selecionado tem um preenchimento cinza; as abas selecionadas têm um contorno fechado unido à linha de baixo. As suas próprias mensagens usam um branco atenuado |

Um navegador que nunca escolheu começa no que, entre Day e Night, combina com
o sistema operacional, e o acompanha até alguém escolher um. Depois disso, a
escolha fica guardada neste navegador, como o idioma, então um celular e um
computador não precisam concordar.

Um tema é um arquivo CSS em `frontend/themes/` no servidor que redefine as
variáveis `--colour-*`. Colocar um arquivo ali acrescenta um tema — não há
nenhuma lista no código para atualizar. O nome e a descrição dele vêm do
comentário no topo do arquivo:

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

Defina todas. Uma variável que um tema deixa de fora mantém o valor do
app.css — o que, num tema claro, significa uma cor da paleta escura largada no
meio dele.

Todo tema que vem incluído aqui supera o contraste de 4,5:1 em todas as cores
com que pinta texto, e os dois de alto contraste superam 7:1 — WCAG AAA. Há um
teste que falha se algum deixar de fazer isso, cobrado pelo patamar que o nome dele promete. Um tema acrescentado
à mão não é cobrado por isso, mas a mesma pergunta vale para ele: um serviço
marcado como fora do ar num vermelho que ninguém consegue ler é um serviço que
ninguém percebe.

## Quando um cartão é executado

Atribuir um cartão é como você dá trabalho a um agente, e é um serviço
**buzzer** (campainha) que transforma isso numa execução:

    a cada poucos segundos:
      cartões com dono, com um horário que já passou e ainda sem toque
        -> iniciar esse agente, a menos que ele já esteja rodando
        -> registrar o toque no cartão

**Quando**, no formulário de novo cartão, decide o horário:

| Opção | O que acontece |
|---|---|
| **Imediatamente** | O agente é acordado assim que o cartão é salvo. É o padrão: atribuir um cartão é pedir o trabalho |
| **Quando o agente acordar** | O cartão espera no quadro. Ninguém é acordado; o agente o encontra na próxima execução própria |
| **Agendar para um horário** | Um horário em UTC. O agente é acordado nessa hora |

Um agente que já está trabalhando não é interrompido. O cartão mantém a vez e
é tentado de novo na passada seguinte, então uma execução agendada para um
agente ocupado começa alguns segundos atrasada em vez de não começar, e um
agente nunca tem duas execuções ao mesmo tempo. Um cartão toca uma vez só: para
executá-lo de novo, defina o horário dele de novo.

### O cartão aparece na conversa do agente

Quando a execução começa, a conversa do agente recebe uma mensagem que cita o
cartão:

    Foi atribuída a você uma tarefa em um cartão:

    ID do cartão: 1284
    Título: Renovar os certificados
    Qual é a tarefa: “Execute o instalador com --update e relate”
    A executar: Imediatamente

Se foi outro agente que entregou o cartão, a primeira linha diz quem: *manager
atribuiu um novo cartão a você*. Se o cartão foi agendado em vez de pedido na
hora, a última linha mostra o horário: `a2026m03d31@13:45`, em UTC, o mesmo
horário que o quadro mostra no cartão.

A mensagem é escrita **quando a execução começa**, nunca antes. Um cartão que
você agenda para esta noite e exclui hoje à tarde não deixa nada na conversa,
porque nada chegou a rodar.

O agente responde embaixo dela como a qualquer outra mensagem, com o custo da
execução. Três coisas podem colocar uma linha ali sem que o agente tenha feito
nada, e cada uma diz qual foi: o agente estava desligado, ele já tinha gastado
as execuções do dia, ou a execução nem sequer pôde começar. Nenhuma delas é
silenciosa, porque um cartão que foi anunciado e depois ignorado parece
exatamente um agente que não está funcionando.

Uma coisa que essa execução não faz é ler a conversa. As instruções dela são o
cartão. O que você disse antes na conversa só é reenviado quando você mesmo
manda uma mensagem — do contrário, toda execução agendada pagaria por uma
conversa que ninguém está tendo.

Um cartão entregue ao **manager** é tratado de outro jeito: ele é instruído a
decidir quem deve fazer o trabalho e a passar o cartão adiante com
`kanban.assign_card`. O cartão mantém o id, as instruções e o histórico e muda
de mãos, e o agente em que ele cai é acordado para ele. Isso é delegação — não
um segundo cartão para o mesmo trabalho.

## Canais

Em **Configurações → Canais**, configure onde os agentes podem escrever:

| Canal | Do que precisa |
|---|---|
| Discord | um `bot_token` e um `channel_id` para conversar nos dois sentidos, ou uma URL de webhook só para enviar |
| Mattermost | uma URL de webhook de entrada |
| Telegram | o `bot_token` do BotFather e o `chat_id` |
| X | um `bearer_token` |

Cada canal configurado mostra **Configurado** em verde, com a mesma cor de uma
chave de API guardada. Os canais sem configuração mantêm o estado neutro.

As credenciais são guardadas de forma que **nenhum agente consiga lê-las**. Um
agente pede ao servidor que envie; o servidor lê o token e envia. A mensagem
chega precedida do nome do agente, acrescentado pelo servidor, então nenhum
agente consegue se passar por outro.

Depois, na aba **Canais** de cada agente, marque quais canais ele pode usar. Ele precisa
das duas coisas: `channel.write` e o próprio canal.

### Respondendo a um agente pelo Telegram

O Telegram e o Discord são os dois canais que também funcionam no outro sentido. Marque **Deixar que eu
responda aos agentes pelo Telegram** nas configurações dele, salve, e você
poderá responder.

O bot tem três ferramentas no menu, e são elas que o botão `/` oferece:

| Comando | O que faz |
|---|---|
| `/agents` | Lista os seus agentes como botões. Toque num deles para começar a conversar com ele |
| `/status` | Serviços, quadro e cada agente com o modelo, as ferramentas e as habilidades dele |
| `/help` | Esses três, e as outras duas formas de chegar a um agente |

### Ninguém mais vê nada disso

O nome de usuário do bot é público — qualquer pessoa que o encontre pode
abri-lo —, então o menu é escrito **só para a sua conversa**. Outra pessoa que
abra o mesmo bot vê uma conversa vazia: nenhum comando em `/`, nenhuma
descrição, nada para apertar além do botão Começar, que o Telegram desenha em
todo bot e que nenhuma API consegue remover.

Apertá-lo não faz nada. O listener compara o `chat_id` de cada mensagem com o
que está nas suas configurações e descarta o que não bate, antes que qualquer
comando rode e antes que qualquer agente seja escolhido.

**E nada é anotado.** Nenhuma resposta, nenhuma linha no log, nenhum registro
de que alguém tenha escrito. O id de uma conversa que não é sua é dado de outra
pessoa, e guardá-lo significaria a sua instalação montando discretamente uma
lista de quem encontrou o bot.

O preço disso é que um `chat_id` definido errado parece exatamente um
estranho: as suas próprias mensagens são descartadas em silêncio. O
configurado é gravado no log a cada inicialização, e é com ele que se pode
comparar:

```bash
journalctl -u boa-channel-telegram.service | grep "Registered"
```

No Debian, as unidades dos canais usam `boa-channel-<channel>.service`. Execute
o instalador com `--update` para migrar automaticamente os nomes antigos das
unidades. O Alpine mantém os nomes OpenRC `boa-telegram` e `boa-discord`.

O filtro é por **conversa**, não por pessoa. Se o `chat_id` que você configurou
for um grupo, todos os membros desse grupo podem falar com os seus agentes.

### Escolhendo com quem você fala

Toque em `/agents`, toque num agente, e ele responde:

```
Agente os-watcher:

Envíame tus instrucciones...
```

A partir daí, **tudo o que você escrever vai para esse agente** até você
escolher outro. Você pode fazer quatro perguntas seguidas sem citar ninguém, e
é isso que faz disso uma conversa, e não uma linha de comando.

Três formas de se dirigir a alguém, nesta ordem:

1. **Responder a algo que um agente disse** vai para esse agente, seja quem for
   o selecionado. Responda à mensagem dele (deslize-a, ou toque e segure ou clique com o botão direito e escolha Responder), escreva, envie.
2. **Citar um pelo nome** — `@os-watcher check the disk` — vai para ele *e* o
   torna o selecionado. `@001` também funciona, e um nome com espaço também:
   `@News Miner what is new` é um agente, não duas palavras.
3. **Nenhuma das duas** vai para quem você escolheu por último.

Nada mais muda a seleção, então um agente nunca herda a sua conversa só por
ter sido o último a falar. Um agente que você exclui deixa de estar selecionado
em vez de continuar recebendo tudo.

Enquanto você não tiver escolhido ninguém, uma mensagem que não cita ninguém
recebe de volta a lista de agentes, então nada nunca some sem explicação.

### O que volta

O agente responde no Telegram como uma resposta ao que você escreveu, com o
nome dele na primeira linha:

```
os-watcher:
25G free of 28G on /, unchanged since yesterday.
```

**E a troca inteira fica na conversa desse agente na interface web**, a sua
pergunta e a resposta dele, com `(via Telegram)` ao lado do horário no que você
enviou. Uma única tela continua mostrando tudo o que pediram ao agente e tudo o
que ele disse, seja qual for o dispositivo em que cada metade foi digitada.

Duas coisas a esperar:

- **Um agente ocupado avisa.** Se ele já está respondendo a alguma coisa, você
  é informado de que deve tentar de novo daqui a pouco, em vez de ser colocado
  numa fila — uma fila esconderia que um agente está ficando para trás.
- **Só a sua conversa é escutada.** O nome de usuário de um bot é público, e
  qualquer pessoa que o encontre pode escrever para ele. As mensagens de
  qualquer outra conversa são descartadas sem resposta, então o `chat_id` que
  você configurou é o que decide quem pode falar com os seus agentes. Se ele
  estiver errado, não acontece nada.

É long polling, não um webhook: o servidor se conecta para fora, ao Telegram,
então não é preciso abrir nada para a internet para isso funcionar.

Se o Telegram não aceitar a resposta — você bloqueou o bot, o id da conversa
mudou, o token deixou de ser válido —, ela é descartada do Telegram na hora, e
se o Telegram não puder ser alcançado durante uma hora ela também é descartada.
Ela nunca se perde: a conversa inteira, essa resposta incluída, está na
conversa do agente na interface web.

### Como fica a mensagem de um agente

Os modelos escrevem markdown, e o Telegram renderiza um pequeno subconjunto de
HTML, então um é convertido no outro na saída. O que chega é formatado, não
asteriscos:

| O que o agente escreve | O que você vê no celular |
|---|---|
| `**25G free**` | **25G free** |
| `` `df -h` `` | `df -h` em fonte monoespaçada |
| `# Disk report` | uma linha em negrito |
| `- item` | • item |
| uma tabela | um bloco monoespaçado, com as colunas alinhadas |
| ```` ```bash ```` | um bloco de código |
| `[text](https://…)` | um link |

O Telegram não tem título, lista nem tabela próprios, e é por isso que esses
três viram a coisa legível mais próxima em vez de desaparecer.

Se algum dia o Telegram recusar a formatação, **a mensagem é enviada de novo
como texto simples em vez de se perder**. Você recebe as palavras de um jeito
ou de outro; o log do servidor diz o que aconteceu, para que um bug de
formatação apareça em vez de degradar em silêncio para sempre.

Tudo o que o próprio bot diz — a lista de agentes, “ainda respondendo a outra
coisa”, o `/status` — está no idioma definido em **Configurações → Agentes**, o
mesmo em que os agentes respondem.

## Respondendo a um agente pelo Discord

O Discord funciona do mesmo jeito que o Telegram, com um bot seu. Cinco minutos
de configuração, uma vez só.

### Criando o bot

1. Abra <https://discord.com/developers/applications> e aperte **New
   Application**. Dê o nome que quiser.
2. **Bot** na barra lateral, depois **Reset Token**, e copie o que ele mostrar.
   Esse é o `bot_token`, e ele é mostrado uma única vez.
3. **OAuth2 → URL Generator**: marque **bot** e, abaixo dele, **View
   Channels**, **Send Messages** e **Read Message History**. Abra a URL que ele
   monta e adicione o bot ao seu servidor.
4. No próprio Discord, ative **Configurações → Avançado → Modo desenvolvedor**,
   depois clique com o botão direito no canal em que você quer os agentes e
   escolha **Copiar ID do canal**. Esse é o `channel_id`.

Não é preciso mais nada. Em particular, você **não** precisa do Message Content
Intent: esse interruptor é para o Gateway, e isto lê o canal pela API comum.

### Ligando

Em **Configurações → Canais → Discord**, preencha o token e o id do canal,
marque **Deixar que eu responda aos agentes pelo Discord** e salve. Em poucos
segundos o log diz qual bot está escutando e onde:

```bash
journalctl -u boa-channel-discord.service | grep "Listening"      # Debian
tail /opt/boa/logs/boa-discord.log                # Alpine
```

As mensagens escritas antes de você ligá-lo não são respondidas: a primeira
passada anota onde o canal está e começa dali.

### Conversando com um agente

| Comando | O que faz |
|---|---|
| `!agents` | Lista os seus agentes e o que digitar para chegar a cada um |
| `!status` | Serviços, quadro e cada agente com o modelo, as ferramentas e as habilidades dele |
| `!help` | Esses três, e as outras formas de chegar a um agente |

O `/agents` também funciona, se é isso que os seus dedos digitam. Aqui não há
botões nem menu de comandos com barra: as duas coisas são *interações*, que o
Discord só entrega por uma conexão que esta instalação, de propósito, não abre.

As três formas de se dirigir a alguém são as que você já conhece:

1. **Responder a algo que um agente disse** vai para esse agente, seja quem for
   o selecionado. Clique com o botão direito na mensagem dele → Responder, ou
   deslize-a no celular.
2. **Citar um pelo nome** — `@os-watcher check the disk` — vai para ele *e* o
   torna o selecionado. `!os-watcher`, `@001` e `@News Miner what is new`
   funcionam todos.
3. **Nenhuma das duas** vai para quem você escolheu por último.

### O que volta

A resposta chega como uma resposta à sua pergunta, com o nome do agente em
negrito na primeira linha, e **a troca inteira fica na conversa desse agente na
interface web**, com `(via Discord)` ao lado do horário no que você enviou.

Uma resposta longa chega em várias mensagens, em vez de uma só cortada: o
Discord recusa qualquer coisa acima de 2.000 caracteres, então a resposta é
dividida entre linhas, em no máximo quatro mensagens. Você pode responder a
qualquer uma delas e chega ao mesmo agente. Se havia conteúdo para mais de
quatro mensagens, a última termina em `…` — e o texto inteiro está na
interface web, onde foi escrito.

### Quem pode falar com os seus agentes

**Todo mundo que pode escrever nesse canal.** Essa é a única diferença real em
relação ao Telegram, e vale um minuto do seu tempo: lá, o bot compara o id da
conversa de cada mensagem e descarta o que não bate, então um estranho que
encontre o seu bot não recebe nada. Aqui, o bot lê um canal, e qualquer pessoa
que possa postar nele pode iniciar execuções no seu servidor.

Então coloque os agentes num **canal privado** — um que só você, ou você e as
pessoas em quem confia, consigam ver. O bot não precisa de acesso a mais nada.

### Se você só quer alertas

Deixe o token vazio e defina uma **URL de webhook**: **Configurações do canal →
Integrações → Webhooks → Novo webhook → Copiar URL do webhook**. Os agentes
então podem escrever no canal, e só isso. Escutar exige o bot, então o
interruptor é recusado com um webhook em vez de não fazer nada.

## O orquestrador

O `agent-000`, chamado **manager**, é o único agente criado na instalação. É um agente
normal em todos os aspectos, exceto que não pode ser excluído.

O padrão pensado: dê ao manager as ferramentas do kanban e um prompt dizendo
que ele divida objetivos em cartões e os atribua a outros agentes pelo id. Dê
aos outros agentes o `bash.run` e o que mais eles precisarem, e um prompt
dizendo que trabalhem nos cartões atribuídos a eles.

Isso só funciona se os cartões do manager disserem o que significa
“concluído”. Um cartão que não diz é um desejo, e o agente que o pegar vai
decidir sozinho.

## A aba de ferramentas

**Configurações → Ferramentas** mostra o que está instalado no servidor. Cada
família é uma subaba — Automação, Navegador, Canais, E-mail, Imagens, Internet,
Kanban, Memória, Sistema operacional, RAG, Habilidades — com o número de ferramentas que tem, e
cada ferramenta ganha a sua caixa com os argumentos e o que eles significam. A
aba aberta fica na URL (`/settings/?tab=tools&family=mail`), então recarregar a página ou abrir um favorito a mantém.
Os links antigos para `/tools/` redirecionam para cá e mantêm a família selecionada.

Uma ferramenta cuja família ninguém nomeou — um `.py` que alguém colocou em
`/opt/boa/tools/` — vai para **Outros**, com a família escrita na própria
caixa. Ela continua sendo uma ferramenta até a interface; só não ganha uma aba
própria, senão a fileira cresceria a cada script avulso.

Qual agente pode usar qual ferramenta é definido na aba **Ferramentas** de cada
agente, e não aqui.

## A documentação da API

**Documentação da API**, na barra lateral, lista todos os endpoints em
`/api/`, agrupados por área, com os parâmetros e o que cada um responde. Ela é
gerada a partir da própria descrição OpenAPI desta instalação, então não tem
como se distanciar do código: o `openapi.json`, com link no topo, é a mesma
coisa num arquivo que você pode entregar a um gerador de clientes.

Ela está no idioma que você escolheu em **Configurações → Interface**, como o
resto da interface. A especificação em si continua em inglês: nomes de campos,
ids e mensagens de erro estão em inglês em todo este projeto, e um
`openapi.json` traduzido descreveria uma API que não existe.

Os corpos das requisições aparecem como JSON colorido, do jeito que um editor
os mostra: nomes de campos numa cor, valores em outra, e as chaves e vírgulas
esmaecidas, porque são andaime. As cores vêm do tema que você escolheu, e
copiar um bloco continua dando um JSON válido.

A página também pode ser lida sem fazer login, sozinha, sem a barra lateral.
Ela descreve a forma da API, e não nenhum dos seus dados.

## Trabalho que não exige que o agente pense

Alguns trabalhos são recorrentes e mecânicos: verificar um certificado,
rotacionar um log, coletar um número. Acordar um agente para isso custa tokens
toda vez, para chegar a uma conclusão a que um script de shell chega de graça.

Por isso um agente pode escrever scripts para si mesmo e agendá-los. Dê a ele
as ferramentas de **Automação** e ele pode:

1. `script.write` — colocar um script de shell no próprio diretório `scripts/`.
2. `cron.add` — executá-lo num agendamento, no próprio crontab.
3. Ler os resultados na próxima execução e decidir o que eles significam.

O script roda como o usuário Linux desse agente, com as mesmas permissões que o
agente tem, e **não custa nenhum token** — é um script de shell, não uma
chamada ao modelo. O que custa tokens é o agente ler a saída depois e decidir o
que fazer a respeito.

O que ele não pode fazer:

- Agendar qualquer coisa que não sejam os próprios scripts. Um comando livre
  num crontab é algo que ninguém consegue revisar depois.
- Rodar com mais frequência do que a cada 5 minutos. Uma tarefa a cada minuto
  não é um agendamento.
- Mexer na linha que o acorda. Essa é sua, na aba **Cron** dele.

Você vê as duas metades: os scripts na pasta pessoal dele, e as linhas que os
executam na aba Cron, ao lado das suas.

## Para onde vai o relatório de uma execução

Uma execução que você inicia pela conversa responde a você ali. Uma execução
iniciada por um cartão que chegou ao seu horário responde no mesmo lugar. Uma
execução iniciada pelo **próprio crontab** do agente não responde em nenhum
lugar em particular — ninguém perguntou nada a ele —, então:

- **Sempre no Histórico**, em **Últimas execuções**: o que cada execução disse,
  com quanto custou. É ali que você deve olhar quando quiser saber o que um
  agente andou fazendo.
- **Também na conversa, quando vale a pena interromper você**: a execução não
  terminou, ou mudou algo que você veria — um cartão, uma mensagem num canal,
  uma caixa de correio. Uma execução que só olhou as coisas fica no Histórico.
  Do contrário, um agente num crontab de hora em hora publicaria vinte e quatro mensagens
  de “nada a relatar” por dia na conversa.

Essas mensagens dizem, acima delas, que ninguém as pediu, e nunca são
reenviadas ao modelo, então não custam nada na sua próxima mensagem.

**Uma execução que nunca começou também fica no Histórico**, marcada como “não
chegou a começar”. Aperte **Executar agora** num agente cuja chave de API
ainda não foi definida, ou enquanto o agente já está rodando, e a linha no
Histórico diz qual dos dois casos foi. Antes, a tela dizia que a execução tinha
começado e nada mais aparecia, porque o motivo era gravado num lugar que nada
lê. Uma execução que não começou não conta para as execuções do dia do agente,
e também não conta como falha do agente: nada dela rodou.

## A barra de status

A faixa no pé de todas as páginas, que ocupa a largura inteira da janela,
passando também por baixo da barra lateral, trata da instalação como um todo:

- **executor** e **API dos agentes**, verdes quando estão rodando. Se algum
  deles estiver vermelho, os agentes não vão rodar e nada mais na interface vai
  avisar você.
- **agentes**: quantos estão ligados, do total que existe.
- **quadro**: os cartões em cada coluna.
- **tokens hoje**: tudo o que foi gasto desde a meia-noite UTC, somando todos
  os agentes, e quantas execuções isso levou. É esse o número que mostra que um
  agente entrou num laço antes que a fatura mostre.

Na ponta direita da faixa, o símbolo do GitHub e o nome **nipegun** abrem o
repositório do projeto, <https://github.com/nipegun/bunch-of-aigents>, numa
nova aba. A conta com que você entrou não é mostrada: uma instalação só tem
uma, então exibi-la não diria nada que você já não soubesse.

## Em que idioma os seus agentes respondem

Escreva o prompt de cada agente no idioma em que você pensa e ele vai
responder nesse idioma. Isso cobre a conversa. Não cobre uma execução iniciada
pelo próprio crontab do agente: ninguém escreveu para ele em idioma nenhum, e
os prompts que vêm incluídos estão em inglês — então uma instalação usada em
espanhol recebia os relatórios agendados em inglês.

**Configurações → Agentes → Idioma em que os agentes respondem** resolve isso
para todos os agentes de uma vez. Acrescenta uma linha ao prompt de sistema de
cada agente, escrita no idioma que ela pede, dizendo que ela prevalece sobre o
que o prompt disser sobre idiomas. Deixe no padrão e nada muda: cada agente
responde no idioma do próprio prompt.

Ela fica guardada no servidor, ao contrário do idioma desta interface, que é
uma preferência no seu navegador. Uma execução acordada pelo cron não tem
navegador.

## Escrevendo prompts no seu próprio idioma

Escreva o prompt de sistema no idioma em que você pensa. Nada no sistema está
preso ao inglês: o prompt, a memória, a conversa, os títulos dos cartões e as
mensagens entre os serviços são todos UTF-8 de ponta a ponta, acentos e tudo.

O prompt padrão que um agente novo recebe está em inglês, e a última regra dele
diz ao agente que responda no idioma em que o prompt está escrito. Reescreva
tudo no seu idioma e essa regra vai junto — o agente vai seguir o prompt que
tem, e não aquele com que começou.

Os prompts são guardados com linhas inteiras, sem quebra numa coluna fixa. A
caixa de texto as quebra na tela para que continuem legíveis, sem colocar as
quebras de linha no arquivo: uma regra que é uma frase continua sendo uma
linha, e editá-la não significa reorganizar as quebras de um parágrafo.

## Backup e restauração

Tudo o que faz desta instalação a sua fica em `/opt/boa/` e nos usuários Linux
dos agentes. Um comando reúne tudo num único arquivo compactado:

```bash
./install-update-reinstall-debian.sh --backup
```

Ele grava `/root/boa-backup-<date>.tar.gz`, só para `root`, modo 0600, com os
serviços rodando — nada para. Passe um caminho para gravá-lo em outro lugar:
`--backup /mnt/usb/boa.tar.gz`. Dentro dele: os dois bancos de dados, copiados
pela própria API de backup do SQLite para que nada que ainda esteja num
write-ahead log se perca; as chaves dos provedores, os segredos dos canais e o
segredo das sessões; os certificados; cada agente com a pasta pessoal, os
arquivos protegidos, o usuário Linux e o crontab dele; as habilidades e as
ferramentas escritas neste servidor; e o log da instalação, por causa da senha
que está nele. Fora dele: o código, o ambiente Python, o navegador e as duas
escolhas próprias desta máquina — o modo de portas e se ela tem navegador —,
para que uma restauração nunca importe as de outra máquina.

**Guarde-o com o mesmo cuidado que a própria máquina.** Ele contém todas as
chaves de API, todos os tokens dos canais e a senha de login.

Para restaurar, nesta máquina ou numa nova:

```bash
./install-update-reinstall-debian.sh --install       # só numa máquina nova
./install-update-reinstall-debian.sh --restore /root/boa-backup-<date>.tar.gz
```

Ele pede um YES, ou aceita `--yes`. Depois para os serviços, cria de novo os
usuários dos agentes com os mesmos nomes, e com os mesmos ids quando estão
livres, substitui os bancos de dados, as chaves, os certificados, os agentes,
as habilidades e as ferramentas pelos do arquivo, instala os crontabs e inicia
tudo. Entre com o e-mail e a senha do backup: os dois são acrescentados a
`/opt/boa/logs/install.log` sob o título `Credentials of the restored
backup`, e o log inteiro do backup é guardado ao lado como
`install.log.restored-<date>`.

Um agente que esta máquina tinha e o backup não tem mantém a pasta pessoal no
disco e desaparece da interface, porque a lista de agentes está no banco de
dados restaurado. No Alpine são as mesmas duas flags, no
`install-update-reinstall-alpine.sh`.

## Serviços

| Serviço | Roda como | O que faz |
|---|---|---|
| `boa-proxy` | `boa` | HAProxy: faz a terminação do TLS na 11443, redireciona a 11080 e serve as portas web |
| `boa-web` | `boa` | A interface web e a API, num socket Unix atrás do proxy |
| `boa-exec` | `root` | Cria usuários, instala crontabs, inicia as execuções dos agentes |
| `boa-samba` | `root` | Autentica os usuários SMB e serve cada pasta samba/ como o usuário do agente correspondente |
| `boa-agent-api` | `boa` | A porta que os agentes usam para chegar ao quadro e aos canais |
| `boa-buzzer` | `boa` | Vigia o quadro e acorda um agente quando um cartão chega ao seu horário |
| `boa-embeddings` | `boa` | Serve o modelo de vetorização local das bibliotecas de documentos, num socket Unix |
| `boa-rag` | `boa` | Agenda a fila de indexação das bibliotecas de documentos |
| `boa-channel-telegram.service` | `boa` | Escuta no Telegram, para que você possa responder a um agente pelo celular |
| `boa-channel-discord.service` | `boa` | O mesmo para um canal do Discord |

```bash
systemctl status boa-proxy boa-web boa-exec boa-agent-api boa-buzzer \
                 boa-embeddings boa-rag \
                 boa-channel-telegram.service boa-channel-discord.service boa-samba
journalctl -u boa-exec -f
```

As unidades de canais do Debian usam `boa-channel-<channel>.service`.
Atualizar com `--update` para e desativa as unidades de canais antigas antes de
ativar as novas.

Os mesmos processos rodam no Alpine; lá, os serviços de canais continuam sendo
`boa-telegram` e `boa-discord`. São serviços OpenRC supervisionados com
`supervise-daemon`, e o que cada um imprime vai para um arquivo próprio em
`/opt/boa/logs/`, rotacionado toda semana:

```bash
rc-status
rc-service boa-exec status
tail -f /opt/boa/logs/boa-exec.log
```

## Segurança

O projeto parte do princípio de que um agente vai acabar fazendo algo que você
não pretendia, porque ele é um modelo de linguagem com uma shell.

- **Cada agente é um usuário Linux separado**, e a pasta pessoal dele é
  `0700`. Os agentes não conseguem ler os arquivos, os prompts nem as chaves de
  API uns dos outros.
- **`/opt/boa/agents/` é `0711`**, então nenhum agente consegue nem listar
  quais outros agentes existem.
- **Nenhum agente roda como root, nunca.** Só o `boa-exec` roda, e ele aceita
  uma lista fechada de operações por um socket Unix. Entre elas não há nenhuma
  do tipo “execute este comando”.
- **Uma execução é limitada pelo kernel, e não só pelos tetos.** Nenhum agente
  pode ter mais de 1.024 processos e threads, então uma fork bomb para nesse
  número; no Debian cada execução vive num escopo systemd próprio com 2 GiB de
  memória, o que também encerra o que quer que a execução tenha deixado
  rodando quando termina.
- **Os agentes nunca veem as credenciais dos canais.** Um token de bot não é
  uma mensagem: é uma autorização permanente para enviar tudo o que esse bot
  pode enviar. Os agentes pedem à API dos agentes que envie, e ela envia.
- **Os agentes só mexem nos próprios cartões.** Veja [O quadro kanban](#o-quadro-kanban).
- **O `web.fetch` recusa endereços privados**, verificando o IP resolvido e
  verificando de novo a cada redirecionamento, então um agente que lê uma
  página hostil não pode ser levado a chamar a sua rede interna.

Ele foi feito para uma rede local e não deve ser exposto à internet.

## Quando algo não funciona

**Escolhi `--ports direct` e o HAProxy da máquina sumiu.** Ele não sumiu, foi
aposentado: parado, fora de todos os runlevels no Alpine, desativado e
mascarado no Debian, e com o `/etc/haproxy/haproxy.cfg` dele apagado se foi o
instalador que o escreveu, ou guardado como `haproxy.cfg.before-boa.<date>` se
foi você. Nesse modo a aplicação ocupa ela mesma o 80 e o 443, e qualquer outra
coisa que ocupe essas portas a impede de iniciar — um proxy deixado ativo as
tomaria no próximo boot, antes mesmo de a aplicação rodar. O pacote `haproxy`
continua instalado de propósito: o `boa-proxy` é o `/usr/sbin/haproxy`, e nesse
modo é ele que serve o 80 e o 443.

Para voltar atrás, execute o instalador com `--update --ports proxied`: ele
desmascara a unidade, grava de novo a configuração da máquina e a inicia. O seu
arquivo antigo, se havia um, continua ao lado, com o nome `before-boa`.

**O `boa-proxy` reinicia sem parar e nada escuta na 11443.** Leia
`/opt/boa/logs/boa-proxy.log`. Se ele disser `Cannot raise FD limit to 4131`,
o limite rígido de descritores de arquivo desta máquina é menor do que o que o
proxy pediu — um contêiner pequeno, geralmente. Uma instalação feita antes de
isso ser corrigido ainda tem `maxconn 2048` em `/opt/boa/config/haproxy.cfg`.
Executar o instalador com `--update` reescreve o arquivo; para corrigir na
hora:

```bash
sed -i 's/^  maxconn 2048$/  fd-hard-limit 4000/' /opt/boa/config/haproxy.cfg
rc-service boa-proxy restart        # systemctl restart boa-proxy no Debian
```

O HAProxy então se dimensiona a partir dos descritores que realmente pode ter,
o que, com um limite rígido de 4.096, dá cerca de 1.987 conexões — muito mais
do que isto vai precisar algum dia.

**O instalador termina com “Everything is in place but the application does
not answer”.** A instalação está lá e uma página nunca voltou. O log já contém
o motivo:

```bash
sed -n '/Why it did not answer/,$p' /opt/boa/logs/install.log
```

Esse bloco é como a máquina estava naquele momento: o que o curl entendeu da
requisição, se há algo escutando na porta, o estado dos dez serviços e as
últimas linhas do que o proxy e a aplicação web imprimiram. `000` não é um
código HTTP — é o curl dizendo que nunca recebeu um. Um serviço que se diz
`started` ao lado de `nothing is listening on port 11443` é um processo que
morre e é reiniciado a cada poucos segundos, e o log dele, algumas linhas
abaixo, diz por quê.

Uma atualização que falhou aqui já restaurou a versão anterior e a está
rodando. Uma primeira instalação não tem para onde voltar, então deixa tudo no
lugar: corrija o que o bloco indica e execute o instalador de novo com
`--update`.

**O instalador para com “systemd is not running”.** Ele está se recusando a
instalar numa máquina em que o systemd não é o PID 1, porque todo serviço que
ele escreve é uma unidade do systemd e não haveria nada para iniciá-los. Um
Debian normal serve; um contêiner, não, a menos que tenha sido criado para
rodar o systemd:

```bash
apt-get install -y systemd systemd-sysv dbus dbus-user-session
```

e depois crie o contêiner de novo com `/sbin/init` como comando — um contêiner
que já está rodando não pode mudar o seu PID 1. No Alpine isso não acontece: o
instalador de lá adiciona o OpenRC ele mesmo quando a máquina não tem.

**Não acontece nada quando aperto Executar agora.** Olhe os dois pontos no pé
da barra lateral. Se o `executor` estiver vermelho:

```bash
systemctl status boa-exec
journalctl -u boa-exec -n 50
```


**O navegador mostra 503 e os serviços estão todos rodando.** O HAProxy da
máquina marcou o backend como fora do ar. Quase sempre é o `option
ssl-hello-chk` nesse backend: o ClientHello dele é anterior ao TLS 1.2, e a
aplicação o exige. Remova essa linha e recarregue o HAProxy.

**Um agente roda mas não faz nada.** Confira o painel Histórico dele. Depois,
execute-o à mão e acompanhe:

```bash
runuser -u agent-001 -- /opt/boa/venv/bin/python3 \
  /opt/boa/webapp/backend/core/runner.py --agent-id 001
```

Acrescente `--dry-run` para ver o que ele carregaria — provedor, ferramentas,
tetos — sem chamar o modelo.

**Ele diz que não consegue alcançar o modelo.** Para provedores auto-hospedados,
verifique se o servidor está no ar e se a URL base está certa. Para os da
nuvem, verifique se o arquivo da chave existe na pasta pessoal do agente e se
pertence a esse agente.

**Ele diz que uma ferramenta não está disponível para ele.** A ferramenta não
está marcada na página desse agente. O prompt não pode passar por cima disso, e
é justamente essa a ideia.

**Os cartões pararam de aparecer.** Ou a caixa de seleção do kanban está
desmarcada para esse agente, ou a `agent API` está vermelha no pé da barra
lateral:

```bash
systemctl status boa-agent-api
```

**Quero ver tudo o que um agente fez.** O diário dele fica na própria pasta
pessoal:

```bash
cat /opt/boa/agents/001/runs.jsonl
```

Um objeto JSON por linha: quando rodou, quanto gastou, se terminou.

## Licença

MIT. Veja [LICENSE](../LICENSE).
