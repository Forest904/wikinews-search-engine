"use strict";
const form = document.querySelector('#search-form');
const status = document.querySelector('#status');
const results = document.querySelector('#results');
const button = form.querySelector('button');
const previous = document.querySelector('#previous');
const next = document.querySelector('#next');
const pageStatus = document.querySelector('#page-status');
const pagination = document.querySelector('#pagination');
const empty = document.querySelector('#search-empty');
const retry = document.querySelector('#retry');
let currentPage = 1, pageSize = 10, controller = null;
const descriptions = {
  E0: 'Cerca le parole nel titolo e nel testo delle notizie.',
  E1: 'Riconosce le varianti delle parole italiane, nel titolo e nel testo.',
  E2: 'Dà più importanza alle parole presenti nel titolo.',
  E3: 'Dà più importanza al titolo e include parole simili per tollerare piccoli refusi.',
  E4: 'Premia le parole vicine. Usa "energia solare" Italia per richiedere la frase e almeno un termine esterno. Ogni frase tra virgolette è obbligatoria; il confronto usa l’analisi linguistica italiana. Le virgolette valgono solo in E4.'
};
function profileHelp() {
  document.querySelector('#profile-summary').textContent = form.elements.profile.selectedOptions[0].textContent;
  document.querySelector('#profile-help').textContent = descriptions[form.elements.profile.value] || '';
}
function restore() {
  const params = new URLSearchParams(location.search);
  form.elements.q.value = params.get('q') || '';
  form.elements.profile.value = [...form.elements.profile.options].some(o => o.value === params.get('profile')) ? params.get('profile') : 'E0';
  currentPage = Number(params.get('page') || 1);
  pageSize = Number(params.get('page_size') || 10);
  profileHelp();
}
function initialState() {
  controller?.abort(); controller = null;
  button.disabled = false;
  results.removeAttribute('aria-busy');
  results.replaceChildren(); pagination.hidden = true; retry.hidden = true; empty.hidden = false;
  document.querySelector('#main').classList.remove('has-results');
  status.className = ''; status.textContent = 'Inserisci una parola per cercare nelle notizie.';
}
async function search(historyMode = 'push') {
  const query = form.elements.q.value.trim();
  if (!query) {
    if (historyMode === 'push') history.pushState(null, '', `/?profile=${form.elements.profile.value}`);
    currentPage = 1; form.elements.q.value = ''; initialState(); return;
  }
  controller?.abort();
  const request = new AbortController(); controller = request;
  const params = new URLSearchParams(new FormData(form));
  params.set('q', query); params.set('page', currentPage); params.set('page_size', pageSize);
  const url = `/?${params}`;
  if (historyMode === 'push' && location.pathname + location.search !== url) history.pushState(null, '', url);
  else if (historyMode === 'replace') history.replaceState(null, '', url);
  document.querySelector('#main').classList.add('has-results');
  empty.hidden = true; retry.hidden = true; pagination.hidden = true;
  previous.disabled = next.disabled = true; button.disabled = true;
  results.replaceChildren(); results.setAttribute('aria-busy', 'true');
  pageStatus.textContent = ''; status.className = ''; status.textContent = 'Ricerca in corso…';
  try {
    const response = await fetch(`/api/search?${params}`, {signal:request.signal});
    if (!response.ok) {
      const messages = {404:'L’archivio non è disponibile. Riprova più tardi.',422:'Controlla la query e le opzioni di ricerca.',503:'Il servizio di ricerca non è disponibile. Riprova più tardi.'};
      const error = response.status === 422 ? await response.json() : null;
      throw new Error((typeof error?.detail === 'string' ? error.detail : null) || messages[response.status] || 'La ricerca non è riuscita. Riprova.');
    }
    const data = await response.json();
    if (controller !== request) return;
    status.textContent = data.total === 0 ? 'Nessun risultato. Prova con meno parole o modifica la modalità di ricerca.' : `${data.total.toLocaleString('it-IT')} ${data.total === 1 ? 'risultato' : 'risultati'}`;
    status.title = `Tempo di ricerca: ${data.elapsed_ms} ms`;
    const pages = Math.min(Math.ceil(data.total / data.page_size), Math.floor(10000 / data.page_size));
    pageStatus.textContent = `Pagina ${data.page} di ${Math.max(pages,1)}` + (data.total > 10000 ? ' · Primi 10.000 risultati' : '');
    pagination.hidden = pages <= 1;
    previous.disabled = data.page <= 1; next.disabled = data.page >= pages;
    results.start = (data.page - 1) * data.page_size + 1;
    for (const [index,hit] of data.hits.entries()) {
      const li = document.createElement('li'), link = document.createElement('a'), p = document.createElement('p');
      const rank = document.createElement('span'); rank.className = 'result-rank'; rank.textContent = String(results.start + index);
      rank.setAttribute('aria-hidden', 'true');
      link.href = `/articles/${encodeURIComponent(hit.document_id)}?${params}`;
      renderSegments(link, hit.title_segments, hit.title); renderSegments(p, hit.snippet_segments, hit.snippet);
      li.append(rank,link,p); results.append(li);
    }
  } catch(error) {
    if (error.name === 'AbortError' || controller !== request) return;
    status.className = 'error'; status.textContent = error instanceof TypeError ? 'Impossibile contattare il servizio. Controlla la connessione e riprova.' : error.message;
    retry.hidden = false;
  } finally {
    if (controller === request) { button.disabled = false; results.removeAttribute('aria-busy'); }
  }
}
form.addEventListener('submit', event => { event.preventDefault(); currentPage = 1; search(); });
form.elements.profile.addEventListener('change', () => { profileHelp(); currentPage = 1; if (form.elements.q.value.trim()) search(); });
previous.addEventListener('click', () => { currentPage--; search(); document.querySelector('#main').scrollIntoView(); });
next.addEventListener('click', () => { currentPage++; search(); document.querySelector('#main').scrollIntoView(); });
retry.addEventListener('click', () => search('replace'));
document.querySelectorAll('[data-query]').forEach(el => el.onclick = () => { form.elements.q.value = el.dataset.query; currentPage = 1; search(); });
window.addEventListener('popstate', () => { restore(); if (form.elements.q.value.trim()) search('none'); else initialState(); });
restore();
if (form.elements.q.value.trim()) search('replace');
function renderSegments(element, segments, fallback) {
  if (!segments?.length) { element.textContent = fallback; return; }
  for (const segment of segments) {
    const node = segment.highlighted ? document.createElement('mark') : document.createTextNode('');
    node.textContent = segment.text; element.append(node);
  }
}
