import sys
sys.path.append('.')
from src.engine import CombatEngine, CombatEntity
from rich.console import Console

console = Console()
engine = CombatEngine(console)

# Test combat JSON parsing with skills
json_str = """
[COMBAT_START: [{"name": "Boss", "hp": 30, "ac": 12, "attack_bonus": 5, "damage_dice": "1d8", "skills": {"Beam": "2d6", "Swipe": "1d8+2"}}]]
"""
enemies = engine.parse_combat_start(json_str)
print('Parsed enemies:', enemies)

engine.start_combat(enemies)
print('Enemy 0 skills:', engine.entities[0].skills)
print('Test Completed Successfully.')
