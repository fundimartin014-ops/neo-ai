from pathlib import Path

js = r"""// speak.js — 🔊 button + optional auto-speak on every assistant reply.
(function(){
  'use strict';
  var SELECTORS = [
    '[data-role="assistant"]',
    '.message.assistant',
    '.message.ai',
    '.msg.assistant',
    '.assistant-message',
    '.bubble.assistant'
  ];

  var AUTO = false;         // toggled by the UI panel
  var VOICE = null;         // cached local voice

  function getMessageText(el){
    var body = el.querySelector('.message-body, .body, .text, p');
    var raw = body ? body.textContent : el.textContent;
    return (raw || '').trim();
  }

  function pickLocalVoice(){
    if (VOICE) return VOICE;
    if (!('speechSynthesis' in window)) return null;
    var voices = window.speechSynthesis.getVoices() || [];
    // Prefer en-* local voices (localService === true)
    var local = voices.filter(function(v){
      return v.localService === true && /en[-_]/i.test(v.lang);
    });
    if (local.length) return (VOICE = local[0]);
    // Fall back to any en voice
    var en = voices.find(function(v){ return /en[-_]/i.test(v.lang); });
    if (en) return (VOICE = en);
    // Last resort: first voice at all
    return (VOICE = voices[0] || null);
  }

  function speak(text){
    if (!('speechSynthesis' in window)) { return; }
    try {
      window.speechSynthesis.cancel();
      var u = new SpeechSynthesisUtterance(text);
      u.rate = 1.0; u.pitch = 1.0; u.volume = 1.0;
      var v = pickLocalVoice();
      if (v) u.voice = v;
      // If it errors, retry once without specifying a voice (uses default)
      u.onerror = function(ev){
        if (ev && ev.error && ev.error !== 'canceled' && u.voice) {
          u.voice = null;
          try { window.speechSynthesis.speak(u); } catch(e){}
        }
      };
      window.speechSynthesis.speak(u);
    } catch (e) {
      console.warn('[speak] failed:', e);
    }
  }

  function buildPanel(){
    if (document.getElementById('neo-speak-panel')) return;
    var box = document.createElement('div');
    box.id = 'neo-speak-panel';
    box.style.cssText = 'position:fixed;right:16px;bottom:110px;z-index:99999;' +
      'background:rgba(30,41,59,0.96);color:#e2e8f0;border:1px solid #334155;' +
      'border-radius:10px;padding:8px 10px;font-family:-apple-system,sans-serif;' +
      'font-size:12px;box-shadow:0 8px 24px rgba(0,0,0,0.4);';
    box.innerHTML = '<label style="cursor:pointer;display:flex;gap:6px;align-items:center">' +
      '<input type="checkbox" id="neo-auto-speak"> Auto-speak replies</label>' +
      '<div style="margin-top:6px;color:#94a3b8" id="neo-speak-status">voice: loading…</div>';
    document.body.appendChild(box);
    var cb = box.querySelector('#neo-auto-speak');
    cb.checked = AUTO;
    cb.addEventListener('change', function(){ AUTO = cb.checked; });
    setTimeout(function(){
      var v = pickLocalVoice();
      var s = document.getElementById('neo-speak-status');
      if (v && s) s.textContent = 'voice: ' + v.name;
      else if (s) s.textContent = 'voice: none found';
    }, 400);
  }

  function addButtons(){
    SELECTORS.forEach(function(sel){
      document.querySelectorAll(sel).forEach(function(el){
        if (el.querySelector('.neo-speak-btn')) return;
        var text = getMessageText(el);
        if (!text || text.length < 3) return;
        var btn = document.createElement('button');
        btn.className = 'neo-speak-btn';
        btn.textContent = '🔊';
        btn.title = 'Speak this response';
        btn.style.cssText = 'background:none;border:1px solid #334155;color:#94a3b8;' +
          'border-radius:6px;cursor:pointer;padding:2px 8px;font-size:12px;' +
          'margin-left:8px;vertical-align:middle';
        btn.addEventListener('click', function(e){
          e.preventDefault(); e.stopPropagation();
          speak(text);
          btn.textContent = '⏸';
          setTimeout(function(){ btn.textContent = '🔊'; }, 2000);
        });
        el.appendChild(btn);
        if (AUTO) speak(text);
      });
    });
  }

  var obs = new MutationObserver(addButtons);
  function boot(){
    buildPanel();
    addButtons();
    obs.observe(document.body, { childList: true, subtree: true });
    if ('speechSynthesis' in window) {
      window.speechSynthesis.onvoiceschanged = function(){ VOICE = null; pickLocalVoice(); };
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
"""
Path("static/speak.js").write_text(js, encoding="utf-8")
print("Rewrote static/speak.js — local voices only + auto-speak toggle")