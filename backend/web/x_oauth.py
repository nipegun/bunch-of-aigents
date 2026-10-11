"""Browser return from X, bound to the administrator's initiating session."""

import secrets

from flask import Blueprint, redirect, request, session

from backend.core import channels, x_auth
from backend.web import auth

vXOAuthBlueprint = Blueprint("x_oauth", __name__, url_prefix="/api/channels/x/oauth")


@vXOAuthBlueprint.route("/callback", methods=["GET"])
@auth.fRequireLogin
def fCompleteXAuthorization():
  vExpected = session.pop("x_oauth_state", "")
  vState = request.args.get("state", "")
  vResult = "error"
  if vExpected and secrets.compare_digest(vExpected, vState) and not request.args.get("error"):
    try:
      x_auth.fCompleteAuthorization(vState, request.args.get("code", ""))
      vResult = "ok"
    except channels.ChannelError:
      pass
  vResponse = redirect("/settings/?tab=channels&x_auth=" + vResult, code=303)
  vResponse.headers["Cache-Control"] = "no-store"
  vResponse.headers["Referrer-Policy"] = "no-referrer"
  return vResponse
