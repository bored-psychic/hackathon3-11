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
  var STORE_KEY = 'triage-app-v1';    // per number: STORE_KEY + ':' + phone
  var SESSION_KEY = 'triage-session-v1'; // demo sign-in: { phone }
  var DEMO_CODE = '123456';
  var DAY = 86400000;
  var APPROX_M = 3000;                // a location fix worse than this is "approximate" (Wi-Fi / IP based)

  var CONDITIONS = ['diabetes', 'bp', 'heart', 'lung', 'kidney', 'tb', 'epilepsy'];
  var COND_EN = { diabetes: 'diabetes', bp: 'high blood pressure', heart: 'heart disease',
    lung: 'asthma or lung disease', kidney: 'kidney disease', tb: 'tuberculosis', epilepsy: 'epilepsy (fits)' };
  var RELATIONS = ['self', 'spouse', 'child', 'parent', 'grandparent', 'sibling', 'other'];
  var HELPLINES = ['108', '112', '104', '14416'];
  var FILTERS = [['all', 'fAll'], ['govt', 'fGovt'], ['hospital', 'fHospital'], ['clinic', 'fClinic'], ['ngo', 'fNgo']];
  var AVATAR_COLORS = ['#0F766E', '#1565c0', '#6a1b9a', '#c2185b', '#b45309', '#00838f'];
  var KIND_COLORS = { govt: '#0F766E', hospital: '#c62828', clinic: '#1565c0', ngo: '#6a1b9a' };

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
    cross: '<path d="M9.5 3h5v6.5H21v5h-6.5V21h-5v-6.5H3v-5h6.5z"/>',
    edit: '<path d="M3 17.25V21h3.75L17.8 9.94l-3.75-3.75L3 17.25zM20.7 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/>',
    target: '<path d="M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zm9 3h-2.1A7 7 0 0 0 13 5.1V3h-2v2.1A7 7 0 0 0 5.1 11H3v2h2.1a7 7 0 0 0 5.9 5.9V21h2v-2.1a7 7 0 0 0 5.9-5.9H21v-2zm-9 6a5 5 0 1 1 0-10 5 5 0 0 1 0 10z"/>',
    sms: '<path d="M20 2H4a2 2 0 0 0-2 2v18l4-4h14a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2zM9 11H7V9h2v2zm4 0h-2V9h2v2zm4 0h-2V9h2v2z"/>',
    bell: '<path d="M12 22a2 2 0 0 0 2-2h-4a2 2 0 0 0 2 2zm6-6v-5a6 6 0 0 0-5-5.9V4a1 1 0 0 0-2 0v1.1A6 6 0 0 0 6 11v5l-2 2v1h16v-1l-2-2z"/>',
    clock: '<path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm1 11H8v-2h3V6h2v7z"/>'
  };
  function icon(name) {
    var s = document.createElement('span');
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
  var phone = null;   // signed-in mobile number (10 digits). It stays on this phone: never sent anywhere.
  var sessionId = 0;  // bumped on every sign-in/out so a late reply cannot write into another number's store
  function storeKey() { return STORE_KEY + ':' + phone; }
  function loadStore() {
    var s = null;
    if (phone) { try { s = JSON.parse(localStorage.getItem(storeKey())); } catch (e) {} }
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
  function save() { if (!phone) return; try { localStorage.setItem(storeKey(), JSON.stringify(store)); } catch (e) {} }
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
  function fmtDate(ts, opts) {
    try { return new Date(ts).toLocaleString(SPEECH_LANG[lang()] || 'en-IN', opts); } catch (e) { return new Date(ts).toDateString(); }
  }
  function shortDate(ts) { return fmtDate(ts, { day: 'numeric', month: 'short' }); }
  function dateTime(ts) { return fmtDate(ts, { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' }); }
  function fmtKm(km) { return km < 10 ? km.toFixed(1) : String(Math.round(km)); }

  /* ---------- Language auto-detection ----------
     1) Native script in what was typed / heard (ಕನ್ನಡ, हिन्दी, …) -> that language, before sending.
     2) The server also reports the language of each message (catches "mujhe bukhar hai" typed in English letters).
     Either way the app, the replies and the next mic session switch to that language. */
  var SCRIPTS = [['kn', /[ಀ-೿]/g], ['hi', /[ऀ-ॿ]/g], ['ta', /[஀-௿]/g],
    ['te', /[ఀ-౿]/g], ['ml', /[ഀ-ൿ]/g]];
  function detectScript(text) {
    var best = null, most = 0;
    SCRIPTS.forEach(function (s) {
      var n = (text.match(s[1]) || []).length;
      if (n > most) { most = n; best = s[0]; }
    });
    return most >= 2 ? best : null; // English letters: leave it to the server
  }
  function langName(code) {
    var o = langSel.querySelector('option[value="' + code + '"]');
    return code === 'en' ? 'English' : (o ? o.textContent : code);
  }
  function switchLang(code, noteEl) {
    if (!T[code] || code === lang()) return false;
    langSel.value = code;
    applyLanguage();
    refreshListenButtons();
    if (noteEl) noteEl.textContent = t('langSwitched', { lang: langName(code) });
    return true;
  }
  // First visit: use the phone's language if we support it, else Kannada.
  function initialLang() {
    if (T[store.lang]) return store.lang;
    var prefs = navigator.languages || [navigator.language || ''];
    for (var i = 0; i < prefs.length; i++) {
      var c = String(prefs[i] || '').slice(0, 2).toLowerCase();
      if (T[c] && c !== 'en') return c;
    }
    return DEFAULT_LANG;
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
    try { localStorage.setItem('triage-lang', code); } catch (e) {} // language only, so the login screen and new numbers follow it
    updateAcct();
    save();
  }

  /* ---------- Small shared pieces ---------- */
  function colorFor(id) {
    var n = 0;
    for (var i = 0; i < (id || '').length; i++) n += id.charCodeAt(i);
    return AVATAR_COLORS[n % AVATAR_COLORS.length];
  }
  function avatar(m) {
    return h('span', { class: 'avatar', style: 'background:' + colorFor(m.id), text: (m.name || '?').trim().charAt(0).toUpperCase() });
  }
  function sectionTitle(ic, text) { return h('h3', { class: 'sec' }, [icon(ic), text]); }
  function memberMeta(m) {
    var bits = [t('rel_' + (m.relation || 'other'))];
    if (m.age != null && m.age !== '') bits.push(t('yrs', { n: m.age }));
    if (m.pregnant) bits.push(t('pfPregnant'));
    return bits.join(' · ');
  }
  function helplinesBlock() {
    return h('div', null, [sectionTitle('phone', t('helplines')), h('div', { class: 'helplines' }, HELPLINES.map(function (n) {
      return h('a', { class: 'helpline', href: 'tel:' + n }, [h('span', { class: 'hl-ico' }, [icon('phone')]),
        h('span', null, [h('b', { text: n }), h('span', { class: 'lbl', text: t('hl' + n) })])]);
    }))]);
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

  /* ---------- Demo sign-in (no SMS, no server; each number keeps its own data on this phone) ---------- */
  var login = { step: 'phone', num: '', err: '' };
  function readSession() {
    try { var x = JSON.parse(localStorage.getItem(SESSION_KEY)); return x && /^\d{10}$/.test(x.phone) ? x.phone : null; } catch (e) { return null; }
  }
  function updateAcct() {
    var b = $('acct');
    b.hidden = !phone;
    if (!phone) return;
    b.textContent = '•••• ' + phone.slice(-4);
    b.setAttribute('aria-label', t('switchNumber') + ': •••• ' + phone.slice(-4));
  }
  // Forget everything in memory that belongs to the previous number (chat, nearby search, forms).
  function resetSessionState() {
    if (activeRec) activeRec.stop();
    stopSpeaking();
    history = []; started = false; busy = false; typingRow = null;
    chat.textContent = ''; note.textContent = ''; whoSel.textContent = '';
    sendBtn.disabled = false; micBtn.disabled = false; whoSel.disabled = false;
    near = { status: 'idle', choices: [], filter: 'all', query: '', where: null, spec: '' };
    fam = { editing: undefined, confirm: null, flash: '' };
  }
  function signIn(p) {
    try {
      var key = STORE_KEY + ':' + p;
      if (localStorage.getItem(key) == null) { // the pre-login single store moves to the FIRST number only, then is deleted
        var old = localStorage.getItem(STORE_KEY);
        if (old != null) { localStorage.setItem(key, old); localStorage.removeItem(STORE_KEY); }
      }
      localStorage.setItem(SESSION_KEY, JSON.stringify({ phone: p }));
    } catch (e) {} // storage blocked: still works for this visit, in memory
    sessionId++;
    resetSessionState();
    phone = p;
    store = loadStore();
    login = { step: 'phone', num: '', err: '' };
    if (T[store.lang]) langSel.value = store.lang;
    applyLanguage();
    go('home');
  }
  function signOut() {
    try { localStorage.removeItem(SESSION_KEY); } catch (e) {}
    sessionId++;
    resetSessionState();
    phone = null;
    store = loadStore(); // blank, language only
    route();
  }

  // Split screen: the art panel (3D form, logo, big title) is built once and kept; only the card pane is re-rendered.
  function loginPane() {
    var v = $('view-login'), split = v.querySelector('.login-split');
    if (!split) {
      v.textContent = '';
      var logo = icon('cross');
      logo.setAttribute('class', 'login-logo');
      split = h('div', { class: 'login-split' }, [
        h('aside', { class: 'login-art', 'aria-hidden': 'true' }, [
          h('div', { class: 'fx-host login-fx' }, [h('div', { class: 'fx-fallback' })]),
          logo,
          h('div', { class: 'login-copy' }, [h('p', { class: 'display', id: 'loginDisplay' }), h('p', { class: 'display-sub', id: 'loginDisplaySub' })])
        ]),
        h('div', { class: 'login-pane' })
      ]);
      v.appendChild(split);
    }
    $('loginDisplay').textContent = t('appName');
    $('loginDisplaySub').textContent = t('heroSub');
    var pane = split.querySelector('.login-pane');
    pane.textContent = '';
    return pane;
  }

  function renderLogin() {
    var pane = loginPane();
    function digitsOnly(el) { el.value = el.value.replace(/\D/g, ''); }
    var demo = h('p', { class: 'demochip', text: t('demoCode') });
    var err = h('p', { class: 'err-text', role: 'alert', text: login.err });
    var first;
    if (login.step === 'phone') {
      var ph = first = h('input', { type: 'tel', id: 'lph', inputmode: 'numeric', autocomplete: 'tel-national', maxlength: 10 });
      ph.value = login.num;
      ph.addEventListener('input', function () { digitsOnly(ph); login.num = ph.value; });
      pane.appendChild(h('form', { class: 'card loginbox', onsubmit: function (e) {
        e.preventDefault();
        if (!/^\d{10}$/.test(ph.value)) { login.err = t('badPhone'); err.textContent = login.err; ph.focus(); return; }
        login.num = ph.value; login.step = 'code'; login.err = ''; renderLogin();
      } }, [
        h('h2', { text: t('loginTitle') }),
        h('p', { class: 'muted', text: t('loginSub') }),
        h('div', { class: 'field' }, [h('label', { for: 'lph', text: t('mobile') }),
          h('div', { class: 'phonerow' }, [h('span', { class: 'prefix', text: '+91' }), ph])]),
        err,
        h('button', { class: 'btn primary big', type: 'submit', text: t('sendCode') }),
        demo
      ]));
    } else {
      // Six visual cells mirror one real input (so autofill of one-time codes keeps working).
      var code = first = h('input', { type: 'text', id: 'lcode', inputmode: 'numeric', autocomplete: 'one-time-code', maxlength: 6 });
      var cells = [0, 1, 2, 3, 4, 5].map(function () { return h('span'); });
      var paint = function () {
        digitsOnly(code);
        cells.forEach(function (c, i) {
          c.textContent = code.value.charAt(i);
          c.classList.toggle('cur', i === Math.min(code.value.length, 5));
        });
      };
      code.addEventListener('input', paint);
      paint();
      var wrap = h('div', { class: 'codewrap' }, [h('div', { class: 'cells', 'aria-hidden': 'true' }, cells), code]);
      pane.appendChild(h('form', { class: 'card loginbox', onsubmit: function (e) {
        e.preventDefault();
        if (code.value !== DEMO_CODE) { err.textContent = t('badCode'); code.focus(); return; }
        signIn(login.num);
      } }, [
        h('button', { class: 'linkbtn', type: 'button', text: '← ' + t('changeNumber'),
          onclick: function () { login.step = 'phone'; login.err = ''; renderLogin(); } }),
        h('h2', { text: t('codeTitle') }),
        h('p', { class: 'muted', text: t('codeSent', { num: login.num.slice(0, 5) + ' ' + login.num.slice(5) }) }),
        h('div', { class: 'field' }, [h('label', { for: 'lcode', text: t('codeLbl') }), wrap]),
        err,
        h('button', { class: 'btn primary big', type: 'submit', text: t('verify') }),
        demo
      ]));
    }
    setTimeout(function () { if (first.isConnected && !first.disabled) first.focus(); }, 0);
  }

  /* ---------- Router: #home | #check | #near | #family ---------- */
  var VIEWS = { home: renderHome, check: renderCheck, near: renderNear, family: renderFamily };
  function currentTab() {
    var tab = (location.hash || '#home').slice(1);
    return VIEWS[tab] ? tab : 'home';
  }
  function route() {
    var tab = currentTab();
    document.body.classList.toggle('signed-out', !phone);
    updateAcct();
    $('view-login').hidden = !!phone;
    if (!phone) { // signed out: only the login view (the topbar with language + 108 is always there)
      Object.keys(VIEWS).forEach(function (k) { $('view-' + k).hidden = true; });
      renderLogin();
      return;
    }
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
  function tile(ic, label, color, onclick) {
    return h('button', { class: 'tile ' + color, type: 'button', onclick: onclick },
      [h('span', { class: 'tile-ico' }, [icon(ic)]), h('span', { class: 'tile-lbl', text: label })]);
  }

  function renderHome() {
    var v = $('view-home');
    v.textContent = '';

    // Hero banner with the main action
    v.appendChild(h('section', { class: 'hero' }, [
      h('div', { class: 'fx-host hero-fx', 'aria-hidden': 'true' }, [h('div', { class: 'fx-fallback' })]),
      h('div', { class: 'hero-date', text: fmtDate(Date.now(), { weekday: 'long', day: 'numeric', month: 'long' }) }),
      h('h2', { text: t('hello') }),
      h('p', { class: 'hero-sub', text: t('heroSub') }),
      h('button', { class: 'btn hero-btn', type: 'button', onclick: function () { startCheckFor(''); } }, [icon('chat'), t('startCheck')])
    ]));

    // Quick actions
    v.appendChild(h('div', { class: 'tiles' }, [
      tile('pin', t('findHospital'), 'green', function () { openNearby('all'); }),
      tile('people', t('navFamily'), 'blue', function () { go('family'); }),
      h('a', { class: 'tile red', href: 'tel:108' }, [h('span', { class: 'tile-ico' }, [icon('phone')]), h('span', { class: 'tile-lbl', text: t('call108') })])
    ]));

    // Alerts needing follow-up
    var al = activeAlerts();
    v.appendChild(sectionTitle('bell', t('alerts')));
    if (!al.length) v.appendChild(h('p', { class: 'muted', text: t('noAlerts') }));
    al.slice().reverse().forEach(function (c) {
      var follow = c.level === 'RED' ? t('goNow') : t('seeBy', { date: shortDate(c.at + 2 * DAY) });
      v.appendChild(h('div', { class: 'card alert ' + c.level }, [
        h('div', null, [h('span', { class: 'badge ' + c.level, text: t(c.level)[0] }), ' ', h('b', { text: whoName(c) })]),
        h('div', { class: 'when', text: dateTime(c.at) }),
        c.reason ? h('div', { text: c.reason }) : null,
        h('div', { class: 'follow', text: follow }),
        h('div', { class: 'row-actions' }, [
          c.level === 'RED' ? h('a', { class: 'btn danger', href: 'tel:108' }, [icon('phone'), t('call108')]) : null,
          h('button', { class: 'btn', type: 'button', onclick: function () { openNearby('all', c.specialty); } },
            [icon('pin'), c.specialty && c.specialty !== 'general' ? t('findSpec', { spec: t('sp_' + c.specialty) }) : t('findHospital')]),
          h('button', { class: 'btn ghost', type: 'button', onclick: function () { c.done = true; save(); renderHome(); } }, [t('markDone')])
        ])
      ]));
    });

    // Family
    v.appendChild(sectionTitle('people', t('family')));
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
          h('div', { class: 'top' }, [avatar(m),
            h('div', null, [h('div', { class: 'name', text: m.name }), h('div', { class: 'meta', text: memberMeta(m) })])]),
          h('div', null, (m.conditions || []).slice(0, 3).map(function (c) { return h('span', { class: 'chip', text: t('c_' + c) }); })),
          h('div', { class: 'last' }, last
            ? [t('lastCheck') + ': ', h('span', { class: 'badge ' + last.level, text: t(last.level)[0] }), ' ' + shortDate(last.at)]
            : [t('noCheckYet')])
        ]));
      });
      v.appendChild(grid);
    }

    // Recent checks
    var recent = store.checks.slice(-8).reverse();
    v.appendChild(sectionTitle('clock', t('recent')));
    if (!recent.length) v.appendChild(h('p', { class: 'muted', text: t('noChecks') }));
    else v.appendChild(h('div', { class: 'card' }, [h('ul', { class: 'checklist' }, recent.map(function (c) {
      return h('li', null, [h('span', { class: 'badge ' + c.level, text: t(c.level)[0] }),
        h('div', { class: 'txt' }, [h('b', { text: whoName(c) }), h('span', { class: 'muted small', text: ' · ' + dateTime(c.at) }),
          c.reason ? h('div', { class: 'reason', text: c.reason }) : null])]);
    }))]));

    v.appendChild(helplinesBlock());
    v.appendChild(h('p', { class: 'muted small', text: t('disclaimer') }));
  }

  /* =====================================================================
     VOICE INPUT (Web Speech API) — words appear in the box while speaking
     ===================================================================== */
  var Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  var activeRec = null;

  // Start/stop listening into `target`; `onFinal(text)` runs when the person stops speaking.
  function toggleVoice(btn, target, onFinal, noteEl) {
    if (activeRec) { activeRec.stop(); return; } // second tap stops listening
    stopSpeaking();
    var r;
    try { r = new Recognition(); } catch (e) { btn.hidden = true; return; }
    activeRec = r;
    var before = target.value, heard = false, finalText = '';
    var setNote = function (s) { if (noteEl) noteEl.textContent = s; };
    r.lang = SPEECH_LANG[lang()] || 'en-IN';
    r.interimResults = true;   // live partial words
    r.continuous = false;      // stop after a pause
    r.maxAlternatives = 1;
    r.onstart = function () { btn.classList.add('on'); target.classList.add('live'); target.value = ''; setNote(t('listening')); };
    r.onresult = function (ev) {
      var interim = '';
      finalText = '';
      for (var i = 0; i < ev.results.length; i++) {
        var s = ev.results[i][0].transcript;
        if (ev.results[i].isFinal) finalText += s; else interim += s;
      }
      heard = true;
      target.value = (finalText + interim).replace(/\s+/g, ' ').trim(); // type as they speak
    };
    r.onerror = function (ev) {
      if (ev.error === 'not-allowed' || ev.error === 'service-not-allowed') setNote(t('micDenied'));
      else if (ev.error !== 'aborted') setNote(t('micNoSpeech'));
    };
    r.onend = function () {
      btn.classList.remove('on');
      target.classList.remove('live');
      activeRec = null;
      if (noteEl && noteEl.textContent === t('listening')) setNote('');
      var text = (finalText || target.value).trim();
      if (heard && text) onFinal(text);
      else if (!target.value) target.value = before; // nothing said: put back what was there
    };
    try { r.start(); } catch (e) { activeRec = null; }
  }

  function voiceButton(target, onFinal, noteEl) {
    var b = h('button', { type: 'button', class: 'iconbtn', 'aria-label': t('speak'), title: t('speak') }, [icon('mic')]);
    if (!Recognition) { b.hidden = true; return b; }
    b.addEventListener('click', function () { toggleVoice(b, target, onFinal, noteEl); });
    return b;
  }

  /* =====================================================================
     SYMPTOM CHECK (chatbot)
     ===================================================================== */
  var chat = $('chat'), form = $('f'), input = $('m'), sendBtn = $('send'), micBtn = $('mic'), note = $('note'), whoSel = $('who');
  var history = [];      // [{role:'user'|'bot', text}] sent with every request
  var busy = false;      // true while a /chat request is in flight
  var started = false;   // has the user sent anything in this check?
  micBtn.appendChild(icon('mic'));
  if (Recognition) {
    micBtn.hidden = false;
    micBtn.addEventListener('click', function () { if (!busy || activeRec) toggleVoice(micBtn, input, send, note); });
  }

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
  function botAvatar() { return h('span', { class: 'bot-av', 'aria-hidden': 'true' }, [icon('cross')]); }

  function addBubble(text, who, opts) {
    opts = opts || {};
    var code = opts.lang || lang();
    var b = h('div', { class: 'bubble' + (opts.err ? ' err' : ''), text: text, lang: code });
    var wrap = h('div', null, [b, who === 'bot' ? listenButton(text, code) : null]);
    var row = h('div', { class: 'row ' + who }, [who === 'bot' ? botAvatar() : null, wrap]);
    chat.appendChild(row);
    scrollDown();
    return row;
  }

  function showWelcome() {
    var m = member(whoSel.value);
    addBubble(m ? t('welcomeFor', { name: m.name }) : t('welcome'), 'bot');
    // One-tap common problems (helps people who find typing hard)
    chat.appendChild(h('div', { class: 'suggest' }, [
      h('div', { class: 'suggest-lbl', text: t('common') }),
      h('div', { class: 'chips' }, t('sugg').map(function (s) {
        return h('button', { class: 'chip-btn', type: 'button', text: s, onclick: function () { send(s); } });
      }))
    ]));
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
      typingRow = h('div', { class: 'row bot typing' }, [botAvatar(), h('div', null, [h('div', { class: 'bubble' }, [t('typing'),
        h('span', { class: 'dots', 'aria-hidden': 'true' }, [h('span'), h('span'), h('span')])])])]);
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

  async function send(text) {
    text = (text || '').trim();
    if (!text || busy) return;
    var m = member(whoSel.value), sid = sessionId;
    input.value = '';
    note.textContent = '';
    var det = detectScript(text);
    if (det) switchLang(det, note); // typed or spoken in another script: follow it
    var code = lang();
    started = true;
    chat.querySelectorAll('.suggest').forEach(function (e) { e.remove(); });
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
    if (sid !== sessionId) return; // signed out / switched number meanwhile: drop the reply
    setBusy(false);

    if (!data || !data.type) {
      // Network failure: friendly message, keep the text so one tap on Send retries.
      addBubble(t('offline', null, code), 'bot', { err: true, lang: code });
      input.value = text;
      return;
    }
    // The server detected another language (e.g. Hindi in English letters): the reply is in it, so follow.
    if (data.type !== 'error' && T[data.language] && data.language !== code) {
      switchLang(data.language, note);
      code = data.language;
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
      symptoms: Array.isArray(o.symptoms_en) ? o.symptoms_en.slice(0, 12) : [], done: false,
      specialty: T.en['sp_' + o.specialty] ? o.specialty : 'general',
      facility: T.en['fac_' + o.facility] ? o.facility : '' };
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
    // Which kind of doctor / building to go to
    var specLabel = t('sp_' + rec.specialty, null, code);
    var facLabel = rec.facility ? t('fac_' + rec.facility, null, code) : '';
    card.appendChild(listenButton([L[level][1], showReply ? reply : '', reason, advice !== reason ? advice : '',
      t('recommend', null, code) + ': ' + specLabel, facLabel].filter(Boolean).join('. '), code));

    if (level !== 'GREEN') card.appendChild(h('a', { class: 'call', href: 'tel:108' }, [icon('phone'), h('span', { text: L.call108 })]));
    card.appendChild(h('div', { class: 'recommend' }, [
      h('div', { class: 'label', text: t('recommend', null, code) }),
      h('div', { class: 'rec-spec' }, [icon('cross'), h('span', { text: specLabel })]),
      facLabel ? h('div', { class: 'rec-fac', text: t('goTo', null, code) + ': ' + facLabel }) : null,
      h('button', { class: 'btn primary block', type: 'button', onclick: function () { openNearby('all', rec.specialty); } },
        [icon('pin'), rec.specialty === 'general' ? L.findHospital : t('findSpec', { spec: specLabel }, code)])
    ]));
    if (level !== 'GREEN') card.appendChild(alertBox(rec, m, code));
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
    var box = h('div', { class: 'alertbox' }), sid = sessionId;
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
          if (sid !== sessionId) return;
          store.lastLoc = { lat: pos.coords.latitude, lon: pos.coords.longitude, acc: pos.coords.accuracy, at: Date.now() };
          save();
          fill();
        }, function () {}, { enableHighAccuracy: true, timeout: 15000, maximumAge: 120000 });
      }).catch(function () {});
    }
    return box;
  }

  form.addEventListener('submit', function (e) { e.preventDefault(); send(input.value); });

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
  // where: the location being searched {lat, lon, acc, name} (shown in the banner while loading)
  // spec: recommended speciality from the last check ('' = none); matching places are listed first
  var near = { status: 'idle', choices: [], filter: 'all', query: '', where: null, spec: '' };

  function openNearby(filter, spec) {
    near.filter = filter || 'all';
    near.spec = spec && spec !== 'general' ? spec : '';
    go('near');
    var P = store.places, loading = near.status === 'locating' || near.status === 'loading';
    if (loading) return;
    if (!P) locate();
    // lists saved before speciality tagging existed: fetch again for the same spot
    else if (near.spec && P.list && P.list.length && !P.list.some(function (p) { return Array.isArray(p.specialties); })) {
      loadPlaces(P.lat, P.lon, P.label, P.acc);
    }
  }

  var BIG = { govt_hospital: 1, hospital: 1, charity_hospital: 1, chc: 1 };
  function offers(p, spec) {
    if (!spec) return false;
    if (spec === 'emergency') return !!p.emergency || (p.specialties || []).indexOf('emergency') >= 0;
    return (p.specialties || []).indexOf(spec) >= 0;
  }
  // 0 = offers the speciality, 1 = big / government hospital (can refer onwards), 2 = everything else
  function rankFor(p, spec) {
    if (!spec) return 0;
    return offers(p, spec) ? 0 : BIG[p.sub] ? 1 : 2;
  }

  function setNear(status, extra) {
    near.status = status;
    for (var k in (extra || {})) near[k] = extra[k];
    if (currentTab() === 'near') renderNear();
  }

  function locate() {
    if (!navigator.geolocation) { setNear('error', { msg: 'locErr' }); return; }
    var sid = sessionId;
    setNear('locating', { choices: [] });
    // High accuracy asks the phone for GPS instead of a rough network guess.
    navigator.geolocation.getCurrentPosition(function (pos) {
      if (sid !== sessionId) return;
      var c = pos.coords;
      store.lastLoc = { lat: c.latitude, lon: c.longitude, acc: c.accuracy, at: Date.now() };
      save();
      loadPlaces(c.latitude, c.longitude, '', c.accuracy);
    }, function () {
      if (sid !== sessionId) return;
      setNear('error', { msg: 'locErr' });
    }, { enableHighAccuracy: true, timeout: 20000, maximumAge: 60000 });
  }

  async function searchPlace(q) {
    q = (q || '').trim();
    near.query = q;
    if (!q) return;
    var sid = sessionId;
    setNear('loading', { choices: [] });
    try {
      var r = await fetchJSON('/geocode?q=' + encodeURIComponent(q) + '&lang=' + lang(), null, 20000);
      if (sid !== sessionId) return;
      var res = (r.data && r.data.results) || [];
      if (!res.length) setNear('error', { msg: 'locErr' });
      else if (res.length === 1) loadPlaces(res[0].lat, res[0].lon, res[0].name, null);
      else setNear('choose', { choices: res });
    } catch (e) {
      if (sid === sessionId) setNear('error', { msg: 'nearErr' });
    }
  }

  async function loadPlaces(lat, lon, label, acc) {
    var sid = sessionId;
    near.where = { lat: lat, lon: lon, acc: acc, name: label || '' };
    setNear('loading', { choices: [] });
    // For GPS, look up the place name in parallel so the person can see whether the location is right.
    if (!label) {
      fetchJSON('/reverse?lat=' + lat.toFixed(5) + '&lon=' + lon.toFixed(5) + '&lang=' + lang(), null, 15000).then(function (r) {
        var name = r.data && r.data.name;
        if (!name || sid !== sessionId) return;
        if (near.where && near.where.lat === lat) near.where.name = name;
        if (store.places && store.places.lat === lat) { store.places.label = name; save(); }
        if (currentTab() === 'near') renderNear();
      }).catch(function () {});
    }
    try {
      var r = await fetchJSON('/places?lat=' + lat.toFixed(5) + '&lon=' + lon.toFixed(5), null, PLACES_TIMEOUT_MS);
      if (sid !== sessionId) return;
      if (!r.ok || !r.data || !Array.isArray(r.data.places)) throw new Error('bad response');
      store.places = { at: Date.now(), lat: lat, lon: lon, acc: acc, label: (near.where && near.where.name) || label || '',
        list: r.data.places, radius_km: r.data.radius_km };
      save();
      setNear('done');
    } catch (e) {
      if (sid !== sessionId) return;
      setNear('error', { msg: 'nearErr' }); // a previously saved list (if any) is still shown below
    }
  }

  function distanceKm(lat1, lon1, lat2, lon2) {
    var R = 6371, rad = Math.PI / 180;
    var dLat = (lat2 - lat1) * rad, dLon = (lon2 - lon1) * rad;
    var a = Math.sin(dLat / 2) * Math.sin(dLat / 2) + Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
    return 2 * R * Math.asin(Math.sqrt(a));
  }
  function firstPhone(p) { return (p || '').split(/[;,/]/)[0].replace(/[^\d+]/g, ''); }
  function shortPlace(name) { return (name || '').split(',').slice(0, 2).join(',').trim(); }
  // Start the route from the same point the list was built from, so the map matches the distances shown.
  function directionsUrl(p, from) {
    return 'https://www.google.com/maps/dir/?api=1&origin=' + from.lat.toFixed(6) + ',' + from.lon.toFixed(6) +
      '&destination=' + (+p.lat).toFixed(6) + ',' + (+p.lon).toFixed(6) + '&travelmode=driving';
  }

  function locationBanner(where) {
    var acc = where.acc;
    var box = h('div', null, [h('div', { class: 'locbar' }, [icon('pin'), h('div', { class: 'locbar-txt' }, [
      h('div', { class: 'loc-main', text: t('locHere', { place: shortPlace(where.name) || t('myLocation') }) }),
      acc ? h('div', { class: 'loc-acc', text: t('locAcc', { n: fmtKm(acc / 1000) }) }) : null,
      h('button', { class: 'linkbtn', type: 'button', text: t('locWrong'), onclick: function () { var q = $('placeq'); if (q) q.focus(); } })
    ])])]);
    if (acc && acc > APPROX_M) box.appendChild(h('p', { class: 'status warn', text: t('locApprox') }));
    return box;
  }

  function renderNear() {
    var v = $('view-near');
    v.textContent = '';
    v.appendChild(h('h2', { text: t('nearTitle') }));
    var busyNow = near.status === 'locating' || near.status === 'loading';

    v.appendChild(h('button', { class: 'btn primary big', type: 'button', disabled: busyNow, onclick: locate }, [icon('target'), t('useLoc')]));
    var q = h('input', { type: 'text', id: 'placeq', placeholder: t('orType'), 'aria-label': t('orType'), enterkeyhint: 'search' });
    q.value = near.query;
    var statusLine = h('p', { class: 'status', role: 'status' });
    v.appendChild(h('form', { class: 'searchrow', onsubmit: function (e) { e.preventDefault(); searchPlace(q.value); } },
      [q, voiceButton(q, searchPlace, statusLine), h('button', { class: 'btn', type: 'submit', disabled: busyNow, text: t('search') })]));

    // Status line
    var msg = near.status === 'locating' ? t('locating') : near.status === 'loading' ? t('loading')
      : near.status === 'error' ? t(near.msg) : '';
    statusLine.textContent = msg;
    statusLine.className = 'status' + (near.status === 'error' ? ' err' : busyNow ? ' loading' : '');
    v.appendChild(statusLine);

    // Choose between several matching places
    if (near.status === 'choose') {
      v.appendChild(h('p', { class: 'status', text: t('pickPlace') }));
      v.appendChild(h('div', { class: 'choices' }, near.choices.map(function (c) {
        return h('button', { class: 'btn', type: 'button', text: c.name, onclick: function () { loadPlaces(c.lat, c.lon, c.name, null); } });
      })));
    }

    var P = store.places;
    // Where are we searching from? (the new location while loading, otherwise the saved list's location)
    var where = busyNow && near.where ? near.where : P ? { lat: P.lat, lon: P.lon, acc: P.acc, name: P.label } : null;
    if (where) v.appendChild(locationBanner(where));

    if (P && P.list) {
      var stale = Date.now() - P.at > 6 * 3600000;
      if (stale || near.status === 'error') v.appendChild(h('p', { class: 'muted small', text: t('savedList', { date: dateTime(P.at) }) }));

      v.appendChild(h('div', { class: 'filters', role: 'group' }, FILTERS.map(function (f) {
        var n = f[0] === 'all' ? P.list.length : P.list.filter(function (p) { return p.kind === f[0]; }).length;
        return h('button', { type: 'button', 'aria-pressed': String(near.filter === f[0]),
          onclick: function () { near.filter = f[0]; renderNear(); } },
          [near.filter === f[0] ? h('span', { class: 'pill', 'data-flip-id': 'fpill', 'aria-hidden': 'true' }) : null, t(f[1]) + ' (' + n + ')']);
      })));

      // Recommended speciality from the symptom check
      var spec = near.spec, specLabel = spec ? t('sp_' + spec) : '';
      if (spec) {
        v.appendChild(h('div', { class: 'specbar' }, [h('span', { text: '★ ' + t('specShowing', { spec: specLabel }) }),
          h('button', { class: 'linkbtn', type: 'button', text: t('specAll'), onclick: function () { near.spec = ''; renderNear(); } })]));
        if (!P.list.some(function (p) { return offers(p, spec); })) v.appendChild(h('p', { class: 'status warn', text: t('specNone', { spec: specLabel }) }));
      }

      // Distances from the exact searched point (the server caches by ~1 km cell)
      var list = P.list.filter(function (p) { return near.filter === 'all' || p.kind === near.filter; })
        .map(function (p) { return { p: p, km: distanceKm(P.lat, P.lon, +p.lat, +p.lon), rank: rankFor(p, spec) }; })
        .sort(function (a, b) { return a.rank - b.rank || a.km - b.km; });
      if (!list.length && near.filter !== 'ngo') v.appendChild(h('p', { class: 'muted', text: t('none') }));
      list.forEach(function (x) {
        var p = x.p, phone = firstPhone(p.phone), match = offers(p, spec);
        var extra = (p.specialties || []).filter(function (s) { return s !== 'emergency' && s !== spec; });
        v.appendChild(h('div', { class: 'card place ' + p.kind + (match ? ' match' : '') }, [
          h('span', { class: 'k-ico', style: 'background:' + (KIND_COLORS[p.kind] || '#0F766E') }, [icon('cross')]),
          h('div', { class: 'body' }, [
            h('div', { class: 'head' }, [
              h('div', null, [h('div', { class: 'pname', text: p.name }), p.local_name ? h('div', { class: 'local', text: p.local_name }) : null]),
              h('span', { class: 'dist', text: t('km', { n: fmtKm(x.km) }) })
            ]),
            h('div', { class: 'kind', style: 'color:' + (KIND_COLORS[p.kind] || '#0F766E') },
              [t('s_' + p.sub), p.emergency ? ' ' : null, p.emergency ? h('span', { class: 'badge em', text: t('emergency24') }) : null]),
            match && spec !== 'emergency' ? h('div', null, [h('span', { class: 'badge spec', text: '★ ' + specLabel })]) : null,
            extra.length ? h('div', { class: 'spchips' }, extra.map(function (s) { return h('span', { class: 'chip', text: t('sp_' + s) }); })) : null,
            p.address ? h('div', { class: 'addr', text: p.address }) : null,
            h('div', { class: 'row-actions' }, [
              phone ? h('a', { class: 'btn', href: 'tel:' + phone }, [icon('phone'), t('callPlace')]) : null,
              h('a', { class: 'btn primary', target: '_blank', rel: 'noopener', href: directionsUrl(p, P) }, [icon('route'), t('directions')])
            ])
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
      h('div', { class: 'sec', style: 'margin-top:0' }, [icon('phone'), t('pfContact')]),
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
    v.appendChild(sectionTitle('people', t('pfMembers')));
    store.members.forEach(function (m) {
      var confirming = fam.confirm === m.id;
      v.appendChild(h('div', { class: 'card' }, [
        h('div', { class: 'mrow' }, [avatar(m),
          h('div', { class: 'txt' }, [h('div', { class: 'name', text: m.name }), h('div', { class: 'muted small', text: memberMeta(m) })])
        ]),
        h('div', { style: 'margin-top:6px' }, (m.conditions || []).map(function (c) { return h('span', { class: 'chip', text: t('c_' + c) }); })),
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
  phone = readSession();
  store = loadStore();
  $('acct').addEventListener('click', function () {
    if (phone && confirm(t('switchConfirm', { num: '•••• ' + phone.slice(-4) }))) signOut();
  });
  langSel.value = initialLang();
  langSel.addEventListener('change', function () {
    stopSpeaking();
    applyLanguage();
    route();               // re-render the visible view in the new language
    refreshListenButtons();
  });
  applyLanguage();
  route();
})();
