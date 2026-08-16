from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime

# Cria a API
app = FastAPI(title="Bank Notifications API")

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

    for notif in notifications:
        # Converte o timestamp do Android (milissegundos) para data legível
        data_hora = datetime.fromtimestamp(notif.timestamp / 1000.0).strftime('%d/%m/%Y %H:%M:%S')

        # Por enquanto, vamos apenas imprimir no terminal
        print(f"[{data_hora}] {notif.bankName}")
        print(f"Título: {notif.title}")
        print(f"Texto: {notif.content}")
        print("-" * 30)

    # O Android espera um HTTP 200 para apagar os dados do celular.
    # O FastAPI retorna 200 automaticamente se não houver erros.
    return {"status": "success", "message": f"{len(notifications)} notifications saved."}