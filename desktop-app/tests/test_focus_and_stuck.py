"""
The keystrokes this app sends are claim answers.

`{ENTER}` accepts a claim, `s` skips it, `0{ENTER}` waives a copay. They were
sent with `pywinauto.keyboard.send_keys`, which types into whatever owns the
FOREGROUND -- not into the window that was just read. These tests cover the
guard that stops one landing somewhere nobody chose.

They stub pywinauto, so they run anywhere, not only on the pharmacy
workstation: `python -m pytest desktop-app/tests` from the repo root.
"""
import os
import sys
import types
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

# Stub pywinauto before the package is imported -- it is Windows-only.
_sent = []
_kb = types.ModuleType("pywinauto.keyboard")
_kb.send_keys = lambda keys, **kw: _sent.append(keys)
_pywinauto = types.ModuleType("pywinauto")
_pywinauto.Desktop = lambda **kw: types.SimpleNamespace(windows=lambda: [])
_pywinauto.keyboard = _kb
sys.modules.setdefault("pywinauto", _pywinauto)
sys.modules.setdefault("pywinauto.keyboard", _kb)
_pil = types.ModuleType("PIL")
_pil.ImageGrab = types.SimpleNamespace(grab=lambda **kw: None)
_pil.Image = types.SimpleNamespace(Image=object)
sys.modules.setdefault("PIL", _pil)
sys.modules.setdefault("PIL.ImageGrab", _pil.ImageGrab)
sys.modules.setdefault("PIL.Image", _pil.Image)

from automation import window_utils                        # noqa: E402
from automation import adjudicator                         # noqa: E402


class FakeWin:
    """A window that may or may not accept the foreground."""

    def __init__(self, handle=1, takes_focus=True, visible=True,
                 title="Adjudication Response for ODB"):
        self.handle = handle
        self.takes_focus = takes_focus
        self.visible = visible
        self.title = title
        self.active = False
        self.focus_calls = 0

    def window_text(self):
        # The loop re-reads the title after the paint delay, to catch an ONNMS
        # that has appeared at the same coordinates. Without this the fake
        # raised, the loop swallowed it, and every round `continue`d before the
        # token was ever read.
        return self.title

    def set_focus(self):
        self.focus_calls += 1
        if not self.takes_focus:
            raise RuntimeError("another window owns the foreground")
        self.active = True

    def is_active(self):
        return self.active

    def is_visible(self):
        return self.visible


class SendToTestCase(unittest.TestCase):
    """A claim answer goes to the window it was meant for, or nowhere."""

    def setUp(self):
        _sent.clear()

    def test_keys_are_sent_once_the_window_is_in_front(self):
        win = FakeWin()
        self.assertTrue(window_utils.send_to(win, "{ENTER}"))
        self.assertEqual(_sent, ["{ENTER}"])

    def test_nothing_is_typed_when_the_window_will_not_come_forward(self):
        # This is the whole point: an ONNMS popup holding the foreground used
        # to receive the adjudication window's {ENTER}.
        win = FakeWin(takes_focus=False)
        self.assertFalse(window_utils.send_to(win, "{ENTER}"))
        self.assertEqual(_sent, [], "a claim answer must not go to another window")

    def test_a_refusal_is_reported_and_names_the_keys(self):
        said = []
        window_utils.send_to(FakeWin(takes_focus=False), "s", said.append)
        self.assertEqual(len(said), 1)
        self.assertIn("'s'", said[0])
        self.assertIn("NOT sent", said[0])

    def test_an_already_active_window_is_not_re_focused(self):
        win = FakeWin()
        win.active = True
        self.assertTrue(window_utils.send_to(win, "n"))
        self.assertEqual(win.focus_calls, 0)

    def test_focus_is_retried_before_giving_up(self):
        win = FakeWin(takes_focus=False)
        self.assertFalse(window_utils.focus_window(win, attempts=3, settle=0))
        self.assertEqual(win.focus_calls, 3)


class WaitForWindowCloseTestCase(unittest.TestCase):
    """
    It used to return nothing, so every caller behaved identically whether the
    window had gone or was still sitting there unanswered.
    """

    def test_true_when_the_window_closed(self):
        self.assertTrue(window_utils.wait_for_window_close(
            FakeWin(visible=False), timeout=0.1))

    def test_false_when_it_is_still_up(self):
        self.assertFalse(window_utils.wait_for_window_close(
            FakeWin(visible=True), timeout=0.1))

    def test_a_destroyed_window_counts_as_closed(self):
        class Gone:
            def is_visible(self):
                raise RuntimeError("window handle is invalid")
        self.assertTrue(window_utils.wait_for_window_close(Gone(), timeout=0.1))


if __name__ == "__main__":
    unittest.main()


