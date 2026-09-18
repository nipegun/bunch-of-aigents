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

async function fLoadTranslations(pLanguage) {
  /* Named explicitly when previewing a language that is not the stored one. */
  const vLanguage = pLanguage || fGetLanguage();
  vLoadSequence += 1;
  const vThisLoad = vLoadSequence;
  document.documentElement.setAttribute("lang", vLanguage);
  if (vLanguage === cDefaultLanguage) {
    dTranslations = {};
    return dTranslations;
  }
  try {
    const vResponse = await fetch("/static/i18n/" + vLanguage + ".json", {
      credentials: "same-origin",
    });
    if (vThisLoad !== vLoadSequence) { return dTranslations; }
    if (vResponse.ok) { dTranslations = await vResponse.json(); }
  } catch (vError) {
    if (vThisLoad === vLoadSequence) { dTranslations = {}; }
  }
  return dTranslations;
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
