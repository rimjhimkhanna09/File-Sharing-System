import pytest
from fastapi.testclient import TestClient
from main import app, get_db, Base, get_password_hash, User, File
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_file_share.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(autouse=True, scope="session")
def setup_test_database():
    # Drop existing tables if they exist
    Base.metadata.drop_all(bind=engine)
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    yield
    # Drop all tables at the end of the test session
    Base.metadata.drop_all(bind=engine)

def setup_database():
    # Drop existing tables if they exist
    Base.metadata.drop_all(bind=engine)
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Create test database session
    db = TestingSessionLocal()
    try:
        # Create test user for ops user tests
        test_user = User(
            email="test_ops@example.com",
            hashed_password=get_password_hash("password123"),
            is_ops_user=True,
            is_verified=True
        )
        db.add(test_user)
        db.commit()
    finally:
        db.close()

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

@pytest.fixture
def test_client():
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)

@pytest.fixture
def test_db():
    setup_database()
    yield TestingSessionLocal()

def test_signup(test_client, test_db):
    response = test_client.post(
        "/signup",
        json={
            "email": "test@example.com",
            "password": "password123",
            "is_ops_user": False
        }
    )
    assert response.status_code == 200
    assert response.json()["message"] == "User created successfully. Please check your email for verification."
    assert "verification_token" in response.json()
    
    # Verify user was created
    user = test_db.query(User).filter(User.email == "test@example.com").first()
    assert user is not None
    assert user.is_verified == False
    assert user.verification_token is not None
    assert user.verification_token == response.json()["verification_token"]

def test_login(test_client, test_db):
    # First signup a user
    signup_response = test_client.post(
        "/signup",
        json={
            "email": "login@example.com",
            "password": "password123",
            "is_ops_user": False
        }
    )
    assert signup_response.status_code == 200
    
    # Get the verification token from the database
    user = test_db.query(User).filter(User.email == "login@example.com").first()
    
    # Verify email
    verify_response = test_client.post(f"/verify-email/{user.verification_token}")
    assert verify_response.status_code == 200
    assert "access_token" in verify_response.json()
    
    # Then try to login
    login_response = test_client.post(
        "/token",
        data={
            "username": "login@example.com",
            "password": "password123"
        }
    )
    assert login_response.status_code == 200
    token_data = login_response.json()
    assert "access_token" in token_data
    assert "token_type" in token_data
    
    # Verify user is logged in
    token = token_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    response = test_client.get("/users/me", headers=headers)
    assert response.status_code == 200

def test_upload_file(test_client, test_db):
    # First signup as ops user
    signup_response = test_client.post(
        "/signup",
        json={
            "email": "ops@example.com",
            "password": "password123",
            "is_ops_user": True
        }
    )
    assert signup_response.status_code == 200
    
    # Get the verification token from the database
    user = test_db.query(User).filter(User.email == "ops@example.com").first()
    
    # Verify email
    verify_response = test_client.post(f"/verify-email/{user.verification_token}")
    assert verify_response.status_code == 200
    assert "access_token" in verify_response.json()
    
    # Login
    login_response = test_client.post(
        "/token",
        data={
            "username": "ops@example.com",
            "password": "password123"
        }
    )
    assert login_response.status_code == 200
    token_data = login_response.json()
    assert "access_token" in token_data
    assert "token_type" in token_data
    
    token = token_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create a test file
    test_file = (
        b"\x50\x4B\x05\x06\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    )
    
    response = test_client.post(
        "/upload-file/",
        headers=headers,
        files={"file": ("test.pptx", test_file, "application/vnd.openxmlformats-officedocument.presentationml.presentation")}
    )
    assert response.status_code == 200
    upload_data = response.json()
    assert "message" in upload_data
    assert "download_token" in upload_data
    
    # Verify file was uploaded
    download_token = upload_data["download_token"]
    file = test_db.query(File).filter(File.download_token == download_token).first()
    assert file is not None
    assert file.filename == "test.pptx"
    assert file.uploaded_by == user.id

def test_download_file(test_client, test_db):
    # First signup as ops user
    signup_response = test_client.post(
        "/signup",
        json={
            "email": "download@example.com",
            "password": "password123",
            "is_ops_user": True
        }
    )
    assert signup_response.status_code == 200
    
    # Get the verification token from the database
    user = test_db.query(User).filter(User.email == "download@example.com").first()
    
    # Verify email
    verify_response = test_client.post(f"/verify-email/{user.verification_token}")
    assert verify_response.status_code == 200
    assert "access_token" in verify_response.json()
    
    # Login
    login_response = test_client.post(
        "/token",
        data={
            "username": "download@example.com",
            "password": "password123"
        }
    )
    assert login_response.status_code == 200
    
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Upload a test file
    test_file = (
        b"\x50\x4B\x05\x06\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    )
    
    upload_response = test_client.post(
        "/upload-file/",
        headers=headers,
        files={"file": ("test.pptx", test_file, "application/vnd.openxmlformats-officedocument.presentationml.presentation")}
    )
    assert upload_response.status_code == 200
    assert "download_token" in upload_response.json()
    
    download_token = upload_response.json()["download_token"]
    
    # Download file
    response = test_client.get(
        f"/download-file/{download_token}",
        headers=headers
    )
    assert response.status_code == 200
    assert response.headers["content-disposition"] == 'attachment; filename="test.pptx"'

def test_list_files(test_client, test_db):
    # First signup as ops user
    signup_response = test_client.post(
        "/signup",
        json={
            "email": "list@example.com",
            "password": "password123",
            "is_ops_user": True
        }
    )
    assert signup_response.status_code == 200
    
    # Get the verification token from the database
    user = test_db.query(User).filter(User.email == "list@example.com").first()
    
    # Verify email
    verify_response = test_client.post(f"/verify-email/{user.verification_token}")
    assert verify_response.status_code == 200
    assert "access_token" in verify_response.json()
    
    # Login
    login_response = test_client.post(
        "/token",
        data={
            "username": "list@example.com",
            "password": "password123"
        }
    )
    assert login_response.status_code == 200
    
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Upload test files
    test_files = []
    for filename in ["file1.pptx", "file2.pptx"]:
        test_file = (
            b"\x50\x4B\x05\x06\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        )
        
        upload_response = test_client.post(
            "/upload-file/",
            headers=headers,
            files={"file": (filename, test_file, "application/vnd.openxmlformats-officedocument.presentationml.presentation")}
        )
        assert upload_response.status_code == 200
        assert "download_token" in upload_response.json()
        test_files.append(upload_response.json())
    
    # List files
    response = test_client.get(
        "/files",
        headers=headers
    )
    assert response.status_code == 200
    files = response.json()
    assert len(files) == 2
    
    # Verify file details
    for file in files:
        assert file["filename"] in ["file1.pptx", "file2.pptx"]
        assert "upload_date" in file
        assert "download_token" in file
        assert "uploaded_by" in file
