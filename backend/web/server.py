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


def fGetOrCreateSecretKey():
  """Return the session signing key, generating it once if needed.

  Kept in a file rather than in the database so that a corrupt database means
  a lost board, not a login that cannot be trusted.
  """
  vSecretPath = os.path.join(paths.fGetConfigDir(), cSecretKeyFileName)
  try:
    with open(vSecretPath, "r", encoding="utf-8") as vFile:
      vSecret = vFile.read().strip()
      if len(vSecret) >= 32:
        return vSecret
  except OSError:
    pass

  vSecret = secrets.token_hex(32)
  try:
    os.makedirs(os.path.dirname(vSecretPath), exist_ok=True)
    vTempPath = vSecretPath + ".tmp"
    with open(vTempPath, "w", encoding="utf-8") as vFile:
      vFile.write(vSecret + "\n")
    os.chmod(vTempPath, 0o600)
    os.replace(vTempPath, vSecretPath)
  except OSError:
    # This is worse than it looks. Gunicorn runs several workers, each building
    # its own application, so a key that cannot be persisted means every worker
    # signs sessions with a different one - and a login succeeds or fails
    # depending on which worker answers. The installer makes the directory
    # writable by the service user; if this ever fires, that is what broke.
    sys.stderr.write(
      "Cannot persist the session key at %s. Sessions will break across "
      "gunicorn workers until this is fixed.\n" % (vSecretPath,)
    )
  return vSecret


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
