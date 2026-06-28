# Terrain Tab — Map Design Concepts

> 8 design proposals for the MultiPlanner terrain map as it will appear inside
> NSP_UBT as a second tab. Theme baseline: NSP_UBT dark/light CSS variables,
> HankenGrotesk / GeistMono fonts, same control chrome language.
>
> Designs 1–2 are "faithful" (match NSP_UBT exactly or closely).
> Designs 3–4 use icon markers with flyout action menus.
> Designs 5–8 are imaginative departures.

---

## Design 1 — Faithful Clone

**Concept:** Drop the terrain layer group into NSP_UBT's existing three-column
map layout without changing anything else. A user switching to the terrain tab
sees an identical shell with one new collapsible section at the bottom of the
left panel.

```
┌────────────────────────────────────────────────────────────────────────┐
│  NSP_UBT  [Dashboard] [Map ●] [Source Explorer] [Import] ...           │
├──────────────┬─────────────────────────────────────┬───────────────────┤
│ LAYERS       │                                     │  INSPECTOR        │
│              │                                     │                   │
│ Basemap      │                                     │  Click a feature  │
│  ○ OSM       │                                     │  to inspect it.   │
│  ● Esri Img  │                                     │                   │
│              │     Leaflet map — hillshade tiles   │                   │
│ Overlays     │     under existing site/link layer  │                   │
│  ✓ Links     │                                     │                   │
│  ✓ Sites     │     (same dots, same coloured       │                   │
│  □ NSP NEs   │      link lines, same labels)       │                   │
│  □ BNetzA    │                                     │                   │
│  □ Site Trk  │                                     │                   │
│              │                                     │                   │
│ ▼ Terrain    │ ╔══ Probe popup ════════════╗       │                   │
│   Prov [NRW] │ ║ WZO-MW-001               ║       │                   │
│   □ DGM      │ ║ DGM  289.6 m             ║       │                   │
│   □ DOM      │ ║ DOM  301.2 m             ║       │                   │
│   □ nDSM     │ ║ nDSM  11.6 m            ║       │                   │
│   Opacity 60%│ ╚══════════════════════════╝       │                   │
│   [⛰ Probe] │                                     │                   │
└──────────────┴─────────────────────────────────────┴───────────────────┘
```

**Theme integration:** Zero delta. Reuses every existing CSS class, control
pattern, and colour variable. The terrain group follows the identical
collapsible-section component used for every other layer group.

**Effort:** Lowest — only map.js + map_layers_panel.py changes.

**Distinguishing detail:** Terrain tiles appear as a semi-transparent hillshade
texture under the site/link network. Link colours remain Primary-blue /
Nominal-brown. Probe popup is a styled Leaflet popup matching existing
popup.nsp-popup CSS.

---

## Design 2 — Compact Icon Rail

**Concept:** Same content as Design 1 but the left LayersPanel collapses to a
vertical icon rail at rest (≈40 px wide), expanding on hover or click. Gives
≈220 px more map width on smaller screens. Terrain group sits at the bottom of
the expanded rail alongside existing overlay groups.

```
┌───┬──────────────────────────────────────────────────────┬────────────┐
│ ☰ │                                                      │ INSPECTOR  │
│   │                                                      │            │
│ 🗺 │                                                      │            │
│   │      Full-width Leaflet map                          │            │
│ 🔗 │      Hillshade + network overlay                     │            │
│   │      Site dots · Link lines · Labels                 │            │
│ 📡 │                                                      │            │
│   │                                                      │            │
│ ⛰ │◄── hover ──────────────────────────────────────────► │            │
│   │  ┌─ Terrain ──────────────────────┐                  │            │
│   │  │  Provider  [geobasis-nrw  ▼]   │                  │            │
│ 🔍 │  │  □ DGM (hillshade)            │                  │            │
│   │  │  □ DOM (surface)              │                  │            │
│   │  │  □ nDSM (vegetation)          │                  │            │
│   │  │  Opacity [━━━━━○━━━━━] 60%    │                  │            │
│   │  │  [⛰ Probe mode]               │                  │            │
│   │  └───────────────────────────────┘                  │            │
└───┴──────────────────────────────────────────────────────┴────────────┘
```

Rail icons (top to bottom): Basemap selector · Overlays · Links · Sites ·
Terrain · Search. Each expands a panel on click, collapsing others.

**Theme integration:** Inherits all NSP_UBT CSS variables. Rail uses
`var(--panel-bg)` and `var(--icon-fg)` from the existing theme. Rail icons are
SVG matching the existing icon set in the NSP_UBT source explorer toolbar.

