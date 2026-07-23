# Vue + CopilotKit + Agent Framework AG-UI 直连示例

通过 AG-UI，让 Vue 3 聊天界面直接连接 Python Agent Framework 接口，不经过中间 Runtime 服务。

```text
Vue 3 + CopilotKit
        |
        | HttpAgent、HTTP POST、SSE
        v
FastAPI + Agent Framework
        |
        v
本地确定性客户端
```

本示例使用确定性客户端，无需外部模型账号、API 密钥或模型调用费用，即可复现完整请求链路。

## 识别 Agent Framework AG-UI 适配器

使用 `agent-framework-ag-ui` 作为 Agent Framework 对应的 AG-UI 适配器。FastAPI 注册函数可接收原生 Agent Framework `Agent` 或 `Workflow`，将 AG-UI 请求转换为 Framework Run，并将 Framework 事件通过 AG-UI SSE 事件流返回。

| Agent 后端 | AG-UI 集成方式 |
| --- | --- |
| LangGraph | 通过其 AG-UI 适配器封装或暴露编译后的 Graph。 |
| Agent Framework | 调用 `add_agent_framework_fastapi_endpoint(app, agent, "/agent")`。 |

不要仅为了完成协议转换而增加 Copilot Runtime。Agent Framework 的 AG-UI 包已经提供消息转换、事件桥接、流式响应、状态、线程快照、中断与恢复，以及 FastAPI 接口注册能力。

优先使用以下公开导入路径：

```python
from agent_framework.ag_ui import add_agent_framework_fastapi_endpoint
```

也可以直接从 `agent_framework_ag_ui` 导入，但推荐应用使用上面的 Framework facade。

## 区分 Runtime 与直连模式

`runtimeUrl` 和 `selfManagedAgents` 代表两种不同架构：

| Provider 配置 | 浏览器请求目标 | Copilot Runtime | Agent 选择方式 |
| --- | --- | --- | --- |
| `runtime-url="http://localhost:9000/copilotkit"` | `/copilotkit` | 存在 | Runtime 自动发现和路由 |
| `:self-managed-agents="{ 'direct-agent': agent }"` | FastAPI `/agent` | 不存在 | 浏览器显式注册 |

CopilotKit Vue Agent Framework 快速入门当前展示的是第一种架构。只要使用 `runtime-url` 和 `/copilotkit/info`，请求链路中就仍然包含 Runtime，即使下游 Agent 通过 AG-UI 暴露。

本仓库展示第二种架构。项目不安装 `@copilotkit/runtime`，不暴露 `/copilotkit` 或 `/copilotkit/info`，不使用 `CopilotKitRemoteEndpoint`，也不增加 Runtime 专用的 Agent Framework 包装层。

本示例使用以下链路：

```text
Vue CopilotKitProvider(selfManagedAgents)
  -> @ag-ui/client HttpAgent
  -> POST FastAPI /agent
  -> add_agent_framework_fastapi_endpoint
  -> Agent Framework Agent
  -> Chat Client
```

如果目标是直连，请勿使用以下 Runtime 链路：

```text
Vue CopilotKitProvider(runtimeUrl)
  -> POST /copilotkit
  -> Copilot Runtime 发现和路由
  -> 远程 AG-UI Agent
```

生产环境直接连接 AG-UI Agent 时，应使用 `selfManagedAgents`，不要使用仅限开发的 `agents__unsafe_dev_only`。CopilotKit 当前将 `selfManagedAgents` 列为 Enterprise Intelligence 能力，并要求联系其团队确认生产许可。没有 License Key 时功能可能仍能运行，但这不代表已获得生产使用授权。请在上线前确认适用套餐、许可条款和功能限制。

## 前置条件

请先安装以下工具：

| 工具 | 支持版本 |
| --- | --- |
| Windows | 10 或更高版本 |
| PowerShell | 7 或 Windows PowerShell 5.1 |
| Python | 3.12 或更高版本 |
| Node.js | 22 或更高版本 |
| npm | 随 Node.js 安装 |

确认工具版本：

```powershell
python --version
node --version
npm --version
```

确保端口 `8100`、`5174`、`8110` 和 `5184` 未被占用。

## 运行示例

### 1. 克隆仓库

```powershell
$REPOSITORY_URL = "https://github.com/OWNER/REPOSITORY.git"
git clone $REPOSITORY_URL vue-agui-direct-demo
cd vue-agui-direct-demo
```

### 2. 启动服务

```powershell
.\start-demo.ps1
```

脚本会执行以下操作：

- 不存在 `.venv` 时创建 Python 虚拟环境；
- 安装 `backend/requirements.txt` 中的 Python 依赖；
- 通过 `npm ci` 安装前端依赖；
- 在 `127.0.0.1:8100` 启动 FastAPI；
- 在 `127.0.0.1:5174` 启动 Vite；
- Vite 进程退出时停止 API。

### 3. 打开应用

访问 <http://127.0.0.1:5174/?scoutTheme=light>。

### 4. 验证请求链路

