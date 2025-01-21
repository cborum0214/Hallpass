# Attendance Tracking System with Flask and SQLite

from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)
app.secret_key = 'secret_key_for_session'  # Replace with a strong secret key

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
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), nullable=False)  # Leaving or Returning
    timestamp = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/student', methods=['GET', 'POST'])
def student():
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        location = request.form.get('location')
        status = request.form.get('status')

        if first_name and last_name and location and status:
            new_attendance = Attendance(
                first_name=first_name,
                last_name=last_name,
                location=location,
                status=status
            )
            db.session.add(new_attendance)
            db.session.commit()
            return redirect(url_for('student'))

    locations = ["Office", "Library", "Cafeteria"]  # Example locations
    return render_template('student.html', locations=locations)

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
        'date': request.args.get('date', default=None),
        'time_start': request.args.get('time_start', default=None),
        'time_end': request.args.get('time_end', default=None),
        'last_name': request.args.get('last_name', default=""),
        'first_name': request.args.get('first_name', default="")
    }

    query = Attendance.query

    if filters['date']:
        query = query.filter(db.func.date(Attendance.timestamp) == filters['date'])
    if filters['time_start'] and filters['time_end']:
        query = query.filter(db.func.time(Attendance.timestamp).between(filters['time_start'], filters['time_end']))
    if filters['last_name']:
        query = query.filter(Attendance.last_name.ilike(f"%{filters['last_name']}%"))
    if filters['first_name']:
        query = query.filter(Attendance.first_name.ilike(f"%{filters['first_name']}%"))

    attendance_records = query.order_by(
        Attendance.timestamp,
        Attendance.last_name,
        Attendance.first_name
    ).all()

    return render_template('admin.html', records=attendance_records, filters=filters, back_url=url_for('index'))

@app.route('/logout')
def logout():
    session.pop('authenticated', None)
    return redirect(url_for('admin'))

@app.route('/attendance_report')
def attendance_report():
    report = db.session.query(Attendance.first_name, Attendance.last_name, Attendance.location, Attendance.status, Attendance.timestamp).all()
    return render_template('report.html', report=report)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000)
