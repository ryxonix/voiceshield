# VoiceShield AI — Frontend

React + TypeScript + Vite dashboard for the VoiceShield AI voice-integrity
platform. Talks to the FastAPI backend (`backend/`) over `/api`, `/ws` and
`/health`, which are proxied to `http://localhost:8000` in dev (see
`vite.config.ts`).

## Run

```sh
npm install
npm run dev        # http://localhost:5173  (proxies to :8000 backend)
npm run build      # typecheck + production bundle (dist/)
```

## Wiring

- `src/api` convention: fetch requests use `apiBase()` (`src/components/ui.tsx`),
  which returns `http://<host>:8000` during local dev and an empty string when
  served from the same origin as the backend (e.g. a reverse proxy).
- WebSocket sessions: `wsBase()` in the same file.
- UI text goes through `src/i18n.tsx` (`en` is the source language; `hi` and
  `kn` are full translations). Add any new user-facing string to the three
  dictionaries.