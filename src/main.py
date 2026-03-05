import sys
from pathlib import Path
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

# Assuming running from e:/code/d20
sys.path.append(str(Path(__file__).parent.parent))

from src.ai_client import AIClient
from src.character import Character
from src.dice import DiceSystem, DiceRequest
from src.save_manager import SaveManager
from src.engine import CombatEngine

console = Console()

def load_ruleset(ruleset_name: str) -> str:
    ruleset_path = Path("data/rulesets") / ruleset_name
    if not ruleset_path.exists():
        console.print(f"[bold red]Ruleset not found: {ruleset_path}[/bold red]")
        sys.exit(1)
    with open(ruleset_path, 'r', encoding='utf-8') as f:
        return f.read()

def setup_game() -> tuple[AIClient, Character, DiceSystem, str, bool, SaveManager, CombatEngine]:
    console.print(Panel.fit("[bold magenta]🎲 欢迎来到 D20 AI 文字冒险系统 🎲[/bold magenta]", border_style="magenta"))
    
    ai = AIClient()
    dice_mode = ai.config.get("game", {}).get("dice_mode", "virtual")
    # Initialize character with default data, it might be overwritten by a save
    character = Character("data/character.json")
    dice = DiceSystem(console, mode=dice_mode, character=character)
    
    # Initialize combat engine
    combat_engine = CombatEngine(console)
    
    # 0. Check for existing saves
    save_manager = SaveManager()
    available_saves = save_manager.get_available_saves()
        
    is_loaded_save = False
    ruleset_prompt = ""
    
    if available_saves:
        action_choice = Prompt.ask(
            "你想 [bold green](N)新建冒险[/bold green] 还是 [bold yellow](L)载入存档[/bold yellow]？", 
            choices=["n", "l"], 
            default="n"
        )
        
        if action_choice == "l":
            console.print("\n[bold cyan]=========== 现有存档列表 ===========[/bold cyan]")
            for idx, sname in enumerate(available_saves):
                console.print(f"  [{idx+1}] {sname}")
            console.print("[bold cyan]====================================[/bold cyan]")
            
            choices_str = [str(i+1) for i in range(len(available_saves))]
            save_idx_str = Prompt.ask("请输入你想读取的[bold yellow]存档编号[/bold yellow]", choices=choices_str)
            try:
                save_idx = int(save_idx_str) - 1
                save_name = available_saves[save_idx]
                loaded_data = save_manager.load_game(save_name)
                if loaded_data:
                    ruleset_prompt, history, char_data = loaded_data
                    ai.history = history
                    if char_data:
                        character.update_from_dict(char_data)
                    console.print(f"[bold green]成功载入存档: {save_name}[/bold green]")
                    is_loaded_save = True
                else:
                    console.print("[bold red]读取存档失败，转为新建冒险。[/bold red]")
            except ValueError:
                console.print("[bold red]无效编号，转为新建冒险。[/bold red]")
                
    if not is_loaded_save:
        # 1. Ask about ruleset/theme
        default_ruleset = ai.config.get("game", {}).get("ruleset", "fantasy.txt")
        theme_choice = Prompt.ask(
            "请输入一个你想要的跑团世界观（例如：赛博朋克 / 修仙），或直接回车使用默认设定", 
            default=default_ruleset
        )
        
        if theme_choice == default_ruleset:
            console.print(f"[dim]正在加载设定集: {default_ruleset}...[/dim]")
            ruleset_prompt = load_ruleset(default_ruleset)
        else:
            console.print(f"[bold yellow]正在启动小规模世界坍缩以生成自定义规则设定：'{theme_choice}'...[/bold yellow]")
            ruleset_prompt = ai.generate_ruleset(theme_choice)
            console.print("[green]新世界设定已生成完毕！[/green]\n")
            
        # 2. Ask about Character
        char_choice = Prompt.ask(
            "你是想 [bold green](L)读取[/bold green] 已存角色卡 还是想让 AI 为你 [bold yellow](G)生成[/bold yellow] 一张新角色卡？", 
            choices=["l", "g"], 
            default="l"
        )
        
        if char_choice == "g":
            desc = Prompt.ask("用一两句话描述一下你想扮演的角色（例如：'一个脾气暴躁的矮人铁匠'）")
            console.print("[bold yellow]正在为你量身打造属性与技能...[/bold yellow]")
            new_char_data = ai.generate_character(desc, ruleset_prompt)
            if new_char_data:
                auto_roll_choice = Prompt.ask(
                    "关于角色的 6 项基础属性，你想直接使用 AI 分配的数值，还是使用你当前的掷骰模式来 [bold yellow]亲自投掷 (4d6 丢弃最低值)[/bold yellow]？\n[bold green](A)I自动分配[/bold green] / [bold yellow](R)亲自投掷[/bold yellow]", 
                    choices=["a", "r"], 
                    default="a"
                )
                
                if auto_roll_choice == "r":
                    console.print("\n[bold magenta]开始为 6 项基础属性掷骰 (4d6，保留最高的3个)...[/bold magenta]")
                    # Temporarily force manual mode for these rolls
                    original_mode = dice.mode
                    dice.mode = "manual"
                    
                    attr_names = {
                        "strength": "力量",
                        "dexterity": "敏捷", 
                        "constitution": "体质", 
                        "intelligence": "智力", 
                        "wisdom": "感知", 
                        "charisma": "魅力"
                    }
                    for attr_key, attr_name in attr_names.items():
                        req = DiceRequest(notation="4d6 (取最高3个)", count=4, faces=6, drop_lowest=1)
                        total, _, _ = dice.prompt_roll(req, reason=f"决定你的 {attr_name} 属性")
                        new_char_data["attributes"][attr_key] = total
                        
                    # Restore original mode
                    dice.mode = original_mode
                        
                character.update_from_dict(new_char_data)
                console.print("[green]新角色卡已就绪并存档！[/green]\n")
            else:
                console.print("[red]角色生成失败，回退至你身上仅存的数据。[/red]\n")

    console.print(Panel(character.format_summary(), title="[cyan]你的角色卡[/cyan]", border_style="cyan"))
    
    return ai, character, dice, ruleset_prompt, is_loaded_save, save_manager, combat_engine

