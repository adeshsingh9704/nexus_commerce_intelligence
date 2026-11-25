
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from datetime import datetime, timedelta
from bson import ObjectId
from db import db
import csv
import io

modules_bp = Blueprint("modules", __name__)

products = db["products"]
orders = db["orders"]
movements = db["inventory_movements"]
suppliers = db["suppliers"]
purchase_orders = db["purchase_orders"]


# ---------------- COMMON HELPERS ----------------

def number(value, default=0):
    try:
        return float(value or 0)
    except (ValueError, TypeError):
        return default


def money(value):
    return round(number(value), 2)


def order_total(order):
    return money(
        order.get("total_amount")
        or order.get("grand_total")
        or order.get("total")
        or 0
    )


def order_date(order):
    value = order.get("created_at") or order.get("order_date")
    if isinstance(value, datetime):
        return value
    return None


def product_label(product):
    return product.get("name", "Unknown product")


def page(title, subtitle, headers=None, rows=None, cards=None,
         fields=None, form_action=None, extra=None):
    return render_template(
        "modules/page.html",
        title=title,
        subtitle=subtitle,
        headers=headers or [],
        rows=rows or [],
        cards=cards or [],
        fields=fields or [],
        form_action=form_action,
        extra=extra or {}
    )


# ---------------- INVENTORY ----------------

@modules_bp.route("/inventory/")
def inventory():
    all_products = list(products.find().sort("name", 1))
    rows = []
    low_count = 0
    out_count = 0
    total_units = 0

    for p in all_products:
        stock = int(number(p.get("stock")))
        reorder = int(number(p.get("reorder_level")))
        total_units += stock

        status = "Healthy"
        if stock <= 0:
            status = "Out of stock"
            out_count += 1
        elif stock <= reorder:
            status = "Low stock"
            low_count += 1

        rows.append({
            "cells": [
                product_label(p),
                p.get("category", "-"),
                stock,
                reorder,
                p.get("currency", "INR"),
                status
            ]
        })

    return page(
        "Inventory Management",
        "Monitor stock levels and record inventory adjustments.",
        ["Product", "Category", "Available", "Reorder level", "Currency", "Status"],
        rows,
        [
            {"label": "Total products", "value": len(all_products)},
            {"label": "Units in stock", "value": total_units},
            {"label": "Low stock", "value": low_count},
            {"label": "Out of stock", "value": out_count}
        ],
        [
            {"name": "product_id", "label": "Product", "type": "select",
             "options": [{"value": str(p["_id"]), "label": product_label(p)}
                         for p in all_products]},
            {"name": "change", "label": "Stock change (+/-)", "type": "number"},
            {"name": "reason", "label": "Reason", "type": "text"}
        ],
        url_for("modules.adjust_inventory")
    )


@modules_bp.route("/inventory/adjust", methods=["POST"])
def adjust_inventory():
    product_id = request.form.get("product_id", "")
    change = request.form.get("change", "")
    reason = request.form.get("reason", "").strip() or "Manual adjustment"

    try:
        product = products.find_one({"_id": ObjectId(product_id)})
        qty_change = int(change)
    except Exception:
        product = None
        qty_change = 0

    if not product or qty_change == 0:
        flash("Select a valid product and enter a non-zero stock change.", "danger")
        return redirect(url_for("modules.inventory"))

    current_stock = int(number(product.get("stock")))
    new_stock = current_stock + qty_change

    if new_stock < 0:
        flash("Stock cannot become negative.", "danger")
        return redirect(url_for("modules.inventory"))

    result = products.update_one(
        {"_id": product["_id"], "stock": product.get("stock", 0)},
        {"$set": {"stock": new_stock, "updated_at": datetime.utcnow()}}
    )

    if result.modified_count != 1:
        flash("Stock changed elsewhere. Refresh and try again.", "warning")
        return redirect(url_for("modules.inventory"))

    movements.insert_one({
        "product_id": str(product["_id"]),
        "product_name": product_label(product),
        "movement_type": "manual_adjustment",
        "quantity_change": qty_change,
        "stock_before": current_stock,
        "stock_after": new_stock,
        "reason": reason,
        "source": "manual",
        "created_at": datetime.utcnow()
    })

    flash("Inventory updated successfully.", "success")
    return redirect(url_for("modules.inventory"))


# ---------------- ANALYTICS ----------------

