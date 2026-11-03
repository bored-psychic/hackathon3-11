/* Motion layer: GSAP choreography for the Health Check app.
   app.js calls window.Motion.<hook>(...). If this file, GSAP or the user's "reduce motion" setting says no,
   window.Motion is a set of no-ops and app.js behaves exactly as without it.

   SAFETY: nothing here touches the 108 button in the top bar. On a RED result the card, its text and the
   "Call 108" link are fully opaque from the first frame; only the level word punches and the ring pulses.
   READABILITY: text is only ever split into LINES (never characters or words as visible units), always reverted
   afterwards, and every tween ends in the natural state (clearProps). */
(function () {
  'use strict';

  var g = window.gsap;
  var HOOKS = ['enterView', 'transition', 'login', 'shake', 'errIn', 'bubble', 'chips', 'typing', 'clear', 'result',
    'echo', 'tabs', 'list', 'expand', 'collapse', 'crossfade', 'fx', 'pillState', 'pillGlide'];
  var NOOP = { tier: 'off', active: function () { return 0; } };
  HOOKS.forEach(function (n) { NOOP[n] = function () {}; });

  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!g || reduce) { window.Motion = NOOP; return; }

  [window.ScrollTrigger, window.Flip, window.SplitText].forEach(function (p) { if (p) g.registerPlugin(p); });
  g.config({ nullTargetWarn: false });
  document.documentElement.classList.add('motion');

  /* ---------- tiers ----------
     full: desktop with enough memory. Everything, including Three.js.
     lite: phones and low-power devices. Durations x0.7, transform/opacity only, no line splitting, no blur,
           no magnetic hover, no ScrollTrigger, no Three.js.
     off:  prefers-reduced-motion (or GSAP missing). window.Motion is all no-ops, content shows instantly. */
  function pickTier() {
    var c = navigator.connection;
    var lite = window.innerWidth < 1024 || (navigator.deviceMemory && navigator.deviceMemory < 4) ||
      (navigator.hardwareConcurrency && navigator.hardwareConcurrency <= 2) || (c && c.saveData);
    return lite ? { tier: 'lite', k: .7, split: false, blur: false, magnet: false, scroll: false }
      : { tier: 'full', k: 1, split: true, blur: true, magnet: true, scroll: true };
  }
  var S = pickTier();
  function D(x) { return x * S.k; }
  function arr(x) { return !x ? [] : x.nodeType ? [x] : Array.prototype.slice.call(x); }
  function plain(els) { g.set(els, { clearProps: 'transform,opacity,filter,visibility' }); }
  function done(fn) { var once = false; return function () { if (once) return; once = true; if (fn) fn(); }; }

  /* ---------- line-by-line reveal (never characters) ---------- */
  function lineReveal(targets, o) {
    o = o || {};
    var list = arr(targets).filter(function (n) { return n && n.textContent; });
    if (!list.length) return;
    var sp = null;
    if (S.split && window.SplitText) { try { sp = window.SplitText.create(list, { type: 'lines' }); } catch (e) { sp = null; } }
    var items = sp ? sp.lines : list;
    var finish = function () { if (sp) { try { sp.revert(); } catch (e) {} } plain(list); };
    g.fromTo(items, { y: o.y || 22, opacity: 0 }, {
      y: 0, opacity: 1, duration: D(o.dur || .7), ease: 'power3.out', stagger: o.stagger == null ? .09 : o.stagger,
      delay: o.delay || 0, onComplete: finish, onInterrupt: finish
    });
  }

  /* ---------- count up (ends on the exact original text) ---------- */
  function countUp(el, dur) {
    var txt = el.textContent, m = txt.match(/\d+(?:\.\d+)?/);
    if (!m) return;
    var end = parseFloat(m[0]), dec = (m[0].split('.')[1] || '').length;
    var pre = txt.slice(0, m.index), post = txt.slice(m.index + m[0].length), o = { v: 0 };
    var restore = function () { el.textContent = txt; };
    g.to(o, { v: end, duration: dur, ease: 'power2.out',
      onUpdate: function () { el.textContent = pre + o.v.toFixed(dec) + post; }, onComplete: restore, onInterrupt: restore });
  }

  /* ---------- views ---------- */
  function killIn(el) {
    (el._st || []).forEach(function (t) { try { t.kill(); } catch (e) {} });
    el._st = [];
    if (el._tl) { el._tl.kill(); el._tl = null; }
  }

  // The outgoing view is replaced by a non-interactive snapshot that fades and slides 12px, so input is never blocked.
  function ghost(prev) {
    if (!prev || !prev.parentNode) return;
    if (S.tier === 'lite' && prev.getElementsByTagName('*').length > 250) return; // a big clone costs more than it shows
    document.querySelectorAll('.view-ghost').forEach(function (n) { n.remove(); });
    var c = prev.cloneNode(true);
    c.removeAttribute('hidden'); c.removeAttribute('id');
    c.classList.add('view-ghost');
    c.setAttribute('aria-hidden', 'true'); c.setAttribute('inert', '');
    c.querySelectorAll('[id]').forEach(function (n) { n.removeAttribute('id'); });
    c.querySelectorAll('canvas').forEach(function (n) { n.remove(); });
    c.querySelectorAll('input, select, textarea').forEach(function (n) { n.setAttribute('name', 'ghost'); });
    prev.parentNode.insertBefore(c, prev);
    c.scrollTop = prev.scrollTop;
    var rm = done(function () { c.remove(); });
    g.to(c, { opacity: 0, y: -12, duration: D(.2), ease: 'power2.in', onComplete: rm });
    g.delayedCall(.6, rm);
  }

  function enter(el, name) {
    if (!el || name === 'login') return;
    killIn(el);
    var kids = arr(el.children).filter(function (k) { return !k.matches('.fx-host'); });
    var hero = el.querySelector('.hero');
    var tiles = arr(el.querySelectorAll('.tile'));
    var alerts = arr(el.querySelectorAll('.alert'));
    var members = arr(el.querySelectorAll('.member, .fam-item'));
    var places = Date.now() - (el._listAt || 0) < 300 ? arr(el.querySelectorAll('.place')) : [];
    var special = [hero].concat(alerts, places);
    var generic = kids.filter(function (k) {
      return special.indexOf(k) < 0 && !k.classList.contains('tiles') && !k.classList.contains('members') && !k.classList.contains('fam-list');
    });

    // below the fold on a big screen: reveal on scroll (never anything that holds the 108 link)
    var later = [];
    if (S.scroll && window.ScrollTrigger && name === 'home' && el.clientHeight) {
      var limit = el.getBoundingClientRect().top + el.clientHeight * .92;
      later = generic.filter(function (k) { return k.getBoundingClientRect().top > limit && !k.querySelector('a[href="tel:108"]'); });
      generic = generic.filter(function (k) { return later.indexOf(k) < 0; });
    }

    el._entering = true;
    var tl = el._tl = g.timeline({ onComplete: function () { el._entering = false; el._tl = null; } });
    if (hero) {
      tl.fromTo(hero, { y: 18, opacity: 0 }, { y: 0, opacity: 1, duration: D(.5), ease: 'power3.out', clearProps: 'transform,opacity' }, 0);
      tl.add(function () { lineReveal(hero.querySelector('h2'), { delay: .08 }); }, 0);
    }
    tl.fromTo(generic, { y: 24, opacity: 0 }, { y: 0, opacity: 1, duration: D(.42), ease: 'power3.out', stagger: .06, clearProps: 'transform,opacity' }, .1);
    tl.fromTo(tiles, { y: 16, scale: .92, opacity: 0 }, { y: 0, scale: 1, opacity: 1, duration: D(.5), ease: 'back.out(1.4)', stagger: .07, clearProps: 'transform,opacity' }, .2);
    tl.fromTo(alerts, { x: -36, opacity: 0 }, { x: 0, opacity: 1, duration: D(.5), ease: 'power3.out', stagger: .08, clearProps: 'transform,opacity' }, .25);
    tl.fromTo(members, { scale: .88, opacity: 0 }, { scale: 1, opacity: 1, duration: D(.45), ease: 'back.out(1.5)', stagger: .06, clearProps: 'transform,opacity' }, .3);
    tl.fromTo(places, { y: 20, opacity: 0 }, { y: 0, opacity: 1, duration: D(.45), ease: 'power3.out', stagger: Math.min(.06, .6 / Math.max(1, places.length)), clearProps: 'transform,opacity' }, .15);
    if (name === 'home') arr(el.querySelectorAll('.helpline b')).forEach(function (b) { tl.add(function () { countUp(b, D(.9)); }, .3); });

    later.forEach(function (k) {
      g.set(k, { opacity: 0, y: 24 });
      var go = done(function () { g.to(k, { opacity: 1, y: 0, duration: D(.5), ease: 'power3.out', clearProps: 'transform,opacity' }); });
      el._st.push(window.ScrollTrigger.create({ trigger: k, scroller: el, start: 'top 94%', once: true, onEnter: go }));
      g.delayedCall(6, go); // never leave a section hidden
    });
    g.delayedCall(D(1.6) + .8, function () { plain(generic.concat(tiles, alerts, members, places, hero ? [hero] : [])); el._entering = false; });
  }

  /* ---------- the tab highlight (bottom bar and desktop sidebar) glides with Flip ---------- */
  var tabsReady = false;
  function tabs() {
    var nav = document.querySelector('.tabbar');
    if (!nav || !nav.getClientRects().length) { tabsReady = false; return; }
    var a = nav.querySelector('a[aria-current="page"]');
    if (!a) return;
    var side = window.matchMedia('(min-width: 1024px)').matches;
    var host = side ? a : (a.querySelector('.ico') || a);
    var ind = nav.querySelector('.tab-ind');
    if (!ind) {
      ind = document.createElement('span');
      ind.className = 'tab-ind'; ind.setAttribute('aria-hidden', 'true'); ind.setAttribute('data-flip-id', 'tabind');
    }
    if (ind.parentNode === host) return;
    var instant = !tabsReady || !window.Flip;
    tabsReady = true;
    if (instant) { host.insertBefore(ind, host.firstChild); return; }
    var st = window.Flip.getState(ind);
    host.insertBefore(ind, host.firstChild);
    window.Flip.from(st, { duration: D(.38), ease: 'power3.out', scale: true, onComplete: function () { g.set(ind, { clearProps: 'transform' }); } });
  }
  var rsz;
  window.addEventListener('resize', function () { clearTimeout(rsz); rsz = setTimeout(function () { tabsReady = false; tabs(); }, 120); });

  /* ---------- login ---------- */
  function drawLogo(svg) {
    var path = svg && svg.querySelector('path');
    if (!path) return;
    try {
      var len = path.getTotalLength();
      g.set(path, { attr: { 'fill-opacity': 0, stroke: 'currentColor', 'stroke-width': 1.1, 'stroke-linejoin': 'round', 'stroke-dasharray': len, 'stroke-dashoffset': len } });
      var tidy = done(function () {
        ['fill-opacity', 'stroke', 'stroke-width', 'stroke-linejoin', 'stroke-dasharray', 'stroke-dashoffset'].forEach(function (a) { path.removeAttribute(a); });
      });
      g.timeline({ onComplete: tidy, onInterrupt: tidy })
        .to(path, { attr: { 'stroke-dashoffset': 0 }, duration: D(1), ease: 'power2.inOut' })
        .to(path, { attr: { 'fill-opacity': 1 }, duration: D(.4), ease: 'power1.out' }, '-=.2');
      g.delayedCall(D(2), tidy);
    } catch (e) { /* the plain logo stays */ }
  }

  function loginIn(pane, step, dir, first) {
    var card = pane.querySelector('.loginbox');
    if (!card) return;
    var root = pane.closest('.login-split') || pane;
    if (first) {
      drawLogo(root.querySelector('.login-logo'));
      lineReveal(root.querySelector('.display'), { delay: .25, dur: .9 });
      g.fromTo(root.querySelector('.display-sub'), { y: 14, opacity: 0 }, { y: 0, opacity: 1, duration: D(.6), delay: D(.7), ease: 'power3.out', clearProps: 'transform,opacity' });
      var from = { y: 40, opacity: 0 }, to = { y: 0, opacity: 1, duration: D(.9), delay: D(.35), ease: 'power3.out', clearProps: 'transform,opacity,filter' };
      if (S.blur) { from.filter = 'blur(10px)'; to.filter = 'blur(0px)'; }
      g.fromTo(card, from, to);
      lineReveal(card.querySelector('h2'), { delay: .55, dur: .6, y: 16 });
    } else if (dir) {
      g.fromTo(card, { x: dir * 64, opacity: 0, scale: .97 }, { x: 0, opacity: 1, scale: 1, duration: D(.46), ease: 'power3.out', clearProps: 'transform,opacity' });
      if (step === 'code') {
        g.fromTo(card.querySelectorAll('.cells span'), { y: 14, opacity: 0, scale: .9 },
          { y: 0, opacity: 1, scale: 1, duration: D(.4), stagger: .06, delay: .18, ease: 'back.out(1.6)', clearProps: 'transform,opacity' });
      }
    } else {
      g.fromTo(card, { opacity: .4 }, { opacity: 1, duration: .3, clearProps: 'opacity' });
    }
  }

  function shake(el) {
    if (!el) return;
    g.killTweensOf(el);
    g.fromTo(el, { x: -8 }, { x: 8, duration: .05, repeat: 5, yoyo: true, ease: 'sine.inOut', onComplete: function () { g.set(el, { clearProps: 'x' }); } });
  }
  function errIn(el) {
    if (!el || !el.textContent) return;
    g.fromTo(el, { y: 8, opacity: 0 }, { y: 0, opacity: 1, duration: D(.3), ease: 'power2.out', clearProps: 'transform,opacity' });
  }

  /* ---------- chat ---------- */
  var waves = [], rings = [];
  function bubble(row, who) {
    if (who === 'user') {
      g.fromTo(row, { x: 44, opacity: 0 }, { x: 0, opacity: 1, duration: D(.55), ease: 'back.out(1.5)', clearProps: 'transform,opacity' });
    } else {
      g.fromTo(row, { y: 16, opacity: 0 }, { y: 0, opacity: 1, duration: D(.42), delay: .08, ease: 'power3.out', clearProps: 'transform,opacity' });
    }
  }
  function chips(box) {
    g.fromTo(box.querySelectorAll('.chip-btn'), { y: 10, opacity: 0, scale: .96 },
      { y: 0, opacity: 1, scale: 1, duration: D(.4), stagger: .05, delay: .3, ease: 'power3.out', clearProps: 'transform,opacity' });
  }
  function typing(row, on) {
    if (!row) return;
    if (on) {
      row._wave = g.to(row.querySelectorAll('.dots span'), { y: -5, duration: .35, ease: 'sine.inOut', yoyo: true, repeat: -1, stagger: .12 });
      waves.push(row._wave);
    } else if (row._wave) {
      row._wave.kill(); waves = waves.filter(function (w) { return w !== row._wave; });
    }
  }
  function clearLoops() {
    waves.concat(rings).forEach(function (t) { try { t.kill(); } catch (e) {} });
    waves = []; rings = [];
    document.querySelectorAll('.call-ring').forEach(function (n) { n.remove(); });
  }

  /* ---------- result card ---------- */
  function result(card, level) {
    var word = card.querySelector('.level'), call = card.querySelector('.call');
    echo(level);
    if (level === 'RED') {
      // SAFETY: no opacity, no delay, no scale on the card or its text. Only the level word punches and the ring pulses.
      if (word) g.fromTo(word, { scale: 1.15 }, { scale: 1, duration: .3, ease: 'power2.out', transformOrigin: 'left center', clearProps: 'transform' });
      if (call) {
        var ring = document.createElement('span');
        ring.className = 'call-ring'; ring.setAttribute('aria-hidden', 'true');
        call.appendChild(ring);
        var r = call.getBoundingClientRect(); // grow by the same 14px on every side
        rings.push(g.fromTo(ring, { scaleX: 1, scaleY: 1, opacity: .55 },
          { scaleX: 1 + 28 / (r.width || 300), scaleY: 1 + 28 / (r.height || 58), opacity: 0, duration: 1.4, ease: 'power1.out', repeat: -1 }));
      }
      return;
    }
    g.fromTo(card, { opacity: 0, scale: .94, y: 12 }, { opacity: 1, scale: 1, y: 0, duration: D(.38), ease: 'power3.out', clearProps: 'transform,opacity' });
    if (word) g.fromTo(word, { scale: 1.15 }, { scale: 1, duration: D(.45), delay: .1, ease: 'back.out(2)', transformOrigin: 'left center', clearProps: 'transform' });
    lineReveal(card.querySelectorAll('.meaning, .text'), { delay: .25, dur: .5, y: 14, stagger: .08 });
    var rec = card.querySelector('.recommend');
    if (rec) {
      g.fromTo(rec, { y: 12, opacity: 0 }, { y: 0, opacity: 1, duration: D(.45), delay: .55, ease: 'power3.out', clearProps: 'transform,opacity' });
      g.fromTo(rec.querySelector('.rec-spec'), { scale: .9 }, { scale: 1, duration: D(.5), delay: .7, ease: 'back.out(2.2)', transformOrigin: 'left center', clearProps: 'transform' });
    }
    g.delayedCall(D(1.8) + .6, function () { plain(card); }); // failsafe: never leave the card half-faded
  }
  function echo(level) { if (window.FX3D && window.FX3D.echo) { try { window.FX3D.echo(level); } catch (e) {} } }

  /* ---------- lists, family form, language ---------- */
  function list(els, kind) {
    els = arr(els);
    if (!els.length) return;
    var view = els[0].closest('.view');
    if (view) view._listAt = Date.now();
    var some = S.tier === 'lite' ? els.slice(0, 8) : els; // on a cheap phone only what can be on screen animates
    g.fromTo(some, { y: 20, opacity: 0 }, { y: 0, opacity: 1, duration: D(.45), ease: 'power3.out',
      stagger: Math.min(.06, .6 / some.length), clearProps: 'transform,opacity' });
    if (kind === 'near') some.forEach(function (e) { var d = e.querySelector('.dist'); if (d) countUp(d, D(.8)); });
  }
  function expand(form) {
    g.delayedCall(0, function () {
      var view = form.closest('.view');
      if (!form.isConnected || (view && view._entering)) return;
      if (S.tier === 'lite') {
        g.fromTo(form, { y: 18, opacity: 0 }, { y: 0, opacity: 1, duration: D(.45), ease: 'power3.out', clearProps: 'transform,opacity' });
        return;
      }
      var h0 = form.offsetHeight;
      g.fromTo(form, { height: 0, opacity: 0, overflow: 'hidden' }, { height: h0, opacity: 1, duration: D(.45), ease: 'power3.out',
        onComplete: function () { g.set(form, { clearProps: 'height,opacity,overflow' }); } });
    });
  }
  function collapse(card, cb) {
    var fin = done(cb);
    try {
      if (S.tier === 'lite') {
        g.to(card, { opacity: 0, scale: .96, duration: D(.28), ease: 'power2.in', onComplete: fin });
        g.delayedCall(.7, fin);
        return true;
      }
      g.to(card, { opacity: 0, height: 0, paddingTop: 0, paddingBottom: 0, marginBottom: 0, borderWidth: 0, overflow: 'hidden',
        duration: D(.32), ease: 'power2.inOut', onComplete: fin });
      g.delayedCall(.7, fin);
    } catch (e) { fin(); }
    return true;
  }
  function crossfade(el) {
    if (el) g.fromTo(el, { opacity: .35 }, { opacity: 1, duration: D(.35), ease: 'power1.out', clearProps: 'opacity' });
  }

  /* ---------- Nearby: the active filter pill glides between chips (the chips are rebuilt, Flip matches them by data-flip-id) ---------- */
  function pillState() {
    var p = document.querySelector('.filters .pill');
    return p && window.Flip ? window.Flip.getState(p) : null;
  }
  function pillGlide(st) {
    var p = document.querySelector('.filters .pill');
    if (!st || !p) return;
    window.Flip.from(st, { targets: p, duration: D(.38), ease: 'power3.out', scale: true, onComplete: function () { g.set(p, { clearProps: 'transform' }); } });
  }

  /* ---------- subtle magnetic hover on the main buttons (desktop pointer only) ---------- */
  (function magnet() {
    var sel = '.hero-btn, .btn.primary, .cta', cur = null;
    function release(el) { g.to(el, { x: 0, y: 0, duration: .45, ease: 'elastic.out(1,.55)', clearProps: 'x,y' }); }
    document.addEventListener('pointermove', function (e) {
      if (!S.magnet || e.pointerType !== 'mouse' || window.innerWidth < 1024) return;
      var el = e.target.closest ? e.target.closest(sel) : null;
      if (cur && cur !== el) { release(cur); cur = null; }
      if (!el || el.disabled) return;
      cur = el;
      var r = el.getBoundingClientRect(), x0 = g.getProperty(el, 'x') || 0, y0 = g.getProperty(el, 'y') || 0;
      var dx = (e.clientX - (r.left - x0 + r.width / 2)) / (r.width / 2), dy = (e.clientY - (r.top - y0 + r.height / 2)) / (r.height / 2);
      g.to(el, { x: Math.max(-1, Math.min(1, dx)) * 8, y: Math.max(-1, Math.min(1, dy)) * 8, duration: .3, ease: 'power3.out', overwrite: 'auto' });
    }, { passive: true });
    document.addEventListener('pointerleave', function () { if (cur) { release(cur); cur = null; } }, true);
  })();

  /* ---------- 3D layer: only fetched when every gate passes; otherwise the CSS fallback shape stays ---------- */
  var BASE = ((document.currentScript && document.currentScript.src) || '/static/motion.js').replace(/motion\.js.*$/, '');
  var fxState = 'idle', fxWanted = null, webgl = null; // idle | loading | ready | no
  function webglOk() {
    if (webgl !== null) return webgl;
    webgl = false;
    try {
      var gl = document.createElement('canvas').getContext('webgl2', { failIfMajorPerformanceCaveat: true });
      if (gl) { webgl = true; var lose = gl.getExtension('WEBGL_lose_context'); if (lose) lose.loseContext(); }
    } catch (e) { webgl = false; }
    return webgl;
  }
  function fxAllowed() {
    if (S.tier !== 'full' || window.innerWidth < 1024) return false;
    if (/[?&]fx=off\b/.test(location.search)) return false;
    if (navigator.deviceMemory && navigator.deviceMemory < 4) return false;
    return webglOk();
  }
  function fxSync(name) {
    fxWanted = name;
    if (fxState === 'ready') { try { window.FX3D.sync(name); } catch (e) {} return; }
    if (fxState !== 'idle' || !fxAllowed()) return;
    fxState = 'loading';
    var load = function () {
      import(BASE + 'fx3d.js?v=8').then(function (mod) {
        window.FX3D = mod.default;
        fxState = 'ready';
        window.FX3D.sync(fxWanted);
      }).catch(function () { fxState = 'no'; });
    };
    // Let the first choreography play before parsing Three.js.
    if (window.requestIdleCallback) window.requestIdleCallback(load, { timeout: 900 }); else setTimeout(load, 500);
  }
  window.addEventListener('resize', function () {
    clearTimeout(fxSync._t);
    fxSync._t = setTimeout(function () {
      var next = pickTier();
      for (var k in next) S[k] = next[k];
      if (window.Motion) window.Motion.tier = S.tier;
      if (fxWanted) fxSync(fxWanted);
    }, 200);
  });

  // "Reduce motion" switched on while the app is open: finish everything at its natural state and stop for good.
  function goOff() {
    clearLoops();
    g.globalTimeline.getChildren(true, true, true).forEach(function (t) { try { t.totalProgress(1).kill(); } catch (e) {} });
    if (window.ScrollTrigger) window.ScrollTrigger.getAll().forEach(function (t) { t.kill(); });
    g.set('#main *', { clearProps: 'opacity,transform,filter,visibility' });
    document.querySelectorAll('.view-ghost').forEach(function (n) { n.remove(); });
    document.documentElement.classList.remove('motion');
    if (window.FX3D) { try { window.FX3D.off(); } catch (e) {} }
    fxState = 'no';
    S.magnet = false;
    window.Motion = NOOP;
  }
  var rm = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)');
  if (rm && rm.addEventListener) rm.addEventListener('change', function (e) { if (e.matches) goOff(); });

  /* ---------- public API ---------- */
  window.Motion = {
    tier: S.tier,
    active: function () { return g.globalTimeline.getChildren(false, true, true).length; },
    enterView: enter,
    transition: function (prev, next, name) {
      if (prev && prev.id === 'view-check') clearLoops(); // the RED ring must not keep ticking on a hidden view
      if (prev) killIn(prev);
      ghost(prev);
      enter(next, name);
    },
    login: loginIn, shake: shake, errIn: errIn,
    bubble: bubble, chips: chips, typing: typing, clear: clearLoops,
    result: result, echo: echo, tabs: tabs, list: list, expand: expand, collapse: collapse, crossfade: crossfade,
    pillState: pillState, pillGlide: pillGlide,
    fx: fxSync,
    _S: S
  };
})();
