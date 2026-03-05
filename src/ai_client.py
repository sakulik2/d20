import yaml
from pathlib import Path
from openai import OpenAI
import httpx # To handle localhost ollama weirdness gracefully if needed
from typing import Optional

class AIClient:
    def __init__(self, config_file: str = "config.yaml"):
        self.config_file = Path(config_file)
        self.config = self._load_config()
        self.client = self._init_client()
        self.model = self._get_model_name()
        
        # Keep track of conversation history
        self.history = []
        
    def _load_config(self) -> dict:
        if not self.config_file.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_file}")
        with open(self.config_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _init_client(self) -> OpenAI:
        provider_name = self.config.get("ai", {}).get("provider", "ollama")
        provider_config = self.config.get("ai", {}).get("providers", {}).get(provider_name, {})
        
        api_key = provider_config.get("api_key", "dummy-key")
        base_url = provider_config.get("base_url", "http://localhost:11434/v1")
        
        # For local ollama, we sometimes need a custom httpx client to avoid proxy issues
        http_client = httpx.Client()
        
        return OpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=http_client
        )

    def _get_model_name(self) -> str:
        provider_name = self.config.get("ai", {}).get("provider", "ollama")
        return self.config.get("ai", {}).get("providers", {}).get(provider_name, {}).get("model", "llama3")

    def load_scenario(self, system_prompt: str, character_summary: str):
        """Initializes the conversation with the GM prompt and character sheet"""
        full_system_prompt = f"{system_prompt}\n\n=== PLAYER CHARACTER ===\n{character_summary}\n====================\n\nNow, begin the adventure."
        self.history = [
            {"role": "system", "content": full_system_prompt}
        ]

    def add_user_message(self, message: str):
        self.history.append({"role": "user", "content": message})

    def add_assistant_message(self, message: str):
        self.history.append({"role": "assistant", "content": message})

    def generate_response(self) -> str:
        """Calls the LLM and returns the text response"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.history,
                temperature=0.7,
                max_tokens=800
            )
            content = response.choices[0].message.content
            self.add_assistant_message(content)
            return content
        except Exception as e:
            return f"[System Error: Failed to communicate with AI Provider - {str(e)}]"

    def generate_ruleset(self, user_theme_request: str) -> str:
        """Special method to dynamically generate a ruleset system prompt from a short description"""
        generator_prompt = f"""
        You are an expert tabletop RPG designer. The user wants to play a D20 text adventure with this specific theme: "{user_theme_request}".
        
        Generate a complete System Prompt for an AI Game Master in the style of the user's theme.
        
        CRITICAL RULES FOR THE GENERATED PROMPT:
        1. It must follow the exact structure of my examples (see below details).
        2. It MUST explicitly instruct the AI to use the specific formatting block when a dice roll is needed: `[ROLL: 1d20 DC15 skill:<skill> attr:<attribute>] Action` for player actions.
        3. Define relevant classes and skills for this specific universe.
        4. It MUST emphasize that all player attacks must set the DC to the target's Armor Class (AC), and all skill/ability checks must include an `attr` (and `skill` if applicable).
        5. It MUST explicitly instruct the AI to use `[DM_ROLL: 1d20 DC14]` for all NPC and Monster actions so the system can roll them secretly in the background. Do not add `attr` or `skill` to DM_ROLLs.
        6. The generated System Prompt MUST be written entirely in Chinese (简体中文), except for the mandatory English tags like [ROLL] and [DM_ROLL].
        
        Only output the raw text of the System Prompt, no markdown code blocks surrounding it.
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful RPG system designer."},
                    {"role": "user", "content": generator_prompt}
                ],
                temperature=0.8
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Failed to generate custom ruleset: {e}"

    def generate_character(self, player_description: str, ruleset_prompt: str) -> dict:
        """
        Takes a short description from the player (e.g. "A stealthy rogue who loves knives")
        and the current ruleset, and uses the LLM to generate a valid JSON character sheet.
        """
        prompt = f"""
        Based on the following world ruleset, create a starting character for the player.
        
        PLAYER REQUEST:
        "{player_description}"
        
        WORLD RULESET / THEME:
        "{ruleset_prompt}"
        
        OUTPUT FORMAT MUST BE VALID JSON ONLY, matching exactly this structure:
        {{
          "name": "Generated Name",
          "race": "Appropriate Race",
          "class": "Appropriate Class",
          "level": 1,
          "hp": {{ "current": 10, "max": 10 }},
          "ac": 13,
          "attributes": {{
            "strength": 10,
            "dexterity": 15,
            "constitution": 12,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 14
          }},
          "skills": {{
            "stealth": "proficient",
            "sleight_of_hand": "proficient"
          }},
          "traits": [
            "Darkvision: Can see in the dark up to 60ft.",
            "Fey Ancestry: Advantage against being charmed."
          ],
          "spells": [
            "Firebolt (Cantrip)",
            "Mage Armor (Level 1)"
          ],
          "proficiency_bonus": 2
        }}
        
        Assign reasonable attributes (ranging from 8 to 18), an Armor Class (ac) between 10-18, and a few proficient skills that fit the class/theme.
        Also provide 1-2 racial traits / class features in the 'traits' array. If the class uses spells or cyberware, list 1-3 starting abilities in the 'spells' array (or empty if none).
        Return ONLY the raw JSON string. Do not include markdown blocks like ```json.
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a mechanical character sheet generator. Only output JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                # if the model supports json format, we could force it, but for compatibility we just prompt hard
            )
            content = response.choices[0].message.content.strip()
            # Clean up potential markdown blocks if the LLM ignored the instruction
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
                
            import json
            return json.loads(content.strip())
        except Exception as e:
            print(f"Error generating character: {e}")
            return {}
