# Heirloom Design System

Generated via `ui-ux-pro-max`, built on the existing dark bg / `#00DD94`
accent, fintech color/typography/chart conventions, and an 8px spacing
rhythm. This is the reference for all three dashboards (Parent, Child/Heir,
Wealth Manager) and the auth flow.

## 1. Color System

### Core neutrals
| Token | Hex | Use |
|---|---|---|
| `bg-canvas` | `#0A0A0A` | App background (unchanged) |
| `bg-surface` | `#0D1016` | Page sections, sidebar |
| `bg-elevated` | `#13171F` | Cards, panels |
| `bg-elevated-2` | `#1B2029` | Nested cards, popovers, inputs |
| `border-subtle` | `#242A35` | Dividers, default borders |
| `border-strong` | `#3A4250` | Active/focused containers |
| `text-primary` | `#F2F5F7` | Headings, primary text |
| `text-secondary` | `#9AA4B2` | Labels, secondary data |
| `text-tertiary` | `#5C6472` | Disabled, timestamps |

**Rule:** never pure black (`#000`) or pure white (`#FFF`) — both read harsh
on OLED and break the near-black brand feel. Everything is cool-tinted, not
neutral gray, to avoid a generic "admin panel" look.

### Brand accent
| Token | Hex / Value | Use |
|---|---|---|
| `accent` | `#00DD94` | Primary CTA, links, active nav |
| `accent-hover` | `#1FE8A3` | Hover state |
| `accent-muted` | `#00DD94 @ 12%` | Pills, badges, selected-row bg |
| `accent-on-accent` | `#042016` | Text/icons on solid accent fill |

### Financial polarity (deliberately distinct from brand accent)
The brand green must not collide with the universal "gains are green"
fintech convention — using one green for both reads a brand CTA as a gain
indicator, or a gain number as "just the theme color."

| Token | Hex | Use |
|---|---|---|
| `financial-positive` | `#2DD4A3` | Gains, inflows (close to accent, not identical) |
| `financial-negative` | `#F4694B` | Losses, outflows, negative change |
| `financial-neutral` | `#A3ACB9` | Zero/flat change |

Never rely on color alone — pair every positive/negative value with a
▲/▼ glyph or explicit sign.

### Semantic status (separate from financial polarity — system states)
| Token | Hex | Use |
|---|---|---|
| `success` | `#22C55E` | Action succeeded, verified |
| `warning` | `#F5A623` | Needs attention, review required |
| `danger` | `#EF4444` | Errors, destructive actions |
| `info` | `#3B9EFF` | Informational banners, tooltips |

Keeping `success`/`danger` separate from `financial-positive`/`negative`
matters: a market loss is a normal outcome, not an error — conflating the
two makes ordinary volatility feel alarming.

### Data-visualization palette (categorical, colorblind-safe, ordered — assign in this order, never ad hoc)
1. `#00DD94` (brand)
2. `#3B9EFF` (blue)
3. `#F2B84B` (amber)
4. `#C084FC` (violet)
5. `#F4694B` (coral)
6. `#67E8F9` (cyan)
7. `#A3ACB9` (neutral, for "other/inactive" buckets)

Max 6 active series per chart before switching to small-multiples. Use
stroke pattern (solid/dashed/dotted) for series that must be distinguishable
beyond color. Gridlines at `border-subtle` only, never competing with data.

### Role accent differentiation
Each dashboard keeps the same system but gets a secondary accent so users
instantly know which seat they're in.

| Dashboard | Secondary accent | Feel |
|---|---|---|
| Parent | `#00DD94` (brand, unmodified) | Base — oversight, approval |
| Child / Heir | `#67E8F9` (cyan) | Lighter, "guided/learning" mode |
| Wealth Manager | `#C084FC` (violet) | Professional, distinct, higher density |

Apply the secondary accent as: a status indicator, the role badge in the
header, and chart highlight color for that dashboard — a tint layer on top,
never a full palette replacement of the core brand green CTA color.

## 2. Typography

**Pairing:** IBM Plex Sans (UI text) + IBM Plex Mono (all numeric data).
Plex Sans reads as a banking/fintech trust typeface; Plex Mono shares its
DNA while giving tabular figures, which fintech tables require so digits
don't jitter as values update.

| Role | Font | Size | Weight | Line-height |
|---|---|---|---|---|
| Display (hero balance, big KPI) | Plex Mono | 40px | 500 | 1.1 |
| H1 (page title) | Plex Sans | 28px | 600 | 1.2 |
| H2 (section header) | Plex Sans | 22px | 600 | 1.25 |
| H3 (card title) | Plex Sans | 16px | 600 | 1.3 |
| Body | Plex Sans | 14px | 400 | 1.5 |
| Body small / secondary | Plex Sans | 13px | 400 | 1.5 |
| Caption / label | Plex Sans | 11px | 500, uppercase, +0.02em | 1.3 |
| Table / data figures | Plex Mono | 14px | 400–500 | 1.4 |
| Monetary values (prominent) | Plex Mono | 24px | 500 | 1.2 |

Rules:
- All currency, counts, and dates-as-numbers → always Plex Mono with
  tabular figures, to prevent layout shift on live-updating values.
- Never go below 11px (caption floor).
- Negative numbers: sign + `financial-negative` color, not parentheses —
  parentheses don't fit a live dashboard context.

## 3. Spacing System

4px base unit, dashboard-dense scale (all three roles are data-heavy pages).

