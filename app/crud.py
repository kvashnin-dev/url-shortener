from sqlalchemy.orm import Session
from .models import URL
from .utils import generate_short_code

def create_url(db: Session, original_url: str):
    short_code = generate_short_code()
    while db.query(URL).filter(URL.short_code == short_code).first():
        short_code = generate_short_code()
    
    db_url = URL(original_url=original_url, short_code=short_code)
    db.add(db_url)
    db.commit()
    db.refresh(db_url)
    return db_url