**Effort:** Medium. Requires refactoring `map_layers_panel.py` to support
collapsed/expanded mode; map.js gains a `resizeMap()` call on panel toggle.

---

## Design 3 — Tower Icons + Flyout Action Menu

**Concept:** Site markers become SVG tower silhouettes. Click opens a compact
flyout menu anchored to the icon with four quick actions. Links remain coloured
polylines. This is the primary icon-on-map-surface design.

```
         Tower icon (SVG, 24×32 px, colour = link state of primary link)
              │
              ▼
         ╔════╪════╗    ← flyout anchors top-left of icon
         ║  WZO-   ║
         ║  MW-001 ║
         ╟─────────╢
         ║ ⛰ Probe ║ ← fires POST /probe/multi, shows result inline
         ║ 🔍 Inspect ║ ← opens right-panel inspector
         ║ ↔ Corridor ║ ← activates corridor mode with this as Site A
         ║ 📋 Copy   ║ ← copies lat,lon to clipboard
         ╚═════════╝
```

**Marker states:**

```
Primary-linked site    DOM-linked site       No active link
  🗼 (blue)              🗼 (amber)             🗼 (grey, 60% opacity)

Hovered                 Selected              Probe loading
  🗼 + glow ring         🗼 + solid ring        🗼 + spinner overlay
```

**Link lines:** Same coloured polylines as existing NSP_UBT map. At zoom ≥14,
animated dashes flow along Primary links in the direction of site_a → site_b.

**Terrain tiles:** Hillshade visible when DGM checkbox is active. Tower icons
render above the raster so they're always legible.

**Flyout implementation:** Leaflet custom `L.popup` with `closeButton: false`,
`autoPan: false`. CSS: `background: var(--panel-bg)`, `border: 1px solid
var(--border)`, `border-radius: 8px`, `box-shadow: var(--shadow-md)`. Closes
on map click, on Escape, or on any other icon click.

**Theme integration:** Tower SVG uses `var(--accent-primary)` (blue) for active,
`var(--accent-secondary)` (amber) for Nominal, `var(--fg-muted)` for inactive.
Flyout background and border match inspector panel exactly.

**Effort:** Medium. SVG tower icon + Leaflet divIcon. Flyout is a styled popup.
No new panels needed.

---

## Design 4 — Sector Antenna Icons + Rich Slide-Up Card

**Concept:** Site markers show a directional antenna diagram — a fan sector
pointing in the bearing of its longest link. A coloured status badge sits at
the icon's base. Click opens a "rich card" that slides up from the bottom edge
of the map (not a popup), showing full terrain probe data and multi-source
reconciliation summary at a glance.

```
         Sector antenna icon (SVG):
         ┌────┐
         │ ╱▓╲│  ← sector fan in link bearing, filled with link-state colour
         │  ┃  │  ← mast stem
         │ ●  │  ← status dot (green/amber/red/grey)
         └────┘

         Click → slide-up card from bottom:
┌──────────────────────────────────────────────────────────────────────┐
│ ╳  WZO-MW-001  ·  Wuppertal  ·  ● Active (30x)                      │
│ ─────────────────────────────────────────────────────────────────────│
│  LINKS  3 Primary  ·  1 Nominal          NSP  2 NEs  ·  BNetzA  4   │
│ ─────────────────────────────────────────────────────────────────────│
│  TERRAIN  [geobasis-nrw]                                             │
│   DGM  289.6 m     DOM  301.2 m     nDSM  11.6 m   [⟳]             │
│ ─────────────────────────────────────────────────────────────────────│
│  [Open full inspector]   [→ Corridor]   [Download terrain here]      │
└──────────────────────────────────────────────────────────────────────┘
```

The card occupies the bottom ~180 px of the map area. Map pans up slightly to
keep the selected site visible above the card. Closing the card slides it back
down (CSS `transform: translateY`).

**Icon variation by site type:**

```
Backbone site    POP site         Partner site     Repeater
  ╱▓▓▓╲           ╱░░░╲            ╱▒▒╲             ╱▓╲
  ║════║           ║ ◈  ║           ║   ║             ║ ║
  (tall mast)      (dish)           (small)           (small)
```

**Theme integration:** Slide-up card background `var(--surface-2)`, typography
matches inspector panel. Status dot colours from `ellipse_status.py` mapping
reused. "Open full inspector" button activates the existing right-panel inspector
(card closes, inspector opens).

