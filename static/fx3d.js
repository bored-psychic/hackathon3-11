/* Ambient 3D form (Three.js, ES module). Only loaded by static/motion.js when the gate passes:
   width >= 1024px, no reduced motion, WebGL2 available, deviceMemory >= 4 or unknown.
   One soft teal form per view (login: large, home: behind the hero, check: behind the chat).
   Budget: DPR capped at 1.75, no rendering when the tab is hidden or the canvas is off-screen, everything on the GPU
   is disposed on view change, and it steps down (then bows out to the CSS fallback) if frames are slow. */
import * as THREE from './vendor/three.module.js';

// All Three.js logging stays quiet: a failure here must only ever mean "show the static fallback".
THREE.setConsoleFunction(function () {});

const VERT = /* glsl */`
  uniform float uPhase, uAmp, uFreq;
  uniform vec2 uMouse;
  varying vec3 vNormal;
  varying vec3 vView;
  varying float vHeight;

  // 3D simplex noise. Ian McEwan, Ashima Arts (webgl-noise), MIT licence.
  vec3 mod289(vec3 x){return x-floor(x*(1.0/289.0))*289.0;}
  vec4 mod289(vec4 x){return x-floor(x*(1.0/289.0))*289.0;}
  vec4 permute(vec4 x){return mod289(((x*34.0)+10.0)*x);}
  vec4 taylorInvSqrt(vec4 r){return 1.79284291400159-0.85373472095314*r;}
  float snoise(vec3 v){
    const vec2 C=vec2(1.0/6.0,1.0/3.0);
    const vec4 D=vec4(0.0,0.5,1.0,2.0);
    vec3 i=floor(v+dot(v,C.yyy));
    vec3 x0=v-i+dot(i,C.xxx);
    vec3 g=step(x0.yzx,x0.xyz);
    vec3 l=1.0-g;
    vec3 i1=min(g.xyz,l.zxy);
    vec3 i2=max(g.xyz,l.zxy);
    vec3 x1=x0-i1+C.xxx;
    vec3 x2=x0-i2+C.yyy;
    vec3 x3=x0-D.yyy;
    i=mod289(i);
    vec4 p=permute(permute(permute(i.z+vec4(0.0,i1.z,i2.z,1.0))+i.y+vec4(0.0,i1.y,i2.y,1.0))+i.x+vec4(0.0,i1.x,i2.x,1.0));
    float n_=0.142857142857;
    vec3 ns=n_*D.wyz-D.xzx;
    vec4 j=p-49.0*floor(p*ns.z*ns.z);
    vec4 x_=floor(j*ns.z);
    vec4 y_=floor(j-7.0*x_);
    vec4 x=x_*ns.x+ns.yyyy;
    vec4 y=y_*ns.x+ns.yyyy;
    vec4 h=1.0-abs(x)-abs(y);
    vec4 b0=vec4(x.xy,y.xy);
    vec4 b1=vec4(x.zw,y.zw);
    vec4 s0=floor(b0)*2.0+1.0;
    vec4 s1=floor(b1)*2.0+1.0;
    vec4 sh=-step(h,vec4(0.0));
    vec4 a0=b0.xzyw+s0.xzyw*sh.xxyy;
    vec4 a1=b1.xzyw+s1.xzyw*sh.zzww;
    vec3 p0=vec3(a0.xy,h.x);
    vec3 p1=vec3(a0.zw,h.y);
    vec3 p2=vec3(a1.xy,h.z);
    vec3 p3=vec3(a1.zw,h.w);
    vec4 norm=taylorInvSqrt(vec4(dot(p0,p0),dot(p1,p1),dot(p2,p2),dot(p3,p3)));
    p0*=norm.x;p1*=norm.y;p2*=norm.z;p3*=norm.w;
    vec4 m=max(0.5-vec4(dot(x0,x0),dot(x1,x1),dot(x2,x2),dot(x3,x3)),0.0);
    m=m*m;
    return 105.0*dot(m*m,vec4(dot(p0,x0),dot(p1,x1),dot(p2,x2),dot(p3,x3)));
  }

  vec3 displaced(vec3 p){
    vec3 q=p*uFreq+vec3(uMouse.x*0.35,uMouse.y*0.35,uPhase*0.22);
    return p*(1.0+uAmp*snoise(q));
  }

  void main(){
    vec3 p=normalize(position);
    vec3 a=abs(p.y)<0.99?vec3(0.0,1.0,0.0):vec3(1.0,0.0,0.0);
    vec3 t=normalize(cross(p,a));
    vec3 b=cross(p,t);
    float e=0.012;
    vec3 d0=displaced(p);
    vec3 d1=displaced(normalize(p+t*e));
    vec3 d2=displaced(normalize(p+b*e));
    vNormal=normalize(normalMatrix*normalize(cross(d1-d0,d2-d0)));
    vec4 mv=modelViewMatrix*vec4(d0,1.0);
    vView=-mv.xyz;
    vHeight=length(d0)-1.0;
    gl_Position=projectionMatrix*mv;
  }
`;

