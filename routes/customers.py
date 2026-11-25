
import re
import uuid
from datetime import datetime, timezone

from flask import Blueprint, render_template, request, redirect, url_for, flash
from pymongo.errors import DuplicateKeyError

from db import db

customers_bp = Blueprint("customers", __name__, url_prefix="/customers")

customers = db["customers"]


def generate_customer_id():
    return "CUS-" + uuid.uuid4().hex[:8].upper()


@customers_bp.route("/")
def customer_list():
    search = request.args.get("q", "").strip()

    query = {}
    if search:
        safe_search = re.escape(search)
        query = {
            "$or": [
                {"name": {"$regex": safe_search, "$options": "i"}},
                {"phone": {"$regex": safe_search, "$options": "i"}},
                {"customer_id": {"$regex": safe_search, "$options": "i"}},
            ]
        }

    records = list(
        customers.find(query, {"_id": 0})
        .sort("created_at", -1)
        .limit(200)
    )

    return render_template(
        "customers/list.html",
        customers=records,
        search=search,
        total=customers.count_documents({})
    )


@customers_bp.route("/add", methods=["GET", "POST"])
def add_customer():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip().lower()
        city = request.form.get("city", "").strip()

        if not name or not phone:
            flash("Customer name and phone number are required.", "error")
            return render_template("customers/form.html")

        existing = customers.find_one({"phone": phone})
        if existing:
            flash("A customer with this phone number already exists.", "error")
            return render_template("customers/form.html")

        customer = {
            "customer_id": generate_customer_id(),
            "name": name,
            "phone": phone,
            "email": email,
            "city": city,
            "created_at": datetime.now(timezone.utc),
            "source": "manual",
            "currency": "INR"
        }

        try:
            customers.insert_one(customer)
        except DuplicateKeyError:
            flash("This customer record already exists.", "error")
            return render_template("customers/form.html")

        flash("Customer added successfully!", "success")
        return redirect(url_for("customers.customer_list"))

    return render_template("customers/form.html")


@customers_bp.route("/<customer_id>")
def customer_detail(customer_id):
    customer = customers.find_one(
        {"customer_id": customer_id},
        {"_id": 0}
    )

    if not customer:
        flash("Customer not found.", "error")
        return redirect(url_for("customers.customer_list"))

    orders = list(
        db["orders"].find(
            {"customer_id": customer_id},
            {"_id": 0}
        ).sort("order_date", -1).limit(100)
    )

    return render_template(
        "customers/detail.html",
        customer=customer,
        orders=orders
    )


@customers_bp.route("/<customer_id>/delete", methods=["POST"])
def delete_customer(customer_id):
    result = customers.delete_one({"customer_id": customer_id})

    if result.deleted_count:
        flash("Customer deleted successfully.", "success")
    else:
        flash("Customer not found.", "error")

    return redirect(url_for("customers.customer_list"))
