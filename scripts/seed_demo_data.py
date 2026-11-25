from datetime import datetime, timedelta, timezone
from random import choice, randint, uniform, seed
from uuid import uuid4
from faker import Faker
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from db import db, check_connection

seed(42)
fake = Faker("en_IN")
ok, message = check_connection()
print(message)
if not ok:
    raise SystemExit("MongoDB is not available.")

# Re-running this script replaces only its own synthetic demo records.
for name in ["customers", "products", "orders", "payments", "inventory_movements", "customer_visits", "suppliers"]:
    db[name].delete_many({"source": "synthetic_demo"})

categories = ["Electronics", "Fashion", "Home & Kitchen", "Beauty", "Sports"]
products = []
for i in range(1, 31):
    cost = round(uniform(150, 3500), 2)
    price = round(cost * uniform(1.18, 1.65), 2)
    products.append({
        "product_id": f"PRD-{i:04d}", "name": f"{choice(['Nova','Urban','Prime','Eco','Smart'])} {choice(['Bottle','Headphones','T-Shirt','Lamp','Backpack','Mixer','Watch'])} {i}",
        "category": choice(categories), "cost_price": cost, "selling_price": price,
        "stock_quantity": randint(15, 120), "reorder_level": 12,
        "currency": "INR", "source": "synthetic_demo",
        "created_at": datetime.now(timezone.utc)
    })
db.products.insert_many(products)

customers = []
for i in range(1, 81):
    customers.append({
        "customer_id": f"CUS-{i:05d}", "name": fake.name(),
        "phone": f"9{randint(100000000, 999999999)}",
        "email": f"customer{i}@example.test",
        "city": fake.city(), "source": "synthetic_demo",
        "created_at": datetime.now(timezone.utc)
    })
db.customers.insert_many(customers)

suppliers = [{
    "supplier_id": f"SUP-{i:03d}", "name": fake.company(),
    "contact_email": fake.company_email(), "lead_time_days": randint(3, 14),
    "source": "synthetic_demo"
} for i in range(1, 6)]
db.suppliers.insert_many(suppliers)

orders, movements, payments, visits = [], [], [], []
stock = {p["product_id"]: p["stock_quantity"] for p in products}
for i in range(1, 251):
    customer = choice(customers)
    order_date = datetime.now(timezone.utc) - timedelta(days=randint(0, 89), hours=randint(0, 23))
    channel = choice(["online", "physical_store"])
    item = choice(products)
    qty = randint(1, 3)
    line_revenue = round(item["selling_price"] * qty, 2)
    line_cost = round(item["cost_price"] * qty, 2)
    order_id = f"ORD-{i:06d}"
    orders.append({
        "order_id": order_id, "customer_id": customer["customer_id"],
        "order_date": order_date, "channel": channel,
        "items": [{"product_id": item["product_id"], "name": item["name"],
                   "category": item["category"], "quantity": qty,
                   "unit_selling_price": item["selling_price"],
                   "unit_cost_price": item["cost_price"],
                   "line_revenue": line_revenue, "line_cost": line_cost}],
        "total_revenue": line_revenue, "total_cost": line_cost,
        "gross_profit": round(line_revenue-line_cost, 2),
        "currency": "INR", "source": "synthetic_demo"
    })
    payments.append({"payment_id": f"PAY-{i:06d}", "order_id": order_id,
                     "amount": line_revenue, "currency": "INR",
                     "payment_status": "paid", "source": "synthetic_demo"})
    stock[item["product_id"]] = max(0, stock[item["product_id"]] - qty)
    movements.append({"movement_id": str(uuid4()), "product_id": item["product_id"],
                      "movement_type": "sale", "quantity_change": -qty,
                      "reference_id": order_id, "created_at": order_date,
                      "source": "synthetic_demo"})
    if channel == "physical_store":
        visits.append({"visit_id": str(uuid4()), "customer_id": customer["customer_id"],
                       "visit_time": order_date - timedelta(minutes=randint(2, 35)),
                       "visit_type": "purchase_visit", "source": "synthetic_demo"})
db.orders.insert_many(orders)
db.payments.insert_many(payments)
db.inventory_movements.insert_many(movements)
if visits:
    db.customer_visits.insert_many(visits)
for product_id, quantity in stock.items():
    db.products.update_one({"product_id": product_id}, {"$set": {"stock_quantity": quantity}})
print(f"Inserted {len(customers)} customers, {len(products)} products, {len(orders)} demo orders.")
print("Demo data uses INR and source=synthetic_demo. It is not real customer data.")
