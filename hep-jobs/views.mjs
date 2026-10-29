// Keep both views mounted so switching tabs preserves the vacancy filters and map.
export function installViews({document:doc,window:win,onChange}) {
  const tabs=[...doc.querySelectorAll('[data-view]')];
  const panels=new Map(tabs.map(tab=>[tab.dataset.view,doc.getElementById(tab.getAttribute('aria-controls'))]));
  let current;
  function activate(view,{navigate=false,focus=false}={}) {
    if(!panels.has(view))view='vacancies';
    const changed=current!==view;current=view;
    for(const tab of tabs){
      const active=tab.dataset.view===view;
      tab.setAttribute('aria-selected',String(active));tab.tabIndex=active?0:-1;
      panels.get(tab.dataset.view).hidden=!active;
      if(active&&focus)tab.focus();
    }
    doc.querySelector('.directory-link').hidden=view!=='vacancies';
    if(navigate){
      const url=new URL(win.location.href);url.hash=view;
      if(url.href!==win.location.href)win.history.pushState(null,'',url);
    }
    if(changed)onChange(view);
  }
  const fromLocation=()=>activate(win.location.hash==='#rumors'?'rumors':'vacancies');
  for(const [index,tab] of tabs.entries()){
    tab.addEventListener('click',event=>{event.preventDefault();activate(tab.dataset.view,{navigate:true})});
    tab.addEventListener('keydown',event=>{
      if(event.key===' '){event.preventDefault();activate(tab.dataset.view,{navigate:true});return}
      const next={ArrowRight:(index+1)%tabs.length,ArrowLeft:(index+tabs.length-1)%tabs.length,Home:0,End:tabs.length-1}[event.key];
      if(next===undefined)return;
      event.preventDefault();activate(tabs[next].dataset.view,{navigate:true,focus:true});
    });
  }
  win.addEventListener('popstate',fromLocation);win.addEventListener('hashchange',fromLocation);
  fromLocation();
  return {get current(){return current}};
}
