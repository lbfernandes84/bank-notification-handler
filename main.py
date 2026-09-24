import os
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from db import get_supabase_client
from models import DroppedNotification, Notification
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


def _dedup_key(type_: str, ammount: float, datetime_: datetime | str) -> tuple[str, float, str]:
    # Normaliza o datetime (objeto ou string vindo do banco) para o mesmo formato de comparação
    if isinstance(datetime_, str):
        datetime_ = datetime.fromisoformat(datetime_)
    return (type_, ammount, datetime_.isoformat())


def _filter_out_duplicate_infos(supabase, infos: list[Notification]) -> tuple[list[Notification], int]:
    datetimes = list({info.datetime_.isoformat() for info in infos if info.datetime_})
    existing_keys = set()
    if datetimes:
        response = (
            supabase.table("notifications")
            .select("type_, ammount, datetime_")
            .in_("datetime_", datetimes)
            .execute()
        )
        existing_keys = {
            _dedup_key(row["type_"], row["ammount"], row["datetime_"]) for row in response.data
        }

    seen_keys = set()
    filtered_infos = []
    duplicates_skipped = 0
    for info in infos:
        key = _dedup_key(info.type_, info.ammount, info.datetime_)
        if key in existing_keys or key in seen_keys:
            duplicates_skipped += 1
            continue
        seen_keys.add(key)
        filtered_infos.append(info)
    return filtered_infos, duplicates_skipped

# Cria a rota de POST
@app.post("/api/v1/notifications/sync")
async def sync_notifications(notifications: list[NotificationPayload]):
    try:
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
            info = notif_info_extractors.extract(
                notif.bankName, notif.title, notif.content, notif_datetime
            )
            if info:
                extracted_infos.append(info)
                if os.environ.get("DEBUG") == "1":
                    print(info)
            else:
                raw_notification = DroppedNotification(
                bank_name=notif.bankName,
                transaction_title=notif.title,
                transaction_content=notif.content,
                timestamp_=notif.timestamp,
                )
                raw_notifications.append(raw_notification.model_dump(exclude_unset=True))

        supabase = get_supabase_client()
        if raw_notifications:
            supabase.table("dropped_notifications").insert(raw_notifications).execute()

        duplicates_skipped = 0
        infos_to_insert = []
        if extracted_infos:
            infos_to_insert, duplicates_skipped = _filter_out_duplicate_infos(supabase, extracted_infos)
            if infos_to_insert:
                dumped_infos = [info.model_dump(mode="json", exclude_unset=True) for info in infos_to_insert]
                supabase.table("notifications").insert(dumped_infos).execute()

        # O Android espera um HTTP 200 para apagar os dados do celular.
        # O FastAPI retorna 200 automaticamente se não houver erros.
        return {
            "status": "success",
            "message": f"{len(notifications)} notifications saved.",
            "duplicates_skipped": duplicates_skipped,
        }
    except Exception as error:
        if os.environ.get("DEBUG") == "1":
            print(f"Erro ao sincronizar notificações: {error}")
        raise HTTPException(status_code=500, detail="Erro ao sincronizar notificações.") from error

# Cria a rota de GET
@app.get("/api/v1/notifications", response_model=list[Notification])
async def get_notifications(timestamp: int) -> list[Notification]:
    supabase = get_supabase_client()
    from_datetime = datetime.fromtimestamp(timestamp / 1000.0)
    response = (
        supabase.table("notifications")
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
