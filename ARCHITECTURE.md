# nanobot 架构分析

> 📅 更新时间：2026-02-06
> 作者：代码分析

---

## 🏗️ 总体架构

nanobot 是一个**轻量级 AI 代理框架**（~4,000 行代码），采用**事件驱动、模块化**设计。

```
┌─────────────────────────────────────────────────────────────────────┐
│                      CLI 命令行                          │
│                   (nanobot/cli/commands.py)             │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        │   Gateway 网关          │
        │ (channels + agent)    │
        └──────────────┬──────────────┘
                       │
         ┌─────────────┼─────────────┐
         │             │             │
    ┌────┴────┐  ┌────┴────┐  ┌────┴─────┐
    │ Channels │  │  Agent   │  │  MessageBus │
    │ 聊天渠道│  │  核心引擎│  │  消息总线 │
    └─────────┘  └───────────┘  └────────────┘
                              │
        ┌───────────────────┴───────────────────┐
        │                                      │
   ┌────┴─────┐   ┌───────────┴───────────┐
   │  Tools    │   │   Cron/Heartbeat      │
   │  工具系统  │   │   定时/心跳           │
   └───────────┘   └───────────────────────┘
```

---

## 📂 目录结构

```
nanobot/
├── cli/              # CLI 命令行接口
│   └── commands.py  # Typer 命令定义 (agent, gateway, status)
├── config/           # 配置管理
│   ├── loader.py   # 配置加载/保存 (JSON + Pydantic)
│   └── schema.py    # 配置数据模型 (Pydantic BaseModel)
├── providers/         # LLM Provider 层
│   ├── base.py            # LLM 提供商抽象基类
│   └── litellm_provider.py # LiteLLM 实现 (支持 OpenRouter/Anthropic/MiniMax 等)
├── agent/            # 核心代理引擎
│   ├── loop.py       # Agent 主循环 (消息处理)
│   ├── context.py     # 上下文构建 (引导文件、记忆、技能)
│   ├── skills.py      # 技能加载器
│   ├── memory.py      # 记忆存储 (MEMORY.md)
│   ├── subagent.py   # 子代理管理
│   └── tools/        # 工具系统
│       ├── base.py        # 工具抽象基类
│       ├── registry.py    # 工具注册表
│       ├── filesystem.py  # 文件操作 (read_file, write_file, edit_file)
│       ├── shell.py       # 命令执行
│       ├── web.py         # 网页搜索/获取 (Brave Search)
│       ├── message.py     # 消息发送
│       ├── spawn.py      # 子代理调用
│       └── cron.py        # 定时任务工具
├── channels/          # 聊天渠道层
│   ├── base.py      # 渠道抽象基类
│   ├── manager.py    # 渠道管理器 (初始化、启动、停止)
│   ├── telegram.py   # Telegram 渠道
│   ├── whatsapp.py   # WhatsApp 渠道
│   └── feishu.py     # 飞书渠道 (WebSocket 长连接)
├── bus/              # 消息总线
│   ├── queue.py      # 异步消息队列 (inbound/outbound)
│   └── events.py     # 消息事件定义 (InboundMessage, OutboundMessage)
├── session/           # 会话管理
│   └── manager.py    # Session 管理 (JSONL 持久化)
├── cron/             # 定时任务
│   ├── service.py    # Cron 服务 (任务调度)
│   └── types.py      # 任务类型定义
├── heartbeat/         # 心跳服务
│   └── service.py    # 定时健康检查 (30min 间隔)
├── skills/           # 内置技能
│   └── (各技能的 SKILL.md)
└── utils/            # 工具函数
```

---

## 🔑 核心组件详解

### 1️⃣ CLI 入口 (`nanobot/cli/commands.py`)

**职责**：命令行接口和网关启动

**主要命令**：

| 命令 | 功能 | 说明 |
|-------|------|------|
| `nanobot onboard` | 初始化配置和工作区 |
| `nanobot gateway` | 启动网关 (channels + agent) |
| `nanobot agent -m` | 直接对话 (单条消息) |
| `nanobot status` | 显示状态 (API key, 模型) |
| `nanobot channels login` | WhatsApp 扫码登录 |
| `nanobot cron` | 定时任务管理 |

**启动流程 (gateway 模式)**：

