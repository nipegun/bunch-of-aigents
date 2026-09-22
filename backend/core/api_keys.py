"""Provider API keys shared by every agent.

    /opt/boa/config/apikeys/<provider>.key

Written by the web application, readable by the agent API, and readable by no
agent at all: the directory is `boa`-owned and 0700, the files 0600. Not 0750
and 0640, which would already keep agents out - they are not in the `boa`
group - but which rests on the group list of every agent user staying empty
for the life of the installation. A mode that grants nothing to the group
cannot be undone by a later `usermod -aG boa`.

An agent still needs the key in its own process to call the provider, so the
agent API hands it over on request - but only the key for the provider that
agent is actually configured with. An agent running on Ollama cannot ask for
the Anthropic key, and neither can one whose provider was changed a moment ago
without saving.

Being honest about what this does and does not protect:

  - It does NOT stop an agent that legitimately uses a paid provider from
    reading its own key. It has to have it to make the call, and an agent with
    bash.run could print it. That is inherent: the key is the thing it needs.
  - It DOES stop an agent from collecting the keys of providers it does not
    use, and it keeps every key out of the agent home directories, where a
    backup or a stray `cat` would expose all of them at once.

An agent can still have its own key, in keys/<provider>.key inside its home.
That one wins, which is how one agent gets billed to a different account.
"""

import os

from backend.core import paths

# The directory name says what is in it. It used to be `keys`, which read as
# "the keys of this installation" and sat one typo away from the per-agent
# `keys/` inside each agent home. The installer moves the old one across on
# update.
cKeysDirectoryName = "apikeys"

# Nobody but the owner, on the directory and on the files in it.
cKeysDirectoryMode = 0o700
cKeyFileMode = 0o600


def fGetKeysDirectory():
  """Return the directory holding the shared provider keys."""
  return os.path.join(paths.fGetConfigDir(), cKeysDirectoryName)


def fGetKeyPath(pProviderName):
  """Return the key path of one provider."""
  vName = str(pProviderName or "").strip().lower()
  # The name comes from the provider registry, but a separator here would be a
  # path traversal, so it is refused rather than trusted.
  if not vName or "/" in vName or "\\" in vName or vName.startswith("."):
    raise ValueError("Invalid provider name: %r" % (pProviderName,))
  return os.path.join(fGetKeysDirectory(), "%s.key" % (vName,))


def fRead(pProviderName):
  """Return the shared key of one provider, or an empty string."""
  try:
    with open(fGetKeyPath(pProviderName), "r", encoding="utf-8") as vFile:
      return vFile.read().strip()
  except (OSError, ValueError):
    return ""


def fWrite(pProviderName, pKey):
  """Store the shared key of one provider.

  An empty key deletes the file rather than storing an empty one: "no key" and
  "a key that is the empty string" behave differently everywhere else.
  """
  vKeyPath = fGetKeyPath(pProviderName)
  vKey = str(pKey or "").strip()

  if not vKey:
    try:
      os.unlink(vKeyPath)
    except FileNotFoundError:
      pass
    except OSError as vError:
      raise RuntimeError("Cannot remove the key: %s" % (vError,))
    return False

  vTempPath = vKeyPath + ".tmp"
  try:
    vDirectory = os.path.dirname(vKeyPath)
    os.makedirs(vDirectory, mode=cKeysDirectoryMode, exist_ok=True)
    # `makedirs` applies the umask to its mode and does nothing at all when
    # the directory is already there, so the mode is set again explicitly:
    # every write is also the moment this directory is made unreadable to
    # anyone but its owner, whatever it was before.
    os.chmod(vDirectory, cKeysDirectoryMode)
    vDescriptor = os.open(
      vTempPath, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, cKeyFileMode)
    with os.fdopen(vDescriptor, "w", encoding="utf-8") as vFile:
      vFile.write(vKey + "\n")
    # `os.open` also applies the umask, and `os.replace` carries the mode of
    # the temporary file over to the final one.
    os.chmod(vTempPath, cKeyFileMode)
    os.replace(vTempPath, vKeyPath)
  except OSError as vError:
    try:
      os.unlink(vTempPath)
    except OSError:
      pass
    raise RuntimeError("Cannot write the key: %s" % (vError,))
  return True


def fDescribe(pProviderName):
  """Return whether a key is stored, and a hint of which one.

  Never the key itself. The hint is the last four characters, which is enough
  to tell two keys apart when you are wondering which account is being billed,
  and useless to anyone who gets hold of it.
  """
  vKey = fRead(pProviderName)
  if not vKey:
    return {"provider": pProviderName, "configured": False, "hint": ""}
  return {
    "provider": pProviderName,
    "configured": True,
    "hint": "…" + vKey[-4:] if len(vKey) > 4 else "…",
    "length": len(vKey),
  }


def fDescribeAll(pProviderNames):
  """Return the state of every provider's key, with no key in it."""
  return [fDescribe(vName) for vName in pProviderNames]
