# Vendored libraries (served locally, no CDN, works offline)

Downloaded once with `npm pack` from the public npm registry. Files are copied unmodified.
To upgrade: repeat `npm pack <name>@<version>`, copy the files below, update this table.

| Library | Version | Files | Size | Licence |
|---|---|---|---|---|
| GSAP | 3.15.0 (published 2026-04-13) | `gsap.min.js` | 71.2 KB | GreenSock "Standard no-charge licence", https://gsap.com/standard-license (free for commercial use) |
| GSAP ScrollTrigger | 3.15.0 | `ScrollTrigger.min.js` | 43.5 KB | same |
| GSAP Flip | 3.15.0 | `Flip.min.js` | 24.9 KB | same |
| GSAP SplitText | 3.15.0 | `SplitText.min.js` | 7.6 KB | same |
| Three.js | 0.186.0 / r186 (published 2026-09-08) | `three.module.js` (ES module) + `three.core.js` (imported by it) | 647.2 KB + 1423.9 KB (about 131 KB + 288 KB gzipped) | MIT, see `three.LICENSE` |

Three.js no longer ships a minified build, so the pristine files are used. They are only fetched on a desktop
that passes the gate in `static/motion.js` (width >= 1024px, no reduced motion, WebGL, memory >= 4 GB), never on phones.

SHA-256 of the vendored files:

```
cbe3ca726350f8d230da38a14ce2384e7772e05a45cee6144dd7fe6dde868c2f  Flip.min.js
92bb9a96476f983d212a2bc4f54c889039c1696dd4461d40a736860938570fbb  gsap.min.js
b0b14d67b55b0c43c756ac0b106cfcb09d0879945f6ead64451065b0672916a2  ScrollTrigger.min.js
419f7027a5f086a12cb7988736d8fdd3a6ed2200229661de25b6628ca7ced344  SplitText.min.js
9edde002b066a9a05676a6127f67735b62baf399bdea529f2f7e31657da769e6  three.core.js
9052042d676cb0fdc1ddfefe193053f34b7ac0513a616fdac4535d49987812ea  three.module.js
```

Google Fonts (Inter) stays the only external request in the app.
