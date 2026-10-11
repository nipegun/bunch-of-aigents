"""Bound local RPC work before allocating a thread or reading a request."""

import pwd
import re
import socket
import socketserver
import struct
import threading
import time


def fPeerUid(pSocket):
  return struct.unpack("3i", pSocket.getsockopt(
    socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))[1]


def fReadRequest(pSocket, pLimit, pSeconds):
  """Read one line with both a byte ceiling and an absolute deadline."""
  vDeadline = time.monotonic() + pSeconds
  vData = bytearray()
  while len(vData) <= pLimit:
    vRemaining = vDeadline - time.monotonic()
    if vRemaining <= 0:
      raise TimeoutError("Request deadline exceeded")
    pSocket.settimeout(vRemaining)
    vChunk = pSocket.recv(min(8192, pLimit + 1 - len(vData)))
    if not vChunk:
      raise ValueError("Incomplete request")
    vData.extend(vChunk)
    if b"\n" in vChunk:
      if len(vData) > pLimit or not vData.endswith(b"\n"):
        raise ValueError("Oversized or multiple requests")
      return bytes(vData)
  raise ValueError("Request is too large")


class BoundedUnixServer(socketserver.ThreadingUnixStreamServer):
  """Only agent/service UIDs, with limits enforced before thread creation."""

  daemon_threads = True
  allow_reuse_address = True
  cMaxConnections = 32
  cMaxConnectionsPerUid = 2

  def __init__(self, *pArguments, **pdOptions):
    self.vAdmissionLock = threading.Lock()
    self.dConnections = {}
    super().__init__(*pArguments, **pdOptions)

  def fAllowUid(self, pUid):
    if pUid == 0:
      return True
    try:
      vName = pwd.getpwuid(pUid).pw_name
    except KeyError:
      return False
    return vName == "boa" or bool(re.fullmatch(r"agent-[0-9]{3}", vName))

  def process_request(self, pRequest, pAddress):
    try:
      vUid = fPeerUid(pRequest)
      if not self.fAllowUid(vUid):
        self.shutdown_request(pRequest)
        return
      with self.vAdmissionLock:
        if (sum(self.dConnections.values()) >= self.cMaxConnections
            or self.dConnections.get(vUid, 0) >= self.cMaxConnectionsPerUid):
          self.shutdown_request(pRequest)
          return
        self.dConnections[vUid] = self.dConnections.get(vUid, 0) + 1
      try:
        super().process_request(pRequest, pAddress)
      except Exception:
        self.fRelease(vUid)
        raise
    except OSError:
      self.shutdown_request(pRequest)

  def fRelease(self, pUid):
    with self.vAdmissionLock:
      self.dConnections[pUid] -= 1
      if not self.dConnections[pUid]:
        del self.dConnections[pUid]

  def process_request_thread(self, pRequest, pAddress):
    vUid = fPeerUid(pRequest)
    try:
      super().process_request_thread(pRequest, pAddress)
    finally:
      self.fRelease(vUid)
