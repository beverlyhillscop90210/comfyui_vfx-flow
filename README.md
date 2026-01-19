# VFX Flow - ShotGrid/Flow Integration for ComfyUI

Connect your ComfyUI workflows directly to Autodesk Flow (formerly ShotGrid).

## Features

- **Project Browser** - Select active projects
- **Shot Browser** - Browse shots, auto-set status to "In Progress"
- **Task Selector** - Pick tasks, auto-assign to yourself
- **Publish to Flow** - Upload versions with safety toggle
- **Filename from Pipe** - Consistent naming throughout workflow

## Installation

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/beverlyhillscop90210/comfyui_vfx-flow.git
pip install -r comfyui_vfx-flow/requirements.txt
```

## Setup

### Environment Variables (Recommended)

```bash
export FLOW_SITE_URL="https://your-studio.shotgrid.autodesk.com"
export FLOW_SCRIPT_NAME="comfyui_vfx_flow"
export FLOW_API_KEY="your_api_key_here"
```

### Create Script User in Flow

1. Go to Admin → Scripts
2. Create new script: `comfyui_vfx_flow`
3. Copy the API key

## Workflow

```
Flow Login
    ↓
Project Browser (select project)
    ↓ pipe
Shot Browser (select shot → auto "In Progress")
    ↓ pipe + latest_version_path
Task Selector (assign yourself)
    ↓ pipe
    ├──→ Filename from Pipe → EXR Save Node (VFX Bridge)
    │
    └──→ [Your Processing...]
            ↓
         Publish to Flow [do_publish: true]
```

## Nodes

### Flow Login
Connect to your Flow instance.
- **Inputs:** `site_url`, `script_name`, `api_key`
- **Outputs:** `session`, `status`

### Project Browser
Select a project.
- **Inputs:** `session`, `project_name` (filter)
- **Outputs:** `pipe`, `info`

### Shot Browser
Select a shot and get latest version.
- **Inputs:** `pipe`, `shot_code` (filter), `set_in_progress`
- **Outputs:** `pipe`, `latest_version_path`, `info`

### Task Selector
Assign a task to yourself.
- **Inputs:** `pipe`, `task_name`, `assign_to_me`
- **Outputs:** `pipe`, `info`

### Publish to Flow
Upload a version (only when enabled).
- **Inputs:** `pipe`, `file_path`, `description`, `do_publish`, `status`
- **Outputs:** `version_id`, `info`

### Filename from Pipe
Extract consistent filename for saving.
- **Inputs:** `pipe`, `suffix`
- **Outputs:** `filename`, `folder_suggestion`, `info`

## The FLOW_PIPE

All data flows through the `pipe`:

```python
{
    "session": <ShotGrid connection>,
    "project": {"id": 123, "name": "Project_X"},
    "shot": {"id": 456, "code": "SH010", "sequence": "SEQ01"},
    "task": {"id": 789, "name": "comp"},
    "user": {"id": 42, "name": "Peter Schings"},
    "version_number": 3,
    "resolved_filename": "ProjectX_SEQ01_SH010_comp_v003"
}
```

## Integration with VFX Bridge

Use `latest_version_path` directly with EXR Hot Folder Loader:

```
Shot Browser
    ↓ latest_version_path
EXR Hot Folder Loader (folder_path = latest_version_path parent)
```

Use `Filename from Pipe` with EXR Save Node:

```
Filename from Pipe
    ↓ filename
EXR Save Node (filename = pipe filename)
```

## License

MIT
