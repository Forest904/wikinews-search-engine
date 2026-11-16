"use strict";
window.Annotation = (() => {
  const $ = id => document.getElementById(id);
  let session = null;
  function message(text, kind = '') { $('message').textContent = text; $('message').className = `notice ${kind}`; }
  async function api(path, data, binary = false) {
    const response = await fetch(`/api/annotation/${path}`, data === undefined ? {cache:'no-store'} : {
      method:'POST', headers:{'Content-Type':'application/json', 'X-CSRF-Token':session?.csrf || ''},
      body:JSON.stringify(data)
    });
    if (!response.ok) {
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
    async function ready(user) {
      session = user; $('login-panel').hidden = true; $('account').hidden = false;
      $('user-name').textContent = user.user_id; $('coordinate-link').hidden = !user.coordinator;
      await onReady(user); message('');
    }
    $('login').onsubmit = async event => {
      event.preventDefault(); const button = event.target.querySelector('button'); button.disabled = true;
      try { await ready(await api('login', Object.fromEntries(new FormData(event.target)))); $('login-password').value = ''; }
      catch(error) { message(error.message, 'error'); }
      finally { button.disabled = false; }
    };
    $('logout').onclick = async () => {
      if (window.annotationDirty && !confirm('Ci sono modifiche non salvate. Vuoi uscire?')) return;
      try { await api('logout', {}); window.annotationDirty = false; location.reload(); }
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
