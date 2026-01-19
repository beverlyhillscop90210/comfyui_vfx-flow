"""
VFX Flow - ShotGrid/Flow Production Pipeline Integration for ComfyUI
=====================================================================

Nodes for connecting ComfyUI to Autodesk Flow (formerly ShotGrid).
Browse projects, shots, tasks - with automatic status updates and publishing.
"""

import os
import json
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path

# Load .env file if it exists (for credentials)
def _load_env_file():
    env_paths = [
        Path(__file__).parent / ".env",
        Path.home() / ".comfyui_vfx_flow.env",
    ]
    for env_path in env_paths:
        if env_path.exists():
            try:
                with open(env_path) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, value = line.split("=", 1)
                            os.environ.setdefault(key.strip(), value.strip())
                print(f"[VFX Flow] Loaded credentials from {env_path}")
                return
            except Exception as e:
                print(f"[VFX Flow] Failed to load {env_path}: {e}")

_load_env_file()

# Try to import shotgun_api3
try:
    import shotgun_api3
    HAS_SHOTGUN = True
    print("[VFX Flow] shotgun_api3 loaded successfully")
except ImportError:
    HAS_SHOTGUN = False
    print("[VFX Flow] shotgun_api3 not installed - install with: pip install shotgun_api3")


# =============================================================================
# FLOW PIPE DATA TYPE
# =============================================================================

# This carries all context through the workflow
# FLOW_CONTEXT contains: session, project, shot, task, user, version info, filename template

_flow_sessions = {}  # Cache for sessions


# =============================================================================
# FLOW LOGIN NODE
# =============================================================================

class FlowLogin:
    """
    Connect to Autodesk Flow (ShotGrid).
    Supports both Script-based (API key) and User-based (login/password) authentication.
    Credentials can be provided directly or via environment variables.
    """
    
    CATEGORY = "VFX Flow"
    FUNCTION = "login"
    RETURN_TYPES = ("FLOW_SESSION", "STRING",)
    RETURN_NAMES = ("session", "status",)
    OUTPUT_NODE = True
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "site_url": ("STRING", {"default": os.environ.get("FLOW_SITE_URL", "https://your-studio.shotgrid.autodesk.com")}),
                "auth_method": (["user", "script"], {"default": "user"}),
            },
            "optional": {
                # Script-based auth
                "script_name": ("STRING", {"default": os.environ.get("FLOW_SCRIPT_NAME", "comfyui_vfx_flow")}),
                "api_key": ("STRING", {"default": os.environ.get("FLOW_API_KEY", "")}),
                # User-based auth
                "login": ("STRING", {"default": os.environ.get("FLOW_LOGIN", "")}),
                "password": ("STRING", {"default": os.environ.get("FLOW_PASSWORD", "")}),
            },
        }
    
    def login(self, site_url: str, auth_method: str, 
              script_name: str = "", api_key: str = "",
              login: str = "", password: str = ""):
        if not HAS_SHOTGUN:
            return (None, "ERROR: shotgun_api3 not installed\npip install shotgun_api3")
        
        # Determine auth type
        if auth_method == "user":
            if not login or not password:
                return (None, "ERROR: login and password required for user auth")
            cache_key = f"{site_url}:user:{login}"
            auth_info = f"User: {login}"
        else:
            if not api_key:
                return (None, "ERROR: No API key provided\nSet FLOW_API_KEY env var or enter directly")
            cache_key = f"{site_url}:script:{script_name}"
            auth_info = f"Script: {script_name}"
        
        # Check cache
        if cache_key in _flow_sessions:
            sg = _flow_sessions[cache_key]
            try:
                # Test connection
                sg.find_one("Project", [], ["name"])
                return (sg, f"✓ Connected (cached)\n{site_url}\n{auth_info}")
            except:
                del _flow_sessions[cache_key]
        
        try:
            if auth_method == "user":
                sg = shotgun_api3.Shotgun(
                    site_url,
                    login=login,
                    password=password
                )
            else:
                sg = shotgun_api3.Shotgun(
                    site_url,
                    script_name=script_name,
                    api_key=api_key
                )
            
            # Test connection
            sg.find_one("Project", [], ["name"])
            _flow_sessions[cache_key] = sg
            
            status = f"✓ Connected\n{site_url}\n{auth_info}"
            print(f"[VFX Flow] Connected to {site_url} via {auth_method}")
            return (sg, status)
            
        except Exception as e:
            return (None, f"ERROR: {str(e)}")


