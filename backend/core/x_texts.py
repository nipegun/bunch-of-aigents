"""Plain-text X commands; agent selection persists within the authorized DM.

!post and !discard answer a post an agent asked for (x_posts).
"""

from backend.core import discord_texts, telegram_texts

dHelp = {
  "en-US": "!agents lists agents; !status shows system status; !help shows this help. Write @name followed by your request. Later messages go to that agent until you choose another with @name. Replies here are private direct messages. !post CODE publishes a post an agent asked for; !discard CODE discards it.",
  "en-GB": "!agents lists agents; !status shows system status; !help shows this help. Write @name followed by your request. Later messages go to that agent until you choose another with @name. Replies here are private direct messages. !post CODE publishes a post an agent asked for; !discard CODE discards it.",
  "es-ES": "!agents lista los agentes; !status muestra el estado del sistema; !help muestra esta ayuda. Escribe @nombre seguido de tu petición. Los mensajes siguientes van a ese agente hasta que elijas otro con @nombre. Las respuestas aquí son mensajes directos privados. !post CÓDIGO publica lo que un agente ha pedido publicar; !discard CÓDIGO lo descarta.",
  "es-AR": "!agents lista los agentes; !status muestra el estado del sistema; !help muestra esta ayuda. Escribí @nombre seguido de tu pedido. Los mensajes siguientes van a ese agente hasta que elijas otro con @nombre. Las respuestas acá son mensajes directos privados. !post CÓDIGO publica lo que un agente pidió publicar; !discard CÓDIGO lo descarta.",
  "de-DE": "!agents listet die Agenten auf; !status zeigt den Systemstatus; !help zeigt diese Hilfe. Schreibe @Name und deine Anfrage. Weitere Nachrichten gehen an diesen Agenten, bis du mit @Name einen anderen auswählst. Antworten hier sind private Direktnachrichten. !post CODE veröffentlicht einen von einem Agenten angefragten Beitrag; !discard CODE verwirft ihn.",
  "fr-FR": "!agents liste les agents ; !status affiche l’état du système ; !help affiche cette aide. Écrivez @nom suivi de votre demande. Les messages suivants vont à cet agent jusqu’à la sélection d’un autre avec @nom. Les réponses ici sont des messages privés. !post CODE publie ce qu’un agent a demandé à publier ; !discard CODE l’écarte.",
  "he-IL": "!agents מציג את הסוכנים; !status מציג את מצב המערכת; !help מציג עזרה זו. יש לכתוב @שם ואחריו את הבקשה. ההודעות הבאות נשלחות לאותו סוכן עד לבחירת אחר באמצעות @שם. התשובות כאן הן הודעות פרטיות. !post קוד מפרסם את מה שסוכן ביקש לפרסם; !discard קוד מבטל אותו.",
  "hi-IN": "!agents एजेंटों की सूची दिखाता है; !status सिस्टम की स्थिति दिखाता है; !help यह सहायता दिखाता है। @नाम के बाद अपना अनुरोध लिखें। अगले संदेश उसी एजेंट को जाते हैं, जब तक आप @नाम से दूसरा नहीं चुनते। यहाँ उत्तर निजी संदेशों में आते हैं। !post कोड किसी एजेंट द्वारा माँगी गई पोस्ट प्रकाशित करता है; !discard कोड उसे रद्द करता है।",
  "it-IT": "!agents elenca gli agenti; !status mostra lo stato del sistema; !help mostra questa guida. Scrivi @nome seguito dalla richiesta. I messaggi successivi vanno a quell’agente finché non ne scegli un altro con @nome. Le risposte qui sono messaggi diretti privati. !post CODICE pubblica ciò che un agente ha chiesto di pubblicare; !discard CODICE lo scarta.",
  "ja-JP": "!agents はエージェント一覧、!status はシステム状態、!help はこのヘルプを表示します。@名前に続けて依頼を書いてください。@名前で別のエージェントを選ぶまで、その後のメッセージも同じエージェントに届きます。ここでの返信は非公開のダイレクトメッセージです。!post コード はエージェントが求めた投稿を公開し、!discard コード はそれを破棄します。",
  "ko-KR": "!agents는 에이전트 목록, !status는 시스템 상태, !help는 이 도움말을 표시합니다. @이름 뒤에 요청을 입력하세요. @이름으로 다른 에이전트를 선택할 때까지 이후 메시지도 같은 에이전트에게 전달됩니다. 여기의 답변은 비공개 쪽지입니다. !post 코드는 에이전트가 요청한 게시물을 게시하고, !discard 코드는 이를 취소합니다.",
  "pt-BR": "!agents lista os agentes; !status mostra o estado do sistema; !help mostra esta ajuda. Escreva @nome seguido do pedido. As próximas mensagens vão para esse agente até você escolher outro com @nome. As respostas aqui são mensagens diretas privadas. !post CÓDIGO publica o que um agente pediu para publicar; !discard CÓDIGO descarta.",
  "pt-PT": "!agents lista os agentes; !status mostra o estado do sistema; !help mostra esta ajuda. Escreva @nome seguido do pedido. As mensagens seguintes vão para esse agente até escolher outro com @nome. As respostas aqui são mensagens diretas privadas. !post CÓDIGO publica o que um agente pediu para publicar; !discard CÓDIGO descarta-o.",
  "ru-RU": "!agents выводит список агентов; !status показывает состояние системы; !help показывает эту справку. Напишите @имя и свой запрос. Следующие сообщения идут этому агенту, пока вы не выберете другого через @имя. Ответы здесь приходят в личных сообщениях. !post КОД публикует то, что попросил опубликовать агент; !discard КОД отклоняет.",
  "zh-CN": "!agents 列出智能体；!status 显示系统状态；!help 显示此帮助。输入 @名称并写下请求。在用 @名称选择其他智能体之前，后续消息都会发送给同一个智能体。这里的回复均为私信。!post 代码 发布智能体请求发布的内容；!discard 代码 放弃该内容。",
}


