/* Translation.
 *
 * The interface ships in fourteen languages. Strings live in
 * /static/i18n/<tag>.json and are applied to anything carrying data-i18n, so a
 * language change never needs a page rebuild - only a different JSON file.
 *
 * The markup already contains the en-US text, so a missing or unreachable
 * translation file leaves a readable page instead of a page of blanks.
 */

const cDefaultLanguage = "en-US";
/* Every file in /static/i18n/, in the order they are offered: by tag, which
 * is what keeps the two regional variants of a language next to each other. */
const lSupportedLanguages = [
  "de-DE", "en-GB", "en-US", "es-AR", "es-ES", "fr-FR", "hi-IN", "it-IT",
  "ja-JP", "ko-KR", "pt-BR", "pt-PT", "ru-RU", "zh-CN",
];
const cLanguageStorageKey = "boa.language";
const cSendOnEnterStorageKey = "boa.sendOnEnter";

let dTranslations = {};

function fGetLanguage() {
  try {
    const vStored = window.localStorage.getItem(cLanguageStorageKey);
    if (vStored && lSupportedLanguages.indexOf(vStored) !== -1) { return vStored; }
  } catch (vError) {
    /* Private windows and blocked site data throw here. Not a reason to fail. */
  }

  /* en-US until somebody chooses otherwise, on the login page and everywhere
   * else. This used to negotiate with navigator.languages, which meant a new
   * installation spoke whatever the first browser to reach it spoke: the
   * language of the machine somebody happened to open it from, not a decision
   * anybody made. The choice is one click away in the corner of the login
   * card and in Settings, and it is remembered per browser once made. */
  return cDefaultLanguage;
}

function fSetLanguage(pLanguage) {
  if (lSupportedLanguages.indexOf(pLanguage) === -1) { return Promise.resolve(); }
  try {
    window.localStorage.setItem(cLanguageStorageKey, pLanguage);
  } catch (vError) { /* see above */ }
  /* The language is named here rather than read back out of storage: in a
   * private window the line above throws, the read returns the previous
   * choice, and the page reloads the language it was already showing - which
   * looks exactly like "changing the language did nothing". */
  return fLoadTranslations(pLanguage).then(fApplyTranslations);
}

/* Show a language without keeping it, so the settings screen can preview what
 * Save would do and Discard can put it back. The pair mirrors fApplyTheme and
 * fSetTheme, which split the same way and for the same reason. */
function fApplyLanguage(pLanguage) {
  if (lSupportedLanguages.indexOf(pLanguage) === -1) {
    return Promise.resolve();
  }
  return fLoadTranslations(pLanguage).then(fApplyTranslations);
}

function fTranslate(pKey, pFallback) {
  if (Object.prototype.hasOwnProperty.call(dTranslations, pKey)) {
    return dTranslations[pKey];
  }
  return pFallback !== undefined ? pFallback : pKey;
}

/* Which load is the current one. Two changes in quick succession - somebody
 * running down the language list - are two fetches, and the slower one must
 * not land on top of the faster one and leave the page in a language nobody
 * asked for. */
let vLoadSequence = 0;

/* Load one language's strings and make them the current ones.
 *
 * Three things here were wrong, and each of them showed the user a language
 * they had not chosen:
 *
 *   The `lang` attribute was set at the TOP, before the file had been
 *   fetched. A 404 or a parse error then left the previous language's strings
 *   on screen under the new language's name: `lang=fr-FR` with Spanish text.
 *   Nothing is published now until the dictionary is in hand.
 *
 *   The sequence was checked BEFORE `await response.json()`. Two changes in
 *   quick succession - somebody running down the list - are two fetches, and
 *   a slow BODY for the earlier one landed after the later one had finished.
 *   It is checked after every await now, because the sequence can move across
 *   any of them.
 *
 *   A failure left the page in an unknown state and said nothing. It falls
 *   back to en-US, which is a language, and reports the failure through
 *   fOnLoadFailed so the interface can say so.
 */
async function fLoadTranslations(pLanguage) {
  /* Named explicitly when previewing a language that is not the stored one. */
  const vLanguage = pLanguage || fGetLanguage();
  vLoadSequence += 1;
  const vThisLoad = vLoadSequence;

  /* en-US is fetched like any other language.
   *
   * It used to be short-circuited to an empty dictionary, on the grounds that
   * the markup already carries the en-US text - which is true, and which made
   * en-US.json 493 keys of dead weight. Shipped, listed as a catalogue,
   * checked by the tests for parity with the other thirteen, and read by
   * nothing: correcting a typo in it changed nothing on screen, and the only
   * way to find that out was to try.
   *
   * The markup text stays, as the FALLBACK it is described as being in the
   * header of this file: a key the catalogue does not have, or a catalogue
   * that will not load, still leaves a readable page rather than a page of
   * blanks. What changed is which of the two is the source. */

  let dLoaded = null;
  try {
    const vResponse = await fetch("/static/i18n/" + vLanguage + ".json", {
      credentials: "same-origin",
    });
    if (vThisLoad !== vLoadSequence) { return dTranslations; }
    if (vResponse.ok) {
      dLoaded = await vResponse.json();
      if (vThisLoad !== vLoadSequence) { return dTranslations; }
    }
  } catch (vError) {
    dLoaded = null;
  }

  if (vThisLoad !== vLoadSequence) { return dTranslations; }

  if (dLoaded && typeof dLoaded === "object") {
    fPublish(vLanguage, dLoaded, vThisLoad);
    return dTranslations;
  }

  /* Nothing usable came back. The markup's own en-US text is what every
   * element shipped with, so an empty dictionary is a readable page - and the
   * language shown and the language named are the same one either way.
   *
   * That is also what happens when en-US.json itself is the file that failed:
   * there is nothing further to fall back to, and the fallback text is
   * exactly what the catalogue would have said. */
  fPublish(cDefaultLanguage, {}, vThisLoad);
  fOnLoadFailed(vLanguage);
  return dTranslations;
}

