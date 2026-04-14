// ============================================================
// PHYSICS ENGINE (JS port of simulation_engine.py)
// ============================================================
const C_LIGHT = 3e8;
const EPS0 = 8.85e-12;
const MU0 = 4 * Math.PI * 1e-7;

function parseVal(s) {
  if (typeof s === 'number') return s;
  s = s.trim().toLowerCase();
  if (s === 'inf' || s === 'infinity') return Infinity;
  return parseFloat(s);
}

function calcVelocity(eps_r, mu_r) {
  return C_LIGHT / Math.sqrt(eps_r * mu_r);
}

function calcImpedance(eps_r, mu_r, sigma, freq) {
  const eps = eps_r * EPS0;
  const mu = mu_r * MU0;
  if (sigma === 0) return { re: Math.sqrt(mu / eps), im: 0 };
  const omega = 2 * Math.PI * freq;
  // Z = sqrt(j*omega*mu / (sigma + j*omega*eps))
  // numerator: j*omega*mu => (0, omega*mu)
  // denom: sigma + j*omega*eps => (sigma, omega*eps)
  const d_re = sigma, d_im = omega * eps;
  const n_re = 0, n_im = omega * mu;
  // (n_re + j*n_im)/(d_re + j*d_im) = ((n_re*d_re + n_im*d_im) + j*(n_im*d_re - n_re*d_im)) / (d^2)
  const d2 = d_re * d_re + d_im * d_im;
  const q_re = (n_re * d_re + n_im * d_im) / d2;
  const q_im = (n_im * d_re - n_re * d_im) / d2;
  // sqrt of complex
  const r = Math.sqrt(q_re * q_re + q_im * q_im);
  const arg = Math.atan2(q_im, q_re);
  return { re: Math.sqrt(r) * Math.cos(arg / 2), im: Math.sqrt(r) * Math.sin(arg / 2) };
}

function calcReflectionCoeff(Z1, Z2) {
  // R = (Z2-Z1)/(Z2+Z1), real part only
  const dre = Z2.re - Z1.re, dim = Z2.im - Z1.im;
  const sre = Z2.re + Z1.re, sim = Z2.im + Z1.im;
  const s2 = sre * sre + sim * sim;
  if (s2 === 0) return 0;
  return (dre * sre + dim * sim) / s2;
}

function calcAttenuation(sigma, eps_r, mu_r, freq) {
  const eps = eps_r * EPS0;
  const mu = mu_r * MU0;
  if (eps === 0) return 0;
  return (sigma / 2.0) * Math.sqrt(mu / eps);
}

function computeLayerProperties(layers, freq) {
  const results = [];
  let cumTime = 0, cumDepth = 0;
  for (let i = 0; i < layers.length; i++) {
    const l = layers[i];
    const vel = calcVelocity(l.eps_r, l.mu_r);
    const Z = calcImpedance(l.eps_r, l.mu_r, l.sigma, freq);
    const wl = freq > 0 ? vel / freq : 0;
    const alpha = calcAttenuation(l.sigma, l.eps_r, l.mu_r, freq);
    let R = 0;
    if (i > 0) R = calcReflectionCoeff(results[i - 1].Z, Z);
    const t_layer = isFinite(l.thickness) ? l.thickness / vel : 0;
    results.push({
      vel, Z, wl, alpha, R,
      t_layer, cumTime, cumDepth
    });
    if (i === 0 && !isFinite(l.thickness)) {
      // first air layer
    } else {
      cumTime += t_layer;
      cumDepth += isFinite(l.thickness) ? l.thickness : 0;
    }
  }
  return results;
}

function computeObjectProperties(obj, layers, layerProps, freq) {
  if (!obj || obj.layerIdx < 0 || obj.layerIdx >= layers.length) return null;
  const hostIdx = obj.layerIdx;
  const hostProps = layerProps[hostIdx];
  const depthInLayer = Math.max(0, obj.depth - hostProps.cumDepth);
  const t_inside = depthInLayer / hostProps.vel;
  const t_to_obj = hostProps.cumTime + t_inside;
  const ref_time = 2 * t_to_obj;

  const Z_host = hostProps.Z;
  const Z_obj = calcImpedance(obj.eps_r, obj.mu_r, obj.sigma, freq);
  const R_obj = calcReflectionCoeff(Z_host, Z_obj);

  let total_att = 0;
  for (let i = 0; i < hostIdx; i++) {
    if (i === 0 && !isFinite(layers[i].thickness)) continue;
    total_att += layerProps[i].alpha * layers[i].thickness;
  }
  total_att += hostProps.alpha * depthInLayer;
  const recv_amp = R_obj * Math.exp(-2 * total_att);

  return {
    abs_depth: obj.depth,
    ref_time,
    R_obj,
    recv_amp,
    host_vel: hostProps.vel,
    eff_vel: t_to_obj > 0 ? obj.depth / t_to_obj : hostProps.vel
  };
}

