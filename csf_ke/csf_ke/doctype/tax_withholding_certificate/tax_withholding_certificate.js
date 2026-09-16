frappe.ui.form.on("Tax Withholding Certificate", {
	refresh(frm) {
		if (!frm.is_new() && frm.doc.source_document) {
			frm.add_custom_button(__("Extract from PDF"), () => {
				frappe.call({
					method: "csf_ke.csf_ke.doctype.tax_withholding_certificate.tax_withholding_certificate.extract_certificate",
					args: { docname: frm.doc.name },
					freeze: true,
					freeze_message: __("Extracting certificate data..."),
					callback: () => frm.reload_doc(),
				});
			});
		}
	},
});
