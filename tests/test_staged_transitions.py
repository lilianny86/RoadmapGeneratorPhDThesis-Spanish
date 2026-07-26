from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from recommendation_engine import build_engine_config, match_solutions  # noqa: E402
from roadmap_core import build_roadmap, load_profile_data, load_solutions, norm  # noqa: E402


def option_for_level(question: dict[str, object], level: int) -> int:
    mapping = question["mapping"]
    for option, mapped_level in enumerate(mapping, start=1):
        if int(mapped_level) == level:
            return option
    raise AssertionError(f"Question {question['number']} has no option for maturity level {level}.")


def option_for_target(question: dict[str, object], target_level: int) -> int:
    available_levels = sorted(int(level) for level in question["mapping"])
    target_candidates = [level for level in available_levels if level <= target_level]
    return option_for_level(question, target_candidates[-1] if target_candidates else available_levels[0])


class StagedTransitionTests(unittest.TestCase):
    def test_jumpseller_is_not_mapped_to_cloud_technology(self) -> None:
        solutions, _ = load_solutions(ROOT)
        invalid_entries = [
            solution
            for solution in solutions
            if "jumpseller" in norm(str(solution["name"]))
            and norm(str(solution["kpi"])) == "tecnologia cloud"
        ]

        self.assertEqual(invalid_entries, [])

    def test_cloud_transition_does_not_return_jumpseller_candidates(self) -> None:
        profile = load_profile_data(ROOT, "medium", language="es")
        question = next(q for q in profile["questions"] if norm(str(q["kpi"])) == "tecnologia cloud")
        labels = question["level_labels"]
        solutions, _ = load_solutions(ROOT)

        matches = match_solutions(
            solutions,
            sol_hint=str(profile["sol_hint"]),
            domain=question["domain"],
            kda=question["kda"],
            kpi=question["kpi"],
            transition=f"{labels[1]}->{labels[2]}",
            origin=labels[1],
            target=labels[2],
            max_candidates=6,
        )

        self.assertTrue(matches)
        self.assertFalse(any("jumpseller" in norm(str(match["name"])) for match in matches))

    def test_jump_transitions_do_not_use_kpi_fallback(self) -> None:
        profile = load_profile_data(ROOT, "medium", language="es")
        question = next(q for q in profile["questions"] if "inventario" in q["kpi"].lower())
        labels = question["level_labels"]
        solutions, _ = load_solutions(ROOT)

        matches = match_solutions(
            solutions,
            sol_hint=str(profile["sol_hint"]),
            domain=question["domain"],
            kda=question["kda"],
            kpi=question["kpi"],
            transition=f"{labels[0]}->{labels[2]}",
            origin=labels[0],
            target=labels[2],
            max_candidates=6,
        )

        self.assertEqual(matches, [])

    def test_medium_two_level_gap_includes_each_required_stage(self) -> None:
        profile = load_profile_data(ROOT, "medium", language="es")
        question = next(q for q in profile["questions"] if "inventario" in q["kpi"].lower())
        answers = {
            int(q["number"]): option_for_target(q, 3)
            for q in profile["questions"]
        }
        answers[int(question["number"])] = option_for_level(question, 1)

        payload = build_roadmap(
            root=ROOT,
            company_type="medium",
            answers=answers,
            target_level=3,
            company_name="TEST",
            company_rut="11.111.111-1",
            company_email="test@example.invalid",
            engine_cfg=build_engine_config(None),
            language="es",
        )

        labels = question["level_labels"]
        required_transitions = {f"{labels[0]}->{labels[1]}", f"{labels[1]}->{labels[2]}"}
        entries = [
            row
            for row in payload["result"]["roadmap_entries"]
            if row["question_number"] == question["number"]
        ]

        self.assertTrue(entries)
        self.assertTrue(required_transitions.issubset({row["transition"] for row in entries}))
        self.assertTrue(all(row["transition"] in required_transitions for row in entries))
        trace_entries = [
            row
            for row in payload["result"]["traceability_entries"]
            if row["question_number"] == question["number"]
        ]
        self.assertTrue(required_transitions.issubset({row["transition"] for row in trace_entries}))
        self.assertTrue(all(row["gap"] == 1 and row["overall_gap"] == 2 for row in trace_entries))

    def test_medium_n2_to_n4_includes_each_required_stage(self) -> None:
        profile = load_profile_data(ROOT, "medium", language="es")
        question = next(q for q in profile["questions"] if "sistema de riego" in q["kpi"].lower())
        answers = {
            int(q["number"]): option_for_level(q, max(int(level) for level in q["mapping"]))
            for q in profile["questions"]
        }
        answers[int(question["number"])] = option_for_level(question, 2)

        payload = build_roadmap(
            root=ROOT,
            company_type="medium",
            answers=answers,
            target_level=4,
            company_name="TEST",
            company_rut="11.111.111-1",
            company_email="test@example.invalid",
            engine_cfg=build_engine_config(None),
            language="es",
        )

        labels = question["level_labels"]
        required_transitions = {f"{labels[1]}->{labels[2]}", f"{labels[2]}->{labels[3]}"}
        entries = [
            row
            for row in payload["result"]["roadmap_entries"]
            if row["question_number"] == question["number"]
        ]

        self.assertTrue(required_transitions.issubset({row["transition"] for row in entries}))
        self.assertTrue(all(row["transition"] in required_transitions for row in entries))
        self.assertEqual(payload["result"]["engine_summary"]["required_transition_count"], 2)
        self.assertEqual(payload["result"]["engine_summary"]["covered_required_transition_count"], 2)

    def test_medium_question_twelve_remains_three_level_exception(self) -> None:
        profile = load_profile_data(ROOT, "medium", language="es")
        question = next(q for q in profile["questions"] if q["number"] == 12)

        self.assertEqual(question["available_levels"], [1, 2, 4])
        self.assertEqual(question["mapping"], [1, 2, 4])
        answers = {
            int(q["number"]): option_for_level(q, max(int(level) for level in q["mapping"]))
            for q in profile["questions"]
        }
        payload = build_roadmap(
            root=ROOT,
            company_type="medium",
            answers=answers,
            target_level=4,
            company_name="TEST",
            company_rut="11.111.111-1",
            company_email="test@example.invalid",
            engine_cfg=build_engine_config(None),
            language="es",
        )

        self.assertFalse(
            any(row["question_number"] == question["number"] for row in payload["result"]["kpi_results"])
        )

        answers = {
            int(q["number"]): option_for_target(q, 3)
            for q in profile["questions"]
        }
        answers[int(question["number"])] = option_for_level(question, 1)
        payload = build_roadmap(
            root=ROOT,
            company_type="medium",
            answers=answers,
            target_level=3,
            company_name="TEST",
            company_rut="11.111.111-1",
            company_email="test@example.invalid",
            engine_cfg=build_engine_config(None),
            language="es",
        )
        result = next(row for row in payload["result"]["kpi_results"] if row["question_number"] == question["number"])
        self.assertEqual(result["target_level"], 2)
        q12_transitions = {
            row["transition"]
            for row in payload["result"]["roadmap_entries"]
            if row["question_number"] == question["number"]
        }
        self.assertEqual(q12_transitions, {"N1-Ad hoc->N2-Básico"})

        answers = {
            int(q["number"]): option_for_level(q, max(int(level) for level in q["mapping"]))
            for q in profile["questions"]
        }
        answers[int(question["number"])] = option_for_level(question, 2)
        payload = build_roadmap(
            root=ROOT,
            company_type="medium",
            answers=answers,
            target_level=4,
            company_name="TEST",
            company_rut="11.111.111-1",
            company_email="test@example.invalid",
            engine_cfg=build_engine_config(None),
            language="es",
        )
        result = next(row for row in payload["result"]["kpi_results"] if row["question_number"] == question["number"])
        self.assertEqual(result["target_level"], 4)
        self.assertEqual(result["gap"], 1)
        q12_transitions = {
            row["transition"]
            for row in payload["result"]["roadmap_entries"]
            if row["question_number"] == question["number"]
        }
        self.assertEqual(q12_transitions, {"N2-Básico->N4-Superior"})


if __name__ == "__main__":
    unittest.main()
