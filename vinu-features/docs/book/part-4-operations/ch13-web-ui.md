# Chapter 13 - Web UI

| Field | Value |
|-------|-------|
| **Package** | vinu-features |
| **Module** | `vinu-features/web/` |
| **Status** | v1 |
| **Prerequisites** | ch10, ch11 |

## Overview

A modern React-based web interface for managing feature requests, browsing presets, and monitoring runs.

## Quick Start

```bash
cd vinu-features/web
npm install
npm run dev
```

Open http://localhost:5173 to access the UI.

## Production Build

```bash
npm run build
# Output: ../vinu_features/server/static/
```

Serve the static files via the FastAPI app or any static file server.

## Components

### Dashboard (Phase 1 — 2026-07-06)

The dashboard has been rewritten with 8 sections, all computed client-side with no new dependencies:

1. **Stat cards** (7 cards): Pending, Running, Done, Failed, Total, Features count, Presets count
2. **Secondary stats**: Success rate percentage + total rows generated across all runs
3. **System Health**: Shows `data_dir`, `stock_api_url`, `db_path`, `db_size_bytes`, `total_request_count`, and `status_counts` with color badges (green/yellow/red per status)
4. **Top Symbols**: Horizontal bar chart (top 5 symbols by run count)
5. **Most Used Presets**: Horizontal bar chart with ML model chips for presets that use ML
6. **Activity Trend**: Last 7 days bar chart (CSS-based, no chart library)
7. **Recent Failures**: Retry buttons, time-ago timestamps, truncated error messages
8. **Recent Requests**: Last 10 runs with status badges (same as original)

**Health endpoint** (`GET /health`) returns:
```json
{
  "info": {
    "db_path": "...",
    "status_counts": {"pending": 0, "running": 0, "done": 5, "failed": 1},
    "data_dir": "...",
    "stock_api_url": "...",
    "db_size_bytes": 24576,
    "total_request_count": 6,
    "catalog_count": 23,
    "presets_count": 11
  }
}
```

### Request List

- **Filtering**: By status (pending, running, done, failed)
- **Search**: By title
- **Actions**: View details, delete runs
- **Sorting**: By creation date (newest first)

### Submit Form

- **Title**: Unique identifier for the run
- **Symbols**: Comma-separated list (e.g., `AAPL,GOOGL,MSFT`)
- **Days**: Lookback period (default: 365)
- **Interval**: Candle resolution (`1m`, `5m`, `1h`, `1d`, etc.)
- **Preset**: Select from blueprints or custom features
- **Features**: Advanced mode with structured specs (`rsi:period=20`)
- **Run immediately**: Checkbox to process right after submission

### Presets Browser

- **Categories**: TA bundles, themed packs, alpha factors
- **Details**: Feature count and description for each preset
- **Quick select**: Click to populate submit form

### Feature Catalog

- **Search**: Find indicators by name or keyword
- **Details**: Parameters, description, example usage
- **Copy spec**: One-click copy of feature spec string

## Navigation

| Tab | Purpose |
|-----|---------|
| Dashboard | Overview and stats |
| Requests | List and filter runs |
| Submit | Create new request |
| Presets | Browse blueprints |
| Catalog | Feature reference |

## Toast Notifications

Success and error messages appear at the bottom center for 4 seconds.

## API Integration

The UI proxies all requests to the FastAPI backend:

- `/health` - Registry stats
- `/requests` - CRUD operations
- `/presets` - Blueprint list
- `/features` - Indicator catalog

Proxy configured in `vite.config.js`:

```javascript
proxy: {
  '/health': 'http://localhost:8082',
  '/requests': 'http://localhost:8082',
  '/presets': 'http://localhost:8082',
  '/features': 'http://localhost:8082',
}
```

## Styling

- **Theme**: Dark mode with CSS variables
- **Colors**: Primary (`#6366f1`), success, warning, danger
- **Typography**: System sans-serif with mono for specs
- **Animations**: Fade-in transitions, spin for loading

## Browser Support

Modern browsers with ES2020 support:
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## Accessibility

- Keyboard navigation for all interactive elements
- Focus indicators on inputs and buttons
- Semantic HTML structure
- ARIA labels for status badges

## Troubleshooting

**UI won't load**: Check that the backend is running on port 8082

**Proxy errors**: Verify `vite.config.js` proxy targets match your backend

**Stale data**: Refresh the page or navigate away and back

**Build fails**: Clear `node_modules` and run `npm install` again