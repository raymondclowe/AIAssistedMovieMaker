"""AI-Assisted Movie Maker - Main Streamlit Application.

This is the main entry point for the Streamlit UI.
Run with: streamlit run app.py
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

# Define tabs for the movie-making workflow
TAB_NAMES = [
    "Ideation",
    "Plot",
    "Screenplay",
    "Shooting Script",
    "Cast",
    "Locations",
    "Props",
    "Art Direction",
    "Cinematography",
    "Shots",
    "Asset Library",
    "Review"
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
        # Create default tabs
        for i, tab_name in enumerate(TAB_NAMES):
            db.create_tab(project_id, tab_name, i)
    else:
        project_id = projects[0]["id"]

    return db, project_id, default_project_dir


def render_sidebar():
    """Render the sidebar with project info and settings."""
    with st.sidebar:
        st.title("🎬 AI Movie Maker")
        st.markdown("---")

        # Project info
        if st.session_state.project_id:
            project = st.session_state.db.get_project(st.session_state.project_id)
            st.subheader(f"📁 {project['name']}")
            st.caption(f"Created: {project['created_at']}")

        st.markdown("---")

        # Settings
        st.subheader("⚙️ Settings")

        # API Key input
        api_key = st.text_input(
            "OpenAI API Key",
            type="password",
            help="Enter your OpenAI API key for AI features"
        )
        if api_key:
            st.session_state.ai = AIOperations(api_key)
            st.success("API key set!")

        st.markdown("---")

        # Help section
        with st.expander("ℹ️ Help"):
            st.markdown("""
            **How to use:**
            1. Start with **Ideation** - write your movie concept
            2. Use **Generate** buttons to create AI content
            3. Work through tabs in order
            4. Upload or generate assets
            5. Review and assemble your movie

            **Tips:**
            - Tag important content with 'keep' or 'love'
            - Use dependencies to link related content
            - All changes are saved automatically
            """)


def render_ideation_tab(tab_id: int):
    """Render the Ideation tab."""
    st.header("💡 Ideation")
    st.markdown("Start with your core movie idea. Write a logline, concept, or initial thoughts.")

    # Get existing blocks
    blocks = st.session_state.db.get_blocks_by_tab(tab_id)

    # Input for new idea
    with st.form("new_idea"):
        content = st.text_area(
            "Your Movie Idea",
            height=200,
            placeholder="A detective must solve a murder on a moving train before it reaches its destination..."
        )
        col1, col2 = st.columns([1, 4])
        with col1:
            submit = st.form_submit_button("Save", use_container_width=True)
        with col2:
            generate = st.form_submit_button("✨ Expand with AI", use_container_width=True)

        if submit and content:
            st.session_state.db.add_block(tab_id, "logline", content)
            st.success("Idea saved!")
            st.rerun()

        if generate and content:
            with st.spinner("Generating expanded concept..."):
                prompt = f"Expand this movie concept into a detailed premise with genre, tone, and key themes:\n\n{content}"
                expanded = st.session_state.ai.llm_generate_sync(prompt)
                st.session_state.db.add_block(tab_id, "concept", expanded)
                st.success("Concept generated!")
                st.rerun()

    # Display existing ideas
    if blocks:
        st.markdown("---")
        st.subheader("📝 Saved Ideas")
        for block in blocks:
            with st.expander(f"{block['type'].title()}: {block['content'][:50]}...", expanded=False):
                st.markdown(block["content"])
                col1, col2, col3 = st.columns([1, 1, 3])
                with col1:
                    if st.button("🗑️ Delete", key=f"del_{block['id']}"):
                        st.session_state.db.delete_block(block["id"])
                        st.rerun()
                with col2:
                    tags = block.get("tags", [])
                    if "keep" in tags:
                        if st.button("❌ Unkeep", key=f"unkeep_{block['id']}"):
                            tags.remove("keep")
                            st.session_state.db.update_block(block["id"], tags=tags)
                            st.rerun()
                    else:
                        if st.button("⭐ Keep", key=f"keep_{block['id']}"):
                            tags.append("keep")
                            st.session_state.db.update_block(block["id"], tags=tags)
                            st.rerun()


def render_plot_tab(tab_id: int):
    """Render the Plot tab."""
    st.header("📊 Plot / Outline")
    st.markdown("Create your story structure. Generate an outline from your ideation or write it manually.")

    # Get ideation blocks to use as source
    ideation_tab = get_tab_by_name("Ideation")
    ideation_blocks = st.session_state.db.get_blocks_by_tab(ideation_tab["id"]) if ideation_tab else []

    # Generate from ideation
    if ideation_blocks:
        st.subheader("🤖 Generate from Ideation")
        source_block = st.selectbox(
            "Select source idea:",
            options=ideation_blocks,
            format_func=lambda x: f"{x['type']}: {x['content'][:50]}..."
        )
        if st.button("✨ Generate Plot Outline"):
            with st.spinner("Generating plot outline..."):
                prompt = f"Write a detailed 5-act plot outline for a movie based on this concept:\n\n{source_block['content']}"
                outline = st.session_state.ai.llm_generate_sync(prompt)
                block_id = st.session_state.db.add_block(tab_id, "outline", outline)
                # Add dependency
                st.session_state.db.add_dependency(source_block["id"], block_id, "ideation_to_plot")
                st.success("Plot outline generated!")
                st.rerun()

    st.markdown("---")

    # Manual input
    with st.form("new_plot"):
        content = st.text_area(
            "Write Plot Point",
            height=150,
            placeholder="Act 1: Setup - Introduce the detective boarding the train..."
        )
        plot_type = st.selectbox("Type", ["act", "beat", "sequence", "note"])
        if st.form_submit_button("Add Plot Point"):
            if content:
                st.session_state.db.add_block(tab_id, plot_type, content)
                st.success("Plot point added!")
                st.rerun()

    # Display existing plot blocks
    blocks = st.session_state.db.get_blocks_by_tab(tab_id)
    if blocks:
        st.markdown("---")
        st.subheader("📝 Plot Structure")
        for block in blocks:
            with st.expander(f"{block['type'].upper()}: {block['content'][:50]}...", expanded=True):
                st.markdown(block["content"])
                if st.button("🗑️ Delete", key=f"del_plot_{block['id']}"):
                    st.session_state.db.delete_block(block["id"])
                    st.rerun()


def render_screenplay_tab(tab_id: int):
    """Render the Screenplay tab."""
    st.header("📜 Screenplay")
    st.markdown("Write your scenes with dialogue, action, and descriptions.")

    # Get plot blocks as source
    plot_tab = get_tab_by_name("Plot")
    plot_blocks = st.session_state.db.get_blocks_by_tab(plot_tab["id"]) if plot_tab else []

    # Generate from plot
    if plot_blocks:
        st.subheader("🤖 Generate Scene from Plot")
        source_block = st.selectbox(
            "Select plot point:",
            options=plot_blocks,
            format_func=lambda x: f"{x['type']}: {x['content'][:50]}..."
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
                st.session_state.db.add_dependency(source_block["id"], block_id, "plot_to_screenplay")
                st.success("Scene generated!")
                st.rerun()

    st.markdown("---")

    # Manual input
    with st.form("new_scene"):
        scene_heading = st.text_input("Scene Heading", placeholder="INT. TRAIN DINING CAR - NIGHT")
        content = st.text_area(
            "Scene Content",
            height=300,
            placeholder="The DETECTIVE enters the crowded dining car..."
        )
        if st.form_submit_button("Add Scene"):
            if scene_heading and content:
                full_content = f"{scene_heading}\n\n{content}"
                st.session_state.db.add_block(tab_id, "scene", full_content)
                st.success("Scene added!")
                st.rerun()

    # Display scenes
    blocks = st.session_state.db.get_blocks_by_tab(tab_id)
    if blocks:
        st.markdown("---")
        st.subheader("📑 Scenes")
        for block in blocks:
            with st.expander(f"Scene: {block['content'][:50]}...", expanded=False):
                st.text(block["content"])
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("🗑️ Delete", key=f"del_scene_{block['id']}"):
                        st.session_state.db.delete_block(block["id"])
                        st.rerun()
                with col2:
                    tags = block.get("tags", [])
                    tag_str = ", ".join(tags) if tags else "No tags"
                    st.caption(f"Tags: {tag_str}")
                with col3:
                    new_tag = st.selectbox(
                        "Add tag",
                        ["", "keep", "rewrite", "love", "hate"],
                        key=f"tag_{block['id']}"
                    )
                    if new_tag:
                        tags = block.get("tags", [])
                        if new_tag not in tags:
                            tags.append(new_tag)
                            st.session_state.db.update_block(block["id"], tags=tags)
                            st.rerun()


def render_shooting_script_tab(tab_id: int):
    """Render the Shooting Script tab."""
    st.header("🎬 Shooting Script")
    st.markdown("Add technical details to your screenplay scenes.")

    # Get screenplay blocks
    screenplay_tab = get_tab_by_name("Screenplay")
    screenplay_blocks = st.session_state.db.get_blocks_by_tab(screenplay_tab["id"]) if screenplay_tab else []

    if screenplay_blocks:
        st.subheader("📜 Scenes")
        for scene in screenplay_blocks:
            with st.expander(f"Scene: {scene['content'][:50]}...", expanded=False):
                st.text(scene["content"][:500] + "..." if len(scene["content"]) > 500 else scene["content"])

                # Add technical details
                with st.form(f"tech_{scene['id']}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        camera = st.text_input("Camera", placeholder="Wide shot, dolly")
                        location = st.text_input("Location", placeholder="Train dining car set")
                    with col2:
                        characters = st.text_input("Characters", placeholder="Detective, Victim")
                        props = st.text_input("Props", placeholder="Wine glass, knife")

                    if st.form_submit_button("Save Technical Details"):
                        tech_content = f"""SCENE: {scene['content'][:100]}...

