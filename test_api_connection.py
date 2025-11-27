#!/usr/bin/env python3
"""Test script for verifying OpenRouter and Replicate API connections.

Run this script with the appropriate API keys set in the environment:
    OPENROUTER_API_KEY or COPILOT_OPENROUTER_API_KEY
    REPLICATE_API_KEY or COPILOT_REPLICATE_API_KEY
"""

import os
import sys

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.ai import AIOperations, OpenRouterProvider, ReplicateProvider, get_api_key


def test_openrouter_connection():
    """Test OpenRouter API connection and model listing."""
    print("\n" + "=" * 50)
    print("OPENROUTER API TEST")
    print("=" * 50)
    
    key = get_api_key('OPENROUTER_API_KEY', 'COPILOT_OPENROUTER_API_KEY')
    if not key:
        print("❌ No OpenRouter API key found")
        print("   Set OPENROUTER_API_KEY or COPILOT_OPENROUTER_API_KEY")
        return False
    
    print(f"✅ OpenRouter API key found (length: {len(key)})")
    
    provider = OpenRouterProvider(key)
    
    # Test model listing
    print("\n--- Fetching Models ---")
    try:
        models = provider.get_models()
        print(f"✅ Retrieved {len(models)} models from OpenRouter")
        
        # Get categorized models
        categorized = provider.get_models_by_category()
        draft_count = len(categorized.get('draft', []))
        final_count = len(categorized.get('final', []))
        print(f"   Draft models: {draft_count}")
        print(f"   Final models: {final_count}")
        
        # Show a few example models
        if categorized.get('draft'):
            print(f"\n   Example draft models:")
            for m in categorized['draft'][:3]:
                print(f"   - {m['id']}")
        
        if categorized.get('final'):
            print(f"\n   Example final models:")
            for m in categorized['final'][:3]:
                print(f"   - {m['id']}")
                
    except Exception as e:
        print(f"❌ Failed to fetch models: {e}")
        return False
    
    # Test generation with a cheap model
    print("\n--- Testing Text Generation ---")
    try:
        # Use a free/cheap model
        test_model = "meta-llama/llama-3.2-3b-instruct:free"
        print(f"   Using model: {test_model}")
        
        response = provider.generate(
            prompt="Write a one-sentence movie logline about a detective.",
            model=test_model,
            max_tokens=100
        )
        print(f"✅ Generation successful!")
        print(f"   Response: {response[:200]}..." if len(response) > 200 else f"   Response: {response}")
        return True
        
    except Exception as e:
        print(f"❌ Generation failed: {e}")
        return False


def test_replicate_connection():
    """Test Replicate API connection and model listing."""
    print("\n" + "=" * 50)
    print("REPLICATE API TEST")
    print("=" * 50)
    
    key = get_api_key('REPLICATE_API_KEY', 'COPILOT_REPLICATE_API_KEY')
    if not key:
        print("❌ No Replicate API key found")
        print("   Set REPLICATE_API_KEY or COPILOT_REPLICATE_API_KEY")
        return False
    
    print(f"✅ Replicate API key found (length: {len(key)})")
    
    provider = ReplicateProvider(key)
    
    # Test model listing for images
    print("\n--- Fetching Image Models ---")
    try:
        image_models = provider.get_image_models()
        draft_count = len(image_models.get('draft', []))
        final_count = len(image_models.get('final', []))
        print(f"✅ Retrieved image models")
        print(f"   Draft models: {draft_count}")
        print(f"   Final models: {final_count}")
        
        if image_models.get('draft'):
            print(f"\n   Example draft image models:")
            for m in image_models['draft'][:3]:
                print(f"   - {m['id']}")
                
    except Exception as e:
        print(f"❌ Failed to fetch image models: {e}")
    
    # Test model listing for videos
    print("\n--- Fetching Video Models ---")
    try:
        video_models = provider.get_video_models()
        draft_count = len(video_models.get('draft', []))
        final_count = len(video_models.get('final', []))
        print(f"✅ Retrieved video models")
        print(f"   Draft models: {draft_count}")
        print(f"   Final models: {final_count}")
        
        if video_models.get('final'):
            print(f"\n   Example video models:")
            for m in video_models['final'][:3]:
                print(f"   - {m['id']}")
                
    except Exception as e:
        print(f"❌ Failed to fetch video models: {e}")
    
    return True


def test_ai_operations():
    """Test the unified AIOperations class."""
    print("\n" + "=" * 50)
    print("UNIFIED AI OPERATIONS TEST")
    print("=" * 50)
    
    ai = AIOperations()
    status = ai.get_status()
    
    print(f"\nProvider Status: {status}")
    print(f"Is Configured: {ai.is_configured()}")
    
    if ai.openrouter.is_configured():
        print("\n--- Testing LLM Generation via AIOperations ---")
        try:
            response = ai.llm_generate_sync(
                prompt="Write a one-sentence movie tagline about time travel.",
                max_tokens=50
            )
            print(f"✅ LLM Generation successful!")
            print(f"   Response: {response}")
        except Exception as e:
            print(f"❌ LLM Generation failed: {e}")
    
    return True


def main():
    print("=" * 50)
    print("AI API CONNECTION TEST")
    print("=" * 50)
    print("\nThis script tests the OpenRouter and Replicate API connections.")
    print("Make sure to set the appropriate environment variables.")
    
    openrouter_ok = test_openrouter_connection()
    replicate_ok = test_replicate_connection()
    test_ai_operations()
    
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"OpenRouter: {'✅ PASS' if openrouter_ok else '❌ FAIL'}")
    print(f"Replicate:  {'✅ PASS' if replicate_ok else '❌ FAIL'}")
    
    return 0 if (openrouter_ok and replicate_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
