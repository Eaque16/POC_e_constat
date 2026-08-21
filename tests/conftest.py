import os

os.environ["DATABASE_URL"] = "sqlite:///./test_econstat.db"
os.environ["JWT_SECRET"] = "test-secret-that-is-long-enough-1234"
