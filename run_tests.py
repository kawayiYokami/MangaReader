# run_tests.py (v3 - Truly Standalone)
import asyncio
import os
import sys
import json
import zipfile
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import cv2

# --- 1. Environment Setup ---
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- Import project modules AFTER setting up the path ---
from core.config import config
from web.api.translation import get_manga_translation_service

print("✅ [1/4] Environment and imports are ready.")

# --- 2. Test Utilities ---
def create_mock_api_response(original_texts, translated_texts):
    """Helper to create a realistic, nested JSON response from a mock LLM."""
    content_json = {
        "translations": [
            {"original": o, "translated": t} for o, t in zip(original_texts, translated_texts)
        ]
    }
    response_payload = {
        "choices": [{
            "message": {
                "content": json.dumps(content_json, ensure_ascii=False)
            }
        }]
    }
    # Create a simple mock response object that behaves like a requests.Response
    mock_response = type('MockResponse', (object,), {
        'status_code': 200,
        'text': json.dumps(response_payload["choices"][0]["message"]["content"]),
        'json': lambda: response_payload,
        'raise_for_status': lambda: None
    })()
    return mock_response

print("✅ [2/4] Test utilities defined.")

# --- 3. Test Cases ---

async def run_service_e2e_test():
    """
    End-to-end test for MangaTranslationService using the app's own instantiation logic.
    """
    print("\n--- Running: Service End-to-End Test ---")
    
    # Use the application's own factory to create the service
    service = get_manga_translation_service()
    print("✅ Service instance created successfully via application factory.")

    sample_path = "tests/test_data/sample_manga.zip"

    # The test must use the translator from the config file
    active_translator = config.translator_type.value
    print(f"ℹ️  Testing with active translator from config: {active_translator}")

    # We still need to mock the external API call
    def mock_post_func(*args, **kwargs):
        payload = kwargs.get('json', {})
        user_content = payload.get('messages', [])[1].get('content', '[]')
        original_texts = [item['original'] for item in json.loads(user_content)]
        translated_texts = [f"{t} [E2E-Translated by Mock]" for t in original_texts]
        return create_mock_api_response(original_texts, translated_texts)

    with patch('requests.post', side_effect=mock_post_func):
        with tempfile.TemporaryDirectory() as temp_dir:
            print("▶️ Testing offline archive translation...")
            translated_zip_path_str = await service.translate_manga_archive(
                manga_path=sample_path,
                output_dir=temp_dir
            )
            translated_zip_path = Path(translated_zip_path_str)
            assert translated_zip_path.exists(), "Translated zip file was not created."
            with zipfile.ZipFile(translated_zip_path, 'r') as zf:
                assert len(zf.infolist()) > 0, "Translated zip file is empty."
            print("✔️ Offline Archive Test PASSED")

print("✅ [3/4] Test cases defined.")

# --- 4. Main Execution Block ---

async def main():
    """Main function to run all defined tests."""
    print("\n✅ [4/4] Starting test execution...")
    try:
        await run_service_e2e_test()
        print("\n🎉 All tests completed successfully! 🎉")
    except Exception as e:
        print(f"\n❌ A test failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
