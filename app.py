from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from pathlib import Path
from datetime import datetime
import os

try:
    from sklearn.ensemble import IsolationForest
    import numpy as np
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-development-key")
DB_PATH = Path(__file__).with_name("inventory.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'General',
            channel TEXT NOT NULL DEFAULT 'All channels',
            quantity INTEGER NOT NULL DEFAULT 0,
            reorder_level INTEGER NOT NULL DEFAULT 5,
            price REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            customer TEXT NOT NULL,
            channel TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Confirmed',
            created_at TEXT NOT NULL,
            FOREIGN KEY(product_id) REFERENCES products(id)
        );
        CREATE TABLE IF NOT EXISTS movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            change_amount INTEGER NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(product_id) REFERENCES products(id)
        );
        """)
        count = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if count == 0:
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            sample = [
                ("SKU-1001", "Wireless Mouse", "Electronics", "Website", 42, 10, 599),
                ("SKU-1002", "Mechanical Keyboard", "Electronics", "Amazon", 18, 8, 1799),
                ("SKU-1003", "USB-C Hub", "Accessories", "Flipkart", 7, 10, 1299),
                ("SKU-1004", "Laptop Stand", "Accessories", "Website", 31, 8, 899),
                ("SKU-1005", "Bluetooth Speaker", "Electronics", "Amazon", 4, 10, 1499),
            ]
            db.executemany("""INSERT INTO products
                (sku,name,category,channel,quantity,reorder_level,price,created_at)
                VALUES (?,?,?,?,?,?,?,?)""", [( *p, now) for p in sample])
            ids = [r[0] for r in db.execute("SELECT id FROM products ORDER BY id").fetchall()]
            db.executemany("""INSERT INTO movements(product_id,change_amount,reason,created_at)
                VALUES (?,?,?,?)""", [
                (ids[0], 20, "Initial stock", now),
                (ids[1], 8, "Initial stock", now),
                (ids[2], -3, "Sales adjustment", now),
                (ids[3], 12, "Initial stock", now),
                (ids[4], -6, "Sales adjustment", now),
            ])

def get_alerts(db):
    low = db.execute("""SELECT * FROM products
        WHERE quantity <= reorder_level ORDER BY quantity ASC""").fetchall()
    return low

@app.route("/")
def dashboard():
    with get_db() as db:
        stats = {
            "products": db.execute("SELECT COUNT(*) FROM products").fetchone()[0],
            "units": db.execute("SELECT COALESCE(SUM(quantity),0) FROM products").fetchone()[0],
            "orders": db.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
            "alerts": len(get_alerts(db))
        }
        products = db.execute("SELECT * FROM products ORDER BY quantity ASC LIMIT 6").fetchall()
        recent_orders = db.execute("""SELECT orders.*, products.name AS product_name
            FROM orders JOIN products ON products.id=orders.product_id
            ORDER BY orders.id DESC LIMIT 5""").fetchall()
    return render_template("dashboard.html", stats=stats, products=products, recent_orders=recent_orders)

@app.route("/products", methods=["GET", "POST"])
def products():
    if request.method == "POST":
        sku = request.form.get("sku", "").strip()
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "General").strip()
        channel = request.form.get("channel", "All channels").strip()
        try:
            quantity = int(request.form.get("quantity", 0))
            reorder = int(request.form.get("reorder_level", 5))
            price = float(request.form.get("price", 0))
            if not sku or not name or quantity < 0 or reorder < 0 or price < 0:
                raise ValueError
            with get_db() as db:
                cur = db.execute("""INSERT INTO products
                    (sku,name,category,channel,quantity,reorder_level,price,created_at)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (sku,name,category,channel,quantity,reorder,price,datetime.now().strftime("%Y-%m-%d %H:%M")))
                db.execute("INSERT INTO movements(product_id,change_amount,reason,created_at) VALUES (?,?,?,?)",
                    (cur.lastrowid, quantity, "Product created / opening stock", datetime.now().strftime("%Y-%m-%d %H:%M")))
            flash("Product added successfully.", "success")
        except sqlite3.IntegrityError:
            flash("That SKU already exists. Please use a unique SKU.", "error")
        except (ValueError, TypeError):
            flash("Please enter valid values. Quantity, reorder level and price cannot be negative.", "error")
        return redirect(url_for("products"))
    with get_db() as db:
        rows = db.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    return render_template("products.html", products=rows)

