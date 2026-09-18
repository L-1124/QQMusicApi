"""Web 模块级路由适配."""

import importlib
import pkgutil

__all__ = []

for _, name, _ in pkgutil.iter_modules(__path__):
    importlib.import_module(f".{name}", __package__)
    __all__.append(name)
