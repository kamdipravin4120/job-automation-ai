from __future__ import annotations

import logging

from openai import OpenAI

from src.utils.config import MatcherConfig
from src.utils.retry import retry_sync
from src.utils.text import normalize_text


class OpenAIEmbeddingClient:
    def __init__(self, config: MatcherConfig, logger: logging.Logger) -> None:
        self.config = config
        self.logger = logger.getChild("openai_embeddings")
        self.client = OpenAI()

    @retry_sync(attempts=3)
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        sanitized = [normalize_text(text).replace("\n", " ") or "n/a" for text in texts]
        embeddings: list[list[float]] = []

        for batch_start in range(0, len(sanitized), self.config.batch_size):
            batch = sanitized[batch_start : batch_start + self.config.batch_size]
            params = {
                "model": self.config.model,
                "input": batch,
            }
            if self.config.dimensions is not None:
                params["dimensions"] = self.config.dimensions

            response = self.client.embeddings.create(**params)
            embeddings.extend(item.embedding for item in response.data)

        self.logger.info("Generated %s embeddings", len(embeddings))
        return embeddings

