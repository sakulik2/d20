import json
import re
from typing import List, Dict, Optional
from rich.console import Console

def _create_dice_request(notation: str, is_dm_roll: bool = False):
    from src.dice import DiceRequest
    match = re.search(r'(\d+)d(\d+)(?:([\+\-])(\d+))?', notation)
    count, faces, mod = 1, 20, 0
    if match:
        count = int(match.group(1))
        faces = int(match.group(2))
        if match.group(3) and match.group(4):
            val = int(match.group(4))
            mod = val if match.group(3) == '+' else -val
    return DiceRequest(notation, count, faces, base_modifier=mod, is_dm_roll=is_dm_roll)

class CombatEntity:
    def __init__(self, name: str, ac: int, hp: int, attack_bonus: int = 0, damage_dice: str = "1d4", is_player: bool = False):
        self.name = name
        self.ac = ac
        self.max_hp = hp
        self.hp = hp
        self.attack_bonus = attack_bonus
        self.damage_dice = damage_dice
        self.is_player = is_player
        self.initiative = 0

    @property
    def is_alive(self) -> bool:
        return self.hp > 0

class CombatEngine:
    def __init__(self, console: Console):
        self.console = console
        self.in_combat = False
        self.entities: List[CombatEntity] = []
        self.turn_index = 0

    def start_combat(self, enemies_data: List[dict]):
        """Initializes combat state with a list of enemies."""
        self.in_combat = True
        self.entities = []
        self.turn_index = 0
        
        for e_data in enemies_data:
            self.entities.append(CombatEntity(
                name=e_data.get("name", "Unknown Enemy"),
                ac=e_data.get("ac", 10),
                hp=e_data.get("hp", 10),
                attack_bonus=e_data.get("attack_bonus", 0),
                damage_dice=e_data.get("damage_dice", "1d4"),
                is_player=False
            ))
        self.console.print(f"\n[bold red]⚔️ 战斗开始！发现 {len(self.entities)} 名敌人！[/bold red]")

    def add_player(self, name: str, ac: int, hp: int):
        # Remove old player entity if it exists to handle re-joining combat
        self.entities = [e for e in self.entities if not e.is_player]
        player = CombatEntity(name, ac, hp, is_player=True)
        self.entities.append(player)

    def roll_initiative(self, dice_system):
        """Rolls initiative for everyone and sorts the turn order."""
        self.console.print("[dim]正在决定先攻顺序 (Initiative)...[/dim]")
        for entity in self.entities:
            # Simplified initiative: just 1d20 + (dexterity mod if we have it, else 0)
            # For this MVP, we will just use a flat 1d20 + 0 for enemies, and ask the dice system for the player.
            req = _create_dice_request("1d20")
            
            if entity.is_player:
                total, _, _ = dice_system.prompt_roll(req, reason="投掷先攻 (Initiative)")
                entity.initiative = total
            else:
                # Enemies auto-roll in the background
                original_mode = dice_system.mode
                dice_system.mode = "virtual"
                total, _, _ = dice_system.prompt_roll(req, reason=f"Enemy {entity.name} Initiative")
                dice_system.mode = original_mode
                entity.initiative = total
                
        # Sort by highest initiative
        self.entities.sort(key=lambda x: x.initiative, reverse=True)
        
        self.console.print("\n[bold cyan]=========== 行动顺序 ===========[/bold cyan]")
        for idx, e in enumerate(self.entities):
            role = "👑 玩家" if e.is_player else "👹 怪物"
            self.console.print(f"[{idx+1}] {role} {e.name} (先攻: {e.initiative})")
        self.console.print("[bold cyan]================================[/bold cyan]\n")

    def get_current_turn_entity(self) -> CombatEntity:
        return self.entities[self.turn_index]

    def advance_turn(self):
        self.turn_index = (self.turn_index + 1) % len(self.entities)
        # Skip dead entities
        while not self.entities[self.turn_index].is_alive:
            self.turn_index = (self.turn_index + 1) % len(self.entities)

    def remove_dead_enemies(self) -> List[str]:
        dead = [e for e in self.entities if not e.is_player and not e.is_alive]
        self.entities = [e for e in self.entities if e.is_player or e.is_alive]
        return [e.name for e in dead]

    def check_combat_end(self) -> bool:
        """Returns True if combat is over (all enemies dead or player dead)."""
        player_alive = any(e.is_player and e.is_alive for e in self.entities)
        enemies_alive = any(not e.is_player and e.is_alive for e in self.entities)
        
        if not player_alive:
            self.console.print("\n[bold red]💀 玩家已阵亡...[/bold red]")
            self.in_combat = False
            return True
            
        if not enemies_alive:
            self.console.print("\n[bold green]🏆 战斗胜利！所有敌人已被消灭。[/bold green]")
            self.in_combat = False
            return True
            
        return False

    def parse_combat_start(self, ai_response: str) -> Optional[List[dict]]:
        """
        Looks for [COMBAT_START: [{...}]] JSON array in the AI response.
        """
        match = re.search(r'\[COMBAT_START:\s*(\[.*?\])\s*\]', ai_response, re.DOTALL)
        if match:
            json_str = match.group(1)
            try:
                enemies = json.loads(json_str)
                return enemies
            except json.JSONDecodeError as e:
                self.console.print(f"[dim red]Failed to parse combat JSON: {e}[/dim red]")
                return None
        return None

    def execute_player_turn(self, dice_system, character) -> str:
        """Presents a combat menu to the player and handles the attack resolution."""
        from rich.prompt import Prompt
        from src.dice import DiceRequest
        
        self.console.print(f"\n[bold green]>>> 【你的回合】 <<=[/bold green]")
        
        # Simple menu MVP
        action = Prompt.ask("选择你的行动: [bold cyan](1) 攻击[/bold cyan]  [bold yellow](2) 特殊行动/法术 (交由DM裁决)[/bold yellow]", choices=["1", "2"], default="1")
        
        if action == "2":
            desc = input("描述你的特殊行动 >> ")
            # Tell AI about the special action, we leave mechanical resolution of non-standard attacks to AI or DM parsing later
            return f"系统提示：玩家选择了特殊行动：'{desc}'。请 DM 根据当前形势要求玩家进行相应的技能属性检定。"
            
        else:
            # Attack!
            targets = [e for e in self.entities if not e.is_player and e.is_alive]
            self.console.print("可用目标:")
            for idx, t in enumerate(targets):
                self.console.print(f"  [{idx+1}] {t.name} (HP: {t.hp}/{t.max_hp})")
                
            t_idx_str = Prompt.ask("选择攻击目标编号", choices=[str(i+1) for i in range(len(targets))])
            target = targets[int(t_idx_str) - 1]
            
            # Request Attack Roll
            # We assume a basic melee/ranged attack using the D20 system. Let's just ask the player to roll a D20 for attack.
            # We add their highest str/dex mod if possible, but let's just keep it simple or ask them.
            req = _create_dice_request("1d20")
            atk_total, _, _ = dice_system.prompt_roll(req, reason=f"对 {target.name} 发起攻击判定！(目标 AC: {target.ac})")
            
            result_str = ""
            if atk_total >= target.ac:
                self.console.print("[bold green]命中！[/bold green]")
                # Request Damage Roll. Standardizing to use character's main weapon or 1d8 as default
                dmg_req = _create_dice_request("1d8") # MVP default damage
                dmg_total, _, _ = dice_system.prompt_roll(dmg_req, reason=f"造成多少伤害？")
                
                target.hp -= dmg_total
                result_str = f"系统战斗判定：玩家攻击了 {target.name}，攻击检定为 {atk_total} (对抗 AC {target.ac})，成功命中！造成了 {dmg_total} 点伤害。"
                if target.hp <= 0:
                    result_str += f" {target.name} 被击杀了！"
            else:
                self.console.print("[bold red]未命中！[/bold red]")
                result_str = f"系统战斗判定：玩家攻击了 {target.name}，攻击检定为 {atk_total} (对抗 AC {target.ac})，未命中。"
                
            return result_str + " 请用生动、血腥或暴力的修辞将以上冰冷的数值结果描绘成一段精彩的战斗画面。"

    def execute_enemy_turn(self, dice_system, entity: CombatEntity, player: CombatEntity) -> str:
        """Automatically rolls for the enemy and deducts player HP."""
        from src.dice import DiceRequest
        
        self.console.print(f"\n[bold red]>>> 【{entity.name} 的回合】 <<=[/bold red]")
        self.console.print(f"[dim]引擎正在为 {entity.name} 演算攻击...[/dim]")
        
        # Force virtual mode for enemy rolls
        original_mode = dice_system.mode
        dice_system.mode = "virtual"
        
        atk_req = _create_dice_request("1d20", is_dm_roll=True)
        atk_roll, _, _ = dice_system.prompt_roll(atk_req, reason="Enemy Attack")
        atk_total = atk_roll + entity.attack_bonus
        
        result_str = ""
        if atk_total >= player.ac:
            dmg_req = _create_dice_request(entity.damage_dice, is_dm_roll=True)
            dmg_total, _, _ = dice_system.prompt_roll(dmg_req, reason="Enemy Damage")
            player.hp -= dmg_total
            result_str = f"系统战斗判定：怪物 {entity.name} 攻击了玩家，攻击检定为 {atk_total} (对抗玩家 AC {player.ac})，成功命中！对玩家造成了 {dmg_total} 点伤害。玩家当前剩余HP: {player.hp}。"
            if player.hp <= 0:
                result_str += " 玩家已被击倒！"
        else:
            result_str = f"系统战斗判定：怪物 {entity.name} 攻击了玩家，攻击检定为 {atk_total} (对抗玩家 AC {player.ac})，未命中。"
            
        dice_system.mode = original_mode
        return result_str + f" 请生动描绘怪物 {entity.name} 是如何发起这次攻击的。"
