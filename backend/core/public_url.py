"""Whether a URL an agent was given points somewhere it may go.

This lived inside web.fetch until a second tool needed it. A security check
with two implementations is a security check with two chances of being wrong,
and the second copy is always the one that does not get the fix.

What it defends against: an agent reading an attacker-chosen page - or an
attacker-chosen feed - can be told "now fetch http://127.0.0.1:11443/api/..."
or the cloud metadata address, and from inside the LAN it would work. The
check runs on the RESOLVED address rather than on the hostname, because a
hostname resolves wherever its owner likes.
"""

import ipaddress
import socket
import urllib.parse

# Identify the caller honestly: a site owner reading their logs should be able
# to tell that this was an automated agent.
cUserAgent = "BunchOfAIgents/1.0 (+https://github.com/nipegun/bunch-of-aigents)"


class UnsafeUrlError(ValueError):
  """Raised when a URL points somewhere an agent must not reach."""


def fCheckUrlIsPublic(pUrl):
  """Raise unless the URL resolves to a public address.

  Checks every address the hostname resolves to, not just the first: a name
  with one public and one private A record would otherwise get through on a
  lucky ordering.
  """
  dParsed = urllib.parse.urlparse(pUrl)
  if dParsed.scheme not in ("http", "https"):
    raise UnsafeUrlError(
      "Only http and https URLs are allowed, not %r." % (dParsed.scheme,)
    )
  if not dParsed.hostname:
    raise UnsafeUrlError("That URL has no hostname.")

  try:
    lAddressInfo = socket.getaddrinfo(dParsed.hostname, None)
  except socket.gaierror as vError:
    raise UnsafeUrlError("Cannot resolve %s: %s" % (dParsed.hostname, vError))

  for vAddressInfo in lAddressInfo:
    vAddress = vAddressInfo[4][0]
    try:
      vIpAddress = ipaddress.ip_address(vAddress)
    except ValueError:
      raise UnsafeUrlError("Cannot parse the address %r." % (vAddress,))
    if vIpAddress.is_private or vIpAddress.is_loopback or vIpAddress.is_reserved \
       or vIpAddress.is_link_local or vIpAddress.is_multicast:
      raise UnsafeUrlError(
        "%s resolves to %s, which is not a public address. Agents may only "
        "fetch public pages." % (dParsed.hostname, vAddress)
      )
  return True
