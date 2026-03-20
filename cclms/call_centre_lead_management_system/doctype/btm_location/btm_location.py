from frappe.model.document import Document

from cclms.services.mirror.operator_deal_sync import build_address_fingerprint


class BTMLocation(Document):
    def validate(self):
        if not self.address_fingerprint:
            self.address_fingerprint = build_address_fingerprint(self.address_line1, self.zip_code)
