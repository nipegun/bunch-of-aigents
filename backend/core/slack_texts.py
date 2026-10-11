"""Slack uses the existing translated command vocabulary and agent prompts."""

from backend.core import discord_texts, telegram_texts

dTexts = {
  vLanguage: {vKey: vText.replace("Discord", "Slack") for vKey, vText in dLanguage.items()}
  for vLanguage, dLanguage in discord_texts.dTexts.items()
}


def fText(pKey, pLanguage=None, **pdValues):
  vLanguage = pLanguage or telegram_texts.fReadLanguage()
  dOwn = dTexts.get(vLanguage) or dTexts[telegram_texts.cDefaultLanguage]
  if pKey not in dOwn:
    return telegram_texts.fText(pKey, vLanguage, **pdValues)
  vText = dOwn[pKey]
  try:
    vText = vText.format(**pdValues) if pdValues else vText
  except (KeyError, IndexError, ValueError):
    pass
  if pKey == "helpText":
    vText += "\n\n`/boa agents` · `/boa status` · `/boa help`"
  return vText
