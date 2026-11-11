# SwitchBlade Finished UI Specification (`UI_SPEC.md`) — For Antigravity

Integrate this finished **Neo-Clean SaaS (Minimalistic Light Mode)** design system, isolated Landing Page (`/`), and Live Workspace Cockpit (`/workspace`) directly into the `SwitchBlade/ui/` architecture served by FastAPI (`proxy.py` on port `8002`).

---

## 1. Non-Negotiable Visual & Structural Requirements

1. **Color Theme — Theme 1: Neo-Clean SaaS (Minimalistic Light Mode)**:
   - **60% Base (Alabaster Chalk)**: `#F8FAFC` — Page backgrounds, table row alternating fills, subtle container wells. Cards use crisp `#FFFFFF` surfaces.
   - **30% Structure (Charcoal Ink)**: `#0F172A` — Primary headings, body text, `1.5px solid #0F172A` neo-brutalist/neo-clean borders, and `4px 4px 0px #0F172A` structural card shadows.
   - **10% Accent (Royal Indigo)**: `#4F46E5` (hover `#4338CA`, soft tint `#EEF2FF`) — Active buttons, focus rings, link hover states, and active telemetry highlights.
2. **Header & Brand Lockup Cleanup**:
   - **Remove `"01 / "` from `"01 / Workspace"`**: All navigation links, breadcrumbs, and page headers must read **`Workspace`** (never `"01 / Workspace"`).
   - **Custom SwitchBlade SVG Logo (`/ui/assets/logo.svg` & `/logo.svg`)**: Save this exact geometric Circuit-Switch + Blade-Edge SVG to `ui/assets/logo.svg` (and serve it at `/logo.svg` in `proxy.py` so `LiquidGlassLogo` loads it directly):
     ```xml
     <svg width="256" height="256" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
       <path d="M6 9H17L22 4L27 9V14H15L10 19H6V9Z" fill="#FFFFFF"/>
       <path d="M26 23H15L10 28L5 23V18H17L22 13H26V23Z" fill="#4F46E5"/>
       <circle cx="9.5" cy="12.5" r="1.75" fill="#0F172A"/>
       <circle cx="22.5" cy="19.5" r="1.75" fill="#0F172A"/>
     </svg>
     ```
