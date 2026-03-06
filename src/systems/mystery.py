from typing import Tuple
from src.systems.base import BaseGameSystem
from src.dice import DiceRequest
import re

class MysterySystem(BaseGameSystem):
    def __init__(self, console):
        self.console = console
        
    @property
    def system_id(self) -> str:
        return "mystery"
        
    @property
    def system_name(self) -> str:
        return "纯文字探案解谜 (无战斗/线索薄机制)"

    def get_system_prompts(self) -> str:
        return """
        【核心规则：线索收集与解谜】
        1. 这是一个没有战斗模块、没有复杂抛物线检定的纯文字推理游戏。玩家通过观察细节和对话来获取信息。
        2. 当玩家寻找线索，或者在现场勘查找到了一件有价值的关键物品时，你必须在独立行抛出指令将其记录到玩家的线索薄中：
           `[CLUE_FOUND: 沾血的怀表]`。本地系统会自动将这个线索录入到角色的证据库中。
        3. 对于偶尔需要测试运气的行为，可以简单地要求系统进行二元硬币抛掷（系统将处理成功/失败）：
           `[ROLL: 1d2 skill:运气 attr:1] 尝试在暗处摸索开关`
        """

    def build_character_generator_prompt(self, theme: str) -> str:
        return f"""
        You are a Master Detective guiding a player in a pure investigation text adventure set in {theme}.
        Generate a character sheet JSON with these keys: 
        "name", "class" (e.g. Detective, Forensic Expert, Journalist), "background", 
        "attributes" (Observation, Logic, Empathy, Intimidation - values from 1-10 describing proficiency level), 
        "clues" (leave this as an empty array []), 
        "inventory" (list of basic items like notebook, pen, magnifying_glass).
        Output ONLY valid JSON. Note that hp and ac are NOT needed.
        """

    def parse_and_execute_roll(self, ai_response: str, character, dice_system, console) -> Tuple[bool, str]:
        clue_matches = re.finditer(r"\[CLUE_FOUND:\s*(.*?)\]", ai_response, re.IGNORECASE)
        clue_found = False
        feedback_msgs = []
        
        for match in clue_matches:
            clue_str = match.group(1).strip()
            clues_list = character.data.setdefault("clues", [])
            if clue_str not in clues_list:
                clues_list.append(clue_str)
                console.print(f"\\n[bold yellow]🔍 提取到关键线索并记入线索薄：【{clue_str}】[/bold yellow]")
                feedback_msgs.append(f"System: 玩家成功将线索【{clue_str}】记录到了卷宗里。")
                clue_found = True
                
        # Handle regular 1d2 rolls if any
        roll_requests = dice_system.parse_all_roll_requests(ai_response)
        if roll_requests:
            for request in roll_requests:
                total, _, status = dice_system.prompt_roll(request)
                if total >= 2:
                    res = "成功 (Success)"
                else:
                    res = "失败 (Failure)"
                
                attr_name = request.skill if request.skill else "行动"
                msg = f"玩家尝试了 {attr_name}，需要大于等于 2。掷出了 {total}。结果为：{res}。"
                console.print(f"[bold cyan]结果: {msg}[/bold cyan]")
                feedback_msgs.append(msg)
                
        if clue_found or roll_requests:
            return True, "\\n".join(feedback_msgs)
            
        return False, ""

    def process_combat(self, ai_response: str, character, dice_system, console, ai_client) -> Tuple[bool, str]:
        # Investigation system has no combat.
        return False, ""

    def format_character_summary(self, character) -> str:
        summary = f"角色名字: {character.name}\n"
        summary += f"背景/职业: {character.char_class}\n\n"
        
        traits = character.data.get('traits', [])
        if traits:
            summary += "人物特写:\n"
            for t in traits:
                summary += f"- {t}\n"
                
        clues = character.data.get('clues', [])
        summary += f"\n已收集线索集 ({len(clues)}):\n"
        if clues:
            for c in clues:
                summary += f"- {c}\n"
        else:
            summary += "- 案卷一片空白\n"
            
        return summary

