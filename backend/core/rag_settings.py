"""RAG settings and paths. Embedding inference has no remote endpoint."""

import json
import math
import os
from pathlib import Path

from backend.core import paths

cSocketPath = "/run/boa-embeddings/engine.sock"
cUploadChunkBytes = 256 * 1024
cFormats = (".pdf", ".epub", ".txt", ".md")
dDefaults = {
  "enabled": False, "mode": "mixed", "max_file_mb": 128,
  "max_storage_mb": 2048, "max_chunks": 200000,
  "context_characters": 16000, "results": 8, "ocr": True,
  "ocr_languages": "eng+spa", "chunk_tokens": 320,
  "min_similarity": 0.2,
}
dRuntimeDefaults = {"threads": 2, "workers": 1, "ocr_languages": "eng+spa", "model": ""}


def fReadModelCatalogue():
  """The embedding models this installation can run, from rag_models.json.

  One file for everything that differs between models: where the weights come
  from and their hash, how the engine pools them, what goes before a query
  and before a passage, and the two similarities measured for each one.
  """
  return json.loads((Path(__file__).with_name("rag_models.json")).read_text())


def fFindModel(pModelId):
  if not isinstance(pModelId, str):
    return None
  return next((dModel for dModel in fReadModelCatalogue()["models"] if dModel["id"] == pModelId), None)


def fSelectedModel():
  """The model chosen in Settings -> RAG, which is the one the engine serves."""
  return (fFindModel(fRuntimeSettings().get("model"))
          or fFindModel(fReadModelCatalogue()["default"]))


def fRuntimeDirectory():
  return Path(paths.fGetBaseDir()) / "rag-runtime"


def fDirectory(pAgentId):
  return Path(paths.fGetAgentHome(pAgentId)) / "rag"


def fValidateSettings(pSettings):
  if not isinstance(pSettings, dict) or set(pSettings) - set(dDefaults):
    raise ValueError("Invalid RAG settings.")
  # Similarities are on each model's own scale, so the default floor is the
  # one measured for the model in use.
  dSettings = {**dDefaults, "ocr_languages":fRuntimeSettings()["ocr_languages"],
               "min_similarity":fSelectedModel()["min_similarity"], **pSettings}
  for vKey in ("enabled", "ocr"):
    if type(dSettings[vKey]) is not bool:
      raise ValueError("%s must be a boolean." % vKey)
  if dSettings["mode"] not in ("mixed", "documental", "verified"):
    raise ValueError("Choose mixed, documental or verified RAG mode.")
  for vKey, vMin, vMax in (("max_file_mb", 1, 1024), ("max_storage_mb", 1, 1048576),
                          ("max_chunks", 100, 2000000), ("context_characters", 1000, 64000),
                          ("results", 1, 30), ("chunk_tokens", 64, 440)):
    if type(dSettings[vKey]) is not int or not vMin <= dSettings[vKey] <= vMax:
      raise ValueError("%s must be between %d and %d." % (vKey, vMin, vMax))
  if dSettings["max_file_mb"] > dSettings["max_storage_mb"]:
    raise ValueError("The file limit cannot exceed the library storage limit.")
  fValidateLanguages(dSettings["ocr_languages"])
  if (type(dSettings["min_similarity"]) not in (int,float) or
      not math.isfinite(dSettings["min_similarity"]) or not 0<=dSettings["min_similarity"]<=1):
    raise ValueError("Minimum similarity must be between 0 and 1.")
  return dSettings


def fValidateLanguages(pLanguages):
  import re
  if not isinstance(pLanguages, str) or not re.fullmatch(r"[a-z]{3}(?:\+[a-z]{3}){0,5}", pLanguages):
    raise ValueError("Use OCR language codes such as eng+spa.")
  return pLanguages


def fRead(pAgentId):
  from backend.core import agents
  return fValidateSettings(agents.fReadAgentInfo(pAgentId).get("rag") or {})


def fRuntimeSettings():
  try:
    dSaved = json.loads((fRuntimeDirectory() / "settings.json").read_text())
  except FileNotFoundError:
    dSaved = {}
  dSettings = {**dRuntimeDefaults, **dSaved}
  # A model this version no longer ships falls back to the default rather than
  # leaving the engine without weights to load.
  if fFindModel(dSettings["model"]) is None:
    dSettings["model"] = fReadModelCatalogue()["default"]
  return dSettings


def fSaveRuntimeSettings(pSettings):
  if not isinstance(pSettings, dict) or set(pSettings) - set(dRuntimeDefaults):
    raise ValueError("Invalid local embedding settings.")
  dSettings = {**fRuntimeSettings(), **pSettings}
  for vKey, vMax in (("threads", 32), ("workers", 4)):
    if type(dSettings[vKey]) is not int or not 1 <= dSettings[vKey] <= vMax:
      raise ValueError("%s must be between 1 and %d." % (vKey, vMax))
  fValidateLanguages(dSettings["ocr_languages"])
  if fFindModel(dSettings["model"]) is None:
    raise ValueError("Choose one of the listed embedding models.")
  vPath = fRuntimeDirectory() / "settings.json"
  vTemporary = vPath.with_suffix(".tmp")
  vTemporary.write_text(json.dumps(dSettings, indent=2) + "\n")
  os.chmod(vTemporary, 0o644)
  os.replace(vTemporary, vPath)
  return dSettings