const FRAG = /* glsl */`
  precision highp float;
  uniform vec3 uColor, uRim;
  varying vec3 vNormal;
  varying vec3 vView;
  varying float vHeight;

  void main(){
    vec3 n=normalize(vNormal);
    vec3 v=normalize(vView);
    vec3 l=normalize(vec3(-0.45,0.75,0.6));
    float wrap=dot(n,l)*0.5+0.5;
    vec3 col=mix(uColor*0.58,uColor,smoothstep(0.15,0.95,wrap));
    col+=uColor*vHeight*0.55;
    float fres=pow(1.0-clamp(dot(n,v),0.0,1.0),2.6);
    col=mix(col,uRim,fres*0.85);
    vec3 h=normalize(l+v);
    col+=pow(max(dot(n,h),0.0),48.0)*0.16;
    gl_FragColor=vec4(col,1.0);
  }
`;

function rgb(hex) { return new THREE.Vector3(((hex >> 16) & 255) / 255, ((hex >> 8) & 255) / 255, (hex & 255) / 255); }
const TEAL = { color: rgb(0x0F766E), rim: rgb(0xA7E3DA), speed: 1 };
const LEVELS = {
  AMBER: { color: rgb(0xF5B544), rim: rgb(0xFFE9BE), speed: 1.6 },
  RED: { color: rgb(0xB42318), rim: rgb(0xFFC9C2), speed: 3.4 },
  GREEN: { color: rgb(0x166534), rim: rgb(0xBFE3CC), speed: 1 }
};
const MODES = {
  // fit: larger = smaller on screen. xf / yf: offset as a fraction of the visible area, so the form keeps clear of the
  // login heading at any window size (ink text on the teal form would fail the 4.5:1 contrast rule).
  login: { sel: '#view-login .login-fx', detail: 32, fit: 1.9, amp: .13, freq: .95, parallax: 1, xf: .1, yf: .17 },
  home: { sel: '#view-home .hero-fx', detail: 22, fit: 1.32, amp: .12, freq: 1, parallax: .6, xf: 0, yf: 0 },
  check: { sel: '#view-check .chat-orb', detail: 16, fit: 1.32, amp: .12, freq: 1, parallax: .35, xf: 0, yf: 0 }
};
const FOV = 35, DPR_MAX = 1.75, ECHO_IN = .5, ECHO_HOLD = 3, ECHO_OUT = 1.2;

const geometries = {};  // JS arrays are kept between views; dispose() only frees the GPU copy
let cur = null;         // the mounted scene
let dead = false;       // gave up for this visit: the CSS fallback stays
let mountId = 0;
const mouse = { x: 0, y: 0 };

