"""Bound and fairly queue agent access to the private inference socket."""

from collections import deque
from contextlib import contextmanager
import http.client
from http.server import BaseHTTPRequestHandler
import json
import socket
import threading

from backend.core import local_server

cMaxBodyBytes = 128 * 1024


class EmbeddingProxy(local_server.BoundedUnixServer):
  def __init__(self, pPublicPath, pPrivatePath):
    self.vPrivatePath = pPrivatePath
    self.vQueueCondition = threading.Condition()
    self.lQueue = deque()
    super().__init__(pPublicPath, EmbeddingHandler)

  @contextmanager
  def fTurn(self):
    vTicket = object()
    with self.vQueueCondition:
      self.lQueue.append(vTicket)
      self.vQueueCondition.wait_for(lambda: self.lQueue[0] is vTicket)
    try:
      yield
    finally:
      with self.vQueueCondition:
        self.lQueue.popleft()
        self.vQueueCondition.notify_all()


def fValidateRequest(pPath, pBody):
  """No engine controls, unbounded batches, token arrays or client overrides."""
  if not isinstance(pBody, dict):
    raise ValueError("Expected an object")
  if pPath == "/tokenize":
    vText = pBody.get("content")
    if not isinstance(vText, str) or len(vText) > 8192:
      raise ValueError("Tokenization input is too large")
    return {"content": vText, "add_special": False}
  if pPath == "/v1/embeddings":
    lInput = pBody.get("input")
    if (not isinstance(lInput, list) or len(lInput) != 1
        or not isinstance(lInput[0], str) or len(lInput[0]) > 8192):
      raise ValueError("Submit one bounded text per embedding request")
    return {"input": lInput, "encoding_format": "float"}
  raise ValueError("Endpoint is not available")


class EmbeddingHandler(BaseHTTPRequestHandler):
  timeout = 5

  def log_message(self, pFormat, *pArguments):
    pass

  def fReply(self, pStatus, pData):
    self.send_response(pStatus)
    self.send_header("Content-Type", "application/json")
    self.send_header("Content-Length", str(len(pData)))
    self.send_header("Connection", "close")
    self.end_headers()
    self.wfile.write(pData)

  def do_GET(self):
    self.fForward()

  def do_POST(self):
    self.fForward()

  def fForward(self):
    vConnection = None
    try:
      vBody = None
      if self.command == "GET":
        if self.path not in ("/health", "/v1/models"):
          raise ValueError("Endpoint is not available")
      else:
        if self.headers.get("Transfer-Encoding"):
          raise ValueError("Chunked requests are not accepted")
        vLength = int(self.headers.get("Content-Length", "0"))
        if not 0 < vLength <= cMaxBodyBytes:
          raise ValueError("Request is too large")
        vBody = json.dumps(fValidateRequest(
          self.path, json.loads(self.rfile.read(vLength)))).encode()
      with self.server.fTurn():
        vConnection = http.client.HTTPConnection("localhost", timeout=30)
        vConnection.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        vConnection.sock.settimeout(30)
        vConnection.sock.connect(self.server.vPrivatePath)
        vConnection.request(self.command, self.path, vBody,
                            {"Content-Type": "application/json"})
        vResponse = vConnection.getresponse()
        vData = vResponse.read(1024 * 1024 + 1)
        if len(vData) > 1024 * 1024:
          raise ValueError("Engine response is too large")
      self.fReply(vResponse.status, vData)
    except (ValueError, RecursionError):
      self.fReply(400, b'{"error":"Invalid or oversized embedding request"}')
    except (OSError, http.client.HTTPException):
      try:
        self.fReply(503, b'{"error":"Embedding engine unavailable"}')
      except OSError:
        pass
    finally:
      if vConnection is not None:
        vConnection.close()