```python
# 1. 加载配置
config = load_config()

# 2. 创建消息总线
bus = MessageBus()

# 3. 创建 LLM Provider
provider = LiteLLMProvider(
    api_key=config.get_api_key(),
    api_base=config.get_api_base(),
    default_model=config.agents.defaults.model
)

# 4. 创建 Agent Loop
agent = AgentLoop(
    bus=bus,
    provider=provider,
    workspace=config.workspace_path,
    # ...
)

# 5. 创建渠道管理器
channels = ChannelManager(config, bus)

# 6. 并发运行所有组件
await asyncio.gather(
    agent.run(),         # 处理消息
    channels.start_all(),  # 启动渠道
)
```

---

### 2️⃣ 配置系统 (`nanobot/config/`)

#### schema.py - 配置数据模型

```python
class Config(BaseSettings):
    agents: AgentsConfig        # 默认设置 (model, maxTokens, workspace)
    channels: ChannelsConfig      # 渠道配置 (telegram, whatsapp, feishu)
    providers: ProvidersConfig    # LLM 提供商 (OpenRouter, Anthropic, MiniMax, etc.)
    gateway: GatewayConfig       # 网关配置 (host, port)
    tools: ToolsConfig          # 工具配置 (web.search, exec)

    # 优先级获取 API key
    def get_api_key(self) -> str | None:
        return (self.providers.openrouter.api_key or
                self.providers.deepseek.api_key or
                self.providers.minimax.api_key or
                # ...)

    # 获取 API base
    def get_api_base(self) -> str | None:
        if self.providers.openrouter.api_key:
            return "https://openrouter.ai/api/v1"
        if self.providers.minimax.api_key:
            return self.providers.minimax.api_base
        # ...
```

**配置文件位置**：`~/.nanobot/config.json`

---

### 3️⃣ LLM Provider (`nanobot/providers/`)

#### base.py - 抽象基类

```python
class LLMProvider(ABC):
    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        pass
```

#### litellm_provider.py - LiteLLM 实现

**职责**：通过 LiteLLM 统一接口支持多个 LLM

**核心逻辑**：

```python
class LiteLLMProvider(LLMProvider):
    def __init__(self, api_key, api_base, default_model):
        # 1. 检测 provider 类型
        self.is_openrouter = api_key and api_key.startswith("sk-or-")
        self.is_minimax = api_base and "minimaxi.com" in api_base
        self.is_vllm = bool(api_base) and not (self.is_openrouter or self.is_minimax)

        # 2. 设置环境变量
        if api_key:
            if self.is_openrouter:
                os.environ["OPENROUTER_API_KEY"] = api_key
            elif self.is_vllm:
                os.environ["OPENAI_API_KEY"] = api_key
            elif "minimax" in default_model.lower():
                os.environ.setdefault("MINIMAX_API_KEY", api_key)

        # 3. 配置 LiteLLM
        if api_base:
            litellm.api_base = api_base

    async def chat(self, messages, tools, model, max_tokens, temperature):
        # 1. 处理模型名称 (OpenRouter/MiniMax 前缀)
        if self.is_openrouter:
            model = f"openrouter/{model}"
        if self.is_minimax and "minimax/" not in model:
            model = f"minimax/{model}"
        if self.is_vllm:
            model = f"hosted_vllm/{model}"

        # 2. 调用 LiteLLM
        kwargs = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if self.api_base:
            kwargs["base_url"] = self.api_base  # 注意：LiteLLM 1.81.8 用 base_url
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if tools:
            kwargs["tools"] = tools

        response = await acompletion(**kwargs)
        return self._parse_response(response)
```

**支持的 LLM**：

- OpenRouter (聚合平台)
- Anthropic (Claude)
- OpenAI (GPT-4, GPT-4.1)
- MiniMax (OpenAI 兼容)
- DeepSeek
- Groq
- Zhipu (智谱)
- Gemini
- vLLM (本地部署)

---

### 4️⃣ Agent 核心引擎 (`nanobot/agent/loop.py`)

#### 核心职责

```python
class AgentLoop:
    """代理循环：处理消息的核心引擎"""

    def __init__(self, bus, provider, workspace, ...):
        self.bus = bus
        self.provider = provider
        self.context = ContextBuilder(workspace)    # 上下文构建器
        self.sessions = SessionManager(workspace)    # 会话管理器
        self.tools = ToolRegistry()               # 工具注册表
        self.subagents = SubagentManager(...)        # 子代理管理器

        # 注册默认工具
        self._register_default_tools()

    async def run(self):
        """主循环：等待并处理消息"""
        while self._running:
            msg = await asyncio.wait_for(self.bus.consume_inbound(), timeout=1.0)
            response = await self._process_message(msg)
            if response:
                await self.bus.publish_outbound(response)
```

