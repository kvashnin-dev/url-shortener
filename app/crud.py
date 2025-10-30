from sqlalchemy.orm import Session
from .models import URL, User
from .utils import generate_short_code, get_password_hash, verify_password
from .schemas import UserCreate

def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()

def create_user(db: Session, user: UserCreate):
    hashed = get_password_hash(user.password)
    db_user = User(email=user.email, hashed_password=hashed)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def create_url(db: Session, original_url: str, user_id: int):
    short_code = generate_short_code()
    while db.query(URL).filter(URL.short_code == short_code).first():
        short_code = generate_short_code()
    
    db_url = URL(original_url=original_url, short_code=short_code, owner_id=user_id)
    db.add(db_url)
    db.commit()
    db.refresh(db_url)
    return db_url

def get_user_urls(db: Session, user_id: int, skip: int = 0, limit: int = 10):
    return db.query(URL).filter(URL.owner_id == user_id).offset(skip).limit(limit).all()

def get_url_by_id(db: Session, url_id: int, user_id: int):
    return db.query(URL).filter(URL.id == url_id, URL.owner_id == user_id).first()

def delete_url(db: Session, url_id: int, user_id: int):
    url = get_url_by_id(db, url_id, user_id)
    if url:
        db.delete(url)
        db.commit()
        return True
    return False