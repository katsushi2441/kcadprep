// Kurage 設計下書き — 画面の動き（送信・進み具合・3D 表示）
import * as THREE from 'three';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

// 共有
$('copy').addEventListener('click', async (ev) => {
  try { await navigator.clipboard.writeText(ev.target.dataset.copy); ev.target.textContent = 'コピーしました'; } catch (e) { prompt('コピーしてください', ev.target.dataset.copy); }
});
// 見本
document.querySelectorAll('#ex button').forEach((b) => b.addEventListener('click', () => { $('req').value = b.dataset.t; }));
document.querySelectorAll('input[name=engine]').forEach((r) => r.addEventListener('change', () => {
  $('passbox').style.display = document.querySelector('input[name=engine]:checked').value === 'codex' ? 'block' : 'none';
}));

// ---- 3D ----
let renderer, scene, camera, controls, meshes = {}, size = 100;
function initViewer() {
  if (renderer) return;
  const box = $('viewer');
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  box.appendChild(renderer.domElement);
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(35, 1, 0.1, 10000);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x8899aa, 1.6));
  const d = new THREE.DirectionalLight(0xffffff, 1.4); d.position.set(1, -1.5, 2); scene.add(d);
  const d2 = new THREE.DirectionalLight(0xffffff, 0.6); d2.position.set(-2, 1, -1); scene.add(d2);
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  const resize = () => { const w = box.clientWidth, h = box.clientHeight; renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); };
  new ResizeObserver(resize).observe(box); resize();
  (function loop() { requestAnimationFrame(loop); controls.update(); renderer.render(scene, camera); })();
}
const MAT = {
  part: new THREE.MeshStandardMaterial({ color: 0x8a95a1, metalness: 0.1, roughness: 0.55 }),
  cavity: new THREE.MeshStandardMaterial({ color: 0x3d7bd9, metalness: 0.3, roughness: 0.45, transparent: true, opacity: 0.55, side: THREE.DoubleSide }),
  core: new THREE.MeshStandardMaterial({ color: 0xe08a2b, metalness: 0.3, roughness: 0.45, transparent: true, opacity: 0.55, side: THREE.DoubleSide }),
};
function placeOpen() {
  const open = $('open').checked, gap = size * 0.9;
  if (meshes.cavity) meshes.cavity.position.z = open ? gap : 0;
  if (meshes.core) meshes.core.position.z = open ? -gap * 0.6 : 0;
}
async function loadModels(id, names) {
  initViewer();
  $('empty').style.display = 'none';
  Object.values(meshes).forEach((m) => scene.remove(m)); meshes = {};
  const loader = new STLLoader();
  for (const n of names) {
    const buf = await fetch(`api.php?a=file&id=${id}&name=${n}.stl`).then((r) => { if (!r.ok) throw new Error(n); return r.arrayBuffer(); });
    const g = loader.parse(buf); g.computeVertexNormals();
    const m = new THREE.Mesh(g, MAT[n]); m.renderOrder = n === 'part' ? 0 : 1;
    meshes[n] = m; scene.add(m);
  }
  const bb = new THREE.Box3().setFromObject(meshes.part);
  const s = bb.getSize(new THREE.Vector3()); size = Math.max(s.x, s.y, s.z);
  placeOpen();
  const all = new THREE.Box3(); Object.values(meshes).forEach((m) => all.expandByObject(m));
  const c = all.getCenter(new THREE.Vector3()), r = all.getSize(new THREE.Vector3()).length();
  camera.up.set(0, 0, 1);
  camera.position.set(c.x + r * 0.9, c.y - r * 1.25, c.z + r * 0.7);
  camera.near = r / 100; camera.far = r * 20; camera.updateProjectionMatrix();
  controls.target.copy(c); controls.update();
  document.querySelectorAll('#tg input[data-k]').forEach((x) => { if (meshes[x.dataset.k]) meshes[x.dataset.k].visible = x.checked; });
  $('tg').style.display = 'flex';
}
document.querySelectorAll('#tg input[data-k]').forEach((x) => x.addEventListener('change', () => { if (meshes[x.dataset.k]) meshes[x.dataset.k].visible = x.checked; }));
$('open').addEventListener('change', placeOpen);

