// gesture.js — webcam gesture control using MediaPipe GestureRecognizer.
// Injected into the chat page alongside quick_panel.js.
//
// Gestures mapped to actions:
//   Thumb_Up    -> run farm brief
//   Open_Palm   -> stop camera
//   Victory     -> market prices
//   Closed_Fist -> clear (nothing for now)
//   ILoveYou    -> switch profile to all
//   Pointing_Up -> open /farm dashboard
(function(){
  'use strict';

  const MP_VISION = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14';
  const MODEL_URL = 'https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task';

  let recognizer = null;
  let videoEl = null;
  let rafId = null;
  let lastGesture = '';
  let lastFireTime = 0;
  const COOLDOWN_MS = 2500;      // don't refire the same gesture within 2.5s
  const MIN_CONFIDENCE = 0.7;

  const ACTIONS = {
    'Thumb_Up':    { label: 'Full farm brief', payload: 'farm: Nakuru' },
    'Victory':     { label: 'Market prices',   payload: 'market: maize milk beans' },
    'ILoveYou':    { label: 'Switch to all profile', payload: '' },
    'Pointing_Up': { label: 'Open /farm',      payload: '' },
    'Open_Palm':   { label: 'Stop camera',     payload: '' },
    'Closed_Fist': { label: 'Local news',      payload: 'search: Kenya farming news this week' },
  };

  function makePanel(){
    if (document.getElementById('neo-gesture-panel')) return;
    const box = document.createElement('div');
    box.id = 'neo-gesture-panel';
    box.style.cssText = [
      'position:fixed','left:16px','bottom:16px','z-index:99999',
      'background:rgba(30,41,59,0.96)','color:#e2e8f0',
      'border:1px solid #334155','border-radius:12px','padding:10px',
      'font-family:-apple-system,system-ui,sans-serif','font-size:12px',
      'box-shadow:0 8px 24px rgba(0,0,0,0.4)','max-width:260px',
    ].join(';');
    box.innerHTML = `
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
        <span style="font-weight:600">Gesture</span>
        <span id="neo-gesture-status" style="font-size:11px;color:#94a3b8">off</span>
        <button id="neo-gesture-toggle" style="margin-left:auto;background:none;border:0;color:#94a3b8;cursor:pointer">▶</button>
      </div>
      <div id="neo-gesture-body" style="display:none">
        <video id="neo-gesture-video" autoplay playsinline muted
               style="width:100%;border-radius:6px;background:#000"></video>
        <div id="neo-gesture-last" style="margin-top:6px;color:#94a3b8">last: —</div>
        <div style="margin-top:6px;line-height:1.4">
          👍 brief &nbsp; ✌️ market &nbsp; 🤟 all &nbsp; ☝️ /farm<br>
          ✋ stop &nbsp;&nbsp; ✊ news
        </div>
      </div>
    `;
    document.body.appendChild(box);

    document.getElementById('neo-gesture-toggle').addEventListener('click', toggleCamera);
  }

  async function toggleCamera(){
    const btn = document.getElementById('neo-gesture-toggle');
    const body = document.getElementById('neo-gesture-body');
    const status = document.getElementById('neo-gesture-status');

    if (videoEl) {
      // stop
      if (rafId) cancelAnimationFrame(rafId);
      if (videoEl.srcObject) videoEl.srcObject.getTracks().forEach(t => t.stop());
      videoEl = null;
      body.style.display = 'none';
      btn.textContent = '▶';
      status.textContent = 'off';
      return;
    }

    btn.textContent = '…';
    status.textContent = 'loading model…';

    try {
      const vision = await import(`${MP_VISION}`);
      const { GestureRecognizer, FilesetResolver } = vision;

      const fileset = await FilesetResolver.forVisionTasks(`${MP_VISION}/wasm`);
      recognizer = await GestureRecognizer.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: MODEL_URL, delegate: 'GPU' },
        runningMode: 'VIDEO',
        numHands: 1,
      });

      videoEl = document.getElementById('neo-gesture-video');
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 320, height: 240 }, audio: false });
      videoEl.srcObject = stream;
      await videoEl.play();

      body.style.display = 'block';
      btn.textContent = '⏸';
      status.textContent = 'active';
      loop();
    } catch (e) {
      status.textContent = 'error: ' + e.message;
      btn.textContent = '▶';
      console.error('[gesture]', e);
    }
  }

  function loop(){
    if (!videoEl || !recognizer) return;
    const now = performance.now();
    try {
      const res = recognizer.recognizeForVideo(videoEl, now);
      if (res && res.gestures && res.gestures.length) {
        const top = res.gestures[0][0];
        if (top && top.categoryName && top.score >= MIN_CONFIDENCE) {
          onGesture(top.categoryName);
        }
      }
    } catch (e) { /* ignore single-frame errors */ }
    rafId = requestAnimationFrame(loop);
  }

  function onGesture(name){
    const now = Date.now();
    if (name === lastGesture && now - lastFireTime < COOLDOWN_MS) return;
    lastGesture = name;
    lastFireTime = now;

    const el = document.getElementById('neo-gesture-last');
    const action = ACTIONS[name];
    if (el) el.textContent = `last: ${name}${action ? ' → ' + action.label : ''}`;

    if (!action) return;
    if (name === 'Open_Palm') { toggleCamera(); return; }
    if (name === 'Pointing_Up') { window.open('/farm', '_blank'); return; }
    if (name === 'ILoveYou') { sendCommand('agent list'); return; }
    if (action.payload) sendCommand(action.payload);
  }

  function sendCommand(text){
    const inp = document.querySelector('input[type="text"]') ||
                document.querySelector('textarea') ||
                document.querySelector('form input');
    if (!inp) { console.warn('[gesture] no chat input found'); return; }
    const desc = Object.getOwnPropertyDescriptor(inp.constructor.prototype, 'value');
    if (desc && desc.set) desc.set.call(inp, text);
    else inp.value = text;
    inp.dispatchEvent(new Event('input', { bubbles: true }));
    inp.dispatchEvent(new Event('change', { bubbles: true }));
    const btns = document.querySelectorAll('button');
    for (const b of btns) {
      const t = (b.textContent || '').toLowerCase();
      if (t.includes('send') || t.includes('ask')) { b.click(); return; }
    }
    if (inp.form) inp.form.requestSubmit ? inp.form.requestSubmit() : inp.form.submit();
  }

  function boot(){
    if (document.getElementById('neo-gesture-panel')) return;
    makePanel();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();