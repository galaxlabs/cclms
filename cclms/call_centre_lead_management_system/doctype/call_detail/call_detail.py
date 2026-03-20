# Copyright (c) 2026, Galaxy and contributors
# For license information, please see license.txt

from frappe.model.document import Document
from frappe.utils import get_datetime, nowdate, time_diff_in_seconds


class CallDetail(Document):
    def validate(self):
        if not self.call_date:
            self.call_date = nowdate()

        if self.start_time and self.end_time:
            start = get_datetime(self.start_time)
            end = get_datetime(self.end_time)
            self.duration = max(0, int(time_diff_in_seconds(end, start)))
