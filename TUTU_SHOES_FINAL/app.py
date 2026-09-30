import os
import secrets
from werkzeug.utils import secure_filename
from decimal import Decimal, InvalidOperation
from functools import wraps

import mysql.connector
from dotenv import load_dotenv
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-only-change-me")
UPLOAD_FOLDER = os.path.join(
    app.root_path,
    "static",
    "uploads",
    "products"
)

ALLOWED_IMAGE_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "webp"
}

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)


def allowed_image(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_IMAGE_EXTENSIONS
    )

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DATABASE", "tutu_shoes"),
}


def db_connection(use_database=True):
    cfg = DB_CONFIG.copy()

    if not use_database:
        cfg.pop("database", None)

    return mysql.connector.connect(**cfg)


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def init_database():
    """Create database and tables for local development."""

    # -----------------------------------------------------
    # Create database
    # -----------------------------------------------------
    conn = db_connection(use_database=False)
    cur = conn.cursor()

    cur.execute(
        f"CREATE DATABASE IF NOT EXISTS `{DB_CONFIG['database']}` "
        "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
    )

    cur.close()
    conn.close()

    # -----------------------------------------------------
    # Create tables
    # -----------------------------------------------------
    conn = db_connection()
    cur = conn.cursor()

    statements = [

        # -------------------------------------------------
        # ADMIN USERS
        # -------------------------------------------------
        """
        CREATE TABLE IF NOT EXISTS admin_users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            role VARCHAR(50) NOT NULL DEFAULT 'Owner Admin',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,

        # -------------------------------------------------
        # PRODUCTS
        # -------------------------------------------------
        """
        CREATE TABLE IF NOT EXISTS products (
            id INT AUTO_INCREMENT PRIMARY KEY,
            product_name VARCHAR(255) NOT NULL,
            brand VARCHAR(100),
            category VARCHAR(100) NOT NULL,
            gender VARCHAR(50) NOT NULL,
            description TEXT,
            price DECIMAL(10,2) NOT NULL,
            stock_quantity INT NOT NULL DEFAULT 0,
            sizes VARCHAR(255),
            colors VARCHAR(255),
            image_url VARCHAR(500),
            status ENUM('Active','Inactive') NOT NULL DEFAULT 'Active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ON UPDATE CURRENT_TIMESTAMP,

            INDEX idx_products_category (category),
            INDEX idx_products_gender (gender),
            INDEX idx_products_status (status),
            INDEX idx_products_brand (brand)
        )
        """,

        # -------------------------------------------------
        # ORDERS
        # -------------------------------------------------
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INT AUTO_INCREMENT PRIMARY KEY,

            order_id VARCHAR(50) UNIQUE NOT NULL,

            customer_id INT NULL,

            customer_name VARCHAR(100) NOT NULL,
            phone VARCHAR(20) NOT NULL,

            address TEXT NOT NULL,
            city VARCHAR(100) NOT NULL,
            district VARCHAR(100) NOT NULL,
            state VARCHAR(100) NOT NULL,
            pincode VARCHAR(10) NOT NULL,

            product_name VARCHAR(255),
            quantity INT DEFAULT 0,

            total_amount DECIMAL(10,2) NOT NULL,

            payment_method VARCHAR(50)
                NOT NULL DEFAULT 'Prepaid',

            payment_status VARCHAR(50)
                NOT NULL DEFAULT 'Pending',

            order_status VARCHAR(50)
                NOT NULL DEFAULT 'Pending',

            courier_name VARCHAR(100),
            tracking_number VARCHAR(150),

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ON UPDATE CURRENT_TIMESTAMP,

            INDEX idx_orders_customer_id (customer_id),
            INDEX idx_orders_status (order_status),
            INDEX idx_orders_created (created_at)
        )
        """,

        # -------------------------------------------------
        # ORDER ITEMS
        # -------------------------------------------------
        """
        CREATE TABLE IF NOT EXISTS order_items (
            id INT AUTO_INCREMENT PRIMARY KEY,

            order_id INT NOT NULL,

            product_id INT NULL,

            product_name VARCHAR(255) NOT NULL,
            brand VARCHAR(100),

            size VARCHAR(20),
            color VARCHAR(50),

            quantity INT NOT NULL,

            unit_price DECIMAL(10,2) NOT NULL,
            line_total DECIMAL(10,2) NOT NULL,

            FOREIGN KEY (order_id)
                REFERENCES orders(id)
                ON DELETE CASCADE,

            FOREIGN KEY (product_id)
                REFERENCES products(id)
                ON DELETE SET NULL
        )
        """,

        # -------------------------------------------------
        # CUSTOMERS
        # -------------------------------------------------
        """
        CREATE TABLE IF NOT EXISTS customers (
            id INT AUTO_INCREMENT PRIMARY KEY,

            full_name VARCHAR(100) NOT NULL,

            email VARCHAR(150) UNIQUE NOT NULL,

            phone VARCHAR(20),

            password_hash VARCHAR(255) NOT NULL,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    ]

    for statement in statements:
        cur.execute(statement)

    conn.commit()

    cur.close()
    conn.close()

    # -----------------------------------------------------
    # DATABASE COMPATIBILITY
    #
    # Existing orders table may already exist without
    # customer_id/product_name/quantity.
    #
    # Add missing columns automatically.
    # -----------------------------------------------------
    conn = db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT COUNT(*)
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = %s
        AND TABLE_NAME = 'orders'
        AND COLUMN_NAME = 'customer_id'
        """,
        (DB_CONFIG["database"],)
    )

    customer_id_exists = cur.fetchone()[0]

    if not customer_id_exists:
        cur.execute(
            """
            ALTER TABLE orders
            ADD COLUMN customer_id INT NULL
            """
        )

        cur.execute(
            """
            CREATE INDEX idx_orders_customer_id
            ON orders(customer_id)
            """
        )

    # -----------------------------------------------------
    # product_name compatibility
    # -----------------------------------------------------
    cur.execute(
        """
        SELECT COUNT(*)
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = %s
        AND TABLE_NAME = 'orders'
        AND COLUMN_NAME = 'product_name'
        """,
        (DB_CONFIG["database"],)
    )

    product_name_exists = cur.fetchone()[0]

    if not product_name_exists:
        cur.execute(
            """
            ALTER TABLE orders
            ADD COLUMN product_name VARCHAR(255)
            """
        )

    # -----------------------------------------------------
    # quantity compatibility
    # -----------------------------------------------------
    cur.execute(
        """
        SELECT COUNT(*)
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = %s
        AND TABLE_NAME = 'orders'
        AND COLUMN_NAME = 'quantity'
        """,
        (DB_CONFIG["database"],)
    )

    quantity_exists = cur.fetchone()[0]

    if not quantity_exists:
        cur.execute(
            """
            ALTER TABLE orders
            ADD COLUMN quantity INT DEFAULT 0
            """
        )

    conn.commit()

    cur.close()
    conn.close()


