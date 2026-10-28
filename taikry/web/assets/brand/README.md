# ZYROX AI — Official Brand Assets & Motion Identity System

> **Brand:** ZYROX AI  
> **Tagline:** Read the Market. Own Your Edge.  
> **Aesthetic:** Institutional Financial Terminal · Emerald Precision · Quantum Execution  

---

## 🎨 Brand Palette Tokens

| Token | Hex Value | Semantic Role |
| :--- | :--- | :--- |
| `--zyrox-bg` | `#060B09` | Deep institutional cockpit background |
| `--zyrox-surface` | `#0B1511` | Card and panel base surface |
| `--zyrox-surface-raised`| `#102019` | Elevated widgets, modals, and dropdowns |
| `--zyrox-border` | `#20372C` | Subtle structure borders |
| `--zyrox-primary` | `#00D99A` | Authentic institutional emerald green |
| `--zyrox-primary-hover`| `#16E6AB` | Vibrant laser emerald accent |
| `--zyrox-text` | `#EAFFF5` | Primary crisp white text |
| `--zyrox-text-secondary`| `#87A99A` | Secondary metadata and labels |
| `--zyrox-text-muted` | `#60796D` | De-emphasized timestamps & guides |

---

## 📁 Deliverables Directory

This directory contains the production-ready assets for the ZYROX AI trading platform:

### 1. Vector Master Assets
- **[`zyrox-logo.svg`](./zyrox-logo.svg)**: Master scalable static vector logo (320×64). Contains geometric Z-shield monogram, crisp "ZYROX AI" typography, and tagline.
- **[`zyrox-logo-loop.svg`](./zyrox-logo-loop.svg)**: Seamless infinite loop animated logo (320×64) with dual-layer emerald light sweep, quantum nexus pulse, and metallic wordmark shimmer. Powered by hardware-accelerated CSS keyframes with 0 KB JavaScript overhead and zero layout shift.
- **[`zyrox-logo-hero.svg`](./zyrox-logo-hero.svg)**: Cinematic 800×450 vector presentation for landing hero sections, splash screens, and modal showcases.
- **[`zyrox-logo-icon.svg`](./zyrox-logo-icon.svg)**: 512×512 square high-contrast app icon with beveled shield and quantum nexus, optimized from 16px favicon to 512px retina display.
- **[`favicon.svg`](./favicon.svg)**: Lightweight browser tab favicon.

### 2. Raster Deliverables
- **[`zyrox-logo-static.png`](./zyrox-logo-static.png)**: High-resolution PNG master logo with alpha channel.
- **[`zyrox-logo-icon.png`](./zyrox-logo-icon.png)**: 512×512 PNG app icon for PWA and mobile home-screen bookmarks.

### 3. Video & Animation Loops
- **[`zyrox-logo-loop.webm`](./zyrox-logo-loop.webm)**: Ultra-efficient VP9 video loop (4.5s @ 30 FPS) with seamless boundary continuity (frame 0 == frame 135).
- **[`zyrox-logo-loop.mp4`](./zyrox-logo-loop.mp4)**: Universal H.264 video loop with `+faststart` metadata for instant browser playback without buffering.
- **[`zyrox-logo-loop.gif`](./zyrox-logo-loop.gif)**: Optimized 24 FPS palette-quantized GIF loop for third-party embeds, Telegram, and Discord bots.
- **[`zyrox-logo-hero.mp4`](./zyrox-logo-hero.mp4)**: 1280×720 HD widescreen hero animation loop.

---

## 🚀 Website Integration Guidelines

### 1. Main Header & Sidebar (Recommended: SVG Loop)
```html
<a href="/dashboard/" class="terminal-brand" aria-label="ZYROX AI Dashboard">
  <img 
    src="/assets/brand/zyrox-logo-loop.svg" 
    alt="ZYROX AI — Read the Market. Own Your Edge." 
    class="zyrox-brand-logo"
    width="210" 
    height="42"
    loading="eager"
    decoding="async"
  >
</a>
```

### 2. Video Loop Implementation (Optional Native Video Tag)
```html
<video 
  class="zyrox-logo-video"
  autoplay 
  muted 
  loop 
  playsinline 
  preload="metadata"
  aria-label="ZYROX AI Animated Motion Logo"
>
  <source src="/assets/brand/zyrox-logo-loop.webm" type="video/webm">
  <source src="/assets/brand/zyrox-logo-loop.mp4" type="video/mp4">
  <img src="/assets/brand/zyrox-logo-static.png" alt="ZYROX AI Logo">
</video>
```

### 3. Accessibility & Reduced Motion Support
The SVG loop natively respects `prefers-reduced-motion: reduce`:
```css
@media (prefers-reduced-motion: reduce) {
  .zyrox-anim-logo *,
  .shield-interactive-group,
  .nexus-core,
  .nexus-halo {
    animation: none !important;
  }
}
```

---

## 🛠 Regenerating Brand Assets
To rebuild all raster PNGs, MP4s, WebM, and GIFs:
```bash
python scripts/generate_brand_assets.py
```
*Requirements: Python `pillow` and system `ffmpeg`.*

