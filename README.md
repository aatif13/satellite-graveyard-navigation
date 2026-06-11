# Satellite Graveyard Navigator

**FAR AWAY 2026 · Space & Aerospace Theme**

Interactive 3D space debris risk platform. Mission planners draw orbits on a live globe, get velocity-aware collision scores, AI mission suggestions, ISRO constellation filtering, launch window recommendations, and downloadable PDF reports.

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Optional: `GEMINI_API_KEY` for AI mission planner (works without via keyword fallback)

### Backend (FastAPI)

```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env    # Add GEMINI_API_KEY for AI planner
uvicorn main:app --reload --port 8000
```

### Frontend (React + Vite)

```powershell
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** — the Vite dev server proxies `/api` to port 8000.

### Production build

```powershell
cd frontend
npm run build
npm run preview
```

## Features

| Feature | Description |
|---------|-------------|
| 3D debris globe | globe.gl Earth + live debris points (Celestrak TLE → SGP4) |
| Orbit drawing | Click globe to place waypoints, analyze collision risk |
| Velocity-aware risk | ECEF tangent velocity vs debris SGP4 velocity crossing angle |
| AI Mission Planner | Natural language → orbit (Gemini 2.5 Flash, keyword fallback) |
| ISRO Constellation View | Filter + highlight Indian satellites (orange on globe) |
| Launch Window Recommender | Next 7 days heuristic launch windows |
| Debris Heatmap Mode | Altitude/lat/lng density grid |
| Live Tracking | WebSocket push every 60s with auto-reconnect |
| Find Safer Altitude | One-click re-orbit to low-density band + re-score |
| Orbit Presets | ISS, ISRO EOS-07, ISRO LEO one-click demos |
| 3D Command Panel | Glass cockpit UI with 3D risk ring |
| PDF Report | Risk breakdown, waypoints, ISRO context, launch windows |

## 3-Minute Demo Script

1. **0:00** — Globe loads with live debris catalog. Mention Kessler Syndrome.
2. **0:30** — Click **ISS** preset → risk score appears in 3D ring.
3. **1:00** — AI Planner: type *"ISRO lunar comms relay at 650km"* → orbit auto-drawn.
4. **1:30** — Show velocity-crossing breakdown (density / crossing / overlap).
5. **2:00** — Click **Find Safer Altitude** → green orbit arc, score drops.
6. **2:30** — Toggle **ISRO View** and **Heatmap** modes.
7. **3:00** — Download PDF report with waypoints + launch windows.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Server status + cache age |
| GET | `/api/debris?isro_only=&refresh=` | Propagated debris catalog |
| GET | `/api/isro/constellation` | ISRO missions + tracked objects |
| GET | `/api/heatmap` | Density grid for heatmap mode |
| GET | `/api/presets` | ISS / ISRO orbit presets |
| POST | `/api/analyze` | `{ waypoints, target_alt_km }` → risk score |
| POST | `/api/ai/plan` | `{ query }` → AI mission plan + risk |
| WS | `/api/ws/live` | Live debris push (`set_filter`, `refresh` messages) |

## Data Sources

- [Celestrak GP Data](https://celestrak.org/NORAD/elements/gp.php) — `FORMAT=TLE` with groups: active, stations, science, weather, gps-ops, analyst + named debris queries
- SGP4 propagation via Python `sgp4` library
- AI via Google Gemini 2.5 Flash (optional)

## Project Structure

```
backend/
  main.py            # FastAPI routes + WebSocket
  tle_processor.py   # Celestrak fetch + SGP4 propagation
  risk_engine.py     # Velocity-aware risk + DBSCAN zones
  ai_planner.py      # Gemini mission planner
  launch_window.py   # 7-day launch window heuristic
  orbit_presets.py   # ISS / ISRO presets
  isro_satellites.py # ISRO name matching
  ws_manager.py      # WebSocket broadcast manager

frontend/
  src/App.jsx              # Main app + Mission Control panel
  src/components/SpaceGlobe.jsx   # 3D globe
  src/hooks/useLiveDebris.js      # WebSocket live feed
  public/textures/         # Earth + starfield images
```

## Deploy

- **Frontend:** Vercel (`frontend/`)
- **Backend:** Railway (`backend/`)

Set `GEMINI_API_KEY` in Railway env for AI planner.

## Honest Technical Notes (for judges)

**Real:** SGP4 propagation, Celestrak TLE pipeline, velocity-crossing concept, live WebSocket data.

**Heuristic (not NASA-grade):** Risk score 0–100, launch windows (sine simulation), altitude-band proximity (no full 3D TCA/Pc).
