from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import pymysql
import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'exam-seating-secret-key'

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Nettur@123',  
    'database': 'exam_seating',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

def get_db():
    return pymysql.connect(**DB_CONFIG)

# Column to Year mapping
COLUMN_YEAR_MAP = {
    'A': 1, 'B': 2, 'C': 3, 'D': 4,
    'E': 1, 'F': 2, 'G': 3, 'H': 4, 'I': 1
}

# Column to Department Pair mapping
COLUMN_DEPT_PAIR = {
    # Updated pairs so selected columns alternate between two departments
    # A: alternate CE <-> CS, C: alternate ME <-> CS,
    # E: alternate CD <-> CS, H: alternate CE <-> CS
    'A': ['CE', 'CS'], 'B': ['ME', 'EC'], 'C': ['ME', 'CS'],
    'D': ['CE', 'EC'], 'E': ['CD', 'CS'], 'F': ['CE', 'ME'],
    'G': ['EC', 'CE'], 'H': ['CE', 'CS'], 'I': ['ME', 'CD']
}

# ==================== LOGIN DECORATORS ====================

def login_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session or session.get('role') != role:
                flash(f'Please login as {role}', 'danger')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ==================== START PAGE ====================

@app.route('/')
def index():
    return render_template('index.html')

# ==================== ADMIN ROUTES ====================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM admins WHERE username = %s AND password = %s", 
                      (username, password))
        admin = cursor.fetchone()
        conn.close()
        
        if admin:
            session['user_id'] = admin['id']
            session['role'] = 'admin'
            session['username'] = admin['username']
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid credentials', 'danger')
    
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
@login_required('admin')
def admin_dashboard():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) as count FROM students")
    student_count = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM halls")
    hall_count = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM invigilators")
    invigilator_count = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM exam_sessions")
    session_count = cursor.fetchone()['count']
    
    cursor.execute("""
        SELECT es.*, h.hall_name 
        FROM exam_sessions es 
        JOIN halls h ON es.hall_id = h.id 
        ORDER BY es.id DESC LIMIT 5
    """)
    recent_sessions = cursor.fetchall()
    
    conn.close()
    
    return render_template('admin_dashboard.html', 
                         student_count=student_count,
                         hall_count=hall_count,
                         invigilator_count=invigilator_count,
                         session_count=session_count,
                         recent_sessions=recent_sessions)

# ==================== ADMIN STUDENT MANAGEMENT ====================

