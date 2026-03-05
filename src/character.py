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
    def proficiency_bonus(self) -> int:
        return self.data.get('proficiency_bonus', 2)

    @property
    def armor_class(self) -> int:
        return self.data.get('ac', 10)

    def get_attribute_modifier(self, attr_name: str) -> int:
        """Calculate standard D&D attribute modifier: (Score - 10) // 2"""
        score = self.data.get('attributes', {}).get(attr_name.lower(), 10)
        return (score - 10) // 2

    def get_skill_modifier(self, skill_name: str, base_attr: str) -> int:
        """Calculate total modifier including attribute and proficiency"""
        modifier = self.get_attribute_modifier(base_attr)
        proficiency = self.data.get('skills', {}).get(skill_name.lower(), 'normal')
        
        if proficiency == 'proficient':
            modifier += self.proficiency_bonus
        elif proficiency == 'expert':
            modifier += (self.proficiency_bonus * 2)
            
        return modifier

    def format_summary(self) -> str:
        """Returns a string summary of the character for the AI to understand"""
        summary = f"角色名字: {self.name}\n"
        summary += f"种族: {self.data.get('race', 'Unknown')}\n"
        summary += f"职业: {self.char_class}\n"
        summary += f"等级: {self.data.get('level', 1)}\n"
        summary += f"护甲等级(AC): {self.armor_class}\n\n"
        
        summary += "基础属性 (调整值):\n"
        for attr, score in self.data.get('attributes', {}).items():
            mod = self.get_attribute_modifier(attr)
            summary += f"- {attr.capitalize()}: {score} ({mod:+d})\n"
            
        summary += "\n熟练技能:\n"
        proficient_skills = [s for s, p in self.data.get('skills', {}).items() if p in ('proficient', 'expert')]
        if proficient_skills:
            for skill in proficient_skills:
                # We don't necessarily know the base attr here without a mapping, so just list them
                summary += f"- {skill.replace('_', ' ').capitalize()}\n"
        else:
            summary += "- 无\n"
            
        traits = self.data.get('traits', [])
        if traits:
            summary += "\n种族特性与天赋:\n"
            for t in traits:
                summary += f"- {t}\n"
                
        spells = self.data.get('spells', [])
        if spells:
            summary += "\n法术与可用能力:\n"
            for s in spells:
                summary += f"- {s}\n"
            
        return summary
