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
    if not fIsPublicAddress(vIpAddress):
      raise UnsafeUrlError(
        "%s resolves to %s, which is not a public address. Agents may only "
        "fetch public pages." % (dParsed.hostname, vAddress)
      )
  return True


def fIsPublicAddress(pIpAddress):
  """Return whether one resolved address is somewhere an agent may reach.

  Stated positively, with `is_global`, rather than as a list of the ranges to
  refuse. The list was the thing to get wrong: it named private, loopback,
  reserved, link-local and multicast, and 100.64.0.0/10 - carrier-grade NAT,
  which is also what Tailscale and several hosts hand out on their internal
  networks - is in none of those, so it was allowed through. `is_global` is
  Python's own answer to "is this routable on the public internet", and it
  gets a new range right on the day the standard library does.

  IPv4 carried inside IPv6 is unwrapped first. `::ffff:127.0.0.1` is loopback
  written the long way, and asking an IPv6 address whether it is loopback
  answers about the IPv6 address, not the IPv4 one inside it.

  Multicast is refused on top of `is_global`, not by it: `224.0.0.1.is_global`
  is True, and 224.0.0.0/4 was on the old list. Replacing that list with
  `is_global` alone would have fixed one range and opened another.
  """
  vAddress = pIpAddress
  vMapped = getattr(vAddress, "ipv4_mapped", None)
  if vMapped is not None:
    vAddress = vMapped

  if vAddress.is_multicast:
    return False
  return bool(vAddress.is_global)
