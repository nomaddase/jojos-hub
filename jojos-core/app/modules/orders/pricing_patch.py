def install_paid_multi_pricing() -> None:
    """
    Patch the existing authoritative order normalizer so option groups with
    mode=paid_multi charge every selected option.

    Legacy modes keep their current semantics:
    - single: selected option is included in the base product price;
    - multi: first selected option is included, later selections are paid;
    - paid_multi: every selected option uses its configured catalog price.
    """
    from app.modules.orders import routes as orders_routes

    current = orders_routes.normalize_order_items
    if getattr(current, "_jojo_paid_multi_installed", False):
        return

    def patched(payload_items):
        normalized_items, inventory_map = current(payload_items)
        catalog_index = orders_routes.build_catalog_index()

        for payload_item, normalized_item in zip(payload_items, normalized_items):
            catalog_item = catalog_index.get(payload_item.item_id)
            if not catalog_item:
                continue
            for option in normalized_item.get("options") or []:
                group = catalog_item.get("options", {}).get(option.get("group_id"))
                if not group or group.get("mode") != "paid_multi":
                    continue
                catalog_option = group.get("items", {}).get(option.get("option_id"))
                if not catalog_option:
                    continue
                option["price"] = int(catalog_option.get("price") or 0)

        return normalized_items, inventory_map

    patched._jojo_paid_multi_installed = True
    orders_routes.normalize_order_items = patched
