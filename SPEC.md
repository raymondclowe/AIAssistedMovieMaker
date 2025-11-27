
Below is a **cleaned‑up, high‑level specification** for the “movie‑making‑assistant” you described, followed by a **practical architecture sketch** that you can start building on a single PC (or later expose as a web service).  
I’ve kept the language Python‑centric because you’re most comfortable there, but I also note where a JavaScript/Flutter/Node path would make sense.

---

## 1. What the app does – Core Concepts  

| Concept | What it represents | Key behaviours |
|--------|-------------------|----------------|
| **Project** | A container for everything that belongs to one movie (idea → final cut). | One‑file “project bundle” (ZIP/JSON) that can be exported/imported. |
| **Tab (Stage)** | Logical work‑area that matches a step in the pipeline (Ideation, Screenplay, Shooting Script, Cast, Locations, Props, Art‑Direction, Cinematography, Shots, Asset Library, Final Assemble). | Each tab owns its own data model, UI, and history. |
| **Block** | Smallest editable unit of text (scene description, dialogue line, note, tag). | Versioned, taggable, can be marked “keep / rewrite / love / hate”. |
| **Asset** | Binary blob (image, video clip, audio, 3‑D model, etc.) + metadata. | Stored on disk, referenced by hash, searchable by tags. |
| **AI‑Operation** | Call to an external model (LLM, image‑gen, video‑gen, audio‑gen). | Takes structured input (prompt + context) → produces new asset or new block. |
| **History / Versioning** | Immutable log of every change (text edit, asset replace, AI‑generation). | Allows “undo”, “compare”, “branch”, “re‑use old version”. |
| **Dependency Graph** | Links between objects (e.g., a shot depends on a screenplay block, a location, a character). | When a source changes, downstream objects are flagged for possible regeneration. |

---

## 2. User‑Facing Workflow (Tab order)

```
1️⃣ Ideation
2️⃣ Plot / Outline
3️⃣ Screenplay (blocks of scenes)
4️⃣ Shooting Script (screenplay + technical notes)
5️⃣ Cast & Characters
6️⃣ Locations
7️⃣ Props / Costumes
8️⃣ Art‑Direction
9️⃣ Cinematography
🔟 Shots (individual video‑generation units)
🅰️ Asset Library (generated / uploaded assets)
🅱️ Review & Assembly (timeline, transitions, final render)
```

*The order is *suggested* – users may jump between tabs; the system will keep everything in sync via the dependency graph.*

### Quick UI sketch per tab

| Tab | Main UI elements (think “pages” or “panels”) |
|-----|--------------------------------------------|
| **Ideation** | Free‑form rich‑text editor, optional image drop, tags (genre, tone). |
| **Plot** | Bullet‑list outline, drag‑reorder, “summary” field, auto‑generate from Ideation (LLM). |
| **Screenplay** | Word‑processor‑like view where each **Scene Block** is a collapsible card. Inside: scene heading, dialogue, **tags** (keep / rewrite / love / hate). Buttons: *Generate with AI*, *Create revision*, *History*. |
| **Shooting Script** | Same blocks but with extra columns: camera angle, movement, location, characters, props. Auto‑populate from Screenplay + selected Location/Props. |
| **Cast** | Card per character – photo (upload / AI‑generate), description, physical traits, voice notes, **asset list** (headshots, expression sheets). |
| **Locations** | Card per location – name, map/skyline image, mood board, tags, **asset list** (exterior, interior). |
| **Props / Costumes** | Grid of items – description, thumbnail, source (uploaded / AI). |
| **Art‑Direction** | Mood‑board editor (image tiles, style keywords, reference videos). |
| **Cinematography** | Table of “looks” – shot‑type, lens, lighting style, references. |
| **Shots** | Hierarchical view: Scene → Shot Cards. Each card shows: script line, camera spec, characters, location, **generated preview** (image or short video), notes, tags. Buttons: *Generate*, *Regenerate*, *Replace Asset*. |
| **Asset Library** | Searchable list of all binary blobs: hash, type, tags, size, generation parameters, linked objects. |
| **Review & Assembly** | Timeline view (like a simple NLE). Drag‑drop generated clips, add transitions, add subtitles/credits. Export button (render locally or send to cloud rendering service). |

---

## 3. Data Model (SQLite + JSON)

I recommend **SQLite** for the relational part (projects, blocks, assets, history) and **JSON** columns for flexible payloads (LLM prompts, generation parameters).  
All binary files live in a **project‑root folder** (e.g. `my‑movie/ assets/…`).  

### 3.1 Tables (simplified)

