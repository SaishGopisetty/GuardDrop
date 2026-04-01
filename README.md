# GuardDrop

GuardDrop is a small full-stack app for watching deliveries after they hit the porch.

The idea is simple: you add a package, the app simulates the usual delivery timeline, and if the package sits outside too long it starts escalating. First it warns you. Then, if you have an accepted backup contact and Twilio is set up, it can text that person too.

This repo has two parts:

- a React + Vite frontend in `frontend/`
- a FastAPI backend in `backend/`

They run separately in development, and the frontend talks to the backend over both HTTP and WebSocket.

## What the app does

Once a delivery is created, the backend starts a background simulation:

- `pending`
- `eta_sent` after 10 seconds
- `delivered` after another 10 seconds
- first escalation warning after 20 seconds
- second escalation warning after another 20 seconds
- trusted contact alert attempt after another 20 seconds

At any point after delivery, the user can slide to confirm pickup. That stops the escalation path and marks the package as picked up.

The frontend listens for live updates over WebSocket, shows toast messages in the app, and can also trigger browser notifications if permission is allowed.

## Stack

- Frontend: React 19, Vite, Axios
- Backend: FastAPI, SQLAlchemy, SQLite
- Realtime: WebSockets
- Optional SMS: Twilio

## Project layout

```text
GuardDrop/
|- frontend/   # React app
|- backend/    # FastAPI app
|- guarddrop.db
`- README.md
```

Useful files:

- `frontend/src/App.jsx`: app shell, page switching, session handling, WebSocket setup
- `frontend/src/pages/`: auth, deliveries, contacts, new delivery, profile
- `frontend/src/index.css`: shared styling
- `backend/main.py`: API routes, WebSocket manager, delivery simulation
- `backend/models.py`: database models
- `backend/database.py`: SQLite setup
- `backend/auth.py`: token creation and request authentication

## Running it locally

You need both servers running.

### 1. Start the backend

From `backend/`:

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

The API will be available at [http://localhost:8000](http://localhost:8000).

The SQLite database file is created automatically. By default it lives in the backend folder as `guarddrop.db`.

### 2. Start the frontend

From `frontend/`:

```bash
npm install
npm run dev
```

The frontend runs at [http://localhost:5173](http://localhost:5173).

By default it sends API requests to `http://localhost:8000` and connects to the matching WebSocket endpoint.

## Environment notes

Most of the app works without extra setup. A few things can be configured through environment variables.

Backend:

- `DATABASE_URL`: override the SQLite connection string
- `GUARDDROP_SECRET_KEY`: secret used to sign access tokens
- `GUARDDROP_TOKEN_TTL_SECONDS`: access token lifetime
- `GUARDDROP_ALLOWED_ORIGINS`: comma-separated list of allowed frontend origins
- `TWILIO_ACCOUNT_SID`: required for SMS alerts
- `TWILIO_AUTH_TOKEN`: required for SMS alerts
- `TWILIO_FROM_NUMBER`: required for SMS alerts

Frontend:

- `VITE_API_BASE_URL`: override the backend base URL if you are not using `http://localhost:8000`

If the Twilio values are missing, the app still runs. It just will not send real SMS messages during escalation.

## How to use it

1. Open the frontend and create an account.
2. Add a trusted contact in the Trust Network page.
3. Accept that contact in the app so it becomes eligible for escalation.
4. Create a delivery.
5. Watch the status change in real time.
6. Use the slide control to confirm pickup before the escalation chain finishes.

## API at a glance

Main routes:

- `POST /signup`
- `POST /login`
- `GET /users/me`
- `GET /users/{user_id}`
- `POST /contacts`
- `GET /contacts`
- `POST /contacts/{contact_id}/accept`
- `POST /deliveries`
- `GET /deliveries`
- `POST /deliveries/{delivery_id}/pickup`
- `GET /deliveries/{delivery_id}/events`
- `WS /ws/{user_id}`

## Testing

There is a backend test module covering auth rules, user isolation, WebSocket access, and escalation outcomes.

From the repo root:

```bash
python -m unittest backend.tests.test_auth
```

## A few implementation details worth knowing

- Sessions are stored in the browser with a signed access token.
- The frontend clears saved session data automatically if the backend returns `401`.
- Delivery updates are pushed over WebSocket, not polled.
- Contacts have to be marked as accepted before the escalation flow can use them.
- The project does not use a frontend router. Page changes are handled in `App.jsx`.

## Why this project exists

This is the kind of app that works best as a clear demo: one user, one package flow, one visible escalation path, and live updates that are easy to follow. It is not pretending to be a full shipping platform. It is a focused prototype for the moment after delivery, when a package is most likely to be ignored or stolen.
