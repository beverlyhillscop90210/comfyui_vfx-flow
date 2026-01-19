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

# Session cache - stores active ShotGrid connections
_login_sessions = {}

routes = PromptServer.instance.routes


def get_active_session():
    """Get the first active session or None."""
    if _login_sessions:
        return list(_login_sessions.values())[0]
    return None


# =============================================================================
# LOGIN / LOGOUT
# =============================================================================

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
    session = get_active_session()
    if session:
        return web.json_response({
            "logged_in": True,
            "user_name": session.get("user_name", "Unknown"),
            "site_url": session.get("site_url", "")
        })
    return web.json_response({"logged_in": False})


@routes.post("/vfx-flow/logout")
async def flow_logout(request):
    """Clear all sessions."""
    _login_sessions.clear()
    return web.json_response({"success": True})


# =============================================================================
# PROJECTS
# =============================================================================

@routes.get("/vfx-flow/projects")
async def get_projects(request):
    """Get all active projects."""
    session = get_active_session()
    if not session:
        return web.json_response({"success": False, "error": "Not logged in", "projects": []})
    
    try:
        sg = session["sg"]
        projects = sg.find(
            "Project",
            [["sg_status", "is", "Active"]],
            ["name", "id", "sg_status", "image"],
            order=[{"field_name": "name", "direction": "asc"}]
        )
        
        # Format for dropdown
        project_list = [{"id": p["id"], "name": p["name"]} for p in projects]
        
        return web.json_response({
            "success": True,
            "projects": project_list
        })
    except Exception as e:
        return web.json_response({
            "success": False,
            "error": str(e),
            "projects": []
        })


# =============================================================================
# SEQUENCES
# =============================================================================

@routes.get("/vfx-flow/sequences")
async def get_sequences(request):
    """Get sequences for a project."""
    session = get_active_session()
    if not session:
        return web.json_response({"success": False, "error": "Not logged in", "sequences": []})
    
    project_id = request.query.get("project_id")
    if not project_id:
        return web.json_response({"success": False, "error": "project_id required", "sequences": []})
    
    try:
        sg = session["sg"]
        sequences = sg.find(
            "Sequence",
            [["project", "is", {"type": "Project", "id": int(project_id)}]],
            ["code", "id", "sg_status_list"],
            order=[{"field_name": "code", "direction": "asc"}]
        )
        
        seq_list = [{"id": s["id"], "code": s["code"], "status": s.get("sg_status_list", "")} for s in sequences]
        
        return web.json_response({
            "success": True,
            "sequences": seq_list
        })
    except Exception as e:
        return web.json_response({
            "success": False,
            "error": str(e),
            "sequences": []
        })


# =============================================================================
# SHOTS
# =============================================================================

@routes.get("/vfx-flow/shots")
async def get_shots(request):
    """Get shots for a project or sequence."""
    session = get_active_session()
    if not session:
        return web.json_response({"success": False, "error": "Not logged in", "shots": []})
    
    project_id = request.query.get("project_id")
    sequence_id = request.query.get("sequence_id")
    
    if not project_id:
        return web.json_response({"success": False, "error": "project_id required", "shots": []})
    
    try:
        sg = session["sg"]
        
        filters = [["project", "is", {"type": "Project", "id": int(project_id)}]]
        if sequence_id:
            filters.append(["sg_sequence", "is", {"type": "Sequence", "id": int(sequence_id)}])
        
        shots = sg.find(
            "Shot",
            filters,
            ["code", "id", "sg_status_list", "sg_sequence", "image", "sg_cut_in", "sg_cut_out"],
            order=[{"field_name": "code", "direction": "asc"}]
        )
        
        shot_list = []
        for s in shots:
            seq = s.get("sg_sequence")
            shot_list.append({
                "id": s["id"],
                "code": s["code"],
                "status": s.get("sg_status_list", ""),
                "sequence": seq.get("name", "") if seq else "",
                "sequence_id": seq.get("id") if seq else None,
                "cut_in": s.get("sg_cut_in"),
                "cut_out": s.get("sg_cut_out"),
                "thumbnail": s.get("image")
            })
        
        return web.json_response({
            "success": True,
            "shots": shot_list
        })
    except Exception as e:
        return web.json_response({
            "success": False,
            "error": str(e),
            "shots": []
        })


