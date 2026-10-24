# Ghost Audit Console (web)

React + TypeScript + Vite operator console for the deletion auditor. It talks only to the local FastAPI (`code/ghost/api.py`) through the `/api` dev proxy and never holds API keys.

```text
npm install
npm run dev      # http://127.0.0.1:5173 (API expected at 127.0.0.1:8000)
npm run build
```

Screens and their issues: `docs/delivery_plan.md` §5.
