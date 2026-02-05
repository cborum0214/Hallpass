# attendance_tracker.py
from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import timedelta

app = Flask(__name__)

# ---------------- App Config ---------------- #
# Secrets / config from env, with safe fallbacks
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")
app.permanent_session_lifetime = timedelta(minutes=int(os.getenv("SESSION_MINUTES", "20")))

# SQLite path: default to project folder; in Docker we usually set DB_DIR=/data
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_DIR = os.getenv("DB_DIR", BASE_DIR)
DB_FILE = os.getenv("DB_FILE", "attendance.db")
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(DB_DIR, DB_FILE)}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ---------------- Models ---------------- #
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), nullable=False, default="Employee")  # "Admin" or "Employee"

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher = db.Column(db.String(100), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    notes = db.Column(db.Text, nullable=True)  # ✅ optional
    status = db.Column(db.String(20), nullable=False)  # "Leaving" or "Returning"
    timestamp = db.Column(db.DateTime, nullable=False, server_default=db.func.now())


# ---------------- One-time DB Initializer ---------------- #
def initialize_database() -> None:
    """
    Ensure tables exist and seed a default admin if none present.
    This runs at import time (under app.app_context), so it works with Gunicorn too.
    """
    db.create_all()
    # Seed default admin if missing
    if not User.query.filter_by(role="Admin").first():
        default_username = os.getenv("DEFAULT_ADMIN_USER", "admin")
        default_password = os.getenv("DEFAULT_ADMIN_PASS", "admin123")  # change after first login
        new_admin = User(username=default_username, role="Admin")
        new_admin.set_password(default_password)
        db.session.add(new_admin)
        db.session.commit()

# Run initializer immediately (works for Flask dev server and Gunicorn)
with app.app_context():
    initialize_database()


# ---------------- Helpers / Constants ---------------- #
LOCATIONS = ["Restroom", "Office", "Guidance", "Library", "Cafeteria", "Other Classroom"]
TEACHERS = ["Mr. Borum", "Mr. VanCampen", "Mrs. Vargas"]


@app.before_request
def make_session_permanent():
    session.permanent = True


# ---------------- Static / Favicon ---------------- #
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, 'static'),
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon'
    )


# ---------------- Routes ---------------- #
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/student', methods=['GET', 'POST'])
def student():
    if request.method == 'POST':
        teacher = request.form.get('teacher')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        location = request.form.get('location')
        notes = request.form.get('notes', '').strip()  # ✅ NEW: optional
        status = request.form.get('status')

        if teacher and first_name and last_name and location and status:
            new_attendance = Attendance(
                teacher=teacher,
                first_name=first_name,
                last_name=last_name,
                location=location,
                notes=notes,  # ✅ NEW
                status=status
            )
            db.session.add(new_attendance)
            db.session.commit()

            # Remember last teacher selection (you already use this on GET)
            session['last_teacher'] = teacher

            flash("Attendance recorded successfully.", "success")
            return redirect(url_for('student'))
        else:
            flash("All fields are required.", "danger")

    selected_teacher = session.get('last_teacher')
    if not selected_teacher:
        last_row = Attendance.query.order_by(Attendance.timestamp.desc()).first()
        selected_teacher = last_row.teacher if last_row else (TEACHERS[0] if TEACHERS else "")

    # Ensure the selected teacher is present in the dropdown list
    teachers_list = TEACHERS if selected_teacher in TEACHERS else (TEACHERS + [selected_teacher] if selected_teacher else TEACHERS)

    return render_template('student.html', locations=LOCATIONS, teachers=teachers_list, selected_teacher=selected_teacher)


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    # Not logged in? Show login form (username + password)
    if 'user_id' not in session:
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            user = User.query.filter_by(username=username, role="Admin").first()
            if user and user.check_password(password):
                session['user_id'] = user.id
                session['role'] = user.role
                flash("Logged in successfully.", "success")
                return redirect(url_for('admin'))
            else:
                return render_template('admin_login.html', error="Invalid credentials", back_url=url_for('index'))
        return render_template('admin_login.html', back_url=url_for('index'))

    # Logged in: apply filters and show records
    filters = {
        'date_start': request.args.get('date_start'),
        'date_end': request.args.get('date_end'),
        'time_start': request.args.get('time_start'),
        'time_end': request.args.get('time_end'),
        'last_name': request.args.get('last_name', ""),
        'first_name': request.args.get('first_name', ""),
        'teacher': request.args.get('teacher', "")
    }

    query = Attendance.query
    if filters['date_start'] and filters['date_end']:
        query = query.filter(db.func.date(Attendance.timestamp).between(filters['date_start'], filters['date_end']))
    if filters['time_start'] and filters['time_end']:
        query = query.filter(db.func.time(Attendance.timestamp).between(filters['time_start'], filters['time_end']))
    if filters['last_name']:
        query = query.filter(Attendance.last_name.ilike(f"%{filters['last_name']}%"))
    if filters['first_name']:
        query = query.filter(Attendance.first_name.ilike(f"%{filters['first_name']}%"))
    if filters['teacher']:
        query = query.filter(Attendance.teacher.ilike(f"%{filters['teacher']}%"))

    attendance_records = query.order_by(Attendance.timestamp.desc()).all()

    return render_template(
        'admin.html',
        records=attendance_records,
        filters=filters,
        teachers=TEACHERS,
        back_url=url_for('index')
    )


@app.route('/admin/add_admin', methods=['GET', 'POST'])
def add_admin():
    if 'user_id' not in session or session.get('role') != "Admin":
        flash("Unauthorized access.", "danger")
        return redirect(url_for('admin'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not username or not password:
            flash("Both fields are required.", "danger")
            return redirect(url_for('add_admin'))

        if User.query.filter_by(username=username).first():
            flash("Username already exists.", "danger")
            return redirect(url_for('add_admin'))

        new_admin = User(username=username, role="Admin")
        new_admin.set_password(password)
        db.session.add(new_admin)
        db.session.commit()
        flash("New admin added successfully!", "success")
        return redirect(url_for('admin'))

    return render_template('add_admin.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('admin'))


@app.route('/attendance_report')
def attendance_report():
    report = db.session.query(
        Attendance.teacher,
        Attendance.first_name,
        Attendance.last_name,
        Attendance.location,
        Attendance.notes,
        Attendance.status,
        Attendance.timestamp
    ).all()
    return render_template('report.html', report=report)


# -------- Optional CLI: flask --app attendance_tracker:app init-db -------- #
@app.cli.command("init-db")
def init_db_command():
    initialize_database()
    print("Database initialized (tables + default admin if missing).")


# ---------------- Local Dev Entry ---------------- #
if __name__ == '__main__':
    # For local runs, ensure DB is ready (already handled above, but harmless)
    with app.app_context():
        initialize_database()
    app.run(host='0.0.0.0', port=5000)