# What answers a post an agent asked for (x_posts): the request with its code,
# and the replies to !post and !discard.
dPostTexts = {
  "de-DE": {
    "postRequest": "{name} möchte dies im X-Profil @{account} veröffentlichen:\n\n{text}\n\nZum Veröffentlichen antworte: !post {code}\nZum Verwerfen: !discard {code}\nDer Code läuft in {minutes} Minuten ab.",
    "postPublished": "Auf X veröffentlicht: {url}",
    "postDiscarded": "Verworfen. Es wurde nichts veröffentlicht.",
    "postUnknownCode": "Für diesen Code wartet kein Beitrag. Jeder Code gilt nur einmal und läuft nach {minutes} Minuten ab.",
    "postUncertain": "X hat den Beitrag nicht bestätigt. Prüfe das Profil: BoA veröffentlicht ihn nicht von sich aus erneut.",
    "postFailed": "X hat den Beitrag nicht veröffentlicht: {reason}",
  },
  "en-GB": {
    "postRequest": "{name} asks to publish this on the X profile @{account}:\n\n{text}\n\nTo publish it, answer: !post {code}\nTo discard it: !discard {code}\nThe code expires in {minutes} minutes.",
    "postPublished": "Published on X: {url}",
    "postDiscarded": "Discarded. Nothing was published.",
    "postUnknownCode": "No post is waiting for that code. Each code works once and expires after {minutes} minutes.",
    "postUncertain": "X did not confirm the post. Check the profile: BoA will not publish it again on its own.",
    "postFailed": "X did not publish the post: {reason}",
  },
  "en-US": {
    "postRequest": "{name} asks to publish this on the X profile @{account}:\n\n{text}\n\nTo publish it, answer: !post {code}\nTo discard it: !discard {code}\nThe code expires in {minutes} minutes.",
    "postPublished": "Published on X: {url}",
    "postDiscarded": "Discarded. Nothing was published.",
    "postUnknownCode": "No post is waiting for that code. Each code works once and expires after {minutes} minutes.",
    "postUncertain": "X did not confirm the post. Check the profile: BoA will not publish it again on its own.",
    "postFailed": "X did not publish the post: {reason}",
  },
  "es-AR": {
    "postRequest": "{name} pide publicar esto en el perfil de X @{account}:\n\n{text}\n\nPara publicarlo, respondé: !post {code}\nPara descartarlo: !discard {code}\nEl código vence en {minutes} minutos.",
    "postPublished": "Publicado en X: {url}",
    "postDiscarded": "Descartado. No se publicó nada.",
    "postUnknownCode": "Ninguna publicación espera ese código. Cada código sirve una sola vez y vence a los {minutes} minutos.",
    "postUncertain": "X no confirmó la publicación. Revisá el perfil: BoA no va a volver a publicarla por su cuenta.",
    "postFailed": "X no publicó el mensaje: {reason}",
  },
  "es-ES": {
    "postRequest": "{name} pide publicar esto en el perfil de X @{account}:\n\n{text}\n\nPara publicarlo, responde: !post {code}\nPara descartarlo: !discard {code}\nEl código caduca en {minutes} minutos.",
    "postPublished": "Publicado en X: {url}",
    "postDiscarded": "Descartado. No se ha publicado nada.",
    "postUnknownCode": "Ninguna publicación espera ese código. Cada código sirve una sola vez y caduca a los {minutes} minutos.",
    "postUncertain": "X no ha confirmado la publicación. Revisa el perfil: BoA no volverá a publicarla por su cuenta.",
    "postFailed": "X no ha publicado el mensaje: {reason}",
  },
  "fr-FR": {
    "postRequest": "{name} demande à publier ceci sur le profil X @{account} :\n\n{text}\n\nPour le publier, répondez : !post {code}\nPour l’écarter : !discard {code}\nLe code expire dans {minutes} minutes.",
    "postPublished": "Publié sur X : {url}",
    "postDiscarded": "Écarté. Rien n’a été publié.",
    "postUnknownCode": "Aucune publication n’attend ce code. Chaque code ne sert qu’une fois et expire au bout de {minutes} minutes.",
    "postUncertain": "X n’a pas confirmé la publication. Vérifiez le profil : BoA ne la publiera pas de nouveau de lui-même.",
    "postFailed": "X n’a pas publié le message : {reason}",
  },
  "he-IL": {
    "postRequest": "{name} מבקש לפרסם את התוכן הבא בפרופיל X @{account}:\n\n{text}\n\nכדי לפרסם, יש להשיב: !post {code}\nכדי לבטל: !discard {code}\nתוקף הקוד יפוג בעוד {minutes} דקות.",
    "postPublished": "פורסם ב-X: {url}",
    "postDiscarded": "בוטל. דבר לא פורסם.",
    "postUnknownCode": "אין פרסום שממתין לקוד הזה. כל קוד תקף פעם אחת בלבד ותוקפו פג לאחר {minutes} דקות.",
    "postUncertain": "X לא אישר את הפרסום. יש לבדוק את הפרופיל: BoA לא יפרסם אותו שוב מעצמו.",
    "postFailed": "X לא פרסם את ההודעה: {reason}",
  },
  "hi-IN": {
    "postRequest": "{name} इसे X प्रोफ़ाइल @{account} पर प्रकाशित करने के लिए कह रहा है:\n\n{text}\n\nप्रकाशित करने के लिए उत्तर दें: !post {code}\nरद्द करने के लिए: !discard {code}\nयह कोड {minutes} मिनट में समाप्त हो जाएगा।",
    "postPublished": "X पर प्रकाशित किया गया: {url}",
    "postDiscarded": "रद्द किया गया। कुछ भी प्रकाशित नहीं हुआ।",
    "postUnknownCode": "इस कोड की प्रतीक्षा में कोई पोस्ट नहीं है। हर कोड केवल एक बार काम करता है और {minutes} मिनट बाद समाप्त हो जाता है।",
    "postUncertain": "X ने पोस्ट की पुष्टि नहीं की। प्रोफ़ाइल जाँचें: BoA इसे अपने आप दोबारा प्रकाशित नहीं करेगा।",
    "postFailed": "X ने पोस्ट प्रकाशित नहीं की: {reason}",
  },
  "it-IT": {
    "postRequest": "{name} chiede di pubblicare questo sul profilo X @{account}:\n\n{text}\n\nPer pubblicarlo, rispondi: !post {code}\nPer scartarlo: !discard {code}\nIl codice scade tra {minutes} minuti.",
    "postPublished": "Pubblicato su X: {url}",
    "postDiscarded": "Scartato. Non è stato pubblicato nulla.",
    "postUnknownCode": "Nessuna pubblicazione attende questo codice. Ogni codice vale una sola volta e scade dopo {minutes} minuti.",
    "postUncertain": "X non ha confermato la pubblicazione. Controlla il profilo: BoA non la pubblicherà di nuovo da solo.",
    "postFailed": "X non ha pubblicato il messaggio: {reason}",
  },
  "ja-JP": {
    "postRequest": "{name} が X のプロフィール @{account} に次の内容を投稿するよう求めています：\n\n{text}\n\n投稿するには次のように返信してください：!post {code}\n破棄するには：!discard {code}\nこのコードは {minutes} 分後に失効します。",
    "postPublished": "X に投稿しました：{url}",
    "postDiscarded": "破棄しました。何も投稿されていません。",
    "postUnknownCode": "このコードを待っている投稿はありません。コードは一度だけ使え、{minutes} 分後に失効します。",
    "postUncertain": "X が投稿を確認しませんでした。プロフィールを確認してください。BoA が自動で再投稿することはありません。",
    "postFailed": "X は投稿しませんでした：{reason}",
  },
  "ko-KR": {
    "postRequest": "{name}이(가) X 프로필 @{account}에 다음 내용을 게시하도록 요청했습니다:\n\n{text}\n\n게시하려면 다음과 같이 답장하세요: !post {code}\n취소하려면: !discard {code}\n이 코드는 {minutes}분 후 만료됩니다.",
    "postPublished": "X에 게시했습니다: {url}",
    "postDiscarded": "취소했습니다. 아무것도 게시되지 않았습니다.",
    "postUnknownCode": "이 코드를 기다리는 게시물이 없습니다. 각 코드는 한 번만 사용할 수 있으며 {minutes}분 후 만료됩니다.",
    "postUncertain": "X가 게시를 확인하지 않았습니다. 프로필을 확인하세요. BoA는 스스로 다시 게시하지 않습니다.",
    "postFailed": "X가 게시하지 않았습니다: {reason}",
  },
  "pt-BR": {
    "postRequest": "{name} pede para publicar isto no perfil do X @{account}:\n\n{text}\n\nPara publicar, responda: !post {code}\nPara descartar: !discard {code}\nO código expira em {minutes} minutos.",
    "postPublished": "Publicado no X: {url}",
    "postDiscarded": "Descartado. Nada foi publicado.",
    "postUnknownCode": "Nenhuma publicação aguarda esse código. Cada código vale uma única vez e expira após {minutes} minutos.",
    "postUncertain": "O X não confirmou a publicação. Verifique o perfil: o BoA não vai publicá-la de novo sozinho.",
    "postFailed": "O X não publicou a mensagem: {reason}",
  },
  "pt-PT": {
    "postRequest": "{name} pede para publicar isto no perfil do X @{account}:\n\n{text}\n\nPara publicar, responda: !post {code}\nPara descartar: !discard {code}\nO código expira dentro de {minutes} minutos.",
    "postPublished": "Publicado no X: {url}",
    "postDiscarded": "Descartado. Nada foi publicado.",
    "postUnknownCode": "Nenhuma publicação aguarda esse código. Cada código só serve uma vez e expira ao fim de {minutes} minutos.",
    "postUncertain": "O X não confirmou a publicação. Verifique o perfil: o BoA não a voltará a publicar por iniciativa própria.",
    "postFailed": "O X não publicou a mensagem: {reason}",
  },
  "ru-RU": {
    "postRequest": "{name} просит опубликовать это в профиле X @{account}:\n\n{text}\n\nЧтобы опубликовать, ответьте: !post {code}\nЧтобы отклонить: !discard {code}\nКод действует {minutes} минут.",
    "postPublished": "Опубликовано в X: {url}",
    "postDiscarded": "Отклонено. Ничего не опубликовано.",
    "postUnknownCode": "Нет публикации, ожидающей этот код. Каждый код действует один раз и истекает через {minutes} минут.",
    "postUncertain": "X не подтвердил публикацию. Проверьте профиль: BoA не будет публиковать её повторно сам.",
    "postFailed": "X не опубликовал сообщение: {reason}",
  },
  "zh-CN": {
    "postRequest": "{name} 请求在 X 个人资料 @{account} 上发布以下内容：\n\n{text}\n\n要发布，请回复：!post {code}\n要放弃，请回复：!discard {code}\n此代码将在 {minutes} 分钟后过期。",
    "postPublished": "已在 X 上发布：{url}",
    "postDiscarded": "已放弃，未发布任何内容。",
    "postUnknownCode": "没有等待此代码的帖子。每个代码只能使用一次，并在 {minutes} 分钟后过期。",
    "postUncertain": "X 未确认该帖子。请检查个人资料：BoA 不会自行再次发布。",
    "postFailed": "X 未发布该帖子：{reason}",
  },
}


def fText(pKey, pLanguage=None, **pdValues):
  vLanguage = pLanguage or telegram_texts.fReadLanguage()
  if pKey in ("helpText", "noAgent"):
    return dHelp.get(vLanguage, dHelp["en-US"])
  if pKey in dPostTexts["en-US"]:
    vTemplate = (dPostTexts.get(vLanguage) or dPostTexts["en-US"])[pKey]
    try:
      return vTemplate.format(**pdValues)
    except (KeyError, IndexError, ValueError):
      return vTemplate
  vText = discord_texts.fText(pKey, vLanguage, **pdValues)
  return vText.replace("**", "").replace("`", "").replace("\n_", "\n").rstrip("_")
