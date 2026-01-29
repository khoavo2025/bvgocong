from flask import Flask, render_template, request, redirect, send_file
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import psycopg2, pandas as pd
from functools import wraps
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from flask import Flask, render_template, request, redirect, url_for, session
from flask import session
from flask import flash
from flask_login import login_user
from flask_login import login_required, current_user
from flask import flash
from flask_login import login_required, logout_user, current_user

app = Flask(__name__)
app.secret_key = "hospital_secret_key"
# ===== DANH SÁCH KHOA (DÙNG CHUNG) =====
DEPARTMENTS = [
    {"code": "HSCC", "name": "HSCC"},
    {"code": "NTM", "name": "Nội tim mạch"},
    {"code": "NTH", "name": "Nội tổng hợp"},
    {"code": "NG",  "name": "Ngoại"},
    {"code": "SAN", "name": "Sản"},
    {"code": "NHI", "name": "Nhi"},
    {"code": "NHIEM", "name": "Nhiễm"},
    {"code": "GMHS", "name": "Phẫu thuật GMHS"},
]


# ===== DATABASE =====
def db():
    return psycopg2.connect(
        host="localhost",
        database="hospital",
        user="postgres",
        password="123456"  # đổi cho đúng
    )

# ===== LOGIN =====
login_manager = LoginManager(app)
login_manager.login_view = "login"

class User(UserMixin):
    def __init__(self, id, username, role, dept, is_active=True):
        self.id = id
        self.username = username
        self.role = role
        self.dept = dept
        self.is_active = is_active

    def is_active(self):
        return self.is_active


@login_manager.user_loader
def load_user(user_id):
    cur = db().cursor()
    cur.execute("SELECT id, username, role, dept FROM users WHERE id=%s", (user_id,))
    u = cur.fetchone()
    return User(*u) if u else None

def role_required(*roles):
    def wrap(f):
        @wraps(f)
        def inner(*args, **kwargs):
            if current_user.role not in roles:
                return "⛔ Không có quyền", 403
            return f(*args, **kwargs)
        return inner
    return wrap

# ===== AUTH =====
@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        cur = db().cursor()
        cur.execute("""
            SELECT id, username, password, role, dept, is_active
            FROM users
            WHERE username=%s
        """, (username,))
        u = cur.fetchone()

        if not u:
            flash("❌ Sai tài khoản hoặc mật khẩu", "danger")
            return render_template("login.html")

        if not u[5]:
            flash("⛔ Tài khoản đã bị khóa. Liên hệ quản trị.", "warning")
            return render_template("login.html")

        if u[2] != password:
            flash("❌ Sai tài khoản hoặc mật khẩu", "danger")
            return render_template("login.html")

        user = User(u[0], u[1], u[3], u[4])
        login_user(user)

        session["username"] = user.username
        session["role"] = user.role
        session["dept"] = user.dept

        return redirect("/report")

    return render_template("login.html")


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        username = request.form["username"]
        new_password = request.form["new_password"]

        cur = db().cursor()
        cur.execute("SELECT id FROM users WHERE username=%s", (username,))
        u = cur.fetchone()

        if not u:
            flash("❌ Không tồn tại tài khoản", "danger")
            return redirect("/forgot-password")

        cur.execute(
            "UPDATE users SET password=%s WHERE username=%s",
            (new_password, username)
        )
        db().commit()

        flash("✅ Đặt lại mật khẩu thành công, hãy đăng nhập", "success")
        return redirect("/login")

    return render_template("forgot_password.html")





