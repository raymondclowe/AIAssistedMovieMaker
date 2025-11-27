"""AI-Assisted Movie Maker - Main Streamlit Application.

This is the main entry point for the Streamlit UI.
Run with: streamlit run app.py

Implements a simplified 4-phase workflow:
1. Story - Ideation, Plot, Screenplay
2. Design - Characters, Locations, Props, Art Direction
3. Shooting - Shooting Script, Cinematography, Shot Cards
4. Generate - Asset Generation, Library, Review
"""

import streamlit as st
from pathlib import Path
import json
from typing import Optional

from backend.db import Database
from backend.assets import AssetManager
from backend.ai import AIOperations

# Page configuration
st.set_page_config(
    page_title="AI Movie Maker",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Define the 4-phase workflow
PHASES = [
    ("📝 Story", "story"),
    ("🎨 Design", "design"),
    ("🎬 Shooting", "shooting"),
    ("⚡ Generate", "generate")
]


def init_session_state():
    """Initialize session state variables."""
    if "project_id" not in st.session_state:
        st.session_state.project_id = None
    if "project_root" not in st.session_state:
        st.session_state.project_root = None
    if "db" not in st.session_state:
        st.session_state.db = None
    if "asset_manager" not in st.session_state:
        st.session_state.asset_manager = None
    if "ai" not in st.session_state:
        st.session_state.ai = AIOperations()
    if "ai_mode" not in st.session_state:
        st.session_state.ai_mode = "draft"
    if "selected_llm_model" not in st.session_state:
        st.session_state.selected_llm_model = None
    if "selected_image_model" not in st.session_state:
        st.session_state.selected_image_model = None
    if "selected_video_model" not in st.session_state:
        st.session_state.selected_video_model = None
    # API keys entered via UI
    if "openrouter_key_input" not in st.session_state:
        st.session_state.openrouter_key_input = ""
    if "replicate_key_input" not in st.session_state:
        st.session_state.replicate_key_input = ""


def get_or_create_default_project():
    """Get or create the default project."""
    default_project_dir = Path("./movie_project")
    default_project_dir.mkdir(parents=True, exist_ok=True)

    db_path = default_project_dir / "project.db"
    db = Database(db_path)

    # Check if default project exists
    projects = db.get_all_projects()
    if not projects:
        # Create default project
        project_id = db.create_project("My Movie", str(default_project_dir))
        # Create tabs for data storage (internal, not shown as UI tabs)
        tab_names = ["Story", "Design", "Shooting", "Generate"]
        for i, tab_name in enumerate(tab_names):
            db.create_tab(project_id, tab_name, i)
    else:
        project_id = projects[0]["id"]

    return db, project_id, default_project_dir


def render_sidebar():
    """Render the sidebar with project info, settings, and API key inputs."""
    with st.sidebar:
        st.title("🎬 AI Movie Maker")
        st.markdown("---")

        # Project info
        if st.session_state.project_id:
            project = st.session_state.db.get_project(st.session_state.project_id)
            st.subheader(f"📁 {project['name']}")
            st.caption(f"Created: {project['created_at']}")

        st.markdown("---")

        # API Keys Section - for non-tech users
        with st.expander("🔑 API Keys", expanded=not st.session_state.ai.is_configured()):
            st.markdown("Enter your API keys below, or set them as environment variables.")
            
            status = st.session_state.ai.get_status()
            
            # OpenRouter Key
            openrouter_status = "✅ Connected" if status["openrouter"] else "❌ Not configured"
            st.caption(f"OpenRouter: {openrouter_status}")
            openrouter_key = st.text_input(
                "OpenRouter API Key",
                type="password",
                value=st.session_state.openrouter_key_input,
                placeholder="sk-or-...",
                help="Get your key at https://openrouter.ai/keys"
            )
            if openrouter_key and openrouter_key != st.session_state.openrouter_key_input:
                st.session_state.openrouter_key_input = openrouter_key
                st.session_state.ai.set_openrouter_key(openrouter_key)
                st.rerun()
            
            # Replicate Key
            replicate_status = "✅ Connected" if status["replicate"] else "❌ Not configured"
            st.caption(f"Replicate: {replicate_status}")
            replicate_key = st.text_input(
                "Replicate API Key",
                type="password",
                value=st.session_state.replicate_key_input,
                placeholder="r8_...",
                help="Get your key at https://replicate.com/account/api-tokens"
            )
            if replicate_key and replicate_key != st.session_state.replicate_key_input:
                st.session_state.replicate_key_input = replicate_key
                st.session_state.ai.set_replicate_key(replicate_key)
                st.rerun()
            
            st.markdown("---")
            st.caption("💡 Keys are stored in session only, not saved to disk.")

        st.markdown("---")

        # AI Provider Status
        st.subheader("🤖 AI Status")
        status = st.session_state.ai.get_status()
        
        col1, col2 = st.columns(2)
        with col1:
            if status["openrouter"]:
                st.success("✅ Text AI")
            else:
                st.error("❌ Text AI")
        with col2:
            if status["replicate"]:
                st.success("✅ Image AI")
            else:
                st.error("❌ Image AI")
        
        # Mode selection
        mode = st.radio(
            "Generation Mode",
            options=["draft", "final"],
            index=0 if st.session_state.ai_mode == "draft" else 1,
            help="Draft: Fast & cheap models. Final: Best quality models.",
            horizontal=True
        )
        if mode != st.session_state.ai_mode:
            st.session_state.ai_mode = mode
            st.session_state.ai.set_mode(mode)
            # Reset model selections when mode changes
            st.session_state.selected_llm_model = None
            st.session_state.selected_image_model = None
            st.session_state.selected_video_model = None
        
        # Model selection expander
        with st.expander("🔧 Model Selection", expanded=False):
            # LLM Model
            if status["openrouter"]:
                llm_models = st.session_state.ai.get_available_llm_models()
                mode_llm_models = llm_models.get(st.session_state.ai_mode, [])
                if mode_llm_models:
                    llm_options = [m["id"] for m in mode_llm_models[:20]]
                    current_llm = st.session_state.selected_llm_model
                    if current_llm not in llm_options:
                        current_llm = llm_options[0] if llm_options else None
                    
                    selected_llm = st.selectbox(
                        "LLM Model",
                        options=llm_options,
                        index=llm_options.index(current_llm) if current_llm in llm_options else 0,
                        help="Model for text generation"
                    )
                    if selected_llm != st.session_state.selected_llm_model:
                        st.session_state.selected_llm_model = selected_llm
                        st.session_state.ai.set_llm_model(selected_llm)
            
            # Image Model
            if status["replicate"]:
                image_models = st.session_state.ai.get_available_image_models()
                mode_image_models = image_models.get(st.session_state.ai_mode, [])
                if mode_image_models:
                    image_options = [m["id"] for m in mode_image_models[:10]]
                    current_image = st.session_state.selected_image_model
                    if current_image not in image_options:
                        current_image = image_options[0] if image_options else None
                    
                    selected_image = st.selectbox(
                        "Image Model",
                        options=image_options,
                        index=image_options.index(current_image) if current_image in image_options else 0,
                        help="Model for image generation"
                    )
                    if selected_image != st.session_state.selected_image_model:
                        st.session_state.selected_image_model = selected_image
                        st.session_state.ai.set_image_model(selected_image)
                
                # Video Model
                video_models = st.session_state.ai.get_available_video_models()
                mode_video_models = video_models.get(st.session_state.ai_mode, [])
                if mode_video_models:
                    video_options = [m["id"] for m in mode_video_models[:10]]
                    current_video = st.session_state.selected_video_model
                    if current_video not in video_options:
                        current_video = video_options[0] if video_options else None
                    
                    selected_video = st.selectbox(
                        "Video Model",
                        options=video_options,
                        index=video_options.index(current_video) if current_video in video_options else 0,
                        help="Model for video generation"
                    )
                    if selected_video != st.session_state.selected_video_model:
                        st.session_state.selected_video_model = selected_video
                        st.session_state.ai.set_video_model(selected_video)

        st.markdown("---")

        # Help section
        with st.expander("ℹ️ Help"):
            st.markdown("""
            **Quick Start:**
            1. Enter your API keys above (or set as environment variables)
            2. Start in **📝 Story** - write your movie concept
            3. Move to **🎨 Design** - define characters & locations
            4. Create **🎬 Shooting** script with shot cards
            5. **⚡ Generate** images and videos for each shot
            
            **Generation Modes:**
            - **Draft**: Fast, cheap models for iteration
            - **Final**: Best quality models for production
            
            **Tips:**
            - Use Draft mode while developing your story
            - Generate stills first to save costs
            - Switch to Final mode for your best shots
            """)


def get_tab_by_name(name: str) -> Optional[dict]:
    """Get tab by name."""
    tabs = st.session_state.db.get_tabs(st.session_state.project_id)
    for tab in tabs:
        if tab["name"] == name:
            return tab
    return None


# =============================================================================
# PHASE 1: STORY
# =============================================================================

def render_story_phase():
    """Render the Story phase - combines Ideation, Plot, and Screenplay."""
    st.header("📝 Story Development")
    st.markdown("Develop your movie from concept to complete screenplay.")
    
    # Get or create Story tab
    tab = get_tab_by_name("Story")
    if not tab:
        # Create it if it doesn't exist (for existing projects)
        tab_id = st.session_state.db.create_tab(st.session_state.project_id, "Story", 0)
        tab = {"id": tab_id, "name": "Story"}
    
    tab_id = tab["id"]
    
    # Create subtabs within Story
    story_tabs = st.tabs(["💡 Concept", "📊 Plot", "📜 Screenplay"])
    
    # Concept subtab
    with story_tabs[0]:
        render_concept_section(tab_id)
    
    # Plot subtab
    with story_tabs[1]:
        render_plot_section(tab_id)
    
    # Screenplay subtab
    with story_tabs[2]:
        render_screenplay_section(tab_id)


def render_concept_section(tab_id: int):
    """Render the Concept section."""
    st.subheader("💡 Movie Concept")
    st.markdown("Start with your core movie idea - a logline or concept.")
    
    # Get existing concept blocks
    blocks = st.session_state.db.get_blocks_by_tab(tab_id)
    concepts = [b for b in blocks if b["type"] in ("logline", "concept")]
    
    # Input for new concept
    with st.form("new_concept"):
        content = st.text_area(
            "Your Movie Idea",
            height=150,
            placeholder="A detective must solve a murder on a moving train before it reaches its destination..."
        )
        col1, col2 = st.columns([1, 4])
        with col1:
            submit = st.form_submit_button("💾 Save", use_container_width=True)
        with col2:
            generate = st.form_submit_button("✨ Expand with AI", use_container_width=True)

        if submit and content:
            st.session_state.db.add_block(tab_id, "logline", content)
            st.success("Concept saved!")
            st.rerun()

        if generate and content:
            with st.spinner("Generating expanded concept..."):
                prompt = f"Expand this movie concept into a detailed premise with genre, tone, themes, and potential story hooks:\n\n{content}"
                expanded = st.session_state.ai.llm_generate_sync(prompt)
                st.session_state.db.add_block(tab_id, "concept", expanded)
                st.success("Concept expanded!")
                st.rerun()

    # Display existing concepts
    if concepts:
        st.markdown("---")
        st.subheader("📝 Saved Concepts")
        for block in concepts:
            with st.expander(f"{block['type'].title()}: {block['content'][:60]}...", expanded=len(concepts) == 1):
                st.markdown(block["content"])
                col1, col2 = st.columns([1, 5])
                with col1:
                    if st.button("🗑️ Delete", key=f"del_concept_{block['id']}"):
                        st.session_state.db.delete_block(block["id"])
                        st.rerun()


def render_plot_section(tab_id: int):
    """Render the Plot section."""
    st.subheader("📊 Plot Structure")
    st.markdown("Create your story structure - generate from concept or write manually.")
    
    # Get blocks
    blocks = st.session_state.db.get_blocks_by_tab(tab_id)
    concepts = [b for b in blocks if b["type"] in ("logline", "concept")]
    plots = [b for b in blocks if b["type"] in ("outline", "act", "beat")]
    
    # Generate from concept
    if concepts:
        st.markdown("**Generate from Concept:**")
        source_block = st.selectbox(
            "Select source concept:",
            options=concepts,
            format_func=lambda x: f"{x['content'][:60]}..."
        )
        if st.button("✨ Generate Plot Outline"):
            with st.spinner("Generating plot outline..."):
                prompt = f"Write a detailed 5-act plot outline for a movie based on this concept:\n\n{source_block['content']}"
                outline = st.session_state.ai.llm_generate_sync(prompt)
                block_id = st.session_state.db.add_block(tab_id, "outline", outline)
                st.session_state.db.add_dependency(source_block["id"], block_id, "concept_to_plot")
                st.success("Plot outline generated!")
                st.rerun()
    
    st.markdown("---")
    
    # Manual input
    with st.form("new_plot_point"):
        content = st.text_area(
            "Write Plot Point",
            height=100,
            placeholder="Act 1: Setup - Introduce the detective boarding the train..."
        )
        plot_type = st.selectbox("Type", ["act", "beat", "outline"])
        if st.form_submit_button("💾 Add Plot Point"):
            if content:
                st.session_state.db.add_block(tab_id, plot_type, content)
                st.success("Plot point added!")
                st.rerun()
    
    # Display existing plots
    if plots:
        st.markdown("---")
        st.subheader("📑 Plot Structure")
        for block in plots:
            with st.expander(f"{block['type'].upper()}: {block['content'][:60]}...", expanded=True):
                st.markdown(block["content"])
                if st.button("🗑️ Delete", key=f"del_plot_{block['id']}"):
                    st.session_state.db.delete_block(block["id"])
                    st.rerun()


def render_screenplay_section(tab_id: int):
    """Render the Screenplay section."""
    st.subheader("📜 Screenplay")
    st.markdown("Write your scenes with dialogue, action, and descriptions.")
    
    # Get blocks
    blocks = st.session_state.db.get_blocks_by_tab(tab_id)
    plots = [b for b in blocks if b["type"] in ("outline", "act", "beat")]
    scenes = [b for b in blocks if b["type"] == "scene"]
    
    # Generate from plot
    if plots:
        st.markdown("**Generate Scene from Plot:**")
        source_block = st.selectbox(
            "Select plot point:",
            options=plots,
            format_func=lambda x: f"{x['type'].upper()}: {x['content'][:50]}..."
        )
        if st.button("✨ Generate Scene"):
            with st.spinner("Generating screenplay scene..."):
                prompt = f"""Write a screenplay scene based on this plot point.
Use proper screenplay format with scene headings (INT./EXT.), 
character names in caps, dialogue, and action descriptions.

Plot point:
{source_block['content']}"""
                scene = st.session_state.ai.llm_generate_sync(prompt)
                block_id = st.session_state.db.add_block(tab_id, "scene", scene)
                st.session_state.db.add_dependency(source_block["id"], block_id, "plot_to_scene")
                st.success("Scene generated!")
                st.rerun()
    
    st.markdown("---")
    
    # Manual scene input
    with st.form("new_scene"):
        scene_heading = st.text_input("Scene Heading", placeholder="INT. TRAIN DINING CAR - NIGHT")
        content = st.text_area(
            "Scene Content",
            height=200,
            placeholder="The DETECTIVE enters the crowded dining car..."
        )
        if st.form_submit_button("💾 Add Scene"):
            if scene_heading or content:
                full_content = f"{scene_heading}\n\n{content}" if scene_heading else content
                st.session_state.db.add_block(tab_id, "scene", full_content)
                st.success("Scene added!")
                st.rerun()
    
    # Display scenes
    if scenes:
        st.markdown("---")
        st.subheader("📑 Scenes")
        for i, block in enumerate(scenes, 1):
            with st.expander(f"Scene {i}: {block['content'][:50]}...", expanded=False):
                st.text(block["content"])
                col1, col2 = st.columns([1, 5])
                with col1:
                    if st.button("🗑️ Delete", key=f"del_scene_{block['id']}"):
                        st.session_state.db.delete_block(block["id"])
                        st.rerun()


# =============================================================================
# PHASE 2: DESIGN
# =============================================================================

def render_design_phase():
    """Render the Design phase - Characters, Locations, Props, Art Direction."""
    st.header("🎨 Production Design")
    st.markdown("Define the visual elements of your movie - characters, locations, props, and style.")
    
    # Get or create Design tab
    tab = get_tab_by_name("Design")
    if not tab:
        tab_id = st.session_state.db.create_tab(st.session_state.project_id, "Design", 1)
        tab = {"id": tab_id, "name": "Design"}
    
    tab_id = tab["id"]
    
    # Create subtabs
    design_tabs = st.tabs(["👥 Characters", "📍 Locations", "🎭 Props", "🎨 Style"])
    
    with design_tabs[0]:
        render_characters_section(tab_id)
    
    with design_tabs[1]:
        render_locations_section(tab_id)
    
    with design_tabs[2]:
        render_props_section(tab_id)
    
    with design_tabs[3]:
        render_style_section(tab_id)


def render_characters_section(tab_id: int):
    """Render the Characters section."""
    st.subheader("👥 Characters")
    st.markdown("Define your characters with descriptions and reference images.")
    
    # Get existing characters
    blocks = st.session_state.db.get_blocks_by_tab(tab_id)
    characters = [b for b in blocks if b["type"] == "character"]
    
    # Add new character
    with st.form("new_character"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Character Name", placeholder="Detective Jane Doe")
        with col2:
            role = st.selectbox("Role", ["Lead", "Supporting", "Minor", "Background"])
        
        description = st.text_area(
            "Description",
            height=100,
            placeholder="Age, appearance, personality, background..."
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("💾 Save Character"):
                if name:
                    content = f"# {name}\n**Role:** {role}\n\n{description}"
                    st.session_state.db.add_block(tab_id, "character", content)
                    st.success("Character added!")
                    st.rerun()
        with col2:
            if st.form_submit_button("✨ Generate Character"):
                if name:
                    with st.spinner("Generating character..."):
                        prompt = f"Create a detailed character profile for a movie character named {name} ({role}). Include physical description, personality, background, and motivation."
                        if description:
                            prompt += f"\n\nAdditional context: {description}"
                        generated = st.session_state.ai.llm_generate_sync(prompt)
                        st.session_state.db.add_block(tab_id, "character", generated)
                        st.success("Character generated!")
                        st.rerun()
    
    # Display characters
    if characters:
        st.markdown("---")
        cols = st.columns(2)
        for i, block in enumerate(characters):
            with cols[i % 2]:
                with st.container(border=True):
                    st.markdown(block["content"])
                    if st.button("🗑️ Delete", key=f"del_char_{block['id']}"):
                        st.session_state.db.delete_block(block["id"])
                        st.rerun()


def render_locations_section(tab_id: int):
    """Render the Locations section."""
    st.subheader("📍 Locations")
    st.markdown("Define the settings and locations for your movie.")
    
    blocks = st.session_state.db.get_blocks_by_tab(tab_id)
    locations = [b for b in blocks if b["type"] == "location"]
    
    with st.form("new_location"):
        name = st.text_input("Location Name", placeholder="Train Dining Car")
        description = st.text_area(
            "Description",
            height=100,
            placeholder="Visual details, atmosphere, mood..."
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("💾 Save Location"):
                if name:
                    content = f"# {name}\n\n{description}"
                    st.session_state.db.add_block(tab_id, "location", content)
                    st.success("Location added!")
                    st.rerun()
        with col2:
            if st.form_submit_button("✨ Generate Location"):
                if name:
                    with st.spinner("Generating location..."):
                        prompt = f"Create a detailed location description for a movie setting: {name}. Include visual details, atmosphere, mood, and key areas."
                        if description:
                            prompt += f"\n\nAdditional context: {description}"
                        generated = st.session_state.ai.llm_generate_sync(prompt)
                        st.session_state.db.add_block(tab_id, "location", generated)
                        st.success("Location generated!")
                        st.rerun()
    
    if locations:
        st.markdown("---")
        for block in locations:
            with st.expander(block["content"].split('\n')[0], expanded=False):
                st.markdown(block["content"])
                if st.button("🗑️ Delete", key=f"del_loc_{block['id']}"):
                    st.session_state.db.delete_block(block["id"])
                    st.rerun()


def render_props_section(tab_id: int):
    """Render the Props section."""
    st.subheader("🎭 Props & Costumes")
    st.markdown("Track props, costumes, and other physical items.")
    
    blocks = st.session_state.db.get_blocks_by_tab(tab_id)
    props = [b for b in blocks if b["type"] in ("prop", "costume", "vehicle")]
    
    with st.form("new_prop"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Item Name", placeholder="Poison Wine Glass")
            item_type = st.selectbox("Type", ["prop", "costume", "vehicle"])
        with col2:
            description = st.text_area("Description", placeholder="Description and visual details...")

        if st.form_submit_button("💾 Save Item"):
            if name:
                content = f"**{name}** ({item_type})\n\n{description}"
                st.session_state.db.add_block(tab_id, item_type, content)
                st.success("Item added!")
                st.rerun()
    
    if props:
        st.markdown("---")
        cols = st.columns(3)
        for i, block in enumerate(props):
            with cols[i % 3]:
                with st.container(border=True):
                    st.markdown(block["content"])
                    if st.button("🗑️", key=f"del_prop_{block['id']}"):
                        st.session_state.db.delete_block(block["id"])
                        st.rerun()


def render_style_section(tab_id: int):
    """Render the Art Direction / Style section."""
    st.subheader("🎨 Visual Style")
    st.markdown("Define the visual style and art direction for your movie.")
    
    blocks = st.session_state.db.get_blocks_by_tab(tab_id)
    styles = [b for b in blocks if b["type"] in ("style_guide", "color_palette", "mood", "visual_theme")]
    
    with st.form("new_style"):
        element_type = st.selectbox("Element Type", ["style_guide", "color_palette", "mood", "visual_theme"])
        content = st.text_area(
            "Description",
            height=100,
            placeholder="Describe the visual style element..."
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("💾 Save"):
                if content:
                    st.session_state.db.add_block(tab_id, element_type, content)
                    st.success("Style element added!")
                    st.rerun()
        with col2:
            if st.form_submit_button("✨ Generate Style Guide"):
                if content:
                    with st.spinner("Generating style guide..."):
                        prompt = f"Create a detailed art direction guide for a movie with this style: {content}. Include color palette, lighting, textures, and visual references."
                        generated = st.session_state.ai.llm_generate_sync(prompt)
                        st.session_state.db.add_block(tab_id, "style_guide", generated)
                        st.success("Style guide generated!")
                        st.rerun()
    
    if styles:
        st.markdown("---")
        for block in styles:
            with st.expander(f"{block['type'].replace('_', ' ').title()}", expanded=False):
                st.markdown(block["content"])
                if st.button("🗑️ Delete", key=f"del_style_{block['id']}"):
                    st.session_state.db.delete_block(block["id"])
                    st.rerun()


# =============================================================================
# PHASE 3: SHOOTING
# =============================================================================

def render_shooting_phase():
    """Render the Shooting phase - Shooting Script, Cinematography, Shots."""
    st.header("🎬 Shooting Script")
    st.markdown("Break down your screenplay into production-ready shots.")
    
    # Get or create Shooting tab
    tab = get_tab_by_name("Shooting")
    if not tab:
        tab_id = st.session_state.db.create_tab(st.session_state.project_id, "Shooting", 2)
        tab = {"id": tab_id, "name": "Shooting"}
    
    tab_id = tab["id"]
    
    # Create subtabs
    shooting_tabs = st.tabs(["📋 Shot List", "🎥 Cinematography", "📝 Shot Cards"])
    
    with shooting_tabs[0]:
        render_shot_list_section(tab_id)
    
    with shooting_tabs[1]:
        render_cinematography_section(tab_id)
    
    with shooting_tabs[2]:
        render_shot_cards_section(tab_id)


def render_shot_list_section(tab_id: int):
    """Render the Shot List section."""
    st.subheader("📋 Shot List")
    st.markdown("Create a list of shots from your screenplay scenes.")
    
    # Get screenplay scenes
    story_tab = get_tab_by_name("Story")
    story_blocks = st.session_state.db.get_blocks_by_tab(story_tab["id"]) if story_tab else []
    scenes = [b for b in story_blocks if b["type"] == "scene"]
    
    if scenes:
        st.markdown("**Generate Shots from Scene:**")
        source_scene = st.selectbox(
            "Select scene:",
            options=scenes,
            format_func=lambda x: f"{x['content'][:60]}..."
        )
        if st.button("✨ Generate Shot Breakdown"):
            with st.spinner("Breaking down scene into shots..."):
                prompt = f"""Break down this screenplay scene into a list of individual shots.
For each shot, provide:
- Shot number
- Shot type (wide, medium, close-up, etc.)
- Subject/framing
- Camera movement (if any)
- Brief action description

Scene:
{source_scene['content']}"""
                shots = st.session_state.ai.llm_generate_sync(prompt)
                block_id = st.session_state.db.add_block(tab_id, "shot_breakdown", shots)
                st.session_state.db.add_dependency(source_scene["id"], block_id, "scene_to_shots")
                st.success("Shot breakdown generated!")
                st.rerun()
    else:
        st.info("Add scenes in the Story phase first.")
    
    # Display shot breakdowns
    blocks = st.session_state.db.get_blocks_by_tab(tab_id)
    breakdowns = [b for b in blocks if b["type"] == "shot_breakdown"]
    
    if breakdowns:
        st.markdown("---")
        st.subheader("Shot Breakdowns")
        for i, block in enumerate(breakdowns, 1):
            with st.expander(f"Breakdown {i}", expanded=True):
                st.markdown(block["content"])
                if st.button("🗑️ Delete", key=f"del_breakdown_{block['id']}"):
                    st.session_state.db.delete_block(block["id"])
                    st.rerun()


def render_cinematography_section(tab_id: int):
    """Render the Cinematography section."""
    st.subheader("🎥 Cinematography")
    st.markdown("Define camera work, lighting, and visual techniques.")
    
    blocks = st.session_state.db.get_blocks_by_tab(tab_id)
    cine_notes = [b for b in blocks if b["type"] == "cinematography"]
    
    with st.form("new_cine"):
        col1, col2 = st.columns(2)
        with col1:
            shot_type = st.selectbox("Shot Type", [
                "establishing", "wide", "medium", "close-up", "extreme close-up",
                "over-the-shoulder", "POV", "tracking", "crane", "handheld"
            ])
            lens = st.text_input("Lens", placeholder="35mm, anamorphic")
        with col2:
            lighting = st.text_input("Lighting", placeholder="Low-key, dramatic shadows")
            movement = st.text_input("Movement", placeholder="Slow dolly, static")

        notes = st.text_area("Notes", placeholder="Additional cinematography notes...")

        if st.form_submit_button("💾 Save"):
            content = f"""**Shot Type:** {shot_type}
**Lens:** {lens}
**Lighting:** {lighting}
**Movement:** {movement}

{notes}"""
            st.session_state.db.add_block(tab_id, "cinematography", content)
            st.success("Cinematography note added!")
            st.rerun()
    
    if cine_notes:
        st.markdown("---")
        for block in cine_notes:
            with st.expander(f"Shot: {block['content'][:40]}...", expanded=False):
                st.markdown(block["content"])
                if st.button("🗑️ Delete", key=f"del_cine_{block['id']}"):
                    st.session_state.db.delete_block(block["id"])
                    st.rerun()


def render_shot_cards_section(tab_id: int):
    """Render the Shot Cards section."""
    st.subheader("📝 Shot Cards")
    st.markdown("Create detailed shot cards for video generation.")
    
    blocks = st.session_state.db.get_blocks_by_tab(tab_id)
    shots = [b for b in blocks if b["type"] == "shot"]
    
    with st.form("new_shot"):
        description = st.text_area(
            "Shot Description",
            height=80,
            placeholder="Wide shot of train entering tunnel, steam billowing..."
        )

        col1, col2, col3 = st.columns(3)
        with col1:
            shot_type = st.selectbox("Shot Type", ["wide", "medium", "close-up", "POV", "tracking"])
        with col2:
            duration = st.number_input("Duration (seconds)", min_value=1, max_value=60, value=5)
        with col3:
            characters = st.text_input("Characters", placeholder="Detective")

        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("💾 Save Shot"):
                if description:
                    content = f"""**Shot Type:** {shot_type}
**Duration:** {duration}s
**Characters:** {characters}

{description}"""
                    st.session_state.db.add_block(tab_id, "shot", content)
                    st.success("Shot added!")
                    st.rerun()
        with col2:
            if st.form_submit_button("✨ Generate Shot Description"):
                if description:
                    with st.spinner("Generating shot description..."):
                        prompt = f"Create a detailed shot description for video generation: {description}. Include visual composition, camera angle, lighting, mood, and any motion."
                        generated = st.session_state.ai.llm_generate_sync(prompt)
                        st.session_state.db.add_block(tab_id, "shot", generated)
                        st.success("Shot description generated!")
                        st.rerun()
    
    if shots:
        st.markdown("---")
        st.subheader("🎬 Shot List")
        for i, block in enumerate(shots, 1):
            with st.expander(f"Shot {i}: {block['content'][:50]}...", expanded=False):
                st.markdown(block["content"])
                if st.button("🗑️ Delete", key=f"del_shot_{block['id']}"):
                    st.session_state.db.delete_block(block["id"])
                    st.rerun()


# =============================================================================
# PHASE 4: GENERATE
# =============================================================================

def render_generate_phase():
    """Render the Generate phase - Asset Generation, Library, Review."""
    st.header("⚡ Generate & Review")
    st.markdown("Generate images and videos for your shots, manage assets, and review your project.")
    
    # Get or create Generate tab
    tab = get_tab_by_name("Generate")
    if not tab:
        tab_id = st.session_state.db.create_tab(st.session_state.project_id, "Generate", 3)
    
    # Create subtabs
    gen_tabs = st.tabs(["🖼️ Generate", "📁 Assets", "📊 Review"])
    
    with gen_tabs[0]:
        render_generation_section()
    
    with gen_tabs[1]:
        render_assets_section()
    
    with gen_tabs[2]:
        render_review_section()


def render_generation_section():
    """Render the Generation section."""
    st.subheader("🖼️ Generate Assets")
    st.markdown("Generate images and videos from your shot descriptions.")
    
    # Get shots from Shooting tab
    shooting_tab = get_tab_by_name("Shooting")
    if shooting_tab:
        blocks = st.session_state.db.get_blocks_by_tab(shooting_tab["id"])
        shots = [b for b in blocks if b["type"] == "shot"]
    else:
        shots = []
    
    if not shots:
        st.info("Create shot cards in the Shooting phase first.")
        return
    
    # Generation options
    gen_type = st.radio("Generation Type", ["🖼️ Still Image", "🎬 Video"], horizontal=True)
    
    st.markdown("---")
    
    # Select shot to generate
    selected_shot = st.selectbox(
        "Select Shot:",
        options=shots,
        format_func=lambda x: f"{x['content'][:60]}..."
    )
    
    if selected_shot:
        with st.container(border=True):
            st.markdown("**Shot Details:**")
            st.markdown(selected_shot["content"])
        
        # Generate button
        if gen_type == "🖼️ Still Image":
            if st.button("✨ Generate Still Image", type="primary", use_container_width=True):
                if not st.session_state.ai.replicate.is_configured():
                    st.error("Replicate API key not configured. Add your key in the sidebar.")
                else:
                    with st.spinner("Generating image... (this may take 30-60 seconds)"):
                        try:
                            # Extract description from shot content
                            prompt = f"Cinematic film still: {selected_shot['content']}"
                            image_url = st.session_state.ai.generate_image_sync(prompt)
                            st.image(image_url, caption="Generated Image")
                            st.success("Image generated!")
                            
                            # Offer to save
                            if st.button("💾 Save to Asset Library"):
                                # Download and save
                                image_bytes = st.session_state.ai.download_asset(image_url)
                                asset_id = st.session_state.asset_manager.store_asset_from_bytes(
                                    image_bytes,
                                    "generated.png",
                                    st.session_state.project_id,
                                    {"source": "generated", "shot_id": selected_shot["id"], "prompt": prompt}
                                )
                                st.success(f"Saved as asset #{asset_id}")
                        except Exception as e:
                            st.error(f"Generation failed: {e}")
        else:
            if st.button("✨ Generate Video", type="primary", use_container_width=True):
                if not st.session_state.ai.replicate.is_configured():
                    st.error("Replicate API key not configured. Add your key in the sidebar.")
                else:
                    with st.spinner("Generating video... (this may take several minutes)"):
                        try:
                            prompt = f"Cinematic video: {selected_shot['content']}"
                            video_url = st.session_state.ai.generate_video_sync(prompt)
                            st.video(video_url)
                            st.success("Video generated!")
                        except Exception as e:
                            st.error(f"Generation failed: {e}")


def render_assets_section():
    """Render the Asset Library section."""
    st.subheader("📁 Asset Library")
    st.markdown("Manage all your project assets.")
    
    # File upload
    st.markdown("**Upload Asset:**")
    uploaded_file = st.file_uploader(
        "Choose a file",
        type=["png", "jpg", "jpeg", "gif", "mp4", "mov", "mp3", "wav"],
        help="Upload images, videos, or audio files"
    )

    if uploaded_file:
        col1, col2 = st.columns(2)
        with col1:
            tags_input = st.text_input("Tags (comma-separated)", placeholder="character, headshot, jane")
        with col2:
            description = st.text_input("Description", placeholder="Jane's character reference")

        if st.button("📤 Upload"):
            tags = [t.strip() for t in tags_input.split(",") if t.strip()]
            meta = {"tags": tags, "description": description}

            asset_id = st.session_state.asset_manager.store_asset_from_file(
                uploaded_file,
                uploaded_file.name,
                st.session_state.project_id,
                meta
            )
            st.success(f"Asset uploaded! ID: {asset_id}")
            st.rerun()

    # Display assets
    assets = st.session_state.asset_manager.get_all_assets(st.session_state.project_id)
    if assets:
        st.markdown("---")
        
        # Filter
        filter_type = st.selectbox("Filter by type", ["All", "Images", "Videos", "Audio"])

        cols = st.columns(4)
        filtered_assets = assets
        if filter_type == "Images":
            filtered_assets = [a for a in assets if a["mime_type"].startswith("image")]
        elif filter_type == "Videos":
            filtered_assets = [a for a in assets if a["mime_type"].startswith("video")]
        elif filter_type == "Audio":
            filtered_assets = [a for a in assets if a["mime_type"].startswith("audio")]

        for i, asset in enumerate(filtered_assets):
            with cols[i % 4]:
                with st.container(border=True):
                    st.caption(f"ID: {asset['id']}")
                    st.caption(asset["mime_type"])

                    if asset["mime_type"].startswith("image"):
                        try:
                            st.image(str(asset["full_path"]), use_container_width=True)
                        except Exception:
                            st.caption("📷 Image")
                    elif asset["mime_type"].startswith("video"):
                        st.caption("🎬 Video")
                    elif asset["mime_type"].startswith("audio"):
                        st.caption("🎵 Audio")

                    meta = asset.get("meta", {})
                    if meta.get("tags"):
                        st.caption(f"Tags: {', '.join(meta['tags'])}")

                    if st.button("🗑️", key=f"del_asset_{asset['id']}"):
                        st.session_state.asset_manager.delete_asset(asset["id"])
                        st.rerun()
    else:
        st.info("No assets uploaded yet.")


def render_review_section():
    """Render the Review section."""
    st.subheader("📊 Project Review")
    st.markdown("Review your project progress and export.")
    
    # Project summary
    col1, col2, col3, col4 = st.columns(4)
    
    story_tab = get_tab_by_name("Story")
    design_tab = get_tab_by_name("Design")
    shooting_tab = get_tab_by_name("Shooting")
    
    with col1:
        if story_tab:
            blocks = st.session_state.db.get_blocks_by_tab(story_tab["id"])
            scenes = len([b for b in blocks if b["type"] == "scene"])
        else:
            scenes = 0
        st.metric("📜 Scenes", scenes)
    
    with col2:
        if design_tab:
            blocks = st.session_state.db.get_blocks_by_tab(design_tab["id"])
            chars = len([b for b in blocks if b["type"] == "character"])
        else:
            chars = 0
        st.metric("👥 Characters", chars)
    
    with col3:
        if shooting_tab:
            blocks = st.session_state.db.get_blocks_by_tab(shooting_tab["id"])
            shots = len([b for b in blocks if b["type"] == "shot"])
        else:
            shots = 0
        st.metric("🎬 Shots", shots)
    
    with col4:
        assets_count = len(st.session_state.asset_manager.get_all_assets(st.session_state.project_id))
        st.metric("📁 Assets", assets_count)
    
    st.markdown("---")
    
    # Export options
    st.subheader("📤 Export")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📄 Export Project Summary", use_container_width=True):
            summary = generate_project_summary()
            st.download_button(
                "⬇️ Download Summary",
                summary,
                "project_summary.md",
                "text/markdown"
            )
    
    with col2:
        if st.button("📦 Export Project JSON", use_container_width=True):
            project_data = export_project_json()
            st.download_button(
                "⬇️ Download JSON",
                json.dumps(project_data, indent=2),
                "project.json",
                "application/json"
            )


def generate_project_summary() -> str:
    """Generate a markdown summary of the project."""
    summary = "# Project Summary\n\n"

    tabs = st.session_state.db.get_tabs(st.session_state.project_id)
    for tab in tabs:
        blocks = st.session_state.db.get_blocks_by_tab(tab["id"])
        if blocks:
            summary += f"## {tab['name']}\n\n"
            for block in blocks:
                summary += f"### {block['type']}\n"
                summary += f"{block['content']}\n\n"

    return summary


def export_project_json() -> dict:
    """Export project data as JSON."""
    project = st.session_state.db.get_project(st.session_state.project_id)
    tabs = st.session_state.db.get_tabs(st.session_state.project_id)

    data = {
        "project": project,
        "tabs": []
    }

    for tab in tabs:
        blocks = st.session_state.db.get_blocks_by_tab(tab["id"])
        data["tabs"].append({
            "name": tab["name"],
            "blocks": blocks
        })

    return data


def main():
    """Main application entry point."""
    init_session_state()

    # Get or create default project
    if st.session_state.db is None:
        db, project_id, project_root = get_or_create_default_project()
        st.session_state.db = db
        st.session_state.project_id = project_id
        st.session_state.project_root = project_root
        st.session_state.asset_manager = AssetManager(project_root, db)

    render_sidebar()

    # Create the 4 main phase tabs
    phase_tabs = st.tabs([name for name, _ in PHASES])

    # Render each phase
    for tab_obj, (name, phase_id) in zip(phase_tabs, PHASES):
        with tab_obj:
            if phase_id == "story":
                render_story_phase()
            elif phase_id == "design":
                render_design_phase()
            elif phase_id == "shooting":
                render_shooting_phase()
            elif phase_id == "generate":
                render_generate_phase()


if __name__ == "__main__":
    main()