# =========================================================
# ADMIN AUTH DECORATOR
# =========================================================

def admin_required(view):

    @wraps(view)
    def wrapped(*args, **kwargs):

        if "admin_id" not in session:
            return redirect(url_for("admin_login"))

        return view(*args, **kwargs)

    return wrapped


# =========================================================
# GLOBAL DATA
# =========================================================

@app.context_processor
def inject_globals():

    return {
        "categories": [
            "Formal",
            "Sneakers",
            "Sports Shoes",
            "Crocs",
            "Sliders"
        ],

        "genders": [
            "Men",
            "Women",
            "Kids",
            "Unisex"
        ],
    }


# =========================================================
# CUSTOMER SIDE
# =========================================================

@app.route("/")
def home():

    conn = db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute(
        """
        SELECT *
        FROM products
        WHERE status='Active'
        ORDER BY created_at DESC
        LIMIT 12
        """
    )

    products = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "index.html",
        products=products
    )


# ---------------------------------------------------------
# PRODUCTS
# ---------------------------------------------------------

@app.route("/products")
def products():

    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()
    gender = request.args.get("gender", "").strip()

    conn = db_connection()
    cur = conn.cursor(dictionary=True)

    query = """
        SELECT *
        FROM products
        WHERE status='Active'
    """

    params = []

    if search:

        query += """
            AND (
                product_name LIKE %s
                OR brand LIKE %s
            )
        """

        params.extend([
            f"%{search}%",
            f"%{search}%"
        ])

    if category:

        query += """
            AND category = %s
        """

        params.append(category)

    if gender:

        query += """
            AND gender = %s
        """

        params.append(gender)

    query += """
        ORDER BY created_at DESC
    """

    cur.execute(query, params)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "products.html",
        products=rows,
        search=search,
        selected_category=category,
        selected_gender=gender,
    )


