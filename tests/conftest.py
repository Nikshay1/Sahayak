"""
Pytest Configuration and Fixtures
"""

import pytest
import asyncio
from typing import Generator
from unittest.mock import MagicMock

# Configure asyncio for pytest
@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_settings():
    """Mock application settings"""
    settings = MagicMock()
    settings.OPENAI_API_KEY = "test-key"
    settings.OPENAI_MODEL = "gpt-4o"
    settings.CONFIDENCE_THRESHOLD = 0.85
    settings.SAFE_REFUSAL_THRESHOLD = 0.90
    settings.MAX_TRANSACTION_AMOUNT = 2000
    settings.SILENCE_THRESHOLD_SECONDS = 1.5
    settings.ENVIRONMENT = "test"
    return settings