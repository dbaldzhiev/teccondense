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
        <label>Thickness (cm)</label>
        <input type="number" step="0.1" class="d" value="10.0">
        <input type="range" min="0.5" max="50.0" step="0.1" value="10.0" class="dSlider">
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
    dSlider.addEventListener('input', () => { dInput.value = (+dSlider.value).toFixed(1); });
    dInput.addEventListener('input', () => { dSlider.value = dInput.value; });
    const sel = d.querySelector('.matSelect');
    sel.addEventListener('change', () => {
      const idx = parseInt(sel.value, 10);
      const m = Number.isNaN(idx) ? null : materials[idx];
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
      sel.innerHTML = '<option value="">—</option>' + materials.map((m,i) => `<option value="${i}">${m.name}</option>`).join('');
    };
    d.fillMaterials = fillSel;
    // Apply sensible defaults for first two layers
    // L1: 25 cm Brick, L2: 10 cm Mineral wool
    try{
      if (idx === 0){
        d.querySelector('.name').value = 'Brick';
        dInput.value = '25.0'; dSlider.value = '25.0';
        d.querySelector('.lambda').value = '0.790';
        d.querySelector('.mu').value = '7';
        d.querySelector('.rho').value = '1800';
        d.querySelector('.xr').value = '2.0';
        d.querySelector('.xmax').value = '14.0';
      } else if (idx === 1){
        d.querySelector('.name').value = 'Mineral wool';
        dInput.value = '10.0'; dSlider.value = '10.0';
        d.querySelector('.lambda').value = '0.040';
        d.querySelector('.mu').value = '1';
        d.querySelector('.rho').value = '40';
        d.querySelector('.xr').value = '5.0';
        d.querySelector('.xmax').value = '20.0';
      }
    }catch(_){/* ignore */}
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
  function num(v){ return parseFloat(String(v || '0').replace(',', '.')); }
  window.runAnalyze = async function(){
    const payloadLayers = layers.map(el => ({
      name: el.querySelector('.name').value,
      d: num(el.querySelector('.d').value) / 100.0, // cm → m
      lambda_: num(el.querySelector('.lambda').value),
      mu: num(el.querySelector('.mu').value),
      rho: num(el.querySelector('.rho').value),
      xr_percent: num(el.querySelector('.xr').value),
      xmax_percent: num(el.querySelector('.xmax').value),
    })).filter(L => L.d > 0 && L.lambda_ > 0);
    if (!payloadLayers.length){ alert('Add at least one valid layer'); return; }
    const tk = num(document.getElementById('tk')?.value || '1440');
    const tu = num(document.getElementById('tu')?.value || '1440');
    const payload = {
      layers: payloadLayers,
      Rsi: num(document.getElementById('Rsi').value || '0.13'),
      Rse: num(document.getElementById('Rse').value || '0.04'),
      climate: {
        theta_i: num(document.getElementById('theta_i').value || '20'),
        phi_i: num(document.getElementById('phi_i').value || '65'),
        theta_e: num(document.getElementById('theta_e').value || '5'),
        phi_e: num(document.getElementById('phi_e').value || '90'),
      },
      tk_hours: tk,
      tu_hours: tu,
    };
    const res = await fetch('/analyze', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
    const js = await res.json();
    const out = document.getElementById('results');
    if (!js.ok){ out.textContent = 'Error: ' + js.error; return; }
    const r = js.result;
    const surfacePass = !r.surface?.risk;
const internalCond = !!r.internal_condensation;
const dryingPass = !!r.drying_ok;
const badge = (label, pass) => `<span class=\"badge ${pass ? 'pass':'fail'}\">${label}: ${pass ? 'OK':'Fail'}</span>`;
const summary = `
  <div class=\"badge-row\">
    ${badge('Surface', surfacePass)}
    ${badge('Internal Condensation', !internalCond)}
    ${badge('Drying', dryingPass)}
  </div>`;
const key = `
  <div class=\"metrics\">
    <div><div class=\"k\">U</div><div class=\"v\">${r.U.toFixed(4)} W/m²·K</div></div>
    <div><div class=\"k\">ΣR</div><div class=\"v\">${r.R_total.toFixed(4)} m²·K/W</div></div>
    <div><div class=\"k\">q</div><div class=\"v\">${r.q.toFixed(3)} W/m²</div></div>
    <div><div class=\"k\">pᵢ / pₑ</div><div class=\"v\">${(r.p_i||0).toFixed(0)} / ${(r.p_e||0).toFixed(0)} Pa</div></div>
    <div><div class=\"k\">Wk</div><div class=\"v\">${r.Wk_total.toFixed(4)} kg/m² (tk=${tk.toFixed(0)} h)</div></div>
    <div><div class=\"k\">Drying</div><div class=\"v\">${r.drying_capacity.toFixed(4)} kg/m² (tu=${tu.toFixed(0)} h)</div></div>
  </div>`;
const surf = r.surface || {};
const surfDet = `
  <div class=\"section\">
    <div class=\"section-title\">Surface Check</div>
    <div class=\"mini-grid\">
      <div>θsi</div><div>${(surf.theta_si||0).toFixed(2)} °C</div>
      <div>θs</div><div>${(surf.theta_s||0).toFixed(2)} °C</div>
      <div>θse</div><div>${(surf.theta_se||0).toFixed(2)} °C</div>
      <div>θs,e</div><div>${(surf.theta_s_e||0).toFixed(2)} °C</div>
    </div>
  </div>`;
const mlim = Array.isArray(r.moisture_limits) ? r.moisture_limits : [];
const moisture = mlim.length ? (
  `<div class=\"section\"><div class=\"section-title\">Moisture Limits</div>
    <table class=\"table\">
      <thead><tr><th>Layer</th><th>Δx_dif (%)</th><th>xʹᵤₖ (%)</th><th>x_max (%)</th><th>Status</th></tr></thead>
      <tbody>
        ${mlim.map((row,i)=>{
          const wkL = (r.Wk_layers||[]).find(xx => parseInt(xx.index)===i);
          const dx = wkL ? wkL.delta_x_percent : 0;
          const ok = !!row.ok;
          return `<tr><td>${r.layers?.[i]?.name||('L'+(i+1))}</td><td>${dx.toFixed(3)}</td><td>${row.x_uk_prime.toFixed(2)}</td><td>${row.x_max.toFixed(2)}</td><td>${ok? 'OK':'Exceeds'}</td></tr>`;
        }).join('')}
      </tbody>
    </table>
  </div>`
) : '';
out.innerHTML = summary + key + surfDet + moisture;const zones = r.zones || [];
const zonesHtml = zones.length ? (
  `<table class=\"table\"><thead><tr><th>z start</th><th>z end</th><th>x start</th><th>x end</th></tr></thead><tbody>
    ${zones.map(z => {
      const xa = mapZtoX(z.start_z, r.vapor_axis, r.thickness_axis);
      const xb = mapZtoX(z.end_z, r.vapor_axis, r.thickness_axis);
      return `<tr><td>${z.start_z.toFixed(3)}</td><td>${z.end_z.toFixed(3)}</td><td>${xa.toFixed(3)}</td><td>${xb.toFixed(3)}</td></tr>`;
    }).join('')}
  </tbody></table>`
) : '-';
document.getElementById('zones').innerHTML = zonesHtml;drawAssembly(r.layers || [], r.thickness_axis, r.theta_profile, r.zones || [], r.vapor_axis);
    drawTemp(r.thickness_axis, r.theta_profile);
    drawVapor(r.vapor_axis, r.p_line, r.p_sat, r.zones, r.vapor_axis_final, r.p_final);
  }

  function linMap(v, v0,v1, p0,p1){ return p0 + (v - v0) * (p1 - p0) / (v1 - v0 || 1); }
  function clamp(v, a, b){ return Math.max(a, Math.min(b, v)); }
  function hashColor(str){
    let h = 0; for (let i = 0; i < str.length; i++){ h = (h*31 + str.charCodeAt(i))|0; }
    const r = 160 + (h & 0x3F); const g = 140 + ((h>>6) & 0x3F); const b = 120 + ((h>>12) & 0x3F);
    return `rgba(${r%255}, ${g%255}, ${b%255}, 0.25)`;
  }
  function interpAt(xq, xs, ys){
    if (!xs || xs.length === 0) return 0;
    if (xq <= xs[0]) return ys[0];
    if (xq >= xs[xs.length-1]) return ys[ys.length-1];
    for (let i=1;i<xs.length;i++){
      if (xq <= xs[i]){
        const x0=xs[i-1], x1=xs[i]; const y0=ys[i-1], y1=ys[i];
        const t=(xq-x0)/((x1-x0)||1); return y0 + t*(y1-y0);
      }
    }
    return ys[ys.length-1];
  }
  function mapZtoX(z, zAxis, xAxis){
    if (!zAxis || !xAxis || zAxis.length !== xAxis.length) return 0;
    if (z <= zAxis[0]) return xAxis[0];
    if (z >= zAxis[zAxis.length-1]) return xAxis[xAxis.length-1];
    for (let i=1;i<zAxis.length;i++){
      if (z <= zAxis[i]){
        const z0=zAxis[i-1], z1=zAxis[i]; const x0=xAxis[i-1], x1=xAxis[i];
        const t=(z - z0)/((z1 - z0)||1); return x0 + t*(x1 - x0);
      }
    }
    return xAxis[xAxis.length-1];
  }
  window.drawTemp = function(x, y){ const c=document.getElementById('chartTemp'); c.width=c.clientWidth; c.height=300; const ctx=c.getContext('2d'); ctx.clearRect(0,0,c.width,c.height); const w=c.width, h=c.height; const pad=40; const xmin=Math.min(...x), xmax=Math.max(...x); const ymin=Math.min(...y), ymax=Math.max(...y); ctx.strokeStyle='#444'; ctx.strokeRect(0,0,w,h); ctx.save(); ctx.translate(pad,pad); const iw=w-2*pad, ih=h-2*pad; ctx.fillStyle='#9ca3af'; ctx.font='12px sans-serif'; ctx.fillText(`${xmin.toFixed(2)} m`,0,ih+16); ctx.fillText(`${xmax.toFixed(2)} m`,iw-60,ih+16); ctx.fillText(`${ymin.toFixed(1)}°C`,-30,ih); ctx.fillText(`${ymax.toFixed(1)}°C`,-30,10); ctx.beginPath(); for(let i=0;i<x.length;i++){ const X=linMap(x[i], xmin,xmax, 0,iw); const Y=linMap(y[i], ymin,ymax, ih,0); if(i===0) ctx.moveTo(X,Y); else ctx.lineTo(X,Y);} ctx.strokeStyle='#60a5fa'; ctx.lineWidth=2; ctx.stroke(); ctx.restore(); }
  window.drawVapor = function(x, p, ps, zones, xf, pf){ const c=document.getElementById('chartVapor'); c.width=c.clientWidth; c.height=300; const ctx=c.getContext('2d'); ctx.clearRect(0,0,c.width,c.height); const w=c.width,h=c.height; const pad=44; const xmin=Math.min(...x), xmax=Math.max(...x); const all=[...p,...ps]; const ymin=Math.min(...all), ymax=Math.max(...all); ctx.strokeStyle='#444'; ctx.strokeRect(0,0,w,h); ctx.save(); ctx.translate(pad,pad); const iw=w-2*pad, ih=h-2*pad; ctx.fillStyle='#9ca3af'; ctx.font='12px sans-serif'; ctx.fillText(`${xmin.toFixed(2)} Σz`,0,ih+16); ctx.fillText(`${xmax.toFixed(2)} Σz`,iw-60,ih+16); ctx.fillText(`${(ymin/100).toFixed(0)} hPa`,-36,ih); ctx.fillText(`${(ymax/100).toFixed(0)} hPa`,-36,10);
    // Layer interface lines
    ctx.strokeStyle='#374151'; ctx.lineWidth=1; for(let i=0;i<x.length;i++){ const X=linMap(x[i], xmin,xmax,0,iw); ctx.beginPath(); ctx.moveTo(X,0); ctx.lineTo(X,ih); ctx.stroke(); }
    // Condensation zones shading
    if (zones && zones.length){ ctx.fillStyle='rgba(248,113,113,0.15)'; zones.forEach(z => { const X0=linMap(z.start_z, xmin,xmax,0,iw); const X1=linMap(z.end_z, xmin,xmax,0,iw); ctx.fillRect(Math.min(X0,X1),0, Math.abs(X1-X0), ih); }); }
    // Curves
    const plot = (xs, arr, color) => { ctx.beginPath(); for(let i=0;i<xs.length;i++){ const X=linMap(xs[i], xmin,xmax,0,iw); const Y=linMap(arr[i], ymin,ymax, ih,0); if(i===0) ctx.moveTo(X,Y); else ctx.lineTo(X,Y);} ctx.strokeStyle=color; ctx.lineWidth=2; ctx.stroke(); };
    plot(x, ps, '#f87171'); // p_sat
    plot(x, p, '#34d399'); // p linear
    if (xf && pf) plot(xf, pf, '#93c5fd'); // Glaser limited profile
    // Crossing markers at zone edges
    ctx.fillStyle='#ef4444'; ctx.strokeStyle='#ef4444'; zones && zones.forEach(z => {
      const zA = z.start_z, zB = z.end_z;
      const yA = interpAt(zA, x, ps); const yB = interpAt(zB, x, ps);
      const XA=linMap(zA, xmin,xmax,0,iw), YA=linMap(yA, ymin,ymax, ih,0);
      const XB=linMap(zB, xmin,xmax,0,iw), YB=linMap(yB, ymin,ymax, ih,0);
      ctx.beginPath(); ctx.arc(XA, YA, 3, 0, Math.PI*2); ctx.fill();
      ctx.beginPath(); ctx.arc(XB, YB, 3, 0, Math.PI*2); ctx.fill();
    });
    ctx.restore();
    // Tooltip
    const tipId = 'vaporTip'; let tip = document.getElementById(tipId);
    if (!tip){ tip = document.createElement('div'); tip.id = tipId; tip.style.position='fixed'; tip.style.pointerEvents='none'; tip.style.background='rgba(17,24,39,0.95)'; tip.style.border='1px solid #374151'; tip.style.color='#e5e7eb'; tip.style.padding='6px 8px'; tip.style.borderRadius='6px'; tip.style.font='12px sans-serif'; tip.style.display='none'; document.body.appendChild(tip); }
    c.onmousemove = (ev) => {
      const rect = c.getBoundingClientRect(); const px = ev.clientX - rect.left; const py = ev.clientY - rect.top; if (px < pad || px > w-pad || py < pad || py > h-pad){ tip.style.display='none'; return; }
      const zx = linMap(px - pad, 0, w-2*pad, xmin, xmax);
      const pL = interpAt(zx, x, p); const pS = interpAt(zx, x, ps); const dP = pL - pS;
      tip.textContent = `Σz=${zx.toFixed(3)} | p=${pL.toFixed(0)} Pa, p_sat=${pS.toFixed(0)} Pa, Δ=${dP.toFixed(0)} Pa`;
      tip.style.left = `${ev.clientX + 12}px`; tip.style.top = `${ev.clientY + 12}px`; tip.style.display='block';
    };
    c.onmouseleave = () => { const t=document.getElementById(tipId); if (t) t.style.display='none'; };
  }

  window.drawAssembly = function(layers, xAxis, temps, zones, zAxis){
    const c = document.getElementById('chartAssembly'); if (!c) return; c.width=c.clientWidth; c.height=300; const ctx=c.getContext('2d'); ctx.clearRect(0,0,c.width,c.height);
    const w=c.width, h=c.height; const pad=44; const xmin=Math.min(...xAxis), xmax=Math.max(...xAxis); const ymin=Math.min(...temps), ymax=Math.max(...temps);
    ctx.strokeStyle='#444'; ctx.strokeRect(0,0,w,h); ctx.save(); ctx.translate(pad,pad); const iw=w-2*pad, ih=h-2*pad;
    // Draw layer rectangles across height
    let x0 = xAxis[0] || 0; for (let i=1;i<xAxis.length;i++){
      const x1 = xAxis[i]; const X0=linMap(x0, xmin,xmax, 0,iw); const X1=linMap(x1, xmin,xmax, 0,iw);
      const name = layers[i-1]?.name || `L${i}`; ctx.fillStyle = hashColor(name);
      ctx.fillRect(X0, 0, (X1-X0), ih);
      ctx.strokeStyle='#1f2937'; ctx.strokeRect(X0, 0, (X1-X0), ih);
      // Label
      ctx.fillStyle='#e5e7eb'; ctx.font='12px sans-serif'; const label = `${name} (${((x1-x0)*100).toFixed(1)} cm)`; ctx.fillText(label, X0+6, 16);
      x0 = x1;
    }
    // Interfaces
    ctx.strokeStyle='#374151'; for (let i=0;i<xAxis.length;i++){ const X=linMap(xAxis[i], xmin,xmax,0,iw); ctx.beginPath(); ctx.moveTo(X,0); ctx.lineTo(X,ih); ctx.stroke(); }
    // Condensation zones mapped from z to x
    if (zones && zones.length){ ctx.fillStyle='rgba(248,113,113,0.25)'; zones.forEach(z => { const xA = mapZtoX(z.start_z, zAxis, xAxis); const xB = mapZtoX(z.end_z, zAxis, xAxis); const XA=linMap(xA, xmin,xmax,0,iw), XB=linMap(xB, xmin,xmax,0,iw); ctx.fillRect(Math.min(XA,XB), 0, Math.abs(XB-XA), ih); }); }
    // Temperature line overlay
    ctx.beginPath(); for(let i=0;i<xAxis.length;i++){ const X=linMap(xAxis[i], xmin,xmax,0,iw); const Y=linMap(temps[i], ymin,ymax, ih,0); if(i===0) ctx.moveTo(X,Y); else ctx.lineTo(X,Y);} ctx.strokeStyle='#60a5fa'; ctx.lineWidth=2; ctx.stroke();
    // Axes labels
    ctx.fillStyle='#9ca3af'; ctx.font='12px sans-serif'; ctx.fillText(`${xmin.toFixed(2)} m`,0,ih+16); ctx.fillText(`${xmax.toFixed(2)} m`,iw-60,ih+16); ctx.fillText(`${ymin.toFixed(1)}°C`,-30,ih); ctx.fillText(`${ymax.toFixed(1)}°C`,-30,10);
    ctx.restore();
  }

  // init
  window.addLayer();
})();







