# -*- coding: utf-8 -*-
"""
AI Service

Handles all AI-related operations:
- Text embeddings generation (migrating from `text-embedding-004` to `gemini-embedding-001`)
- AI-powered summarization using Gemini Flash Lite
- Batch processing and parallel summarization
- Rate limiting and retry logic

Embedding migration decisions:
- The embeddings client will use `google.genai.Client` with model ID `gemini-embedding-001` (no `models/` prefix).
- Supported output dimensionalities are 768, 1536, and 3072; we default to 768 to preserve clustering behavior.
- Summarization stays on `google-generativeai` to limit the blast radius of the client swap.
"""

import asyncio
import re
import time
from collections import deque
from typing import List, Dict, Iterable
import numpy as np
import google.generativeai as genai
from google import genai as ggenai

from bot.utils.config import (
    GEMINI_API,
    GEMINI_CONCURRENT_LIMIT,
    GEMINI_EMBEDDING_MODEL,
    EMBEDDING_TASK_TYPE,
    EMBEDDING_TEXTS_PER_BATCH,
    EMBEDDING_OUTPUT_DIM,
    EMBEDDING_MAX_TOKENS,
    EMBEDDING_RPM,
    GEMINI_EMBEDDING_CONCURRENT_LIMIT,
)
from bot.utils.logger import setup_logging

logger, _ = setup_logging()


