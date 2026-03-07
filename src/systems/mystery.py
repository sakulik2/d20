from typing import Tuple
from src.systems.base import BaseGameSystem
from src.dice import DiceRequest
import re
import random


class MysterySystem(BaseGameSystem):
    def __init__(self, console):
        self.console = console

    @property
    def system_id(self) -> str:
        return "mystery"

    @property
    def system_name(self) -> str:
        return "纯文字探案解谜 (线索薄 / 嫌疑人档案)"

    def get_system_prompts(self) -> str:
        return """
【核心规则：推理探案系统】

调查员拥有 4 个属性（值域 1–10），检定时投 1d10 与属性值比对：
  - 投出值 <= 属性值的 1/2  → 【完全成功】
  - 投出值 <= 属性值        → 【部分成功】
  - 投出值 > 属性值         → 【失败】
  - Nat 1                   → 【神来之笔】（超出预期的发现）
  - Nat 10                  → 【完全失手】（严重后果）

你可以使用以下本地引擎指令，每条必须独占一行：

1. 属性检定（调查员用）：
   `[CLUE_ROLL: skill:观察 attr:观察]`   ← attr 填属性名，引擎自动取值
   `[CLUE_ROLL: skill:询问嫌疑人 attr:共情]`

2. 收录线索：
   `[CLUE_FOUND: 沾血的怀表]`

3. 新增嫌疑人：
   `[SUSPECT_FOUND: 管家威廉 | 动机:遗产纠纷]`

4. 提升嫌疑度（每次发现不利证据时调用）：
   `[SUSPICION_RAISE: 管家威廉]`

5. 指控某人（当玩家明确表示指控或确认凶手时）：
   `[ACCUSATION: 管家威廉]`

6. 推理推演（玩家组合两条或多条线索推理时）：
   `[DEDUCE: 沾血的怀表 + 被撕碎的信件]`
   你随后根据当前的线索薄状态给出推理洞见反馈。

重要：不得有传统战斗。所有冲突通过威慑检定或属性检定解决。
"""

    def build_character_generator_prompt(self, theme: str) -> str:
        return f"""
        You are a Master Detective guiding a player in a pure investigation text adventure set in {theme}.
        Generate a character sheet JSON with these keys:
        "name", "class" (e.g. Detective, Forensic Expert, Journalist),
        "background" (one sentence),
        "attributes" (observation, logic, empathy, intimidation — all integers 1-10),
        "clues" (empty array []),
        "suspects" (empty array []),
        "inventory" (list of basic items like 放大镜, 笔记本, 手电筒).
        Output ONLY valid JSON. No hp or ac needed.
        """

    def _get_attr_value(self, character, attr_name: str) -> int:
        """Look up an attribute by name (fuzzy match Chinese or English)."""
        ATTR_MAP = {
            "观察": "observation", "observation": "observation",
            "逻辑": "logic", "logic": "logic",
            "共情": "empathy", "empathy": "empathy",
            "威慑": "intimidation", "intimidation": "intimidation",
        }
        key = ATTR_MAP.get(attr_name.strip().lower(), attr_name.strip().lower())
        attrs = character.data.get("attributes", {})
        return attrs.get(key, attrs.get(attr_name, 5))

    def parse_and_execute_roll(self, ai_response: str, character, dice_system, console) -> Tuple[bool, str]:
        feedback_msgs = []
        handled = False

        # ── 1. CLUE_ROLL: real attribute-based 1d10 check ─────────────────────
        for m in re.finditer(r"\[CLUE_ROLL:\s*([^\]]+)\]", ai_response, re.IGNORECASE):
            handled = True
            tag_content = m.group(1)
            skill_m = re.search(r"skill:([^\s|,\]]+)", tag_content, re.IGNORECASE)
            attr_m  = re.search(r"attr:([^\s|,\]]+)", tag_content, re.IGNORECASE)
            skill_name = skill_m.group(1) if skill_m else "行动"
            attr_name  = attr_m.group(1) if attr_m else "观察"
            attr_val   = self._get_attr_value(character, attr_name)

            req = DiceRequest("1d10", 1, 10, skill=skill_name)
            total, _, _ = dice_system.prompt_roll(req)

            if total == 1:
                status = "【神来之笔】"
                msg_tag = "调查员出乎意料地发现了一个关键细节！请描述一个超出预期的发现。"
            elif total == 10:
                status = "【完全失手】"
                msg_tag = "调查员极其失误，请描述严重的负面后果，例如打草惊蛇或破坏了证据。"
            elif total <= attr_val // 2:
                status = "【完全成功】"
                msg_tag = "调查员非常顺利地完成了这个行动。"
            elif total <= attr_val:
                status = "【部分成功】"
                msg_tag = "调查员部分达成了目标，但有一点小麻烦或代价。"
            else:
                status = "【失败】"
                msg_tag = "调查员这次行动失败了。"

            console.print(f"[bold cyan]{skill_name} 检定 (属性:{attr_name} {attr_val}/10)  投出: {total}  → {status}[/bold cyan]")
            msg = f"玩家进行了【{skill_name}】检定（属性:{attr_name}={attr_val}），投出 {total}，结果：{status}。{msg_tag}"
            feedback_msgs.append(msg)

        # ── 2. CLUE_FOUND ─────────────────────────────────────────────────────
        for m in re.finditer(r"\[CLUE_FOUND:\s*(.*?)\]", ai_response, re.IGNORECASE):
            handled = True
            clue = m.group(1).strip()
            clues = character.data.setdefault("clues", [])
            if clue not in clues:
                clues.append(clue)
                console.print(f"\n[bold yellow]🔍 线索入档：【{clue}】[/bold yellow]")
                feedback_msgs.append(f"线索【{clue}】已记录到案卷。")

        # ── 3. SUSPECT_FOUND ─────────────────────────────────────────────────
        for m in re.finditer(r"\[SUSPECT_FOUND:\s*([^|^\]]+)(?:\|([^\]]*))?\]", ai_response, re.IGNORECASE):
            handled = True
            name = m.group(1).strip()
            extra = m.group(2).strip() if m.group(2) else ""
            suspects = character.data.setdefault("suspects", [])
            existing = next((s for s in suspects if s["name"] == name), None)
            if not existing:
                suspects.append({"name": name, "info": extra, "suspicion": 0})
                console.print(f"\n[bold red]👤 新增嫌疑人：{name}  {extra}[/bold red]")
                feedback_msgs.append(f"嫌疑人【{name}】已加入档案。{extra}")

        # ── 4. SUSPICION_RAISE ───────────────────────────────────────────────
        for m in re.finditer(r"\[SUSPICION_RAISE:\s*(.*?)\]", ai_response, re.IGNORECASE):
            handled = True
            name = m.group(1).strip()
            suspects = character.data.setdefault("suspects", [])
            target = next((s for s in suspects if name in s["name"]), None)
            if target:
                target["suspicion"] = target.get("suspicion", 0) + 1
                lvl = target["suspicion"]
                bar = "▓" * lvl + "░" * max(0, 5 - lvl)
                console.print(f"[bold red]⚠ {name} 嫌疑度上升！[{bar}] {lvl}/5[/bold red]")
                feedback_msgs.append(f"嫌疑人【{name}】嫌疑度提升至 {lvl} 点。")
            else:
                feedback_msgs.append(f"未能在档案中找到嫌疑人【{name}】，请先使用 SUSPECT_FOUND 添加。")

        # ── 5. ACCUSATION ────────────────────────────────────────────────────
        for m in re.finditer(r"\[ACCUSATION:\s*(.*?)\]", ai_response, re.IGNORECASE):
            handled = True
            name = m.group(1).strip()
            suspects = character.data.get("suspects", [])
            target = next((s for s in suspects if name in s["name"]), None)
            clue_count = len(character.data.get("clues", []))
            suspicion = target.get("suspicion", 0) if target else 0
            console.print(f"\n[bold white on red]  ⚖ 调查员正式指控：{name}！  [/bold white on red]")
            console.print(f"[dim]当前线索数: {clue_count}  {name} 嫌疑度: {suspicion}/5[/dim]")
            feedback_msgs.append(
                f"调查员正式指控【{name}】为凶手！当前已收集 {clue_count} 条线索，{name} 嫌疑度为 {suspicion}/5。"
                f"请作为主持人判断此指控是否正确，并以戏剧性的方式揭露真相或揭示指控有误的后果。"
            )

        # ── 6. DEDUCE ────────────────────────────────────────────────────────
        for m in re.finditer(r"\[DEDUCE:\s*(.*?)\]", ai_response, re.IGNORECASE):
            handled = True
            combo = m.group(1).strip()
            clues = character.data.get("clues", [])
            console.print(f"\n[bold magenta]🧠 推理推演：{combo}[/bold magenta]")
            feedback_msgs.append(
                f"调查员尝试推演线索组合：【{combo}】。当前卷宗记录：{', '.join(clues) if clues else '无'}。"
                f"请根据以上线索给出一段合理的推理洞见，引导调查员朝正确（或错误）方向推进。"
            )

        # ── Legacy 1d2 fallback ───────────────────────────────────────────────
        if not handled:
            roll_requests = dice_system.parse_all_roll_requests(ai_response)
            if roll_requests:
                for request in roll_requests:
                    total, _, _ = dice_system.prompt_roll(request)
                    res = "成功" if total >= 2 else "失败"
                    msg = f"玩家进行了 {request.skill or '行动'} 测试，结果：{res}（{total}）。"
                    console.print(f"[bold cyan]{msg}[/bold cyan]")
                    feedback_msgs.append(msg)
                    handled = True

        if handled and feedback_msgs:
            return True, " | ".join(feedback_msgs)
        return False, ""

    def process_combat(self, ai_response: str, character, dice_system, console, ai_client) -> Tuple[bool, str]:
        return False, ""

    def format_character_summary(self, character) -> str:
        d = character.data
        summary = f"调查员: {character.name}  |  身份: {character.char_class}\n"

        # Attributes
        attrs = d.get("attributes", {})
        if attrs:
            summary += "\n==== 调查员属性 (1-10) ====\n"
            label = {"observation": "观察", "logic": "逻辑", "empathy": "共情", "intimidation": "威慑"}
            for k, v in attrs.items():
                cn = label.get(k, k)
                bar = "█" * v + "░" * (10 - v)
                summary += f"  {cn:>3}: [{bar}] {v}\n"

        # Clue archive
        clues = d.get("clues", [])
        summary += f"\n==== 线索卷宗 ({len(clues)} 条) ====\n"
        if clues:
            for i, c in enumerate(clues, 1):
                summary += f"  [{i}] {c}\n"
        else:
            summary += "  (尚未收集到任何线索)\n"

        # Suspects
        suspects = d.get("suspects", [])
        if suspects:
            summary += f"\n==== 嫌疑人档案 ({len(suspects)} 人) ====\n"
            for s in suspects:
                lvl = s.get("suspicion", 0)
                bar = "▓" * lvl + "░" * max(0, 5 - lvl)
                summary += f"  👤 {s['name']}  [{bar}] {lvl}/5\n"
                if s.get("info"):
                    summary += f"     └ {s['info']}\n"

        # Inventory
        inv = d.get("inventory", [])
        if inv:
            summary += "\n==== 随身物品 ====\n"
            items = inv if isinstance(inv, list) else list(inv)
            summary += f"  {', '.join(items)}\n"

        return summary

    def manual_gen(self, console, dice_system, base_dict: dict) -> dict:
        from rich.prompt import Prompt

        console.print("[bold white]调查员属性分配[/bold white]  共 [bold yellow]28[/bold yellow] 点分配到 4 个属性（每项 1–10）。")

        attr_labels = [
            ("observation", "观察 — 发现现场细节、识别伪装"),
            ("logic",       "逻辑 — 推断因果、破解密码"),
            ("empathy",     "共情 — 套取证词、感知谎言"),
            ("intimidation","威慑 — 逼问嫌疑人、压制威胁"),
        ]
        attrs = {}
        remaining = 28

        for key, desc in attr_labels:
            while True:
                console.print(f"[dim]剩余点数: {remaining}[/dim]  {desc}")
                val_str = Prompt.ask(f"  分配给 [{key}]", default="5")
                try:
                    val = int(val_str)
                    if val < 1 or val > 10:
                        console.print("[red]必须在 1–10 之间[/red]")
                    elif val > remaining:
                        console.print(f"[red]点数不足（剩余 {remaining}）[/red]")
                    else:
                        attrs[key] = val
                        remaining -= val
                        break
                except ValueError:
                    console.print("[red]请输入数字[/red]")

        if remaining > 0:
            console.print(f"[dim]剩余 {remaining} 点自动加到逻辑[/dim]")
            attrs["logic"] = attrs.get("logic", 5) + remaining

        base_dict["attributes"] = attrs
        base_dict["clues"]     = []
        base_dict["suspects"]  = []
        return base_dict
