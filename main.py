from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from typing import Optional, List
from pydantic import BaseModel, EmailStr
import secrets
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

# Database configuration
SQLALCHEMY_DATABASE_URL = "sqlite:///./file_share.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Security configuration
SECRET_KEY = secrets.token_urlsafe(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Email configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_EMAIL = "your-email@gmail.com"
SMTP_PASSWORD = "your-app-specific-password"

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    is_ops_user = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    verification_token = Column(String, unique=True, nullable=True)

class File(Base):
    __tablename__ = "files"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String)
    upload_date = Column(DateTime, default=datetime.utcnow)
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    download_token = Column(String, unique=True)

Base.metadata.create_all(bind=engine)

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    is_ops_user: bool = False

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class FileUpload(BaseModel):
    filename: str
    download_token: str

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.email == token_data.email).first()
    if user is None:
        raise credentials_exception
    return user

def get_current_active_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def get_current_ops_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_ops_user:
        raise HTTPException(status_code=403, detail="Not an operations user")
    return current_user

@app.post("/signup", response_model=Token)
async def signup(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    verification_token = secrets.token_urlsafe(32)
    db_user = User(
        email=user.email,
        hashed_password=get_password_hash(user.password),
        is_ops_user=user.is_ops_user,
        verification_token=verification_token
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Send verification email
    send_verification_email(user.email, verification_token)
    
    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/verify-email/{token}")
async def verify_email(token: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.verification_token == token).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid verification token")
    
    user.is_verified = True
    user.verification_token = None
    db.commit()
    return {"message": "Email verified successfully"}

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email first",
        )
    
    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/upload-file/")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_ops_user),
    db: Session = Depends(get_db)
):
    allowed_extensions = [".pptx", ".docx", ".xlsx"]
    if not any(file.filename.endswith(ext) for ext in allowed_extensions):
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    download_token = secrets.token_urlsafe(32)
    db_file = File(
        filename=file.filename,
        uploaded_by=current_user.id,
        download_token=download_token
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)
    
    # Save file to disk
    file_location = f"uploads/{download_token}_{file.filename}"
    os.makedirs("uploads", exist_ok=True)
    with open(file_location, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    
    return {"message": "File uploaded successfully", "download_token": download_token}

@app.get("/download-file/{file_id}")
async def get_download_link(
    file_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    file = db.query(File).filter(File.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    if not current_user.is_ops_user:
        raise HTTPException(status_code=403, detail="Access denied")
    
    download_url = f"/download/{file.download_token}"
    return {"download-link": download_url, "message": "success"}

@app.get("/download/{token}")
async def download_file(
    token: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    file = db.query(File).filter(File.download_token == token).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    if current_user.is_ops_user:
        raise HTTPException(status_code=403, detail="Access denied")
    
    file_location = f"uploads/{token}_{file.filename}"
    if not os.path.exists(file_location):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(file_location, filename=file.filename)

@app.get("/files", response_model=List[FileUpload])
async def list_files(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    if current_user.is_ops_user:
        files = db.query(File).all()
    else:
        files = db.query(File).filter(File.uploaded_by == current_user.id).all()
    return files

def send_verification_email(email: str, token: str):
    message = MIMEMultipart()
    message["From"] = SMTP_EMAIL
    message["To"] = email
    message["Subject"] = "Verify your email"
    
    verification_link = f"http://localhost:8000/verify-email/{token}"
    body = f"Please click the following link to verify your email: {verification_link}"
    message.attach(MIMEText(body, "plain"))
    
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, email, message.as_string())
    except Exception as e:
        print(f"Failed to send verification email: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
