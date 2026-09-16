# Copyright (c) 2026, Aakvatech Limited and contributors

import frappe
from frappe.tests.utils import FrappeTestCase

from csf_ke.csf_ke.doctype.tax_withholding_certificate.tax_withholding_certificate import (
	parse_kra_withholding_certificate,
)


SAMPLE_CERTIFICATE_TEXT = """
VAT - Withholding Certificate
Date of Certificate: 31/01/2026
Certificate Serial Number: KRAVWMTO03694204726
PIN of Withholder P051674763R
Name of Withholder LATENT AUTOMOBILES AND SPARES LIMITED
Address of Withholder
BAYO HOUSE, Moi road, NAKURU, Nakuru District-20100
VAT Withholding Agency Number P051674763RP000
PIN of Withholdee P051189348K
Name of Withholdee AMEX AUTOPARTS LIMITED
Address of Withholdee
IDEAL CORNER BUILDING, LUSAKA ROAD, INDUSTRIAL AREA, Nairobi-00500
Details of Tax Withheld
Tax Head VAT - Withholding
Payment Date 26/01/2026
Invoice Number 0040560340000214176
Gross Amount of Transaction (Ksh) 13,793.00
Withholding Tax Rate 2.00
Amount of Tax Withheld (Ksh) 276.00
"""


class TestTaxWithholdingCertificate(FrappeTestCase):
	def test_parse_kra_vat_withholding_certificate(self):
		data = parse_kra_withholding_certificate(SAMPLE_CERTIFICATE_TEXT)

		self.assertEqual(data["certificate_serial_number"], "KRAVWMTO03694204726")
		self.assertEqual(data["withholder_pin"], "P051674763R")
		self.assertEqual(data["withholder_name"], "LATENT AUTOMOBILES AND SPARES LIMITED")
		self.assertEqual(data["withholding_agency_number"], "P051674763RP000")
		self.assertEqual(data["withholdee_pin"], "P051189348K")
		self.assertEqual(data["withholdee_name"], "AMEX AUTOPARTS LIMITED")
		self.assertEqual(data["invoice_number"], "0040560340000214176")
		self.assertEqual(data["gross_amount"], 13793.0)
		self.assertEqual(data["withholding_tax_rate"], 2.0)
		self.assertEqual(data["tax_withheld_amount"], 276.0)
		self.assertEqual(str(data["certificate_date"]), "2026-01-31")
		self.assertEqual(str(data["payment_date"]), "2026-01-26")

	def test_rejects_non_withholding_document(self):
		with self.assertRaises(frappe.ValidationError):
			parse_kra_withholding_certificate("This is an unrelated PDF document")

	def test_requires_core_certificate_fields(self):
		with self.assertRaises(frappe.ValidationError):
			parse_kra_withholding_certificate("VAT - Withholding Certificate\nPayment Date 26/01/2026")
