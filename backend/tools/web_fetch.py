"""Tool: web.fetch - read a web page.

Runs inside the agent's own process, because fetching a URL needs no privilege
the agent does not already have.

What it does add is a guard the agent cannot be talked out of: the target is
resolved before the request and refused if it points at a private address.
That check is `core.public_url`, shared with rss.fetch, because a security
check with two implementations has two chances of being wrong.

Redirects are followed manually: a public URL that redirects to
169.254.169.254 would otherwise walk straight past a check done only on the
original address.
"""

import urllib.parse

import requests

from backend.core.public_url import (UnsafeUrlError, cUserAgent,
                                     fCheckUrlIsPublic)

cToolName = "web.fetch"

cToolDescription = (
  "Fetch a public web page or API endpoint over HTTP and return its content as "
  "text. Only public addresses are allowed. Large pages are truncated."
)

dToolSchema = {
  "type": "object",
  "properties": {
    "url": {
      "type": "string",
      "description": "The http:// or https:// URL to fetch.",
    },
    "method": {
      "type": "string",
      "enum": ["GET", "POST"],
      "description": "HTTP method. Defaults to GET.",
    },
    "body": {
      "type": "string",
      "description": "Request body, for POST.",
    },
    "timeout_seconds": {
      "type": "integer",
      "description": "Seconds before giving up. Default 30, max 120.",
    },
  },
  "required": ["url"],
  "additionalProperties": False,
}

cDefaultTimeoutSeconds = 30
cMaxTimeoutSeconds = 120
cMaxResponseCharacters = 20000
cMaxRedirects = 5

def fTruncate(pText, pLimit=cMaxResponseCharacters):
  """Return text cut to a limit, saying how much was dropped."""
  vText = str(pText or "")
  if len(vText) <= pLimit:
    return vText
  return "%s\n\n[... %d characters omitted ...]" % (
    vText[:pLimit], len(vText) - pLimit
  )


def fRunTool(pArguments, pContext):
  """Fetch one URL and return its body as text."""
  vUrl = str(pArguments.get("url") or "").strip()
  if not vUrl:
    return "No URL given."

  vMethod = str(pArguments.get("method") or "GET").upper()
  if vMethod not in ("GET", "POST"):
    return "Only GET and POST are supported."

  vTimeout = pArguments.get("timeout_seconds") or cDefaultTimeoutSeconds
  try:
    vTimeout = max(1, min(int(vTimeout), cMaxTimeoutSeconds))
  except (TypeError, ValueError):
    vTimeout = cDefaultTimeoutSeconds

  vCurrentUrl = vUrl
  for vRedirectCount in range(cMaxRedirects + 1):
    try:
      fCheckUrlIsPublic(vCurrentUrl)
    except UnsafeUrlError as vError:
      return "Refused: %s" % (vError,)

    try:
      vResponse = requests.request(
        vMethod,
        vCurrentUrl,
        data=pArguments.get("body") if vMethod == "POST" else None,
        headers={"User-Agent": cUserAgent},
        timeout=vTimeout,
        # Redirects are followed by hand so each hop is checked too.
        allow_redirects=False,
      )
    except requests.Timeout:
      return "The request timed out after %d seconds." % (vTimeout,)
    except requests.RequestException as vError:
      return "The request failed: %s" % (vError,)

    if vResponse.status_code in (301, 302, 303, 307, 308):
      vLocation = vResponse.headers.get("Location") or ""
      if not vLocation:
        return "Got a redirect with no destination (HTTP %d)." % (vResponse.status_code,)
      vCurrentUrl = urllib.parse.urljoin(vCurrentUrl, vLocation)
      continue

    vContentType = vResponse.headers.get("Content-Type", "")
    vBody = fTruncate(vResponse.text)
    return "HTTP %d %s\nContent-Type: %s\n\n%s" % (
      vResponse.status_code, vResponse.reason or "", vContentType, vBody
    )

  return "Gave up after %d redirects." % (cMaxRedirects,)