#### 消息处理流程

```
InboundMessage (收到消息)
    ↓
1. _process_message()
    ↓
2. 识别：用户消息 / 系统消息 / 工具结果
    ↓
3. 构建上下文：
   - ContextBuilder.build_system_prompt()
     ├─ 身份 (时间、系统、工作区)
     ├─ 引导文件 (AGENTS.md, SOUL.md, USER.md, TOOLS.md)
     ├─ 记忆 (MEMORY.md)
     └─ 技能 (活跃技能摘要)
    ↓
4. 构建消息列表：
   - build_messages(history, current_message, media)
    ↓
5. 调用 LLM：
   - provider.chat(messages, tools)
    ↓
6. 解析响应：
   - _parse_response()
     ├─ 纯文本 → 直接回复
     └─ 工具调用 → 执行工具
    ↓
7. 工具执行循环 (max 20 次)：
   while tool_calls:
     ├─ 执行工具 (ToolRegistry.execute)
     ├─ 收集结果 (ContextBuilder.add_tool_result)
     └─ 再次调用 LLM (传入工具结果)
    ↓
8. OutboundMessage (发送回复)
```

---

### 5️⃣ 工具系统 (`nanobot/agent/tools/`)

#### base.py - 工具基类

```python
class Tool(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称"""

    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述"""

    @property
    @abstractmethod
    def parameters(self) -> dict:
        """JSON Schema 参数"""

    @abstractmethod
    async def execute(self, **kwargs) -> str:
        """执行工具"""

    def to_schema(self) -> dict:
        """转换为 OpenAI function schema"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }
```

#### 内置工具清单

| 工具 | 文件 | 功能 |
|------|------|------|
| read_file | filesystem.py | 读取文件内容 |
| write_file | filesystem.py | 写入文件 |
| edit_file | filesystem.py | 编辑文件 (替换) |
| list_dir | filesystem.py | 列出目录 |
| exec | shell.py | 执行 shell 命令 |
| web_search | web.py | 网页搜索 (Brave API) |
| web_fetch | web.py | 获取网页内容 (readability) |
| message | message.py | 发送消息到指定渠道 |
| spawn | spawn.py | 创建子代理 |
| cron | cron.py | 管理定时任务 |

#### 工具注册

```python
class ToolRegistry:
    """工具注册表"""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    async def execute(self, name: str, params: dict) -> str:
        tool = self._tools.get(name)
        return await tool.execute(**params)

    def get_definitions(self) -> list[dict]:
        """获取所有工具的 OpenAI function schema"""
        return [tool.to_schema() for tool in self._tools.values()]
```

---

### 6️⃣ 上下文构建 (`nanobot/agent/context.py`)

#### 引导文件

```python
class ContextBuilder:
    BOOTSTRAP_FILES = [
        "AGENTS.md",   # 代理指令
        "SOUL.md",     # 个性定义
        "USER.md",      # 用户偏好
        "TOOLS.md",     # 工具说明
        "IDENTITY.md",  # 身份信息
    ]
```

#### System Prompt 组成

```
1. 身份 (nanobot 🐈)
   └─ 当前时间 (2026-02-06 15:05)
   └─ 运行环境 (macOS arm64, Python 3.12)
   └─ 工作区路径

2. 引导文件内容
   └─ 逐个加载 BOOTSTRAP_FILES

3. 记忆 (MEMORY.md)
   └─ 从 memory/ 目录读取

4. 活跃技能
   └─ 加载 always 技能内容

5. 可用技能摘要
   └─ 列出 workspace/skills 下的技能
```

---

### 7️⃣ 消息总线 (`nanobot/bus/`)

#### queue.py - 异步消息队列

