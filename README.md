# Agentic Jewelry Intelligence Framework

An autonomous, modular backend system for intelligent jewelry product scraping and analysis.

## Overview

This framework provides an end-to-end solution for:
- **Autonomous Web Scraping**: Crawls jewelry websites using Playwright for JS-rendered content
- **Intelligent Extraction**: Extracts and normalizes product metadata
- **AI-Powered Analysis**: Uses vision models to infer visual attributes (gemstone, metal color, jewelry type)
- **Smart Summarization**: Generates product summaries and vibe classifications
- **RESTful API**: Clean API for triggering scrapes and querying results

## Architecture

The system is built on a modular agent-based architecture:

1. **Crawler Agent** - Discovers and scrapes product pages using Playwright
2. **Extractor Agent** - Extracts metadata from HTML using heuristics and selectors
3. **Normalizer Agent** - Normalizes data to canonical formats
4. **Inference Agent** - AI-powered visual attribute detection using OpenAI Vision
5. **Summarizer Agent** - Generates summaries and vibe tags
6. **Storage Agent** - Persists data with deduplication
7. **Orchestrator** - Coordinates the entire pipeline

## Tech Stack

- **Framework**: FastAPI (async-first Python web framework)
- **Crawler**: Playwright (headless browser automation)
- **Database**: PostgreSQL + SQLAlchemy (async)
- **Queue**: Redis + Celery (background job processing)
- **AI**: OpenAI Vision API (or fallback rule-based inference)
- **Containerization**: Docker + Docker Compose

## Prerequisites

- Python 3.11+
- Docker & Docker Compose (recommended)
- PostgreSQL 15+ (if running locally)
- Redis (if running locally)
- OpenAI API key (optional, for AI features)

## Quick Start with Docker

1. **Clone the repository**:
```bash
cd "F:\projects\Agentic Jewelry Intelligence Framework\Agentic-Jewelry-Intelligence-Framework"
```

2. **Create environment file**:
```bash
cp .env.template .env
```

Edit `.env` and add your OpenAI API key:
```
OPENAI_API_KEY=your-api-key-here
```

3. **Start services**:
```bash
docker-compose up --build
```

4. **Access the API**:
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

## Local Development Setup

1. **Install Poetry** (if not already installed):
```bash
pip install poetry
```

2. **Install dependencies**:
```bash
poetry install
```

3. **Install Playwright browsers**:
```bash
poetry run playwright install chromium
```

4. **Setup PostgreSQL and Redis** (make sure they're running):
```bash
# Using Docker for databases only:
docker run -d --name postgres -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:15-alpine
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

5. **Create .env file**:
```bash
cp .env.template .env
# Edit .env with your configuration
```

6. **Run database migrations**:
```bash
poetry run alembic upgrade head
```

7. **Start the application**:
```bash
poetry run uvicorn app.main:app --reload
```

## API Usage

### 1. Create a Scraping Job

```bash
curl -X POST "http://localhost:8000/scrape" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.example-jewelry-site.com"}'
```

Response:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued"
}
```

### 2. Check Job Status

```bash
curl "http://localhost:8000/status/550e8400-e29b-41d4-a716-446655440000"
```

Response:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "url": "https://www.example-jewelry-site.com",
  "status": "success",
  "started_at": "2025-01-15T10:30:00Z",
  "finished_at": "2025-01-15T10:35:00Z",
  "stats_json": {
    "pages_crawled": 25,
    "products_found": 15,
    "products_stored": 15,
    "images_downloaded": 45,
    "errors": 0
  }
}
```

### 3. Query Jewelry Products

```bash
# Get all jewelry
curl "http://localhost:8000/jewels?limit=10&offset=0"

# Filter by vibe
curl "http://localhost:8000/jewels?vibe=wedding&limit=10"

# Filter by metal
curl "http://localhost:8000/jewels?metal=gold&limit=10"

# Filter by jewelry type
curl "http://localhost:8000/jewels?jewel_type=ring&limit=10"

