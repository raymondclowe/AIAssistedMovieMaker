# Workflow Review and Design Recommendations

This document reviews the manual workflow demonstrated in `Example-manual-flow.md` and proposes design improvements for the AI-Assisted Movie Maker app.

## Executive Summary

The manual workflow demonstrates a **clear, linear progression** that moves from concept to producible video content. The current app design (12 tabs) creates unnecessary complexity that doesn't align with how users naturally work. This document proposes a **simplified 5-phase workflow** that mirrors the successful manual process.

---

## Analysis of Manual Workflow

### What Works Well

1. **Natural Progression**: Concept → Synopsis → Screenplay → Shooting Script → Video
2. **Iterative Refinement**: Each step builds on the previous, allowing for course correction
3. **JSON as Intermediate Format**: The shooting script in JSON provides structured data for both human review and AI generation
4. **Character Reference Sheets**: Using contact sheets for character consistency is elegant
5. **Reusing Context**: The manual workflow passes headers/context with each shot generation

### Pain Points Identified

1. **Too Many Manual Handoffs**: User has to manually copy/paste between AI sessions
2. **No Persistent State**: Each AI conversation starts fresh, losing context
3. **Reference Image Management**: Images are scattered, not linked to characters/locations
4. **Prompt Engineering Required**: User needs to know how to structure prompts for each AI
5. **No Visual Continuity System**: No way to ensure characters look consistent across shots

### Key Insight: The 4 Natural Breakpoints

From the manual workflow, we can identify 4 natural breakpoints where user input/review is needed:

| Phase | Input | Output | User Action |
|-------|-------|--------|-------------|
| 1. **Story** | Initial idea | Complete screenplay | Review, iterate, approve |
| 2. **Production Design** | Screenplay | Characters, Locations, Props defined | Create/upload reference images |
| 3. **Shooting Script** | Screenplay + Design | Structured JSON shot list | Review technical details |
| 4. **Generation** | Shots + References | Images/Videos | Review, regenerate, approve |

---

## Proposed Simplified Workflow

### Phase 1: Story Development
**Combines**: Ideation → Plot → Screenplay

A single unified workspace for story development:
- **Logline/Concept** area (where you start)
- **Synopsis/Outline** area (expandable bullet points)
- **Screenplay** area (full screenplay with scene breakdown)

**AI Operations**:
- "Expand logline to synopsis"
- "Generate screenplay from synopsis"
- "Rewrite scene with notes"
- "Break screenplay into scenes"

### Phase 2: Production Design
**Combines**: Cast → Locations → Props → Art Direction

A visual reference board with three columns:
- **Characters**: Name, description, reference images, continuity sheets
- **Locations**: Name, description, reference images, mood board
- **Props/Costumes**: Name, description, reference images

**AI Operations**:
- "Generate character description from screenplay"
- "Generate character reference image"
- "Generate continuity contact sheet"
- "Generate location concept art"

### Phase 3: Shooting Script
**Combines**: Shooting Script → Cinematography → Shots

A structured editor that converts screenplay to production-ready shots:
- Scene-by-scene breakdown
- Shot cards with: framing, camera, characters, location, action, dialogue
- Drag-and-drop reordering
- JSON export for video generation

**AI Operations**:
- "Break scene into shots"
- "Suggest camera angles for scene"
- "Generate shot descriptions"

### Phase 4: Generation & Assembly
**Combines**: Shots → Asset Library → Review

A production queue and timeline:
- Shot queue with reference images attached
- Progress tracking for generation jobs
- Preview grid of generated assets
- Simple timeline for ordering shots

**AI Operations**:
- "Generate still for shot"
- "Generate video for shot"
- "Regenerate with different parameters"

---

## Technical Recommendations

### 1. Frontend Architecture for Future Swap

To prepare for swapping Streamlit for a more attractive frontend:

```
┌─────────────────────────────────────────────┐
│                  Frontend                    │
│  (Streamlit now → React/Vue/Svelte later)   │
├─────────────────────────────────────────────┤
│              REST API Layer                  │
│         (FastAPI - NEW ADDITION)            │
├─────────────────────────────────────────────┤
│             Backend Services                 │
│   db.py │ assets.py │ ai.py │ workflow.py   │
└─────────────────────────────────────────────┘
```

**Recommendation**: Add a thin FastAPI layer between the Streamlit frontend and backend services. This will:
- Enable easy frontend replacement
- Support multiple concurrent UIs (web, mobile, CLI)
- Enable async job processing for video generation

### 2. Workflow State Machine

Add a `workflow.py` module that manages project state:

