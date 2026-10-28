import test from 'node:test';
import assert from 'node:assert/strict';
import {createClusterUpdates} from '../cluster-updates.mjs';
class Events {
  constructor(){this.handlers=new Map()}
  addEventListener(type,fn){if(!this.handlers.has(type))this.handlers.set(type,new Set());this.handlers.get(type).add(fn)}
  removeEventListener(type,fn){this.handlers.get(type)?.delete(fn)}
  emit(type,event={}){for(const fn of this.handlers.get(type)||[])fn(event)}
}
function harness(){
  const container=new Events(),doc=new Events(),win=new Events(),frames=new Map(),log=[];
  let serial=0;
  const mark={closest:()=>mark},other={closest:()=>null};
  const api=createClusterUpdates(container,()=>log.push('render'),{document:doc,window:win,requestFrame:fn=>{const id=++serial;frames.set(id,fn);return id},cancelFrame:id=>frames.delete(id)});
  const event=(extra={})=>({target:mark,pointerId:1,...extra});
  const advance=()=>{const next=[...frames.values()];frames.clear();next.forEach(fn=>fn())};
  return {container,doc,win,frames,log,api,event,advance,mark,other};
}
test('normal completed zoom renders immediately',()=>{const h=harness();h.api.request();assert.deepEqual(h.log,['render']);assert.equal(h.frames.size,0)});
test('held pointer survives any number of frames and request calls',()=>{const h=harness();h.container.emit('pointerdown',h.event());h.api.request();h.api.request();for(let i=0;i<30;i++)h.advance();assert.deepEqual(h.log,[]);h.doc.emit('pointerup',h.event());h.doc.emit('click',h.event());h.log.push('click action');assert.deepEqual(h.log,['click action']);h.advance();assert.deepEqual(h.log,['click action','render'])});
test('release without click eventually rebuilds',()=>{const h=harness();h.container.emit('pointerdown',h.event());h.api.request();h.doc.emit('pointerup',h.event({target:h.other}));h.advance();assert.deepEqual(h.log,['render'])});
test('Enter and Space preserve target until activation has completed',()=>{for(const key of ['Enter',' ']){const h=harness();h.container.emit('keydown',h.event({key}));h.api.request();h.doc.emit('click',h.event());h.log.push('keyboard action');h.advance();assert.deepEqual(h.log,['keyboard action','render'])}});
test('keyboard activation without DOM click releases on keyup',()=>{const h=harness();h.container.emit('keydown',h.event({key:'Enter'}));h.api.request();h.doc.emit('keyup',h.event({key:'Enter'}));h.advance();assert.deepEqual(h.log,['render'])});
test('a second gesture invalidates an older pending release callback',()=>{const h=harness();h.container.emit('pointerdown',h.event());h.api.request();h.doc.emit('pointerup',h.event());const stale=[...h.frames.values()][0];h.container.emit('pointerdown',h.event({pointerId:2}));stale();h.advance();assert.deepEqual(h.log,[]);h.doc.emit('pointerup',h.event({pointerId:2}));h.advance();assert.deepEqual(h.log,['render'])});
test('pointercancel releases immediately; independent held pointer remains protected',()=>{const h=harness();h.container.emit('pointerdown',h.event());h.container.emit('pointerdown',h.event({pointerId:2}));h.api.request();h.doc.emit('pointercancel',h.event());assert.deepEqual(h.log,[]);h.doc.emit('pointercancel',h.event({pointerId:2}));assert.deepEqual(h.log,['render'])});
test('explicit filter flush supersedes queued callbacks',()=>{const h=harness();h.container.emit('pointerdown',h.event());h.api.request();h.doc.emit('pointerup',h.event());const stale=[...h.frames.values()][0];h.api.flush();stale();h.advance();assert.deepEqual(h.log,['render'])});
test('nonmarker input never delays normal zoom updates',()=>{const h=harness();h.container.emit('pointerdown',h.event({target:h.other}));h.api.request();assert.deepEqual(h.log,['render'])});
test('blur and tab hiding cannot leave a stale interaction hold',()=>{for(const kind of ['blur','hidden']){const h=harness();h.container.emit('pointerdown',h.event());h.api.request();if(kind==='blur')h.win.emit('blur');else{h.doc.hidden=true;h.doc.emit('visibilitychange')}assert.deepEqual(h.log,['render'])}});
test('destroy removes handlers and invalidates pending callbacks',()=>{const h=harness();h.container.emit('pointerdown',h.event());h.api.request();h.doc.emit('pointerup',h.event());const stale=[...h.frames.values()][0];h.api.destroy();stale();h.api.request();h.api.flush();h.container.emit('pointerdown',h.event());h.doc.emit('pointerup',h.event());h.advance();assert.deepEqual(h.log,[]);assert.equal(h.frames.size,0)});
