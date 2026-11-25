from flask import Flask, jsonify, render_template
from routes.customers import customers_bp
from routes.product import products_bp
from routes.sales import sales_bp
from routes.modules import modules_bp
from config import SECRET_KEY, FLASK_DEBUG
from db import db, check_connection

app = Flask(__name__)
app.register_blueprint(customers_bp)
app.register_blueprint(products_bp)
app.register_blueprint(sales_bp)
app.register_blueprint(modules_bp)
app.config["SECRET_KEY"] = SECRET_KEY
app.config["DEBUG"] = FLASK_DEBUG

@app.get("/")
def dashboard():
    ok, message = check_connection()
    if not ok:
        return render_template("dashboard.html", connected=False, message=message,
                               customer_count=0, product_count=0, order_count=0,
                               revenue=0, recent_orders=[])
    # Stage 1 demo KPIs are INR-only synthetic records. Real GBP imports are excluded.
    demo_filter = {"source": "synthetic_demo", "currency": "INR"}
    customer_count = db.customers.count_documents({"source": "synthetic_demo"})
    product_count = db.products.count_documents({"source": "synthetic_demo"})
    order_count = db.orders.count_documents(demo_filter)
    pipeline = [
        {"$match": demo_filter},
        {"$group": {"_id": None, "revenue": {"$sum": "$total_revenue"}}}
    ]
    result = list(db.orders.aggregate(pipeline))
    revenue = result[0]["revenue"] if result else 0
    recent_orders = list(db.orders.find(demo_filter, {"_id": 0}).sort("order_date", -1).limit(8))
    return render_template("dashboard.html", connected=True, message=message,
                           customer_count=customer_count, product_count=product_count,
                           order_count=order_count, revenue=round(revenue, 2),
                           recent_orders=recent_orders)

@app.get("/api/health")
def health():
    ok, message = check_connection()
    return jsonify({"database_connected": ok, "message": message}), (200 if ok else 503)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=app.config["DEBUG"])
