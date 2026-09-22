"""What the Discord bot says, where it does not say what the Telegram one says.

Nearly all of it is the same catalogue. "It is still answering something
else", "I never finished answering that", the whole status report - none of
that is about which network the sentence travels over, and a second copy of
thirty sentences in fourteen languages is a second copy that stops matching
the first.

So this module holds only what Discord makes different, and `fText` falls
through to `telegram_texts` for everything else. Three keys differ, and each
for a reason a reader can check:

  noAgent       : Telegram says "swipe its message to the left". Discord has
                  no swipe on the desktop, where most of its users are; there
                  a reply is the right-click menu.
  helpText      : the commands are `!agents`, `!status` and `!help`. Discord
                  reserves `/` for application commands, which need either the
                  Gateway or a public HTTPS endpoint to receive - neither of
                  which an installation on a LAN has. `/agents` typed anyway
                  still works, because the listener accepts both.
  agentsHeading : Telegram puts a button under each name. There are no buttons
                  here for the same reason there are no slash commands, so the
                  heading has to say what to type instead.

Which language is decided by `telegram_texts.fReadLanguage`, so both bots
speak the language this installation was set to and there is one setting, not
two.
"""

from backend.core import telegram_texts

cDefaultLanguage = telegram_texts.cDefaultLanguage

