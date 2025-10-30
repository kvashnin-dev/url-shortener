# app/main.py
import time
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import text  # ← ОБЯЗАТЕЛЬНО
from jose import JWTError, jwt
from . import crud, schemas, database, cache, rabbit, utils
from .database import SessionLocal, Base, engine
from app.models import URL

# =================================================
# Инициализация БД с ожиданием
# =================================================
def init_db():
    max_retries = 10
    retry = 0
    while retry < max_retries:
        try:
            with engine.begin() as conn:
                conn.execute(text("SELECT 1"))  # ← text("SELECT 1") — ВОТ ТАК!
            print("PostgreSQL connected!")
            Base.metadata.create_all(bind=engine)
            print("Tables created!")
            return
        except Exception as e:
            retry += 1
            print(f"DB not ready (attempt {retry}/{max_retries}): {e}")
            time.sleep(2)
    raise Exception("Could not connect to PostgreSQL")

# =================================================
# FastAPI
# =================================================
app = FastAPI()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

@app.on_event("startup")
async def startup_event():
    init_db()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# =================================================
# Аутентификация
# =================================================
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, utils.SECRET_KEY, algorithms=[utils.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = crud.get_user_by_email(db, email)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# =================================================
# Публичные
# =================================================
@app.post("/register", response_model=schemas.Token)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    if crud.get_user_by_email(db, user.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    db_user = crud.create_user(db, user)
    token = utils.create_access_token({"sub": db_user.email})
    return {"access_token": token, "token_type": "bearer"}

@app.post("/login", response_model=schemas.Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = crud.get_user_by_email(db, form.username)
    if not user or not utils.verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    token = utils.create_access_token({"sub": user.email})
    return {"access_token": token, "token_type": "bearer"}

# =================================================
# CRUD
# =================================================
@app.post("/shorten", response_model=schemas.URLResponse)
async def shorten_url(
    request: schemas.URLCreate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    cached = cache.get_cached_url(request.original_url)
    if cached:
        return cached

    db_url = crud.create_url(db, request.original_url, current_user.id)
    result = schemas.URLResponse.from_orm(db_url)
    
    cache.set_cached_url(
        db_url.short_code,
        result.model_dump(mode='json')  # ← автоматически конвертирует datetime в ISO строку
    )
    rabbit.publish_event("url_created", {"short_code": db_url.short_code, "user_id": current_user.id})

    return result

@app.get("/urls", response_model=schemas.URLList)
def list_urls(
    skip: int = 0, limit: int = 10,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    urls = crud.get_user_urls(db, current_user.id, skip, limit)
    return {"urls": [schemas.URLResponse.from_orm(u) for u in urls]}

@app.get("/urls/{url_id}", response_model=schemas.URLResponse)
def get_url(
    url_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    url = crud.get_url_by_id(db, url_id, current_user.id)
    if not url:
        raise HTTPException(404, "URL not found")
    return schemas.URLResponse.from_orm(url)

@app.delete("/urls/{url_id}")
def delete_url(
    url_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if crud.delete_url(db, url_id, current_user.id):
        return {"detail": "Deleted"}
    raise HTTPException(404, "URL not found")

# =================================================
# Редирект
# =================================================
@app.get("/{short_code}")
async def redirect(short_code: str, db: Session = Depends(get_db)):
    cached = cache.get_cached_url(short_code)
    if cached:
        return {"original_url": cached["original_url"]}

    url = db.query(URL).filter(URL.short_code == short_code).first()  # ← URL, не database.URL
    if not url:
        raise HTTPException(status_code=404, detail="URL not found")

    # Кэшируем
    cache.set_cached_url(short_code, {"original_url": url.original_url})
    return {"original_url": url.original_url}