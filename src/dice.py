import re
import random
from typing import Tuple, List, Optional

class DiceRequest:
    def __init__(self, notation: str, count: int, faces: int, base_modifier: int = 0, dc: Optional[int] = None, skill: str = "", attr: str = "", drop_lowest: int = 0, is_dm_roll: bool = False):
        self.notation = notation
        self.count = count
        self.faces = faces
        self.base_modifier = base_modifier
        self.dc = dc
        self.skill = skill
        self.attr = attr
        self.drop_lowest = drop_lowest
        self.is_dm_roll = is_dm_roll

    def __str__(self):
        dc_str = f" (DC: {self.dc})" if self.dc else ""
        tags = []
        if self.skill: tags.append(f"技:{self.skill}")
        if self.attr: tags.append(f"属:{self.attr}")
        tag_str = f" [{' '.join(tags)}]" if tags else ""
        mod_str = f"{self.base_modifier:+}" if self.base_modifier != 0 else ""
        return f"{self.count}d{self.faces}{mod_str}{dc_str}{tag_str}"

class DiceSystem:
    def __init__(self, console, mode: str = "virtual", character=None):
        self.console = console  # rich Console instance
        self.mode = mode
        self.character = character

    def set_mode(self, mode: str):
        if mode in ("virtual", "manual"):
            self.mode = mode
            self.console.print(f"[bold green]》系统提示：当前掷骰模式已切换为 '{self.mode}'[/bold green]")
        else:
            self.console.print(f"[bold red]无效模式: {mode}。请使用 '/dice virtual' 或 '/dice manual'。[/bold red]")

    def parse_all_roll_requests(self, command: str) -> List[DiceRequest]:
        """
        Parses all requests like: [ROLL: 1d20 DC15 skill:stealth attr:dexterity]
        or [DM_ROLL: 1d4+2 DC14] for NPC checks.
        Returns a list of DiceRequest objects.
        """
        requests = []
        # Matches [ROLL: 1d20+2 DC15 skill:stealth attr:dexterity]
        pattern = r'\[(DM_)?ROLL:\s*(\d+)d(\d+)(?:\s*([\+\-])\s*(\d+))?(?:\s+DC(\d+))?(?:\s+skill:(\w+))?(?:\s+attr:(\w+))?\]'
        for match in re.finditer(pattern, command, re.IGNORECASE):
            is_dm_roll = bool(match.group(1))
            count = int(match.group(2))
            faces = int(match.group(3))
            
            # Handle base modifier (e.g. +2 or -1)
            base_modifier = 0
            if match.group(4) and match.group(5):
                base_modifier = int(match.group(5))
                if match.group(4) == '-':
                    base_modifier = -base_modifier
                    
            dc = int(match.group(6)) if match.group(6) else None
            skill = match.group(7).lower() if match.group(7) else ""
            attr = match.group(8).lower() if match.group(8) else ""
            
            mod_str = f"{base_modifier:+}" if base_modifier != 0 else ""
            requests.append(DiceRequest(f"{count}d{faces}{mod_str}", count, faces, base_modifier, dc, skill, attr, is_dm_roll=is_dm_roll))
        return requests

    def prompt_roll(self, request: DiceRequest, reason: str = "") -> Tuple[int, List[int], str]:
        """
        Rolls the dice, applies character modifiers if present, and returns the result.
        Returns: (final_total, [list_of_individual_rolls], result_status_string)
        """
        if request.is_dm_roll:
            reason_str = f"（{reason}）" if reason else ""
            self.console.print(f"\n[bold yellow]🎲 NPC 暗中投掷 {request}{reason_str}[/bold yellow]")
        elif reason:
            self.console.print(f"\n[bold yellow]🎲 为【{reason}】投掷 {request}[/bold yellow]")
        else:
            self.console.print(f"\n[bold yellow]🎲 投掷 {request}[/bold yellow]")
        
        rolls = []
        effective_mode = "virtual" if request.is_dm_roll else self.mode
        
        if effective_mode == "virtual":
            self.console.print("[dim italic]系统自动抛出了虚拟骰子...[/dim italic]")
            rolls = [random.randint(1, request.faces) for _ in range(request.count)]
            if request.drop_lowest > 0 and len(rolls) > request.drop_lowest:
                sorted_rolls = sorted(rolls)
                dropped = sorted_rolls[:request.drop_lowest]
                raw_total = sum(rolls) - sum(dropped)
                self.console.print(f"抛出数字: {rolls} (自动扣除了最低的 {dropped}) -> 骰面有效总和: [bold]{raw_total}[/bold]")
            else:
                raw_total = sum(rolls)
                self.console.print(f"抛出数字: {rolls} -> 骰面总和: [bold]{raw_total}[/bold]")
        else:
            self.console.print(f"[bold cyan]✋ 请去现实中投掷真实的 {request.notation}。如果你算好了骰面总和，请在这里输入：[/bold cyan]")
            while True:
                try:
                    user_input = input(">> 骰面总和是：").strip()
                    raw_total = int(user_input)
                    rolls = [raw_total]
                    break
                except ValueError:
                    self.console.print("[red]这可不是数字，请告诉我掷出了几点。[/red]")

        # Calculate Modifier Total based on explicit base_modifier only
        modifier = request.base_modifier
        # DECOUPLED: Domain specific modifiers (like DND Stats) are now handled by the Systems themselves 
        # BEFORE they construct the DiceRequest, not here.

                
        final_total = raw_total + modifier
        if modifier != 0:
            self.console.print(f"最终判定值: {raw_total} {modifier:+} = [bold magenta]{final_total}[/bold magenta]")

        # Determine success status if DC is provided
        status = ""
        if request.dc is not None:
            # Check for criticals exclusively on d20 raw face value
            is_crit_success = (request.faces == 20 and rolls[0] == 20)
            is_crit_fail = (request.faces == 20 and rolls[0] == 1)
            
            if is_crit_success:
                status = "大成功 (Critical Success)"
            elif is_crit_fail:
                status = "大失败 (Critical Failure)"
            elif final_total >= request.dc:
                status = "成功 (Success)"
            else:
                status = "失败 (Failure)"
                    
            status_color = "green" if "成功" in status else "red"
            self.console.print(f"[{status_color}]判定结果: {status} (所需难度 DC {request.dc})[/{status_color}]")
            
        return final_total, rolls, status
