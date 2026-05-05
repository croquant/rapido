# Design philosophy

Three principles for server-rendered web apps, in priority order.

## 1. Tablet first

**Why.** Tablet is the hardest target: touch like phone, density like desktop. Design for it, the others fall out.

**Rules.**

- Lay out at tablet width first; phone and desktop follow.
- Don't shrink Pico's default touch targets (buttons, inputs).
- No hover-only affordances. If it's reachable by mouse hover, it must also be reachable by tap.
- No fixed pixel widths. Lean on Pico defaults plus a fluid layout grid.

## 2. Pico CSS + HTMX, minimal AlpineJS, no plain JavaScript

**Why.** Each layer has one job. The smaller the surface, the less to maintain.

**Rules.**

- **Pico** owns typography, forms, tables, buttons, `<dialog>`. Don't fight it.
- **Custom CSS** is for Pico CSS customization, minimal custom elements.
- **HTMX** owns mutations and partial swaps. Use `hx-post`/`hx-get`, `hx-target`, `hx-swap`, and `hx-swap-oob` for cross-component updates (e.g. flash). Use the `HX-Trigger` response header for cross-component refresh.
- **Alpine** is for ephemeral UI state only: open/close, toggle, `$dispatch`. Light form UX (e.g. live slug) is OK. Never for data fetching or DOM building - that's HTMX's job.
- **Zero hand-written JS files.** Vendor both libraries and load them from the base template. No `<script>` blocks with logic.

## 3. Semantic syntax, no inline style

**Why.** Semantic HTML is accessible by default and styled by Pico for free. Inline styles bypass tokens and block future theming.

**Rules.**

- Use semantic tags: `<section aria-labelledby>`, `<article>`, `<dialog>`, `<details>`, `<header>`, `<nav>`.
- Render form fields via a shared component that emits label, `aria-invalid`, and error text.
- Render icons via a shared component backed by an SVG sprite.
- No `style="..."` attributes.
- Accessibility baseline: WCAG 2.1 AA.

## 4. High-contrast industrial

**Why.** Bright rooms, quick reads, gloved hands. Direct beats decorative. Confidence beats comfort.

**Rules.**

- Near-black ink on near-white paper. No mid-grays for primary text.
- One hot accent, used sparingly: primary action, focus ring, current state. Never as decoration.
- Square corners. Don't add `border-radius` on top of Pico defaults; prefer reducing it.
- No shadows. Separate surfaces with 1-2px borders.
- Heavy weight for headings and buttons. Uppercase tracking for short labels (nav, table headers, badges).
- Monospace or geometric sans only. No serifs, no script, no display faces.
- No gradients, no glassmorphism, no pastel fills.