TECHNICAL DETAILS:
- Camera: {camera}
- Location: {location}
- Characters: {characters}
- Props: {props}"""
                        block_id = st.session_state.db.add_block(tab_id, "shooting_notes", tech_content)
                        st.session_state.db.add_dependency(scene["id"], block_id, "screenplay_to_shooting")
                        st.success("Technical details saved!")
                        st.rerun()

    # Display existing shooting script notes
    blocks = st.session_state.db.get_blocks_by_tab(tab_id)
    if blocks:
        st.markdown("---")
        st.subheader("📋 Shooting Notes")
        for block in blocks:
            with st.expander(f"Notes: {block['content'][:50]}...", expanded=False):
                st.markdown(block["content"])
                if st.button("🗑️ Delete", key=f"del_shooting_{block['id']}"):
                    st.session_state.db.delete_block(block["id"])
                    st.rerun()
    elif not screenplay_blocks:
        st.info("Add scenes in the Screenplay tab first.")


def render_cast_tab(tab_id: int):
    """Render the Cast tab."""
    st.header("👥 Cast & Characters")
    st.markdown("Define your characters with descriptions and reference images.")

    # Add new character
    with st.form("new_character"):
        st.subheader("➕ Add Character")
        name = st.text_input("Character Name", placeholder="Detective Jane Doe")
        description = st.text_area(
            "Description",
            height=150,
            placeholder="Age, appearance, personality, background..."
        )
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("Save Character"):
                if name and description:
                    content = f"# {name}\n\n{description}"
                    st.session_state.db.add_block(tab_id, "character", content)
                    st.success("Character added!")
                    st.rerun()
        with col2:
            if st.form_submit_button("✨ Generate Character"):
                if name:
                    with st.spinner("Generating character..."):
                        prompt = f"Create a detailed character profile for a movie character named {name}. Include physical description, personality, background, and motivation."
                        if description:
                            prompt += f"\n\nAdditional context: {description}"
                        generated = st.session_state.ai.llm_generate_sync(prompt)
                        st.session_state.db.add_block(tab_id, "character", generated)
                        st.success("Character generated!")
                        st.rerun()

    # Display characters
    blocks = st.session_state.db.get_blocks_by_tab(tab_id)
    if blocks:
        st.markdown("---")
        st.subheader("🎭 Characters")
        cols = st.columns(2)
        for i, block in enumerate(blocks):
            with cols[i % 2]:
                with st.container(border=True):
                    st.markdown(block["content"])
                    if st.button("🗑️ Delete", key=f"del_char_{block['id']}"):
                        st.session_state.db.delete_block(block["id"])
                        st.rerun()


def render_locations_tab(tab_id: int):
    """Render the Locations tab."""
    st.header("📍 Locations")
    st.markdown("Define the settings and locations for your movie.")

    # Add new location
    with st.form("new_location"):
        st.subheader("➕ Add Location")
        name = st.text_input("Location Name", placeholder="Train Dining Car")
        description = st.text_area(
            "Description",
            height=150,
            placeholder="Visual details, atmosphere, mood..."
        )
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("Save Location"):
                if name and description:
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

    # Display locations
    blocks = st.session_state.db.get_blocks_by_tab(tab_id)
    if blocks:
        st.markdown("---")
        st.subheader("🗺️ Locations")
        for block in blocks:
            with st.expander(block["content"][:50] + "...", expanded=False):
                st.markdown(block["content"])
                if st.button("🗑️ Delete", key=f"del_loc_{block['id']}"):
                    st.session_state.db.delete_block(block["id"])
                    st.rerun()


def render_props_tab(tab_id: int):
    """Render the Props tab."""
    st.header("🎭 Props & Costumes")
    st.markdown("Track props, costumes, and other physical items needed for your movie.")

    # Add new item
    with st.form("new_prop"):
        st.subheader("➕ Add Item")
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Item Name", placeholder="Poison Wine Glass")
            item_type = st.selectbox("Type", ["prop", "costume", "vehicle", "other"])
        with col2:
            description = st.text_area("Description", placeholder="Description and visual details...")

        if st.form_submit_button("Save Item"):
            if name:
                content = f"**{name}** ({item_type})\n\n{description}"
                st.session_state.db.add_block(tab_id, item_type, content)
                st.success("Item added!")
                st.rerun()

    # Display items
    blocks = st.session_state.db.get_blocks_by_tab(tab_id)
    if blocks:
        st.markdown("---")
        st.subheader("📦 Items")
        cols = st.columns(3)
        for i, block in enumerate(blocks):
            with cols[i % 3]:
                with st.container(border=True):
                    st.markdown(block["content"])
                    st.caption(f"Type: {block['type']}")
                    if st.button("🗑️", key=f"del_prop_{block['id']}"):
                        st.session_state.db.delete_block(block["id"])
                        st.rerun()


def render_art_direction_tab(tab_id: int):
    """Render the Art Direction tab."""
    st.header("🎨 Art Direction")
    st.markdown("Define the visual style, mood boards, and artistic direction.")

    # Add style guide
    with st.form("new_style"):
        st.subheader("➕ Add Style Element")
        element_type = st.selectbox("Element Type", ["color_palette", "mood", "style_reference", "visual_theme"])
        content = st.text_area(
            "Description",
            height=150,
            placeholder="Describe the visual style element..."
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("Save"):
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

    # Display style elements
    blocks = st.session_state.db.get_blocks_by_tab(tab_id)
    if blocks:
        st.markdown("---")
        st.subheader("🖼️ Style Elements")
        for block in blocks:
            with st.expander(f"{block['type'].replace('_', ' ').title()}", expanded=False):
                st.markdown(block["content"])
                if st.button("🗑️ Delete", key=f"del_art_{block['id']}"):
                    st.session_state.db.delete_block(block["id"])
                    st.rerun()


def render_cinematography_tab(tab_id: int):
    """Render the Cinematography tab."""
    st.header("🎥 Cinematography")
    st.markdown("Define camera work, lighting, and visual techniques.")

    # Add cinematography element
    with st.form("new_cine"):
        st.subheader("➕ Add Cinematography Note")
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

        if st.form_submit_button("Save"):
            content = f"""**Shot Type:** {shot_type}
