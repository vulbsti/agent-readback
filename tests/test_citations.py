from agent_readback import citations
from agent_readback.backends import Reply
from agent_readback.explain import Explainer
from agent_readback.model import Event, Hunk, Session


def test_expand_check_and_strip():
    assert citations.expand("E3-E5, H2") == ["E3", "E4", "E5", "H2"]
    valid = {"E1", "E2", "H1"}
    text = "**Changed**\n- a does b [E1, H1]\n- c does d\n- bogus [E9, E2]\n- only bogus [E8]\n```mermaid\nflowchart TD\n A-->B\n```"
    c = citations.check(text, valid)
    assert c.unknown == ["E8", "E9"] and c.factual_lines == 4
    assert c.uncited_lines == ["- c does d", "- only bogus [E8]"]  # unknown ids alone don't count as cited
    assert citations.strip_unknown("x [E9, E2] y [E9]", valid) == "x [E2] y "


class Scripted:
    """Backend that first answers without citations, then (repair pass) with them."""

    name = "scripted"

    def __init__(self):
        self.calls = []

    def complete(self, system, prompt):
        self.calls.append(prompt)
        if len(self.calls) == 1:
            return Reply("- the agent edited add()\n- it ran tests [E7]")
        return Reply("- the agent edited add() [E1, H1]\n- it ran tests [E1]")


def test_repair_pass_adds_citations_and_drops_unknown_ids(tmp_path):
    s = Session(
        agent="claude-code",
        path=str(tmp_path / "t.jsonl"),
        events=[Event(id="E1", kind="tool", text="Edit calc.py", line=1, tool="Edit")],
        hunks=[Hunk(id="H1", file="calc.py", header="@@ -1 +1 @@", text="@@ -1 +1 @@\n+x")],
    )
    b = Scripted()
    ex = Explainer(s, b).run("overview")
    assert len(b.calls) == 2 and "unknown ids E7" in b.calls[1]
    assert ex.coverage == 1.0 and ex.cited == ["E1", "H1"] and not ex.unknown_removed


class Long:
    """Backend whose first answer is three screens long; the shorten pass returns a short one."""

    name = "long"

    def __init__(self):
        self.calls = []

    def complete(self, system, prompt):
        self.calls.append(prompt)
        if len(self.calls) == 1:
            return Reply("\n".join(f"- step {i} edited add() [E1]" for i in range(150)))
        return Reply("- the agent edited add() [E1, H1]")


def test_answers_longer_than_a_screen_are_shortened(tmp_path):
    s = Session(
        agent="claude-code",
        path=str(tmp_path / "t.jsonl"),
        events=[Event(id="E1", kind="tool", text="Edit calc.py", line=1, tool="Edit")],
        hunks=[Hunk(id="H1", file="calc.py", header="@@ -1 +1 @@", text="@@ -1 +1 @@\n+x")],
    )
    b = Long()
    ex = Explainer(s, b).run("walkthrough")
    assert len(b.calls) == 2 and "longer than one screen" in b.calls[1]
    assert ex.text == "- the agent edited add() [E1, H1]" and ex.coverage == 1.0