class StuckLoopTestCase(unittest.TestCase):
    """
    A claim that keeps coming back means the last answer did not land.

    Stropnicki, live 2026-10-03: `ODB:COPAY_AUTO_WAIVED` was read six times
    from the same window, ten seconds apart, because the `{ENTER}` answering it
    went to an ONNMS popup that had taken the foreground. The loop then hit its
    safety cap and called `done_cb` -- the very same callback a clean finish
    uses -- so from outside it looked like the patient had been billed. The run
    stopped on the 30th claim of 35.
    """

    def setUp(self):
        self.said = []
        self.done = []
        self.stop = type("E", (), {"is_set": lambda s: False})()
        self._saved = (adjudicator.window_utils, adjudicator.vision_client,
                       adjudicator._PLAN_HANDLERS)

    def tearDown(self):
        (adjudicator.window_utils, adjudicator.vision_client,
         adjudicator._PLAN_HANDLERS) = self._saved

    def _run_against(self, token, handler_result="continue"):
        """A window that never closes and always reads back the same token."""
        win = FakeWin(handle=99)
        adjudicator.window_utils = types.SimpleNamespace(
            find_adjudication_or_onnms=lambda: (win, "adjudication"),
            is_window_open=lambda w: True,
            screenshot_window=lambda w: "IMG",
            wait_for_window_close=lambda w, timeout=6.0: False,
            send_to=lambda w, keys, cb=None: True,
            dismiss_onnms=lambda w: True,
        )
        adjudicator.vision_client = types.SimpleNamespace(
            analyse_full=lambda img, a, b: {"token": token, "pricing": None})
        adjudicator._PLAN_HANDLERS = {
            "ODB": lambda *a, **k: handler_result}
        adjudicator.run(self.said.append, lambda: self.done.append(True),
                        self.stop)

    def test_it_stops_instead_of_answering_the_same_claim_forever(self):
        self._run_against("ODB:COPAY_AUTO_WAIVED")
        self.assertTrue(any("STUCK" in m for m in self.said))

    def test_it_does_NOT_report_the_patient_done(self):
        # The whole failure was a give-up that looked like a finish.
        self._run_against("ODB:COPAY_AUTO_WAIVED")
        self.assertEqual(self.done, [], "a stuck loop must not signal completion")

    def test_it_stops_long_before_the_safety_cap(self):
        self._run_against("ODB:COPAY_AUTO_WAIVED")
        reads = [m for m in self.said if m.startswith("Token:")]
        self.assertLess(len(reads), 6)
        self.assertFalse(any("Safety cap" in m for m in self.said))

    def test_the_message_names_the_claim_that_is_stuck(self):
        self._run_against("ODB:COPAY_AUTO_WAIVED")
        stuck = [m for m in self.said if "STUCK" in m][0]
        self.assertIn("ODB:COPAY_AUTO_WAIVED", stuck)

    def test_a_loop_that_is_making_progress_is_untouched(self):
        # Different token each round, then no window: a normal finish.
        tokens = ["ODB:ACCEPTED", "ODB:COPAY:2.00", "ODB:ACCEPTED", None]
        win = FakeWin(handle=99)

        def find():
            return (win, "adjudication") if tokens and tokens[0] else (None, None)

        def analyse(img, a, b):
            return {"token": tokens.pop(0), "pricing": None}

        adjudicator.window_utils = types.SimpleNamespace(
            find_adjudication_or_onnms=find,
            is_window_open=lambda w: True,
            screenshot_window=lambda w: "IMG",
            wait_for_window_close=lambda w, timeout=6.0: True,
            send_to=lambda w, keys, cb=None: True,
            dismiss_onnms=lambda w: True,
        )
        adjudicator.vision_client = types.SimpleNamespace(analyse_full=analyse)
        adjudicator._PLAN_HANDLERS = {"ODB": lambda *a, **k: "continue"}
        adjudicator._DONE_TIMEOUT = 0.2
        adjudicator.run(self.said.append, lambda: self.done.append(True),
                        self.stop)
        self.assertEqual(self.done, [True], "a real finish must still report done")
        self.assertFalse(any("STUCK" in m for m in self.said))


class InterventionSendsStayWithTheirDialogTestCase(unittest.TestCase):
    """
    Not every keystroke in a handler belongs to the adjudication window.

    `i` opens the intervention dialog; the `UA{ENTER}` after it belongs to THAT
    dialog. Routing it through `send_to(win, ...)` would pull focus back to the
    window behind and type an intervention code into it. Same trap in bc.py,
    whose last two sends go to the free-form dialog.

    This is a source check because there is no window to assert against -- the
    point is that a later mechanical sweep of `kb.send_keys` must not take
    these with it.
    """

    def _source(self, name):
        path = os.path.join(os.path.dirname(_HERE), "automation", "plans",
                            f"{name}.py")
        with open(path, encoding="utf-8") as fh:
            return fh.read()

    def test_the_code_after_i_is_not_aimed_at_the_adjudication_window(self):
        for name in ("odb", "gs", "assure"):
            src = self._source(name)
            self.assertIn('kb.send_keys("UA{ENTER}")', src, name)
            self.assertNotIn('send_to(win, "UA{ENTER}")', src, name)

    def test_the_i_itself_still_goes_to_the_adjudication_window(self):
        for name in ("odb", "gs", "assure", "bc"):
            self.assertIn('send_to(win, "i"', self._source(name), name)

    def test_bc_types_into_the_free_form_dialog_not_the_rejection_window(self):
        src = self._source("bc")
        self.assertIn('send_to(freeform_win, "UN"', src)
        self.assertIn('send_to(freeform_win, "{ENTER}"', src)
        self.assertNotIn('send_to(win, "UN"', src)

    def test_the_claim_answers_all_go_through_the_focus_guard(self):
        # {ENTER} accepts, s skips, 0{ENTER} waives. None may be blind.
        for name in ("odb", "bc", "cs", "gs", "assure"):
            src = self._source(name)
            for blind in ('kb.send_keys("{ENTER}")', 'kb.send_keys("s")',
                          'kb.send_keys("0{ENTER}")', 'kb.send_keys("n")'):
                self.assertNotIn(blind, src, f"{name}: {blind}")
