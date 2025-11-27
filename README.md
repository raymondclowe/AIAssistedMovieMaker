# AI-Assisted Movie Maker 🎬

An AI-powered application to help you create movies from concept to final cut. This tool guides you through a streamlined 4-phase filmmaking workflow with AI assistance at every step.

## Quick Start

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Run the app:**
```bash
streamlit run app.py
```

3. **Add your API keys** in the sidebar (or set as environment variables)

That's it! Start creating your movie.

## Workflow

The app uses a simplified **4-phase workflow** that mirrors how professionals develop film projects:

### 📝 Phase 1: Story
Develop your narrative from initial concept to complete screenplay.
- **Concept** - Write your logline or movie idea
- **Plot** - Generate or write a structured plot outline
- **Screenplay** - Create scenes with dialogue and action

### 🎨 Phase 2: Design
Define the visual elements of your movie.
- **Characters** - Create detailed character profiles
- **Locations** - Describe your settings and environments
- **Props** - Track important items and costumes
- **Style** - Define your visual art direction

### 🎬 Phase 3: Shooting
Plan your production with detailed shot breakdowns.
- **Shot List** - Break scenes into individual shots
- **Cinematography** - Define camera work and lighting
- **Shot Cards** - Create detailed descriptions for each shot

### ⚡ Phase 4: Generate
Create your visual assets and review your project.
- **Generate** - Create still images or videos from shot descriptions
- **Assets** - Manage all your project media files
- **Review** - See project summary and export data

## AI Providers

The app uses two AI services:

| Provider | Purpose | Get API Key |
|----------|---------|-------------|
| **OpenRouter** | Text generation (plot, scenes, characters) | [openrouter.ai/keys](https://openrouter.ai/keys) |
| **Replicate** | Image and video generation | [replicate.com/account](https://replicate.com/account/api-tokens) |

### Setting Up API Keys

**Option 1: Via the App (Recommended for most users)**
- Click the "🔑 API Keys" section in the sidebar
- Paste your keys into the input fields
- Keys are stored in session only (not saved to disk)

**Option 2: Environment Variables (For developers)**
```bash
export OPENROUTER_API_KEY=sk-or-...
export REPLICATE_API_KEY=r8_...
```

The app also checks for `COPILOT_` prefixed versions of these keys.

## Generation Modes

- **Draft Mode** (default) - Uses fast, inexpensive models for rapid iteration
- **Final Mode** - Uses best-quality models for production content

💡 **Tip:** Use Draft mode while developing your story, then switch to Final mode for your best shots.

## Project Structure

```
AIAssistedMovieMaker/
├── app.py                 # Main Streamlit application
├── backend/
│   ├── __init__.py
│   ├── db.py              # SQLite database operations
│   ├── assets.py          # Asset management
│   └── ai.py              # AI operations (OpenRouter, Replicate)
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

## Data Storage

Projects are stored locally in a `movie_project/` directory:
- `project.db` - SQLite database with all your content
- `assets/` - Media files (hash-named for deduplication)

## Cost-Efficient Development

The app is designed for iterative development without breaking the bank:

1. **Draft Mode** - Uses free or cheap models by default
2. **Stills First** - Generate still images before committing to video
3. **Smart Caching** - Hash-based deduplication prevents regenerating identical content
4. **Mock Mode** - Works without API keys (shows placeholder content)

## Requirements

- Python 3.9+
- Dependencies in `requirements.txt`:
  - streamlit
  - httpx
  - sqlalchemy

## License

MIT License

## Contributing

Contributions welcome! The app is designed with a clean separation between:
- **Frontend** (app.py - Streamlit, easily swappable)
- **Backend** (backend/ - reusable services)

This makes it easy to replace Streamlit with a different frontend framework in the future.
