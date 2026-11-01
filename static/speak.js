// speak.js - local-voice TTS with auto-speak panel.
// Refuses Chrome/Edge online voices (they cause "voice error: network").
(function () {
  'use strict';

  var AUTO = false;
  var RATE = 1.0;
  var VOICE = null;
  var VOICES = [];

  function refreshVoices() {
    if (!('speechSynthesis' in window)) return [];
    var all = window.speechSynthesis.getVoices() || [];
    VOICES = all.filter(function (v) { return v.localService === true; });
    VOICES.sort(function (a, b) {
      var ae = /^en[-_]/i.test(a.lang) ? 0 : 1;
      var be = /^en[-_]/i.test(b.lang) ? 0 : 1;
      if (ae !== be) return ae - be;
      return (a.name || '').localeCompare(b.name || '');
    });
    if (!VOICE || VOICES.indexOf(VOICE) === -1) {
      VOICE = VOICES[0] || null;
    }
    return VOICES;
  }

  function speak(text) {
    if (!('speechSynthesis' in window)) return;
    text = (text || '').trim();
    if (!text) return;
    try {
      window.speechSynthesis.cancel();
      var u = new SpeechSynthesisUtterance(text);
      u.rate = RATE; u.pitch = 1.0; u.volume = 1.0;
      if (VOICE) u.voice = VOICE;
      u.onerror = function (ev) {
        if (ev && ev.error && ev.error !== 'canceled' && u.voice) {
          var u2 = new SpeechSynthesisUtterance(text);
          u2.rate = RATE;
          try { window.speechSynthesis.speak(u2); } catch (e) {}
        }
      };
      window.speechSynthesis.speak(u);
    } catch (e) {
      console.warn('[speak] failed:', e);
    }
  }

  var SELECTORS = [
    '[data-role="assistant"]',
    '.message.assistant', '.message.ai',
    '.msg.assistant', '.assistant-message',
    '.bubble.assistant'
  ];

  function getMessageText(el) {
    var body = el.querySelector('.message-body, .body, .text, p');
    return ((body ? body.textContent : el.textContent) || '').trim();
  }

  function buildPanel() {
    if (document.getElementById('neo-speak-panel')) return;

    var box = document.createElement('div');
    box.id = 'neo-speak-panel';
    box.style.cssText =
      'position:fixed;right:16px;bottom:110px;z-index:99999;' +
      'background:rgba(30,41,59,0.96);color:#e2e8f0;' +
      'border:1px solid #334155;border-radius:12px;padding:10px 12px;' +
      'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;' +
      'font-size:12px;box-shadow:0 8px 28px rgba(0,0,0,0.45);' +
      'min-width:230px;backdrop-filter:blur(6px);';

    box.innerHTML =
      '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">' +
        '<strong style="color:#f1f5f9;font-size:12px;">\uD83D\uDD0A Voice</strong>' +
        '<button id="neo-speak-close" style="background:none;border:none;color:#94a3b8;cursor:pointer;padding:0 4px;font-size:14px;">\u00D7</button>' +
      '</div>' +
      '<label style="display:flex;gap:6px;align-items:center;cursor:pointer;margin-bottom:6px;">' +
        '<input type="checkbox" id="neo-auto-speak">' +
        '<span>Auto-speak replies</span>' +
      '</label>' +
      '<div style="margin-bottom:6px;">' +
        '<label style="display:block;color:#94a3b8;margin-bottom:2px;">Voice</label>' +
        '<select id="neo-voice-pick" style="width:100%;background:#0f172a;color:#e2e8f0;border:1px solid #334155;border-radius:6px;padding:3px 6px;font-size:11px;"></select>' +
      '</div>' +
      '<div>' +
        '<label style="display:block;color:#94a3b8;margin-bottom:2px;">Rate <span id="neo-rate-val">1.0</span>\u00D7</label>' +
        '<input type="range" id="neo-rate" min="0.5" max="1.8" step="0.1" value="1.0" style="width:100%;">' +
      '</div>' +
      '<div style="margin-top:6px;color:#64748b;font-size:10px;" id="neo-speak-status">loading voices\u2026</div>';

    document.body.appendChild(box);

    var cb = box.querySelector('#neo-auto-speak');
    var pick = box.querySelector('#neo-voice-pick');
    var rate = box.querySelector('#neo-rate');
    var rateVal = box.querySelector('#neo-rate-val');
    var status = box.querySelector('#neo-speak-status');

    cb.checked = AUTO;
    cb.addEventListener('change', function () { AUTO = cb.checked; });

    rate.addEventListener('input', function () {
      RATE = parseFloat(rate.value);
      rateVal.textContent = RATE.toFixed(1);
    });

    pick.addEventListener('change', function () {
      var name = pick.value;
      VOICE = VOICES.filter(function (v) { return v.name === name; })[0] || null;
    });

    box.querySelector('#neo-speak-close').addEventListener('click', function () {
      box.style.display = 'none';
    });

    function populate() {
      refreshVoices();
      if (!VOICES.length) {
        status.textContent = 'no local voices found';
        pick.innerHTML = '<option>(none)</option>';
        return;
      }
      pick.innerHTML = VOICES.map(function (v) {
        var sel = (VOICE && v.name === VOICE.name) ? ' selected' : '';
        var n = v.name.replace(/"/g, '&quot;');
        return '<option value="' + n + '"' + sel + '>' + v.name + ' (' + v.lang + ')</option>';
      }).join('');
      status.textContent = VOICES.length + ' local voice(s) \u00B7 ' +
                           (VOICE ? VOICE.name : 'none selected');
    }

    populate();
    setTimeout(populate, 400);
    if ('speechSynthesis' in window) {
      window.speechSynthesis.onvoiceschanged = populate;
    }
  }

  function addButtons() {
    SELECTORS.forEach(function (sel) {
      document.querySelectorAll(sel).forEach(function (el) {
        if (el.querySelector('.neo-speak-btn')) return;
        var text = getMessageText(el);
        if (!text || text.length < 3) return;

        var btn = document.createElement('button');
        btn.className = 'neo-speak-btn';
        btn.textContent = '\uD83D\uDD0A';
        btn.title = 'Speak this response';
        btn.style.cssText =
          'background:none;border:1px solid #334155;color:#94a3b8;' +
          'border-radius:6px;cursor:pointer;padding:2px 8px;font-size:12px;' +
          'margin-left:8px;vertical-align:middle;';

        btn.addEventListener('click', function (e) {
          e.preventDefault(); e.stopPropagation();
          speak(text);
          btn.textContent = '\u23F8';
          setTimeout(function () { btn.textContent = '\uD83D\uDD0A'; }, 2000);
        });
        el.appendChild(btn);

        if (AUTO) speak(text);
      });
    });
  }

  var obs = new MutationObserver(addButtons);

  function boot() {
    buildPanel();
    addButtons();
    if (document.body) {
      obs.observe(document.body, { childList: true, subtree: true });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
