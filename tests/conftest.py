import os
import shutil
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base, get_db
import app.services.job_service as job_service_module
from app.main import app


@pytest.fixture(scope="session")
def temp_storage():
    """Create a temporary storage directory for tests and clean up afterwards."""
    temp_dir = tempfile.mkdtemp(prefix="cert_test_storage_")
    orig_storage = settings.STORAGE_DIR
    settings.STORAGE_DIR = Path(temp_dir)
    yield Path(temp_dir)
    # Cleanup
    settings.STORAGE_DIR = orig_storage
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="function")
def db_session(temp_storage):
    """Create an isolated SQLite database for each test function."""
    db_file = tempfile.mktemp(suffix=".db")
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    # Patch job_service to use the testing session factory for background tasks
    orig_job_service_session = job_service_module.SessionLocal
    job_service_module.SessionLocal = TestingSessionLocal

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        job_service_module.SessionLocal = orig_job_service_session
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
        if os.path.exists(db_file):
            try:
                os.remove(db_file)
            except OSError:
                pass


@pytest.fixture(scope="function")
def client(db_session, temp_storage):
    """FastAPI TestClient with overridden database dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
