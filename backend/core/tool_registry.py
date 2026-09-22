"""Discovery and dispatch of the tools available to agents.

Every tool is one .py file in /opt/boa/tools/, so that root can drop a new file
in that directory and have it appear in the web interface without touching the
application. A tool module declares:

    cToolName        : str, the dotted name agents call it by, e.g. "bash.run"
    cToolDescription : str, what the model is told the tool does
    dToolSchema      : dict, a JSON Schema for its arguments
    fRunTool(pArguments, pContext) -> str

`pContext` carries the calling agent's id and configuration, so a tool can act
on behalf of that agent without trusting anything the model said about who it
is.

Two rules hold this together:

  - Only root can write that directory. The web application imports these files
    as code, so write access to them is equivalent to running as the web user.
  - A tool is only offered to an agent whose info.json lists it. That check
    happens here, on the server, never in the prompt: an agent that asks for a
    tool it was not granted gets a refusal, not an execution.
"""

import importlib.util
import os
import sys

from backend.core import paths

# Modules are imported under this prefix so a tool file named `json.py` cannot
# shadow the standard library for the rest of the process.
cToolModulePrefix = "boa_tool_"

# Attributes a tool module must define to be loadable.
lRequiredAttributes = ["cToolName", "cToolDescription", "dToolSchema", "fRunTool"]


class ToolError(RuntimeError):
  """Raised when a tool cannot be loaded, is not allowed, or fails."""


class ToolFailure(RuntimeError):
  """Raised by a tool to report a failure in its own words.

  A tool that returns its error message as an ordinary string would be recorded
  as a success: the model reads the message, but the run log says the call
  worked, and whoever is debugging sees nothing wrong. Raising this instead
  keeps the tool's wording and still marks the result as an error.
  """


class ToolContext:
  """What a tool is told about the agent calling it."""

  def __init__(self, pAgentId, pAgentInfo, pApiToken=""):
    self.vAgentId = pAgentId
    self.dAgentInfo = pAgentInfo or {}
    self.vApiToken = pApiToken
    self.lAttachments = []

  @property
  def vAgentName(self):
    """Return the display name of the calling agent."""
    return self.dAgentInfo.get("name", self.vAgentId)


def fDiscoverToolFiles():
  """Return the path of every tool module, sorted by file name."""
  vToolsDir = paths.fGetToolsDir()
  lPaths = []
  try:
    lEntries = sorted(os.listdir(vToolsDir))
  except OSError:
    return lPaths
  for vEntry in lEntries:
    if vEntry.endswith(".py") and not vEntry.startswith("_"):
      lPaths.append(os.path.join(vToolsDir, vEntry))
  return lPaths


def fLoadToolModule(pModulePath):
  """Import one tool module from its path and validate its interface."""
  vModuleName = cToolModulePrefix + os.path.splitext(os.path.basename(pModulePath))[0]
  try:
    vSpec = importlib.util.spec_from_file_location(vModuleName, pModulePath)
    if vSpec is None or vSpec.loader is None:
      raise ToolError("Cannot load %s" % (pModulePath,))
    vModule = importlib.util.module_from_spec(vSpec)
    sys.modules[vModuleName] = vModule
    vSpec.loader.exec_module(vModule)
  except Exception as vError:
    raise ToolError("Tool %s failed to import: %s" % (pModulePath, vError))

  for vAttribute in lRequiredAttributes:
    if not hasattr(vModule, vAttribute):
      raise ToolError(
        "Tool %s is missing %s" % (os.path.basename(pModulePath), vAttribute)
      )
  return vModule


def fLoadAllTools():
  """Return every loadable tool, keyed by tool name.

  A broken tool file is skipped rather than fatal: one bad file in the tools
  directory must not stop every agent in the installation from running.
  """
  dTools = {}
  lErrors = []
  for vPath in fDiscoverToolFiles():
    try:
      vModule = fLoadToolModule(vPath)
    except ToolError as vError:
      lErrors.append(str(vError))
      continue
    dTools[vModule.cToolName] = vModule
  return dTools, lErrors


def fBuildToolSchemas(pTools, pAllowedToolNames):
  """Return the neutral tool schemas for the tools one agent may use."""
  lSchemas = []
  for vToolName in pAllowedToolNames:
    vModule = pTools.get(vToolName)
    if vModule is None:
      continue
    lSchemas.append({
      "name": vToolName,
      "description": vModule.cToolDescription,
      "input_schema": vModule.dToolSchema,
    })
  return lSchemas


def fRunTool(pTools, pAllowedToolNames, pToolName, pArguments, pContext):
  """Run one tool on behalf of an agent, enforcing its permissions.

  Returns (result_text, is_error). A tool that raises is reported back to the
  model as a failed tool result rather than killing the run: the model can
  often recover, and an agent that dies on its first bad argument is useless.
  """
  if pToolName not in pAllowedToolNames:
    return (
      "Tool %r is not available to you. Ask the user to grant it in the web "
      "interface." % (pToolName,),
      True,
    )

  vModule = pTools.get(pToolName)
  if vModule is None:
    return ("Tool %r is not installed on this server." % (pToolName,), True)

  try:
    vResult = vModule.fRunTool(pArguments or {}, pContext)
  except ToolFailure as vError:
    # The tool said what went wrong in language aimed at the model.
    return (str(vError), True)
  except Exception as vError:
    return ("Tool %r failed: %s" % (pToolName, vError), True)

  if vResult is None:
    return ("", False)
  return (str(vResult), False)
