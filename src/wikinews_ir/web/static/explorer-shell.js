const menuButton = document.querySelector("#menu-button");
const sidebar = document.querySelector("#sidebar");
const mobileLayout = matchMedia("(max-width: 700px)");

function setMobileMenu(open, returnFocus = false) {
  sidebar.classList.toggle("open", open);
  menuButton.setAttribute("aria-expanded", String(open));
  menuButton.setAttribute("aria-label", open ? "Chiudi navigazione" : "Apri navigazione");
  if (open) {
    requestAnimationFrame(() => sidebar.querySelector("a, button")?.focus());
  } else if (returnFocus) {
    menuButton.focus();
  }
}

menuButton.addEventListener("click", () => setMobileMenu(!sidebar.classList.contains("open")));
document.addEventListener("keydown", event => {
  if (event.key === "Escape" && sidebar.classList.contains("open")) {
    event.preventDefault();
    setMobileMenu(false, true);
  }
});
document.addEventListener("pointerdown", event => {
  if (sidebar.classList.contains("open") && !sidebar.contains(event.target) && !menuButton.contains(event.target)) {
    setMobileMenu(false);
  }
});
sidebar.addEventListener("click", event => {
  if (sidebar.classList.contains("open") && event.target.closest("a, button")) setMobileMenu(false, true);
});
mobileLayout.addEventListener("change", () => setMobileMenu(false));

{
  const workspace = document.querySelector(".workspace");
  const handle = document.querySelector("#sidebar-resize");
  const toggle = document.querySelector("#sidebar-toggle");
  const minimum = 132;
  const maximum = 300;
  const key = document.body.classList.contains("work-area") ? "newsfinder.work.navigation.v1" : "newsfinder.navigation.v1";
  let width = 160;
  let closed = false;
  try {
    const stored = JSON.parse(localStorage.getItem(key));
    if (Number.isFinite(stored?.width))
      width = Math.min(maximum, Math.max(minimum, stored.width));
    closed = stored?.closed === true;
  } catch {}
  function render() {
    workspace.style.setProperty("--sidebar-width", width + "px");
    workspace.classList.toggle("sidebar-closed", closed);
    toggle.firstElementChild.textContent = closed ? "\u203a" : "\u2039";
    toggle.setAttribute("aria-expanded", String(!closed));
    toggle.title = closed ? "Apri navigazione" : "Chiudi navigazione";
    toggle.setAttribute("aria-label", toggle.title);
    handle.setAttribute("aria-valuenow", closed ? 0 : width);
  }
  function remember() {
    try {
      localStorage.setItem(key, JSON.stringify({ width, closed }));
    } catch {}
  }
  function resize(value) {
    closed = value <= minimum;
    if (!closed) width = Math.min(maximum, Math.round(value));
    render();
  }
  toggle.onclick = () => {
    closed = !closed;
    render();
    remember();
  };
  let drag = null;
  handle.onpointerdown = (event) => {
    if (event.button !== 0 || drag) return;
    event.preventDefault();
    handle.focus({ preventScroll: true });
    drag = {
      x: event.clientX,
      width: closed ? 0 : width,
      previous: width,
      pointer: event.pointerId,
    };
    handle.setPointerCapture(event.pointerId);
    workspace.classList.add("resizing");
  };
  handle.onpointermove = handle.onpointerup = (event) => {
    if (drag?.pointer !== event.pointerId) return;
    resize(drag.width + event.clientX - drag.x);
    if (closed) width = drag.previous;
  };
  handle.onlostpointercapture = () => {
    drag = null;
    workspace.classList.remove("resizing");
    remember();
  };
  handle.onkeydown = (event) => {
    if (
      !["ArrowLeft", "ArrowRight", "Home", "End", "Enter"].includes(event.key)
    )
      return;
    event.preventDefault();
    if (event.key === "Enter") toggle.click();
    else if (event.key === "Home") resize(0);
    else if (event.key === "End") resize(maximum);
    else if (closed && event.key === "ArrowRight") toggle.click();
    else if (!closed) resize(width + (event.key === "ArrowRight" ? 12 : -12));
    remember();
  };
  render();
}
