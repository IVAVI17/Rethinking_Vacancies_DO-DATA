/* ReVive events overlay. Additive to the existing MapLibre + AI search experience. */
export async function initEventsMap({ map, maplibregl, listings, openSpace }) {
  const PANEL_STYLE = `
    .revive-event-tools{position:absolute;top:16px;left:16px;z-index:4;max-width:calc(100% - 100px);background:#fffffff7;border:1px solid #e9ebee;border-radius:16px;padding:10px;box-shadow:0 4px 16px #1112;font:12px system-ui,-apple-system,sans-serif;color:#20232a}
    .revive-event-mode{display:flex;gap:4px;flex-wrap:wrap}
    .revive-event-mode button{border:0;background:transparent;border-radius:10px;padding:9px 11px;font:inherit;font-weight:800;cursor:pointer;color:#545b66}
    .revive-event-mode button[aria-pressed="true"]{background:#20232a;color:white}
    .revive-event-mode button[data-layer="spaces"][aria-pressed="true"]{background:#FFD429;color:white}
    .revive-event-mode button[data-layer="events"][aria-pressed="true"]{background:#2563eb;color:white}
    .revive-event-legend{display:flex;align-items:center;flex-wrap:wrap;gap:11px;padding:8px 4px 2px;font-size:11px}
    .revive-event-dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px}
    .revive-event-status{font-size:10px;color:#71757c;margin:5px 4px 0;line-height:1.35}
    .revive-refresh{border:0;background:none;color:#b11e42;font:inherit;cursor:pointer;text-decoration:underline;padding:0 3px}
    .revive-event-popup{font:12px/1.5 system-ui,-apple-system,sans-serif;width:min(280px,70vw);color:#20232a}
    .revive-event-popup strong{font-size:15px;display:block;margin:7px 0 4px}
    .revive-event-popup .revive-type{display:inline-block;padding:4px 8px;border-radius:9px;color:#1556a8;background:#e8f0ff;font-size:10px;font-weight:800}
    .revive-event-popup .revive-type.demo{color:#117447;background:#e5f7ee}
    .revive-event-popup .revive-event-meta{color:#656d78;margin:4px 0}
    .revive-event-popup .revive-event-action{display:block;border:1px solid #e8d5dc;border-radius:10px;background:#fff;padding:7px 8px;text-align:left;margin:7px 0 0;font:inherit;font-weight:700;color:#ac2747;cursor:pointer;width:100%}
    .revive-event-popup a{color:#a91d43}
    .revive-event-popup .revive-event-divider{border-top:1px solid #e9ebee;margin:9px 0}
    .revive-event-popup .revive-event-list{max-height:200px;overflow:auto}
    .revive-event-popup .revive-event-list button{font:inherit;text-align:left;border:0;background:#f6f7f8;width:100%;margin:3px 0;padding:9px;border-radius:8px;cursor:pointer}
    @media(max-width:720px){.revive-event-tools{left:8px;top:8px;max-width:calc(100% - 65px);padding:6px}.revive-event-mode button{padding:8px}.revive-event-legend{gap:6px;font-size:10px}}
  `;
  const css = document.createElement('style');
  css.textContent = PANEL_STYLE;
  document.head.appendChild(css);
  const place = document.querySelector('.maparea');
  if (!place) return;
  const tools = document.createElement('div');
  tools.className = 'revive-event-tools';
  tools.setAttribute('aria-label', 'Map layers');
  tools.innerHTML = `
    <div class="revive-event-mode" role="group" aria-label="Show map layers">
      <button type="button" data-layer="spaces" aria-pressed="true">Spaces</button>
      <button type="button" data-layer="events" aria-pressed="true">Events</button>
    </div>
    <div class="revive-event-legend">
      <span><i class="revive-event-dot" style="background:#FFD429"></i> Spaces</span>
      <span><i class="revive-event-dot" style="background:#2563eb"></i> City</span>
      <span><i class="revive-event-dot" style="background:#16a34a"></i> Hosted events</span>
    </div>
    <div class="revive-event-status" role="status"><span id="revive-event-status">Loading events…</span> <button type="button" class="revive-refresh" id="revive-refresh-events" aria-label="Reload events JSON">↻ Refresh</button></div>`;
  place.appendChild(tools);
  const status = tools.querySelector('#revive-event-status');
  const idToSpace = new Map(listings.map(p => [String(p.id), p]));
  const SOURCE = 'revive-events';
  const sourceData = {type:'FeatureCollection', features:[]};
  const enabled = {spaces:true, events:true};
  let events = [], eventById = new Map(), plotted = [];

  const validNumber = x => x !== null && x !== undefined && x !== '' && Number.isFinite(Number(x));
  const coords = loc => {
    if (!loc) return null;
    const lat = loc.latitude ?? loc.lat ?? loc.coordinates?.latitude;
    const lng = loc.longitude ?? loc.lng ?? loc.lon ?? loc.coordinates?.longitude;
    if (!validNumber(lat) || !validNumber(lng)) return null;
    const a = Number(lat), b = Number(lng);
    return Math.abs(a) <= 90 && Math.abs(b) <= 180 ? [b,a] : null;
  };
  const kmBetween = (a,b) => {
    const R=6371, radians=n=>n*Math.PI/180;
    const dLat=radians(b[1]-a[1]),dLng=radians(b[0]-a[0]);
    const h=Math.sin(dLat/2)**2+Math.cos(radians(a[1]))*Math.cos(radians(b[1]))*Math.sin(dLng/2)**2;
    return R*2*Math.asin(Math.min(1,Math.sqrt(h)));
  };
  function eventLocation(e){
    const actual = coords(e.location);
    if (actual) return actual;
    // Only fictionally hosted events may inherit their linked fictional space position.
    if (e.is_synthetic === true && e.location?.space_id) return coords(idToSpace.get(String(e.location.space_id))?.address);
    return null;
  }
  const future = e => !e.date || e.date >= new Date().toLocaleDateString('sv-SE', {timeZone:'Europe/Berlin'});
  function setVisible(){
    tools.querySelectorAll('[data-layer]').forEach(b =>
      b.setAttribute('aria-pressed', String(enabled[b.dataset.layer])));
    for (const name of ['clusters','cluster-count','spaces-dots','spaces-prices']) {
      if (map.getLayer(name)) map.setLayoutProperty(name,'visibility',enabled.spaces?'visible':'none');
    }
    for (const name of ['revive-event-clusters','revive-event-cluster-count','revive-event-dots','revive-event-labels']) {
      if (map.getLayer(name)) map.setLayoutProperty(name,'visibility',enabled.events?'visible':'none');
    }
  }
  tools.querySelectorAll('[data-layer]').forEach(btn => btn.addEventListener('click',()=>{
    enabled[btn.dataset.layer] = !enabled[btn.dataset.layer];
    setVisible();
  }));

  map.addSource(SOURCE, {type:'geojson',data:sourceData,cluster:true,clusterRadius:40,clusterMaxZoom:14});
  map.addLayer({id:'revive-event-clusters',type:'circle',source:SOURCE,filter:['has','point_count'],paint:{'circle-color':'#5267d7','circle-radius':['step',['get','point_count'],17,5,22,15,28],'circle-stroke-color':'#fff','circle-stroke-width':3}});
  map.addLayer({id:'revive-event-cluster-count',type:'symbol',source:SOURCE,filter:['has','point_count'],layout:{'text-field':['get','point_count_abbreviated'],'text-size':12},paint:{'text-color':'#fff'}});
  map.addLayer({id:'revive-event-dots',type:'circle',source:SOURCE,filter:['!',['has','point_count']],paint:{'circle-color':['case',['==',['get','demo'],1],'#16a34a','#2563eb'],'circle-radius':15,'circle-stroke-color':'#fff','circle-stroke-width':3}});
  map.addLayer({id:'revive-event-labels',type:'symbol',source:SOURCE,filter:['!',['has','point_count']],layout:{'text-field':['get','symbol'],'text-size':12,'text-font':['Noto Sans Bold','Open Sans Bold'],'text-allow-overlap':true},paint:{'text-color':'#fff'}});

  const create = (tag, txt, cls) => {const el=document.createElement(tag);if(txt!==undefined)el.textContent=String(txt);if(cls)el.className=cls;return el;};
  const fmtDate = x => /^\d{4}-\d{2}-\d{2}$/.test(x||'') ? new Date(x+'T12:00:00').toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'}) : (x||'Date to confirm');
  function popupForEvent(e){
    const panel=create('div',undefined,'revive-event-popup');
    const synthetic=e.is_synthetic===true;
    const tag=create('span',synthetic?'Fictional ReVive event':'City-sourced event · verify details','revive-type'+(synthetic?' demo':''));
    panel.append(tag,create('strong',e.event_name||'Untitled event'));
    panel.appendChild(create('div',`${fmtDate(e.date)}${e.start_time?' · '+e.start_time:''}`,'revive-event-meta'));
    panel.appendChild(create('div',e.location?.venue||e.location?.district||'Venue not specified','revive-event-meta'));
    if(e.description) panel.appendChild(create('p',e.description));
    if(synthetic) panel.appendChild(create('div','Demo only · not an actual booking or event','revive-event-meta'));
    if(!synthetic && /^https:\/\//.test(e.source_url||'')){
      const link=create('a','Check city event source ↗');link.href=e.source_url;link.target='_blank';link.rel='noopener noreferrer';panel.appendChild(link);
    }
    const spaceId=e.location?.space_id;
    if(spaceId && idToSpace.has(String(spaceId))){
      const button=create('button','View hosting space →','revive-event-action');button.type='button';
      button.addEventListener('click',()=>openSpace(idToSpace.get(String(spaceId))));panel.appendChild(button);
    }else{
      const position=eventLocation(e);
      if(position){
        const nearby=listings.map(p=>({p,location:coords(p.address)})).filter(x=>x.location)
          .map(({p,location})=>({p,km:kmBetween(position,location)})).filter(x=>x.km<=2)
          .sort((a,b)=>a.km-b.km).slice(0,3);
        if(nearby.length){
          panel.appendChild(create('div','Demo spaces within 2 km','revive-event-meta'));
          nearby.forEach(x=>{
            const b=create('button',`${x.p.address?.district||'Dortmund'} · ${x.km.toFixed(1)} km away →`,'revive-event-action');
            b.type='button';b.addEventListener('click',()=>openSpace(x.p));panel.appendChild(b);
          });
        }
      }
    }
    return panel;
  }
  function openEvent(e){
    const position=eventLocation(e);if(!position)return;
    const popup=new maplibregl.Popup({offset:19,maxWidth:'320px'}).setLngLat(position).setDOMContent(popupForEvent(e)).addTo(map);
    return popup;
  }
  map.on('click','revive-event-dots',e=>{
    const id=e.features?.[0]?.properties?.event_id;
    if(id && eventById.has(String(id)))openEvent(eventById.get(String(id)));
  });
  map.on('click','revive-event-clusters',async e=>{
    const feat=e.features?.[0];if(!feat)return;
    try{
      const leaves=await map.getSource(SOURCE).getClusterLeaves(feat.properties.cluster_id,100,0);
      if(!leaves.length)return;
      const all=leaves.map(f=>eventById.get(String(f.properties.event_id))).filter(Boolean);
      const panel=create('div',undefined,'revive-event-popup');
      panel.appendChild(create('strong',`${all.length} events at this location`));
      const list=create('div',undefined,'revive-event-list');
      all.sort((a,b)=>(a.date||'').localeCompare(b.date||'')).forEach(event=>{
        const btn=create('button',`${fmtDate(event.date)} · ${event.event_name||'Event'}`);
        btn.addEventListener('click',()=>openEvent(event));list.appendChild(btn);
      });panel.appendChild(list);
      new maplibregl.Popup({offset:20,maxWidth:'310px'}).setLngLat(feat.geometry.coordinates).setDOMContent(panel).addTo(map);
    }catch(err){console.warn('Event cluster could not open',err);}
  });
  for(const layer of ['revive-event-dots','revive-event-clusters']){
    map.on('mouseenter',layer,()=>{map.getCanvas().style.cursor='pointer';});
    map.on('mouseleave',layer,()=>{map.getCanvas().style.cursor='';});
  }

  async function reloadEvents(){
    status.textContent='Updating events…';
    try{
      const response=await fetch('/api/events',{cache:'no-store'});
      if(!response.ok)throw new Error(`HTTP ${response.status}`);
      const payload=await response.json();
      if(!Array.isArray(payload.events))throw new Error('Expected an events array');
      events=payload.events.filter(future);
      eventById=new Map(events.map(e=>[String(e.event_id),e]));
      plotted=events.map(e=>({event:e, position:eventLocation(e)})).filter(x=>x.position);
      map.getSource(SOURCE).setData({type:'FeatureCollection',features:plotted.map(({event:e,position},index)=>({
        type:'Feature',id:index,geometry:{type:'Point',coordinates:position},properties:{event_id:String(e.event_id),demo:e.is_synthetic?1:0,symbol:e.is_synthetic?'R':'E'}
      }))});
      const city=events.filter(e=>e.is_synthetic===false).length,demo=events.filter(e=>e.is_synthetic===true).length;
      const unplaced=events.length-plotted.length;
      status.textContent='';
      setVisible();
    }catch(err){
      status.textContent='Events unavailable; property search still works.';
      console.warn('ReVive events layer:',err);
    }
  }
  tools.querySelector('#revive-refresh-events').addEventListener('click',reloadEvents);
  await reloadEvents();
  return {reloadEvents};
}
