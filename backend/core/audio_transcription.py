"""Shared audio settings, decoding and speech recognition, run as boa.

Cloud credentials stay in the existing key store. Native models and binaries
are installed by root; decoding and inference never need elevated privileges.
"""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.parse import quote
import wave

import requests

from backend.core import api_keys, db, paths, whisper_runtime
from backend.providers.cloudflare import fSplitCredential

cSetting = "audio_transcription"
cMaxFileBytes = 20 * 1024 * 1024
cChunkSeconds = 120
cMaxTextCharacters = 30000
dDefaults = {"engine": "disabled", "provider": "", "api_model": "",
             "local_model": "base", "language": "auto", "max_seconds": 600,
             "threads": 2, "keep_audio": True}
dProviders = {
  "openai": {"name": "OpenAI", "url": "https://api.openai.com/v1/audio/transcriptions",
             "models": ["gpt-4o-mini-transcribe", "gpt-4o-transcribe", "whisper-1",
                        "gpt-4o-mini-transcribe-2025-12-15", "gpt-4o-transcribe-diarize"]},
  "groq": {"name": "Groq", "url": "https://api.groq.com/openai/v1/audio/transcriptions",
           "models": ["whisper-large-v3-turbo", "whisper-large-v3"]},
  "mistral": {"name": "Mistral", "url": "https://api.mistral.ai/v1/audio/transcriptions",
              "models": ["voxtral-mini-latest", "voxtral-mini-2507"]},
  "together": {"name": "Together AI", "url": "https://api.together.ai/v1/audio/transcriptions",
               "models": ["openai/whisper-large-v3", "nvidia/parakeet-tdt-0.6b-v3",
                          "nvidia/nemotron-3-asr-streaming-0.6b",
                          "nvidia/nemotron-3.5-asr-streaming-0.6b"]},
  "huggingface": {"name": "Hugging Face", "models": ["openai/whisper-large-v3"],
                  "language": False, "chunk_seconds": 30},
  "cloudflare": {"name": "Cloudflare", "models": ["@cf/openai/whisper", "@cf/openai/whisper-tiny-en"],
                 "language": False, "chunk_seconds": 30},
}


class AudioError(ValueError):
  """An actionable transcription failure, safe to show without credentials."""


def fReadSettings():
  try:
    dStored = json.loads(db.fReadSetting(cSetting, "{}"))
    return {**dDefaults, **{vKey: vValue for vKey, vValue in dStored.items()
                           if vKey in dDefaults}}
  except (ValueError, AttributeError):
    return dict(dDefaults)


def fValidateSettings(pSettings):
  if not isinstance(pSettings, dict) or set(pSettings) - set(dDefaults):
    raise AudioError("Invalid audio settings.")
  dSettings = {**fReadSettings(), **pSettings}
  if dSettings["engine"] not in ("disabled", "local", "api"):
    raise AudioError("Choose disabled, local or API transcription.")
  for vKey, vMinimum, vMaximum in (("max_seconds", 30, 3600), ("threads", 1, 32)):
    if type(dSettings[vKey]) is not int or not vMinimum <= dSettings[vKey] <= vMaximum:
      raise AudioError("%s must be between %d and %d." % (vKey, vMinimum, vMaximum))
  if type(dSettings["keep_audio"]) is not bool:
    raise AudioError("keep_audio must be a boolean.")
  if not isinstance(dSettings["language"], str) or not re.fullmatch(r"auto|[a-z]{2,3}", dSettings["language"]):
    raise AudioError("Use auto or a two/three-letter language code.")
  whisper_runtime.fValidateModelName(dSettings["local_model"])
  if not (whisper_runtime.fGetModel(dSettings["local_model"])
          or whisper_runtime.fIsModelInstalled(dSettings["local_model"])):
    raise AudioError("Unknown local transcription model.")
  if not isinstance(dSettings["provider"], str) or (dSettings["provider"] and dSettings["provider"] not in dProviders):
    raise AudioError("Unsupported transcription provider.")
  if not isinstance(dSettings["api_model"], str) or (dSettings["api_model"] and
      not re.fullmatch(r"[@a-zA-Z0-9][a-zA-Z0-9@/._:-]{0,199}", dSettings["api_model"])):
    raise AudioError("Invalid transcription model identifier.")
  if ".." in dSettings["api_model"]:
    raise AudioError("Invalid transcription model identifier.")
  if dSettings["engine"] == "api":
    if not dSettings["provider"] or not api_keys.fRead(dSettings["provider"]):
      raise AudioError("Save an API key for a supported transcription provider first.")
    if not dSettings["api_model"]:
      raise AudioError("Choose a transcription model.")
    if dSettings["provider"] == "cloudflare" and dSettings["api_model"] not in dProviders["cloudflare"]["models"]:
      raise AudioError("Choose one of the supported Cloudflare Whisper models.")
  return dSettings


