/* Dialogs that look like the rest of the application.
 *
 * The browser's own confirm() and prompt() are unstyleable, freeze the page
 * while they are open, and look like a different program - which is exactly
 * the wrong impression for "this will delete an agent and its Linux user".
 *
 * Built on <dialog>, which gives the parts that are easy to get wrong for
 * free: Escape closes it, focus is trapped inside it, the rest of the page is
 * inert while it is open, and the backdrop is styleable.
 *
 * Both functions return a promise: fConfirm resolves to true or false,
 * fPrompt to the text or to null when cancelled.
 */

let vOpenDialogResolve = null;

function fBuildDialogElement() {
  let vDialog = document.getElementById("vAppDialog");
  if (vDialog) { return vDialog; }

  vDialog = document.createElement("dialog");
  vDialog.id = "vAppDialog";
  vDialog.className = "app-dialog";
  /* So a destructive dialog can hold the focus itself rather than parking it
   * on a button that Enter would then press. */
  vDialog.tabIndex = -1;

  const vForm = document.createElement("form");
  vForm.method = "dialog";
  vForm.className = "app-dialog-form";

  vForm.appendChild(fCreateElement("h2", "app-dialog-title", ""));
  vForm.appendChild(fCreateElement("p", "app-dialog-message", ""));

  const vField = fCreateElement("div", "field app-dialog-field");
  const vInput = document.createElement("input");
  vInput.type = "text";
  vInput.className = "app-dialog-input";
  vInput.autocomplete = "off";
  vField.appendChild(vInput);
  vForm.appendChild(vField);

  /* The choices of a "choose" dialog. Each is a button that answers the
   * promise on its own, so there is one click between the question and the
   * answer rather than pick-then-confirm. */
  const vChoices = fCreateElement("div", "app-dialog-choices");
  vForm.appendChild(vChoices);

  const vActions = fCreateElement("div", "app-dialog-actions");
  const vCancelButton = fCreateElement("button", "button app-dialog-cancel", "");
  vCancelButton.type = "button";
  vCancelButton.value = "cancel";
  const vConfirmButton = fCreateElement("button", "button button-primary app-dialog-confirm", "");
  vConfirmButton.type = "submit";
  /* A <form method="dialog"> closes the dialog with the submit button's value,
   * and browsers disagree about whether that happens before or after the
   * submit handler runs. With the value set here the answer is the same
   * either way. */
  vConfirmButton.value = "confirm";
  vActions.appendChild(vCancelButton);
  vActions.appendChild(vConfirmButton);
  vForm.appendChild(vActions);

  vDialog.appendChild(vForm);
  document.body.appendChild(vDialog);

  vCancelButton.addEventListener("click", function () {
    vDialog.close("cancel");
  });

  /* Escape, the backdrop and the close button all land here, so there is one
   * place that answers the promise and it always gets answered. */
  vDialog.addEventListener("close", function () {
    if (vOpenDialogResolve === null) { return; }
    const fResolve = vOpenDialogResolve;
    vOpenDialogResolve = null;
    const vMode = vDialog.dataset.mode;
    if (vDialog.returnValue === "confirm") {
      if (vMode === "prompt") { fResolve(vInput.value); }
      else if (vMode === "choose") {
        /* Whether a choice was made, not whether its id is truthy. The empty
         * agent's id IS the empty string, so `dataset.chosen || null` turned
         * choosing it into dismissing the dialog - and the caller, which
         * treats null as "cancelled", did nothing at all. Pressing "Empty
         * agent" looked like pressing Escape. */
        fResolve("chosen" in vDialog.dataset ? vDialog.dataset.chosen : null);
      }
      else { fResolve(true); }
    } else {
      fResolve(vMode === "confirm" ? false : null);
    }
  });

  /* Clicking outside the panel closes it, the way the native dialog does not. */
  vDialog.addEventListener("click", function (pEvent) {
    if (pEvent.target === vDialog) { vDialog.close("cancel"); }
  });

  return vDialog;
}