```python
class MessageBus:
    """消息总线：解耦渠道与 Agent"""

    def __init__(self):
        self.inbound: asyncio.Queue[InboundMessage]   # 入站消息
        self.outbound: asyncio.Queue[OutboundMessage] # 出站消息
        self._outbound_subscribers: dict[str, list[Callable]]  # 渠道订阅

    async def publish_inbound(self, msg):
        """发布入站消息（渠道 → Agent）"""
        await self.inbound.put(msg)

    async def publish_outbound(self, msg):
        """发布出站消息（Agent → 渠道）"""
        await self.outbound.put(msg)

    def subscribe_outbound(self, channel, callback):
        """订阅出站消息（渠道订阅）"""
        if channel not in self._outbound_subscribers:
            self._outbound_subscribers[channel] = []
        self._outbound_subscribers[channel].append(callback)

    async def dispatch_outbound(self):
        """分发出站消息到对应渠道"""
        while True:
            msg = await self.bus.consume_outbound()
            subscribers = self._outbound_subscribers.get(msg.channel, [])
            for callback in subscribers:
                await callback(msg)
```

#### 消息流

```
Telegram/WhatsApp/Feishu
    ↓ publish_inbound(InboundMessage)
    ↓ MessageBus.inbound (Queue)
    ↓ AgentLoop.consume_inbound()
    ↓ 处理
    ↓ publish_outbound(OutboundMessage)
    ↓ MessageBus.outbound (Queue)
    ↓ dispatch_outbound()
    ↓ Telegram.send() / WhatsApp.send() / Feishu.send()
```

---

### 8️⃣ 会话管理 (`nanobot/session/manager.py`)

```python
@dataclass
class Session:
    key: str                    # channel:chat_id
    messages: list[dict]           # 对话历史
    created_at: datetime
    updated_at: datetime
    metadata: dict                # 元数据

    def add_message(self, role, content):
        """添加消息"""

    def get_history(self, max_messages=50):
        """获取历史（LLM 格式）"""

class SessionManager:
    """会话管理器"""

    def get_or_create(self, key):
        """获取或创建会话"""

    def save(self, session):
        """保存会话到 JSONL 文件"""
```

**存储位置**：`~/.nanobot/sessions/`

**格式**：JSONL (每行一个 JSON)

---

### 9️⃣ 聊天渠道 (`nanobot/channels/`)

#### base.py - 渠道基类

```python
class BaseChannel(ABC):
    @abstractmethod
    async def start(self):
        """启动渠道"""

    @abstractmethod
    async def stop(self):
        """停止渠道"""

    @abstractmethod
    async def send(self, msg: OutboundMessage):
        """发送消息"""

    @property
    @abstractmethod
    def is_running(self) -> bool:
        """是否运行中"""
```

#### manager.py - 渠道管理器

```python
class ChannelManager:
    """管理多个渠道"""

    def _init_channels(self):
        if config.channels.telegram.enabled:
            self.channels["telegram"] = TelegramChannel(...)
        if config.channels.whatsapp.enabled:
            self.channels["whatsapp"] = WhatsAppChannel(...)
        if config.channels.feishu.enabled:
            self.channels["feishu"] = FeishuChannel(...)

    async def start_all(self):
        """启动所有渠道"""
        tasks = []
        for name, channel in self.channels.items():
            tasks.append(asyncio.create_task(channel.start()))
        await asyncio.gather(*tasks)

    async def _dispatch_outbound(self):
        """分发出站消息"""
        while True:
            msg = await self.bus.consume_outbound()
            channel = self.channels.get(msg.channel)
            if channel:
                await channel.send(msg)
```

#### feishu.py - 飞书渠道

```python
class FeishuChannel(BaseChannel):
    """飞书渠道：WebSocket 长连接"""

    async def start(self):
        """启动 WebSocket 连接"""
        client = lark.ws.Client(
            app_id=self.config.app_id,
            app_secret=self.config.app_secret,
        )
        client.set_event_handler(self._on_message)
        client.start()

    async def _on_message(self, data):
        """收到消息"""
        await self.bus.publish_inbound(InboundMessage(
            channel="feishu",
            chat_id=data.sender_id,
            content=data.content,
            media=data.media,
        ))

    async def send(self, msg):
        """发送消息"""
        response = client.message.create(
            CreateMessageRequest(
                receive_id_type="open_id",
                receive_id=msg.chat_id,
                msg_type="text",
                content=msg.content,
            )
        )
```

---

### 🔟 定时任务 (`nanobot/cron/`)

#### service.py - Cron 服务