def fSaveSettings(pSettings):
  dSettings = fValidateSettings(pSettings)
  db.fWriteSetting(cSetting, json.dumps(dSettings))
  return dSettings


def fDescribeSettings():
  return {"settings": fReadSettings(), "local": whisper_runtime.fDescribeInstallation(),
          "decoder_installed": bool(shutil.which("ffmpeg")),
          "providers": [{"id": vId, "name": dProvider["name"],
                         "models": dProvider["models"], "language": dProvider.get("language", True)}
                        for vId, dProvider in sorted(dProviders.items()) if api_keys.fRead(vId)]}


def fRequireReady(pSettings):
  if pSettings["engine"] == "disabled":
    raise AudioError("Enable transcription in Settings > Audio first.")
  if not shutil.which("ffmpeg"):
    raise AudioError("The audio decoder is missing. Run the BoA installer with --update.")
  if pSettings["engine"] == "local":
    if not whisper_runtime.fIsInstalled() or not whisper_runtime.fIsModelInstalled(pSettings["local_model"]):
      raise AudioError("Install whisper.cpp and download the selected model in Settings > Audio.")
    if ".en" in pSettings["local_model"] and pSettings["language"] not in ("auto", "en"):
      raise AudioError("This model only understands English. Select a multilingual model.")
  elif not api_keys.fRead(pSettings["provider"]):
    raise AudioError("The selected transcription provider has no API key.")


def fDecodeAudio(pSource, pDestination, pMaxSeconds):
  """Decode only media containers, with no network protocols or playlists."""
  if not 0 < Path(pSource).stat().st_size <= cMaxFileBytes:
    raise AudioError("Audio must be a nonempty file of at most 20 MiB.")
  lCommand = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-threads", "2",
              "-protocol_whitelist", "file,pipe", "-format_whitelist",
              "wav,ogg,mp3,mov,matroska,webm,flac,aac,amr,aiff", "-i", str(pSource),
              "-t", str(pMaxSeconds + 1), "-map", "0:a:0", "-vn", "-ar", "16000",
              "-ac", "1", "-c:a", "pcm_s16le", "-threads", "2", str(pDestination)]
  try:
    vResult = subprocess.run(lCommand, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, timeout=120, check=False)
    if vResult.returncode:
      raise AudioError("The file could not be decoded as audio.")
    os.chmod(pDestination, 0o600)
    with wave.open(str(pDestination), "rb") as vAudio:
      vDuration = vAudio.getnframes() / vAudio.getframerate()
    if vDuration > pMaxSeconds:
      raise AudioError("Audio exceeds the configured duration limit (%d seconds)." % pMaxSeconds)
    if vDuration <= 0:
      raise AudioError("The audio is empty.")
    return vDuration
  except (OSError, wave.Error, subprocess.TimeoutExpired) as vError:
    raise AudioError("Audio decoding failed or timed out.") from vError


def fTranscribeLocal(pAudio, pSettings):
  vOutput = Path(pAudio).with_suffix(".transcript")
  try:
    vResult = subprocess.run([
      str(whisper_runtime.fGetBinaryPath()), "-m", str(whisper_runtime.fGetModelPath(pSettings["local_model"])),
      "-f", str(pAudio), "-l", pSettings["language"], "-t", str(pSettings["threads"]),
      "-otxt", "-of", str(vOutput), "-nt", "-np"],
      stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
      timeout=900, check=False)
    if vResult.returncode:
      raise AudioError("whisper.cpp could not transcribe this audio. Check the model and available memory.")
    return Path(str(vOutput) + ".txt").read_text(encoding="utf-8").strip()
  except (OSError, subprocess.TimeoutExpired) as vError:
    raise AudioError("Local transcription failed or timed out.") from vError
  finally:
    Path(str(vOutput) + ".txt").unlink(missing_ok=True)


