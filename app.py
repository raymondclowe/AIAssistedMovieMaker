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
    # Generic editing state (for any block)
    if "editing_block_id" not in st.session_state:
        st.session_state.editing_block_id = None
    if "block_version_index" not in st.session_state:
        st.session_state.block_version_index = {}
    # Legacy concept editing state (kept for backward compatibility)
    if "editing_concept_id" not in st.session_state:
        st.session_state.editing_concept_id = None
    if "concept_version_index" not in st.session_state:
        st.session_state.concept_version_index = {}


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
        tab_names = ["Story", "Design", "Shooting", "Generate", "CreativeNotes"]
        for i, tab_name in enumerate(tab_names):
            db.create_tab(project_id, tab_name, i)
    else:
        project_id = projects[0]["id"]
        # Ensure CreativeNotes tab exists for existing projects
        tabs = db.get_tabs(project_id)
        tab_names = [t["name"] for t in tabs]
        if "CreativeNotes" not in tab_names:
            db.create_tab(project_id, "CreativeNotes", len(tabs))

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
        mode_options = ["draft", "medium", "final"]
        current_mode_index = mode_options.index(st.session_state.ai_mode) if st.session_state.ai_mode in mode_options else 0
        mode = st.radio(
            "Quality Mode",
            options=mode_options,
            index=current_mode_index,
            help="Draft: Fast & cheap (Llama 3.2). Medium: Balanced (GPT-4o). Final: Best quality (Claude Sonnet).",
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
        
        # Creative Notes section
        render_creative_notes_section()

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
            
            **Quality Modes:**
            - **Draft**: Fast, cheap models (Llama 3.2) for rapid iteration
            - **Medium**: Balanced quality/cost (GPT-4o)
            - **Final**: Best quality models (Claude Sonnet) for production
            
            **Tips:**
            - Use Draft mode while developing your story
            - Generate stills first to save costs
            - Switch to Final mode for your best shots
            - Use the Notes feature to refine AI-generated content
            - Save creative ideas in Creative Notes for later use
            """)


def get_tab_by_name(name: str) -> Optional[dict]:
    """Get tab by name."""
    tabs = st.session_state.db.get_tabs(st.session_state.project_id)
    for tab in tabs:
        if tab["name"] == name:
            return tab
    return None


def get_creative_notes_for_category(category: str) -> list:
    """Get creative notes for a specific category (e.g., 'scene', 'dialogue', 'shot')."""
    notes_tab = get_tab_by_name("CreativeNotes")
    if not notes_tab:
        return []
    blocks = st.session_state.db.get_blocks_by_tab(notes_tab["id"])
    return [b for b in blocks if b["type"] == f"note_{category}" and "used" not in b.get("tags", [])]


def truncate_content(content: str, max_length: int = 60) -> str:
    """Truncate content and add ellipsis if needed."""
    if len(content) > max_length:
        return content[:max_length] + "..."
    return content


def render_creative_notes_selector(category: str, form_key: str) -> Optional[str]:
    """Render a selector for creative notes that can be incorporated into AI prompts.
    
    Returns the selected note content or None if no note selected.
    """
    notes = get_creative_notes_for_category(category)
    if not notes:
        return None
    
    st.markdown("**📌 Include Creative Note:**")
    options = [{"id": None, "content": "-- No note --"}] + notes
    selected = st.selectbox(
        "Select a saved idea to include",
        options=options,
        format_func=lambda x: truncate_content(x["content"]) if x["id"] else "-- No note --",
        key=f"note_select_{form_key}"
    )
    if selected and selected.get("id"):
        return selected["content"]
    return None


def render_block_with_feedback(block: dict, block_type_name: str, revision_prompt_template: str, 
                                source_content: str = "", extra_context: str = ""):
    """Render a block with edit, delete, and AI revision capabilities.
    
    Args:
        block: The block dict from the database
        block_type_name: Human-readable name for the block type (e.g., "Plot Outline")
        revision_prompt_template: Template for revision prompt with {content} and {notes} placeholders
        source_content: Original source content if available
        extra_context: Additional context to include in revision prompt
    """
    block_id = block["id"]
    history = st.session_state.db.get_history(block_id)
    
    # Get version history
    content_history = [
        h for h in history 
        if h["action"] == "create" or (h["action"] == "edit" and h.get("payload", {}).get("new_content"))
    ]
    total_versions = len(content_history) if content_history else 1
    
    # Get current version index (0 = latest/current, higher = older versions)
    version_key = f"version_{block_id}"
    if version_key not in st.session_state.block_version_index:
        st.session_state.block_version_index[version_key] = 0
    current_version_idx = st.session_state.block_version_index[version_key]
    
    # Determine which content to show
    # Index 0 means show current/latest content from block
    # Index > 0 means show historical version from content_history
    if current_version_idx == 0:
        display_content = block["content"]
    else:
        # Show historical version - ensure index is within bounds
        history_idx = current_version_idx - 1
        if history_idx >= 0 and history_idx < len(content_history):
            payload = content_history[history_idx].get("payload", {})
            # For edit actions, old_content contains the previous version
            # For create actions, content contains the initial version
            display_content = payload.get("old_content") or payload.get("content") or block["content"]
        else:
            display_content = block["content"]
    
    # Version navigation
    if total_versions > 1:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col1:
            # Disable "Older" when at the oldest version
            if st.button("⬅️ Older", key=f"older_{block_id}", disabled=current_version_idx >= total_versions - 1):
                st.session_state.block_version_index[version_key] = current_version_idx + 1
                st.rerun()
        with col2:
            st.caption(f"Version {total_versions - current_version_idx} of {total_versions}")
        with col3:
            # Disable "Newer" when at the latest version (index 0)
            if st.button("Newer ➡️", key=f"newer_{block_id}", disabled=current_version_idx <= 0):
                st.session_state.block_version_index[version_key] = current_version_idx - 1
                st.rerun()
    
    # Check if in edit mode
    is_editing = st.session_state.editing_block_id == block_id
    
    if is_editing:
        # Editable text area
        edited_content = st.text_area(
            f"Edit {block_type_name}",
            value=display_content,
            height=300,
            key=f"edit_area_{block_id}"
        )
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Save Edit", key=f"save_edit_{block_id}"):
                st.session_state.db.update_block(block_id, content=edited_content)
                st.session_state.editing_block_id = None
                st.session_state.block_version_index[version_key] = 0
                st.success(f"{block_type_name} updated!")
                st.rerun()
        with col2:
            if st.button("❌ Cancel", key=f"cancel_edit_{block_id}"):
                st.session_state.editing_block_id = None
                st.rerun()
    else:
        # Display content
        st.markdown(display_content)
        
        # Action buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✏️ Edit", key=f"edit_{block_id}"):
                st.session_state.editing_block_id = block_id
                st.rerun()
        with col2:
            if st.button("🗑️ Delete", key=f"del_{block_id}"):
                st.session_state.db.delete_block(block_id)
                st.rerun()
    
    # Feedback/Notes section (always visible when not editing)
    if not is_editing:
        st.markdown("---")
        st.markdown("**📝 Refine with Notes**")
        st.caption(f"Add notes to guide AI revision of this {block_type_name.lower()}")
        
        with st.form(f"notes_form_{block_id}"):
            notes = st.text_area(
                "Your Notes",
                height=100,
                placeholder="e.g., Make it more dramatic, add more detail about the setting, change the tone...",
                key=f"notes_{block_id}"
            )
            
            if st.form_submit_button("🔄 Revise with AI", use_container_width=True):
                if notes:
                    with st.spinner(f"Revising {block_type_name.lower()} based on your notes..."):
                        # Build the revision prompt
                        revision_prompt = revision_prompt_template.format(
                            source=source_content if source_content else "Not provided",
                            content=display_content,
                            notes=notes,
                            extra_context=extra_context
                        )
                        revised = st.session_state.ai.llm_generate_sync(revision_prompt)
                        st.session_state.db.update_block(block_id, content=revised)
                        st.session_state.block_version_index[version_key] = 0
                        st.success(f"{block_type_name} revised!")
                        st.rerun()
                else:
                    st.warning("Please enter some notes to guide the revision.")


# =============================================================================
# CREATIVE NOTES SIDEBAR
# =============================================================================

def render_creative_notes_section():
    """Render the Creative Notes section in the sidebar."""
    notes_tab = get_tab_by_name("CreativeNotes")
    if not notes_tab:
        return
    
    with st.expander("💡 Creative Notes", expanded=False):
        st.caption("Capture ideas for later use in the workflow")
        
        # Quick add form
        with st.form("quick_note", clear_on_submit=True):
            note_category = st.selectbox(
                "Category",
                options=["scene", "dialogue", "shot", "character", "location", "visual", "general"],
                help="What type of idea is this?"
            )
            note_content = st.text_area(
                "Your Idea",
                height=80,
                placeholder="A specific line of dialogue, a shot description, a scene idea..."
            )
            if st.form_submit_button("💾 Save Note", use_container_width=True):
                if note_content:
                    st.session_state.db.add_block(notes_tab["id"], f"note_{note_category}", note_content)
                    st.success("Note saved!")
                    st.rerun()
        
        # Display existing notes
        blocks = st.session_state.db.get_blocks_by_tab(notes_tab["id"])
        if blocks:
            st.markdown("---")
            st.caption("**Saved Ideas:**")
            for block in blocks:
                category = block["type"].replace("note_", "")
                tags = block.get("tags", [])
                used_marker = " ✅" if "used" in tags else ""
                with st.container(border=True):
                    st.caption(f"📌 {category.title()}{used_marker}")
                    st.markdown(truncate_content(block["content"], 100))
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("🗑️", key=f"del_note_{block['id']}"):
                            st.session_state.db.delete_block(block["id"])
                            st.rerun()
                    with col2:
                        if "used" not in tags:
                            if st.button("✓", key=f"mark_used_{block['id']}", help="Mark as used"):
                                new_tags = tags + ["used"]
                                st.session_state.db.update_block(block["id"], tags=new_tags)
                                st.rerun()


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
    """Render the Concept section with feedback mechanism."""
    st.subheader("💡 Movie Concept")
    st.markdown("Start with your core movie idea - a logline or concept.")
    
    # Get existing concept blocks
    blocks = st.session_state.db.get_blocks_by_tab(tab_id)
    loglines = [b for b in blocks if b["type"] == "logline"]
    concepts = [b for b in blocks if b["type"] == "concept"]
    
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
                # Store the expanded concept with metadata linking to original
                block_id = st.session_state.db.add_block(tab_id, "concept", expanded)
                # Also save the original logline for reference if not already saved
                logline_id = st.session_state.db.add_block(tab_id, "logline", content)
                st.session_state.db.add_dependency(logline_id, block_id, "logline_to_concept")
                st.success("Concept expanded!")
                st.rerun()

    # Display saved loglines
    if loglines:
        st.markdown("---")
        st.subheader("📝 Original Ideas")
        for block in loglines:
            with st.expander(f"💡 {block['content'][:60]}...", expanded=False):
                st.markdown(block["content"])
                if st.button("🗑️ Delete", key=f"del_logline_{block['id']}"):
                    st.session_state.db.delete_block(block["id"])
                    st.rerun()

    # Display expanded concepts with feedback mechanism
    if concepts:
        st.markdown("---")
        st.subheader("🎬 Expanded Concepts")
        
        for block in concepts:
            block_id = block["id"]
            history = st.session_state.db.get_history(block_id)
            
            # Get version history (filter for content-changing edits)
            # Include 'create' actions and 'edit' actions that have new_content
            content_history = [
                h for h in history 
                if h["action"] == "create" or (h["action"] == "edit" and h.get("payload", {}).get("new_content"))
            ]
            total_versions = len(content_history) if content_history else 1
            
            # Get current version index for this block
            version_key = f"version_{block_id}"
            if version_key not in st.session_state.concept_version_index:
                st.session_state.concept_version_index[version_key] = 0  # 0 = current/latest
            current_version_idx = st.session_state.concept_version_index[version_key]
            
            # Determine which content to show
            if current_version_idx == 0:
                display_content = block["content"]
            else:
                # Show historical version (index > 0 means looking at older versions)
                if current_version_idx > 0 and current_version_idx <= len(content_history):
                    payload = content_history[current_version_idx - 1].get("payload", {})
                    display_content = payload.get("old_content") or payload.get("content") or block["content"]
                else:
                    display_content = block["content"]
            
            with st.expander(f"🎬 {display_content[:60]}...", expanded=True):
                # Version navigation
                if total_versions > 1:
                    col1, col2, col3 = st.columns([1, 2, 1])
                    with col1:
                        if st.button("⬅️ Older", key=f"older_{block_id}", disabled=current_version_idx >= total_versions - 1):
                            st.session_state.concept_version_index[version_key] = current_version_idx + 1
                            st.rerun()
                    with col2:
                        st.caption(f"Version {total_versions - current_version_idx} of {total_versions}")
                    with col3:
                        if st.button("Newer ➡️", key=f"newer_{block_id}", disabled=current_version_idx <= 0):
                            st.session_state.concept_version_index[version_key] = current_version_idx - 1
                            st.rerun()
                
                # Check if in edit mode
                is_editing = st.session_state.editing_concept_id == block_id
                
                if is_editing:
                    # Editable text area
                    edited_content = st.text_area(
                        "Edit Concept",
                        value=display_content,
                        height=300,
                        key=f"edit_area_{block_id}"
                    )
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("💾 Save Edit", key=f"save_edit_{block_id}"):
                            st.session_state.db.update_block(block_id, content=edited_content)
                            st.session_state.editing_concept_id = None
                            st.session_state.concept_version_index[version_key] = 0  # Reset to latest
                            st.success("Concept updated!")
                            st.rerun()
                    with col2:
                        if st.button("❌ Cancel", key=f"cancel_edit_{block_id}"):
                            st.session_state.editing_concept_id = None
                            st.rerun()
                else:
                    # Display content
                    st.markdown(display_content)
                    
                    # Action buttons
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("✏️ Edit", key=f"edit_{block_id}"):
                            st.session_state.editing_concept_id = block_id
                            st.rerun()
                    with col2:
                        if st.button("🗑️ Delete", key=f"del_concept_{block_id}"):
                            st.session_state.db.delete_block(block_id)
                            st.rerun()
                
                # Feedback/Notes section (always visible when not editing)
                if not is_editing:
                    st.markdown("---")
                    st.markdown("**📝 Refine with Notes**")
                    st.caption("Add notes to guide AI revision of this concept")
                    
                    # Get the original logline if available (concept is the destination of the dependency)
                    original_logline = ""
                    deps = st.session_state.db.get_reverse_dependencies(block_id)
                    for dep in deps:
                        if dep.get("type") == "logline_to_concept":
                            src_block = st.session_state.db.get_block(dep["src_block_id"])
                            if src_block:
                                original_logline = src_block["content"]
                                break
                    # Also check fallback - use first logline if no dependency found
                    if not original_logline and loglines:
                        original_logline = loglines[0]["content"]  # Use first logline as fallback
                    
                    with st.form(f"notes_form_{block_id}"):
                        notes = st.text_area(
                            "Your Notes",
                            height=100,
                            placeholder="e.g., Make the protagonist more mysterious, emphasize the noir elements, change the setting to 1940s...",
                            key=f"notes_{block_id}"
                        )
                        
                        if st.form_submit_button("🔄 Revise with AI", use_container_width=True):
                            if notes:
                                with st.spinner("Revising concept based on your notes..."):
                                    revision_prompt = f"""Revise the following movie concept based on the creator's notes.

ORIGINAL IDEA:
{original_logline if original_logline else "Not provided"}

CURRENT EXPANDED CONCEPT:
{display_content}

CREATOR'S NOTES/FEEDBACK:
{notes}

Please revise the expanded concept to incorporate the feedback while maintaining the core premise. Output only the revised concept."""
                                    revised = st.session_state.ai.llm_generate_sync(revision_prompt)
                                    # Update the block with the revised content
                                    st.session_state.db.update_block(block_id, content=revised)
                                    st.session_state.concept_version_index[version_key] = 0  # Reset to latest
                                    st.success("Concept revised!")
                                    st.rerun()
                            else:
                                st.warning("Please enter some notes to guide the revision.")


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
            format_func=lambda x: f"{x['content'][:60]}...",
            key="plot_source_concept"
        )
        
        # Option to include a creative note
        scene_note = render_creative_notes_selector("scene", "plot_gen")
        
        if st.button("✨ Generate Plot Outline"):
            with st.spinner("Generating plot outline..."):
                prompt = f"Write a detailed 5-act plot outline for a movie based on this concept:\n\n{source_block['content']}"
                if scene_note:
                    prompt += f"\n\nIncorporate this specific idea from the creator:\n{scene_note}"
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
    
    # Display existing plots with feedback mechanism
    if plots:
        st.markdown("---")
        st.subheader("📑 Plot Structure")
        
        # Define revision prompt template for plots
        plot_revision_template = """Revise the following plot element based on the creator's notes.

ORIGINAL SOURCE CONCEPT:
{source}

CURRENT PLOT CONTENT:
{content}

CREATOR'S NOTES/FEEDBACK:
{notes}

Please revise the plot to incorporate the feedback while maintaining story coherence. Output only the revised plot."""
        
        for block in plots:
            # Find source concept for this plot
            source_content = ""
            deps = st.session_state.db.get_reverse_dependencies(block["id"])
            for dep in deps:
                if dep.get("type") == "concept_to_plot":
                    src_block = st.session_state.db.get_block(dep["src_block_id"])
                    if src_block:
                        source_content = src_block["content"]
                        break
            
            with st.expander(f"{block['type'].upper()}: {block['content'][:60]}...", expanded=True):
                render_block_with_feedback(
                    block=block,
                    block_type_name=f"Plot {block['type'].title()}",
                    revision_prompt_template=plot_revision_template,
                    source_content=source_content
                )


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
            format_func=lambda x: f"{x['type'].upper()}: {x['content'][:50]}...",
            key="scene_source_plot"
        )
        
        # Option to include creative notes for scene or dialogue
        scene_note = render_creative_notes_selector("scene", "scene_gen")
        dialogue_note = render_creative_notes_selector("dialogue", "scene_dialogue_gen")
        
        if st.button("✨ Generate Scene"):
            with st.spinner("Generating screenplay scene..."):
                prompt = f"""Write a screenplay scene based on this plot point.
Use proper screenplay format with scene headings (INT./EXT.), 
character names in caps, dialogue, and action descriptions.

Plot point:
{source_block['content']}"""
                if scene_note:
                    prompt += f"\n\nIncorporate this scene idea from the creator:\n{scene_note}"
                if dialogue_note:
                    prompt += f"\n\nInclude this specific dialogue from the creator:\n{dialogue_note}"
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
    
    # Display scenes with feedback mechanism
    if scenes:
        st.markdown("---")
        st.subheader("📑 Scenes")
        
        # Define revision prompt template for scenes
        scene_revision_template = """Revise the following screenplay scene based on the creator's notes.

ORIGINAL PLOT POINT:
{source}

CURRENT SCENE:
{content}

CREATOR'S NOTES/FEEDBACK:
{notes}

Please revise the scene to incorporate the feedback while maintaining proper screenplay format. Output only the revised scene."""
        
        for i, block in enumerate(scenes, 1):
            # Find source plot for this scene
            source_content = ""
            deps = st.session_state.db.get_reverse_dependencies(block["id"])
            for dep in deps:
                if dep.get("type") == "plot_to_scene":
                    src_block = st.session_state.db.get_block(dep["src_block_id"])
                    if src_block:
                        source_content = src_block["content"]
                        break
            
            with st.expander(f"Scene {i}: {block['content'][:50]}...", expanded=False):
                render_block_with_feedback(
                    block=block,
                    block_type_name="Scene",
                    revision_prompt_template=scene_revision_template,
                    source_content=source_content
                )


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
    
    # Option to include creative note for character
    char_note = render_creative_notes_selector("character", "char_gen")
    
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
                        if char_note:
                            prompt += f"\n\nIncorporate this character idea from the creator:\n{char_note}"
                        generated = st.session_state.ai.llm_generate_sync(prompt)
                        st.session_state.db.add_block(tab_id, "character", generated)
                        st.success("Character generated!")
                        st.rerun()
    
    # Display characters with feedback mechanism
    if characters:
        st.markdown("---")
        
        # Define revision prompt template for characters
        char_revision_template = """Revise the following character profile based on the creator's notes.

CURRENT CHARACTER:
{content}

CREATOR'S NOTES/FEEDBACK:
{notes}

Please revise the character to incorporate the feedback while maintaining consistency. Output only the revised character profile."""
        
        for block in characters:
            # Get first line of content as title
            first_line = block['content'].split('\n')[0]
            with st.expander(f"👤 {truncate_content(first_line)}", expanded=False):
                render_block_with_feedback(
                    block=block,
                    block_type_name="Character",
                    revision_prompt_template=char_revision_template
                )


def render_locations_section(tab_id: int):
    """Render the Locations section."""
    st.subheader("📍 Locations")
    st.markdown("Define the settings and locations for your movie.")
    
    blocks = st.session_state.db.get_blocks_by_tab(tab_id)
    locations = [b for b in blocks if b["type"] == "location"]
    
    # Option to include creative note for location
    loc_note = render_creative_notes_selector("location", "loc_gen")
    
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
                        if loc_note:
                            prompt += f"\n\nIncorporate this location idea from the creator:\n{loc_note}"
                        generated = st.session_state.ai.llm_generate_sync(prompt)
                        st.session_state.db.add_block(tab_id, "location", generated)
                        st.success("Location generated!")
                        st.rerun()
    
    # Display locations with feedback mechanism
    if locations:
        st.markdown("---")
        
        # Define revision prompt template for locations
        loc_revision_template = """Revise the following location description based on the creator's notes.

CURRENT LOCATION:
{content}

CREATOR'S NOTES/FEEDBACK:
{notes}

Please revise the location to incorporate the feedback while maintaining consistency. Output only the revised location description."""
        
        for block in locations:
            with st.expander(block["content"].split('\n')[0], expanded=False):
                render_block_with_feedback(
                    block=block,
                    block_type_name="Location",
                    revision_prompt_template=loc_revision_template
                )


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
    
    # Option to include creative note for visual style
    visual_note = render_creative_notes_selector("visual", "style_gen")
    
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
                        if visual_note:
                            prompt += f"\n\nIncorporate this visual idea from the creator:\n{visual_note}"
                        generated = st.session_state.ai.llm_generate_sync(prompt)
                        st.session_state.db.add_block(tab_id, "style_guide", generated)
                        st.success("Style guide generated!")
                        st.rerun()
    
    # Display styles with feedback mechanism
    if styles:
        st.markdown("---")
        
        # Define revision prompt template for style
        style_revision_template = """Revise the following visual style guide based on the creator's notes.

CURRENT STYLE:
{content}

CREATOR'S NOTES/FEEDBACK:
{notes}

Please revise the style guide to incorporate the feedback. Output only the revised style guide."""
        
        for block in styles:
            with st.expander(f"{block['type'].replace('_', ' ').title()}", expanded=False):
                render_block_with_feedback(
                    block=block,
                    block_type_name="Style Guide",
                    revision_prompt_template=style_revision_template
                )


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
            format_func=lambda x: f"{x['content'][:60]}...",
            key="shot_source_scene"
        )
        
        # Option to include creative note for shot
        shot_note = render_creative_notes_selector("shot", "shot_breakdown_gen")
        
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
                if shot_note:
                    prompt += f"\n\nIncorporate this specific shot idea from the creator:\n{shot_note}"
                shots = st.session_state.ai.llm_generate_sync(prompt)
                block_id = st.session_state.db.add_block(tab_id, "shot_breakdown", shots)
                st.session_state.db.add_dependency(source_scene["id"], block_id, "scene_to_shots")
                st.success("Shot breakdown generated!")
                st.rerun()
    else:
        st.info("Add scenes in the Story phase first.")
    
    # Display shot breakdowns with feedback mechanism
    blocks = st.session_state.db.get_blocks_by_tab(tab_id)
    breakdowns = [b for b in blocks if b["type"] == "shot_breakdown"]
    
    if breakdowns:
        st.markdown("---")
        st.subheader("Shot Breakdowns")
        
        # Define revision prompt template for shot breakdowns
        shot_revision_template = """Revise the following shot breakdown based on the creator's notes.

ORIGINAL SCENE:
{source}

CURRENT SHOT BREAKDOWN:
{content}

CREATOR'S NOTES/FEEDBACK:
{notes}

Please revise the shot breakdown to incorporate the feedback. Output only the revised shot breakdown."""
        
        for i, block in enumerate(breakdowns, 1):
            # Find source scene
            source_content = ""
            deps = st.session_state.db.get_reverse_dependencies(block["id"])
            for dep in deps:
                if dep.get("type") == "scene_to_shots":
                    src_block = st.session_state.db.get_block(dep["src_block_id"])
                    if src_block:
                        source_content = src_block["content"]
                        break
            
            with st.expander(f"Breakdown {i}", expanded=True):
                render_block_with_feedback(
                    block=block,
                    block_type_name="Shot Breakdown",
                    revision_prompt_template=shot_revision_template,
                    source_content=source_content
                )


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
    
    # Option to include creative note for shot
    shot_note = render_creative_notes_selector("shot", "shot_card_gen")
    
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
                        if shot_note:
                            prompt += f"\n\nIncorporate this specific shot idea from the creator:\n{shot_note}"
                        generated = st.session_state.ai.llm_generate_sync(prompt)
                        st.session_state.db.add_block(tab_id, "shot", generated)
                        st.success("Shot description generated!")
                        st.rerun()
    
    # Display shots with feedback mechanism
    if shots:
        st.markdown("---")
        st.subheader("🎬 Shot List")
        
        # Define revision prompt template for shots
        shot_card_revision_template = """Revise the following shot description based on the creator's notes.

CURRENT SHOT:
{content}

CREATOR'S NOTES/FEEDBACK:
{notes}

Please revise the shot description to incorporate the feedback. Output only the revised shot description."""
        
        for i, block in enumerate(shots, 1):
            with st.expander(f"Shot {i}: {block['content'][:50]}...", expanded=False):
                render_block_with_feedback(
                    block=block,
                    block_type_name="Shot Description",
                    revision_prompt_template=shot_card_revision_template
                )


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
                            # Store in session state for display and saving
                            st.session_state.generated_image_url = image_url
                            st.session_state.generated_image_prompt = prompt
                            st.session_state.generated_image_shot_id = selected_shot["id"]
                            st.success("Image generated!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Generation failed: {e}")

            # After generation, show image and save button if available
            if (
                "generated_image_url" in st.session_state
                and st.session_state.generated_image_url
                and "generated_image_shot_id" in st.session_state
                and st.session_state.generated_image_shot_id == selected_shot["id"]
            ):
                st.image(st.session_state.generated_image_url, caption="Generated Image")
                if st.button("💾 Save to Asset Library"):
                    try:
                        image_bytes = st.session_state.ai.download_asset(st.session_state.generated_image_url)
                        asset_id = st.session_state.asset_manager.store_asset_from_bytes(
                            image_bytes,
                            "generated.png",
                            st.session_state.project_id,
                            {
                                "source": "generated",
                                "shot_id": st.session_state.generated_image_shot_id,
                                "prompt": st.session_state.generated_image_prompt,
                            }
                        )
                        st.success(f"Saved as asset #{asset_id}")
                    except Exception as e:
                        st.error(f"Failed to save asset: {e}")
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
