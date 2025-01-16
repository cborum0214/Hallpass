# Attendance Tracking System with Flask and SQLite

from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)

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
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

@app.route('/')
def index():
    users = User.query.all()
    return render_template('index.html', users=users)

@app.route('/mark_attendance', methods=['POST'])
def mark_attendance():
    user_id = request.form.get('user_id')
    if user_id:
        attendance = Attendance(user_id=user_id)
        db.session.add(attendance)
        db.session.commit()
        return redirect(url_for('index'))
    return "Error: User ID is required.", 400

@app.route('/attendance_report')
def attendance_report():
    report = db.session.query(User.name, Attendance.timestamp).join(Attendance).all()
    return render_template('report.html', report=report)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='200.10.1.21', port=5000)
