"""
hub/main.py — Saathi Cloud Hub: Multi-Tenant SaaS Message Broker

Central orchestration server deployed on HuggingFace Spaces (Docker).

Responsibilities:
  1. JWT-based authentication for users and daemons
  2. WebSocket management for Edge Daemon connections
  3. Redis Pub/Sub for real-time daemon registry & message brokering
  4. LLM Router integration for NL → execution payload conversion
  5. Offline fallback trigger when daemon is unreachable
"""

import asyncio
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

import redis.asyncio as aioredis
import uvicorn
from dotenv import load_dotenv
from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from hub.auth import (
    TokenPair,
    UserLogin,
    UserRegister,
    authenticate_user,
    create_daemon_token,
    create_token_pair,
    decode_token,
    register_user,
    validate_access_token,
    validate_daemon_psk,
    validate_daemon_token,
)
from hub.llm_router import LLMRouter, TaskTier, classify_intent, router as llm_router
from infrastructure.docker_fallback import CloudWorkspaceManager

load_dotenv()

# ── Logging ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("saathi.hub")

# ── Configuration ──────────────────────────────────────────────────────────────

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
HUB_HOST = os.getenv("HUB_HOST", "0.0.0.0")
HUB_PORT = int(os.getenv("HUB_PORT", "7860"))  # HF Spaces default
DAEMON_HEARTBEAT_TIMEOUT = int(os.getenv("DAEMON_HEARTBEAT_TIMEOUT", "60"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

# ── Redis Connection ───────────────────────────────────────────────────────────

redis_pool: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    """Get or create the Redis connection pool."""
    global redis_pool
    if redis_pool is None:
        try:
            redis_pool = aioredis.from_url(
                REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
            )
            await redis_pool.ping()
            logger.info(f"✅ Redis connected: {REDIS_URL}")
        except Exception as exc:
            logger.warning(f"⚠️  Redis unavailable ({exc}). Using in-memory fallback.")
            redis_pool = None
    return redis_pool


# ── In-Memory Daemon Registry (fallback if Redis is down) ─────────────────────

class DaemonRegistry:
    """
    Tracks connected Edge Daemons. Uses Redis when available,
    falls back to in-memory dict.
    """

    def __init__(self):
        self._local: dict[str, dict] = {}
        self._websockets: dict[str, WebSocket] = {}

    async def register(self, daemon_id: str, user_id: str, ws: WebSocket, metadata: dict = None):
        """Register a daemon connection."""
        entry = {
            "daemon_id": daemon_id,
            "user_id": user_id,
            "connected_at": datetime.now(timezone.utc).isoformat(),
            "last_heartbeat": time.time(),
            "metadata": metadata or {},
            "status": "online",
        }
        self._local[daemon_id] = entry
        self._websockets[daemon_id] = ws

        # Persist to Redis if available
        r = await get_redis()
        if r:
            try:
                await r.hset(f"daemon:{daemon_id}", mapping={
                    "user_id": user_id,
                    "status": "online",
                    "connected_at": entry["connected_at"],
                    "last_heartbeat": str(entry["last_heartbeat"]),
                })
                await r.sadd(f"user:{user_id}:daemons", daemon_id)
                # Publish registration event
                await r.publish("daemon_events", json.dumps({
                    "event": "daemon_connected",
                    "daemon_id": daemon_id,
                    "user_id": user_id,
                    "timestamp": entry["connected_at"],
                }))
            except Exception as exc:
                logger.warning(f"Redis write failed: {exc}")

        logger.info(f"🟢 Daemon registered: {daemon_id} (user: {user_id})")

    async def unregister(self, daemon_id: str):
        """Remove a daemon from the registry."""
        entry = self._local.pop(daemon_id, None)
        self._websockets.pop(daemon_id, None)

        r = await get_redis()
        if r and entry:
            try:
                await r.delete(f"daemon:{daemon_id}")
                await r.srem(f"user:{entry['user_id']}:daemons", daemon_id)
                await r.publish("daemon_events", json.dumps({
                    "event": "daemon_disconnected",
                    "daemon_id": daemon_id,
                    "user_id": entry["user_id"],
                }))
            except Exception:
                pass

        logger.info(f"🔴 Daemon unregistered: {daemon_id}")

    async def heartbeat(self, daemon_id: str):
        """Update the heartbeat timestamp for a daemon."""
        if daemon_id in self._local:
            self._local[daemon_id]["last_heartbeat"] = time.time()

        r = await get_redis()
        if r:
            try:
                await r.hset(f"daemon:{daemon_id}", "last_heartbeat", str(time.time()))
            except Exception:
                pass

    def get_websocket(self, daemon_id: str) -> Optional[WebSocket]:
        """Get the WebSocket for a connected daemon."""
        return self._websockets.get(daemon_id)

    async def get_user_daemons(self, user_id: str) -> list[dict]:
        """Get all daemons for a user."""
        # Check Redis first
        r = await get_redis()
        if r:
            try:
                daemon_ids = await r.smembers(f"user:{user_id}:daemons")
                result = []
                for did in daemon_ids:
                    data = await r.hgetall(f"daemon:{did}")
                    if data:
                        data["daemon_id"] = did
                        data["ws_connected"] = did in self._websockets
                        result.append(data)
                return result
            except Exception:
                pass

        # Fallback to local
        return [
            {**v, "ws_connected": k in self._websockets}
            for k, v in self._local.items()
            if v.get("user_id") == user_id
        ]

    def is_online(self, daemon_id: str) -> bool:
        """Check if a daemon has an active WebSocket connection."""
        if daemon_id not in self._websockets:
            return False
        entry = self._local.get(daemon_id, {})
        last_hb = entry.get("last_heartbeat", 0)
        return (time.time() - last_hb) < DAEMON_HEARTBEAT_TIMEOUT


# ── Singletons ─────────────────────────────────────────────────────────────────

daemon_registry = DaemonRegistry()
workspace_manager = CloudWorkspaceManager()

# ── Lifespan ───────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown hooks."""
    logger.info("═" * 56)
    logger.info("  Saathi Cloud Hub — Starting Up")
    logger.info(f"  Redis:  {REDIS_URL}")
    logger.info(f"  Port:   {HUB_PORT}")
    logger.info("═" * 56)

    # Warm up Redis
    await get_redis()

    yield

    # Shutdown
    global redis_pool
    if redis_pool:
        await redis_pool.close()
        redis_pool = None
    logger.info("Saathi Cloud Hub — Shut down cleanly.")


# ── FastAPI App ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Saathi Cloud Hub",
    version="3.0.0",
    description="Multi-tenant Cloud-to-Edge SaaS message broker for Saathi AI",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Dependency: Extract Current User from JWT ─────────────────────────────────

async def get_current_user(request: Request) -> dict:
    """Extract and validate the JWT from the Authorization header."""
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth[7:].strip()
    payload = validate_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return payload


# ── Request/Response Models ────────────────────────────────────────────────────

class CommandRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    daemon_id: Optional[str] = None
    force_cloud: bool = False


class CommandResponse(BaseModel):
    intent: dict
    payload: Optional[dict] = None
    response: str
    routed_to: str  # "daemon" | "cloud_workspace" | "llm_only"
    daemon_status: str = "unknown"


class DaemonAuthRequest(BaseModel):
    daemon_id: str
    psk: str  # Pre-shared key


# ══════════════════════════════════════════════════════════════════════════════
#  REST API ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    r = await get_redis()
    return {
        "status": "healthy",
        "version": "3.0.0",
        "redis": "connected" if r else "unavailable",
        "active_daemons": len(daemon_registry._local),
        "llm_router": llm_router.stats,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── Auth Endpoints ─────────────────────────────────────────────────────────────

@app.post("/api/auth/register", response_model=TokenPair)
async def api_register(req: UserRegister):
    """Register a new user and return JWT tokens."""
    try:
        user = register_user(req.email, req.password, req.full_name)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return create_token_pair(user["id"], user["email"])


@app.post("/api/auth/login", response_model=TokenPair)
async def api_login(req: UserLogin):
    """Authenticate and return JWT tokens."""
    user = authenticate_user(req.email, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return create_token_pair(user["id"], user["email"])


@app.post("/api/auth/daemon-token")
async def api_daemon_token(req: DaemonAuthRequest):
    """
    Issue a long-lived JWT token for a daemon using a pre-shared key.
    The daemon uses this token to authenticate its WebSocket connection.
    """
    if not validate_daemon_psk(req.psk):
        raise HTTPException(status_code=403, detail="Invalid pre-shared key")
    token = create_daemon_token(req.daemon_id)
    return {"token": token, "daemon_id": req.daemon_id}


# ── Command Endpoint ──────────────────────────────────────────────────────────

@app.post("/api/command", response_model=CommandResponse)
async def send_command(req: CommandRequest, user: dict = Depends(get_current_user)):
    """
    Process a natural language command:
    1. Classify intent via LLM Router
    2. Generate execution payload
    3. Route to daemon (if online) or cloud workspace (if offline)
    """
    user_id = user["sub"]

    # Step 1: Classify & generate
    result = await llm_router.classify_and_route(req.message)
    intent = result["intent"]
    payload = result["payload"]
    response_text = result["response"]["text"]

    # Step 2: Determine routing target
    routed_to = "llm_only"
    daemon_status = "no_daemon"

    if payload and not req.force_cloud:
        # Try to find an online daemon for this user
        daemons = await daemon_registry.get_user_daemons(user_id)
        target_daemon = None

        if req.daemon_id:
            # Specific daemon requested
            target_daemon = next(
                (d for d in daemons if d["daemon_id"] == req.daemon_id), None
            )
        else:
            # Pick first online daemon
            target_daemon = next(
                (d for d in daemons if daemon_registry.is_online(d["daemon_id"])), None
            )

        if target_daemon and daemon_registry.is_online(target_daemon["daemon_id"]):
            # Route to daemon via WebSocket
            ws = daemon_registry.get_websocket(target_daemon["daemon_id"])
            if ws:
                try:
                    await ws.send_json({
                        "type": "execute",
                        "payload": payload,
                        "request_id": str(uuid.uuid4()),
                        "user_id": user_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                    routed_to = "daemon"
                    daemon_status = "online"
                except Exception as exc:
                    logger.error(f"Failed to send to daemon: {exc}")
                    daemon_status = "send_failed"
        else:
            daemon_status = "offline"

        # Step 3: Fallback to cloud workspace if daemon is offline
        if routed_to != "daemon" and payload.get("action") in (
            "run_script", "shell_exec"
        ):
            routed_to = "cloud_workspace"
            daemon_status = "offline_fallback"
            # Trigger cloud workspace (async, non-blocking)
            asyncio.create_task(
                _execute_in_cloud_workspace(user_id, payload, req.message)
            )

    return CommandResponse(
        intent=intent,
        payload=payload,
        response=response_text,
        routed_to=routed_to,
        daemon_status=daemon_status,
    )


async def _execute_in_cloud_workspace(
    user_id: str, payload: dict, original_message: str
):
    """Execute a command in an ephemeral cloud workspace when daemon is offline."""
    try:
        result = await workspace_manager.execute(
            user_id=user_id,
            action=payload.get("action", "shell_exec"),
            args=payload.get("args", {}),
        )
        logger.info(f"Cloud workspace result for {user_id}: {result.get('status')}")

        # Publish result via Redis for the user to poll
        r = await get_redis()
        if r:
            await r.publish(f"user:{user_id}:results", json.dumps({
                "source": "cloud_workspace",
                "result": result,
                "original_message": original_message,
            }))
    except Exception as exc:
        logger.error(f"Cloud workspace execution failed: {exc}")


# ── Daemon Registry Endpoints ─────────────────────────────────────────────────

@app.get("/api/daemons")
async def list_daemons(user: dict = Depends(get_current_user)):
    """List all daemons registered to the current user."""
    daemons = await daemon_registry.get_user_daemons(user["sub"])
    return {
        "daemons": [
            {
                "daemon_id": d.get("daemon_id"),
                "status": "online" if daemon_registry.is_online(d.get("daemon_id", "")) else "offline",
                "connected_at": d.get("connected_at"),
                "last_heartbeat": d.get("last_heartbeat"),
                "ws_connected": d.get("ws_connected", False),
            }
            for d in daemons
        ]
    }


# ── LLM Router Status ─────────────────────────────────────────────────────────

@app.get("/api/llm/status")
async def llm_status():
    """Get the current LLM router stats and available models."""
    return llm_router.stats


@app.post("/api/llm/classify")
async def llm_classify(req: CommandRequest):
    """Classify the intent of a message (for testing/debugging)."""
    intent = await classify_intent(req.message)
    return intent


# ══════════════════════════════════════════════════════════════════════════════
#  WEBSOCKET ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@app.websocket("/ws/daemon")
async def daemon_websocket(
    ws: WebSocket,
    token: str = Query(default=""),
):
    """
    WebSocket endpoint for Edge Daemon connections.

    Authentication: The daemon passes its JWT token as a query parameter.
    Protocol:
      1. Daemon connects with JWT
      2. Hub validates token
      3. Bidirectional message flow:
         - Hub → Daemon: execution payloads
         - Daemon → Hub: stdout/stderr streams, heartbeats
    """
    # Validate the daemon token
    payload = validate_daemon_token(token)
    if not payload:
        await ws.close(code=4001, reason="Invalid or expired daemon token")
        return

    daemon_id = payload["sub"]
    # Derive user_id: for daemon tokens, we store user_id in metadata
    # For now, use daemon_id prefix convention: "daemon-{user_id}-{machine}"
    parts = daemon_id.split("-", 2)
    user_id = parts[1] if len(parts) > 1 else daemon_id

    await ws.accept()
    logger.info(f"📡 Daemon WebSocket accepted: {daemon_id}")

    # Register the daemon
    await daemon_registry.register(daemon_id, user_id, ws)

    # Send welcome
    await ws.send_json({
        "type": "connected",
        "daemon_id": daemon_id,
        "hub_version": "3.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type", "unknown")

            if msg_type == "heartbeat":
                await daemon_registry.heartbeat(daemon_id)
                await ws.send_json({"type": "heartbeat_ack", "ts": time.time()})

            elif msg_type == "result":
                # Daemon is sending back execution results
                request_id = data.get("request_id", "")
                result = data.get("result", {})
                logger.info(
                    f"📥 Result from {daemon_id} [req:{request_id}]: "
                    f"status={result.get('status', 'unknown')}"
                )

                # Forward result to user via Redis
                r = await get_redis()
                if r:
                    await r.publish(f"user:{user_id}:results", json.dumps({
                        "source": "daemon",
                        "daemon_id": daemon_id,
                        "request_id": request_id,
                        "result": result,
                    }))

            elif msg_type == "stream":
                # Real-time stdout/stderr streaming
                r = await get_redis()
                if r:
                    await r.publish(f"user:{user_id}:stream", json.dumps({
                        "daemon_id": daemon_id,
                        "line": data.get("line", ""),
                        "stream_type": data.get("stream_type", "stdout"),
                        "request_id": data.get("request_id", ""),
                    }))

            elif msg_type == "error":
                logger.error(f"Daemon {daemon_id} error: {data.get('error', 'unknown')}")

            else:
                logger.warning(f"Unknown message type from daemon: {msg_type}")

    except WebSocketDisconnect:
        logger.info(f"Daemon {daemon_id} disconnected normally")
    except Exception as exc:
        logger.error(f"Daemon {daemon_id} connection error: {exc}")
    finally:
        await daemon_registry.unregister(daemon_id)


@app.websocket("/ws/user")
async def user_stream_websocket(
    ws: WebSocket,
    token: str = Query(default=""),
):
    """
    WebSocket for users to receive real-time execution streams
    from their daemons or cloud workspaces.
    """
    payload = validate_access_token(token)
    if not payload:
        await ws.close(code=4001, reason="Invalid token")
        return

    user_id = payload["sub"]
    await ws.accept()

    logger.info(f"👤 User stream connected: {user_id}")

    # Subscribe to Redis channels for this user
    r = await get_redis()
    if r:
        pubsub = r.pubsub()
        await pubsub.subscribe(
            f"user:{user_id}:results",
            f"user:{user_id}:stream",
        )

        try:
            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message and message["type"] == "message":
                    await ws.send_text(message["data"])

                # Also check for WebSocket messages from client (e.g., ping)
                try:
                    client_msg = await asyncio.wait_for(
                        ws.receive_text(), timeout=0.1
                    )
                    if client_msg == "ping":
                        await ws.send_text(json.dumps({"type": "pong"}))
                except asyncio.TimeoutError:
                    pass
        except WebSocketDisconnect:
            pass
        finally:
            await pubsub.unsubscribe()
            await pubsub.close()
    else:
        # No Redis — just keep connection alive for direct pushes
        try:
            while True:
                data = await ws.receive_text()
                if data == "ping":
                    await ws.send_text(json.dumps({"type": "pong"}))
        except WebSocketDisconnect:
            pass

    logger.info(f"👤 User stream disconnected: {user_id}")


# ══════════════════════════════════════════════════════════════════════════════
#  EXCEPTION HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )


# ── Entry Point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "hub.main:app",
        host=HUB_HOST,
        port=HUB_PORT,
        reload=True,
        log_level="info",
    )
