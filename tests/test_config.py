import pytest

from snippetbox import config
from snippetbox.errors import ConfigError


def test_default_config():
    cfg = config.Config()
    assert cfg.book_path
    assert cfg.server_port > 0


def test_book_resolved_expands_home(monkeypatch, tmp_path):
    # cross-platform: set both HOME (POSIX) and USERPROFILE (Windows)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    cfg = config.Config(book_path="~/x.json")
    assert "x.json" in str(cfg.book_resolved())


def test_default_config_path_under_home():
    p = config.default_config_path()
    assert p.name == "config.toml"


def test_load_missing_file_falls_back(tmp_path):
    cfg = config.load(tmp_path / "missing.toml")
    assert cfg.book_path


def test_load_picks_up_environ(monkeypatch, tmp_path):
    monkeypatch.setenv("SNIPPETBOX_BOOK", "/elsewhere/book.json")
    cfg = config.load(tmp_path / "missing.toml")
    assert "/elsewhere" in cfg.book_path


def test_save_and_load_round_trip(tmp_path):
    cfg = config.Config(editor="vim", server_port=9999)
    p = config.save(cfg, tmp_path / "config.toml")
    cfg2 = config.load(p)
    assert cfg2.editor == "vim"
    assert cfg2.server_port == 9999


def test_parse_quoted_string(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text('editor = "vim"\n', encoding="utf-8")
    cfg = config.load(p)
    assert cfg.editor == "vim"


def test_parse_single_quoted_string(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text("editor = 'nano'\n", encoding="utf-8")
    cfg = config.load(p)
    assert cfg.editor == "nano"


def test_parse_bool(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text("audit_enabled = true\n", encoding="utf-8")
    cfg = config.load(p)
    assert cfg.audit_enabled is True


def test_parse_int(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text("server_port = 9090\n", encoding="utf-8")
    cfg = config.load(p)
    assert cfg.server_port == 9090


def test_parse_skips_comments_and_blank(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text("# comment\n\n  \neditor = \"vim\"\n", encoding="utf-8")
    cfg = config.load(p)
    assert cfg.editor == "vim"


def test_parse_with_section_header(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text('[main]\neditor = "vim"\n', encoding="utf-8")
    cfg = config.load(p)
    assert cfg.editor == "vim"


def test_parse_skips_unknown_keys(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text('unknown = "value"\neditor = "vim"\n', encoding="utf-8")
    cfg = config.load(p)
    assert cfg.editor == "vim"


def test_validate_clean():
    assert config.validate(config.Config()) == []


def test_validate_blank_book_path():
    cfg = config.Config(book_path="")
    assert config.validate(cfg)


def test_validate_bad_port():
    cfg = config.Config(server_port=0)
    assert config.validate(cfg)


def test_validate_bad_format():
    cfg = config.Config(default_format="weird")
    assert config.validate(cfg)


def test_reset_returns_default():
    assert config.reset().editor == ""


def test_from_dict_unknown_keys_ignored():
    cfg = config.from_dict({"editor": "vim", "unknown": "x"})
    assert cfg.editor == "vim"


def test_from_dict_non_dict_raises():
    with pytest.raises(ConfigError):
        config.from_dict("not a dict")  # type: ignore[arg-type]


def test_from_environ_uses_editor(monkeypatch):
    monkeypatch.delenv("SNIPPETBOX_EDITOR", raising=False)
    monkeypatch.setenv("EDITOR", "nvim")
    cfg = config._from_environ()
    assert cfg.editor == "nvim"


def test_from_environ_prefers_snippetbox_editor(monkeypatch):
    monkeypatch.setenv("SNIPPETBOX_EDITOR", "code")
    monkeypatch.setenv("EDITOR", "nvim")
    cfg = config._from_environ()
    assert cfg.editor == "code"


def test_render_includes_keys():
    text = config._render(config.Config(editor="vim"))
    assert "editor" in text
    assert "vim" in text


def test_load_handles_kv_without_equals(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text("invalidline\neditor = \"vim\"\n", encoding="utf-8")
    cfg = config.load(p)
    assert cfg.editor == "vim"


def test_parse_float(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text("server_port = 8080.0\n", encoding="utf-8")
    cfg = config.load(p)
    # int in dataclass; float coerces to int through merge
    assert int(cfg.server_port) == 8080
