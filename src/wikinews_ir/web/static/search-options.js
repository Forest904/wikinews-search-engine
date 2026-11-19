"use strict";
const searchForm = document.querySelector("#search-form");
// Only consume one unambiguous expression. Numeric date fragments stay searchable.
function publicationPeriod(text) {
  const years = [...text.matchAll(/(?<![\p{L}\p{N}_])\d{4}(?![\p{L}\p{N}_])/gu)];
  if (years.length < 1 || years.length > 2 || years.some(year => +year[0] === 0)) return null;
  const first = years[0], last = years[years.length - 1];
  let from = first.index, to = last.index + 4;
  if (years.length === 2) {
    const separator = text.slice(from + 4, last.index).trim();
    if (separator === ",") {
      const opening = text.slice(0, from).match(/\[\s*$/);
      const closing = text.slice(to).match(/^\s*\]/);
      if (!opening || !closing) return null;
      from -= opening[0].length;
      to += closing[0].length;
    } else if (separator !== "-" && separator !== "/") return null;
  }
  const before = text.slice(0, from), after = text.slice(to);
  if (/[-/[]\s*$|\d[.]$/.test(before) || /^\s*[-/\]]|^[.]\d/.test(after)) return null;
  return {start: first[0], end: last[0], expression: text.slice(from, to),
    query: [before.trimEnd(), after.trimStart()].filter(Boolean).join(" ").trim()};
}

let inferredPeriod = null;
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
  searchForm.elements.q.required = live || !(searchForm.elements.year_from.value || searchForm.elements.year_to.value);
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
    const live = searchForm.elements.profile.value === "live";
    searchForm.elements.q.required = live || !(start.value || end.value);
    end.setCustomValidity(start.value && end.value && +start.value > +end.value
      ? "L’anno finale deve essere uguale o successivo a quello iniziale." : "");
  }
  function syncPeriod() {
    const period = searchForm.elements.profile.value === "live" ? null : publicationPeriod(searchForm.elements.q.value);
    if (period && period.expression !== inferredPeriod?.expression) {
      const previous = inferredPeriod?.previous || [start.value, end.value];
      inferredPeriod = {expression: period.expression, previous};
      start.value = period.start;
      end.value = period.end;
    } else if (!period && inferredPeriod) {
      [start.value, end.value] = inferredPeriod.previous;
      inferredPeriod = null;
    }
    validateYears();
  }
  searchForm.addEventListener("input", event => {
    if (event.target === searchForm.elements.q) syncPeriod();
    else {
      if (inferredPeriod && (event.target === start || event.target === end))
        inferredPeriod.previous = [start.value, end.value];
      validateYears();
    }
  });
  searchForm.addEventListener("invalid", event => {
    if (panel.contains(event.target)) { pinned = true; display(true); }
  }, true);
  searchForm.addEventListener("formdata", event => {
    for (const name of ["year_from", "year_to"]) {
      if (!event.formData.get(name)) event.formData.delete(name);
    }
  });
  searchForm.addEventListener("submit", event => {
    syncPeriod();
    const period = inferredPeriod && publicationPeriod(searchForm.elements.q.value);
    if (period && !period.query && !start.value && !end.value) {
      searchForm.elements.q.setCustomValidity("Inserisci parole chiave o un periodo di pubblicazione.");
      searchForm.elements.q.reportValidity();
      searchForm.elements.q.setCustomValidity("");
      event.preventDefault();
      event.stopImmediatePropagation();
      return;
    }
    if (period) searchForm.elements.q.value = period.query;
    inferredPeriod = null;
    display(false);
  });
  searchForm.elements.profile.addEventListener("change", () => { syncPeriod(); profileHelp(); });
  profileHelp();
}
