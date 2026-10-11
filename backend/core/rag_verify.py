"""Checks an answer against the document passages it cites.

Used by the runner in the RAG "verified" mode. What it can establish is
limited, and it says so: that every paragraph cites a passage retrieved in this
run, and that the paragraph is close in meaning to a passage it cites. It
cannot prove that nothing inside a cited paragraph came from the model's own
weights; it can refuse the paragraphs where that is visible.

The unit is the paragraph, and each item of a list is a paragraph of its own:
an item is a separate claim, and one citation at the end of a list would
otherwise vouch for all of them. A fenced code block belongs to the paragraph
before it, which is where its citation is written, and is compared with it:
the lead of an example says little, the code says what it shows. Headings, short labels
ending in a colon ("Sources:") and separators say nothing about the documents
and are left alone.
"""

import re

from backend.core import rag_embeddings

cCitationPattern = re.compile(r"\[rag:([^\]\n]+)\]")
cListItemPattern = re.compile(r"^\s{0,3}(?:[-*+]|\d{1,3}[.)])\s+")
cFencePattern = re.compile(r"^\s{0,3}(?:```|~~~)")
cHeadingPattern = re.compile(r"^\s{0,3}#{1,6}\s")

# How close, in the embedding space the library is searched in, a paragraph
# has to be to a passage it cites: `min_support` of each model in
# rag_models.json, because each model has its own scale. Measured on
# 2026-09-29 on the Debian test library: 23 passages of its four Python books,
# Spanish and English, on different topics; 138 faithful paragraphs in six
# styles (paraphrase, translation, one-line summary, list item, a lead with its
# code block, a long paragraph joining two facts), each compared with its own
# passage; and every faithful paragraph compared with the passages of other
# topics (2,652 pairs), which is a citation to the wrong passage.
#   threshold          faithful removed     wrong citations kept
#   Gemma 0.40         14 (10.1%)            2 (0.08%)
#   Gemma 0.36          9 (6.5%)            25 (0.94%)
#   Gemma 0.34          6 (4.3%)            52 (1.96%)
#   Qwen  0.43          7 (5.1%)            31 (1.17%)
#   Qwen  0.44          8 (5.8%)            21 (0.79%)
#   Qwen  0.46         10 (7.2%)            10 (0.38%)
# No value separates the two groups with either model: each hundredth lower
# saves a faithful paragraph or two and lets dozens of wrong citations through.
# Each threshold is the highest that removes fewer faithful paragraphs while
# keeping wrong citations under 1%. What still falls below is mostly short list
# items and one-line summaries, with little text to compare. The limit of the
# check: a citation to a passage on the same topic passes (85 and 98 of 384
# such pairs at these thresholds), and a paragraph contradicting its passage
# scores like a faithful one; both are left to the citation rule and the prompt.

# Below this many letters or digits, once the citations are taken out, a
# paragraph is a reference ("- [rag:ab:3]") or a one-word answer, and there is
# nothing to compare. The citation still has to be one retrieved in this run.
cMinComparableCharacters = 12

# A paragraph longer than this is compared by its beginning. The model's
# context is 2048 tokens and no answer paragraph needs more to be judged.
cMaxUnitCharacters = 4000

cReasonNoCitation = "no valid citation"
cReasonUnsupported = "not supported by the passage it cites"

