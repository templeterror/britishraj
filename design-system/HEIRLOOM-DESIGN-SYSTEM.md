# Heirloom Design System — "Estate Ledger"

Replaces the earlier Kalshi-derived neon-green/dark theme. That direction
read as a crypto trading app; Heirloom is about inheritance, intent, and a
family office's record of decisions — closer to a bound ledger than a
trading terminal. This is the one spec the code should match; if they ever
disagree, fix the code or update this doc in the same change.

## Why this changed

- Neon green (`#00DD94`) on near-black is the default look of crypto
  wallets and trading apps. Heirloom is the opposite of a trading app.
- Money set in a monospace face (IBM Plex Mono) reads like a terminal.
  Private banks and ledgers set numbers in a proportional face with
  tabular figures, not code font.
- The product's own sign-in page had already drifted to a warm,
  serif-wordmark direction while the rest of the app stayed neon-on-black
  — two inconsistent products in one app. This spec unifies them.

## Color

Light, paper-toned canvas by default. (A dense dark variant for Wealth
Managers' working view is a reasonable future addition — not built yet;
don't assume one exists in code until it does.)

| Token | Hex | Role |
|---|---|---|
| `--bg-canvas` | `#F3F4F0` | Paper. The default page background. |
| `--bg-surface` | `#FAFAF7` | Slightly lifted surface (headers, rails). |
| `--bg-elevated` | `#FFFFFF` | Cards, inputs, anything that should read "on top." |
| `--bg-elevated-2` | `#ECECE6` | Hover/active state for elevated surfaces. |
| `--border-subtle` | `#DCDED5` | Default hairlines. |
| `--border-strong` | `#BFC2B5` | Focus/hover borders. |
| `--text-primary` | `#1C1D1A` | Ink. Body text, headings. |
| `--text-secondary` | `#686A5F` | Slate. Supporting text. |
| `--text-tertiary` | `#9A9C8F` | Placeholder/disabled text. |
| `--accent` (Evergreen) | `#1F5A45` | Primary action — buttons, links, selected states. |
| `--accent-hover` | `#27725A` | Hover state for the above. |
| `--brass` | `#A8874A` | Signature accent only — logo ring, rare highlight. Not a button color. |
| `--financial-positive` | `#3C7A5A` | Gains. Deliberately distinct from `--accent`. |
| `--financial-negative` | `#9E3F2E` | Losses (oxblood). |
| `--financial-neutral` | `#797C70` | Flat/unchanged figures. |

**Rule:** `--financial-positive` and `--accent` must stay visually
distinct — one is a brand color, one is a polarity signal, and they
should never be swapped for each other even though both are green.

### Role tints

Roles are told apart by a muted tint plus layout density, not by neon
hue-shifting:

| Role | Token | Hex |
|---|---|---|
| Parent | `--role-parent` | `#1F5A45` (evergreen) |
| Child / Heir | `--role-child` | `#55597F` (muted indigo) |
| Wealth Manager | `--role-wealth-manager` | `#8C6D3F` (muted brass) |

## Typography

- **UI text and body copy:** IBM Plex Sans (`--font-plex-sans`). Unchanged
  — it's a fine, quiet workhorse face.
- **Headings (`h1`, page titles, dashboard section openers):** a serif,
  `--font-heirloom-serif` (Source Serif 4). Used for the wordmark and for
  page-level headings only — never for body copy, labels, or buttons.
  (Fraunces was dropped — it's become a generic "premium SaaS" pick and
  doesn't carry the ledger/estate feeling this product wants.)
- **Numbers (dollar amounts, dates, any tabular figure):** IBM Plex Sans
  with `font-variant-numeric: tabular-nums` (see `.kb-num` in
  `globals.css`) — **not** a monospace font. Monospace reads as code;
  tabular figures in the body face read as money.

## Shape

- `--radius-card: 4px`, `--radius-control: 4px` — small, deliberate
  corners. Not the 8px+ bubbly rounding of a consumer fintech app.
- Badges (role pills, status tags) are not uppercase, not fully-rounded
  pill chrome. Sentence case, `--radius-control` corners.

## Logo

The interlocking-rings mark (original artwork, see `HeirloomLogo.tsx`) in
Evergreen + Brass. No third-party logo assets ship anywhere in this repo.

## Voice in the UI

- Dashboard section openers can use a short serif headline instead of a
  plain card title where it helps (e.g. a family's name), but everything
  below it stays in the plain UI face — don't let the serif voice spread
  into labels, buttons, or data.
- Avoid trailing decorative arrows ("Manage your firm & invite families
  →") and debug-sounding parentheticals ("(read-only access)") — write
  the actual sentence instead.

## Surface treatment — liquid glass

Cards, modals, and the top nav use a shared iOS-style liquid-glass
primitive — translucent white, a strong backdrop blur with saturation
boost, a specular 1px top highlight, a hairline inset outline, and a
soft outer drop shadow. A fixed ambient background sits behind every
page (three low-opacity radial-gradient "blobs" in the brand palette)
to give the glass something to blur over, which is what makes the
effect read as glass instead of as a translucent panel on a flat color.

**Do not** apply this treatment to tables, dense tabular data, or
anything where small-text density matters — translucency hurts scanning
and contrast. Keep those on `--bg-elevated`.

### Tokens

| Token | Value | Role |
|---|---|---|
| `--glass-bg` | `rgba(255, 255, 255, 0.55)` | Surface fill at rest. |
| `--glass-bg-hover` | `rgba(255, 255, 255, 0.68)` | Hover/active state fill. |
| `--glass-border` | `rgba(255, 255, 255, 0.6)` | Reserved for direct-border uses. |
| `--glass-border-inner` | `rgba(28, 29, 26, 0.06)` | Inset outline hairline. |
| `--glass-blur` | `28px` | Backdrop blur radius. |
| `--glass-saturate` | `180%` | Backdrop saturation boost (the iOS move). |
| `--glass-shadow` | composite | 1px specular top highlight (inset) + 1px inner outline (inset) + soft outer drop + close-in micro-shadow. |

The composite `--glass-shadow` is the whole trick — the top-edge
specular highlight is what sells "glass" rather than "translucent card."
Keep all four layers; they're each doing a job.

### Classes

- **`.kb-glass`** — the primitive. Apply directly to any new surface
  that should feel like glass (modals, popovers, side panels).
- **`.kb-card`** — glass + `--radius-card` (14px) + 16px padding. Used
  for every dashboard card (`DashboardCard` in `DashboardShell`).
- **`.kb-role-card`** — glass + role-pick padding + a hover state that
  thickens the fill and lifts the card 1px (via `translateY`).
- **`.kb-nav`** — glass + sticky top positioning + fully pill-rounded
  (`999px`). Used for the dashboard header.

### Ambient background

`body::before` paints three fixed radial gradients in Evergreen, Brass,
and muted Indigo (the role tints) at 14–18% alpha. These sit at `z-index:
-1` behind every page and never respond to pointer events. They give the
glass its blur subject; without them, glass over a flat canvas looks like
a plain opaque card.

### Fallback

A `@supports not (backdrop-filter)` rule drops back to an opaque
`--bg-elevated` surface with a single hairline outline and a tiny
drop-shadow — enough visual separation to keep cards legible on browsers
without backdrop-filter support (older Firefox, some embedded webviews).
Text contrast stays ≥ 4.5:1.

### Clerk components

`<SignIn>`, `<SignUp>`, `<UserProfile>`, etc. inherit the same glass
chrome via `ClerkProvider`'s `appearance.elements.card` override, so the
hosted Clerk UI matches our own cards rather than looking like a solid
dropped-in widget.

## Known gaps / not done in this pass

- No dark variant yet (mentioned above as a reasonable future addition
  for the Wealth Manager workspace).
- No formal spacing scale — spacing is still ad hoc inline styles in a
  few places (`DashboardShell.tsx`, dashboard pages). Worth a token pass
  later, not blocking for the hackathon.
- Accessibility: no visible focus ring beyond the browser default yet.
  Low risk right now since there's little keyboard-trap-prone motion, but
  revisit before this goes further than a demo.