@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    conn = db()                  # 🔥 LẤY CONNECTION 1 LẦN
    cur = conn.cursor()

    if request.method == "POST":
        old_pw = request.form["old_password"]
        new_pw = request.form["new_password"]

        # 1️⃣ Kiểm tra mật khẩu cũ
        cur.execute(
            "SELECT password FROM users WHERE id=%s",
            (current_user.id,)
        )
        row = cur.fetchone()

        if not row or row[0] != old_pw:
            flash("❌ Mật khẩu cũ không đúng", "danger")
            return redirect(request.url)

        # 2️⃣ Update mật khẩu mới
        cur.execute(
            "UPDATE users SET password=%s WHERE id=%s",
            (new_pw, current_user.id)
        )

        conn.commit()            # 🔥 COMMIT ĐÚNG CONNECTION

        # 3️⃣ Logout để đăng nhập lại
        logout_user()
        session.clear()

        flash("✅ Đổi mật khẩu thành công. Vui lòng đăng nhập lại.", "success")
        return redirect("/login")

    return render_template("change_password.html")




@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/login")

# ===== KHOA PHÒNG =====
@app.route("/departments", methods=["GET","POST"])
@login_required
@role_required("admin")
def departments():
    conn = db()
    cur = conn.cursor()
    if request.method == "POST":
        cur.execute("INSERT INTO departments VALUES (%s,%s)",
                    (request.form["code"], request.form["name"]))
        conn.commit()
    cur.execute("SELECT * FROM departments")
    return render_template("departments.html", data=cur.fetchall())

# ===== DASHBOARD =====
@app.route("/dashboard/khoa/<dept_code>")
@login_required
def dept_dashboard(dept_code):

    if current_user.role != "admin" and current_user.dept != dept_code:
        abort(403)

    return render_template(
        "dept_dashboard.html",
        dept=dept_code
    )
# ===== USERS =====
@app.route("/admin/users")
@login_required
@role_required("admin")
def admin_users():
    conn = db()
    cur = conn.cursor()

    q = request.args.get("q", "").strip()
    dept = request.args.get("dept", "").strip()
    highlight = request.args.get("highlight")

    sql = """
        SELECT id, username, email, role, dept, is_active
        FROM users
        WHERE 1=1
    """
    params = []

    # 🔍 Tìm theo username
    if q:
        sql += " AND username ILIKE %s"
        params.append(f"%{q}%")

    # 🏥 Lọc theo khoa
    if dept:
        sql += " AND dept = %s"
        params.append(dept)

    # ⬆️ User vừa cập nhật lên đầu
    if highlight:
        sql += """
            ORDER BY
            CASE WHEN id=%s THEN 0 ELSE 1 END,
            id DESC
        """
        params.append(highlight)
    else:
        sql += " ORDER BY id DESC"

    cur.execute(sql, params)
    users = cur.fetchall()

    return render_template(
        "admin_users.html",
        users=users,
        q=q,
        dept=dept,
        highlight=highlight
    )





# ===== USERS MỚI =====
@app.route("/admin/users/create", methods=["GET","POST"])
@login_required
@role_required("admin")
def create_user():
    if request.method == "POST":
        conn = db()
        cur = conn.cursor()

        username = request.form["username"].strip()
        email    = request.form["email"].strip().lower()
        password = request.form["password"]
        role     = request.form["role"]
        dept     = request.form["dept"]

        # 🚫 CHECK TRÙNG USERNAME
        cur.execute(
            "SELECT 1 FROM users WHERE username = %s",
            (username,)
        )
        if cur.fetchone():
            flash("❌ Username đã tồn tại, vui lòng chọn tên khác", "danger")
            return redirect("/admin/users/create")

        # 🚫 CHECK TRÙNG EMAIL
        cur.execute(
            "SELECT 1 FROM users WHERE email = %s",
            (email,)
        )
        if cur.fetchone():
            flash("❌ Email đã được sử dụng, vui lòng kiểm tra lại", "danger")
            return redirect("/admin/users/create")

        # ✅ INSERT USER
        cur.execute("""
            INSERT INTO users (username, password, email, role, dept)
            VALUES (%s, %s, %s, %s, %s)
        """, (username, password, email, role, dept))

        conn.commit()

        flash("✅ Tạo user thành công", "success")
        return redirect("/admin/users")

    return render_template("admin_user_form.html")


