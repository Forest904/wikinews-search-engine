const form = document.querySelector('#search-form');
const status = document.querySelector('#status');
const results = document.querySelector('#results');

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  results.replaceChildren();
  status.textContent = 'Ricerca in corso…';
  const params = new URLSearchParams(new FormData(form));
  try {
    const response = await fetch(`/api/search?${params.toString()}`);
    const data = await response.json();
    if (!response.ok) {
      status.textContent = `Errore ${response.status}: ${JSON.stringify(data.detail)}`;
      return;
    }
    status.textContent = `${data.total} risultati · ${data.elapsed_ms} ms · ${data.index}`;
    for (const hit of data.hits) {
      const li = document.createElement('li');
      const link = document.createElement('a');
      link.href = hit.url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.textContent = hit.title;
      const p = document.createElement('p');
      p.textContent = hit.snippet;
      li.append(link, p);
      results.append(li);
    }
  } catch (error) {
    status.textContent = `Errore di rete: ${error.message}`;
  }
});
