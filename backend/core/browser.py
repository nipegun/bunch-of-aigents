"""One browser, belonging to one agent, for the length of one run.

`web.fetch` reads a public page and stops there: no session, no form, no
button. Plenty of what an agent is asked to do needs the other thing - log in,
click, read what came back - and that is what this is.

    /opt/boa/playwright/            root:root 0755   the browser itself
    /opt/boa/agents/007/browser/    agent-007 0700   this agent's profile

The split is the whole design. The binary is shared because it is a binary and
there is nothing to isolate about it; one copy per agent would be 600 MB each
and an update to do N times. The profile is not shared, because it holds the
cookies: agent 007 logging into something must not leave agent 008 logged in.
That separation is the kernel's, the same 0700 home everything else of an
agent's lives in - which is the thing hosted agent products cannot offer, since
their agents share one machine and one set of sessions.

The browser stays open across tool calls within a run. `browser.click` has to
act on what `browser.open` left on the screen, and the run is one process from
the first tool call to the last, so a module-level handle is all the state that
needs. It is closed on the way out by `atexit`, and the profile on disk is what
carries a login into tomorrow's run.

Headless, always. What is wanted here is the session and the DOM, not a picture
of a window, and a virtual display would be another moving part to install, run
and debug for nothing.

Playwright is imported inside the functions, never at the top. The tools that
use this are listed in the interface whether or not the browser was installed,
and an ImportError at module scope would make them vanish from that list with
no explanation anywhere. Imported late, a missing browser is a sentence telling
the user what to run.
"""

import atexit
import os

from backend.core import paths

# Where a browser profile lives inside an agent's home.
cBrowserDirName = "browser"
cProfileDirName = "profile"
cDownloadsDirName = "downloads"

# How long any one navigation or click may take. Generous: a page behind a
# login can be slow, and the run has its own ceilings around all of this.
cDefaultTimeoutMilliseconds = 30000

# What one tool call may return. The same ceiling as bash.run and web.fetch,
# for the same reason: a tool result is part of the conversation from then on.
cMaxTextCharacters = 20000

# What the viewport claims to be. A desktop size, because a site that decides
# it is talking to a phone serves a different page, and the agent was asked
# about the ordinary one.
cViewportWidth = 1280
cViewportHeight = 900

# What is said when Playwright is not installed. Long on purpose: it is the
# answer to "why did this tool not work", and the model repeats it to the user.
cNotInstalledMessage = (
  "This server has no browser installed, so this tool cannot do anything. "
  "Tell the user to run the installer again with --browser yes, as root: "
  "./install-update-reinstall-debian.sh --update --browser yes"
)


class BrowserError(RuntimeError):
  """Raised when the browser cannot be started or driven."""


# The live browser, kept between tool calls of one run. Module level because
# the run is one process and there is nothing else to hang it on.
vPlaywright = None
vContext = None


def fGetBrowserDir(pAgentId):
  """Return the browser directory inside one agent's home."""
  return os.path.join(paths.fGetAgentHome(pAgentId), cBrowserDirName)


def fGetProfileDir(pAgentId):
  """Return where this agent's cookies and sessions live."""
  return os.path.join(fGetBrowserDir(pAgentId), cProfileDirName)


def fGetDownloadsDir(pAgentId):
  """Return where this agent's downloads and screenshots land."""
  return os.path.join(fGetBrowserDir(pAgentId), cDownloadsDirName)


def fReadConfiguredExecutable():
  """Return the browser binary the installer recorded, or "".

  On Debian this is empty and Playwright launches the build it downloaded into
  `/opt/boa/playwright/`. On Alpine that build does not run at all - it is
  linked against glibc and the system is musl - so the installer puts the
  system chromium here instead, and this is what tells the difference.

  Read from the file rather than from the environment because a tool is also
  reached from a script an agent wrote, where the environment is whatever cron
  gave it. An unreadable or missing file means "whatever Playwright has",
  which is what every installation had before this line existed.
  """
  vPath = os.path.join(paths.fGetConfigDir(), "browser.conf")
  try:
    with open(vPath, "r", encoding="utf-8") as vFile:
      for vLine in vFile:
        vLine = vLine.strip()
        if vLine.startswith("executable="):
          return vLine.split("=", 1)[1].strip()
  except OSError:
    pass
  return ""