function fOpenDialog(dOptions) {
  const vDialog = fBuildDialogElement();
  const vForm = vDialog.querySelector(".app-dialog-form");
  const vTitle = vDialog.querySelector(".app-dialog-title");
  const vMessage = vDialog.querySelector(".app-dialog-message");
  const vField = vDialog.querySelector(".app-dialog-field");
  const vInput = vDialog.querySelector(".app-dialog-input");
  const vCancelButton = vDialog.querySelector(".app-dialog-cancel");
  const vConfirmButton = vDialog.querySelector(".app-dialog-confirm");

  vTitle.textContent = dOptions.title || "";
  vTitle.hidden = !dOptions.title;
  vMessage.textContent = dOptions.message || "";
  vMessage.hidden = !dOptions.message;

  vDialog.dataset.mode = dOptions.mode || "confirm";
  vField.hidden = dOptions.mode !== "prompt";
  vInput.value = dOptions.value || "";
  vInput.placeholder = dOptions.placeholder || "";

  const vChoices = vDialog.querySelector(".app-dialog-choices");
  fClear(vChoices);
  vChoices.hidden = dOptions.mode !== "choose";
  if (dOptions.mode === "choose") {
    (dOptions.choices || []).forEach(function (dChoice) {
      const vButton = fCreateElement("button", "app-dialog-choice");
      vButton.type = "button";
      vButton.appendChild(fCreateElement("span", "app-dialog-choice-name",
                                         dChoice.name));
      if (dChoice.description) {
        vButton.appendChild(fCreateElement("span", "app-dialog-choice-hint",
                                           dChoice.description));
      }
      /* A second line for what choosing this actually does. On the agent
       * examples it is the tools it comes with, which is the part worth
       * reading before pressing it: a name and a sentence do not say that
       * something arrives able to delete mail. */
      if (dChoice.detail) {
        vButton.appendChild(fCreateElement("span", "app-dialog-choice-detail",
                                           dChoice.detail));
      }
      vButton.addEventListener("click", function () {
        vDialog.dataset.chosen = dChoice.id;
        vDialog.close("confirm");
      });
      vChoices.appendChild(vButton);
    });
    delete vDialog.dataset.chosen;
  }

  vCancelButton.textContent = dOptions.cancelLabel
    || fTranslate("common.cancel", "Cancel");
  vConfirmButton.textContent = dOptions.confirmLabel
    || fTranslate("common.confirm", "Confirm");
  vConfirmButton.classList.toggle("button-danger-solid", !!dOptions.danger);
  vConfirmButton.hidden = dOptions.mode === "choose";

  vDialog.returnValue = "";
  /* The form's submit sets the return value; the cancel button sets its own. */
  vForm.onsubmit = function () { vDialog.returnValue = "confirm"; };

  return new Promise(function (fResolve) {
    vOpenDialogResolve = fResolve;
    vDialog.showModal();
    if (dOptions.mode === "prompt") {
      vInput.focus();
      vInput.select();
    } else if (dOptions.mode === "choose") {
      const vFirst = vDialog.querySelector(".app-dialog-choice");
      if (vFirst) { vFirst.focus(); }
    } else if (dOptions.danger) {
      /* A destructive dialog has NO default button: the focus goes to the
       * dialog itself, so Enter does neither thing and the user has to say
       * which one they mean.
       *
       * The focus used to start on Cancel, so that Enter by reflex would not
       * delete anything. It did not delete anything - and it did not say so
       * either: the dialog closed, no request was sent, and the key was still
       * there afterwards. "Confirm did nothing" is what that looks like from
       * the outside, and it was reported as a bug twice.
       *
       * Enter cannot submit from here: a form is only submitted implicitly
       * from a text field, and the focus is on neither button nor field.
       * Escape still cancels, which is the one keyboard answer that is
       * universal and unambiguous. */
      vDialog.focus();
    } else {
      /* An ordinary confirmation destroys nothing, so Enter means yes, which
       * is what anyone pressing it expects. */
      vConfirmButton.focus();
    }
  });
}

function fConfirm(dOptions) {
  return fOpenDialog(Object.assign({}, dOptions, { mode: "confirm" }));
}

function fPrompt(dOptions) {
  return fOpenDialog(Object.assign({}, dOptions, { mode: "prompt" }));
}

/* Pick one of a list, or cancel. Resolves to the chosen id, or null.
 *
 * Each choice is its own button rather than a <select> with a Confirm beside
 * it: a menu of things to create is read by looking at it, and a list of
 * options with a description under each says far more than a dropdown that
 * shows one line at a time. */
function fChoose(dOptions) {
  return fOpenDialog(Object.assign({}, dOptions, { mode: "choose" }));
}