```sql
-- Projects ---------------------------------------------------------
CREATE TABLE projects (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    root_path   TEXT NOT NULL   -- where the asset folder lives
);

-- Tabs (just for ordering, optional)
CREATE TABLE tabs (
    id          INTEGER PRIMARY KEY,
    project_id  INTEGER REFERENCES projects(id),
    name        TEXT NOT NULL,
    position    INTEGER NOT NULL
);

-- Blocks – generic container for any text piece
CREATE TABLE blocks (
    id          INTEGER PRIMARY KEY,
    tab_id      INTEGER REFERENCES tabs(id),
    parent_id   INTEGER REFERENCES blocks(id),   -- for hierarchy (scene → paragraph)
    type        TEXT NOT NULL,   -- e.g. 'scene_heading', 'dialogue', 'note'
    content     TEXT,            -- plain text or markdown
    tags        TEXT,            -- CSV or JSON list
    version     INTEGER NOT NULL DEFAULT 1,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Asset metadata --------------------------------------------------
CREATE TABLE assets (
    id          INTEGER PRIMARY KEY,
    project_id  INTEGER REFERENCES projects(id),
    hash        TEXT NOT NULL UNIQUE,   -- SHA‑256 of the file
    path        TEXT NOT NULL,          -- relative to project root
    mime_type   TEXT NOT NULL,
    size_bytes  INTEGER,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    meta_json   TEXT                    -- arbitrary key/value (tags, prompt, model, etc.)
);

-- Block ↔ Asset linking (many‑to‑many)
CREATE TABLE block_assets (
    block_id INTEGER REFERENCES blocks(id),
    asset_id INTEGER REFERENCES assets(id),
    role     TEXT,                     -- e.g. 'preview', 'full_clip', 'reference'
    PRIMARY KEY (block_id, asset_id)
);

-- History – immutable log of every change
CREATE TABLE history (
    id          INTEGER PRIMARY KEY,
    block_id    INTEGER REFERENCES blocks(id),
    action      TEXT NOT NULL,         -- 'edit', 'ai_generate', 'tag_change', ...
    payload     TEXT,                  -- JSON snapshot of the change
    timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Dependency edges (for downstream invalidation)
CREATE TABLE dependencies (
    src_block_id INTEGER REFERENCES blocks(id),
    dst_block_id INTEGER REFERENCES blocks(id),
    type         TEXT,                 -- e.g. 'screenplay_to_shooting', 'shot_to_asset'
    PRIMARY KEY (src_block_id, dst_block_id)
);
```

### 3.2 Asset hashing & storage

```python
import hashlib, pathlib, shutil, sqlite3, json, datetime

def store_asset(project_root: pathlib.Path, src_file: pathlib.Path, meta: dict) -> int:
    # 1️⃣ read & hash
    data = src_file.read_bytes()
    h = hashlib.sha256(data).hexdigest()
    # 2️⃣ copy into assets folder if not already there
    dest = project_root / "assets" / f"{h}{src_file.suffix}"
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    # 3️⃣ insert metadata row
    con = sqlite3.connect(project_root / "project.db")
    cur = con.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO assets (project_id, hash, path, mime_type, size_bytes, meta_json) "
        "VALUES (1, ?, ?, ?, ?, ?)",
        (h, str(dest.relative_to(project_root)), mimetypes.guess_type(dest)[0],
         len(data), json.dumps(meta))
    )
    con.commit()
    return cur.lastrowid
```

*The `hash` column guarantees that identical files are stored only once.*

---

## 4. AI‑Operation Layer

| Operation | Model (example) | Input | Output | Where it lives |
|-----------|----------------|-------|--------|----------------|
| **LLM (text)** | OpenAI `gpt‑4o` / Anthropic `claude-3` | Prompt + context JSON (e.g. “Write a 2‑page screenplay from this plot”) | Text block (new version) | Backend service (Python function) |
| **Image generation** | Stability AI `sdxl`, DALL‑E 3, Midjourney API | Prompt + style tags | PNG/JPEG asset | Same backend, returns asset id |
| **Video generation** | RunwayML Gen‑2, Google `videocrafter`, or a custom `v2v` model | Prompt + optional start‑image + end‑image | MP4 (short clip) | Backend (may be async, use a job queue) |
| **Audio / Voice** | ElevenLabs TTS, RVC voice clone | Script line + voice profile | WAV/MP3 | Backend |
| **Metadata extraction** | CLIP, BLIP‑2, or Whisper (for speech) | Asset file | JSON description (objects, mood, etc.) | Post‑generation step to fill `meta_json` |

### 4.1 “Smart Re‑use” logic

When a generation request is made:

