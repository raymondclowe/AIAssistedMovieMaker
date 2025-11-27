"""AI Operations module for AI-Assisted Movie Maker.

This module provides the AIOperations class for making calls to
AI models (LLM, image generation, video generation, audio generation).
"""

import os
from typing import Optional


class AIOperations:
    """AI operations manager for LLM and generation tasks."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize AI operations.

        Args:
            api_key: OpenAI API key (optional, will check env if not provided).
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._client = None

    def _get_client(self):
        """Get or create OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "OpenAI package not installed. "
                    "Install with: pip install openai"
                )
            except Exception as e:
                raise RuntimeError(f"Failed to initialize OpenAI client: {e}")
        return self._client

    async def llm_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: str = "gpt-4o",
        max_tokens: int = 4096,
        temperature: float = 0.7
    ) -> str:
        """Generate text using LLM.

        Args:
            prompt: User prompt.
            system_prompt: System prompt (optional).
            model: Model name.
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature.

        Returns:
            Generated text.
        """
        if not self.api_key:
            # Return mock response if no API key
            return self._mock_llm_response(prompt)

        try:
            client = self._get_client()
            messages = []

            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            messages.append({"role": "user", "content": prompt})

            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )

            return response.choices[0].message.content

        except Exception as e:
            raise RuntimeError(f"LLM generation failed: {e}")

    def llm_generate_sync(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: str = "gpt-4o",
        max_tokens: int = 4096,
        temperature: float = 0.7
    ) -> str:
        """Synchronous version of llm_generate.

        Args:
            prompt: User prompt.
            system_prompt: System prompt (optional).
            model: Model name.
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature.

        Returns:
            Generated text.
        """
        if not self.api_key:
            # Return mock response if no API key
            return self._mock_llm_response(prompt)

        try:
            client = self._get_client()
            messages = []

            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            messages.append({"role": "user", "content": prompt})

            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )

            return response.choices[0].message.content

        except Exception as e:
            raise RuntimeError(f"LLM generation failed: {e}")

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

*Note: This is a placeholder outline. Connect your OpenAI API key for AI-generated content.*"""

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

*Note: This is a placeholder scene. Connect your OpenAI API key for AI-generated content.*"""

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

*Note: This is a placeholder character. Connect your OpenAI API key for AI-generated content.*"""

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

*Note: This is a placeholder location. Connect your OpenAI API key for AI-generated content.*"""

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

*Note: This is a placeholder shot description. Connect your OpenAI API key for AI-generated content.*"""

        else:
            return f"""# AI Response

Thank you for your prompt. Here's a response to: "{prompt[:100]}..."

This is a placeholder response. To get actual AI-generated content, please:

1. Set your OpenAI API key in the environment variable `OPENAI_API_KEY`
2. Or pass it when initializing the AIOperations class

Once configured, the app will use GPT-4o to generate creative content for your movie project.

*Note: The AI features of this app require a valid OpenAI API key.*"""

    async def generate_image(
        self,
        prompt: str,
        size: str = "1024x1024",
        quality: str = "standard",
        style: str = "natural"
    ) -> bytes:
        """Generate an image using DALL-E.

        Args:
            prompt: Image prompt.
            size: Image size (1024x1024, 1792x1024, or 1024x1792).
            quality: Quality (standard or hd).
            style: Style (natural or vivid).

        Returns:
            Image bytes.
        """
        if not self.api_key:
            raise RuntimeError(
                "No API key configured. "
                "Set OPENAI_API_KEY environment variable."
            )

        try:
            import httpx
            client = self._get_client()

            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size=size,
                quality=quality,
                style=style,
                n=1,
                response_format="url"
            )

            # Download the image
            image_url = response.data[0].url
            async with httpx.AsyncClient() as http_client:
                img_response = await http_client.get(image_url)
                return img_response.content

        except Exception as e:
            raise RuntimeError(f"Image generation failed: {e}")

    def generate_image_sync(
        self,
        prompt: str,
        size: str = "1024x1024",
        quality: str = "standard",
        style: str = "natural"
    ) -> bytes:
        """Synchronous version of generate_image.

        Args:
            prompt: Image prompt.
            size: Image size.
            quality: Quality.
            style: Style.

        Returns:
            Image bytes.
        """
        if not self.api_key:
            raise RuntimeError(
                "No API key configured. "
                "Set OPENAI_API_KEY environment variable."
            )

        try:
            import httpx
            client = self._get_client()

            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size=size,
                quality=quality,
                style=style,
                n=1,
                response_format="url"
            )

            # Download the image
            image_url = response.data[0].url
            with httpx.Client() as http_client:
                img_response = http_client.get(image_url)
                return img_response.content

        except Exception as e:
            raise RuntimeError(f"Image generation failed: {e}")
