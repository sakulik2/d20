import json
from pathlib import Path
from typing import Optional, List, Tuple

class SaveManager:
    def __init__(self, saves_dir: str = "saves"):
        self.saves_dir = Path(saves_dir)
        self.saves_dir.mkdir(parents=True, exist_ok=True)

    def get_available_saves(self) -> List[str]:
        """Returns a list of available save folder names."""
        if not self.saves_dir.exists():
            return []
        # A valid save must be a directory containing savegame.json
        return [d.name for d in self.saves_dir.iterdir() if d.is_dir() and (d / "savegame.json").exists()]

    def save_game(self, save_name: str, ruleset_prompt: str, history: list, character_data: dict, combat_style: str = "engine") -> bool:
        """Saves the current adventure state (history, ruleset, character, and combat_style) to disk."""
        try:
            save_dir = self.saves_dir / save_name
            save_dir.mkdir(parents=True, exist_ok=True)
            
            save_data = {
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

    def load_game(self, save_name: str) -> Optional[Tuple[str, list, dict, str]]:
        """Loads the adventure state from disk and returns (ruleset_prompt, history, character_data, combat_style). Returns None on failure."""
        try:
            save_file = self.saves_dir / save_name / "savegame.json"
            if not save_file.exists():
                return None
                
            with open(save_file, "r", encoding="utf-8") as f:
                save_data = json.load(f)
                
            return (
                save_data.get("ruleset_prompt", ""), 
                save_data.get("history", []),
                save_data.get("character_data", {}),
                save_data.get("combat_style", "engine")
            )
        except Exception as e:
            print(f"Error loading game: {e}")
            return None
