"use strict";
const searchForm = document.querySelector("#search-form");
const help = {
  semantic: "Cerca articoli per significato, anche quando usano parole diverse.",
  E0: "Cerca nel titolo e nel testo.",
  E1: "Riconosce varianti delle parole italiane.",
  E2: "Dà più importanza al titolo.",
  E3: "Include parole simili per piccoli refusi.",
  E4: "Premia le parole vicine e riconosce le frasi tra virgolette.",
};
function profileHelp() {
  const profile = searchForm.elements.profile.value;
  const live = profile === "live";
  searchForm.querySelector(".year-range").disabled = live;
  document.querySelector("#profile-help").textContent = live
    ? "Cerca nel sito corrente. Il periodo di pubblicazione si applica solo alla ricerca in archivio."
    : profile === "semantic" ? help.semantic : help[profile] + " Profilo " + profile + ".";
}

if (searchForm) {
  const control = searchForm.querySelector(".filter-control");
  const trigger = control.querySelector("#filters");
  const panel = control.querySelector("#search-options");
  let pinned = false;
  function display(open) {
    panel.hidden = !open;
    trigger.setAttribute("aria-expanded", String(open));
    if (!open) pinned = false;
  }
  control.addEventListener("pointerenter", event => {
    if (event.pointerType === "mouse") display(true);
  });
  control.addEventListener("pointerleave", () => {
    if (!pinned && !panel.contains(document.activeElement)) display(false);
  });
  trigger.addEventListener("click", () => {
    pinned = !pinned;
    display(pinned);
  });
  document.addEventListener("pointerdown", event => {
    if (!control.contains(event.target)) display(false);
  });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && !panel.hidden) {
      display(false);
      trigger.focus();
    }
  });
  control.addEventListener("focusout", event => {
    if (event.relatedTarget && !control.contains(event.relatedTarget)) display(false);
  });
  const start = searchForm.elements.year_from, end = searchForm.elements.year_to;
  function validateYears() {
    end.setCustomValidity(start.value && end.value && +start.value > +end.value
      ? "L’anno finale deve essere uguale o successivo a quello iniziale." : "");
  }
  searchForm.addEventListener("input", validateYears);
  searchForm.addEventListener("invalid", event => {
    if (panel.contains(event.target)) { pinned = true; display(true); }
  }, true);
  searchForm.addEventListener("formdata", event => {
    for (const name of ["year_from", "year_to"]) {
      if (!event.formData.get(name)) event.formData.delete(name);
    }
  });
  searchForm.addEventListener("submit", () => display(false));
  searchForm.elements.profile.addEventListener("change", profileHelp);
  profileHelp();
}
