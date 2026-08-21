import frappe


def execute():
	for dt, fieldname in (
		("Purchase Invoice Item", "withholding_tax_entry"),
		("Sales Invoice Item", "withholding_tax_entry"),
		("Purchase Invoice", "withholding_vat_entry"),
		("Sales Invoice", "withholding_vat_entry"),
	):
		name = f"{dt}-{fieldname}"
		if frappe.db.exists("Custom Field", name):
			frappe.db.set_value("Custom Field", name, {"fieldtype": "Data", "options": ""})

	frappe.clear_cache()