function collectEvents(layerProps, layers, objRes) {
  const events = [];

  // Layer reflections: amplitude = actual reflection coefficient * attenuation
  // Keep natural scale — no artificial boost so layer spikes stay smaller than object peak
  for (let i = 1; i < layerProps.length; i++) {
    const lr = layerProps[i];
    if (Math.abs(lr.R) < 1e-6) continue;
    let att = 0;
    for (let j = 0; j < i; j++) {
      if (j === 0 && !isFinite(layers[j].thickness)) continue;
      att += layerProps[j].alpha * layers[j].thickness;
    }
    // Natural amplitude — layer boundary spikes are smaller, realistic
    const amp = lr.R * Math.exp(-2 * att);
    events.push({ time: 2 * lr.cumTime, amp, type: 'layer' });
  }

  if (objRes) {
    // Object amplitude reflects material type:
    // Metal: high reflection (R near ±1), Void: moderate, Plastic: small, Water: moderate
    // recv_amp already encodes |R_obj| * attenuation, so scale relative to that
    // Boost so object stands out above layer events but respects material contrast
    const objAmp = objRes.recv_amp * 2.5;
    events.push({ time: objRes.ref_time, amp: objAmp, type: 'object' });
  }
  return events;
}

function rickerPulse(t_arr, ev_time, amp, freq) {
  return t_arr.map(t => {
    const tau = t * 1e-9 - ev_time;
    const pft = Math.PI * freq * tau;
    return amp * (1 - 2 * pft * pft) * Math.exp(-pft * pft);
  });
}

function gaussSmooth(arr, sigma) {
  const r = Math.ceil(3 * sigma);
  const kernel = [];
  let sum = 0;
  for (let x = -r; x <= r; x++) {
    const v = Math.exp(-x * x / (2 * sigma * sigma));
    kernel.push(v); sum += v;
  }
  const k = kernel.map(v => v / sum);
  const out = new Float64Array(arr.length);
  for (let i = 0; i < arr.length; i++) {
    let val = 0;
    for (let j = 0; j < k.length; j++) {
      const idx = i + j - r;
      if (idx >= 0 && idx < arr.length) val += arr[idx] * k[j];
    }
    out[i] = val;
  }
  return out;
}

function generateAScan(t_ns, events, freq, noiseLevel) {
  const scan = new Float64Array(t_ns.length);
  for (const ev of events) {
    const p = rickerPulse(t_ns, ev.time, ev.amp, freq);
    for (let i = 0; i < scan.length; i++) scan[i] += p[i];
  }
  // Low noise — just enough texture, not enough to bury small layer spikes
  const maxS = Math.max(...scan.map(Math.abs)) || 1e-6;
  const ns = noiseLevel * 0.4 * maxS;  // reduced noise so layer events are visible
  for (let i = 0; i < scan.length; i++) {
    scan[i] += (Math.random() - 0.5) * 2 * ns;
  }
  // Very light smoothing to preserve spike sharpness
  const smoothed = gaussSmooth(scan, 0.3);
  const maxA = Math.max(...smoothed.map(Math.abs));
  if (maxA > 0) for (let i = 0; i < smoothed.length; i++) smoothed[i] /= maxA;
  return smoothed;
}

function generateBScan(t_ns, events, objRes, freq, noiseLevel) {
  const numTraces = 80;
  const bscan = [];
  const center = numTraces / 2;
  const step = 0.02;

  // Separate layer events (horizontal) from object event (hyperbolic per-trace)
  const layerEvts = events.filter(e => e.type === 'layer');

  for (let i = 0; i < numTraces; i++) {
    const x_dist = (i - center) * step;

    // Layer events: SAME time for every trace → horizontal lines in B-scan
    const traceEvts = layerEvts.map(e => ({ ...e }));

    // Object event: hyperbolic time shift per trace position
    if (objRes) {
      const d = objRes.abs_depth;
      const v = objRes.eff_vel;
      const t_hyp = 2 * Math.sqrt(d * d + x_dist * x_dist) / v;
      // Beam pattern: signal strongest directly below, fades at sides
      const ang_att = Math.exp(-(x_dist * x_dist) / 0.25);
      const amp = objRes.recv_amp * ang_att * 2.5;
      traceEvts.push({ time: t_hyp, amp, type: 'object' });
    }

    bscan.push(generateAScan(t_ns, traceEvts, freq, noiseLevel));
  }

  // Minimal horizontal smoothing — just enough to remove pixel noise,
  // but NOT so much that horizontal layer lines get blurred away
  const result = bscan.map(r => [...r]);
  for (let row = 0; row < t_ns.length; row++) {
    const rowData = bscan.map(col => col[row]);
    const smoothed = gaussSmooth(rowData, 0.3);
    for (let col = 0; col < numTraces; col++) result[col][row] = smoothed[col];
  }

  // Normalize
  let maxB = 0;
  for (const col of result) for (const v of col) maxB = Math.max(maxB, Math.abs(v));
  if (maxB > 0) for (const col of result) for (let i = 0; i < col.length; i++) col[i] /= maxB;
  return result;
}

function generateCScan(bscan) {
  const numTraces = bscan.length;
  const energy = bscan.map(col => Math.max(...col.map(Math.abs)));
  const peakVal = Math.max(...energy);
  const avgBg   = energy.reduce((a, b) => a + b, 0) / numTraces;
  const cscan   = [];
  const cx      = numTraces / 2; // always centre X
  const cy      = numTraces / 2; // always centre Y

  for (let y = 0; y < numTraces; y++) {
    cscan.push([]);
    for (let x = 0; x < numTraces; x++) {
      const dist2 = (x - cx) * (x - cx) + (y - cy) * (y - cy);
      const v = peakVal * Math.exp(-dist2 / 18.0) + 0.04 * avgBg;
      cscan[y].push(v);
    }
  }
  let maxC = 0;
  for (const row of cscan) for (const v of row) maxC = Math.max(maxC, v);
  if (maxC > 0) for (const row of cscan) for (let i = 0; i < row.length; i++) row[i] /= maxC;
  return cscan;
}

