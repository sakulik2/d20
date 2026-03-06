from abc import ABC, abstractmethod
from typing import Optional, Tuple

class BaseGameSystem(ABC):
    """
    Abstract Base Class representing a TRPG System (D20, CoC, etc.).
    It defines how the Python application interacts with the specific mechanics
    (rolling, combat, character generation).
    """
    
    @property
    @abstractmethod
    def system_id(self) -> str:
        """Unique ID for this system (e.g., 'd20', 'coc')."""
        pass
        
    @property
    @abstractmethod
    def system_name(self) -> str:
        """Display name for this system."""
        pass

    @abstractmethod
    def get_system_prompts(self) -> str:
        """
        Returns the specific prompt instructions required by this system.
        This string will be appended to the AI's general instructions to 
        teach it how to invoke this system's tags (like [ROLL...], [COMBAT_START...]).
        """
        pass

    @abstractmethod
    def build_character_generator_prompt(self, theme: str) -> str:
        """
        Returns the prompt needed for the AI to generate a character JSON
        compatible with this system.
        """
        pass

    @abstractmethod
    def parse_and_execute_roll(self, ai_response: str, character, dice_system, console) -> Tuple[bool, str]:
        """
        Scans the AI's response for specific roll tags (e.g. [ROLL: ...]),
        executes the UI prompt, rolls the dice, and returns:
        (was_game_interrupted, append_message_for_ai)
        """
        pass

    @abstractmethod
    def process_combat(self, ai_response: str, character, dice_system, console, ai_client) -> Tuple[bool, str]:
        """
        Handles combat state machine. Checks for combat triggers or manages ongoing turns.
        Returns: (is_combat_active, batched_results_for_ai)
        """
        pass

    @abstractmethod
    def format_character_summary(self, character) -> str:
        """
        Takes a Character instance and formats its attributes, math, 
        and traits according to this system's specific layout for display.
        """
        pass
        
    @abstractmethod
    def manual_gen(self, console, dice_system, base_dict: dict) -> dict:
        """
        Interactive Character Generation logic specific to this TRPG System.
        Provides a console UI for the user to step through the manual stat 
        allocation / dice rolls independently of LLM hallucination.
        Receives `base_dict` (containing name, backgrounds, etc.) and should 
        return the fully populated JSON dict.
        """
        pass

