window.__appLoaded = true;
(function(){
  const layersDiv = document.getElementById('layers');
  let materials = [];
  const layers = [];

  function makeLayerEl(idx){
    const d = document.createElement('div');
    d.className = 'row';
    d.innerHTML = `
      <div>
        <label>Material</label>
        <select data-idx="${idx}" class="matSelect"><option value="">—</option></select>
        <label>Name</label>
        <input type="text" class="name" value="Layer ${idx+1}">
      </div>
      <div>
        <label>Thickness (m)</label>
        <input type="number" step="0.001" class="d" value="0.100">
        <input type="range" min="0.005" max="0.500" step="0.001" value="0.100" class="dSlider">
      </div>
      <div>
        <label>λ (W/mK)</label>
        <input type="number" step="0.001" class="lambda" value="0.040">
      </div>
      <div>
        <label>μ (-)</label>
        <input type="number" step="1" class="mu" value="20">
      </div>
      <div>
        <label>ρ (kg/m³)</label>
        <input type="number" step="1" class="rho" value="800">
      </div>
      <div>
        <label>xr (%)</label>
        <input type="number" step="0.1" class="xr" value="5">
      </div>
      <div>
        <label>xmax (%)</label>
        <input type="number" step="0.1" class="xmax" value="20">
      </div>`;
    const dInput = d.querySelector('.d');
    const dSlider = d.querySelector('.dSlider');
    dSlider.addEventListener('input', () => { dInput.value = (+dSlider.value).toFixed(3); });
    dInput.addEventListener('input', () => { dSlider.value = dInput.value; });
    const sel = d.querySelector('.matSelect');
    sel.addEventListener('change', () => {
      const m = materials.find(mm => mm.name === sel.value);
      if (m) {
        d.querySelector('.lambda').value = m.lambda_;
        d.querySelector('.mu').value = m.mu;
        d.querySelector('.rho').value = m.rho;
        d.querySelector('.xr').value = m.xr_percent;
        d.querySelector('.xmax').value = m.xmax_percent;
        d.querySelector('.name').value = m.name;
      }
    });
    const fillSel = () => {
      sel.innerHTML = '<option value="">—</option>' + materials.map(m => `<option>${m.name}</option>`).join('');
    };
    d.fillMaterials = fillSel;
    return d;
  }

  window.addLayer = function(){
    const idx = layers.length;
    const el = makeLayerEl(idx);
    layers.push(el);
    layersDiv.appendChild(el);
    if (materials.length) el.fillMaterials();
  }
  window.removeLayer = function(){
    const el = layers.pop();
    if (el) el.remove();
  }
  window.loadMaterials = async function(){
    try{
      const res = await fetch('/materials');
      const js = await res.json();
      if (js.ok){
        materials = js.materials;
        layers.forEach(el => el.fillMaterials && el.fillMaterials());
      }
    }catch(e){ console.warn(e); }
  }
  window.applyClimatePreset = function(){
    const sel = document.getElementById('climatePreset');
    const v = sel ? sel.value : '';
    if (v) document.getElementById('theta_e').value = v;
  }
  window.runAnalyze = async function(){
    const payloadLayers = layers.map(el => ({
      name: el.querySelector('.name').value,
      d: parseFloat(el.querySelector('.d').value || '0'),
      lambda_: parseFloat(el.querySelector('.lambda').value || '0'),
      mu: parseFloat(el.querySelector('.mu').value || '0'),
      rho: parseFloat(el.querySelector('.rho').value || '0'),
      xr_percent: parseFloat(el.querySelector('.xr').value || '0'),
      xmax_percent: parseFloat(el.querySelector('.xmax').value || '0'),
    })).filter(L => L.d > 0 && L.lambda_ > 0);
    if (!payloadLayers.length){ alert('Add at least one valid layer'); return; }
    const tk = parseFloat(document.getElementById('tk')?.value || '1440');
    const tu = parseFloat(document.getElementById('tu')?.value || '1440');
    const payload = {
      layers: payloadLayers,
      Rsi: parseFloat(document.getElementById('Rsi').value || '0.13'),
      Rse: parseFloat(document.getElementById('Rse').value || '0.04'),
      climate: {
        theta_i: parseFloat(document.getElementById('theta_i').value || '20'),
        phi_i: parseFloat(document.getElementById('phi_i').value || '65'),
        theta_e: parseFloat(document.getElementById('theta_e').value || '5'),
        phi_e: parseFloat(document.getElementById('phi_e').value || '90'),
      },
      tk_hours: tk,
      tu_hours: tu,
    };
    const res = await fetch('/analyze', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
    const js = await res.json();
    const out = document.getElementById('results');
    if (!js.ok){ out.textContent = 'Error: ' + js.error; return; }
    const r = js.result;
    out.textContent = `U=${r.U.toFixed(4)} W/m²K\n`+
      `ΣR=${r.R_total.toFixed(4)} m²K/W, q=${r.q.toFixed(3)} W/m²\n`+
      `Surface risk: ${r.surface.risk ? 'Yes' : 'No'} (θsi=${r.surface.theta_si.toFixed(2)}°C vs θs=${r.surface.theta_s.toFixed(2)}°C) | Ext: ${r.surface.risk_e ? 'Yes' : 'No'} (θse=${r.surface.theta_se.toFixed(2)}°C vs θs,e=${r.surface.theta_s_e.toFixed(2)}°C)\n`+
      `Wk_total=${r.Wk_total.toFixed(4)} kg/m² over tk=${tk.toFixed(0)}h, Drying capacity=${r.drying_capacity.toFixed(4)} kg/m² over tu=${tu.toFixed(0)}h → OK=${r.drying_ok ? 'Yes':'No'}`;
    const zones = r.zones || [];
    document.getElementById('zones').textContent = zones.length ? zones.map(z => `(${z.start_z.toFixed(3)} → ${z.end_z.toFixed(3)})`).join('\n') : '—';
    drawTemp(r.thickness_axis, r.theta_profile);
    drawVapor(r.vapor_axis, r.p_line, r.p_sat, r.zones, r.vapor_axis_final, r.p_final);
  }

  function linMap(v, v0,v1, p0,p1){ return p0 + (v - v0) * (p1 - p0) / (v1 - v0 || 1); }
  window.drawTemp = function(x, y){ const c=document.getElementById('chartTemp'); c.width=c.clientWidth; c.height=300; const ctx=c.getContext('2d'); ctx.clearRect(0,0,c.width,c.height); const w=c.width, h=c.height; const pad=40; const xmin=Math.min(...x), xmax=Math.max(...x); const ymin=Math.min(...y), ymax=Math.max(...y); ctx.strokeStyle='#444'; ctx.strokeRect(0,0,w,h); ctx.save(); ctx.translate(pad,pad); const iw=w-2*pad, ih=h-2*pad; ctx.fillStyle='#9ca3af'; ctx.font='12px sans-serif'; ctx.fillText(`${xmin.toFixed(2)} m`,0,ih+16); ctx.fillText(`${xmax.toFixed(2)} m`,iw-60,ih+16); ctx.fillText(`${ymin.toFixed(1)}°C`,-30,ih); ctx.fillText(`${ymax.toFixed(1)}°C`,-30,10); ctx.beginPath(); for(let i=0;i<x.length;i++){ const X=linMap(x[i], xmin,xmax, 0,iw); const Y=linMap(y[i], ymin,ymax, ih,0); if(i===0) ctx.moveTo(X,Y); else ctx.lineTo(X,Y);} ctx.strokeStyle='#60a5fa'; ctx.lineWidth=2; ctx.stroke(); ctx.restore(); }
  window.drawVapor = function(x, p, ps, zones, xf, pf){ const c=document.getElementById('chartVapor'); c.width=c.clientWidth; c.height=300; const ctx=c.getContext('2d'); ctx.clearRect(0,0,c.width,c.height); const w=c.width,h=c.height; const pad=40; const xmin=Math.min(...x), xmax=Math.max(...x); const all=[...p,...ps]; const ymin=Math.min(...all), ymax=Math.max(...all); ctx.strokeStyle='#444'; ctx.strokeRect(0,0,w,h); ctx.save(); ctx.translate(pad,pad); const iw=w-2*pad, ih=h-2*pad; ctx.fillStyle='#9ca3af'; ctx.font='12px sans-serif'; ctx.fillText(`${xmin.toFixed(2)}`,0,ih+16); ctx.fillText(`${xmax.toFixed(2)}`,iw-30,ih+16); ctx.fillText(`${(ymin/100).toFixed(0)} hPa`,-35,ih); ctx.fillText(`${(ymax/100).toFixed(0)} hPa`,-35,10); const plot = (xs, arr, color) => { ctx.beginPath(); for(let i=0;i<xs.length;i++){ const X=linMap(xs[i], xmin,xmax,0,iw); const Y=linMap(arr[i], ymin,ymax, ih,0); if(i===0) ctx.moveTo(X,Y); else ctx.lineTo(X,Y);} ctx.strokeStyle=color; ctx.lineWidth=2; ctx.stroke(); };
    if (zones && zones.length){ ctx.fillStyle='rgba(248,113,113,0.15)'; zones.forEach(z => { const X0=linMap(z.start_z, xmin,xmax,0,iw); const X1=linMap(z.end_z, xmin,xmax,0,iw); ctx.fillRect(X0,0, X1-X0, ih); }); }
    plot(x, ps, '#f87171');
    plot(x, p, '#34d399');
    if (xf && pf) plot(xf, pf, '#93c5fd');
    ctx.restore(); }

  // init
  window.addLayer();
})();
