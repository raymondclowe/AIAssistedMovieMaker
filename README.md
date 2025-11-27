# AI-Assisted Movie Maker 🎬

An AI-powered application to help you create movies from concept to final cut. This tool guides you through the entire filmmaking pipeline with AI assistance at every step.

## Features

- **Complete Workflow**: 12 tabs covering the full movie-making pipeline
  - Ideation → Plot → Screenplay → Shooting Script → Cast → Locations → Props → Art Direction → Cinematography → Shots → Asset Library → Review

- **AI-Powered Generation**: Generate content at each stage using GPT-4o
  - Plot outlines from concepts
  - Screenplay scenes from plot points
  - Character profiles
  - Location descriptions
  - Shot descriptions

- **Asset Management**: Hash-based deduplication for images, videos, and audio

- **Version History**: Track all changes with full history

- **Dependency Tracking**: Link related content across tabs

## Installation

1. Clone the repository:
```bash
git clone https://github.com/raymondclowe/AIAssistedMovieMaker.git
cd AIAssistedMovieMaker
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. (Optional) Set your OpenAI API key for AI features:
```bash
export OPENAI_API_KEY=your_api_key_here
```

## Usage

Run the Streamlit application:
```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`.

### Workflow

1. **Ideation**: Start with your movie concept or logline
2. **Plot**: Generate or write a plot outline
3. **Screenplay**: Create scenes with dialogue and action
4. **Shooting Script**: Add technical details to scenes
5. **Cast**: Define your characters
6. **Locations**: Describe your settings
7. **Props**: Track physical items
8. **Art Direction**: Define visual style
9. **Cinematography**: Plan camera work
10. **Shots**: Create individual shot cards
11. **Asset Library**: Manage media files
12. **Review**: Review and export your project

### AI Features

- Click "✨ Generate" buttons to create AI content
- Works without API key (shows placeholder content)
- Full AI generation requires OpenAI API key

## Project Structure

```
AIAssistedMovieMaker/
├── app.py                 # Main Streamlit application
├── backend/
│   ├── __init__.py
│   ├── db.py              # SQLite database operations
│   ├── assets.py          # Asset management
│   └── ai.py              # AI operations (LLM, image gen)
├── requirements.txt       # Python dependencies
├── SPEC.md               # Detailed specification
└── README.md             # This file
```

## Data Storage

Projects are stored in a `movie_project/` directory:
- `project.db` - SQLite database
- `assets/` - Media files (hash-named)
- `exports/` - Exported files

## License

MIT License

## Contributing

Contributions welcome! Please read SPEC.md for the full specification.
