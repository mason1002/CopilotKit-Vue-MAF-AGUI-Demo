# Vue + CopilotKit + Agent Framework AG-UI Direct Demo

Connect a Vue 3 chat interface directly to a Python Agent Framework endpoint over AG-UI. Do not run an intermediary agent service.

```text
Vue 3 + CopilotKit
        |
        | HttpAgent, HTTP POST, SSE
        v
FastAPI + Agent Framework
        |
        v
Deterministic local client
```

Use the deterministic client to reproduce the full request path without an external model account, API key, or usage charge.

## Prerequisites

Install these tools before continuing:

| Tool | Supported version |
| --- | --- |
| Windows | 10 or later |
| PowerShell | 7 or Windows PowerShell 5.1 |
| Python | 3.12 or later |
| Node.js | 22 or later |
| npm | Included with Node.js |

Confirm the tools:

```powershell
python --version
node --version
npm --version
```

Keep ports `8100`, `5174`, `8110`, and `5184` available.

## Run The Demo

### 1. Clone The Repository

```powershell
$REPOSITORY_URL = "https://github.com/OWNER/REPOSITORY.git"
git clone $REPOSITORY_URL vue-agui-direct-demo
cd vue-agui-direct-demo
```

### 2. Start The Services

```powershell
.\start-demo.ps1
```

The script performs these actions:

- create `.venv` when it does not exist;
- install Python dependencies from `backend/requirements.txt`;
- install frontend dependencies with `npm ci`;
- start FastAPI on `127.0.0.1:8100`;
- start Vite on `127.0.0.1:5174`;
- stop the API when the Vite process exits.

### 3. Open The Application

Open <http://127.0.0.1:5174/?scoutTheme=light>.

### 4. Verify The Request

Send a message. Confirm the request route shows three nodes:

```text
Vue -> Python Agent -> Local client
```

Confirm the event list starts with `RUN_STARTED` and ends with `RUN_FINISHED`.

## Run The Tests

Run the isolated Direct test suite:

```powershell
.\scripts\test-direct.ps1
```

The script uses these isolated ports:

| Component | Port |
| --- | ---: |
| FastAPI | 8110 |
| Vite | 5184 |

The script does not start an intermediary agent service. It performs these checks:

- validate CORS preflight behavior;
- reject missing and invalid bearer tokens;
- verify the AG-UI SSE event sequence;
- confirm the browser posts only to `/agent`;
- confirm the chat displays the streamed response;
- confirm the desktop layout has no horizontal overflow.

## Understand The Direct Connection

Create an AG-UI client in Vue:

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

Register the client with the Vue provider:

```vue
<CopilotKitProvider
  :self-managed-agents="{ 'direct-agent': agent }"
  :public-license-key="publicLicenseKey || undefined"
>
  <CopilotChat agent-id="direct-agent" />
</CopilotKitProvider>
```

Expose the Python Agent through the AG-UI adapter:

```python
from agent_framework_ag_ui import add_agent_framework_fastapi_endpoint

add_agent_framework_fastapi_endpoint(app, agent, "/agent")
```

## Configure The Frontend

Copy the frontend example only when an endpoint override or public license key is required:

```powershell
Copy-Item frontend\.env.example frontend\.env
```

Set these variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `VITE_AGENT_URL` | `http://127.0.0.1:8100` | Set the FastAPI base URL. |
| `VITE_COPILOTKIT_PUBLIC_LICENSE_KEY` | empty | Supply the public key required by the applicable product license. |

Do not place private credentials in a `VITE_` variable. Vite includes these values in the browser bundle.

## Configure The API

Copy the API example only when changing the default host or demo secret:

```powershell
Copy-Item backend\.env.example backend\.env
```

Set these variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `FRONTEND_ORIGIN` | `http://127.0.0.1:5174` | Allow one browser origin through CORS. |
| `DEMO_JWT_SECRET` | local demo value | Replace before binding outside loopback. |

Keep the default API bound to loopback. Replace the demo token endpoint before any network deployment.

## Review The Security Boundary

Treat every browser field as untrusted. Enforce these controls in the API:

- validate the token before starting an Agent run;
- rebuild roles and data scope from a trusted server-side source;
- bind thread, snapshot, interrupt, resume, and cancel operations to the authenticated owner;
- authorize every tool call independently;
- restrict CORS to exact origins and headers;
- limit request size, concurrency, duration, and rate;
- avoid logging tokens, prompts, or sensitive tool output;
- return generic external errors;
- use HTTPS outside loopback;
- place the Agent endpoint behind a trusted same-origin BFF or API gateway when possible.

Read [SECURITY.md](SECURITY.md) before adapting the demo for deployment.

## Project Layout

```text
backend/
  main.py                  FastAPI, JWT validation, deterministic Agent
  tests/                   API and AG-UI contract tests
frontend/
  src/App.vue              Vue UI, HttpAgent, live request telemetry
  tests/                   Playwright Direct tests
scripts/
  test-direct.ps1          Isolated test runner
.github/workflows/ci.yml   Build and test workflow
```

## Known Limits

- Use the local token issuer only for demonstration.
- Implement persistent thread storage in the application when required.
- Implement production authorization, rate limits, audit, and content controls separately.
- Confirm the applicable license before using `selfManagedAgents` in production.
- Expect a large frontend bundle because the prebuilt chat package includes optional rendering features.

## License

Use this project under the terms of the [MIT License](LICENSE).
