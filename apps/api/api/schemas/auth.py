"""Auth schemas.

Per ADR-015 (``.agent/adr/015-auth-hardening.md`` §15.7), every
mutation-bound schema in this module uses ``extra="forbid"`` to
prevent clients from setting fields the API does not expect.
Response schemas (UserOut) are unchanged — they are constructed by
the API, not parsed from the client.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class UserLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str


class UserOut(BaseModel):
    # Same fix as ``ArticleOut`` — pre-existing bug surfaced during #34
    # acceptance. /auth/login, /auth/register, /auth/me all hit this
    # when serializing a User ORM row.
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    created_at: datetime


class AuthResponse(BaseModel):
    user: UserOut
    token: str
