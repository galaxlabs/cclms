frappe.pages["bitcoin-depot"].on_page_load = function () {
  frappe.route_options = {
    ...(frappe.route_options || {}),
    operator: "Bitcoin Depot",
  };
  frappe.set_route("ops-control-room");
};