# ---------------------------------------------------------
# PRODUCT DETAILS
# ---------------------------------------------------------

@app.route("/product/<int:product_id>")
def product_detail(product_id):

    conn = db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute(
        """
        SELECT *
        FROM products
        WHERE id=%s
        AND status='Active'
        """,
        (product_id,)
    )

    product = cur.fetchone()

    cur.close()
    conn.close()

    if not product:
        return "Product not found", 404

    return render_template(
        "product.html",
        product=product
    )


# ---------------------------------------------------------
# CART
# ---------------------------------------------------------

@app.route("/cart")
def cart():

    return render_template("cart.html")


# ---------------------------------------------------------
# CHECKOUT
# ---------------------------------------------------------

@app.route("/checkout")
def checkout():

    return render_template("checkout.html")


# ---------------------------------------------------------
# ORDER SUCCESS
# ---------------------------------------------------------

@app.route("/order-success/<order_id>")
def order_success(order_id):

    conn = db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute(
        """
        SELECT *
        FROM orders
        WHERE order_id=%s
        """,
        (order_id,)
    )

    order = cur.fetchone()

    cur.close()
    conn.close()

    if not order:
        return "Order not found", 404

    return render_template(
        "order_success.html",
        order=order
    )


# =========================================================
# CREATE ORDER API
# =========================================================