/* Publish a language and its dictionary together.
 *
 * One function, because the failure this exists to prevent is exactly the two
 * being set apart: the name said fr-FR while the strings were still Spanish.
 */
function fPublish(pLanguage, pTranslations, pSequence) {
  if (pSequence !== undefined && pSequence !== vLoadSequence) { return; }
  dTranslations = pTranslations || {};
  document.documentElement.setAttribute("lang", pLanguage);
}

/* Called when a language file could not be loaded. Replaced by the interface
 * so that a failure is something the user is told about rather than a page
 * that quietly reverted. */
let fOnLoadFailed = function (pLanguage) {
  if (window.console && window.console.warn) {
    window.console.warn(
      "Could not load the " + pLanguage + " strings; showing en-US.");
  }
};

function fSetLoadFailureHandler(pHandler) {
  if (typeof pHandler === "function") { fOnLoadFailed = pHandler; }
}

/* The en-US string each element shipped with, kept the first time that element
 * is translated.
 *
 * Without it there is nothing to go back to. `textContent` has already been
 * overwritten by the previous language, so a switch that has no string for a
 * key - going back to en-US, where there is no file at all, or to a language
 * whose file is missing that key - left the old words on screen. On the login
 * page that read as "changing the language does nothing", and changing it
 * twice appeared to help only because the second language did have the key.
 *
 * A WeakMap rather than a data- attribute: it holds nothing once the element
 * is gone, and it does not put a second copy of every string into the markup. */
const dOriginalStrings = new WeakMap();

function fRememberOriginal(pElement, pField, pValue) {
  let dOriginal = dOriginalStrings.get(pElement);
  if (dOriginal === undefined) {
    dOriginal = {};
    dOriginalStrings.set(pElement, dOriginal);
  }
  if (!Object.prototype.hasOwnProperty.call(dOriginal, pField)) {
    dOriginal[pField] = pValue;
  }
  return dOriginal[pField];
}

function fTranslateOrRestore(pElement, pKey, pField, pCurrent) {
  const vOriginal = fRememberOriginal(pElement, pField, pCurrent);
  if (Object.prototype.hasOwnProperty.call(dTranslations, pKey)) {
    return dTranslations[pKey];
  }
  return vOriginal;
}

function fApplyTranslations() {
  document.querySelectorAll("[data-i18n]").forEach(function (vElement) {
    const vKey = vElement.getAttribute("data-i18n");
    vElement.textContent = fTranslateOrRestore(
      vElement, vKey, "text", vElement.textContent);
  });
  document.querySelectorAll("[data-i18n-title]").forEach(function (vElement) {
    const vKey = vElement.getAttribute("data-i18n-title");
    vElement.setAttribute("title", fTranslateOrRestore(
      vElement, vKey, "title", vElement.getAttribute("title") || ""));
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach(function (vElement) {
    const vKey = vElement.getAttribute("data-i18n-placeholder");
    vElement.setAttribute("placeholder", fTranslateOrRestore(
      vElement, vKey, "placeholder", vElement.getAttribute("placeholder") || ""));
  });
}

/* Loading starts as soon as this script runs, not on DOMContentLoaded, and the
 * promise is exposed. Anything that builds DOM from JavaScript must await it:
 * otherwise the first render uses the fallback strings and a page in Spanish
 * shows one stray English word where a select was filled too early. */
const vTranslationsReady = fLoadTranslations();

document.addEventListener("DOMContentLoaded", function () {
  vTranslationsReady.then(fApplyTranslations);
});

async function fWaitForTranslations() {
  await vTranslationsReady;
}

/* Interface preferences.
 *
 * These live in the browser rather than on the server because they describe
 * how this person types on this machine, not what the installation does. A
 * phone and a desktop can reasonably disagree about whether Enter should send.
 *
 * Every read is guarded: a private window or blocked site data makes
 * localStorage throw rather than return nothing. */

function fGetSendOnEnter() {
  try {
    const vStored = window.localStorage.getItem(cSendOnEnterStorageKey);
    if (vStored === "0") { return false; }
  } catch (vError) {
    /* Fall through to the default. */
  }
  /* Default: Enter sends. */
  return true;
}

/* Any other preference stored in this browser. Guarded the same way: a private
 * window makes localStorage throw rather than return nothing. */
function fReadInterfacePreference(pKey, pDefault) {
  try {
    const vStored = window.localStorage.getItem(pKey);
    return vStored === null ? pDefault : vStored;
  } catch (vError) {
    return pDefault;
  }
}

function fSetSendOnEnter(pSendOnEnter) {
  try {
    window.localStorage.setItem(cSendOnEnterStorageKey, pSendOnEnter ? "1" : "0");
  } catch (vError) {
    /* A preference that cannot be stored is a preference for this page only. */
  }
}
