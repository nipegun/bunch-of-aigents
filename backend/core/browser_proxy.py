"""Per-run SOCKS5 egress: DNS is checked at the socket that actually connects."""

import select
import socket
import socketserver
import struct
import threading
import time

from backend.core import public_url


def fReadExact(pSocket, pSize):
  vData = bytearray()
  while len(vData) < pSize:
    vChunk = pSocket.recv(pSize - len(vData))
    if not vChunk:
      raise OSError("Incomplete proxy handshake")
    vData.extend(vChunk)
  return bytes(vData)


class PublicProxyHandler(socketserver.BaseRequestHandler):
  def handle(self):
    vUpstream = None
    self.request.settimeout(5)
    try:
      vVersion, vCount = fReadExact(self.request, 2)
      if vVersion != 5 or 0 not in fReadExact(self.request, vCount):
        return
      self.request.sendall(b"\x05\x00")
      vVersion, vCommand, vReserved, vType = fReadExact(self.request, 4)
      if (vVersion, vCommand, vReserved) != (5, 1, 0):
        return
      if vType == 1:
        vHost = socket.inet_ntop(socket.AF_INET, fReadExact(self.request, 4))
      elif vType == 4:
        vHost = "[%s]" % socket.inet_ntop(socket.AF_INET6, fReadExact(self.request, 16))
      elif vType == 3:
        vHost = fReadExact(self.request, fReadExact(self.request, 1)[0]).decode("ascii")
        if any(vCharacter in vHost for vCharacter in "/\\@:#?[]%"):
          return
      else:
        return
      vPort = struct.unpack("!H", fReadExact(self.request, 2))[0]
      if not vPort:
        return
      vUpstream = public_url.fConnectPublic("http://%s:%d" % (vHost, vPort), 15)
      self.request.sendall(b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00")
      vDeadline = time.monotonic() + 120
      while time.monotonic() < vDeadline:
        lReady, _, _ = select.select([self.request, vUpstream], [], [], 15)
        if not lReady:
          break
        for vSource in lReady:
          vData = vSource.recv(65536)
          if not vData:
            return
          vTarget = vUpstream if vSource is self.request else self.request
          vTarget.sendall(vData)
    except (OSError, ValueError):
      pass
    finally:
      if vUpstream is not None:
        vUpstream.close()


class PublicProxy(socketserver.ThreadingTCPServer):
  daemon_threads = True
  allow_reuse_address = True

  def __init__(self):
    self.vSlots = threading.BoundedSemaphore(32)
    super().__init__(("127.0.0.1", 0), PublicProxyHandler)

  def process_request(self, pRequest, pAddress):
    if not self.vSlots.acquire(blocking=False):
      self.shutdown_request(pRequest)
      return
    try:
      super().process_request(pRequest, pAddress)
    except Exception:
      self.vSlots.release()
      raise

  def process_request_thread(self, pRequest, pAddress):
    try:
      super().process_request_thread(pRequest, pAddress)
    finally:
      self.vSlots.release()


def fStart():
  vServer = PublicProxy()
  threading.Thread(target=vServer.serve_forever, daemon=True).start()
  return vServer
