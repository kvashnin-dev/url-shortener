from pydantic import BaseModel

class URLCreate(BaseModel):
    original_url: str

class URLResponse(BaseModel):
    short_code: str
    original_url: str