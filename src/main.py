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
from src.systems.d20 import D20System
from src.systems.coc import CoCSystem
from src.systems.mystery import MysterySystem
from src.systems.narrative import NarrativeSystem
from src.systems.cyberpunk import CyberpunkSystem
from src.systems.fitd import ForgedInTheDarkSystem
from rich.prompt import Prompt

console = Console()

def load_ruleset(ruleset_name: str) -> str:
    ruleset_path = Path("data/rulesets") / ruleset_name
    if not ruleset_path.exists():
        console.print(f"[bold red]Ruleset not found: {ruleset_path}[/bold red]")
        sys.exit(1)
    with open(ruleset_path, 'r', encoding='utf-8') as f:
        return f.read()

def setup_game() -> tuple[AIClient, Character, DiceSystem, str, bool, SaveManager, object, str]:
    console.print(Panel.fit("[bold magenta]🎲 欢迎来到 AI 多规则跑团模拟器 🎲[/bold magenta]", border_style="magenta"))
    
    ai = AIClient()
    save_manager = SaveManager()
    
    console.print("\n[bold]请选择你的核心游玩规则引擎：[/bold]")
    console.print("1. [red]经典 D20 战斗系统 (默认)[/red] - 回合制判定与 AC 护甲体系")
    console.print("2. [green]克苏鲁 D100 系统 (CoC)[/green] - 百分点检定与理智 (SAN) 崩坏判定")
    console.print("3. [blue]纯文字解谜 (Mystery)[/blue] - 无战斗，专注推演提取线索查案")
    console.print("4. [yellow]命运叙事系统 (Narrative)[/yellow] - 无数值轻量建卡，基于 PbtA 动态剧情三元转折")
    console.print("5. [purple]赛博朋克深黑未来 (Cyberpunk)[/purple] - 硬核 1D10 检定，SP 护甲消融与赛博精神病机制")
    console.print("6. [white]暗夜本源 (Forged in the Dark)[/white] - FitD 引擎，抛掷多面骰池，利用压力系统解决危机。")
    
    sys_choice = Prompt.ask("请输入选项 (1/2/3/4/5/6)", choices=["1", "2", "3", "4", "5", "6"], default="1")
    
    if sys_choice == "1":
        game_system = D20System(console)
    elif sys_choice == "2":
        game_system = CoCSystem(console)
    elif sys_choice == "3":
        game_system = MysterySystem(console)
    elif sys_choice == "4":
        game_system = NarrativeSystem(console)
    elif sys_choice == "5":
        game_system = CyberpunkSystem(console)
    else:
        game_system = ForgedInTheDarkSystem(console)
        
    ai.config.setdefault("game", {})["system_id"] = game_system.system_id
    
    dice_mode = ai.config.get("game", {}).get("dice_mode", "virtual")
    # Initialize character with default data per system, it might be overwritten by a save
    char_file_path = f"data/{game_system.system_id}/character.json"
    
    # Ensure dir exists safely
    Path(f"data/{game_system.system_id}").mkdir(parents=True, exist_ok=True)
    character = Character(char_file_path)
    dice = DiceSystem(console, mode=dice_mode, character=character)
    
    # 0. Check for existing saves
    save_manager = SaveManager()
    available_saves = save_manager.get_available_saves(system_id=game_system.system_id)
        
    is_loaded_save = False
    ruleset_prompt = ""
    combat_style = ai.config.get("game", {}).get("combat_style", "engine")
    
    if available_saves:
        action_choice = Prompt.ask(
            "你想 [bold green](N)新建冒险[/bold green] 还是 [bold yellow](L)载入存档[/bold yellow]？", 
            choices=["n", "l", "N", "L"],
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
                loaded_data = save_manager.load_game(save_name, system_id=game_system.system_id)
                if loaded_data:
                    ruleset_prompt, history, char_data, combat_style_from_save, loaded_sys_id = loaded_data
                    combat_style = combat_style_from_save
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
        action_choice = Prompt.ask(
            "\n你是想 [bold green](G)让 AI 生成[/bold green] 新的世界观，还是 [bold yellow](L)载入本地设定文件[/bold yellow]？", 
            choices=["g", "l", "G", "L"],
            default="g"
        )
        
        ruleset_loaded_from_file = False
        if action_choice == 'l':
            ruleset_dir = Path("data/rulesets")
            if ruleset_dir.exists() and any(ruleset_dir.iterdir()):
                rulesets = sorted([f.name for f in ruleset_dir.iterdir() if f.is_file()])
                if rulesets:
                    console.print("\n[bold cyan]=========== 本地设定文件 ===========[/bold cyan]")
                    for idx, rs in enumerate(rulesets):
                        console.print(f"  [{idx+1}] {rs}")
                    console.print("[bold cyan]====================================[/bold cyan]")
                    
                    choices_str = [str(i+1) for i in range(len(rulesets))]
                    choices_str.append("c")
                    rs_idx_str = Prompt.ask("请选择设定文件编号 (输入 'c' 取消)", choices=choices_str)
                    if rs_idx_str != 'c':
                        selected_rs = rulesets[int(rs_idx_str) - 1]
                        ruleset_prompt = load_ruleset(selected_rs)
                        console.print(f"[green]成功载入设定： {selected_rs}[/green]\n")
                        ruleset_loaded_from_file = True
            
            if not ruleset_loaded_from_file:
                console.print("[red]没有找到（或取消选择）本地世界观设定文件，转为生成模式。[/red]")
                
        if not ruleset_loaded_from_file:
            # Create new universe
            setting_prompt = Prompt.ask("\n[bold yellow]你想在什么世界观下跑团？ (比如：赛博朋克、中世纪丧尸、克苏鲁神话，直接回车使用默认奇幻设定)[/bold yellow]")
            if not setting_prompt:
                setting_prompt = "经典龙与地下城中世纪奇幻"
                
            with console.status("[dim]AI 正在为你构筑全新世界观规则，这可能需要一点时间...[/dim]"):
                # Pass the selected system prompts into the ruleset generation
                system_instructions = game_system.get_system_prompts()
                ruleset_prompt = ai.generate_ruleset(setting_prompt, system_instructions)
                
            console.print("[green]世界观规则生成完毕！[/green]\n")
        
        # Determine combat style (for D20 especially)
        combat_style = "engine"
        if game_system.system_id == "d20":
            console.print("[bold cyan]选择战斗模式 (Combat Style):[/bold cyan]")
            console.print("1. [bold red]硬核回合制[/bold red] - 由程序接管严谨的战斗算力：自动算血量、比对护甲(AC)判定命中，角色阵亡将直接结束旅程。")
            console.print("2. [bold blue]剧情向叙事[/bold blue] - 战斗像平常一样融入对话，偏重演出效果，不强制跳出菜单进行计算。")
            c_choice = Prompt.ask("你的选择 (1/2)", choices=["1", "2"], default="1")
            combat_style = "engine" if c_choice == "1" else "narrative"
            
        ai.config.setdefault("game", {})["combat_style"] = combat_style
            
        # 2. Ask about Character
        char_choice = Prompt.ask(
            "关于角色卡，你想：\n[bold green](L)读取本地存档[/bold green]\n[bold yellow](A)AI 自动生成[/bold yellow]\n[bold magenta](M)手动投骰[/bold magenta]",
            choices=["l", "a", "m", "L", "A", "M"],
            default="l"
        ).lower()
        
        if char_choice in ["a", "m"]:
            desc = Prompt.ask("用一两句话描述一下你想扮演的角色（例如：'一个脾气暴躁的矮人铁匠'）")

            if char_choice == "a":
                console.print("[bold yellow]正在由 AI 生成属性与技能...[/bold yellow]")
                new_char_data = ai.generate_character(desc, ruleset_prompt)
                if new_char_data:
                    character.update_from_dict(new_char_data)
                    console.print("[green]新角色卡已就绪并存档！[/green]\n")
            else:
                console.print("[bold yellow]正在请求 AI 提取身份框架...[/bold yellow]")
                with console.status("[dim]AI 提取角色外壳...[/dim]"):
                    shell_data = ai.generate_shell(desc)
                
                dice_roll_mode = Prompt.ask(
                    "掷骰方式：\n[bold green](A)自动模拟[/bold green] - 程序自动投骰\n[bold yellow](M)手动输入[/bold yellow] - 现实骰点自己录入",
                    choices=["a", "m", "A", "M"],
                    default="a"
                )
                dice.set_mode("manual" if dice_roll_mode == "m" else "virtual")
                try:
                    completed_data = game_system.manual_gen(console, dice, shell_data)
                    if completed_data:
                        with console.status("[dim]AI 正在补全背景、技能与特性...[/dim]"):
                            completed_data = ai.enrich_character(completed_data, desc, ruleset_prompt)
                        character.update_from_dict(completed_data)
                        console.print("\n[bold green]建卡完成！[/bold green]\n")
                    else:
                        console.print("[red]手动建卡被取消或遇到错误，退出程序。[/red]")
                        return
                except NotImplementedError:
                    console.print(f"[red]抱歉，{game_system.system_name} 暂未实装本地手动捏卡面板！[/red]")
                    return
        else:
            console.print("[green]成功读取本地角色卡。[/green]\n")

    console.print(Panel(game_system.format_character_summary(character), title="[cyan]你的角色卡[/cyan]", border_style="cyan"))
    
    return ai, character, dice, ruleset_prompt, is_loaded_save, save_manager, game_system, combat_style

def main():
    ai, character, dice, ruleset_prompt, is_loaded_save, save_manager, game_system, combat_style = setup_game()
    
    # Store combat style in ai config so everyone else can see it
    ai.config.setdefault("game", {})["combat_style"] = combat_style
    
    console.print("\n[bold magenta]世界初始化完成，正在载入地下城主 (DM)...[/bold magenta]\n")
    
    if not is_loaded_save:
        ai.load_scenario(ruleset_prompt, game_system.format_character_summary(character))
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
            
            # 1. System handles Combat/Events
            is_combat_active, combat_results = game_system.process_combat(last_message, character, dice, console, ai)
            
            if is_combat_active:
                if combat_results:
                    ai.add_user_message(combat_results)
                    with console.status("[dim]DM 正在生动描绘你刚刚的战斗画面...[/dim]"):
                        response = ai.generate_response()
                    console.print(Panel(Markdown(response), title="[bold red]🎲 Game Master 🎲[/bold red]", border_style="red"))
                continue
                
            # 2. System handles UI Roll parsing
            rolls_handled, roll_feedback = game_system.parse_and_execute_roll(last_message, character, dice, console)
            if rolls_handled:
                ai.add_user_message(roll_feedback)
                with console.status("[dim]DM 根据你的掷骰检视结果...[/dim]"):
                    response = ai.generate_response()
                console.print(Panel(Markdown(response), title="[bold red]🎲 Game Master 🎲[/bold red]", border_style="red"))
                continue
                
            # 3. Get User Input
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
                    success = save_manager.save_game(save_name, ruleset_prompt, ai.history, character.data, combat_style, system_id=game_system.system_id)
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
