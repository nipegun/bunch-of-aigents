"""Mattermost shares the translated text commands used by the Discord bot."""

from backend.core import discord_texts, telegram_texts

dTexts = {
  vLanguage: {vKey: vText.replace("Discord", "Mattermost") for vKey, vText in dLanguage.items()}
  for vLanguage, dLanguage in discord_texts.dTexts.items()
}


def fText(pKey, pLanguage=None, **pdValues):
  vLanguage = pLanguage or telegram_texts.fReadLanguage()
  dOwn = dTexts.get(vLanguage) or dTexts[telegram_texts.cDefaultLanguage]
  if pKey not in dOwn:
    return telegram_texts.fText(pKey, vLanguage, **pdValues)
  vText = dOwn[pKey]
  try:
    return vText.format(**pdValues) if pdValues else vText
  except (KeyError, IndexError, ValueError):
    return vText
