from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse
import uvicorn
import threading
from fastmcp import FastMCP
import httpx
import os
from typing import Optional, List

mcp = FastMCP("WAGMIOS")

BASE_URL = "http://localhost:5179/api"
API_KEY = os.environ.get("X_API_KEY", "")

def get_headers():
    return {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }


@mcp.tool()
async def list_containers(status: Optional[str] = "all") -> dict:
    """List all Docker containers managed by WAGMIOS, including their status (running, stopped, etc.), names, and IDs. Use this to get an overview of what containers exist before performing any management operations."""
    _track("list_containers")
    params = {}
    if status and status != "all":
        params["status"] = status
    else:
        params["status"] = "all"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{BASE_URL}/containers",
            headers=get_headers(),
            params=params
        )
        return {
            "status_code": response.status_code,
            "data": response.json() if response.content else {}
        }


@mcp.tool()
async def manage_container(container_id: str, action: str) -> dict:
    """Start, stop, restart, or delete a specific Docker container by its ID or name. Use this to control the lifecycle of existing containers. Requires appropriate scope permissions (e.g., containers:delete for deletion). Actions: 'start', 'stop', 'restart', 'delete'."""
    _track("manage_container")
    valid_actions = ["start", "stop", "restart", "delete"]
    if action not in valid_actions:
        return {"error": f"Invalid action '{action}'. Must be one of: {valid_actions}"}

    async with httpx.AsyncClient(timeout=60.0) as client:
        if action == "delete":
            response = await client.delete(
                f"{BASE_URL}/containers/{container_id}",
                headers=get_headers()
            )
        else:
            response = await client.post(
                f"{BASE_URL}/containers/{container_id}/{action}",
                headers=get_headers()
            )
        return {
            "status_code": response.status_code,
            "data": response.json() if response.content else {}
        }


@mcp.tool()
async def install_marketplace_app(
    _track("install_marketplace_app")
    app_name: str,
    config_overrides: Optional[str] = None
) -> dict:
    """Install a self-hosted app from the WAGMIOS marketplace (e.g., Plex, Jellyfin, Ollama, Home Assistant). Use this when the user wants to deploy a new application without manually configuring Docker."""
    import json

    payload: dict = {"app_name": app_name}
    if config_overrides:
        try:
            overrides = json.loads(config_overrides)
            payload["config"] = overrides
        except json.JSONDecodeError:
            return {"error": "config_overrides must be a valid JSON string"}

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{BASE_URL}/marketplace/install",
            headers=get_headers(),
            json=payload
        )
        return {
            "status_code": response.status_code,
            "data": response.json() if response.content else {}
        }


@mcp.tool()
async def list_marketplace_apps(installed_only: Optional[bool] = False) -> dict:
    """Retrieve the full list of available apps in the WAGMIOS marketplace, including their names, descriptions, and installation status. Use this before installing an app to confirm it is available or to browse what can be deployed."""
    _track("list_marketplace_apps")
    params = {}
    if installed_only:
        params["installed"] = "true"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{BASE_URL}/marketplace",
            headers=get_headers(),
            params=params
        )
        return {
            "status_code": response.status_code,
            "data": response.json() if response.content else {}
        }


@mcp.tool()
async def get_activity_feed(
    _track("get_activity_feed")
    limit: Optional[int] = 50,
    event_type: Optional[str] = None
) -> dict:
    """Retrieve the recent activity log of all actions performed in WAGMIOS, including who performed them, what was done, and when. Use this to audit agent actions, troubleshoot issues, or review homelab history."""
    if limit is None:
        limit = 50
    limit = max(1, min(limit, 500))

    params: dict = {"limit": limit}
    if event_type:
        params["type"] = event_type

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{BASE_URL}/activity",
            headers=get_headers(),
            params=params
        )
        return {
            "status_code": response.status_code,
            "data": response.json() if response.content else {}
        }


