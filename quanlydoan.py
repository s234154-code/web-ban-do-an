import sqlite3
import re
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, jsonify

app = Flask(__name__)
app.secret_key = "quanlydoan_secret_key_123"
DB_NAME = "database.db"

# ================= KHỞI TẠO CƠ SỞ DỮ LIỆU =================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. Bảng món ăn
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS food (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            image_url TEXT
        )
    ''')
    
    # 2. Bảng đơn hàng
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_type TEXT NOT NULL,
            table_number TEXT,
            food_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            customer_name TEXT,
            customer_phone TEXT,
            address TEXT,
            status TEXT DEFAULT 'Pending',
            payment_method TEXT DEFAULT 'CASH',
            payment_status TEXT DEFAULT 'UNPAID',
            created_at TEXT,
            is_urgent INTEGER DEFAULT 0,
            username TEXT,
            FOREIGN KEY (food_id) REFERENCES food (id)
        )
    ''')

    # Tự động nâng cấp thêm cột is_urgent và username nếu DB cũ chưa có
    cursor.execute("PRAGMA table_info(orders)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'is_urgent' not in columns:
        cursor.execute("ALTER TABLE orders ADD COLUMN is_urgent INTEGER DEFAULT 0")
    if 'username' not in columns:
        cursor.execute("ALTER TABLE orders ADD COLUMN username TEXT")

    # 3. Bảng tài khoản
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'customer'
        )
    ''')

    # 4. Bảng cấu hình hệ thống
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')

    # Tạo tài khoản Admin mặc định
    cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO users (username, password, role) VALUES ('admin', '123456', 'admin')")

    # Cấu hình MoMo mặc định
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('momo_phone', '0855939726')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('momo_name', 'NGUYEN QUOC HUY')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('momo_qr_url', '')")

    conn.commit()
    conn.close()

def get_momo_config():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings WHERE key IN ('momo_phone', 'momo_name', 'momo_qr_url')")
    config = dict(cursor.fetchall())
    conn.close()
    return config


# ================= ĐĂNG NHẬP / ĐĂNG KÝ =================
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session["logged_in"] = True
            session["username"] = user[1]
            session["role"] = user[3]
            return redirect(url_for("admin") if user[3] in ["admin", "staff"] else url_for("index"))
        else:
            error = "Mật khẩu hoặc tên đăng nhập không đúng!"
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if password != confirm_password:
            return render_template("register.html", error="Mật khẩu xác nhận không khớp!")

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            conn.close()
            return render_template("register.html", error="Tên đăng nhập đã tồn tại!")

        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
                       (username, password, "customer"))
        conn.commit()
        conn.close()

        return redirect(url_for("login"))

    return render_template("register.html")


# ================= TRANG CHỦ & ĐẶT HÀNG =================
@app.route("/")
def index():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM food")
    foods = cursor.fetchall()

    cursor.execute("SELECT DISTINCT category FROM food WHERE category IS NOT NULL AND category != ''")
    categories = [row[0] for row in cursor.fetchall()]

    # Lấy danh sách đơn hàng của người dùng đang đăng nhập
    my_orders = []
    username = session.get("username")
    if username:
        cursor.execute('''
            SELECT orders.id, food.name, orders.quantity, (food.price * orders.quantity), orders.status, orders.created_at
            FROM orders
            JOIN food ON orders.food_id = food.id
            WHERE orders.username = ?
            ORDER BY orders.id DESC
        ''', (username,))
        my_orders = cursor.fetchall()

    conn.close()

    return render_template("index.html", foods=foods, categories=categories, my_orders=my_orders)

@app.route("/order-table", methods=["GET", "POST"])
@app.route("/table-order", methods=["GET", "POST"])
def table_order():
    if request.method == "POST":
        food_id = request.form.get("food_id")
        quantity = request.form.get("quantity", 1)
        customer_name = request.form.get("customer_name", "Khách tại bàn")
        customer_phone = request.form.get("customer_phone", "")
        address = request.form.get("address", "")
        payment_method = request.form.get("payment_method", "CASH")
        table_number = request.form.get("table_number", "1")
        order_type = "AT_TABLE"
        username = session.get("username", "")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT name, price FROM food WHERE id = ?", (food_id,))
        food = cursor.fetchone()
        
        if food:
            total_amount = food[1] * int(quantity)
            cursor.execute(
                '''INSERT INTO orders (order_type, table_number, food_id, quantity, customer_name, customer_phone, address, status, payment_method, payment_status, created_at, is_urgent, username) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending', ?, 'UNPAID', ?, 0, ?)''',
                (order_type, f"Bàn {table_number}", int(food_id), int(quantity), customer_name, customer_phone, address, payment_method, now, username)
            )
            order_id = cursor.lastrowid
            conn.commit()
            conn.close()

            if payment_method in ["MOMO", "BANK"]:
                momo_settings = get_momo_config()
                order_info = (order_id, order_type, table_number, food[0], quantity, total_amount)
                return render_template("momo_payment.html", order=order_info, momo_settings=momo_settings)

            return redirect(url_for("payment_success", order_id=order_id))
        conn.close()

    table = request.args.get("table", "1")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM food")
    foods = cursor.fetchall()
    conn.close()
    
    try:
        return render_template("table_order.html", foods=foods, table_number=table)
    except:
        options = "".join([f'<option value="{f[0]}">{f[1]} - {int(f[3]):,} VNĐ</option>' for f in foods])
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Gọi Món Tại Bàn #{table}</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: Arial, sans-serif; background: #f3f4f6; padding: 20px;">
            <div style="max-width: 500px; margin: auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                <h2 style="color: #dc2626; text-align: center;">🍽️ GỌI MÓN TẠI BÀN #{table}</h2>
                <form action="/order-table" method="POST">
                    <input type="hidden" name="table_number" value="{table}">
                    <div style="margin-bottom: 15px;">
                        <label style="display: block; margin-bottom: 5px; font-weight: bold;">Chọn Món Ăn:</label>
                        <select name="food_id" style="width: 100%; padding: 10px; border: 1px solid #ccc; border-radius: 4px;">
                            {options}
                        </select>
                    </div>
                    <div style="margin-bottom: 15px;">
                        <label style="display: block; margin-bottom: 5px; font-weight: bold;">Số Lượng:</label>
                        <input type="number" name="quantity" value="1" min="1" style="width: 100%; padding: 10px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box;">
                    </div>
                    <div style="margin-bottom: 15px;">
                        <label style="display: block; margin-bottom: 5px; font-weight: bold;">Tên Của Bạn (Tùy chọn):</label>
                        <input type="text" name="customer_name" placeholder="Nhập tên..." style="width: 100%; padding: 10px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box;">
                    </div>
                    <div style="margin-bottom: 15px;">
                        <label style="display: block; margin-bottom: 5px; font-weight: bold;">Hình Thức Thanh Toán:</label>
                        <select name="payment_method" style="width: 100%; padding: 10px; border: 1px solid #ccc; border-radius: 4px;">
                            <option value="CASH">Tiền mặt tại bàn</option>
                            <option value="BANK">Chuyển khoản / MoMo</option>
                        </select>
                    </div>
                    <button type="submit" style="width: 100%; padding: 12px; background: #dc2626; color: white; border: none; border-radius: 6px; font-weight: bold; font-size: 16px; cursor: pointer;">Gửi Yêu Cầu Cho Bếp</button>
                </form>
            </div>
        </body>
        </html>
        """

@app.route("/order-checkout", methods=["POST"])
def order_checkout():
    food_id = request.form.get("food_id")
    quantity = request.form.get("quantity", 1)
    customer_name = request.form.get("customer_name", "Khách hàng")
    customer_phone = request.form.get("customer_phone", "")
    address = request.form.get("address", "")
    payment_method = request.form.get("payment_method", "CASH")
    table_number = request.form.get("table_number", "")
    order_type = "AT_TABLE" if table_number else "ONLINE"
    username = session.get("username", "")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT name, price FROM food WHERE id = ?", (food_id,))
    food = cursor.fetchone()
    total_amount = food[1] * int(quantity) if food else 0

    cursor.execute(
        '''INSERT INTO orders (order_type, table_number, food_id, quantity, customer_name, customer_phone, address, status, payment_method, payment_status, created_at, is_urgent, username) 
           VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending', ?, 'UNPAID', ?, 0, ?)''',
        (order_type, f"Bàn {table_number}" if table_number else "", int(food_id), int(quantity), customer_name, customer_phone, address, payment_method, now, username)
    )
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()

    if payment_method in ["MOMO", "BANK"]:
        momo_settings = get_momo_config()
        order_info = (order_id, order_type, table_number, food[0] if food else "", quantity, total_amount)
        return render_template("momo_payment.html", order=order_info, momo_settings=momo_settings)

    return redirect(url_for("payment_success", order_id=order_id))


# ================= API LẤY TIẾN TRÌNH ĐƠN HÀNG =================
@app.route("/api/my-orders", methods=["POST"])
def get_my_orders():
    data = request.get_json() or {}
    order_ids = data.get("order_ids", [])
    
    if not order_ids:
        return jsonify([])

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    placeholders = ",".join(["?"] * len(order_ids))
    cursor.execute(f'''
        SELECT orders.id, food.name, orders.quantity, (food.price * orders.quantity), orders.status, orders.created_at
        FROM orders
        JOIN food ON orders.food_id = food.id
        WHERE orders.id IN ({placeholders})
        ORDER BY orders.id DESC
    ''', order_ids)
    
    rows = cursor.fetchall()
    conn.close()

    result = []
    for r in rows:
        result.append({
            "id": r[0],
            "food_name": r[1],
            "quantity": r[2],
            "total_price": r[3],
            "status": r[4],
            "created_at": r[5]
        })

    return jsonify(result)


# ================= CHECK THANH TOÁN =================
@app.route("/check-payment-status/<int:order_id>")
def check_payment_status(order_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT payment_status FROM orders WHERE id = ?", (order_id,))
    res = cursor.fetchone()
    conn.close()
    if res and res[0] == 'PAID':
        return jsonify({"status": "PAID"})
    return jsonify({"status": "UNPAID"})

@app.route("/payment-success/<int:order_id>")
def payment_success(order_id):
    return f"""
        <div style="text-align: center; font-family: sans-serif; padding: 50px;">
            <h1 style="color: #22c55e; font-size: 32px;">🎉 Đặt Hàng Thành Công!</h1>
            <p style="font-size: 18px; color: #374151;">Mã đơn hàng: <b>#{order_id}</b></p>
            <p style="color: #16a34a; font-weight: bold;">👨‍🍳 Đơn hàng đã được ghi nhận và chuyển tới Bếp!</p>
            <a href="/" style="display: inline-block; margin-top: 20px; padding: 12px 24px; background: #dc2626; color: white; text-decoration: none; border-radius: 8px; font-weight: bold;">Quay Về Trang Chủ</a>
        </div>
    """


# ================= GIAO DIỆN BẾP (KITCHEN DISPLAY) =================

    # ================= GIAO DIỆN BẾP (KITCHEN DISPLAY) =================
@app.route("/kitchen")
def kitchen():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT orders.id, orders.order_type, orders.table_number, 
               food.name, orders.quantity, orders.status, orders.payment_status, orders.created_at, food.image_url, orders.is_urgent
        FROM orders
        JOIN food ON orders.food_id = food.id
        WHERE orders.status IN ('Pending', 'Chờ', 'Cooking', 'Đang nấu')
        ORDER BY orders.is_urgent DESC, orders.id ASC
    ''')
    kitchen_orders = cursor.fetchall()
    conn.close()

    cards_html = ""
    for item in kitchen_orders:
        order_type_vn = f"📍 {item[2]}" if item[2] else "🛵 Mang về / Giao hàng"
        status_raw = item[5]
        is_urgent = item[9]
        
        # Xử lý nút bấm theo tiến trình Bếp
        if status_raw in ['Pending', 'Chờ']:
            status_vn = "⏳ Chờ chế biến"
            status_bg = "#fef3c7"
            status_color = "#d97706"
            action_btn = f'''
                <a href="/update-order-status/{item[0]}/Cooking" 
                   style="display: block; text-align: center; background: #2563eb; color: white; padding: 10px; border-radius: 8px; text-decoration: none; font-weight: bold;">
                    🔥 Bắt Đầu Nấu
                </a>
            '''
        else: # Cooking / Đang nấu
            status_vn = "🔥 Đang chế biến"
            status_bg = "#dbeafe"
            status_color = "#2563eb"
            action_btn = f'''
                <a href="/update-order-status/{item[0]}/Shipping" 
                   style="display: block; text-align: center; background: #16a34a; color: white; padding: 10px; border-radius: 8px; text-decoration: none; font-weight: bold;">
                    ✔ Chế Biến Xong (Chuyển Giao Hàng)
                </a>
            '''

        urgent_tag = '<span style="background: #ef4444; color: white; padding: 4px 10px; border-radius: 20px; font-size: 13px; font-weight: bold;">⚡ CẦN GẤP!</span>' if is_urgent else ''
        pay_raw = item[6]
        pay_vn = "✅ Đã thanh toán" if pay_raw == 'PAID' else "❌ Chưa thanh toán"
        pay_color = "#16a34a" if pay_raw == 'PAID' else "#dc2626"
        image_src = item[8] if item[8] else "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=200"

        cards_html += f"""
        <div style="background: white; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); padding: 18px; border-top: 5px solid {'#ef4444' if is_urgent else '#dc2626'}; display: flex; flex-direction: column; justify-content: space-between;">
            <div>
                <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #f3f4f6; padding-bottom: 10px; margin-bottom: 12px;">
                    <span style="font-size: 20px; font-weight: bold; color: #111827;">Mã đơn: #{item[0]}</span>
                    <div>
                        {urgent_tag}
                        <span style="background: {status_bg}; color: {status_color}; padding: 4px 10px; border-radius: 20px; font-size: 13px; font-weight: bold;">{status_vn}</span>
                    </div>
                </div>
                <div style="font-size: 15px; font-weight: 600; color: #4b5563; margin-bottom: 12px;">{order_type_vn}</div>
                
                <div style="background: #f9fafb; padding: 10px; border-radius: 8px; margin-bottom: 12px; display: flex; align-items: center; gap: 12px;">
                    <img src="{image_src}" style="width: 65px; height: 65px; object-fit: cover; border-radius: 8px; border: 1px solid #e5e7eb;">
                    <div style="flex: 1; display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-size: 16px; font-weight: bold; color: #1e3a8a;">{item[3]}</span>
                        <span style="font-size: 18px; font-weight: 800; color: #dc2626; background: #fee2e2; padding: 2px 10px; border-radius: 6px;">x{item[4]}</span>
                    </div>
                </div>
                
                <div style="font-size: 13px; color: {pay_color}; font-weight: bold; margin-bottom: 6px;">{pay_vn}</div>
                <div style="font-size: 12px; color: #9ca3af; margin-bottom: 15px;">🕒 Thời gian: {item[7]}</div>
            </div>
            {action_btn}
        </div>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Màn Hình Bếp KDS</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta http-equiv="refresh" content="5">
    </head>
    <body style="font-family: Arial, sans-serif; background: #f8fafc; margin: 0; padding: 20px;">
        <div style="max-width: 1300px; margin: auto;">
            <div style="display: flex; justify-content: space-between; align-items: center; background: #1e293b; color: white; padding: 16px 24px; border-radius: 12px; margin-bottom: 24px;">
                <div>
                    <h1 style="margin: 0; font-size: 24px;">👨‍🍳 MÀN HÌNH BẾP (KITCHEN DISPLAY)</h1>
                    <p style="margin: 5px 0 0 0; font-size: 13px; color: #94a3b8;">Tự động cập nhật sau 5s</p>
                </div>
                <a href="/admin" style="background: #3b82f6; color: white; padding: 8px 16px; border-radius: 6px; text-decoration: none; font-weight: bold; font-size: 14px;">← Trang Quản Lý Admin</a>
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 20px;">
                {cards_html if cards_html else '<div style="grid-column: 1/-1; background: white; padding: 40px; text-align: center; border-radius: 12px; color: #64748b; font-size: 18px; font-weight: bold;">🎉 Không có đơn hàng cần chế biến!</div>'}
            </div>
        </div>
    </body>
    </html>
    """

# Route cập nhật trạng thái đồng bộ
@app.route("/update-order-status/<int:order_id>/<string:status>")
def update_order_status(order_id, status):
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    conn.commit()
    conn.close()

    referrer = request.headers.get("Referer", "")
    if "kitchen" in referrer:
        return redirect(url_for("kitchen"))
    return redirect(url_for("admin"))


# ================= ADMIN & QUẢN LÝ =================
@app.route("/admin")
def admin():
    if not session.get("logged_in") or session.get("role") not in ["admin", "staff"]:
        return redirect(url_for("login"))

    user_role = session.get("role")
    date_filter = request.args.get("date_filter")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    momo_settings = get_momo_config()

    cursor.execute("SELECT * FROM food")
    foods = cursor.fetchall()

    staff_list = []
    if user_role == "admin":
        cursor.execute("SELECT id, username, role FROM users WHERE role IN ('admin', 'staff')")
        staff_list = cursor.fetchall()
    
    if date_filter:
        cursor.execute('''
            SELECT orders.id, orders.order_type, orders.table_number, 
                   food.name, orders.quantity, (food.price * orders.quantity) as total_price,
                   orders.customer_name, orders.customer_phone, orders.address, orders.status, 
                   orders.payment_method, orders.payment_status, orders.created_at, orders.is_urgent
            FROM orders
            JOIN food ON orders.food_id = food.id
            WHERE orders.created_at LIKE ?
            ORDER BY orders.id DESC
        ''', (f"{date_filter}%",))
        orders = cursor.fetchall()

        total_revenue = 0
        if user_role == "admin":
            cursor.execute("""
                SELECT SUM(food.price * orders.quantity) 
                FROM orders 
                JOIN food ON orders.food_id = food.id 
                WHERE orders.payment_status = 'PAID' AND orders.created_at LIKE ?
            """, (f"{date_filter}%",))
            revenue_res = cursor.fetchone()[0]
            total_revenue = revenue_res if revenue_res else 0

    else:
        cursor.execute('''
            SELECT orders.id, orders.order_type, orders.table_number, 
                   food.name, orders.quantity, (food.price * orders.quantity) as total_price,
                   orders.customer_name, orders.customer_phone, orders.address, orders.status, 
                   orders.payment_method, orders.payment_status, orders.created_at, orders.is_urgent
            FROM orders
            JOIN food ON orders.food_id = food.id
            ORDER BY orders.id DESC
        ''')
        orders = cursor.fetchall()

        total_revenue = 0
        if user_role == "admin":
            cursor.execute("""
                SELECT SUM(food.price * orders.quantity) 
                FROM orders 
                JOIN food ON orders.food_id = food.id 
                WHERE orders.payment_status = 'PAID'
            """)
            revenue_res = cursor.fetchone()[0]
            total_revenue = revenue_res if revenue_res else 0
    
    conn.close()
    return render_template("admin.html", 
                           foods=foods, 
                           orders=orders, 
                           total_revenue=total_revenue, 
                           staff_list=staff_list, 
                           selected_date=date_filter, 
                           momo_settings=momo_settings,
                           user_role=user_role)

@app.route("/update-momo-config", methods=["POST"])
def update_momo_config():
    if not session.get("logged_in") or session.get("role") != "admin":
        return redirect(url_for("login"))

    momo_phone = request.form.get("momo_phone")
    momo_name = request.form.get("momo_name")
    momo_qr_url = request.form.get("momo_qr_url")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('momo_phone', ?)", (momo_phone,))
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('momo_name', ?)", (momo_name,))
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('momo_qr_url', ?)", (momo_qr_url,))
    conn.commit()
    conn.close()

    return redirect(url_for("admin"))

@app.route("/mark-paid-admin/<int:order_id>")
def mark_paid_admin(order_id):
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET payment_status = 'PAID' WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin"))

@app.route("/update-order-status/<int:order_id>/<string:status>")
@app.route("/update-order-status/<int:order_id>/<string:status>")
def update_order_status_route(order_id, status):
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    
    status_map = {
        'Chờ': 'Pending',
        'Đã Giao': 'Completed',
        'Hủy': 'Cancelled',
        'Completed': 'Completed',
        'Pending': 'Pending'
    }
    # ... giữ nguyên phần code bên trong bên dưới
    final_status = status_map.get(status, status)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (final_status, order_id))
    conn.commit()
    conn.close()
    
    referrer = request.headers.get("Referer", "")
    if "kitchen" in referrer:
        return redirect(url_for("kitchen"))
    return redirect(url_for("admin"))

@app.route('/admin/update-order-status', methods=['POST'])
def update_order_status_admin():
    if session.get('role') not in ['admin', 'staff']:
        return "Unauthorized", 403

    order_id = request.form.get('order_id')
    new_status = request.form.get('status')

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
    conn.commit()
    conn.close()

    return redirect('/admin')

@app.route("/add-food", methods=["POST"])
def add_food():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    name = request.form.get("name")
    category = request.form.get("category")
    price = request.form.get("price")
    image_url = request.form.get("image_url")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO food (name, category, price, image_url) VALUES (?, ?, ?, ?)", (name, category, float(price), image_url))
    conn.commit()
    conn.close()
    return redirect(url_for("admin"))

@app.route("/edit-food/<int:food_id>", methods=["POST"])
def edit_food(food_id):
    if not session.get("logged_in") or session.get("role") not in ["admin", "staff"]:
        return redirect(url_for("login"))
    
    name = request.form.get("name")
    category = request.form.get("category")
    price = request.form.get("price")
    image_url = request.form.get("image_url")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE food 
        SET name = ?, category = ?, price = ?, image_url = ?
        WHERE id = ?
    """, (name, category, price, image_url, food_id))
    conn.commit()
    conn.close()

    return redirect(url_for("admin"))