function calcSNR(ascan, noiseLevel) {
  const sigPow = Math.max(...ascan.map(Math.abs)) ** 2;
  const noisePow = (noiseLevel * sigPow) ** 2 || 1e-12;
  return Math.round(10 * Math.log10(sigPow / noisePow) * 10) / 10;
}

// ============================================================
// LAYER MANAGEMENT
// ============================================================
let layerCounter = 0;
const layers = [];

function addLayer(name, thick, eps, mu, sig, insertIdx = -1) {
  const id = ++layerCounter;
  const card = document.createElement('div');
  card.className = 'layer-card';
  card.dataset.id = id;

  const displayIdx = insertIdx === -1 ? layers.length + 1 : insertIdx + 1;

  card.innerHTML = `
    <div class="layer-header">
      <span class="layer-title" data-title>▶ STRATA ${displayIdx}</span>
      <div class="layer-btns">
        <button class="btn btn-sm" onclick="insertAbove(${id})">↑ Above</button>
        <button class="btn btn-sm" onclick="insertBelow(${id})">↓ Below</button>
        <button class="btn btn-sm" style="color:var(--red);border-color:var(--red);" onclick="removeLayer(${id})">✕</button>
      </div>
    </div>
    <div class="form-row"><label>Label:</label><input type="text" data-field="name" value="${name}"></div>
    <div class="form-row"><label>Depth (m):</label><input type="text" data-field="thick" value="${thick}"></div>
    <div class="form-row"><label>εr:</label><input type="text" data-field="eps" value="${eps}"></div>
    <div class="form-row"><label>σ:</label><input type="text" data-field="sig" value="${sig}"></div>
  `;

  const layerData = { id, card };

  const container = document.getElementById('layers-container');
  if (insertIdx === -1 || insertIdx >= layers.length) {
    container.appendChild(card);
    layers.push(layerData);
  } else {
    const refCard = layers[insertIdx].card;
    container.insertBefore(card, refCard);
    layers.splice(insertIdx, 0, layerData);
  }

  rebuildLayerIndices();
  document.getElementById('cb-presets').value = 'custom';
}

function removeLastLayer() {
  if (layers.length <= 1) return;
  const ld = layers.pop();
  ld.card.remove();
  rebuildLayerIndices();
}

function removeLayer(id) {
  if (layers.length <= 1) return;
  const idx = layers.findIndex(l => l.id === id);
  if (idx === -1) return;
  layers[idx].card.remove();
  layers.splice(idx, 1);
  rebuildLayerIndices();
}

function insertAbove(id) {
  const idx = layers.findIndex(l => l.id === id);
  if (idx !== -1) addLayer('New Stratum', '0.2', '4', '1', '0.01', idx);
}

function insertBelow(id) {
  const idx = layers.findIndex(l => l.id === id);
  if (idx !== -1) addLayer('New Stratum', '0.2', '4', '1', '0.01', idx + 1);
}

function rebuildLayerIndices() {
  layers.forEach((l, i) => {
    const t = l.card.querySelector('[data-title]');
    if (t) t.textContent = `▶ STRATA ${i + 1}`;
  });
  updateObjLayerCombo();
}

function getLayerData(ld) {
  const get = f => ld.card.querySelector(`[data-field="${f}"]`).value;
  return {
    name: get('name'),
    thickness: parseVal(get('thick')),
    eps_r: parseVal(get('eps')) || 1,
    mu_r: 1.0,
    sigma: parseVal(get('sig')) || 0
  };
}

function updateObjLayerCombo() {
  const sel = document.getElementById('cb-obj-layer');
  const curr = sel.value;
  sel.innerHTML = '';
  layers.forEach((ld, i) => {
    const name = ld.card.querySelector('[data-field="name"]').value;
    const opt = document.createElement('option');
    opt.value = i;
    opt.textContent = `Strata ${i + 1}: ${name}`;
    sel.appendChild(opt);
  });
  if (curr !== '' && curr < layers.length) sel.value = curr;
}

function clearLayers() {
  document.getElementById('layers-container').innerHTML = '';
  layers.length = 0;
}

// ============================================================
// PRESETS
// ============================================================
function onTargetTypeChanged() {
  const t = document.getElementById('cb-obj-type').value;
  if (t.includes('Metal')) {
    document.getElementById('le-obj-eps').value = '1.0';
    document.getElementById('le-obj-sig').value = '1e7';
    document.getElementById('le-obj-mu').value = '100.0';
  } else if (t.includes('Plastic')) {
    document.getElementById('le-obj-eps').value = '3.0';
    document.getElementById('le-obj-sig').value = '0.0';
    document.getElementById('le-obj-mu').value = '1.0';
  } else if (t.includes('Void')) {
    document.getElementById('le-obj-eps').value = '1.0';
    document.getElementById('le-obj-sig').value = '0.0';
    document.getElementById('le-obj-mu').value = '1.0';
  } else if (t.includes('Water')) {
    document.getElementById('le-obj-eps').value = '80.0';
    document.getElementById('le-obj-sig').value = '0.5';
    document.getElementById('le-obj-mu').value = '1.0';
  }
}

