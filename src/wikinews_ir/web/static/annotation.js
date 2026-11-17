"use strict";
(() => {
  const {$, api, message, element, start} = Annotation;
  const labels = {judged:'Giudicato', needs_review:'Astensione', deferred:'Rinviato', unstarted:'Da iniziare'};
  let annotations = [], reviews = [], current = null, evidence = [], mode = 'annotation', user = null;
  let pending = null, saving = false, selectedIndex = 0;
  let topicKey = null, selectedQuote = null, matches = [], matchIndex = -1;
  let taskFilter = 'all';
  const filterNames = {all:'Tutte',todo:'Da fare',deferred:'Rinviate',completed:'Completate'};
  const includesTask = (task, filter) => filter === 'all' || (filter === 'todo' ? !task.own_judgment || task.own_judgment.status === 'unstarted' : filter === 'deferred' ? task.own_judgment?.status === 'deferred' : ['judged','needs_review'].includes(task.own_judgment?.status));
  const list = () => mode === 'annotation' ? annotations.filter(t => includesTask(t,taskFilter)) : reviews;
  function changeFilter(value) {
    if (saving || !mayLeave()) { $('task-filter').value = taskFilter; return; }
    const previous = current && key(current);
    taskFilter = value; $('task-filter').value = value;
    sessionStorage.setItem(`annotation-filter:${user.user_id}`,value);
    renderOptions(); selectTask(Math.max(0,list().findIndex(t => key(t) === previous)));
  }
  $('task-filter').onchange = () => changeFilter($('task-filter').value);
  $('show-all-tasks').onclick = () => changeFilter('all');
  const key = task => [task.packet_id, task.topic.query_id, task.document.document_id].join('/');
  function clearValidation() {
    for (const id of ['grade-error','evidence-error','rationale-error']) { $(id).hidden = true; $(id).textContent = ''; }
    $('rationale').removeAttribute('aria-invalid');
  }
  function dirty() { window.annotationDirty = true; $('save-state').textContent = 'Modifiche non salvate'; $('save-state').className = 'small dirty'; clearValidation(); }
  function mayLeave() { return !window.annotationDirty || confirm('Ci sono modifiche non salvate. Vuoi abbandonarle?'); }
  function progress() {
    const done = annotations.filter(t => ['judged','needs_review'].includes(t.own_judgment?.status)).length;
    $('progress-label').textContent = `${done}/${annotations.length}`;
    $('progress').max = Math.max(annotations.length,1); $('progress').value = done;
    $('progress').setAttribute('aria-valuetext', `${done} di ${annotations.length} annotazioni completate`);
    $('review-count').textContent = reviews.length;
  }
  function renderEvidence() {
    $('evidence-count').textContent = evidence.length; $('evidence-empty').hidden = !!evidence.length;
    $('evidence').replaceChildren(...evidence.map((item,index) => {
      const li = element('li'), quote = element('blockquote', item.quote), remove = element('button',undefined,'quiet remove-evidence');
      remove.setAttribute('aria-label','Rimuovi citazione'); remove.title = 'Rimuovi citazione';
      const icon = document.createElementNS('http://www.w3.org/2000/svg','svg');
      icon.setAttribute('viewBox','0 0 24 24'); icon.setAttribute('aria-hidden','true');
      const path = document.createElementNS('http://www.w3.org/2000/svg','path');
      path.setAttribute('d','M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7');
      icon.append(path); remove.append(icon);
      remove.type = 'button'; remove.disabled = saving; remove.onclick = () => { evidence.splice(index,1); dirty(); renderEvidence(); };
      li.append(quote,remove); return li;
    }));
  }
  function renderOptions() {
    $('task-filters').hidden = mode !== 'annotation';
    for (const option of $('task-filter').options) option.textContent = `${filterNames[option.value]} (${annotations.filter(t => includesTask(t,option.value)).length})`;
    $('show-all-tasks').hidden = mode !== 'annotation' || taskFilter === 'all';
    $('tasks').replaceChildren(...list().map((t,i) => new Option(
      `${mode === 'annotation' ? labels[t.own_judgment?.status || 'unstarted'] + ' · ' : ''}${t.document.title}`, i)));
  }
  function selectTask(index = 0) {
    window.dispatchEvent(new Event('annotation-task-changing'));
    window.annotationTimerTask = null;
    selectedIndex = index; current = list()[index]; pending = null; window.annotationDirty = false;
    selectedQuote = null; matches = []; matchIndex = -1; clearValidation();
    $('find-previous').disabled = $('find-next').disabled = true;
    $('quote-feedback').textContent = '';
    $('empty-state').hidden = !!current; $('task-area').hidden = !current;
    $('tasks').closest('.task-navigation').hidden = !current;
    if (!current) return;
    window.annotationTimerTask = {packet_id:current.packet_id,query_id:current.topic.query_id,
      document_id:current.document.document_id, review:mode === 'review'};
    $('tasks').value = String(index); $('task-position').textContent = `${index + 1} / ${list().length}`;
    $('previous-task').disabled = index === 0; $('next-task').disabled = index === list().length - 1;
    const topic = current.topic, own = mode === 'annotation' ? current.own_judgment : null;
    const nextTopicKey = `${current.packet_id}/${topic.query_id}`;
    if (topicKey !== nextTopicKey) $('topic-details').open = false;
    topicKey = nextTopicKey;
    $('topic-query').textContent = topic.query; $('topic-need').textContent = topic.information_need;
    $('topic-narrative').textContent = topic.narrative;
    $('topic-inclusions').replaceChildren(...(topic.inclusion_criteria.length ? topic.inclusion_criteria : ['Segui il bisogno informativo.']).map(t => element('li',t)));
    $('topic-exclusions').replaceChildren(...(topic.exclusion_criteria.length ? topic.exclusion_criteria : ['Nessuna esclusione aggiuntiva.']).map(t => element('li',t)));
    $('rubric').replaceChildren(...Object.entries(topic.relevance_criteria).map(([grade,text]) => {
      const row = element('div'); row.append(element('strong',grade),element('span',text)); return row;
    }));
    $('title').textContent = current.document.title; $('body').textContent = current.document.body;
    $('document-meta').textContent = `Documento ${current.document.document_id} · Revisione ${current.document.revision_id} · Testo congelato`;
    $('find').value = ''; $('find-count').textContent = '';
    $('rationale').value = own?.rationale || ''; $('reason').value = '';
    evidence = structuredClone(own?.evidence || []); renderEvidence();
    document.querySelectorAll('[name=grade]').forEach(radio => radio.checked = own?.grade === Number(radio.value));
    $('current-status').textContent = mode === 'review' ? 'Revisione indipendente' : labels[own?.status || 'unstarted'];
    $('current-status').className = `status-chip ${own ? 'saved' : ''}`;
    $('save-state').textContent = own ? `Salvato · versione ${own.version}` : 'Nessuna modifica da salvare.';
    $('save-state').className = 'small'; $('judgment-heading').textContent = mode === 'review' ? 'Decisione finale' : 'Valuta la rilevanza';
    $('defer-action').hidden = mode === 'review'; $('history-details').hidden = mode === 'review';
    $('history-details').open = false; $('history').replaceChildren();
    $('review-originals').hidden = mode !== 'review'; $('originals').replaceChildren();
    if (mode === 'review') current.originals.forEach(original => {
      const card = element('div',undefined,'original-card');
      card.append(element('strong', `${original.annotator_id} · ${original.status === 'judged' ? 'grado ' + original.grade : 'astensione'}`), element('p',original.rationale));
      original.evidence.forEach(ev => card.append(element('p',`«${ev.quote}»`))); $('originals').append(card);
    });
    sessionStorage.setItem(`annotation-resume:${user.user_id}:${mode}`, key(current));
  }
  async function refresh(preferred) {
    [annotations,reviews] = await Promise.all([api('tasks'),api('reviews')]); progress(); renderOptions();
    const remembered = preferred || sessionStorage.getItem(`annotation-resume:${user.user_id}:${mode}`);
    let index = list().findIndex(t => key(t) === remembered);
    if (index < 0 && preferred) index = Math.min(selectedIndex, list().length - 1);
    if (index < 0) index = list().findIndex(t => !t.own_judgment || t.own_judgment.status === 'deferred');
    selectTask(Math.max(0,index));
  }
  function changeMode(next) {
    if (saving || !mayLeave()) return;
    mode = next;
    for (const [id,value] of [['annotation-mode','annotation'],['review-mode','review']]) {
      $(id).classList.toggle('active', mode === value); $(id).setAttribute('aria-pressed',String(mode === value));
    }
    renderOptions(); selectTask();
  }
  $('annotation-mode').onclick = () => changeMode('annotation'); $('review-mode').onclick = () => changeMode('review');
  $('tasks').onchange = () => { if (mayLeave()) selectTask(Number($('tasks').value)); else $('tasks').value = String(selectedIndex); };
  $('previous-task').onclick = () => { if (mayLeave()) selectTask(selectedIndex - 1); };
  $('next-task').onclick = () => { if (mayLeave()) selectTask(selectedIndex + 1); };
  $('refresh-tasks').onclick = () => $('reload-task').click();
  $('reload-task').onclick = async () => {
    if (!mayLeave()) return;
    try { await refresh(current && key(current)); message('Dati aggiornati.'); }
    catch(error) { message(error.message,'error'); }
  };
  function captureQuote() {
    const selection = window.getSelection();
    if (!selection.rangeCount || selection.isCollapsed) return null;
    const range = selection.getRangeAt(0), body = $('body');
    if (!body.contains(range.startContainer) || !body.contains(range.endContainer)) return null;
    const prefix = range.cloneRange(); prefix.selectNodeContents(body); prefix.setEnd(range.startContainer,range.startOffset);
    const quote = range.toString(), begin = Array.from(prefix.toString()).length;
    return {field:'body',quote,start:begin,end:begin + Array.from(quote).length};
  }
  // Capture before button focus collapses the range, including keyboard activation.
  document.addEventListener('selectionchange', () => {
    const quote = captureQuote();
    if (quote) selectedQuote = quote;
    else if (!['quote'].includes(document.activeElement?.id)) selectedQuote = null;
  });
  function addQuote() {
    if (saving || !current) return;
    const quote = captureQuote() || selectedQuote;
    if (!quote) { $('quote-feedback').textContent = 'Seleziona prima un passaggio nel testo del documento.'; return; }
    if (evidence.some(item => item.start === quote.start && item.end === quote.end)) {
      $('quote-feedback').textContent = 'Questo passaggio è già presente nelle evidenze.'; return;
    }
    evidence.push(quote); renderEvidence(); dirty(); selectedQuote = null;
    $('quote-feedback').textContent = 'Citazione aggiunta alle evidenze.';
    message('Citazione aggiunta.');
  }
  for (const id of ['quote']) {
    $(id).addEventListener('pointerdown', () => { selectedQuote = captureQuote(); });
    $(id).onclick = addQuote;
  }
  function focusMatch(delta) {
    if (!matches.length) return;
    matchIndex = matchIndex < 0 ? (delta > 0 ? 0 : matches.length - 1) : (matchIndex + delta + matches.length) % matches.length;
    matches.forEach((mark,index) => mark.classList.toggle('current-match',index === matchIndex));
    matches[matchIndex].scrollIntoView({block:'center'});
    $('find-count').textContent = `${matchIndex + 1} di ${matches.length} occorrenze`;
  };
  $('find-previous').onclick = () => focusMatch(-1);
  $('find-next').onclick = () => focusMatch(1);
  $('find').oninput = () => {
    if (!current) return;
    const body = $('body'), text = current.document.body, query = $('find').value;
    selectedQuote = null; matches = []; matchIndex = -1;
    $('find-previous').disabled = $('find-next').disabled = true;
    body.replaceChildren(); let offset = 0, found, count = 0;
    if (!query) { body.textContent = text; $('find-count').textContent = ''; return; }
    // Regex matches preserve original UTF-16 indices, even when case folding changes length.
    const expression = new RegExp(query.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'giu');
    while ((found = expression.exec(text)) !== null) {
      body.append(document.createTextNode(text.slice(offset,found.index)));
      body.append(element('mark',found[0])); offset = found.index + found[0].length; count++;
    }
    body.append(document.createTextNode(text.slice(offset))); $('find-count').textContent = `${count} occorrenze`;
    matches = [...body.querySelectorAll('mark')];
    $('find-previous').disabled = $('find-next').disabled = !matches.length;
  };
  $('reason').onchange = () => { if ($('reason').value) { $('rationale').value = [$('rationale').value,$('reason').value].filter(Boolean).join('\n'); dirty(); } };
  $('judgment').oninput = dirty;
  $('judgment').onsubmit = event => event.preventDefault();
  $('history-details').ontoggle = async () => {
    if (!$('history-details').open || !current) return;
    const originalKey = key(current);
    try {
      const rows = await api(`history?${new URLSearchParams({packet_id:current.packet_id,query_id:current.topic.query_id,document_id:current.document.document_id})}`);
      if (!current || key(current) !== originalKey) return;
      $('history').replaceChildren(...rows.map(row => element('li',`v${row.version} · ${labels[row.status]}${row.grade === null ? '' : ' (' + row.grade + ')'} · ${new Date(row.saved_at).toLocaleString('it-IT')} — ${row.rationale}`)));
      if (!rows.length) $('history').append(element('li','Nessun salvataggio precedente.'));
    } catch(error) { message(error.message,'error'); }
  };
  function lock(value) {
    saving = value;
    document.querySelectorAll('#judgment-panel [data-state],#judgment button,#judgment input,#judgment select,#judgment textarea,#tasks,#task-filter,#previous-task,#next-task,#reload-task,#logout').forEach(el => el.disabled = value);
    if (!value) { $('previous-task').disabled = selectedIndex === 0; $('next-task').disabled = selectedIndex >= list().length - 1; }
  }
  document.querySelectorAll('[data-state]').forEach(button => button.onclick = async () => {
    if (!current || saving) return;
    const status = button.dataset.state, selected = document.querySelector('[name=grade]:checked');
    clearValidation();
    let firstInvalid = null;
    function invalid(id, text, target) { $(id).textContent = text; $(id).hidden = false; firstInvalid ||= target; }
    if (status === 'judged' && !selected) invalid('grade-error','Scegli un grado di rilevanza.','grade-field');
    if (status === 'judged' && !evidence.length) invalid('evidence-error','Aggiungi almeno una citazione dal documento.','quote');
    if (status !== 'deferred' && !$('rationale').value.trim()) {
      invalid('rationale-error','Scrivi una motivazione per questo giudizio.','rationale');
      $('rationale').setAttribute('aria-invalid','true');
    }
    if (firstInvalid) {
      const target = firstInvalid === 'grade-field' ? document.querySelector('[name=grade]') : $(firstInvalid);
      target.focus(); target.scrollIntoView({block:'nearest'}); return;
    }
    const data = {packet_id:current.packet_id,query_id:current.topic.query_id,document_id:current.document.document_id,
      status,grade:status === 'judged' && selected ? Number(selected.value) : null,rationale:$('rationale').value,evidence:structuredClone(evidence)};
    if (mode === 'annotation') data.expected_version = current.own_judgment?.version || 0; else data.basis = current.basis;
    const signature = JSON.stringify(data);
    if (!pending || pending.signature !== signature) pending = {signature, id:crypto.randomUUID()};
    data.request_id = pending.id; lock(true); $('save-state').textContent = 'Salvataggio in corso…';
    const previousKey = key(current), nextKey = list()[selectedIndex + 1] && key(list()[selectedIndex + 1]);
    try {
      if (window.pauseAnnotationTimer) await window.pauseAnnotationTimer();
      await api(mode === 'annotation' ? 'judgments' : 'decisions',data);
      window.annotationDirty = false; pending = null;
      if (button.dataset.exit) { window.location.assign('/'); return; }
      // The response confirms persistence. A refresh failure must not imply that saving failed.
      message(mode === 'review' ? 'Decisione finale salvata.' : 'Salvataggio confermato.','success');
      try { await refresh(button.dataset.advance && nextKey ? nextKey : previousKey); }
      catch(error) { $('save-state').textContent = 'Salvato. Aggiorna la pagina per ricaricare la coda.'; message(`Salvato, ma aggiornamento della coda non riuscito: ${error.message}`,'error'); }
    } catch(error) {
      $('save-state').textContent = error.status === 409
        ? 'Conflitto: il giudizio è cambiato. Conserva le tue modifiche prima di ricaricare il giudizio salvato in Altre azioni.'
        : error.status === 401
          ? 'Sessione scaduta. Accedi in un’altra scheda, poi riprova qui: il modulo è conservato.'
          : 'Salvataggio non confermato. Il contenuto del modulo è conservato: puoi riprovare.';
      $('save-state').className = 'small dirty'; message(error.message,'error');
    } finally { lock(false); }
  });
  document.addEventListener('keydown',event => {
    if (saving || !current || ['INPUT','TEXTAREA','SELECT','BUTTON'].includes(event.target.tagName) || event.ctrlKey || event.metaKey || event.altKey) return;
    if (['0','1','2'].includes(event.key)) { document.querySelector(`[name=grade][value="${event.key}"]`).checked = true; dirty(); }
  });
  window.addEventListener('beforeunload',event => { if (window.annotationDirty) { event.preventDefault(); event.returnValue = ''; } });
  document.querySelectorAll('.topbar a').forEach(link => link.addEventListener('click', event => {
    if (saving || !mayLeave()) event.preventDefault();
    else window.annotationDirty = false;
  }));
  start(async session => { user = session; const stored = sessionStorage.getItem(`annotation-filter:${user.user_id}`); taskFilter = Object.hasOwn(filterNames,stored) ? stored : 'all'; $('task-filter').value = taskFilter; await refresh(); $('workspace').hidden = false; });
})();
