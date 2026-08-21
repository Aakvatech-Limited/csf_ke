frappe.ui.form.on("Purchase Invoice", {
	supplier(frm) {
		if (!frm.doc.supplier) {
			return;
		}

		frappe.db.get_value("Supplier", frm.doc.supplier, "withholding_vat_rate").then((r) => {
			frm.set_value("withholding_vat_rate", flt(r.message.withholding_vat_rate || 0));
		});
	},
});