# The three sentences the user may be shown instead of, or after, the model's
# answer. In the answer language configured for the application, and in
# English when there is none, as the rest of the runner does.
dFixedTexts = {
  "en-GB": {
    "no_sources": "The document library does not contain enough information to answer this question.",
    "removed": "Paragraphs removed because the documents could not back them: {count}.",
    "unverifiable": "The answer could not be checked against the documents because the local embedding engine is unavailable, so it has been withheld. Try again in a moment.",
  },
  "en-US": {
    "no_sources": "The document library does not contain enough information to answer this question.",
    "removed": "Paragraphs removed because the documents could not back them: {count}.",
    "unverifiable": "The answer could not be checked against the documents because the local embedding engine is unavailable, so it has been withheld. Try again in a moment.",
  },
  "es-AR": {
    "no_sources": "La biblioteca de documentos no contiene información suficiente para responder a esta pregunta.",
    "removed": "Párrafos retirados por no poder respaldarse con los documentos: {count}.",
    "unverifiable": "No se pudo comprobar la respuesta con los documentos porque el motor local de vectores no está disponible, así que no se muestra. Intentalo de nuevo en un rato.",
  },
  "es-ES": {
    "no_sources": "La biblioteca de documentos no contiene información suficiente para responder a esta pregunta.",
    "removed": "Párrafos retirados por no poder respaldarse con los documentos: {count}.",
    "unverifiable": "No se ha podido comprobar la respuesta con los documentos porque el motor local de vectores no está disponible, así que no se muestra. Inténtalo de nuevo en un momento.",
  },
  "de-DE": {
    "no_sources": "Die Dokumentbibliothek enthält nicht genug Informationen, um diese Frage zu beantworten.",
    "removed": "Absätze entfernt, weil die Dokumente sie nicht belegen konnten: {count}.",
    "unverifiable": "Die Antwort konnte nicht mit den Dokumenten abgeglichen werden, weil die lokale Embedding-Engine nicht verfügbar ist; sie wird daher nicht angezeigt. Versuche es gleich noch einmal.",
  },
  "fr-FR": {
    "no_sources": "La bibliothèque de documents ne contient pas assez d'informations pour répondre à cette question.",
    "removed": "Paragraphes retirés faute d'appui dans les documents : {count}.",
    "unverifiable": "La réponse n'a pas pu être vérifiée par rapport aux documents, car le moteur local de vectorisation est indisponible ; elle n'est donc pas affichée. Réessaie dans un instant.",
  },
  "he-IL": {
    "no_sources": "בספריית המסמכים אין מספיק מידע כדי לענות על השאלה הזו.",
    "removed": "פסקאות שהוסרו כי המסמכים לא ביססו אותן: {count}.",
    "unverifiable": "לא ניתן היה לבדוק את התשובה מול המסמכים כי מנוע ההטמעה המקומי לא זמין, ולכן היא לא מוצגת. אפשר לנסות שוב בעוד רגע.",
  },
  "hi-IN": {
    "no_sources": "दस्तावेज़ लाइब्रेरी में इस सवाल का जवाब देने के लिए पर्याप्त जानकारी नहीं है।",
    "removed": "जिन अनुच्छेदों की पुष्टि दस्तावेज़ों से नहीं हो सकी, उन्हें हटाया गया: {count}",
    "unverifiable": "स्थानीय एम्बेडिंग इंजन उपलब्ध नहीं है, इसलिए जवाब का दस्तावेज़ों से मिलान नहीं हो सका और उसे नहीं दिखाया गया। थोड़ी देर बाद फिर कोशिश करें।",
  },
  "it-IT": {
    "no_sources": "La biblioteca di documenti non contiene informazioni sufficienti per rispondere a questa domanda.",
    "removed": "Paragrafi rimossi perché i documenti non li supportano: {count}.",
    "unverifiable": "Non è stato possibile verificare la risposta con i documenti perché il motore locale di vettorizzazione non è disponibile, quindi non viene mostrata. Riprova tra un momento.",
  },
  "ja-JP": {
    "no_sources": "文書ライブラリには、この質問に答えるのに十分な情報がありません。",
    "removed": "文書で裏付けられなかったため削除した段落: {count}",
    "unverifiable": "ローカルの埋め込みエンジンが利用できないため、回答を文書と照合できませんでした。そのため回答は表示されません。しばらくしてからもう一度お試しください。",
  },
  "ko-KR": {
    "no_sources": "문서 라이브러리에 이 질문에 답할 만한 정보가 충분하지 않습니다.",
    "removed": "문서로 뒷받침되지 않아 삭제한 단락: {count}개",
    "unverifiable": "로컬 임베딩 엔진을 사용할 수 없어 답변을 문서와 대조하지 못했으므로 표시하지 않습니다. 잠시 후 다시 시도해 주세요.",
  },
  "pt-BR": {
    "no_sources": "A biblioteca de documentos não contém informações suficientes para responder a esta pergunta.",
    "removed": "Parágrafos removidos por não terem respaldo nos documentos: {count}.",
    "unverifiable": "Não foi possível verificar a resposta com os documentos porque o mecanismo local de vetores não está disponível, então ela não é exibida. Tente de novo em instantes.",
  },
  "pt-PT": {
    "no_sources": "A biblioteca de documentos não contém informação suficiente para responder a esta pergunta.",
    "removed": "Parágrafos retirados por não terem suporte nos documentos: {count}.",
    "unverifiable": "Não foi possível verificar a resposta com os documentos porque o motor local de vetores não está disponível, pelo que não é mostrada. Tenta novamente daqui a pouco.",
  },
  "ru-RU": {
    "no_sources": "В библиотеке документов недостаточно информации, чтобы ответить на этот вопрос.",
    "removed": "Удалено абзацев, которые не подтверждаются документами: {count}.",
    "unverifiable": "Не удалось сверить ответ с документами, потому что локальный движок векторизации недоступен, поэтому ответ не показан. Попробуй ещё раз чуть позже.",
  },
  "zh-CN": {
    "no_sources": "文档库中没有足够的信息来回答这个问题。",
    "removed": "因无法在文档中找到依据而删除的段落：{count}",
    "unverifiable": "由于本地向量引擎不可用，无法将回答与文档核对，因此不予显示。请稍后再试。",
  },
}