# ===== USERS edit =====
@app.route("/admin/users/edit/<int:user_id>", methods=["GET", "POST"])
@login_required
@role_required("admin")
def edit_user(user_id):
    conn = db()
    cur = conn.cursor()

    if request.method == "POST":

        # 🔴 CHECK TRÙNG USERNAME
        cur.execute(
            "SELECT 1 FROM users WHERE username=%s AND id<>%s",
            (request.form["username"], user_id)
        )
        if cur.fetchone():
            flash("❌ Username đã tồn tại", "danger")
            return redirect(request.url)

        # 🟢 UPDATE USER
        cur.execute("""
            UPDATE users
            SET username=%s,
                email=%s,
                role=%s,
                dept=%s
            WHERE id=%s
        """, (
            request.form["username"],
            request.form["email"],
            request.form["role"],
            request.form["dept"],
            user_id
        ))

        conn.commit()
        flash("✅ Cập nhật user thành công", "success")
        return redirect(f"/admin/users?highlight={user_id}")


    # 🔵 LOAD USER
    cur.execute("""
        SELECT id, username, email, role, dept
        FROM users
        WHERE id=%s
    """, (user_id,))
    user = cur.fetchone()

    return render_template("admin_user_edit.html", user=user)




# ===== reset =====
@app.route("/admin/users/reset/<int:user_id>")
@login_required
@role_required("admin")
def reset_user_password(user_id):
    conn = db()              # ✅ LẤY 1 CONNECTION
    cur = conn.cursor()

    new_pass = "123456"

    cur.execute("""
        UPDATE users
        SET password=%s
        WHERE id=%s
    """, (new_pass, user_id))

    conn.commit()            # ✅ COMMIT ĐÚNG CONNECTION

    flash("🔑 Đã reset mật khẩu về 123456", "success")
    return redirect("/admin/users")

# ===== delete =====
@app.route("/admin/users/delete/<int:user_id>", methods=["POST"])
@login_required
@role_required("admin")
def delete_user(user_id):
    conn = db()
    cur = conn.cursor()

    cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
    conn.commit()

    flash("🗑️ Đã xóa user", "danger")
    return redirect("/admin/users")

# ===== lock user =====
@app.route("/admin/users/lock/<int:user_id>", methods=["POST"])
@login_required
@role_required("admin")
def lock_user(user_id):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        "UPDATE users SET is_active=FALSE WHERE id=%s",
        (user_id,)
    )
    conn.commit()

    flash("⛔ User đã bị tạm khóa", "warning")
    return redirect("/admin/users")

# ===== unlock user =====
@app.route("/admin/users/unlock/<int:user_id>", methods=["POST"])
@login_required
@role_required("admin")
def unlock_user(user_id):
    conn = db()
    cur = conn.cursor()

    cur.execute(
        "UPDATE users SET is_active=TRUE WHERE id=%s",
        (user_id,)
    )
    conn.commit()

    flash("✅ User đã được mở khóa", "success")
    return redirect("/admin/users")


# ===== NHÂN SỰ =====
@app.route("/staff", methods=["GET","POST"])
@login_required
@role_required("admin","truong_khoa")
def staff():
    conn = db()
    cur = conn.cursor()
    if request.method == "POST":
        cur.execute("""
            INSERT INTO staff VALUES (%s,%s,%s,%s)
        """, (request.form["sid"], request.form["name"],
              request.form["role"], request.form["dept"]))
        conn.commit()

    if current_user.role == "truong_khoa":
        cur.execute("SELECT * FROM staff WHERE dept=%s", (current_user.dept,))
    else:
        cur.execute("SELECT * FROM staff")
    data = cur.fetchall()

    cur.execute("SELECT * FROM departments")
    depts = cur.fetchall()

    return render_template("staff.html", data=data, depts=depts)

