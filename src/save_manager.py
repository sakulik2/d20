import json
from pathlib import Path
from typing import Optional, List, Tuple

class SaveManager:
    def __init__(self, saves_dir: str = "saves"):
        self.saves_dir = Path(saves_dir)
        self.saves_dir.mkdir(parents=True, exist_ok=True)

    def get_available_saves(self, system_id: str) -> List[str]:
        """Returns a list of available save folder names for the given system_id."""
        sys_saves_dir = self.saves_dir / system_id
        if not sys_saves_dir.exists():
            return []
            
        saves = []
        for d in sys_saves_dir.iterdir():
            if d.is_dir() and (d / "savegame.json").exists():
                saves.append(d.name)
        return saves

    def save_game(self, save_name: str, ruleset_prompt: str, history: list, character_data: dict, combat_style: str = "engine", system_id: str = "d20") -> bool:
        """Saves the current adventure state (history, ruleset, character, and combat_style) to disk."""
        try:
            save_dir = self.saves_dir / system_id / save_name
            save_dir.mkdir(parents=True, exist_ok=True)
            
            save_data = {
                "system_id": system_id,
                "ruleset_prompt": ruleset_prompt,
                "history": history,
                "character_data": character_data,
                "combat_style": combat_style
            }
            
            with open(save_dir / "savegame.json", "w", encoding="utf-8") as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Error saving game: {e}")
            return False

    def load_game(self, save_name: str, system_id: str) -> Optional[Tuple[str, list, dict, str, str]]:
        """Loads the adventure state from disk and returns (ruleset_prompt, history, character_data, combat_style, system_id). Returns None on failure."""
        try:
            save_file = self.saves_dir / system_id / save_name / "savegame.json"
            if not save_file.exists():
                return None
                
            with open(save_file, "r", encoding="utf-8") as f:
                save_data = json.load(f)
                
            return (
                save_data.get("ruleset_prompt", ""), 
                save_data.get("history", []),
                save_data.get("character_data", {}),
                save_data.get("combat_style", "engine"),
                save_data.get("system_id", "d20") # Default to d20 for legacy saves
            )
        except Exception as e:
            print(f"Error loading game: {e}")
            return None