# =============================================================================
# PROJECT BROWSER NODE
# =============================================================================

class ProjectBrowser:
    """
    Browse and select a project from Flow.
    Shows only active projects. Type part of the project name to filter.
    """
    
    CATEGORY = "VFX Flow"
    FUNCTION = "browse"
    RETURN_TYPES = ("FLOW_CONTEXT", "STRING",)
    RETURN_NAMES = ("flow", "info",)
    OUTPUT_NODE = True
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "session": ("FLOW_SESSION",),
            },
            "optional": {
                "filter": ("STRING", {"default": "", "placeholder": "Project name filter..."}),
            },
        }
    
    def browse(self, session, filter: str = ""):
        if session is None:
            return (None, "❌ No Flow session - connect Flow Login first")
        
        try:
            # Find projects
            filters = [["sg_status", "is", "Active"]]
            if filter:
                filters.append(["name", "contains", filter])
            
            projects = session.find(
                "Project",
                filters,
                ["name", "sg_status", "id"]
            )
            
            if not projects:
                return (None, "❌ No projects found")
            
            # Use first match
            project = projects[0]
            
            # Build context (internal, not shown to user as "flow")
            context = {
                "session": session,
                "project": {
                    "id": project["id"],
                    "name": project["name"],
                },
                "shot": None,
                "task": None,
                "user": None,
                "version_number": 1,
                "resolved_filename": None,
            }
            
            # Build info - show all available projects
            info_lines = [f"✓ Selected: {project['name']}", ""]
            if len(projects) > 1:
                info_lines.append(f"Available projects ({len(projects)}):")
                for p in projects[:10]:
                    marker = "→" if p["id"] == project["id"] else " "
                    info_lines.append(f"  {marker} {p['name']}")
                if len(projects) > 10:
                    info_lines.append(f"  ... and {len(projects)-10} more")
            
            info = "\n".join(info_lines)
            print(f"[VFX Flow] Selected project: {project['name']}")
            
            return (context, info)
            
        except Exception as e:
            return (None, f"❌ Error: {str(e)}")


# =============================================================================
# SHOT BROWSER NODE
# =============================================================================

class ShotBrowser:
    """
    Browse and select a shot from the project.
    Automatically sets shot status to "In Progress" when selected.
    Outputs folder_path for direct connection to VFX Bridge EXR Loader.
    """
    
    CATEGORY = "VFX Flow"
    FUNCTION = "browse"
    RETURN_TYPES = ("FLOW_CONTEXT", "STRING", "STRING", "STRING",)
    RETURN_NAMES = ("flow", "folder_path", "latest_file", "info",)
    OUTPUT_NODE = True
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "flow": ("FLOW_CONTEXT",),
                "shot_code": ("STRING", {"default": ""}),
            },
            "optional": {
                "set_in_progress": ("BOOLEAN", {"default": True}),
            },
        }
    
    def browse(self, flow, shot_code: str, set_in_progress: bool = True):
        if flow is None:
            return (None, "", "", "ERROR: No flow data")
        
        session = flow.get("session")
        project = flow.get("project")
        
        if not session or not project:
            return (None, "", "", "ERROR: Invalid flow data")
        
        try:
            # Find shots
            filters = [["project", "is", {"type": "Project", "id": project["id"]}]]
            if shot_code:
                filters.append(["code", "contains", shot_code])
            
            shots = session.find(
                "Shot",
                filters,
                ["code", "sg_status_list", "sg_sequence", "id", "sg_cut_in", "sg_cut_out"]
            )
            
            if not shots:
                return (flow, "", "", "No shots found")
            
            shot = shots[0]
            sequence = shot.get("sg_sequence", {})
            seq_name = sequence.get("name", "SEQ") if sequence else "SEQ"
            
            # Set status to In Progress
            if set_in_progress:
                session.update("Shot", shot["id"], {"sg_status_list": "ip"})
                print(f"[VFX Flow] Set shot {shot['code']} to In Progress")
            
            # Find latest version
            versions = session.find(
                "Version",
                [["entity", "is", {"type": "Shot", "id": shot["id"]}]],
                ["code", "sg_path_to_movie", "sg_path_to_frames", "version_number"],
                order=[{"field_name": "version_number", "direction": "desc"}],
                limit=1
            )
            
            latest_file = ""
            folder_path = ""
            version_num = 1
            if versions:
                v = versions[0]
                latest_file = v.get("sg_path_to_frames") or v.get("sg_path_to_movie") or ""
                version_num = (v.get("version_number") or 0) + 1
                # Extract folder from file path for VFX Bridge EXR Loader
                if latest_file:
                    folder_path = os.path.dirname(latest_file)
            
            # Update pipe
            pipe = flow.copy()
            pipe["shot"] = {
                "id": shot["id"],
                "code": shot["code"],
                "sequence": seq_name,
                "cut_in": shot.get("sg_cut_in"),
                "cut_out": shot.get("sg_cut_out"),
            }
            pipe["version_number"] = version_num
            pipe["resolved_filename"] = f"{project['name']}_{seq_name}_{shot['code']}_v{version_num:03d}"
            pipe["folder_path"] = folder_path  # Store for later use
            
            # Build info
            info_lines = [
                f"Shot: {shot['code']}",
                f"Sequence: {seq_name}",
                f"Status: {'In Progress' if set_in_progress else shot.get('sg_status_list', 'N/A')}",
                f"Next Version: v{version_num:03d}",
            ]
            if folder_path:
                info_lines.append(f"Folder: {folder_path}")
            if latest_file:
                info_lines.append(f"Latest: {os.path.basename(latest_file)}")
            
            info = "\n".join(info_lines)
            return (flow, folder_path, latest_file, info)
            
        except Exception as e:
            return (flow, "", "", f"ERROR: {str(e)}")


