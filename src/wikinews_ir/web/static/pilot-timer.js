"use strict";
(() => {
  const {api, element, message} = Annotation;
  const panel = element('details',undefined,'timer-panel');
  panel.id = 'timer-panel';
  panel.setAttribute('aria-label','Tempo operativo');
  const summary = element('summary','');
  const label = element('label',undefined,'timer-phase'), phase = element('select');
  phase.setAttribute('aria-label','Fase del timer');
  for (const [value,text] of [['reading','Lettura'],['annotation','Compilazione'],['review','Revisione']]) phase.append(new Option(text,value));
  label.append(phase);
  const start = element('button','Avvia / riprendi','secondary'), pause = element('button','Pausa','secondary');
  const status = element('span','Timer in pausa.','timer-state');
  status.setAttribute('aria-live','polite');
  summary.append(status);
  const actions = element('span',undefined,'timer-controls'); actions.append(label,start,pause);
  panel.append(summary,actions);
  panel.title = 'Avvio manuale. Cambiare attività o scheda mette il timer in pausa.';
  document.getElementById('timer-slot').append(panel);
  pause.disabled = true;
  const phaseNames = {reading:'Lettura',annotation:'Compilazione',review:'Revisione'};
  let active = null, chain = Promise.resolve();
  function enqueue(body) {
    chain = chain.then(() => api('timing',body)).catch(error => {
      active = null; status.textContent = 'Timer non confermato';
      start.disabled = false; pause.disabled = true;
      message(error.message,'error');
    });
    return chain;
  }
  function checkpoint(stop) {
    if (!active) return chain;
    const body = {...active.body,seconds:Math.round((performance.now()-active.begin)/1000),stop};
    if (stop) { active = null; status.textContent = 'Timer in pausa.'; start.disabled = false; pause.disabled = true; }
    return enqueue(body);
  }
  start.onclick = async () => {
    if (active || !window.annotationTimerTask || document.hidden) return;
    start.disabled = true;
    const target = window.annotationTimerTask;
    try {
      await chain;
      if (target !== window.annotationTimerTask) return;
      const {review,...key} = target;
      const selected = review ? 'review' : phase.value;
      if (!review && selected === 'review') throw new Error('La fase revisione richiede una revisione assegnata.');
      const body = {...key,phase:selected,timer_id:crypto.randomUUID(),seconds:0,stop:false};
      await api('timing',body);
      if (target !== window.annotationTimerTask) { await enqueue({...body,stop:true}); return; }
      active = {body,begin:performance.now()}; status.textContent = `Timer attivo: ${phaseNames[selected]}`;
      pause.disabled = false;
      if (document.hidden) checkpoint(true);
    } catch(error) { message(error.message,'error'); }
    finally { start.disabled = !!active; }
  };
  pause.onclick = () => checkpoint(true);
  window.pauseAnnotationTimer = () => checkpoint(true);
  phase.onchange = () => checkpoint(true);
  setInterval(() => checkpoint(false),15000);
  document.addEventListener('visibilitychange',() => { if (document.hidden) checkpoint(true); });
  window.addEventListener('annotation-task-changing',() => checkpoint(true));
})();
