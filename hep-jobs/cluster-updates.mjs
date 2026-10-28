// Keep a marker that received pointer/key input alive until its click handlers
// finish. Install before the wheel adapter so capture establishes the hold
// before cancelling a wheel gesture can emit zoomend.
export function createClusterUpdates(container, render, env={}) {
  const doc=env.document||container.ownerDocument;
  const win=env.window||doc.defaultView;
  const raf=env.requestFrame||win.requestAnimationFrame.bind(win);
  const caf=env.cancelFrame||win.cancelAnimationFrame.bind(win);
  const holds=new Map();
  let pending=false,frame=null,revision=0,destroyed=false;
  const marker=event=>event.target?.closest?.('.map-marker');
  const pointerToken=event=>`pointer:${event.pointerId??0}`;
  const keyToken=event=>event.key==='Enter'?'key:enter':[' ','Spacebar'].includes(event.key)?'key:space':null;
  function cancelDeferred(){revision++;if(frame!==null)caf(frame);frame=null;}
  function pruneReleased(){for(const [id,hold] of holds)if(hold.released)holds.delete(id);}
  function drain(){if(!destroyed&&pending&&!holds.size){pending=false;render();}}
  function later(){
    if(frame!==null||destroyed)return;
    const current=revision;
    frame=raf(()=>{
      if(destroyed||current!==revision)return;
      frame=null;pruneReleased();drain();
    });
  }
  function begin(event,id){
    // A new gesture invalidates a prior release callback. Already released
    // inputs must not remain as stale holds when that callback is cancelled.
    cancelDeferred();pruneReleased();
    const target=marker(event);
    if(target&&id)holds.set(id,{target,released:false});
    drain();
  }
  function release(id){
    if(!holds.has(id))return;
    holds.get(id).released=true;later();
  }
  const pointerdown=event=>begin(event,pointerToken(event));
  const keydown=event=>{const id=keyToken(event);if(id)begin(event,id)};
  const pointerup=event=>release(pointerToken(event));
  const keyup=event=>{const id=keyToken(event);if(id)release(id)};
  const click=event=>{
    const target=marker(event);if(!target)return;
    // Capture runs before the marker's application click callback. Defer the
    // rebuild to a later frame, including for keyboard-generated DOM clicks.
    for(const hold of holds.values())if(hold.target===target)hold.released=true;
    if(holds.size)later();
  };
  const pointercancel=event=>{holds.delete(pointerToken(event));pruneReleased();drain()};
  const abandon=()=>{cancelDeferred();holds.clear();drain()};
  const visibility=()=>{if(doc.hidden)abandon()};
  container.addEventListener('pointerdown',pointerdown,true);
  container.addEventListener('keydown',keydown,true);
  doc.addEventListener('pointerup',pointerup,true);
  doc.addEventListener('pointercancel',pointercancel,true);
  doc.addEventListener('keyup',keyup,true);
  doc.addEventListener('click',click,true);
  doc.addEventListener('visibilitychange',visibility);
  win.addEventListener('blur',abandon);
  return {
    request(){if(destroyed)return;pending=true;drain()},
    // Explicit filtering supersedes input holds and any queued map update.
    flush(){if(destroyed)return;cancelDeferred();holds.clear();pending=false;render()},
    destroy(){
      if(destroyed)return;destroyed=true;cancelDeferred();holds.clear();pending=false;
      container.removeEventListener('pointerdown',pointerdown,true);
      container.removeEventListener('keydown',keydown,true);
      doc.removeEventListener('pointerup',pointerup,true);
      doc.removeEventListener('pointercancel',pointercancel,true);
      doc.removeEventListener('keyup',keyup,true);
      doc.removeEventListener('click',click,true);
      doc.removeEventListener('visibilitychange',visibility);
      win.removeEventListener('blur',abandon);
    }
  };
}