# =============================================================================
# TASK SELECTOR NODE
# =============================================================================

class TaskSelector:
    """
    Select a task for the shot and assign yourself.
    """
    
    CATEGORY = "VFX Flow"
    FUNCTION = "select"
    RETURN_TYPES = ("FLOW_CONTEXT", "STRING",)
    RETURN_NAMES = ("flow", "info",)
    OUTPUT_NODE = True
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "flow": ("FLOW_CONTEXT",),
                "task_name": ("STRING", {"default": "comp"}),
            },
            "optional": {
                "assign_to_me": ("BOOLEAN", {"default": True}),
            },
        }
    
    def select(self, flow, task_name: str, assign_to_me: bool = True):
        if flow is None:
            return (None, "ERROR: No flow data")
        
        session = flow.get("session")
        shot = flow.get("shot")
        
        if not session or not shot:
            return (flow, "ERROR: Need shot selected first")
        
        try:
            # Find task
            tasks = session.find(
                "Task",
                [
                    ["entity", "is", {"type": "Shot", "id": shot["id"]}],
                    ["content", "contains", task_name],
                ],
                ["content", "task_assignees", "sg_status_list", "id"]
            )
            
            if not tasks:
                return (flow, f"No task '{task_name}' found on shot {shot['code']}")
            
            task = tasks[0]
            
            # Get current user and assign
            user_name = "Unknown"
            user_id = None
            
            if assign_to_me:
                # Try to get current user from script user
                try:
                    # This gets the human user associated with the script
                    me = session.find_one(
                        "HumanUser",
                        [["sg_status_list", "is", "act"]],
                        ["name", "login", "id"]
                    )
                    if me:
                        user_name = me.get("name", me.get("login", "Unknown"))
                        user_id = me["id"]
                        
                        # Assign task
                        session.update("Task", task["id"], {
                            "task_assignees": [{"type": "HumanUser", "id": user_id}],
                            "sg_status_list": "ip"
                        })
                        print(f"[VFX Flow] Assigned {task['content']} to {user_name}")
                except:
                    pass
            
            # Update pipe
            pipe = flow.copy()
            pipe["task"] = {
                "id": task["id"],
                "name": task["content"],
            }
            pipe["user"] = {
                "id": user_id,
                "name": user_name,
            }
            
            # Update resolved filename with task
            project = flow.get("project", {})
            shot_data = flow.get("shot", {})
            pipe["resolved_filename"] = f"{project.get('name', 'proj')}_{shot_data.get('sequence', 'SEQ')}_{shot_data.get('code', 'shot')}_{task['content']}_v{pipe['version_number']:03d}"
            
            info = f"Task: {task['content']}\nAssigned to: {user_name}\nFilename: {pipe['resolved_filename']}"
            return (flow, info)
            
        except Exception as e:
            return (flow, f"ERROR: {str(e)}")


# =============================================================================
# PUBLISH TO FLOW NODE
# =============================================================================

