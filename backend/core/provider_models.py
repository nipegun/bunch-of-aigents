"""Model catalogues, one JSON file per provider.

    /opt/boa/config/providers/<provider>.json

They live in the configuration directory rather than in the code because
providers release models far faster than this project releases versions: a list
compiled into the application would be wrong within weeks, and correcting it
would mean an update. Here, it is a file the user can edit on the running
server.

Nothing validates the contents against the provider. The list is a convenience
for the person filling in the form - the model field still accepts anything
typed into it, because a model released this morning is not going to be in any
file yet.
"""

import json
import os

from backend.core import paths

cProvidersDirectoryName = "providers"


def fGetProvidersDirectory():
  """Return the directory holding the model catalogues."""
  return os.path.join(paths.fGetConfigDir(), cProvidersDirectoryName)


def fGetCataloguePath(pProviderName):
  """Return the catalogue path of one provider."""
  vName = str(pProviderName or "").strip().lower()
  # The name comes from the provider registry, never from a request, but a
  # separator here would still be a path traversal, so it is refused.
  if not vName or "/" in vName or "\\" in vName or vName.startswith("."):
    raise ValueError("Invalid provider name: %r" % (pProviderName,))
  return os.path.join(fGetProvidersDirectory(), "%s.json" % (vName,))


def fReadCatalogue(pProviderName):
  """Return one provider's catalogue, or an empty one.

  A missing or broken file is not an error: the field it feeds is a free text
  box with suggestions, so the worst case is having to type the model name.
  """
  try:
    with open(fGetCataloguePath(pProviderName), "r", encoding="utf-8") as vFile:
      dCatalogue = json.load(vFile)
  except (OSError, ValueError):
    return {"provider": pProviderName, "models": []}

  if not isinstance(dCatalogue, dict):
    return {"provider": pProviderName, "models": []}

  lModels = []
  for dModel in dCatalogue.get("models") or []:
    if isinstance(dModel, str):
      lModels.append({"id": dModel, "label": dModel})
    elif isinstance(dModel, dict) and dModel.get("id"):
      lModels.append({
        "id": str(dModel["id"]),
        "label": str(dModel.get("label") or dModel["id"]),
        "note": str(dModel.get("note") or ""),
        "context": str(dModel.get("context") or ""),
      })

  return {
    "provider": str(dCatalogue.get("provider") or pProviderName),
    "documentation": str(dCatalogue.get("documentation") or ""),
    "note": str(dCatalogue.get("note") or ""),
    "models": lModels,
  }


def fReadAllCatalogues(pProviderNames):
  """Return the catalogue of every provider, keyed by provider name."""
  dCatalogues = {}
  for vName in pProviderNames:
    dCatalogues[vName] = fReadCatalogue(vName)
  return dCatalogues