class AIService:
    """Manages AI operations for embeddings and content generation."""

    def __init__(self):
        # Configure Google Generative AI
        genai.configure(api_key=GEMINI_API)

        # Dedicated embeddings client (kept separate from generation)
        self._emb_client = ggenai.Client(api_key=GEMINI_API)

        # Embedding model configuration
        self.embedding_model = GEMINI_EMBEDDING_MODEL
        self.embedding_task_type = EMBEDDING_TASK_TYPE
        self.embedding_batch_size = EMBEDDING_TEXTS_PER_BATCH  # Google API allows up to 50 per batch
        self.embedding_output_dim = EMBEDDING_OUTPUT_DIM
        self.embedding_max_tokens = EMBEDDING_MAX_TOKENS
        self.embedding_rpm = EMBEDDING_RPM
        self._embedding_chars_per_token = 3  # heuristic: 3 characters ~ 1 token
        # Generation model configuration
        self.generation_model_name = "gemini-flash-lite-latest"
        self._gemini_model = None  # Cached model instance

        # Rate limiting
        self._gemini_semaphore = asyncio.Semaphore(GEMINI_CONCURRENT_LIMIT)
        self._embed_semaphore = asyncio.Semaphore(GEMINI_EMBEDDING_CONCURRENT_LIMIT)
        self._embed_rpm_lock = asyncio.Lock()
        self._embed_request_times: deque[float] = deque()

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

    def _truncate_for_embedding(self, text: str) -> str:
        """
        Truncate an input string so the embedding request stays within token budget.

        Uses a heuristic of three characters per token and trims on a word boundary
        when possible. Logs when truncation occurs to aid production tuning.
        """
        if not text:
            return ""

        if self.embedding_max_tokens <= 0:
            return text

        max_chars = self.embedding_max_tokens * self._embedding_chars_per_token
        if len(text) <= max_chars:
            return text

        clipped = text[:max_chars]
        last_space = clipped.rfind(" ")
        truncated = clipped if last_space < 0 else clipped[:last_space]
        truncated = truncated.rstrip()

        if not truncated:
            truncated = clipped.rstrip()

        logger.debug(
            "Truncated embedding input from %s to %s chars (max tokens: %s)",
            len(text),
            len(truncated),
            self.embedding_max_tokens,
        )
        return truncated

    def _build_embedding_requests(self, texts: Iterable[str]) -> List[Dict]:
        """
        Build the request payload expected by the gemini embedding batch endpoint.

        Each text is truncated to respect EMBEDDING_MAX_TOKENS before being packaged.
        """
        requests: List[Dict] = []
        use_title = self.embedding_task_type.lower() == "retrieval_document"
        for text in texts:
            prepared = self._truncate_for_embedding(text or "")
            request = {
                "content": prepared,
                "task_type": self.embedding_task_type,
                "output_dimensionality": self.embedding_output_dim,
            }
            if use_title:
                request["title"] = "telegram_post"
            requests.append(request)
        return requests

    async def _acquire_embedding_rpm_slot(self) -> float:
        """
        Ensure embedding calls do not exceed EMBEDDING_RPM.

        Returns:
            Total sleep time incurred before acquiring the slot.
        """
        if self.embedding_rpm <= 0:
            return 0.0

        total_sleep = 0.0
        while True:
            async with self._embed_rpm_lock:
                now = time.monotonic()
                while self._embed_request_times and now - self._embed_request_times[0] >= 60:
                    self._embed_request_times.popleft()

                if len(self._embed_request_times) < self.embedding_rpm:
                    self._embed_request_times.append(now)
                    return total_sleep

                oldest = self._embed_request_times[0]
                wait_time = max(0.0, 60 - (now - oldest))

            if wait_time > 0:
                logger.info("Embedding RPM limiter sleeping for %.2fs", wait_time)
                await asyncio.sleep(wait_time)
                total_sleep += wait_time
            else:
                await asyncio.sleep(0)

    async def _call_embedding_batch(self, batch_requests: List[Dict]):
        """Invoke the google-genai embedding endpoint with batched contents."""
        if not batch_requests:
            return None

        loop = asyncio.get_event_loop()

        batch_method = getattr(self._emb_client.models, "batch_embed_contents", None)
        if callable(batch_method):
            payload: List[Dict] = []
            for req in batch_requests:
                content_text = req.get("content") or ""
                request_entry = {"content": {"parts": [{"text": content_text}]}}
                task_type = req.get("task_type")
                if task_type:
                    request_entry["task_type"] = task_type
                title = req.get("title")
                if title:
                    request_entry["title"] = title
                output_dim = req.get("output_dimensionality")
                if output_dim:
                    request_entry["output_dimensionality"] = output_dim
                payload.append(request_entry)

            return await loop.run_in_executor(
                None,
                lambda requests=payload: batch_method(
                    model=self.embedding_model,
                    requests=requests,
                ),
            )

        # Fallback for SDK versions without batch_embed_contents support.
        logger.debug("google-genai client missing batch_embed_contents; falling back to embed_content.")
        exemplar = batch_requests[0]
        config: Dict[str, object] = {}
        task_type = exemplar.get("task_type")
        if task_type:
            config["task_type"] = task_type
        output_dim = exemplar.get("output_dimensionality")
        if output_dim:
            config["output_dimensionality"] = output_dim
        title = exemplar.get("title")
        if title and str(task_type).lower() == "retrieval_document":
            config["title"] = title

        return await loop.run_in_executor(
            None,
            lambda contents=[req.get("content") or "" for req in batch_requests], cfg=config: self._emb_client.models.embed_content(  # type: ignore[var-annotated]
                model=self.embedding_model,
                contents=contents,
                config=cfg or None,
            ),
        )

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
            embeddings: List[np.ndarray] = []

            for start in range(0, len(texts), self.embedding_batch_size):
                batch = texts[start:start + self.embedding_batch_size]
                batch_requests = self._build_embedding_requests(batch)
                truncated_count = sum(
                    1
                    for original, request in zip(batch, batch_requests)
                    if len(request["content"]) < len((original or ""))
                )

                logger.info(
                    "Embedding batch start=%s size=%s truncated=%s",
                    start,
                    len(batch_requests),
                    truncated_count,
                )

                for attempt in range(1, self.default_retry_count + 1):
                    rpm_wait = await self._acquire_embedding_rpm_slot()
                    try:
                        async with self._embed_semaphore:
                            response = await self._call_embedding_batch(batch_requests)

                        if not getattr(response, "embeddings", None):
                            raise ValueError("Embedding response missing 'embeddings' field")

                        batch_vectors: List[np.ndarray] = []
                        for idx, embedding in enumerate(response.embeddings):
                            values = getattr(embedding, "values", None)
                            if values is None:
                                logger.warning(
                                    "Embedding response missing values at index %s; skipping.",
                                    idx,
                                )
                                continue

                            vector = np.array(values, dtype=float)
                            if vector.size != self.embedding_output_dim:
                                logger.warning(
                                    "Embedding dimension mismatch (expected %s, got %s) at index %s; skipping.",
                                    self.embedding_output_dim,
                                    vector.size,
                                    idx,
                                )
                                continue

                            batch_vectors.append(vector)

                        embeddings.extend(batch_vectors)
                        missing = len(batch_requests) - len(batch_vectors)
                        logger.info(
                            "Embedding batch complete start=%s returned=%s wait=%.2fs",
                            start,
                            len(batch_vectors),
                            rpm_wait,
                        )
                        if missing:
                            logger.warning(
                                "Embedding batch start=%s skipped=%s items due to response issues.",
                                start,
                                missing,
                            )
                        break

                    except Exception as exc:
                        is_last_attempt = attempt == self.default_retry_count
                        logger.warning(
                            "Error embedding batch start=%s size=%s attempt %s/%s: %s",
                            start,
                            len(batch_requests),
                            attempt,
                            self.default_retry_count,
                            exc,
                        )

                        wait_time = min(2 ** (attempt - 1), self.max_retry_delay)
                        error_str = str(exc)
                        if "retry_delay" in error_str:
                            try:
                                match = re.search(r"retry_delay\s*{\s*seconds:\s*(\d+)", error_str)
                                if match:
                                    suggested = int(match.group(1))
                                    wait_time = min(suggested, self.max_retry_delay)
                                    logger.info(
                                        "Embedding API suggested retry delay %ss; sleeping %ss",
                                        suggested,
                                        wait_time,
                                    )
                            except Exception:
                                pass

                        if is_last_attempt:
                            logger.error(
                                "Failed embedding batch after %s attempts.", self.default_retry_count, exc_info=True
                            )
                            raise

                        logger.info("Retrying embedding batch in %.2fs", wait_time)
                        await asyncio.sleep(wait_time)

            return embeddings

        except Exception as e:
            logger.error(f"Error getting embeddings: {str(e)}", exc_info=True)
            return []

        finally:
            expected = len(texts)
            produced = len(embeddings) if 'embeddings' in locals() else 0
            if produced and produced != expected:
                logger.warning(
                    "Embedding call returned %s vectors for %s inputs; downstream consumers should handle gaps.",
                    produced,
                    expected,
                )

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