3. **Hero Layout Above the Fold (Where Each Component Lives)**:
   - **Full-Bleed Hero Background**: [ReactDrops `TopographicFlow`](https://reactdrops.dev/components) (`ID: "topographic-flow"`).
   - **Top Center Hero Heading**: [ReactBits `TechText`](https://reactbits.dev/text-animations/tech-text) (`ui/effects/TechText.jsx`) — the interactive vector-path wordmark (`"SwitchBlade"`) where letters turn into dashed vector silhouettes (`dashLength=4`, `dashGap=2`, `strokeWidth=1.5`) under the cursor with a gliding CAD selection frame, dimension labels, 15 blinking specks, draggable spring letters (`bounce=0.4`), and click-kick wave ripple.
   - **Hero Split Stage (Immediately Below the `TechText` Wordmark, Above the Fold)**:
     - **Left Column (6 cols)**: Value proposition card + `[Enter Workspace]` and `[Trigger Live 422 Loop in Workspace]` CTAs.
     - **Right Column (6 cols)**: The 480px tall black-stage [ReactDrops `LiquidGlassLogo`](https://reactdrops.dev/components) (`<LiquidGlassLogo logo="/logo.svg" ending="logo" style={{ height: 480 }} />`).

---

## 2. Exact Component Integrations (`ui/effects/`)

### A. Hero Wordmark Heading: ReactBits `TechText` (`ui/effects/TechText.jsx`)
Reference: [ReactBits Tech-Text](https://reactbits.dev/text-animations/tech-text) (*"A wordmark whose letters turn into dashed vector paths under the cursor"*).
Mount your existing `ui/effects/TechText.jsx` at the top of the Hero with these exact Official ReactBits props:

```jsx
import TechText from './TechText';

export function HeroTechTextWordmark() {
  return (
    <TechText
      text="SwitchBlade"
      fontWeight={800}
      fontSize={120}
      letterSpacing={-0.04}
      align="center"
      color="#0F172A"
      accentColor="#4F46E5"
      reveal="letter"
      reach={200}
      softness={0.7}
      dashLength={4}
      dashGap={2}
      lineStyle="dashed"
      strokeWidth={1.5}
      specks={15}
      selection={true}
      labels={true}
      draggable={true}
      bounce={0.4}
      clickKick={true}
      intro="assemble"
      introDuration={2}
      guides={true}
      sweep={true}
      speed={1}
    />
  );
}
```

### B. Hero Right-Column Emblem Stage: ReactDrops `LiquidGlassLogo` (`ID: "liquid-glass-logo"`)
Install the existing [ReactDrops](https://reactdrops.dev/components) component `"Liquid Glass Logo"` (`ID: "liquid-glass-logo"`) inside `ui/effects/`:

```bash
cd ui/effects
npx shadcn@latest add https://reactdrops.dev/r/liquid-glass-logo.json
```

Use the installed files as the source of truth. Preserve the sphere-to-tile glass entrance, wavelength-based bevel refraction, chromatic edge streaks, measured responsive fitting, reduced-motion support, and the image fallback. Finish on the original SwitchBlade logo (`/logo.svg`) alone at its normal size, on a black background (`#000000`), without a second text reveal. Mount it right in the Hero right-hand column with this exact configuration:

```jsx
import { LiquidGlassLogo } from './components/liquid-glass-logo';

export function Example() {
  return (
    <LiquidGlassLogo
      logo="/logo.svg"
      ending="logo"
      style={{ height: 480 }}
    />
  );
}
```

### C. Hero Full-Bleed Background: ReactDrops `TopographicFlow` (`ID: "topographic-flow"`)
Install the existing [ReactDrops](https://reactdrops.dev/components) component `"Topographic Flow"` (`ID: "topographic-flow"`) inside `ui/effects/`:

```bash
cd ui/effects
npx shadcn@latest add https://reactdrops.dev/r/topographic-flow.json
```

Use the downloaded implementation as the source of truth. Preserve the smoothly evolving elevation field, connected contour paths, mixed dashed survey lines, reduced motion, visibility pausing, and cleanup:

```jsx
import { TopographicFlow } from './components/topographic-flow';

export function HeroTopographicBackground() {
  return (
    <TopographicFlow
      animateEntrance={true}
      scale={480}
      density={5}
      speed={1.5}
      distortion={2.4}
      lineWidth={1}
      opacity={1}
      dashLength={7}
      dashGap={8}
      seed={42}
      gradientDiffusion={0}
      paused={false}
      hover={0.6}
      hoverRadius={200}
      hoverFollow={0.16}
      hoverFade={0.8}
      hoverEffect={"rings"}
      backgroundColor={"#ffffff"}
      backgroundImage={"none"}
      gradientColors={[]}
      grain={0}
      lineColor={"#000000"}
      accentColor={"#000000"}
      lineStyle={"solid"}
    />
  );
}
```

---

## 3. Copy-Paste Prompt for Antigravity

Paste this prompt directly into Antigravity:

> Read `UI_SPEC.md` and `switchblade_finished_ui.html`. Update our `ui/` directory (`ui/dashboard.html`, `ui/assets/site.css`, `ui/assets/site.js`, `ui/assets/logo.svg`, and `ui/effects/`) and `proxy.py` to match this exact finished UI:
> 1. Apply **Theme 1: Neo-Clean SaaS** (`#F8FAFC` Alabaster Chalk base, `#0F172A` Charcoal Ink structure/borders, `#4F46E5` Royal Indigo accent) and remove `"01 / "` from `"01 / Workspace"` everywhere.
> 2. Save our custom geometric SwitchBlade SVG to `ui/assets/logo.svg` and serve it at `GET /logo.svg` in `proxy.py`.
> 3. Separate the `/` Landing Page from the `/workspace` Cockpit route.
> 4. In the Landing Page Hero (above the fold):
>    - Mount **ReactBits `TechText`** (`ui/effects/TechText.jsx`, per `https://reactbits.dev/text-animations/tech-text`) as the top hero wordmark (`text="SwitchBlade"`, dashed vector outlines under the cursor with `dashLength={4}`, `dashGap={2}`, `strokeWidth={1.5}`, gliding selection frame, dimension labels, 15 blinking specks, draggable spring letters, and click-kick ripple).
>    - Mount **ReactDrops `LiquidGlassLogo`** (`npx shadcn@latest add https://reactdrops.dev/r/liquid-glass-logo.json`) directly in the right column of the Hero on a 480px black stage (`<LiquidGlassLogo logo="/logo.svg" ending="logo" style={{ height: 480 }} />`).
>    - Mount **ReactDrops `TopographicFlow`** (`npx shadcn@latest add https://reactdrops.dev/r/topographic-flow.json`) as the Hero background canvas with the exact props in `UI_SPEC.md` Section 2C.
> 5. Connect `/workspace` to our FastAPI endpoints (`GET /state`, `GET /events`, `GET /ledger/entries`, `POST /escrow/decision`, `POST /vaccine/promote`, `POST /vaccine/rollback`, `POST /escrow/reset`), keep the interactive fallback simulation when offline, and run `npm run build` inside `ui/effects` to bundle `ui/assets/effects.js`.