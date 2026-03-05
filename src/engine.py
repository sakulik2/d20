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
    def __init__(self, name: str, ac: int, hp: int, attack_bonus: int = 0, damage_dice: str = "1d4", is_player: bool = False, skills: Dict[str, str] = None):
        self.name = name
        self.ac = ac
        self.max_hp = hp
        self.hp = hp
        self.attack_bonus = attack_bonus
        self.damage_dice = damage_dice
        self.is_player = is_player
        self.skills = skills or {}
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
                skills=e_data.get("skills", {}),
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
        
        targets = [e for e in self.entities if not e.is_player and e.is_alive]
        player_entity = next(e for e in self.entities if e.is_player)
        
        action = Prompt.ask(
            "选择你的行动: [bold cyan](1) 普通攻击[/bold cyan] | [bold magenta](S) 法术/技能[/bold magenta] | [bold green](I) 道具使用[/bold green] | [dim](F) 逃跑[/dim] | [bold yellow](2) 剧情特殊动作 (交由DM裁决)[/bold yellow]",
            choices=["1", "s", "i", "f", "2"],
            default="1"
        )
        
        if action == "2":
            desc = Prompt.ask("描述你的特殊行动")
            return f"系统提示：玩家在战斗回合中选择了特殊剧情互动：'{desc}'。请 DM 根据当前形势要求玩家进行相应的技能属性检定，或者直接描绘结果。"
            
        elif action == "f":
            self.console.print("[dim]试图逃离战场... 需要进行敏捷(Dexterity)检定 (DC 15)。[/dim]")
            req = _create_dice_request("1d20")
            req.dc = 15
            req.attr = "dexterity"
            total, _, status = dice_system.prompt_roll(req, reason="逃跑检定")
            if "成功" in status:
                self.in_combat = False
                return "系统战斗判定：玩家进行了逃跑的敏捷检定并成功脱战！请生动描绘玩家是如何在这个危急关头逃亡的。"
            else:
                return "系统战斗判定：玩家试图逃跑但敏捷检定失败了，未能脱战，且浪费了这一回合。"
                
        elif action == "i":
            # Inventory MVP implementation
            inventory = character.data.setdefault("inventory", {"health_potions": 3})
            potions = inventory.get("health_potions", 0)
            if potions > 0:
                self.console.print(f"你使用了 [bold red]生命药水[/bold red] (剩余 {potions-1} 瓶)。")
                inventory["health_potions"] -= 1
                
                heal_req = _create_dice_request("2d4+2") # Standard 5e healing potion
                heal_amount, _, _ = dice_system.prompt_roll(heal_req, reason="血瓶恢复量")
                
                player_entity.hp = min(player_entity.max_hp, player_entity.hp + heal_amount)
                # Keep character JSON hp updated too
                character.data.setdefault("hp", {})["current"] = player_entity.hp
                
                return f"系统战斗判定：玩家消耗了一回合，喝下了一瓶生命药水，恢复了 {heal_amount} 点 HP，当前 HP: {player_entity.hp}。"
            else:
                self.console.print("[red]你的背包里没有生命药水了！行动作废。[/red]")
                return "系统战斗判定：玩家在背包里胡乱翻找一通却没有找到血瓶，浪费了一回合。"
                
        elif action == "s":
            spells = character.data.get("spells", [])
            if not spells:
                self.console.print("[red]你没有任何已知的职业法术或技能！[/red]")
                return self.execute_player_turn(dice_system, character) # recursive retry
                
            self.console.print("\n[bold magenta]已掌握的法术与技能:[/bold magenta]")
            for idx, spell in enumerate(spells):
                self.console.print(f"  [{idx+1}] {spell}")
            
            s_idx_str = Prompt.ask("选择要释放的法术编号，或输入 'c' 取消", default="c")
            if s_idx_str.lower() == 'c':
                return self.execute_player_turn(dice_system, character)
                
            try:
                spell_name = spells[int(s_idx_str) - 1]
            except Exception:
                spell_name = "未知能量脉冲"
                
            # Ask player targeting & damage
            self.console.print("可用目标:")
            for idx, t in enumerate(targets):
                self.console.print(f"  [{idx+1}] {t.name} (HP: {t.hp}/{t.max_hp})")
                
            t_idx_str = Prompt.ask("选择施法目标编号", choices=[str(i+1) for i in range(len(targets))])
            target = targets[int(t_idx_str) - 1]
            
            dice_formula = Prompt.ask("请输入该法术造成的伤害骰子公式 (如 2d6 / 1d10+2)，如果此法术无伤害直接回车", default="")
            result_str = f"系统战斗判定：玩家对 {target.name} 释放了技能/法术【{spell_name}】！"
            
            if dice_formula:
                dmg_req = _create_dice_request(dice_formula)
                dmg_total, _, _ = dice_system.prompt_roll(dmg_req, reason=f"法术 {spell_name} 伤害量")
                target.hp -= dmg_total
                result_str += f" 魔法威力造成了 {dmg_total} 点伤害。"
                if target.hp <= 0:
                    result_str += f" {target.name} 在法术的轰击下死亡！"
            else:
                result_str += f" 这是一个非直接伤害法术，请 DM 根据该法术的通常效果演化剧情。"
                
            return result_str
            
        else:
            # action "1" - Attack!
            self.console.print("可用目标:")
            for idx, t in enumerate(targets):
                self.console.print(f"  [{idx+1}] {t.name} (HP: {t.hp}/{t.max_hp})")
                
            t_idx_str = Prompt.ask("选择攻击目标编号", choices=[str(i+1) for i in range(len(targets))])
            target = targets[int(t_idx_str) - 1]
            
            # Request Attack Roll
            req = _create_dice_request("1d20")
            atk_total, rolls, _ = dice_system.prompt_roll(req, reason=f"对 {target.name} 发起攻击判定！(目标 AC: {target.ac})")
            raw_roll = rolls[0] if rolls else 0
            
            is_crit_success = (raw_roll == 20)
            is_crit_fail = (raw_roll == 1)
            
            result_str = ""
            if is_crit_fail:
                self.console.print("[bold red]大失败 (Critical Miss)！[/bold red]")
                result_str = f"系统判定：玩家试图普通攻击 {target.name} 时掷出了【大失败(1)】，攻击不仅完全落空，还可能导致了糟糕的后果。"
            elif is_crit_success or atk_total >= target.ac:
                if is_crit_success:
                    self.console.print("[bold magenta]🎉 大成功 (Critical Hit) 命中！伤害翻倍！🎉[/bold magenta]")
                else:
                    self.console.print("[bold green]命中！[/bold green]")
                    
                # Request Damage Roll. Standardizing to use character's main weapon or 1d8 as default
                dmg_req = _create_dice_request("1d8") # MVP default damage
                dmg_total, _, _ = dice_system.prompt_roll(dmg_req, reason=f"普通攻击造成多少伤害？")
                
                if is_crit_success:
                    dmg_total *= 2
                    
                target.hp -= dmg_total
                crit_text = "【大成功暴击(20)】" if is_crit_success else "成功命中"
                result_str = f"系统判定：玩家攻击了 {target.name}，掷出 {crit_text} (总值{atk_total} vs AC{target.ac})！造成了 {dmg_total} 点伤害。"
                if target.hp <= 0:
                    result_str += f" {target.name} 被惨烈击杀了！"
            else:
                self.console.print("[bold red]未命中！[/bold red]")
                result_str = f"系统战斗判定：玩家攻击了 {target.name}，攻击检定为 {atk_total} (对抗 AC {target.ac})，未命中。"
                
            return result_str + " 请用生动、血腥或暴力的修辞将以上冰冷的数值结果描绘成一段精彩的战斗画面。"

    def execute_enemy_turn(self, dice_system, entity: CombatEntity, player: CombatEntity) -> str:
        """Automatically rolls for the enemy and deducts player HP."""
        from src.dice import DiceRequest
        import random
        
        self.console.print(f"\n[bold red]>>> 【{entity.name} 的回合】 <<=[/bold red]")
        self.console.print(f"[dim]引擎正在为 {entity.name} 演算攻击...[/dim]")
        
        # Decide what attack to use
        attack_name = "普通攻击"
        damage_dice_to_use = entity.damage_dice
        
        if entity.skills and random.random() < 0.4:  # 40% chance to use a special skill if available
            skill_name, skill_dmg = random.choice(list(entity.skills.items()))
            attack_name = f"特殊技能【{skill_name}】"
            damage_dice_to_use = skill_dmg
        
        # Force virtual mode for enemy rolls
        original_mode = dice_system.mode
        dice_system.mode = "virtual"
        
        atk_req = _create_dice_request("1d20", is_dm_roll=True)
        atk_roll, rolls, _ = dice_system.prompt_roll(atk_req, reason=f"Enemy Attack ({attack_name})")
        raw_roll = rolls[0] if rolls else 0
        atk_total = atk_roll + entity.attack_bonus
        
        is_crit_success = (raw_roll == 20)
        is_crit_fail = (raw_roll == 1)
        
        result_str = ""
        if is_crit_fail:
            result_str = f"系统判定：怪物 {entity.name} 使用 {attack_name} 攻击玩家时掷出了【大失败(1)】，攻击不但落空，还可能让自己陷入了破绽之中。"
        elif is_crit_success or atk_total >= player.ac:
            dmg_req = _create_dice_request(damage_dice_to_use, is_dm_roll=True)
            dmg_total, _, _ = dice_system.prompt_roll(dmg_req, reason="Enemy Damage")
            
            if is_crit_success:
                dmg_total *= 2
                
            player.hp -= dmg_total
            crit_text = "【致命暴击(20)】" if is_crit_success else "成功命中"
            result_str = f"系统判定：怪物 {entity.name} 使用 {attack_name} 攻击了玩家，触发 {crit_text} (总计{atk_total} vs AC{player.ac})！对玩家造成了 {dmg_total} 点伤害。玩家当前剩余HP: {player.hp}。"
            if player.hp <= 0:
                result_str += " 玩家已被击倒！"
        else:
            result_str = f"系统判定：怪物 {entity.name} 使用 {attack_name} 攻击了玩家，攻击检定为 {atk_total} (对抗玩家 AC {player.ac})，未命中。"
            
        dice_system.mode = original_mode
        return result_str + f" 请生动描绘怪物 {entity.name} 是如何发起这次 {attack_name} 攻击的。"