发送一条消息，确认界面显示以下三个节点：

```text
Vue -> Python Agent -> Local client
```

确认事件列表以 `RUN_STARTED` 开始，并以 `RUN_FINISHED` 结束。

## 运行测试

运行隔离的直连测试套件：

```powershell
.\scripts\test-direct.ps1
```

测试脚本使用以下隔离端口：

| 组件 | 端口 |
| --- | ---: |
| FastAPI | 8110 |
| Vite | 5184 |

该脚本不会启动中间 Runtime 服务，并验证：

- CORS 预检响应；
- 缺失或无效 Bearer Token 时拒绝请求；
- AG-UI SSE 事件顺序；
- 浏览器只向 `/agent` 发送请求；
- 不存在 `/copilotkit` Runtime 路由；
- 聊天窗口显示流式响应；
- 桌面布局无横向溢出。

## 理解直连实现

在 Vue 中创建 AG-UI 客户端：

```ts
import { HttpAgent } from "@ag-ui/client"

const agent = new HttpAgent({
  agentId: "direct-agent",
  url: "http://127.0.0.1:8100/agent",
  headers: {
    Authorization: `Bearer ${token}`,
  },
})
```

将客户端注册到 Vue Provider：

```vue
<CopilotKitProvider
  :self-managed-agents="{ 'direct-agent': agent }"
  :public-license-key="publicLicenseKey || undefined"
>
  <CopilotChat agent-id="direct-agent" />
</CopilotKitProvider>
```

通过 AG-UI 适配器暴露 Python Agent：

```python
from agent_framework.ag_ui import add_agent_framework_fastapi_endpoint

add_agent_framework_fastapi_endpoint(app, agent, "/agent")
```

## 配置前端

仅在需要覆盖接口地址或配置公开 License Key 时复制前端环境变量示例：

```powershell
Copy-Item frontend\.env.example frontend\.env
```

设置以下变量：

| 变量 | 默认值 | 用途 |
| --- | --- | --- |
| `VITE_AGENT_URL` | `http://127.0.0.1:8100` | 设置 FastAPI 基础地址。 |
| `VITE_COPILOTKIT_PUBLIC_LICENSE_KEY` | 空 | 设置适用产品许可要求的公开 License Key。 |

不要把私密凭据写入 `VITE_` 变量。Vite 会将这些变量包含在浏览器 Bundle 中。

## 配置 API

仅在需要更改默认 Host 或示例 Secret 时复制 API 环境变量示例：

```powershell
Copy-Item backend\.env.example backend\.env
```

设置以下变量：

| 变量 | 默认值 | 用途 |
| --- | --- | --- |
| `FRONTEND_ORIGIN` | `http://127.0.0.1:5174` | 允许一个浏览器 Origin 通过 CORS。 |
| `DEMO_JWT_SECRET` | 本地示例值 | 在绑定到非 Loopback 地址之前替换。 |

保持默认 API 仅绑定 Loopback 地址。部署到任何网络之前，必须替换示例 Token 接口。

## 检查安全边界

将所有浏览器输入视为不可信数据，并在 API 中实施以下控制：

- 在启动 Agent Run 前验证 Token；
- 从可信服务端数据源重建角色和数据范围；
- 将 Thread、Snapshot、Interrupt、Resume 和 Cancel 操作绑定到已认证 Owner；
- 独立授权每一次 Tool 调用；
- 将 CORS 限制为准确的 Origin 和 Header；
- 限制请求体大小、并发数、执行时间和请求频率；
- 避免记录 Token、Prompt 或敏感 Tool 输出；
- 对外返回通用错误信息；
- 在 Loopback 之外使用 HTTPS；
- 生产环境优先将 Agent 接口置于可信同源 BFF 或 API Gateway 之后。

在部署前阅读 [SECURITY.md](SECURITY.md)。

## 项目结构

```text
backend/
  main.py                  FastAPI、JWT 验证、确定性 Agent
  tests/                   API 和 AG-UI 契约测试
frontend/
  src/App.vue              Vue UI、HttpAgent、实时请求遥测
  tests/                   Playwright 直连测试
scripts/
  test-direct.ps1          隔离测试脚本
.github/workflows/ci.yml   构建和测试工作流
```

## 已知限制

- 本地 Token 签发接口仅用于演示。
- 按需在应用中实现持久化 Thread 存储。
- 暴露多个 Agent 时，实现明确的 Endpoint 选择或应用自有 Registry。
- 启用 Shared State、Frontend Tools、人工审批、Interrupt/Resume 和 Cancel 前，分别验证协议与授权逻辑。
- 单独实现生产环境认证授权、限流、审计和内容安全控制。
- 在生产环境使用 `selfManagedAgents` 前，向 CopilotKit 确认 Enterprise Intelligence 许可和费用。
- 预构建聊天组件包含可选渲染功能，因此前端 Bundle 较大。

## 许可证

本项目依据 [MIT License](LICENSE) 使用和分发。第三方依赖仍适用各自的许可证和商业条款。
