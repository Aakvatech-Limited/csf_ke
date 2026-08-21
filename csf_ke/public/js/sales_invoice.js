frappe.ui.form.on("Sales Invoice", {
	customer(frm) {
		if (!frm.doc.customer) {
			return;
		}

		frappe.db.get_value("Customer", frm.doc.customer, "withholding_vat_rate").then((r) => {
			frm.set_value("withholding_vat_rate", flt(r.message.withholding_vat_rate || 0));
		});
	},
});