# =============================================================================
# TASKS
# =============================================================================

@routes.get("/vfx-flow/tasks")
async def get_tasks(request):
    """Get tasks for a shot."""
    session = get_active_session()
    if not session:
        return web.json_response({"success": False, "error": "Not logged in", "tasks": []})
    
    shot_id = request.query.get("shot_id")
    if not shot_id:
        return web.json_response({"success": False, "error": "shot_id required", "tasks": []})
    
    try:
        sg = session["sg"]
        tasks = sg.find(
            "Task",
            [["entity", "is", {"type": "Shot", "id": int(shot_id)}]],
            ["content", "id", "sg_status_list", "task_assignees", "step"],
            order=[{"field_name": "content", "direction": "asc"}]
        )
        
        task_list = []
        for t in tasks:
            assignees = t.get("task_assignees", [])
            step = t.get("step")
            task_list.append({
                "id": t["id"],
                "name": t["content"],
                "status": t.get("sg_status_list", ""),
                "step": step.get("name", "") if step else "",
                "assignees": [a.get("name", "") for a in assignees] if assignees else []
            })
        
        return web.json_response({
            "success": True,
            "tasks": task_list
        })
    except Exception as e:
        return web.json_response({
            "success": False,
            "error": str(e),
            "tasks": []
        })


# =============================================================================
# VERSIONS (for loading latest)
# =============================================================================

@routes.get("/vfx-flow/versions")
async def get_versions(request):
    """Get versions for a shot."""
    session = get_active_session()
    if not session:
        return web.json_response({"success": False, "error": "Not logged in", "versions": []})
    
    shot_id = request.query.get("shot_id")
    if not shot_id:
        return web.json_response({"success": False, "error": "shot_id required", "versions": []})
    
    try:
        sg = session["sg"]
        versions = sg.find(
            "Version",
            [["entity", "is", {"type": "Shot", "id": int(shot_id)}]],
            ["code", "id", "sg_status_list", "sg_path_to_frames", "sg_path_to_movie", 
             "version_number", "created_at", "user", "image"],
            order=[{"field_name": "version_number", "direction": "desc"}],
            limit=20
        )
        
        version_list = []
        for v in versions:
            user = v.get("user")
            version_list.append({
                "id": v["id"],
                "code": v["code"],
                "version_number": v.get("version_number", 0),
                "status": v.get("sg_status_list", ""),
                "path_to_frames": v.get("sg_path_to_frames", ""),
                "path_to_movie": v.get("sg_path_to_movie", ""),
                "created_at": str(v.get("created_at", "")),
                "user": user.get("name", "") if user else "",
                "thumbnail": v.get("image")
            })
        
        return web.json_response({
            "success": True,
            "versions": version_list
        })
    except Exception as e:
        return web.json_response({
            "success": False,
            "error": str(e),
            "versions": []
        })


# =============================================================================
# SELECT (for setting active project/shot/task in session)
# =============================================================================

@routes.post("/vfx-flow/select")
async def select_entity(request):
    """Select a project, shot, or task and store in session."""
    session = get_active_session()
    if not session:
        return web.json_response({"success": False, "error": "Not logged in"})
    
    try:
        data = await request.json()
        entity_type = data.get("type")  # "project", "shot", "task"
        entity_id = data.get("id")
        
        if not entity_type or not entity_id:
            return web.json_response({"success": False, "error": "type and id required"})
        
        # Store selection in session
        session[f"selected_{entity_type}"] = entity_id
        
        # If selecting a shot, update its status to "In Progress"
        if entity_type == "shot" and data.get("set_in_progress", True):
            try:
                sg = session["sg"]
                sg.update("Shot", int(entity_id), {"sg_status_list": "ip"})
            except:
                pass  # Non-critical
        
        return web.json_response({
            "success": True,
            "selected": {entity_type: entity_id}
        })
    except Exception as e:
        return web.json_response({
            "success": False,
            "error": str(e)
        })


print("[VFX Flow] Server routes registered")
