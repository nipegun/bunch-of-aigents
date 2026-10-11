"""OAuth 2.0 PKCE and serialized credential rotation for the X channel."""

import base64
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
import secrets
import time
from urllib.parse import urlencode, urlsplit

import requests

from backend.core import channels

cCallbackPath = "/api/channels/x/oauth/callback"
cTokenUrl = "https://api.x.com/2/oauth2/token"
cAuthorizeUrl = "https://x.com/i/oauth2/authorize"
lBaseScopes = ["tweet.read", "users.read", "dm.read", "dm.write", "media.write", "offline.access"]
lTokenFields = ["access_token", "refresh_token", "expires_at", "scopes", "account_id", "account_username", "auth_generation"]


@contextmanager
def fLockedConfig():
  """Use one lock across web workers, the listener and the agent API."""
  vPath = channels.fGetChannelConfigPath("x")
  vDescriptor = os.open(vPath + ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o640)
  try:
    fcntl.flock(vDescriptor, fcntl.LOCK_EX)
    yield channels.fReadConfigForEditing("x")
  finally:
    os.close(vDescriptor)


def fWriteConfig(pConfig):
  """Replace the file while fLockedConfig is held; secrets never reach the UI."""
  vPath = channels.fGetChannelConfigPath("x")
  vTemporary = vPath + "." + secrets.token_hex(8) + ".tmp"
  try:
    vDescriptor = os.open(vTemporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
    with os.fdopen(vDescriptor, "w", encoding="utf-8") as vFile:
      json.dump(pConfig, vFile, ensure_ascii=False, indent=2)
      vFile.write("\n")
      vFile.flush()
      os.fsync(vFile.fileno())
    os.replace(vTemporary, vPath)
  finally:
    if os.path.exists(vTemporary):
      os.unlink(vTemporary)


def fScopes(pConfig):
  return lBaseScopes + (["tweet.write"] if pConfig.get("allow_posts") else [])


def fCredential(pConfig, pField):
  vValue = pConfig.get(pField)
  if not isinstance(vValue, str) or not vValue or any(vChar.isspace() for vChar in vValue):
    raise channels.ChannelRejected("X requires a valid %s. Configure and authorize X in Settings → Channels." % pField)
  return vValue


def fExchange(pConfig, pData):
  """Never include an OAuth error body, URL or credential in an exception."""
  try:
    vResponse = requests.post(cTokenUrl, data=pData,
      auth=(fCredential(pConfig, "client_id"), fCredential(pConfig, "client_secret")),
      timeout=30, allow_redirects=False)
  except requests.RequestException:
    raise channels.ChannelError("Cannot reach X's authorization server. Try authorizing again.") from None
  if vResponse.status_code != 200:
    raise channels.ChannelRejected("X authorization failed (HTTP %s). Authorize X again in Settings → Channels."
                                   % vResponse.status_code)
  try:
    dToken = vResponse.json()
    fCredential(dToken, "access_token")
    fCredential(dToken, "refresh_token")
    vExpiry = int(dToken["expires_in"])
    if vExpiry < 60 or str(dToken.get("token_type", "")).lower() != "bearer":
      raise ValueError()
    sScopes = set(str(dToken["scope"]).split())
    if not set(fScopes(pConfig)).issubset(sScopes):
      raise ValueError()
  except (ValueError, KeyError, TypeError, channels.ChannelError):
    raise channels.ChannelRejected("X did not grant the required permissions or a refresh token. Authorize X again.") from None
  return {"access_token": dToken["access_token"], "refresh_token": dToken["refresh_token"],
          "expires_at": int(time.time()) + vExpiry, "scopes": sorted(sScopes)}


def fStartAuthorization(pCallbackUrl):
  dUrl = urlsplit(pCallbackUrl)
  if (dUrl.scheme != "https" or not dUrl.hostname or dUrl.username or dUrl.password
      or dUrl.path != cCallbackPath or dUrl.query or dUrl.fragment):
    raise channels.ChannelRejected("Open BoA over HTTPS before authorizing X.")
  with fLockedConfig() as dConfig:
    fCredential(dConfig, "client_id")
    fCredential(dConfig, "client_secret")
    vState = secrets.token_urlsafe(32)
    vVerifier = secrets.token_urlsafe(64)
    dConfig["_oauth"] = {"state": vState, "verifier": vVerifier,
      "callback": pCallbackUrl, "expires_at": int(time.time()) + 600}
    fWriteConfig(dConfig)
    vChallenge = base64.urlsafe_b64encode(hashlib.sha256(vVerifier.encode()).digest()).decode().rstrip("=")
    return vState, cAuthorizeUrl + "?" + urlencode({
      "response_type": "code", "client_id": dConfig["client_id"], "redirect_uri": pCallbackUrl,
      "scope": " ".join(fScopes(dConfig)), "state": vState,
      "code_challenge": vChallenge, "code_challenge_method": "S256"})


def fCompleteAuthorization(pState, pCode):
  with fLockedConfig() as dConfig:
    dFlow = dConfig.get("_oauth") or {}
    if (not pState or not isinstance(pCode, str) or not pCode
        or not secrets.compare_digest(str(dFlow.get("state", "")), pState)
        or int(dFlow.get("expires_at", 0)) < time.time()):
      raise channels.ChannelRejected("The X authorization expired or belongs to another session. Start again in Settings → Channels.")
    dConfig.pop("_oauth", None)
    fWriteConfig(dConfig)
    dToken = fExchange(dConfig, {"grant_type": "authorization_code", "code": pCode,
      "redirect_uri": dFlow["callback"], "code_verifier": dFlow["verifier"]})
    # Read-only identity lookup: authorization itself never sends anything.
    try:
      vResponse = requests.get("https://api.x.com/2/users/me",
        headers={"Authorization": "Bearer " + dToken["access_token"]}, timeout=30, allow_redirects=False)
      dUser = vResponse.json().get("data", {}) if vResponse.status_code == 200 else {}
      if not str(dUser.get("id", "")).isdigit() or not dUser.get("username"):
        raise ValueError()
    except (requests.RequestException, ValueError, TypeError, AttributeError):
      raise channels.ChannelRejected("X could not confirm the authorized account. Check API access and available credits, then authorize again.") from None
    dConfig.update(dToken)
    dConfig.update({"account_id": str(dUser["id"]), "account_username": str(dUser["username"]),
      "auth_generation": secrets.token_hex(16), "listen": False})
    fWriteConfig(dConfig)


def fAccessToken(pConfig):
  """Refresh once under the shared lock; never switch a queued task's account."""
  with fLockedConfig() as dCurrent:
    if (not dCurrent.get("enabled", True) or not pConfig.get("auth_generation")
        or any(dCurrent.get(vKey) != pConfig.get(vKey) for vKey in (
          "auth_generation", "account_id", "recipient_id", "allow_posts", "listen"))):
      raise channels.ChannelRejected("The X authorization changed or was disabled. Reload its configuration.")
    if int(dCurrent.get("expires_at", 0)) <= time.time() + 60:
      dCurrent.update(fExchange(dict(dCurrent, allow_posts="tweet.write" in (dCurrent.get("scopes") or [])), {"grant_type": "refresh_token",
        "refresh_token": fCredential(dCurrent, "refresh_token")}))
      fWriteConfig(dCurrent)
    return fCredential(dCurrent, "access_token")


def fSaveSettings(pChanges):
  """Only operator settings are writable through the generic channel form."""
  sAllowed = {"enabled", "listen", "allow_posts", "client_id", "client_secret", "recipient_id"}
  if set(pChanges) - sAllowed:
    raise channels.ChannelRejected("Unknown X setting. Use Client ID, Client Secret and the authorized recipient's numeric ID.")
  with fLockedConfig() as dConfig:
    vWasListening = bool(dConfig.get("enabled", True) and dConfig.get("listen"))
    vChangedApp = any(pChanges.get(vKey) and pChanges[vKey] != dConfig.get(vKey)
                      for vKey in ("client_id", "client_secret"))
    for vKey, vValue in pChanges.items():
      if vKey in ("enabled", "listen", "allow_posts"):
        if not isinstance(vValue, bool):
          raise channels.ChannelRejected("X %s must be true or false." % vKey)
      elif not isinstance(vValue, str):
        raise channels.ChannelRejected("X %s must be text." % vKey)
      if vKey == "client_secret" and not vValue:
        continue
      dConfig[vKey] = vValue.strip() if isinstance(vValue, str) else vValue
    dConfig.setdefault("enabled", True)
    if vChangedApp:
      for vKey in lTokenFields + ["_oauth"]:
        dConfig.pop(vKey, None)
    vRecipient = str(dConfig.get("recipient_id") or "")
    if vRecipient and (not vRecipient.isascii() or not vRecipient.isdigit() or len(vRecipient) > 19):
      raise channels.ChannelRejected("X recipient_id must be a numeric user ID, not an @username.")
    if vRecipient and vRecipient == dConfig.get("account_id"):
      raise channels.ChannelRejected("The X recipient must be a different account from the account used by BoA.")
    if dConfig.get("enabled") and dConfig.get("listen"):
      if not dConfig.get("auth_generation") or not vRecipient:
        raise channels.ChannelRejected("Authorize X and configure recipient_id before enabling direct-message reception.")
      if not set(lBaseScopes).issubset(set(dConfig.get("scopes") or [])):
        raise channels.ChannelRejected("Authorize X again to grant direct-message access.")
      if not vWasListening:
        dConfig["poll_generation"] = secrets.token_hex(16)
    fWriteConfig(dConfig)
