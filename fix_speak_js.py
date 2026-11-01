from pathlib import Path

js = r"""// speak.js — adds a 🔊 button to every assistant message.
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
  function getMessageText(el){
    var body = el.querySelector('.message-body, .body, .text, p');
    var raw = body ? body.textContent : el.textContent;
    return (raw || '').trim();
  }
  function speak(text){
    if (!('speechSynthesis' in window)) { alert('No speech synthesis'); return; }
    window.speechSynthesis.cancel();
    var u = new SpeechSynthesisUtterance(text);
    u.rate = 1.0; u.pitch = 1.0; u.volume = 1.0;
    var voices = window.speechSynthesis.getVoices();
    var preferred = voices.find(function(v){ return /en[-_]/i.test(v.lang); }) || voices[0];
    if (preferred) u.voice = preferred;
    window.speechSynthesis.speak(u);
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
      });
    });
  }
  var obs = new MutationObserver(addButtons);
  function boot(){
    addButtons();
    obs.observe(document.body, { childList: true, subtree: true });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
"""
Path("static/speak.js").write_text(js, encoding="utf-8")
print("Rewrote static/speak.js cleanly")