**Lens:** {lens}
**Lighting:** {lighting}
**Movement:** {movement}

{notes}"""
            st.session_state.db.add_block(tab_id, "cinematography", content)
            st.success("Cinematography note added!")
            st.rerun()

    # Display cinematography notes
    blocks = st.session_state.db.get_blocks_by_tab(tab_id)
    if blocks:
        st.markdown("---")
        st.subheader("📹 Cinematography Notes")
        for block in blocks:
            with st.expander(f"Shot: {block['content'][:50]}...", expanded=False):
                st.markdown(block["content"])
                if st.button("🗑️ Delete", key=f"del_cine_{block['id']}"):
                    st.session_state.db.delete_block(block["id"])
                    st.rerun()


def render_shots_tab(tab_id: int):
    """Render the Shots tab."""
    st.header("🎯 Shots")
    st.markdown("Create individual shot cards for video generation.")

    # Get screenplay scenes for reference
    screenplay_tab = get_tab_by_name("Screenplay")
    screenplay_blocks = st.session_state.db.get_blocks_by_tab(screenplay_tab["id"]) if screenplay_tab else []

    # Add new shot
    with st.form("new_shot"):
        st.subheader("➕ Add Shot")

        if screenplay_blocks:
            scene_ref = st.selectbox(
                "Reference Scene (optional)",
                options=[None] + screenplay_blocks,
                format_func=lambda x: "Select scene..." if x is None else f"{x['content'][:50]}..."
            )

        description = st.text_area(
            "Shot Description",
            height=100,
            placeholder="Wide shot of train entering tunnel..."
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
            if st.form_submit_button("Save Shot"):
                if description:
                    content = f"""**Shot Type:** {shot_type}