@app.route("/stock/<int:product_id>", methods=["POST"])
def adjust_stock(product_id):
    try:
        change = int(request.form.get("change", "0"))
        reason = request.form.get("reason", "Manual stock update").strip() or "Manual stock update"
        if change == 0:
            raise ValueError
        with get_db() as db:
            product = db.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
            if product is None:
                flash("Product not found.", "error")
            elif product["quantity"] + change < 0:
                flash("Stock cannot become negative.", "error")
            else:
                db.execute("UPDATE products SET quantity=quantity+? WHERE id=?", (change, product_id))
                db.execute("INSERT INTO movements(product_id,change_amount,reason,created_at) VALUES (?,?,?,?)",
                    (product_id, change, reason, datetime.now().strftime("%Y-%m-%d %H:%M")))
                flash("Stock updated successfully.", "success")
    except ValueError:
        flash("Enter a non-zero whole number for the stock change.", "error")
    return redirect(url_for("products"))

@app.route("/orders", methods=["GET", "POST"])
def orders():
    if request.method == "POST":
        try:
            product_id = int(request.form["product_id"])
            quantity = int(request.form["quantity"])
            customer = request.form["customer"].strip()
            channel = request.form["channel"]
            if quantity <= 0 or not customer:
                raise ValueError
            with get_db() as db:
                product = db.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
                if not product:
                    flash("Select a valid product.", "error")
                elif product["quantity"] < quantity:
                    flash(f"Not enough stock. Available: {product['quantity']}.", "error")
                else:
                    db.execute("""INSERT INTO orders(product_id,quantity,customer,channel,status,created_at)
                        VALUES (?,?,?,?,?,?)""",
                        (product_id, quantity, customer, channel, "Confirmed", datetime.now().strftime("%Y-%m-%d %H:%M")))
                    db.execute("UPDATE products SET quantity=quantity-? WHERE id=?", (quantity, product_id))
                    db.execute("""INSERT INTO movements(product_id,change_amount,reason,created_at)
                        VALUES (?,?,?,?)""",
                        (product_id, -quantity, f"Order placed by {customer}", datetime.now().strftime("%Y-%m-%d %H:%M")))
                    flash("Order placed and inventory updated.", "success")
        except (ValueError, KeyError):
            flash("Please enter valid order details.", "error")
        return redirect(url_for("orders"))
    with get_db() as db:
        products = db.execute("SELECT * FROM products ORDER BY name").fetchall()
        orders = db.execute("""SELECT orders.*, products.name AS product_name, products.sku
            FROM orders JOIN products ON products.id=orders.product_id ORDER BY orders.id DESC""").fetchall()
    return render_template("orders.html", products=products, orders=orders)

@app.route("/alerts")
def alerts():
    with get_db() as db:
        low_stock = get_alerts(db)
        recent_movements = db.execute("""SELECT movements.*, products.name AS product_name, products.sku
            FROM movements JOIN products ON products.id=movements.product_id
            ORDER BY movements.id DESC LIMIT 30""").fetchall()
    return render_template("alerts.html", low_stock=low_stock, movements=recent_movements)

@app.route("/ml-detection", methods=["GET", "POST"])
def ml_detection():
    results = []
    model_message = "Machine learning checks recent stock movements for unusual changes."
    with get_db() as db:
        products = db.execute("SELECT * FROM products").fetchall()
        movements = db.execute("""SELECT movements.*, products.name AS product_name, products.sku
            FROM movements JOIN products ON products.id=movements.product_id
            ORDER BY movements.id DESC LIMIT 100""").fetchall()
        for m in movements:
            results.append({
                "name": m["product_name"], "sku": m["sku"],
                "change": m["change_amount"], "reason": m["reason"],
                "date": m["created_at"], "anomaly": False
            })
    if len(results) >= 5 and ML_AVAILABLE:
        X = np.array([[abs(r["change"]), 1 if r["change"] < 0 else 0] for r in results])
        model = IsolationForest(contamination=0.15, random_state=42)
        predictions = model.fit_predict(X)
        for item, prediction in zip(results, predictions):
            item["anomaly"] = prediction == -1
        model_message = "Isolation Forest model trained on recorded stock movements. Review flagged records before taking action."
    else:
        for item in results:
            item["anomaly"] = abs(item["change"]) >= 10
        model_message = ("Not enough movement records for Isolation Forest yet; showing a basic large-change rule."
                         if ML_AVAILABLE else "Scikit-learn is not installed; showing a basic large-change rule.")
    low_count = sum(1 for p in products if p["quantity"] <= p["reorder_level"])
    return render_template("ml.html", movements=results, low_count=low_count,
                           anomaly_count=sum(1 for r in results if r["anomaly"]),
                           model_message=model_message, ml_available=ML_AVAILABLE)

@app.route("/reports")
def reports():
    with get_db() as db:
        rows = db.execute("""SELECT category, COUNT(*) AS products,
            SUM(quantity) AS units, ROUND(SUM(quantity*price),2) AS value
            FROM products GROUP BY category ORDER BY value DESC""").fetchall()
        total_value = db.execute("SELECT COALESCE(ROUND(SUM(quantity*price),2),0) FROM products").fetchone()[0]
    return render_template("reports.html", rows=rows, total_value=total_value)

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
