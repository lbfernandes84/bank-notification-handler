from pydantic import BaseModel

class Notifications(BaseModel):
    banktitle: str
    title: str
    content: str
    timestamp: int