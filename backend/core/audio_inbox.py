"""Durable Telegram voice-note intake and one unprivileged background worker."""

import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time
import uuid
from urllib.parse import quote

import requests

from backend.core import audio_transcription, channels, db, exec_client, paths

cJobPattern = re.compile(r"[a-f0-9]{32}")
cQueueLimit = 20
cJobExpirySeconds = 86400
cMaxTranscriptCharacters = 30000
vWorker = None
vWorkerLock = threading.Lock()


def fGetDirectory():
  return Path(paths.fGetBaseDir()) / "audio"


def fGetJobDirectory(pId):
  if not isinstance(pId, str) or not cJobPattern.fullmatch(pId):
    raise ValueError("Invalid audio identifier.")
  return fGetDirectory() / pId


def fReadJob(pId):
  fGetJobDirectory(pId)
  vConnection = db.fOpenAppDb()
  try:
    vRow = vConnection.execute("SELECT * FROM audio_jobs WHERE id = ?", (pId,)).fetchone()
    return dict(vRow) if vRow else None
  finally:
    vConnection.close()


def fGetTelegramAudio(pMessage):
  dAudio = pMessage.get("voice") or pMessage.get("audio")
  if isinstance(dAudio, dict):
    return dAudio
  dDocument = pMessage.get("document")
  if isinstance(dDocument, dict) and str(dDocument.get("mime_type", "")).startswith("audio/"):
    return dDocument
  return None


def fEnqueueTelegram(pMessage, pConfig, pAgentId, pCaption=""):
  dSettings = audio_transcription.fReadSettings()
  audio_transcription.fRequireReady(dSettings)
  dMedia = fGetTelegramAudio(pMessage) or {}
  if not isinstance(dMedia, dict) or not isinstance(dMedia.get("file_id"), str):
    raise audio_transcription.AudioError("Telegram supplied no audio file.")
  if len(dMedia["file_id"]) > 1024 or dMedia.get("file_size", 0) > audio_transcription.cMaxFileBytes:
    raise audio_transcription.AudioError("Telegram audio must be at most 20 MiB.")
  if dMedia.get("duration", 0) > dSettings["max_seconds"]:
    raise audio_transcription.AudioError("Audio exceeds the configured duration limit.")
  vId = uuid.uuid4().hex
  vConnection = db.fOpenAppDb()
  try:
    vConnection.execute("BEGIN IMMEDIATE")
    vExisting = vConnection.execute(
      "SELECT id FROM audio_jobs WHERE source = 'telegram' AND source_chat = ? AND source_message = ?",
      (str(pConfig["chat_id"]), str(pMessage["message_id"]))).fetchone()
    if vExisting:
      return vExisting["id"], False
    vCount = vConnection.execute("SELECT count(*) FROM audio_jobs WHERE state IN ('queued', 'processing', 'transcribed')").fetchone()[0]
    if vCount >= cQueueLimit:
      raise audio_transcription.AudioError("The audio queue is full. Try again after the current notes finish.")
    vConnection.execute(
      "INSERT INTO audio_jobs (id, source, source_chat, source_message, agent_id, turn_id, settings, media, caption, created_at) "
      "VALUES (?, 'telegram', ?, ?, ?, ?, ?, ?, ?, ?)",
      (vId, str(pConfig["chat_id"]), str(pMessage["message_id"]), pAgentId, vId[:16],
       json.dumps(dSettings), json.dumps({"file_id": dMedia["file_id"]}),
       str(pCaption)[:4000], int(time.time())))
    vConnection.commit()
    return vId, True
  finally:
    vConnection.close()


def fUpdateJob(pId, **pFields):
  if not pFields or set(pFields) - {"state", "transcript", "result", "error", "attempts", "retry_at"}:
    raise ValueError("Invalid audio job fields.")
  vConnection = db.fOpenAppDb()
  try:
    vConnection.execute("UPDATE audio_jobs SET " + ", ".join(vKey + " = ?" for vKey in pFields) + " WHERE id = ?",
                         (*pFields.values(), pId))
    vConnection.commit()
  finally:
    vConnection.close()


