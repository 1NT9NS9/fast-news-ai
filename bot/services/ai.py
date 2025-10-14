# -*- coding: utf-8 -*-
"""
AI Service

Handles all AI-related operations:
- Text embeddings generation using Google's text-embedding-004
- AI-powered summarization using Gemini Flash Lite
- Batch processing and parallel summarization
- Rate limiting and retry logic
"""

import asyncio
import re
from typing import List, Dict
import numpy as np
import google.generativeai as genai

from bot.utils.config import GEMINI_API, GEMINI_CONCURRENT_LIMIT
from bot.utils.logger import setup_logging

logger, _ = setup_logging()


class AIService:
    """Manages AI operations for embeddings and content generation."""

    def __init__(self):
        # Configure Google Generative AI
        genai.configure(api_key=GEMINI_API)

        # Embedding model configuration
        self.embedding_model = "models/text-embedding-004"
        self.embedding_task_type = "retrieval_document"
        self.embedding_batch_size = 100  # Google API allows up to 100 per batch

        # Generation model configuration
        self.generation_model_name = "gemini-flash-lite-latest"
        self._gemini_model = None  # Cached model instance

        # Rate limiting
        self._gemini_semaphore = asyncio.Semaphore(GEMINI_CONCURRENT_LIMIT)

        # Retry configuration
        self.default_retry_count = 3
        self.max_retry_delay = 30  # seconds

        # Generation parameters
        self.generation_config = genai.types.GenerationConfig(
            temperature=0.3,
            max_output_tokens=500,
        )

        # Safety settings (less restrictive to avoid blocking legitimate news)
        self.safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]

    # ========================================================================
    # Embedding Operations
    # ========================================================================

    async def get_embeddings(self, texts: List[str]) -> List[np.ndarray]:
        """
        Get embeddings for a list of texts using Google's text-embedding model.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors (numpy arrays)
        """
        if not texts:
            return []

        try:
            embeddings = []

            # Run embedding calls in thread pool to avoid blocking event loop
            loop = asyncio.get_event_loop()

            for i in range(0, len(texts), self.embedding_batch_size):
                batch = texts[i:i + self.embedding_batch_size]

                # Use Google's embedding model in executor to prevent blocking
                result = await loop.run_in_executor(
                    None,
                    lambda b=batch: genai.embed_content(
                        model=self.embedding_model,
                        content=b,
                        task_type=self.embedding_task_type
                    )
                )

                # Extract embeddings from result
                for embedding in result['embedding']:
                    embeddings.append(np.array(embedding))

            return embeddings

        except Exception as e:
            logger.error(f"Error getting embeddings: {str(e)}", exc_info=True)
            return []

    # ========================================================================
    # Model Management
    # ========================================================================

    def get_gemini_model(self):
        """Get or create cached Gemini model instance."""
        if self._gemini_model is None:
            self._gemini_model = genai.GenerativeModel(self.generation_model_name)
        return self._gemini_model

    # ========================================================================
    # Summarization Operations
    # ========================================================================

    async def summarize_cluster(self, posts: List[Dict], retry_count: int = None) -> Dict:
        """
        Summarize a cluster of similar posts using Gemini.

        Args:
            posts: List of post dictionaries from the same story
            retry_count: Number of retries for API calls (default: self.default_retry_count)

        Returns:
            Dictionary with 'headline', 'summary', 'channels', 'post_links', and 'count' fields
        """
        if retry_count is None:
            retry_count = self.default_retry_count

        if not posts:
            return {'headline': '', 'summary': '', 'channels': [], 'post_links': [], 'count': 0}

        # Select the longest post as the most representative
        representative_post = max(posts, key=lambda p: len(p['text']))

        # Collect all channels that covered this story (using set for deduplication)
        channels = list({post['channel'] for post in posts})

        # Collect post URLs with their channels for creating links
        post_links = [{'channel': post['channel'], 'url': post['url']}
                      for post in posts if post.get('url')]

        prompt = f"""Вы - краткий новостной аналитик. Ваша задача - обобщить новостной сюжет на основе следующего текста.

Предоставьте:
1. Один впечатляющий заголовок (максимум 15 слов)
2. Краткое резюме ключевых фактов из 2-3 пунктов

ВАЖНО: НЕ ВКЛЮЧАЙТЕ никаких ссылок или гиперссылок в заголовок и резюме. Используйте только обычный текст. Если в посте есть ссылка сделай ее простым текстом! Не превращайте слова, которые выглядят как домены (например: "x.ai", "X.AI", "OpenAI.com", Epoch.AI" и другие) в ссылки.

Текст новости:
{representative_post['text']}

Формат ответа:
ЗАГОЛОВОК: [ваш заголовок]

РЕЗЮМЕ:
• [первый ключевой факт]
• [второй ключевой факт]
• [третий ключевой факт, если необходимо]"""

        # Get cached model instance
        model = self.get_gemini_model()

        # Retry loop with exponential backoff
        for attempt in range(retry_count):
            try:
                # Use semaphore to limit concurrent API calls
                async with self._gemini_semaphore:
                    # Generate content (run in thread pool since genai is synchronous)
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(
                        None,
                        lambda: model.generate_content(
                            prompt,
                            generation_config=self.generation_config,
                            safety_settings=self.safety_settings
                        )
                    )

                # Check if response was blocked
                if not response.candidates:
                    raise ValueError("Response was blocked by safety filters")

                if response.candidates[0].finish_reason not in [1, 0]:  # 0=UNSPECIFIED, 1=STOP (normal)
                    raise ValueError(f"Response blocked with finish_reason: {response.candidates[0].finish_reason}")

                content = response.text

                # Check if content is None or empty
                if not content:
                    raise ValueError("API returned empty response")

                # Parse the response
                lines = content.strip().split('\n')
                headline = ''
                summary_points = []

                in_summary = False
                for line in lines:
                    line = line.strip()
                    if line.startswith('ЗАГОЛОВОК:'):
                        headline = line.replace('ЗАГОЛОВОК:', '').strip()
                        # Remove ** markdown formatting from headline
                        headline = headline.strip('*').strip()
                    elif line.startswith('РЕЗЮМЕ:'):
                        in_summary = True
                    elif in_summary and line:  # Capture all non-empty lines after РЕЗЮМЕ
                        summary_points.append(line)

                summary = '\n'.join(summary_points)

                return {
                    'headline': headline,
                    'summary': summary,
                    'channels': channels,
                    'post_links': post_links,
                    'count': len(posts)
                }

            except Exception as e:
                is_last_attempt = (attempt == retry_count - 1)
                logger.warning(f"Error summarizing cluster (attempt {attempt + 1}/{retry_count}): {str(e)}")

                if is_last_attempt:
                    # All retries failed, log error and return fallback
                    logger.error(f"Failed to summarize cluster after {retry_count} attempts: {str(e)}", exc_info=True)
                    return {
                        'headline': 'Ошибка обработки',
                        'summary': representative_post['text'][:300] + '...',
                        'channels': channels,
                        'post_links': post_links,
                        'count': len(posts)
                    }

                # Calculate wait time with exponential backoff
                wait_time = (2 ** attempt)  # Default: 1s, 2s, 4s

                # Try to extract retry_delay from ResourceExhausted exception
                if 'retry_delay' in str(e):
                    try:
                        match = re.search(r'retry_delay\s*{\s*seconds:\s*(\d+)', str(e))
                        if match:
                            suggested_delay = int(match.group(1))
                            # Use suggested delay but cap at max to avoid excessive waiting
                            wait_time = min(suggested_delay, self.max_retry_delay)
                            logger.info(f"API suggested retry delay: {suggested_delay}s, using {wait_time}s")
                    except Exception:
                        pass  # Fall back to exponential backoff if parsing fails

                logger.info(f"Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)

        # This should never be reached due to return in is_last_attempt, but added for safety
        return {
            'headline': 'Ошибка обработки',
            'summary': representative_post['text'][:300] + '...',
            'channels': channels,
            'post_links': post_links,
            'count': len(posts)
        }