# Combine filters
curl "http://localhost:8000/jewels?vibe=engagement&metal=platinum&jewel_type=ring"
```

Response:
```json
{
  "items": [
    {
      "id": "...",
      "name": "Elegant Diamond Ring",
      "source_url": "https://...",
      "jewel_type": "ring",
      "metal": "platinum",
      "gemstone": "diamond",
      "gemstone_color": "white",
      "metal_color": "platinum",
      "price_amount": 5999.99,
      "price_currency": "USD",
      "vibe": "engagement",
      "summary": "A stunning platinum ring featuring a brilliant white diamond, perfect for engagements.",
      "images": ["path/to/image1.jpg", "path/to/image2.jpg"],
      "inferred_attributes": {
        "jewelry_type": "ring",
        "gemstone": "diamond",
        "gemstone_color": "white",
        "metal_color": "platinum",
        "confidence": {"gemstone": 0.95, "metal_color": 0.90}
      }
    }
  ],
  "total": 15,
  "limit": 10,
  "offset": 0
}
```

### 4. Get Single Jewel

```bash
curl "http://localhost:8000/jewels/{jewel_id}"
```

## Database Schema

### Jobs Table
- `id` (UUID) - Primary key
- `url` (TEXT) - URL to scrape
- `status` (ENUM) - queued, running, success, failed
- `started_at`, `finished_at` (TIMESTAMP)
- `stats_json` (JSON) - Job statistics
- `error_message` (TEXT) - Error details if failed

### Jewels Table
- `id` (UUID) - Primary key
- `name` (TEXT) - Product name
- `source_url` (TEXT) - Original product URL (unique)
- `jewel_type` (VARCHAR) - ring, necklace, earring, etc.
- `metal` (VARCHAR) - Metal type (normalized)
- `gemstone` (VARCHAR) - Gemstone type
- `gemstone_color`, `metal_color`, `color` (VARCHAR)
- `price_amount` (NUMERIC), `price_currency` (VARCHAR)
- `inferred_attributes` (JSON) - AI-inferred data
- `vibe` (VARCHAR) - Occasion classification
- `summary` (TEXT) - AI-generated summary
- `images` (JSON) - Array of image paths
- `raw_metadata` (JSON) - Original scraped data
- `created_at`, `updated_at` (TIMESTAMP)

## Configuration

All configuration is done via environment variables in `.env`:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/jewelry_db

# Redis
REDIS_URL=redis://localhost:6379/0

# OpenAI
OPENAI_API_KEY=your-api-key

# Application
APP_HOST=0.0.0.0
APP_PORT=8000
LOG_LEVEL=INFO

# Storage
IMAGE_STORAGE_PATH=./data/images
MAX_IMAGES_PER_PRODUCT=5

# Crawler
CRAWLER_MAX_PAGES=50
CRAWLER_TIMEOUT=30000
CRAWLER_HEADLESS=true

# AI
AI_MODEL=gpt-4-vision-preview
AI_MAX_TOKENS=500
AI_TEMPERATURE=0.3
```

## Normalization Rules

The system applies the following normalization:

### Metal
- `18K`, `18kt`, `18 kt` → `18kt gold`
- `white gold`, `yellow gold`, `rose gold` → canonical forms
- `sterling silver`, `platinum`, etc.

### Currency
- Symbol extraction: `$` → `USD`, `€` → `EUR`, `₹` → `INR`
- Numeric parsing with decimal handling

### Deduplication
- Based on `source_url` (exact match)
- Future: Image perceptual hashing

## AI Inference

The framework supports two modes:

### 1. OpenAI Vision (Recommended)
- Uses `gpt-4-vision-preview` to analyze product images
- Infers: jewelry type, gemstone, gemstone color, metal color
- Provides confidence scores

### 2. Rule-Based Fallback
- Activates when OpenAI API is unavailable
- Uses text extraction and heuristics
- Lower confidence scores

## Vibe Classifications

Products are automatically classified into vibes:
- `wedding` - Bridal jewelry
- `engagement` - Engagement rings
- `casual` - Everyday wear
- `festive` - Festival/celebration jewelry
- `formal` - Formal events
- `date-night` - Romantic occasions
- `everyday` - Daily wear
- `party` - Party/cocktail events

## Project Structure

```
agentic-jewelry-intelligence/
├── app/
│   ├── agents/              # Agent modules
│   │   ├── crawler.py       # Web crawler
│   │   ├── extractor.py     # Metadata extraction
│   │   ├── normalizer.py    # Data normalization
│   │   ├── inference.py     # AI inference
│   │   ├── summarizer.py    # Summary generation
│   │   ├── storage.py       # Data storage
│   │   └── orchestrator.py  # Pipeline orchestration
│   ├── api/                 # API endpoints
│   │   ├── scrape.py
│   │   ├── status.py
│   │   └── jewels.py
│   ├── models/              # Database models
│   │   ├── job.py
│   │   └── jewel.py
│   ├── schemas/             # Pydantic schemas
│   ├── config.py            # Configuration
│   ├── database.py          # Database setup
│   └── main.py              # FastAPI app
├── alembic/                 # Database migrations
├── data/images/             # Downloaded images
├── tests/                   # Test suite
├── docker-compose.yml       # Docker setup
├── Dockerfile
├── pyproject.toml           # Dependencies
├── .env.template            # Environment template
└── README.md
```

## Testing

Run tests:
```bash
poetry run pytest
```

Run with coverage:
```bash
poetry run pytest --cov=app tests/
```

## Troubleshooting

### Issue: Playwright browser not found
```bash
poetry run playwright install chromium
poetry run playwright install-deps
```

### Issue: Database connection error
- Ensure PostgreSQL is running
- Check `DATABASE_URL` in `.env`
- Run migrations: `poetry run alembic upgrade head`

### Issue: Redis connection error
- Ensure Redis is running
- Check `REDIS_URL` in `.env`

### Issue: OpenAI API errors
- Verify `OPENAI_API_KEY` is set correctly
- Check API quota/limits
- System will fallback to rule-based inference if AI fails

## Performance Considerations

- **Crawler**: Respects `CRAWLER_MAX_PAGES` limit
- **Rate Limiting**: Add delays between requests for production
- **Image Storage**: Local filesystem (dev) or S3 (production)
- **Concurrency**: Async throughout, uses background tasks

## Future Enhancements

- [ ] Celery worker integration for distributed processing
- [ ] S3 storage for images
- [ ] Image perceptual hashing for deduplication
- [ ] Fine-tuned CLIP model for offline inference
- [ ] Rate limiting and robots.txt compliance
- [ ] Admin dashboard
- [ ] Webhook notifications
- [ ] Multi-site scraping profiles

## License

MIT License

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## Support

For issues and questions:
- Create an issue on GitHub
- Check documentation at `/docs`

---

**Built for Thuli Studios Technical Challenge**

*Autonomous. Intelligent. Scalable.*
