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
import threading
import time
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
  fResolvePublicUrl(pUrl)
  return True


def fResolvePublicUrl(pUrl):
  """Validate every result and return the exact numeric socket destinations."""
  try:
    dParsed = urllib.parse.urlparse(pUrl)
    vPort = dParsed.port or (443 if dParsed.scheme == "https" else 80)
  except ValueError as vError:
    raise UnsafeUrlError("Invalid URL") from vError
  if dParsed.scheme not in ("http", "https"):
    raise UnsafeUrlError(
      "Only http and https URLs are allowed, not %r." % (dParsed.scheme,)
    )
  if not dParsed.hostname:
    raise UnsafeUrlError("That URL has no hostname.")
  if dParsed.username is not None or dParsed.password is not None:
    raise UnsafeUrlError("Credentials in URLs are not allowed.")

  try:
    lAddressInfo = socket.getaddrinfo(dParsed.hostname, vPort, type=socket.SOCK_STREAM)
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
  if not lAddressInfo:
    raise UnsafeUrlError("The hostname has no addresses.")
  return lAddressInfo


def fConnectPublic(pUrl, pTimeout=30):
  """Connect to an already checked numeric address, never resolving it again."""
  lAddresses = fResolvePublicUrl(pUrl)
  vLastError = OSError("No public address could be reached")
  for vFamily, vType, vProtocol, _vName, vAddress in lAddresses:
    vSocket = socket.socket(vFamily, vType, vProtocol)
    try:
      vSocket.settimeout(pTimeout)
      vSocket.connect(vAddress)
      return vSocket
    except OSError as vError:
      vLastError = vError
      vSocket.close()
  raise vLastError


def fClampTimeout(pTimeout, pLeft):
  """A requests timeout no longer than pLeft seconds, scalar or (connect, read)."""
  if isinstance(pTimeout, tuple):
    return tuple(pLeft if vPart is None else min(float(vPart), pLeft) for vPart in pTimeout)
  if pTimeout is None:
    return pLeft
  return min(float(pTimeout), pLeft)


def fRequestPublic(pMethod, pUrl, pDeadline=None, **pdOptions):
  """Keep the hostname for Host, SNI and TLS verification; pin the TCP peer.

  pDeadline, a time.monotonic() value, ends the whole request there: the
  connection, the headers and, for a streamed response, the body, until it is
  closed. requests' own timeout is not that. It bounds how long one read may
  wait, so a server that sends a byte now and then - of the headers or of the
  body - kept a tool, and the run around it, going past every limit it had.
  At the deadline a timer shuts the socket down, and whatever was reading
  from it stops; the request raises requests.Timeout, and a body read after
  it is the caller's to check against the same deadline.
  """
  import requests
  from urllib3 import connection, connectionpool

  lSockets = []
  dCutOff = {"done": False}
  vLock = threading.Lock()

  def fCutOff():
    with vLock:
      dCutOff["done"] = True
      lOpen = list(lSockets)
    for vSocket in lOpen:
      try:
        vSocket.shutdown(socket.SHUT_RDWR)
      except OSError:
        pass

  class PublicConnection:
    def _new_conn(self):
      vScheme = "https" if isinstance(self, connection.HTTPSConnection) else "http"
      vHost = "[%s]" % self.host if ":" in self.host else self.host
      vSocket = fConnectPublic("%s://%s:%d" % (vScheme, vHost, self.port), self.timeout)
      with vLock:
        lSockets.append(vSocket)
        vLate = dCutOff["done"]
      if vLate:
        vSocket.close()
        raise OSError("The deadline passed while connecting.")
      return vSocket

  class PublicHttpConnection(PublicConnection, connection.HTTPConnection):
    pass

  class PublicHttpsConnection(PublicConnection, connection.HTTPSConnection):
    pass

  class PublicHttpPool(connectionpool.HTTPConnectionPool):
    ConnectionCls = PublicHttpConnection

  class PublicHttpsPool(connectionpool.HTTPSConnectionPool):
    ConnectionCls = PublicHttpsConnection

  vSession = requests.Session()
  vSession.trust_env = False
  vAdapter = requests.adapters.HTTPAdapter(max_retries=0)
  vAdapter.poolmanager.pool_classes_by_scheme = {
    "http": PublicHttpPool, "https": PublicHttpsPool}
  vSession.mount("http://", vAdapter)
  vSession.mount("https://", vAdapter)
  pdOptions["allow_redirects"] = False
  vTimer = None
  if pDeadline is not None:
    vLeft = pDeadline - time.monotonic()
    if vLeft <= 0:
      vSession.close()
      raise requests.Timeout("The deadline passed before the request was made.")
    pdOptions["timeout"] = fClampTimeout(pdOptions.get("timeout"), vLeft)
    vTimer = threading.Timer(vLeft, fCutOff)
    vTimer.daemon = True
    vTimer.start()
  try:
    vResponse = vSession.request(pMethod, pUrl, **pdOptions)
  except Exception as vError:
    if vTimer is not None:
      vTimer.cancel()
    vSession.close()
    if dCutOff["done"] and not isinstance(vError, requests.Timeout):
      raise requests.Timeout("The request did not finish before its deadline.") from vError
    raise
  fOriginalClose = vResponse.close

  def fClose():
    try:
      fOriginalClose()
    finally:
      if vTimer is not None:
        vTimer.cancel()
      vSession.close()

  vResponse.close = fClose
  return vResponse


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
