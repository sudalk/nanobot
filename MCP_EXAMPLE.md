# MCP (Model Context Protocol) 集成

nanobot 支持通过 MCP 协议接入外部工具。

## 使用 MiniMax MCP Server

### 方法1：自动配置（推荐）

如果你已经在 `~/.nanobot/config.json` 中配置了 MiniMax API Key，MCP 工具会自动启用：

```json
{
  "providers": {
    "minimax": {
      "api_key": "your-api-key",
      "api_base": "https://api.minimax.com"
    }
  }
}
```

启动 nanobot 后，`minimax` 工具会自动注册。

### 方法2：显式配置

在 `~/.nanobot/config.json` 中添加 MCP 配置：

```json
{
  "tools": {
    "mcp": {
      "enabled": true,
      "command": "uvx",
      "args": ["minimax-coding-plan-mcp", "-y"],
      "env": {
        "MINIMAX_API_KEY": "your-api-key",
        "MINIMAX_API_BASE": "https://api.minimax.com"
      },
      "alias": "minimax"
    }
  }
}
```

### 方法3：使用 Claude Desktop 配置

如果你之前用 Claude Desktop 添加过 MCP，可以直接复制配置：

```bash
# Claude Desktop 配置通常在：
# macOS: ~/Library/Application Support/Claude/claude_desktop_config.json
# Windows: %APPDATA%/Claude/claude_desktop_config.json
```

把其中的 `mcpServers` 配置转换为 nanobot 的格式即可。

## 测试 MCP 工具

启动 nanobot 后，可以测试：

```bash
nanobot agent -m "使用 minimax 工具帮我制定一个学习计划"
```

或者在 Web 界面中直接询问。

## 添加其他 MCP Servers

你可以添加任何符合 MCP 协议的服务器：

```json
{
  "tools": {
    "mcp": {
      "enabled": true,
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allow"],
      "alias": "filesystem"
    }
  }
}
```

## 常见问题

1. **uvx 未找到**: 确保已安装 uv：`pip install uv`
2. **MCP 工具未显示**: 检查 nanobot 日志，确认配置已加载
3. **环境变量**: 敏感信息建议使用环境变量而非写入配置文件

## 相关资源

- [MCP 文档](https://modelcontextprotocol.io/)
- [MiniMax MCP Server](https://github.com/your-repo/minimax-coding-plan-mcp)
