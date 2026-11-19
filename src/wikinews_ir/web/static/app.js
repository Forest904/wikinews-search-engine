"use strict";
const form = document.querySelector("#search-form"),
  results = document.querySelector("#results"),
  status = document.querySelector("#status"),
  pagination = document.querySelector("#pagination");
let nextCursor = null;
let page = 1,
  controller = null;
const publicationDateFormat = new Intl.DateTimeFormat("it-IT", {
  day: "numeric", month: "long", year: "numeric", timeZone: "UTC",
});
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
function searchExcerpt(parts = []) {
  const match = parts.findIndex(part => part.highlighted);
  if (match < 1) return parts;
  const prefix = parts.slice(0, match).map(part => part.text).join("");
  if (prefix.length <= 36) return parts;
  const context = prefix.slice(-36).replace(/^\S*\s+/, "");
  return [{text: "? " + context, highlighted: false}, ...parts.slice(match)];
}
function liveFigure(image) {
  const figure = document.createElement("figure"), img = document.createElement("img");
  const caption = document.createElement("figcaption"), source = document.createElement("a");
  figure.className = "live-figure";
  Object.assign(img, {src: image.url, width: image.width, height: image.height, alt: "", loading: "lazy"});
  img.addEventListener("error", () => { figure.hidden = true; });
  source.href = image.source;
  source.textContent = "Scheda del file";
  if (image.artist) caption.append(image.artist + " · ");
  if (image.license_url) {
    const license = document.createElement("a");
    license.href = image.license_url;
    license.textContent = image.license;
    caption.append(license);
  } else caption.append(image.license);
  caption.append(" · ", source);
  figure.append(img, caption);
  return figure;
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
function selectedProfile(params) {
  return params.get("mode") === "live" ? "live" : params.get("profile") || "E0";
}
function restore() {
  inferredPeriod = null;
  controller?.abort();
  controller = null;
  const p = new URLSearchParams(location.search);
  form.elements.q.value = p.get("q") || "";
  form.elements.profile.value = selectedProfile(p);
  if (!form.elements.profile.value) form.elements.profile.value = "E0";
  for (const name of ["year_from", "year_to"]) {
    form.elements[name].value = p.get(name) || history.state?.years?.[name] || "";
  }
  form.elements.year_to.setCustomValidity("");
  page = Math.max(1, Number(p.get("page")) || 1);
  profileHelp();
  if (p.get("view") === "saved") savedView();
  else if (form.elements.q.value.trim() || p.get("year_from") || p.get("year_to")) search(false, p);
  else show("home");
}
async function search(push = true, applied = null, previousCursors = []) {
  const q = applied ? applied.get("q") || "" : form.elements.q.value.trim();
  const profile = applied
    ? selectedProfile(applied)
    : form.elements.profile.value;
  const live = profile === "live";
  const start = applied ? applied.get("year_from") : form.elements.year_from.value;
  const end = applied ? applied.get("year_to") : form.elements.year_to.value;
  if (!q && (live || !(start || end))) {
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
    profile,
    page: String(page),
    page_size: new URLSearchParams(location.search).get("page_size") || "10",
  });
  if (!live && start) params.set("year_from", start);
  if (!live && end) params.set("year_to", end);
  if (live) {
    params.delete("profile");
    params.delete("page_size");
    params.set("mode", "live");
    if (applied?.get("cursor")) params.set("cursor", applied.get("cursor"));
  }
  if (push) {
    const years = {year_from: form.elements.year_from.value, year_to: form.elements.year_to.value};
    history.pushState(live ? {years, previousCursors} : null, "", `/?${params}`);
  }
  const heading = live ? "Risultati da Wikinotizie" : "Risultati";
  const period = start && end ? (start === end ? start : `${start}–${end}`) :
    start ? `dal ${start}` : `fino al ${end}`;
  document.querySelector("#results-title").textContent = q ? `${heading} per “${q}”` : `${heading} · ${period}`;
  document.querySelector("#foot-status").textContent = "";
  status.textContent = "Ricerca in corso…";
  results.replaceChildren();
  pagination.hidden = true;
  document.querySelector("#no-results").hidden = true;
  document.querySelector("#retry").hidden = true;
  try {
    const apiParams = live ? new URLSearchParams({q}) : params;
    if (live && params.has("cursor")) apiParams.set("cursor", params.get("cursor"));
    const response = await fetch(`/api/search${live ? "/live" : ""}?${apiParams}`, {
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
        503: profile === "semantic" ? "Ricerca semantica temporaneamente indisponibile." : "Il servizio di ricerca non è disponibile.",
      };
      throw Error(messages[response.status] || "Ricerca non riuscita.");
    }
    const data = await response.json();
    if (controller !== request) return;
    document.querySelector("#standard-search").hidden = profile === "E0";
    if (live) data.page = page;
    const hasHits = data.hits.length > 0;
    status.textContent = hasHits
      ? `${data.total.toLocaleString("it-IT")} ${data.total === 1 ? "risultato" : "risultati"}`
      : "Nessun risultato";
    document.querySelector("#foot-status").textContent =
      `Pagina ${data.page} · ${data.total} notizie`;
    document.querySelector("#no-results").hidden = hasHits;
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
      if (live) a.href = hit.local_url ? hit.local_url + "?" + params : hit.url;
      segments(a, hit.title_segments, hit.title);
      segments(p, searchExcerpt(hit.snippet_segments), hit.snippet);
      b.type = "button";
      b.className = "save-button";
      b.dataset.id = hit.document_id;
      b.dataset.title = hit.title;
      b.dataset.url = `/articles/${encodeURIComponent(hit.document_id)}`;
      b.dataset.snippet = hit.snippet;
      if (hit.publication_date) {
        const date = document.createElement("time");
        date.dateTime = hit.publication_date;
        date.textContent = publicationDateFormat.format(new Date(hit.publication_date));
        copy.append(date);
      }
      copy.append(a, p);
      if (live) {
        const destination = document.createElement("small");
        destination.textContent = hit.local_url ? "Apri la copia in archivio" : "Apri su Wikinotizie";
        if (hit.local_url) {
          const current = document.createElement("a");
          current.href = hit.url;
          current.textContent = "Versione corrente";
          destination.append(" · ", current);
        }
        copy.append(destination);
        if (hit.image) copy.append(liveFigure(hit.image));
      }
      li.append(icon, copy);
      if (!live || hit.local_url) li.append(b);
      results.append(li);
    }
    refreshSaved();
    restoreListPosition();
    if (live) {
      nextCursor = data.next_cursor;
      const previous = Boolean(history.state?.previousCursors?.length);
      pagination.hidden = !previous && !nextCursor;
      document.querySelector("#page-status").textContent = `Pagina ${page}`;
      document.querySelector("#previous").disabled = !previous;
      document.querySelector("#next").disabled = !nextCursor;
      return;
    }
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
document.querySelectorAll("[data-query]").forEach((b) =>
  b.addEventListener("click", () => {
    form.elements.q.value = b.dataset.query;
    form.elements.q.dispatchEvent(new Event("input", {bubbles: true}));
    form.requestSubmit();
  }),
);
fetch("/archivio/cartelle-home")
  .then(async response => {
    if (response.ok) document.querySelector("#home-folders").innerHTML = await response.text();
  })
  .catch(() => {}); // Keep the ordinary archive link when offline.
function turnPage(step) {
  const params = new URLSearchParams(location.search);
  const previous = [...(history.state?.previousCursors || [])];
  if (params.get("mode") === "live") {
    const target = step > 0 ? nextCursor : previous.pop();
    if (step > 0) previous.push(params.get("cursor"));
    if (target) params.set("cursor", target);
    else params.delete("cursor");
  }
  page += step;
  search(true, params, previous);
  window.scrollTo(0, 0);
}
document.querySelector("#previous").onclick = () => turnPage(-1);
document.querySelector("#next").onclick = () => turnPage(1);
document.querySelector("#retry").onclick = () => search(false, new URLSearchParams(location.search));
document.querySelector("#edit-search").onclick = () => form.elements.q.focus();
document.querySelector("#standard-search").onclick = () => {
  form.elements.profile.value = "E0";
  form.elements.profile.dispatchEvent(new Event("change"));
  form.requestSubmit();
};
window.addEventListener("popstate", restore);
restore();
