"use strict";
const savedKey = "newsfinder.saved.v1";
function explorerIcon(name) {
  const ns = "http://www.w3.org/2000/svg",
    svg = document.createElementNS(ns, "svg"),
    use = document.createElementNS(ns, "use");
  svg.classList.add("icon");
  svg.setAttribute("aria-hidden", "true");
  use.setAttribute("href", "/static/explorer-icons.svg#" + name);
  svg.append(use);
  return svg;
}
function setNavigation(mode) {
  const target =
    mode === "saved"
      ? "/?view=saved"
      : location.hash === "#folders"
        ? "/#folders"
        : "/";
  for (const link of document.querySelectorAll(".ribbon-item,#sidebar a")) {
    if (link.getAttribute("href") === target)
      link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
}
function savedItems() {
  try {
    const items = JSON.parse(localStorage.getItem(savedKey));
    return Array.isArray(items)
      ? items.filter(
          (item) =>
            typeof item?.id === "string" && typeof item.title === "string",
        )
      : [];
  } catch {
    return [];
  }
}
function refreshSaved() {
  const ids = new Set(savedItems().map((item) => item.id));
  document.querySelector("#saved-count").textContent = ids.size
    ? "(" + ids.size + ")"
    : "";
  for (const button of document.querySelectorAll(".save-button[data-id]")) {
    const active = ids.has(button.dataset.id);
    button.setAttribute("aria-pressed", String(active));
    button.setAttribute("aria-label", "Salva " + button.dataset.title);
    button.title = active ? "Rimuovi dai salvati" : "Salva articolo";
    button.replaceChildren(explorerIcon("saved"));
    if (button.closest(".article-tools"))
      button.append(active ? "Salvato" : "Salva");
  }
}
function updateCollection() {
  if (
    document.querySelector("#saved-view") &&
    !document.querySelector("#saved-view").hidden
  )
    savedView();
  else refreshSaved();
}
function restoreListPosition() {
  try {
    const key = "newsfinder.scroll." + location.search;
    const offset = sessionStorage.getItem(key);
    if (offset !== null) {
      window.scrollTo(0, Number(offset));
      sessionStorage.removeItem(key);
    }
  } catch {}
}
document.addEventListener("click", (event) => {
  if (event.target.closest(".result-copy a")) {
    try {
      sessionStorage.setItem(
        "newsfinder.scroll." + location.search,
        String(window.scrollY),
      );
    } catch {}
  }
  const button = event.target.closest(".save-button");
  if (!button) return;
  const buttons = [...document.querySelectorAll("#saved-results button")],
    index = buttons.indexOf(button);
  const items = savedItems(),
    existing = items.findIndex((item) => item.id === button.dataset.id);
  if (existing >= 0) items.splice(existing, 1);
  else
    items.unshift({
      id: button.dataset.id,
      title: button.dataset.title,
      snippet: button.dataset.snippet || "",
      savedAt: Date.now(),
    });
  try {
    localStorage.setItem(savedKey, JSON.stringify(items));
  } catch {
    alert("Impossibile salvare in questo browser.");
    return;
  }
  updateCollection();
  if (index >= 0) {
    const remaining = document.querySelectorAll("#saved-results button");
    (
      remaining[Math.min(index, remaining.length - 1)] ||
      document.querySelector("#q")
    ).focus();
  }
});
window.addEventListener("storage", (event) => {
  if (!event.key || event.key === savedKey) updateCollection();
});
window.addEventListener("hashchange", () =>
  setNavigation(new URLSearchParams(location.search).get("view")),
);
setNavigation(new URLSearchParams(location.search).get("view"));
refreshSaved();
