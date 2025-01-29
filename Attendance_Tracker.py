# Attendance Tracking System with Flask and SQLite

from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import timedelta

app = Flask(__name__)
app.secret_key = 'secret_key_for_session'  # Replace with a strong secret key

# Configure session timeout (20 minutes of inactivity)
app.permanent_session_lifetime = timedelta(minutes=20)

# Configure SQLite Database
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'attendance.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Define the database models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50), nullable=False, default="Employee")

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher = db.Column(db.String(100), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), nullable=False)  # Leaving or Returning
    timestamp = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

@app.before_request
def make_session_permanent():
    session.permanent = True  # Set session as permanent

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
        status = request.form.get('status')

        if teacher and first_name and last_name and location and status:
            new_attendance = Attendance(
                teacher=teacher,
                first_name=first_name,
                last_name=last_name,
                location=location,
                status=status
            )
            db.session.add(new_attendance)
            db.session.commit()
            return redirect(url_for('student'))

    locations = ["Restroom", "Office", "Library", "Cafeteria"]  # Example locations
    teachers = ["Mr. Borum", "Mr. VanCampen"]  # Example teachers
    return render_template('student.html', locations=locations, teachers=teachers)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'authenticated' not in session:
        if request.method == 'POST':
            password = request.form.get('password')
            if password == "0d8pwDfO":
                session['authenticated'] = True
                return redirect(url_for('admin'))
            else:
                return render_template('admin_login.html', error="Invalid password", back_url=url_for('index'))
        return render_template('admin_login.html', back_url=url_for('index'))

    filters = {
        'date_start': request.args.get('date_start', default=None),
        'date_end': request.args.get('date_end', default=None),
        'time_start': request.args.get('time_start', default=None),
        'time_end': request.args.get('time_end', default=None),
        'last_name': request.args.get('last_name', default=""),
        'first_name': request.args.get('first_name', default=""),
        'teacher': request.args.get('teacher', default="")
    }

    teachers = ["Mr. Borum", "Mr. VanCampen"]  # Example teachers for picklist

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

    attendance_records = query.order_by(
        Attendance.timestamp,
        Attendance.last_name,
        Attendance.first_name
    ).all()

    return render_template('admin.html', records=attendance_records, filters=filters, teachers=teachers, back_url=url_for('index'))

@app.route('/logout')
def logout():
    session.pop('authenticated', None)
    return redirect(url_for('admin'))

@app.route('/attendance_report')
def attendance_report():
    report = db.session.query(Attendance.teacher, Attendance.first_name, Attendance.last_name, Attendance.location, Attendance.status, Attendance.timestamp).all()
    return render_template('report.html', report=report)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000)
