from typing import Tuple
from src.systems.base import BaseGameSystem
from src.dice import DiceRequest
import re
import random

COC_MANIAS = [
    "广场恐惧症 (死不愿出门)", "幽闭恐惧症 (畏缩于狭小空间)", 
    "偏执狂 (怀疑身边的所有人)", "暴食症 (止不住地往嘴里塞东西)",
    "被害妄想 (总觉得背后有视线)", "失语症 (无法说出连贯的句子)",
    "狂躁症 (情绪极其激荡暴走)"
]

class CoCSystem(BaseGameSystem):
    def __init__(self, console):
        self.console = console
        
    @property
    def system_id(self) -> str:
        return "coc"
        
    @property
    def system_name(self) -> str:
        return "克苏鲁的呼唤 D100 体系"

    def get_system_prompts(self) -> str:
        return """
        【核心规则：百分点体系 (D100)】
        1. 玩家的技能与属性满分为 100。检定时掷一次 1d100，结果【小于等于】技能数值即为成功。
        2. 为了引导系统判定，你必须在独立行抛出特定语法的指令给本地引擎：
           - **普通属性/技能检定**: `[ROLL: 1d100 skill:侦查 attr:50] 观察昏暗的地下室房间` (本地引擎将判断 1d100 是否 <= 50)
           - **奖惩骰**: 如果由于角色状态极佳或环境极劣，可以附加奖惩：`[ROLL: 1d100 bonus:1 skill:说服 attr:60]` 或 `[ROLL: 1d100 penalty:1 attr:40]`。
           - **理智值(SAN)检定**: 无以名状的恐惧出现时，要求 `[SAN_CHECK: 失败掉SAN值 (如 1d6) / 成功掉SAN值 (如 1 或 0)]`。系统会在本地自动扣除主角的 SAN 值并根据结果回复你角色是否陷入疯狂。
           - **无传统战斗**: 这个世界没有HP对砍的战斗画面！你只需通过检定要求、或者直接通过暗骰 `[DM_ROLL: 1d100]` 描述恐怖事件，然后让角色直面诡异与不可名状的结局。
        """

    def build_character_generator_prompt(self, theme: str) -> str:
        return f"""
        You are a Keeper of Arcane Lore generating a character for a Call of Cthulhu scenario set in {theme}.
        Generate a character sheet JSON with these keys: 
        "name", "class" (e.g. Investigator, Journalist), "background", 
        "hp" (dict with current, max, typically around 10-12),
        "san" (dict with current, max, typically around 50-80),
        "attributes" (strength, constitution, size, dexterity, appearance, intelligence, power, education - values 1-100), 
        "proficiencies" (list of skills like Spot Hidden, Library Use, Psychology with their values 1-100 formatted as "Spot Hidden: 60"), 
        "inventory" (list of realistic items like flashlight, revolver, notebook).
        Output ONLY valid JSON.
        """

    def parse_and_execute_roll(self, ai_response: str, character, dice_system, console) -> Tuple[bool, str]:
        # Handle regular ROLLs specifically with D100 logic
        # For CoC: [ROLL: 1d100 skill:侦查 attr:50]
        roll_requests = dice_system.parse_all_roll_requests(ai_response)
        san_match = re.search(r"\[SAN_CHECK:\s*([^/]+)\s*/\s*([^\]]+)\]", ai_response, re.IGNORECASE)
        
        if not roll_requests and not san_match:
            return False, ""
            
        feedback_msgs = []
        
        # 1. Handle regular skill rolls
        if roll_requests:
            for idx, request in enumerate(roll_requests):
                if idx > 0:
                    console.print("\\n[dim]-- 下一个连续检定 --[/dim]")
                    
                # Parse customized tags like bonus:1 or penalty:1 from the raw response
                # Since dice.py standard parser might drop unrecognized tags, we grep for it manually
                raw_notation_match = re.search(r"\[ROLL:[^\]]+\]", ai_response)
                bonus_dice = 0
                penalty_dice = 0
                if raw_notation_match:
                    raw_str = raw_notation_match.group(0).lower()
                    b_match = re.search(r"bonus:(\d+)", raw_str)
                    p_match = re.search(r"penalty:(\d+)", raw_str)
                    if b_match: bonus_dice = int(b_match.group(1))
                    if p_match: penalty_dice = int(p_match.group(1))
                    
                total, rolls, _ = dice_system.prompt_roll(request)
                
                # CoC Logic: <= attr is success
                target_attr = request.base_modifier if request.base_modifier else 50
                
                # Apply bonus/penalty logic for D100
                final_total = total
                if bonus_dice > 0 or penalty_dice > 0:
                    extra_tens = []
                    for _ in range(max(bonus_dice, penalty_dice)):
                        res, _, _ = dice_system.prompt_roll(DiceRequest("1d10", 1, 10))
                        num = res * 10 if res < 10 else 0
                        extra_tens.append(num)
                        
                    base_tens = (total // 10) * 10
                    units = total % 10
                    if base_tens == 100:
                        base_tens = 0
                    
                    all_tens = [base_tens] + extra_tens
                    if bonus_dice > 0:
                        best_tens = min(all_tens)
                        final_total = best_tens + units
                        if final_total == 0: final_total = 100
                        console.print(f"[dim]附加了 {bonus_dice} 颗奖励骰, 原始十位 {base_tens}, 额外十位 {extra_tens}, 取优十位 {best_tens} -> 最终结果: {final_total}[/dim]")
                    else:
                        worst_tens = max(all_tens)
                        final_total = worst_tens + units
                        if final_total == 0: final_total = 100
                        console.print(f"[dim]附加了 {penalty_dice} 颗惩罚骰, 原始十位 {base_tens}, 额外十位 {extra_tens}, 取劣十位 {worst_tens} -> 最终结果: {final_total}[/dim]")

                is_crit_fail = final_total >= 96
                is_crit_success = final_total <= 5
                
                status = ""
                if is_crit_fail:
                    status = "大失败 (Fumble)"
                elif is_crit_success:
                    status = "极难成功 (Extreme Success)"
                elif final_total <= target_attr:
                    if final_total <= target_attr / 5:
                        status = "极难成功 (Extreme Success)"
                    elif final_total <= target_attr / 2:
                        status = "困难成功 (Hard Success)"
                    else:
                        status = "成功 (Success)"
                else:
                    status = "失败 (Failure)"
                    
                attr_name = request.skill if request.skill else "目标"
                msg = f"玩家尝试了 {attr_name} 检定，需要小于等于 {target_attr}。最终掷出了 {final_total}。结果为：{status}。"
                
                # Ask to Push Roll and Burn Luck
                from rich.prompt import Prompt
                
                if final_total > target_attr and not is_crit_fail:
                    # 3. Burning Luck
                    current_luck = character.data.get("attributes", {}).get("luck", 50)
                    needed_luck = final_total - target_attr
                    
                    if needed_luck <= current_luck:
                        # Auto-mocking burn luck for test script
                        burn_q = getattr(self, "mock_burn", "n")
                        if not hasattr(self, "mock_burn"):
                            burn_q = Prompt.ask(f"[bold yellow]差一点点！你需要 {target_attr}，掷出了 {final_total}。你当前有 {current_luck} 点幸运值。是否燃烧 {needed_luck} 点幸运值来强行将结果改为成功？(y/n)[/bold yellow]", choices=["y", "n"], default="n")
                            
                        if burn_q.lower() == "y":
                            new_luck = current_luck - needed_luck
                            character.data.setdefault("attributes", {})["luck"] = new_luck
                            status = "孤注一掷成功 (Burned Luck Success)"
                            msg = f"玩家检定失败 ({final_total} > {target_attr})，但玩家剧烈燃烧了 {needed_luck} 点幸运值扭转了命运！结果改为：{status}。余下幸运值: {new_luck}。"
                            console.print(f"[bold green]>> 发动幸运逆转！余下幸运值: {new_luck}[/bold green]")
                        else:
                            # 2. Pushing the Roll if they don't burn luck
                            push_q = getattr(self, "mock_push", "n")
                            if not hasattr(self, "mock_push"):
                                push_q = Prompt.ask(f"[bold red]要进行孤注一掷 (Pushing the Roll) 吗？若重掷失败，你将面临极其恐怖的深渊反噬！(y/n)[/bold red]", choices=["y", "n"], default="n")
                                
                            if push_q.lower() == "y":
                                console.print("[bold red]>>> 开始孤注一掷！愿旧日支配者垂怜你！[/bold red]")
                                push_total, _, _ = dice_system.prompt_roll(request)
                                
                                if push_total <= target_attr:
                                    status = "孤注一掷成功 (Pushed Roll Success)"
                                    msg = f"玩家初始检定失败，但随后孤注一掷投出了 {push_total} <= {target_attr}！惊险战胜了绝境，结果为：{status}。"
                                else:
                                    status = "厄运降临 (Pushed Fumble)"
                                    msg = f"玩家孤注一掷彻底失败（掷出 {push_total} > {target_attr}），此时玩家陷入极其危险的被动。请直接描述最致命、最残酷的反击或深渊反噬！这将会是致命一击！"
                                console.print(f"[bold cyan]结果: {msg}[/bold cyan]")
                            else:
                                console.print(f"[bold cyan]结果: {msg}[/bold cyan]")
                    else:
                        console.print(f"[bold cyan]结果: {msg}[/bold cyan]")
                else:
                    console.print(f"[bold cyan]结果: {msg}[/bold cyan]")
                
                feedback_msgs.append(msg)
                
        # 2. Handle SAN Checks
        if san_match:
            fail_loss_dice = san_match.group(1).strip()
            succ_loss_dice = san_match.group(2).strip()
            
            console.print("\\n[bold magenta]!!! 发现不可名状之物：理智值(SAN) 检定 !!![/bold magenta]")
            current_san = character.data.get("san", {}).get("current", 50)
            
            san_req = DiceRequest("1d100", 1, 100, skill="理智(SAN)检定")
            total, _, _ = dice_system.prompt_roll(san_req)
            
            is_success = total <= current_san
            result_str = "成功 (Success)" if is_success else "失败 (Failure)"
            
            loss_dice_str = succ_loss_dice if is_success else fail_loss_dice
            
            # Simple manual roll for sanity loss string like "1d6" or "1"
            loss_val = 0
            if "d" in loss_dice_str.lower():
                try:
                    count, faces = map(int, loss_dice_str.lower().split("d"))
                    loss_req = DiceRequest(loss_dice_str, count, faces, skill="失去理智值")
                    loss_val, _, _ = dice_system.prompt_roll(loss_req)
                except ValueError:
                    loss_val = 1
            else:
                try:
                    loss_val = int(loss_dice_str)
                except ValueError:
                    loss_val = 1
            
            new_san = current_san - loss_val
            character.data.setdefault("san", {})["current"] = new_san
            
            msg = f"玩家进行了理智值(SAN)检定 (当前SAN: {current_san})，掷出 {total}。判定为 {result_str}。玩家失去了 {loss_val} 点理智值，目前剩余: {new_san}。"
            if loss_val >= 5:
                # Bouts of Madness
                mania = random.choice(COC_MANIAS)
                
                # traits can be a list or a dict containing lists depending on how it was generated
                traits_obj = character.data.get("traits")
                if isinstance(traits_obj, list):
                    if mania not in traits_obj:
                        traits_obj.append(mania)
                else:
                    traits_dict = character.data.setdefault("traits", {})
                    insanities = traits_dict.setdefault("insanity", [])
                    if mania not in insanities:
                        insanities.append(mania)
                        
                msg += f" 由于单次失去 5 点以上理智，玩家陷入了临时性疯狂(Temporary Insanity)！获得了疯狂后遗症：【{mania}】。请在接下来的剧情中强制扮演此缺陷！"
                console.print(f"[bold red]警告：玩家已陷入临时性疯狂！获得了心理创伤：{mania}[/bold red]")
                
            feedback_msgs.append(msg)
            
        feedback_msg = f"[System: {' '.join(feedback_msgs)}]"
        console.print(f"\\n[dim italic]>>> 正在将结果组合提交到 Keeper (DM)...[/dim italic]")
        return True, feedback_msg

    def process_combat(self, ai_response: str, character, dice_system, console, ai_client) -> Tuple[bool, str]:
        # CoC has no "Combat Engine" interception like D20. Return False immediately.
        return False, ""

    def format_character_summary(self, character) -> str:
        summary = f"调查员名字: {character.name}\n"
        summary += f"职业: {character.char_class}\n"
        hp_data = character.data.get('hp', {})
        summary += f"生命值(HP): {hp_data.get('current', 10)}/{hp_data.get('max', 10)}\n"
        
        san_data = character.data.get('san', {})
        summary += f"理智值(SAN): {san_data.get('current', 50)}\n"
        
        luck = character.data.get('attributes', {}).get('luck', 50)
        summary += f"幸运值(Luck): {luck}\n\n"
        
        summary += "基础属性与技能 (百分比):\n"
        for attr, score in character.data.get('attributes', {}).items():
            if attr.lower() != 'luck':
                summary += f"- {attr.capitalize()}: {score}%\n"
                
        traits = character.data.get('traits')
        if isinstance(traits, list) and traits:
            summary += "\n特质与背景:\n"
            for t in traits:
                summary += f"- {t}\n"
        elif isinstance(traits, dict):
            insanities = traits.get('insanity', [])
            if insanities:
                summary += "\n[bold red]精神创伤 (Bouts of Madness):[/bold red]\n"
                for i in insanities:
                    summary += f"- {i}\n"
                    
        return summary

    def manual_gen(self, console, dice_system, base_dict: dict) -> dict:
        from rich.prompt import Prompt
        from rich.panel import Panel
        from src.dice import DiceRequest

        console.print("[bold green]CoC D100 属性生成[/bold green]")

        final_attrs = {}
        
        # 1. 3d6 * 5 stats
        console.print("[dim]掷骰: 力量(STR), 体质(CON), 敏捷(DEX), 外貌(APP), 意志(POW) [3d6 * 5][/dim]")
        for attr, name in [("strength", "力量"), ("constitution", "体质"), ("dexterity", "敏捷"), ("appearance", "外貌"), ("power", "意志")]:
            req = DiceRequest("3d6", 3, 6)
            total, _, _ = dice_system.prompt_roll(req, reason=f"决定 {name}")
            final_attrs[attr] = total * 5
            
        # 2. (2d6+6) * 5 stats
        console.print("\n[dim]掷骰: 体型(SIZ), 智力(INT), 教育(EDU) [(2d6 + 6) * 5][/dim]")
        for attr, name in [("size", "体型"), ("intelligence", "智力"), ("education", "教育")]:
            req = DiceRequest("2d6", 2, 6)
            total, _, _ = dice_system.prompt_roll(req, reason=f"决定 {name}")
            final_attrs[attr] = (total + 6) * 5
            
        # 3. Derived stats
        hp_max = (final_attrs["strength"] + final_attrs["size"]) // 10
        san_max = final_attrs["power"]
        
        req = DiceRequest("3d6", 3, 6)
        luck_base, _, _ = dice_system.prompt_roll(req, reason="决定 幸运(Luck)")
        final_attrs["luck"] = luck_base * 5
        
        console.print(f"\n[bold magenta]生成的衍生属性:[/bold magenta]")
        console.print(f"最大生命值(HP): [bold red]{hp_max}[/bold red]  |  初始理智值(SAN): [bold cyan]{san_max}[/bold cyan]  |  幸运(Luck): [bold yellow]{final_attrs['luck']}[/bold yellow]")
        
        # 4. Skill allocation
        skill_points = final_attrs["education"] * 2 + final_attrs["intelligence"] * 2
        console.print(f"\n[bold yellow]技能点分配[/bold yellow]  共 [bold yellow]{skill_points}[/bold yellow] 点可用。")
        
        skill_mode = Prompt.ask(
            "(A)交给 AI 自动分配  (M)手动分配",
            choices=["a", "m"],
            default="a"
        )
        
        skills = {}
        if skill_mode == "m":
            console.print("输入格式: [技能名 点数]，例如 侦查 20。输入 done 结束。")
            while skill_points > 0:
                console.print(f"[dim]剩余: {skill_points}[/dim]")
                alloc = Prompt.ask("技能分配")
                if alloc.lower() == "done":
                    break
                parts = alloc.strip().split()
                if len(parts) == 2:
                    s_name = parts[0]
                    try:
                        s_pts = int(parts[1])
                        if s_pts > skill_points:
                            console.print(f"[red]点数不足（剩余 {skill_points}）[/red]")
                        elif s_pts < 0:
                            console.print("[red]不能为负数[/red]")
                        else:
                            skills[s_name] = skills.get(s_name, 20) + s_pts
                            skill_points -= s_pts
                            console.print(f"[green]{s_name} → {skills[s_name]}[/green]")
                    except ValueError:
                        console.print("[red]格式: 侦查 20[/red]")
                else:
                    console.print("[red]格式: 侦查 20[/red]")
        else:
            console.print("[dim]AI 将根据职业和属性自动分配技能点。[/dim]")
            # Pass the skill points budget to AI via meta field; AI flavor step will handle it
            base_dict["_skill_points_budget"] = skill_points
                
        base_dict["attributes"] = final_attrs
        base_dict["proficiencies"] = [f"{k}: {v}" for k, v in skills.items()] if skills else []
        base_dict["hp"] = {"current": hp_max, "max": hp_max}
        base_dict["san"] = {"current": san_max, "max": 99}
        
        return base_dict
