/* The login form.
 *
 * Enter moves from the email to the password, and Enter on the password
 * submits. That is what a browser does by default with a two-field form - but
 * only the submitting half - so the first half is worth adding: tabbing with
 * Enter is what fingers do on a login screen.
 */

document.addEventListener("DOMContentLoaded", function () {
  /* Reaching the login page means there is no session, so the sidebar's cached
   * agent list has no business surviving into the next one. This is the one
   * page every way out of the application passes through - logging out, a
   * session expiring, an API call answering 401 - so clearing it here covers
   * all of them. */
  fClearSidebarCache();

  /* The language picker, so somebody who does not read the installed default
   * can log in without being told which field is which. */
  const vLanguageInput = document.getElementById("vLoginLanguageInput");
  if (vLanguageInput) {
    vLanguageInput.value = fGetLanguage();
    vLanguageInput.addEventListener("change", function (pEvent) {
      fSetLanguage(pEvent.target.value);
    });
  }

  const vEmailInput = document.getElementById("vEmailInput");
  const vPasswordInput = document.getElementById("vPasswordInput");
  const vForm = document.getElementById("vLoginForm");
  if (!vEmailInput || !vPasswordInput || !vForm) { return; }

  vEmailInput.addEventListener("keydown", function (pEvent) {
    if (pEvent.key !== "Enter") { return; }
    /* Without this the form submits with an empty password and comes back
     * with "that does not match", which is a confusing way to learn that you
     * skipped a field. */
    pEvent.preventDefault();
    vPasswordInput.focus();
  });

  vPasswordInput.addEventListener("keydown", function (pEvent) {
    if (pEvent.key !== "Enter") { return; }
    pEvent.preventDefault();
    vForm.requestSubmit();
  });
});
