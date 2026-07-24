from pydantic import BaseModel, Field, field_validator
from datetime import datetime, date
from typing import List, Optional
import re

class UserBase(BaseModel):
    line_user_id: str
    nickname: Optional[str] = None
    notification_time: str = "21:00"
    report_day_of_week: int = Field(default=0, ge=0, le=6)
    report_time: str = "09:00"
    timezone: str = "Asia/Tokyo"

    @field_validator("notification_time", "report_time")
    @classmethod
    def validate_time(cls, value: str) -> str:
        if not re.match(r"^(?:[01]\d|2[0-3]):[0-5]\d$", value):
            raise ValueError("Time must be in HH:MM format (24-hour style, e.g., '21:30')")
        return value

class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    nickname: Optional[str] = None
    chat_state: Optional[str] = None
    notification_time: Optional[str] = None
    report_day_of_week: Optional[int] = Field(default=None, ge=0, le=6)
    report_time: Optional[str] = None
    timezone: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("notification_time", "report_time")
    @classmethod
    def validate_time(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not re.match(r"^(?:[01]\d|2[0-3]):[0-5]\d$", value):
            raise ValueError("Time must be in HH:MM format (24-hour style, e.g., '21:30')")
        return value

class UserSchema(UserBase):
    id: int
    chat_state: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class ExtraAnswerBase(BaseModel):
    question_key: str
    answer: str

class ExtraAnswerCreate(ExtraAnswerBase):
    pass

class ExtraAnswerSchema(ExtraAnswerBase):
    id: int
    entry_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class DailyEntryBase(BaseModel):
    date: date
    content: str

class DailyEntryCreate(DailyEntryBase):
    pass

class DailyEntrySchema(DailyEntryBase):
    id: int
    user_id: int
    created_at: datetime
    extra_answers: List[ExtraAnswerSchema] = []

    class Config:
        from_attributes = True

class WeeklyReportBase(BaseModel):
    start_date: date
    end_date: date
    report_content: str

class WeeklyReportCreate(WeeklyReportBase):
    pass

class WeeklyReportSchema(WeeklyReportBase):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True
