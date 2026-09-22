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

from backend.core import tool_registry
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

# How many bytes are read off the wire at all. Far above what is shown,
# because the point is to bound what this process holds rather than to cut the
# page short: a document that needs more than this is not one to put in a
# conversation.
cMaxResponseBytes = 4 * 1024 * 1024
cMaxRedirects = 5

def fTruncate(pText, pLimit=cMaxResponseCharacters):
  """Return text cut to a limit, saying how much was dropped."""
  vText = str(pText or "")
  if len(vText) <= pLimit:
    return vText
  return "%s\n\n[... %d characters omitted ...]" % (
    vText[:pLimit], len(vText) - pLimit
  )


def fDecodeBody(pResponse, pChunks):
  """Decode a streamed body, without asking the response to re-read itself.

  `apparent_encoding` runs chardet over `response.content`, and `content` on a
  streamed response that has already been iterated raises "the content for
  this response was already consumed". So the header's charset is used when
  there is one, and UTF-8 otherwise - which is what almost every feed and page
  is, and a wrong guess only produces replacement characters rather than an
  exception in the middle of a tool call.
  """
  vRaw = b"".join(pChunks)
  vEncoding = pResponse.encoding or "utf-8"
  try:
    return vRaw.decode(vEncoding, "replace")
  except (LookupError, TypeError):
    return vRaw.decode("utf-8", "replace")


def fReadBoundedBody(pResponse):
  """Return a response body, stopping once there is more than anyone needs.

  The connection is closed either way, which is what returns it to the pool
  and stops a half-read response holding a socket open for the rest of the
  run.
  """
  lChunks = []
  vBytes = 0
  vTruncated = False
  try:
    for vChunk in pResponse.iter_content(chunk_size=65536):
      if not vChunk:
        continue
      lChunks.append(vChunk)
      vBytes += len(vChunk)
      if vBytes >= cMaxResponseBytes:
        vTruncated = True
        break
  finally:
    pResponse.close()

  vText = fDecodeBody(pResponse, lChunks)

  if vTruncated:
    return "%s\n\n[... the response was longer than %d bytes and the rest was not read ...]" % (
      fTruncate(vText), cMaxResponseBytes)
  return fTruncate(vText)


def fRunTool(pArguments, pContext):
  """Fetch one URL and return its body as text."""
  vUrl = str(pArguments.get("url") or "").strip()
  if not vUrl:
    raise tool_registry.ToolFailure("No URL given.")

  vMethod = str(pArguments.get("method") or "GET").upper()
  if vMethod not in ("GET", "POST"):
    raise tool_registry.ToolFailure("Only GET and POST are supported.")

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
      raise tool_registry.ToolFailure("Refused: %s" % (vError,))

    try:
      vResponse = requests.request(
        vMethod,
        vCurrentUrl,
        data=pArguments.get("body") if vMethod == "POST" else None,
        headers={"User-Agent": cUserAgent},
        timeout=vTimeout,
        # Redirects are followed by hand so each hop is checked too.
        allow_redirects=False,
        # Streamed, so that the ceiling below runs WHILE the body arrives.
        # `vResponse.text` reads the whole thing first and truncates after,
        # which caps what the model is shown and not what this process holds:
        # a server answering with a gigabyte was bounded by the timeout and by
        # nothing else.
        stream=True,
      )
    except requests.Timeout:
      raise tool_registry.ToolFailure(
        "The request timed out after %d seconds." % (vTimeout,))
    except requests.RequestException as vError:
      raise tool_registry.ToolFailure("The request failed: %s" % (vError,))

    if vResponse.status_code in (301, 302, 303, 307, 308):
      vLocation = vResponse.headers.get("Location") or ""
      if not vLocation:
        raise tool_registry.ToolFailure(
          "Got a redirect with no destination (HTTP %d)."
          % (vResponse.status_code,))
      vCurrentUrl = urllib.parse.urljoin(vCurrentUrl, vLocation)
      continue

    vContentType = vResponse.headers.get("Content-Type", "")
    try:
      vBody = fReadBoundedBody(vResponse)
    except requests.Timeout:
      raise tool_registry.ToolFailure(
        "The request timed out after %d seconds." % (vTimeout,))
    except requests.RequestException as vError:
      raise tool_registry.ToolFailure(
        "The response could not be read: %s" % (vError,))
    return "HTTP %d %s\nContent-Type: %s\n\n%s" % (
      vResponse.status_code, vResponse.reason or "", vContentType, vBody
    )

  raise tool_registry.ToolFailure(
    "Gave up after %d redirects." % (cMaxRedirects,))
