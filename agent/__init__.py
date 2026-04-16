"""GEMS agent package.

Two image-generation lines are exposed:

* :class:`agent.GEMS.GEMS` — original line, posts to an HTTP generation
  server (see ``agent/server/qwen_image.py`` / ``agent/server/z_image.py``).
* :class:`agent.comfy_gems.ComfyGEMS` — new ComfyUI line, builds a
  ComfyUI API-format workflow for one of the supported models and
  submits it to a running ComfyUI instance.
"""

from agent.GEMS import GEMS
from agent.comfy_gems import ComfyGEMS

__all__ = ["GEMS", "ComfyGEMS"]
