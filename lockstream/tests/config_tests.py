import os

from pathlib import Path

# Set the environment variable for testing
os.environ["EVENT_LOG_PATH"] = "test_event_log.jsonl"

from lockstream.infrastructure.config import settings