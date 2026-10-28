import test from 'node:test';import assert from 'node:assert/strict';
import {installSmoothZoom,wheelZoomDelta,easedZoom} from '../smooth-zoom.mjs';
class Point{constructor(x,y){this.x=x;this.y=y}subtract(p){return new Point(this.x-p.x,this.y-p.y)}divideBy(n){return new Point(this.x/n,this.y/n)}equals(p){return this.x===p.x&&this.y===p.y}}
class Events{constructor(){this.listeners=new Map();this.classList={add(){},remove(){}}}addEventListener(t,f){if(!this.listeners.has(t))this.listeners.set(t,new Set());this.listeners.get(t).add(f)}removeEventListener(t,f){this.listeners.get(t)?.delete(f)}emit(t,e={}){for(const f of this.listeners.get(t)||[])f(e)}on(ts,f){ts.split(' ').forEach(t=>this.addEventListener(t,f))}off(ts,f){ts.split(' ').forEach(t=>this.removeEventListener(t,f))}}
function harness(reduced=false){
 const container=new Events(),doc=new Events(),win=new Events(),map=new Events();let time=0,serial=0;const frames=new Map();
 map.options={maxBounds:null};map.zoom=2;map.center=new Point(0,0);map.starts=0;map.ends=0;map.moves=[];map.container=container;
 map.scrollWheelZoom={enable(){this.enabled=true},disable(){this.enabled=false}};map.touchZoom={_zooming:false};map.dragging={moving:()=>false};
 map.getContainer=()=>container;map.getZoom=()=>map.zoom;map.getMinZoom=()=>0;map.getMaxZoom=()=>8;map.getSize=()=>new Point(800,600);
 map.project=(p,z)=>new Point(p.x*2**z,p.y*2**z);map.unproject=(p,z)=>new Point(p.x/2**z,p.y/2**z);
 map.containerPointToLatLng=p=>new Point(map.center.x+(p.x-400)/2**map.zoom,map.center.y+(p.y-300)/2**map.zoom);
 map.mouseEventToContainerPoint=e=>new Point(e.clientX??600,e.clientY??220);map._limitCenter=p=>p;map._stop=()=>{};
 map._moveStart=()=>{map.starts++;map.emit('zoomstart');map.emit('movestart')};
 map._move=(c,z)=>{map.center=c;map.zoom=z;map.moves.push({c,z});map.emit('zoom');map.emit('move')};
 map._moveEnd=()=>{map.ends++;map.emit('zoomend');map.emit('moveend')};
 const api=installSmoothZoom(map,{version:'1.9.4'},{document:doc,window:win,now:()=>time,reducedMotion:()=>reduced,requestFrame:f=>{const id=++serial;frames.set(id,f);return id},cancelFrame:id=>frames.delete(id)});
 function advance(ms=16){time+=ms;const entries=[...frames.values()];frames.clear();for(const f of entries)f(time)}
 function wheel(d,extra={}){const e={deltaY:d,deltaMode:0,ctrlKey:false,target:{closest:()=>false},preventDefault(){this.prevented=true},stopPropagation(){},...extra};container.emit('wheel',e);return e}
 function settle(){for(let n=0;frames.size&&n<200;n++)advance();assert.equal(frames.size,0)}
 return {api,map,doc,container,win,wheel,advance,settle,frames};
}
test('normalizes wheel units and limits a large event',()=>{assert.equal(wheelZoomDelta({deltaY:300,deltaMode:0}),-1);assert.equal(wheelZoomDelta({deltaY:3,deltaMode:1}),-.16);assert.equal(wheelZoomDelta({deltaY:10,deltaMode:2}),-1);assert.equal(wheelZoomDelta({deltaY:-15,deltaMode:0,ctrlKey:true}),.1)});
test('easing is frame-rate independent and honors reduced motion',()=>{const a=easedZoom(2,3,16),b=easedZoom(a,3,16);assert.ok(Math.abs(b-easedZoom(2,3,32))<1e-12);assert.equal(easedZoom(2,3,16,true),3)});
test('one start/end for continuous burst; no per-frame completion',()=>{const h=harness();for(let i=0;i<12;i++){h.wheel(-20);h.advance()}assert.equal(h.map.starts,1);assert.equal(h.map.ends,0);h.settle();assert.equal(h.map.ends,1);assert.ok(h.map.moves.length>12);assert.ok(Math.abs(h.map.zoom-2.8)<.003)});
test('stationary cursor keeps the same geographic anchor',()=>{const h=harness();const point=new Point(600,220),anchor=h.map.containerPointToLatLng(point);h.wheel(-200);h.settle();const after=h.map.containerPointToLatLng(point);assert.ok(Math.hypot(anchor.x-after.x,anchor.y-after.y)<1e-10)});
test('reversal immediately discards pending zoom-in tail',()=>{const h=harness();h.wheel(-200);for(let i=0;i<4;i++)h.advance();const before=h.map.zoom;h.wheel(40);h.advance();assert.ok(h.map.zoom<before);h.settle()});
test('pointer interruption cancels queued frames and cannot pull back view',()=>{const h=harness();h.wheel(-200);h.advance();h.advance();h.container.emit('pointerdown');assert.equal(h.frames.size,0);assert.equal(h.map.ends,1);const z=h.map.zoom;h.advance(200);assert.equal(h.map.zoom,z)});
test('tab hiding and external navigation finish active gestures',()=>{for(const type of ['hidden','external']){const h=harness();h.wheel(-100);h.advance();if(type==='hidden'){h.doc.hidden=true;h.doc.emit('visibilitychange')}else h.map.emit('zoomstart');assert.equal(h.api.active,false);assert.equal(h.frames.size,0);assert.equal(h.map.ends,1)}});
test('wheel waits for existing CSS zoom, then uses its final view',()=>{const h=harness();h.map._animatingZoom=true;h.wheel(-150);h.advance();assert.equal(h.map.starts,0);h.map.zoom=3;h.map._animatingZoom=false;h.settle();assert.ok(Math.abs(h.map.zoom-3.5)<.003);assert.equal(h.map.starts,1)});
test('minimum and maximum zoom stop without oscillation',()=>{for(const [start,delta,target] of [[7.9,-500,8],[.1,500,0],[8,-30,8]]){const h=harness();h.map.zoom=start;h.wheel(delta);h.settle();assert.ok(Math.abs(h.map.zoom-target)<.003);assert.ok(h.map.moves.every(m=>m.z>=0&&m.z<=8))}});
test('native pinch and map controls do not trigger a wheel gesture',()=>{const h=harness();h.map.touchZoom._zooming=true;assert.equal(h.wheel(-30).prevented,undefined);h.map.touchZoom._zooming=false;h.wheel(-30,{target:{closest:()=>true}});assert.equal(h.api.active,false);h.container.emit('touchstart');assert.equal(h.map.touchZoom._zooming,false)});
test('destroy detaches input and cancels motion',()=>{const h=harness();h.wheel(-100);h.advance();h.api.destroy();h.wheel(-100);assert.equal(h.frames.size,0);assert.equal(h.api.active,false)});
