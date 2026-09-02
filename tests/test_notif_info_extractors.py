import json
import unittest
from pathlib import Path

from notification_handler import (
    NotifInfoExtractors,
    TransactionInfoExtractor,
    TransactionPattern,
    TransactionType,
)


class NotifInfoExtractorsTests(unittest.TestCase):
    def test_loads_configuration_objects_from_settings_json(self):
        project_root = Path(__file__).resolve().parents[1]
        settings_file = project_root / "settings.json"

        with settings_file.open("r", encoding="utf-8") as file:
            settings = json.load(file)

        extractors = NotifInfoExtractors(settings_file)

        for extractor_config in settings["notif_info_extractors"]:
            bank_name = extractor_config["bank"]

            self.assertIn(bank_name, extractors.extractors_per_bank)
            self.assertIsInstance(extractors.extractors_per_bank[bank_name], TransactionInfoExtractor)

            for bank_title in extractor_config["bank_titles"]:
                self.assertIn(bank_title, extractors.titles)
                self.assertEqual(bank_name, extractors.titles[bank_title])

            info_extractor = extractors.extractors_per_bank[bank_name]
            for transaction_config in extractor_config["transactions_config"]:
                transaction_name = transaction_config["name"]

                self.assertIn(transaction_name, info_extractor.transactions_types)
                self.assertIsInstance(info_extractor.transactions_types[transaction_name], TransactionType)

                transaction_type = info_extractor.transactions_types[transaction_name]
                self.assertEqual(transaction_config["label"], transaction_type.label)
                self.assertEqual(len(transaction_config["patterns"]), len(transaction_type.transaction_patterns))
                self.assertTrue(all(isinstance(pattern, TransactionPattern) for pattern in transaction_type.transaction_patterns))

                for title in transaction_config["titles"]:
                    self.assertIn(title, info_extractor.transactions_titles_map)
                    self.assertEqual(transaction_name, info_extractor.transactions_titles_map[title])


if __name__ == "__main__":
    unittest.main()
