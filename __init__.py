import importlib
import sys


bl_info = {
    "name": "Mechanical Overshoot",
    "author": "Isaac O'Connor",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "Graph Editor > Sidebar > Mechanical",
    "description": "Add elastic overshoot to mechanical animation keyframes.",
    "category": "Animation",
}


_MODULE_NAME = f"{__name__}.mechanical_overshoot"

if _MODULE_NAME in sys.modules:
    mechanical_overshoot = importlib.reload(sys.modules[_MODULE_NAME])
else:
    from . import mechanical_overshoot


def register():
    mechanical_overshoot.register()


def unregister():
    mechanical_overshoot.unregister()
