/* Add nearby city and hosted demo events to an existing ReVive listing detail page.
   Runs separately, without modifying the team's reviews or listing scripts. */
(() => {
  const spaceId = new URLSearchParams(location.search).get('id');
  if (!spaceId) return;
  const style=document.createElement('style');
  style.textContent=`
    .revive-insights{background:#fff;border:1px solid #e9ebee;border-radius:16px;padding:20px;margin-bottom:16px}
    .revive-insights h2{font-size:20px;margin:0 0 9px}.revive-insights p{line-height:1.5;color:#737982}
    .revive-insights h3{font-size:14px;margin:16px 0 8px}
    .revive-insights .revive-event-item{border:1px solid #e9ebee;border-radius:12px;padding:12px;margin:8px 0}
    .revive-insights .revive-event-item strong{display:block;margin:6px 0}
    .revive-insights .revive-event-item .meta{font-size:12px;color:#737982;line-height:1.5}
    .revive-insights .event-pill{font-size:11px;font-weight:800;border-radius:8px;padding:4px 7px;color:#1558b2;background:#edf2ff;display:inline-block}
    .revive-insights .event-pill.demo{color:#178049;background:#e5f6eb}
    .revive-insights a{color:#bb2449;text-decoration:underline}
    .revive-insights .note{font-size:11px;color:#737982;margin:10px 0 0}
  `;
  document.head.appendChild(style);
  const today=()=>new Date().toLocaleDateString('sv-SE',{timeZone:'Europe/Berlin'});
  const valid=x=>x!==null&&x!==undefined&&x!==''&&Number.isFinite(Number(x));
  const coords=loc=>{
    const lat=loc?.latitude??loc?.lat??loc?.coordinates?.latitude;
    const lng=loc?.longitude??loc?.lng??loc?.lon??loc?.coordinates?.longitude;
    return valid(lat)&&valid(lng)&&Math.abs(Number(lat))<=90&&Math.abs(Number(lng))<=180?[Number(lng),Number(lat)]:null;
  };
  const km=(a,b)=>{
    const r=x=>x*Math.PI/180;
    const dlat=r(b[1]-a[1]),dlng=r(b[0]-a[0]);
    const h=Math.sin(dlat/2)**2+Math.cos(r(a[1]))*Math.cos(r(b[1]))*Math.sin(dlng/2)**2;
    return 12742*Math.asin(Math.min(1,Math.sqrt(h)));
  };
  const add=(parent,tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=String(text);if(cls)n.className=cls;parent.appendChild(n);return n;};
  const dateFormat=d=>/^\d{4}-\d{2}-\d{2}$/.test(d||'')?new Date(d+'T12:00:00').toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'}):(d||'Date to confirm');
  function addEvent(container,e,distance){
    const card=add(container,'div',undefined,'revive-event-item');
    add(card,'span',e.is_synthetic?'Fictional ReVive event':'City-sourced · verify details','event-pill'+(e.is_synthetic?' demo':''));
    add(card,'strong',e.event_name||'Untitled event');
    add(card,'div',`${dateFormat(e.date)}${e.start_time?' · '+e.start_time:''}${distance!==null?' · '+distance.toFixed(1)+' km away':''}`,'meta');
    add(card,'div',e.location?.venue||e.location?.district||'Location to confirm','meta');
    if(!e.is_synthetic && /^https:\/\//.test(e.source_url||'')){
      const a=add(card,'a','Check city calendar ↗');a.href=e.source_url;a.target='_blank';a.rel='noopener noreferrer';
    }
    if(e.is_synthetic)add(card,'div','Demonstration only · not an actual scheduled event','note');
  }
  async function run(){
    const anchor=document.querySelector('#all-fields')?.closest('section.panel');
    const left=anchor?.parentElement;
    if(!anchor||!left)return;
    const panel=document.createElement('section');panel.className='revive-insights';
    panel.setAttribute('aria-label','Opportunities around this space');
    add(panel,'h2','✦ Opportunities around this space');
    const status=add(panel,'p','Loading nearby events…');
    left.insertBefore(panel,anchor);
    try{
      const [evResp,spaceResp]=await Promise.all([
        fetch('/api/events',{cache:'no-store'}),
        fetch('/spaces/'+encodeURIComponent(spaceId),{cache:'no-store'})
      ]);
      if(!evResp.ok||!spaceResp.ok)throw new Error('Could not load event or space data');
      const [data,space]=await Promise.all([evResp.json(),spaceResp.json()]);
      if(!Array.isArray(data.events))throw new Error('Invalid events JSON');
      const pCoords=coords(space.address);
      const relevant=data.events.filter(e=>!e.date||e.date>=today());
      const atSpace=relevant.filter(e=>e.is_synthetic===true && String(e.location?.space_id||'')===String(spaceId));
      const nearby=pCoords?relevant.filter(e=>e.is_synthetic===false)
        .map(e=>({e,position:coords(e.location)})).filter(x=>x.position)
        .map(x=>({e:x.e,distance:km(pCoords,x.position)})).filter(x=>x.distance<=3)
        .sort((a,b)=>a.distance-b.distance).slice(0,4):[];
      status.textContent='Explore how nearby cultural activity might inspire temporary use. Proximity does not guarantee demand.';
      add(panel,'h3','Events hosted at this space');
      if(!atSpace.length)add(panel,'p','No hosted demo events currently linked to this property.');
      atSpace.forEach(e=>addEvent(panel,e,null));
      add(panel,'h3','City events within 3 km');
      if(!nearby.length)add(panel,'p','No upcoming geolocated city events found within 3 km.');
      nearby.forEach(x=>addEvent(panel,x.e,x.distance));
      const suggestions=(space.purposes_allowed_or_suggested||[]).slice(0,3);
      if(suggestions.length)add(panel,'p','Potential uses to explore: '+suggestions.join(', ')+'.');
      add(panel,'p','City event information should be rechecked. Listing locations and hosted ReVive events are fictional demo data.','note');
    }catch(error){
      status.textContent='Event insights are temporarily unavailable. The property details and reviews still work.';
      console.warn('Could not load nearby event insights:',error);
    }
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',run,{once:true});else run();
})();
