import pytest

from snippetbox import plugins
from snippetbox.errors import PluginError


@pytest.fixture(autouse=True)
def clean_registry():
    plugins.clear()
    yield
    plugins.clear()


def test_register_returns_plugin():
    p = plugins.register("hello", lambda x: x + 1)
    assert p.name == "hello"


def test_register_blank_name_raises():
    with pytest.raises(PluginError):
        plugins.register("", lambda x: x)


def test_register_non_callable_raises():
    with pytest.raises(PluginError):
        plugins.register("x", 5)  # type: ignore[arg-type]


def test_unregister_existing():
    plugins.register("x", lambda: None)
    assert plugins.unregister("x") is True


def test_unregister_missing():
    assert plugins.unregister("missing") is False


def test_get_existing():
    plugins.register("x", lambda: 1)
    assert plugins.get("x").name == "x"


def test_get_missing_raises():
    with pytest.raises(PluginError):
        plugins.get("nope")


def test_has_truthy():
    plugins.register("x", lambda: 1)
    assert plugins.has("x") is True
    assert plugins.has("y") is False


def test_names_sorted():
    plugins.register("b", lambda: 1)
    plugins.register("a", lambda: 1)
    assert plugins.names() == ["a", "b"]


def test_call_invokes_callback():
    plugins.register("double", lambda x: x * 2)
    assert plugins.call("double", 5) == 10


def test_call_wraps_exception():
    def boom():
        raise ValueError("nope")

    plugins.register("boom", boom)
    with pytest.raises(PluginError):
        plugins.call("boom")


def test_call_passes_through_plugin_error():
    def boom():
        raise PluginError("boom", "explicit")

    plugins.register("boom", boom)
    with pytest.raises(PluginError):
        plugins.call("boom")


def test_call_safe_returns_default_on_error():
    def boom():
        raise RuntimeError("x")

    plugins.register("boom", boom)
    assert plugins.call_safe("boom", default="ok") == "ok"


def test_call_safe_returns_value_on_success():
    plugins.register("good", lambda: "ok")
    assert plugins.call_safe("good") == "ok"


def test_clear_removes_everything():
    plugins.register("x", lambda: 1)
    plugins.clear()
    assert plugins.names() == []


def test_listing_returns_plugins():
    plugins.register("a", lambda: 1)
    out = plugins.listing()
    assert len(out) == 1


def test_hook_decorator_registers():
    @plugins.hook("on-add", description="d")
    def my_fn(snippet):
        return snippet

    assert plugins.has("on-add")


def test_chain_no_plugin_returns_value():
    assert plugins.chain("missing", 5) == 5


def test_chain_with_plugin():
    plugins.register("double", lambda v: v * 2)
    assert plugins.chain("double", 5) == 10


def test_describe_known():
    plugins.register("x", lambda: 1, description="does x", version="1.0")
    out = plugins.describe("x")
    assert "1.0" in out


def test_describe_unknown():
    assert "unknown" in plugins.describe("nope").lower()


def test_find_by_prefix():
    plugins.register("on-add", lambda: 1)
    plugins.register("on-edit", lambda: 1)
    plugins.register("misc", lambda: 1)
    assert set(plugins.find_by_prefix("on-")) == {"on-add", "on-edit"}
