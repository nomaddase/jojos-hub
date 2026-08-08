#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else "/home/admini/jojos-core")
orders = root / "app/modules/orders/routes.py"
text = orders.read_text(encoding="utf-8")

old = '''            effective_price = (
                0
                if catalog_group["mode"] == "single" or selection_index == 0
                else int(catalog_option["price"])
            )'''
new = '''            effective_price = (
                0
                if catalog_group["mode"] == "single"
                or (catalog_group["mode"] == "multi" and selection_index == 0)
                else int(catalog_option["price"])
            )'''

if old in text:
    text = text.replace(old, new)
elif new not in text:
    raise SystemExit("prepare-runtime: option pricing block not found")

orders.write_text(text, encoding="utf-8")
print("Prepared Hub runtime: paid_multi add-ons always use configured price")
