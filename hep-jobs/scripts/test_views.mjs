import test from 'node:test';
import assert from 'node:assert/strict';
import {installViews} from '../views.mjs';

function fixture(hash=''){
  const changes=[],events={},panels={vacancies:{hidden:false},rumors:{hidden:true}},directory={hidden:false};
  const tabs=['vacancies','rumors'].map(view=>({dataset:{view},attrs:{'aria-controls':view},events:{},
    getAttribute(name){return this.attrs[name]},setAttribute(name,value){this.attrs[name]=value},
    addEventListener(type,fn){this.events[type]=fn},focus(){this.focused=true}}));
  const win={location:{href:'https://example.org/hep-jobs/?keep=1'+hash,hash},
    history:{pushState(_state,_title,url){win.location={href:url.href,hash:url.hash}}},
    addEventListener(type,fn){events[type]=fn}};
  const doc={querySelectorAll:()=>tabs,getElementById:id=>panels[id],querySelector:()=>directory};
  const api=installViews({document:doc,window:win,onChange:view=>changes.push(view)});
  const click=index=>tabs[index].events.click({preventDefault(){}});
  const key=(index,value)=>tabs[index].events.keydown({key:value,preventDefault(){}});
  const navigate=hash=>{win.location={href:'https://example.org/hep-jobs/?keep=1'+hash,hash};events.popstate()};
  return {api,panels,tabs,changes,win,directory,click,key,navigate};
}
test('a shared rumor URL opens only the rumor view without starting vacancies',()=>{
  const f=fixture('#rumors');assert.deepEqual(f.changes,['rumors']);assert.equal(f.panels.vacancies.hidden,true);
  assert.equal(f.panels.rumors.hidden,false);assert.equal(f.directory.hidden,true);assert.equal(f.tabs[1].attrs['aria-selected'],'true');
});
test('tab changes keep panel contents and URL parameters; Back restores directory view',()=>{
  const f=fixture();f.panels.vacancies.filter='cosmology';f.panels.vacancies.center=[12,43];
  f.click(1);assert.equal(new URL(f.win.location.href).searchParams.get('keep'),'1');
  f.navigate('#directory');assert.equal(f.api.current,'vacancies');assert.equal(f.directory.hidden,false);
  assert.equal(f.panels.vacancies.filter,'cosmology');assert.deepEqual(f.panels.vacancies.center,[12,43]);
  assert.deepEqual(f.changes,['vacancies','rumors','vacancies']);
});
test('keyboard navigation wraps and moves focus to the only tab stop',()=>{
  const f=fixture();f.key(0,'ArrowLeft');assert.equal(f.api.current,'rumors');assert.equal(f.tabs[1].focused,true);
  assert.equal(f.tabs[0].tabIndex,-1);assert.equal(f.tabs[1].tabIndex,0);
  f.key(1,'Home');assert.equal(f.api.current,'vacancies');f.key(0,'End');assert.equal(f.api.current,'rumors');
  f.key(1,' ');assert.deepEqual(f.changes,['vacancies','rumors','vacancies','rumors']);
});
