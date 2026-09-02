from dataclasses import dataclass
from datetime import datetime
import re
import json

@dataclass
class TransactionPattern:
    text: str
    ammount_integer_part: int
    ammount_cents: int
    destination : int | None = None
    sender : int | None = None
    datetime_month : int = 0
    datetime_day : int = 0
    datetime_hour : int = 0
    datetime_minute : int = 0
    card_end_number : int | None = None

@dataclass
class TransactionInfo:
    type: str = ""
    ammount: float = 0.0
    destination : str | None = None
    sender : str | None = None
    datetime_ : datetime | None = None
    card_end_number : int | None = None
    extra_info: str = ""

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

    def extract_info(self, notification:str, notification_time:datetime):
        info = TransactionInfo()
        for pattern in self.transaction_patterns:
            pattern_compiled = re.compile(pattern.text)
            match = pattern_compiled.fullmatch(notification)
            if match:
                info.type = self.label
                info.ammount = float(match.groups(pattern.ammount_integer_part)) + float(match.groups(pattern.ammount_cents))/100
                info.destination = match.groups(pattern.destination) if pattern.destination else None
                info.sender = match.groups(pattern.sender) if pattern.sender else None
                info.datetime_ = datetime(
                    notification_time.year,
                    int(match.groups(pattern.month)),
                    int(match.groups(pattern.day)),
                    int(match.groups(pattern.hour)),
                    int(match.groups(pattern.minute)),
                    0)
                if len(self.lookups) > 0 and pattern.card_end_number:
                    info.extra_info = self.lookups[int(match.groups(pattern.card_end_number))]
                return info
        return info

class TransactionInfoExtractor:

    def __init__(self, bank_name:str):
        self.bank_name = bank_name
        self.transactions_titles_map = {}
        self.transactions_types = {}

    def add_transaction_type(self, transaction_config : dict):
        name = transaction_config["name"]
        label = transaction_config["label"]
        patterns = transaction_config["patterns"]
        titles = transaction_config["titles"]
        lookups = transaction_config.get("lookups")
        self.transactions_types[name] = TransactionType(name, label, patterns)
        self.transactions_types[name].add_lookups(lookups)
        for title in titles:
            self.transactions_titles_map[title] = name

    def extract_info(self, title, text, notification_time)->TransactionInfo:
        target_transaction = self.transactions_titles_map[title]
        return self.transactions_types[target_transaction].extract_info(text, notification_time)

class NotifInfoExtractors:

    def __init__(self, settings_file):
        self.data = None
        self.titles = {}
        self.extractors_per_bank = {}
        with open(settings_file, "r", encoding="utf-8") as file:
            data = json.load(file)
            for extractor_config in data["notif_info_extractors"]:
                bank_name = extractor_config["bank"]
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



def load_notif_info_extractors()->dict:
    pass
