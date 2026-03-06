import json
from pathlib import Path

class Character:
    def __init__(self, data_file: str):
        self.data_file = Path(data_file)
        self.data = self._load()

    def _load(self) -> dict:
        if not self.data_file.exists():
            # If the file doesn't exist, start with an empty dict template
            return {}
        with open(self.data_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save(self):
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def update_from_dict(self, new_data: dict):
        """Overwrites the current character with new generated data and saves it"""
        if new_data:
            self.data = new_data
            self.save()

    @property
    def name(self) -> str:
        return self.data.get('name', 'Unknown Hero')

    @property
    def char_class(self) -> str:
        return self.data.get('class', 'Adventurer')

    @property
    def armor_class(self) -> int:
        return self.data.get('ac', 10)

