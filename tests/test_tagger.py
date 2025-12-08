from snippetbox import tagger
from snippetbox.snippet import Snippet


def test_suggest_tags_python_io():
    s = Snippet(
        title="x",
        body="with open('foo') as f: f.read()",
        language="python",
    )
    tags = tagger.suggest_tags(s)
    assert "io" in tags


def test_suggest_tags_async():
    s = Snippet(title="x", body="async def main(): await asyncio.sleep(1)", language="python")
    tags = tagger.suggest_tags(s)
    assert "async" in tags


def test_suggest_tags_no_match():
    s = Snippet(title="x", body="x = 1", language="python")
    tags = tagger.suggest_tags(s)
    assert tags == []


def test_suggest_tags_respects_max():
    s = Snippet(
        title="x",
        body="open(f) async def x(): await asyncio.sleep(1) re.search('x', y)",
        language="python",
    )
    tags = tagger.suggest_tags(s, max_tags=2)
    assert len(tags) == 2


def test_suggest_tags_subprocess():
    s = Snippet(title="x", body="import subprocess; subprocess.run(['ls'])", language="python")
    tags = tagger.suggest_tags(s)
    assert "subprocess" in tags


def test_suggest_tags_threading():
    s = Snippet(title="x", body="import threading; threading.Thread(target=f)", language="python")
    tags = tagger.suggest_tags(s)
    assert "threading" in tags


def test_suggest_tags_test():
    s = Snippet(title="x", body="def test_foo(): assert True", language="python")
    tags = tagger.suggest_tags(s)
    assert "test" in tags


def test_suggest_tags_logging():
    s = Snippet(title="x", body="logger.info('hi')", language="python")
    tags = tagger.suggest_tags(s)
    assert "logging" in tags


def test_suggest_tags_dataclass():
    s = Snippet(title="x", body="@dataclass\nclass Foo: pass", language="python")
    tags = tagger.suggest_tags(s)
    assert "dataclass" in tags


def test_suggest_tags_typing():
    s = Snippet(title="x", body="from typing import Optional", language="python")
    tags = tagger.suggest_tags(s)
    assert "typing" in tags


def test_suggest_tags_django():
    s = Snippet(title="x", body="import django", language="python")
    tags = tagger.suggest_tags(s)
    assert "django" in tags


def test_suggest_tags_flask():
    s = Snippet(title="x", body="@app.route('/x')\ndef hi(): pass", language="python")
    tags = tagger.suggest_tags(s)
    assert "flask" in tags


def test_suggest_tags_react():
    s = Snippet(
        title="x",
        body="const x = useState(1); useEffect(() => {})",
        language="javascript",
    )
    tags = tagger.suggest_tags(s)
    assert "react" in tags


def test_suggest_tags_git():
    s = Snippet(title="x", body="git rebase -i HEAD~3", language="shell")
    tags = tagger.suggest_tags(s)
    assert "git" in tags


def test_suggest_tags_docker():
    s = Snippet(title="x", body="docker run -it ubuntu", language="shell")
    tags = tagger.suggest_tags(s)
    assert "docker" in tags


def test_suggest_tags_aws():
    s = Snippet(title="x", body="import boto3", language="python")
    tags = tagger.suggest_tags(s)
    assert "aws" in tags


def test_apply_to_mutates_snippet():
    s = Snippet(title="x", body="open('f')", language="python")
    out = tagger.apply_to(s)
    assert s.auto_tags == out


def test_apply_to_many_counts_changes():
    a = Snippet(title="x", body="open('f')", language="python")
    b = Snippet(title="y", body="just text")
    n = tagger.apply_to_many([a, b])
    assert n == 1


def test_known_tags_includes_io():
    assert "io" in tagger.known_tags()


def test_match_count_with_matches():
    text = "open('f') async def x(): await asyncio.sleep(1)"
    assert tagger.match_count(text) >= 2


def test_match_count_blank():
    assert tagger.match_count("") == 0


def test_add_custom_rule_extends():
    tagger.add_custom_rule("custom-x", [r"\bcustomthing\b"])
    s = Snippet(title="x", body="customthing here", language="plain")
    tags = tagger.suggest_tags(s)
    assert "custom-x" in tags


def test_add_custom_rule_no_op_when_blank():
    before = list(tagger._COMPILED)
    tagger.add_custom_rule("", [])
    assert tagger._COMPILED == before


def test_apply_to_blank_body_returns_empty():
    s = Snippet(title="x", body="", language="plain")
    s.body = "anything"
    assert tagger.apply_to(s, max_tags=1) == []
