# Pixiv Crawler - Comprehensive Collection Tool

A powerful, production-ready async web crawler specifically designed for **Pixiv** (ピクシブ), capable of collecting artwork metadata, user information, and downloading high-quality images with intelligent management.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Overview](#api-overview)
- [Data Models](#data-models)
- [Troubleshooting](#troubleshooting)

---

## Features

### Core Capabilities

✅ **Multi-Account Support** — Manage multiple Pixiv accounts with automatic rotation and rate-limit handling  
✅ **Async/Await Architecture** — Non-blocking I/O with configurable concurrency (default: 20 concurrent tasks)  
✅ **Intelligent Scheduling** — Priority-based request scheduling with circular queue management  
✅ **Middleware Stack** — Extensible request/response processing pipeline with automatic retry logic  
✅ **MongoDB Integration** — Persistent storage with efficient indexing and aggregation  
✅ **Proxy Support** — Optional HTTP proxy for bypassing regional restrictions  
✅ **Error Recovery** — Automatic timeout/rate-limit detection with exponential backoff  
✅ **Interactive CLI Interface** — Real-time control with pause/resume/status commands ⭐ NEW  
✅ **Runtime Monitoring** — Comprehensive metrics and performance tracking ⭐ NEW  
✅ **Configuration Management** — Persistent settings and run history ⭐ NEW  

### Supported Collection Types

- [x] **User Followings** — Track and update all followed creators with metadata
- [x] **Artwork Metadata** — Illustrations, Manga, Ugoira (animated GIFs), Novels
- [x] **Bookmarks** — Collect and organize bookmarked works
- [x] **Series Information** — Chain-fetch multi-part works (partial support)
- [ ] **Discovery/Trending** — Trending and recommended content
- [ ] **Tag-based Search** — Collect by specific tags or keywords

### Download Support

- [x] **Illustrations** (PNG, JPEG) — Multi-page support
- [x] **Manga** — Full chapter download with page ordering
- [x] **Ugoira** — Animated GIF with frame metadata
- [x] **Novels** — Text content + cover images
- [ ] **Series Collections** — Multi-part novel/manga collections
- [x] **User Profiles** — Avatar and background images

---

## Architecture

### Project Structure

```
pixiv-crawler/
├── cmdapp/
│   ├── config.json                   # Configuration (credentials, proxy, logging)
│   ├── main.py                       # Entry point
│   ├── gui_for_cmdapp.py             # PyQt5 GUI wrapper
│   │
│   ├── engine/                       # Core crawler engine
│   │   ├── engine.py                 # Main orchestration
│   │   └── scheduler.py              # Request scheduling (Priority Queue)
│   │
│   ├── spiders/                      # Spider implementations
│   │   ├── base_spider.py            # Abstract spider class
│   │   └── followings_info_spider.py # Follows metadata collection
│   │
│   ├── downloader/                   # HTTP client management
│   │   ├── clientpool.py             # Account rotation & rate limiting
│   │   └── downloader.py             # Request executor
│   │
│   ├── middlewares/                  # Request/response processing
│   │   ├── base.py                   # Middleware interface
│   │   ├── retry.py                  # Automatic retry logic
│   │   └── manager.py                # Middleware chain
│   │
│   ├── pipelines/                    # Data processing & storage
│   │   ├── base.py                   # Pipeline interface
│   │   ├── mongodb.py                # MongoDB storage backend
│   │   └── manager.py                # Pipeline coordination
│   │
│   ├── storage/                      # Database handlers
│   │   └── mongoDB_handler.py        # Async MongoDB interface
│   │
│   ├── data/                         # Data models & types
│   │   ├── models.py                 # Request, Response, Item dataclasses
│   │   └── __init__.py
│   │
│   ├── utils/                        # Utilities & helpers
│   │   ├── config_handler.py         # Configuration parsing
│   │   ├── data_service.py           # Read-only data access layer
│   │   └── logger.py                 # Logging configuration
│   │
│   ├── common/                       # Common utilities
│   │   ├── clientpool.py             # Client pool
│   │   └── response_hander.py        # Response processing
│   │
│   ├── download_hander/              # Download orchestration
│   │   ├── download_hander.py
│   │   └── image_downloader.py
│   │
│   └── info_recorders/               # Data collection handlers
│       ├── work_info_recorder.py
│       └── work_id_fetcher.py
│
├── tests/
├── examples/                         # API response examples
├── GUIcmd/                           # PyQt5 UI components
└── requirements.txt
```

### Request Flow

```
Request Generation (Spider)
        ↓
Scheduler (Priority Queue + Rate Limit)
        ↓
Middleware (Request Preparation)
        ↓
Downloader (HTTP Execution)
        ↓
Middleware (Response Processing + Error Handling)
        ↓
Spider Callback (Parsing)
        ↓
Pipeline (Processing & Storage)
        ↓
Request Queue Feedback (New Requests)
```

---

## Installation

### Prerequisites

- Python 3.8+
- MongoDB 4.0+
- pip or conda

### Setup Steps

```bash
# 1. Clone repository
git clone https://github.com/YOUR_USERNAME/pixiv-crawler.git
cd pixiv-crawler/cmdapp

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start MongoDB
mongod  # or: brew services start mongodb-community

# 4. Configure credentials
# - Open https://pixiv.net and log in
# - Get PHPSESSID from browser cookies (DevTools → Application → Cookies)
# - Update config.json with your session ID
```

---

## Configuration

### config.json

```json
{
    "clientpool_config": {
        "proxy": {
            "enable": false,
            "url": "http://localhost:12334"
        },
        "max_connections": 3,
        "request_interval": 2,
        "primary_account": {
            "id": 123456789,
            "email": "your-email@example.com",
            "cookies": {
                "PHPSESSID": "YOUR_SESSION_ID"
            }
        },
        "client_pool": [
            {
                "email": "secondary-account@example.com",
                "cookies": {
                    "PHPSESSID": "ANOTHER_SESSION_ID"
                }
            }
        ]
    }
}
```

### Key Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `proxy.enable` | bool | `false` | Enable HTTP proxy |
| `max_connections` | int | `3` | Concurrent request limit |
| `request_interval` | float | `2` | Min seconds between requests |
| `primary_account` | dict | — | Main account (higher priority) |
| `client_pool` | list | — | Secondary accounts for load balancing |

---

## Usage

### 🎮 Interactive CLI Mode (New!)

Start the crawler with real-time control interface:

```bash
python main.py

# Output:
# ============================================================
#   Welcome to Pixiv Crawler - Type 'help' for commands
# ============================================================
#
# crawler> help
```

#### Available Commands

| Command | Description | Example |
|---------|-------------|---------|
| `help` | Show all commands | `help` |
| `status` | Display real-time status & metrics | `status` |
| `spider` | List all registered spiders | `spider` |
| `pause` | Pause current crawler | `pause` |
| `resume` | Resume paused crawler | `resume` |
| `run <name>` | Start specific spider | `run workinfo` |
| `exit` / `quit` | Gracefully shutdown | `exit` |

#### Status Display Example

```
╔════════════════════════════════════════════════════════════╗
║              Engine Status & Statistics                    ║
╠════════════════════════════════════════════════════════════╣
║ Status             : RUNNING                               ║
║ Running Time       : 00:05:32                              ║
║ Current Spider     : workinfo                              ║
║ Active Tasks       : 8                                     ║
║ Pending Tasks      : 0                                     ║
║ Queue Size         : 45                                    ║
║ Scheduled Requests : 102                                   ║
║ Finished Requests  : 567                                   ║
╚════════════════════════════════════════════════════════════╝
```

### Command Line (Standard)

```bash
# Start crawler (CLI mode)
python main.py

# Monitor logs
tail -f crawler.log

# GUI mode (PyQt5)
python gui_for_cmdapp.py
```

### Programmatic Usage

```python
from engine import Engine

crawler = Engine()
import asyncio
asyncio.run(crawler.start())
```

---

## 📚 Documentation

For comprehensive guides and advanced usage, see:

- **[QUICK_START.md](QUICK_START.md)** — Installation and basic commands
- **[OPTIMIZATION_GUIDE.md](OPTIMIZATION_GUIDE.md)** — Code analysis and optimization strategies
- **[ADVANCED_USAGE.md](ADVANCED_USAGE.md)** — Performance tuning, custom spiders, and deployment
- **[IMPROVEMENTS_SUMMARY.md](IMPROVEMENTS_SUMMARY.md)** — Summary of recent improvements

---

## API Overview

### Core Classes

#### `Engine`

Main orchestration class.

```python
class Engine:
    async def start(self) -> None
    async def pause(self) -> None
    async def resume(self) -> None
    async def shutdown(self) -> None
```

#### `BaseSpider`

Base class for custom spiders.

```python
class BaseSpider:
    name: str
    init_requests: List[Request]
    async def parse(self, response: Response) -> SpiderResult
```

#### `MongoDBHandler`

Async MongoDB interface.

```python
class MongoDBHandler:
    async def insert_one(self, document: dict, collection: str) -> bool
    async def find_one(self, key: str, value: Any, collection: str) -> dict | None
    async def find_exist(self, key: str, collection: str):
        yield doc  # Async generator
```

---

## Data Models

### Request

```python
@dataclass
class Request:
    method: str                    # HTTP method
    url: str                       # Target URL
    spider_parser: Callable        # Parser function
    params: dict | None = None
    priority: int = 50             # 0-100 (higher = earlier)
    max_retry: int = 3
```

### Response

```python
@dataclass
class Response:
    request: Request
    status: int                    # HTTP status
    headers: dict
    content: bytes
    elapsed: float                 # Duration (seconds)
    
    def text(self) -> str
    def json(self) -> dict
```

### Item

```python
@dataclass
class Item:
    type: str                      # e.g., "db" for storage
    data: dict                     # Item data
```

---

## Troubleshooting

### "Request failed: 401 Unauthorized"

**Cause:** Session expired  
**Solution:** Update PHPSESSID in config.json

```bash
# Update to fresh session from browser cookies
```

### "Rate Limited (HTTP 429)"

**Cause:** Too many requests  
**Solution:** Adjust config.json

```json
"request_interval": 5,
"max_connections": 2
```

### "MongoDB Connection Refused"

**Cause:** MongoDB not running  
**Solution:**

```bash
# OS X
brew services start mongodb-community

# Linux
sudo systemctl start mongod

# Windows
net start MongoDB
```

### "Proxy Connection Failed"

**Cause:** Proxy unreachable  
**Solution:** Verify proxy URL and connectivity

```bash
curl -x http://localhost:12334 https://www.pixiv.net
```

---

## Recent Updates

- ✅ Fixed followings spider to request all pages (was only first page)
- ✅ Improved engine exception handling and logging
- ✅ Completed response handler file write implementation
- ✅ Standardized field naming (userName)
- ✅ Enhanced error recovery and rate-limit detection

See [updatehistory.md](./updatehistory.md) for full changelog.

---

## Roadmap

### Network Features
- [x] Clientpool with async support
- [x] Multi-account rotation
- [ ] SNI bypass for Pixiv blocking
- [ ] Pixiv cat image proxy integration

### Collection Types
- [x] Bookmarks
- [x] Followings  
- [ ] ID-based search
- [ ] Tag-based search
- [ ] Trending/Discovery

### Download Types
- [x] Illust, Manga, Ugoira, Novel
- [ ] Series collections
- [ ] Novel-embedded illustrations

---

## Contributing

Contributions welcome! Please follow PEP 8 and include tests.

```bash
# Format code
pip install black isort
black . && isort .

# Run tests
pytest tests/ -v
```

---

## Legal Notice

This project is for **educational and personal use** only. Please respect Pixiv's Terms of Service and copyright policies. Ensure compliance with robots.txt and rate limits.

---

## License

Provided as-is for learning purposes.

---

**Last Updated:** March 2026

