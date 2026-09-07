# FlockGuard AI — Build Checklist

Monorepo: `frontend/` (React + Vite + Tailwind, yarn) and `backend/` (Python + FastAPI).
We work through this list top to bottom. Check items off as they land.

## Phase 0 — Repo & Tooling
- [x] Split repo into `frontend/` and `backend/`
- [x] Root `CHECKLIST.md` (this file)
- [x] Root `README.md` describing monorepo layout
- [ ] Root `docs/architecture.md` (adapt from product brief)

## Phase 1 — Frontend Scaffold
- [x] Install Tailwind CSS + design tokens (colors, Manrope/Inter fonts)
- [x] Install React Router
- [x] Install Zustand
- [x] Install Recharts
- [x] Install PWA plugin (vite-plugin-pwa) + manifest (real icon PNGs still needed)
- [x] Base layout shell: desktop sidebar + mobile bottom nav (Home | Radar | CHECK | Alerts | AI)
- [x] Firebase Authentication client setup (email/password, logout, reset)
- [x] API client wrapper (fetch → FastAPI, attaches Firebase ID token)
- [x] Global Zustand stores: auth/session (`useAuthStore`) + farm/house context (`useAppStore`)

## Phase 2 — Backend Scaffold
- [x] FastAPI app skeleton (`backend/app/main.py`) with CORS
- [x] Firebase Admin SDK token verification dependency (`get_current_user`)
- [x] Firestore client setup
- [x] Cloudinary client setup (signed upload helper)
- [x] Grok API client wrapper (key stays server-side only)
- [x] Risk Engine module (pure Python, deterministic scoring 0–100)
- [x] Alert Engine module
- [x] Core routers: farms, houses, flock-checks, alerts, ask-flockguard
- [x] Remaining routers: flocks, inspections, analytics, media upload endpoint

## Phase 3 — Priority Screens (frontend)
All wired to the live backend and verified end-to-end (Playwright smoke run: register → onboarding → dashboard → flock check → radar → alerts → ask).
- [x] 1. Mobile Flock Check (form: mortality, feed, water, activity, behaviour, crowding/sound, temp/humidity, camera/upload/audio, notes) — `FlockCheckPage`
- [x] 2. Desktop Overview — greeting, needs-attention mini radar, 5 real stat cards (Farm Health, Total Birds, Active Flocks, Active Alerts, Last Check), activity feed — `OverviewPage`
- [x] 3. AI Health Radar (custom React + SVG, concentric risk rings, priority queue) — `RadarPage` + `RadarCanvas`
- [x] 4. House Details (status/score header, stat bar, factor breakdown, recommended actions incl. inline Record Inspection, trend charts, recent checks) — `HouseDetailPage`
- [x] 5. Ask FlockGuard (chat + suggested prompts, real Grok/OpenRouter answers) — `AskFlockGuardPage`
- [x] 6. Alerts (open/resolved/all filter, factor bars, View House/Ask/Acknowledge actions) — `AlertsPage`
- [x] 7. Mobile Home (responsive bottom nav: Home/Radar/CHECK/Alerts/AI) — `AppLayout`
- [x] 8. Onboarding (farm → house → flock, 3-step wizard) — `OnboardingPage`
- [x] Flock Check result screen: "What changed" as icon+headline+detail rows compared against a real rolling baseline (up to 14 prior checks, mirrors Risk Engine's own sample size), AI-generated prose-only "Why FlockGuard flagged it" (via /ask, no duplicated factor bars), deterministic "Recommended inspection priorities" (headline+why, tied to the actual factor), View House / Ask / Record Inspection actions
- [x] Full labeled sidebar (logo+name, all nav, Management section: Team/Settings/Billing, farm switcher, user profile+logout) — `AppLayout`
- [x] Flock Check detail page (`/houses/:houseId/checks/:checkId`, real GET-by-id backend endpoint so refresh/deep-link works) — clickable from Flock Checks list and House Details' recent-checks list — `FlockCheckDetailPage`
- [x] Flocks table redesign: Flock code column (deterministic BR-001/LY-001/BE-001, derived from real start_date ordering per bird type - not random), Age in Day/Week depending on bird type, real current Birds (latest check's bird_count, falls back to initial_bird_count), pill-style status badge (`StatusBadge` `pill` prop) — `FlocksPage`
- [ ] Real FlockGuard logo (`frontend/public/logo.png`) — currently a hand-drawn flat fallback mark; swaps in automatically once the file is added
- [ ] PWA icon PNGs (192/512) referenced in `vite.config.js`

## Phase 4 — Secondary Screens
- [x] Flocks list (farm-wide, aggregated across houses) — `FlocksPage`
- [x] Houses list + create — `HousesPage`
- [x] Analytics (per-house Recharts trends: risk/mortality/feed/water) — `AnalyticsPage`
- [x] Auth screens (login/register/forgot-password) — `pages/auth/*`
- [x] Empty / loading states (every data page handles zero-data gracefully - verified in browser)
- [x] Inspections (inline form on House Details; auto-acknowledges the linked alert) — `HouseDetailPage`
- [x] Team page (current owner shown; invites not wired - no memberships backend yet) — `TeamPage`
- [x] Billing page (placeholder - no plans/payments yet) — `BillingPage`
- [ ] Settings beyond account/farm basics (check-window config, real team invites)
- [ ] Notifications
- [ ] Landing page (marketing page before login)
- [ ] Error states (network-failure UI beyond thrown errors)

## Phase 5 — Backend Depth
- [x] Flock Check submission → validation → historical retrieval → baseline comparison → Risk Engine → status classification → Alert Engine
- [x] Media flow: Cloudinary upload → Firestore metadata (`url`, `public_id`) → attach to Flock Check/Inspection
- [x] Real `bird_type` on Flock and optional `water_liters` on Flock Check (added so House Details/Analytics charts use real data instead of a fabricated metric)
- [ ] Morning vs evening same-day comparison (currently baseline is a rolling average, not morning-vs-evening specific)
- [ ] Grok integration endpoints beyond generic ask (explain alert, farm summary, compare checks)
- [ ] Organizations / users / memberships / subscriptions data model in Firestore

**Fixed during frontend browser QA:** the mortality scorer compared a raw
mortality *rate* against a ratio-to-baseline threshold, so a house's
first-ever check (no baseline yet) could almost never flag high mortality
no matter how severe - now falls back to an absolute reference rate
(0.5%/day) when there's no baseline. Also fixed `/ask` referencing raw
Firestore house IDs instead of house names in Grok's context.

## Phase 6 — Deployment
- [ ] Frontend → Vercel
- [ ] Backend → Render
- [ ] Env var / secrets setup on both (Firebase, Cloudinary, Grok key — backend only)

---
Status legend: unchecked = not started. Update this file as each item completes.
