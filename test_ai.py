# -*- coding: utf-8 -*-
"""Quick test for AIService"""
import asyncio
from bot.services.ai import AIService


async def test_ai():
    ai = AIService()
    print('[OK] AIService instantiated successfully')

    # Test that all key methods exist
    assert hasattr(ai, 'get_embeddings')
    assert hasattr(ai, 'get_gemini_model')
    assert hasattr(ai, 'summarize_cluster')
    print('[OK] All AI methods are accessible')

    # Test model initialization (doesn't make API call)
    model = ai.get_gemini_model()
    print(f'[OK] Gemini model loaded: {ai.generation_model_name}')

    print('\n[PASS] AI Service test completed successfully!')
    return True


if __name__ == '__main__':
    result = asyncio.run(test_ai())
    exit(0 if result else 1)
