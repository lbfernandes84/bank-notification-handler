import os
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

from db import get_supabase_client
from models import RawNotification, Notification
from notification_handler import NotificationInfoExtractors

# Cria a API
app = FastAPI(title="Bank Notifications API")

# Carrega os padrões de extração uma única vez, na subida da aplicação
PATTERNS_PATH = Path(__file__).resolve().parent / "patterns.json"
notif_info_extractors = NotificationInfoExtractors(PATTERNS_PATH)

# Define o formato exato que o Android vai mandar
class NotificationPayload(BaseModel):
    bankName: str
    title: str
    content: str
    timestamp: int

# Cria a rota de POST
@app.post("/api/v1/notifications/sync")
async def sync_notifications(notifications: list[NotificationPayload]):
    if os.environ.get("DEBUG") == "1":
        print(f"--- Recebidas {len(notifications)} notificações ---")

    raw_notifications = []
    extracted_infos = []
    for notif in notifications:
        # Converte o timestamp do Android (milissegundos) para data
        notif_datetime = datetime.fromtimestamp(notif.timestamp / 1000.0)

        if os.environ.get("DEBUG") == "1":
            print(f"[{notif_datetime.strftime('%d/%m/%Y %H:%M:%S')}] {notif.bankName}")
            print(f"Título: {notif.title}")
            print(f"Texto: {notif.content}")
            print("-" * 30)

        raw_notification = RawNotification(
            bank_name=notif.bankName,
            transaction_title=notif.title,
            transaction_content=notif.content,
            timestamp_=notif.timestamp,
        )
        raw_notifications.append(raw_notification.model_dump(exclude_unset=True))

        info = notif_info_extractors.extract(
            notif.bankName, notif.title, notif.content, notif_datetime
        )
        if info:
            extracted_infos.append(info.model_dump(mode="json", exclude_unset=True))
            if os.environ.get("DEBUG") == "1":
                print(info)

    supabase = get_supabase_client()
    if raw_notifications:
        supabase.table("RawNotifications").insert(raw_notifications).execute()
    if extracted_infos:
        supabase.table("Notifications").insert(extracted_infos).execute()

    # O Android espera um HTTP 200 para apagar os dados do celular.
    # O FastAPI retorna 200 automaticamente se não houver erros.
    return {"status": "success", "message": f"{len(notifications)} notifications saved."}

# Cria a rota de GET
@app.get("/api/v1/notifications", response_model=list[Notification])
async def get_notifications(timestamp: int) -> list[Notification]:
    supabase = get_supabase_client()
    from_datetime = datetime.fromtimestamp(timestamp / 1000.0)
    response = (
        supabase.table("Notifications")
        .select("*")
        .gte("datetime_", from_datetime.isoformat())
        .order("datetime_")
        .execute()
    )

    notifications = [Notification(**row) for row in response.data]
    if os.environ.get("DEBUG") == "1":
        for notif in notifications:
            print(notif)

    return notifications