def fFixedText(pLanguage, pKey):
  """One of the fixed sentences, in pLanguage or else in English."""
  return (dFixedTexts.get(str(pLanguage or "")) or dFixedTexts["en-US"])[pKey]


def fIsExempt(pText):
  """Whether a piece of the answer says nothing that could be checked."""
  vText = pText.strip()
  if not re.search(r"\w", vText):
    return True
  lLines = vText.split("\n")
  if all(cHeadingPattern.match(vLine) for vLine in lLines):
    return True
  return (len(lLines) == 1 and vText.endswith(":") and len(vText) <= 80
          and not cCitationPattern.search(vText))


def fSplitUnits(pText):
  """Split an answer into blocks of pieces, keeping enough to rebuild it.

  Returns a list of blocks; each block is a list of pieces, each piece a
  dictionary with its `text` and its `kind`: "unit" (to be checked),
  "exempt", or "attached" (a code block, kept or removed with `owner`).
  """
  lBlocks = []
  lCurrent = []
  vInFence = False
  for vLine in str(pText or "").replace("\r\n", "\n").split("\n"):
    if cFencePattern.match(vLine):
      vInFence = not vInFence
    if not vLine.strip() and not vInFence:
      if lCurrent:
        lBlocks.append(lCurrent)
        lCurrent = []
      continue
    lCurrent.append(vLine)
  if lCurrent:
    lBlocks.append(lCurrent)

  ldBlocks = []
  vUnits = 0
  vLastUnit = None
  for lLines in lBlocks:
    ldPieces = []
    if cFencePattern.match(lLines[0]) and vLastUnit is not None:
      ldPieces.append({"text": "\n".join(lLines), "kind": "attached", "owner": vLastUnit})
      ldBlocks.append(ldPieces)
      continue
    # A new piece at every list marker; what comes before the first one is
    # the block's lead, a piece of its own.
    lItems = []
    vInItemFence = False
    for vLine in lLines:
      if cFencePattern.match(vLine):
        vInItemFence = not vInItemFence
      if not vInItemFence and cListItemPattern.match(vLine) and lItems:
        lItems.append([vLine])
      elif lItems:
        lItems[-1].append(vLine)
      else:
        lItems.append([vLine])
    for lItem in lItems:
      vText = "\n".join(lItem)
      if fIsExempt(vText):
        ldPieces.append({"text": vText, "kind": "exempt"})
      else:
        ldPieces.append({"text": vText, "kind": "unit", "id": vUnits})
        vLastUnit = vUnits
        vUnits += 1
    ldBlocks.append(ldPieces)
  return ldBlocks


def fRebuild(pBlocks, pRemoved):
  """The answer without the units in pRemoved (and their code blocks)."""
  lBlocks = []
  for ldPieces in pBlocks:
    lKept = []
    for dPiece in ldPieces:
      if dPiece["kind"] == "unit" and dPiece["id"] in pRemoved:
        continue
      if dPiece["kind"] == "attached" and dPiece["owner"] in pRemoved:
        continue
      lKept.append(dPiece["text"])
    if lKept:
      lBlocks.append("\n".join(lKept))
  return "\n\n".join(lBlocks)


