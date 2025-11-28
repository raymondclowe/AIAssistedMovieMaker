"""AI Operations module for AI-Assisted Movie Maker.

This module provides the AIOperations class for making calls to
AI models (LLM, image generation, video generation, audio generation).

Supports:
- OpenRouter.ai for text/LLM generation
- Replicate.com for video and image generation
"""

import asyncio
import os
import time
from typing import Optional, List, Dict, Any
import httpx


# Price thresholds for model categorization (USD per token)
# Models are categorized into 3 tiers based on cost:
# - Draft: Cheap/free models for rapid iteration
# - Medium: Mid-range models for balanced quality/cost
# - Final: Premium models for best quality
DRAFT_PRICE_THRESHOLD = 0.001  # $0.001 per 1k tokens - below this is draft
MEDIUM_PRICE_THRESHOLD = 0.01  # $0.01 per 1k tokens - below this is medium, above is final

# Model name patterns that indicate draft/fast models
DRAFT_MODEL_PATTERNS = ["schnell", "turbo", "fast", "lite", "lightning"]

# Popularity thresholds for Replicate model categorization
# Video and image models are categorized by run_count since they don't have pricing info
# Higher run counts indicate more popular/established models (medium tier)
# Lower run counts include newer premium models (final tier)
VIDEO_MEDIUM_RUN_COUNT_THRESHOLD = 100000  # Video models with >100k runs are medium tier
IMAGE_MEDIUM_RUN_COUNT_THRESHOLD = 1000000  # Image models with >1M runs are medium tier


def get_api_key(primary_key: str, fallback_key: str) -> Optional[str]:
    """Get API key from environment, checking both primary and fallback names.
    
    Args:
        primary_key: Primary environment variable name.
        fallback_key: Fallback environment variable name (e.g., COPILOT_ prefixed).
    
    Returns:
        API key if found, None otherwise.
    """
    return os.getenv(primary_key) or os.getenv(fallback_key)


