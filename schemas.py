from pydantic import BaseModel
import datetime
from typing import Optional


class UserBase(BaseModel):
    telegram_id: int
    username: Optional[str] = None

    class Config:
        orm_mode = True


class ExpenseBase(BaseModel):
    name: str
    uah: float
    usd: float


class ExpenseResponse(ExpenseBase):
    id: int
    user_id: int
    created_at: datetime.datetime

    class Config:
        orm_mode = True
