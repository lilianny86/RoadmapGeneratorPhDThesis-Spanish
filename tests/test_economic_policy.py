import csv
import io
import tempfile
import unittest
from pathlib import Path

from economic_policy import BUDGET_OPTIONS, classify_economic_fit
from pdf_export import export_roadmap_pdf, identified_gap_indicators
from pdf_export_en import export_roadmap_pdf as export_roadmap_pdf_en
from recommendation_engine import EngineConfig, optimize_recommendations
from roadmap_core import build_roadmap, load_profile_data, load_solutions
from stats_export import (
    build_kpi_statistical_records,
    build_statistical_csv_bytes,
    build_statistical_record,
)


ROOT = Path(__file__).resolve().parents[1]


def candidate(name, effort, financing='direct', transition='1:test', stage='Short term'):
    return {
        'solution_name': name,
        'economic_effort': effort,
        'financing_mode': financing,
        'required_transition_key': transition,
        'plazo': stage,
        'priority': 1,
    }


class EconomicPolicyTests(unittest.TestCase):
    def test_matrix_by_profile(self):
        expected = (
            ("compatible", "conditional_effort", "not_compatible"),
            ("compatible", "compatible", "conditional_effort"),
            ("compatible", "compatible", "compatible"),
            ("compatible", "compatible", "conditional_effort"),
            ("compatible", "compatible", "compatible"),
            ("compatible", "compatible", "compatible"),
        )
        for capacity, results in zip((*BUDGET_OPTIONS['small'], *BUDGET_OPTIONS['medium']), expected):
            for mode in ('direct', 'free'):
                self.assertEqual(tuple(classify_economic_fit(capacity, e, mode) for e in ('low', 'medium', 'high')), results)
            self.assertEqual(classify_economic_fit(capacity, 'high', 'quotation_required'), 'quotation_pending')
            self.assertEqual(classify_economic_fit(capacity, 'high', 'cofinancing'), 'cofinancing_pending')
            self.assertEqual(classify_economic_fit(capacity, 'not_assessable', 'direct'), 'insufficient_evidence')

    def test_reserves_conditional_actions_for_transitions_without_compatible_option(self):
        entries, result = optimize_recommendations([
            candidate('A medium cost', 'medium'),
            candidate('B low cost', 'low'),
            candidate('C only medium', 'medium', transition='2:test'),
            candidate('D quoted', 'high', 'quotation_required', transition='3:test'),
            candidate('E cofinancing', 'high', 'cofinancing', transition='4:test'),
            candidate('F free access, high effort', 'high', 'free', transition='5:test'),
        ], EngineConfig(budget_capacity='small_low'))
        self.assertEqual({row['solution_name']: row['selection_status'] for row in entries}, {
            'B low cost': 'compatible', 'C only medium': 'conditional_effort',
            'D quoted': 'quotation_pending', 'E cofinancing': 'cofinancing_pending',
        })
        self.assertEqual(result['transition_outcomes']['5:test']['status'], 'not_compatible')

    def test_horizon_does_not_change_selection_score(self):
        selected, _ = optimize_recommendations([
            candidate('A long-term action', 'high', stage='Long term'),
            candidate('B short-term action', 'high'),
        ], EngineConfig(budget_capacity='medium_high', max_recommendations=1))
        self.assertEqual(selected[0]['solution_name'], 'A long-term action')
        self.assertNotIn('factor_horizonte', selected[0]['engine_explanation']['component_scores'])

    def test_medium_high_has_no_additional_high_effort_cap(self):
        selected, _ = optimize_recommendations([
            candidate(str(i), 'high', transition=f'{i}:test') for i in range(1, 7)
        ], EngineConfig(budget_capacity='medium_high'))
        self.assertEqual(len(selected), 6)

    def test_roadmap_gap_list_and_optional_unclassified_section(self):
        first = dict(candidate('Action 1', 'low'), kpi='Irrigation', question_number=1, selection_status='compatible')
        second = dict(candidate('Action 2', 'low', stage='Unclassified'), kpi='Water', question_number=2,
                      priority=2, selection_status='compatible')
        irrigation_gap = dict(first, gap=1)
        water_gap = dict(second, gap=2)
        at_target = {'kpi': 'Met target', 'question_number': 3, 'gap': 0, 'priority': 0}
        gaps = [irrigation_gap, water_gap]
        self.assertEqual(identified_gap_indicators([*gaps, irrigation_gap, at_target]), ['Water', 'Irrigation'])
        for export, heading, financing, hidden, unclassified in (
            (export_roadmap_pdf, 'Indicadores con brecha identificada', 'Financiamiento directo',
             ('Aspectos prioritarios', 'Condiciones econ\u00f3micas', 'Objetivo: ', 'Compatible seg\u00fan la matriz'), 'Sin clasificar'),
            (export_roadmap_pdf_en, 'Indicators with identified gaps', 'Direct financing',
             ('Priority areas', 'Economic considerations', 'Objective: ', 'Compatible under the matrix'), 'Unclassified'),
        ):
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'roadmap.pdf'
                export({'result': {'roadmap_entries': [first], 'kpi_results': gaps}}, path)
                text_stream = path.read_bytes().decode('cp1252', errors='replace')
                for label in (heading, financing, 'Action 1', '1. Water', '2. Irrigation'):
                    self.assertIn(label, text_stream)
                for label in (*hidden, unclassified, 'Met target', 'Action 2'):
                    self.assertNotIn(label, text_stream)
                export({'result': {'roadmap_entries': [first, second], 'kpi_results': gaps}}, path)
                text_stream = path.read_bytes().decode('cp1252', errors='replace')
                self.assertIn(unclassified, text_stream)
                self.assertIn('Action 2', text_stream)

    def test_catalog_and_bilingual_pipeline(self):
        rows, report = load_solutions(ROOT)
        self.assertEqual(report['summary']['error_count'], 0)
        self.assertEqual(len(rows), 212)
        self.assertNotIn('price_min_clp', rows[0])
        for profile, capacities in BUDGET_OPTIONS.items():
            questions = load_profile_data(ROOT, profile)['questions']
            answers = {row['number']: 1 for row in questions}
            target = 3 if profile == 'small' else 4
            baseline = None
            for capacity in capacities:
                es = build_roadmap(ROOT, profile, answers, target, 'Test', '', '', EngineConfig(budget_capacity=capacity))
                en = build_roadmap(ROOT, profile, answers, target, 'Test', '', '', EngineConfig(budget_capacity=capacity), 'en')
                left, right = (payload['result'] for payload in (es, en))
                diagnostic = [left[key] for key in ('current_score', 'target_score', 'target_progress_pct', 'kpi_assessment_results')]
                if baseline is None:
                    baseline = diagnostic
                self.assertEqual(baseline, diagnostic)
                def identity(result):
                    return {(row['required_transition_key'], row['solution_code'], row['selection_status']) for row in result['roadmap_entries']}
                self.assertEqual(identity(left), identity(right))
                summary = build_statistical_record(es, company_type=profile, budget_range=capacity, participant_code='test')
                details = build_kpi_statistical_records(es, summary)
                self.assertEqual(len(details), len(questions))
                for key in ('covered_transitions_total', 'required_transitions_total', 'conditional_transitions_total', 'matched_transitions_total'):
                    self.assertEqual(summary[key], sum(row[key] for row in details))
                self.assertEqual(summary['recommendations_total'], sum(summary[k] for k in (
                    'compatible_actions', 'effort_conditional_actions', 'cofinancing_actions', 'quotation_actions',
                )))
                csv_text = build_statistical_csv_bytes(summary).decode('utf-8-sig')
                self.assertNotIn('Presupuesto usado', next(csv.reader(io.StringIO(csv_text))))
                with tempfile.TemporaryDirectory() as tmp:
                    for export, payload in ((export_roadmap_pdf, es), (export_roadmap_pdf_en, en)):
                        path = Path(tmp) / 'roadmap.pdf'
                        export(payload, path)
                        self.assertTrue(path.read_bytes().startswith(b'%PDF'))


if __name__ == '__main__':
    unittest.main()