document.getElementById('cb-presets').addEventListener('change', function () {
  loadPreset(this.value);
  if (this.value !== 'custom') runSimulation();
});

function setObjType(idx) {
  document.getElementById('cb-obj-type').selectedIndex = idx;
  onTargetTypeChanged();
}

function loadPreset(preset) {
  clearLayers();
  if (preset === 'road') {
    document.getElementById('le-frequency').value = '2e9';
    addLayer('Atmos (Air)', 'inf', '1', '1', '0');
    addLayer('Asphalt Binder', '0.08', '4.5', '1', '0.01');
    addLayer('Granular Base', '0.20', '6.5', '1', '0.02');
    addLayer('Subgrade Soil', 'inf', '12', '1', '0.05');
    setObjType(2); // Void
    document.getElementById('le-obj-radius').value = '0.03';
    document.getElementById('le-obj-depth').value = '0.05';
    document.getElementById('cb-obj-layer').value = '1';
    document.getElementById('le-obj-eps').value = '1.0';
    document.getElementById('le-obj-sig').value = '0.0';
  } else if (preset === 'utility') {
    document.getElementById('le-frequency').value = '4e8';
    addLayer('Atmos (Air)', 'inf', '1', '1', '0');
    addLayer('Dry Topsoil', '0.50', '4', '1', '0.001');
    addLayer('Saturated Clay', 'inf', '15', '1', '0.05');
    setObjType(0); // Metal
    document.getElementById('le-obj-radius').value = '0.1';
    document.getElementById('le-obj-depth').value = '0.3';
    document.getElementById('cb-obj-layer').value = '1';
    document.getElementById('le-obj-sig').value = '1e7';
    document.getElementById('le-obj-eps').value = '1.0';
    document.getElementById('le-obj-mu').value = '100.0';
  } else if (preset === 'landmine') {
    document.getElementById('le-frequency').value = '1e9';
    addLayer('Atmos (Air)', 'inf', '1', '1', '0');
    addLayer('Desert Sand', 'inf', '3.0', '1', '0.0001');
    setObjType(1); // Plastic
    document.getElementById('le-obj-radius').value = '0.05';
    document.getElementById('le-obj-depth').value = '0.1';
    document.getElementById('cb-obj-layer').value = '1';
    document.getElementById('le-obj-eps').value = '3.2';
    document.getElementById('le-obj-sig').value = '0.0';
    document.getElementById('le-obj-mu').value = '1.0';
  }
}

// ============================================================
// CHART RENDERING
// ============================================================
let ascanChart = null;
let lastSimResults = null;

function renderAScan(t_ns, ascan, freq, objRes, velocity) {
  const canvas = document.getElementById('ascan-canvas');
  const ctx = canvas.getContext('2d');

  if (ascanChart) { ascanChart.destroy(); ascanChart = null; }

  // Find peak near object reflection
  let peakIdx = 0;
  if (objRes && objRes.ref_time > 0) {
    const targetNs = objRes.ref_time * 1e9;
    let nearIdx = 0, minD = Infinity;
    for (let i = 0; i < t_ns.length; i++) {
      const d = Math.abs(t_ns[i] - targetNs);
      if (d < minD) { minD = d; nearIdx = i; }
    }
    const start = Math.max(0, nearIdx - 15), end = Math.min(ascan.length, nearIdx + 15);
    let localMax = 0;
    for (let i = start; i < end; i++) if (Math.abs(ascan[i]) > localMax) { localMax = Math.abs(ascan[i]); peakIdx = i; }
  } else {
    let mx = 0;
    for (let i = 0; i < ascan.length; i++) if (Math.abs(ascan[i]) > mx) { mx = Math.abs(ascan[i]); peakIdx = i; }
  }

  const peakT = t_ns[peakIdx];
  const peakA = ascan[peakIdx];
  const estDepth = (velocity * peakT * 1e-9) / 2.0;

  const pointData = t_ns.map((t, i) => ({ x: t, y: ascan[i] }));

  ascanChart = new Chart(ctx, {
    type: 'line',
    data: {
      datasets: [{
        data: pointData,
        borderColor: '#00FF00',
        borderWidth: 1.5,
        pointRadius: 0,
        tension: 0.2,
        fill: false
      }, {
        data: [{ x: peakT, y: peakA }],
        borderColor: 'red',
        backgroundColor: 'red',
        pointRadius: 6,
        pointStyle: 'circle',
        showLine: false,
        label: `Depth=${estDepth.toFixed(3)}m (T=${peakT.toFixed(1)}ns)`
      }]
    },
    options: {
      animation: false,
      responsive: true,
      maintainAspectRatio: false,
      layout: { padding: { top: 8, right: 16, bottom: 4, left: 4 } },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => ctx.datasetIndex === 1 ? `Depth: ${estDepth.toFixed(3)}m  T: ${peakT.toFixed(1)}ns` : null
          }
        },
        annotation: {}
      },
      scales: {
        x: {
          type: 'linear',
          min: t_ns[0],
          max: t_ns[t_ns.length - 1],
          title: { display: true, text: 'Time (ns)', color: '#A0AEC0', font: { size: 14, family: 'Poppins' }, padding: { top: 4 } },
          grid: { color: '#003300' },
          ticks: { color: '#E0E0E0', font: { size: 13, family: 'Poppins' }, maxTicksLimit: 8, maxRotation: 0 }
        },
        y: {
          min: -1.6,
          max: 1.6,
          title: { display: true, text: 'Amplitude', color: '#A0AEC0', font: { size: 14, family: 'Poppins' }, padding: { bottom: 4 } },
          grid: { color: '#1F2937' },
          ticks: { color: '#E0E0E0', font: { size: 13, family: 'Poppins' }, maxTicksLimit: 6 }
        }
      },
      backgroundColor: '#0B0F19'
    },
    plugins: [{
      id: 'bgPlugin',
      beforeDraw(chart) {
        chart.ctx.save();
        chart.ctx.fillStyle = '#0B0F19';
        chart.ctx.fillRect(0, 0, chart.width, chart.height);
        chart.ctx.restore();
      }
    }, {
      id: 'peakLabel',
      afterDatasetsDraw(chart) {
        const ds1 = chart.getDatasetMeta(1);
        if (!ds1.data.length) return;
        const pt = ds1.data[0];
        const ctx2 = chart.ctx;
        const chartArea = chart.chartArea;

        // Draw a clean vertical dashed line from peak down to x-axis
        ctx2.save();
        ctx2.strokeStyle = 'rgba(255,80,80,0.5)';
        ctx2.setLineDash([3, 3]);
        ctx2.lineWidth = 1;
        ctx2.beginPath();
        ctx2.moveTo(pt.x, pt.y);
        ctx2.lineTo(pt.x, chartArea.bottom);
        ctx2.stroke();
        ctx2.setLineDash([]);
        ctx2.restore();
      }
    }]
  });
}

