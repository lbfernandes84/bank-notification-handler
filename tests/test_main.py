import asyncio
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from main import reprocess_dropped_notifications
from models import Notification


class ReprocessDroppedNotificationsTests(unittest.TestCase):

    def test_reprocesses_dropped_notifications_without_inserting_duplicates(self):
        timestamp = 1_780_300_800_000
        dropped_rows = [
            {
                "id": 1,
                "bank_name": "Banco do Brasil",
                "transaction_title": "Pix Recebido",
                "transaction_content": "Primeira notificação",
                "timestamp_": timestamp,
            },
            {
                "id": 2,
                "bank_name": "Banco do Brasil",
                "transaction_title": "Pix Recebido",
                "transaction_content": "Segunda notificação",
                "timestamp_": timestamp + 60_000,
            },
        ]
        existing_info = Notification(
            type_="Pix Entrada",
            ammount=10.0,
            datetime_=datetime.fromtimestamp(timestamp / 1000.0),
        )
        new_info = Notification(
            type_="Pix Entrada",
            ammount=20.0,
            datetime_=datetime.fromtimestamp((timestamp + 60_000) / 1000.0),
        )

        dropped_table = MagicMock()
        dropped_table.select.return_value = dropped_table
        dropped_table.gte.return_value = dropped_table
        dropped_table.order.return_value = dropped_table
        dropped_table.execute.return_value = SimpleNamespace(data=dropped_rows)

        notifications_table = MagicMock()
        notifications_table.select.return_value = notifications_table
        notifications_table.in_.return_value = notifications_table
        notifications_table.execute.return_value = SimpleNamespace(
            data=[existing_info.model_dump(mode="json")]
        )
        notifications_table.insert.return_value = notifications_table

        supabase = MagicMock()
        supabase.table.side_effect = lambda table_name: {
            "dropped_notifications": dropped_table,
            "notifications": notifications_table,
        }[table_name]

        with (
            patch("main.get_supabase_client", return_value=supabase),
            patch(
                "main.notif_info_extractors.extract",
                side_effect=[existing_info, new_info],
            ),
        ):
            result = asyncio.run(reprocess_dropped_notifications(timestamp))

        dropped_table.gte.assert_called_once_with("timestamp_", timestamp)
        notifications_table.insert.assert_called_once()
        inserted_rows = notifications_table.insert.call_args.args[0]
        self.assertEqual([new_info.model_dump(mode="json", exclude_unset=True)], inserted_rows)
        self.assertEqual(
            {
                "status": "success",
                "notifications_analyzed": 2,
                "notifications_saved": 1,
                "duplicates_skipped": 1,
            },
            result,
        )


if __name__ == "__main__":
    unittest.main()