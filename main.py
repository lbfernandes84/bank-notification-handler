from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

from db import get_supabase_client
from models import Notifications
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
    print(f"--- Recebidas {len(notifications)} notificações ---")

    rows = []
    for notif in notifications:
        # Converte o timestamp do Android (milissegundos) para data legível
        data_hora = datetime.fromtimestamp(notif.timestamp / 1000.0).strftime('%d/%m/%Y %H:%M:%S')

        # Por enquanto, vamos apenas imprimir no terminal
        print(f"[{data_hora}] {notif.bankName}")
        print(f"Título: {notif.title}")
        print(f"Texto: {notif.content}")
        print("-" * 30)

        row = Notifications(
            bankTitle=notif.bankName,
            title=notif.title,
            content=notif.content,
            timestamp=notif.timestamp,
        )
        rows.append(row.model_dump())

    supabase = get_supabase_client()
    supabase.table("Notifications").insert(rows).execute()

    # O Android espera um HTTP 200 para apagar os dados do celular.
    # O FastAPI retorna 200 automaticamente se não houver erros.
    return {"status": "success", "message": f"{len(notifications)} notifications saved."}

# Cria a rota de GET
@app.get("/api/v1/notifications")
async def get_notifications(timestamp: int):
    supabase = get_supabase_client()
    response = (
        supabase.table("Notifications")
        .select("*")
        .gte("timestamp", timestamp)
        .order("timestamp")
        .execute()
    )

    extracted_infos = []
    for row in response.data:
        notification_time = datetime.fromtimestamp(row["timestamp"] / 1000.0)
        info = notif_info_extractors.extract(
            row["bankTitle"], row["title"], row["content"], notification_time
        )
        if info:
            extracted_infos.append(info)

    return extracted_infos

# Cartao de credito BB
BB_CREDITO = r"Compra de R\$\s+(\d+)\,(\d{2}), realizada em (\w+) às (\d{2})\:(\d{2}) do dia (\d{2})\/(\d{2}), com cartão final \d{4}\."