class OpenRouterProvider:
    """OpenRouter.ai provider for LLM text generation."""
    
    BASE_URL = "https://openrouter.ai/api/v1"
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize OpenRouter provider.
        
        Args:
            api_key: OpenRouter API key (optional, will check env if not provided).
        """
        self.api_key = api_key or get_api_key("OPENROUTER_API_KEY", "COPILOT_OPENROUTER_API_KEY")
        self._models_cache = None
        self._models_cache_time = 0
        self._cache_ttl = 300  # 5 minutes cache
    
    def set_api_key(self, api_key: str):
        """Set the API key at runtime.
        
        Args:
            api_key: OpenRouter API key.
        
        Raises:
            ValueError: If api_key is empty or contains only whitespace.
        """
        if not api_key or not api_key.strip():
            raise ValueError("API key cannot be empty")
        self.api_key = api_key.strip()
        # Clear cache when key changes
        self._models_cache = None
        self._models_cache_time = 0
    
    def is_configured(self) -> bool:
        """Check if the provider is properly configured."""
        return self.api_key is not None
    
    def get_models(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Fetch available models from OpenRouter.
        
        Args:
            force_refresh: Force refresh the cache.
            
        Returns:
            List of model dictionaries with id, name, pricing, etc.
        """
        if not self.is_configured():
            return []
        
        # Return cached if valid
        if not force_refresh and self._models_cache and (time.time() - self._models_cache_time < self._cache_ttl):
            return self._models_cache
        
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(
                    f"{self.BASE_URL}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                response.raise_for_status()
                data = response.json()
                self._models_cache = data.get("data", [])
                self._models_cache_time = time.time()
                return self._models_cache
        except Exception as e:
            print(f"Error fetching OpenRouter models: {e}")
            return []
    
    def get_models_by_category(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get models organized by cost category (draft, medium, final).
        
        Returns:
            Dictionary with 'draft', 'medium', and 'final' model lists.
        """
        models = self.get_models()
        
        draft_models = []
        medium_models = []
        final_models = []
        
        for model in models:
            model_id = model.get("id", "")
            pricing = model.get("pricing", {})
            prompt_price = float(pricing.get("prompt", "0") or "0")
            
            model_info = {
                "id": model_id,
                "name": model.get("name", model_id),
                "context_length": model.get("context_length", 4096),
                "prompt_price": prompt_price,
                "description": model.get("description", "")
            }
            
            # Categorize by price threshold into 3 tiers
            if prompt_price < DRAFT_PRICE_THRESHOLD:
                draft_models.append(model_info)
            elif prompt_price < MEDIUM_PRICE_THRESHOLD:
                medium_models.append(model_info)
            else:
                final_models.append(model_info)
        
        # Sort by price
        draft_models.sort(key=lambda x: x["prompt_price"])
        medium_models.sort(key=lambda x: x["prompt_price"])
        final_models.sort(key=lambda x: x["prompt_price"])
        
        return {"draft": draft_models, "medium": medium_models, "final": final_models}
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: str = "meta-llama/llama-3.2-3b-instruct:free",
        max_tokens: int = 4096,
        temperature: float = 0.7
    ) -> str:
        """Generate text using OpenRouter.
        
        Args:
            prompt: User prompt.
            system_prompt: System prompt (optional).
            model: Model ID to use.
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature.
            
        Returns:
            Generated text.
        """
        if not self.is_configured():
            raise RuntimeError("OpenRouter API key not configured")
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    f"{self.BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://github.com/raymondclowe/AIAssistedMovieMaker",
                        "X-Title": "AI Movie Maker"
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        "max_tokens": max_tokens,
                        "temperature": temperature
                    }
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"OpenRouter API error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise RuntimeError(f"OpenRouter generation failed: {e}")


class ReplicateProvider:
    """Replicate.com provider for image and video generation."""
    
    BASE_URL = "https://api.replicate.com/v1"
    
    # Default models for different tasks
    DEFAULT_VIDEO_MODEL = "minimax/video-01"
    DEFAULT_IMAGE_MODEL = "black-forest-labs/flux-schnell"
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Replicate provider.
        
        Args:
            api_key: Replicate API key (optional, will check env if not provided).
        """
        self.api_key = api_key or get_api_key("REPLICATE_API_KEY", "COPILOT_REPLICATE_API_KEY")
        self._models_cache = {}
        self._models_cache_time = {}
        self._cache_ttl = 300  # 5 minutes cache
    
    def set_api_key(self, api_key: str):
        """Set the API key at runtime.
        
        Args:
            api_key: Replicate API key.
        
        Raises:
            ValueError: If api_key is empty or contains only whitespace.
        """
        if not api_key or not api_key.strip():
            raise ValueError("API key cannot be empty")
        self.api_key = api_key.strip()
        # Clear cache when key changes
        self._models_cache = {}
        self._models_cache_time = {}
    
    def is_configured(self) -> bool:
        """Check if the provider is properly configured."""
        return self.api_key is not None
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for Replicate API requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def get_models(self, collection: str = "text-to-video", force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Fetch available models from Replicate collections.
        
        Args:
            collection: Collection name (e.g., 'text-to-video', 'text-to-image').
            force_refresh: Force refresh the cache.
            
        Returns:
            List of model dictionaries.
        """
        if not self.is_configured():
            return []
        
        cache_key = collection
        if not force_refresh and cache_key in self._models_cache:
            if time.time() - self._models_cache_time.get(cache_key, 0) < self._cache_ttl:
                return self._models_cache[cache_key]
        
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(
                    f"{self.BASE_URL}/collections/{collection}",
                    headers=self._get_headers()
                )
                response.raise_for_status()
                data = response.json()
                models = data.get("models", [])
                self._models_cache[cache_key] = models
                self._models_cache_time[cache_key] = time.time()
                return models
        except Exception as e:
            print(f"Error fetching Replicate models for {collection}: {e}")
            return []
    
    def get_video_models(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get video generation models organized by quality tier.
        
        Returns:
            Dictionary with 'draft', 'medium', and 'final' model lists.
        """
        models = self.get_models("text-to-video")
        
        draft_models = []
        medium_models = []
        final_models = []
        
        for model in models:
            owner = model.get("owner", "")
            name = model.get("name", "")
            model_id = f"{owner}/{name}"
            
            model_info = {
                "id": model_id,
                "name": model.get("name", model_id),
                "description": model.get("description", ""),
                "run_count": model.get("run_count", 0)
            }
            
            # Categorize by name patterns using shared constant
            is_draft = any(pattern in name.lower() for pattern in DRAFT_MODEL_PATTERNS)
            
            if is_draft:
                draft_models.append(model_info)
            else:
                # For video models without clear draft patterns, split by popularity
                # High run_count models go to medium, lower to final (premium/newer)
                run_count = model.get("run_count", 0)
                if run_count > VIDEO_MEDIUM_RUN_COUNT_THRESHOLD:
                    medium_models.append(model_info)
                else:
                    final_models.append(model_info)
        
        # Sort by popularity (run_count)
        draft_models.sort(key=lambda x: x.get("run_count", 0), reverse=True)
        medium_models.sort(key=lambda x: x.get("run_count", 0), reverse=True)
        final_models.sort(key=lambda x: x.get("run_count", 0), reverse=True)
        
        return {"draft": draft_models, "medium": medium_models, "final": final_models}
    
    def get_image_models(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get image generation models organized by quality tier.
        
        Returns:
            Dictionary with 'draft', 'medium', and 'final' model lists.
        """
        models = self.get_models("text-to-image")
        
        draft_models = []
        medium_models = []
        final_models = []
        
        for model in models:
            owner = model.get("owner", "")
            name = model.get("name", "")
            model_id = f"{owner}/{name}"
            
            model_info = {
                "id": model_id,
                "name": model.get("name", model_id),
                "description": model.get("description", ""),
                "run_count": model.get("run_count", 0)
            }
            
            # Categorize by name patterns using shared constant
            is_draft = any(pattern in name.lower() for pattern in DRAFT_MODEL_PATTERNS)
            
            if is_draft:
                draft_models.append(model_info)
            else:
                # For image models without clear draft patterns, split by popularity
                # High run_count models go to medium, lower to final (premium/newer)
                run_count = model.get("run_count", 0)
                if run_count > IMAGE_MEDIUM_RUN_COUNT_THRESHOLD:
                    medium_models.append(model_info)
                else:
                    final_models.append(model_info)
        
        # Sort by popularity (run_count)
        draft_models.sort(key=lambda x: x.get("run_count", 0), reverse=True)
        medium_models.sort(key=lambda x: x.get("run_count", 0), reverse=True)
        final_models.sort(key=lambda x: x.get("run_count", 0), reverse=True)
        
        return {"draft": draft_models, "medium": medium_models, "final": final_models}
    
    def _wait_for_prediction(self, prediction_url: str, timeout: int = 300) -> Dict[str, Any]:
        """Wait for a Replicate prediction to complete.
        
        Args:
            prediction_url: URL to poll for prediction status.
            timeout: Maximum time to wait in seconds.
            
        Returns:
            Completed prediction data.
        """
        start_time = time.time()
        
        with httpx.Client(timeout=30.0) as client:
            while time.time() - start_time < timeout:
                response = client.get(prediction_url, headers=self._get_headers())
                response.raise_for_status()
                prediction = response.json()
                
                status = prediction.get("status")
                if status == "succeeded":
                    return prediction
                elif status == "failed":
                    error = prediction.get("error", "Unknown error")
                    raise RuntimeError(f"Prediction failed: {error}")
                elif status == "canceled":
                    raise RuntimeError("Prediction was canceled")
                
                # Wait before polling again
                time.sleep(2)
        
        raise RuntimeError(f"Prediction timed out after {timeout} seconds")
    
    def generate_video(
        self,
        prompt: str,
        model: Optional[str] = None,
        **kwargs
    ) -> str:
        """Generate a video using Replicate.
        
        Args:
            prompt: Text prompt for video generation.
            model: Model ID to use (optional, uses default if not provided).
            **kwargs: Additional model-specific parameters.
            
        Returns:
            URL of the generated video.
        """
        if not self.is_configured():
            raise RuntimeError("Replicate API key not configured")
        
        model = model or self.DEFAULT_VIDEO_MODEL
        
        # Prepare input based on model
        model_input = {"prompt": prompt}
        model_input.update(kwargs)
        
        try:
            with httpx.Client(timeout=30.0) as client:
                # Create prediction
                # Replicate accepts either 'model' (owner/name) or 'version' (full hash)
                # We use 'model' for official models without version specification
                response = client.post(
                    f"{self.BASE_URL}/predictions",
                    headers=self._get_headers(),
                    json={
                        "model": model,
                        "input": model_input
                    }
                )
                response.raise_for_status()
                prediction = response.json()
                
                # Wait for completion
                prediction_url = prediction.get("urls", {}).get("get")
                if not prediction_url:
                    prediction_url = f"{self.BASE_URL}/predictions/{prediction['id']}"
                
                result = self._wait_for_prediction(prediction_url)
                output = result.get("output")
                
                if isinstance(output, list):
                    return output[0] if output else None
                return output
                
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Replicate API error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise RuntimeError(f"Video generation failed: {e}")
    
    def generate_image(
        self,
        prompt: str,
        model: Optional[str] = None,
        **kwargs
    ) -> str:
        """Generate an image using Replicate.
        
        Args:
            prompt: Text prompt for image generation.
            model: Model ID to use (optional, uses default if not provided).
            **kwargs: Additional model-specific parameters.
            
        Returns:
            URL of the generated image.
        """
        if not self.is_configured():
            raise RuntimeError("Replicate API key not configured")
        
        model = model or self.DEFAULT_IMAGE_MODEL
        
        # Prepare input based on model
        model_input = {"prompt": prompt}
        model_input.update(kwargs)
        
        try:
            with httpx.Client(timeout=30.0) as client:
                # Create prediction
                # Replicate accepts either 'model' (owner/name) or 'version' (full hash)
                # We use 'model' for official models without version specification
                response = client.post(
                    f"{self.BASE_URL}/predictions",
                    headers=self._get_headers(),
                    json={
                        "model": model,
                        "input": model_input
                    }
                )
                response.raise_for_status()
                prediction = response.json()
                
                # Wait for completion
                prediction_url = prediction.get("urls", {}).get("get")
                if not prediction_url:
                    prediction_url = f"{self.BASE_URL}/predictions/{prediction['id']}"
                
                result = self._wait_for_prediction(prediction_url, timeout=120)
                output = result.get("output")
                
                if isinstance(output, list):
                    return output[0] if output else None
                return output
                
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Replicate API error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise RuntimeError(f"Image generation failed: {e}")


class AIOperations:
    """AI operations manager for LLM and generation tasks.
    
    Supports multiple providers:
    - OpenRouter for text generation
    - Replicate for image and video generation
    """
    
    # Default models for each quality tier
    DEFAULT_LLM_MODELS = {
        "draft": "meta-llama/llama-3.2-3b-instruct:free",
        "medium": "openai/gpt-4o",
        "final": "anthropic/claude-sonnet-4"
    }

    def __init__(
        self,
        openrouter_key: Optional[str] = None,
        replicate_key: Optional[str] = None,
        mode: str = "draft"
    ):
        """Initialize AI operations.

        Args:
            openrouter_key: OpenRouter API key (optional, will check env).
            replicate_key: Replicate API key (optional, will check env).
            mode: Generation mode - "draft" for cheap/fast, "medium" for balanced, "final" for best quality.
        """
        self.openrouter = OpenRouterProvider(openrouter_key)
        self.replicate = ReplicateProvider(replicate_key)
        self.mode = mode
        
        # Selected models (can be overridden)
        self._selected_llm_model = None
        self._selected_image_model = None
        self._selected_video_model = None
        
        # Track last used model for diagnostics/repeatability
        self._last_used_llm_model = None
        self._last_used_image_model = None
        self._last_used_video_model = None
    
    def get_last_used_model(self, model_type: str = "llm") -> Optional[str]:
        """Get the last model used for a specific type.
        
        Args:
            model_type: Type of model - "llm", "image", or "video"
            
        Returns:
            The model ID that was last used, or None if not available.
        """
        if model_type == "llm":
            return self._last_used_llm_model
        elif model_type == "image":
            return self._last_used_image_model
        elif model_type == "video":
            return self._last_used_video_model
        return None
    
    def is_configured(self) -> bool:
        """Check if any provider is configured."""
        return self.openrouter.is_configured() or self.replicate.is_configured()
    
    def get_status(self) -> Dict[str, bool]:
        """Get configuration status for each provider."""
        return {
            "openrouter": self.openrouter.is_configured(),
            "replicate": self.replicate.is_configured()
        }
    
    def set_openrouter_key(self, api_key: str):
        """Set the OpenRouter API key at runtime.
        
        Args:
            api_key: OpenRouter API key.
        """
        self.openrouter.set_api_key(api_key)
        # Reset model selection
        self._selected_llm_model = None
    
    def set_replicate_key(self, api_key: str):
        """Set the Replicate API key at runtime.
        
        Args:
            api_key: Replicate API key.
        """
        self.replicate.set_api_key(api_key)
        # Reset model selections
        self._selected_image_model = None
        self._selected_video_model = None
    
    def set_mode(self, mode: str):
        """Set the generation mode.
        
        Args:
            mode: "draft" for cheap/fast models, "medium" for balanced, "final" for best quality.
        """
        if mode not in ("draft", "medium", "final"):
            raise ValueError("Mode must be 'draft', 'medium', or 'final'")
        self.mode = mode
    
    def get_available_llm_models(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get available LLM models from OpenRouter."""
        return self.openrouter.get_models_by_category()
    
    def get_available_image_models(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get available image generation models from Replicate."""
        return self.replicate.get_image_models()
    
    def get_available_video_models(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get available video generation models from Replicate."""
        return self.replicate.get_video_models()
    
    def set_llm_model(self, model_id: str):
        """Set the LLM model to use."""
        self._selected_llm_model = model_id
    
    def set_image_model(self, model_id: str):
        """Set the image generation model to use."""
        self._selected_image_model = model_id
    
    def set_video_model(self, model_id: str):
        """Set the video generation model to use."""
        self._selected_video_model = model_id
    
    def _get_default_llm_model(self) -> str:
        """Get default LLM model based on mode."""
        # Use predefined defaults for each tier
        return self.DEFAULT_LLM_MODELS.get(self.mode, self.DEFAULT_LLM_MODELS["draft"])
    
    def llm_generate_sync(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7
    ) -> str:
        """Synchronous text generation using OpenRouter.

        Args:
            prompt: User prompt.
            system_prompt: System prompt (optional).
            model: Model ID (optional, uses selected or default).
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature.

        Returns:
            Generated text.
        """
        if not self.openrouter.is_configured():
            # Return mock response if no API key
            self._last_used_llm_model = "mock"
            return self._mock_llm_response(prompt)
        
        model = model or self._selected_llm_model or self._get_default_llm_model()
        # Track the model used for diagnostics/repeatability
        self._last_used_llm_model = model
        
        return self.openrouter.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature
        )
    
    async def llm_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7
    ) -> str:
        """Async text generation using asyncio.to_thread for non-blocking execution.

        Args:
            prompt: User prompt.
            system_prompt: System prompt (optional).
            model: Model ID (optional).
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature.

        Returns:
            Generated text.
        """
        return await asyncio.to_thread(
            self.llm_generate_sync,
            prompt,
            system_prompt,
            model,
            max_tokens,
            temperature
        )

    def _mock_llm_response(self, prompt: str) -> str:
        """Generate a mock response when no API key is available.

        Args:
            prompt: The prompt.

        Returns:
            Mock response text.
        """
        prompt_lower = prompt.lower()

        if "plot" in prompt_lower or "outline" in prompt_lower:
            return """# 5-Act Outline

## Act 1: Setup
- Introduction of main characters
- Establishing the world and setting
- The inciting incident that sets the story in motion

## Act 2: Rising Action
- The protagonist faces initial obstacles
- Character development and relationships deepen
- Stakes begin to rise

## Act 3: Midpoint
- A major revelation or twist
- The protagonist's approach changes
- New alliances or enemies emerge

## Act 4: Climax Approach
- Tensions reach their peak
- The protagonist faces their greatest challenge
- All subplots begin to converge

## Act 5: Resolution
- The final confrontation
- Resolution of main conflict
- New equilibrium established

*Note: This is a placeholder outline. Set OPENROUTER_API_KEY for AI-generated content.*"""

        elif "scene" in prompt_lower or "screenplay" in prompt_lower:
            return """INT. COFFEE SHOP - DAY

The camera pans across a cozy coffee shop. DETECTIVE JANE DOE (40s, sharp eyes) sits alone at a corner table, studying a case file.

JANE
(to herself)
Something doesn't add up...

A BARISTA (20s, friendly) approaches with a fresh cup.

BARISTA
Refill?

JANE
(looking up)
Thanks. Say, you work the morning shift, right?

BARISTA
Every day. Why?

Jane slides a photograph across the table.

JANE
Ever see this person?

The Barista's expression changes. Recognition.

BARISTA
(nervous)
I... I think I need to check on something in the back.

Jane watches as the Barista hurries away. She makes a note in her file.

*Note: This is a placeholder scene. Set OPENROUTER_API_KEY for AI-generated content.*"""

        elif "character" in prompt_lower or "cast" in prompt_lower:
            return """# Character Profile

**Name:** Detective Jane Doe
**Age:** 45
**Occupation:** Homicide Detective
**Physical Description:** Tall, athletic build, short gray hair, piercing blue eyes

## Background
- 20 years on the force
- Previously worked undercover
- Lost her partner in a case gone wrong

## Personality Traits
- Analytical and methodical
- Struggles with trust
- Dry sense of humor
- Dedicated to justice

## Motivation
Finding the truth, no matter where it leads

*Note: This is a placeholder character. Set OPENROUTER_API_KEY for AI-generated content.*"""

        elif "location" in prompt_lower:
            return """# Location Description

**Name:** The Midnight Express
**Type:** Moving Train
**Era:** Contemporary

## Physical Details
- Luxury sleeper train
- Art deco interior design
- Dimly lit corridors
- Private compartments with velvet seats

## Atmosphere
- Mysterious and claustrophobic
- The constant rhythm of wheels on tracks
- Occasional tunnel darkness
- Elegant but tense ambiance

## Key Areas
1. Dining car - where passengers gather
2. Observation car - panoramic windows
3. Sleeper compartments - private spaces
4. Service areas - staff only

*Note: This is a placeholder location. Set OPENROUTER_API_KEY for AI-generated content.*"""

        elif "shot" in prompt_lower or "cinematography" in prompt_lower:
            return """# Shot Description

**Scene:** Opening sequence
**Shot Type:** Establishing wide shot

## Technical Specifications
- Lens: 24mm wide angle
- Movement: Slow dolly forward
- Duration: 8 seconds

## Composition
- Train station at dusk
- Steam rising from the platform
- Silhouettes of passengers boarding
- Warm light from train windows contrasting with blue hour sky

## Lighting
- Natural light (magic hour)
- Practical lights from train
- Soft shadows

## Notes
This shot sets the mood and establishes the setting before we cut to our protagonist.

*Note: This is a placeholder shot. Set OPENROUTER_API_KEY for AI-generated content.*"""

        else:
            return f"""# AI Response

Thank you for your prompt. Here's a response to: "{prompt[:100]}..."

This is a placeholder response. To get actual AI-generated content, please:

1. Set your OpenRouter API key: `OPENROUTER_API_KEY`
2. Set your Replicate API key: `REPLICATE_API_KEY`

Once configured, the app will use live AI models for content generation.

*Note: This is a placeholder. Set API keys for AI-generated content.*"""

    def generate_image_sync(
        self,
        prompt: str,
        model: Optional[str] = None,
        **kwargs
    ) -> str:
        """Generate an image using Replicate.

        Args:
            prompt: Image prompt.
            model: Model ID (optional, uses selected or default).
            **kwargs: Additional model-specific parameters.

        Returns:
            URL of the generated image.
        """
        if not self.replicate.is_configured():
            raise RuntimeError(
                "Replicate API key not configured. "
                "Set REPLICATE_API_KEY environment variable."
            )
        
        model = model or self._selected_image_model
        # Track the model used for diagnostics/repeatability
        self._last_used_image_model = model
        return self.replicate.generate_image(prompt=prompt, model=model, **kwargs)
    
    async def generate_image(
        self,
        prompt: str,
        model: Optional[str] = None,
        **kwargs
    ) -> str:
        """Generate an image using asyncio.to_thread for non-blocking execution.

        Args:
            prompt: Image prompt.
            model: Model ID (optional).
            **kwargs: Additional model-specific parameters.

        Returns:
            URL of the generated image.
        """
        return await asyncio.to_thread(
            self.generate_image_sync,
            prompt,
            model,
            **kwargs
        )
    
    def generate_video_sync(
        self,
        prompt: str,
        model: Optional[str] = None,
        **kwargs
    ) -> str:
        """Generate a video using Replicate.

        Args:
            prompt: Video prompt.
            model: Model ID (optional, uses selected or default).
            **kwargs: Additional model-specific parameters.

        Returns:
            URL of the generated video.
        """
        if not self.replicate.is_configured():
            raise RuntimeError(
                "Replicate API key not configured. "
                "Set REPLICATE_API_KEY environment variable."
            )
        
        model = model or self._selected_video_model
        # Track the model used for diagnostics/repeatability
        self._last_used_video_model = model
        return self.replicate.generate_video(prompt=prompt, model=model, **kwargs)
    
    async def generate_video(
        self,
        prompt: str,
        model: Optional[str] = None,
        **kwargs
    ) -> str:
        """Generate a video using asyncio.to_thread for non-blocking execution.

        Args:
            prompt: Video prompt.
            model: Model ID (optional).
            **kwargs: Additional model-specific parameters.

        Returns:
            URL of the generated video.
        """
        return await asyncio.to_thread(
            self.generate_video_sync,
            prompt,
            model,
            **kwargs
        )
    
    def download_asset(self, url: str) -> bytes:
        """Download an asset from a URL.
        
        Args:
            url: URL of the asset to download.
            
        Returns:
            Asset bytes.
        """
        with httpx.Client(timeout=60.0) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.content
