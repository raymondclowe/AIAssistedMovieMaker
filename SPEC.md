# AI-Assisted Movie Maker - Technical Specification

## Overview

The AI-Assisted Movie Maker is a Streamlit application that guides users through the filmmaking process from concept to final production, using AI assistance at every step.

## Architecture

```
┌─────────────────────────────────────────────┐
│              Frontend Layer                  │
│           Streamlit (app.py)                │
├─────────────────────────────────────────────┤
│            Backend Services                  │
│     db.py │ assets.py │ ai.py              │
├─────────────────────────────────────────────┤
│              Data Layer                      │
│   SQLite Database │ File System (assets/)   │
└─────────────────────────────────────────────┘
```

**Design for Frontend Swappability**: The backend services (`db.py`, `assets.py`, `ai.py`) are independent of Streamlit and can be used with any frontend framework (React, Vue, Flask, etc.).

## 4-Phase Workflow

The app implements a simplified 4-phase workflow that mirrors professional film development:

| Phase | Purpose | Content Types |
|-------|---------|---------------|
| **📝 Story** | Develop narrative | logline, concept, outline, act, beat, scene |
| **🎨 Design** | Define visuals | character, location, prop, costume, style_guide |
| **🎬 Shooting** | Plan production | shot_breakdown, cinematography, shot |
| **⚡ Generate** | Create assets | images, videos, audio files |

## Data Model

### Database Schema (SQLite)

```sql
-- Projects
CREATE TABLE projects (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    root_path TEXT NOT NULL
);

-- Tabs (internal organization)
CREATE TABLE tabs (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    name TEXT NOT NULL,
    position INTEGER NOT NULL
);

-- Blocks (all content)
CREATE TABLE blocks (
    id INTEGER PRIMARY KEY,
    tab_id INTEGER REFERENCES tabs(id),
    parent_id INTEGER REFERENCES blocks(id),
    type TEXT NOT NULL,
    content TEXT,
    tags TEXT,  -- JSON array
    version INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Assets (binary files)
CREATE TABLE assets (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    hash TEXT NOT NULL UNIQUE,  -- SHA-256
    path TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    size_bytes INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    meta_json TEXT
);

-- Block-Asset linking
CREATE TABLE block_assets (
    block_id INTEGER REFERENCES blocks(id),
    asset_id INTEGER REFERENCES assets(id),
    role TEXT,
    PRIMARY KEY (block_id, asset_id)
);

-- History (change tracking)
CREATE TABLE history (
    id INTEGER PRIMARY KEY,
    block_id INTEGER REFERENCES blocks(id),
    action TEXT NOT NULL,
    payload TEXT,  -- JSON
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Dependencies (content relationships)
CREATE TABLE dependencies (
    src_block_id INTEGER REFERENCES blocks(id),
    dst_block_id INTEGER REFERENCES blocks(id),
    type TEXT,
    PRIMARY KEY (src_block_id, dst_block_id)
);
```

### File System Layout

```
movie_project/
├── project.db          # SQLite database
├── assets/
│   ├── abc123...def.png   # Hash-named files
│   └── 789xyz...ghi.mp4
└── exports/
    └── project_summary.md
```

## AI Providers

### OpenRouter (Text Generation)
- **Purpose**: Generate text content (plots, scenes, characters, etc.)
- **API**: https://openrouter.ai/api/v1
- **Model Selection**: Categorized by price (draft vs final)
- **Draft Models**: Price < $0.001/1k tokens
- **Final Models**: Higher quality, higher cost

### Replicate (Image/Video Generation)
- **Purpose**: Generate visual assets
- **API**: https://api.replicate.com/v1
- **Collections**: text-to-image, text-to-video
- **Draft Models**: Identified by name patterns (schnell, turbo, fast)
- **Final Models**: Higher quality models

## API Key Configuration

The app supports multiple ways to configure API keys:

1. **UI Input** (recommended for non-technical users)
   - Enter keys in the sidebar "🔑 API Keys" section
   - Keys stored in session only, not persisted

2. **Environment Variables** (recommended for developers)
   ```bash
   OPENROUTER_API_KEY=sk-or-...
   REPLICATE_API_KEY=r8_...
   ```

3. **Fallback Variables** (for CI/CD environments)
   ```bash
   COPILOT_OPENROUTER_API_KEY=sk-or-...
   COPILOT_REPLICATE_API_KEY=r8_...
   ```

## Key Features

### Hash-Based Asset Deduplication
- All assets stored with SHA-256 hash as filename
- Identical files stored only once
- Prevents regenerating existing content

### Draft vs Final Mode
- **Draft**: Use cheap/free models for rapid iteration
- **Final**: Use best-quality models for production

### Dependency Tracking
- Blocks can depend on other blocks
- When source changes, dependents flagged for regeneration

### Version History
- All block changes recorded in history table
- Supports undo and change tracking

## Testing Strategy

For cost-efficient development:
1. **Mock Mode**: Works without API keys (placeholder content)
2. **Draft Mode Default**: Uses cheapest available models
3. **Stills Before Video**: Generate images first, videos only when approved
4. **Smart Caching**: Hash-based deduplication prevents duplicates

## Requirements

```
streamlit>=1.28.0
httpx>=0.25.0
sqlalchemy>=2.0.0
```

## Future Enhancements

Planned improvements that can be added incrementally:
- FastAPI layer for alternative frontends
- Batch generation operations
- Timeline/assembly view
- Collaborative editing
- Cloud storage integration