@app.post("/api/orders")
def create_order():

    data = request.get_json(silent=True) or {}

    required = [
        "customer_name",
        "phone",
        "address",
        "city",
        "district",
        "state",
        "pincode",
        "items"
    ]

    if any(not data.get(key) for key in required):

        return jsonify({
            "success": False,
            "message": "Missing required fields"
        }), 400

    items = data.get("items")

    if not isinstance(items, list) or not items:

        return jsonify({
            "success": False,
            "message": "Cart is empty"
        }), 400

    conn = db_connection()
    cur = conn.cursor(dictionary=True)

    try:

        # -------------------------------------------------
        # Customer ID
        #
        # If customer is logged in, connect order to
        # customer account.
        #
        # Guest checkout remains allowed.
        # -------------------------------------------------

        customer_id = session.get("customer_id")

        # -------------------------------------------------
        # Product IDs
        # -------------------------------------------------

        product_ids = [
            int(item["product_id"])
            for item in items
        ]

        placeholders = ",".join(
            ["%s"] * len(product_ids)
        )

        cur.execute(
            f"""
            SELECT *
            FROM products
            WHERE id IN ({placeholders})
            AND status='Active'
            FOR UPDATE
            """,
            product_ids
        )

        db_products = {
            row["id"]: row
            for row in cur.fetchall()
        }

        total = Decimal("0.00")

        clean_items = []

        # -------------------------------------------------
        # Validate cart
        # -------------------------------------------------

        for item in items:

            pid = int(item["product_id"])

            qty = int(
                item.get("quantity", 0)
            )

            if qty < 1 or pid not in db_products:

                raise ValueError(
                    "Invalid cart item"
                )

            product = db_products[pid]

            if product["stock_quantity"] < qty:

                raise ValueError(
                    f"Insufficient stock for "
                    f"{product['product_name']}"
                )

            unit_price = Decimal(
                str(product["price"])
            )

            line_total = unit_price * qty

            total += line_total

            clean_items.append({

                "product": product,

                "quantity": qty,

                "size": str(
                    item.get("size", "")
                )[:20],

                "color": str(
                    item.get("color", "")
                )[:50],

                "unit_price": unit_price,

                "line_total": line_total
            })

        # -------------------------------------------------
        # Generate Order ID
        # -------------------------------------------------

        order_id = (
            "TUTU-"
            + secrets.token_hex(5).upper()
        )

        # -------------------------------------------------
        # First product name
        #
        # Kept for compatibility with existing
        # orders table.
        # -------------------------------------------------

        first_product_name = (
            clean_items[0]["product"]["product_name"]
            if clean_items
            else ""
        )

        total_quantity = sum(
            item["quantity"]
            for item in clean_items
        )

        # -------------------------------------------------
        # Insert Order
        # -------------------------------------------------

        cur.execute(
            """
            INSERT INTO orders
            (
                order_id,
                customer_id,

                customer_name,
                phone,

                address,
                city,
                district,
                state,
                pincode,

                product_name,
                quantity,

                total_amount,

                payment_method,
                payment_status,
                order_status
            )

            VALUES
            (
                %s,
                %s,

                %s,
                %s,

                %s,
                %s,
                %s,
                %s,
                %s,

                %s,
                %s,

                %s,

                %s,
                %s,
                %s
            )
            """,

            (
                order_id,
                customer_id,

                data["customer_name"].strip(),
                data["phone"].strip(),

                data["address"].strip(),
                data["city"].strip(),
                data["district"].strip(),
                data["state"].strip(),
                data["pincode"].strip(),

                first_product_name,
                total_quantity,

                total,

                "Prepaid",
                "Test Paid",
                "Pending"
            )
        )

        order_db_id = cur.lastrowid

        # -------------------------------------------------
        # Insert Order Items + Deduct Stock
        # -------------------------------------------------

        for item in clean_items:

            product = item["product"]

            # ---------------------------------------------
            # ORDER ITEM
            # ---------------------------------------------

            cur.execute(
                """
                INSERT INTO order_items
                (
                    order_id,
                    product_id,
                    product_name,
                    brand,
                    size,
                    color,
                    quantity,
                    unit_price,
                    line_total
                )

                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,

                (
                    order_db_id,

                    product["id"],

                    product["product_name"],

                    product["brand"],

                    item["size"],

                    item["color"],

                    item["quantity"],

                    item["unit_price"],

                    item["line_total"]
                )
            )

            # ---------------------------------------------
            # STOCK DEDUCTION
            # ---------------------------------------------

            cur.execute(
                """
                UPDATE products
                SET stock_quantity =
                    stock_quantity - %s
                WHERE id=%s
                """,

                (
                    item["quantity"],
                    product["id"]
                )
            )

        # -------------------------------------------------
        # Commit
        # -------------------------------------------------

        conn.commit()

        return jsonify({

            "success": True,

            "order_id": order_id,

            "message":
                "Order placed successfully"
        })

    except (
        ValueError,
        KeyError,
        InvalidOperation
    ) as exc:

        conn.rollback()

        return jsonify({

            "success": False,

            "message": str(exc)

        }), 400

    except Exception as exc:

        conn.rollback()

        print(
            "ORDER ERROR:",
            repr(exc)
        )

        return jsonify({

            "success": False,

            "message":
                "Could not create order"

        }), 500

    finally:

        cur.close()
        conn.close()


# =========================================================
# CUSTOMER ORDER HISTORY
# =========================================================

@app.route("/customer/orders")
def customer_orders():

    # -----------------------------------------------------
    # Login required
    # -----------------------------------------------------

    if "customer_id" not in session:

        return redirect(
            url_for("customer_login")
        )

    customer_id = session["customer_id"]

    conn = db_connection()
    cur = conn.cursor(dictionary=True)

    try:

        cur.execute(
            """
            SELECT
                order_id,
                total_amount,
                payment_method,
                payment_status,
                order_status,
                courier_name,
                tracking_number,
                created_at

            FROM orders

            WHERE customer_id=%s

            ORDER BY created_at DESC
            """,

            (customer_id,)
        )

        orders = cur.fetchall()

    finally:

        cur.close()
        conn.close()

    return render_template(
        "customer_orders.html",
        orders=orders
    )


# =========================================================
# CUSTOMER ORDER TRACKING
# =========================================================

@app.route("/customer/orders/<order_id>")
def customer_order_tracking(order_id):

    # -----------------------------------------------------
    # Login required
    # -----------------------------------------------------

    if "customer_id" not in session:

        return redirect(
            url_for("customer_login")
        )

    customer_id = session["customer_id"]

    conn = db_connection()
    cur = conn.cursor(dictionary=True)

    try:

        cur.execute(
            """
            SELECT *
            FROM orders

            WHERE order_id=%s
            AND customer_id=%s
            """,

            (
                order_id,
                customer_id
            )
        )

        order = cur.fetchone()

    finally:

        cur.close()
        conn.close()

    if not order:

        return "Order not found", 404

    # -----------------------------------------------------
    # Order Status Progress
    # -----------------------------------------------------

    statuses = [
        "Pending",
        "Confirmed",
        "Packed",
        "Shipped",
        "Delivered"
    ]

    current_status = order["order_status"]

    return render_template(
        "customer_order_tracking.html",

        order=order,

        statuses=statuses,

        current_status=current_status
    )


# =========================================================
# ADMIN
# =========================================================

# ---------------------------------------------------------
# SETUP ADMIN
# ---------------------------------------------------------

@app.route(
    "/setup-admin",
    methods=["GET", "POST"]
)
def setup_admin():

    """
    One-time local setup.
    Disable/remove before production.
    """

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        if (
            not username
            or len(password) < 8
        ):

            return render_template(
                "setup_admin.html",

                error=(
                    "Username required and "
                    "password must be at least "
                    "8 characters."
                )
            )

        conn = db_connection()
        cur = conn.cursor()

        try:

            cur.execute(
                """
                INSERT INTO admin_users
                (
                    username,
                    password_hash,
                    role
                )

                VALUES
                (
                    %s,
                    %s,
                    %s
                )
                """,

                (
                    username,

                    generate_password_hash(
                        password
                    ),

                    "Owner Admin"
                )
            )

            conn.commit()

            return redirect(
                url_for("admin_login")
            )

        except mysql.connector.IntegrityError:

            return render_template(
                "setup_admin.html",

                error=
                    "Username already exists."
            )

        finally:

            cur.close()
            conn.close()

    return render_template(
        "setup_admin.html"
    )


# ---------------------------------------------------------
# ADMIN LOGIN
# ---------------------------------------------------------

@app.route(
    "/admin/login",
    methods=["GET", "POST"]
)
def admin_login():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        conn = db_connection()
        cur = conn.cursor(
            dictionary=True
        )

        cur.execute(
            """
            SELECT *
            FROM admin_users
            WHERE username=%s
            """,

            (username,)
        )

        admin = cur.fetchone()

        cur.close()
        conn.close()

        if (
            admin
            and check_password_hash(
                admin["password_hash"],
                password
            )
        ):

            session.clear()

            session["admin_id"] = (
                admin["id"]
            )

            session["admin_username"] = (
                admin["username"]
            )

            session["admin_role"] = (
                admin["role"]
            )

            return redirect(
                url_for("admin_dashboard")
            )

        return render_template(
            "admin_login.html",

            error=
                "Invalid username or password."
        )

    return render_template(
        "admin_login.html"
    )


# ---------------------------------------------------------
# ADMIN LOGOUT
# ---------------------------------------------------------

@app.post("/admin/logout")
@admin_required
def admin_logout():

    session.clear()

    return redirect(
        url_for("admin_login")
    )


# ---------------------------------------------------------
# ADMIN DASHBOARD
# ---------------------------------------------------------

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():

    conn = db_connection()
    cur = conn.cursor(
        dictionary=True
    )

    # Total orders
    cur.execute(
        """
        SELECT COUNT(*) AS count
        FROM orders
        """
    )

    total_orders = (
        cur.fetchone()["count"]
    )

    # Confirmed orders
    cur.execute(
        """
        SELECT COUNT(*) AS count
        FROM orders
        WHERE order_status='Confirmed'
        """
    )

    confirmed_orders = (
        cur.fetchone()["count"]
    )

    # Pending orders
    cur.execute(
        """
        SELECT COUNT(*) AS count
        FROM orders
        WHERE order_status='Pending'
        """
    )

    pending_orders = (
        cur.fetchone()["count"]
    )

    # Total sales
    cur.execute(
        """
        SELECT
            COALESCE(
                SUM(total_amount),
                0
            ) AS total

        FROM orders

        WHERE payment_status='Test Paid'
        """
    )

    total_sales = (
        cur.fetchone()["total"]
    )

    # Total products
    cur.execute(
        """
        SELECT COUNT(*) AS count
        FROM products
        """
    )

    total_products = (
        cur.fetchone()["count"]
    )

    # Active products
    cur.execute(
        """
        SELECT COUNT(*) AS count
        FROM products
        WHERE status='Active'
        """
    )

    active_products = (
        cur.fetchone()["count"]
    )

    cur.close()
    conn.close()

    return render_template(

        "admin_dashboard.html",

        total_orders=total_orders,

        confirmed_orders=
            confirmed_orders,

        pending_orders=
            pending_orders,

        total_sales=total_sales,

        total_products=
            total_products,

        active_products=
            active_products,
    )


# =========================================================
# ADMIN PRODUCTS
# =========================================================

@app.route("/admin/products")
@admin_required
def admin_products():

    search = request.args.get(
        "search",
        ""
    ).strip()

    category = request.args.get(
        "category",
        ""
    ).strip()

    gender = request.args.get(
        "gender",
        ""
    ).strip()

    status = request.args.get(
        "status",
        ""
    ).strip()

    conn = db_connection()

    cur = conn.cursor(
        dictionary=True
    )

    query = """
        SELECT *
        FROM products
        WHERE 1=1
    """

    params = []

    if search:

        query += """
            AND (
                product_name LIKE %s
                OR brand LIKE %s
            )
        """

        params.extend([
            f"%{search}%",
            f"%{search}%"
        ])

    if category:

        query += """
            AND category=%s
        """

        params.append(category)

    if gender:

        query += """
            AND gender=%s
        """

        params.append(gender)

    if status:

        query += """
            AND status=%s
        """

        params.append(status)

    query += """
        ORDER BY created_at DESC
    """

    cur.execute(
        query,
        params
    )

    products_rows = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(

        "admin_products.html",

        products=products_rows,

        search=search,

        selected_category=
            category,

        selected_gender=
            gender,

        selected_status=
            status,
    )


# ---------------------------------------------------------
# ADD PRODUCT
# ---------------------------------------------------------

@app.route("/admin/products/add", methods=["GET", "POST"])
@admin_required
def add_product():
    if request.method == "GET":
        return render_template("admin_add_product.html")

    form = request.form

    product_name = form.get("product_name", "").strip()
    brand = form.get("brand", "").strip()
    category = form.get("category", "").strip()
    gender = form.get("gender", "").strip()
    description = form.get("description", "").strip()
    price = form.get("price")
    stock = form.get("stock_quantity")
    sizes = form.get("sizes", "").strip()
    colors = form.get("colors", "").strip()
    status = form.get("status", "Active")

    if (
        not product_name
        or not category
        or not gender
        or price is None
        or stock is None
    ):
        return "Please fill all required fields.", 400

    # Default: no image
    image_url = ""

    # Handle product image upload
    image = request.files.get("product_image")

    if image and image.filename:
        if not allowed_image(image.filename):
            return "Invalid image format. Use JPG, JPEG, PNG or WEBP.", 400

        filename = secure_filename(image.filename)

        extension = filename.rsplit(".", 1)[1].lower()

        # Generate unique filename
        filename = f"{secrets.token_hex(8)}.{extension}"

        # Save image
        image.save(
            os.path.join(
                UPLOAD_FOLDER,
                filename
            )
        )

        # Store relative path in database
        image_url = f"uploads/products/{filename}"

    conn = db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO products
            (
                product_name,
                brand,
                category,
                gender,
                description,
                price,
                stock_quantity,
                sizes,
                colors,
                image_url,
                status
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                product_name,
                brand,
                category,
                gender,
                description,
                price,
                stock,
                sizes,
                colors,
                image_url,
                status
            )
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()

    return redirect(url_for("admin_products"))


# ---------------------------------------------------------
# EDIT PRODUCT
# ---------------------------------------------------------

@app.route(
    "/admin/products/edit/<int:product_id>",
    methods=["GET", "POST"]
)
@app.route(
    "/admin/products/edit/<int:product_id>",
    methods=["GET", "POST"]
)
@admin_required
def edit_product(product_id):

    conn = db_connection()
    cur = conn.cursor(dictionary=True)

    # GET → Show edit page
    if request.method == "GET":

        cur.execute(
            "SELECT * FROM products WHERE id=%s",
            (product_id,)
        )

        product = cur.fetchone()

        cur.close()
        conn.close()

        if not product:
            return "Product not found", 404

        return render_template(
            "admin_edit_product.html",
            product=product
        )

    # POST → Update product
    form = request.form

    product_name = form.get("product_name", "").strip()
    brand = form.get("brand", "").strip()
    category = form.get("category", "").strip()
    gender = form.get("gender", "").strip()
    description = form.get("description", "").strip()
    price = form.get("price")
    stock = form.get("stock_quantity")
    sizes = form.get("sizes", "").strip()
    colors = form.get("colors", "").strip()
    status = form.get("status", "Active")

    if (
        not product_name
        or not category
        or not gender
        or price is None
        or stock is None
    ):
        cur.close()
        conn.close()
        return "Please fill all required fields.", 400

    # Get existing image
    cur.execute(
        "SELECT image_url FROM products WHERE id=%s",
        (product_id,)
    )

    existing_product = cur.fetchone()

    image_url = ""

    if existing_product:
        image_url = existing_product.get("image_url") or ""

    # Check for new uploaded image
    image = request.files.get("product_image")

    if image and image.filename:

        if not allowed_image(image.filename):
            cur.close()
            conn.close()
            return "Invalid image format. Use JPG, JPEG, PNG or WEBP.", 400

        filename = secure_filename(image.filename)

        extension = filename.rsplit(".", 1)[1].lower()

        # Generate unique filename
        filename = f"{secrets.token_hex(8)}.{extension}"

        # Save new image
        image.save(
            os.path.join(
                UPLOAD_FOLDER,
                filename
            )
        )

        # Save relative path
        image_url = f"uploads/products/{filename}"

    # Update product
    cur.execute(
        """
        UPDATE products SET
            product_name=%s,
            brand=%s,
            category=%s,
            gender=%s,
            description=%s,
            price=%s,
            stock_quantity=%s,
            sizes=%s,
            colors=%s,
            image_url=%s,
            status=%s
        WHERE id=%s
        """,
        (
            product_name,
            brand,
            category,
            gender,
            description,
            price,
            stock,
            sizes,
            colors,
            image_url,
            status,
            product_id
        )
    )

    conn.commit()

    cur.close()
    conn.close()

    return redirect(
        url_for("admin_products")
    )


# ---------------------------------------------------------
# DEACTIVATE PRODUCT
# ---------------------------------------------------------

@app.post(
    "/admin/products/deactivate/<int:product_id>"
)
@admin_required
def deactivate_product(product_id):

    conn = db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE products
        SET status='Inactive'
        WHERE id=%s
        """,

        (product_id,)
    )

    conn.commit()

    cur.close()
    conn.close()

    return redirect(
        url_for("admin_products")
    )


