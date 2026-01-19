"""
VFX Flow - ShotGrid/Flow Integration for ComfyUI
Connect your ComfyUI workflows directly to your production pipeline.
"""

from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

# Import server routes
try:
    from . import server
except ImportError:
    pass

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']

WEB_DIRECTORY = "./web"