window.addEventListener('pointermove', (e) => {
  if (e.pointerType !== 'mouse') return;
  mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
  mouse.y = -((e.clientY / window.innerHeight) * 2 - 1);
}, { passive: true });
document.addEventListener('visibilitychange', () => { if (cur) schedule(cur); });

function geometryFor(detail) {
  if (!geometries[detail]) geometries[detail] = new THREE.IcosahedronGeometry(1, detail);
  return geometries[detail];
}

function fit(c) {
  const w = c.host.clientWidth, h = c.host.clientHeight;
  if (!w || !h) return;
  c.renderer.setSize(w, h, false);
  c.camera.aspect = w / h;
  c.camera.position.z = (c.mode.fit / Math.tan((FOV * Math.PI) / 360)) / Math.min(1, c.camera.aspect);
  c.camera.updateProjectionMatrix();
  c.vh = 2 * c.camera.position.z * Math.tan((FOV * Math.PI) / 360);
  c.vw = c.vh * c.camera.aspect;
}

function dispose(c) {
  if (!c) return;
  c.gone = true;
  if (c.raf) cancelAnimationFrame(c.raf);
  c.raf = 0;
  c.ro.disconnect();
  c.io.disconnect();
  c.canvas.removeEventListener('webglcontextlost', c.onLost);
  c.host.classList.remove('fx-on', 'fx-echo');
  c.mesh.geometry.dispose();
  c.material.dispose();
  c.renderer.dispose();
  try { c.renderer.forceContextLoss(); } catch (e) { /* already gone */ }
  c.canvas.remove();
}

function fail(c) {
  dead = true;
  if (cur === c) cur = null;
  dispose(c);
}

function schedule(c) {
  const want = !c.gone && c.ready && c.onscreen && !document.hidden;
  if (want && !c.raf) { c.last = performance.now(); c.raf = requestAnimationFrame((t) => frame(c, t)); }
  else if (!want && c.raf) { cancelAnimationFrame(c.raf); c.raf = 0; }
}

function echoAmount(c, now) {
  if (!c.echo) return 0;
  const s = (now - c.echo.at) / 1000;
  if (s >= ECHO_IN + ECHO_HOLD + ECHO_OUT) { c.echo = null; c.host.classList.remove('fx-echo'); return 0; }
  const k = s < ECHO_IN ? s / ECHO_IN : s < ECHO_IN + ECHO_HOLD ? 1 : 1 - (s - ECHO_IN - ECHO_HOLD) / ECHO_OUT;
  return k * k * (3 - 2 * k);
}

function frame(c, now) {
  c.raf = 0;
  if (c.gone) return;
  const raw = now - c.last;
  c.last = now;
  const dt = Math.min(raw, 50) / 1000;

  const k = echoAmount(c, now);
  const tgt = c.echo ? c.echo.to : TEAL;
  const u = c.material.uniforms;
  u.uColor.value.lerpVectors(TEAL.color, tgt.color, k);
  u.uRim.value.lerpVectors(TEAL.rim, tgt.rim, k);
  const speed = TEAL.speed + (tgt.speed - TEAL.speed) * k;

  c.phase += dt * speed;
  u.uPhase.value = c.phase;
  c.mx += (mouse.x - c.mx) * .045;
  c.my += (mouse.y - c.my) * .045;
  u.uMouse.value.set(c.mx, c.my);

  const P = c.mode.parallax;
  c.mesh.rotation.y = c.phase * .08 + c.mx * .5 * P;
  c.mesh.rotation.x = Math.sin(c.phase * .05) * .12 - c.my * .35 * P;
  c.mesh.position.x = c.mode.xf * c.vw + c.mx * .1 * P + Math.sin(c.phase * .11) * .03;
  c.mesh.position.y = c.mode.yf * c.vh + c.my * .06 * P + Math.cos(c.phase * .09) * .03;
  c.mesh.scale.setScalar(1 + Math.sin(c.phase * .9) * .018);

  c.renderer.render(c.scene, c.camera);
  c.frames++;
  if (c.frames === 1) c.host.classList.add('fx-on');

  // Quality guard: slow frames first drop the pixel ratio, then hand over to the static fallback.
  if (raw < 250) { c.sampleMs += raw; c.samples++; }
  if (c.samples >= 90) {
    const avg = c.sampleMs / c.samples;
    c.fps = Math.round(1000 / avg);
    c.sampleMs = 0; c.samples = 0;
    if (avg > 45 && c.renderer.getPixelRatio() <= 1) { fail(c); return; }
    if (avg > 26 && c.renderer.getPixelRatio() > 1) { c.renderer.setPixelRatio(1); fit(c); }
  }
  schedule(c);
}