@modules_bp.route("/analytics/")
def analytics():
    currency_totals = {}
    product_sales = {}
    customer_orders = {}
    daily_sales = {}

    for order in orders.find():
        currency = order.get("currency", "INR")
        amount = order_total(order)
        currency_totals.setdefault(currency, {
            "revenue": 0, "orders": 0
        })
        currency_totals[currency]["revenue"] += amount
        currency_totals[currency]["orders"] += 1

        customer = str(order.get("customer_id") or order.get("customer_name") or "Guest")
        customer_orders[customer] = customer_orders.get(customer, 0) + 1

        dt = order_date(order)
        if dt:
            day = dt.strftime("%Y-%m-%d")
            daily_sales.setdefault((currency, day), 0)
            daily_sales[(currency, day)] += amount

        # Supports both single-product orders and orders with an items array.
        items = order.get("items") or []
        if items:
            for item in items:
                name = item.get("product_name") or item.get("name") or "Unknown"
                qty = int(number(item.get("quantity"), 0))
                product_sales[name] = product_sales.get(name, 0) + qty
        else:
            name = order.get("product_name") or order.get("name")
            if name:
                qty = int(number(order.get("quantity"), 0))
                product_sales[name] = product_sales.get(name, 0) + qty

    currency_cards = [
        {
            "label": f"{currency} revenue",
            "value": f"{money(values['revenue']):,.2f}"
        }
        for currency, values in sorted(currency_totals.items())
    ]
    currency_cards += [
        {
            "label": f"{currency} orders",
            "value": values["orders"]
        }
        for currency, values in sorted(currency_totals.items())
    ]

    top_products = sorted(product_sales.items(), key=lambda x: x[1], reverse=True)[:10]
    rows = [{"cells": [name, qty]} for name, qty in top_products]

    customer_count = len(customer_orders)
    repeat_customers = sum(1 for count in customer_orders.values() if count > 1)

    return page(
        "Commerce Analytics",
        "Sales and customer indicators. Different currencies are shown separately.",
        ["Best-selling product", "Units sold"],
        rows,
        currency_cards + [
            {"label": "Customers with orders", "value": customer_count},
            {"label": "Repeat customers", "value": repeat_customers}
        ]
    )


# ---------------- SALES FORECASTING ----------------

@modules_bp.route("/forecasting/")
def forecasting():
    now = datetime.utcnow()
    start = now - timedelta(days=30)

    sales_by_product = {}

    for order in orders.find():
        dt = order_date(order)
        if not dt or dt < start:
            continue

        items = order.get("items") or []
        if items:
            for item in items:
                pid = str(item.get("product_id") or "")
                qty = int(number(item.get("quantity")))
                if pid:
                    sales_by_product[pid] = sales_by_product.get(pid, 0) + qty
        else:
            pid = str(order.get("product_id") or "")
            qty = int(number(order.get("quantity")))
            if pid:
                sales_by_product[pid] = sales_by_product.get(pid, 0) + qty

    rows = []
    for p in products.find():
        pid = str(p["_id"])
        sold = sales_by_product.get(pid, 0)
        daily_velocity = sold / 30
        stock = int(number(p.get("stock")))
        reorder = int(number(p.get("reorder_level")))
        days_left = round(stock / daily_velocity, 1) if daily_velocity > 0 else None

        lead_time = int(number(p.get("lead_time_days"), 7))
        target_stock = max(reorder, int(round(daily_velocity * (lead_time + 7))))
        suggested = max(0, target_stock - stock)

        if daily_velocity == 0:
            status = "Insufficient recent sales"
        elif days_left is not None and days_left <= lead_time:
            status = "Reorder urgently"
        elif stock <= reorder:
            status = "Below reorder level"
        else:
            status = "Stock appears sufficient"

        rows.append({
            "cells": [
                product_label(p),
                sold,
                round(daily_velocity, 2),
                stock,
                f"{days_left} days" if days_left is not None else "N/A",
                suggested,
                status
            ]
        })

    return page(
        "AI Demand & Stock Forecast",
        "Baseline estimate using the previous 30 days of recorded sales. It is not a trained ML prediction.",
        ["Product", "Units sold (30d)", "Daily velocity", "Stock", "Estimated stock cover", "Suggested reorder", "Assessment"],
        rows,
        [
            {"label": "Forecast window", "value": "30 days"},
            {"label": "Method", "value": "Sales velocity baseline"}
        ]
    )


# ---------------- SUPPLIERS ----------------