// Colormap: cyan -> dark navy -> yellow  (GPR style)
function gprColor(v) {
  // v in [-1, 1]
  if (v < 0) {
    const t = -v; // 0..1, 0=navy, 1=cyan
    return [Math.round(t * 0), Math.round(t * 255), Math.round(t * 255)];
  } else {
    const t = v;
    return [Math.round(t * 255), Math.round(t * 255), 0];
  }
}

function renderBScan(bscan, t_ns) {
  const numTraces = bscan.length;
  const numT = t_ns.length;
  const canvas = document.getElementById('bscan-canvas');
  const container = canvas.parentElement;
  const dpr = window.devicePixelRatio || 1;
  const titleH = container.querySelector('.chart-box-title').offsetHeight + 4;
  const cssW = container.clientWidth - 16;
  const cssH = Math.max(80, container.clientHeight - titleH - 16);
  canvas.style.width  = cssW + 'px';
  canvas.style.height = cssH + 'px';
  canvas.width  = Math.round(cssW * dpr);
  canvas.height = Math.round(cssH * dpr);
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  const W = cssW, H = cssH;
  ctx.fillStyle = '#0B0F19';
  ctx.fillRect(0, 0, W, H);

  const imgData = ctx.createImageData(numTraces, numT);
  let maxV = 0;
  for (const col of bscan) for (const v of col) maxV = Math.max(maxV, Math.abs(v));
  if (maxV === 0) maxV = 1;

  for (let x = 0; x < numTraces; x++) {
    for (let y = 0; y < numT; y++) {
      const v = bscan[x][y] / maxV;
      const [r, g, b] = gprColor(v);
      const idx = (y * numTraces + x) * 4;
      imgData.data[idx] = r;
      imgData.data[idx + 1] = g;
      imgData.data[idx + 2] = b;
      imgData.data[idx + 3] = 255;
    }
  }

  // Draw to offscreen and scale
  const offscreen = document.createElement('canvas');
  offscreen.width = numTraces;
  offscreen.height = numT;
  offscreen.getContext('2d').putImageData(imgData, 0, 0);

  // margins: left for Y labels + Y title, bottom for X labels + X title, top, right
  const marginL = 58, marginB = 48, marginT = 6, marginR = 10;
  const drawW = W - marginL - marginR;
  const drawH = H - marginB - marginT;
  ctx.drawImage(offscreen, marginL, marginT, drawW, drawH);

  const FONT_TICK  = '12px "Poppins", sans-serif';
  const FONT_TITLE = '13px "Poppins", sans-serif';

  // ---- Y axis ticks (Time) ----
  const maxT = t_ns[t_ns.length - 1];
  for (let i = 0; i <= 5; i++) {
    const val = (maxT * i / 5).toFixed(1);
    const py = marginT + drawH * i / 5;
    // grid line
    ctx.strokeStyle = 'rgba(31,41,55,0.6)';
    ctx.lineWidth = 0.5;
    ctx.beginPath(); ctx.moveTo(marginL, py); ctx.lineTo(marginL + drawW, py); ctx.stroke();
    // tick
    ctx.strokeStyle = '#5A6880'; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(marginL - 5, py); ctx.lineTo(marginL, py); ctx.stroke();
    // label — right-aligned, clear gap from tick
    ctx.fillStyle = '#D8E0EC';
    ctx.font = FONT_TICK;
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    ctx.fillText(val, marginL - 8, py);
    ctx.textBaseline = 'alphabetic';
  }

  // ---- Y axis title (rotated) ----
  ctx.save();
  ctx.fillStyle = '#A8B8CC';
  ctx.font = FONT_TITLE;
  ctx.textAlign = 'center';
  ctx.translate(13, marginT + drawH / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText('Time (ns) ↓', 0, 0);
  ctx.restore();

  // ---- X axis ticks (Distance) ----
  const maxDist = (numTraces / 2) * 0.02;
  for (let i = 0; i <= 6; i++) {
    const val = (-maxDist + maxDist * 2 * i / 6).toFixed(2);
    const px = marginL + drawW * i / 6;
    // grid line
    ctx.strokeStyle = 'rgba(31,41,55,0.6)';
    ctx.lineWidth = 0.5;
    ctx.beginPath(); ctx.moveTo(px, marginT); ctx.lineTo(px, marginT + drawH); ctx.stroke();
    // tick
    ctx.strokeStyle = '#5A6880'; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(px, marginT + drawH); ctx.lineTo(px, marginT + drawH + 5); ctx.stroke();
    // label — centred under tick, 18px below plot bottom
    ctx.fillStyle = '#D8E0EC';
    ctx.font = FONT_TICK;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    ctx.fillText(val, px, marginT + drawH + 6);
    ctx.textBaseline = 'alphabetic';
  }

  // ---- X axis title — at bottom of canvas, clear of tick labels ----
  ctx.fillStyle = '#A8B8CC';
  ctx.font = FONT_TITLE;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'bottom';
  ctx.fillText('Distance (m)', marginL + drawW / 2, H - 2);
  ctx.textBaseline = 'alphabetic';
}

function renderCScan(cscan) {
  const n = cscan.length;
  const canvas = document.getElementById('cscan-canvas');
  const container = canvas.parentElement;
  const dpr = window.devicePixelRatio || 1;
  const titleH = container.querySelector('.chart-box-title').offsetHeight + 4;
  const cssW = container.clientWidth - 16;
  const cssH = Math.max(80, container.clientHeight - titleH - 16);
  canvas.style.width  = cssW + 'px';
  canvas.style.height = cssH + 'px';
  canvas.width  = Math.round(cssW * dpr);
  canvas.height = Math.round(cssH * dpr);
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  const W = cssW, H = cssH;
  ctx.fillStyle = '#0B0F19';
  ctx.fillRect(0, 0, W, H);

  const imgData = ctx.createImageData(n, n);
  // inferno-like colormap
  function infernoColor(v) {
    // 0: black/purple, 0.5: orange, 1: yellow
    if (v < 0.5) {
      const t = v * 2;
      return [Math.round(t * 200), Math.round(t * 50), Math.round(100 + t * 50)];
    } else {
      const t = (v - 0.5) * 2;
      return [Math.round(200 + t * 55), Math.round(50 + t * 205), Math.round(150 - t * 150)];
    }
  }

  for (let y = 0; y < n; y++) {
    for (let x = 0; x < n; x++) {
      const v = cscan[y][x];
      const [r, g, b] = infernoColor(v);
      const idx = (y * n + x) * 4;
      imgData.data[idx] = r;
      imgData.data[idx + 1] = g;
      imgData.data[idx + 2] = b;
      imgData.data[idx + 3] = 255;
    }
  }

  const off = document.createElement('canvas');
  off.width = n; off.height = n;
  off.getContext('2d').putImageData(imgData, 0, 0);

  const mL = 48, mB = 48, mT = 6, mR = 10;
  const dW = W - mL - mR, dH = H - mB - mT;
  ctx.drawImage(off, mL, mT, dW, dH);

  // Plot border
  ctx.strokeStyle = '#374151'; ctx.lineWidth = 1;
  ctx.strokeRect(mL, mT, dW, dH);

  // Crosshairs at center
  const cx = mL + dW / 2, cy = mT + dH / 2;
  ctx.strokeStyle = 'rgba(255,50,50,0.6)';
  ctx.setLineDash([5, 3]);
  ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(mL, cy); ctx.lineTo(mL + dW, cy); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(cx, mT); ctx.lineTo(cx, mT + dH); ctx.stroke();
  ctx.setLineDash([]);
  ctx.strokeStyle = 'red'; ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.arc(cx, cy, 8, 0, Math.PI * 2); ctx.stroke();

  const FONT_TICK  = '12px "Poppins", sans-serif';
  const FONT_TITLE = '13px "Poppins", sans-serif';

  // ---- Y axis ticks ----
  for (let i = 0; i <= 4; i++) {
    const val = (-1.5 + 3 * i / 4).toFixed(1);
    const py = mT + dH - dH * i / 4;
    // tick mark
    ctx.strokeStyle = '#5A6880'; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(mL - 5, py); ctx.lineTo(mL, py); ctx.stroke();
    // label right-aligned with clear gap
    ctx.fillStyle = '#D8E0EC';
    ctx.font = FONT_TICK;
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    ctx.fillText(val, mL - 8, py);
    ctx.textBaseline = 'alphabetic';
  }

  // ---- Y axis title ----
  ctx.save();
  ctx.fillStyle = '#A8B8CC';
  ctx.font = FONT_TITLE;
  ctx.textAlign = 'center';
  ctx.translate(13, mT + dH / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText('Y Location', 0, 0);
  ctx.restore();

  // ---- X axis ticks ----
  for (let i = 0; i <= 4; i++) {
    const val = (-1.5 + 3 * i / 4).toFixed(1);
    const px = mL + dW * i / 4;
    // tick mark
    ctx.strokeStyle = '#5A6880'; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(px, mT + dH); ctx.lineTo(px, mT + dH + 5); ctx.stroke();
    // label centred under tick, 18px below plot bottom
    ctx.fillStyle = '#D8E0EC';
    ctx.font = FONT_TICK;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    ctx.fillText(val, px, mT + dH + 6);
    ctx.textBaseline = 'alphabetic';
  }

  // ---- X axis title — at very bottom, clear of tick labels ----
  ctx.fillStyle = '#A8B8CC';
  ctx.font = FONT_TITLE;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'bottom';
  ctx.fillText('X Location', mL + dW / 2, H - 2);
  ctx.textBaseline = 'alphabetic';
}

// ============================================================
// ENVIRONMENT CANVAS RENDERER
// ============================================================
const LAYER_COLORS = ['#1A2B4C', '#252A30', '#3A3E45', '#4A3B22', '#2F4F4F'];

function renderEnvironment(layerDataArr, obj) {
  const canvas = document.getElementById('env-canvas');
  const panel = canvas.parentElement;
  const dpr = window.devicePixelRatio || 1;

  // CSS size
  const cssW = canvas.offsetWidth  || panel.clientWidth - 8;
  const cssH = canvas.offsetHeight || (panel.clientHeight - 34);

  // Physical pixels
  canvas.width  = Math.round(cssW * dpr);
  canvas.height = Math.round(cssH * dpr);
  canvas.style.width  = cssW + 'px';
  canvas.style.height = cssH + 'px';

  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);

  // Work in CSS-pixel coordinates from here
  const W = cssW, H = cssH;

  ctx.fillStyle = '#080C14';
  ctx.fillRect(0, 0, W, H);

  if (!layerDataArr.length) return;

  const mL = 48, mT = 10, mR = 8, mB = 16;
  const drawW = W - mL - mR;
  const drawH = H - mT - mB;

  const totalVisDepth = layerDataArr.reduce((s, l) => s + (isFinite(l.thickness) ? l.thickness : 0.5), 0) || 1;
  const scaleY = drawH / totalVisDepth;

  let curY = mT;
  let cumDepth = 0;

  layerDataArr.forEach((l, i) => {
    const visThick = isFinite(l.thickness) ? l.thickness : 0.5;
    const pH = visThick * scaleY;
    const col = LAYER_COLORS[i % LAYER_COLORS.length];

    // Layer fill
    ctx.fillStyle = col;
    ctx.fillRect(mL, curY, drawW, pH);

    // Subtle gradient overlay
    const grad = ctx.createLinearGradient(mL, curY, mL, curY + pH);
    grad.addColorStop(0, 'rgba(255,255,255,0.05)');
    grad.addColorStop(1, 'rgba(0,0,0,0.15)');
    ctx.fillStyle = grad;
    ctx.fillRect(mL, curY, drawW, pH);

    // Border
    ctx.strokeStyle = '#00CCCC';
    ctx.lineWidth = 1;
    ctx.strokeRect(mL, curY, drawW, pH);

    // Layer label - only if tall enough
    if (pH >= 20) {
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';

      // Name: pure white, bold
      const nameFontSize = Math.min(14, Math.max(12, pH / 4));
      ctx.font = `${nameFontSize}px "Poppins", sans-serif`;
      ctx.fillStyle = '#FFFFFF';
      const textY = curY + pH / 2 + (pH >= 34 ? -8 : 0);
      ctx.fillText(l.name, mL + drawW / 2, textY);

      if (pH >= 34) {
        ctx.font = '12px "Poppins", sans-serif';
        ctx.fillStyle = '#7EE8E8';
        ctx.fillText(`εr=${l.eps_r.toFixed(1)}  |  σ=${l.sigma.toExponential(1)}`, mL + drawW / 2, curY + pH / 2 + 10);
      }
      ctx.textBaseline = 'alphabetic';
    }

    // Depth tick on Y axis
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = '#E0EAF8';
    ctx.font = '12px "Poppins", sans-serif';
    ctx.fillText(cumDepth.toFixed(2), mL - 5, curY);
    ctx.textBaseline = 'alphabetic';

    // Tick mark
    ctx.strokeStyle = '#6A7A90';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(mL - 4, curY);
    ctx.lineTo(mL, curY);
    ctx.stroke();

    curY += pH;
    cumDepth += visThick;
  });

  // Final depth label at bottom
  ctx.textAlign = 'right';
  ctx.textBaseline = 'middle';
  ctx.fillStyle = '#E0EAF8';
  ctx.font = '12px "Poppins", sans-serif';
  ctx.fillText(cumDepth.toFixed(2), mL - 5, curY);
  ctx.textBaseline = 'alphabetic';

  ctx.strokeStyle = '#6A7A90';
  ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(mL - 4, curY); ctx.lineTo(mL, curY); ctx.stroke();

  // Y-axis line
  ctx.strokeStyle = '#5A6880';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(mL, mT);
  ctx.lineTo(mL, mT + drawH);
  ctx.stroke();

  // Y-axis label "Depth (m)"
  ctx.save();
  ctx.fillStyle = '#B8C8E0';
  ctx.font = '13px "Poppins", sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.translate(12, mT + drawH / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText('Depth (m)', 0, 0);
  ctx.restore();

  // Draw object
  if (obj && obj.layerIdx >= 0 && obj.layerIdx < layerDataArr.length) {
    const objY = mT + obj.depth * scaleY;
    const objX = mL + drawW / 2;
    const r = Math.min(Math.max(6, obj.radius * scaleY), drawW * 0.18);

    // Outer glow ring
    ctx.strokeStyle = 'rgba(255, 60, 60, 0.45)';
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.arc(objX, objY, r + 6, 0, Math.PI * 2);
    ctx.stroke();

    // Sphere fill
    const sGrad = ctx.createRadialGradient(objX - r * 0.3, objY - r * 0.3, r * 0.1, objX, objY, r);
    sGrad.addColorStop(0, '#FF7777');
    sGrad.addColorStop(1, '#AA0000');
    ctx.fillStyle = sGrad;
    ctx.strokeStyle = '#FF2222';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.arc(objX, objY, r, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // Annotation label
    const objLabel = obj.type.split('(')[0].trim();
    ctx.fillStyle = '#FF6666';
    ctx.font = '12px "Poppins", sans-serif';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    ctx.strokeStyle = '#FF6666';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(objX + r + 2, objY);
    ctx.lineTo(objX + r + 7, objY);
    ctx.stroke();
    ctx.fillText(`← ${objLabel}`, objX + r + 8, objY);
    ctx.textBaseline = 'alphabetic';
  }
}

// ============================================================
// MAIN SIMULATION RUNNER
// ============================================================
function runSimulation() {
  try {
    const freq = parseVal(document.getElementById('le-frequency').value);
    const bw = parseVal(document.getElementById('le-bandwidth').value);
    const pw = parseVal(document.getElementById('le-pulse-width').value);
    const noiseLevel = 0.02;

    const layerDataArr = layers.map(getLayerData);
    if (!layerDataArr.length) return;

    const objLayerIdx = parseInt(document.getElementById('cb-obj-layer').value) || 0;
    const obj = {
      type: document.getElementById('cb-obj-type').value,
      radius: parseVal(document.getElementById('le-obj-radius').value),
      depth: parseVal(document.getElementById('le-obj-depth').value),
      sigma: parseVal(document.getElementById('le-obj-sig').value),
      eps_r: parseVal(document.getElementById('le-obj-eps').value),
      mu_r: parseVal(document.getElementById('le-obj-mu').value),
      layerIdx: objLayerIdx
    };

    const layerProps = computeLayerProperties(layerDataArr, freq);
    const objRes = computeObjectProperties(obj, layerDataArr, layerProps, freq);
    const events = collectEvents(layerProps, layerDataArr, objRes);

    // Time window
    let maxTime = 0;
    for (const e of events) if (e.time > maxTime) maxTime = e.time;
    maxTime = maxTime * 1.5 || 20e-9;
    const maxTimeNs = maxTime * 1e9;
    const numSamples = Math.min(Math.round(maxTime * 10e9), 1000);
    const t_ns = Array.from({ length: numSamples }, (_, i) => i * maxTimeNs / (numSamples - 1));

    const ascan = generateAScan(t_ns, events, freq, noiseLevel);
    const bscan = generateBScan(t_ns, events, objRes, freq, noiseLevel);
    const cscan = generateCScan(bscan);

    const velocity = objRes ? objRes.eff_vel : layerProps[0].vel;
    const snr = calcSNR(ascan, noiseLevel);

    // Render plots
    renderAScan(t_ns, ascan, freq, objRes, velocity);
    renderBScan(bscan, t_ns);
    renderCScan(cscan);
    renderEnvironment(layerDataArr, obj);

    // Update metrics
    const depth = objRes ? objRes.abs_depth : 0;
    const refTimeNs = objRes ? objRes.ref_time * 1e9 : 0;
    const amp = objRes ? objRes.recv_amp : 0;

    document.getElementById('m-depth').textContent = `${depth.toFixed(3)} m`;
    document.getElementById('m-time').textContent = `${refTimeNs.toFixed(2)} ns`;
    document.getElementById('m-snr').textContent = `${snr.toFixed(1)} dB`;
    document.getElementById('m-vel').textContent = `${velocity.toExponential(2)} m/s`;

    const ampEl = document.getElementById('m-amp');
    if (amp > 0.01) {
      ampEl.textContent = `${amp.toFixed(2)} (HI)`;
      ampEl.style.color = '#00FF00';
    } else {
      ampEl.textContent = `${amp.toExponential(1)} (LO)`;
      ampEl.style.color = '#FFBF00';
    }

    lastSimResults = { t_ns, ascan };

  } catch (e) {
    console.error('Simulation error:', e);
  }
}

// ============================================================
// EXPORT
// ============================================================
function exportTelemetry() {
  if (!lastSimResults) return;
  const { t_ns, ascan } = lastSimResults;
  let csv = 'Time (ns),A-Scan Amplitude\n';
  for (let i = 0; i < t_ns.length; i++) csv += `${t_ns[i].toFixed(4)},${ascan[i].toFixed(6)}\n`;
  const blob = new Blob([csv], { type: 'text/csv' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'telemetry_export.csv';
  a.click();
}

// ============================================================
// INIT
// ============================================================
window.addEventListener('load', () => {
  loadPreset('road');
  setTimeout(runSimulation, 100);
});

window.addEventListener('resize', () => {
  if (lastSimResults) runSimulation();
});