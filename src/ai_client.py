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
        combat_style = self.config.get("game", {}).get("combat_style", "engine")
        style_override = ""
        
        if combat_style == "narrative":
            style_override = "\n\n=== 战斗系统重要覆盖 ===\n当前系统处于【叙事化战斗模式 (Narrative Mode)】！\n你绝对不可以使用 [COMBAT_START: ...] 指令！请忽略系统提示词中原本要求你使用 COMBAT_START 进入战斗引擎的任何内容。\n当战斗爆发时，请直接将其视为普通的剧情检定，通过要求玩家进行 [ROLL: ...]（例如掷骰攻击），以及你自己使用 [DM_ROLL: ...] 来暗骰决定结果。保持回合间的平滑语言交流，不要锁定游戏。所有战斗结果由你凭叙事和掷骰结果自行判断与推演。\n====================\n"
            
        full_system_prompt = f"{system_prompt}{style_override}\n\n=== PLAYER CHARACTER ===\n{character_summary}\n====================\n\nNow, begin the adventure."
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

    def generate_ruleset(self, user_theme_request: str, system_instructions: str = "") -> str:
        """Special method to dynamically generate a ruleset system prompt from a short description"""
        generator_prompt = f"""
        You are an expert tabletop RPG designer. The user wants to play a text adventure with this specific theme: "{user_theme_request}".
        
        Generate a complete System Prompt for an AI Game Master in the style of the user's theme.
        
        CRITICAL RULES FOR THE GENERATED PROMPT:
        1. It must follow the exact structure of my examples (see below details).
        {system_instructions}
        2. It MUST include a strict rule forbidding the AI from ending, summarizing, or concluding the story. The AI must keep throwing new hooks, mysteries, or encounters to ensure infinite gameplay unless the user explicitly types a quit command.
        3. The generated System Prompt MUST be written entirely in Chinese (简体中文), except for the mandatory English tags.
        
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

    def evaluate_combat_style(self, theme_or_ruleset: str) -> str:
        """Asks the LLM to decide whether this worldview should use engine or narrative combat."""
        prompt = f"""
        Based on the following world ruleset/theme, decide if a strict turn-based combat system (like tactical D&D) or a loose, narrative-driven combat system (like Call of Cthulhu or storytelling focus) is more appropriate.
        
        Theme:
        "{theme_or_ruleset}"
        
        Reply with ONLY the word "engine" or "narrative" in lowercase. No other text.
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a system analyzer. Reply strictly with 'engine' or 'narrative'."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            content = response.choices[0].message.content.strip().lower()
            return "narrative" if "narrative" in content else "engine"
        except Exception:
            return "engine"

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
