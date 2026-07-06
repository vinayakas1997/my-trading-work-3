# Chapter 24 — Web UI dashboard

| Field | Value |
|-------|-------|
| **Package** | vinu-correlation |
| **Module** | `vinu_correlation/web/` |
| **Status** | DRAFT |
| **Prerequisites** | ch22 |

## 1. Overview

A React-based single-page app served at `/ui` on the FastAPI server. It provides a dashboard for viewing correlation data for watchlist tickers.

## 2. Components

| File | Responsibility |
|------|----------------|
| `web/src/App.jsx` | Main app layout with sidebar + search |
| `web/src/components/CorrelationDashboard.jsx` | Dashboard view for a ticker |
| `web/src/api.js` | API client for backend endpoints |
| `web/src/main.jsx` | React entry point |
| `web/src/index.css` | Styling |
| `web/vite.config.js` | Vite build config |

## 3. Features

- **Sidebar**: watchlist tickers with active indicator
- **Search**: type any ticker to switch view
- **Dashboard**: shows correlation metrics for the selected ticker

## 4. Build

```bash
cd web
npm install
npm run build   # outputs to server/static/
```

The built static files are served directly by FastAPI's `StaticFiles` mount.
