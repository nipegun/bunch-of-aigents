#!/usr/bin/env -S PYTHONDONTWRITEBYTECODE=1 python3

"""Flask application factory and entry point.

Gunicorn imports `vApp` from this module. Running it directly starts Flask's
own server, which is for development on the code machine only - production
always goes through gunicorn, because that is what terminates TLS and speaks
PROXY protocol to the local HAProxy.
"""

import datetime
import os
import secrets
import sys
import time

from flask import Flask, jsonify, request

from backend.core import db
from backend.core import paths
from backend.web import api
from backend.web import api_doc
from backend.web import auth
from backend.web import views

# Where the session signing key is kept. Generated on first start and readable
# only by the boa user: anyone who can read it can forge a session.
cSecretKeyFileName = "session-secret"

# How long a worker that lost the race waits for the winner to write the key.
# It is waiting for one small write, so this is generous by a wide margin; it
# exists so that a worker never spins for ever on a file that stays empty.
cSecretKeyWaitSeconds = 5


def fReadSecretKey(pPath):
  """Return the stored session key, or "" when there is not a usable one."""
  try:
    with open(pPath, "r", encoding="utf-8") as vFile:
      vSecret = vFile.read().strip()
      if len(vSecret) >= 32:
        return vSecret
  except OSError:
    pass
  return ""


def fGetOrCreateSecretKey():
  """Return the session signing key, generating it once if needed.

  Kept in a file rather than in the database so that a corrupt database means
  a lost board, not a login that cannot be trusted.

  Created with O_CREAT|O_EXCL, and the file is READ BACK afterwards. Both
  halves matter, because gunicorn runs several workers and each builds its own
  application: on a first start they all find no key, all generate one, and
  all write it. Writing to a shared temporary name and renaming meant the last
  rename won and every other worker went on using the key it had generated and
  thrown away - so a login succeeded or failed depending on which worker
  answered, and the answer changed from request to request.

  O_EXCL makes exactly one of them the creator. Everybody else gets EEXIST and
  reads what the winner wrote, so all of them end up with the same key.
  """
  vSecretPath = os.path.join(paths.fGetConfigDir(), cSecretKeyFileName)
  vSecret = fReadSecretKey(vSecretPath)
  if vSecret:
    return vSecret

  vCandidate = secrets.token_hex(32)
  try:
    os.makedirs(os.path.dirname(vSecretPath), exist_ok=True)
    vDescriptor = os.open(
      vSecretPath, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
      with os.fdopen(vDescriptor, "w", encoding="utf-8") as vFile:
        vFile.write(vCandidate + "\n")
        vFile.flush()
        os.fsync(vFile.fileno())
    except Exception:
      # A half-written key is worse than none: the next start would read it,
      # find it long enough and sign sessions with a truncated secret.
      try:
        os.unlink(vSecretPath)
      except OSError:
        pass
      raise
    return vCandidate
  except FileExistsError:
    # Another worker got there first. Its key is the one on disk, and the one
    # every worker has to use - but O_CREAT made the file exist before the
    # winner had written anything into it, so reading once lands on an empty
    # file often enough to matter. Measured: eight workers released together
    # produced three different keys with a single read.
    #
    # So the losers wait for the content, briefly and with a deadline. The
    # window is one small write; a worker still finding nothing after this
    # long is looking at something else, and says so below rather than
    # spinning.
    vDeadline = time.monotonic() + cSecretKeyWaitSeconds
    while True:
      vSecret = fReadSecretKey(vSecretPath)
      if vSecret:
        return vSecret
      if time.monotonic() >= vDeadline:
        break
      time.sleep(0.01)
  except OSError:
    pass

  # Either the directory is not writable, or the file exists and cannot be
  # read. Both mean every worker signs with a different key, which is a login
  # that works or does not depending on who answers - so it is said out loud
  # rather than discovered later.
  sys.stderr.write(
    "Cannot establish a shared session key at %s. Sessions will break across "
    "gunicorn workers until this is fixed.\n" % (vSecretPath,)
  )
  return vCandidate


def fCreateApp():
  """Build the Flask application."""
  vWebAppDir = paths.fGetWebAppDir()
  vTemplateDir = os.path.join(vWebAppDir, "frontend", "templates")
  vStaticDir = os.path.join(vWebAppDir, "frontend", "static")

  # On the development machine the code is not deployed under /opt/boa, so the
  # templates are looked up relative to this file instead.
  if not os.path.isdir(vTemplateDir):
    vProjectDir = os.path.dirname(os.path.dirname(os.path.dirname(
      os.path.abspath(__file__)
    )))
    vTemplateDir = os.path.join(vProjectDir, "frontend", "templates")
    vStaticDir = os.path.join(vProjectDir, "frontend", "static")

  vApplication = Flask(
    __name__,
    template_folder=vTemplateDir,
    static_folder=vStaticDir,
    static_url_path="/static",
  )

  vApplication.config.update(
    SECRET_KEY=fGetOrCreateSecretKey(),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    # The site is served over HTTPS by gunicorn, so the cookie never needs to
    # travel in clear.
    SESSION_COOKIE_SECURE=True,
    PERMANENT_SESSION_LIFETIME=datetime.timedelta(
      hours=auth.cSessionLifetimeHours
    ),
    MAX_CONTENT_LENGTH=2 * 1024 * 1024,
    JSON_SORT_KEYS=False,
  )

  db.fCreateAppSchema()
  db.fCreateKanbanSchema()

  vApplication.register_blueprint(views.vViewsBlueprint)
  vApplication.register_blueprint(api.vApiBlueprint)
  vApplication.register_blueprint(api_doc.vApiDocBlueprint)

  @vApplication.after_request
  def fAddSecurityHeaders(pResponse):
    """Add the headers a single-user LAN application still benefits from."""
    pResponse.headers["X-Content-Type-Options"] = "nosniff"
    pResponse.headers["X-Frame-Options"] = "DENY"
    pResponse.headers["Referrer-Policy"] = "same-origin"
    # Everything is served from this origin: no CDN, no external font, no
    # analytics. Saying so closes off injected script as a class of problem.
    pResponse.headers["Content-Security-Policy"] = (
      "default-src 'self'; img-src 'self' data:; style-src 'self'; "
      "script-src 'self'; connect-src 'self'; frame-ancestors 'none'; "
      "base-uri 'self'; form-action 'self'"
    )
    return pResponse

  @vApplication.errorhandler(404)
  def fHandleNotFound(pError):
    if request.path.startswith("/api/"):
      return jsonify({"ok": False, "error": "No such endpoint"}), 404
    return ("Not found", 404)

  @vApplication.errorhandler(500)
  def fHandleServerError(pError):
    if request.path.startswith("/api/"):
      return jsonify({"ok": False, "error": "Internal error"}), 500
    return ("Internal error", 500)

  return vApplication


# Gunicorn's entry point.
vApp = fCreateApp()


def fMain():
  """Run Flask's development server. Never used in production."""
  vApp.run(
    host=paths.cBindAddress,
    port=int(os.environ.get("BOA_DEV_PORT", paths.cHttpsPort)),
    debug=False,
  )
  return 0


if __name__ == "__main__":
  sys.exit(fMain())
