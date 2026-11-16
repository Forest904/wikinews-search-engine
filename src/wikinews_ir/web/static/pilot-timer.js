"use strict";
(() => {
  const {api, element, message} = Annotation;
  const panel = element('section',undefined,'panel');
  panel.setAttribute('aria-label','Tempo operativo');
  const label = element('label','Fase del timer'), phase = element('select');
  for (const [value,text] of [['reading','Lettura'],['annotation','Compilazione'],['review','Revisione']]) phase.append(new Option(text,value));
  label.append(phase);
  const start = element('button','Avvia / riprendi','secondary'), pause = element('button','Pausa','secondary');
  const status = element('p','Timer in pausa. I tempi sono misure operative dichiarate.','small');
  panel.append(label,start,pause,status);
  document.getElementById('task-area').prepend(panel);
  let active = null, chain = Promise.resolve();
  function enqueue(body) {
    chain = chain.then(() => api('timing',body)).catch(error => {
      active = null; status.textContent = 'Tempo non confermato: segmento incompleto. Riprendi esplicitamente.';
      message(error.message,'error');
    });
    return chain;
  }
  function checkpoint(stop) {
    if (!active) return chain;
    const body = {...active.body,seconds:Math.round((performance.now()-active.begin)/1000),stop};
    if (stop) { active = null; status.textContent = 'Timer in pausa.'; }
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
      active = {body,begin:performance.now()}; status.textContent = `Timer attivo: ${selected}`;
      if (document.hidden) checkpoint(true);
    } catch(error) { message(error.message,'error'); }
    finally { start.disabled = false; }
  };
  pause.onclick = () => checkpoint(true);
  window.pauseAnnotationTimer = () => checkpoint(true);
  phase.onchange = () => checkpoint(true);
  setInterval(() => checkpoint(false),15000);
  document.addEventListener('visibilitychange',() => { if (document.hidden) checkpoint(true); });
  window.addEventListener('annotation-task-changing',() => checkpoint(true));
})();
