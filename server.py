"""
VFX Flow Server Routes
======================
API endpoints for Flow/ShotGrid integration.
"""

import os
import json
from aiohttp import web
from server import PromptServer

# Import from nodes
try:
    import shotgun_api3
    HAS_SHOTGUN = True
except ImportError:
    HAS_SHOTGUN = False

# Session cache
_login_sessions = {}

routes = PromptServer.instance.routes


@routes.post("/vfx-flow/login")
async def flow_login(request):
    """Test login and return status."""
    try:
        data = await request.json()
        
        site_url = data.get("site_url", "")
        auth_method = data.get("auth_method", "user")
        login = data.get("login", "")
        password = data.get("password", "")
        script_name = data.get("script_name", "")
        api_key = data.get("api_key", "")
        
        if not HAS_SHOTGUN:
            return web.json_response({
                "success": False,
                "error": "shotgun_api3 not installed",
                "message": "pip install shotgun_api3"
            })
        
        if not site_url:
            return web.json_response({
                "success": False,
                "error": "No site URL provided"
            })
        
        try:
            if auth_method == "user":
                if not login or not password:
                    return web.json_response({
                        "success": False,
                        "error": "Login and password required"
                    })
                sg = shotgun_api3.Shotgun(site_url, login=login, password=password)
                cache_key = f"{site_url}:user:{login}"
            else:
                if not api_key:
                    return web.json_response({
                        "success": False,
                        "error": "API key required"
                    })
                sg = shotgun_api3.Shotgun(site_url, script_name=script_name, api_key=api_key)
                cache_key = f"{site_url}:script:{script_name}"
            
            # Test connection by fetching user info
            if auth_method == "user":
                user = sg.find_one("HumanUser", [["login", "is", login]], ["name", "email"])
                user_name = user.get("name", login) if user else login
            else:
                user_name = script_name
            
            # Cache the session
            _login_sessions[cache_key] = {
                "sg": sg,
                "user_name": user_name,
                "site_url": site_url
            }
            
            return web.json_response({
                "success": True,
                "user_name": user_name,
                "site_url": site_url,
                "message": f"Logged in as {user_name}"
            })
            
        except Exception as e:
            error_msg = str(e)
            if "authentication" in error_msg.lower() or "401" in error_msg:
                error_msg = "Invalid credentials"
            return web.json_response({
                "success": False,
                "error": error_msg
            })
            
    except Exception as e:
        return web.json_response({
            "success": False,
            "error": str(e)
        })


@routes.get("/vfx-flow/status")
async def flow_status(request):
    """Check if any session is active."""
    if _login_sessions:
        first_session = list(_login_sessions.values())[0]
        return web.json_response({
            "logged_in": True,
            "user_name": first_session.get("user_name", "Unknown"),
            "site_url": first_session.get("site_url", "")
        })
    return web.json_response({
        "logged_in": False
    })


@routes.post("/vfx-flow/logout")
async def flow_logout(request):
    """Clear all sessions."""
    _login_sessions.clear()
    return web.json_response({"success": True})


print("[VFX Flow] Server routes registered")
