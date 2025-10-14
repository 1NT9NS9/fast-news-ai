# -*- coding: utf-8 -*-
"""Quick test for ClusteringService"""
import numpy as np
from bot.services.clustering import ClusteringService


def test_clustering():
    clustering = ClusteringService()
    print('[OK] ClusteringService instantiated successfully')

    # Test that all key methods exist
    assert hasattr(clustering, 'cluster_posts')
    print('[OK] All clustering methods are accessible')

    # Test basic clustering with sample data
    posts = [
        {'text': 'Post 1', 'channel': '@test'},
        {'text': 'Post 2', 'channel': '@test'}
    ]
    embeddings = [np.array([1.0, 0.0, 0.0]), np.array([0.9, 0.1, 0.0])]  # Similar
    clusters = clustering.cluster_posts(embeddings, posts)
    assert len(clusters) > 0
    print(f'[OK] Clustering works - created {len(clusters)} cluster(s) from 2 posts')

    print('\n[PASS] Clustering Service test completed successfully!')
    return True


if __name__ == '__main__':
    result = test_clustering()
    exit(0 if result else 1)