def fDownloadTelegram(pJob, pConfig):
  vDirectory = fGetJobDirectory(pJob["id"])
  vDirectory.mkdir(parents=True, mode=0o700, exist_ok=True)
  os.chmod(vDirectory, 0o700)
  vPath = vDirectory / "original.audio"
  if vPath.is_file():
    return vPath
  try:
    vResponse = channels.fCallTelegram(pConfig["bot_token"], "getFile", {
      "file_id": json.loads(pJob["media"])["file_id"]})
    try:
      dFile = vResponse.json().get("result", {})
    finally:
      vResponse.close()
    vRemotePath = dFile.get("file_path", "")
    if not re.fullmatch(r"[a-zA-Z0-9_./-]+", vRemotePath) or ".." in vRemotePath or vRemotePath.startswith("/"):
      raise audio_transcription.AudioError("Telegram returned an invalid audio file path.")
    if dFile.get("file_size", 0) > audio_transcription.cMaxFileBytes:
      raise audio_transcription.AudioError("Telegram audio exceeds the 20 MiB download limit.")
    vPartial = vPath.with_suffix(".part")
    vUrl = "https://api.telegram.org/file/bot%s/%s" % (pConfig["bot_token"], quote(vRemotePath, safe="/"))
    vDeadline = time.monotonic() + 180
    with requests.get(vUrl, stream=True, timeout=(15, 30), allow_redirects=False) as vDownload:
      if vDownload.status_code != 200:
        raise audio_transcription.AudioError("Telegram could not download this audio. Send it again.")
      vSize = 0
      with vPartial.open("wb") as vFile:
        os.chmod(vPartial, 0o600)
        for vChunk in vDownload.iter_content(65536):
          vSize += len(vChunk)
          if vSize > audio_transcription.cMaxFileBytes or time.monotonic() > vDeadline:
            raise audio_transcription.AudioError("The audio download exceeded its size or time limit.")
          vFile.write(vChunk)
      if not vSize:
        raise audio_transcription.AudioError("The downloaded audio is empty.")
    os.replace(vPartial, vPath)
    return vPath
  except (requests.RequestException, channels.ChannelError, ValueError, KeyError) as vError:
    if isinstance(vError, audio_transcription.AudioError):
      raise
    raise audio_transcription.AudioError("Could not retrieve the audio from Telegram. Send it again.") from vError


def fSubmitTranscript(pJob):
  # A restart between persisting the text and deleting the original must
  # still honor retention before any saved transcript is submitted.
  vDirectory = fGetJobDirectory(pJob["id"])
  (vDirectory / "original.audio").unlink(missing_ok=True)
  if not json.loads(pJob["settings"])["keep_audio"]:
    (vDirectory / "playback.ogg").unlink(missing_ok=True)
  vText = pJob["transcript"]
  if pJob["caption"]:
    vText = pJob["caption"] + "\n\n" + vText
  if len(vText) > cMaxTranscriptCharacters:
    raise audio_transcription.AudioError("The audio transcript is too long for a chat message.")
  exec_client.fSendChatMessage(pJob["agent_id"], vText, pSource="telegram",
                              pTurnId=pJob["turn_id"], pAudioId=pJob["id"])
  # Queue the answer and finish the job in the same transaction. Retrying
  # after a lost executor response uses the same turn ID, never a second run.
  vConnection = db.fOpenAppDb()
  try:
    vConnection.execute("BEGIN IMMEDIATE")
    vConnection.execute("INSERT OR IGNORE INTO telegram_pending (turn_id, agent_id, reply_to) VALUES (?, ?, ?)",
                         (pJob["turn_id"], pJob["agent_id"], int(pJob["source_message"])))
    vConnection.execute("UPDATE audio_jobs SET state = 'submitted' WHERE id = ?", (pJob["id"],))
    vConnection.commit()
  finally:
    vConnection.close()


def fProcessJob(pJob, pConfig):
  if int(time.time()) - pJob["created_at"] > cJobExpirySeconds:
    raise audio_transcription.AudioError("The audio job expired. Send the note again.")
  if pJob["source_chat"] != str(pConfig.get("chat_id", "")):
    raise audio_transcription.AudioError("The Telegram destination changed before this audio was processed.")
  if not pJob["transcript"]:
    # TemporaryDirectory cannot clean itself when the service is killed.
    for vScratch in fGetJobDirectory(pJob["id"]).glob("decode-*"):
      if vScratch.is_dir() and not vScratch.is_symlink():
        shutil.rmtree(vScratch)
    fUpdateJob(pJob["id"], state="processing")
    vPath = fDownloadTelegram(pJob, pConfig)
    dSettings = json.loads(pJob["settings"])
    dResult = audio_transcription.fTranscribe(vPath, dSettings)
    vText = dResult.pop("text")
    fUpdateJob(pJob["id"], state="transcribed", transcript=vText, result=json.dumps(dResult))
    # A normalized Ogg/Opus copy plays consistently in browsers, regardless
    # of whether Telegram received an M4A, MP3 or voice note originally.
    if dSettings["keep_audio"]:
      vPlayback = vPath.parent / "playback.ogg"
      try:
        vProcess = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-protocol_whitelist", "file,pipe",
                                 "-format_whitelist", "wav,ogg,mp3,mov,matroska,webm,flac,aac,amr,aiff",
                                 "-i", str(vPath), "-map", "0:a:0", "-vn", "-t", str(dSettings["max_seconds"]),
                                 "-ac", "1", "-c:a", "libopus", "-b:a", "32k", str(vPlayback)],
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=120, check=False)
        if vProcess.returncode == 0:
          os.chmod(vPlayback, 0o600)
        else:
          vPlayback.unlink(missing_ok=True)
      except (OSError, subprocess.TimeoutExpired):
        vPlayback.unlink(missing_ok=True)
    vPath.unlink(missing_ok=True)
    pJob = fReadJob(pJob["id"])
  fSubmitTranscript(pJob)


