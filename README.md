# Satellite Graveyard Navigator

**FAR AWAY 2026 · Space & Aerospace Theme**

Interactive 3D space debris risk platform. Mission planners visualize ~15,000+ orbiting objects on a live Earth globe, draw or select orbits, get velocity-aware collision scores, use AI to plan missions, filter ISRO assets, find safer altitudes, compare before/after risk, and export PDF reports.

---

## Table of Contents

- [Problem Statement](#problem-statement)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
- [Features](#features)
- [Orbit Presets](#orbit-presets)
- [How It Works](#how-it-works)
- [Risk Scoring](#risk-scoring)
- [Demo Script](#demo-script)
- [API Reference](#api-reference)
- [WebSocket Protocol](#websocket-protocol)
- [Project Structure](#project-structure)
- [Deploy](#deploy)
- [Honest Technical Notes](#honest-technical-notes-for-judges)

---

## Problem Statement

Earth orbit is crowded with active satellites and debris — the **Kessler Syndrome** risk. Before launching or changing orbit, operators need to know:

- How many objects are near your altitude band?
- Are they **crossing** your orbit (high relative velocity) or co-orbiting?
- Where are **danger clusters** on the ground track?
- Is there a **cleaner altitude band** nearby?
- When might be a **better launch window**?

This app answers those questions interactively on a live 3D globe, with a focus on **ISRO missions** (Chandrayaan-3, Aditya-L1, EOS, GSAT) but applicable to any LEO/MEO/GEO scenario.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  External Data                                                  │
│  Space-Track.org │ Celestrak GP │ Gemini 2.5 Flash (optional)   │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  Backend — Python FastAPI :8000                                 │
│  tle_processor → SGP4 propagation → risk_engine → REST + WS     │
│  ai_planner │ launch_window │ orbit_presets │ isro_satellites   │
│  Disk cache: .data/cache/ (TLE + propagated positions)          │
└────────────────────────────┬────────────────────────────────────┘
                             │  /api/*  (Vite proxy in dev)
┌────────────────────────────▼────────────────────────────────────┐
│  Frontend — React + Vite :5173                                  │
│  Landing Page → Mission Control → SpaceGlobe (globe.gl/Three.js)│
└─────────────────────────────────────────────────────────────────┘
```

**Two processes run locally:**

| Process | Command | Port |
|---------|---------|------|
| Backend | `.\venv\Scripts\uvicorn main:app --reload --port 8000` | 8000 |
| Frontend | `npm run dev` | 5173 |

> **Important:** Always run uvicorn from the backend **venv**. Plain `uvicorn` uses system Python and will fail with `No module named 'sgp4'`.

The Vite dev server proxies `/api` and WebSocket traffic to port 8000.

---

## Technology Stack

### Backend (Python 3.11+)

| Package | Purpose |
|---------|---------|
| **FastAPI** | REST API + WebSocket server |
| **Uvicorn** | ASGI server with hot reload |
| **sgp4** | SGP4 orbital propagation from TLE |
| **NumPy** | Vector math for velocity crossing |
| **scikit-learn** | DBSCAN clustering for danger zones |
| **requests** | HTTP fetch from Celestrak / Space-Track |
| **python-dotenv** | Load `.env` secrets |
| **google-generativeai** | Gemini AI mission planner |
| **Pydantic** | Request/response validation |

### Frontend (Node.js 18+)

| Package | Purpose |
|---------|---------|
| **React 19** | UI framework |
| **Vite 8** | Dev server + production bundler |
| **globe.gl** | 3D Earth globe (Three.js wrapper) |
| **three** | WebGL 3D rendering engine |
| **lucide-react** | Icons |
| **jsPDF** | Client-side PDF report generation |
| **IBM Plex Sans / Mono** | Typography (Google Fonts) |

### External Data & Services

| Source | Role |
|--------|------|
| [Space-Track.org](https://www.space-track.org) | Primary TLE catalog (~10k–20k objects) when credentials are set |
| [Celestrak GP](https://celestrak.org/NORAD/elements/gp.php) | Automatic fallback TLE groups |
| **Google Gemini 2.5 Flash** | Natural-language mission planning (optional) |
| **Cloudinary** | Landing page hero video + poster |

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Optional: `GEMINI_API_KEY` for AI mission planner (keyword fallback works without it)
- Optional: Space-Track credentials for the largest catalog (~20k objects)

### Backend (FastAPI)

```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env    # Add keys (see Environment Variables)
.\venv\Scripts\uvicorn main:app --reload --port 8000
```

Or use the helper script:

```powershell
cd backend
.\start.ps1
```

### Frontend (React + Vite)

```powershell
cd frontend
npm install
npm run dev
```

Or:

```powershell
cd frontend
.\start.ps1
```

Open **http://localhost:5173**

### Production build

```powershell
cd frontend
npm run build
npm run preview
```

---

## Environment Variables

Create `backend/.env` from `.env.example`:

```env
# Optional — AI mission planner (uses keyword fallback if unset)
GEMINI_API_KEY=your_gemini_api_key_here

# Optional — primary TLE catalog (~20k objects)
# Falls back to Celestrak automatically if unset
SPACE_TRACK_USER=your_space_track_username
SPACE_TRACK_PASSWORD=your_space_track_password
```

---

## Features

| Feature | Description |
|---------|-------------|
| **3D debris globe** | globe.gl Earth + live debris points (Space-Track / Celestrak TLE → SGP4) |
| **Orbit drawing** | Click globe to place waypoints, analyze collision risk |
| **Velocity-aware risk** | ECEF tangent velocity vs debris SGP4 velocity crossing angle |
| **Before/After comparison** | Side-by-side Initial/Current or Before/After scores with delta badge |
| **Segmented orbit colors** | Green → yellow → red arc by local debris density along the path |
| **Critical object labels** | Top 5 conjunction threats on globe + sidebar with NORAD IDs |
| **AI Mission Planner** | Natural language → orbit (Gemini 2.5 Flash, keyword fallback) |
| **ISRO Constellation View** | Filter + highlight Indian satellites (orange on globe) |
| **Launch Window Recommender** | Next 7 days heuristic launch windows |
| **Debris Heatmap Mode** | Altitude/lat/lng density grid |
| **Live Tracking** | WebSocket push on catalog refresh with auto-reconnect |
| **Find Safer Altitude** | One-click re-orbit to low-density band + re-score + green orbit |
| **Orbit Presets** | ISS, ISRO EOS-07, ISRO LEO, Chandrayaan-3, Aditya-L1 |
| **Onboarding tooltip** | 30-second first-run guide (Click globe → Analyze → Safer Altitude) |
| **Mission Control UI** | Professional dark aerospace console with 3D risk ring |
| **PDF Report** | Risk breakdown, waypoints, ISRO context, launch windows, critical objects |
| **Cinematic landing** | Cloudinary video hero with transition into Mission Control |

---

## Orbit Presets

One-click demo orbits with pre-computed ground tracks and auto-analysis:

| Preset | Altitude | Inclination | Agency | Story |
|--------|----------|-------------|--------|-------|
| **ISS Orbit** | 408 km | 51.6° | NASA / Roscosmos | — |
| **ISRO EOS-07** | 529 km | 97.4° (SSO) | ISRO | Sun-sync Earth observation shell |
| **ISRO LEO Comms** | 650 km | 51.6° | ISRO | Representative LEO relay band |
| **Chandrayaan-3 Parking** | 100 km | 32.5° | ISRO | Earth parking orbit before lunar TLI |
| **Aditya-L1 Transfer** | 650 km | 37.6° | ISRO | Earth departure phase before Sun–Earth L1 |

ISRO presets show an orange narrative blurb in the sidebar when selected.

---

## How It Works

### Data Pipeline (TLE → Globe)

1. **Fetch TLE triples** (name + line1 + line2):
   - Try **Space-Track** first (if credentials in `.env`)
   - Fall back to **Celestrak** `gp.php` groups: `active`, `stations`, `debris`, `science`, `weather`, `gps-ops`, `galileo`, `last-30-days`, `oneweb`, `starlink`
   - If network fails: bundled **seed catalog** or **synthetic LEO** demo data

2. **Parse TLE** → build SGP4 `Satrec` objects

3. **Propagate** each satellite to current UTC (8 worker threads)

4. **Output per object:**
   ```json
   {
     "name": "COSMOS 2251 DEB",
     "norad_id": "33767",
     "lat": 45.2, "lng": -12.8, "alt_km": 789,
     "vx": 0.1, "vy": 7.2, "vz": 0.3,
     "is_isro": false
   }
   ```

5. **Cache** to `.data/cache/` so restarts are instant (~15,729 objects when live)

### User Journey

1. **Landing page** — hero video, feature cards, enter Mission Control
2. **Globe loads** — WebSocket connects, debris catalog renders as colored points
3. **Draw or preset** — click globe for waypoints, or pick ISS / Chandrayaan-3 / etc.
4. **Analyze Risk** — POST `/api/analyze` → score, danger zones, critical objects, safe altitude
5. **Visual feedback** — colored orbit arc, pulsing danger rings, threat labels on globe
6. **Safer Altitude** — moves orbit to low-density band, re-scores, shows Before/After delta
7. **Export** — download PDF report with full mission context

### Frontend Components

| Component | Role |
|-----------|------|
| `App.jsx` | Routes Landing ↔ Mission Control |
| `MissionControl.jsx` | Main dashboard: sidebar controls + globe area |
| `SpaceGlobe.jsx` | 3D globe: debris, orbit path, danger rings, labels |
| `Landing.jsx` | Cinematic entry with Cloudinary video |
| `GlobeHUD.jsx` | Bottom-left overlay: count, altitude, WS status |
| `MissionPresets.jsx` | Preset grid + ISRO story blurb |
| `AIMissionPlanner.jsx` | Natural-language mission input |
| `RiskRing3D.jsx` | Circular 0–100 risk gauge |
| `RiskCompare.jsx` | Before/After side-by-side scores |
| `CriticalObjectsPanel.jsx` | Top 5 conjunction threats list |
| `OnboardingGuide.jsx` | 30s first-run tooltip (localStorage) |
| `ReportGenerator.jsx` | jsPDF mission report download |
| `useLiveDebris.js` | WebSocket hook with auto-reconnect |

### Backend Modules

| Module | Role |
|--------|------|
| `main.py` | FastAPI routes, WebSocket, startup cache refresh |
| `tle_processor.py` | TLE fetch, SGP4 propagation, disk cache |
| `space_track.py` | Space-Track.org login + GP catalog download |
| `risk_engine.py` | Velocity-aware scoring, DBSCAN zones, safe altitude |
| `ai_planner.py` | Gemini 2.5 Flash + keyword fallback |
| `launch_window.py` | 7-day launch window heuristic |
| `orbit_presets.py` | ISS + ISRO preset definitions |
| `isro_satellites.py` | ISRO name matching + mission list |
| `ws_manager.py` | WebSocket client management + broadcast |
| `seed_catalog.py` | Offline fallback TLE / synthetic catalog |

---

## Risk Scoring

When you analyze an orbit, `risk_engine.py`:

1. Computes **orbit velocity vector** in ECEF from waypoint geometry (circular orbit speed √(GM/r))
2. Filters debris within altitude band (±75 km margin)
3. For each nearby object:
   - **Velocity crossing factor** — angle between debris and orbit velocities (crossing = higher risk)
   - **Altitude proximity score** — how close debris altitude is to your band
   - **Contribution** = crossing × altitude score
4. Runs **DBSCAN clustering** on lat/lng → **danger zones** (pulsing red rings on globe)
5. Computes **risk score 0–100**:
   - **Density** (40 pts) — share of catalog in your altitude shell
   - **Velocity crossing** (45 pts) — average crossing angle
   - **Overlap / clusters** (15+ pts) — spatial clustering penalty
6. Finds **safe altitude** — lowest-density 50 km band within ±300 km of your orbit
7. Returns **critical objects** — top threats with name, NORAD ID, lat/lng, crossing factor

**Globe orbit coloring:** The frontend splits the orbit into 8 segments and colors each green/yellow/red based on local debris density at that point along the arc.

---

## Demo Script

### 3-Minute Judge Demo

1. **0:00** — Globe loads with live debris catalog. Mention Kessler Syndrome.
2. **0:30** — Click **Chandrayaan-3** or **ISS** preset → risk score + ISRO story appear.
3. **1:00** — Point out **Before/After panel**, colored orbit arc, and **critical object labels** on globe.
4. **1:30** — AI Planner: type *"ISRO lunar comms relay at 650km"* → orbit auto-drawn.
5. **2:00** — Show velocity-crossing breakdown (density / crossing / overlap).
6. **2:30** — Click **Safer Altitude** → green orbit arc, score drops, delta badge appears.
7. **3:00** — Toggle **ISRO View** and **Heatmap** → download PDF report.

### Reset Onboarding Tooltip

In browser console:

```js
localStorage.removeItem('sgn-onboarding-done')
```

Then refresh to see the 30-second guide again.

---

## API Reference

| Method | Path | Body / Params | Returns |
|--------|------|---------------|---------|
| GET | `/api/health` | — | Status, cache age, catalog count, source |
| GET | `/api/debris` | `isro_only`, `refresh` | Full propagated catalog |
| GET | `/api/isro/constellation` | — | ISRO missions list + tracked objects |
| GET | `/api/heatmap` | `bins=36` | Lat/lng/alt density grid |
| GET | `/api/presets` | — | All orbit presets |
| POST | `/api/analyze` | `{ waypoints, target_alt_km, debris_objects? }` | Risk score, zones, safe alt, launch windows |
| POST | `/api/ai/plan` | `{ query }` | AI plan + risk + launch windows |
| WS | `/api/ws/live` | `?isro_only=` | Live debris push |

### POST `/api/analyze` example

```json
{
  "waypoints": [
    { "lat": 0, "lng": 0, "alt_km": 408 },
    { "lat": 51.6, "lng": 90, "alt_km": 408 }
  ],
  "target_alt_km": 408
}
```

Response includes: `risk_score`, `danger_zones`, `safe_altitude`, `nearby_count`, `critical_objects`, `risk_breakdown`, `launch_windows`, `data_ready`.

---

## WebSocket Protocol

**Connect:** `ws://localhost:5173/api/ws/live?isro_only=false`

**Client → Server:**

```json
{ "type": "set_filter", "isro_only": true }
{ "type": "refresh" }
```

**Server → Client:**

```json
{
  "type": "debris_update",
  "count": 15729,
  "objects": [ ... ],
  "cache_age_s": 42.3,
  "catalog_live": true,
  "catalog_source": "space-track",
  "timestamp": "2026-06-12T19:00:00+00:00"
}
```

The frontend hook (`useLiveDebris.js`) auto-reconnects with exponential backoff.

---

## Project Structure

```
satellite-graveyard-navigator/
├── README.md
├── .data/cache/                  # Runtime TLE + debris pickle cache
│   ├── debris_cache.pkl
│   └── tle_catalog.pkl
├── backend/
│   ├── main.py                   # FastAPI app + routes + WebSocket
│   ├── tle_processor.py          # TLE fetch, SGP4, disk cache
│   ├── space_track.py            # Space-Track.org client
│   ├── risk_engine.py            # Risk scoring + DBSCAN
│   ├── ai_planner.py             # Gemini + keyword fallback
│   ├── launch_window.py          # 7-day launch windows
│   ├── orbit_presets.py          # ISS + ISRO presets
│   ├── isro_satellites.py        # ISRO name matching
│   ├── ws_manager.py             # WebSocket broadcast manager
│   ├── seed_catalog.py           # Offline fallback data
│   ├── requirements.txt
│   ├── .env.example
│   └── start.ps1
└── frontend/
    ├── src/
    │   ├── App.jsx               # Landing ↔ MissionControl router
    │   ├── MissionControl.jsx    # Main dashboard
    │   ├── api.js                # HTTP client
    │   ├── index.css             # Design system
    │   ├── main.jsx
    │   ├── hooks/
    │   │   └── useLiveDebris.js  # WebSocket live feed
    │   └── components/
    │       ├── Landing.jsx
    │       ├── SpaceGlobe.jsx    # 3D globe
    │       ├── GlobeHUD.jsx
    │       ├── MissionPresets.jsx
    │       ├── AIMissionPlanner.jsx
    │       ├── RiskRing3D.jsx
    │       ├── RiskCompare.jsx
    │       ├── CriticalObjectsPanel.jsx
    │       ├── OnboardingGuide.jsx
    │       ├── ReportGenerator.jsx
    │       └── Section.jsx
    ├── public/textures/          # Earth + starfield images
    ├── vite.config.js            # /api proxy to :8000
    ├── package.json
    └── start.ps1
```

---

## Deploy

| Part | Platform | Notes |
|------|----------|-------|
| **Frontend** | Vercel | Deploy `frontend/` directory |
| **Backend** | Railway | Deploy `backend/` directory |

Set environment variables on Railway:

- `GEMINI_API_KEY` — for AI planner
- `SPACE_TRACK_USER` / `SPACE_TRACK_PASSWORD` — for largest catalog

Configure the frontend to proxy or point API calls to the Railway backend URL in production.

---

## Honest Technical Notes (for judges)

### What is real

- **SGP4 propagation** — industry-standard TLE propagator used by space operators
- **Live TLE pipeline** — Space-Track / Celestrak with disk caching
- **Velocity-crossing concept** — debris crossing angle vs co-orbiting objects
- **WebSocket live feed** — catalog refresh pushed to all connected clients
- **DBSCAN clustering** — spatial danger zone detection on ground track

### What is heuristic (not NASA-grade)

- **Risk score 0–100** — weighted index, not a probability of collision (Pc)
- **No full conjunction analysis** — no Time of Closest Approach (TCA), miss distance, or covariances
- **Altitude-band filtering** — not full orbital element matching (RAAN, eccentricity, etc.)
- **Launch windows** — time-slot simulation with SGP4 re-propagation, not operational go/no-go
- **Safe altitude** — density-bin scan, not a formal maneuver planning solution

### One-sentence pitch

**Satellite Graveyard Navigator** pulls live orbital catalogs from Space-Track/Celestrak, propagates every object with SGP4, renders them on an interactive 3D globe, and scores proposed orbits using velocity-aware debris crossing analysis — with AI mission planning, ISRO-focused presets, safer-altitude recommendations, launch windows, and exportable PDF reports.

---

## License

Built for FAR AWAY 2026 hackathon.
