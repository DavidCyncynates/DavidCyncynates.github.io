import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {rumorCard,loadRumors} from '../rumors.mjs';
const data=JSON.parse(readFileSync(new URL('../data/rumor-mills.json',import.meta.url)));
test('the source directory keeps archive and availability labels distinct',()=>{
  const ids=new Set();
  for(const source of data.sources){
    assert.ok(!ids.has(source.id));ids.add(source.id);
    assert.match(source.checkedOn,/^\d{4}-\d{2}-\d{2}$/);assert.ok(source.evidenceUrls.includes(source.url));
    const card=rumorCard(source);
    if(source.status==='current'){assert.ok(source.cycle);assert.match(card,/Open rumor mill/)}
    else if(source.status==='archive'){assert.match(card,/Open archive/);assert.doesNotMatch(card,/Open rumor mill/)}
    else {assert.match(card,/Availability unconfirmed/);assert.match(card,/Last attempted/);assert.doesNotMatch(card,/Link checked/)}
  }
});
test('a failed directory load offers a source index without changing the map',async()=>{
  const target={innerHTML:''};await loadRumors({querySelector:()=>target},async()=>({ok:false}));
  assert.match(target.innerHTML,/directory could not load/);assert.match(target.innerHTML,/sites.google.com\/site\/postdocrumor/);
});
test('source prose is escaped and unsafe link protocols are rejected',()=>{
  const source={...data.sources[0],name:'<script>bad</script>'};assert.doesNotMatch(rumorCard(source),/<script>/);
  assert.throws(()=>rumorCard({...source,url:'javascript:alert(1)'}),/Invalid rumor source/);
});
