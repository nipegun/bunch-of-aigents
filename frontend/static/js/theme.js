/* The chosen theme, applied before the page is painted.
 *
 * This file is loaded from the <head> without `defer`, which is deliberate: it
 * has to run before the browser paints anything, or every page would flash in
 * the default palette and then repaint in the chosen one. The page is served
 * under `script-src 'self'`, so an inline script - the usual way to do this -
 * is not available, and a blocking file the size of this one costs less than
 * the flash it prevents.
 *
 * Which theme is chosen lives in localStorage next to the language, because it
 * describes how one person works at one machine: it would be odd for a phone
 * and a desktop to have to agree on it.
 *
 * There is no list of valid names here. The server refuses a name that is not
 * a theme, and a stylesheet that 404s leaves the default palette in place -
 * which is the right outcome for a theme that was uninstalled.
 */

const cThemeStorageKey = "boa.theme";

/* Every theme is a file, so these are the two the first visit can land on.
 * There is no "follow the system" theme: the system decides which of these two
 * a new browser starts with, and after that the choice is the user's. */
const cLightThemeName = "day";
const cDarkThemeName = "night";

const cThemeLinkId = "vThemeStylesheet";

function fGetSystemTheme() {
  try {
    if (window.matchMedia &&
        window.matchMedia("(prefers-color-scheme: dark)").matches) {
      return cDarkThemeName;
    }
  } catch (vError) {
    /* An old browser without matchMedia gets the light one. */
  }
  return cLightThemeName;
}

/* Names that were once in the list and may still be sitting in a browser that
 * chose them. "light" and "dark" were renamed and still mean what they said;
 * "system" means what no choice at all now means, so it maps to nothing and
 * falls through to the system's own preference.
 *
 * Without this, a browser that had chosen one of them would ask for a
 * stylesheet that is no longer there and show its own setting as "not
 * installed" - a choice the user made, reported back as a mistake. */
const dRenamedThemeNames = {
  light: cLightThemeName,
  dark: cDarkThemeName,
  /* The single high-contrast theme was a dark one before it gained a light
   * counterpart, so a browser holding the old name meant the dark one. The
   * pair was then renamed the other way round, so that the list sorts into
   * Day, Day High Contrast, Night, Night High Contrast. */
  "high-contrast": "night-high-contrast",
  "high-contrast-day": "day-high-contrast",
  "high-contrast-night": "night-high-contrast",
  system: "",
};

function fGetTheme() {
  /* What is on screen: the stored choice, or - until there is one - whichever
   * matches the operating system. Not stored on the way past, so a machine
   * that switches to dark at sunset still follows until somebody picks. */
  try {
    const vStored = window.localStorage.getItem(cThemeStorageKey);
    if (vStored) {
      const vRenamed = Object.prototype.hasOwnProperty.call(
        dRenamedThemeNames, vStored) ? dRenamedThemeNames[vStored] : vStored;
      if (vRenamed) { return vRenamed; }
    }
  } catch (vError) {
    /* Private windows and blocked site data throw here. Not a reason to fail. */
  }
  return fGetSystemTheme();
}

function fApplyTheme(pName) {
  const vName = pName || fGetSystemTheme();
  const vExisting = document.getElementById(cThemeLinkId);

  /* Reusing the one link rather than adding another means switching theme
   * repaints instead of stacking palettes whose order would decide the
   * colours. */
  const vLink = vExisting || document.createElement("link");
  vLink.id = cThemeLinkId;
  vLink.rel = "stylesheet";
  vLink.href = "/themes/" + encodeURIComponent(vName) + ".css";
  if (!vExisting) { document.head.appendChild(vLink); }
}

function fSetTheme(pName) {
  try {
    window.localStorage.setItem(cThemeStorageKey, pName || fGetSystemTheme());
  } catch (vError) {
    /* A preference that cannot be stored applies to this page only. */
  }
  fApplyTheme(pName);
}

fApplyTheme(fGetTheme());
