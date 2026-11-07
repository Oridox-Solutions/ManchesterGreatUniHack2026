# TestPilot frontend

React and Vite interface for the TestPilot API.

    npm ci
    npm run dev

The development server proxies /api and /health to http://localhost:8000. Set VITE_API_URL when the backend is hosted elsewhere.

Quality checks:

    npm run lint
    npm run build