def main():
    ai, character, dice, ruleset_prompt, is_loaded_save, save_manager, combat_engine = setup_game()
    
    console.print("\n[bold magenta]世界初始化完成，正在载入地下城主 (DM)...[/bold magenta]\n")
    
    if not is_loaded_save:
        ai.load_scenario(ruleset_prompt, character.format_summary())
        # Get the opening sequence
        with console.status("[dim]DM 正在构思场景...[/dim]"):
            opening = ai.generate_response()
            
        console.print(Panel(Markdown(opening), title="[bold red]🎲 Game Master 🎲[/bold red]", border_style="red"))
    else:
        # Re-print the last AI message to orient the player
        if ai.history:
            last_msg = ""
            for msg in reversed(ai.history):
                if msg["role"] == "assistant":
                    last_msg = msg["content"]
                    break
            if last_msg:
                console.print(Panel(Markdown(last_msg), title="[bold red]🎲 Game Master (读档恢复) 🎲[/bold red]", border_style="red"))
        else:
            console.print("[dim]存档中没有历史对话记录。[/dim]")
    
    # Main Game Loop
    while True:
        try:
            last_message = ai.history[-1]["content"] if ai.history else ""
            
            # 0. Check if AI just triggered a Combat state
            # We must only trigger this if we aren't ALREADY in combat, to avoid infinite loops
            if not combat_engine.in_combat:
                enemies_data = combat_engine.parse_combat_start(last_message)
                if enemies_data:
                    combat_engine.start_combat(enemies_data)
                    player_hp = character.data.get("hp", {}).get("current", 10)
                    combat_engine.add_player(character.name, character.armor_class, player_hp)
                    combat_engine.roll_initiative(dice)
                    
                    # Force the loop to continue and immediately drop into the Combat branch
                    continue

            # 1. Combat State Machine Branch
            if combat_engine.in_combat:
                cur_entity = combat_engine.get_current_turn_entity()
                
                if cur_entity.is_player:
                    action_result = combat_engine.execute_player_turn(dice, character)
                else:
                    player_entity = next(e for e in combat_engine.entities if e.is_player)
                    action_result = combat_engine.execute_enemy_turn(dice, cur_entity, player_entity)
                    
                # Evaluate results (e.g. check for deaths)
                dead_enemies = combat_engine.remove_dead_enemies()
                if dead_enemies:
                    console.print(f"[dim]已清理被击败的单位：{', '.join(dead_enemies)}[/dim]")
                
                # Check if combat has ended
                if combat_engine.check_combat_end():
                    action_result += " 战斗已经结束，请总结这场战斗，然后引导玩家进入下一步探索。"
                    
                # Send the raw mechanical outcome to AI to narrate
                ai.add_user_message(action_result)
                with console.status("[dim]DM 正在生动描绘这一回合的战斗激况...[/dim]"):
                    response = ai.generate_response()
                console.print(Panel(Markdown(response), title="[bold red]🎲 Game Master 🎲[/bold red]", border_style="red"))
                
                if combat_engine.in_combat:
                    combat_engine.advance_turn()
                continue
                
            # 2. Exploration / Normal Interactions Branch
            roll_requests = dice.parse_all_roll_requests(last_message)
            
            if roll_requests:
                feedback_msgs = []
                for idx, roll_request in enumerate(roll_requests):
                    if idx > 0:
                        console.print("\n[dim]-- 下一个连续检定 --[/dim]")
                    # Execute roll
                    total, rolls, status = dice.prompt_roll(roll_request)
                    feedback_msgs.append(f"Player rolled {roll_request.notation}. Total result: {total} ({status})")
                
                feedback_msg = f"[System: {'; '.join(feedback_msgs)}]"
                
                # Send result directly back without waiting for user action
                console.print(f"\n[dim italic]>>> 正在将所有掷骰结果组合提交到 DM...[/dim italic]")
                ai.add_user_message(feedback_msg)
                with console.status("[dim]DM 根据你的掷骰检视结果...[/dim]"):
                    反应 = ai.generate_response()
                console.print(Panel(Markdown(反应), title="[bold red]🎲 Game Master 🎲[/bold red]", border_style="red"))
                continue # Skip asking for user input, let DM narrate the result first
                
            # 2. Get User Input
            console.print()
            user_action = input("你的行动是？ (或输入指令 /dice virtual|manual, /save <名字>, /quit) >> ").strip()
            
            if not user_action:
                continue
                
            if user_action.lower() in ('/quit', '/exit', 'quit', 'exit'):
                console.print("[bold]感谢游玩，冒险者。下次江湖再见！[/bold]")
                break
                
            if user_action.startswith('/save '):
                save_name = user_action.split(' ', 1)[1].strip()
                if save_name:
                    success = save_manager.save_game(save_name, ruleset_prompt, ai.history, character.data)
                    if success:
                        console.print(f"[bold green]》系统提示：当前进度与角色卡已保存至存档模块 '{save_name}'。[/bold green]")
                    else:
                        console.print(f"[bold red]保存失败，请检查写入权限。[/bold red]")
                continue
                
            if user_action.startswith('/dice '):
                mode = user_action.split(' ')[1].strip()
                dice.set_mode(mode)
                continue
                
            # 3. Send action to DM
            ai.add_user_message(user_action)
            with console.status("[dim]DM 正在推进因果之轮...[/dim]"):
                response = ai.generate_response()
                
            console.print(Panel(Markdown(response), title="[bold red]🎲 Game Master 🎲[/bold red]", border_style="red"))
            
        except KeyboardInterrupt:
            console.print("\n[bold]跑团已挂起。下次再见！[/bold]")
            break
        except Exception as e:
            console.print(f"[bold red]An error occurred: {e}[/bold red]")
            break

if __name__ == "__main__":
    main()