@modules_bp.route("/suppliers/", methods=["GET", "POST"])
def supplier_list():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        contact = request.form.get("contact", "").strip()
        email = request.form.get("email", "").strip()
        lead_time = int(number(request.form.get("lead_time_days"), 7))

        if not name:
            flash("Supplier name is required.", "danger")
        else:
            suppliers.insert_one({
                "name": name,
                "contact": contact,
                "email": email,
                "lead_time_days": max(0, lead_time),
                "source": "manual",
                "created_at": datetime.utcnow()
            })
            flash("Supplier added.", "success")
        return redirect(url_for("modules.supplier_list"))

    rows = []
    for s in suppliers.find().sort("name", 1):
        rows.append({
            "cells": [
                s.get("name", "-"),
                s.get("contact", "-"),
                s.get("email", "-"),
                s.get("lead_time_days", 7)
            ]
        })

    return page(
        "Supplier Management",
        "Maintain supplier contacts and typical replenishment lead times.",
        ["Supplier", "Contact", "Email", "Lead time (days)"],
        rows,
        [{"label": "Total suppliers", "value": suppliers.count_documents({})}],
        [
            {"name": "name", "label": "Supplier name", "type": "text"},
            {"name": "contact", "label": "Phone / contact", "type": "text"},
            {"name": "email", "label": "Email", "type": "email"},
            {"name": "lead_time_days", "label": "Lead time (days)", "type": "number", "value": "7"}
        ],
        url_for("modules.supplier_list")
    )


# ---------------- PURCHASE ORDERS ----------------

@modules_bp.route("/suppliers/purchase-orders", methods=["GET", "POST"])
def purchase_order_list():
    if request.method == "POST":
        try:
            product = products.find_one({"_id": ObjectId(request.form.get("product_id", ""))})
            supplier = suppliers.find_one({"_id": ObjectId(request.form.get("supplier_id", ""))})
            quantity = int(request.form.get("quantity", "0"))
        except Exception:
            product, supplier, quantity = None, None, 0

        if not product or not supplier or quantity <= 0:
            flash("Choose a valid product, supplier, and positive quantity.", "danger")
            return redirect(url_for("modules.purchase_order_list"))

        purchase_orders.insert_one({
            "product_id": str(product["_id"]),
            "product_name": product_label(product),
            "supplier_id": str(supplier["_id"]),
            "supplier_name": supplier.get("name"),
            "quantity": quantity,
            "status": "pending",
            "currency": product.get("currency", "INR"),
            "source": "manual",
            "created_at": datetime.utcnow()
        })
        flash("Purchase order created. Stock will change only after receiving it.", "success")
        return redirect(url_for("modules.purchase_order_list"))

    rows = []
    for po in purchase_orders.find().sort("created_at", -1):
        rows.append({
            "cells": [
                po.get("product_name", "-"),
                po.get("supplier_name", "-"),
                po.get("quantity", 0),
                po.get("status", "-"),
                po.get("created_at").strftime("%Y-%m-%d") if isinstance(po.get("created_at"), datetime) else "-"
            ],
            "action_url": (
                url_for("modules.receive_purchase_order", po_id=str(po["_id"]))
                if po.get("status") == "pending" else None
            ),
            "action_label": "Receive stock"
        })

    return page(
        "Purchase Orders",
        "Create replenishment orders and receive stock when deliveries arrive.",
        ["Product", "Supplier", "Quantity", "Status", "Created", "Action"],
        rows,
        [{"label": "Pending orders", "value": purchase_orders.count_documents({"status": "pending"})}],
        [
            {"name": "product_id", "label": "Product", "type": "select",
             "options": [{"value": str(p["_id"]), "label": product_label(p)}
                         for p in products.find()]},
            {"name": "supplier_id", "label": "Supplier", "type": "select",
             "options": [{"value": str(s["_id"]), "label": s.get("name", "Supplier")}
                         for s in suppliers.find()]},
            {"name": "quantity", "label": "Quantity", "type": "number"}
        ],
        url_for("modules.purchase_order_list")
    )


@modules_bp.route("/suppliers/purchase-orders/<po_id>/receive", methods=["POST"])
def receive_purchase_order(po_id):
    try:
        po = purchase_orders.find_one({
            "_id": ObjectId(po_id),
            "status": "pending"
        })
    except Exception:
        po = None

    if not po:
        flash("Purchase order not found or already received.", "danger")
        return redirect(url_for("modules.purchase_order_list"))

    try:
        product = products.find_one({"_id": ObjectId(po["product_id"])})
    except Exception:
        product = None

    if not product:
        flash("The product linked to this purchase order no longer exists.", "danger")
        return redirect(url_for("modules.purchase_order_list"))

    qty = int(number(po.get("quantity")))
    before = int(number(product.get("stock")))
    result = products.update_one(
        {"_id": product["_id"], "stock": product.get("stock", 0)},
        {"$inc": {"stock": qty}, "$set": {"updated_at": datetime.utcnow()}}
    )

    if result.modified_count != 1:
        flash("Stock changed elsewhere. Refresh and try again.", "warning")
        return redirect(url_for("modules.purchase_order_list"))

    updated = purchase_orders.update_one(
        {"_id": po["_id"], "status": "pending"},
        {"$set": {"status": "received", "received_at": datetime.utcnow()}}
    )

    if updated.modified_count != 1:
        products.update_one({"_id": product["_id"]}, {"$inc": {"stock": -qty}})
        flash("Could not update purchase order status; stock update was reversed.", "danger")
        return redirect(url_for("modules.purchase_order_list"))

    movements.insert_one({
        "product_id": po["product_id"],
        "product_name": po.get("product_name"),
        "movement_type": "purchase_receipt",
        "quantity_change": qty,
        "stock_before": before,
        "stock_after": before + qty,
        "reason": f"Received purchase order {po_id}",
        "source": "manual",
        "created_at": datetime.utcnow()
    })

    flash("Purchase order received and stock updated.", "success")
    return redirect(url_for("modules.purchase_order_list"))


# ---------------- REPORTS & CSV EXPORT ----------------

@modules_bp.route("/reports/")
def reports():
    return page(
        "Reports & Export",
        "Download records for analysis in Excel, Power BI, or other tools.",
        ["Report", "Description", "Download"],
        [
            {"cells": ["Orders", "Order records with currency and source"], "action_url": url_for("modules.export_orders"), "action_label": "Export CSV"},
            {"cells": ["Products", "Product catalogue and stock levels"], "action_url": url_for("modules.export_products"), "action_label": "Export CSV"},
            {"cells": ["Customers", "Customer records"], "action_url": url_for("modules.export_customers"), "action_label": "Export CSV"},
            {"cells": ["Inventory movements", "Stock adjustment and receipt history"], "action_url": url_for("modules.export_movements"), "action_label": "Export CSV"}
        ]
    )


def csv_response(filename, headers, data):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(data)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@modules_bp.route("/reports/orders.csv")
def export_orders():
    data = []
    for o in orders.find():
        data.append([
            str(o.get("_id")),
            o.get("customer_name", ""),
            o.get("product_name", ""),
            o.get("quantity", ""),
            order_total(o),
            o.get("currency", "INR"),
            o.get("channel", ""),
            o.get("source", ""),
            order_date(o).isoformat() if order_date(o) else ""
        ])
    return csv_response(
        "nexus_orders.csv",
        ["order_id", "customer", "product", "quantity", "total", "currency", "channel", "source", "created_at"],
        data
    )


@modules_bp.route("/reports/products.csv")
def export_products():
    data = [
        [str(p.get("_id")), p.get("name", ""), p.get("category", ""),
         p.get("stock", 0), p.get("reorder_level", 0),
         p.get("cost_price", 0), p.get("selling_price", 0),
         p.get("currency", "INR"), p.get("source", "")]
        for p in products.find()
    ]
    return csv_response(
        "nexus_products.csv",
        ["product_id", "name", "category", "stock", "reorder_level",
         "cost_price", "selling_price", "currency", "source"],
        data
    )


@modules_bp.route("/reports/customers.csv")
def export_customers():
    data = [
        [str(c.get("_id")), c.get("customer_id", ""), c.get("name", ""),
         c.get("phone", ""), c.get("email", ""), c.get("source", "")]
        for c in db["customers"].find()
    ]
    return csv_response(
        "nexus_customers.csv",
        ["id", "customer_id", "name", "phone", "email", "source"],
        data
    )


@modules_bp.route("/reports/inventory-movements.csv")
def export_movements():
    data = [
        [str(m.get("_id")), m.get("product_name", ""), m.get("movement_type", ""),
         m.get("quantity_change", ""), m.get("stock_before", ""),
         m.get("stock_after", ""), m.get("reason", ""),
         m.get("created_at").isoformat() if isinstance(m.get("created_at"), datetime) else ""]
        for m in movements.find().sort("created_at", -1)
    ]
    return csv_response(
        "nexus_inventory_movements.csv",
        ["id", "product", "movement_type", "quantity_change",
         "stock_before", "stock_after", "reason", "created_at"],
        data
    )