# ---------------------------------------------------------
# ACTIVATE PRODUCT
# ---------------------------------------------------------

@app.post(
    "/admin/products/activate/<int:product_id>"
)
@admin_required
def activate_product(product_id):

    conn = db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE products
        SET status='Active'
        WHERE id=%s
        """,

        (product_id,)
    )

    conn.commit()

    cur.close()
    conn.close()

    return redirect(
        url_for("admin_products")
    )


# =========================================================
# ADMIN ORDERS
# =========================================================

@app.route("/admin/orders")
@admin_required
def admin_orders():

    status = request.args.get(
        "status",
        ""
    ).strip()

    conn = db_connection()

    cur = conn.cursor(
        dictionary=True
    )

    if status:

        cur.execute(
            """
            SELECT *
            FROM orders
            WHERE order_status=%s
            ORDER BY created_at DESC
            """,

            (status,)
        )

    else:

        cur.execute(
            """
            SELECT *
            FROM orders
            ORDER BY created_at DESC
            """
        )

    orders_rows = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(

        "admin_orders.html",

        orders=orders_rows,

        selected_status=
            status
    )


# ---------------------------------------------------------
# UPDATE ORDER STATUS
# ---------------------------------------------------------

@app.post(
    "/admin/orders/update-status"
)
@admin_required
def update_order_status():

    order_id = request.form.get(
        "order_id"
    )

    order_status = request.form.get(
        "order_status"
    )

    allowed = [

        "Pending",

        "Confirmed",

        "Packed",

        "Shipped",

        "Delivered",

        "Cancelled"
    ]

    if order_status not in allowed:

        return (
            "Invalid order status",
            400
        )

    conn = db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE orders

        SET order_status=%s

        WHERE order_id=%s
        """,

        (
            order_status,
            order_id
        )
    )

    conn.commit()

    cur.close()
    conn.close()

    return redirect(
        url_for("admin_orders")
    )


