// quick_panel.js — floating panel with profile badge + quick-launch buttons.
// Injected by launcher into the chat page.
(function(){
  'use strict';

  function makePanel(){
    const box = document.createElement('div');
    box.id = 'neo-quick-panel';
    box.style.cssText = [
      'position:fixed', 'right:16px', 'bottom:16px', 'z-index:99999',
      'background:rgba(30,41,59,0.96)', 'color:#e2e8f0',
      'border:1px solid #334155', 'border-radius:12px', 'padding:12px',
      'font-family:-apple-system,system-ui,"Segoe UI",sans-serif', 'font-size:12px',
      'box-shadow:0 8px 24px rgba(0,0,0,0.4)', 'max-width:260px',
      'backdrop-filter:blur(6px)',
    ].join(';');

    box.innerHTML = `
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
        <span style="font-weight:600;font-size:12px">Farm Quick</span>
        <span id="neo-profile-badge" style="
          font-size:10px;padding:2px 8px;border-radius:8px;
          background:rgba(34,197,94,0.18);color:#22c55e;letter-spacing:.4px">
          loading…
        </span>
        <button id="neo-panel-toggle" style="
          margin-left:auto;background:none;border:0;color:#94a3b8;
          cursor:pointer;font-size:14px;padding:0">×</button>
      </div>
      <div style="display:flex;flex-direction:column;gap:6px">
        <button data-p="farm: Nakuru">Full brief</button>
        <button data-p="market: maize milk beans">Market prices</button>
        <button data-p="search: Kenya farming news this week">Local news</button>
        <a href="/farm" style="
          padding:6px 10px;border-radius:6px;border:1px solid #334155;
          color:#e2e8f0;text-decoration:none;text-align:center;font-size:12px">
          Open /farm
        </a>
      </div>
    `;

    // Style the buttons inline
    box.querySelectorAll('button[data-p]').forEach(b => {
      b.style.cssText = 'padding:6px 10px;border-radius:6px;border:1px solid #334155;background:#1e293b;color:#e2e8f0;cursor:pointer;font-size:12px;text-align:left';
      b.addEventListener('mouseover', () => { b.style.borderColor = '#38bdf8'; b.style.color = '#38bdf8'; });
      b.addEventListener('mouseout', () => { b.style.borderColor = '#334155'; b.style.color = '#e2e8f0'; });
      b.addEventListener('click', () => send(b.dataset.p));
    });

    box.querySelector('#neo-panel-toggle').addEventListener('click', () => {
      box.remove();
    });

    document.body.appendChild(box);
    loadProfile();
  }

  function findInput(){
    // Try common chat-input selectors
    const sels = [
      'input[type="text"]', 'textarea', 'input#message', 'input.chat-input',
      'form input', 'input[placeholder*="essage" i]', 'input[placeholder*="sk" i]',
    ];
    for (const s of sels){
      const el = document.querySelector(s);
      if (el) return el;
    }
    return null;
  }

  function findSendButton(){
    const btns = document.querySelectorAll('button');
    for (const b of btns){
      const t = (b.textContent || '').toLowerCase();
      if (t.includes('send') || t.includes('ask') || t.includes('go')) return b;
    }
    return null;
  }

  function send(text){
    const inp = findInput();
    if (!inp) { alert('Could not find chat input. Use the /farm page instead.'); return; }
    const desc = Object.getOwnPropertyDescriptor(inp.constructor.prototype, 'value');
    if (desc && desc.set) desc.set.call(inp, text);
    else inp.value = text;
    inp.dispatchEvent(new Event('input', { bubbles: true }));
    inp.dispatchEvent(new Event('change', { bubbles: true }));

    const btn = findSendButton();
    if (btn) { btn.click(); return; }
    // Fallback: submit the form
    if (inp.form) { inp.form.requestSubmit ? inp.form.requestSubmit() : inp.form.submit(); return; }
    // Keyboard fallback
    inp.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', code:'Enter', keyCode:13, bubbles:true}));
  }

  async function loadProfile(){
    try {
      const r = await fetch('/api/profile');
      const j = await r.json();
      const el = document.getElementById('neo-profile-badge');
      if (el) el.textContent = (j.active || '?');
    } catch (e) {
      const el = document.getElementById('neo-profile-badge');
      if (el) el.textContent = 'offline';
    }
  }

  function boot(){
    if (document.getElementById('neo-quick-panel')) return;
    makePanel();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();