**Effort:** Medium-high. Custom SVG icon per site type + slide-up card animation.
Terrain probe fires lazily on card open.

---

## Design 5 — Terrain-First Immersive

**Concept:** Terrain raster is the dominant visual at full opacity. Network
overlay is reduced to semi-transparent luminous dots and hairline links that
float above the texture. All chrome collapses by default. Controls appear as
floating pill-buttons that minimise to icons when idle.

```
┌────────────────────────────────────────────────────────────────────────┐
│  [⊞ NRW DGM]  [⊞ DOM]  [⊡ nDSM]       [🔍]  [⛰ Probe]  [↔ Corridor] │  ← floating top bar, 36px
│                                                                         │
│                                                                         │
│      ░░░░▓▓▓▓▓░░░░▓▓▓▓▓▓░░  ← hillshade terrain                       │
│    ░░░░░░▓▓▓▓▓▓▓▓▓░░░░░░░░░░                                           │
│    ░▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░  ○────────────○  ← luminous site dots     │
│    ░░░▓▓▓▓░░░░░░░░░░░░░        ╲          ╱    and hairline links       │
│    ░░░░░░░░░░░░░░░░░░░░░        ○────────○     (blue = Primary)         │
│    ░░░░░░░░░▓▓▓▓░░░░░░░░                                               │
│    ░░░░░░░▓▓▓▓▓▓▓░░░░░░░░                                              │
│                                                                         │
│                                    ╔══ Probe result card ════╗          │
│                                    ║ 50.9687°N 7.5967°E      ║          │
│                                    ║ ▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬  ║          │
│                                    ║ DGM   289.6 m           ║          │
│                                    ║ DOM   301.2 m           ║          │
│                                    ║ nDSM   11.6 m          ║          │
│                                    ╚════════════════════════╝          │
│  [+] [-]        NRW 1m DEM · OpenStreetMap basemap               [⊙]  │
└────────────────────────────────────────────────────────────────────────┘
```

**Network overlay rendering in immersive mode:**
- Site dots: 8 px `radial-gradient(circle, rgba(255,255,255,0.9), transparent)`
  — glowing white dots regardless of status (status shown only on click)
- Link lines: 1.5 px, `rgba(29, 78, 216, 0.55)` for Primary,
  `rgba(139, 69, 19, 0.45)` for Nominal

**Probe result card:** Glass morphism — `backdrop-filter: blur(12px)`,
`background: rgba(var(--surface-rgb), 0.75)`, rounded corners, subtle shadow.
Appears at the click position (clamped to viewport edges).

**Top bar behaviour:** Idle for 4 s → pills shrink to icon-only (label hides).
Hover → labels expand. One active "mode" button highlighted in
`var(--accent-primary)`.

**Theme integration:** CSS variables still drive colours but in their
`rgba()` form for transparency. HankenGrotesk font on probe card.

**Effort:** Medium. The challenging part is the glass morphism probe card and
pill animation. Map tile rendering is unchanged.

---

## Design 6 — Dual-Pane Synchronized

**Concept:** The terrain tab splits the available width 50/50. Left pane: NSP_UBT
inventory map (all existing overlays, inspector). Right pane: terrain hillshade
(DGM/DOM/nDSM tiles, probe mode). Both panes are pan/zoom synchronised by
default. A divider can be dragged left or right. A lock icon in the centre of
the divider toggles sync.

```
┌──────────────────────────────┬─┬──────────────────────────────────────┐
│ INVENTORY MAP                │🔒│ TERRAIN MAP                          │
│ (NSP_UBT Leaflet map)        │ │ (MultiPlanner raster tiles)          │
│                              │ │                                       │
│  ○───────○   (link lines)    │ │  ░░▓▓▓▓▓░░░░░░░░  (hillshade)       │
│     ╲         Blue=Primary   │ │  ░░░▓▓▓▓▓▓░░░░░░                    │
│      ○                       │ │  ░░░░▓▓▓▓▓░░░░░░  ○ ─────── ○       │
│                              │ │  ░░░░░░░░░░░░░░░░    (same sites,   │
│  [Layers ▼] [Operator ▼]    │ │                       semi-transp.)  │
│                              │ │                                       │
│                              │ │  ╔═══ Probe ═══════╗                 │
│  ┌── Inspector ────────────┐ │ │  ║ DGM  289.6 m    ║                 │
│  │ WZO-MW-001              │ │ │  ║ DOM  301.2 m    ║                 │
│  │ Ellipse: 3 links        │ │ │  ║ nDSM  11.6 m   ║                 │
│  │ BNetzA: 4 licenses      │ │ │  ╚════════════════╝                 │
│  └─────────────────────────┘ │ │                                       │
│                              │ │  Provider [NRW ▼]  [⛰ Probe mode]   │
└──────────────────────────────┴─┴───────────────────────────────────────┘
                                    drag divider ←→
```

