import os
import uuid
import qrcode
from datetime import datetime
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for,
                   flash, session, jsonify, send_from_directory)
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from bson.objectid import ObjectId
import certifi
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

# ─────────────────────────── MongoDB ────────────────────────────────────────
_mongo_uri = app.config['MONGO_URI']
_mongo_kwargs = {'tlsCAFile': certifi.where()} if 'mongodb+srv' in _mongo_uri or ('mongodb' in _mongo_uri and 'localhost' not in _mongo_uri and '127.0.0.1' not in _mongo_uri) else {}
client = MongoClient(_mongo_uri, **_mongo_kwargs)
try:
    db = client.get_default_database()
except Exception:
    db = client['certdb']
certs_col = db['certificates']
admins_col = db['admins']
logs_col   = db['scan_logs']

# ─────────────────────────── Helper ─────────────────────────────────────────
def allowed_file(filename):
    return ('.' in filename and
            filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS'])

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def save_file(file, subfolder='uploads'):
    if file and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        folder = os.path.join(app.root_path, 'static', subfolder)
        os.makedirs(folder, exist_ok=True)
        file.save(os.path.join(folder, filename))
        return filename
    return None

def generate_qr(certificate_id, base_url=None):
    if not base_url:
        base_url = app.config.get('BASE_URL', '')
    # Fall back to request host if BASE_URL is localhost or unset
    if not base_url or 'localhost' in base_url or '127.0.0.1' in base_url:
        from flask import request as _req
        try:
            base_url = _req.host_url.rstrip('/')
        except RuntimeError:
            pass
    verify_url = f"{base_url}/verify/{certificate_id}"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(verify_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1a237e", back_color="white")
    qr_folder = app.config['QRCODE_FOLDER']
    os.makedirs(qr_folder, exist_ok=True)
    filename = f"qr_{certificate_id}.png"
    img.save(os.path.join(qr_folder, filename))
    return filename

def seed_admin():
    """Create default admin if none exists."""
    if admins_col.count_documents({}) == 0:
        admins_col.insert_one({
            'username': app.config['ADMIN_USERNAME'],
            'password': generate_password_hash(app.config['ADMIN_PASSWORD']),
            'email': app.config['ADMIN_EMAIL'],
            'created_at': datetime.utcnow()
        })
        print(f"[SEED] Admin created → username: {app.config['ADMIN_USERNAME']}  password: {app.config['ADMIN_PASSWORD']}")

# Automatically call when application is imported by Gunicorn
seed_admin()

# ─────────────────────────── Auth Routes ─────────────────────────────────────
@app.route('/')
def index():
    return redirect(url_for('dashboard') if session.get('admin_logged_in') else url_for('login'))

@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    if session.get('admin_logged_in'):
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        admin = admins_col.find_one({'username': username})
        if admin and check_password_hash(admin['password'], password):
            session['admin_logged_in'] = True
            session['admin_username'] = username
            flash('Welcome back! 👋', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid username or password.', 'danger')
    return render_template('login.html')

@app.route('/admin/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# ─────────────────────────── Dashboard ───────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    search_query = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '')
    query = {}
    if search_query:
        query['$or'] = [
            {'name':            {'$regex': search_query, '$options': 'i'}},
            {'certificate_id':  {'$regex': search_query, '$options': 'i'}},
            {'dn':              {'$regex': search_query, '$options': 'i'}},
            {'number':          {'$regex': search_query, '$options': 'i'}},
        ]
    if status_filter:
        query['status'] = status_filter

    certificates = list(certs_col.find(query).sort('created_at', -1))

    stats = {
        'total':   certs_col.count_documents({}),
        'active':  certs_col.count_documents({'status': 'active'}),
        'expired': certs_col.count_documents({'status': 'expired'}),
        'revoked': certs_col.count_documents({'status': 'revoked'}),
    }
    return render_template('dashboard.html', certificates=certificates,
                           stats=stats, search_query=search_query,
                           status_filter=status_filter)

# ─────────────────────────── Add Certificate ─────────────────────────────────
@app.route('/certificate/add', methods=['GET', 'POST'])
@login_required
def add_certificate():
    if request.method == 'POST':
        cert_id = 'CERT' + uuid.uuid4().hex[:8].upper()
        qr_code = generate_qr(cert_id)
        doc = {
            'certificate_id':   cert_id,
            'dn':               request.form.get('dn', '').strip(),
            'number':           request.form.get('number', '').strip(),
            'name':             request.form.get('name', '').strip(),
            'dob':              request.form.get('dob', ''),
            'nationality':      request.form.get('nationality', '').strip(),
            'regulations':      request.form.get('regulations', '').strip(),
            'issued_date':      request.form.get('issued_date', ''),
            'expiry_date':      request.form.get('expiry_date', ''),
            'status':           request.form.get('status', 'active'),
            'level':            request.form.get('level', '').strip(),
            'stc':              request.form.get('stc', '').strip(),
            'capacity':         request.form.get('capacity', '').strip(),
            'limitations':      request.form.get('limitations', 'None').strip(),
            'qr_code':          qr_code,
            'created_at':       datetime.utcnow(),
            'updated_at':       datetime.utcnow(),
        }
        certs_col.insert_one(doc)
        flash(f'Certificate {cert_id} created successfully! QR code generated.', 'success')
        return redirect(url_for('dashboard'))
    return render_template('add_certificate.html')

# ─────────────────────────── Edit Certificate ────────────────────────────────
@app.route('/certificate/edit/<cert_id>', methods=['GET', 'POST'])
@login_required
def edit_certificate(cert_id):
    cert = certs_col.find_one({'certificate_id': cert_id})
    if not cert:
        flash('Certificate not found.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        update = {
            'dn':               request.form.get('dn', '').strip(),
            'number':           request.form.get('number', '').strip(),
            'name':             request.form.get('name', '').strip(),
            'dob':              request.form.get('dob', ''),
            'nationality':      request.form.get('nationality', '').strip(),
            'regulations':      request.form.get('regulations', '').strip(),
            'issued_date':      request.form.get('issued_date', ''),
            'expiry_date':      request.form.get('expiry_date', ''),
            'status':           request.form.get('status', 'active'),
            'level':            request.form.get('level', '').strip(),
            'stc':              request.form.get('stc', '').strip(),
            'capacity':         request.form.get('capacity', '').strip(),
            'limitations':      request.form.get('limitations', 'None').strip(),
            'updated_at':       datetime.utcnow(),
        }

        certs_col.update_one({'certificate_id': cert_id}, {'$set': update})
        flash('Certificate updated successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('edit_certificate.html', cert=cert)

# ─────────────────────────── Delete Certificate ──────────────────────────────
@app.route('/certificate/delete/<cert_id>', methods=['POST'])
@login_required
def delete_certificate(cert_id):
    certs_col.delete_one({'certificate_id': cert_id})
    flash('Certificate deleted successfully.', 'success')
    return redirect(url_for('dashboard'))

# ─────────────────────────── Regenerate QR ───────────────────────────────────
@app.route('/certificate/regenerate-qr/<cert_id>', methods=['POST'])
@login_required
def regenerate_qr(cert_id):
    cert = certs_col.find_one({'certificate_id': cert_id})
    if not cert:
        flash('Certificate not found.', 'danger')
        return redirect(url_for('dashboard'))
    qr_filename = generate_qr(cert_id)
    certs_col.update_one({'certificate_id': cert_id}, {'$set': {'qr_code': qr_filename}})
    flash(f'QR code regenerated for {cert_id}.', 'success')
    return redirect(url_for('dashboard'))

# ─────────────────────────── Public Verification ─────────────────────────────
@app.route('/verify/<certificate_id>')
def verify(certificate_id):
    cert = certs_col.find_one({'certificate_id': certificate_id})
    # Log scan attempt
    logs_col.insert_one({
        'certificate_id': certificate_id,
        'ip': request.remote_addr,
        'user_agent': request.user_agent.string,
        'found': cert is not None,
        'scanned_at': datetime.utcnow()
    })
    if cert:
        # Auto-expire check
        if cert.get('expiry_date'):
            try:
                expiry = datetime.strptime(cert['expiry_date'], '%Y-%m-%d')
                if expiry < datetime.utcnow() and cert['status'] == 'active':
                    certs_col.update_one({'certificate_id': certificate_id},
                                         {'$set': {'status': 'expired'}})
                    cert['status'] = 'expired'
            except Exception:
                pass
    return render_template('verify.html', cert=cert, cert_id=certificate_id)

# ─────────────────────────── Analytics API ───────────────────────────────────
@app.route('/api/analytics')
@login_required
def analytics():
    pipeline = [
        {'$group': {'_id': '$status', 'count': {'$sum': 1}}}
    ]
    status_data = list(certs_col.aggregate(pipeline))
    recent_scans = logs_col.count_documents({
        'scanned_at': {'$gte': datetime(datetime.utcnow().year,
                                        datetime.utcnow().month,
                                        datetime.utcnow().day)}
    })
    return jsonify({'status_data': status_data, 'recent_scans': recent_scans})

# ─────────────────────────── Static file views ───────────────────────────────
@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/static/qrcodes/<filename>')
def qr_file(filename):
    return send_from_directory(app.config['QRCODE_FOLDER'], filename)

# ─────────────────────────── Run ─────────────────────────────────────────────
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
