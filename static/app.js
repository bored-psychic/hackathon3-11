/* Health Check web app: dashboard, symptom chat, nearby facilities, family profiles.
   Vanilla JS, no build step. All server/user text is inserted with textContent (never innerHTML);
   innerHTML is only used for the static SVG icons defined below. */
(function () {
  'use strict';

  var T = window.I18N;
  var SPEECH_LANG = { en: 'en-IN', kn: 'kn-IN', hi: 'hi-IN', ta: 'ta-IN', te: 'te-IN', ml: 'ml-IN' };
  var DEFAULT_LANG = 'kn';            // Karnataka default (see API.md)
  var CHAT_TIMEOUT_MS = 40000;        // backend LLM call can take ~25s
  var PLACES_TIMEOUT_MS = 75000;      // OpenStreetMap lookups can be slow
  var STORE_KEY = 'triage-app-v1';
  var DAY = 86400000;

  var CONDITIONS = ['diabetes', 'bp', 'heart', 'lung', 'kidney', 'tb', 'epilepsy'];
  var COND_EN = { diabetes: 'diabetes', bp: 'high blood pressure', heart: 'heart disease',
    lung: 'asthma or lung disease', kidney: 'kidney disease', tb: 'tuberculosis', epilepsy: 'epilepsy (fits)' };
  var RELATIONS = ['self', 'spouse', 'child', 'parent', 'grandparent', 'sibling', 'other'];
  var HELPLINES = ['108', '112', '104', '14416'];
  var FILTERS = [['all', 'fAll'], ['govt', 'fGovt'], ['hospital', 'fHospital'], ['clinic', 'fClinic'], ['ngo', 'fNgo']];

  var ICONS = {
    home: '<path d="M12 3 2 12h3v8h5v-6h4v6h5v-8h3z"/>',
    chat: '<path d="M4 4h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H8l-4 4V6a2 2 0 0 1 2-2zm3 5v2h10V9H7zm0 4v2h7v-2H7z"/>',
    pin: '<path d="M12 2a7 7 0 0 0-7 7c0 5.2 7 13 7 13s7-7.8 7-13a7 7 0 0 0-7-7zm0 9.5A2.5 2.5 0 1 1 12 6.5a2.5 2.5 0 0 1 0 5z"/>',
    people: '<path d="M16 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6zm-8 0a3 3 0 1 0 0-6 3 3 0 0 0 0 6zm0 2c-2.7 0-8 1.3-8 4v3h10v-3c0-1.1.5-2.1 1.4-2.9A12 12 0 0 0 8 13zm8 0c-.3 0-.7 0-1.1.1 1.3.9 2.1 2 2.1 3.9v3h7v-3c0-2.7-5.3-4-8-4z"/>',
    phone: '<path d="M6.6 10.8a15.1 15.1 0 0 0 6.6 6.6l2.2-2.2a1 1 0 0 1 1-.25 11.4 11.4 0 0 0 3.6.57 1 1 0 0 1 1 1V20a1 1 0 0 1-1 1A17 17 0 0 1 3 4a1 1 0 0 1 1-1h3.5a1 1 0 0 1 1 1c0 1.25.2 2.45.57 3.57a1 1 0 0 1-.25 1l-2.2 2.2z"/>',
    mic: '<path d="M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-3.08A7 7 0 0 0 19 11h-2z"/>',
    speaker: '<path d="M3 10v4h4l5 5V5L7 10H3zm13.5 2A4.5 4.5 0 0 0 14 8v8a4.5 4.5 0 0 0 2.5-4zM14 3.2v2.1a7 7 0 0 1 0 13.4v2.1a9 9 0 0 0 0-17.6z"/>',
    route: '<path d="M21.7 11.3 12.7 2.3a1 1 0 0 0-1.4 0l-9 9a1 1 0 0 0 0 1.4l9 9a1 1 0 0 0 1.4 0l9-9a1 1 0 0 0 0-1.4zM14 14.5V12h-4v3H8v-4a1 1 0 0 1 1-1h5V7.5l3.5 3.5-3.5 3.5z"/>',
    plus: '<path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6z"/>',
    edit: '<path d="M3 17.25V21h3.75L17.8 9.94l-3.75-3.75L3 17.25zM20.7 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/>',
    target: '<path d="M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zm9 3h-2.1A7 7 0 0 0 13 5.1V3h-2v2.1A7 7 0 0 0 5.1 11H3v2h2.1a7 7 0 0 0 5.9 5.9V21h2v-2.1a7 7 0 0 0 5.9-5.9H21v-2zm-9 6a5 5 0 1 1 0-10 5 5 0 0 1 0 10z"/>',
    sms: '<path d="M20 2H4a2 2 0 0 0-2 2v18l4-4h14a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2zM9 11H7V9h2v2zm4 0h-2V9h2v2zm4 0h-2V9h2v2z"/>'
  };
  function icon(name) {
    var s = document.createElement('span');
    s.style.display = 'inline-flex';
    s.innerHTML = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">' + ICONS[name] + '</svg>'; // static only
    return s.firstChild;
  }

  /* ---------- Tiny DOM helper: h('div', {class, text, onclick, ...}, [children]) ---------- */
  function h(tag, attrs, kids) {
    var e = document.createElement(tag);
    for (var k in (attrs || {})) {
      var v = attrs[k];
      if (v == null || v === false) continue;
      if (k === 'class') e.className = v;
      else if (k === 'text') e.textContent = v; // always textContent for data
      else if (k.indexOf('on') === 0) e.addEventListener(k.slice(2), v);
      else e.setAttribute(k, v === true ? '' : v);
    }
    (kids || []).forEach(function (c) {
      if (c == null || c === false) return;
      e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    });
    return e;
  }
  var $ = function (id) { return document.getElementById(id); };

  /* ---------- Local storage (this phone only) ---------- */
  function blankStore() {
    return { lang: null, members: [], contact: { name: '', phone: '' }, checks: [], places: null, lastLoc: null };
  }
  function loadStore() {
    var s = null;
    try { s = JSON.parse(localStorage.getItem(STORE_KEY)); } catch (e) {}
    if (s && typeof s === 'object' && Array.isArray(s.members)) {
      var b = blankStore();
      for (var k in b) if (s[k] === undefined) s[k] = b[k];
      return s;
    }
    s = blankStore();
    try { s.lang = localStorage.getItem('triage-lang'); } catch (e) {} // from the older single-page version
    return s;
  }
  var store = loadStore();
  function save() { try { localStorage.setItem(STORE_KEY, JSON.stringify(store)); } catch (e) {} }
  function uid() { return Date.now().toString(36) + Math.random().toString(36).slice(2, 7); }
  function member(id) { return store.members.find(function (m) { return m.id === id; }) || null; }

  /* ---------- i18n ---------- */
  var langSel = $('lang');
  function lang() { return langSel.value; }
  // t(key, vars, code): translated text with {placeholders} filled in
  function t(key, vars, code) {
    var pack = T[code || lang()] || T.en;
    var s = pack[key] != null ? pack[key] : T.en[key];
    if (s == null) return key;
    if (vars && typeof s === 'string') s = s.replace(/\{(\w+)\}/g, function (_, k) { return vars[k] != null ? vars[k] : ''; });
    return s;
  }
  function fmtDate(ts, withTime) {
    var o = withTime ? { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' } : { day: 'numeric', month: 'short' };
    try { return new Date(ts).toLocaleString(SPEECH_LANG[lang()] || 'en-IN', o); } catch (e) { return new Date(ts).toDateString(); }
  }

  function applyLanguage() {
    var code = lang();
    document.documentElement.lang = code; // helps the browser pick the right script font
    document.title = t('appName');
    document.querySelectorAll('[data-i18n]').forEach(function (e) { e.textContent = t(e.getAttribute('data-i18n')); });
    document.querySelectorAll('[data-i18n-ph]').forEach(function (e) { e.placeholder = t(e.getAttribute('data-i18n-ph')); });
    document.querySelectorAll('[data-i18n-aria]').forEach(function (e) {
      e.setAttribute('aria-label', t(e.getAttribute('data-i18n-aria')));
    });
    store.lang = code;
    save();
  }

  /* ---------- Router: #home | #check | #near | #family ---------- */
  var VIEWS = { home: renderHome, check: renderCheck, near: renderNear, family: renderFamily };
  function currentTab() {
    var tab = (location.hash || '#home').slice(1);
    return VIEWS[tab] ? tab : 'home';
  }
  function route() {
    var tab = currentTab();
    Object.keys(VIEWS).forEach(function (k) { $('view-' + k).hidden = k !== tab; });
    document.querySelectorAll('.tabbar a').forEach(function (a) {
      if (a.dataset.tab === tab) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
    });
    VIEWS[tab]();
  }
  function go(tab) {
    if (currentTab() === tab) route(); else location.hash = '#' + tab;
  }
  window.addEventListener('hashchange', route);

  /* =====================================================================
     HOME / DASHBOARD
     ===================================================================== */
  function activeAlerts() {
    var now = Date.now();
    return store.checks.filter(function (c) {
      return !c.done && (c.level === 'RED' || c.level === 'AMBER') && now - c.at < 3 * DAY;
    });
  }
  function whoName(c) { var m = member(c.memberId); return m ? m.name : t('someoneElse'); }
  function lastCheckOf(id) {
    for (var i = store.checks.length - 1; i >= 0; i--) if (store.checks[i].memberId === id) return store.checks[i];
    return null;
  }

  function renderHome() {
    var v = $('view-home');
    v.textContent = '';
    v.appendChild(h('h2', { class: 'hello', text: t('hello') + ' 🙏' }));
    v.appendChild(h('button', { class: 'btn primary big', type: 'button', onclick: function () { startCheckFor(''); } },
      [icon('chat'), t('startCheck')]));

    // Alerts needing follow-up
    v.appendChild(h('h3', { text: t('alerts') }));
    var al = activeAlerts();
    if (!al.length) v.appendChild(h('p', { class: 'muted', text: t('noAlerts') }));
    al.slice().reverse().forEach(function (c) {
      var follow = c.level === 'RED' ? t('goNow') : t('seeBy', { date: fmtDate(c.at + 2 * DAY) });
      v.appendChild(h('div', { class: 'card alert ' + c.level }, [
        h('div', null, [h('span', { class: 'badge ' + c.level, text: t(c.level)[0] }), ' ', h('b', { text: whoName(c) })]),
        h('div', { class: 'when', text: fmtDate(c.at, true) }),
        c.reason ? h('div', { text: c.reason }) : null,
        h('div', { class: 'follow', text: follow }),
        h('div', { class: 'row-actions' }, [
          c.level === 'RED' ? h('a', { class: 'btn danger', href: 'tel:108' }, [icon('phone'), t('call108')]) : null,
          h('button', { class: 'btn', type: 'button', onclick: function () { openNearby('all'); } }, [icon('pin'), t('findHospital')]),
          h('button', { class: 'btn ghost', type: 'button', onclick: function () { c.done = true; save(); renderHome(); } }, [t('markDone')])
        ])
      ]));
    });

    // Family
    v.appendChild(h('h3', { text: t('family') }));
    if (!store.members.length) {
      v.appendChild(h('div', { class: 'card' }, [
        h('b', { text: t('onboardTitle') }),
        h('p', { class: 'muted small', text: t('onboardText') }),
        h('button', { class: 'btn primary block', type: 'button', onclick: function () { editMember(null); } }, [icon('plus'), t('addFamily')])
      ]));
    } else {
      var grid = h('div', { class: 'members' });
      store.members.forEach(function (m) {
        var last = lastCheckOf(m.id);
        grid.appendChild(h('button', { class: 'member', type: 'button', onclick: function () { startCheckFor(m.id); } }, [
          h('div', { class: 'top' }, [h('span', { class: 'avatar', text: (m.name || '?').trim().charAt(0).toUpperCase() }),
            h('div', null, [h('div', { class: 'name', text: m.name }), h('div', { class: 'meta', text: memberMeta(m) })])]),
          h('div', null, (m.conditions || []).slice(0, 3).map(function (c) { return h('span', { class: 'chip', text: t('c_' + c) }); })),
          h('div', { class: 'last' }, last
            ? [t('lastCheck') + ': ', h('span', { class: 'badge ' + last.level, text: t(last.level)[0] }), ' ' + fmtDate(last.at)]
            : [t('noCheckYet')])
        ]));
      });
      v.appendChild(grid);
    }

    // Recent checks
    v.appendChild(h('h3', { text: t('recent') }));
    var recent = store.checks.slice(-8).reverse();
    if (!recent.length) v.appendChild(h('p', { class: 'muted', text: t('noChecks') }));
    else v.appendChild(h('div', { class: 'card' }, [h('ul', { class: 'checklist' }, recent.map(function (c) {
      return h('li', null, [h('span', { class: 'badge ' + c.level, text: t(c.level)[0] }),
        h('div', { class: 'txt' }, [h('b', { text: whoName(c) }), h('span', { class: 'muted small', text: ' · ' + fmtDate(c.at, true) }),
          c.reason ? h('div', { class: 'reason', text: c.reason }) : null])]);
    }))]));

    v.appendChild(helplinesBlock());
    v.appendChild(h('p', { class: 'muted small', text: t('disclaimer') }));
  }

  function memberMeta(m) {
    var bits = [t('rel_' + (m.relation || 'other'))];
    if (m.age != null && m.age !== '') bits.push(t('yrs', { n: m.age }));
    if (m.pregnant) bits.push(t('pfPregnant'));
    return bits.join(' · ');
  }

  function helplinesBlock() {
    return h('div', null, [h('h3', { text: t('helplines') }), h('div', { class: 'helplines' }, HELPLINES.map(function (n) {
      return h('a', { class: 'helpline', href: 'tel:' + n }, [h('b', { text: n }), h('span', { text: t('hl' + n) })]);
    }))]);
  }

  /* =====================================================================
     SYMPTOM CHECK (chatbot)
     ===================================================================== */
  var chat = $('chat'), form = $('f'), input = $('m'), sendBtn = $('send'), micBtn = $('mic'), note = $('note'), whoSel = $('who');
  var history = [];      // [{role:'user'|'bot', text}] sent with every request
  var busy = false;      // true while a /chat request is in flight
  var started = false;   // has the user sent anything in this check?
  micBtn.appendChild(icon('mic'));

  function renderCheck() {
    // (Re)build the "checking for" list, keeping the current choice.
    var first = !whoSel.options.length, cur = whoSel.value;
    whoSel.textContent = '';
    store.members.forEach(function (m) { whoSel.appendChild(h('option', { value: m.id, text: m.name })); });
    whoSel.appendChild(h('option', { value: '', text: t('someoneElse') }));
    var keep = !first && (member(cur) || cur === '');
    whoSel.value = keep ? cur : (store.members[0] ? store.members[0].id : '');
    whoSel.disabled = busy;
    $('shareNote').hidden = !member(whoSel.value);
    if (!chat.children.length) resetChat();
    else if (!started) { chat.textContent = ''; showWelcome(); } // re-translate the welcome
  }

  function startCheckFor(id) {
    if (!member(id)) id = '';
    location.hash = '#check';
    renderCheck();
    whoSel.value = id;
    resetChat();
  }

  whoSel.addEventListener('change', function () { resetChat(); });

  function scrollDown() { chat.scrollTop = chat.scrollHeight; }

  function addBubble(text, who, opts) {
    opts = opts || {};
    var b = h('div', { class: 'bubble' + (opts.err ? ' err' : ''), text: text, lang: opts.lang || lang() });
    var wrap = h('div', null, [b, who === 'bot' ? listenButton(text, opts.lang || lang()) : null]);
    var row = h('div', { class: 'row ' + who }, [wrap]);
    chat.appendChild(row);
    scrollDown();
    return row;
  }

  function showWelcome() {
    var m = member(whoSel.value);
    addBubble(m ? t('welcomeFor', { name: m.name }) : t('welcome'), 'bot');
  }

  function resetChat() {
    stopSpeaking();
    history = [];
    started = false;
    chat.textContent = '';
    note.textContent = '';
    $('shareNote').hidden = !member(whoSel.value);
    showWelcome();
  }

  var typingRow = null;
  function showTyping(on) {
    if (on && !typingRow) {
      typingRow = h('div', { class: 'row bot typing' }, [h('div', { class: 'bubble' }, [t('typing'),
        h('span', { class: 'dots', 'aria-hidden': 'true' }, [h('span'), h('span'), h('span')])])]);
      chat.appendChild(typingRow);
      scrollDown();
    } else if (!on && typingRow) {
      typingRow.remove();
      typingRow = null;
    }
  }

  function setBusy(on) {
    busy = on;
    sendBtn.disabled = on;
    micBtn.disabled = on;
    whoSel.disabled = on;
    showTyping(on);
  }

  // Only medical facts go to the server (no name / phone / notes).
  function profileFor(m) {
    if (!m) return undefined;
    var conds = (m.conditions || []).map(function (c) { return COND_EN[c]; }).filter(Boolean);
    (m.other || '').split(',').forEach(function (s) { s = s.trim(); if (s) conds.push(s); });
    var p = { conditions: conds, allergies: m.allergies || '', medicines: m.medicines || '' };
    if (m.age !== '' && m.age != null && !isNaN(+m.age)) p.age = +m.age;
    if (m.sex) p.sex = m.sex;
    if (m.pregnant) p.pregnant = true;
    return p;
  }

  async function fetchJSON(url, opts, timeoutMs) {
    var ctrl = window.AbortController ? new AbortController() : null;
    var timer = ctrl ? setTimeout(function () { ctrl.abort(); }, timeoutMs) : null;
    try {
      var res = await fetch(url, Object.assign({}, opts || {}, { signal: ctrl ? ctrl.signal : undefined }));
      var data = await res.json();
      return { ok: res.ok, data: data };
    } finally {
      clearTimeout(timer);
    }
  }

  async function send(text) {
    text = (text || '').trim();
    if (!text || busy) return;
    var code = lang();
    var m = member(whoSel.value);
    input.value = '';
    note.textContent = '';
    started = true;
    addBubble(text, 'user', { lang: code });
    setBusy(true);

    var data = null;
    try {
      var r = await fetchJSON('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, language: code, history: history, profile: profileFor(m) })
      }, CHAT_TIMEOUT_MS);
      data = r.data;
    } catch (e) {
      data = null; // offline, timeout, or non-JSON server error
    }
    setBusy(false);

    if (!data || !data.type) {
      // Network failure: friendly message, keep the text so one tap on Send retries.
      addBubble(t('offline', null, code), 'bot', { err: true, lang: code });
      input.value = text;
      return;
    }
    if (data.type === 'final') {
      var rec = saveCheck(data, m);
      showResult(data, code, m, rec);
      history = []; // conversation is over
    } else if (data.type === 'question') {
      addBubble(data.reply || '…', 'bot', { lang: code });
      history.push({ role: 'user', text: text });
      history.push({ role: 'bot', text: data.reply || '' });
    } else {
      // type "error" (or anything unexpected): show the reply as a bubble.
      addBubble(data.reply || t('offline', null, code), 'bot', { err: true, lang: code });
      history.push({ role: 'user', text: text });
    }
  }

  function levelOf(o) { return (o.level === 'RED' || o.level === 'AMBER' || o.level === 'GREEN') ? o.level : 'AMBER'; }

  function saveCheck(o, m) {
    var rec = { id: uid(), memberId: m ? m.id : '', at: Date.now(), level: levelOf(o),
      reason: (o.reason || o.reply || '').trim(), advice: (o.advice || '').trim(),
      symptoms: Array.isArray(o.symptoms_en) ? o.symptoms_en.slice(0, 12) : [], done: false };
    store.checks.push(rec);
    if (store.checks.length > 200) store.checks = store.checks.slice(-200);
    save();
    return rec;
  }

  // Full-width coloured result card for a "final" response.
  function showResult(o, code, m, rec) {
    var level = levelOf(o);
    var L = T[code] || T.en;
    var card = h('section', { class: 'result ' + level, lang: code }, [
      h('div', { class: 'level', text: L[level][0] }),
      h('div', { class: 'meaning', text: L[level][1] })
    ]);
    // The hard-coded RED path sends identical reply/reason/advice; show each distinct text once.
    var reply = (o.reply || '').trim(), reason = (o.reason || '').trim(), advice = (o.advice || '').trim();
    var showReply = reply && reply !== reason && reply !== advice;
    if (showReply) card.appendChild(h('div', { class: 'text', text: reply }));
    if (reason) { card.appendChild(h('div', { class: 'label', text: L.why })); card.appendChild(h('div', { class: 'text', text: reason })); }
    if (advice && advice !== reason) { card.appendChild(h('div', { class: 'label', text: L.todo })); card.appendChild(h('div', { class: 'text', text: advice })); }
    card.appendChild(listenButton([L[level][1], showReply ? reply : '', reason, advice !== reason ? advice : ''].filter(Boolean).join('. '), code));

    if (level !== 'GREEN') {
      card.appendChild(h('a', { class: 'call', href: 'tel:108' }, [icon('phone'), h('span', { text: L.call108 })]));
      card.appendChild(h('div', { class: 'row-actions' }, [
        h('button', { class: 'btn', type: 'button', onclick: function () { openNearby('all'); } }, [icon('pin'), L.findHospital])
      ]));
      card.appendChild(alertBox(rec, m, code));
    }
    if (m) card.appendChild(h('div', { class: 'saved', text: t('savedTo', { name: m.name }, code) }));
    chat.appendChild(card);
    chat.appendChild(h('button', { class: 'btn block', type: 'button', style: 'margin:4px 0 12px', onclick: resetChat }, [t('newCheck', null, code)]));
    scrollDown();
  }

  /* ---------- Alert the emergency contact (opens SMS / WhatsApp; the user presses send) ---------- */
  function alertText(rec, m, code) {
    var word = t(rec.level, null, code)[0];
    var msg = t('alertMsg', { name: m ? m.name : t('someoneElse', null, code),
      level: word === rec.level ? word : word + ' (' + rec.level + ')', reason: rec.reason }, code);
    var loc = store.lastLoc;
    if (loc && Date.now() - loc.at < DAY) msg += '\n' + t('alertLoc', null, code) + ': https://maps.google.com/?q=' + loc.lat.toFixed(5) + ',' + loc.lon.toFixed(5);
    return msg + '\n– ' + t('appName', null, code);
  }
  function waNumber(phone) {
    var d = (phone || '').replace(/\D/g, '');
    if (d.length === 10) return '91' + d;
    if (d.length === 11 && d.charAt(0) === '0') return '91' + d.slice(1);
    return d;
  }
  function alertBox(rec, m, code) {
    var c = store.contact || {};
    if (!c.phone) {
      return h('div', { class: 'alertbox' }, [h('button', { class: 'btn', type: 'button',
        onclick: function () { location.hash = '#family'; } }, [icon('plus'), t('addContact', null, code)])]);
    }
    var box = h('div', { class: 'alertbox' });
    function fill() {
      var msg = encodeURIComponent(alertText(rec, m, code));
      box.textContent = '';
      box.appendChild(h('div', { class: 'lbl', text: t('alertFamily', { name: c.name || c.phone }, code) }));
      box.appendChild(h('div', { class: 'row-actions' }, [
        h('a', { class: 'btn', href: 'sms:' + c.phone.replace(/[^\d+]/g, '') + '?body=' + msg }, [icon('sms'), 'SMS']),
        h('a', { class: 'btn', href: 'https://wa.me/' + waNumber(c.phone) + '?text=' + msg, target: '_blank', rel: 'noopener' }, ['WhatsApp'])
      ]));
    }
    fill();
    // If location permission was already given, add a fresh location link to the alert (no new prompt).
    if (navigator.permissions && navigator.geolocation) {
      navigator.permissions.query({ name: 'geolocation' }).then(function (p) {
        if (p.state !== 'granted') return;
        navigator.geolocation.getCurrentPosition(function (pos) {
          store.lastLoc = { lat: pos.coords.latitude, lon: pos.coords.longitude, at: Date.now() };
          save();
          fill();
        }, function () {}, { timeout: 10000, maximumAge: 600000 });
      }).catch(function () {});
    }
    return box;
  }

  form.addEventListener('submit', function (e) { e.preventDefault(); send(input.value); });

  /* ---------- Voice input (Web Speech API) ---------- */
  var Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  var rec = null;
  if (Recognition) {
    micBtn.hidden = false;
    micBtn.addEventListener('click', function () {
      if (rec) { rec.stop(); return; } // second tap stops listening
      if (busy) return;
      stopSpeaking();
      try { rec = new Recognition(); } catch (e) { micBtn.hidden = true; return; }
      rec.lang = SPEECH_LANG[lang()] || 'en-IN';
      rec.interimResults = false;
      rec.maxAlternatives = 1;
      rec.onstart = function () { micBtn.classList.add('on'); note.textContent = t('listening'); };
      rec.onresult = function (ev) {
        var said = ev.results[0][0].transcript;
        input.value = said;
        note.textContent = '';
        send(said);
      };
      rec.onerror = function (ev) {
        if (ev.error === 'not-allowed' || ev.error === 'service-not-allowed') note.textContent = t('micDenied');
        else if (ev.error !== 'aborted') note.textContent = t('micNoSpeech');
      };
      rec.onend = function () {
        micBtn.classList.remove('on');
        if (note.textContent === t('listening')) note.textContent = '';
        rec = null;
      };
      try { rec.start(); } catch (e) { rec = null; }
    });
  }

  /* ---------- "Listen" button (speechSynthesis) ---------- */
  var synth = window.speechSynthesis || null;
  function voiceFor(code) {
    if (!synth) return null;
    var want = (SPEECH_LANG[code] || 'en-IN').toLowerCase();
    var voices = synth.getVoices();
    var norm = function (v) { return (v.lang || '').replace('_', '-').toLowerCase(); };
    return voices.find(function (v) { return norm(v) === want; }) ||
           voices.find(function (v) { return norm(v).split('-')[0] === code; }) || null;
  }
  function listenButton(text, code) {
    var b = h('button', { class: 'listen', type: 'button', 'data-lang': code }, [icon('speaker'), h('span', { text: t('listen', null, code) })]);
    b.hidden = !voiceFor(code); // only offer it when the phone can speak this language
    b.addEventListener('click', function () {
      var v = voiceFor(code);
      if (!v) return;
      synth.cancel();
      var u = new SpeechSynthesisUtterance(text);
      u.voice = v; u.lang = v.lang; u.rate = 0.9;
      synth.speak(u);
    });
    return b;
  }
  function refreshListenButtons() {
    document.querySelectorAll('.listen').forEach(function (b) { b.hidden = !voiceFor(b.dataset.lang); });
  }
  function stopSpeaking() { if (synth) synth.cancel(); }
  if (synth && 'onvoiceschanged' in synth) synth.addEventListener('voiceschanged', refreshListenButtons);

  /* =====================================================================
     NEARBY HEALTH FACILITIES
     ===================================================================== */
  var near = { status: 'idle', choices: [], filter: 'all', query: '' };

  function openNearby(filter) {
    near.filter = filter || 'all';
    go('near');
    if (!store.places && near.status !== 'locating' && near.status !== 'loading') locate();
  }

  function setNear(status, extra) {
    near.status = status;
    for (var k in (extra || {})) near[k] = extra[k];
    if (currentTab() === 'near') renderNear();
  }

  function locate() {
    if (!navigator.geolocation) { setNear('error', { msg: 'locErr' }); return; }
    setNear('locating', { choices: [] });
    navigator.geolocation.getCurrentPosition(function (pos) {
      store.lastLoc = { lat: pos.coords.latitude, lon: pos.coords.longitude, at: Date.now() };
      save();
      loadPlaces(pos.coords.latitude, pos.coords.longitude, '');
    }, function () {
      setNear('error', { msg: 'locErr' });
    }, { enableHighAccuracy: false, timeout: 15000, maximumAge: 600000 });
  }

  async function searchPlace(q) {
    q = (q || '').trim();
    near.query = q;
    if (!q) return;
    setNear('loading', { choices: [] });
    try {
      var r = await fetchJSON('/geocode?q=' + encodeURIComponent(q) + '&lang=' + lang(), null, 20000);
      var res = (r.data && r.data.results) || [];
      if (!res.length) setNear('error', { msg: 'locErr' });
      else if (res.length === 1) loadPlaces(res[0].lat, res[0].lon, res[0].name);
      else setNear('choose', { choices: res });
    } catch (e) {
      setNear('error', { msg: 'nearErr' });
    }
  }

  async function loadPlaces(lat, lon, label) {
    setNear('loading', { choices: [] });
    try {
      var r = await fetchJSON('/places?lat=' + lat.toFixed(5) + '&lon=' + lon.toFixed(5), null, PLACES_TIMEOUT_MS);
      if (!r.ok || !r.data || !Array.isArray(r.data.places)) throw new Error('bad response');
      store.places = { at: Date.now(), lat: lat, lon: lon, label: label || '', list: r.data.places, radius_km: r.data.radius_km };
      save();
      setNear('done');
    } catch (e) {
      setNear('error', { msg: 'nearErr' }); // a previously saved list (if any) is still shown below
    }
  }

  function firstPhone(p) { return (p || '').split(/[;,/]/)[0].replace(/[^\d+]/g, ''); }

  function renderNear() {
    var v = $('view-near');
    v.textContent = '';
    v.appendChild(h('h2', { text: t('nearTitle') }));
    var busyNow = near.status === 'locating' || near.status === 'loading';

    v.appendChild(h('button', { class: 'btn primary big', type: 'button', disabled: busyNow, onclick: locate }, [icon('target'), t('useLoc')]));
    var q = h('input', { type: 'text', id: 'placeq', placeholder: t('orType'), 'aria-label': t('orType'), enterkeyhint: 'search' });
    q.value = near.query;
    v.appendChild(h('form', { class: 'searchrow', onsubmit: function (e) { e.preventDefault(); searchPlace(q.value); } },
      [q, h('button', { class: 'btn', type: 'submit', disabled: busyNow, text: t('search') })]));

    // Status line
    var msg = near.status === 'locating' ? t('locating') : near.status === 'loading' ? t('loading')
      : near.status === 'error' ? t(near.msg) : '';
    if (msg) v.appendChild(h('p', { class: 'status' + (near.status === 'error' ? ' err' : ''), role: 'status', text: msg }));

    // Choose between several matching places
    if (near.status === 'choose') {
      v.appendChild(h('p', { class: 'status', text: t('pickPlace') }));
      v.appendChild(h('div', { class: 'choices' }, near.choices.map(function (c) {
        return h('button', { class: 'btn', type: 'button', text: c.name, onclick: function () { loadPlaces(c.lat, c.lon, c.name); } });
      })));
    }

    var P = store.places;
    if (P && P.list) {
      var head = P.label ? t('nearFor', { place: P.label.split(',').slice(0, 2).join(',') }) : t('myLocation');
      var stale = Date.now() - P.at > 6 * 3600000;
      v.appendChild(h('p', { class: 'muted small', text: head + (stale || near.status === 'error' ? ' · ' + t('savedList', { date: fmtDate(P.at, true) }) : '') }));

      v.appendChild(h('div', { class: 'filters', role: 'group' }, FILTERS.map(function (f) {
        var n = f[0] === 'all' ? P.list.length : P.list.filter(function (p) { return p.kind === f[0]; }).length;
        return h('button', { type: 'button', 'aria-pressed': String(near.filter === f[0]),
          onclick: function () { near.filter = f[0]; renderNear(); } }, [t(f[1]) + ' (' + n + ')']);
      })));

      var list = P.list.filter(function (p) { return near.filter === 'all' || p.kind === near.filter; });
      if (!list.length && near.filter !== 'ngo') v.appendChild(h('p', { class: 'muted', text: t('none') }));
      list.forEach(function (p) {
        var phone = firstPhone(p.phone);
        v.appendChild(h('div', { class: 'card place ' + p.kind }, [
          h('div', { class: 'head' }, [
            h('div', null, [h('div', { class: 'pname', text: p.name }), p.local_name ? h('div', { class: 'local', text: p.local_name, lang: 'kn' }) : null]),
            h('span', { class: 'dist', text: t('km', { n: p.distance_km }) })
          ]),
          h('div', { class: 'kind' }, [t('s_' + p.sub), p.emergency ? ' ' : null, p.emergency ? h('span', { class: 'badge em', text: t('emergency24') }) : null]),
          p.address ? h('div', { class: 'addr', text: p.address }) : null,
          h('div', { class: 'row-actions' }, [
            phone ? h('a', { class: 'btn', href: 'tel:' + phone }, [icon('phone'), t('callPlace')]) : null,
            h('a', { class: 'btn primary', target: '_blank', rel: 'noopener',
              href: 'https://www.google.com/maps/dir/?api=1&destination=' + p.lat + ',' + p.lon }, [icon('route'), t('directions')])
          ])
        ]));
      });
      if (near.filter === 'ngo' || near.filter === 'all') v.appendChild(h('p', { class: 'muted small', text: t('ngoNote') }));
      v.appendChild(h('p', { class: 'muted small', text: t('nearNote') }));
    } else if (near.status === 'idle') {
      v.appendChild(h('p', { class: 'muted small', text: t('nearNote') }));
    }
    v.appendChild(helplinesBlock());
  }

  /* =====================================================================
     FAMILY PROFILES
     ===================================================================== */
  var fam = { editing: undefined, confirm: null, flash: '' }; // editing: undefined = list, null = new, id = edit

  function editMember(id) {
    fam.editing = id;
    go('family');
  }

  function renderFamily() {
    var v = $('view-family');
    v.textContent = '';
    if (fam.editing !== undefined) { v.appendChild(memberForm(fam.editing === null ? null : member(fam.editing))); v.scrollTop = 0; return; }

    v.appendChild(h('h2', { text: t('navFamily') }));
    v.appendChild(h('p', { class: 'muted small', text: t('pfPrivacy') }));

    // Emergency contact
    var cName = h('input', { type: 'text', id: 'cname', autocomplete: 'name' }); cName.value = store.contact.name || '';
    var cPhone = h('input', { type: 'tel', id: 'cphone', inputmode: 'tel', autocomplete: 'tel' }); cPhone.value = store.contact.phone || '';
    v.appendChild(h('form', { class: 'card', onsubmit: function (e) {
      e.preventDefault();
      store.contact = { name: cName.value.trim().slice(0, 60), phone: cPhone.value.trim().slice(0, 20) };
      save();
      fam.flash = 'contact';
      renderFamily();
    } }, [
      h('b', { text: t('pfContact') }),
      h('p', { class: 'muted small', text: t('pfContactHint') }),
      h('div', { class: 'two' }, [
        h('div', { class: 'field' }, [h('label', { for: 'cname', text: t('pfContactName') }), cName]),
        h('div', { class: 'field' }, [h('label', { for: 'cphone', text: t('pfContactPhone') }), cPhone])
      ]),
      h('div', null, [h('button', { class: 'btn primary', type: 'submit', text: t('save') }),
        fam.flash === 'contact' ? h('span', { class: 'flash', text: '✓ ' + t('saved') }) : null])
    ]));
    fam.flash = '';

    // Members
    v.appendChild(h('h3', { text: t('pfMembers') }));
    store.members.forEach(function (m) {
      var confirming = fam.confirm === m.id;
      v.appendChild(h('div', { class: 'card' }, [
        h('div', { class: 'mrow' }, [
          h('span', { class: 'avatar', text: (m.name || '?').trim().charAt(0).toUpperCase() }),
          h('div', { class: 'txt' }, [h('div', { class: 'name', text: m.name }), h('div', { class: 'muted small', text: memberMeta(m) })])
        ]),
        h('div', null, (m.conditions || []).map(function (c) { return h('span', { class: 'chip', text: t('c_' + c) }); })),
        h('div', { class: 'row-actions' }, [
          h('button', { class: 'btn primary', type: 'button', onclick: function () { startCheckFor(m.id); } }, [icon('chat'), t('navCheck')]),
          h('button', { class: 'btn', type: 'button', onclick: function () { editMember(m.id); } }, [icon('edit'), t('edit')]),
          h('button', { class: 'btn danger', type: 'button', onclick: function () {
            if (!confirming) { fam.confirm = m.id; renderFamily(); return; }
            store.members = store.members.filter(function (x) { return x.id !== m.id; });
            store.checks = store.checks.filter(function (c) { return c.memberId !== m.id; });
            fam.confirm = null; save(); renderFamily();
          } }, [confirming ? t('confirmDel') : t('del')])
        ])
      ]));
    });
    v.appendChild(h('button', { class: 'btn primary big', type: 'button', onclick: function () { editMember(null); } }, [icon('plus'), t('pfAdd')]));

    // Wipe everything (two taps)
    var wiping = fam.confirm === '__all';
    v.appendChild(h('p', { style: 'margin-top:28px' }, [h('button', { class: 'btn danger', type: 'button', onclick: function () {
      if (!wiping) { fam.confirm = '__all'; renderFamily(); return; }
      var keepLang = store.lang;
      store = blankStore(); store.lang = keepLang; save();
      fam.confirm = null; resetChat(); renderFamily();
    } }, [wiping ? t('confirmDel') : t('pfWipe')])]));
  }

  function memberForm(m) {
    m = m || { name: '', relation: store.members.length ? 'other' : 'self', age: '', sex: '', pregnant: false, conditions: [], other: '', allergies: '', medicines: '', notes: '' };
    function field(id, labelKey, el) { el.id = id; return h('div', { class: 'field' }, [h('label', { for: id, text: t(labelKey) }), el]); }
    function text(val, max) { var i = h('input', { type: 'text', maxlength: max || 120 }); i.value = val || ''; return i; }

    var name = text(m.name, 60);
    var rel = h('select', null, RELATIONS.map(function (r) { return h('option', { value: r, text: t('rel_' + r) }); })); rel.value = m.relation || 'other';
    var age = h('input', { type: 'number', min: 0, max: 120, inputmode: 'numeric' }); age.value = m.age != null ? m.age : '';
    var sex = h('select', null, [['', '—'], ['female', t('female')], ['male', t('male')], ['other', t('other')]].map(function (o) {
      return h('option', { value: o[0], text: o[1] });
    })); sex.value = m.sex || '';
    var preg = h('input', { type: 'checkbox', id: 'fpreg' }); preg.checked = !!m.pregnant;
    var pregWrap = h('div', { class: 'field checks' }, [h('label', { for: 'fpreg' }, [preg, t('pfPregnant')])]);
    function syncPreg() { pregWrap.hidden = sex.value !== 'female'; }
    sex.addEventListener('change', syncPreg); syncPreg();

    var condBoxes = CONDITIONS.map(function (c) {
      var cb = h('input', { type: 'checkbox', value: c }); cb.checked = (m.conditions || []).indexOf(c) >= 0;
      return h('label', null, [cb, t('c_' + c)]);
    });
    var other = text(m.other, 200), allergies = text(m.allergies, 200), meds = text(m.medicines, 200);
    var notes = h('textarea', { maxlength: 500 }); notes.value = m.notes || '';
    var err = h('p', { class: 'err-text', role: 'alert' });

    return h('form', { onsubmit: function (e) {
      e.preventDefault();
      if (!name.value.trim()) { err.textContent = t('nameRequired'); name.focus(); return; }
      var a = age.value === '' ? '' : Math.max(0, Math.min(120, Math.round(+age.value)));
      var rec = { id: m.id || uid(), name: name.value.trim(), relation: rel.value, age: a, sex: sex.value,
        pregnant: sex.value === 'female' && preg.checked,
        conditions: condBoxes.map(function (l) { return l.firstChild; }).filter(function (cb) { return cb.checked; }).map(function (cb) { return cb.value; }),
        other: other.value.trim(), allergies: allergies.value.trim(), medicines: meds.value.trim(), notes: notes.value.trim() };
      var i = store.members.findIndex(function (x) { return x.id === rec.id; });
      if (i >= 0) store.members[i] = rec; else store.members.push(rec);
      save();
      fam.editing = undefined;
      renderFamily();
    } }, [
      h('h2', { text: m.id ? m.name : t('pfAdd') }),
      field('fname', 'pfName', name),
      h('div', { class: 'two' }, [field('frel', 'pfRelation', rel), field('fage', 'pfAge', age)]),
      field('fsex', 'pfSex', sex),
      pregWrap,
      h('div', { class: 'field' }, [h('span', { class: 'lbl', text: t('pfConditions') }), h('div', { class: 'checks' }, condBoxes)]),
      field('fother', 'pfOther', other),
      field('fall', 'pfAllergies', allergies),
      field('fmeds', 'pfMeds', meds),
      field('fnotes', 'pfNotes', notes),
      err,
      h('div', { class: 'row-actions' }, [
        h('button', { class: 'btn primary', type: 'submit', text: t('save') }),
        h('button', { class: 'btn', type: 'button', text: t('cancel'), onclick: function () { fam.editing = undefined; renderFamily(); } })
      ])
    ]);
  }

  /* =====================================================================
     START
     ===================================================================== */
  document.querySelectorAll('[data-icon]').forEach(function (s) { s.appendChild(icon(s.getAttribute('data-icon'))); });
  langSel.value = T[store.lang] ? store.lang : DEFAULT_LANG;
  langSel.addEventListener('change', function () {
    stopSpeaking();
    applyLanguage();
    route();               // re-render the visible view in the new language
    refreshListenButtons();
  });
  applyLanguage();
  route();
})();
