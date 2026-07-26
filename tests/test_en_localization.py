import unittest

from en_localization import localize_price_display


class PriceLocalizationTests(unittest.TestCase):
    def test_localizes_variable_price_labels_for_english_outputs(self) -> None:
        price = (
            "Sin precio público único; costo variable según diámetro, longitud, "
            "mano de obra y diseño hidráulico; requiere cotización CLP"
        )

        self.assertEqual(
            localize_price_display(price, language="en"),
            "No single public price; cost varies by diameter, length, labor, and hydraulic design; quotation required (CLP)",
        )

    def test_keeps_spanish_price_labels_for_spanish_outputs(self) -> None:
        price = "Piloto o convenio; sin precio público vigente CLP"

        self.assertEqual(localize_price_display(price, language="es"), price)

    def test_localizes_cofunded_project_price_labels_for_english_outputs(self) -> None:
        price = "Postulación o proyecto cofinanciado; sin precio público único CLP"

        self.assertEqual(
            localize_price_display(price, language="en"),
            "Application or co-funded project; no single public price (CLP)",
        )


if __name__ == "__main__":
    unittest.main()
