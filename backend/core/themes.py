"""Interface themes, one CSS file per theme.

    frontend/themes/<name>.css

A theme is a plain stylesheet that redefines the `--colour-*` variables. It is
loaded after app.css, so its `:root` block wins over the palette there -
including over app.css's `prefers-color-scheme: dark` block, which is what lets
a theme stay light on a machine set to dark.

They are discovered by listing the directory, the same way tools are, so
dropping a file in adds a theme with no code change. What the interface needs
to name it - a title, whether it is light or dark - lives in a comment at the
top of the file, in `key: value` lines, so a theme is still one file and that
file is still servable CSS.

Every theme is a file. There is no "follow the system" entry in the list: the
browser still picks one by the system's preference the first time somebody
arrives, but that is `theme.js` choosing a real theme, not a theme of its own.

Nothing here reads a theme chosen by the user: which one is in use is a
per-browser preference in localStorage, next to the language, because it
describes how one person works at one machine.
"""

import os
import re

from backend.core import paths

cThemesDirectoryName = "themes"

# Metadata lives in the first comment of the file. Anything after it is the
# stylesheet and is never parsed here.
cHeaderPattern = re.compile(r"/\*(.*?)\*/", re.S)
cMetadataLinePattern = re.compile(r"^\s*([a-z_]+)\s*:\s*(.+?)\s*$")

lKnownMetadataKeys = ["name", "scheme", "description"]

# What a theme file may be called. A name that leaves the directory, or that is
# not a plain stylesheet name, is not a theme.
cThemeNamePattern = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")


def fGetThemesDirectory():
  """Return the directory holding the theme stylesheets."""
  vWebAppDir = paths.fGetWebAppDir()
  vDirectory = os.path.join(vWebAppDir, "frontend", cThemesDirectoryName)
  if os.path.isdir(vDirectory):
    return vDirectory

  # On the development machine the code is not deployed under /opt/boa, so the
  # themes are looked up relative to this file instead. Same fallback the Flask
  # application uses for its templates.
  vProjectDir = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
  )))
  return os.path.join(vProjectDir, "frontend", cThemesDirectoryName)


def fIsValidThemeName(pName):
  """Return whether a name can be a theme, and cannot be a path."""
  return bool(cThemeNamePattern.match(str(pName or "")))


def fGetThemePath(pName):
  """Return the stylesheet path of one theme.

  The name arrives in a URL, so it is matched against a pattern rather than
  cleaned: anything with a separator, a dot or an unexpected character is not a
  theme name and is refused outright.
  """
  if not fIsValidThemeName(pName):
    raise ValueError("Invalid theme name: %r" % (pName,))
  return os.path.join(fGetThemesDirectory(), "%s.css" % (pName,))


def fReadMetadata(pPath, pName):
  """Return what the header comment of a theme says about it."""
  dMetadata = {"name": pName, "scheme": "", "description": ""}
  try:
    with open(pPath, "r", encoding="utf-8") as vFile:
      # The header is at the top; reading the whole file to find it would mean
      # reading every stylesheet to draw one dropdown.
      vHead = vFile.read(2048)
  except OSError:
    return dMetadata

  dMatch = cHeaderPattern.search(vHead)
  if not dMatch:
    return dMetadata

  for vLine in dMatch.group(1).splitlines():
    dLine = cMetadataLinePattern.match(vLine)
    if not dLine:
      continue
    vKey = dLine.group(1).lower()
    if vKey in lKnownMetadataKeys:
      dMetadata[vKey] = dLine.group(2)
  return dMetadata


def fListThemes():
  """Return every installed theme, in the order of the names shown.

  Sorted by the name, not by the file: the dropdown shows names, and a list
  that is alphabetical in a column the user cannot see is not a sorted list to
  them. The two orders also disagree - `-` sorts before `.`, so by file name
  `day-high-contrast.css` would come before `day.css` and the pairs would come
  out interleaved.

  A file that cannot be read still appears, named after itself: a theme missing
  from the list would look like a theme that was never installed, and the user
  would go looking in the wrong place.
  """
  lThemes = []

  vDirectory = fGetThemesDirectory()
  try:
    lFiles = sorted(os.listdir(vDirectory))
  except OSError:
    return lThemes

  for vFileName in lFiles:
    if not vFileName.endswith(".css"):
      continue
    vId = vFileName[:-len(".css")]
    if not fIsValidThemeName(vId):
      continue
    dMetadata = fReadMetadata(os.path.join(vDirectory, vFileName), vId)
    lThemes.append({
      "id": vId,
      "name": dMetadata["name"] or vId,
      "scheme": dMetadata["scheme"] or "",
      "description": dMetadata["description"],
    })

  lThemes.sort(key=lambda dTheme: dTheme["name"].lower())
  return lThemes


def fThemeExists(pName):
  """Return whether a theme is installed."""
  try:
    return os.path.isfile(fGetThemePath(pName))
  except ValueError:
    return False
