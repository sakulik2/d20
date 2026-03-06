import re
import random
from typing import Tuple, Optional
from rich.console import Console
from rich.panel import Panel
from src.character import Character
from src.dice import DiceSystem, DiceRequest
from src.systems.base import BaseGameSystem

class ForgedInTheDarkSystem(BaseGameSystem):
    def __init__(self, console: Console):
        self.console = console

    @property
    def system_id(self) -> str:
        return "fitd"

    @property
    def system_name(self) -> str:
        return "Forged in the Dark"

    def get_system_prompts(self) -> str:
        return """
========================================
系统核心：Forged in the Dark
========================================

你现在是一名“Forged in the Dark” (暗夜本源) 游戏的主持人 (GM)。
你必须严格遵循以“Forged in the Dark (暗夜本源)”为核心的游戏机制：

1. **行动判定 (Action Roll)**
   - 当玩家角色尝试有挑战性、有风险的行动时，要求他们进行行动判定。
   - 要求玩家发送指令格式为：`[ACTION_ROLL: Nd6 action:技能名称]`，其中 N 是角色的该项技能值（0 到 4 之间）。
   - 你需要预先或者在判定前告知玩家当前的**处境 (Position)**（受控 Controlled / 冒险 Risky / 绝望 Desperate）以及**效果 (Effect)**（微弱 Limited / 标准 Standard / 极佳 Great）。
   - 系统会自动投骰子并返回成功等级：大成功 (Crit, 两个6)、完全成功 (Full Success, 6)、部分成功 (Mixed Success, 4-5)、失败 (Failure, 1-3)。如果 N=0，系统会投 2d6 并取最低值。
   - 基于系统返回的成功等级、处境和效果，你来描述后果（推演剧情，制造危机或给予奖励）。

2. **抵抗判定 (Resistance Roll)**
   - 玩家可以抵抗（减轻或完全避免）你施加的负面后果。
   - 玩家必须声明用哪一个属性（Insight 洞察 / Prowess 勇武 / Resolve 决心）来抵抗。
   - 要求玩家发送指令：`[RESIST_ROLL: Nd6 attr:属性名称]`，其中 N 是他们对应的属性值。
   - 抵抗必然会减轻后果，但玩家需要承受**压力 (Stress)**。系统会自动计算并扣除压力，公式为 `6 - 抵抗掷骰的最高值`。如果压力满（9点），系统会判定角色承受创伤 (Trauma) 并出局。

3. **消耗压力 (Stress & Pushing)**
   - 玩家可以选择“逼迫自己 (Push Yourself)”来获得掷骰+1d或提升效果，代价是承受 2 点压力。
   - 当玩家主动消耗压力时，要求他们发送：`[STRESS_INC: 数量]`，系统会自动将压力累加到角色卡上。

4. **切入机制 (Engagement Roll)**
   - FitD 强调“跳过无聊的计划阶段，直接切入核心行动”。当玩家群体决定了目标和进入方式（如潜行入内、社交混入、骇客突入）后，你需要立刻进行一次 **切入掷骰 (Engagement Roll)**。
   - 掷骰的骰池基于团队准备情况、盟友/敌人干预而定。你来扮演命运投掷 `[DM_ROLL: 1d6]`（或更多骰子结合优势）。结果决定了任务开始时的初始处境：Crit(受控+巨大利好)，6(受控)，4/5(冒险)，1-3(绝望：被包围、被发现或陷入陷阱)。

5. **倒叙机制 (Flashbacks)**
   - 由于跳过了计划阶段，玩家在任务中遇到阻碍时，可以使用 **倒叙 (Flashback)** 来宣告“我早就料到了，其实我之前已经...”。
   - 只要合乎逻辑，你必须允许这种做法！
   - 你需要根据倒叙行动的复杂度和不可能性来裁定**压力消耗**：普通前置准备(0压力)，复杂或高危的准备(1-2压力)，荒谬但勉强说得通的准备(3+压力)。并让玩家发送 `[STRESS_INC: X]` 结算，或者需要为此额外扔一次 Action Roll。

如果剧情需要结算掷骰或压力状态，请向玩家发送包含相应 `[TAG]` 的文本，系统后台程序会拦截并在终端结算！
"""

    def build_character_generator_prompt(self, user_description: str) -> str:
        return f"""
基于以下玩家的人物设定，请使用严谨的《Forged in the Dark》规则，为其生成一张符合引擎标准的角色卡（JSON 格式）。

玩家设定："'{user_description}'"

你必须严格使用以下格式返回。
1. **属性块 (attributes)**: 包含三大主属性值。每个属性值由其下属的四项行动技能（Actions）中拥有技能点的数量决定。
   - "Insight" (洞察): 影响 Doctor, Hack, Rig, Study
   - "Prowess" (勇武): 影响 Helm, Scramble, Scrap, Skulk
   - "Resolve" (决心): 影响 Attune, Command, Consort, Sway
   分配原则：初始角色三大属性每项至少为 1，至多为 4。这是用来做抵抗检定 (Resistance) 的骰子数。
2. **状态记录 (stats)**:
   - "Stress": 初始压力值为 0，最大不能超过 9。
   - "Traumas": 创伤列表，初始为空列表 []。
3. **技能 (actions)**: 包含上述 12 项行动技能。请根据玩家设定分配技能点：
   初始分配：分配 1 点到 3 个不同的技能，分配 2 点到 1 个技能，分配 1 点到由其剧本 (Playbook) 决定的技能，总计通常为 6-7 点。单项技能在创角时上限为 2。
   (例如 "Hack": 2, "Helm": 1, "Scramble": 1 等。未列出或值为 0 则视为 0 骰字)。
4. **物品**:填入 "inventory" 列表中，包含角色携带的几项经典工具和武器。
5. 请在 "class" 字段中填写角色的剧本 playbook (例如: Mechanic, Muscle, Mystic, Pilot, Scoundrel, Speaker, Stitch)。

仅返回一个纯 JSON 字符串（无需 Markdown 格式包裹），包含：name, class, background, attributes(字典), actions(字典), stats(字典), inventory(列表)。
"""

    def format_character_summary(self, character: Character) -> str:
        attr = character.data.get("attributes", {})
        actions = character.data.get("actions", {})
        stats = character.data.get("stats", {})
        name = character.data.get("name", "Unknown Scoundrel")
        role = character.data.get("class", "Scoundrel")
        
        stress = stats.get("Stress", 0)
        traumas = stats.get("Traumas", [])
        
        text = f"[bold cyan]身份:[/bold cyan] {name} ({role})\n"
        
        # Stress Bar
        stress_bar = ("■" * stress) + ("□" * (9 - stress))
        text += f"[bold red]==== 压力与创伤 (Stress & Trauma) ====[/bold red]\n"
        text += f"[bold magenta]压力 (Stress):[/bold magenta] [{stress_bar}] ({stress}/9)\n"
        text += f"[bold yellow]创伤 (Trauma):[/bold yellow] {', '.join(traumas) if traumas else '无 (None)'}\n"
        
        # Attributes and Actions
        text += "\n[bold cyan]==== 属性与行动 (Attributes & Actions) ====[/bold cyan]\n"
        
        insight = attr.get("Insight", 0)
        prowess = attr.get("Prowess", 0)
        resolve = attr.get("Resolve", 0)
        
        action_strs = []
        for k, v in actions.items():
            if v > 0:
                action_strs.append(f"{k}({v})")
                
        text += f"[bold white]洞察 (Insight): {insight}[/bold white] | [bold white]勇武 (Prowess): {prowess}[/bold white] | [bold white]决心 (Resolve): {resolve}[/bold white]\n"
        text += f"[bold green]专精行动:[/bold green] {', '.join(action_strs) if action_strs else '无'}\n"
        
        # Inventory
        inventory = character.data.get("inventory", [])
        if inventory:
            text += f"\n[bold yellow]==== 物品清单 (Inventory) ====[/bold yellow]\n"
            text += f"{', '.join(inventory)}\n"

        return text

    def parse_and_execute_roll(self, message: str, character: Character, dice: DiceSystem, console: Console) -> Tuple[bool, str]:
        sys_feedback = ""
        handled = False
        
        # 1. Action Roll: [ACTION_ROLL: 2d6 action:Hack]
        action_match = re.search(r'\[ACTION_ROLL:\s*(\d+)[dD]6(?:\s+action:([a-zA-Z0-9_\u4e00-\u9fa5]+))?\]', message, re.IGNORECASE)
        if action_match:
            num_dice = int(action_match.group(1))
            action_name = action_match.group(2) or "行动"
            
            # Action Roll Logic for FitD:
            # If dice > 0, roll Nd6 and take the highest single die.
            # If dice == 0, roll 2d6 and take the lowest single die.
            
            actual_dice = max(2, num_dice) if num_dice == 0 else num_dice
            res_total, res_rolls, _ = dice.prompt_roll(DiceRequest(f"{actual_dice}d6", actual_dice, 6), f"使用 {action_name} 行动")
            
            if num_dice == 0:
                final_result = min(res_rolls)
                roll_desc = f"掷 2 取低: {res_rolls} -> [bold red]最终看 {final_result}[/bold red]"
            else:
                final_result = max(res_rolls)
                # Check for critical (multiple 6s)
                sixes_count = sum(1 for face in res_rolls if face == 6)
                if sixes_count >= 2:
                    final_result = 7 # Internal representation for critical
                    roll_desc = f"掷 {num_dice} 取高: {res_rolls} -> [blink bold yellow]大成功 (CRITICAL)! 骰出 {sixes_count} 个 6！[/blink bold yellow]"
                else:
                    roll_desc = f"掷 {num_dice} 取高: {res_rolls} -> [bold cyan]最高面临 {final_result}[/bold cyan]"
            
            # Outcome
            if final_result >= 7:
                outcome = "[blink bold yellow]大成功 (Critical Success)[/blink bold yellow] - 效果极佳或超出预期！"
                sys_feedback += f"系统回传：玩家行动技能检定结果为【大成功 (Crit)】(投出了多个 6)。\n结合预先宣布的“处境与效果”，请描述玩家不仅完全达到了目的，还赢得了显著的额外好处或是增强了效果！"
            elif final_result == 6:
                outcome = "[bold green]完全成功 (Full Success)[/bold green] - 完美达成目的！"
                sys_feedback += f"系统回传：玩家行动技能检定结果为【完全成功 (6)】。\n结合“处境与效果”，玩家干净利落地达成了目标！即使是在绝望处境下也成功了（但仍会面临严重后果）。"
            elif final_result in (4, 5):
                outcome = "[bold magenta]部分成功 (Mixed Success)[/bold magenta] - 成功但带有代价！"
                sys_feedback += f"系统回传：玩家行动技能检定结果为【部分成功/代价 (4 或 5)】。\n玩家做到了他们想做的事，但作为 GM，你必须施加一个后果 (负面状态、引起注意、失去一点效果、受到伤害或消耗资源)。"
            else:
                outcome = "[bold red]失败 (Failure)[/bold red] - 未达成目标且面临后果！"
                sys_feedback += f"系统回传：玩家行动技能检定结果为【失败 (1-3)】。\n事情变得更糟了。请让情况恶化，不要让玩家毫无代价地再次尝试，必须引发严重的危机后果！"

            console.print(Panel(f"技能: {action_name} (骰池: {num_dice}d6)\n{roll_desc}\n结果: {outcome}", title="[bold blue]🎲 S&V 行动判定[/bold blue]", border_style="blue"))
            handled = True

        # 2. Resistance Roll: [RESIST_ROLL: 2d6 attr:Insight]
        resist_match = re.search(r'\[RESIST_ROLL:\s*(\d+)[dD]6(?:\s+attr:([a-zA-Z0-9_\u4e00-\u9fa5]+))?\]', message, re.IGNORECASE)
        if resist_match:
            num_dice = int(resist_match.group(1))
            attr_name = resist_match.group(2) or "抵抗属性"
            
            actual_dice = max(2, num_dice) if num_dice == 0 else num_dice
            res_total, res_rolls, _ = dice.prompt_roll(DiceRequest(f"{actual_dice}d6", actual_dice, 6), f"使用 {attr_name} 抵抗后果")
            
            if num_dice == 0:
                highest_face = min(res_rolls)
                roll_desc = f"掷 2 取低: {res_rolls} -> [bold red]最终看 {highest_face}[/bold red]"
            else:
                highest_face = max(res_rolls)
                # Crit on resistance means stress 0 and sometimes regain 1 stress (-1), but here standard rule is Stress cost = 6 - max
                sixes_count = sum(1 for face in res_rolls if face == 6)
                if sixes_count >= 2:
                    highest_face = 7 # Indicates crit clear
                    roll_desc = f"掷 {num_dice} 取高: {res_rolls} -> [blink bold green]大成功抵抗 (CRIT)! 不消耗压力，并且清除 1 点已有压力！[/blink bold green]"
                else:
                    roll_desc = f"掷 {num_dice} 取高: {res_rolls} -> [bold cyan]最高面临 {highest_face}[/bold cyan]"
            
            stress_cost = 6 - highest_face
            if highest_face == 7:
                stress_cost = -1
                
            stats = character.data.setdefault("stats", {})
            current_stress = stats.setdefault("Stress", 0)
            traumas = stats.setdefault("Traumas", [])
            
            new_stress = max(0, current_stress + stress_cost)
            trauma_added = False
            
            if new_stress > 9:
                new_stress = 0
                traumas.append("未定义创伤")
                trauma_added = True
                
            stats["Stress"] = new_stress
            stats["Traumas"] = traumas
            character.save()
            
            stress_cost_str = f"+{stress_cost}" if stress_cost >= 0 else str(stress_cost)
            out_msg = f"抵抗判定结束。\n由于最高骰面为 {highest_face}，你承受了 {stress_cost_str} 点压力。\n[bold magenta]当前压力: {new_stress} / 9[/bold magenta]"
            sys_msg_add = f"\n抵抗结算完成，玩家消耗了 {stress_cost} 点压力。后果已被极大减轻或避免！"
            
            if trauma_added:
                out_msg += f"\n[blink bold red]🚨 警告：压力超出极限！你获得了一个永久创伤 (Trauma)！你暂时退出了当前场景。[/blink bold red]"
                sys_msg_add += f"\n警告：玩家压力值达到10点顶峰，获得了一个永久的创伤(Trauma)！在本次任务中他很可能会暂时昏迷或失去行动力，请根据形势刻画他精神崩溃出局的瞬间！"
                
            console.print(Panel(f"抵抗属性: {attr_name} (骰池: {num_dice}d6)\n{roll_desc}\n{out_msg}", title="[bold green]🛡️ S&V 抵抗判定 (Resistance)[/bold green]", border_style="green"))
            sys_feedback += sys_msg_add
            handled = True

        # 3. Stress Increment: [STRESS_INC: 2]
        stress_match = re.search(r'\[STRESS_INC:\s*(\d+)\]', message, re.IGNORECASE)
        if stress_match:
            inc_val = int(stress_match.group(1))
            stats = character.data.setdefault("stats", {})
            current_stress = stats.setdefault("Stress", 0)
            traumas = stats.setdefault("Traumas", [])
            
            new_stress = current_stress + inc_val
            trauma_added = False
            if new_stress > 9:
                new_stress = 0
                traumas.append("未定义创伤")
                trauma_added = True
                
            stats["Stress"] = new_stress
            character.save()
            
            out_msg = f"你消耗了 [bold red]{inc_val}[/bold red] 点压力 (用于激发潜力、倒叙或其他机制)。\n[bold magenta]当前压力: {new_stress} / 9[/bold magenta]"
            sys_msg_add = f"\n规则强制推进：玩家牺牲了 {inc_val} 点压力以换取在叙事上的优势（如倒叙补救、追加额外效果）。"
            
            if trauma_added:
                out_msg += f"\n[blink bold red]🚨 警告：压力耗尽突破极限！你获得了一个永久创伤 (Trauma) 并失去意识退场！[/blink bold red]"
                sys_msg_add += f"\n警告：由于过度逼迫自己，玩家精神防线崩溃，获得了创伤并被迫退场！"
                
            console.print(Panel(out_msg, title="[magenta]🧠 意志极限 (Stress Cost)[/magenta]", border_style="magenta"))
            sys_feedback += sys_msg_add
            handled = True

        return handled, sys_feedback

    def process_combat(self, ai_response: str, character: Character, dice_system: DiceSystem, console: Console, ai_client) -> Tuple[bool, str]:
        # FitD has no traditional turn-based HP combat loop, it's all narrative action rolls.
        return False, ""

    def manual_gen(self, console, dice_system, base_dict: dict) -> dict:
        from rich.prompt import Prompt
        from rich.panel import Panel

        console.print(f"[bold white]Forged in the Dark 动作分配[/bold white]  7 点分配到各动作，单项最高 2。")

        actions = {
            "attune": 0, "command": 0, "consort": 0, "finesse": 0, 
            "hack": 0, "hunt": 0, "prowl": 0, "skirmish": 0, 
            "study": 0, "survey": 0, "sway": 0, "tinker": 0
        }
        
        action_names_cn = {
            "attune": "调谐(Attune)", "command": "统御(Command)", "consort": "结交(Consort)", 
            "finesse": "灵巧(Finesse)", "hack": "骇入(Hack)", "hunt": "狩猎(Hunt)", 
            "prowl": "潜行(Prowl)", "skirmish": "斗殴(Skirmish)", "study": "研究(Study)", 
            "survey": "洞察(Survey)", "sway": "煽动(Sway)", "tinker": "工匠(Tinker)"
        }
        
        points = 7
        
        while points > 0:
            console.print(f"\n[bold green]剩余可用点数: {points}[/bold green]")
            # Display current stats
            display = []
            for k, v in actions.items():
                if v > 0:
                    display.append(f"[cyan]{action_names_cn[k]}: {v}[/cyan]")
                else:
                    display.append(f"[dim]{action_names_cn[k]}: 0[/dim]")
                    
            for i in range(0, len(display), 4):
                console.print(" | ".join(display[i:i+4]))
                
            choice = Prompt.ask("\n请输入你要加 1 点的[bold yellow]动作英文名[/bold yellow] (如 hack, hunt, skirmish)")
            choice = choice.lower().strip()
            
            if choice in actions:
                if actions[choice] >= 2:
                    console.print(f"[red]{action_names_cn[choice]} 已经达到初始上限 2 点！请选择其他动作。[/red]")
                else:
                    actions[choice] += 1
                    points -= 1
                    console.print(f"[bold green]成功！{action_names_cn[choice]} 提升至 {actions[choice]}。[/bold green]")
            else:
                console.print(f"[red]未知的动作项：'{choice}'，请检查拼写。[/red]")
                
        # Calculate Attributes (Resistance)
        # Insight: Hack, Study, Survey, Tinker
        # Prowess: Finesse, Hunt, Prowl, Skirmish
        # Resolve: Attune, Command, Consort, Sway
        insight = sum(1 for a in ["hack", "study", "survey", "tinker"] if actions[a] > 0)
        prowess = sum(1 for a in ["finesse", "hunt", "prowl", "skirmish"] if actions[a] > 0)
        resolve = sum(1 for a in ["attune", "command", "consort", "sway"] if actions[a] > 0)
        
        attributes = {
            "insight": insight,
            "prowess": prowess,
            "resolve": resolve
        }
        
        console.print(f"\n[bold magenta]您的基础抗性属性根据动作点数倒推生成完毕：[/bold magenta]")
        console.print(f"洞察 (Insight): [bold cyan]{insight}[/bold cyan]  |  勇武 (Prowess): [bold red]{prowess}[/bold red]  |  决意 (Resolve): [bold yellow]{resolve}[/bold yellow]")
        
        base_dict["attributes"] = attributes
        base_dict["actions"] = actions
        base_dict["stats"] = {"Stress": 0, "Traumas": []} # Use the correct keys as per the prompt
        
        return base_dict