def fVerify(pText, pSources, pMinSupport=None):
  """Check every paragraph of an answer against the passages it cites.

  Returns a dictionary: `text` (the answer without the unsupported
  paragraphs), `kept` (how many checkable paragraphs remain) and `removed`
  (a list of {text, reason}). Raises rag_embeddings.EngineUnavailable when the
  comparison cannot be made; the caller decides what an unverifiable answer
  is worth.
  """
  dSources = {dSource["ref"]: dSource for dSource in (pSources or []) if dSource.get("ref")}
  ldBlocks = fSplitUnits(pText)
  ldUnits = [dPiece for ldPieces in ldBlocks for dPiece in ldPieces if dPiece["kind"] == "unit"]
  dAttached = {}
  for dPiece in (dPiece for ldPieces in ldBlocks for dPiece in ldPieces if dPiece["kind"] == "attached"):
    dAttached.setdefault(dPiece["owner"], []).append(
      "\n".join(vLine for vLine in dPiece["text"].split("\n") if not cFencePattern.match(vLine)))
  dRemoved = {}
  ldToCompare = []
  for dUnit in ldUnits:
    lRefs = [vRef for vRef in cCitationPattern.findall(dUnit["text"]) if vRef in dSources]
    if not lRefs:
      dRemoved[dUnit["id"]] = cReasonNoCitation
      continue
    # A code block after a paragraph is compared with it. Alone, the lead
    # ("The book's example:") says next to nothing about the passage, and a
    # faithful example was removed for its introduction.
    vBody = "\n".join([cCitationPattern.sub(" ", dUnit["text"]).strip()] + dAttached.get(dUnit["id"], [])).strip()
    if len(re.findall(r"\w", vBody)) < cMinComparableCharacters:
      continue
    ldToCompare.append({"id": dUnit["id"], "body": vBody[:cMaxUnitCharacters],
                        "passages": [dSources[vRef]["text"] for vRef in dict.fromkeys(lRefs)]})

  if ldToCompare:
    # The paragraph is asked as a query and the passages are embedded as
    # documents, which is how the library was searched: the same distance that
    # found a passage for a question is the one that judges a paragraph.
    # One model for both sides and for the threshold, which is on its scale.
    dModel = rag_embeddings.fModel()
    vMinSupport = dModel["min_support"] if pMinSupport is None else pMinSupport
    lPassages = list(dict.fromkeys(vText for dItem in ldToCompare for vText in dItem["passages"]))
    lUnitVectors = rag_embeddings.fEmbed([dItem["body"] for dItem in ldToCompare], pQuery=True, pModel=dModel)
    dPassageVectors = dict(zip(lPassages, rag_embeddings.fEmbed(lPassages, pModel=dModel)))
    for dItem, lUnitVector in zip(ldToCompare, lUnitVectors):
      vBest = max(sum(vA * vB for vA, vB in zip(lUnitVector, dPassageVectors[vText]))
                  for vText in dItem["passages"])
      if vBest < vMinSupport:
        dRemoved[dItem["id"]] = cReasonUnsupported

  return {
    "text": fRebuild(ldBlocks, set(dRemoved)),
    "kept": len(ldUnits) - len(dRemoved),
    "removed": [{"text": dUnit["text"], "reason": dRemoved[dUnit["id"]]}
                for dUnit in ldUnits if dUnit["id"] in dRemoved],
  }


def fBuildCorrectionPrompt(pRemoved):
  """What the model is told, once, before its unsupported paragraphs go."""
  lLines = []
  for vIndex, dRemoved in enumerate(pRemoved[:12], 1):
    vText = " ".join(dRemoved["text"].split())
    if len(vText) > 240:
      vText = vText[:240] + "..."
    lLines.append('%d. (%s) "%s"' % (vIndex, dRemoved["reason"], vText))
  return ("Your answer was checked against the document passages. These paragraphs "
          "have no valid [rag:REFERENCE] citation, or say something the passage they "
          "cite does not support, and will be removed before the user sees them:\n"
          + "\n".join(lLines) +
          "\nWrite the answer again. Every paragraph and every list item must cite, "
          "as [rag:REFERENCE], a passage retrieved in this run that states what it says. "
          "Search again with rag.search if you need more passages. Leave out whatever "
          "the documents do not support; do not replace it with general knowledge.")
