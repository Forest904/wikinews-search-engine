const form = document.querySelector('#search-form');
const status = document.querySelector('#status');
const results = document.querySelector('#results');
const button = form.querySelector('button');
const initial = new URLSearchParams(window.location.search);
form.elements.q.value = initial.get('q') || '';
if (Array.from(form.elements.profile.options).some(option => option.value === initial.get('profile'))) form.elements.profile.value = initial.get('profile');
const previous = document.querySelector('#previous');
const next = document.querySelector('#next');
const pageStatus = document.querySelector('#page-status');
let currentPage = Number(initial.get('page') || 1);
const pageSize = Number(initial.get('page_size') || 10);

async function search() {
  if (button.disabled) return;
  const query = form.elements.q.value.trim();
  if (!query) {
    results.replaceChildren();
    status.textContent = 'Inserisci una query non vuota.';
    return;
  }
  results.replaceChildren();
  previous.disabled = next.disabled = true;
  pageStatus.textContent = '';
  button.disabled = true;
  status.textContent = 'Ricerca in corso…';
  const params = new URLSearchParams(new FormData(form));
  params.set('q', query);
  params.set('page', currentPage);
  params.set('page_size', pageSize);
  window.history.replaceState(null, '', `/?${params}`);
  form.elements.profile.disabled = true;
  form.elements.q.disabled = true;
  try {
    const response = await fetch(`/api/search?${params}`);
    if (!response.ok) {
      const messages = {
        404: 'Indice non disponibile. Esegui index build per preparare il corpus.',
        422: 'Controlla la query e i parametri di ricerca.',
        503: 'Il servizio di ricerca non è disponibile. Riprova più tardi.',
      };
      const error = response.status === 422 ? await response.json() : null;
      status.textContent = (typeof error?.detail === 'string' ? error.detail : null) || messages[response.status] || 'La ricerca non è riuscita. Riprova.';
      return;
    }
    const data = await response.json();
    status.textContent = data.total === 0
      ? 'Nessun risultato. Prova con un’altra parola.'
      : `${data.total} risultati · ${data.elapsed_ms} ms`;
    const pages = Math.min(Math.ceil(data.total / data.page_size), Math.floor(10000 / data.page_size));
    pageStatus.textContent = `Pagina ${data.page} di ${Math.max(pages, 1)}`
      + (data.total > 10000 ? ' · Navigabili i primi 10.000 risultati' : '');
    previous.disabled = data.page <= 1;
    next.disabled = data.page >= pages;
    results.start = (data.page - 1) * data.page_size + 1;
    for (const hit of data.hits) {
      const li = document.createElement('li');
      const link = document.createElement('a');
      link.href = `/articles/${encodeURIComponent(hit.document_id)}?${params}`;
      renderSegments(link, hit.title_segments, hit.title);
      const p = document.createElement('p');
      renderSegments(p, hit.snippet_segments, hit.snippet);
      li.append(link, p);
      results.append(li);
    }
  } catch {
    status.textContent = 'Impossibile contattare il servizio. Controlla la connessione e riprova.';
  } finally {
    button.disabled = false;
    form.elements.profile.disabled = false;
    form.elements.q.disabled = false;
  }
}

form.addEventListener('submit', (event) => {
  event.preventDefault();
  currentPage = 1;
  search();
});
if (initial.has('q')) search();

form.elements.profile.addEventListener('change', () => { currentPage = 1; search(); });
previous.addEventListener('click', () => { currentPage -= 1; search(); });
next.addEventListener('click', () => { currentPage += 1; search(); });

function renderSegments(element, segments, fallback) {
  if (!segments?.length) { element.textContent = fallback; return; }
  for (const segment of segments) {
    const node = segment.highlighted ? document.createElement('mark') : document.createTextNode('');
    node.textContent = segment.text;
    element.append(node);
  }
}