# ---------------------------------------------------------
# UPDATE COURIER
# ---------------------------------------------------------

@app.post(
    "/admin/orders/update-courier"
)
@admin_required
def update_courier():

    order_id = request.form.get(
        "order_id"
    )

    courier = request.form.get(
        "courier_name",
        ""
    ).strip()

    tracking = request.form.get(
        "tracking_number",
        ""
    ).strip()

    conn = db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE orders

        SET
            courier_name=%s,
            tracking_number=%s

        WHERE order_id=%s
        """,

        (
            courier,
            tracking,
            order_id
        )
    )

    conn.commit()

    cur.close()
    conn.close()

    return redirect(
        url_for("admin_orders")
    )


# =========================================================
# CUSTOMER AUTHENTICATION
# =========================================================

# ---------------------------------------------------------
# CUSTOMER SIGNUP
# ---------------------------------------------------------

@app.route(
    "/customer/signup",
    methods=["GET", "POST"]
)
def customer_signup():

    if request.method == "POST":

        full_name = request.form.get(
            "full_name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        if (
            not full_name
            or not email
            or not password
        ):

            return render_template(

                "customer_signup.html",

                error=(
                    "Name, email and password "
                    "are required."
                )
            )

        conn = db_connection()

        cur = conn.cursor(
            dictionary=True
        )

        try:

            # ---------------------------------------------
            # Check existing account
            # ---------------------------------------------

            cur.execute(
                """
                SELECT id
                FROM customers
                WHERE email=%s
                """,

                (email,)
            )

            existing = cur.fetchone()

            if existing:

                return render_template(

                    "customer_signup.html",

                    error=(
                        "An account with this "
                        "email already exists."
                    )
                )

            # ---------------------------------------------
            # Hash password
            # ---------------------------------------------

            password_hash = (
                generate_password_hash(
                    password
                )
            )

            # ---------------------------------------------
            # Create customer
            # ---------------------------------------------

            cur.execute(
                """
                INSERT INTO customers
                (
                    full_name,
                    email,
                    phone,
                    password_hash
                )

                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,

                (
                    full_name,
                    email,
                    phone,
                    password_hash
                )
            )

            conn.commit()

            return redirect(
                url_for("customer_login")
            )

        except Exception as exc:

            conn.rollback()

            print(
                "CUSTOMER SIGNUP ERROR:",
                repr(exc)
            )

            return render_template(

                "customer_signup.html",

                error=
                    "Could not create account."
            )

        finally:

            cur.close()
            conn.close()

    return render_template(
        "customer_signup.html"
    )