def fEnsureDirectories(pAgentId):
  """Create this agent's browser directories if they are not there yet.

  Made on first use rather than when the agent is created, so agents that
  already existed when this arrived need no migration. 0700 like everything
  else in the home: the profile is where the cookies are.
  """
  for vPath in (fGetBrowserDir(pAgentId), fGetProfileDir(pAgentId),
                fGetDownloadsDir(pAgentId)):
    os.makedirs(vPath, mode=0o700, exist_ok=True)
  return True


def fIsInstalled():
  """Return whether there is a browser on this server to drive."""
  try:
    import playwright  # noqa: F401
  except ImportError:
    return False
  return os.path.isdir(paths.fGetPlaywrightDir())


def fGetContext(pAgentId):
  """Return this agent's browser context, starting it if it is not running.

  A persistent context rather than a fresh browser: that is what writes the
  profile to disk, and the profile is what makes a login survive to the next
  run. The alternative - logging in on every run - is both slower and far more
  likely to trip whatever the site does about unfamiliar sessions.
  """
  global vPlaywright, vContext
  if vContext is not None:
    return vContext

  try:
    from playwright.sync_api import sync_playwright
  except ImportError:
    raise BrowserError(cNotInstalledMessage)

  fEnsureDirectories(pAgentId)
  # Playwright looks here for the browser it downloaded. Set for this process
  # as well as by the executor, because a tool can also be reached from a
  # script an agent wrote, where the environment is whatever cron gave it.
  os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", paths.fGetPlaywrightDir())

  # An empty value is left out rather than passed: Playwright takes the
  # absence of the argument as "use the browser I downloaded", and an empty
  # string as a path that is not there.
  dExtra = {}
  vExecutable = fReadConfiguredExecutable()
  if vExecutable:
    dExtra["executable_path"] = vExecutable

  try:
    vPlaywright = sync_playwright().start()
    vContext = vPlaywright.chromium.launch_persistent_context(
      user_data_dir=fGetProfileDir(pAgentId),
      headless=True,
      accept_downloads=True,
      downloads_path=fGetDownloadsDir(pAgentId),
      viewport={"width": cViewportWidth, "height": cViewportHeight},
      **dExtra,
      args=[
        # The sandbox needs kernel features a container often does not give,
        # and the isolation it would add is already the agent's own Linux user.
        "--no-sandbox",
        # /dev/shm is small in a container, and Chromium crashing for that
        # reason looks exactly like Chromium crashing for any other.
        "--disable-dev-shm-usage",
      ],
    )
  except Exception as vError:
    fClose()
    raise BrowserError(
      "The browser would not start: %s. If it was never installed, tell the "
      "user to run the installer with --browser yes." % (vError,))

  vContext.set_default_timeout(cDefaultTimeoutMilliseconds)
  return vContext


def fGetPage(pAgentId):
  """Return the page being worked on, opening one if there is none."""
  vBrowserContext = fGetContext(pAgentId)
  lPages = vBrowserContext.pages
  if lPages:
    return lPages[-1]
  return vBrowserContext.new_page()


def fClose():
  """Close the browser, if one is open. Safe to call twice."""
  global vPlaywright, vContext
  if vContext is not None:
    try:
      vContext.close()
    except Exception:
      pass
    vContext = None
  if vPlaywright is not None:
    try:
      vPlaywright.stop()
    except Exception:
      pass
    vPlaywright = None
  return True


# The run ends and the browser goes with it. Without this, a chromium is left
# behind by every run that used one, and an agent on an hourly schedule fills
# the machine with them by morning.
atexit.register(fClose)


def fTruncate(pText):
  """Cut a page's text to what one tool result may carry."""
  vText = str(pText or "")
  if len(vText) <= cMaxTextCharacters:
    return vText
  return "%s\n\n[... %d more characters on the page]" % (
    vText[:cMaxTextCharacters], len(vText) - cMaxTextCharacters)


def fDescribePage(pPage, pText=""):
  """Return the standard heading every browser tool answers with.

  Title and address on every answer, because a click can navigate and an
  agent that does not notice is an agent reading the wrong page.
  """
  lLines = ["Page: %s" % (pPage.title() or "(no title)",),
            "URL: %s" % (pPage.url,)]
  if pText:
    lLines.append("")
    lLines.append(fTruncate(pText))
  return "\n".join(lLines)
