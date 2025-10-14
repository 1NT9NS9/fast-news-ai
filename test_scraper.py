# -*- coding: utf-8 -*-
"""Quick test for ScraperService"""
import asyncio
from bot.services.scraper import ScraperService


async def test_scraper():
    scraper = ScraperService()
    print('[OK] ScraperService instantiated successfully')

    # Test that all key methods exist
    assert hasattr(scraper, 'scrape_channel')
    assert hasattr(scraper, 'validate_channel_access')
    assert hasattr(scraper, 'parse_subscriber_count')
    assert hasattr(scraper, 'get_http_client')
    print('[OK] All scraper methods are accessible')

    # Test subscriber count parsing
    assert scraper.parse_subscriber_count("1.2M subscribers") == 1_200_000
    assert scraper.parse_subscriber_count("53K members") == 53_000
    assert scraper.parse_subscriber_count("987 subscribers") == 987
    print('[OK] Subscriber count parsing works correctly')

    print('\n[PASS] Scraper Service test completed successfully!')
    return True


if __name__ == '__main__':
    result = asyncio.run(test_scraper())
    exit(0 if result else 1)