function mount(host, modeName) {
  const id = ++mountId, mode = MODES[modeName];
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, stencil: false, failIfMajorPerformanceCaveat: true });
  } catch (e) { dead = true; return; }
  renderer.setClearColor(0x000000, 0);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, DPR_MAX));

  const material = new THREE.ShaderMaterial({
    vertexShader: VERT, fragmentShader: FRAG,
    uniforms: {
      uPhase: { value: Math.random() * 40 }, uAmp: { value: mode.amp }, uFreq: { value: mode.freq },
      uMouse: { value: new THREE.Vector2() },
      uColor: { value: TEAL.color.clone() }, uRim: { value: TEAL.rim.clone() }
    }
  });
  const mesh = new THREE.Mesh(geometryFor(mode.detail), material);
  const scene = new THREE.Scene();
  scene.add(mesh);
  const camera = new THREE.PerspectiveCamera(FOV, 1, .1, 30);

  const canvas = renderer.domElement;
  canvas.setAttribute('aria-hidden', 'true');
  host.appendChild(canvas);

  const c = { id, host, mode, name: modeName, renderer, material, mesh, scene, camera, canvas, gone: false, ready: false, onscreen: true, raf: 0,
    last: 0, phase: material.uniforms.uPhase.value, mx: 0, my: 0, vh: 1, vw: 1, frames: 0, sampleMs: 0, samples: 0, fps: 0, echo: null };
  c.onLost = (e) => { e.preventDefault(); fail(c); };
  canvas.addEventListener('webglcontextlost', c.onLost);
  renderer.debug.onShaderError = () => fail(c);
  c.ro = new ResizeObserver(() => { if (!c.gone) fit(c); });
  c.ro.observe(host);
  c.io = new IntersectionObserver((list) => { c.onscreen = list[list.length - 1].isIntersecting; schedule(c); });
  c.io.observe(host);
  fit(c);
  cur = c;

  // Compile without stalling the main thread, then start drawing.
  renderer.compileAsync(scene, camera).then(() => {
    if (c.gone || id !== mountId) return;
    c.ready = true;
    schedule(c);
  }).catch(() => fail(c));
}

/* ---------- API used by static/motion.js ---------- */
function sync(name) {
  const mode = MODES[name];
  const host = !dead && mode && window.innerWidth >= 1024 ? document.querySelector(mode.sel) : null;
  if (cur && cur.host === host) return;
  if (cur) { dispose(cur); cur = null; mountId++; }
  if (host) mount(host, name);
}

function echo(level) {
  const to = LEVELS[level];
  if (!cur || !to) return;
  cur.echo = { to, at: performance.now() };
  cur.host.classList.add('fx-echo');
}

function off() {
  dead = true;
  if (cur) { dispose(cur); cur = null; }
}

function stats() {
  return cur
    ? { mounted: cur.name, running: !!cur.raf, frames: cur.frames, fps: cur.fps, pixelRatio: cur.renderer.getPixelRatio(), echo: !!cur.echo, dead }
    : { mounted: null, running: false, frames: 0, fps: 0, pixelRatio: 0, echo: false, dead };
}

export default { sync, echo, off, stats };
