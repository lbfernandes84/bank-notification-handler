import asyncio
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from main import NotificationPayload, _cleanup_old_notifications, sync_notifications
from models import Notification

TIMESTAMP_MS = 1_780_300_800_000


def _make_supabase(dropped_select_data=None, notifications_select_data=None):
    dropped_table = MagicMock()
    dropped_table.select.return_value = dropped_table
    dropped_table.insert.return_value = dropped_table
    dropped_table.delete.return_value = dropped_table
    dropped_table.in_.return_value = dropped_table
    dropped_table.lt.return_value = dropped_table
    dropped_table.execute.return_value = SimpleNamespace(data=dropped_select_data or [])

    notifications_table = MagicMock()
    notifications_table.select.return_value = notifications_table
    notifications_table.insert.return_value = notifications_table
    notifications_table.delete.return_value = notifications_table
    notifications_table.lt.return_value = notifications_table
    notifications_table.in_.return_value = notifications_table
    notifications_table.execute.return_value = SimpleNamespace(data=notifications_select_data or [])

    supabase = MagicMock()
    supabase.table.side_effect = lambda table_name: {
        "dropped_notifications": dropped_table,
        "notifications": notifications_table,
    }[table_name]
    return supabase, dropped_table, notifications_table


class SyncNotificationsTests(unittest.TestCase):

    def test_cleanup_uses_start_of_previous_year_and_month(self):
        supabase, dropped_table, notifications_table = _make_supabase()

        _cleanup_old_notifications(supabase, datetime(2026, 10, 15, 12, 0, 0))

        notifications_table.lt.assert_called_once_with("datetime_", "2025-01-01T00:00:00")
        dropped_table.lt.assert_called_once_with(
            "timestamp_", int(datetime(2026, 9, 1).timestamp() * 1000)
        )
        notifications_table.execute.assert_called_once()
        dropped_table.execute.assert_called_once()

    def test_new_recognized_notification_is_inserted_into_notifications(self):
        payload = [
            NotificationPayload(
                bankName="Banco do Brasil", title="Pix Recebido", content="Texto", timestamp=TIMESTAMP_MS
            )
        ]
        recognized_info = Notification(
            type_="Pix Entrada", ammount=10.0, datetime_=datetime.fromtimestamp(TIMESTAMP_MS / 1000.0)
        )
        supabase, dropped_table, notifications_table = _make_supabase()

        with (
            patch("main.get_supabase_client", return_value=supabase),
            patch("main.notif_info_extractors.extract", side_effect=[recognized_info]),
        ):
            result = asyncio.run(sync_notifications(payload))

        notifications_table.insert.assert_called_once()
        inserted = notifications_table.insert.call_args.args[0]
        self.assertEqual([recognized_info.model_dump(mode="json", exclude_unset=True)], inserted)
        dropped_table.insert.assert_not_called()
        dropped_table.delete.assert_called_once()
        self.assertEqual(
            {
                "status": "success",
                "message": "1 notifications saved.",
                "duplicates_skipped": 0,
                "dropped_notifications_recovered": 0,
            },
            result,
        )

    def test_new_unrecognized_notification_is_inserted_into_dropped(self):
        payload = [
            NotificationPayload(
                bankName="Banco do Brasil", title="Pix Recebido", content="Texto", timestamp=TIMESTAMP_MS
            )
        ]
        supabase, dropped_table, notifications_table = _make_supabase()

        with (
            patch("main.get_supabase_client", return_value=supabase),
            patch("main.notif_info_extractors.extract", side_effect=[None]),
        ):
            result = asyncio.run(sync_notifications(payload))

        dropped_table.insert.assert_called_once()
        inserted_raw = dropped_table.insert.call_args.args[0]
        self.assertEqual(
            [
                {
                    "bank_name": "Banco do Brasil",
                    "transaction_title": "Pix Recebido",
                    "transaction_content": "Texto",
                    "timestamp_": TIMESTAMP_MS,
                }
            ],
            inserted_raw,
        )
        notifications_table.insert.assert_not_called()
        self.assertEqual(0, result["dropped_notifications_recovered"])

    def test_recognized_dropped_notification_is_inserted_and_removed(self):
        dropped_rows = [
            {
                "id": 5,
                "bank_name": "Banco do Brasil",
                "transaction_title": "Pix Recebido",
                "transaction_content": "Texto antigo",
                "timestamp_": TIMESTAMP_MS,
            }
        ]
        recognized_info = Notification(
            type_="Pix Entrada", ammount=20.0, datetime_=datetime.fromtimestamp(TIMESTAMP_MS / 1000.0)
        )
        supabase, dropped_table, notifications_table = _make_supabase(dropped_select_data=dropped_rows)

        with (
            patch("main.get_supabase_client", return_value=supabase),
            patch("main.notif_info_extractors.extract", side_effect=[recognized_info]),
        ):
            result = asyncio.run(sync_notifications([]))

        notifications_table.insert.assert_called_once()
        inserted = notifications_table.insert.call_args.args[0]
        self.assertEqual([recognized_info.model_dump(mode="json", exclude_unset=True)], inserted)
        self.assertEqual(2, dropped_table.delete.call_count)
        dropped_table.in_.assert_called_once_with("id", [5])
        self.assertEqual(1, result["dropped_notifications_recovered"])
        self.assertEqual(0, result["duplicates_skipped"])

    def test_recognized_duplicate_dropped_notification_is_removed_but_not_reinserted(self):
        dropped_rows = [
            {
                "id": 7,
                "bank_name": "Banco do Brasil",
                "transaction_title": "Pix Recebido",
                "transaction_content": "Texto antigo",
                "timestamp_": TIMESTAMP_MS,
            }
        ]
        duplicate_info = Notification(
            type_="Pix Entrada", ammount=30.0, datetime_=datetime.fromtimestamp(TIMESTAMP_MS / 1000.0)
        )
        existing_rows = [duplicate_info.model_dump(mode="json")]
        supabase, dropped_table, notifications_table = _make_supabase(
            dropped_select_data=dropped_rows, notifications_select_data=existing_rows
        )

        with (
            patch("main.get_supabase_client", return_value=supabase),
            patch("main.notif_info_extractors.extract", side_effect=[duplicate_info]),
        ):
            result = asyncio.run(sync_notifications([]))

        notifications_table.insert.assert_not_called()
        self.assertEqual(2, dropped_table.delete.call_count)
        dropped_table.in_.assert_called_once_with("id", [7])
        self.assertEqual(1, result["dropped_notifications_recovered"])
        self.assertEqual(1, result["duplicates_skipped"])

    def test_still_unrecognized_dropped_notification_is_left_untouched(self):
        dropped_rows = [
            {
                "id": 9,
                "bank_name": "Banco do Brasil",
                "transaction_title": "Pix Recebido",
                "transaction_content": "Texto antigo",
                "timestamp_": TIMESTAMP_MS,
            }
        ]
        supabase, dropped_table, notifications_table = _make_supabase(dropped_select_data=dropped_rows)

        with (
            patch("main.get_supabase_client", return_value=supabase),
            patch("main.notif_info_extractors.extract", side_effect=[None]),
        ):
            result = asyncio.run(sync_notifications([]))

        dropped_table.delete.assert_called_once()
        notifications_table.insert.assert_not_called()
        self.assertEqual(0, result["dropped_notifications_recovered"])
        self.assertEqual(0, result["duplicates_skipped"])


if __name__ == "__main__":
    unittest.main()
