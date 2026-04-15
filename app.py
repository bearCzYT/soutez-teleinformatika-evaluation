import json
import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import secrets
from datetime import datetime, timedelta

# Získat absolutní cestu ke složce, ve které se nachází tento soubor
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

ALLOWED_PREVIEW_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}
ALLOWED_SOURCE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}

# Zajistit existenci složek uvnitř složky aplikace
DATA_DIR = os.path.join(BASE_DIR, 'data')
UPLOADS_DIR = os.path.join(BASE_DIR, 'uploads')
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)

# Cesty k datovým souborům - vždy uvnitř složky aplikace
USERS_FILE = os.path.join(DATA_DIR, 'users.json')
CREATIONS_FILE = os.path.join(DATA_DIR, 'creations.json')
EVALUATIONS_FILE = os.path.join(DATA_DIR, 'evaluations.json')
CONTEST_STATE_FILE = os.path.join(DATA_DIR, 'contest_state.json')
CRITERIA_FILE = os.path.join(DATA_DIR, 'criteria.json')
EVALUATION_LOGS_FILE = os.path.join(DATA_DIR, 'evaluation_logs.json')
ERROR_REPORTS_FILE = os.path.join(DATA_DIR, 'error_reports.json')
ACTIVE_SESSIONS_FILE = os.path.join(DATA_DIR, 'active_sessions.json')
DB_FILE = os.path.join(DATA_DIR, 'app.sqlite3')

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def read_legacy_json(filepath, default=None):
    if default is None:
        default = []
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return default