def fTranscribeApi(pAudio, pSettings):
  vProvider = pSettings["provider"]
  dProvider = dProviders[vProvider]
  vKey = api_keys.fRead(vProvider)
  if not vKey:
    raise AudioError("The selected transcription provider has no API key.")
  dHeaders = {"Authorization": "Bearer " + vKey}
  dArguments = {"headers": dHeaders, "timeout": (15, 300), "allow_redirects": False}
  vModel = pSettings["api_model"]
  try:
    with open(pAudio, "rb") as vFile:
      if vProvider == "cloudflare":
        vAccount, vToken = fSplitCredential(vKey)
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", vAccount):
          raise AudioError("Invalid Cloudflare account ID in the stored credential.")
        dHeaders["Authorization"] = "Bearer " + vToken
        dHeaders["Content-Type"] = "audio/wav"
        vUrl = "https://api.cloudflare.com/client/v4/accounts/%s/ai/run/%s" % (vAccount, quote(vModel, safe="/@"))
        dArguments["data"] = vFile
      elif vProvider == "huggingface":
        vUrl = "https://router.huggingface.co/hf-inference/models/" + quote(vModel, safe="/")
        dHeaders["Content-Type"] = "audio/wav"
        dArguments["data"] = vFile
      else:
        vUrl = dProvider["url"]
        dFields = {"model": vModel}
        if vProvider != "mistral":
          dFields["response_format"] = "json"
        if pSettings["language"] != "auto":
          dFields["language"] = pSettings["language"]
        if vProvider == "openai" and "diarize" in vModel:
          dFields["chunking_strategy"] = "auto"
        dArguments.update({"data": dFields, "files": {"file": ("audio.wav", vFile, "audio/wav")}})
      with requests.post(vUrl, stream=True, **dArguments) as vResponse:
        if not 200 <= vResponse.status_code < 300:
          raise AudioError("%s transcription returned HTTP %d. Check the key, model and provider quota."
                           % (dProvider["name"], vResponse.status_code))
        vBody = bytearray()
        for vChunk in vResponse.iter_content(65536):
          vBody.extend(vChunk)
          if len(vBody) > 2 * 1024 * 1024:
            raise AudioError("The transcription provider returned an oversized response.")
        dResponse = json.loads(vBody)
      if vProvider == "cloudflare":
        dResponse = dResponse.get("result", {})
      vText = dResponse.get("text")
      if not isinstance(vText, str):
        raise AudioError("The transcription provider returned no transcript.")
      return vText.strip()
  except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError) as vError:
    if isinstance(vError, AudioError):
      raise
    # Never expose a request URL, a credential or a provider's echo of input.
    raise AudioError("%s transcription failed. Check the connection and provider settings." % dProvider["name"]) from vError


def fTranscribe(pSource, pSettings=None):
  dSettings = fValidateSettings(pSettings or fReadSettings())
  fRequireReady(dSettings)
  # Put all scratch files beside the managed input, inside boa's private spool.
  with tempfile.TemporaryDirectory(prefix="decode-", dir=Path(pSource).parent) as vDirectory:
    vWave = Path(vDirectory) / "audio.wav"
    vDuration = fDecodeAudio(pSource, vWave, dSettings["max_seconds"])
    lText = []
    # Raw-binary endpoints cannot carry Whisper's long-form generation
    # options. Keep those requests inside one 30-second encoder window.
    vChunkSeconds = (dProviders[dSettings["provider"]].get("chunk_seconds", cChunkSeconds)
                     if dSettings["engine"] == "api" else cChunkSeconds)
    with wave.open(str(vWave), "rb") as vInput:
      while vFrames := vInput.readframes(vChunkSeconds * 16000):
        vChunk = Path(vDirectory) / "chunk.wav"
        with wave.open(str(vChunk), "wb") as vOutput:
          vOutput.setparams(vInput.getparams())
          vOutput.writeframes(vFrames)
        os.chmod(vChunk, 0o600)
        vText = (fTranscribeLocal(vChunk, dSettings) if dSettings["engine"] == "local"
                 else fTranscribeApi(vChunk, dSettings))
        lText.append(vText)
        if sum(map(len, lText)) > cMaxTextCharacters:
          raise AudioError("The transcript is too long for a chat message.")
    vText = "\n".join(vText for vText in lText if vText).strip()
    if not vText:
      raise AudioError("No speech was recognized in this audio.")
    return {"text": vText, "duration": round(vDuration, 2), "engine": dSettings["engine"],
            "model": dSettings["local_model"] if dSettings["engine"] == "local" else dSettings["api_model"],
            "provider": dSettings["provider"] if dSettings["engine"] == "api" else "whisper.cpp"}