# ===== THIẾT BỊ =====
@app.route("/equipment", methods=["GET","POST"])
@login_required
def equipment():
    conn = db()
    cur = conn.cursor()

    # ========== INSERT ==========
    if request.method == "POST":
        # user thường chỉ được thêm thiết bị khoa mình
        dept = request.form["dept"]
        if current_user.role != "admin":
            dept = current_user.dept

        cur.execute("""
            INSERT INTO equipment (eid, name, qty, dept)
            VALUES (%s,%s,%s,%s)
        """, (
            request.form["eid"],
            request.form["name"],
            request.form["qty"],
            dept
        ))
        conn.commit()

    # ========== SELECT ==========
    if current_user.role == "admin":
        cur.execute("SELECT * FROM equipment")
        cur.execute("SELECT * FROM departments")
        depts = cur.fetchall()
    else:
        cur.execute("""
            SELECT * FROM equipment
            WHERE dept = %s
        """, (current_user.dept,))
        depts = [(current_user.dept,)]

    data = cur.fetchall()

    return render_template(
        "equipment.html",
        data=data,
        depts=depts
    )
# ===== BÁO CÁO điều dưỡng =====
from datetime import datetime

@app.route("/nurse-report", methods=["GET", "POST"])
@login_required
def nurse_report():
    now = datetime.now()

    month = request.args.get("month", now.month, type=int)
    year = request.args.get("year", now.year, type=int)

    if request.method == "POST":
        # DEBUG – xem dữ liệu submit
        for key, value in request.form.items():
            print(key, value)
        # TODO: lưu DB sau

    return render_template(
        "nurse_report.html",
        data=DEPARTMENTS,
        month=month,
        year=year,
        user_khoa=session.get("khoa_code")
    )

@app.route("/api/nurse-report/save", methods=["POST"])
def nurse_report_autosave():
    data = request.json

    save_cell(
        month=data["month"],
        year=data["year"],
        day=data["day"],
        khoa=data["khoa"],
        type=data["type"],
        scope=data["scope"],
        value=data["value"]
    )

    return jsonify(ok=True)

@app.route("/api/report/save", methods=["POST"])
@login_required
def save_report():
    data = request.json

    incoming_dept = data.get("dept")   # HSCC / NOI / NGOAI ...
    day = data.get("day")
    field = data.get("field")
    value = data.get("value")

    # ====== CHECK PHÂN QUYỀN (BẮT BUỘC) ======
    if session["dept"] != incoming_dept and session["role"] != "admin":
        abort(403)

    # ====== GHI DB ======
    cur = db().cursor() 
    cur.execute("""
        INSERT INTO nurse_report (dept, day, field, value)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (dept, day, field)
        DO UPDATE SET value = EXCLUDED.value
    """, (incoming_dept, day, field, value))

    db().commit()
    return {"ok": True}

# ===== BÁO CÁO =====
@app.route("/report")
@login_required
def report():
    cur = db().cursor()

    # ===== BÁO CÁO TỔNG =====
    cur.execute("""
        SELECT d.name, COUNT(s.sid), COALESCE(SUM(e.qty),0)
        FROM departments d
        LEFT JOIN staff s ON d.code=s.dept
        LEFT JOIN equipment e ON d.code=e.dept
        GROUP BY d.name
    """)
    report = cur.fetchall()

    # ===== THIẾT BỊ SẮP HẾT =====
    cur.execute("SELECT name, dept, qty FROM equipment WHERE qty < 5")
    low = cur.fetchall()

    # ===== QUYỀN HIỂN THỊ BÁO CÁO ĐIỀU DƯỠNG =====
    show_nurse_report = (
        session.get("role") == "admin"
        or session.get("dept") != "DUOC"
    )

    return render_template(
        "report.html",
        report=report,
        low=low,
        show_nurse_report=show_nurse_report
    )


# KHÔNG cần app.run() khi deploy
# app.run(debug=True)