```python
class CronService:
    """定时任务服务"""

    def _compute_next_run(schedule, now_ms):
        """计算下次运行时间"""
        if schedule.kind == "every":
            return now_ms + schedule.every_ms
        if schedule.kind == "cron" and schedule.expr:
            from croniter import croniter
            cron = croniter(schedule.expr, time.time())
            next_time = cron.get_next()
            return int(next_time * 1000)

    async def start(self):
        """启动定时器"""
        while self._running:
            now_ms = _now_ms()
            due_jobs = [job for job in self._store.jobs if job.next_run_at_ms <= now_ms]
            for job in due_jobs:
                await self.on_job(job)
```

**任务类型**：

| 类型 | 说明 | 示例 |
|------|------|------|
| `at` | 指定时间执行 | `"2026-02-07 09:00"` |
| `every` | 间隔执行 | `{"every": 3600000}` (1小时) |
| `cron` | Cron 表达式 | `"0 9 * * *"` (每天9点) |

---

## 🔄 数据流

### 1️⃣ 用户发消息流程 (飞书私聊)

```
用户在飞书发送 "你好"
    ↓
FeishuChannel 收到 WebSocket 事件
    ↓
publish_inbound(InboundMessage{channel: "feishu", chat_id: "ou_xxx", content: "你好"})
    ↓
MessageBus.inbound.put()
    ↓
AgentLoop 消费消息
    ↓
ProcessMessage:
  ├─ 获取/创建会话
  ├─ 构建上下文:
  │   ├─ System Prompt (身份 + 引导 + 记忆 + 技能)
  │   └─ History (会话历史)
  └─ 调用 LLM:
      ├─ model: minimax/MiniMax-M2.1
      ├─ messages: [system, user_message]
      └─ tools: [read_file, write_file, exec, web_search, ...]
    ↓
LLM 响应: "你好！有什么可以帮你的？"
    ↓
publish_outbound(OutboundMessage{channel: "feishu", chat_id: "ou_xxx", content: "你好！..."})
    ↓
FeishuChannel 发送消息
    ↓
用户收到回复
```

### 2️⃣ 工具调用流程

```
用户: "帮我读取 test.txt 文件"
    ↓
LLM 响应: tool_calls=[{name: "read_file", arguments: {path: "test.txt"}}]
    ↓
ToolRegistry.execute("read_file", {path: "test.txt"})
    ↓
ReadFileTool.execute(path="test.txt")
    ↓
返回结果: "文件内容是：Hello World"
    ↓
ContextBuilder.add_tool_result(tool_call_id, "read_file", "文件内容是：Hello World")
    ↓
再次调用 LLM (传入工具结果)
    ↓
LLM 响应: "文件已读取，内容是 Hello World"
    ↓
发送给用户
```

---

## 🎯 关键设计模式

| 模式 | 应用 | 说明 |
|------|------|------|
| **事件驱动** | MessageBus | 异步队列解耦模块 |
| **抽象工厂** | LLMProvider, Tool | 支持多种 LLM/工具 |
| **注册表模式** | ToolRegistry | 动态注册工具 |
| **策略模式** | ContextBuilder | 不同的技能加载策略 |
| **观察者模式** | ChannelManager | 订阅出站消息 |
| **单一职责** | 每个类职责明确 | 易于测试和维护 |

---

## 🔌 扩展点

### 1. 添加新的 LLM Provider

```python
# nanobot/providers/my_provider.py
class MyLLMProvider(LLMProvider):
    async def chat(self, messages, tools, ...):
        # 调用你的 LLM API
        return LLMResponse(content="...")

# nanobot/config/schema.py
class ProvidersConfig(BaseModel):
    my_provider: ProviderConfig = Field(default_factory=ProviderConfig)

# nanobot/config/loader.py
def get_api_key(self):
    return self.providers.my_provider.api_key or ...
```

### 2. 添加新的工具

```python
# nanobot/agent/tools/my_tool.py
class MyTool(Tool):
    @property
    def name(self) -> str:
        return "my_tool"

    @property
    def description(self) -> str:
        return "我的工具描述"

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {...}}

    async def execute(self, **kwargs) -> str:
        # 工具逻辑
        return "执行结果"

# nanobot/agent/loop.py
def _register_default_tools(self):
    self.tools.register(MyTool())
```

### 3. 添加新的聊天渠道

```python
# nanobot/channels/my_channel.py
class MyChannel(BaseChannel):
    async def start(self):
        # 启动逻辑

    async def send(self, msg):
        # 发送逻辑

    async def _on_message(self, data):
        await self.bus.publish_inbound(...)

# nanobot/config/schema.py
class ChannelsConfig(BaseModel):
    my_channel: MyChannelConfig = Field(default_factory=MyChannelConfig)

# nanobot/channels/manager.py
def _init_channels(self):
    if self.config.channels.my_channel.enabled:
        self.channels["my_channel"] = MyChannel(...)
```

