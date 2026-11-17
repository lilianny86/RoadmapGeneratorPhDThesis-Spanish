import unittest

from en_localization import localize_solution_description
from pdf_export import _format_solution_description


class SolutionDescriptionTests(unittest.TestCase):
    def test_spanish_training_descriptions_keep_accents(self):
        masters = "Fortalecer el nivel educacional del tomador de decisiones con formacion avanzada en gestion del sector agroalimentario."
        doctorate = "Escalar a un nivel de especializacion avanzada para liderar innovacion, analisis y estrategia con alta base tecnica."

        self.assertIn("formación avanzada en gestión", localize_solution_description(masters, "es"))
        corrected = localize_solution_description(doctorate, "es")
        self.assertIn("especialización", corrected)
        self.assertIn("la innovación, el análisis", corrected)
        self.assertIn("base técnica", corrected)
        self.assertIn("advanced training", localize_solution_description(masters, "en"))
        self.assertIn("strong technical grounding", localize_solution_description(doctorate, "en"))

    def test_pdf_keeps_long_sentences_and_following_context(self):
        spanish = (
            "Usar la plataforma Agrometeorología INIA, especialmente la información de evapotranspiración, "
            "para estimar demanda hídrica, ajustar la frecuencia de riego y apoyar decisiones operativas ante variabilidad climática. "
            "Esta recomendación permite programar riegos con datos agroclimáticos."
        )
        english = (
            "Use the INIA agrometeorology platform, particularly its evapotranspiration data, to estimate crop water demand, "
            "adjust irrigation frequency, and support farm management decisions under variable weather conditions. "
            "The recommendation relies on public agroclimatic data."
        )
        for description in (spanish, english):
            with self.subTest(description=description):
                self.assertGreater(len(description), 180)
                self.assertEqual(_format_solution_description(description), description)

    def test_pdf_omits_catalog_transition_notes_and_keeps_punctuation(self):
        self.assertEqual(
            _format_solution_description("  Ajustar\n el riego, Se propone para la transición indicada."), "Ajustar el riego."
        )
        self.assertEqual(
            _format_solution_description("Adjust irrigation. It is proposed for the transition indicated."), "Adjust irrigation."
        )
        self.assertEqual(_format_solution_description(None), "")
