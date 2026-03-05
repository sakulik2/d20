# D20 AI 文字冒险系统 (D20 AI Text Adventure)

这是一个结合了大语言模型（LLM）动态叙事与经典 D20（20面骰）跑团检定机制的单人命令行赛博跑团系统。在这个项目中，AI 充当完全中立且严厉的地下城主（DM），而你则是唯一的玩家。

## 🌟 核心特色

- **双核掷骰系统**：想体验跑团的真实感？输入 `/dice manual`，系统会在需要判定时挂起，等你拿着现实中的实体骰子丢出点数并输入。随时可以通过 `/dice virtual` 切换回系统自动生成的随机数。
- **全系 D&D 骰子兼容**：AI 完全理解不仅只有 1d20。当你使用匕首时它会要求你扔 `1d4` 算伤害，使用巨剑暴击时会要求 `2d6`，所有复杂的骰点系统均能通过正则表达式在后台被主程序精准捕捉。
- **无限动态世界引擎（AI 规则生成）**：你想玩中世纪奇幻？还是赛博朋克深潜？或者火星求生？游戏启动时，只需输入一句主题（如“漫威废土僵尸生存”），系统将立刻在后台通过 LLM 为你生成专属的设定书（System Prompt）和职业列表。
- **JSON 角色卡引擎**：告别单纯的聊天扮演。系统自带一套完整的 `character.json` 属性机制。无论是创建人物还是自动计算技能熟练度的调整值，一切都在系统底层以代码驱动。
- **极致终端美学**：借助 `rich` 渲染库，享受带有色彩高亮、Markdown 格式支持以及精致面板边框的终端阅读体验。

## 🚀 快速开始

### 1. 环境准备

确保你已经安装了 Python 3.9 或更高版本。
首先，在命令行中进入 `d20` 目录，然后安装必要的依赖包：

```bash
cd e:\code\d20
pip install -r requirements.txt
```

### 2. 配置 AI 大模型

打开项目目录下的 `config.yaml`。本项目兼容遵循 OpenAI 标准的各类 API（包括第三方或本地代理）。

默认配置使用**本地免代理的 Ollama**：
```yaml
ai:
  provider: "ollama"  # 默认使用本地的 Ollama 服务
  providers:
    ollama:
      api_key: "ollama"
      base_url: "http://localhost:11434/v1"
      model: "llama3" # 或修改为你本地的其他模型
```

如果你想使用云端大模型（以 **DeepSeek** 为例）：
1. 将 `provider:` 修改为 `"deepseek"`
2. 在底下的 `deepseek` 栏目填入你的 API Key：
```yaml
    deepseek:
      api_key: "sk-xxxxxx..." # 填入你的真实 KEY
      base_url: "https://api.deepseek.com/v1"
      model: "deepseek-chat"
```

### 3. 开始你的冒险

准备就绪后，直接运行主程序：

```bash
python src/main.py
```

## 🎮 游戏内快捷命令

在等待你输入动作的任何时候，除了描述你要做什么以外，你还可以输入以下系统指令：

- `/dice virtual`：将掷骰模式切换为“虚拟骰子”（系统自动生成随机数进行挑战检定）。
- `/dice manual`：将掷骰模式切换为“实体物理骰子”（系统会暂停，提示你应投掷什么骰子，你需要自己扔完实体色子后输入点数总和）。
- `/quit` 或 `/exit`：退出游戏。

## 📁 目录结构

- `src/main.py`: 核心游戏循环与界面调度。
- `src/ai_client.py`: 负责与大模型 API 通信，管理上下文记忆并包含角色/设定生成器。
- `src/dice.py`: 正则表达式解析引擎，负责抓取并处理各种掷骰请求并处理成功率逻辑。
- `src/character.py`: 负责加载与写入 JSON 格式的玩家角色卡，计算属性加成。
- `data/character.json`: 当前玩家的属性存档库。
- `data/rulesets/`: 存放系统运行时加载的具体世界观设定规则书（如 `fantasy.txt`, `scifi.txt` 等）。

---
**现在，拿起你的剑（或者充能等离子步枪），投掷出属于你的 20 点大成功吧！**