### 4. 添加新的技能

```bash
~/.nanobot/workspace/skills/my_skill/SKILL.md
---
# My Skill

## Description
描述这个技能的功能

## Requirements
技能依赖的软件包

## Usage
如何使用这个技能的说明

## Instructions
技能的详细指令
```

---

## 📚 学习路径

### 入门 (1-2天)

1. **理解整体架构** (本文档)
   - 消息流：渠道 → 总线 → Agent → LLM → 工具 → LLM → 渠道
   - 核心组件：AgentLoop, MessageBus, ToolRegistry

2. **阅读 CLI 入口** (`nanobot/cli/commands.py`)
   - `gateway` 命令如何启动所有组件
   - `agent` 命令如何处理单条消息

3. **阅读核心引擎** (`nanobot/agent/loop.py`)
   - 主循环如何等待和处理消息
   - 工具执行循环（最多 20 次）

### 进阶 (3-5天)

4. **阅读工具系统** (`nanobot/agent/tools/`)
   - base.py - 工具抽象接口
   - filesystem.py - 文件操作实现
   - shell.py - 命令执行实现

5. **阅读渠道实现** (`nanobot/channels/`)
   - feishu.py - WebSocket 长连接
   - telegram.py - Bot API 集成

6. **理解上下文构建** (`nanobot/agent/context.py`)
   - 引导文件如何加载
   - 记忆如何插入

### 高级 (6-7天)

7. **阅读 LLM Provider** (`nanobot/providers/litellm_provider.py`)
   - LiteLLM 如何统一多个 LLM
   - 模型名称如何处理 (前缀逻辑)

8. **阅读定时任务** (`nanobot/cron/`)
   - Cron 表达式如何解析
   - 任务调度如何实现

9. **动手实验**
   - 添加一个自定义工具
   - 添加一个新的技能
   - 添加一个新的渠道

---

## 🔍 调试技巧

### 1. 启用详细日志

```bash
export PYTHONPATH=/path/to/nanobot
nanobot agent -m "test"
```

### 2. 查看消息流

```python
# 在 nanobot/agent/loop.py 的 _process_message 中添加
logger.info(f"Processing: {msg.channel}:{msg.chat_id} - {msg.content[:50]}")
```

### 3. 测试工具单独执行

```python
# nanobot/tests/test_tools.py
async def test_read_file():
    tool = ReadFileTool()
    result = await tool.execute(path="test.txt")
    assert "Hello" in result
```

### 4. 监控消息队列

```python
# 在 CLI 中添加
logger.info(f"Inbound: {bus.inbound_size}, Outbound: {bus.outbound_size}")
```

---

## 💡 关键代码位置速查

| 功能 | 文件路径 | 关键函数 |
|------|---------|---------|
| 启动网关 | `cli/commands.py` | `gateway()` |
| 主循环 | `agent/loop.py` | `AgentLoop.run()` |
| 消息处理 | `agent/loop.py` | `_process_message()` |
| 工具执行 | `agent/tools/registry.py` | `execute()` |
| 上下文构建 | `agent/context.py` | `build_system_prompt()` |
| 消息总线 | `bus/queue.py` | `MessageBus.publish_inbound()` |
| 渠道管理 | `channels/manager.py` | `ChannelManager.start_all()` |
| 飞书渠道 | `channels/feishu.py` | `FeishuChannel.start()` |
| LLM 调用 | `providers/litellm_provider.py` | `LiteLLMProvider.chat()` |

---

## 🎓 总结

nanobot 是一个**设计优秀的轻量级 AI 代理框架**：

✅ **模块化**：每个组件职责明确，易于扩展
✅ **异步**：基于 asyncio，高效处理并发
✅ **事件驱动**：消息总线解耦各模块
✅ **多 Provider**：支持多种 LLM，可灵活切换
✅ **工具系统**：可动态注册/执行工具
✅ **多渠道**：Telegram/WhatsApp/Feishu 一体集成
✅ **定时任务**：Cron 支持，可自动化操作
✅ **持久化**：会话、配置、任务都持久化存储

---

**祝学习愉快！🐈**
