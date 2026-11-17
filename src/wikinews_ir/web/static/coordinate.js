"use strict";
(() => {
  const {$,api,message,element,start} = Annotation;
  let data = null, preview = null, newestBlock = null;
  function navigate(focus = false) {
    const id = ['panoramica','assegnazioni','revisioni','esportazione'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'panoramica';
    document.querySelectorAll('.coord-section').forEach(section => section.hidden = section.id !== id);
    document.querySelectorAll('.coord-nav a').forEach(link => {
      if (link.hash === `#${id}`) link.setAttribute('aria-current','page'); else link.removeAttribute('aria-current');
    });
    if (focus) $(id).focus({preventScroll:true});
  }
  window.addEventListener('hashchange', () => navigate(true));
  navigate();
  function exportSummary() {
    const packet = $('export-packet').selectedOptions[0]?.textContent;
    const split = $('export-split').selectedOptions[0].textContent;
    $('export-summary').textContent = packet ? `${packet} · ${split}. Scaricherai un archivio ZIP con giudizi consolidati, cronologia e manifest.` : 'Nessun pacchetto disponibile per l’esportazione.';
    $('export-form').querySelector('[type=submit]').disabled = !packet;
  }
  function step(name) {
    for (const item of ['configure','preview','activate']) $(`step-${item}`).classList.toggle('active', item === name);
  }
  function options(select,values,empty) {
    const selected = select.value;
    select.replaceChildren(...(empty ? [new Option(empty,'')] : []),...values.map(v => new Option(v.label,v.value)));
    if ([...select.options].some(o => o.value === selected)) select.value = selected;
  }
  function topicOptions() {
    const packet = data.packets.find(p => p.id === $('packet').value);
    options($('topic'),(packet?.topics || []).map(t => ({value:t.query_id,label:`${t.query} · ${t.pairs} documenti`}))); topicLimit();
  }
  function topicLimit() {
    const topic = data.packets.find(p => p.id === $('packet').value)?.topics.find(t => t.query_id === $('topic').value);
    $('overlap').max = topic?.pairs || 0;
    $('overlap').value = Math.min(Number($('overlap').value), Number($('overlap').max));
    $('overlap-help').textContent = `Da 0 a ${$('overlap').max} documenti assegnati anche al secondo valutatore. Per la tripla lettura: ${$('overlap').max}.`;
  }
  async function refresh() {
    data = await api('dashboard');
    $('total-assigned').textContent = data.progress.reduce((n,p) => n + p.total,0);
    $('total-completed').textContent = data.progress.reduce((n,p) => n + (p.judged || 0) + (p.needs_review || 0),0);
    $('total-reviews').textContent = data.pending_reviews.length; $('total-finalized').textContent = data.finalized;
    $('progress-table').replaceChildren(...data.progress.map(p => {
      const row = element('tr'); row.append(element('td',p.user_id));
      const cell = element('td',undefined,'progress-cell'), done = (p.judged || 0) + (p.needs_review || 0), bar = element('progress');
      bar.max = Math.max(p.total,1); bar.value = done; bar.setAttribute('aria-label',`Avanzamento di ${p.user_id}`); bar.setAttribute('aria-valuetext',`${done} di ${p.total}`);
      cell.append(element('span',`${done}/${p.total}`),bar); row.append(cell);
      [p.total,p.unstarted || 0,p.judged || 0,p.needs_review || 0,p.deferred || 0].forEach(v => row.append(element('td',v))); return row;
    }));
    const packets = data.packets.map((p,i) => ({value:p.id,label:`Pacchetto ${i + 1} · ${p.topics.map(t => t.query).join(', ')} · ${p.id.slice(0,8)}`}));
    options($('packet'),packets); options($('export-packet'),packets); topicOptions();
    const users = data.users.map(u => ({value:u.id,label:u.id})); options($('primary-user'),users); options($('secondary-user'),users,'Nessuno'); options($('third-user'),users,'Nessuno');
    $('blocks-count').textContent = `${data.blocks.length} totali · ${data.blocks.filter(b => !b.active).length} bozze`;
    $('blocks').replaceChildren(...data.blocks.map(block => {
      const card = element('div'); card.dataset.blockId = block.id; card.classList.toggle('new-block',block.id === newestBlock); card.append(element('p',`${block.query_id} · ${block.primary_user}${block.secondary_user ? ' + ' + block.secondary_user : ''}${block.third_user ? ' + ' + block.third_user : ''}`),element('span',block.active ? 'Attivo · assegnazioni congelate' : 'Bozza','status-chip'));
      if (!block.active) {
        const button = element('button','Mostra riepilogo','secondary'); button.onclick = async () => {
          button.disabled = true; try { showPreview(await api(`blocks/${block.id}`)); } catch(error) { message(error.message,'error'); } finally { button.disabled = false; }
        }; card.append(button);
      } return card;
    }));
    if (!data.blocks.length) $('blocks').append(element('p','Non sono ancora stati preparati blocchi.','muted'));
    const unassigned = data.pending_reviews.filter(r => !r.reviewer).length;
    $('review-attention').hidden = !unassigned;
    const attentionLink = element('a',`${unassigned} revisioni da assegnare`); attentionLink.href = '#revisioni';
    $('review-attention').replaceChildren(attentionLink);
    $('total-reviews').parentElement.querySelector('span').textContent = `Revisioni pendenti (${unassigned} da assegnare, ${data.pending_reviews.length - unassigned} assegnate)`;
    $('reviews').replaceChildren(...[...data.pending_reviews].sort((a,b) => Number(!!a.reviewer)-Number(!!b.reviewer)).map(review => {
      const card = element('div'); card.append(element('p',`${review.query_id} · documento ${review.document_id}`));
      card.append(element('span',review.reviewer ? `Assegnata a ${review.reviewer}` : 'Da assegnare','status-chip'));
      const label = element('label','Revisore indipendente'), select = element('select');
      options(select,review.eligible.map(u => ({value:u,label:u})), 'Scegli un revisore'); select.value = review.reviewer || '';
      label.append(select); card.append(label);
      const button = element('button','Assegna revisione','secondary'); button.disabled = !review.eligible.length;
      if (!review.eligible.length) card.append(element('p','Nessun revisore indipendente disponibile per questa coppia.','small muted'));
      button.onclick = async () => { button.disabled = true; try {
        if (!select.value) throw new Error('Scegli un revisore.');
        await api('review-assignments',{packet_id:review.packet_id,query_id:review.query_id,document_id:review.document_id,reviewer:select.value});
        await refresh(); message('Revisione assegnata.','success');
      } catch(error) { message(error.message,'error'); } finally { button.disabled = !review.eligible.length; } };
      card.append(button); return card;
    }));
    if (!data.pending_reviews.length) $('reviews').append(element('p','Nessuna revisione pendente.','muted'));
    exportSummary();
    $('block-form').querySelector('[type=submit]').disabled = !data.packets.length || !data.users.length;
  }
  function showPreview(result) {
    preview = result; const b = result.block; step('preview');
    const topic = data.packets.find(p => p.id === b.packet_id)?.topics.find(t => t.query_id === b.query_id);
    $('preview-summary').replaceChildren();
    for (const [label,value] of [['Topic',topic?.query || b.query_id],['Valutatore principale',b.primary_user],['Secondo valutatore',b.secondary_user || 'Nessuno'],['Terzo valutatore',b.third_user || 'Nessuno'],['Documenti in doppio',b.overlap],['Assegnazioni totali',(result.assignments || []).length]]) {
      $('preview-summary').append(element('dt',label),element('dd',String(value)));
    }
    $('preview-seed').textContent = `Seed: ${b.seed}`;
    $('preview-order').replaceChildren(...(result.assignments || []).map(a => element('li',`${a.user_id}: ${a.document_id}`)));
    $('block-preview').hidden = false; $('block-preview').scrollIntoView({block:'nearest'});
  }
  $('packet').onchange = topicOptions; $('topic').onchange = topicLimit;
  $('block-form').addEventListener('input', () => { preview = null; $('block-preview').hidden = true; step('configure'); window.annotationDirty = true; });
  $('block-form').addEventListener('invalid', event => { const detail = event.target.closest('details'); if (detail) detail.open = true; }, true);
  window.addEventListener('beforeunload', event => { if (window.annotationDirty) { event.preventDefault(); event.returnValue = ''; } });
  $('block-form').onsubmit = async event => {
    event.preventDefault(); const button = event.target.querySelector('[type=submit]'); button.disabled = true;
    try { showPreview(await api('blocks',{packet_id:$('packet').value,query_id:$('topic').value,
      primary_user:$('primary-user').value,secondary_user:$('secondary-user').value || null,
      third_user:$('third-user').value || null,overlap:Number($('overlap').value),seed:$('seed').value})); newestBlock = preview.block.id; window.annotationDirty = false; await refresh(); $('prepared-blocks').open = true; message('Blocco preparato. Controlla il riepilogo prima di attivarlo.'); }
    catch(error) { message(error.message,'error'); } finally { button.disabled = false; }
  };
  $('activate-block').onclick = async () => {
    if (!preview) return; $('activate-block').disabled = true;
    try { await api(`blocks/${preview.block.id}/activate`,{}); $('block-preview').hidden = true; step('activate'); await refresh(); message('Blocco attivato. I valutatori possono iniziare.','success'); }
    catch(error) { message(error.message,'error'); } finally { $('activate-block').disabled = false; }
  };
  $('refresh').onclick = async () => { try { await refresh(); message('Avanzamento aggiornato.'); } catch(error) { message(error.message,'error'); } };
  $('export-split').onchange = () => { $('release-test-label').hidden = $('export-split').value !== 'test'; $('release-test').checked = false; exportSummary(); };
  $('export-packet').onchange = () => { $('release-test').checked = false; exportSummary(); };
  $('export-form').onsubmit = async event => {
    event.preventDefault(); const button = event.target.querySelector('[type=submit]'); button.disabled = true;
    try {
      if ($('export-split').value === 'test' && !$('release-test').checked) { $('release-test').focus(); throw new Error('Conferma il rilascio esplicito del test prima di scaricare.'); }
      const blob = await api('exports',{packet_id:$('export-packet').value,split:$('export-split').value,release_test:$('release-test').checked},true);
      const url = URL.createObjectURL(blob), link = element('a'); link.href = url; link.download = `gold-${$('export-split').value}.zip`;
      document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url),1000);
      message('Archivio gold preparato. Il download include cronologia e manifest.','success');
    } catch(error) { message(error.message,'error'); } finally { button.disabled = false; }
  };
  start(async user => { if (!user.coordinator) { $('access-denied').hidden = false; return; } await refresh(); $('workspace').hidden = false; });
})();