@app.route('/admin/add_student', methods=['GET', 'POST'])
@login_required('admin')
def add_student():
    if request.method == 'POST':
        reg_num = request.form['register_number']
        name = request.form['name']
        dept = request.form['department']
        join_year = int(request.form['join_year'])
        current_year = calculate_current_year(join_year)
        
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO students (register_number, name, department, join_year, current_year)
                VALUES (%s, %s, %s, %s, %s)
            """, (reg_num, name, dept, join_year, current_year))
            conn.commit()
            flash('Student added!', 'success')
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
        finally:
            conn.close()
    
    return render_template('add_student.html')
import csv
import io

# ==================== VIEW ROUTES ====================




@app.route('/admin/bulk_upload_students', methods=['GET', 'POST'])
@login_required('admin')
def bulk_upload_students():
    if request.method == 'POST':
        if 'csv_file' not in request.files:
            flash('No file selected', 'danger')
            return redirect(url_for('bulk_upload_students'))
        
        file = request.files['csv_file']
        
        if file.filename == '':
            flash('No file selected', 'danger')
            return redirect(url_for('bulk_upload_students'))
        
        if not file.filename.endswith('.csv'):
            flash('Please upload a CSV file', 'danger')
            return redirect(url_for('bulk_upload_students'))
        
        # Read CSV
        try:
            stream = io.StringIO(file.stream.read().decode("utf-8-sig"), newline=None)
        except:
            stream = io.StringIO(file.stream.read().decode("latin-1"), newline=None)
        
        # Try to detect if first row is header
        sample = stream.read(500)
        stream.seek(0)
        
        # Check if first row contains text headers or data
        first_line = sample.split('\n')[0] if sample else ''
        has_header = any(word in first_line.lower() for word in ['register', 'name', 'dept', 'year', 'number'])
        
        if has_header:
            csv_reader = csv.DictReader(stream)
            # Normalize headers
            if csv_reader.fieldnames:
                csv_reader.fieldnames = [h.strip().replace('\ufeff', '').lower().replace(' ', '_') for h in csv_reader.fieldnames]
        else:
            # No header - use simple CSV reader with fixed positions
            csv_reader = csv.reader(stream)
        
        conn = get_db()
        cursor = conn.cursor()
        
        success_count = 0
        error_count = 0
        errors = []
        row_num = 1
        
        for row in csv_reader:
            row_num += 1
            
            try:
                # Debug
                print(f"Row {row_num}: {row}")
                
                # Handle both formats
                if isinstance(row, dict):
                    # DictReader (with headers)
                    reg_num = (row.get('register_number', '') or 
                              row.get('reg_no', '') or 
                              row.get('registernumber', '') or
                              row.get('register', '')).strip()
                    
                    name = (row.get('name', '') or 
                           row.get('student_name', '') or
                           row.get('studentname', '')).strip()
                    
                    dept = (row.get('department', '') or 
                           row.get('dept', '') or 
                           row.get('branch', '')).strip().upper()
                    
                    join_year_str = (row.get('join_year', '') or 
                                    row.get('joinyear', '') or 
                                    row.get('year', '') or
                                    row.get('batch', '')).strip()
                else:
                    # Simple reader (no headers) - assume order: reg_num, year, dept, name
                    if len(row) < 4:
                        continue
                    
                    reg_num = row[0].strip()
                    join_year_str = row[1].strip()
                    dept = row[2].strip().upper()
                    name = row[3].strip()
                
                # Clean register number
                reg_num = reg_num.replace('L', '').replace('l', '').replace('ECE', 'STM')
                
                # Ensure starts with STM
                if not reg_num.startswith('STM'):
                    # Try to extract and rebuild
                    if len(reg_num) >= 8 and reg_num[2:4].isdigit():
                        year = reg_num[2:4]
                        dept_code = reg_num[4:6] if len(reg_num) >= 6 else dept[:2]
                        roll = reg_num[-3:] if len(reg_num) >= 3 else '001'
                        reg_num = f"STM{year}{dept_code}{roll}"
                    else:
                        reg_num = 'STM' + reg_num
                
                # Convert batch format
                if join_year_str.startswith('2K') or join_year_str.startswith('2k'):
                    join_year = 2000 + int(join_year_str[2:])
                elif len(join_year_str) == 2:
                    join_year = 2000 + int(join_year_str)
                else:
                    join_year = int(join_year_str)
                
                current_year = calculate_current_year(join_year)
                
                # Validate
                if not reg_num or not name or not dept or not join_year:
                    raise ValueError("Missing required fields")
                
                # Check duplicate
                cursor.execute("SELECT id FROM students WHERE register_number = %s", (reg_num,))
                if cursor.fetchone():
                    raise ValueError(f"{reg_num} already exists")
                
                cursor.execute("""
                    INSERT INTO students (register_number, name, department, join_year, current_year, password)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (reg_num, name, dept, join_year, current_year, 'student123'))
                
                success_count += 1
                
            except Exception as e:
                error_count += 1
                errors.append(f"Row {row_num}: {str(e)}")
        
        conn.commit()
        conn.close()
        
        if success_count > 0:
            flash(f'Uploaded {success_count} students!', 'success')
        if error_count > 0:
            flash(f'{error_count} errors', 'warning')
            for error in errors[:5]:
                flash(error, 'danger')
        
        return redirect(url_for('view_students'))
    
    return render_template('bulk_upload_students.html')
    
@app.route('/admin/view_students')
@login_required('admin')
def view_students():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students ORDER BY register_number")
    students = cursor.fetchall()
    conn.close()
    return render_template('view_students.html', students=students)

# ==================== ADMIN HALL MANAGEMENT ====================

@app.route('/admin/add_hall', methods=['GET', 'POST'])
@login_required('admin')
def add_hall():
    if request.method == 'POST':
        hall_name = request.form['hall_name']
        total_rows = int(request.form['total_rows'])
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO halls (hall_name, total_rows, total_columns)
            VALUES (%s, %s, %s)
        """, (hall_name, total_rows, 9))
        conn.commit()
        conn.close()
        flash('Hall added!', 'success')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('add_hall.html')

@app.route('/admin/view_halls')
@login_required('admin')
def view_halls():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM halls")
    halls = cursor.fetchall()
    conn.close()
    return render_template('view_halls.html', halls=halls)

# ==================== ADMIN INVIGILATOR MANAGEMENT ====================

@app.route('/admin/add_invigilator', methods=['GET', 'POST'])
@login_required('admin')
def add_invigilator():
    if request.method == 'POST':
        staff_id = request.form['staff_id']
        name = request.form['name']
        dept = request.form.get('department', '')
        
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO invigilators (staff_id, name, department)
                VALUES (%s, %s, %s)
            """, (staff_id, name, dept))
            conn.commit()
            flash('Invigilator added!', 'success')
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            flash(f'Error: Staff ID must be unique', 'danger')
        finally:
            conn.close()
    
    return render_template('add_invigilator.html')