def fRunWorker(pReadConfig, pSay, pLog):
  fGetDirectory().mkdir(mode=0o700, parents=True, exist_ok=True)
  # Services can overlap briefly during a manual restart. Only one process
  # owns decoding and queue recovery; a dead process releases this lock.
  with (fGetDirectory() / "worker.lock").open("a") as vLock:
    fcntl.flock(vLock, fcntl.LOCK_EX)
    vConnection = db.fOpenAppDb()
    try:
      vConnection.execute("UPDATE audio_jobs SET state = 'queued' WHERE state = 'processing'")
      vConnection.commit()
    finally:
      vConnection.close()
    while True:
      try:
        dConfig = pReadConfig()
        if dConfig:
          fRunOneJob(dConfig, pSay, pLog, pLocked=True)
      except Exception:
        pLog("Audio worker could not process the queue; it will retry.")
      time.sleep(2)


def fRunOneJob(pConfig, pSay, pLog, pLocked=False):
  if not pLocked:
    fGetDirectory().mkdir(mode=0o700, parents=True, exist_ok=True)
    with (fGetDirectory() / "worker.lock").open("a") as vLock:
      try:
        fcntl.flock(vLock, fcntl.LOCK_EX | fcntl.LOCK_NB)
      except BlockingIOError:
        return False
      return fRunOneJob(pConfig, pSay, pLog, pLocked=True)
  vConnection = db.fOpenAppDb()
  try:
    vRow = vConnection.execute("SELECT * FROM audio_jobs WHERE state IN ('queued', 'transcribed') AND retry_at <= ? ORDER BY created_at, id LIMIT 1",
                               (int(time.time()),)).fetchone()
  finally:
    vConnection.close()
  if not vRow:
    return False
  dJob = dict(vRow)
  try:
    fProcessJob(dJob, pConfig)
  except exec_client.ExecError as vError:
    if ("still answering" in str(vError) or "connect" in str(vError).lower()) and int(time.time()) - dJob["created_at"] < cJobExpirySeconds:
      fUpdateJob(dJob["id"], state="transcribed", retry_at=int(time.time()) + 15)
      return True
    fFailJob(dJob, "The agent could not accept the transcript. Check its configuration.", pConfig, pSay)
  except Exception as vError:
    # AudioError messages are deliberately safe; other exceptions may carry
    # a Telegram URL containing its bot token, so never forward them.
    vReason = str(vError) if isinstance(vError, audio_transcription.AudioError) else "Audio processing failed. Check the server and audio settings."
    fFailJob(dJob, vReason, pConfig, pSay)
  return True


def fFailJob(pJob, pReason, pConfig, pSay):
  from backend.core import telegram_texts
  fUpdateJob(pJob["id"], state="failed", error=pReason)
  shutil.rmtree(fGetJobDirectory(pJob["id"]), ignore_errors=True)
  if pJob["source_chat"] == str(pConfig.get("chat_id", "")):
    pSay(pConfig, telegram_texts.fText("audioFailed", None, reason=pReason), int(pJob["source_message"]))


def fStartWorker(pReadConfig, pSay, pLog):
  global vWorker
  with vWorkerLock:
    if vWorker is None or not vWorker.is_alive():
      vWorker = threading.Thread(target=fRunWorker, args=(pReadConfig, pSay, pLog), name="audio-transcription", daemon=True)
      vWorker.start()


def fRemoveAgentAudio(pAgentId, pIncludePending=False):
  vConnection = db.fOpenAppDb()
  try:
    vWhere = "agent_id = ?" + ("" if pIncludePending else " AND state IN ('submitted', 'failed')")
    lRows = vConnection.execute("SELECT id FROM audio_jobs WHERE " + vWhere, (pAgentId,)).fetchall()
    for vRow in lRows:
      shutil.rmtree(fGetJobDirectory(vRow["id"]), ignore_errors=True)
    vConnection.execute("DELETE FROM audio_jobs WHERE " + vWhere, (pAgentId,))
    vConnection.commit()
  finally:
    vConnection.close()
