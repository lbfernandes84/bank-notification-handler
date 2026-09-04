import json
import unittest
from datetime import datetime
from pathlib import Path

from notification_handler import (
    NotificationInfoExtractors,
    TransactionInfoExtractor,
    TransactionPattern,
    TransactionType,
)


class NotifInfoExtractorsTests(unittest.TestCase):

    def test_loads_configuration_objects_from_settings_json(self):
        tests_root = Path(__file__).resolve().parent
        patterns_path =  tests_root  / "files/patterns.json"

        with open(patterns_path, "r", encoding="utf-8") as patterns_file:
            settings = json.load(patterns_file)

        extractors = NotificationInfoExtractors(patterns_path)

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
            x = 1

    def test_extracts_info_from_debit_card_notification(self):
        tests_root = Path(__file__).resolve().parent
        patterns_path = tests_root / "files/patterns.json"

        extractors = NotificationInfoExtractors(patterns_path)

        text = (
            "Compra no valor de RS  42,40, CASA DE RACOES SILVA cartão final 6475 em 01/09/26. "
            "Caso não reconheça a transação clique no botão para BLOQUEAR o cartão."
        )

        info = extractors.extract(
            "Banco do Brasil",
            "Compra com cartão de débito",
            text,
            datetime(2026, 9, 1),
        )

        self.assertIsNotNone(info)
        self.assertEqual("Cartão de Débito", info.type)
        self.assertEqual(42.40, info.ammount)
        self.assertEqual("CASA DE RACOES SILVA", info.counterparty)
        self.assertEqual(datetime(2026, 9, 1), info.datetime_)
        self.assertEqual(6475, info.card_end_number)
        self.assertEqual("Ourocard", info.extra_info)

    def test_extracts_info_from_credit_card_notification(self):
        tests_root = Path(__file__).resolve().parent
        patterns_path = tests_root / "files/patterns.json"

        extractors = NotificationInfoExtractors(patterns_path)

        text = (
            "Compra de R$  139,99, realizada em Wellhub às 08:04 do dia 01/09, com cartão final 2691. "
            "Limite disponível:  5.061. Tenha vantagens exclusivas compartilhando seus dados. "
            "Caso não reconheça essa compra, clique em BLOQUEAR CARTÃO."
        )

        info = extractors.extract(
            "Banco do Brasil",
            "Compra com cartão de crédito",
            text,
            datetime(2026, 9, 1),
        )

        self.assertIsNotNone(info)
        self.assertEqual("Cartão de Crédito", info.type)
        self.assertEqual(139.99, info.ammount)
        self.assertEqual("Wellhub", info.counterparty)
        self.assertEqual(datetime(2026, 9, 1, 8, 4), info.datetime_)
        self.assertEqual(2691, info.card_end_number)
        self.assertEqual("", info.extra_info)


if __name__ == "__main__":
    unittest.main()
