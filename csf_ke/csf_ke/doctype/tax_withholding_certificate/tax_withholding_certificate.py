# Copyright (c) 2026, Aakvatech Limited and contributors
# For license information, please see license.txt

from __future__ import annotations

import re
from io import BytesIO

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate


class TaxWithholdingCertificate(Document):
	"""Store a tax withholding certificate and structured data extracted from its PDF."""

	def before_save(self):
		if self.source_document and (self.is_new() or self.has_value_changed("source_document")):
			self.extract_from_source_document()

	def validate(self):
		self.validate_duplicate_certificate()
		self.validate_amounts()

	def extract_from_source_document(self):
		try:
			text = extract_pdf_text(self.source_document)
			data = parse_kra_withholding_certificate(text)
			for fieldname, value in data.items():
				if value not in (None, "") and self.meta.has_field(fieldname):
					self.set(fieldname, value)

			self.tax_authority = self.tax_authority or "Kenya Revenue Authority"
			self.country = self.country or "Kenya"
			self.currency = self.currency or "KES"
			self._match_erpnext_records()
			self.extraction_status = "Extracted"
			self.extraction_log = _("Certificate data extracted from the attached PDF.")
		except Exception as exc:
			self.extraction_status = "Failed"
			self.extraction_log = str(exc)

	def validate_duplicate_certificate(self):
		if not self.certificate_serial_number:
			return

		duplicate = frappe.db.exists(
			"Tax Withholding Certificate",
			{
				"certificate_serial_number": self.certificate_serial_number,
				"name": ["!=", self.name or ""],
			},
		)
		if duplicate:
			frappe.throw(
				_("Certificate Serial Number {0} already exists in {1}.").format(
					frappe.bold(self.certificate_serial_number), frappe.bold(duplicate)
				),
				frappe.DuplicateEntryError,
			)

	def validate_amounts(self):
		if not (self.gross_amount and self.withholding_tax_rate and self.tax_withheld_amount):
			return

		expected = flt(self.gross_amount) * flt(self.withholding_tax_rate) / 100
		difference = abs(expected - flt(self.tax_withheld_amount))
		if difference > 1.0:
			message = _(
				"Amount check warning: gross amount × withholding rate gives {0}, but the certificate records {1}."
			).format(frappe.format_value(expected, {"fieldtype": "Currency", "options": self.currency}), self.tax_withheld_amount)
			self.extraction_log = "\n".join(filter(None, [self.extraction_log, message]))

	def _match_erpnext_records(self):
		if self.withholdee_pin and not self.company:
			self.company = frappe.db.get_value("Company", {"tax_id": self.withholdee_pin}, "name")

		if self.withholder_pin and not self.customer:
			self.customer = frappe.db.get_value("Customer", {"tax_id": self.withholder_pin}, "name")

		if self.invoice_number and not self.sales_invoice:
			self.sales_invoice = find_sales_invoice(self.invoice_number, self.company, self.customer)


@frappe.whitelist()
def extract_certificate(docname: str):
	"""Re-extract an existing certificate from its attached PDF."""
	doc = frappe.get_doc("Tax Withholding Certificate", docname)
	doc.check_permission("write")
	if not doc.source_document:
		frappe.throw(_("Attach a certificate PDF first."))

	doc.extract_from_source_document()
	doc.save()
	return doc.as_dict()


def extract_pdf_text(file_url: str) -> str:
	"""Return text from a PDF stored in Frappe's File doctype."""
	file_doc = frappe.get_doc("File", {"file_url": file_url})
	content = file_doc.get_content()
	if not content:
		frappe.throw(_("The attached certificate file is empty."))

	try:
		from pypdf import PdfReader
	except ImportError:
		frappe.throw(_("PDF extraction requires the pypdf package."))

	reader = PdfReader(BytesIO(content))
	text = "\n".join(page.extract_text() or "" for page in reader.pages)
	if not text.strip():
		frappe.throw(_("No text could be extracted from the PDF. Scanned/image-only certificates are not yet supported."))
	return text


