import re
import random
from typing import Tuple, Optional
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from src.character import Character
from src.dice import DiceSystem, DiceRequest
from src.systems.base import BaseGameSystem

class CyberpunkSystem(BaseGameSystem):
    def __init__(self, console: Console):
        self.console = console

    @property
    def system_id(self) -> str:
        return "cyberpunk"

    @property
    def system_name(self) -> str:
        return "Cyberpunk Red Interlock"

    def get_system_prompts(self) -> str:
        return """
========================================
系统核心：赛博朋克 Red (Interlock) 规则引擎
========================================

你现在是一名残酷无情的“赛博朋克: 边缘行者 / Red”游戏裁判 (DM)。
你必须严格遵循以下 Interlock 核心游戏机制来裁判动作，不准使用 DND 规则：

1. **核心动作检定 (Stat + Skill + 1d10)**
   - 当玩家进行有挑战的动作时，要求他们进行相关技能测试。格式为 `[ROLL: 1d10 skill:技能名称 attr:属性名称]`。
   - 玩家的最终结果总是 `1d10掷骰结果 + 属性值 + 技能值`。
   - 对抗难度 (DV) 分级：简单(DV 9)，日常(DV 13)，困难(DV 15)，极难(DV 17)，英雄(DV 21)，不可能(DV 29)。
   - **爆炸骰与大失败**：系统底层会自动处理 10点爆炸增持与 1点大失败扣减，你只需要看引擎最终推算出的“最终判定值”即可，并基于此生成夸张的剧情。

2. **暴力与护甲消融 (Combat & Ablative Armor)**
   - 战斗节奏极快且致命。要求玩家进行攻击命中检定 (如使用手枪：`[ROLL: 1d10 skill:Handgun attr:REF]`) 对抗目标的闪避或固定 DV。
   - 命中后，要求玩家进行伤害掷骰，如 `[ROLL: 3d6 damage]`。
   - **护甲结算**：计算好伤害后，你必须发送指令 `[APPLY_DAMAGE: X]`（X为伤害总额）。系统引擎会自动查询角色的 SP 护甲值进行减法结算，并自动处理 SP 永久 -1 的破损逻辑。

3. **双 6 重创机制 (Critical Injuries)**
   - 当大模型生成了包含至少两个 6 的伤害骰时，系统会自动捕捉暴击，并产生额外 5 点极恶劣的真伤。你需要针对这种情况，渲染受残疾重创的影响！

4. **赛博精神病与人性 (Humanity Loss)**
   - 每次安装强力义体，玩家必须失去一定的人性值。
   - 发送指令如 `[HUMANITY: -2d6]` 或固定值 `[HUMANITY: -4]`，系统会自动削弱其状态，并按 `Humanity // 10` 更新 EMP。归零失去游戏控制权。

5. **死亡交锋 (Death Saves)**
   - 当玩家进行到濒死状态时，每回合强制要求玩家发出 `[DEATH_SAVE]` 指令，这事关生死！

如果剧情需要使用以上机制，请直接发送对应的 `[TAG]`，系统后台程序会拦截并在玩家终端产生运算结果！
"""

    def build_character_generator_prompt(self, user_description: str) -> str:
        return f"""
基于以下玩家的人物设定，请使用严谨的《Cyberpunk Red》规则，为其生成一张符合引擎标准的角色卡（JSON 格式）。

玩家设定："'{user_description}'"

你必须严格使用以下格式返回。
1. **属性块 (attributes)**: 必须包含以下九大主属性 (数值设定在 2 到 8 之间)：
   - "INT" (智力), "REF" (反应 - 影响枪械命中), "DEX" (灵巧 - 影响近战与闪避), "TECH" (技术)
   - "COOL" (酷/意志), "WILL" (意志力), "LUCK" (幸运 - 可以消耗来增加判定值)
   - "MOVE" (移动力), "BODY" (躯体 - 影响生命值上限和死亡豁免), "EMP" (共情 - 影响人性和社交)
2. **状态记录 (stats)**:
   - "HP": 最大生命值。公式 = 10 + 5 * ((BODY + WILL) / 2 向上取整)。
   - "MaxHP": 同上。
   - "Humanity": 初始人性值。公式 = EMP * 10。
   - "SP": 初始护甲阻挡值 (如果是穿了 Kevlar，通常是 7；如果是重型装甲，可以是 11 但减 DEX)。初始给个轻甲即可，设定为 7。
   - "DeathSavePenalty": 初始必须为 0。
3. **技能 (skills)**: 提供一组符合该角色设定的强项技能字典（例如 "Handgun": 6, "Brawling": 4, "Stealth": 5, "Cybertech": 3等，通常最高+6）。
4. **义体与物品**: 分别填入 "cyberware"（如"神经连接基座"）和 "inventory" 列表中。
5. 请在 "role" 字段中指明角色的经典职业（如 Solo, Netrunner, Tech, Media, Fixer 等）。

仅返回一个纯 JSON 字符串（无需 Markdown 格式包裹），包含：name, class(这里填 role), background, attributes(字典), stats(字典), skills(字典), cyberware(列表), inventory(列表)。
"""

    def format_character_summary(self, character: Character) -> str:
        # Gracefully extract all default stats safely
        attr = character.data.get("attributes", {})
        stats = character.data.get("stats", {})
        name = character.data.get("name", "Unknown Edgerunner")
        role = character.data.get("class", "Street Scum")
        body = attr.get("BODY", 5)
        emp = attr.get("EMP", 5)
        hp = stats.get("HP", 0)
        max_hp = stats.get("MaxHP", 0)
        sp = stats.get("SP", 0)
        humanity = stats.get("Humanity", emp * 10)
        dsp = stats.get("DeathSavePenalty", 0)

        # Build formatting
        text = f"[bold cyan]身份:[/bold cyan] {name} ({role})\n"
        
        # Attributes grid
        text += "[bold yellow]==== 神经与肉体属性 (Attributes) ====[/bold yellow]\n"
        attr_display = [f"{k}:{v}" for k, v in attr.items()]
        for i in range(0, len(attr_display), 5):
            text += " | ".join(attr_display[i:i+5]) + "\n"
            
        # Vitals
        text += "\n[bold red]==== 生理监控仪 (Vitals Monitor) ====[/bold red]\n"
        text += f"[bold green]HP (生命):[/bold green] {hp} / {max_hp}  "
        if hp == 0:
            text += "[blink bold red][濒死危急 Mortally Wounded! DSP: +{dsp}][/blink bold red]\n"
        else:
            text += "\n"
            
        text += f"[bold magenta]SP (外甲抗穿透阻挡值):[/bold magenta] {sp}\n"
        text += f"[bold cyan]Humanity (剩余人性值/赛博精神病阈值):[/bold cyan] {humanity} (EMP: {emp})\n"
        
        # Skills
        text += "\n[bold magenta]==== 专精程式 (Skills) ====[/bold magenta]\n"
        skills = character.data.get("skills", {})
        skill_displays = [f"{k}(+{v})" for k, v in skills.items()]
        text += ", ".join(skill_displays) + "\n"

        # Gear
        text += "\n[bold cyan]==== 义体与握持物 (Cyberware & Gear) ====[/bold cyan]\n"
        cyberware = character.data.get("cyberware", [])
        inventory = character.data.get("inventory", [])
        if cyberware:
            text += f"[bold yellow]义体植入:[/bold yellow] {', '.join(cyberware)}\n"
        if inventory:
            text += f"[bold green]随身物品:[/bold green] {', '.join(inventory)}\n"

        return text

    def parse_and_execute_roll(self, message: str, character: Character, dice: DiceSystem, console: Console) -> Tuple[bool, str]:
        sys_feedback = ""
        handled = False
        
        # 1. Skill/Attr Roll: [ROLL: 1d10 skill:Handgun attr:REF]
        skill_match = re.search(r'\[ROLL:\s*1[dD]10(?:\s+skill:([a-zA-Z0-9_\u4e00-\u9fa5]+))?(?:\s+attr:([a-zA-Z0-9_\u4e00-\u9fa5]+))?\]', message, re.IGNORECASE)
        if skill_match:
            skill_name = skill_match.group(1)
            attr_name = skill_match.group(2)
            
            # Extract values
            attr_val = character.data.get("attributes", {}).get(attr_name, 0) if attr_name else 0
            skill_val = character.data.get("skills", {}).get(skill_name, 0) if skill_name else 0
            
            res_total, res_rolls, _ = dice.prompt_roll(DiceRequest("1d10", 1, 10), "Cyberpunk 核心检定")
            base_roll = res_total
            
            # Exploding 10 / Fumbling 1
            explosion_feedback = ""
            if base_roll == 10:
                exp_res_total, _, _ = dice.prompt_roll(DiceRequest("1d10", 1, 10), "Critical Success! (单次爆炸骰)")
                base_roll += exp_res_total
                explosion_feedback = f" [bold green]🌟 极限操作 (Critical Success)! 追加 {exp_res_total} 点！[/bold green]"
            elif base_roll == 1:
                fum_res_total, _, _ = dice.prompt_roll(DiceRequest("1d10", 1, 10), "Critical Failure! (单次大失败)")
                base_roll -= fum_res_total
                explosion_feedback = f" [bold red]💀 致命失误 (Critical Failure)! 倒扣 {fum_res_total} 点！[/bold red]"
                
            total = base_roll + attr_val + skill_val
            
            console.print(Panel(f"指令解析: {skill_match.group(0)}\n[bold cyan]1D10 判定:[/bold cyan] {res_total}{explosion_feedback}\n[bold cyan]属性加持({attr_name}):[/bold cyan] +{attr_val}\n[bold cyan]技能熟练度({skill_name}):[/bold cyan] +{skill_val}\n[bold yellow]最终结算值 = {total}[/bold yellow]", title="[bold red]🎲 Cyberpunk Interlock 引擎[/bold red]", border_style="red"))
            
            sys_feedback += f"系统回传：玩家掷出 1D10 最终判定总值为: {total}。请结合此数值和当前动作的 DV (Difficulty Value) 描述后续剧情。"
            if res_total == 1:
                sys_feedback += " 核心警告：玩家掷出了1 (大失败 Critical Failure)，请必定让其付出惨痛代价（枪支炸膛、赛博故障、行动致重伤）！"
            elif res_total == 10:
                sys_feedback += " 核心提示：玩家掷出了10 (大成功)，请生动描绘出他神乎其技、远超常理的巅峰反杀画面！"
            handled = True

        # 2. Damage Roll: [ROLL: 3d6 damage]
        dmg_match = re.search(r'\[ROLL:\s*(\d+)[dD]6\s+damage\]', message, re.IGNORECASE)
        if dmg_match:
            num_dice = int(dmg_match.group(1))
            res_total, res_rolls, _ = dice.prompt_roll(DiceRequest(f"{num_dice}d6", num_dice, 6), "武器伤害 (不可爆炸)")
            
            sixes_count = sum(1 for face in res_rolls if face == 6)
            crit_injury = False
            injury_dmg = 0
            feedback_str = ""
            if sixes_count >= 2:
                crit_injury = True
                injury_dmg = 5
                feedback_str = f"\n[blink bold red]🚨 爆伤警告：掷出 {sixes_count} 个 6，触发【双 6 重创 (Critical Injury)】！额外爆发出 {injury_dmg} 点无视护甲纯粹伤害！[/blink bold red]"
                
            console.print(Panel(f"伤害掷骰: {res_total} {feedback_str}", title="[red]💥 伤害判定输出[/red]", border_style="red"))
            sys_feedback += f"\n系统回推：武器投沙盒出基础伤害为 {res_total}。"
            if crit_injury:
                sys_feedback += f" **高危状况**：伤害骰含有双 6，触发重创 (Critical Injury)！额外附带 5 点完全不可阻挡的真实伤害，且必须强行对目标身体施加一个毁灭性的残疾状态记录！"
            handled = True

        # 3. Apply Damage & Ablative SP: [APPLY_DAMAGE: 15]
        app_dmg_match = re.search(r'\[APPLY_DAMAGE:\s*(\d+)\]', message, re.IGNORECASE)
        if app_dmg_match:
            dmg_val = int(app_dmg_match.group(1))
            stats = character.data.setdefault("stats", {})
            sp = stats.get("SP", 0)
            hp = stats.get("HP", 0)
            
            if dmg_val > sp:
                dmg_taken = dmg_val - sp
                new_hp = max(0, hp - dmg_taken)
                stats["HP"] = new_hp
                sp_loss_msg = ""
                # Ablative SP
                if sp > 0:
                    stats["SP"] -= 1
                    sp_loss_msg = f"\n护甲遭到贯穿，SP 防弹效能永久 -1 (当前剩余 {stats['SP']})。"
                
                character.save()
                console.print(Panel(f"[red]承受猛烈火力伤害 {dmg_val} 点。[/red]\n[cyan]外层装甲 (SP: {sp}) 吸收了 {sp} 点动能。[/cyan]\n[bold red]肉体实际受到贯通伤害 {dmg_taken} 点！ 剩余 HP: {new_hp}[/bold red]{sp_loss_msg}", title="[red]🩸 生命体征受损[/red]", border_style="red"))
                sys_feedback += f"\n护甲解算：命中受真伤 {dmg_taken} 点，剩余 HP={new_hp}。{sp_loss_msg}"
                if new_hp == 0:
                    sys_feedback += " 【紧急】HP归零！玩家进入濒死 (Mortally Wounded)，肉体剧烈休克，从现在起每回合必须做 DEATH_SAVE！"
            else:
                console.print(Panel(f"[green]承受火力伤害 {dmg_val} 点。[/green]\n你的重型防具 (SP: {sp}) 完美阻挡了这次冲击，你只感到一阵钝痛，未受有效伤害！", title="[green]🛡️ 护甲完美跳弹[/green]", border_style="green"))
                sys_feedback += "\n护甲解算：因未能击穿护甲厚度，攻击完全无效(0点伤)。"
            handled = True

        # 4. Death Save: [DEATH_SAVE]
        if "[DEATH_SAVE]" in message:
            stats = character.data.setdefault("stats", {})
            body = character.data.get("attributes", {}).get("BODY", 5)
            dsp = stats.get("DeathSavePenalty", 0)
            
            res_total, res_rolls, _ = dice.prompt_roll(DiceRequest("1d10", 1, 10), "对抗死神的豁免")
            total = res_total + dsp
            
            console.print(Panel(f"你的濒死体质: [bold red]BODY {body}[/bold red]\n[cyan]1D10 丢出 {res_total} 加上 死亡惩罚({dsp})[/cyan] = [bold white]{total}[/bold white]\n[dim]判点必须严密低于你的 BODY 才能扛住休克...[/dim]", title="[blink bold red]☠️ 濒死挽歌 (Death Save)[/blink bold red]"))
            
            if res_total == 10 or total >= body:
                console.print("[blink bold red]>>> 生命体征彻底从脉搏仪上消失。边缘行者(EDGERUNNER)，你已下线。(DEAD) <<<[/blink bold red]")
                sys_feedback += "\n引擎断言：死亡交叉豁免失败。人物当场心脏骤停死亡。请立刻转播这位狂傲的理想主义者是如何悲惨、无声地死在无情的赛博城头的。"
            else:
                stats["DeathSavePenalty"] += 1
                character.save()
                console.print(f"[bold green]活下来了！你咽下一口血。但死神更近了，下回合惩罚上升为 +{stats['DeathSavePenalty']}[/bold green]")
                sys_feedback += f"\n引擎断言：死亡豁免惊险通过。伤者尚存一息。下一次检定惩罚增加至 {stats['DeathSavePenalty']}。"
            handled = True

        # 5. Humanity Loss: [HUMANITY: -2d6] or [HUMANITY: -4]
        hum_match = re.search(r'\[HUMANITY:\s*(-?\d+[dD]\d+|-?\d+)\]', message, re.IGNORECASE)
        if hum_match:
            hum_exp = hum_match.group(1)
            loss_val = 0
            if 'd' in hum_exp.lower():
                num_dice = int(hum_exp.lower().replace('-', '').split('d')[0])
                hum_res_total, _, _ = dice.prompt_roll(DiceRequest(f"{num_dice}d6", num_dice, 6), "义体心理副作用削减")
                loss_val = hum_res_total
            else:
                loss_val = abs(int(hum_exp))
                
            stats = character.data.setdefault("stats", {})
            attr = character.data.setdefault("attributes", {})
            current_hum = stats.get("Humanity", 50)
            
            new_hum = max(0, current_hum - loss_val)
            stats["Humanity"] = new_hum
            
            # EMP 自动跟随跌落
            new_emp = new_hum // 10
            emp_drop_msg = ""
            if attr.get("EMP", 5) != new_emp:
                attr["EMP"] = new_emp
                emp_drop_msg = f" \n[blink bold red]⚠️ 情感认知受损！你的 EMP(共情面) 永久下坠到了 {new_emp} ⚠️[/blink bold red]"
                
            character.save()
            console.print(Panel(f"[magenta]血肉被钢铁取代的代价：你的理智与人性丧失了 {loss_val} 点。[/magenta]\n[bold cyan]剩余 Humanity: {new_hum}[/bold cyan]{emp_drop_msg}", title="[magenta]🧠 赛博精神病早期评估表[/magenta]"))
            sys_feedback += f"\n病历报告：因改造玩家失去了 {loss_val} 点人性值。当前剩余 Humanity={new_hum} (EMP跌落至={new_emp})。"
            if new_hum == 0:
                sys_feedback += " **绝望警钟**：玩家的 Humanity 直接归零！宣告完全丧失作为类人生物的情感底线。转变为最高危的赛博精神病(Cyberpsycho)。AI必须立即接管该角色控制权，要求玩家停控，并描述他疯狂屠戮平民或防暴部队的末世景象！"
            handled = True

        return handled, sys_feedback

    def process_combat(self, ai_response: str, character: Character, dice_system: DiceSystem, console: Console, ai_client) -> Tuple[bool, str]:
        # Cyberpunk Interlock uses standard narrative integration instead of the hex-grid D20 loop.
        return False, ""

    def manual_gen(self, console, dice_system, base_dict: dict) -> dict:
        from rich.prompt import Prompt
        from rich.panel import Panel
        from src.dice import DiceRequest
        import math

        console.print("[bold red]Cyberpunk Red 属性分配[/bold red]")

        rolled_scores = []
        for i in range(10):
            while True:
                req = DiceRequest("1d10", 1, 10)
                total, _, _ = dice_system.prompt_roll(req, reason=f"编译第 {i+1} 个核心潜能区块")
                if total >= 3:
                    rolled_scores.append(total)
                    break
                else:
                    console.print(f"[dim]掷出 {total} 过低，神经系统自动重构...[/dim]")
                    
        rolled_scores.sort(reverse=True)
        
        attr_names = ["INT", "REF", "DEX", "TECH", "COOL", "WILL", "LUCK", "MOVE", "BODY", "EMP"]
        attr_names_cn = ["智力(INT)", "反应(REF)", "敏捷(DEX)", "技术(TECH)", "镇定(COOL)", "意志(WILL)", "幸运(LUCK)", "移动(MOVE)", "肉体(BODY)", "共情(EMP)"]
        
        final_attrs = {}
        
        for i, name_cn in enumerate(attr_names_cn):
            console.print(f"\n[bold cyan]可用神经编码区块池: {rolled_scores}[/bold cyan]")
            
            while True:
                choice = Prompt.ask(f"请为 [bold magenta]{name_cn}[/bold magenta] 注入一段潜能区块", choices=[str(x) for x in set(rolled_scores)])
                val = int(choice)
                if val in rolled_scores:
                    final_attrs[attr_names[i]] = val
                    rolled_scores.remove(val)
                    console.print(f"[green]已将 {val} 注入 {name_cn}！[/green]")
                    break
                else:
                    console.print("[red]请选择可用区块池中剩余的数字。[/red]")
                    
        # Calculate derived stats
        body = final_attrs["BODY"]
        will = final_attrs["WILL"]
        emp = final_attrs["EMP"]
        
        # Cyberpunk Red HP formula: 10 + 5 * ceil((BODY + WILL) / 2)
        hp = 10 + 5 * math.ceil((body + will) / 2)
        humanity = emp * 10
        sp = 11 # Default Light Armor Jacket
        
        console.print(f"\n[bold magenta]基础体征档案生成完毕！[/bold magenta]")
        console.print(f"最大生命值(HP): [bold red]{hp}[/bold red]  |  初始人性(Humanity): [bold cyan]{humanity}[/bold cyan]  |  预置护甲(SP): [bold yellow]{sp}[/bold yellow]")
        
        base_dict["attributes"] = final_attrs
        base_dict["stats"] = {"HP": hp, "Humanity": humanity, "SP": sp, "DeathSavePenalty": 0}
        
        return base_dict
