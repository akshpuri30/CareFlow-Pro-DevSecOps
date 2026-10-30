import os
import secrets
from datetime import datetime, timezone
from functools import wraps
from flask import Flask, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(60), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='receptionist')

class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(20), nullable=False)
    phone = db.Column(db.String(20), nullable=False, default='')
    condition = db.Column(db.String(160), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

class Doctor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    specialization = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    scheduled_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Scheduled')
    patient = db.relationship('Patient')
    doctor = db.relationship('Doctor')

class MedicalRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    diagnosis = db.Column(db.String(200), nullable=False)
    treatment = db.Column(db.String(300), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    patient = db.relationship('Patient')

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Unpaid')
    patient = db.relationship('Patient')

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    actor = db.Column(db.String(60), nullable=False)
    action = db.Column(db.String(160), nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

def log(action):
    db.session.add(AuditLog(actor=current_user.username, action=action))

def role_required(*roles):
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrapped
    return decorator

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id)) if str(user_id).isdigit() else None

def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get('SECRET_KEY', secrets.token_hex(32)),
        SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URL', 'sqlite:///careflow.db'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE', '0') == '1',
        MAX_CONTENT_LENGTH=1024 * 1024,
    )
    if test_config:
        app.config.update(test_config)
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = 'login'

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'"
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.route('/health')
    def health():
        return jsonify(status='ok')

    @app.route('/')
    def index():
        return redirect(url_for('dashboard' if current_user.is_authenticated else 'login'))

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            user = db.session.scalar(db.select(User).filter_by(username=username))
            if user and check_password_hash(user.password_hash, password):
                login_user(user)
                log('Signed in')
                db.session.commit()
                return redirect(url_for('dashboard'))
            flash('Invalid credentials.', 'error')
        return render_template('login.html')

    @app.route('/logout', methods=['POST'])
    @login_required
    def logout():
        log('Signed out')
        db.session.commit()
        logout_user()
        return redirect(url_for('login'))

    @app.route('/dashboard')
    @login_required
    def dashboard():
        stats = dict(patients=db.session.scalar(db.select(func.count(Patient.id))),
                     doctors=db.session.scalar(db.select(func.count(Doctor.id))),
                     appointments=db.session.scalar(db.select(func.count(Appointment.id))),
                     invoices=db.session.scalar(db.select(func.count(Invoice.id))))
        recent = db.session.scalars(db.select(Appointment).order_by(Appointment.scheduled_at.desc()).limit(5)).all()
        return render_template('dashboard.html', stats=stats, recent=recent, section='dashboard')

    @app.route('/patients', methods=['GET', 'POST'])
    @role_required('admin', 'doctor', 'receptionist')
    def patients():
        if request.method == 'POST':
            name = request.form.get('name', '').strip()
            gender = request.form.get('gender', '')
            condition = request.form.get('condition', '').strip()
            phone = request.form.get('phone', '').strip()
            try: age = int(request.form.get('age', ''))
            except ValueError: age = -1
            if not (1 <= len(name) <= 100 and 0 <= age <= 120 and gender in ('Male', 'Female', 'Other') and 1 <= len(condition) <= 160 and len(phone) <= 20):
                flash('Invalid patient details.', 'error')
            else:
                db.session.add(Patient(name=name, age=age, gender=gender, phone=phone, condition=condition))
                log('Created patient record')
                db.session.commit()
                flash('Patient added.', 'success')
                return redirect(url_for('patients'))
        query = request.args.get('q', '').strip()[:80]
        statement = db.select(Patient).order_by(Patient.id.desc())
        if query: statement = statement.where(Patient.name.ilike(f'%{query}%'))
        return render_template('patients.html', rows=db.session.scalars(statement).all(), q=query, section='patients')

    @app.route('/patients/<int:item_id>/delete', methods=['POST'])
    @role_required('admin')
    def delete_patient(item_id):
        patient = db.get_or_404(Patient, item_id)
        if db.session.scalar(db.select(Appointment.id).filter_by(patient_id=item_id).limit(1)) or db.session.scalar(db.select(MedicalRecord.id).filter_by(patient_id=item_id).limit(1)) or db.session.scalar(db.select(Invoice.id).filter_by(patient_id=item_id).limit(1)):
            flash('Cannot delete patient with linked records.', 'error')
        else:
            db.session.delete(patient)
            log(f'Deleted patient #{item_id}')
            db.session.commit()
            flash('Patient deleted.', 'success')
        return redirect(url_for('patients'))

    @app.route('/doctors', methods=['GET', 'POST'])
    @login_required
    def doctors():
        if request.method == 'POST':
            if current_user.role != 'admin': abort(403)
            name = request.form.get('name', '').strip()
            specialty = request.form.get('specialization', '').strip()
            email = request.form.get('email', '').strip()
            if not (name and specialty and '@' in email and len(name) <= 100 and len(specialty) <= 100 and len(email) <= 120):
                flash('Invalid doctor details.', 'error')
            else:
                db.session.add(Doctor(name=name, specialization=specialty, email=email))
                log('Added doctor')
                db.session.commit()
                return redirect(url_for('doctors'))
        return render_template('doctors.html', rows=db.session.scalars(db.select(Doctor).order_by(Doctor.id.desc())).all(), section='doctors')

    @app.route('/appointments', methods=['GET', 'POST'])
    @login_required
    def appointments():
        if request.method == 'POST':
            try:
                patient_id = int(request.form.get('patient_id', ''))
                doctor_id = int(request.form.get('doctor_id', ''))
                scheduled_at = datetime.fromisoformat(request.form.get('scheduled_at', ''))
            except (ValueError, TypeError):
                flash('Invalid appointment details.', 'error')
                return redirect(url_for('appointments'))
            if not db.session.get(Patient, patient_id) or not db.session.get(Doctor, doctor_id):
                flash('Choose a valid patient and doctor.', 'error')
            else:
                db.session.add(Appointment(patient_id=patient_id, doctor_id=doctor_id, scheduled_at=scheduled_at))
                log('Created appointment')
                db.session.commit()
                flash('Appointment scheduled.', 'success')
                return redirect(url_for('appointments'))
        return render_template('appointments.html', rows=db.session.scalars(db.select(Appointment).order_by(Appointment.scheduled_at.desc())).all(), patients=db.session.scalars(db.select(Patient).order_by(Patient.name)).all(), doctors=db.session.scalars(db.select(Doctor).order_by(Doctor.name)).all(), section='appointments')

    @app.route('/appointments/<int:item_id>/status', methods=['POST'])
    @login_required
    def appointment_status(item_id):
        item = db.get_or_404(Appointment, item_id)
        status = request.form.get('status', '')
        if status not in ('Scheduled', 'Completed', 'Cancelled'): abort(400)
        item.status = status
        log(f'Changed appointment #{item_id} to {status}')
        db.session.commit()
        return redirect(url_for('appointments'))

    @app.route('/records', methods=['GET', 'POST'])
    @role_required('admin', 'doctor')
    def records():
        if request.method == 'POST':
            try: patient_id = int(request.form.get('patient_id', ''))
            except ValueError: patient_id = -1
            diagnosis = request.form.get('diagnosis', '').strip()
            treatment = request.form.get('treatment', '').strip()
            if not db.session.get(Patient, patient_id) or not (0 < len(diagnosis) <= 200 and 0 < len(treatment) <= 300):
                flash('Invalid medical record.', 'error')
            else:
                db.session.add(MedicalRecord(patient_id=patient_id, diagnosis=diagnosis, treatment=treatment))
                log('Added medical record')
                db.session.commit()
                return redirect(url_for('records'))
        return render_template('records.html', rows=db.session.scalars(db.select(MedicalRecord).order_by(MedicalRecord.id.desc())).all(), patients=db.session.scalars(db.select(Patient).order_by(Patient.name)).all(), section='records')

    @app.route('/billing', methods=['GET', 'POST'])
    @role_required('admin', 'receptionist')
    def billing():
        if request.method == 'POST':
            try: patient_id, amount = int(request.form.get('patient_id', '')), int(request.form.get('amount', ''))
            except ValueError: patient_id, amount = -1, -1
            if not db.session.get(Patient, patient_id) or not (0 < amount <= 10000000):
                flash('Invalid invoice.', 'error')
            else:
                db.session.add(Invoice(patient_id=patient_id, amount=amount))
                log('Created invoice')
                db.session.commit()
                return redirect(url_for('billing'))
        return render_template('billing.html', rows=db.session.scalars(db.select(Invoice).order_by(Invoice.id.desc())).all(), patients=db.session.scalars(db.select(Patient).order_by(Patient.name)).all(), section='billing')

    @app.route('/billing/<int:item_id>/paid', methods=['POST'])
    @role_required('admin', 'receptionist')
    def mark_paid(item_id):
        invoice = db.get_or_404(Invoice, item_id)
        invoice.status = 'Paid'
        log(f'Marked invoice #{item_id} paid')
        db.session.commit()
        return redirect(url_for('billing'))

    @app.route('/audit')
    @role_required('admin')
    def audit():
        return render_template('audit.html', rows=db.session.scalars(db.select(AuditLog).order_by(AuditLog.id.desc()).limit(100)).all(), section='audit')

    @app.route('/security')
    @role_required('admin')
    def security():
        return render_template('security.html', section='security')

    with app.app_context():
        db.create_all()
    return app

app = create_app()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000)