1. **Build a canonical description** (prompt + all tags).  
2. **Search** `assets.meta_json` for a record whose description *semantically* matches (use vector similarity via `sentence‑transformers`).  
3. If a *close* match (`cosine > 0.85`) exists, **offer** the existing asset instead of generating a new one.  
4. If the user forces generation, store the new asset **and** store the description for future matches.

---

## 5. Versioning & History

*Every edit* (text change, tag change, asset swap) creates a row in `history`.  
A simple **“undo”** walks backwards until it reaches the target version.  

For **branching** (e.g., “try a new ending”), you can clone a block tree:

```python
def branch_screenplay(block_id: int, new_name: str) -> int:
    # copy block and all its children, assign a new root block id
    # keep old versions untouched – they stay in history
```

---

## 6. Suggested Tech Stack (local‑first first)

| Layer | Option 1 – Python‑centric | Option 2 – Web/JS‑centric |
|-------|---------------------------|---------------------------|
| **UI** | • **PyQt6** or **Tkinter** (quick desktop UI) <br>• **Streamlit** (single‑file web UI that runs locally) <br>• **Tauri** (Rust+HTML, but you can embed a Python backend via an HTTP server) | • **React** + **Material‑UI** (or **Svelte**) served by a local Node/Express or FastAPI <br>• **Flutter Desktop** (single binary, nice UI) |
| **Backend** | • **FastAPI** (async, easy to expose as HTTP for the UI) <br>• **Flask** (simpler, sync) | • **Node.js + Express** (if you go full JS) |
| **Database** | **SQLite** (bundled, file‑based) | Same – SQLite works from Node too |
| **AI Calls** | Python wrappers (openai, anthropic, replicate, runpod) – easy to plug in. | Use fetch/axios from the front‑end to a small local server, or call directly from Node if the SDK exists. |
| **Job Queue** | **RQ** (Redis‑based) or simple `concurrent.futures.ThreadPoolExecutor` for async generation. | **BullMQ** (Node) or **Celery** (Python). |
| **Packaging** | • `pyinstaller` → single `.exe`/`.app` <br>• Docker (optional) | • `npx @electron-forge` if you want Electron <br>• `flutter build` for native installers |

**My personal recommendation** for a hobbyist who wants to iterate quickly:

1. **FastAPI** as a tiny local HTTP server (`localhost:8000`).  
2. **Streamlit** as the UI – you get a responsive, web‑styled UI without writing HTML/CSS/JS, and it runs in the browser but talks to the same Python process.  
3. **SQLite + folder** for assets.  
4. **RQ + Redis** for long‑running video generation jobs (or just fire‑and‑forget threads if you don’t need a queue yet).  

All of this can be bundled with **`pyinstaller --onefile`** into a double‑clickable program. Later you can expose the FastAPI server to the internet (via ngrok or a proper VPS) if you want a collaborative, cloud‑backed version.

---

## 7. File‑system layout (example)

```
my‑movie/
│
├─ project.db               ← SQLite DB
├─ assets/
│   ├─ 6f7a3c…1e.png        ← hashed image
│   ├─ a2b9f0…2c.mp4        ← hashed video clip
│   └─ …                    ← …
├─ exports/
│   └─ final_cut.mp4
└─ meta/
    └─ project.json         ← optional human‑readable summary
```

The **project JSON** can be a tiny snapshot that a user can version‑control (git) if they like:

```json
{
  "name": "Midnight Train",
  "created": "2025-11-27T13:45:00Z",
  "tabs": ["Ideation","Plot","Screenplay","ShootingScript","Cast","Locations","Props","ArtDirection","Cinematography","Shots","Review"],
  "asset_root": "assets/"
}
```

---

## 8. Sample Flow (pseudo‑code)

```python
# 1️⃣ User writes a logline in Ideation tab → saved as a Block
ideation_id = db.add_block(tab='Ideation', type='logline',
                           content="A detective must solve a murder on a moving train…")

# 2️⃣ User clicks “Generate Plot”
prompt = f"Write a 5‑act outline for a film based on:\n{ideation_block.content}"
outline_text = await llm_generate(prompt)

# store as Plot tab blocks (one per act)
for i, act in enumerate(parse_acts(outline_text), start=1):
    db.add_block(tab='Plot', type='act', content=act, parent_id=None)

# 3️⃣ Generate first scene screenplay via AI
scene_prompt = f"Write Scene 1 based on act 1:\n{act}"
scene_text = await llm_generate(scene_prompt)
scene_block_id = db.add_block(tab='Screenplay', type='scene',
                              content=scene_text)

# 4️⃣ Tag a paragraph “keep”
db.update_block(block_id=para_id, tags=['keep'])

# 5️⃣ User adds a character in Cast tab, uploads a headshot
char_id = db.add_block(tab='Cast', type='character',
                       content="Detective Jane Doe")
asset_id = store_asset(project_root, Path('photos/jane.png'), 
                       meta={'role':'headshot','character':char_id})

db.link_block_asset(block_id=char_id, asset_id=asset_id, role='headshot')

# 6️⃣ Create Shot cards from Shooting Script
for shot in parse_shots(shooting_script_text):
    shot_id = db.add_block(tab='Shots', type='shot', content=shot.description)
    # auto‑link location, characters, props based on tags
    db.add_dependency(src_block_id=scene_block_id, dst_block_id=shot_id,
                      type='scene_to_shot')
```