@app.route("/delete-food/<int:food_id>")
def delete_food(food_id):
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM food WHERE id = ?", (food_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin"))

@app.route("/add-staff", methods=["POST"])
def add_staff():
    if not session.get("logged_in") or session.get("role") != "admin":
        return redirect(url_for("login"))
    username = request.form.get("username")
    password = request.form.get("password")
    role = request.form.get("role", "staff")

    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, password, role))
        conn.commit()
        conn.close()
    except sqlite3.IntegrityError:
        pass
    return redirect(url_for("admin"))

@app.route("/delete-staff/<int:user_id>")
def delete_staff(user_id):
    if not session.get("logged_in") or session.get("role") != "admin":
        return redirect(url_for("login"))
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ? AND username != 'admin'", (user_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin"))


# ================= TÍNH NĂNG GIỤC BẾP =================
@app.route("/urgent-order/<int:order_id>")
def urgent_order(order_id):
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET is_urgent = 1, status = 'Pending' WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()

    return redirect(url_for("admin"))


# ================= CASSO WEBHOOK =================
@app.route("/casso-webhook", methods=["POST"])
def casso_webhook():
    data = request.get_json()
    if not data or "data" not in data:
        return jsonify({"error": "Invalid data", "code": 400}), 400

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    for item in data["data"]:
        description = item.get("description", "")
        match = re.search(r'DON\s*(\d+)', description, re.IGNORECASE)
        if match:
            order_id = match.group(1)
            cursor.execute("UPDATE orders SET payment_status = 'PAID' WHERE id = ?", (order_id,))

    conn.commit()
    conn.close()
    return jsonify({"error": 0, "message": "Success"}), 200


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)