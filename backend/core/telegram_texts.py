"""What the bot itself says, in the language this installation was set to.

The agents answer in the language they were told to. The bot's own lines - "I
do not know who that is for", "it is still answering something else" - used to
be English whatever that setting said, which in a conversation that is
otherwise in Spanish reads as a different program talking.

Written in markdown, like everything else that goes to Telegram, and rendered
by `telegram_html` on the way out. A list of agents as one long line of plain
text is hard to read on a phone and impossible to act on; as a list, each agent
sits on its own line with its command next to it.

The catalogue is a dictionary here rather than the JSON the browser uses. Those
files hold 470 keys for a web interface and are served to a browser; these are
six sentences read by a background service. `runner.dAnswerLanguageLines` makes
the same choice for the same reason.

Which language: `agent_language` first, because that is the one somebody chose
for the conversation these messages appear in. `language` after it, and English
last - not as a preference, but because a sentence in a language nobody asked
for is still better than no sentence.
"""

from backend.core import db

# The settings that say which language to speak, in the order they are asked.
lLanguageSettings = ["agent_language", "language"]

cDefaultLanguage = "en-US"

# Every language the interface ships. A tag outside this falls back rather than
# producing a KeyError in a service nobody is watching.
lSupportedLanguages = [
  "de-DE", "en-GB", "en-US", "es-AR", "es-ES", "fr-FR", "hi-IN", "it-IT",
  "ja-JP", "ko-KR", "pt-BR", "pt-PT", "ru-RU", "zh-CN",
]

