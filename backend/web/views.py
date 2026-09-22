"""HTML pages.

The pages are server-rendered shells; everything that changes while the page is
open is fetched from /api/admin/ by the page's own JavaScript. There is no
build step: the production server is a self-hosted Debian box, and a deployment
that needs a Node toolchain to change a stylesheet is a deployment that rots.
"""

import os

from flask import (Blueprint, g, redirect, render_template, request,
                   send_from_directory, session, url_for)

from backend.core import themes
from backend.web import auth

vViewsBlueprint = Blueprint("views", __name__)


@vViewsBlueprint.route("/themes/<vThemeName>.css", methods=["GET"])
def fThemeStylesheet(vThemeName):
  """Serve one theme's stylesheet.

  Public, like /static/: it is a palette shipped with the installation, holds
  no data, and the login page is themed too - asking for a session to paint the
  form somebody is about to log in with would be theatre.

  The name is validated rather than cleaned. `fGetThemePath` refuses anything
  that is not a plain theme name, so a crafted URL cannot walk out of the
  directory.
  """
  try:
    vPath = themes.fGetThemePath(vThemeName)
  except ValueError:
    return "", 404
  if not os.path.isfile(vPath):
    return "", 404
  return send_from_directory(
    themes.fGetThemesDirectory(), "%s.css" % (vThemeName,),
    mimetype="text/css"
  )


@vViewsBlueprint.route("/login", methods=["GET", "POST"])
def fLoginPage():
  """Show and handle the login form."""
  if auth.fIsLoggedIn():
    return redirect(url_for("views.fDashboardPage"))

  vError = ""
  if request.method == "POST":
    vRemoteAddress = auth.fGetRemoteAddress()

    if auth.fCountRecentFailures(vRemoteAddress) >= auth.cMaxAttempts:
      vError = "too_many_attempts"
    else:
      vEmail = request.form.get("email", "")
      vPassword = request.form.get("password", "")
      if auth.fVerifyCredentials(vEmail, vPassword):
        auth.fRecordAttempt(vRemoteAddress, True)
        auth.fLogIn(vEmail)
        vNextPath = request.args.get("next") or url_for("views.fDashboardPage")
        # Only relative paths, so a crafted link cannot bounce the login
        # through to another site.
        if not vNextPath.startswith("/") or vNextPath.startswith("//"):
          vNextPath = url_for("views.fDashboardPage")
        return redirect(vNextPath)
      auth.fRecordAttempt(vRemoteAddress, False)
      vError = "bad_credentials"

  return render_template("login.html", vError=vError)


@vViewsBlueprint.route("/logout", methods=["POST", "GET"])
def fLogoutPage():
  """End the session and go back to the login page."""
  auth.fLogOut()
  return redirect(url_for("views.fLoginPage"))


@vViewsBlueprint.route("/", methods=["GET"])
@auth.fRequireLogin
def fDashboardPage():
  """The main page: agent sidebar and the selected agent's configuration."""
  return render_template("dashboard.html", vActiveSection="agents")


@vViewsBlueprint.route("/kanban/", methods=["GET"])
@auth.fRequireLogin
def fKanbanPage():
  """The board."""
  return render_template("kanban.html", vActiveSection="kanban")


@vViewsBlueprint.route("/tools/", methods=["GET"])
@auth.fRequireLogin
def fToolsPage():
  """Keep old tool bookmarks pointing at their family inside Settings."""
  return redirect(url_for("views.fSettingsPage", tab="tools",
                          family=request.args.get("family"),
                          agent=request.args.get("agent")))


@vViewsBlueprint.route("/settings/", methods=["GET"])
@auth.fRequireLogin
def fSettingsPage():
  """Channels, account and interface settings."""
  return render_template("settings.html", vActiveSection="settings")
