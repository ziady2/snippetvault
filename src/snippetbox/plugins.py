"""Tiny plugin registry.

A "plugin" is just a callable registered against a name. Unlike most
plugin systems, this one doesn't try to be clever about discovery:
the user explicitly registers a function. Discovery via setuptools
entry points is on the list but I haven't needed it yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from .errors import PluginError


@dataclass
class Plugin:
    name: str
    callback: Callable[..., Any]
    description: str = ""
    version: str = "0"


_REGISTRY: Dict[str, Plugin] = {}


def register(name: str, callback: Callable[..., Any], *, description: str = "", version: str = "0") -> Plugin:
    if not name:
        raise PluginError(name, "name is empty")
    if not callable(callback):
        raise PluginError(name, "callback is not callable")
    plugin = Plugin(name=name, callback=callback, description=description, version=version)
    _REGISTRY[name] = plugin
    return plugin


def unregister(name: str) -> bool:
    if name in _REGISTRY:
        del _REGISTRY[name]
        return True
    return False


def get(name: str) -> Plugin:
    if name not in _REGISTRY:
        raise PluginError(name, "no such plugin")
    return _REGISTRY[name]


def has(name: str) -> bool:
    return name in _REGISTRY


def names() -> List[str]:
    return sorted(_REGISTRY.keys())


def call(name: str, *args, **kwargs) -> Any:
    plugin = get(name)
    try:
        return plugin.callback(*args, **kwargs)
    except PluginError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise PluginError(name, str(exc)) from exc


def call_safe(name: str, default: Any = None, *args, **kwargs) -> Any:
    try:
        return call(name, *args, **kwargs)
    except PluginError:
        return default


def clear() -> None:
    _REGISTRY.clear()


def listing() -> List[Plugin]:
    return [_REGISTRY[k] for k in sorted(_REGISTRY)]


def hook(name: str, *, description: str = "") -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator form: ``@hook('post-add')`` registers the function."""

    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        register(name, fn, description=description, version=getattr(fn, "__version__", "0"))
        return fn

    return deco


def chain(name: str, value: Any, *args, **kwargs) -> Any:
    """Run all plugins registered under ``name`` (if multiple) on ``value``.

    Currently the registry is single-callback per name, so this is
    equivalent to ``call``. Kept as a separate entry point so we can
    grow into a multi-callback model without API churn.
    """
    if not has(name):
        return value
    return call(name, value, *args, **kwargs)


def describe(name: str) -> str:
    if not has(name):
        return f"<unknown plugin {name!r}>"
    p = _REGISTRY[name]
    return f"{p.name} (v{p.version}): {p.description or 'no description'}"


def find_by_prefix(prefix: str) -> List[str]:
    return [n for n in names() if n.startswith(prefix)]
