"""Regressions for rc19 object-as-actor false positive; synthetic subjects only."""
import importlib.util
from pathlib import Path
import sys
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
NAME = 'h3_prompt_composer_rc20_tests'
spec = importlib.util.spec_from_file_location(NAME, PACKAGE / '__init__.py', submodule_search_locations=[str(PACKAGE)])
module = importlib.util.module_from_spec(spec)
sys.modules[NAME] = module
spec.loader.exec_module(module)
from h3_prompt_composer_rc20_tests.action_fidelity import action_role_checks

REQUIRED = [{'action': 'pin_hands', 'actor_subject': 2,
             'target_subject': 1, 'source': 'user_direction'}]

class TestInterveningObject(unittest.TestCase):
    def test_composer_clause_with_hold_object_is_correctly_grounded(self):
        detail = ("<Subject 2> leans forward with force, using her body weight "
                  "to hold <Subject 1> down, and firmly pins both of "
                  "<Subject 1>'s hands flat against the floor.")
        self.assertEqual(action_role_checks(detail, REQUIRED), [])

    def test_same_clause_with_reverse_actor_is_rejected(self):
        detail = ("<Subject 1> leans forward, using her weight to hold "
                  "<Subject 2> down, and firmly pins both of "
                  "<Subject 2>'s hands flat against the floor. "
                  "<Subject 2> then pins <Subject 1>'s hands in retaliation.")
        problems = action_role_checks(detail, REQUIRED)
        self.assertTrue(any('unrequested hand-pin role reversal' in p for p in problems), problems)

    def test_simple_reversal_with_prepositional_object_is_rejected(self):
        detail = ("<Subject 1> is on top of <Subject 2>, then rolls over "
                  "to pin <Subject 2>'s hands to the floor. "
                  "<Subject 2> counters and pins <Subject 1>'s hands.")
        problems = action_role_checks(detail, REQUIRED)
        self.assertTrue(any('unrequested hand-pin role reversal' in p for p in problems), problems)

    def test_explicit_second_subject_after_conjunction_is_actor(self):
        detail = ("<Subject 1> grabs <Subject 2>, and <Subject 2> pins "
                  "<Subject 1>'s hands to the floor.")
        self.assertEqual(action_role_checks(detail, REQUIRED), [])

    def test_missing_pin_still_fails(self):
        detail = "<Subject 2> pushes <Subject 1> down but does not grab her hands."
        problems = action_role_checks(detail, REQUIRED)
        self.assertTrue(any('required hand-pin action' in p for p in problems), problems)

if __name__ == '__main__':
    unittest.main()
