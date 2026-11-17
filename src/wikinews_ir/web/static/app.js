"use strict";
const form = document.querySelector("#search-form"),
  results = document.querySelector("#results"),
  status = document.querySelector("#status"),
  pagination = document.querySelector("#pagination");
let page = 1,
  controller = null;
const help = {
  E0: "Cerca nel titolo e nel testo.",
  E1: "Riconosce varianti delle parole italiane.",
  E2: "Dà più importanza al titolo.",
  E3: "Include parole simili per piccoli refusi.",
  E4: "Premia le parole vicine e riconosce le frasi tra virgolette.",
};
function profileHelp() {
  document.querySelector("#profile-summary").textContent =
    form.elements.profile.selectedOptions[0].textContent;
  document.querySelector("#profile-help").textContent =
    help[form.elements.profile.value] +
    " Profilo " +
    form.elements.profile.value +
    ".";
}
function segments(el, parts, fallback) {
  if (!parts?.length) {
    el.textContent = fallback;
    return;
  }
  for (const part of parts) {
    const n = part.highlighted
      ? document.createElement("mark")
      : document.createTextNode("");
    n.textContent = part.text;
    el.append(n);
  }
}
function show(mode) {
  document.querySelector("#foot-status").textContent = "";
  setNavigation(mode);
  const saved = mode === "saved",
    search = mode === "results";
  document.querySelector("#main").classList.toggle("has-results", search);
  document.querySelector("#main").classList.toggle("show-saved", saved);
  document.querySelector("#results-view").hidden = !search;
  document.querySelector("#saved-view").hidden = !saved;
  document.querySelector("#crumb-current").textContent = saved
    ? "Salvati"
    : search
      ? "Risultati"
      : "Home";
}
function savedView() {
  show("saved");
  const list = document.querySelector("#saved-results");
  list.replaceChildren();
  const items = savedItems();
  document.querySelector("#saved-empty").hidden = items.length > 0;
  for (const item of items) {
    const li = document.createElement("li"),
      icon = document.createElement("span"),
      copy = document.createElement("div"),
      a = document.createElement("a"),
      b = document.createElement("button");
    icon.className = "doc-icon";
    icon.append(explorerIcon("doc"));
    copy.className = "result-copy";
    a.textContent = item.title;
    a.href = "/articles/" + encodeURIComponent(item.id) + "?view=saved";
    b.className = "save-button";
    b.type = "button";
    b.dataset.id = item.id;
    b.dataset.title = item.title;
    b.dataset.url = item.url;
    const excerpt = document.createElement("p");
    excerpt.textContent = item.snippet || "";
    copy.append(a, excerpt);
    li.append(icon, copy, b);
    list.append(li);
  }
  document.querySelector("#foot-status").textContent =
    `${items.length} documenti salvati`;
  refreshSaved();
  restoreListPosition();
}
function restore() {
  controller?.abort();
  controller = null;
  const p = new URLSearchParams(location.search);
  form.elements.q.value = p.get("q") || "";
  form.elements.profile.value = p.get("profile") || "E0";
  if (!form.elements.profile.value) form.elements.profile.value = "E0";
  page = Math.max(1, Number(p.get("page")) || 1);
  profileHelp();
  if (p.get("view") === "saved") savedView();
  else if (form.elements.q.value.trim()) search(false);
  else show("home");
}
async function search(push = true) {
  const q = form.elements.q.value.trim();
  if (!q) {
    show("home");
    if (push) history.pushState(null, "", "/");
    return;
  }
  show("results");
  controller?.abort();
  const request = new AbortController();
  controller = request;
  const params = new URLSearchParams({
    q,
    profile: form.elements.profile.value,
    page: String(page),
    page_size: new URLSearchParams(location.search).get("page_size") || "10",
  });
  if (push) history.pushState(null, "", `/?${params}`);
  document.querySelector("#results-title").textContent = `Risultati per “${q}”`;
  document.querySelector("#foot-status").textContent = "";
  status.textContent = "Ricerca in corso…";
  results.replaceChildren();
  pagination.hidden = true;
  document.querySelector("#no-results").hidden = true;
  document.querySelector("#retry").hidden = true;
  try {
    const response = await fetch(`/api/search?${params}`, {
      signal: request.signal,
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      const messages = {
        404: "L’archivio non è disponibile.",
        422:
          typeof payload.detail === "string"
            ? payload.detail
            : "Controlla la ricerca e le opzioni.",
        503: "Il servizio di ricerca non è disponibile.",
      };
      throw Error(messages[response.status] || "Ricerca non riuscita.");
    }
    const data = await response.json();
    document.querySelector("#standard-search").hidden = form.elements.profile.value === "E0";
    if (controller !== request) return;
    status.textContent = data.total
      ? `${data.total.toLocaleString("it-IT")} ${data.total === 1 ? "risultato" : "risultati"}`
      : "Nessun risultato";
    document.querySelector("#foot-status").textContent =
      `Pagina ${data.page} · ${data.total} notizie`;
    document.querySelector("#no-results").hidden = data.total !== 0;
    for (const hit of data.hits) {
      const li = document.createElement("li"),
        icon = document.createElement("span"),
        copy = document.createElement("div"),
        a = document.createElement("a"),
        p = document.createElement("p"),
        b = document.createElement("button");
      icon.className = "doc-icon";
      icon.append(explorerIcon("doc"));
      copy.className = "result-copy";
      a.href = `/articles/${encodeURIComponent(hit.document_id)}?${params}`;
      segments(a, hit.title_segments, hit.title);
      segments(p, hit.snippet_segments, hit.snippet);
      b.type = "button";
      b.className = "save-button";
      b.dataset.id = hit.document_id;
      b.dataset.title = hit.title;
      b.dataset.url = `/articles/${encodeURIComponent(hit.document_id)}`;
      b.dataset.snippet = hit.snippet;
      copy.append(a, p);
      li.append(icon, copy, b);
      results.append(li);
    }
    refreshSaved();
    restoreListPosition();
    const pages = Math.min(
      Math.ceil(data.total / data.page_size),
      Math.floor(10000 / data.page_size),
    );
    pagination.hidden = pages <= 1;
    document.querySelector("#page-status").textContent =
      `Pagina ${data.page} di ${pages}`;
    document.querySelector("#previous").disabled = data.page <= 1;
    document.querySelector("#next").disabled = data.page >= pages;
  } catch (e) {
    if (controller !== request || e.name === "AbortError") return;
    status.textContent =
      e instanceof TypeError
        ? "Connessione non disponibile. Riprova."
        : e.message;
    document.querySelector("#retry").hidden = false;
  }
}
form.addEventListener("submit", (e) => {
  e.preventDefault();
  page = 1;
  search();
});
form.elements.profile.addEventListener("change", () => {
  profileHelp();
  page = 1;
  if (form.elements.q.value.trim()) search();
});
document.querySelectorAll("[data-query]").forEach((b) =>
  b.addEventListener("click", () => {
    form.elements.q.value = b.dataset.query;
    page = 1;
    search();
  }),
);
document.querySelector("#previous").onclick = () => {
  page--;
  search();
  window.scrollTo(0, 0);
};
document.querySelector("#next").onclick = () => {
  page++;
  search();
  window.scrollTo(0, 0);
};
document.querySelector("#retry").onclick = () => search(false);
document.querySelector("#edit-search").onclick = () => form.elements.q.focus();
document.querySelector("#standard-search").onclick = () => {
  form.elements.profile.value = "E0";
  profileHelp();
  page = 1;
  search();
};
window.addEventListener("popstate", restore);
restore();