dTexts = {
  "en-US": {
    "audioQueued": "Audio queued for **{name}**. I will transcribe it before passing it to the agent.",
    "audioFailed": "Could not process the audio: {reason}",
    "imageFailed": "Could not deliver the image {name}. Check the attachment in the web chat.",
    "noAgent":
      "**I do not know who that message was for.**\n\n"
      "To answer an agent, swipe its message to the left and write your "
      "reply.\n\n"
      "To start a new conversation, use /agents and pick one.",
    "whatShouldItDo": "Agent **{name}**:\n\nSend me your instructions...",
    "busy":
      "**{name}** is still answering something else. Try again in a moment.",
    "cannotStart": "**{name}** cannot take that right now: {reason}",
    "neverFinished":
      "I never finished answering that. Check this agent's history in the web "
      "interface.",
    "commandAgents": "Available agents",
    "commandStatus": "Server status",
    "commandHelp": "Help for this bot",
    "agentsHeading": "**Available agents:**",
    "agentsNone":
      "**There are no agents yet.** Create one in the web interface.",
    "statusHeading": "**Status**",
    "statusServices": "**Services**",
    "statusServiceUp": "running",
    "statusServiceDown": "**DOWN**",
    "statusBoard": "**Board**: {todo} to do, {doing} doing, {done} done",
    "statusAgents": "**Agents** ({count})",
    "statusAgentOn": "on",
    "statusAgentOff": "off",
    "statusNoModel": "no model yet",
    "statusTools": "tools",
    "statusTool": "tool",
    "statusSkills": "skills",
    "statusSkill": "skill",
    "statusUnreadable": "cannot be read from here",
    "helpText":
      "**What I can do**\n\n"
      "- /agents — list the agents, and tap one to talk to it\n"
      "- /status — how this installation is doing\n"
      "- /help — this message\n\n"
      "You can also write to an agent directly with **@name**, and answer any "
      "message an agent sends by replying to it.",
  },
  "en-GB": {
    "audioQueued": "Audio queued for **{name}**. I will transcribe it before passing it to the agent.",
    "audioFailed": "Could not process the audio: {reason}",
    "imageFailed": "Could not deliver the image {name}. Check the attachment in the web chat.",
    "noAgent":
      "**I do not know who that message was for.**\n\n"
      "To answer an agent, swipe its message to the left and write your "
      "reply.\n\n"
      "To start a new conversation, use /agents and pick one.",
    "whatShouldItDo": "Agent **{name}**:\n\nSend me your instructions...",
    "busy":
      "**{name}** is still answering something else. Try again in a moment.",
    "cannotStart": "**{name}** cannot take that right now: {reason}",
    "neverFinished":
      "I never finished answering that. Check this agent's history in the web "
      "interface.",
    "commandAgents": "Available agents",
    "commandStatus": "Server status",
    "commandHelp": "Help for this bot",
    "agentsHeading": "**Available agents:**",
    "agentsNone":
      "**There are no agents yet.** Create one in the web interface.",
    "statusHeading": "**Status**",
    "statusServices": "**Services**",
    "statusServiceUp": "running",
    "statusServiceDown": "**DOWN**",
    "statusBoard": "**Board**: {todo} to do, {doing} doing, {done} done",
    "statusAgents": "**Agents** ({count})",
    "statusAgentOn": "on",
    "statusAgentOff": "off",
    "statusNoModel": "no model yet",
    "statusTools": "tools",
    "statusTool": "tool",
    "statusSkills": "skills",
    "statusSkill": "skill",
    "statusUnreadable": "cannot be read from here",
    "helpText":
      "**What I can do**\n\n"
      "- /agents — list the agents, and tap one to talk to it\n"
      "- /status — how this installation is doing\n"
      "- /help — this message\n\n"
      "You can also write to an agent directly with **@name**, and answer any "
      "message an agent sends by replying to it.",
  },
  "es-ES": {
    "audioQueued": "Audio en cola para **{name}**. Lo transcribiré antes de entregárselo al agente.",
    "audioFailed": "No se pudo procesar el audio: {reason}",
    "imageFailed": "No se ha podido entregar la imagen {name}. Revisa el adjunto en el chat web.",
    "noAgent":
      "**No sé a quién iba dirigido ese mensaje.**\n\n"
      "Para responder a un agente, desliza su mensaje hacia la izquierda y "
      "escribe tu respuesta.\n\n"
      "Para empezar una conversación nueva, usa /agents y elige uno.",
    "whatShouldItDo": "Agente **{name}**:\n\nEnvíame tus instrucciones...",
    "busy":
      "**{name}** está contestando otra cosa. Inténtalo dentro de un momento.",
    "cannotStart": "**{name}** no puede con eso ahora mismo: {reason}",
    "neverFinished":
      "No llegué a terminar de responder a eso. Mira el historial de este "
      "agente en la interfaz web.",
    "commandAgents": "Agentes disponibles",
    "commandStatus": "Estado del servidor",
    "commandHelp": "Ayuda de este bot",
    "agentsHeading": "**Agentes disponibles:**",
    "agentsNone":
      "**Todavía no hay agentes.** Crea uno en la interfaz web.",
    "statusHeading": "**Estado**",
    "statusServices": "**Servicios**",
    "statusServiceUp": "en marcha",
    "statusServiceDown": "**CAÍDO**",
    "statusBoard": "**Tablero**: {todo} por hacer, {doing} en curso, {done} hechas",
    "statusAgents": "**Agentes** ({count})",
    "statusAgentOn": "encendido",
    "statusAgentOff": "apagado",
    "statusNoModel": "sin modelo todavía",
    "statusTools": "herramientas",
    "statusTool": "herramienta",
    "statusSkills": "habilidades",
    "statusSkill": "habilidad",
    "statusUnreadable": "no se puede leer desde aquí",
    "helpText":
      "**Lo que puedo hacer**\n\n"
      "- /agents — listar los agentes, y tocar uno para hablarle\n"
      "- /status — cómo va esta instalación\n"
      "- /help — este mensaje\n\n"
      "También puedes escribirle a un agente directamente con **@nombre**, y "
      "responder a cualquier mensaje suyo respondiéndole.",
  },
  "es-AR": {
    "audioQueued": "Audio en cola para **{name}**. Lo transcribiré antes de entregárselo al agente.",
    "audioFailed": "No se pudo procesar el audio: {reason}",
    "imageFailed": "No se pudo entregar la imagen {name}. Revisá el adjunto en el chat web.",
    "noAgent":
      "**No sé a quién iba dirigido ese mensaje.**\n\n"
      "Para responderle a un agente, deslizá su mensaje hacia la izquierda y "
      "escribí tu respuesta.\n\n"
      "Para empezar una conversación nueva, usá /agents y elegí uno.",
    "whatShouldItDo": "Agente **{name}**:\n\nEnviame tus instrucciones...",
    "busy":
      "**{name}** está contestando otra cosa. Probá de nuevo en un momento.",
    "cannotStart": "**{name}** no puede con eso ahora mismo: {reason}",
    "neverFinished":
      "No llegué a terminar de responder a eso. Mirá el historial de este "
      "agente en la interfaz web.",
    "commandAgents": "Agentes disponibles",
    "commandStatus": "Estado del servidor",
    "commandHelp": "Ayuda de este bot",
    "agentsHeading": "**Agentes disponibles:**",
    "agentsNone":
      "**Todavía no hay agentes.** Creá uno en la interfaz web.",
    "statusHeading": "**Estado**",
    "statusServices": "**Servicios**",
    "statusServiceUp": "en marcha",
    "statusServiceDown": "**CAÍDO**",
    "statusBoard": "**Tablero**: {todo} por hacer, {doing} en curso, {done} hechas",
    "statusAgents": "**Agentes** ({count})",
    "statusAgentOn": "encendido",
    "statusAgentOff": "apagado",
    "statusNoModel": "sin modelo todavía",
    "statusTools": "herramientas",
    "statusTool": "herramienta",
    "statusSkills": "habilidades",
    "statusSkill": "habilidad",
    "statusUnreadable": "no se puede leer desde acá",
    "helpText":
      "**Lo que puedo hacer**\n\n"
      "- /agents — listar los agentes, y tocar uno para hablarle\n"
      "- /status — cómo va esta instalación\n"
      "- /help — este mensaje\n\n"
      "También podés escribirle a un agente directamente con **@nombre**, y "
      "responderle a cualquier mensaje suyo respondiéndole.",
  },
  "de-DE": {
    "audioQueued": "Audio für **{name}** eingereiht. Ich transkribiere es, bevor der Agent es erhält.",
    "audioFailed": "Audio konnte nicht verarbeitet werden: {reason}",
    "imageFailed": "Das Bild {name} konnte nicht zugestellt werden. Prüfe den Anhang im Webchat.",
    "noAgent":
      "**Ich weiß nicht, für wen diese Nachricht war.**\n\nUm einem "
      "Agenten zu antworten, wische seine Nachricht nach links und "
      "schreib deine Antwort.\n\nFür ein neues Gespräch nimm /agents "
      "und wähle einen aus.",
    "whatShouldItDo": "Agent **{name}**:\n\nSchick mir deine Anweisungen...",
    "busy":
      "**{name}** beantwortet gerade noch etwas anderes. Versuch es "
      "gleich noch einmal.",
    "cannotStart": "**{name}** kann das gerade nicht übernehmen: {reason}",
    "neverFinished":
      "Ich bin mit der Antwort nie fertig geworden. Sieh dir den "
      "Verlauf dieses Agenten in der Weboberfläche an.",
    "commandAgents": "Verfügbare Agenten",
    "commandStatus": "Serverstatus",
    "commandHelp": "Hilfe zu diesem Bot",
    "agentsHeading": "**Verfügbare Agenten:**",
    "agentsNone":
      "**Es gibt noch keine Agenten.** Erstelle einen in der "
      "Weboberfläche.",
    "statusHeading": "**Status**",
    "statusServices": "**Dienste**",
    "statusServiceUp": "läuft",
    "statusServiceDown": "**AUS**",
    "statusBoard": "**Board**: {todo} zu tun, {doing} in Arbeit, {done} erledigt",
    "statusAgents": "**Agenten** ({count})",
    "statusAgentOn": "an",
    "statusAgentOff": "aus",
    "statusNoModel": "noch kein Modell",
    "statusTools": "Werkzeuge",
    "statusTool": "Werkzeug",
    "statusSkills": "Fähigkeiten",
    "statusSkill": "Fähigkeit",
    "statusUnreadable": "von hier aus nicht lesbar",
    "helpText":
      "**Was ich kann**\n\n- /agents — die Agenten auflisten; tippe "
      "einen an, um mit ihm zu reden\n- /status — wie es dieser "
      "Installation geht\n- /help — diese Nachricht\n\nDu kannst einem "
      "Agenten auch direkt mit **@name** schreiben und auf jede seiner "
      "Nachrichten antworten, indem du auf sie antwortest.",
  },
  "fr-FR": {
    "audioQueued": "Audio en attente pour **{name}**. Je le transcrirai avant de le transmettre à l’agent.",
    "audioFailed": "Impossible de traiter l’audio : {reason}",
    "imageFailed": "Impossible de transmettre l’image {name}. Consultez la pièce jointe dans le chat web.",
    "noAgent":
      "**Je ne sais pas à qui ce message était destiné.**\n\nPour "
      "répondre à un agent, faites glisser son message vers la gauche "
      "et écrivez votre réponse.\n\nPour commencer une nouvelle "
      "conversation, utilisez /agents et choisissez-en un.",
    "whatShouldItDo": "Agent **{name}** :\n\nEnvoyez-moi vos instructions...",
    "busy":
      "**{name}** est encore en train de répondre à autre chose. "
      "Réessayez dans un instant.",
    "cannotStart": "**{name}** ne peut pas s'en charger maintenant : {reason}",
    "neverFinished":
      "Je n'ai jamais fini de répondre à cela. Regardez l'historique de "
      "cet agent dans l'interface web.",
    "commandAgents": "Agents disponibles",
    "commandStatus": "État du serveur",
    "commandHelp": "Aide de ce bot",
    "agentsHeading": "**Agents disponibles :**",
    "agentsNone":
      "**Il n'y a pas encore d'agents.** Créez-en un dans l'interface "
      "web.",
    "statusHeading": "**État**",
    "statusServices": "**Services**",
    "statusServiceUp": "en marche",
    "statusServiceDown": "**À L'ARRÊT**",
    "statusBoard": "**Tableau** : {todo} à faire, {doing} en cours, {done} terminées",
    "statusAgents": "**Agents** ({count})",
    "statusAgentOn": "allumé",
    "statusAgentOff": "éteint",
    "statusNoModel": "pas encore de modèle",
    "statusTools": "outils",
    "statusTool": "outil",
    "statusSkills": "compétences",
    "statusSkill": "compétence",
    "statusUnreadable": "illisible d'ici",
    "helpText":
      "**Ce que je sais faire**\n\n- /agents — lister les agents, et en "
      "toucher un pour lui parler\n- /status — comment se porte cette "
      "installation\n- /help — ce message\n\nVous pouvez aussi écrire "
      "directement à un agent avec **@nom**, et répondre à n'importe "
      "quel message d'un agent en y répondant.",
  },
  "it-IT": {
    "audioQueued": "Audio in coda per **{name}**. Lo trascriverò prima di inviarlo all’agente.",
    "audioFailed": "Impossibile elaborare l’audio: {reason}",
    "imageFailed": "Impossibile consegnare l’immagine {name}. Controlla l’allegato nella chat web.",
    "noAgent":
      "**Non so a chi fosse destinato quel messaggio.**\n\nPer "
      "rispondere a un agente, scorri il suo messaggio verso sinistra e "
      "scrivi la tua risposta.\n\nPer cominciare una conversazione "
      "nuova, usa /agents e scegline uno.",
    "whatShouldItDo": "Agente **{name}**:\n\nMandami le tue istruzioni...",
    "busy":
      "**{name}** sta ancora rispondendo a qualcos'altro. Riprova tra "
      "un momento.",
    "cannotStart": "**{name}** adesso non può occuparsene: {reason}",
    "neverFinished":
      "Non ho mai finito di rispondere a quello. Guarda la cronologia "
      "di questo agente nell'interfaccia web.",
    "commandAgents": "Agenti disponibili",
    "commandStatus": "Stato del server",
    "commandHelp": "Aiuto per questo bot",
    "agentsHeading": "**Agenti disponibili:**",
    "agentsNone": "**Non ci sono ancora agenti.** Creane uno nell'interfaccia web.",
    "statusHeading": "**Stato**",
    "statusServices": "**Servizi**",
    "statusServiceUp": "in marcia",
    "statusServiceDown": "**FERMO**",
    "statusBoard": "**Bacheca**: {todo} da fare, {doing} in corso, {done} fatte",
    "statusAgents": "**Agenti** ({count})",
    "statusAgentOn": "acceso",
    "statusAgentOff": "spento",
    "statusNoModel": "ancora nessun modello",
    "statusTools": "strumenti",
    "statusTool": "strumento",
    "statusSkills": "competenze",
    "statusSkill": "competenza",
    "statusUnreadable": "da qui non si legge",
    "helpText":
      "**Che cosa so fare**\n\n- /agents — elencare gli agenti, e "
      "toccarne uno per parlargli\n- /status — come va questa "
      "installazione\n- /help — questo messaggio\n\nPuoi anche scrivere "
      "a un agente direttamente con **@nome**, e rispondere a qualsiasi "
      "messaggio di un agente rispondendogli.",
  },
  "ja-JP": {
    "audioQueued": "**{name}** 宛ての音声をキューに追加しました。文字起こししてからエージェントに渡します。",
    "audioFailed": "音声を処理できませんでした：{reason}",
    "imageFailed": "画像 {name} を送信できませんでした。ウェブチャットの添付ファイルを確認してください。",
    "noAgent":
      "**そのメッセージが誰あてか分かりません。**\n\nエージェントに答えるには、そのメッセージを左にスワイプして返信を書いてください。\n\n新しく話を始めるには "
      "/agents から1人選んでください。",
    "whatShouldItDo": "エージェント **{name}**:\n\n指示を送ってください...",
    "busy": "**{name}** はまだ別のことに答えています。少ししてからもう一度どうぞ。",
    "cannotStart": "**{name}** は今それを引き受けられません: {reason}",
    "neverFinished": "それへの回答を最後まで書けませんでした。ウェブ画面でこのエージェントの履歴を見てください。",
    "commandAgents": "利用できるエージェント",
    "commandStatus": "サーバーの状態",
    "commandHelp": "このボットのヘルプ",
    "agentsHeading": "**利用できるエージェント:**",
    "agentsNone": "**まだエージェントがいません。** ウェブ画面で作成してください。",
    "statusHeading": "**状態**",
    "statusServices": "**サービス**",
    "statusServiceUp": "稼働中",
    "statusServiceDown": "**停止**",
    "statusBoard": "**ボード**: 未着手 {todo}、作業中 {doing}、完了 {done}",
    "statusAgents": "**エージェント** ({count})",
    "statusAgentOn": "オン",
    "statusAgentOff": "オフ",
    "statusNoModel": "モデル未設定",
    "statusTools": "ツール",
    "statusTool": "ツール",
    "statusSkills": "スキル",
    "statusSkill": "スキル",
    "statusUnreadable": "ここからは読めません",
    "helpText":
      "**できること**\n\n- /agents — エージェントの一覧。1人を選ぶと話しかけられます\n- /status — "
      "このインストールの調子\n- /help — このメッセージ\n\n**@名前** "
      "で直接エージェントに書くこともできますし、エージェントのメッセージに返信すればそのまま答えられます。",
  },
  "ko-KR": {
    "audioQueued": "**{name}**에게 보낼 오디오를 대기열에 추가했습니다. 전사한 후 에이전트에게 전달하겠습니다.",
    "audioFailed": "오디오를 처리하지 못했습니다: {reason}",
    "imageFailed": "이미지 {name}을(를) 전송하지 못했습니다. 웹 채팅에서 첨부 파일을 확인하세요.",
    "noAgent":
      "**그 메시지가 누구에게 간 것인지 모르겠습니다.**\n\n에이전트에게 답하려면 그 메시지를 왼쪽으로 밀고 답장을 "
      "쓰세요.\n\n새 대화를 시작하려면 /agents로 하나 고르세요.",
    "whatShouldItDo": "에이전트 **{name}**:\n\n지시를 보내 주세요...",
    "busy": "**{name}**은(는) 아직 다른 일에 답하는 중입니다. 잠시 뒤에 다시 해 보세요.",
    "cannotStart": "**{name}**은(는) 지금 그것을 맡을 수 없습니다: {reason}",
    "neverFinished": "그 답을 끝내 마치지 못했습니다. 웹 화면에서 이 에이전트의 기록을 보세요.",
    "commandAgents": "사용할 수 있는 에이전트",
    "commandStatus": "서버 상태",
    "commandHelp": "이 봇의 도움말",
    "agentsHeading": "**사용할 수 있는 에이전트:**",
    "agentsNone": "**아직 에이전트가 없습니다.** 웹 화면에서 하나 만드세요.",
    "statusHeading": "**상태**",
    "statusServices": "**서비스**",
    "statusServiceUp": "실행 중",
    "statusServiceDown": "**멈춤**",
    "statusBoard": "**보드**: 할 일 {todo}, 진행 중 {doing}, 완료 {done}",
    "statusAgents": "**에이전트** ({count})",
    "statusAgentOn": "켜짐",
    "statusAgentOff": "꺼짐",
    "statusNoModel": "아직 모델 없음",
    "statusTools": "개 도구",
    "statusTool": "개 도구",
    "statusSkills": "개 스킬",
    "statusSkill": "개 스킬",
    "statusUnreadable": "여기서는 읽을 수 없음",
    "helpText":
      "**제가 할 수 있는 일**\n\n- /agents — 에이전트 목록. 하나를 누르면 대화할 수 있습니다\n- "
      "/status — 이 설치가 어떻게 돌아가는지\n- /help — 이 메시지\n\n**@이름**으로 에이전트에게 "
      "바로 쓸 수도 있고, 에이전트의 어떤 메시지든 답장하면 그대로 이어집니다.",
  },
  "pt-BR": {
    "audioQueued": "Áudio na fila para **{name}**. Vou transcrevê-lo antes de entregá-lo ao agente.",
    "audioFailed": "Não foi possível processar o áudio: {reason}",
    "imageFailed": "Não foi possível entregar a imagem {name}. Confira o anexo no chat web.",
    "noAgent":
      "**Não sei para quem era essa mensagem.**\n\nPara responder a um "
      "agente, arraste a mensagem dele para a esquerda e escreva a sua "
      "resposta.\n\nPara começar uma conversa nova, use /agents e "
      "escolha um.",
    "whatShouldItDo": "Agente **{name}**:\n\nMe mande as suas instruções...",
    "busy":
      "**{name}** ainda está respondendo outra coisa. Tente de novo "
      "daqui a pouco.",
    "cannotStart": "**{name}** não pode assumir isso agora: {reason}",
    "neverFinished":
      "Nunca terminei de responder aquilo. Veja o histórico deste "
      "agente na interface web.",
    "commandAgents": "Agentes disponíveis",
    "commandStatus": "Estado do servidor",
    "commandHelp": "Ajuda deste bot",
    "agentsHeading": "**Agentes disponíveis:**",
    "agentsNone": "**Ainda não há agentes.** Crie um na interface web.",
    "statusHeading": "**Estado**",
    "statusServices": "**Serviços**",
    "statusServiceUp": "em execução",
    "statusServiceDown": "**PARADO**",
    "statusBoard": "**Quadro**: {todo} a fazer, {doing} fazendo, {done} feitas",
    "statusAgents": "**Agentes** ({count})",
    "statusAgentOn": "ligado",
    "statusAgentOff": "desligado",
    "statusNoModel": "ainda sem modelo",
    "statusTools": "ferramentas",
    "statusTool": "ferramenta",
    "statusSkills": "habilidades",
    "statusSkill": "habilidade",
    "statusUnreadable": "não dá para ler daqui",
    "helpText":
      "**O que eu sei fazer**\n\n- /agents — listar os agentes, e tocar "
      "em um para falar com ele\n- /status — como vai esta "
      "instalação\n- /help — esta mensagem\n\nVocê também pode escrever "
      "direto para um agente com **@nome**, e responder qualquer "
      "mensagem de um agente respondendo a ela.",
  },
  "pt-PT": {
    "audioQueued": "Áudio em fila para **{name}**. Vou transcrevê-lo antes de o entregar ao agente.",
    "audioFailed": "Não foi possível processar o áudio: {reason}",
    "imageFailed": "Não foi possível entregar a imagem {name}. Verifica o anexo no chat web.",
    "noAgent":
      "**Não sei para quem era essa mensagem.**\n\nPara responder a um "
      "agente, arraste a mensagem dele para a esquerda e escreva a sua "
      "resposta.\n\nPara começar uma conversa nova, use /agents e "
      "escolha um.",
    "whatShouldItDo": "Agente **{name}**:\n\nEnvie-me as suas instruções...",
    "busy":
      "**{name}** ainda está a responder a outra coisa. Tente outra vez "
      "daqui a pouco.",
    "cannotStart": "**{name}** não pode tratar disso agora: {reason}",
    "neverFinished":
      "Nunca cheguei a acabar de responder àquilo. Veja o histórico "
      "deste agente na interface web.",
    "commandAgents": "Agentes disponíveis",
    "commandStatus": "Estado do servidor",
    "commandHelp": "Ajuda deste bot",
    "agentsHeading": "**Agentes disponíveis:**",
    "agentsNone": "**Ainda não há agentes.** Crie um na interface web.",
    "statusHeading": "**Estado**",
    "statusServices": "**Serviços**",
    "statusServiceUp": "a correr",
    "statusServiceDown": "**PARADO**",
    "statusBoard": "**Quadro**: {todo} por fazer, {doing} em curso, {done} feitas",
    "statusAgents": "**Agentes** ({count})",
    "statusAgentOn": "ligado",
    "statusAgentOff": "desligado",
    "statusNoModel": "ainda sem modelo",
    "statusTools": "ferramentas",
    "statusTool": "ferramenta",
    "statusSkills": "competências",
    "statusSkill": "competência",
    "statusUnreadable": "daqui não se consegue ler",
    "helpText":
      "**O que sei fazer**\n\n- /agents — listar os agentes, e tocar "
      "num para falar com ele\n- /status — como vai esta instalação\n- "
      "/help — esta mensagem\n\nTambém pode escrever directamente a um "
      "agente com **@nome**, e responder a qualquer mensagem de um "
      "agente respondendo-lhe.",
  },
  "ru-RU": {
    "audioQueued": "Аудио для **{name}** добавлено в очередь. Я расшифрую его перед передачей агенту.",
    "audioFailed": "Не удалось обработать аудио: {reason}",
    "imageFailed": "Не удалось отправить изображение {name}. Проверьте вложение в веб-чате.",
    "noAgent":
      "**Я не знаю, кому было это сообщение.**\n\nЧтобы ответить "
      "агенту, проведите по его сообщению влево и напишите "
      "ответ.\n\nЧтобы начать новый разговор, наберите /agents и "
      "выберите агента.",
    "whatShouldItDo": "Агент **{name}**:\n\nПришлите мне ваши указания...",
    "busy": "**{name}** ещё отвечает на другое. Попробуйте через минуту.",
    "cannotStart": "**{name}** сейчас не может за это взяться: {reason}",
    "neverFinished":
      "Я так и не дописал ответ на это. Посмотрите историю этого агента "
      "в веб-интерфейсе.",
    "commandAgents": "Доступные агенты",
    "commandStatus": "Состояние сервера",
    "commandHelp": "Справка по этому боту",
    "agentsHeading": "**Доступные агенты:**",
    "agentsNone": "**Агентов пока нет.** Создайте одного в веб-интерфейсе.",
    "statusHeading": "**Состояние**",
    "statusServices": "**Службы**",
    "statusServiceUp": "работает",
    "statusServiceDown": "**НЕ РАБОТАЕТ**",
    "statusBoard": "**Доска**: {todo} к выполнению, {doing} в работе, {done} готово",
    "statusAgents": "**Агенты** ({count})",
    "statusAgentOn": "вкл",
    "statusAgentOff": "выкл",
    "statusNoModel": "модели пока нет",
    "statusTools": "инструментов",
    "statusTool": "инструмент",
    "statusSkills": "навыков",
    "statusSkill": "навык",
    "statusUnreadable": "отсюда не прочитать",
    "helpText":
      "**Что я умею**\n\n- /agents — показать агентов; нажмите на "
      "одного, чтобы поговорить\n- /status — как дела у этой "
      "установки\n- /help — это сообщение\n\nЕщё можно написать агенту "
      "напрямую через **@имя**, а на любое его сообщение ответить, "
      "ответив на него.",
  },
  "zh-CN": {
    "audioQueued": "已将发给 **{name}** 的音频加入队列。我会先将其转写，再交给代理。",
    "audioFailed": "无法处理音频：{reason}",
    "imageFailed": "无法发送图片 {name}。请检查网页聊天中的附件。",
    "noAgent":
      "**我不知道那条消息是发给谁的。**\n\n要回复某个智能体，把它的消息向左滑动，然后写下你的回复。\n\n要开始新的对话，用 "
      "/agents 选一个。",
    "whatShouldItDo": "智能体 **{name}**：\n\n把你的指示发给我……",
    "busy": "**{name}** 还在回答别的事情。过一会儿再试。",
    "cannotStart": "**{name}** 现在接不了这件事：{reason}",
    "neverFinished": "我一直没把那个回答写完。请在网页界面查看这个智能体的历史。",
    "commandAgents": "可用的智能体",
    "commandStatus": "服务器状态",
    "commandHelp": "这个机器人的帮助",
    "agentsHeading": "**可用的智能体：**",
    "agentsNone": "**还没有智能体。** 请在网页界面创建一个。",
    "statusHeading": "**状态**",
    "statusServices": "**服务**",
    "statusServiceUp": "运行中",
    "statusServiceDown": "**已停止**",
    "statusBoard": "**看板**：待办 {todo}，进行中 {doing}，已完成 {done}",
    "statusAgents": "**智能体** ({count})",
    "statusAgentOn": "开",
    "statusAgentOff": "关",
    "statusNoModel": "尚未设置模型",
    "statusTools": "个工具",
    "statusTool": "个工具",
    "statusSkills": "个技能",
    "statusSkill": "个技能",
    "statusUnreadable": "从这里读不到",
    "helpText":
      "**我能做什么**\n\n- /agents — 列出智能体，点一个就能和它说话\n- /status — "
      "这套安装现在怎么样\n- /help — 这条消息\n\n你也可以用 **@名称** "
      "直接写给某个智能体，或者对它的任何消息直接回复。",
  },
  "hi-IN": {
    "audioQueued": "**{name}** के लिए ऑडियो कतार में है। एजेंट को देने से पहले मैं उसका लिप्यंतरण करूँगा।",
    "audioFailed": "ऑडियो संसाधित नहीं किया जा सका: {reason}",
    "imageFailed": "चित्र {name} भेजा नहीं जा सका। वेब चैट में संलग्न फ़ाइल देखें।",
    "noAgent":
      "**मुझे नहीं पता कि वह संदेश किसके लिए था।**\n\nकिसी एजेंट को "
      "जवाब देने के लिए उसके संदेश को बाएँ खिसकाएँ और अपना जवाब "
      "लिखें।\n\nनई बातचीत शुरू करने के लिए /agents से एक एजेंट चुनें।",
    "whatShouldItDo": "एजेंट **{name}**:\n\nमुझे अपने निर्देश भेजें...",
    "busy":
      "**{name}** अभी किसी और बात का जवाब दे रहा है। थोड़ी देर बाद फिर "
      "कोशिश करें।",
    "cannotStart": "**{name}** अभी यह काम नहीं ले सकता: {reason}",
    "neverFinished":
      "मैं उसका जवाब कभी पूरा नहीं कर पाया। वेब इंटरफ़ेस में इस एजेंट "
      "का इतिहास देखें।",
    "commandAgents": "उपलब्ध एजेंट",
    "commandStatus": "सर्वर की स्थिति",
    "commandHelp": "इस बॉट की मदद",
    "agentsHeading": "**उपलब्ध एजेंट:**",
    "agentsNone": "**अभी कोई एजेंट नहीं है।** वेब इंटरफ़ेस में एक बनाएँ।",
    "statusHeading": "**स्थिति**",
    "statusServices": "**सेवाएँ**",
    "statusServiceUp": "चल रही है",
    "statusServiceDown": "**बंद**",
    "statusBoard": "**बोर्ड**: {todo} करना है, {doing} चल रहा है, {done} हो गया",
    "statusAgents": "**एजेंट** ({count})",
    "statusAgentOn": "चालू",
    "statusAgentOff": "बंद",
    "statusNoModel": "अभी कोई मॉडल नहीं",
    "statusTools": "टूल",
    "statusTool": "टूल",
    "statusSkills": "कौशल",
    "statusSkill": "कौशल",
    "statusUnreadable": "यहाँ से नहीं पढ़ा जा सकता",
    "helpText":
      "**मैं क्या कर सकता हूँ**\n\n- /agents — एजेंटों की सूची; किसी एक "
      "को छूकर उससे बात करें\n- /status — इस इंस्टॉलेशन का हाल\n- /help "
      "— यही संदेश\n\nआप किसी एजेंट को **@नाम** से सीधे लिख भी सकते "
      "हैं, और उसके किसी भी संदेश का जवाब उसी पर रिप्लाई करके दे सकते "
      "हैं।",
  },
}


def fReadLanguage():
  """Return the language tag the bot should speak."""
  for vSetting in lLanguageSettings:
    vLanguage = db.fReadSetting(vSetting)
    if vLanguage in lSupportedLanguages:
      return vLanguage
  return cDefaultLanguage


def fText(pKey, pLanguage=None, **pdValues):
  """Return one of the bot's lines, filled in.

  An unknown key is a bug, and returning the key itself is how that bug
  reaches somebody's phone instead of raising in a service nobody is reading
  the log of.
  """
  vLanguage = pLanguage or fReadLanguage()
  dCatalogue = dTexts.get(vLanguage) or dTexts[cDefaultLanguage]
  vTemplate = dCatalogue.get(pKey) or dTexts[cDefaultLanguage].get(pKey)
  if vTemplate is None:
    return str(pKey)
  try:
    return vTemplate.format(**pdValues)
  except (KeyError, IndexError):
    return vTemplate
