// This adapter targets the bundled Leaflet 1.9.4. Its three movement hooks are
// the same path used by Leaflet's native TouchZoom: zoom transforms the SVG,
// while zoomend/moveend reproject geometry only once. Public setView() per frame
// would reset and rebuild that geometry. Recheck this adapter on Leaflet upgrades.
export function wheelZoomDelta(event, pageHeight=800) {
  const pixels=event.deltaY*(event.deltaMode===1?16:event.deltaMode===2?pageHeight:1);
  return Math.max(-1,Math.min(1,-pixels/(event.ctrlKey?150:300)));
}
export function easedZoom(current,target,elapsed,reducedMotion=false) {
  if(reducedMotion||Math.abs(target-current)<.002)return target;
  return current+(target-current)*(1-Math.exp(-Math.min(64,elapsed)/45));
}
export function installSmoothZoom(map,L,env={}) {
  if(L.version!=='1.9.4'||!['_moveStart','_move','_moveEnd','_limitCenter','_stop'].every(k=>typeof map[k]==='function')) {
    map.scrollWheelZoom.enable();
    return {cancel(){},destroy(){},get active(){return false}};
  }
  const container=map.getContainer(),doc=env.document||document,win=env.window||window;
  const raf=env.requestFrame||requestAnimationFrame,caf=env.cancelFrame||cancelAnimationFrame;
  const clock=env.now||(()=>performance.now());
  const reduced=env.reducedMotion||(()=>win.matchMedia('(prefers-reduced-motion: reduce)').matches);
  let gesture=null,frame=null,moving=false,finishing=false;
  const clamp=z=>Math.max(map.getMinZoom(),Math.min(map.getMaxZoom(),z));
  function finish(){
    if(frame!==null)caf(frame);frame=null;
    if(!gesture)return;
    const started=gesture.started;gesture=null;
    container.classList.remove('smooth-wheel-zoom');
    if(started){finishing=true;map._moveEnd(true);finishing=false;}
  }
  function tick(time){
    frame=null;if(!gesture)return;
    // A button/double-click transition may already be in flight. Keep its wheel
    // input queued, then anchor to its finished view instead of fighting its CSS.
    if(map._animatingZoom){frame=raf(tick);return;}
    const g=gesture;
    if(!g.started){
      moving=true;map._stop();moving=false;
      g.target=clamp(map.getZoom()+g.pending);g.pending=0;
      if(g.target===map.getZoom()){finish();return;}
      g.anchor=map.containerPointToLatLng(g.point);g.started=true;g.previous=time;
      container.classList.add('smooth-wheel-zoom');
      moving=true;map._moveStart(true,false);moving=false;
    }
    const current=map.getZoom();
    const zoom=clamp(easedZoom(current,g.target,Math.max(1,time-g.previous),reduced()));g.previous=time;
    const offset=g.point.subtract(map.getSize().divideBy(2));
    const center=map._limitCenter(map.unproject(map.project(g.anchor,zoom).subtract(offset),zoom),zoom,map.options.maxBounds);
    moving=true;map._move(center,zoom,{pinch:true,round:false});moving=false;
    if(time-g.lastInput>=120&&Math.abs(g.target-zoom)<.002){finish();return;}
    frame=raf(tick);
  }
  function wheel(event){
    if(event.defaultPrevented||!event.deltaY||event.target.closest?.('.leaflet-control,button,input,select,a'))return;
    if(map.touchZoom?._zooming||map.dragging?.moving())return;
    const delta=wheelZoomDelta(event,map.getSize().y);if(!delta)return;
    event.preventDefault();event.stopPropagation();
    const point=map.mouseEventToContainerPoint(event),time=clock();
    if(!gesture)gesture={point,target:map.getZoom(),pending:0,started:false,lastInput:time,previous:time,anchor:null};
    const g=gesture;
    if(g.started){
      // Re-anchor only if the cursor moves. Repeated coordinate conversions at
      // one stationary cursor would accumulate Leaflet's pixel-origin rounding.
      if(!g.point.equals(point)){g.point=point;g.anchor=map.containerPointToLatLng(point)}
      // Reversing direction discards the remaining inertial tail immediately.
      if((g.target-map.getZoom())*delta<0)g.target=map.getZoom();
      g.target=clamp(g.target+delta);
    }else{g.point=point;g.pending=Math.max(-8,Math.min(8,g.pending+delta));}
    g.lastInput=time;
    if(frame===null)frame=raf(tick);
  }
  const externalMove=()=>{if(!moving&&!finishing)finish()};
  const hidden=()=>{if(doc.hidden)finish()};
  // Capture phase completes a wheel gesture before Leaflet starts drag, pinch,
  // keyboard/button zoom, or a marker action. Never pull an interrupted view back.
  const interrupts=['pointerdown','touchstart','keydown'];
  interrupts.forEach(type=>container.addEventListener(type,finish,true));
  container.addEventListener('wheel',wheel,{passive:false});
  doc.addEventListener('visibilitychange',hidden);win.addEventListener('blur',finish);
  map.on('movestart zoomstart resize',externalMove);map.on('unload',finish);
  map.scrollWheelZoom.disable();
  return {cancel:finish,get active(){return !!gesture},destroy(){finish();container.removeEventListener('wheel',wheel);interrupts.forEach(type=>container.removeEventListener(type,finish,true));doc.removeEventListener('visibilitychange',hidden);win.removeEventListener('blur',finish);map.off('movestart zoomstart resize',externalMove);map.off('unload',finish)}};
}