**Duration:** {duration}s
**Characters:** {characters}

{description}"""
                    block_id = st.session_state.db.add_block(tab_id, "shot", content)
                    if screenplay_blocks and scene_ref:
                        st.session_state.db.add_dependency(scene_ref["id"], block_id, "scene_to_shot")
                    st.success("Shot added!")
                    st.rerun()
        with col2:
            if st.form_submit_button("✨ Generate Shot Description"):
                if description:
                    with st.spinner("Generating shot description..."):
                        prompt = f"Create a detailed shot description for video generation: {description}. Include visual composition, camera angle, lighting, and mood."
                        generated = st.session_state.ai.llm_generate_sync(prompt)
                        st.session_state.db.add_block(tab_id, "shot", generated)
                        st.success("Shot description generated!")
                        st.rerun()

    # Display shots
    blocks = st.session_state.db.get_blocks_by_tab(tab_id)
    if blocks:
        st.markdown("---")
        st.subheader("🎬 Shot List")
        for i, block in enumerate(blocks, 1):
            with st.expander(f"Shot {i}: {block['content'][:50]}...", expanded=False):
                st.markdown(block["content"])
                col1, col2 = st.columns([1, 4])
                with col1:
                    if st.button("🗑️ Delete", key=f"del_shot_{block['id']}"):
                        st.session_state.db.delete_block(block["id"])
                        st.rerun()
                with col2:
                    tags = block.get("tags", [])
                    if "needs_regen" in tags:
                        st.warning("⚠️ Source material changed - consider regenerating")


def render_asset_library_tab(tab_id: int):
    """Render the Asset Library tab."""
    st.header("📁 Asset Library")
    st.markdown("Manage all your project assets (images, videos, audio).")

    # File upload
    st.subheader("📤 Upload Asset")
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

        if st.button("Upload"):
            # Save the uploaded file
            tags = [t.strip() for t in tags_input.split(",") if t.strip()]
            meta = {"tags": tags, "description": description}

            asset_id = st.session_state.asset_manager.store_asset_from_bytes(
                uploaded_file.read(),
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
        st.subheader("📚 Assets")

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

                    # Display preview based on type
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
        st.info("No assets uploaded yet. Use the uploader above to add files.")


def render_review_tab(tab_id: int):
    """Render the Review & Assembly tab."""
    st.header("🎞️ Review & Assembly")
    st.markdown("Review your project and prepare for final assembly.")

    # Project summary
    st.subheader("📊 Project Summary")

    col1, col2, col3 = st.columns(3)

    with col1:
        screenplay_tab = get_tab_by_name("Screenplay")
        screenplay_count = len(st.session_state.db.get_blocks_by_tab(screenplay_tab["id"])) if screenplay_tab else 0
        st.metric("Scenes", screenplay_count)

    with col2:
        shots_tab = get_tab_by_name("Shots")
        shots_count = len(st.session_state.db.get_blocks_by_tab(shots_tab["id"])) if shots_tab else 0
        st.metric("Shots", shots_count)

    with col3:
        assets_count = len(st.session_state.asset_manager.get_all_assets(st.session_state.project_id))
        st.metric("Assets", assets_count)

    st.markdown("---")

    # Review sections
    st.subheader("📋 Content Review")

    tabs_to_review = ["Ideation", "Plot", "Screenplay", "Shots"]
    for tab_name in tabs_to_review:
        tab = get_tab_by_name(tab_name)
        if tab:
            blocks = st.session_state.db.get_blocks_by_tab(tab["id"])
            with st.expander(f"{tab_name} ({len(blocks)} items)", expanded=False):
                for block in blocks:
                    st.markdown(f"**{block['type']}:** {block['content'][:100]}...")
                    tags = block.get("tags", [])
                    if tags:
                        st.caption(f"Tags: {', '.join(tags)}")
                    st.markdown("---")

    # Export options
    st.markdown("---")
    st.subheader("📤 Export")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📄 Export Project Summary", use_container_width=True):
            summary = generate_project_summary()
            st.download_button(
                "Download Summary",
                summary,
                "project_summary.md",
                "text/markdown"
            )

    with col2:
        if st.button("📦 Export Project JSON", use_container_width=True):
            project_data = export_project_json()
            st.download_button(
                "Download JSON",
                json.dumps(project_data, indent=2),
                "project.json",
                "application/json"
            )


def get_tab_by_name(name: str) -> Optional[dict]:
    """Get tab by name."""
    tabs = st.session_state.db.get_tabs(st.session_state.project_id)
    for tab in tabs:
        if tab["name"] == name:
            return tab
    return None


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
        st.session_state.asset_manager = AssetManager(project_root, db.conn)

    render_sidebar()

    # Get tabs
    tabs = st.session_state.db.get_tabs(st.session_state.project_id)

    # Create tab UI
    tab_objects = st.tabs([tab["name"] for tab in tabs])

    # Render each tab
    tab_renderers = {
        "Ideation": render_ideation_tab,
        "Plot": render_plot_tab,
        "Screenplay": render_screenplay_tab,
        "Shooting Script": render_shooting_script_tab,
        "Cast": render_cast_tab,
        "Locations": render_locations_tab,
        "Props": render_props_tab,
        "Art Direction": render_art_direction_tab,
        "Cinematography": render_cinematography_tab,
        "Shots": render_shots_tab,
        "Asset Library": render_asset_library_tab,
        "Review": render_review_tab
    }

    for tab_obj, tab_data in zip(tab_objects, tabs):
        with tab_obj:
            renderer = tab_renderers.get(tab_data["name"])
            if renderer:
                renderer(tab_data["id"])
            else:
                st.write(f"Tab: {tab_data['name']}")


if __name__ == "__main__":
    main()