**Sync behaviour:**
- Pan left → right map follows (same centre/zoom)
- Zoom left → right map follows
- Click site on left → same site highlighted on right pane
- Click on right in probe mode → probe fires; result shown on right; site
  name label appears on left pane at same location

**Divider lock states:**

```
🔒 Locked — both maps share viewport
🔓 Unlocked — maps scroll independently (useful for comparing different areas)
```

**Theme integration:** Same NSP_UBT CSS for the left pane (zero change). Right
pane uses the same CSS variable sheet with a `data-pane="terrain"` modifier
that lightens the toolbar to distinguish it visually.

**Effort:** High. Requires managing two independent Leaflet map instances and
synchronising their events without infinite recursion.

---

## Design 7 — Command Palette / Glassmorphism

**Concept:** Zero persistent sidebar chrome. Full-screen Leaflet map. All
controls live inside a command palette (Ctrl+K / ⌘K). Site markers are minimal
glass dots. A glass panel materialises on feature hover. Everything feels like
a modern "pro" tool — Raycast or Linear aesthetic applied to GIS.

```
┌────────────────────────────────────────────────────────────────────────┐
│                     ┌───────────────────────────────┐                  │
│                     │  ⌘  Search sites, links, cmds │  ← always visible│
│                     └───────────────────────────────┘     top-centre   │
│                                                                         │
│   ░░░░▓▓▓▓▓░░▓▓▓▓░░░░                                                  │
│   ░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░    ·  ────────── ·    ← minimal glass dots      │
│   ░░░░░▓▓▓▓▓▓▓░░░░░░░░                        and hairline links        │
│                                                                         │
│          ┌────────────────────────────────────────┐                     │
│          │ ◉  WZO-MW-001          50.968°N 7.596°E│ ← glass hover card │
│          │ ─────────────────────────────────────── │                    │
│          │   3 Primary  ·  BNetzA 4  ·  NSP 2 NEs │                    │
│          │   DGM —  DOM —  nDSM —    [Probe ↗]    │                    │
│          └────────────────────────────────────────┘                     │
│                                                                         │
│  [+][-]                                                          [⊙]  │
└────────────────────────────────────────────────────────────────────────┘

  Ctrl+K →
  ┌─────────────────────────────────────────────┐
  │  > _                                        │
  ├─────────────────────────────────────────────┤
  │  🗺  Toggle DGM hillshade         DGM        │
  │  🗺  Toggle DOM surface           DOM        │
  │  🗺  Toggle nDSM vegetation       nDSM       │
  │  👁  Switch to Immersive mode                │
  │  ↔  Corridor mode                           │
  │  ⛰  Probe at current centre                 │
  │  🎨  Switch to light theme                   │
  │  ─────────────────────────────────────────  │
  │  WZO-MW-001    site · Active                │
  │  WZO-MW-001-A  link · Primary               │
  └─────────────────────────────────────────────┘
```

**Glass card styling:**
```css
.glass-card {
  background: rgba(var(--surface-rgb), 0.72);
  backdrop-filter: blur(16px) saturate(1.4);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.28);
}
```

**Command palette:** Rendered as a Leaflet `L.Control` at `topleft` with
`position: absolute; left: 50%; transform: translateX(-50%)`. Keyboard
shortcut wired in `map.js`. Results built from the existing GeoJSON features
(site_name, link_name fields) + static command list.

**Theme integration:** Uses all NSP_UBT CSS variables in rgba form.
HankenGrotesk for labels, GeistMono for coordinates and elevation values.

**Effort:** Medium-high. Command palette UX requires careful keyboard nav.
Glass blur has a performance cost on large tile areas — throttle repaint.

---

## Design 8 — Corridor Elevation Profile

**Concept:** Standard three-column layout (same as Design 1). When the user
activates corridor mode and draws or selects a path between two sites, a bottom
panel slides up showing a live elevation cross-section. The chart is the star:
it shows DGM ground line, DOM surface line, and nDSM filled area across the
entire corridor. Dragging along the chart moves a crosshair on the map. Sites
along the corridor appear as vertical markers on the profile with labels.

