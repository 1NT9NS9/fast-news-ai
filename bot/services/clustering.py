# -*- coding: utf-8 -*-
"""
Clustering Service

Handles post clustering using DBSCAN and embeddings:
- Clusters similar posts together based on semantic similarity
- Uses cosine distance metric with embeddings
- Separates noise posts into individual clusters
"""

from collections import defaultdict
from typing import List, Dict
import numpy as np
from sklearn.cluster import DBSCAN

from bot.utils.config import SIMILARITY_THRESHOLD
from bot.utils.logger import setup_logging

logger, _ = setup_logging()


class ClusteringService:
    """Manages post clustering using DBSCAN algorithm."""

    def __init__(self):
        # Clustering configuration
        self.similarity_threshold = SIMILARITY_THRESHOLD
        self.min_samples = 2  # Minimum posts to form a cluster

        # Calculate epsilon for DBSCAN (cosine distance)
        # eps = 1 - similarity_threshold (converts cosine similarity to distance)
        self.eps = 1 - self.similarity_threshold

    # ========================================================================
    # Clustering Operations
    # ========================================================================

    def cluster_posts(self, embeddings: List[np.ndarray], posts: List[Dict]) -> List[List[Dict]]:
        """
        Cluster similar posts using DBSCAN and embeddings.

        Args:
            embeddings: List of embedding vectors for posts
            posts: List of post dictionaries with 'text' field

        Returns:
            List of clusters, where each cluster is a list of post dictionaries
        """
        if not posts:
            return []

        if not embeddings or len(embeddings) != len(posts):
            logger.warning("Failed to get embeddings or embedding count mismatch")
            return [[post] for post in posts]  # Return each post as its own cluster

        # Create embedding matrix directly (avoid storing in posts to save memory)
        embedding_matrix = np.array(embeddings)

        # Initialize and fit DBSCAN
        db = DBSCAN(eps=self.eps, min_samples=self.min_samples, metric='cosine')
        cluster_labels = db.fit_predict(embedding_matrix)

        # Group posts by cluster label using defaultdict for efficiency
        cluster_dict = defaultdict(list)
        for post, label in zip(posts, cluster_labels):
            cluster_dict[label].append(post)

        # Build cluster list
        clusters = []

        # Add valid clusters (labels >= 0)
        for label in sorted(cluster_dict.keys()):
            if label >= 0:
                clusters.append(cluster_dict[label])

        # Add noise posts (label = -1) as single-item clusters
        if -1 in cluster_dict:
            clusters.extend([[noise_post] for noise_post in cluster_dict[-1]])

        logger.info(
            f"DBSCAN clustering: {len(posts)} posts -> {len(clusters)} clusters "
            f"(noise: {len(cluster_dict.get(-1, []))})"
        )

        return clusters
