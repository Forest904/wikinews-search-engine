const form = document.querySelector('#search-form');
const status = document.querySelector('#status');
const results = document.querySelector('#results');
const button = form.querySelector('button');
const initial = new URLSearchParams(window.location.search);
form.elements.q.value = initial.get('q') || '';
if (initial.get('profile') === 'bm25') form.elements.profile.value = 'bm25';

async function search() {
  if (button.disabled) return;
  const query = form.elements.q.value.trim();
  if (!query) {
    results.replaceChildren();
    status.textContent = 'Inserisci una query non vuota.';
    return;
  }
  results.replaceChildren();
  button.disabled = true;
  status.textContent = 'Ricerca in corso…';
  const params = new URLSearchParams(new FormData(form));
  params.set('q', query);
  window.history.replaceState(null, '', `/?${params}`);
  try {
    const response = await fetch(`/api/search?${params}`);
    if (!response.ok) {
      const messages = {
        404: 'Indice non disponibile. Carica le fixture con seed-demo.',
        422: 'Controlla la query e i parametri di ricerca.',
        503: 'Il servizio di ricerca non è disponibile. Riprova più tardi.',
      };
      status.textContent = messages[response.status] || 'La ricerca non è riuscita. Riprova.';
      return;
    }
    const data = await response.json();
    status.textContent = data.total === 0
      ? 'Nessun risultato. Prova con un’altra parola.'
      : `${data.total} risultati · ${data.elapsed_ms} ms`;
    for (const hit of data.hits) {
      const li = document.createElement('li');
      const link = document.createElement('a');
      link.href = `/articles/${encodeURIComponent(hit.document_id)}?${params}`;
      link.textContent = hit.title;
      const p = document.createElement('p');
      p.textContent = hit.snippet;
      li.append(link, p);
      results.append(li);
    }
  } catch {
    status.textContent = 'Impossibile contattare il servizio. Controlla la connessione e riprova.';
  } finally {
    button.disabled = false;
  }
}

form.addEventListener('submit', (event) => {
  event.preventDefault();
  search();
});
if (initial.has('q')) search();