def parse_kra_withholding_certificate(text: str) -> dict:
	"""Parse a KRA VAT/withholding certificate into normalized fields.

	The parser intentionally works from labels rather than absolute PDF positions so
	minor KRA layout changes do not break extraction.
	"""
	if not text or "withholding" not in text.lower():
		raise frappe.ValidationError(_("The PDF does not appear to be a withholding certificate."))

	clean = _normalize_text(text)
	data = {
		"certificate_type": _first(clean, r"(?im)^\s*(VAT\s*-?\s*Withholding(?:\s+Certificate)?)\s*$") or "VAT - Withholding",
		"certificate_date": _date_value(_first(clean, r"Date of Certificate\s*:?\s*(\d{1,2}/\d{1,2}/\d{4})")),
		"certificate_serial_number": _first(
			clean,
			r"Certificate Serial Number\s*:?\s*([A-Z0-9-]{10,})",
		) or _first(clean, r"\b(KRAVW[A-Z0-9-]{8,})\b"),
		"withholder_pin": _first(clean, r"PIN of Withholder\s*:?\s*([A-Z0-9]+)"),
		"withholder_name": _line_value(clean, "Name of Withholder"),
		"withholder_address": _block_value(clean, "Address of Withholder", ["VAT Withholding Agency Number", "Withholder Details", "Withholdee Details"]),
		"withholding_agency_number": _first(clean, r"VAT Withholding Agency Number\s*:?\s*([A-Z0-9]+)"),
		"withholdee_pin": _first(clean, r"PIN of Withholdee\s*:?\s*([A-Z0-9]+)"),
		"withholdee_name": _line_value(clean, "Name of Withholdee"),
		"withholdee_address": _block_value(clean, "Address of Withholdee", ["Withholdee Details", "Details of Tax Withheld", "Tax Head"]),
		"tax_head": _line_value(clean, "Tax Head"),
		"payment_date": _date_value(_first(clean, r"Payment Date\s*:?\s*(\d{1,2}/\d{1,2}/\d{4})")),
		"invoice_number": _first(clean, r"Invoice Number\s*:?\s*([A-Z0-9/.-]+)"),
		"gross_amount": _number_value(_first(clean, r"Gross Amount of Transaction(?:\s*\([^)]*\))?\s*:?\s*([\d,]+(?:\.\d+)?)")),
		"withholding_tax_rate": _number_value(_first(clean, r"Withholding Tax Rate\s*:?\s*([\d.]+)")),
		"tax_withheld_amount": _number_value(_first(clean, r"Amount of Tax Withheld(?:\s*\([^)]*\))?\s*:?\s*([\d,]+(?:\.\d+)?)")),
	}

	# KRA's PDF extraction may place the serial immediately before the label.
	if not data["certificate_serial_number"]:
		data["certificate_serial_number"] = _first(clean, r"\b(KRA[A-Z0-9]{12,})\b")

	missing = [
		field
		for field in ("certificate_serial_number", "withholder_pin", "withholdee_pin", "tax_withheld_amount")
		if not data.get(field)
	]
	if missing:
		raise frappe.ValidationError(_("Could not extract required certificate fields: {0}").format(", ".join(missing)))

	return data


def find_sales_invoice(invoice_number: str, company: str | None = None, customer: str | None = None) -> str | None:
	"""Find a Sales Invoice using the ERPNext name or a known eTIMS invoice-number field."""
	filters = {}
	if company:
		filters["company"] = company
	if customer:
		filters["customer"] = customer

	if frappe.db.exists("Sales Invoice", {**filters, "name": invoice_number}):
		return invoice_number

	meta = frappe.get_meta("Sales Invoice")
	candidate_fields = (
		"etr_invoice_number",
		"custom_etr_invoice_number",
		"etims_invoice_number",
		"custom_etims_invoice_number",
		"cu_invoice_number",
		"custom_cu_invoice_number",
	)
	for fieldname in candidate_fields:
		if meta.has_field(fieldname):
			match = frappe.db.get_value("Sales Invoice", {**filters, fieldname: invoice_number}, "name")
			if match:
				return match
	return None


def _normalize_text(text: str) -> str:
	text = text.replace("\r\n", "\n").replace("\r", "\n")
	text = re.sub(r"[ \t]+", " ", text)
	text = re.sub(r"\n{3,}", "\n\n", text)
	return text.strip()


def _first(text: str, pattern: str) -> str | None:
	match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
	return match.group(1).strip() if match else None


def _line_value(text: str, label: str) -> str | None:
	return _first(text, rf"{re.escape(label)}\s*:?\s*([^\n]+)")


def _block_value(text: str, label: str, stop_labels: list[str]) -> str | None:
	stops = "|".join(re.escape(value) for value in stop_labels)
	match = re.search(
		rf"{re.escape(label)}\s*:?\s*(.*?)(?=\n\s*(?:{stops})\b|$)",
		text,
		flags=re.IGNORECASE | re.DOTALL,
	)
	if not match:
		return None
	value = re.sub(r"\s*\n\s*", " ", match.group(1)).strip(" ,")
	return value or None


def _date_value(value: str | None):
	if not value:
		return None
	try:
		day, month, year = value.split("/")
		return getdate(f"{year}-{int(month):02d}-{int(day):02d}")
	except (TypeError, ValueError):
		return None


def _number_value(value: str | None) -> float | None:
	if value in (None, ""):
		return None
	return flt(str(value).replace(",", ""))