# Only the keys Discord says differently. Anything missing here is answered by
# the Telegram catalogue, which is the shared one.
dTexts = {
  "en-US": {
    "noAgent":
      "**I do not know who that message was for.**\n\n"
      "To answer an agent, reply to its message and write your reply.\n\n"
      "To start a new conversation, write **@name**, or use !agents to see "
      "them.",
    "helpText":
      "**What I can do**\n\n"
      "- !agents — list the agents\n"
      "- !status — how this installation is doing\n"
      "- !help — this message\n\n"
      "Write to an agent with **@name**, and answer any message an agent "
      "sends by replying to it.",
    "agentsHeading":
      "**Available agents:**\n_Write @name to talk to one._",
  },
  "en-GB": {
    "noAgent":
      "**I do not know who that message was for.**\n\n"
      "To answer an agent, reply to its message and write your reply.\n\n"
      "To start a new conversation, write **@name**, or use !agents to see "
      "them.",
    "helpText":
      "**What I can do**\n\n"
      "- !agents — list the agents\n"
      "- !status — how this installation is doing\n"
      "- !help — this message\n\n"
      "Write to an agent with **@name**, and answer any message an agent "
      "sends by replying to it.",
    "agentsHeading":
      "**Available agents:**\n_Write @name to talk to one._",
  },
  "es-ES": {
    "noAgent":
      "**No sé a quién iba dirigido ese mensaje.**\n\n"
      "Para responder a un agente, responde a su mensaje y escribe tu "
      "respuesta.\n\n"
      "Para empezar una conversación nueva, escribe **@nombre**, o usa "
      "!agents para verlos.",
    "helpText":
      "**Lo que puedo hacer**\n\n"
      "- !agents — listar los agentes\n"
      "- !status — cómo va esta instalación\n"
      "- !help — este mensaje\n\n"
      "Escríbele a un agente con **@nombre**, y responde a cualquier mensaje "
      "suyo respondiéndole.",
    "agentsHeading":
      "**Agentes disponibles:**\n_Escribe @nombre para hablar con uno._",
  },
  "es-AR": {
    "noAgent":
      "**No sé a quién iba dirigido ese mensaje.**\n\n"
      "Para responderle a un agente, respondé a su mensaje y escribí tu "
      "respuesta.\n\n"
      "Para empezar una conversación nueva, escribí **@nombre**, o usá "
      "!agents para verlos.",
    "helpText":
      "**Lo que puedo hacer**\n\n"
      "- !agents — listar los agentes\n"
      "- !status — cómo va esta instalación\n"
      "- !help — este mensaje\n\n"
      "Escribile a un agente con **@nombre**, y respondele a cualquier "
      "mensaje suyo respondiéndole.",
    "agentsHeading":
      "**Agentes disponibles:**\n_Escribí @nombre para hablar con uno._",
  },
  "de-DE": {
    "noAgent":
      "**Ich weiß nicht, für wen diese Nachricht war.**\n\n"
      "Um einem Agenten zu antworten, antworte auf seine Nachricht und "
      "schreib deine Antwort.\n\n"
      "Für ein neues Gespräch schreib **@name**, oder nimm !agents, um sie zu "
      "sehen.",
    "helpText":
      "**Was ich kann**\n\n"
      "- !agents — die Agenten auflisten\n"
      "- !status — wie es dieser Installation geht\n"
      "- !help — diese Nachricht\n\n"
      "Schreib einem Agenten mit **@name**, und antworte auf jede seiner "
      "Nachrichten, indem du auf sie antwortest.",
    "agentsHeading":
      "**Verfügbare Agenten:**\n_Schreib @name, um mit einem zu reden._",
  },
  "fr-FR": {
    "noAgent":
      "**Je ne sais pas à qui ce message était destiné.**\n\n"
      "Pour répondre à un agent, répondez à son message et écrivez votre "
      "réponse.\n\n"
      "Pour commencer une nouvelle conversation, écrivez **@nom**, ou faites "
      "!agents pour les voir.",
    "helpText":
      "**Ce que je sais faire**\n\n"
      "- !agents — lister les agents\n"
      "- !status — comment se porte cette installation\n"
      "- !help — ce message\n\n"
      "Écrivez à un agent avec **@nom**, et répondez à n'importe quel message "
      "d'un agent en y répondant.",
    "agentsHeading":
      "**Agents disponibles :**\n_Écrivez @nom pour parler à l'un d'eux._",
  },
  "it-IT": {
    "noAgent":
      "**Non so a chi fosse destinato quel messaggio.**\n\n"
      "Per rispondere a un agente, rispondi al suo messaggio e scrivi la tua "
      "risposta.\n\n"
      "Per cominciare una conversazione nuova, scrivi **@nome**, oppure usa "
      "!agents per vederli.",
    "helpText":
      "**Che cosa so fare**\n\n"
      "- !agents — elencare gli agenti\n"
      "- !status — come va questa installazione\n"
      "- !help — questo messaggio\n\n"
      "Scrivi a un agente con **@nome**, e rispondi a qualsiasi messaggio di "
      "un agente rispondendogli.",
    "agentsHeading":
      "**Agenti disponibili:**\n_Scrivi @nome per parlare con uno._",
  },
  "ja-JP": {
    "noAgent":
      "**そのメッセージが誰あてか分かりません。**\n\n"
      "エージェントに答えるには、そのメッセージに返信して答えを書いてください。\n\n"
      "新しく話を始めるには **@名前** と書くか、!agents で一覧を見てください。",
    "helpText":
      "**できること**\n\n"
      "- !agents — エージェントの一覧\n"
      "- !status — このインストールの調子\n"
      "- !help — このメッセージ\n\n"
      "**@名前** でエージェントに書けます。エージェントのメッセージに返信すれば"
      "そのまま答えられます。",
    "agentsHeading":
      "**利用できるエージェント:**\n_@名前 と書くと話しかけられます。_",
  },
  "ko-KR": {
    "noAgent":
      "**그 메시지가 누구에게 간 것인지 모르겠습니다.**\n\n"
      "에이전트에게 답하려면 그 메시지에 답장하고 답을 쓰세요.\n\n"
      "새 대화를 시작하려면 **@이름**이라고 쓰거나 !agents로 목록을 보세요.",
    "helpText":
      "**제가 할 수 있는 일**\n\n"
      "- !agents — 에이전트 목록\n"
      "- !status — 이 설치가 어떻게 돌아가는지\n"
      "- !help — 이 메시지\n\n"
      "**@이름**으로 에이전트에게 쓸 수 있고, 에이전트의 어떤 메시지든 답장하면 "
      "그대로 이어집니다.",
    "agentsHeading":
      "**사용할 수 있는 에이전트:**\n_@이름이라고 쓰면 대화할 수 있습니다._",
  },
  "pt-BR": {
    "noAgent":
      "**Não sei para quem era essa mensagem.**\n\n"
      "Para responder a um agente, responda à mensagem dele e escreva a sua "
      "resposta.\n\n"
      "Para começar uma conversa nova, escreva **@nome**, ou use !agents para "
      "vê-los.",
    "helpText":
      "**O que eu sei fazer**\n\n"
      "- !agents — listar os agentes\n"
      "- !status — como vai esta instalação\n"
      "- !help — esta mensagem\n\n"
      "Escreva para um agente com **@nome**, e responda qualquer mensagem de "
      "um agente respondendo a ela.",
    "agentsHeading":
      "**Agentes disponíveis:**\n_Escreva @nome para falar com um._",
  },
  "pt-PT": {
    "noAgent":
      "**Não sei para quem era essa mensagem.**\n\n"
      "Para responder a um agente, responda à mensagem dele e escreva a sua "
      "resposta.\n\n"
      "Para começar uma conversa nova, escreva **@nome**, ou use !agents para "
      "os ver.",
    "helpText":
      "**O que sei fazer**\n\n"
      "- !agents — listar os agentes\n"
      "- !status — como vai esta instalação\n"
      "- !help — esta mensagem\n\n"
      "Escreva a um agente com **@nome**, e responda a qualquer mensagem de "
      "um agente respondendo-lhe.",
    "agentsHeading":
      "**Agentes disponíveis:**\n_Escreva @nome para falar com um._",
  },
  "ru-RU": {
    "noAgent":
      "**Я не знаю, кому было это сообщение.**\n\n"
      "Чтобы ответить агенту, ответьте на его сообщение и напишите ответ.\n\n"
      "Чтобы начать новый разговор, напишите **@имя** или наберите !agents, "
      "чтобы их увидеть.",
    "helpText":
      "**Что я умею**\n\n"
      "- !agents — показать агентов\n"
      "- !status — как дела у этой установки\n"
      "- !help — это сообщение\n\n"
      "Пишите агенту через **@имя**, а на любое его сообщение отвечайте, "
      "ответив на него.",
    "agentsHeading":
      "**Доступные агенты:**\n_Напишите @имя, чтобы поговорить с агентом._",
  },
  "zh-CN": {
    "noAgent":
      "**我不知道那条消息是发给谁的。**\n\n"
      "要回复某个智能体，对它的消息点回复，然后写下你的回复。\n\n"
      "要开始新的对话，写 **@名称**，或者用 !agents 看看有哪些。",
    "helpText":
      "**我能做什么**\n\n"
      "- !agents — 列出智能体\n"
      "- !status — 这套安装现在怎么样\n"
      "- !help — 这条消息\n\n"
      "用 **@名称** 写给某个智能体，或者对它的任何消息直接回复。",
    "agentsHeading":
      "**可用的智能体：**\n_写 @名称 就能和它说话。_",
  },
  "hi-IN": {
    "noAgent":
      "**मुझे नहीं पता कि वह संदेश किसके लिए था।**\n\n"
      "किसी एजेंट को जवाब देने के लिए उसके संदेश पर रिप्लाई करें और अपना जवाब "
      "लिखें।\n\n"
      "नई बातचीत शुरू करने के लिए **@नाम** लिखें, या !agents से सूची देखें।",
    "helpText":
      "**मैं क्या कर सकता हूँ**\n\n"
      "- !agents — एजेंटों की सूची\n"
      "- !status — इस इंस्टॉलेशन का हाल\n"
      "- !help — यही संदेश\n\n"
      "किसी एजेंट को **@नाम** से लिखें, और उसके किसी भी संदेश का जवाब उसी पर "
      "रिप्लाई करके दें।",
    "agentsHeading":
      "**उपलब्ध एजेंट:**\n_किसी से बात करने के लिए @नाम लिखें।_",
  },
}


def fText(pKey, pLanguage=None, **pdValues):
  """Return one of the bot's lines, filled in.

  This catalogue first, the Telegram one after it. A key neither of them has
  comes back as the key itself, which is what `telegram_texts` already does:
  a background service nobody is watching must not stop over a missing string.
  """
  vLanguage = pLanguage or telegram_texts.fReadLanguage()
  dOwn = dTexts.get(vLanguage) or dTexts.get(cDefaultLanguage) or {}
  if pKey in dOwn:
    vText = dOwn[pKey]
    try:
      return vText.format(**pdValues) if pdValues else vText
    except (KeyError, IndexError, ValueError):
      return vText
  return telegram_texts.fText(pKey, vLanguage, **pdValues)
