import os
from pathlib import Path

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test-orbitops.db"
os.environ["APP_SECRET_KEY"] = "test-secret-key-with-more-than-32-characters"
os.environ["BOOTSTRAP_ADMIN_EMAIL"] = "admin@example.com"
os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = "TestOnly-Password-123!"
os.environ["EMAIL_WEBHOOK_SECRET"] = "test-only-email-webhook-secret-32"
os.environ["WHATSAPP_WEBHOOK_SECRET"] = "test-only-whatsapp-webhook-secret-32"

database_file = Path(__file__).parents[1] / "test-orbitops.db"
if database_file.exists():
    database_file.unlink()
