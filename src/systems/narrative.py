"""
Narrative Dice System (Phase 8)
A pure storytelling engine driven by Fate/PbtA mechanics.
No combat logic, no hard attributes. Just tags and 3-tier narrative results.
"""
from typing import Tuple
from src.systems.base import BaseGameSystem
from src.dice import DiceRequest
import re

class NarrativeSystem(BaseGameSystem):
    def __init__(self, console):
        self.console = console
        
    @property
    def system_id(self) -> str:
        return "narrative"
        
    @property
    def system_name(self) -> str:
        return "命运叙事系统 (纯文字驱动 / 2D6 / 多模态检定)"

    def get_system_prompts(self) -> str:
        return """
        【核心规则：纯叙事掷骰系统 (Narrative Dice Engine)】
        1. 这是一个没有战斗模块、没有血条和具体数值的纯文字剧情游戏。角色只有背景和几个“特长标签(Tags)”。
        2. 当玩家在剧情中试图做出一件有**挑战性**或者**关键转折**的行动时，你必须根据情境危险度，强制要求玩家进行命运掷骰。
        3. 你可以请求三种不同方差的骰子：
           - `[ROLL: 2d6]` (标准PbtA)：适合日常波折或连续的小挑战。
           - `[ROLL: 1d20]` (史诗检定)：适合命悬一线、大起大落的赌博式挑战。
           - `[ROLL: 1d100]` (写实概率)：适合需要细腻感知的检定，如探查、微操作。
        4. 玩家可以指出自己角色卡内的 `tags`（如“退役佣兵”）如果符合当前动作，他可以在检定时通过后缀加上 `+1` 补正，例如 `[ROLL: 2d6+1]` 或 `[ROLL: 1d20+2]`。
        5. **系统会拦截结果并强行断言**当前局势的发展（完全成功 / 带代价成功 / 厄运降临）。你**必须**在接下来的描述中，严格遵循本地引擎返还给你的基调来续写故事。尤其是当遇到“代价成功”或“厄运降临”时，你必须生动详尽地描写玩家遭受的严重麻烦或不可预知的反转！
        """

    def build_character_generator_prompt(self, theme: str) -> str:
        return f"""
        You are a collaborative storyteller guiding a player in a pure narrative text adventure set in {theme}.
        Generate a character sheet JSON with these keys: 
        "name", "background" (a 1-sentence origin), 
        "identity" (a short conceptual class/role phrase, like "Disgraced Knight" or "Amateur Hacker"),
        "tags" (an array of 3-5 short phrases describing their specific aptitudes, quirks, or flaws, e.g. ["Fear of fire", "Silver-tongued", "Crack shot"]), 
        "inventory" (list of key narrative items, no stats).
        Output ONLY valid JSON. Note that hp, ac, and standard attributes are NOT needed.
        """

    def parse_and_execute_roll(self, ai_response: str, character, dice_system, console) -> Tuple[bool, str]:
        roll_requests = dice_system.parse_all_roll_requests(ai_response)
        
        if not roll_requests:
            return False, ""
            
        feedback_msgs = []
        for roll_request in roll_requests:
            console.print(f"\\n[bold magenta]!!! 命运交汇：叙事节点判定 !!![/bold magenta]")
            total, rolls, _ = dice_system.prompt_roll(roll_request, reason="尝试扭转命运局势")
            
            faces = roll_request.faces
            count = roll_request.count
            
            result_str = ""
            ai_instruction = ""
            
            # 1. Standard PbtA / Fate (2d6 Scale)
            if faces == 6 and count == 2:
                if total >= 10:
                    console.print("[bold green]🌟 完全成功 (Triumph)！🌟[/bold green]")
                    result_str = f"完全成功 (>=10)。玩家以最完美的姿态完成了动作。"
                    ai_instruction = "请极其振奋地描写玩家是如何完美化解危机，甚至获得了意想不到的额外优势！局势大好！"
                elif total >= 7:
                    console.print("[bold yellow]⚠️ 代价成功 (Success with Consequence)...[/bold yellow]")
                    result_str = f"代价成功 (7-9)。玩家办到了，但必须付出代价。"
                    ai_instruction = "请描写玩家勉强达成了目标，但紧接着立刻给他抛出一个严峻的两难抉择、让他失去某件物品、受到伤害、或者引来新的敌人！这一幕必须让人难受！"
                else:
                    console.print("[bold red]💀 绝望降临 (Despair/Failure)！💀[/bold red]")
                    result_str = f"绝望失败 (<=6)。玩家的行动彻底搞砸了，或者世界对他们露出了獠牙。"
                    ai_instruction = "请毫不留情地让局势急转直下！玩家可能受重伤、被俘、或者引发了更恐怖的灾难，请用最戏剧性的笔触描写这个惨痛的失败局势！"
            
            # 2. Epic / High Variance (1d20 Scale)
            elif faces == 20:
                if total >= 15:
                    console.print("[bold green]🌟 史诗成功 (Epic Triumph)！🌟[/bold green]")
                    result_str = f"英雄般的成功 (>=15)。玩家如同天神下凡般完成了不可能的壮举。"
                    ai_instruction = "请用极度夸张热血的语调，描绘玩家是如何用不可思议的手段碾压了眼前的障碍，震撼全场！"
                elif total >= 8:
                    console.print("[bold yellow]⚠️ 艰难前行 (Mixed Result)...[/bold yellow]")
                    result_str = f"过程带有瑕疵的成功 (8-14)。玩家达成了基础目标，但场面一片狼藉。"
                    ai_instruction = "玩家做到了，但他可能极其狼狈，或者遗留下了极大的隐患。请在剧情中埋下一个随时会引爆的定时炸弹。"
                else:
                    console.print("[bold red]💀 悲惨挫折 (Critical Setback)！💀[/bold red]")
                    result_str = f"严重的挫败 (<=7)。运气抛弃了玩家。"
                    ai_instruction = "请描绘一个令人心碎的失败瞬间，玩家的某件心爱之物可能损毁，或者某个 NPC 可能会因为这次失败而牺牲。"
                    
            # 3. Realistic / Granular (1d100 Scale)
            elif faces == 100:
                if total >= 80:
                    console.print("[bold green]🌟 绝对优势 (Overwhelming Advantage)！🌟[/bold green]")
                    result_str = f"极其显著的成功 (>=80)。行动如丝般顺滑。"
                    ai_instruction = "请详尽刻画细节，描绘玩家行动中展现出的专业素养和绝对统治力。"
                elif total >= 40:
                    console.print("[bold yellow]⚠️ 勉力维系 (Struggling Success)...[/bold yellow]")
                    result_str = f"伴随高压的险胜 (40-79)。行动勉强通过，但玩家被推到了极限。"
                    ai_instruction = "请描写玩家在行动中承受了巨大的心理压力或生理摧残，气喘吁吁地刚好过了及格线。环境此时应该显得十分压抑。"
                else:
                    console.print("[bold red]💀 深渊凝视 (The Abyss Stares Back)！💀[/bold red]")
                    result_str = f"令人绝望的失误 (<=39)。玩家坠入了冰冷的低谷。"
                    ai_instruction = "环境、敌人或是命运立刻对玩家的破绽进行了最严厉的惩罚！请刻画出一种无力回天的窒息感。"
            else:
                # Custom dice fallback
                result_str = f"玩家抛掷了奇异的骰子，获得了 {total} 的结果。"
                ai_instruction = "请根据这个不可思议的点数大小，自由发挥该次动作的成败和剧情发展。"
                
            msg = f"玩家进行了命运判定 ({roll_request.notation} = {total})。系统强制干预结果：{result_str} | AI 必须执行的后置叙事指令：{ai_instruction}"
            feedback_msgs.append(msg)
            
        feedback_msg = f"\\n[System: {' '.join(feedback_msgs)}]"
        return True, feedback_msg

    def process_combat(self, ai_response: str, character, dice_system, console, ai_client) -> Tuple[bool, str]:
        # Pure narrative system has no strict combat mechanism
        return False, ""

    def format_character_summary(self, character) -> str:
        summary = f"主角身份: {character.name} - {character.data.get('identity', '无名之辈')}\n"
        
        bg = character.data.get('background', '')
        if bg:
            summary += f"\n背景故事:\n{bg}\n"
            
        tags = character.data.get('tags', [])
        summary += f"\n核心标签 (Tags):\n"
        if tags:
            for t in tags:
                summary += f"✦ {t}\n"
        else:
            summary += "✦ (无显著特征)\n"
            
        inventory = character.data.get('inventory', [])
        if inventory:
            summary += "\n关键行囊:\n"
            if isinstance(inventory, list):
                for item in inventory:
                    summary += f"- {item}\n"
            elif isinstance(inventory, dict):
                for k, v in inventory.items():
                    summary += f"- {k}: {v}\n"
                    
        return summary