# ---------------------------------------------------------
# CUSTOMER LOGIN
# ---------------------------------------------------------

@app.route(
    "/customer/login",
    methods=["GET", "POST"]
)
def customer_login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        conn = db_connection()

        cur = conn.cursor(
            dictionary=True
        )

        try:

            cur.execute(
                """
                SELECT *
                FROM customers
                WHERE email=%s
                """,

                (email,)
            )

            customer = cur.fetchone()

        finally:

            cur.close()
            conn.close()

        if (
            customer
            and check_password_hash(
                customer["password_hash"],
                password
            )
        ):

            session["customer_id"] = (
                customer["id"]
            )

            session["customer_name"] = (
                customer["full_name"]
            )

            session["customer_email"] = (
                customer["email"]
            )

            return redirect(
                url_for("home")
            )

        return render_template(

            "customer_login.html",

            error=
                "Invalid email or password."
        )

    return render_template(
        "customer_login.html"
    )


# ---------------------------------------------------------
# CUSTOMER LOGOUT
# ---------------------------------------------------------

@app.route("/customer/logout")
def customer_logout():

    session.pop(
        "customer_id",
        None
    )

    session.pop(
        "customer_name",
        None
    )

    session.pop(
        "customer_email",
        None
    )

    return redirect(
        url_for("home")
    )


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    init_database()

    app.run(
        debug=True
    )