// ---- 送信と進み具合 ----
function showErr(t) { $('err').style.display = t ? 'block' : 'none'; $('err').textContent = t || ''; }
function showLog(log) { $('log').innerHTML = (log || []).map(([t, m]) => `<li><b>${Math.round(t)}秒</b>${esc(m)}</li>`).join(''); }
const fmt = (v, u) => (v === undefined || v === null ? '—' : `${Number(v).toLocaleString('ja-JP')}${u}`);
function showResult(id, r) {
  const m = r.metrics || {};
  $('mt').innerHTML = [
    ['外形（mm）', (m.size || []).join(' × ')], ['体積', fmt(m.volume_cm3, ' cm³')], ['重さの目安', fmt(m.weight_g, ' g') + `<small>${esc(m.material || '')}</small>`],
    ['投影面積', fmt(m.projected_cm2, ' cm²')], ['型締め力の目安', fmt(m.clamp_ton, ' トン') + `<small>型内の圧力 ${m.pressure_mpa || '—'}MPa で計算</small>`],
    ['型の大きさ（mm）', (m.mold_size || []).join(' × ')], ['冷却穴', fmt(m.cooling_holes, ' 本') + '<small>φ8・貫通</small>'], ['成形収縮率の目安', fmt(m.shrink_percent, ' %')],
  ].map(([k, v]) => `<div><small>${k}</small><b>${v}</b></div>`).join('');
  const f = (n, label, main) => `<a class="${main ? 'main' : ''}" href="api.php?a=file&id=${id}&name=${n}&dl=1">${label}</a>`;
  $('dl').innerHTML = f('part.step', '成形品 STEP', 1) + (m.mold_ok ? f('cavity.step', 'キャビティ STEP') + f('core.step', 'コア STEP') : '') + f('part.stl', '成形品 STL') + f('part_code.py', 'CAD のコード');
  $('memo').style.display = r.memo ? 'block' : 'none';
  $('memo').textContent = r.memo ? '設計メモ（AI が決めた寸法・仮定）\n' + r.memo : '';
  $('codebox').style.display = 'block'; $('code').textContent = r.code || '';
  if (!m.mold_ok) showErr('成形品は作れましたが、型の分割に失敗しました。成形品だけを表示しています。');
  return loadModels(id, m.mold_ok ? ['part', 'cavity', 'core'] : ['part']);
}
async function poll(id) {
  for (;;) {
    await new Promise((ok) => setTimeout(ok, 2500));
    let d;
    try { d = await fetch(`api.php?a=job&id=${id}`).then((r) => r.json()); } catch (e) { continue; }
    showLog(d.log);
    if (d.status === 'queued') $('log').innerHTML = '<li>順番待ちです。前の設計が終わると始まります。</li>';
    if (d.status === 'done') { await showResult(id, d.result); return; }
    if (d.status === 'failed') {
      const r = d.result || {};
      showErr('下書きを作れませんでした。説明を短く・寸法をはっきり書いて、もう一度お試しください。\n' + (r.error || '').slice(-300));
      if (r.code) { $('codebox').style.display = 'block'; $('code').textContent = r.code; }
      return;
    }
  }
}
$('go').addEventListener('click', async () => {
  showErr(''); $('log').innerHTML = '<li>送っています…</li>';
  const engine = document.querySelector('input[name=engine]:checked').value;
  $('go').disabled = true; $('go').textContent = '設計しています…';
  try {
    const res = await fetch('api.php?a=create', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ request: $('req').value, engine, material: $('mat').value, passcode: $('pass').value }) });
    const d = await res.json().catch(() => ({}));
    if (!res.ok) { showErr(d.detail || '送れませんでした'); $('log').innerHTML = ''; return; }
    history.replaceState(null, '', '#job=' + d.id);
    await poll(d.id);
  } catch (e) { showErr('通信に失敗しました。もう一度お試しください。'); }
  finally { $('go').disabled = false; $('go').textContent = '設計の下書きを作る'; }
});
// 共有された結果（#job=…）を開いたら、その結果を出す
const h = location.hash.match(/job=([0-9]{8}-[0-9]{6}-[a-f0-9]{6})/);
if (h) { fetch(`api.php?a=job&id=${h[1]}`).then((r) => r.json()).then((d) => { if (d.status === 'done') { $('req').value = d.request || ''; showResult(h[1], d.result); } else if (d.status === 'running' || d.status === 'queued') poll(h[1]); }).catch(() => {}); }
