# SEO-Pocket

View any webpage as Googlebot sees it. Extract SEO metadata, detect cloaking, analyze hreflang.

## Features

- View rendered HTML as Googlebot Mobile
- Extract: Title, H1, Meta Description, Canonical, Robots
- Hreflang tags visualization
- Full source code viewer
- Dark theme with particle animation

## Quick Start

### 1. Install dependencies

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Run server

```bash
cd backend
python main.py
```

### 3. Open browser

Go to http://localhost:8000

## Tech Stack

- **Backend:** FastAPI + Playwright + BeautifulSoup
- **Frontend:** Vanilla JS + Canvas 2D particles
- **Styling:** CSS Variables, Dark theme

## API

### POST /api/analyze

Analyze a URL as Googlebot.

**Request:**
```json
{
  "url": "https://example.com"
}
```

**Response:**
```json
{
  "success": true,
  "url": "https://example.com",
  "title": "Example Domain",
  "h1": "Example Domain",
  "description": null,
  "canonical": null,
  "html_lang": "en",
  "hreflang": [],
  "robots": null,
  "status_code": 200,
  "html": "<!doctype html>...",
  "fetch_time_ms": 2340
}
```

### GET /api/health

Health check endpoint.

## Project Structure

```
SEO-Pocket/
├── backend/
│   ├── main.py           # FastAPI app
│   ├── fetcher.py        # Playwright Googlebot fetcher
│   ├── parser.py         # HTML parser
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   └── static/
│       ├── css/
│       │   └── styles.css
│       └── js/
│           ├── app.js
│           └── particles.js
└── README.md
```

## Cloaking Detection

To detect cloaking, compare the HTML from SEO-Pocket (Googlebot view) with regular browser view. If they differ significantly, the site may be using cloaking.

## License

MIT
