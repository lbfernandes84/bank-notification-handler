from datetime import datetime
from pydantic import BaseModel


class DroppedNotification(BaseModel):
    id: int | None = None
    bank_name: str
    transaction_title: str | None = None
    transaction_content: str
    timestamp_: int


class Notification(BaseModel):
    id: int | None = None
    type_: str = ""
    ammount: float = 0.0
    counterparty: str | None = None
    datetime_: datetime | None = None
    card_end_number: str | None = None
    extra_info: str = ""
