# -*- coding: utf-8 -*-
"""Quick test for StorageService"""
import asyncio
from bot.services.storage import StorageService


async def test_storage():
    storage = StorageService()
    print('[OK] StorageService instantiated successfully')

    # Test loading (should return empty dict if file doesn't exist)
    data = await storage.load_user_data()
    print(f'[OK] load_user_data() works - returned: {type(data).__name__}')

    # Test that all key methods exist
    assert hasattr(storage, 'save_user_data')
    assert hasattr(storage, 'get_user_channels')
    assert hasattr(storage, 'set_user_channels')
    assert hasattr(storage, 'get_user_folders')
    assert hasattr(storage, 'create_folder')
    assert hasattr(storage, 'backup_user_data')
    print('[OK] All storage methods are accessible')

    print('\n[PASS] Storage Service test completed successfully!')
    return True


if __name__ == '__main__':
    result = asyncio.run(test_storage())
    exit(0 if result else 1)
