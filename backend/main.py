import asyncio
import os
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from typing import Any, Sequence
from uuid import uuid4

import jwt
from agent_framework import Agent, ChatResponse, ChatResponseUpdate, Content, Message, ResponseStream
from agent_framework.ag_ui import add_agent_framework_fastapi_endpoint
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

JWT_ISSUER = "vue-agent-demo"
JWT_AUDIENCE = "vue-agent-api"
DEFAULT_DEMO_JWT_SECRET = "local-demo-secret-change-me"
JWT_SECRET = os.getenv("DEMO_JWT_SECRET", DEFAULT_DEMO_JWT_SECRET)
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://127.0.0.1:5174")

if JWT_SECRET == DEFAULT_DEMO_JWT_SECRET and not FRONTEND_ORIGIN.startswith(
    ("http://127.0.0.1:", "http://localhost:")
):
    raise RuntimeError("Set DEMO_JWT_SECRET before exposing the demo outside loopback.")


class Principal(BaseModel):
    subject: str
    tenant_id: str
    roles: list[str]


def create_demo_token() -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "iss": JWT_ISSUER,
            "aud": JWT_AUDIENCE,
            "sub": "alice",
            "tid": "demo-tenant",
            "roles": ["agent-user"],
            "iat": now,
            "exp": now + timedelta(minutes=15),
        },
        JWT_SECRET,
        algorithm="HS256",
    )


def authenticate(authorization: str | None = Header(default=None)) -> Principal:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        claims = jwt.decode(
            authorization.removeprefix("Bearer "),
            JWT_SECRET,
            algorithms=["HS256"],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
        )
    except jwt.PyJWTError as error:
        raise HTTPException(status_code=401, detail="Invalid bearer token") from error
    return Principal(subject=claims["sub"], tenant_id=claims["tid"], roles=claims.get("roles", []))


current_principal: ContextVar[Principal | None] = ContextVar("current_principal", default=None)
current_transport: ContextVar[str] = ContextVar("current_transport", default="direct")


class DeterministicChatClient:
    additional_properties: dict[str, Any] = {"model": "deterministic-local-client"}

    def get_response(self, messages: Sequence[Message], *, stream: bool = False, **_: Any) -> Any:
        prompt = next((message.text for message in reversed(messages) if str(message.role) == "user"), "Hello")
        principal = current_principal.get()
        transport = current_transport.get()
        identity = f"{principal.subject}@{principal.tenant_id}" if principal else "authenticated user"
        route = "directly from Vue"
        text = (
            f"Vue + Agent Framework connection confirmed for {identity}. "
            f"The Python Agent Framework agent received: '{prompt}'. "
            f"The request traveled {route} and returned as an AG-UI event stream."
        )
        response_id = str(uuid4())

        if not stream:
            async def complete() -> ChatResponse[Any]:
                return ChatResponse(
                    messages=[Message("assistant", [text])],
                    response_id=response_id,
                    model="deterministic-local-client",
                )
            return complete()

        async def updates():
            for chunk in text.split(" "):
                await asyncio.sleep(0.025)
                yield ChatResponseUpdate(
                    contents=[Content.from_text(f"{chunk} ")],
                    role="assistant",
                    response_id=response_id,
                    model="deterministic-local-client",
                )

        def finalize(items: Sequence[ChatResponseUpdate]) -> ChatResponse[Any]:
            return ChatResponse(
                messages=[Message("assistant", ["".join(item.text or "" for item in items)])],
                response_id=response_id,
                model="deterministic-local-client",
            )
        return ResponseStream(updates(), finalizer=finalize)


local_agent = Agent(
    name="VueDirectDemoAgent",
    instructions="Confirm the Vue, CopilotKit, AG-UI, and Agent Framework request path concisely.",
    client=DeterministicChatClient(),
)

app = FastAPI(title="Vue CopilotKit + Python Agent Framework Demo", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN, FRONTEND_ORIGIN.replace("127.0.0.1", "localhost")],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Demo-Transport", "X-Demo-Request-ID"],
)


@app.middleware("http")
async def jwt_middleware(request: Request, call_next):
    if not request.url.path.startswith("/agent") or request.method == "OPTIONS":
        return await call_next(request)
    try:
        principal = authenticate(request.headers.get("authorization"))
    except Exception as error:
        return JSONResponse(
            {"detail": getattr(error, "detail", "Invalid bearer token")},
            status_code=getattr(error, "status_code", 401),
        )
    principal_token = current_principal.set(principal)
    transport_token = current_transport.set(request.headers.get("x-demo-transport", "direct"))
    try:
        return await call_next(request)
    finally:
        current_transport.reset(transport_token)
        current_principal.reset(principal_token)


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "mode": "python-agent-framework",
        "agentEndpoint": "http://127.0.0.1:8100/agent",
        "model": "deterministic-local-client",
    }


@app.get("/demo-token")
async def demo_token() -> dict[str, str]:
    return {"access_token": create_demo_token(), "token_type": "bearer"}


add_agent_framework_fastapi_endpoint(app, local_agent, "/agent")