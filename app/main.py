from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from . import crud, schemas, database, cache, rabbit
from .database import SessionLocal, Base, engine

Base.metadata.create_all(bind=engine)

app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/shorten", response_model=schemas.URLResponse)
async def shorten_url(request: schemas.URLCreate, db: Session = Depends(get_db)):
    # Проверяем кэш
    cached = cache.get_cached_url(request.original_url)
    if cached:
        return cached

    # Создаём в БД
    db_url = crud.create_url(db, request.original_url)

    result = {"short_code": db_url.short_code, "original_url": db_url.original_url}
    
    # Кэшируем
    cache.set_cached_url(db_url.short_code, result)

    # Отправляем в RabbitMQ
    rabbit.publish_event("url_created", result)

    return result

@app.get("/{short_code}")
async def redirect_url(short_code: str, db: Session = Depends(get_db)):
    # Сначала кэш
    cached = cache.get_cached_url(short_code)
    if cached:
        return {"original_url": cached["original_url"]}

    # Потом БД
    url = db.query(database.URL).filter(database.URL.short_code == short_code).first()
    if not url:
        raise HTTPException(404, "Not found")

    result = {"original_url": url.original_url}
    cache.set_cached_url(short_code, result)
    return result