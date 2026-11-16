"use strict";
(() => {
  const {$,api,message,element,start} = Annotation;
  let data = null, preview = null;
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
  }
  async function refresh() {
    data = await api('dashboard');
    $('total-assigned').textContent = data.progress.reduce((n,p) => n + p.total,0);
    $('total-completed').textContent = data.progress.reduce((n,p) => n + (p.judged || 0) + (p.needs_review || 0),0);
    $('total-reviews').textContent = data.pending_reviews.length; $('total-finalized').textContent = data.finalized;
    $('progress-table').replaceChildren(...data.progress.map(p => {
      const row = element('tr'); [p.user_id,p.total,p.unstarted || 0,p.judged || 0,p.needs_review || 0,p.deferred || 0].forEach(v => row.append(element('td',v))); return row;
    }));
    const packets = data.packets.map((p,i) => ({value:p.id,label:`Pacchetto ${i + 1} · ${p.topics.map(t => t.query).join(', ')} · ${p.id.slice(0,8)}`}));
    options($('packet'),packets); options($('export-packet'),packets); topicOptions();
    const users = data.users.map(u => ({value:u.id,label:u.id})); options($('primary-user'),users); options($('secondary-user'),users,'Nessuno');
    $('blocks').replaceChildren(...data.blocks.map(block => {
      const card = element('div'); card.append(element('p',`${block.query_id} · ${block.primary_user}${block.secondary_user ? ' + ' + block.secondary_user : ''}`),element('span',block.active ? 'Attivo · assegnazioni congelate' : 'Bozza','status-chip'));
      if (!block.active) {
        const button = element('button','Mostra riepilogo','secondary'); button.onclick = async () => {
          try { showPreview(await api(`blocks/${block.id}`)); } catch(error) { message(error.message,'error'); }
        }; card.append(button);
      } return card;
    }));
    if (!data.blocks.length) $('blocks').append(element('p','Non sono ancora stati preparati blocchi.','muted'));
    $('reviews').replaceChildren(...data.pending_reviews.map(review => {
      const card = element('div'); card.append(element('p',`${review.query_id} · documento ${review.document_id}`));
      const label = element('label','Revisore indipendente'), select = element('select');
      options(select,review.eligible.map(u => ({value:u,label:u})), 'Scegli un revisore'); select.value = review.reviewer || '';
      label.append(select); card.append(label);
      const button = element('button','Assegna revisione','secondary'); button.disabled = !review.eligible.length;
      button.onclick = async () => { button.disabled = true; try {
        if (!select.value) throw new Error('Scegli un revisore.');
        await api('review-assignments',{packet_id:review.packet_id,query_id:review.query_id,document_id:review.document_id,reviewer:select.value});
        await refresh(); message('Revisione assegnata.','success');
      } catch(error) { message(error.message,'error'); } finally { button.disabled = false; } };
      card.append(button); return card;
    }));
    if (!data.pending_reviews.length) $('reviews').append(element('p','Nessuna revisione pendente.','muted'));
  }
  function showPreview(result) {
    preview = result; const b = result.block;
    $('preview-summary').textContent = `${b.query_id} · principale: ${b.primary_user} · secondo: ${b.secondary_user || 'nessuno'} · ${b.overlap} documenti in doppio · seed: ${b.seed}`;
    $('preview-order').replaceChildren(...(result.assignments || []).map(a => element('li',`${a.user_id}: ${a.document_id}`)));
    $('block-preview').hidden = false; $('block-preview').scrollIntoView({block:'nearest'});
  }
  $('packet').onchange = topicOptions; $('topic').onchange = topicLimit;
  $('block-form').onsubmit = async event => {
    event.preventDefault(); const button = event.target.querySelector('button'); button.disabled = true;
    try { showPreview(await api('blocks',{packet_id:$('packet').value,query_id:$('topic').value,
      primary_user:$('primary-user').value,secondary_user:$('secondary-user').value || null,
      overlap:Number($('overlap').value),seed:$('seed').value})); await refresh(); message('Blocco preparato. Controlla il riepilogo prima di attivarlo.'); }
    catch(error) { message(error.message,'error'); } finally { button.disabled = false; }
  };
  $('activate-block').onclick = async () => {
    if (!preview) return; $('activate-block').disabled = true;
    try { await api(`blocks/${preview.block.id}/activate`,{}); $('block-preview').hidden = true; await refresh(); message('Blocco attivato. I valutatori possono iniziare.','success'); }
    catch(error) { message(error.message,'error'); } finally { $('activate-block').disabled = false; }
  };
  $('refresh').onclick = async () => { try { await refresh(); message('Avanzamento aggiornato.'); } catch(error) { message(error.message,'error'); } };
  $('export-split').onchange = () => { $('release-test-label').hidden = $('export-split').value !== 'test'; $('release-test').checked = false; };
  $('export-form').onsubmit = async event => {
    event.preventDefault(); const button = event.target.querySelector('button'); button.disabled = true;
    try {
      const blob = await api('exports',{packet_id:$('export-packet').value,split:$('export-split').value,release_test:$('release-test').checked},true);
      const url = URL.createObjectURL(blob), link = element('a'); link.href = url; link.download = `gold-${$('export-split').value}.zip`;
      document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url),1000);
      message('Archivio gold preparato. Il download include cronologia e manifest.','success');
    } catch(error) { message(error.message,'error'); } finally { button.disabled = false; }
  };
  start(async user => { if (!user.coordinator) throw new Error('Questa pagina è riservata al coordinatore. Usa la pagina Annotazione per le tue attività.'); await refresh(); $('workspace').hidden = false; });
})();