```python
class ProjectWorkflow:
    """Manages project state and phase transitions."""
    
    PHASES = ["story", "design", "shooting", "generation"]
    
    def get_current_phase(self) -> str:
        """Determine current phase based on project data."""
        
    def can_advance_to(self, phase: str) -> tuple[bool, str]:
        """Check if project can advance to a phase."""
        
    def get_phase_completeness(self) -> dict:
        """Get completion percentage for each phase."""
```

### 3. Reference Image Linking

Enhance the asset system to support linked references:

```sql
-- Add reference linking table
CREATE TABLE reference_links (
    id INTEGER PRIMARY KEY,
    asset_id INTEGER REFERENCES assets(id),
    entity_type TEXT NOT NULL,  -- 'character', 'location', 'prop'
    entity_id INTEGER NOT NULL, -- block_id of the entity
    usage TEXT,                 -- 'primary', 'expression', 'costume_variation'
    UNIQUE(asset_id, entity_type, entity_id)
);
```

### 4. Shot Prompt Builder

Add a utility to construct optimal prompts for video generation:

```python
class ShotPromptBuilder:
    """Builds optimized prompts for video generation."""
    
    def build_prompt(self, shot: dict, references: dict) -> dict:
        """
        Build a prompt combining:
        - Shot technical details (framing, camera)
        - Character descriptions
        - Location mood
        - Art direction style
        """
```

### 5. Inexpensive Testing Mode

As per the issue, support cheap model testing:

```python
class AIOperations:
    def set_mode(self, mode: str):
        """
        'draft': Use cheap/free models, generate stills instead of video
        'final': Use best quality models, full video generation
        """
```

**Already implemented** in the current `ai.py` - just needs UI exposure.

---

## UI/UX Recommendations

### 1. Phase-Based Navigation

Replace 12 tabs with 4 phase tabs:
```
[ 📝 Story ] [ 🎨 Design ] [ 🎬 Shooting ] [ ⚡ Generate ]
```

Each phase shows:
- Progress indicator (e.g., "3/5 scenes complete")
- "Ready to advance" notification when phase is complete
- Quick summary of what's been created

### 2. Context Panel

Always-visible right panel showing:
- Current project summary
- Selected scene details
- Character/location quick reference
- Generation queue status

### 3. Smart Defaults

Pre-fill fields based on context:
- When adding a shot, default to the scene's location and characters
- When generating video, include relevant reference images automatically
- When creating character, extract description from screenplay

### 4. Batch Operations

Support for efficient batch work:
- "Generate all shots for scene"
- "Create reference images for all characters"
- "Export all shot prompts as JSON"

---

## Database Schema Updates

Minimal schema changes needed:

```sql
-- Add phase tracking to projects
ALTER TABLE projects ADD COLUMN current_phase TEXT DEFAULT 'story';
ALTER TABLE projects ADD COLUMN phase_data TEXT;  -- JSON for phase-specific state

-- Add reference linking (new table)
CREATE TABLE reference_links (
    id INTEGER PRIMARY KEY,
    asset_id INTEGER REFERENCES assets(id),
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    usage TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(asset_id, entity_type, entity_id)
);

-- Add shot ordering within scenes
ALTER TABLE blocks ADD COLUMN position INTEGER DEFAULT 0;
```

---

## Migration Path

### Phase 1: Immediate (This PR)
- [x] Document workflow analysis
- [ ] Update SPEC.md with new design direction

### Phase 2: Short-term
- Refactor tabs to 4 phases
- Add workflow state tracking
- Implement reference linking

### Phase 3: Medium-term
- Add FastAPI layer
- Implement ShotPromptBuilder
- Add batch operations

### Phase 4: Long-term
- Replace Streamlit with React/Vue frontend
- Add collaboration features
- Add video timeline assembly

---

## Testing Strategy (Cost-Efficient)

As noted in the issue, use inexpensive approaches:

1. **Draft Mode Default**: All generation starts in draft mode (cheap models)
2. **Stills Before Video**: Generate stills first, only upgrade to video when approved
3. **Mock Mode**: Built-in mock responses for UI testing without API calls
4. **Cached Results**: Hash-based asset deduplication prevents regenerating identical content

---

## Conclusion

The manual workflow document reveals a simpler, more natural process than the current 12-tab design. By consolidating to 4 phases that match user mental models, we can:

1. Reduce cognitive load
2. Enable easier automation
3. Prepare for frontend modernization
4. Support the iterative, cost-efficient development process the user wants

The key changes are organizational, not technical. The existing backend (`db.py`, `assets.py`, `ai.py`) is well-designed and can support this simplified workflow with minimal changes.
