from pydantic import BaseModel

class Notifications(BaseModel):
    bankTitle: str
    title: str
    content: str
    timestamp: int