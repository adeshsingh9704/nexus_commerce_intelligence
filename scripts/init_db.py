import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from db import db, check_connection

ok, message = check_connection()
print(message)
if not ok:
    raise SystemExit("Start the MongoDB service and run this script again.")

collections = [
    "customers", "products", "orders", "payments",
    "inventory_movements", "customer_visits", "suppliers", "dataset_imports"
]
existing = set(db.list_collection_names())
for name in collections:
    if name not in existing:
        db.create_collection(name)
        print(f"Created collection: {name}")

indexes = [
    ("customers", [("customer_id", 1)], {"unique": True}),
    ("customers", [("name", 1)], {}),
    ("customers", [("email", 1)], {"sparse": True}),
    ("products", [("product_id", 1)], {"unique": True}),
    ("products", [("name", 1)], {}),
    ("products", [("category", 1), ("stock_quantity", 1)], {}),
    ("orders", [("order_id", 1)], {"unique": True}),
    ("orders", [("customer_id", 1), ("order_date", -1)], {}),
    ("orders", [("channel", 1), ("order_date", -1)], {}),
    ("orders", [("source", 1), ("currency", 1)], {}),
    ("payments", [("payment_id", 1)], {"unique": True}),
    ("payments", [("order_id", 1)], {}),
    ("inventory_movements", [("product_id", 1), ("created_at", -1)], {}),
    ("customer_visits", [("customer_id", 1), ("visit_time", -1)], {}),
    ("suppliers", [("supplier_id", 1)], {"unique": True}),
    ("dataset_imports", [("dataset_name", 1)], {"unique": True}),
]
for collection, keys, options in indexes:
    db[collection].create_index(keys, **options)
print("Database initialization complete.")
print("Collections:", ", ".join(collections))