@app.route('/admin/view_invigilators')
@login_required('admin')
def view_invigilators():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM invigilators")
    invigilators = cursor.fetchall()
    conn.close()
    return render_template('view_invigilators.html', invigilators=invigilators)

# ==================== ADMIN SESSION MANAGEMENT ====================

# AJAX endpoint to return student count for a given year (used by dynamic form)
@app.route('/admin/student_count/<int:year>')
@login_required('admin')
def student_count_api(year):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM students WHERE current_year = %s", (year,))
    result = cursor.fetchone()
    conn.close()
    return jsonify({'year': year, 'count': result['count']})

# New multi--hall session creation route
@app.route('/admin/create_multi_hall_session', methods=['GET', 'POST'])
@login_required('admin')
def create_multi_hall_session():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM halls")
    halls = cursor.fetchall()
    conn.close()

    if request.method == 'POST':
        session_type = request.form['session_type']
        session_date = request.form['session_date']
        hall_ids = request.form.getlist('hall_ids')
        years_selected = request.form.getlist('years')

        # basic validations
        if not hall_ids:
            flash('Please select at least one hall', 'danger')
            return redirect(url_for('create_multi_hall_session'))
        if not years_selected:
            flash('Please select at least one year', 'danger')
            return redirect(url_for('create_multi_hall_session'))

        hall_ids = [int(h) for h in hall_ids]
        years = [int(y) for y in years_selected]

        # calculate total seating capacity
        conn = get_db()
        cursor = conn.cursor()
        format_ids = ','.join(['%s'] * len(hall_ids))
        cursor.execute(f"SELECT SUM(total_rows * total_columns) as capacity FROM halls WHERE id IN ({format_ids})", tuple(hall_ids))
        capacity = cursor.fetchone()['capacity'] or 0

        # compute total students (unallocated) for chosen years
        total_students = 0
        time_slot = '9:30 AM - 11:00 AM' if session_type == 'FN' else '2:30 PM - 4:00 PM'
        for y in years:
            cursor.execute("""
                SELECT COUNT(*) as cnt
                FROM students s
                WHERE s.current_year = %s
                AND s.id NOT IN (
                    SELECT a.student_id FROM allocations a
                    JOIN exam_sessions es ON a.session_id = es.id
                    WHERE es.session_date = %s AND es.time_slot = %s
                )
            """, (y, session_date, time_slot))
            total_students += cursor.fetchone()['cnt']

        if total_students > capacity:
            flash(f"Warning: {total_students} students but only {capacity} seats ({total_students-capacity} overflow)", 'warning')

        # create a session row for each hall and allocate sequentially
        session_ids = []
        years_csv = ','.join(str(y) for y in years)
        for hid in hall_ids:
            cursor.execute("""
                INSERT INTO exam_sessions (session_type, time_slot, session_date, years, hall_id)
                VALUES (%s, %s, %s, %s, %s)
            """, (session_type, time_slot, session_date, years_csv, hid))
            session_ids.append(cursor.lastrowid)
        conn.commit()

        # allocation loop (resembles generate_seating logic but proceeds hall by hall)
        total_allocated = 0
        inv_messages = []
        for sid, hid in zip(session_ids, hall_ids):
            cursor.execute("SELECT total_rows FROM halls WHERE id=%s", (hid,))
            hall = cursor.fetchone()
            total_rows = hall['total_rows']
            columns = ['A','B','C','D','E','F','G','H','I']

            # selected_years set for easier membership tests
            selected_years_set = set(years)
            buffer_columns = {'B', 'E', 'H'}
            selected_years_list = sorted(list(selected_years_set))
            fallback_idx = 0

            for col in columns:
                if len(selected_years_set) < 4 and col in buffer_columns:
                    continue

                mapped_year = COLUMN_YEAR_MAP[col]
                dept_pair = COLUMN_DEPT_PAIR[col]
                dept1, dept2 = dept_pair
                effective_year = None
                pre_fetched_dept_groups = None

                if mapped_year in selected_years_set:
                    effective_year = mapped_year
                else:
                    # pick best candidate from the remaining years
                    best_candidate = None
                    best_score = -1
                    best_groups = None
                    for cand in selected_years_list:
                        cand_groups = fetch_students_by_year_excluding(conn, cand, exclude_date=session_date, exclude_time_slot=time_slot)
                        c1 = len(cand_groups.get(dept1, []))
                        c2 = len(cand_groups.get(dept2, []))
                        if c1 > 0 and c2 > 0:
                            best_candidate = cand
                            best_groups = cand_groups
                            best_score = c1 + c2
                            break
                        if (c1 + c2) > best_score:
                            best_candidate = cand
                            best_groups = cand_groups
                            best_score = (c1 + c2)
                    if best_candidate and best_score > 0:
                        effective_year = best_candidate
                        pre_fetched_dept_groups = best_groups
                    else:
                        effective_year = selected_years_list[fallback_idx % len(selected_years_list)]
                        fallback_idx += 1

                if pre_fetched_dept_groups is not None:
                    dept_groups = pre_fetched_dept_groups
                else:
                    dept_groups = fetch_students_by_year_excluding(conn, effective_year, exclude_date=session_date, exclude_time_slot=time_slot)

                column_students = alternate_departments(dept_groups, dept_pair, total_rows)
                for row_idx, student in enumerate(column_students, start=1):
                    cursor.execute("""
                        INSERT INTO allocations 
                        (student_id, session_id, hall_id, `row_number`, `column_name`)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (student['id'], sid, hid, row_idx, col))
                    total_allocated += 1
            conn.commit()

            # automatically assign an invigilator for this hall/session
            invigilator, msg = assign_invigilator_auto(hid, sid)
            if invigilator:
                inv_messages.append(f"Hall {hid}: {msg}")
            else:
                inv_messages.append(f"Hall {hid}: {msg}")

        conn.close()
        unallocated = total_students - total_allocated
        if unallocated > 0:
            flash(f"{unallocated} students could not be allocated and will remain unassigned", 'warning')

        # combine seating and invigilator messages
        seat_msg = f"Seating generated for {total_allocated} students across {len(hall_ids)} halls"
        if inv_messages:
            seat_msg += "; " + " | ".join(inv_messages)
        flash(seat_msg, 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('multi_hall_session.html', halls=halls)

# @app.route('/admin/create_session', methods=['GET', 'POST'])
# @login_required('admin')
# def create_session():
#     conn = get_db()
#     cursor = conn.cursor()
#     cursor.execute("SELECT * FROM halls")
#     halls = cursor.fetchall()
#     conn.close()
    
#     if request.method == 'POST':
#         session_type = request.form['session_type']
#         dept = request.form['department']
#         year = int(request.form['year'])
#         hall_id = int(request.form['hall_id'])
#         time_slot = '9:30 AM - 11:00 AM' if session_type == 'FN' else '2:30 PM - 4:00 PM'
        
#         conn = get_db()
#         cursor = conn.cursor()
#         cursor.execute("""
#             INSERT INTO exam_sessions (session_type, time_slot, department, year, hall_id)
#             VALUES (%s, %s, %s, %s, %s)
#         """, (session_type, time_slot, dept, year, hall_id))
#         conn.commit()
#         session_id = cursor.lastrowid
#         conn.close()
#         flash('Session created!', 'success')
#         return redirect(url_for('admin_dashboard'))
    
#     return render_template('create_session.html', halls=halls)
@app.route('/admin/create_session', methods=['GET', 'POST'])
@login_required('admin')
def create_session():
    # existing single-hall session creation (unchanged)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM halls")
    halls = cursor.fetchall()

    if request.method == 'POST':
        session_type = request.form['session_type']
        hall_id = int(request.form['hall_id'])
        session_date = request.form['session_date']
        years_selected = request.form.getlist('years')

        if not years_selected:
            flash('Please select at least one year', 'danger')
            conn.close()
            return redirect(url_for('create_session'))

        years_csv = ','.join(years_selected)

        time_slot = '9:30 AM - 11:00 AM' if session_type == 'FN' else '2:30 PM - 4:00 PM'

        # Insert session with date and selected years
        cursor.execute("""
            INSERT INTO exam_sessions (session_type, time_slot, session_date, years, hall_id)
            VALUES (%s, %s, %s, %s, %s)
        """, (session_type, time_slot, session_date, years_csv, hall_id))

        conn.commit()
        session_id = cursor.lastrowid
        conn.close()

        # Redirect to seating generation for this session
        return redirect(url_for('generate_seating', session_id=session_id))

    conn.close()
    return render_template('create_session.html', halls=halls)


@app.route('/admin/view_sessions')
@login_required('admin')
def view_sessions():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT es.*, h.hall_name 
        FROM exam_sessions es 
        JOIN halls h ON es.hall_id = h.id 
        ORDER BY es.id DESC
    """)
    sessions = cursor.fetchall()
    conn.close()
    return render_template('view_sessions.html', sessions=sessions)


@app.route('/admin/view_allocation/<int:session_id>')
@login_required('admin')
def view_allocation(session_id):
    conn = get_db()
    cursor = conn.cursor()

    # Fetch session and hall info
    cursor.execute("SELECT es.*, h.hall_name, h.total_rows, h.total_columns FROM exam_sessions es JOIN halls h ON es.hall_id = h.id WHERE es.id = %s", (session_id,))
    es = cursor.fetchone()
    if not es:
        conn.close()
        flash('Session not found', 'danger')
        return redirect(url_for('view_sessions'))

    hall_id = es['hall_id']
    total_rows = es.get('total_rows') or es.get('total_rows', 0)
    try:
        total_rows = int(es['total_rows'])
    except Exception:
        total_rows = 0

    # Fetch invigilator assigned (if any)
    cursor.execute("""
        SELECT i.name as invigilator_name
        FROM allocated_invigilator ai
        JOIN invigilators i ON ai.invigilator_id = i.id
        WHERE ai.session_id = %s AND ai.hall_id = %s
        LIMIT 1
    """, (session_id, hall_id))
    inv = cursor.fetchone()
    inv_name = inv['invigilator_name'] if inv else 'N/A'

    # Prepare hall_info for template
    hall_info = {
        'hall_name': es.get('hall_name', 'N/A'),
        'session_type': es.get('session_type', ''),
        'time_slot': es.get('time_slot', ''),
        'subject': es.get('subject', 'N/A'),
        'invigilator_name': inv_name,
        'department': es.get('department', 'All'),
        'year': es.get('year', 'All'),
        'total_rows': total_rows
    }

    # Initialize grid A-I x rows
    columns = ['A','B','C','D','E','F','G','H','I']
    grid = {col: {r: None for r in range(1, hall_info['total_rows'] + 1)} for col in columns}

    # Fetch allocations and populate grid
    cursor.execute("""
        SELECT a.row_number, a.column_name, s.register_number, s.name, s.department
        FROM allocations a
        JOIN students s ON a.student_id = s.id
        WHERE a.session_id = %s AND a.hall_id = %s
    """, (session_id, hall_id))

    rows = cursor.fetchall()
    for r in rows:
        col = r['column_name']
        rownum = r['row_number']
        if col in grid and rownum in grid[col]:
            grid[col][rownum] = {
                'register_number': r.get('register_number'),
                'name': r.get('name'),
                'department': r.get('department')
            }

    conn.close()
    return render_template('view_allocation.html', session_id=session_id, hall_info=hall_info, grid=grid)


@app.route('/admin/report/<int:session_id>')
@login_required('admin')
def report(session_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT es.*, h.hall_name, h.total_rows, h.total_columns FROM exam_sessions es JOIN halls h ON es.hall_id = h.id WHERE es.id = %s", (session_id,))
    es = cursor.fetchone()
    if not es:
        conn.close()
        flash('Session not found', 'danger')
        return redirect(url_for('view_sessions'))

    hall_id = es['hall_id']
    try:
        total_rows = int(es['total_rows'])
    except Exception:
        total_rows = 0

    hall_info = {
        'hall_name': es.get('hall_name', 'N/A'),
        'session_type': es.get('session_type', ''),
        'time_slot': es.get('time_slot', ''),
        'subject': es.get('subject', 'N/A'),
        'invigilator_name': 'N/A',
        'department': es.get('department', 'All'),
        'year': es.get('year', 'All'),
        'total_rows': total_rows
    }

    # Get assigned invigilator if any
    cursor.execute("""
        SELECT i.name as invigilator_name
        FROM allocated_invigilator ai
        JOIN invigilators i ON ai.invigilator_id = i.id
        WHERE ai.session_id = %s AND ai.hall_id = %s
        LIMIT 1
    """, (session_id, hall_id))
    inv = cursor.fetchone()
    if inv:
        hall_info['invigilator_name'] = inv['invigilator_name']

    columns = ['A','B','C','D','E','F','G','H','I']
    grid = {col: {r: None for r in range(1, hall_info['total_rows'] + 1)} for col in columns}

    cursor.execute("""
        SELECT a.row_number, a.column_name, s.register_number, s.name, s.department
        FROM allocations a
        JOIN students s ON a.student_id = s.id
        WHERE a.session_id = %s AND a.hall_id = %s
    """, (session_id, hall_id))
    rows = cursor.fetchall()

    seat_list = []
    for r in rows:
        col = r['column_name']
        rownum = r['row_number']
        if col in grid and rownum in grid[col]:
            grid[col][rownum] = {
                'register_number': r.get('register_number'),
                'name': r.get('name'),
                'department': r.get('department')
            }

        seat_list.append({
            'column_name': col,
            'row_number': rownum,
            'register_number': r.get('register_number'),
            'student_name': r.get('name'),
            'department': r.get('department')
        })

    conn.close()
    return render_template('report.html', hall_info=hall_info, grid=grid, columns=columns, seat_list=seat_list)

# ==================== HELPER FUNCTIONS ====================

def calculate_current_year(join_year):
    """Calculate current academic year based on join year"""
    current_year = datetime.datetime.now().year
    current_month = datetime.datetime.now().month
    academic_year = current_year if current_month >= 6 else current_year - 1
    diff = academic_year - join_year
    current_academic_year = diff + 1
    if current_academic_year < 1:
        return 1
    elif current_academic_year > 4:
        return 4
    else:
        return current_academic_year

def get_column_letter(idx):
    """Convert column index (0-8) to letter (A-I)"""
    return ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I'][idx]

def fetch_students_by_year(conn, year):
    """Fetch all students for a specific year, grouped by department"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM students 
        WHERE current_year = %s 
        ORDER BY department, register_number
    """, (year,))
    students = cursor.fetchall()
    cursor.close()
    
    dept_groups = {}
    for student in students:
        dept = student['department']
        if dept not in dept_groups:
            dept_groups[dept] = []
        dept_groups[dept].append(student)
    
    return dept_groups

def fetch_students_by_year_excluding(conn, year, exclude_date=None, exclude_time_slot=None):
    """Fetch students for a specific year grouped by department, excluding those already allocated on a given date/time"""
    cursor = conn.cursor()
    if exclude_date and exclude_time_slot:
        cursor.execute("""
            SELECT * FROM students s
            WHERE s.current_year = %s
            AND s.id NOT IN (
                SELECT a.student_id FROM allocations a
                JOIN exam_sessions es ON a.session_id = es.id
                WHERE es.session_date = %s AND es.time_slot = %s
            )
            ORDER BY s.department, s.register_number
        """, (year, exclude_date, exclude_time_slot))
    else:
        cursor.execute("""
            SELECT * FROM students 
            WHERE current_year = %s 
            ORDER BY department, register_number
        """, (year,))

    students = cursor.fetchall()
    cursor.close()

    dept_groups = {}
    for student in students:
        dept = student['department']
        if dept not in dept_groups:
            dept_groups[dept] = []
        dept_groups[dept].append(student)

    return dept_groups

def alternate_departments(dept_groups, dept_pair, total_seats):
    """Alternate between two departments in round-robin fashion"""
    dept1, dept2 = dept_pair
    queue1 = dept_groups.get(dept1, []).copy()
    queue2 = dept_groups.get(dept2, []).copy()
    
    result = []
    use_first = True
    
    for i in range(total_seats):
        if use_first:
            if queue1:
                result.append(queue1.pop(0))
            elif queue2:
                result.append(queue2.pop(0))
            else:
                break
        else:
            if queue2:
                result.append(queue2.pop(0))
            elif queue1:
                result.append(queue1.pop(0))
            else:
                break
        
        use_first = not use_first
    
    return result

# ==================== AUTOMATIC INVIGILATOR ASSIGNMENT ====================

def get_least_workload_invigilator():
    """Fetch available invigilator with least workload"""
    conn = get_db()
    cursor = conn.cursor()
    # Treat NULL or differently-cased values as available, using COALESCE and LOWER
    cursor.execute("""
        SELECT i.id, i.name, i.department, COUNT(ai.id) as workload
        FROM invigilators i
        LEFT JOIN allocated_invigilator ai ON i.id = ai.invigilator_id
        WHERE LOWER(COALESCE(i.availability, 'Available')) = 'available'
        GROUP BY i.id
        ORDER BY workload ASC, i.id ASC
        LIMIT 1
    """)

    invigilator = cursor.fetchone()

    # If none explicitly available, fall back to any invigilator with least workload
    if not invigilator:
        cursor.execute("""
            SELECT i.id, i.name, i.department, COUNT(ai.id) as workload
            FROM invigilators i
            LEFT JOIN allocated_invigilator ai ON i.id = ai.invigilator_id
            GROUP BY i.id
            ORDER BY workload ASC, i.id ASC
            LIMIT 1
        """)
        invigilator = cursor.fetchone()

    conn.close()
    return invigilator

def assign_invigilator_auto(hall_id, session_id):
    """Automatically assign invigilator with least workload"""
    invigilator = get_least_workload_invigilator()
    
    if not invigilator:
        return None, "No available invigilators found"
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO allocated_invigilator (invigilator_id, hall_id, session_id)
            VALUES (%s, %s, %s)
        """, (invigilator['id'], hall_id, session_id))
        conn.commit()
        conn.close()
        
        return invigilator, f"Assigned {invigilator['name']} (Workload: {invigilator['workload']})"
    except Exception as e:
        conn.rollback()
        conn.close()
        return None, str(e)