class PublishToFlow:
    """
    Publish a version to Flow.
    Only publishes when the publish button is clicked (auto_publish=False).
    """
    
    CATEGORY = "VFX Flow"
    FUNCTION = "publish"
    RETURN_TYPES = ("STRING", "STRING",)
    RETURN_NAMES = ("version_id", "info",)
    OUTPUT_NODE = True
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "flow": ("FLOW_CONTEXT",),
                "file_path": ("STRING", {"default": ""}),
                "description": ("STRING", {"default": "", "multiline": True}),
            },
            "optional": {
                "do_publish": ("BOOLEAN", {"default": False}),  # Must explicitly enable
                "status": (["rev", "vwd", "apr"], {"default": "rev"}),  # Pending Review, Viewed, Approved
                "thumbnail": ("IMAGE",),  # Optional thumbnail image
            },
        }
    
    def publish(self, flow, file_path: str, description: str, 
                do_publish: bool = False, status: str = "rev", thumbnail=None):
        if flow is None:
            return ("", "ERROR: No flow data")
        
        if not do_publish:
            return ("", "⏸ Publish disabled\nEnable 'do_publish' to upload to Flow")
        
        session = flow.get("session")
        project = flow.get("project")
        shot = flow.get("shot")
        task = flow.get("task")
        user = flow.get("user")
        
        if not all([session, project, shot]):
            return ("", "ERROR: Need project and shot in pipe")
        
        if not file_path or not os.path.exists(file_path):
            return ("", f"ERROR: File not found: {file_path}")
        
        try:
            # Create version
            version_data = {
                "project": {"type": "Project", "id": project["id"]},
                "entity": {"type": "Shot", "id": shot["id"]},
                "code": flow.get("resolved_filename", f"v{pipe['version_number']:03d}"),
                "description": description,
                "sg_status_list": status,
                "sg_path_to_frames": file_path,
            }
            
            if task:
                version_data["sg_task"] = {"type": "Task", "id": task["id"]}
            
            if user and user.get("id"):
                version_data["user"] = {"type": "HumanUser", "id": user["id"]}
            
            version = session.create("Version", version_data)
            
            # Upload thumbnail
            thumbnail_status = ""
            if thumbnail is not None:
                try:
                    import tempfile
                    import numpy as np
                    from PIL import Image
                    
                    # Convert tensor to image
                    if hasattr(thumbnail, 'cpu'):
                        img_array = thumbnail.cpu().numpy()
                    else:
                        img_array = np.array(thumbnail)
                    
                    # Handle batch dimension
                    if len(img_array.shape) == 4:
                        img_array = img_array[0]
                    
                    # Convert to 8-bit
                    img_array = (np.clip(img_array, 0, 1) * 255).astype(np.uint8)
                    img = Image.fromarray(img_array)
                    
                    # Save temp file
                    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                        img.save(tmp.name, "JPEG", quality=85)
                        session.upload_thumbnail("Version", version["id"], tmp.name)
                        os.unlink(tmp.name)
                    
                    thumbnail_status = "\n✓ Thumbnail uploaded"
                except Exception as e:
                    thumbnail_status = f"\n⚠ Thumbnail failed: {str(e)}"
            elif file_path.lower().endswith(('.jpg', '.png', '.tif', '.tiff')):
                # Try using the file itself as thumbnail
                try:
                    session.upload_thumbnail("Version", version["id"], file_path)
                    thumbnail_status = "\n✓ Thumbnail from file"
                except:
                    pass
            
            version_id = str(version["id"])
            info = f"✓ Published to Flow!\nVersion ID: {version_id}\nCode: {version_data['code']}\nStatus: {status}{thumbnail_status}"
            
            print(f"[VFX Flow] Published version {version_id}")
            return (version_id, info)
            
        except Exception as e:
            return ("", f"ERROR: {str(e)}")


# =============================================================================
# FILENAME FROM PIPE NODE
# =============================================================================

