"use strict";
window.Annotation = (() => {
  const $ = id => document.getElementById(id);
  let session = null;
  let staleSession = false;
  function message(text, kind = '') {
    $('message').textContent = text; $('message').className = `notice ${kind}`;
    // Keep feedback beside the active workflow, without forcing a scroll to the page header.
    const candidate = $('judgment-feedback') || document.querySelector('.coord-section:not([hidden]) .section-feedback');
    const local = candidate && !candidate.closest('[hidden]') ? candidate : null;
    if (local) { local.textContent = text; local.className = `notice section-feedback ${kind}`; }
    $('message').classList.toggle('sr-only', !!local && !$('workspace')?.hidden);
    $('message').setAttribute('aria-live', local && !$('workspace')?.hidden ? 'off' : 'polite');
  }
  async function api(path, data, binary = false) {
    // A later explicit retry can recover after signing in in another tab.
    if (staleSession && data !== undefined && path !== 'login') {
      const response = await fetch('/api/annotation/session', {cache:'no-store'});
      if (response.ok) {
        const renewed = await response.json();
        if (session && renewed.user_id !== session.user_id) {
          const error = new Error('È attivo un altro account. Accedi con il tuo account originale prima di salvare questo modulo.');
          error.status = 401; throw error;
        }
        session = renewed; staleSession = false;
      }
    }
    const response = await fetch(`/api/annotation/${path}`, data === undefined ? {cache:'no-store'} : {
      method:'POST', headers:{'Content-Type':'application/json', 'X-CSRF-Token':session?.csrf || ''},
      body:JSON.stringify(data)
    });
    if (!response.ok) {
      if (response.status === 401 || response.status === 403) staleSession = true;
      let detail; try { detail = (await response.json()).detail; } catch { detail = null; }
      const error = new Error(typeof detail === 'string' ? detail : `Richiesta non riuscita (${response.status}). Verifica i campi e riprova.`);
      error.status = response.status; throw error;
    }
    return binary ? response.blob() : response.json();
  }
  function element(tag, text, className) {
    const el = document.createElement(tag); if (text !== undefined) el.textContent = text;
    if (className) el.className = className; return el;
  }
  async function start(onReady) {
    $('show-password').onclick = () => {
      const show = $('login-password').type === 'password';
      $('login-password').type = show ? 'text' : 'password';
      $('show-password').textContent = show ? 'Nascondi' : 'Mostra';
      $('show-password').setAttribute('aria-pressed', String(show));
    };
    async function ready(user) {
      session = user; staleSession = false; $('login-panel').hidden = true; $('account').hidden = false;
      $('user-name').textContent = user.user_id; $('coordinate-link').hidden = !user.coordinator;
      await onReady(user); message('');
    }
    $('login').onsubmit = async event => {
      event.preventDefault(); const button = event.target.querySelector('[type=submit]'); button.disabled = true;
      $('login-message').textContent = ''; button.textContent = 'Accesso in corso…';
      try { await ready(await api('login', Object.fromEntries(new FormData(event.target)))); $('login-password').value = ''; }
      catch(error) { if ($('login-panel').hidden) message(error.message,'error'); else $('login-message').textContent = error.message; }
      finally { button.disabled = false; button.textContent = 'Accedi'; }
    };
    $('logout').onclick = async () => {
      if (window.annotationDirty && !confirm('Ci sono modifiche non salvate. Vuoi uscire?')) return;
      try { if (window.pauseAnnotationTimer) await window.pauseAnnotationTimer(); await api('logout', {}); window.annotationDirty = false; location.reload(); }
      catch(error) { message(error.message, 'error'); }
    };
    try { await ready(await api('session')); }
    catch(error) {
      if (error.status === 401) { $('login-panel').hidden = false; message(''); }
      else message(error.message, 'error');
    }
  }
  return {$, api, message, element, start};
})();
const queueTabs = document.querySelector(".work-toolbar .tabs");
if (queueTabs) {
  const toolbar = queueTabs.parentElement;
  const links = document.querySelector(".work-links");
  const shell = document.querySelector(".workspace");
  const desktop = matchMedia("(min-width:701px)");
  function placeQueueTabs() {
    const target = ((desktop.matches && !shell.classList.contains("sidebar-closed")) || (!desktop.matches && links.closest("#sidebar").classList.contains("open"))) ? links : toolbar;
    if (queueTabs.parentElement !== target) target.append(queueTabs);
  }
  new MutationObserver(placeQueueTabs).observe(shell, {attributes:true,attributeFilter:["class"]});
  new MutationObserver(placeQueueTabs).observe(links.closest("#sidebar"), {attributes:true,attributeFilter:["class"]});
  desktop.addEventListener("change",placeQueueTabs);
  placeQueueTabs();
}
