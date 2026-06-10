import unittest
from types import SimpleNamespace

from core.practice_workflow import (
    completion_errors,
    form_visible_for_student,
    practice_result,
    report_key,
    step_states,
    steps_for_student,
    unmet_previous_steps,
)


class PracticeWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.student = SimpleNamespace(study_mode="stacjonarne")

    def test_standard_path_starts_with_agreement(self):
        keys = [step["key"] for step in steps_for_student(self.student)]
        self.assertEqual(keys, [
            "zal1",
            "zal2",
            "zal2a",
            "zal6",
            "zal4",
            "zal7",
            "zal3",
            "zal5",
            "zal8",
        ])

    def test_nonstationary_student_uses_attachment_7a(self):
        student = SimpleNamespace(study_mode="niestacjonarne")
        self.assertEqual(report_key(student), "zal7a")
        keys = [step["key"] for step in steps_for_student(student)]
        self.assertIn("zal7a", keys)
        self.assertNotIn("zal7", keys)

    def test_report_visibility_matches_study_mode(self):
        self.assertTrue(form_visible_for_student(self.student, "zal7"))
        self.assertFalse(form_visible_for_student(self.student, "zal7a"))
        nonstationary = SimpleNamespace(study_mode="niestacjonarne")
        self.assertFalse(form_visible_for_student(nonstationary, "zal7"))
        self.assertTrue(form_visible_for_student(nonstationary, "zal7a"))
        self.assertTrue(form_visible_for_student(self.student, "zal4b"))

    def test_only_first_incomplete_step_is_unlocked(self):
        states = step_states(self.student, {"zal1": "approved"})
        self.assertEqual(states[0]["state"], "completed")
        self.assertEqual(states[1]["state"], "current")
        self.assertEqual(states[2]["state"], "locked")

        unmet = unmet_previous_steps(self.student, "zal2", {
            "zal1": "approved",
        })
        self.assertEqual(unmet, [])

    def test_final_result_requires_completed_protocol_and_passing_grade(self):
        internship = SimpleNamespace(grade_k=3)
        self.assertEqual(
            practice_result(self.student, {}, internship)["code"],
            "in_progress",
        )
        self.assertEqual(
            practice_result(
                self.student, {"zal8": "approved"}, internship,
            )["code"],
            "passed",
        )
        internship.grade_k = 2
        self.assertEqual(
            practice_result(
                self.student, {"zal8": "approved"}, internship,
            )["code"],
            "failed",
        )

    def test_incomplete_form_cannot_finish_a_stage(self):
        self.assertEqual(completion_errors("zal5", {
            "pytania": [
                {"nr": number, "odpowiedz": "raczej tak"}
                for number in range(1, 15)
            ],
        }), [])


if __name__ == "__main__":
    unittest.main()