def create_tables():
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                login TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                key TEXT NOT NULL,
                school TEXT NOT NULL,
                role TEXT NOT NULL,
                permissions TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS creations (
                id INTEGER PRIMARY KEY,
                preview_filename TEXT NOT NULL,
                source_filename TEXT NOT NULL,
                original_name TEXT NOT NULL,
                category TEXT NOT NULL,
                uploaded_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS evaluations (
                id INTEGER PRIMARY KEY,
                creation_id INTEGER NOT NULL,
                evaluator_id INTEGER NOT NULL,
                evaluator_name TEXT NOT NULL,
                scores TEXT NOT NULL,
                total INTEGER NOT NULL,
                evaluated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS contest_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                state TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS criteria (
                id INTEGER NOT NULL,
                category TEXT NOT NULL,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                min_value INTEGER,
                max_value INTEGER,
                PRIMARY KEY (category, id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS evaluation_logs (
                id INTEGER PRIMARY KEY,
                evaluation_id INTEGER NOT NULL,
                creation_id INTEGER NOT NULL,
                creation_name TEXT NOT NULL,
                category TEXT NOT NULL,
                evaluator_id INTEGER NOT NULL,
                evaluator_name TEXT NOT NULL,
                criterion_name TEXT NOT NULL,
                criterion_type TEXT NOT NULL,
                score INTEGER NOT NULL,
                logged_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS error_reports (
                id INTEGER PRIMARY KEY,
                creation_id INTEGER NOT NULL,
                creation_name TEXT NOT NULL,
                evaluator_id INTEGER NOT NULL,
                evaluator_name TEXT NOT NULL,
                reported_total INTEGER NOT NULL,
                note TEXT,
                status TEXT NOT NULL,
                reported_at TEXT NOT NULL,
                resolved_at TEXT,
                resolved_by TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS active_sessions (
                user_id INTEGER PRIMARY KEY,
                last_seen TEXT NOT NULL
            )
            """
        )
        conn.commit()


def table_is_empty(table_name):
    with get_db_connection() as conn:
        row = conn.execute(f"SELECT COUNT(*) AS count FROM {table_name}").fetchone()
        return row['count'] == 0


def load_json(filepath, default=None):
    if default is None:
        default = []

    with get_db_connection() as conn:
        if filepath == USERS_FILE:
            rows = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
            return [
                {
                    'id': row['id'],
                    'name': row['name'],
                    'login': row['login'],
                    'password': row['password'],
                    'key': row['key'],
                    'school': row['school'],
                    'role': row['role'],
                    'permissions': json.loads(row['permissions']) if row['permissions'] else []
                }
                for row in rows
            ]

        if filepath == CREATIONS_FILE:
            rows = conn.execute("SELECT * FROM creations ORDER BY id").fetchall()
            return [dict(row) for row in rows]

        if filepath == EVALUATIONS_FILE:
            rows = conn.execute("SELECT * FROM evaluations ORDER BY id").fetchall()
            evaluations = []
            for row in rows:
                evaluations.append({
                    'id': row['id'],
                    'creation_id': row['creation_id'],
                    'evaluator_id': row['evaluator_id'],
                    'evaluator_name': row['evaluator_name'],
                    'scores': json.loads(row['scores']) if row['scores'] else {},
                    'total': row['total'],
                    'evaluated_at': row['evaluated_at']
                })
            return evaluations

        if filepath == CONTEST_STATE_FILE:
            row = conn.execute("SELECT state FROM contest_state WHERE id = 1").fetchone()
            return {'state': row['state']} if row else (default if isinstance(default, dict) else {'state': 'čekání'})

        if filepath == CRITERIA_FILE:
            rows = conn.execute("SELECT * FROM criteria ORDER BY category, id").fetchall()
            result = {}
            for row in rows:
                category = row['category']
                if category not in result:
                    result[category] = []
                criterion = {
                    'id': row['id'],
                    'name': row['name'],
                    'type': row['type']
                }
                if row['type'] == 'slider':
                    criterion['min'] = row['min_value'] if row['min_value'] is not None else 0
                    criterion['max'] = row['max_value'] if row['max_value'] is not None else 10
                result[category].append(criterion)
            return result

        if filepath == EVALUATION_LOGS_FILE:
            rows = conn.execute("SELECT * FROM evaluation_logs ORDER BY id").fetchall()
            return [dict(row) for row in rows]

        if filepath == ERROR_REPORTS_FILE:
            rows = conn.execute("SELECT * FROM error_reports ORDER BY id").fetchall()
            return [dict(row) for row in rows]

        if filepath == ACTIVE_SESSIONS_FILE:
            rows = conn.execute("SELECT * FROM active_sessions ORDER BY user_id").fetchall()
            return [dict(row) for row in rows]

    return default


def save_json(filepath, data):
    with get_db_connection() as conn:
        if filepath == USERS_FILE:
            conn.execute("DELETE FROM users")
            for user in data:
                conn.execute(
                    """
                    INSERT INTO users (id, name, login, password, key, school, role, permissions)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user['id'],
                        user['name'],
                        user['login'],
                        user['password'],
                        user['key'],
                        user['school'],
                        user['role'],
                        json.dumps(user.get('permissions', []), ensure_ascii=False)
                    )
                )

        elif filepath == CREATIONS_FILE:
            conn.execute("DELETE FROM creations")
            for creation in data:
                conn.execute(
                    """
                    INSERT INTO creations (id, preview_filename, source_filename, original_name, category, uploaded_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        creation['id'],
                        creation['preview_filename'],
                        creation['source_filename'],
                        creation['original_name'],
                        creation['category'],
                        creation['uploaded_at']
                    )
                )

        elif filepath == EVALUATIONS_FILE:
            conn.execute("DELETE FROM evaluations")
            for evaluation in data:
                conn.execute(
                    """
                    INSERT INTO evaluations (id, creation_id, evaluator_id, evaluator_name, scores, total, evaluated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        evaluation['id'],
                        evaluation['creation_id'],
                        evaluation['evaluator_id'],
                        evaluation['evaluator_name'],
                        json.dumps(evaluation.get('scores', {}), ensure_ascii=False),
                        evaluation['total'],
                        evaluation['evaluated_at']
                    )
                )

        elif filepath == CONTEST_STATE_FILE:
            state = data.get('state', 'čekání') if isinstance(data, dict) else 'čekání'
            conn.execute(
                """
                INSERT INTO contest_state (id, state)
                VALUES (1, ?)
                ON CONFLICT(id) DO UPDATE SET state = excluded.state
                """,
                (state,)
            )

        elif filepath == CRITERIA_FILE:
            conn.execute("DELETE FROM criteria")
            for category, category_criteria in data.items():
                for criterion in category_criteria:
                    conn.execute(
                        """
                        INSERT INTO criteria (id, category, name, type, min_value, max_value)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            criterion['id'],
                            category,
                            criterion['name'],
                            criterion['type'],
                            criterion.get('min'),
                            criterion.get('max')
                        )
                    )

        elif filepath == EVALUATION_LOGS_FILE:
            conn.execute("DELETE FROM evaluation_logs")
            for log in data:
                conn.execute(
                    """
                    INSERT INTO evaluation_logs (
                        id, evaluation_id, creation_id, creation_name, category,
                        evaluator_id, evaluator_name, criterion_name, criterion_type,
                        score, logged_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        log['id'],
                        log['evaluation_id'],
                        log['creation_id'],
                        log['creation_name'],
                        log['category'],
                        log['evaluator_id'],
                        log['evaluator_name'],
                        log['criterion_name'],
                        log['criterion_type'],
                        log['score'],
                        log['logged_at']
                    )
                )

        elif filepath == ERROR_REPORTS_FILE:
            conn.execute("DELETE FROM error_reports")
            for report in data:
                conn.execute(
                    """
                    INSERT INTO error_reports (
                        id, creation_id, creation_name, evaluator_id, evaluator_name,
                        reported_total, note, status, reported_at, resolved_at, resolved_by
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        report['id'],
                        report['creation_id'],
                        report['creation_name'],
                        report['evaluator_id'],
                        report['evaluator_name'],
                        report.get('reported_total', 0),
                        report.get('note', ''),
                        report.get('status', 'pending'),
                        report.get('reported_at', datetime.now().isoformat()),
                        report.get('resolved_at'),
                        report.get('resolved_by')
                    )
                )

        elif filepath == ACTIVE_SESSIONS_FILE:
            conn.execute("DELETE FROM active_sessions")
            for active in data:
                conn.execute(
                    "INSERT INTO active_sessions (user_id, last_seen) VALUES (?, ?)",
                    (active['user_id'], active['last_seen'])
                )

        conn.commit()

# Inicializace výchozích dat
def initialize_data():
    create_tables()

    # Stav soutěže
    if table_is_empty('contest_state'):
        legacy_state = read_legacy_json(CONTEST_STATE_FILE, {'state': 'čekání'})
        save_json(CONTEST_STATE_FILE, legacy_state)
    
    # Uživatelé (vytvoříme výchozího admina)
    if table_is_empty('users'):
        legacy_users = read_legacy_json(USERS_FILE, None)
        if legacy_users:
            save_json(USERS_FILE, legacy_users)
        else:
            admin = {
                'id': 1,
                'name': 'Admin Admin',
                'login': 'admin.admin',
                'password': generate_password_hash('admin123'),
                'key': 'ADM01',
                'school': 'Systém',
                'role': 'admin',
                'permissions': ['Photoshop', 'Illustrator', 'Blender']
            }
            save_json(USERS_FILE, [admin])
    
    # Práce
    if table_is_empty('creations'):
        save_json(CREATIONS_FILE, read_legacy_json(CREATIONS_FILE, []))
    
    # Hodnocení
    if table_is_empty('evaluations'):
        save_json(EVALUATIONS_FILE, read_legacy_json(EVALUATIONS_FILE, []))
    
    # Kritéria hodnocení
    if table_is_empty('criteria'):
        default_criteria = {
            'Photoshop': [
                {'id': 1, 'name': 'Kompozice', 'type': 'slider', 'min': 0, 'max': 10},
                {'id': 2, 'name': 'Kreativita', 'type': 'slider', 'min': 0, 'max': 10},
                {'id': 3, 'name': 'Technické zpracování', 'type': 'slider', 'min': 0, 'max': 10}
            ],
            'Illustrator': [
                {'id': 1, 'name': 'Kompozice', 'type': 'slider', 'min': 0, 'max': 10},
                {'id': 2, 'name': 'Kreativita', 'type': 'slider', 'min': 0, 'max': 10},
                {'id': 3, 'name': 'Technické zpracování', 'type': 'slider', 'min': 0, 'max': 10}
            ],
            'Blender': [
                {'id': 1, 'name': 'Modelování', 'type': 'slider', 'min': 0, 'max': 10},
                {'id': 2, 'name': 'Osvětlení', 'type': 'slider', 'min': 0, 'max': 10},
                {'id': 3, 'name': 'Celkový dojem', 'type': 'slider', 'min': 0, 'max': 10}
            ]
        }
        legacy_criteria = read_legacy_json(CRITERIA_FILE, None)
        save_json(CRITERIA_FILE, legacy_criteria if legacy_criteria else default_criteria)

    if table_is_empty('evaluation_logs'):
        save_json(EVALUATION_LOGS_FILE, read_legacy_json(EVALUATION_LOGS_FILE, []))

    if table_is_empty('error_reports'):
        save_json(ERROR_REPORTS_FILE, read_legacy_json(ERROR_REPORTS_FILE, []))

    if table_is_empty('active_sessions'):
        save_json(ACTIVE_SESSIONS_FILE, read_legacy_json(ACTIVE_SESSIONS_FILE, []))

initialize_data()

def allowed_preview_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_PREVIEW_EXTENSIONS

def allowed_source_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_SOURCE_EXTENSIONS


def update_active_session(user_id):
    sessions = load_json(ACTIVE_SESSIONS_FILE, [])
    now_iso = datetime.now().isoformat()

    existing = next((s for s in sessions if s.get('user_id') == user_id), None)
    if existing:
        existing['last_seen'] = now_iso
    else:
        sessions.append({'user_id': user_id, 'last_seen': now_iso})

    save_json(ACTIVE_SESSIONS_FILE, sessions)


def get_online_evaluators_count():
    users = load_json(USERS_FILE)
    evaluator_ids = {u['id'] for u in users if u.get('role') != 'admin'}
    sessions = load_json(ACTIVE_SESSIONS_FILE, [])

    cutoff = datetime.now() - timedelta(seconds=60)
    still_active = []
    online_evaluators = set()

    for session_entry in sessions:
        ts = session_entry.get('last_seen')
        if not ts:
            continue

        try:
            last_seen = datetime.fromisoformat(ts)
        except ValueError:
            continue

        if last_seen >= cutoff:
            still_active.append(session_entry)
            if session_entry.get('user_id') in evaluator_ids:
                online_evaluators.add(session_entry.get('user_id'))

    save_json(ACTIVE_SESSIONS_FILE, still_active)
    return len(online_evaluators)

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        users = load_json(USERS_FILE)
        user = next((u for u in users if u['id'] == session['user_id']), None)
        if not user or user['role'] != 'admin':
            flash('Nemáte oprávnění k této stránce.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


# Základní kontrola přihlášení i pro statické soubory (blokuje např. /static/script.js)
@app.before_request
def enforce_login_for_all_routes():
    # Výjimky: samotný login a nezbytné styly pro načtení login stránky
    if request.endpoint == 'login':
        return

    if request.endpoint == 'static' and 'user_id' not in session:
        allowed_public_assets = ('style.css',)
        if not any(request.path.endswith(asset) for asset in allowed_public_assets):
            return redirect(url_for('login'))
        return

    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.endpoint != 'static':
        update_active_session(session['user_id'])

# Routy
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    users = load_json(USERS_FILE)
    user = next((u for u in users if u['id'] == session['user_id']), None)
    
    if not user:
        session.clear()
        return redirect(url_for('login'))
    
    if user['role'] == 'admin':
        return redirect(url_for('admin'))
    else:
        return redirect(url_for('evaluate'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login = request.form.get('login', '').strip()
        password = request.form.get('password', '')
        key = request.form.get('key', '').strip().upper()
        
        users = load_json(USERS_FILE)
        user = next((u for u in users if u['login'] == login and u['key'] == key), None)
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_role'] = user['role']
            flash(f'Vítejte, {user["name"]}!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Neplatné přihlašovací údaje.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    user_id = session.get('user_id')
    if user_id is not None:
        sessions = load_json(ACTIVE_SESSIONS_FILE, [])
        sessions = [s for s in sessions if s.get('user_id') != user_id]
        save_json(ACTIVE_SESSIONS_FILE, sessions)

    session.clear()
    flash('Byli jste odhlášeni.', 'success')
    return redirect(url_for('login'))

@app.route('/admin')
@admin_required
def admin():
    users = load_json(USERS_FILE)
    creations = load_json(CREATIONS_FILE)
    contest_state = load_json(CONTEST_STATE_FILE, {'state': 'čekání'})
    criteria = load_json(CRITERIA_FILE)
    reports = load_json(ERROR_REPORTS_FILE, [])
    pending_reports = [r for r in reports if r.get('status', 'pending') == 'pending']
    pending_reports.sort(key=lambda x: x.get('reported_at', ''), reverse=True)

    return render_template('admin.html', 
                         users=users, 
                         creations=creations, 
                         contest_state=contest_state['state'],
                         criteria=criteria,
                         pending_reports=pending_reports)

@app.route('/admin/user/add', methods=['POST'])
@admin_required
def add_user():
    users = load_json(USERS_FILE)
    
    # Generovat nové ID
    new_id = max([u['id'] for u in users]) + 1 if users else 1
    
    permissions = request.form.getlist('permissions')
    
    new_user = {
        'id': new_id,
        'name': request.form.get('name'),
        'login': request.form.get('login'),
        'password': generate_password_hash(request.form.get('password')),
        'key': request.form.get('key').upper(),
        'school': request.form.get('school'),
        'role': request.form.get('role'),
        'permissions': permissions
    }
    
    users.append(new_user)
    save_json(USERS_FILE, users)
    flash('Uživatel byl přidán.', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/user/delete/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    if user_id == session['user_id']:
        flash('Nemůžete smazat sám sebe.', 'error')
        return redirect(url_for('admin'))
    
    users = load_json(USERS_FILE)
    users = [u for u in users if u['id'] != user_id]
    save_json(USERS_FILE, users)
    flash('Uživatel byl smazán.', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/user/edit/<int:user_id>', methods=['POST'])
@admin_required
def edit_user(user_id):
    users = load_json(USERS_FILE)
    user = next((u for u in users if u['id'] == user_id), None)
    
    if user:
        user['name'] = request.form.get('name')
        user['login'] = request.form.get('login')
        user['school'] = request.form.get('school')
        user['role'] = request.form.get('role')
        user['key'] = request.form.get('key').upper()
        user['permissions'] = request.form.getlist('permissions')
        
        new_password = request.form.get('password')
        if new_password:
            user['password'] = generate_password_hash(new_password)
        
        save_json(USERS_FILE, users)
        flash('Uživatel byl upraven.', 'success')
    
    return redirect(url_for('admin'))

@app.route('/admin/creation/upload', methods=['POST'])
@admin_required
def upload_creation():
    if 'preview_file' not in request.files or 'source_file' not in request.files:
        flash('Musíte nahrát oba obrázky.', 'error')
        return redirect(url_for('admin'))
    
    preview_file = request.files['preview_file']
    source_file = request.files['source_file']
    
    if preview_file.filename == '' or source_file.filename == '':
        flash('Nebyl vybrán žádný soubor.', 'error')
        return redirect(url_for('admin'))
    
    if preview_file and allowed_preview_file(preview_file.filename) and source_file and allowed_source_file(source_file.filename):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        preview_filename = secure_filename(preview_file.filename)
        preview_filename = f"{timestamp}_preview_{preview_filename}"
        preview_path = os.path.join(app.config['UPLOAD_FOLDER'], preview_filename)
        preview_file.save(preview_path)
        
        source_filename = secure_filename(source_file.filename)
        source_filename = f"{timestamp}_detail_{source_filename}"
        source_path = os.path.join(app.config['UPLOAD_FOLDER'], source_filename)
        source_file.save(source_path)
        
        creations = load_json(CREATIONS_FILE)
        new_id = max([c['id'] for c in creations]) + 1 if creations else 1
        
        new_creation = {
            'id': new_id,
            'preview_filename': preview_filename,
            'source_filename': source_filename,
            'original_name': request.form.get('name', source_file.filename),
            'category': request.form.get('category'),
            'uploaded_at': datetime.now().isoformat()
        }
        
        creations.append(new_creation)
        save_json(CREATIONS_FILE, creations)
        flash('Práce byla nahrána.', 'success')
    else:
        flash('Nepovolený formát souboru.', 'error')
    
    return redirect(url_for('admin'))

@app.route('/admin/creation/delete/<int:creation_id>', methods=['POST'])
@admin_required
def delete_creation(creation_id):
    creations = load_json(CREATIONS_FILE)
    creation = next((c for c in creations if c['id'] == creation_id), None)
    
    if creation:
        # Smazat soubory
        preview_path = os.path.join(app.config['UPLOAD_FOLDER'], creation['preview_filename'])
        if os.path.exists(preview_path):
            os.remove(preview_path)
        
        source_path = os.path.join(app.config['UPLOAD_FOLDER'], creation['source_filename'])
        if os.path.exists(source_path):
            os.remove(source_path)
        
        # Smazat z databáze
        creations = [c for c in creations if c['id'] != creation_id]
        save_json(CREATIONS_FILE, creations)
        
        # Smazat hodnocení
        evaluations = load_json(EVALUATIONS_FILE)
        evaluations = [e for e in evaluations if e['creation_id'] != creation_id]
        save_json(EVALUATIONS_FILE, evaluations)
        
        flash('Práce byla smazána.', 'success')
    
    return redirect(url_for('admin'))

@app.route('/admin/contest/state', methods=['POST'])
@admin_required
def set_contest_state():
    new_state = request.form.get('state')
    save_json(CONTEST_STATE_FILE, {'state': new_state})
    flash(f'Stav soutěže nastaven na: {new_state}', 'success')
    return redirect(url_for('admin'))

@app.route('/evaluate')
@login_required
def evaluate():
    users = load_json(USERS_FILE)
    user = next((u for u in users if u['id'] == session['user_id']), None)
    
    if not user or user['role'] == 'admin':
        return redirect(url_for('admin'))
    
    contest_state = load_json(CONTEST_STATE_FILE, {'state': 'čekání'})
    
    if contest_state['state'] == 'čekání' or contest_state['state'] == 'pozastaveno':
        return render_template('waiting.html', state=contest_state['state'])
    
    if contest_state['state'] == 'ukončeno':
        return redirect(url_for('results'))
    
    # Načíst práce, které může hodnotit
    creations = load_json(CREATIONS_FILE)
    evaluations = load_json(EVALUATIONS_FILE)
    criteria = load_json(CRITERIA_FILE)
    
    # Filtrovat práce podle oprávnění
    allowed_creations = [c for c in creations if c['category'] in user['permissions']]
    
    # Zjistit, které již hodnotil
    user_evaluations = [e for e in evaluations if e['evaluator_id'] == user['id']]
    evaluated_ids = [e['creation_id'] for e in user_evaluations]
    
    # Práce k hodnocení - seřazené podle ID (sekvenční hodnocení)
    to_evaluate = [c for c in allowed_creations if c['id'] not in evaluated_ids]
    to_evaluate.sort(key=lambda x: x['id'])
    
    # Pokud jsou všechny ohodnocené, čekáme na ukončení
    if not to_evaluate:
        return render_template('waiting.html', state='všechny_ohodnoceno')
    
    # Vzít první neohodnocenou práci
    current_creation = to_evaluate[0]
    current_criteria = criteria.get(current_creation['category'], [])
    
    total_to_evaluate = len(allowed_creations)
    evaluated_count = len(evaluated_ids)
    
    return render_template('evaluate.html', 
                         creation=current_creation,
                         criteria=current_criteria,
                         progress={'current': evaluated_count + 1, 'total': total_to_evaluate},
                         user=user)

@app.route('/evaluate/submit', methods=['POST'])
@login_required
def submit_evaluation():
    creation_id = int(request.form.get('creation_id'))
    
    users = load_json(USERS_FILE)
    user = next((u for u in users if u['id'] == session['user_id']), None)
    
    evaluations = load_json(EVALUATIONS_FILE)
    creations = load_json(CREATIONS_FILE)
    
    creation = next((c for c in creations if c['id'] == creation_id), None)
    if not creation:
        flash('Práce nebyla nalezena.', 'error')
        return redirect(url_for('evaluate'))
    
    # Zkontrolovat, zda již nehodnotil
    existing = next((e for e in evaluations if e['creation_id'] == creation_id and e['evaluator_id'] == user['id']), None)
    
    if existing:
        flash('Tuto práci jste již hodnotili.', 'error')
        return redirect(url_for('evaluate'))
    
    # Získat hodnocení všech kritérií
    criteria = load_json(CRITERIA_FILE)
    category_criteria = criteria.get(creation['category'], [])
    
    scores = {}
    total = 0
    
    for criterion in category_criteria:
        field_name = f'criterion_{criterion["id"]}'
        value = request.form.get(field_name)
        
        if criterion['type'] == 'checkbox':
            score = 1 if value == 'on' else 0
        else:  # slider
            score = int(value) if value else 0
        
        scores[criterion['name']] = score
        total += score
    
    new_eval = {
        'id': max([e['id'] for e in evaluations]) + 1 if evaluations else 1,
        'creation_id': creation_id,
        'evaluator_id': user['id'],
        'evaluator_name': user['name'],
        'scores': scores,
        'total': total,
        'evaluated_at': datetime.now().isoformat()
    }
    
    evaluations.append(new_eval)
    save_json(EVALUATIONS_FILE, evaluations)

    evaluation_logs = load_json(EVALUATION_LOGS_FILE, [])
    next_log_id = max([l['id'] for l in evaluation_logs]) + 1 if evaluation_logs else 1

    for criterion in category_criteria:
        criterion_name = criterion['name']
        evaluation_logs.append({
            'id': next_log_id,
            'evaluation_id': new_eval['id'],
            'creation_id': creation_id,
            'creation_name': creation['original_name'],
            'category': creation['category'],
            'evaluator_id': user['id'],
            'evaluator_name': user['name'],
            'criterion_name': criterion_name,
            'criterion_type': criterion['type'],
            'score': scores.get(criterion_name, 0),
            'logged_at': datetime.now().isoformat()
        })
        next_log_id += 1

    save_json(EVALUATION_LOGS_FILE, evaluation_logs)
    
    flash('Hodnocení bylo uloženo.', 'success')
    return redirect(url_for('evaluate'))

@app.route('/results')
@login_required
def results():
    # Zkontrolovat stav soutěže - výsledky jsou viditelné až po ukončení
    users = load_json(USERS_FILE)
    user = next((u for u in users if u['id'] == session['user_id']), None)
    
    if user and user['role'] != 'admin':
        contest_state = load_json(CONTEST_STATE_FILE, {'state': 'čekání'})
        if contest_state['state'] != 'ukončeno':
            flash('Výsledky jsou dostupné pouze po skončení soutěže.', 'info')
            return redirect(url_for('evaluate'))
    
    creations = load_json(CREATIONS_FILE)
    evaluations = load_json(EVALUATIONS_FILE)
    
    # Seskupit výsledky podle kategorií
    categories = {}
    
    for creation in creations:
        category = creation['category']
        if category not in categories:
            categories[category] = []
        
        creation_evals = [e for e in evaluations if e['creation_id'] == creation['id']]
        
        if creation_evals:
            avg_total = sum([e['total'] for e in creation_evals]) / len(creation_evals)
            
            # Průměry jednotlivých kritérií
            avg_scores = {}
            if creation_evals:
                # Získat všechna kritéria z prvního hodnocení
                first_eval_scores = creation_evals[0]['scores']
                for criterion_name in first_eval_scores.keys():
                    criterion_values = [e['scores'].get(criterion_name, 0) for e in creation_evals]
                    avg_scores[criterion_name] = round(sum(criterion_values) / len(criterion_values), 2)
            
            categories[category].append({
                'creation': creation,
                'avg_scores': avg_scores,
                'avg_total': round(avg_total, 2),
                'eval_count': len(creation_evals)
            })
    
    # Seřadit každou kategorii podle celkového průměru
    for category in categories:
        categories[category].sort(key=lambda x: x['avg_total'], reverse=True)
    
    return render_template('results.html', categories=categories)


@app.route('/my-evaluations')
@login_required
def my_evaluations():
    users = load_json(USERS_FILE)
    user = next((u for u in users if u['id'] == session['user_id']), None)

    if not user:
        return redirect(url_for('login'))

    if user.get('role') == 'admin':
        return redirect(url_for('admin'))

    contest_state = load_json(CONTEST_STATE_FILE, {'state': 'čekání'})
    if contest_state.get('state') != 'ukončeno':
        flash('Vaše hodnocení budou dostupná po ukončení soutěže.', 'info')
        return redirect(url_for('evaluate'))

    evaluations = load_json(EVALUATIONS_FILE)
    creations = load_json(CREATIONS_FILE)
    creation_map = {c['id']: c for c in creations}

    user_evaluations = [e for e in evaluations if e.get('evaluator_id') == user['id']]
    user_evaluations.sort(key=lambda x: x.get('evaluated_at', ''), reverse=True)

    merged = []
    for evaluation in user_evaluations:
        creation = creation_map.get(evaluation['creation_id'])
        if not creation:
            continue
        merged.append({'evaluation': evaluation, 'creation': creation})

    return render_template('my_evaluations.html', my_evaluations=merged)


@app.route('/my-evaluations/report', methods=['POST'])
@login_required
def report_evaluation_issue():
    users = load_json(USERS_FILE)
    user = next((u for u in users if u['id'] == session['user_id']), None)

    if not user or user.get('role') == 'admin':
        flash('Tato akce není dostupná.', 'error')
        return redirect(url_for('index'))

    creation_id = int(request.form.get('creation_id'))
    note = request.form.get('note', '').strip()

    evaluations = load_json(EVALUATIONS_FILE)
    creations = load_json(CREATIONS_FILE)
    creation = next((c for c in creations if c['id'] == creation_id), None)
    my_eval = next((e for e in evaluations if e['creation_id'] == creation_id and e['evaluator_id'] == user['id']), None)

    if not creation or not my_eval:
        flash('Hodnocení nebylo nalezeno.', 'error')
        return redirect(url_for('my_evaluations'))

    reports = load_json(ERROR_REPORTS_FILE, [])
    new_report = {
        'id': max([r['id'] for r in reports]) + 1 if reports else 1,
        'creation_id': creation_id,
        'creation_name': creation['original_name'],
        'evaluator_id': user['id'],
        'evaluator_name': user['name'],
        'reported_total': my_eval.get('total', 0),
        'note': note,
        'status': 'pending',
        'reported_at': datetime.now().isoformat()
    }

    reports.append(new_report)
    save_json(ERROR_REPORTS_FILE, reports)
    flash('Nesrovnalost byla nahlášena administrátorovi.', 'success')
    return redirect(url_for('my_evaluations'))


@app.route('/admin/reports/resolve/<int:report_id>', methods=['POST'])
@admin_required
def resolve_report(report_id):
    reports = load_json(ERROR_REPORTS_FILE, [])
    report = next((r for r in reports if r['id'] == report_id), None)

    if report:
        report['status'] = 'resolved'
        report['resolved_at'] = datetime.now().isoformat()
        report['resolved_by'] = session.get('user_name', 'Admin')
        save_json(ERROR_REPORTS_FILE, reports)
        flash('Nahlášená nepřesnost byla označena jako vyřešená.', 'success')

    return redirect(url_for('admin'))


@app.route('/admin/evaluations')
@admin_required
def admin_evaluations():
    evaluations = load_json(EVALUATIONS_FILE)
    creations = load_json(CREATIONS_FILE)
    creation_map = {c['id']: c for c in creations}

    merged = []
    for evaluation in evaluations:
        creation = creation_map.get(evaluation['creation_id'])
        if not creation:
            continue
        merged.append({'evaluation': evaluation, 'creation': creation})

    merged.sort(key=lambda x: x['evaluation'].get('evaluated_at', ''), reverse=True)
    return render_template('admin_evaluations.html', all_evaluations=merged)


@app.route('/admin/live-stats')
@admin_required
def admin_live_stats():
    reports = load_json(ERROR_REPORTS_FILE, [])
    pending_reports = [r for r in reports if r.get('status', 'pending') == 'pending']
    pending_reports.sort(key=lambda x: x.get('reported_at', ''), reverse=True)

    return jsonify({
        'pending_reports_count': len(pending_reports),
        'pending_reports': pending_reports[:10]
    })

@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    from flask import send_from_directory
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# API pro správu kritérií
@app.route('/admin/criteria/add', methods=['POST'])
@admin_required
def add_criterion():
    category = request.form.get('category')
    name = request.form.get('name')
    crit_type = request.form.get('type')
    
    criteria = load_json(CRITERIA_FILE)
    
    if category not in criteria:
        criteria[category] = []
    
    new_id = max([c['id'] for c in criteria[category]]) + 1 if criteria[category] else 1
    
    new_criterion = {
        'id': new_id,
        'name': name,
        'type': crit_type
    }
    
    if crit_type == 'slider':
        new_criterion['min'] = int(request.form.get('min', 0))
        new_criterion['max'] = int(request.form.get('max', 10))
    
    criteria[category].append(new_criterion)
    save_json(CRITERIA_FILE, criteria)
    
    flash('Kritérium bylo přidáno.', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/criteria/delete', methods=['POST'])
@admin_required
def delete_criterion():
    category = request.form.get('category')
    criterion_id = int(request.form.get('criterion_id'))
    
    criteria = load_json(CRITERIA_FILE)
    
    if category in criteria:
        criteria[category] = [c for c in criteria[category] if c['id'] != criterion_id]
        save_json(CRITERIA_FILE, criteria)
        flash('Kritérium bylo smazáno.', 'success')
    
    return redirect(url_for('admin'))

@app.route('/admin/evaluations/delete-all', methods=['POST'])
@admin_required
def delete_all_evaluations():
    password = request.form.get('password', '').strip()
    
    if not password:
        flash('Heslo je povinné pro provedení této akce.', 'error')
        return redirect(url_for('admin'))
    
    # Ověřit heslo aktuálně přihlášeného admina
    users = load_json(USERS_FILE)
    admin_user = next((u for u in users if u['id'] == session['user_id']), None)
    
    if not admin_user or not check_password_hash(admin_user['password'], password):
        flash('Nesprávné heslo. Hodnocení nebyla smazána.', 'error')
        return redirect(url_for('admin'))
    
    # Smazat všechna hodnocení a evaluační logy
    save_json(EVALUATIONS_FILE, [])
    save_json(EVALUATION_LOGS_FILE, [])
    
    flash('Všechna hodnocení byla úspěšně smazána.', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/database')
@admin_required
def admin_database():
    tables = {}
    with get_db_connection() as conn:
        # Získat seznam všech tabulek
        table_names = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        
        for table_row in table_names:
            table_name = table_row['name']
            # Získat sloupce
            columns_info = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
            columns = [col['name'] for col in columns_info]
            
            # Získat data
            rows = conn.execute(f"SELECT * FROM {table_name}").fetchall()
            data = [dict(row) for row in rows]
            
            tables[table_name] = {
                'columns': columns,
                'data': data
            }
    
    return render_template('admin_database.html', tables=tables)

@app.route('/admin/database/execute', methods=['POST'])
@admin_required
def admin_database_execute():
    sql_query = request.form.get('query', '').strip()
    
    if not sql_query:
        flash('SQL dotaz je prázdný.', 'error')
        return redirect(url_for('admin_database'))
    
    try:
        with get_db_connection() as conn:
            # Povolit pouze SELECT, UPDATE, INSERT, DELETE
            query_upper = sql_query.upper().strip()
            if not any(query_upper.startswith(cmd) for cmd in ['SELECT', 'UPDATE', 'INSERT', 'DELETE']):
                flash('Povoleny jsou pouze SELECT, UPDATE, INSERT, DELETE dotazy.', 'error')
                return redirect(url_for('admin_database'))
            
            cursor = conn.execute(sql_query)
            conn.commit()
            
            if query_upper.startswith('SELECT'):
                results = cursor.fetchall()
                flash(f'Dotaz vrátil {len(results)} řádků.', 'success')
            else:
                flash(f'Dotaz proveden. Ovlivněno řádků: {cursor.rowcount}', 'success')
                
    except Exception as e:
        flash(f'Chyba SQL: {str(e)}', 'error')
    
    return redirect(url_for('admin_database'))

@app.route('/admin/database/table/<table_name>/delete/<int:row_id>', methods=['POST'])
@admin_required
def admin_database_delete_row(table_name, row_id):
    try:
        with get_db_connection() as conn:
            conn.execute(f"DELETE FROM {table_name} WHERE id = ?", (row_id,))
            conn.commit()
        flash(f'Záznam ID {row_id} byl smazán z tabulky {table_name}.', 'success')
    except Exception as e:
        flash(f'Chyba při mazání: {str(e)}', 'error')
    
    return redirect(url_for('admin_database'))

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=7780)