All of the above can be wrapped in **service functions** that the UI calls via HTTP (`/api/block/add`, `/api/ai/generate`, `/api/asset/upload`, …).

---

## 9. Handling “Down‑stream Changes”

When a source block changes (e.g., you edit a character’s hat), run:

```python
def invalidate_downstream(src_block_id):
    # Find all dependent blocks
    deps = db.query("SELECT dst_block_id FROM dependencies WHERE src_block_id=?", (src_block_id,))
    for (dst_id,) in deps:
        db.update_block(dst_id, tags=append_tag(db.get_block(dst_id).tags, 'needs_regen'))
```

The UI can then highlight those blocks with a red badge (“Regenerate”).  
A single click on the badge runs the appropriate AI generation with **both the old and new versions** as context, so the model can preserve unchanged parts.

---

## 10. Road‑map (MVP → Full)

| Sprint | Goal | Rough effort |
|--------|------|--------------|
| **0 – Setup** | Project skeleton (FastAPI + Streamlit) + SQLite init + asset hash store. | 1–2 days |
| **1 – Ideation → Screenplay** | UI for first three tabs, LLM integration, block‑versioning. | 3–5 days |
| **2 – Shooting Script + Dependency** | Add extra fields (camera, location), auto‑link to Cast/Locations, dependency graph. | 4–6 days |
| **3 – Asset Library** | Upload, AI‑image generation, hash‑lookup, tagging UI. | 4 days |
| **4 – Shots & Video Generation** | Shot cards UI, call to a video‑gen API, store preview clips, “Regenerate” flow. | 5–7 days (depends on API latency) |
| **5 – Review / Timeline** | Simple draggable timeline (use `streamlit-drag-select` or a small React component) + export to MP4 (ffmpeg concat). | 5 days |
| **6 – History & Branching** | Full undo/redo, view history, branch screenplay. | 3–4 days |
| **7 – Smart Re‑use & Similarity Search** | Vector index (FAISS) for asset description, auto‑suggest reuse. | 4 days |
| **8 – Polishing & Packaging** | PyInstaller bundle, settings screen, documentation. | 3 days |
| **Optional** | Collaboration server (multi‑user, auth), Docker deployment, Flutter front‑end. | – |

---

## 11. Next Steps for You

1. **Create a repo** (even a private one) and scaffold the folder layout described in §7.  
2. **Pick a UI framework** – I suggest starting with **Streamlit** because you can get a functional UI in a few lines:

   ```python
   import streamlit as st
   from backend import db, ai, assets

   st.title("Movie Builder – Ideation")
   logline = st.text_area("Logline", height=150)
   if st.button("Generate Plot"):
       outline = ai.llm_generate(f"Outline a 5‑act structure for: {logline}")
       st.success("Plot generated!")
       db.save_block(tab='Plot', type='outline', content=outline)
   ```

3. **Implement the SQLite schema** (run the SQL in a small script).  
4. **Write thin wrapper functions** for “add block”, “update block”, “link asset”, “add dependency”.  
5. **Integrate one LLM call** (OpenAI’s `gpt-4o` is easiest – just set `OPENAI_API_KEY`).  
6. **Test the asset‑hash pipeline** – drop a picture, see it appear under `assets/` with a hash‑named file.  
7. **Iterate** – add the next tab once the previous one feels solid.

---

## 12. Final Thoughts

* The system you described is essentially a **directed‑acyclic graph of content objects** with versioned text nodes and binary leaves.  
* By **centralising everything in SQLite** and using **hash‑addressed files**, you keep the project portable and easy to back up.  
* **AI calls** are the only external, potentially expensive part – the “smart reuse” cache will save you a lot of money and keep the UI snappy.  
* Starting with a **local‑first Python + Streamlit** stack gives you the fastest feedback loop. When you’re ready to go public or add real‑time collaboration, you can lift the same FastAPI backend into a Docker container and replace Streamlit with a richer React/Flutter UI.

Feel free to ask for concrete code snippets for any of the layers (e.g., a FastAPI endpoint that queues a video‑generation job, or a Streamlit component that renders a block‑history timeline). I’m happy to dive deeper into whatever part you want to prototype first!
