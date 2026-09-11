from dataclasses import dataclass
from datetime import datetime
import re
import json

@dataclass
class TransactionPattern:
    text: str
    ammount_integer_part: int
    ammount_cents: int
    counterparty : int | None = None
    datetime_year : int | None = 0
    datetime_month : int | None = 0
    datetime_day : int | None = 0
    datetime_hour : int | None = 0
    datetime_minute : int | None = 0
    card_end_number : str | None = None

@dataclass
class TransactionInfo:
    type: str = ""
    ammount: float = 0.0
    counterparty : str | None = None
    datetime_ : datetime | None = None
    card_end_number : int | None = None
    extra_info: str = ""

    def __repr__(self):
        return ",".join(self.type, self.ammount, self.counterparty, self.datetime_, self.card_end_number, self.extra_info)

class TransactionType:

    def __init__(self, name, label, patterns):
        self.name = name
        self.label = label
        self.transaction_patterns = []
        self.lookups = {}
        for pattern in patterns:
            self.transaction_patterns.append(TransactionPattern(**pattern))

    def add_lookups(self, lookups:list|None):
        if lookups:
            for lookup in lookups:
                self.lookups[lookup[0]] = lookup[1]

    def extract_info(self, bank_name:str, notification:str, notification_time:datetime)->TransactionInfo | None:
        for pattern in self.transaction_patterns:
            pattern_compiled = re.compile(pattern.text)
            match = pattern_compiled.fullmatch(notification)
            if match:
                info = TransactionInfo()
                info.type = self.label
                info.ammount = float(match.group(pattern.ammount_integer_part)) + float(match.group(pattern.ammount_cents))/100
                info.counterparty = match.group(pattern.counterparty) if pattern.counterparty else None
                year = notification_time.year if not pattern.datetime_year else int(match.group(pattern.datetime_year))
                month = notification_time.month if not pattern.datetime_month else int(match.group(pattern.datetime_month))
                day = notification_time.day if not pattern.datetime_day else int(match.group(pattern.datetime_day))
                hour = notification_time.hour if not pattern.datetime_hour else int(match.group(pattern.datetime_hour))
                minute = notification_time.minute if not pattern.datetime_minute else int(match.group(pattern.datetime_minute))
                if pattern.datetime_year and year < 100:  # 2-digit year in notification
                    year += 2000
                info.datetime_ = datetime(  # noqa: DTZ001
                    year,
                    month,
                    day,
                    hour,
                    minute,
                    0)
                if pattern.card_end_number:
                    info.card_end_number = match.group(pattern.card_end_number)
                    info.extra_info = bank_name
                    if len(self.lookups) > 0 and info.card_end_number in self.lookups:
                        info.extra_info = self.lookups[info.card_end_number]
                return info

class TransactionInfoExtractor:

    def __init__(self, bank_name:str, ignore_empty_titles:bool=False):
        self.bank_name = bank_name
        self.ignore_empty_titles = ignore_empty_titles
        self.transactions_types = {}

    def add_transaction_type(self, transaction_config : dict):
        name = transaction_config["name"]
        label = transaction_config["label"]
        patterns = transaction_config["patterns"]
        lookups = transaction_config.get("lookups")
        self.transactions_types[name] = TransactionType(name, label, patterns)
        self.transactions_types[name].add_lookups(lookups)

    def extract_info(self, bank_name:str, transaction_title:str, text:str, notification_time:datetime)->TransactionInfo | None:
        for transaction in self.transactions_types.values():
            info = None
            if transaction_title or not self.ignore_empty_titles:
                info = transaction.extract_info(bank_name, text, notification_time)
                if info:
                    return info


class NotificationInfoExtractors:

    def __init__(self, settings_file):
        self.data = None
        self.titles = {}
        self.extractors_per_bank = {}
        with open(settings_file, "r", encoding="utf-8") as file:
            data = json.load(file)
            for extractor_config in data["notif_info_extractors"]:
                bank_name = extractor_config["bank"]
                ignore_ = extractor_config["bank"]
                info_extractor = TransactionInfoExtractor(bank_name)
                bank_titles = extractor_config["bank_titles"]
                for title in bank_titles:
                    self.titles[title] = bank_name
                self.__add_transactions_extractors_config(info_extractor, extractor_config["transactions_config"])
                self.extractors_per_bank[bank_name] = info_extractor

    def __add_transactions_extractors_config(self, info_extractor:TransactionInfoExtractor,
                                             transactions_configs:list):
        for config in transactions_configs:
            info_extractor.add_transaction_type(config)

    def extract(self, bank_title, transaction_title, text, _datetime)->TransactionInfo | None:
        info = None
        bank_name = self.titles.get(bank_title)
        if bank_name:
            info = self.extractors_per_bank[bank_name].extract_info(bank_name, transaction_title, text, _datetime)
        return info



def load_notif_info_extractors()->dict:
    pass
