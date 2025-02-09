from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional


class DisableMethod(str, Enum):
    PASSWORD = "password"

class WeekDay(str, Enum):
    MONDAY = "mon"
    TUESDAY = "tue"
    WEDNESDAY = "wed"
    THURSDAY = "thu"
    FRIDAY = "fri"
    SATURDAY = "sat"
    SUNDAY = "sun"


class PauseCondition(BaseModel):
    max_pause_days: Optional[int] = None
    pause_args: list[str] = []
    # require_streak: int


class Condition(PauseCondition):
    require_on: list[WeekDay]
    script: str
    args: list[str] = Field(default=[])
    # internal_script: Optional[str] = None
    pause_condition: Optional[PauseCondition] = None
    # pause_until: Optional[str] = None


class Config(BaseModel):
    enable_killswitch: bool = Field(default=True)
    blocked_websites: list[str]
    conditions: dict[str, Condition]
    disable_method: DisableMethod = Field(default=DisableMethod.PASSWORD)

    # Internal
    # pause_until: Optional[str] = None
    # hashed_password: Optional [str] = None
    # hosts_sha: Optional[str] = None
