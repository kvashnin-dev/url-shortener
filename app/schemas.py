from pydantic import BaseModel, field_validator
from urllib.parse import urlparse
from datetime import datetime
from typing import List

class UserCreate(BaseModel):
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class URLCreate(BaseModel):
    original_url: str

    @field_validator("original_url")
    def validate_url(cls, v):
        parsed = urlparse(v)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("Invalid URL format")
        return v

class URLResponse(BaseModel):
    id: int
    short_code: str
    original_url: str
    created_at: datetime 

    class Config:
        from_attributes = True

class URLList(BaseModel):
    urls: List[URLResponse]