| Token | Value | Use |
|---|---|---|
| `space-1` | 4px | Icon-to-label gap, tight inline spacing |
| `space-2` | 8px | Chip/badge padding |
| `space-3` | 12px | Form field padding, table cell padding |
| `space-4` | 16px | Card padding, standard gaps |
| `space-5` | 20px | Section card padding |
| `space-6` | 24px | Section-to-section gaps |
| `space-8` | 32px | Vertical rhythm between major blocks |
| `space-12` | 48px | Page-level top margin |

Grid: 12-column, max-width 1280px, collapse to single/2-column stacks below
768px. Sidebar nav fixed width, collapsible.

## 4. Components

**Cards** — `bg-elevated`, 1px `border-subtle`, 8px radius, `space-4`
padding. No drop shadows (flat dark UI reads cleaner on near-black) — use
`border-strong` at 40% opacity instead of shadow to imply elevation. KPI
cards: caption label, value in Plex Mono display/large size, delta chip
(▲/▼ + % in `financial-positive`/`negative` color).

**Tables** — Row height 44px. Header row: `text-secondary`, 12px caption
style, sticky on scroll. No zebra striping — `border-subtle` row dividers
only; use `financial-positive`/`negative` text color on the value itself,
not the row. Numeric columns right-aligned, tabular figures. Row hover:
`accent-muted` background. Sortable headers use a direction glyph, never
color alone.

**Buttons** — Primary: solid `accent` fill, `accent-on-accent` text, 6px
radius, 40px height. Secondary: outline/transparent fill, `border-subtle`,
`text-primary` text. Destructive: visually and spatially separated from
primary actions (money-moving actions like "Remove beneficiary" need extra
confirmation). Disabled: 40% opacity, no pointer cursor. Loading: spinner
replaces label, button keeps its width.

**Inputs** — `bg-elevated-2` fill, `border-subtle` default, `accent` border
+ 2px ring on focus. 40px height minimum. Currency inputs: fixed-width
currency symbol prefix, Plex Mono value, helper text for "available
balance." Labels always visible, never placeholder-only — compliance-
sensitive forms (transfers, beneficiary changes) need persistent labels.

**Navigation** — Fixed left sidebar; active item marked with the role's
secondary accent as a 3px left border bar + `bg-elevated` background, never
color alone. Top bar: role switcher (if multi-role access), notification
bell with badge count. Breadcrumbs shown when deeper than 2 levels.

**Badges / status** — Pill shape, `space-1`/`space-2` padding, 11px
uppercase caption text. Always icon + text + color, never color alone
(e.g. ● Verified / ✕ Failed). Role badges use the secondary accent as a
subtle background tint, not full saturation.

## 5. Fintech & Dashboard-Specific Guidance

**Data density**
- Wealth Manager: high density — multi-client tables, compact rows, more
  columns visible (a pro tool used all day).
- Parent: medium density — bigger KPI cards up top, approval queues below.
- Child/Heir: low density — larger type, more whitespace, fewer
  simultaneous numbers, more explanatory copy ("goal" framing vs. a bare
  progress bar). Treat this screen as semi-educational.

**Trust & security**
- Mask sensitive identifiers by default (account numbers as •••• 4821),
  click-to-reveal rather than always-visible.
- Show a last-updated timestamp next to every balance/holding figure —
  staleness is a trust issue in finance UI.
- Any money-moving action (withdrawal, beneficiary change) gets a
  confirmation step showing exact amounts, and a success state with a
  reference/confirmation ID.
- Surface security status visibly (last login, device/session list, 2FA
  status) — doesn't need to be prominent, but should be ≤2 clicks from
  account settings.
- Avoid skeuomorphic trust cues (padlocks everywhere, gold gradients) —
  trust in modern fintech comes from clarity and responsiveness, not
  ornamentation.

**Number formatting**
- Currency: two decimal places, comma thousand separators, no abbreviation
  on primary values. "$12.4K" is fine in compact table cells or chart axis
  labels, never on a primary hero value.
- Percentages: 1 decimal place (+3.2%), always signed.
- Dates: absolute + relative together where it matters ("Oct 3, 2026 ·
  3 days ago").
- Large aggregate numbers in charts/axis labels only: 1.2K, 4.5M on the
  axis; exact value on hover/tooltip.

**Chart color rules**
- Positive/negative values use `financial-positive`/`negative`, never
  `accent`/`danger` — keeps the brand green reserved as a UI signal, not a
  data signal.
- Trend lines (e.g. portfolio growth): single-series line chart, `accent`
  or `financial-positive` line with 20%-opacity area fill.
- Multi-holding breakdowns (asset allocation): donut/bar using the 6-color
  dataviz palette, never a pie chart if more than 5 categories.
- Goal tracking (e.g. target allocation): bullet or gauge chart with a
  clear, labeled target marker.
- All charts need tooltips with exact values, and a text/table fallback
  for accessibility.

**Role differentiation summary**

| Aspect | Parent | Child/Heir | Wealth Manager |
|---|---|---|---|
| Density | Medium | Low | High |
| Primary content | Approval queue, oversight of linked accounts | Goal tracking, education | Multi-client table, portfolio tools |
| Tone | Authoritative | Encouraging, simplified | Professional, efficient |
| Accent | Brand green | Cyan | Violet |
| Default landing | Dashboard overview | Balance + goal progress | Client list / portfolio overview |