class FilenameFromFlow:
    """
    Extract the resolved filename and output folder from the flow.
    Connect directly to VFX Bridge EXR Save Node:
      - filename → EXR Save filename
      - output_folder → EXR Save output_folder
    """
    
    CATEGORY = "VFX Flow"
    FUNCTION = "extract"
    RETURN_TYPES = ("STRING", "STRING", "STRING",)
    RETURN_NAMES = ("filename", "output_folder", "info",)
    OUTPUT_NODE = False
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "flow": ("FLOW_CONTEXT",),
            },
            "optional": {
                "suffix": ("STRING", {"default": ""}),  # e.g., "_beauty", "_CryptoObject"
                "base_path": ("STRING", {"default": "~/renders"}),  # Base render folder
            },
        }
    
    def extract(self, flow, suffix: str = "", base_path: str = "~/renders"):
        if flow is None:
            return ("output", "", "ERROR: No flow data")
        
        filename = flow.get("resolved_filename", "output")
        if suffix:
            filename = f"{filename}{suffix}"
        
        project = flow.get("project", {})
        shot = flow.get("shot", {})
        
        # Build output folder path
        base = os.path.expanduser(base_path)
        output_folder = os.path.join(
            base,
            project.get("name", "project"),
            shot.get("sequence", "SEQ"),
            shot.get("code", "shot")
        )
        
        info = f"Filename: {filename}\nOutput: {output_folder}/{filename}.exr"
        
        return (filename, output_folder, info)


# =============================================================================
# ADD NOTE NODE
# =============================================================================

class AddNote:
    """
    Add a note/comment to a shot, version, or task in Flow.
    Notes can include mentions (@user) and are visible in Flow's activity stream.
    """
    
    CATEGORY = "VFX Flow"
    FUNCTION = "add_note"
    RETURN_TYPES = ("STRING", "STRING",)
    RETURN_NAMES = ("note_id", "info",)
    OUTPUT_NODE = True
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "flow": ("FLOW_CONTEXT",),
                "note_text": ("STRING", {"default": "", "multiline": True}),
                "subject": ("STRING", {"default": "ComfyUI Note"}),
            },
            "optional": {
                "attach_to": (["shot", "task", "version"], {"default": "shot"}),
                "version_id": ("STRING", {"default": ""}),  # From PublishToFlow
                "do_post": ("BOOLEAN", {"default": False}),  # Safety toggle
            },
        }
    
    def add_note(self, flow, note_text: str, subject: str,
                 attach_to: str = "shot", version_id: str = "", do_post: bool = False):
        if flow is None:
            return ("", "ERROR: No flow data")
        
        if not do_post:
            return ("", "⏸ Note not posted\nEnable 'do_post' to add note to Flow")
        
        if not note_text.strip():
            return ("", "ERROR: Note text is empty")
        
        session = flow.get("session")
        project = flow.get("project")
        shot = flow.get("shot")
        task = flow.get("task")
        user = flow.get("user")
        
        if not session or not project:
            return ("", "ERROR: Invalid flow data")
        
        try:
            # Determine what to attach the note to
            note_links = []
            link_info = ""
            
            if attach_to == "version" and version_id:
                note_links.append({"type": "Version", "id": int(version_id)})
                link_info = f"Version {version_id}"
            elif attach_to == "task" and task:
                note_links.append({"type": "Task", "id": task["id"]})
                link_info = f"Task: {task['name']}"
            elif shot:
                note_links.append({"type": "Shot", "id": shot["id"]})
                link_info = f"Shot: {shot['code']}"
            else:
                return ("", "ERROR: No valid entity to attach note to")
            
            # Create note
            note_data = {
                "project": {"type": "Project", "id": project["id"]},
                "subject": subject,
                "content": note_text,
                "note_links": note_links,
            }
            
            # Add author if we have user info
            if user and user.get("id"):
                note_data["user"] = {"type": "HumanUser", "id": user["id"]}
            
            note = session.create("Note", note_data)
            
            note_id = str(note["id"])
            info = f"✓ Note posted!\nNote ID: {note_id}\nAttached to: {link_info}\nSubject: {subject}"
            
            print(f"[VFX Flow] Posted note {note_id}")
            return (note_id, info)
            
        except Exception as e:
            return ("", f"ERROR: {str(e)}")


# =============================================================================
# NODE MAPPINGS
# =============================================================================

NODE_CLASS_MAPPINGS = {
    "FlowLogin": FlowLogin,
    "ProjectBrowser": ProjectBrowser,
    "ShotBrowser": ShotBrowser,
    "TaskSelector": TaskSelector,
    "PublishToFlow": PublishToFlow,
    "FilenameFromFlow": FilenameFromFlow,
    "AddNote": AddNote,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "FlowLogin": "Flow Login",
    "ProjectBrowser": "Project Browser",
    "ShotBrowser": "Shot Browser",
    "TaskSelector": "Task Selector",
    "PublishToFlow": "Publish to Flow",
    "FilenameFromFlow": "Filename from Flow",
    "AddNote": "Add Note",
}
