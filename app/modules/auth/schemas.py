from typing import Optional

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: str

    @property
    def identifier(self) -> str:
        return (self.email or self.username or "").strip().lower()


class UserRead(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    full_name: str
    role: str
    is_active: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead
