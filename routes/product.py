
import re
import uuid
from datetime import datetime, timezone

from flask import Blueprint, render_template, request, redirect, url_for, flash
from db import db

products_bp = Blueprint("products", __name__, url_prefix="/products")
products_collection = db["products"]


def generate_product_id():
    return "PRD-" + uuid.uuid4().hex[:8].upper()


def product_for_display(product):
    """Support common price field names in existing demo records."""
    product["display_cost"] = product.get(
        "cost_price", product.get("unit_cost", 0)
    )
    product["display_price"] = product.get(
        "selling_price", product.get("unit_selling_price", 0)
    )
    product["display_stock"] = product.get("stock", 0)
    product["display_reorder"] = product.get("reorder_level", 10)
    return product


@products_bp.route("/")
def product_list():
    search = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()

    query = {}

    if search:
        safe_search = re.escape(search)
        query["$or"] = [
            {"product_id": {"$regex": safe_search, "$options": "i"}},
            {"name": {"$regex": safe_search, "$options": "i"}},
            {"category": {"$regex": safe_search, "$options": "i"}},
        ]

    all_products = [
        product_for_display(p)
        for p in products_collection.find(query, {"_id": 0}).sort("name", 1)
    ]

    if status == "out":
        all_products = [p for p in all_products if p["display_stock"] <= 0]
    elif status == "low":
        all_products = [
            p for p in all_products
            if 0 < p["display_stock"] <= p["display_reorder"]
        ]

    total = products_collection.count_documents({})
    low_count = sum(
        1 for p in all_products
        if 0 < p["display_stock"] <= p["display_reorder"]
    )
    out_count = sum(1 for p in all_products if p["display_stock"] <= 0)

    return render_template(
        "products/list.html",
        products=all_products,
        search=search,
        status=status,
        total=total,
        low_count=low_count,
        out_count=out_count
    )


@products_bp.route("/add", methods=["GET", "POST"])
def add_product():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()

        try:
            cost_price = float(request.form.get("cost_price", "0"))
            selling_price = float(request.form.get("selling_price", "0"))
            stock = int(request.form.get("stock", "0"))
            reorder_level = int(request.form.get("reorder_level", "10"))
        except ValueError:
            flash("Enter valid numbers for prices and stock.", "error")
            return render_template("products/form.html", product=None)

        if not name or not category:
            flash("Product name and category are required.", "error")
            return render_template("products/form.html", product=None)

        if min(cost_price, selling_price, stock, reorder_level) < 0:
            flash("Prices and stock values cannot be negative.", "error")
            return render_template("products/form.html", product=None)

        product = {
            "product_id": generate_product_id(),
            "name": name,
            "category": category,
            "cost_price": cost_price,
            "selling_price": selling_price,
            "stock": stock,
            "reorder_level": reorder_level,
            "currency": "INR",
            "source": "manual",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }

        products_collection.insert_one(product)
        flash("Product added successfully!", "success")
        return redirect(url_for("products.product_list"))

    return render_template("products/form.html", product=None)


@products_bp.route("/<product_id>/edit", methods=["GET", "POST"])
def edit_product(product_id):
    product = products_collection.find_one({"product_id": product_id})

    if not product:
        flash("Product not found.", "error")
        return redirect(url_for("products.product_list"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()

        try:
            cost_price = float(request.form.get("cost_price", "0"))
            selling_price = float(request.form.get("selling_price", "0"))
            stock = int(request.form.get("stock", "0"))
            reorder_level = int(request.form.get("reorder_level", "10"))
        except ValueError:
            flash("Enter valid numbers for prices and stock.", "error")
            return render_template(
                "products/form.html",
                product=product_for_display(product)
            )

        if not name or not category:
            flash("Product name and category are required.", "error")
            return render_template(
                "products/form.html",
                product=product_for_display(product)
            )

        if min(cost_price, selling_price, stock, reorder_level) < 0:
            flash("Prices and stock values cannot be negative.", "error")
            return render_template(
                "products/form.html",
                product=product_for_display(product)
            )

        products_collection.update_one(
            {"product_id": product_id},
            {"$set": {
                "name": name,
                "category": category,
                "cost_price": cost_price,
                "selling_price": selling_price,
                "stock": stock,
                "reorder_level": reorder_level,
                "updated_at": datetime.now(timezone.utc)
            }}
        )

        flash("Product updated successfully!", "success")
        return redirect(url_for("products.product_list"))

    return render_template(
        "products/form.html",
        product=product_for_display(product)
    )
