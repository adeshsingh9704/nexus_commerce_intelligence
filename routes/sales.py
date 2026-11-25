
import uuid
from datetime import datetime, timezone

from flask import Blueprint, render_template, request, redirect, url_for, flash
from db import db

sales_bp = Blueprint("sales", __name__, url_prefix="/sales")

orders = db["orders"]
products = db["products"]
customers = db["customers"]
movements = db["inventory_movements"]


def generate_id(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


@sales_bp.route("/")
def list_orders():
    records = list(
        orders.find({}, {"_id": 0})
        .sort("order_date", -1)
        .limit(300)
    )

    return render_template(
        "sales/orders.html",
        orders=records
    )


@sales_bp.route("/new", methods=["GET", "POST"])
def new_order():

    product_list = list(
        products.find({}, {"_id": 0}).sort("name", 1)
    )

    customer_list = list(
        customers.find({}, {"_id": 0}).sort("name", 1)
    )

    if request.method == "POST":

        customer_id = request.form.get("customer_id", "").strip()
        product_id = request.form.get("product_id", "").strip()
        channel = request.form.get("channel", "physical_store")

        try:
            quantity = int(request.form.get("quantity", "0"))
        except ValueError:
            quantity = 0

        if quantity <= 0:
            flash("Enter a valid quantity.", "error")
            return redirect(url_for("sales.new_order"))

        if channel not in ("online", "physical_store"):
            flash("Invalid sales channel.", "error")
            return redirect(url_for("sales.new_order"))

        product = products.find_one({"product_id": product_id})

        if not product:
            flash("Product not found.", "error")
            return redirect(url_for("sales.new_order"))

        customer = None

        if customer_id:
            customer = customers.find_one(
                {"customer_id": customer_id}
            )

            if not customer:
                flash("Customer not found.", "error")
                return redirect(url_for("sales.new_order"))

        available_stock = int(product.get("stock", 0))

        if available_stock < quantity:
            flash(
                f"Insufficient stock. Available: {available_stock}",
                "error"
            )
            return redirect(url_for("sales.new_order"))

        currency = product.get("currency", "INR")

        selling_price = float(
            product.get("selling_price",
                        product.get("unit_selling_price", 0))
        )

        cost_price = float(
            product.get("cost_price",
                        product.get("unit_cost", 0))
        )

        revenue = selling_price * quantity
        total_cost = cost_price * quantity

        order_id = generate_id("ORD")
        now = datetime.now(timezone.utc)

        # Deduct stock only if sufficient stock remains.
        stock_result = products.update_one(
            {
                "product_id": product_id,
                "stock": {"$gte": quantity}
            },
            {
                "$inc": {"stock": -quantity},
                "$set": {"updated_at": now}
            }
        )

        if stock_result.modified_count != 1:
            flash("Stock changed. Please try again.", "error")
            return redirect(url_for("sales.new_order"))

        order = {
            "order_id": order_id,
            "customer_id": customer_id or None,
            "customer_name": (
                customer.get("name") if customer else "Walk-in customer"
            ),
            "channel": channel,
            "currency": currency,
            "source": "manual",
            "order_date": now,
            "status": "completed",
            "items": [{
                "product_id": product_id,
                "product_name": product["name"],
                "category": product.get("category", ""),
                "quantity": quantity,
                "unit_price": selling_price,
                "unit_cost": cost_price,
                "line_revenue": revenue,
                "line_cost": total_cost
            }],
            "total_revenue": revenue,
            "total_cost": total_cost,
            "total_amount": revenue,
            "gross_profit": revenue - total_cost
        }

        try:
            orders.insert_one(order)

            movements.insert_one({
                "movement_id": generate_id("MOV"),
                "product_id": product_id,
                "product_name": product["name"],
                "movement_type": "sale",
                "quantity_change": -quantity,
                "reference_id": order_id,
                "created_at": now,
                "source": "manual"
            })

        except Exception:
            # Restore stock if saving the order or movement fails.
            products.update_one(
                {"product_id": product_id},
                {"$inc": {"stock": quantity}}
            )
            orders.delete_one({"order_id": order_id})
            movements.delete_one({"reference_id": order_id})
            raise

        flash(f"Sale completed successfully: {order_id}", "success")

        return redirect(url_for("sales.list_orders"))

    return render_template(
        "sales/new_order.html",
        products=product_list,
        customers=customer_list
    )