```
┌──────────────┬───────────────────────────────────────┬───────────────┐
│ LAYERS       │                                       │ INSPECTOR     │
│              │    Leaflet map — terrain + network    │               │
│ ─────────── │                                       │ Corridor:     │
│ ▼ Terrain   │   ○ WZO-MW-001                        │ WZO-MW-001    │
│   ✓ DGM     │    ╲                                  │  → WZO-MW-002 │
│   □ DOM     │     ╲  corridor line (drawn)           │               │
│   □ nDSM    │      ╲                                │ Length: 4.2km │
│   [↔ Corr.] │       ○ WZO-MW-002                   │               │
│             │                                       │ Max DGM: 312m │
│             ╞═══════════════════════════════════════╡ Min DGM: 287m │
│             │ ELEVATION PROFILE  ↔ 4.2 km           │               │
│             │                              ▲ 320m   │ Max nDSM: 15m │
│             │   DOM surface ················│······  │               │
│             │         ╭──╮   ╭─────╮       │        │ [Export CSV]  │
│             │   ──────╯  ╰───╯     ╰────── │ 287m   │               │
│             │  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │        │               │
│             │  nDSM fill (orange, ≤15m)    ▼ 0m    │               │
│             │  DGM ground ─────────────────────────  │               │
│             │  |                    |                │               │
│             │  ○WZO-MW-001          ○WZO-MW-002     │               │
└─────────────┴───────────────────────────────────────┴───────────────┘
   ↑ map area (60% height)    ↓ profile panel (40% height, resizable)
```

**Profile chart details:**

```
  Layers (bottom to top in chart):
    nDSM fill   — orange semi-transparent area from DGM up to DOM
    DGM line    — solid green (#22c55e), 2px
    DOM line    — dashed blue (#3b82f6), 1.5px
    Crosshair   — vertical grey line, follows mouse drag
    Site labels — vertical tick marks at site locations with names

  X axis: distance from Site A (metres or km, auto-scaled)
  Y axis: elevation in metres (AMSL for DGM/DOM)

  Profile is sampled at N points along the great-circle path using
  POST /api/v1/probe/multi called in parallel for each sample point.
  Typical: 50 samples → 50 probe calls → results arrive in ~3–8s.
  Chart renders progressively as results arrive.
```

**Crosshair interaction:**

```
  User drags along chart → crosshair line moves
  → map shows a coloured dot at the corresponding position on the corridor
  → tooltip at dot: "1.8 km  |  DGM 295.4 m  |  nDSM 8.2 m"
```

**Theme integration:** Chart rendered in SVG (no library dependency).
Colours from NSP_UBT CSS vars: `--accent-success` (green/DGM),
`--accent-primary` (blue/DOM), `--accent-warning` (orange/nDSM fill).
Bottom panel uses same background and border as inspector panel.

**Effort:** Highest of the 8. Parallel probe sampling, SVG chart with live
crosshair, and resizable split layout. Delivers the most immediate terrain
planning value for microwave LOS work.

---

## Comparison Matrix

| # | Name | Icon markers | Flyout menu | Terrain visible | Complexity | Best for |
|---|---|---|---|---|---|---|
| 1 | Faithful Clone | Dots (existing) | No | Overlay | Low | Default drop-in |
| 2 | Compact Rail | Dots (existing) | No | Overlay | Medium | Small screens |
| 3 | Tower Icons + Flyout | SVG towers | 4-item menu | Overlay | Medium | Daily operations |
| 4 | Sector Icons + Slide Card | Directional fans | Rich bottom card | Overlay | Med-high | Detailed inspection |
| 5 | Terrain-First Immersive | Glow dots | No (card only) | Full-opacity | Medium | Terrain focus |
| 6 | Dual-Pane Sync | Both styles | Via inspector | Side-by-side | High | Comparison work |
| 7 | Command Palette Glass | Glass dots | Glass hover card | Overlay | Med-high | Power users |
| 8 | Corridor Profile | Dots/icons | Via inspector | Overlay + chart | Highest | LOS corridor planning |

## Recommended path

**Start with Design 1** (faithful clone, lowest risk, fastest to ship).
Add **Design 3** (tower icons + flyout) as a user preference toggle —
"Use icon markers" checkbox in the terrain layer group. This gives users
both behaviours with one setting.

**Design 8** (elevation profile) is the highest-value addition for actual
microwave planning. Implement it after the terrain tile overlay is stable.