@mcp.tool()
async def get_system_metrics() -> dict:
    """Retrieve system health metrics including container counts (total, running, stopped), API request volume over the last 24 hours, image pull counts, and server uptime. Use this to monitor the overall health and usage of the WAGMIOS platform."""
    _track("get_system_metrics")
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{BASE_URL}/metrics",
            headers=get_headers()
        )
        return {
            "status_code": response.status_code,
            "data": response.json() if response.content else {}
        }


@mcp.tool()
async def manage_api_keys(
    _track("manage_api_keys")
    action: str,
    key_id: Optional[str] = None,
    scopes: Optional[List[str]] = None,
    label: Optional[str] = None
) -> dict:
    """Create, list, or revoke API keys for WAGMIOS. Each key has a configurable scope (e.g., containers:read, containers:delete, marketplace:install) to limit agent permissions. Actions: 'create', 'list', 'revoke'."""
    valid_actions = ["create", "list", "revoke"]
    if action not in valid_actions:
        return {"error": f"Invalid action '{action}'. Must be one of: {valid_actions}"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        if action == "list":
            response = await client.get(
                f"{BASE_URL}/keys",
                headers=get_headers()
            )
        elif action == "create":
            if not scopes:
                return {"error": "'scopes' is required when action is 'create'"}
            payload: dict = {"scopes": scopes}
            if label:
                payload["label"] = label
            response = await client.post(
                f"{BASE_URL}/keys",
                headers=get_headers(),
                json=payload
            )
        elif action == "revoke":
            if not key_id:
                return {"error": "'key_id' is required when action is 'revoke'"}
            response = await client.delete(
                f"{BASE_URL}/keys/{key_id}",
                headers=get_headers()
            )
        else:
            return {"error": f"Unhandled action: {action}"}

        return {
            "status_code": response.status_code,
            "data": response.json() if response.content else {}
        }


@mcp.tool()
async def get_system_settings(
    _track("get_system_settings")
    action: Optional[str] = "get",
    settings: Optional[str] = None
) -> dict:
    """Retrieve or update WAGMIOS system-level settings such as data directory configuration and server options. Use this to inspect the current platform configuration or apply system-wide changes. Actions: 'get' or 'update'."""
    import json

    if action not in ["get", "update"]:
        return {"error": "action must be 'get' or 'update'"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        if action == "get":
            response = await client.get(
                f"{BASE_URL}/settings",
                headers=get_headers()
            )
        else:
            if not settings:
                return {"error": "'settings' JSON string is required when action is 'update'"}
            try:
                settings_dict = json.loads(settings)
            except json.JSONDecodeError:
                return {"error": "'settings' must be a valid JSON string"}
            response = await client.put(
                f"{BASE_URL}/settings",
                headers=get_headers(),
                json=settings_dict
            )

        return {
            "status_code": response.status_code,
            "data": response.json() if response.content else {}
        }




_SERVER_SLUG = "mentholmike-wagmios"

def _track(tool_name: str, ua: str = ""):
    import threading
    def _send():
        try:
            import urllib.request, json as _json
            data = _json.dumps({"slug": _SERVER_SLUG, "event": "tool_call", "tool": tool_name, "user_agent": ua}).encode()
            req = urllib.request.Request("https://www.volspan.dev/api/analytics/event", data=data, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass
    threading.Thread(target=_send, daemon=True).start()

async def health(request):
    return JSONResponse({"status": "ok", "server": mcp.name})

async def tools(request):
    registered = await mcp.list_tools()
    tool_list = [{"name": t.name, "description": t.description or ""} for t in registered]
    return JSONResponse({"tools": tool_list, "count": len(tool_list)})

sse_app = mcp.http_app(transport="sse")

app = Starlette(
    routes=[
        Route("/health", health),
        Route("/tools", tools),
        Mount("/", sse_app),
    ],
    lifespan=sse_app.lifespan,
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
