# Weather-Aware Truck Routing

A React + Django app that helps a truck driver pick the safest of three routes using the weather
forecast at the time the truck will actually reach each part of each route, plus its load weight.

- Enter an origin, a destination, a departure time and a load weight.
- The app finds **3 route options**, samples weather **every 10 / 25 / 50 miles** at the
  truck's **ETA** at each checkpoint, rates every checkpoint Low → No Travel, and **recommends**
  a route.
- The map shows all routes, checkpoints, risk levels, ETAs and route summaries, plus a **weather
  heatmap over the trip corridor with a 0–48 h forecast slider**.

No API keys are needed. Routing uses [OSRM](https://project-osrm.org/), weather uses
[Open-Meteo](https://open-meteo.com/), geocoding uses [Photon](https://photon.komoot.io/), and
the basemap comes from Esri.

### Using it

1. Type an origin and destination (a place name, or `lat, lon`), a departure time, the load
   weight, and how often to check the weather. Then press **Find safest route**.
2. The sidebar shows the recommendation and why, a card per route, and the selected route's
   checkpoints. The form folds into a one-line summary; **Edit trip** brings it back.
3. On the map, the recommended route is drawn in risk colours, and green is used only for it.
   Other routes are grey, with colour only where their risk is Moderate or worse. **Start**
   and **End** pins mark the trip; a map key explains the symbols.
4. Click any route, its label or a checkpoint for details. A route popup shows its time,
   distance, arrival, miles per risk level and why it was or wasn't recommended.
5. Drag the slider (0-48 h after departure) or press play to move through the forecast. The
   truck markers show where each truck would be at that time.

### Project layout

```
backend/                 Django API (uv, pyproject.toml)
  config/                settings, URLs
  planner/
    services/            routing, weather, risk, checkpoints, ranking, heatmap (see below)
    tests/               pytest
    models.py, views.py, serializers.py
frontend/                React + Vite + Leaflet
  src/
    components/          form, route cards, forecast panel
    components/map/      map, route layers, heatmap overlay, popups, icons
    lib/                 formatting, colours, path and forecast helpers
docker-compose.yml       db, backend and frontend for running everything locally
.github/workflows/       CI and the GitHub Pages deploy
```

---

## Quick start (Docker)

```bash
docker compose up --build
# open http://localhost:3000
```

This starts three services:

| Service | Image | Role |
| --- | --- | --- |
| `frontend` | [frontend/Dockerfile](frontend/Dockerfile) | Builds the React app and serves it with nginx; proxies `/api` to `backend` |
| `backend` | [backend/Dockerfile](backend/Dockerfile) | Django API (gunicorn); runs migrations and creates the cache table on startup |
| `db` | `postgres:17-alpine` | Saved plans and the shared cache |

Use `PORT=8080 docker compose up --build` to pick a different host port.

### Other Docker commands

```bash
docker compose up -d --build              # start in the background
docker compose ps                         # status and health of each service
docker compose logs -f backend            # follow logs (or frontend, db)
docker compose up -d --build backend      # rebuild and restart one service after a change
docker compose down                       # stop; the Postgres data volume is kept
docker compose down -v                    # stop and delete the Postgres data volume

docker compose exec backend python manage.py migrate   # any manage.py command
docker compose exec backend python manage.py shell     # Django shell
docker compose exec db psql -U truck -d truck          # SQL shell
```

## Local development

```bash
# Postgres (published on localhost:5433 so it doesn't clash with a local install)
docker compose up -d db
export DATABASE_URL=postgres://truck:truck@localhost:5433/truck

# Backend (Python 3.12+, dependencies managed with uv; see below)
cd backend && uv sync
uv run manage.py migrate && uv run manage.py createcachetable
uv run manage.py runserver 3000                             # http://127.0.0.1:3000

# Frontend (Node 22): Vite proxies /api to the Django server
cd frontend && npm install && npm run dev                   # http://localhost:5173

# Tests
cd backend && uv run pytest

# Lint and format (ruff for Python, ESLint + Prettier for TypeScript)
cd backend && uv run ruff check . && uv run ruff format .
cd frontend && npm run lint && npm run format
```

The app uses Postgres everywhere: locally, in CI and in production. Without `DATABASE_URL`,
Django connects to the compose `db` service on `localhost:5433`, so start it first with
`docker compose up -d db`. Tests run against a temporary `test_truck` database on the same
server, which pytest creates and drops.

If Django runs somewhere else, set `API_PROXY=http://127.0.0.1:8765` for Vite.

### Python dependencies (uv)

The backend's dependencies are declared in [backend/pyproject.toml](backend/pyproject.toml):
runtime packages under `dependencies`, and test and lint tools in the `dev` group. Exact
versions are pinned in [backend/uv.lock](backend/uv.lock). Commit both files whenever
dependencies change. The Docker image installs with `uv sync --locked --no-dev`, so the build
fails if the lockfile is out of date.

Run these from `backend/`:

```bash
uv sync                        # create/update .venv from uv.lock (includes the dev group)
uv sync --no-dev               # runtime packages only, as in the Docker image
uv run <command>               # run inside the project environment, e.g. uv run pytest

uv add <package>               # add a runtime dependency (updates pyproject.toml and uv.lock)
uv add --dev <package>         # add a test/lint-only dependency
uv remove <package>            # remove a dependency

uv lock --upgrade-package <package>   # upgrade one package
uv lock --upgrade                     # upgrade everything allowed by pyproject.toml
uv lock --check                       # check uv.lock matches pyproject.toml
uv tree                               # show the dependency tree
```

---

## Database

Postgres stores two things:

- **`TripPlan`**: every `/api/plan` request and its full result, under a UUID, so a plan can be
  reloaded with `GET /api/plans/<id>`.
- **Shared cache** (`planner_cache`, Django's database cache): forecast and geocoding lookups
  are shared by every gunicorn worker and instance. Each plan reads and writes the cache in
  one query (`get_many`/`set_many`), not one query per checkpoint.

## How it works

```
origin/destination ─► OSRM: 3 distinct routes ─► checkpoints every N mi with truck ETA
      ─► Open-Meteo hourly forecast at each checkpoint's ETA ─► risk per checkpoint
      ─► risk miles per route ─► lexicographic ranking ─► recommendation + reasons
```

The logic lives in [backend/planner/services/](backend/planner/services/). Risk, checkpoints and
ranking are pure functions; the network calls are in separate client modules:

| Module | Responsibility |
| --- | --- |
| [risk.py](backend/planner/services/risk.py) | Risk table and load rules |
| [checkpoints.py](backend/planner/services/checkpoints.py) | Checkpoint placement, ETAs, the miles each checkpoint represents |
| [weather.py](backend/planner/services/weather.py) | Open-Meteo client; picks the forecast hour for an ETA |
| [recommend.py](backend/planner/services/recommend.py) | Route ranking and the human-readable "why" |
| [routing.py](backend/planner/services/routing.py) | OSRM client, truck speed model, guaranteeing 3 distinct routes |
| [heatmap.py](backend/planner/services/heatmap.py) | Corridor grid and the 0–48 h forecast frames |
| [planner.py](backend/planner/services/planner.py) | Orchestrates the above into the `/api/plan` response |
| [geo.py](backend/planner/services/geo.py) | Distances (geopy), line simplification (shapely), interpolation along a route |
| [geocoding.py](backend/planner/services/geocoding.py) | Photon place search |
| [upstream.py](backend/planner/services/upstream.py) | Shared HTTP client: one retry, rate-limit and error messages |

### Routes

OSRM's `alternatives` often returns fewer than 3 routes (Dallas → Houston returns 1). When it
does, the app requests routes through **detour waypoints** placed sideways from the fastest
route's midpoint, at 15%, 30% and 45% of the trip's straight-line length on each side. A
candidate is kept only if:

- it is at most **1.6×** the fastest route's time, and
- **at most 80%** of it overlaps a route that was already accepted (checked with a ~1 km
  spatial hash).

At most three routes are kept, labelled A, B, C from fastest to slowest.

**Unreachable places:** if OSRM has to move the start or destination more than 10 km to reach a
road (for example Kansas to France, where it would start the route in Lisbon), the app reports
that no road route exists.

**Truck speed:** the public OSRM server only has a car profile. Each road segment's car speed is
therefore capped at **65 mph** (`TRUCK_MAX_SPEED_MPH`), so ETAs match a governed heavy truck.

### Checkpoints and ETAs

- Checkpoints are placed at mile 0, then every 10, 25 or 50 miles, and at the destination.
- Each checkpoint's ETA is the departure time plus the truck's elapsed time at that point. This
  is interpolated from OSRM's per-segment durations after the speed cap is applied.
- Each checkpoint **represents the route miles closest to it** (half the gap to each neighbour).
  These represented miles add up exactly to the route length, and they are what the "Severe
  miles" and "High miles" totals count.

### Weather at ETA

Open-Meteo's hourly forecast is fetched in `mph` and `inch` units. The response's
`hourly_units` are checked, and a mismatch is an error rather than silently wrong risk levels.

- **Wind** uses the sustained 10 m wind at the hour nearest the ETA. Gusts are shown but not
  used for scoring, because the rule table doesn't specify gusts.
- **Rain** (`rain` + `showers`) and **snow** (`snowfall`) are hourly totals stamped at the end
  of each hour, so they are already rates in in/hr. The app uses the hour *containing* the ETA.
- Forecast lookups snap to a **0.1° (~11 km) grid**. Overlapping routes then share lookups, and
  responses are cached in Postgres for 30 minutes. This keeps a long trip within Open-Meteo's
  free-tier limit (600 locations per minute).
- Values are shown at the forecast's own precision (0.1 mph, 0.001 in/hr), so a displayed number
  never crosses a threshold its risk level doesn't.

### Risk rules

| Condition | Low | Moderate | High | Severe | No Travel |
| --- | --- | --- | --- | --- | --- |
| Wind (mph) | < 25 | 25–34 | 35–44 | 45–54 | ≥ 55 |
| Rain (in/hr) | < 0.10 | 0.10–0.25 | 0.25–0.50 | 0.50–1.00 | > 1.00 |
| Snow (in/hr) | < 0.5 | 0.5–1.0 | 1.0–2.0 | 2.0–3.0 | > 3.0 |

Load rules (applied to wind):

- ≥ 55 mph → No Travel for any load.
- 45–54 mph and a load over 30,000 lb → No Travel.
- 35–44 mph and a load over 40,000 lb → Severe.

A checkpoint's risk is the **worst** of its load-adjusted wind, rain and snow levels.
The condition(s) that set it are kept as the checkpoint's **driver** (e.g. `wind + load` when a
load rule raised the wind level) and shown in the map popup.

**Boundary handling:** each band's lower bound is inclusive. So 35.0 mph is High while 34.9 mph
is Moderate, and 0.25 in/hr of rain is High. The only exceptions are the No Travel bands for
rain and snow, which the table defines as strictly greater (> 1.00 and > 3.0). The load
thresholds are strict too ("over 30,000 lb"). Every boundary is covered by a test in
[test_risk.py](backend/planner/tests/test_risk.py).

### Recommendation

Routes are ranked lexicographically by:

0. **no No Travel miles at all**. A route with any No Travel exposure is flagged ("No Travel"
   tag on its card) and never beats a route without. This step is added ahead of the spec's
   list because No Travel is strictly worse than Severe.
1. fewest **Severe** miles, counting No Travel miles as Severe too
2. fewest **High** miles
3. lowest **average risk** (the distance-weighted mean of levels 0–4)
4. shortest **travel time**

Miles are compared at 0.1 mi precision and average risk at 0.01, so floating-point noise never
decides the winner. The UI explains the decision using the first criterion that separates the
winner from each other route, e.g. *"0 Severe miles vs 42 on Route B"*. Each route also carries
its own `why_not_recommended` line, which the route popup shows.

If even the best route has No Travel or Severe miles, a warning is shown and, for No Travel,
delaying departure is suggested.

### Heatmap

- The backend builds a grid over the trip corridor that is **uniform in Web-Mercator space**,
  and it only fetches cells within a buffer of a route (at most 220 cells). It returns 50 hourly
  frames for the risk, wind, gust, rain and snow layers, starting at the departure hour rounded
  down, so departure + 48 h is covered even when departure isn't on the hour. The risk layer is
  computed on the server with the same rules and load as the checkpoints.
- Slider position *h* means exactly departure + *h* hours. The map shows the forecast frame
  nearest that time, and the trucks are placed at that exact time.
- The frontend draws one frame into an `nx × ny` canvas, one pixel per cell, and stretches it
  over the grid bounds as a Leaflet image overlay. Because the grid is Mercator-uniform, pixels
  line up exactly with cells, and the browser's bilinear scaling gives a smooth field.
- Moving the slider or pressing play only recolours about 200 pixels. There are no network
  requests and no DOM churn, and in headless Chrome each step renders within a single frame.
- Every layer uses the **same colour scale as the risk levels**, with colour stops exactly on
  the thresholds: a wind cell turns orange at 35 mph, which is where a checkpoint becomes High.
- Truck markers show where each truck would be at the selected hour.

## API

| Endpoint | Purpose |
| --- | --- |
| `GET /api/geocode?q=denver` | Place autocomplete |
| `POST /api/plan` | `{origin:{lat,lon}, destination:{lat,lon}, departure: ISO-8601, load_lbs, interval_miles: 10\|25\|50}` → `id`, routes, checkpoints, risk miles, recommendation (saved) |
| `GET /api/plans/<id>` | A saved plan |
| `POST /api/heatmap` | `{corridor: [[[lat,lon],…],…], departure, load_lbs}` → 0–48 h gridded frames |
| `GET /api/health` | Liveness check |

Departure must be between 1 hour ago and 7 days ahead (the forecast range).

Errors: invalid input returns 400 with a message per field, e.g. `{"load_lbs": ["..."]}`. Other
errors return `{"detail": "..."}`: 422 when no route or forecast is possible, 502 when an
external service fails, and 503 when it is rate-limiting.

## Deployment

GitHub Pages only serves static files, so the frontend and the API are hosted separately:

1. **API and database:** run [backend/Dockerfile](backend/Dockerfile) on any container host
   (Render, Fly.io, Railway, Cloud Run, …) with a managed Postgres. Configure it with the
   variables below: at least `DATABASE_URL`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_SECRET_KEY` and
   `CORS_ALLOWED_ORIGINS`. Migrations run automatically when the container starts.
2. **Frontend (GitHub Pages):**
   - Under *Settings → Pages*, set the source to **GitHub Actions**.
   - Under *Settings → Secrets and variables → Actions → Variables*, add `API_BASE_URL` with
     the API's public URL, e.g. `https://truck-routing-api.example.com`.
   - Every push to `main` that touches `frontend/` runs
     [.github/workflows/pages.yml](.github/workflows/pages.yml), which builds the app and
     publishes it. Free GitHub Pages needs a public repository.

[.github/workflows/ci.yml](.github/workflows/ci.yml) runs lint, formatting checks, tests and
the frontend build on every push.

To host both on one container platform instead, deploy the
[frontend/Dockerfile](frontend/Dockerfile) image too. Its nginx forwards `/api` to
`BACKEND_URL` (default `http://backend:3000`), so no CORS setup is needed.

Free hosts often put idle services to sleep. The app pings the API when the page loads, and it
explains the wait if the first request is slow.

| Backend variable | Default | Notes |
| --- | --- | --- |
| `DATABASE_URL` | `postgres://truck:truck@localhost:5433/truck` | The compose `db` from the host. Set it in production, e.g. `postgres://user:pass@host:5432/db` |
| `CORS_ALLOWED_ORIGINS` | – | Frontend origin when it's on another domain, e.g. `https://annenamuli.github.io` |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,0.0.0.0` | Set to your API's domain, e.g. `truck-routing-api.example.com` |
| `DJANGO_SECRET_KEY` | dev key | No sessions or auth use it, but set one anyway |
| `DJANGO_DEBUG` | `true` | The Docker image sets `false` |
| `PORT` | `3000` | Port gunicorn listens on (Docker image); many hosts inject this |
| `OPEN_METEO_API_KEY` | – | Optional commercial key. Also set `OPEN_METEO_BASE_URL=https://customer-api.open-meteo.com` |
| `OPEN_METEO_BASE_URL`, `OSRM_BASE_URL`, `PHOTON_BASE_URL` | public services | Point at your own instances for production use |
| `HTTP_TIMEOUT_SECONDS` | `20` | Timeout for calls to those services |
| `TRUCK_MAX_SPEED_MPH` | `65` | Truck speed cap for ETAs |

| Frontend variable | Used by | Notes |
| --- | --- | --- |
| `VITE_API_BASE` | build | API base URL; defaults to `/api` on the same origin. The Pages workflow sets it from `API_BASE_URL`. |
| `VITE_BASE_PATH` | build | URL path the app is served under; the Pages workflow sets `/<repo>/`. |
| `API_PROXY` | `npm run dev` | Where Vite forwards `/api`; default `http://127.0.0.1:3000`. |
| `BACKEND_URL` | frontend image | Where nginx forwards `/api`; default `http://backend:3000`. |

## Assumptions and limitations

**Routes and timing**
- ETAs use OSRM's car times with every road segment capped at **65 mph**
  (`TRUCK_MAX_SPEED_MPH`). The public OSRM server has no truck profile, so bridge heights and
  weight limits aren't considered. *(routing.py)*
- **No hours-of-service breaks:** ETAs assume continuous driving.
- A detour route counts only if it takes at most **1.6x** the fastest route's time and shares
  at most **80%** of its road with an accepted route. If no three such routes exist, fewer are
  shown, with a warning. *(routing.py)*
- If OSRM has to move the start or destination more than **10 km** to reach a road, the places
  are treated as unconnected, e.g. separated by sea. *(routing.py)*

**Weather**
- **Wind** is the sustained 10 m wind at the hour nearest the ETA; **gusts are shown but not
  scored**. **Rain** (`rain` + `showers`) and **snow** come from the hour containing the ETA,
  because Open-Meteo reports them as totals for the hour ending at each timestamp.
  *(weather.py)*
- Forecast points are snapped to a **0.1° (~11 km)** grid and cached for 30 minutes.
- A **missing forecast value is treated as 0**, meaning none reported. *(weather.py)*
- Departures from an hour ago up to **7 days ahead** are accepted, inside Open-Meteo's
  forecast range. *(serializers.py)*

**Risk and ranking**
- Band lower bounds are inclusive (35.0 mph is High). The exceptions are rain and snow No Travel,
  which start strictly above 1.00 and 3.0 in/hr. Load limits are strict ("over 30,000 lb").
  *(risk.py)*
- Each checkpoint represents half the distance to each neighbour, so its risk applies to those
  miles. *(checkpoints.py)*
- Ranking follows the spec's order, with one addition: a route with **any No Travel miles always
  ranks below** one without, and No Travel miles also count as Severe miles. *(recommend.py)*
- Values are compared after rounding (0.1 mi, 0.01 average risk) so float noise can't decide a
  tie.

**Other**
- Times are shown in the browser's time zone; everything is computed in UTC.
- OSRM's demo server and Open-Meteo's free tier are for light use. Heavier use needs
  self-hosting or an API key; both are configurable.