# ==================== SEATING ALLOCATION ====================

@app.route('/admin/generate_seating/<int:session_id>',methods=['GET', 'POST'])
@login_required('admin')
def generate_seating(session_id):
    conn = get_db()
    cursor = conn.cursor()
    
    # Get session details (include date and years)
    cursor.execute("SELECT * FROM exam_sessions WHERE id = %s", (session_id,))
    exam_session = cursor.fetchone()
    
    if not exam_session:
        conn.close()
        flash('Session not found', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    hall_id = exam_session['hall_id']
    cursor.execute("SELECT total_rows FROM halls WHERE id = %s", (hall_id,))
    hall = cursor.fetchone()
    total_rows = hall['total_rows']
    
    # Clear existing allocations
    cursor.execute("DELETE FROM allocations WHERE session_id = %s", (session_id,))
    cursor.execute("DELETE FROM allocated_invigilator WHERE session_id = %s", (session_id,))
    
    # Generate seating
    total_allocated = 0
    columns = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I']

    # Parse selected years for this session
    years_csv = exam_session.get('years') or ''
    selected_years = set()
    try:
        selected_years = set(int(y) for y in years_csv.split(',') if y)
    except Exception:
        selected_years = set()

    session_date = exam_session.get('session_date')
    session_time_slot = exam_session.get('time_slot')

    # If not all four years are included, reserve columns B, E and H as buffers
    # For other columns whose mapped year is missing, fallback to selected years
    buffer_columns = {'B', 'E', 'H'}
    selected_years_list = sorted(list(selected_years)) if selected_years else []
    fallback_idx = 0

    for col in columns:
        # drop buffer columns when a year is missing to reduce malpractice risk
        if len(selected_years) < 4 and col in buffer_columns:
            continue

        mapped_year = COLUMN_YEAR_MAP[col]
        dept_pair = COLUMN_DEPT_PAIR[col]
        dept1, dept2 = dept_pair

        # Determine effective year to allocate into this column
        effective_year = None
        pre_fetched_dept_groups = None

        if mapped_year in selected_years:
            effective_year = mapped_year
        else:
            # If no years selected at all, nothing to do
            if not selected_years_list:
                continue

            # Prefer a selected year where both departments have students
            best_candidate = None
            best_score = -1
            best_groups = None

            for cand in selected_years_list:
                cand_groups = fetch_students_by_year_excluding(conn, cand, exclude_date=session_date, exclude_time_slot=session_time_slot)
                c1 = len(cand_groups.get(dept1, []))
                c2 = len(cand_groups.get(dept2, []))

                # immediate preference if both departments present
                if c1 > 0 and c2 > 0:
                    best_candidate = cand
                    best_groups = cand_groups
                    best_score = c1 + c2
                    break

                # otherwise prefer the candidate with most relevant students
                if (c1 + c2) > best_score:
                    best_candidate = cand
                    best_groups = cand_groups
                    best_score = (c1 + c2)

            if best_candidate and best_score > 0:
                effective_year = best_candidate
                pre_fetched_dept_groups = best_groups
            else:
                # fallback round-robin if none have students in these departments
                effective_year = selected_years_list[fallback_idx % len(selected_years_list)]
                fallback_idx += 1

        # Fetch students for the effective year (reuse pre-fetched if available)
        if pre_fetched_dept_groups is not None:
            dept_groups = pre_fetched_dept_groups
        else:
            dept_groups = fetch_students_by_year_excluding(conn, effective_year, exclude_date=session_date, exclude_time_slot=session_time_slot)

        column_students = alternate_departments(dept_groups, dept_pair, total_rows)

        for row_idx, student in enumerate(column_students, start=1):
            cursor.execute("""
                INSERT INTO allocations 
                (student_id, session_id, hall_id, `row_number`, `column_name`)
                VALUES (%s, %s, %s, %s, %s)
            """, (student['id'], session_id, hall_id, row_idx, col))
            total_allocated += 1
    # Commit seating inserts BEFORE assigning invigilator to avoid lock waits
    conn.commit()

    # AUTOMATIC INVIGILATOR ASSIGNMENT
    invigilator, message = assign_invigilator_auto(hall_id, session_id)

    conn.close()
    
    # inform about buffer columns if not all years were present
    extra_note = ''
    if len(selected_years) < 4:
        extra_note = ' Columns B, E and H left empty due to missing year.'

    if invigilator:
        flash(f'Seating generated for {total_allocated} students. {message}{extra_note}', 'success')
    else:
        flash(f'Seating generated but {message}{extra_note}', 'warning')
    
    return redirect(url_for('admin_dashboard'))

# ==================== STUDENT ROUTES ====================

@app.route('/student/login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        register_number = request.form['register_number']
        password = request.form['password']
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM students WHERE register_number = %s AND password = %s", 
                      (register_number, password))
        student = cursor.fetchone()
        conn.close()
        
        if student:
            session['user_id'] = student['id']
            session['role'] = 'student'
            session['register_number'] = student['register_number']
            session['name'] = student['name']
            return redirect(url_for('student_dashboard'))
        else:
            flash('Invalid registration number or password', 'danger')
    
    return render_template('student_login.html')

@app.route('/student/dashboard')
@login_required('student')
def student_dashboard():
    conn = get_db()
    cursor = conn.cursor()
    
    # Get student's seating allocation
    cursor.execute("""
        SELECT a.*, h.hall_name, es.session_type, es.time_slot,
               s.department, s.current_year AS year,
               ai.invigilator_id, i.name as invigilator_name
        FROM allocations a
        JOIN students s ON a.student_id = s.id
        JOIN halls h ON a.hall_id = h.id
        JOIN exam_sessions es ON a.session_id = es.id
        LEFT JOIN allocated_invigilator ai ON es.id = ai.session_id AND h.id = ai.hall_id
        LEFT JOIN invigilators i ON ai.invigilator_id = i.id
        WHERE a.student_id = %s
    """, (session['user_id'],))
    
    allocations = cursor.fetchall()
    conn.close()
    
    return render_template('student_dashboard.html', 
                         allocations=allocations,
                         student_name=session['name'],
                         register_number=session['register_number'])

# ==================== INVIGILATOR ROUTES ====================

@app.route('/invigilator/login', methods=['GET', 'POST'])
def invigilator_login():
    if request.method == 'POST':
        staff_id = request.form['staff_id']
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM invigilators WHERE staff_id = %s", (staff_id,))
        invigilator = cursor.fetchone()
        conn.close()
        
        if invigilator:
            session['user_id'] = invigilator['id']
            session['role'] = 'invigilator'
            session['staff_id'] = invigilator['staff_id']
            session['name'] = invigilator['name']
            return redirect(url_for('invigilator_dashboard'))
        else:
            flash('Invalid Staff ID', 'danger')
    
    return render_template('invigilator_login.html')

@app.route('/invigilator/dashboard')
@login_required('invigilator')
def invigilator_dashboard():
    conn = get_db()
    cursor = conn.cursor()
    
    # Get invigilator details
    cursor.execute("SELECT * FROM invigilators WHERE id = %s", (session['user_id'],))
    invigilator = cursor.fetchone()
    
    # Get assigned duties with workload count
    cursor.execute("""
        SELECT ai.*, h.hall_name, es.session_type, es.time_slot,
               NULL AS department, NULL AS year
        FROM allocated_invigilator ai
        JOIN halls h ON ai.hall_id = h.id
        JOIN exam_sessions es ON ai.session_id = es.id
        WHERE ai.invigilator_id = %s
        ORDER BY ai.assigned_date DESC
    """, (session['user_id'],))
    duties = cursor.fetchall()
    
    # Count total workload
    workload_count = len(duties)
    
    conn.close()
    
    return render_template('invigilator_dashboard.html',
                         invigilator=invigilator,
                         duties=duties,
                         workload_count=workload_count)

@app.route('/invigilator/update_availability', methods=['POST'])
@login_required('invigilator')
def update_availability():
    availability = request.form['availability']
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE invigilators SET availability = %s WHERE id = %s",
                  (availability, session['user_id']))
    conn.commit()
    conn.close()
    
    flash(f'Availability updated to {availability}', 'success')
    return redirect(url_for('invigilator_dashboard'))

# ==================== LOGOUT ====================

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)