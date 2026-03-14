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

# Hall columns are fixed A–I (9 columns)
HALL_COLUMNS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I']

# In the original implementation, columns were tied to specific years and department-pairs.
# Per updated requirements, columns must NOT belong to specific years anymore.
# Allocation is now primarily year-distribution driven (avoid same-year adjacency in the same row).

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

# New multi-hall session creation route
@app.route('/admin/create_multi_hall_session', methods=['GET', 'POST'])
@login_required('admin')
def create_multi_hall_session():
    """
    Updated multi-hall allocation:
    - Creates one exam_session per selected hall (same date/time/years).
    - Distributes students across halls in order, filling each hall row-wise with
      "no same-year adjacency in the same row" as much as possible.
    - If the last hall is partially used, auto-select columns to skip (prefer B, E, H).
    """
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

        if not hall_ids:
            flash('Please select at least one hall', 'danger')
            return redirect(url_for('create_multi_hall_session'))
        if not years_selected:
            flash('Please select at least one year', 'danger')
            return redirect(url_for('create_multi_hall_session'))

        hall_ids = [int(h) for h in hall_ids]
        years = sorted({int(y) for y in years_selected})

        time_slot = '9:30 AM - 11:00 AM' if session_type == 'FN' else '2:30 PM - 4:00 PM'
        years_csv = ','.join(str(y) for y in years)

        conn = get_db()
        cursor = conn.cursor()

        # calculate total seating capacity
        format_ids = ','.join(['%s'] * len(hall_ids))
        cursor.execute(
            f"SELECT SUM(total_rows * total_columns) as capacity FROM halls WHERE id IN ({format_ids})",
            tuple(hall_ids),
        )
        capacity = cursor.fetchone()['capacity'] or 0

        # load eligible students once (exclude those already seated for same date/time)
        by_year = fetch_available_students_by_year(
            conn,
            years,
            exclude_date=session_date,
            exclude_time_slot=time_slot,
            session_id=None,
        )
        total_students = sum(len(q) for q in by_year.values())

        if total_students > capacity:
            flash(
                f"Warning: {total_students} students but only {capacity} seats ({total_students - capacity} overflow)",
                'warning',
            )

        # create a session row for each hall
        session_ids = []
        for hid in hall_ids:
            cursor.execute(
                """
                INSERT INTO exam_sessions (session_type, time_slot, session_date, years, hall_id)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (session_type, time_slot, session_date, years_csv, hid),
            )
            session_ids.append(cursor.lastrowid)
        conn.commit()

        total_allocated = 0
        inv_messages = []

        # allocate hall by hall using the same global queues so distribution is across halls
        remaining = sum(len(q) for q in by_year.values())
        for sid, hid in zip(session_ids, hall_ids):
            if remaining <= 0:
                break

            cursor.execute("SELECT total_rows FROM halls WHERE id=%s", (hid,))
            hall = cursor.fetchone()
            total_rows = int(hall['total_rows']) if hall else 0

            columns_to_use = choose_columns_to_use(total_rows, remaining)
            prev_year_in_row = {r: None for r in range(1, total_rows + 1)}

            for r in range(1, total_rows + 1):
                for c in columns_to_use:
                    if remaining <= 0:
                        break

                    forbidden = prev_year_in_row[r]
                    y = pick_year_for_seat(by_year, forbidden_year=forbidden)
                    if y is None:
                        break

                    student = by_year[y].pop(0)
                    cursor.execute(
                        """
                        INSERT INTO allocations
                        (student_id, session_id, hall_id, `row_number`, `column_name`)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (student['id'], sid, hid, r, c),
                    )
                    total_allocated += 1
                    remaining -= 1
                    prev_year_in_row[r] = y

                if remaining <= 0:
                    break

            conn.commit()

            # automatically assign an invigilator for this hall/session
            invigilator, msg = assign_invigilator_auto(hid, sid)
            inv_messages.append(f"Hall {hid}: {msg}")

        conn.close()

        unallocated = total_students - total_allocated
        if unallocated > 0:
            flash(f"{unallocated} students could not be allocated and will remain unassigned", 'warning')

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

@app.route('/admin/delete_session/<int:session_id>', methods=['POST'])
@login_required('admin')
def delete_session(session_id):
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Remove any seating allocations and invigilator allocations
        cursor.execute("DELETE FROM allocations WHERE session_id = %s", (session_id,))
        cursor.execute("DELETE FROM allocated_invigilator WHERE session_id = %s", (session_id,))
        cursor.execute("DELETE FROM exam_sessions WHERE id = %s", (session_id,))
        conn.commit()
        flash('Session deleted successfully', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error deleting session: {str(e)}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('view_sessions'))


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

def fetch_available_students_by_year(conn, years, exclude_date=None, exclude_time_slot=None, session_id=None):
    """
    Fetch students grouped by current_year, excluding those already allocated for the same date/time.
    Also optionally excludes students already allocated in the same session_id.
    Returns: {year_int: [student_dict, ...]} ordered by register_number.
    """
    cursor = conn.cursor()
    params = []
    where = []
    where.append("s.current_year IN (" + ",".join(["%s"] * len(years)) + ")")
    params.extend(list(years))

    if exclude_date and exclude_time_slot:
        where.append("""
            s.id NOT IN (
                SELECT a.student_id
                FROM allocations a
                JOIN exam_sessions es ON a.session_id = es.id
                WHERE es.session_date = %s AND es.time_slot = %s
            )
        """)
        params.extend([exclude_date, exclude_time_slot])

    if session_id is not None:
        where.append("s.id NOT IN (SELECT student_id FROM allocations WHERE session_id = %s)")
        params.append(session_id)

    query = f"""
        SELECT s.*
        FROM students s
        WHERE {' AND '.join(where)}
        ORDER BY s.current_year, s.register_number
    """
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    cursor.close()

    by_year = {int(y): [] for y in years}
    for r in rows:
        by_year[int(r["current_year"])].append(r)
    return by_year

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

def choose_columns_to_use(total_rows, remaining_students):
    """
    Choose which columns (A–I) to use in a hall when remaining_students < capacity.
    - Always uses fixed column set A–I, but may skip some columns to avoid sparse middle columns.
    - Prefer skipping 'buffer' middle columns B, E, H first.
    - Ensures enough seats: len(cols_used) * total_rows >= remaining_students.
    Returns: list of columns to use, in left-to-right order.
    """
    columns = HALL_COLUMNS.copy()
    capacity = total_rows * len(columns)
    if remaining_students >= capacity:
        return columns

    needed_cols = (remaining_students + total_rows - 1) // total_rows  # ceil
    needed_cols = max(1, min(9, needed_cols))

    # Preferred skip order: middle columns first, then near-middle to keep spread even
    skip_preference = ['B', 'E', 'H', 'D', 'F', 'C', 'G', 'A', 'I']

    cols_used = set(columns)
    # remove until we have exactly needed_cols
    to_remove = len(columns) - needed_cols
    for c in skip_preference:
        if to_remove <= 0:
            break
        if c in cols_used:
            cols_used.remove(c)
            to_remove -= 1

    # keep original order
    return [c for c in columns if c in cols_used]


def pick_year_for_seat(by_year_queues, forbidden_year=None):
    """
    Pick next year to seat, trying to avoid forbidden_year.
    Greedy: pick year with most remaining students, excluding forbidden if possible.
    Returns year int or None.
    """
    candidates = []
    for y, q in by_year_queues.items():
        if q:
            candidates.append((len(q), y))
    if not candidates:
        return None

    # try best excluding forbidden
    candidates.sort(reverse=True)
    for _, y in candidates:
        if forbidden_year is None or y != forbidden_year:
            return y

    # if only forbidden available
    return candidates[0][1]

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

@app.route('/admin/generate_seating/<int:session_id>', methods=['GET', 'POST'])
@login_required('admin')
def generate_seating(session_id):
    """
    Updated seating algorithm:
    - Columns A–I fixed, but NOT tied to specific years.
    - Primary constraint: avoid same-year adjacency within the same row across adjacent columns.
    - Avoid allocating the same student twice in the same exam session.
    - If remaining students don't fill a hall, automatically choose columns to skip (prefer B, E, H).
    """
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM exam_sessions WHERE id = %s", (session_id,))
    exam_session = cursor.fetchone()
    if not exam_session:
        conn.close()
        flash('Session not found', 'danger')
        return redirect(url_for('admin_dashboard'))

    hall_id = exam_session['hall_id']
    cursor.execute("SELECT total_rows FROM halls WHERE id = %s", (hall_id,))
    hall = cursor.fetchone()
    total_rows = int(hall['total_rows']) if hall else 0

    # Clear existing allocations for this session/hall
    cursor.execute("DELETE FROM allocations WHERE session_id = %s", (session_id,))
    cursor.execute("DELETE FROM allocated_invigilator WHERE session_id = %s", (session_id,))

    years_csv = exam_session.get('years') or ''
    try:
        selected_years = sorted({int(y) for y in years_csv.split(',') if y.strip()})
    except Exception:
        selected_years = []

    if not selected_years:
        conn.commit()
        conn.close()
        flash('No years selected for this session', 'danger')
        return redirect(url_for('admin_dashboard'))

    session_date = exam_session.get('session_date')
    session_time_slot = exam_session.get('time_slot')

    # Load all eligible students grouped by year (excluding same date/time allocations and this session allocations)
    by_year = fetch_available_students_by_year(
        conn,
        selected_years,
        exclude_date=session_date,
        exclude_time_slot=session_time_slot,
        session_id=session_id,
    )

    total_remaining = sum(len(q) for q in by_year.values())
    if total_remaining == 0:
        conn.commit()
        invigilator, message = assign_invigilator_auto(hall_id, session_id)
        conn.close()
        flash(f'No eligible students available to allocate. {message}', 'warning')
        return redirect(url_for('admin_dashboard'))

    # Column selection (auto-skip for partial usage)
    columns_to_use = choose_columns_to_use(total_rows, total_remaining)

    # Seat filling order: by rows, left-to-right columns.
    # Enforce "no same-year adjacency in same row" against previous placed seat in that row.
    total_allocated = 0
    prev_year_in_row = {r: None for r in range(1, total_rows + 1)}

    for r in range(1, total_rows + 1):
        for c in columns_to_use:
            # If no students left, stop completely
            if total_remaining <= 0:
                break

            forbidden = prev_year_in_row[r]
            y = pick_year_for_seat(by_year, forbidden_year=forbidden)
            if y is None:
                break

            student = by_year[y].pop(0)
            cursor.execute(
                """
                INSERT INTO allocations
                (student_id, session_id, hall_id, `row_number`, `column_name`)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (student['id'], session_id, hall_id, r, c),
            )

            total_allocated += 1
            total_remaining -= 1
            prev_year_in_row[r] = y

        if total_remaining <= 0:
            break

    conn.commit()

    invigilator, message = assign_invigilator_auto(hall_id, session_id)
    conn.close()

    skipped = [col for col in HALL_COLUMNS if col not in columns_to_use]
    skipped_note = f" Skipped columns: {', '.join(skipped)}." if skipped else ""
    if invigilator:
        flash(f'Seating generated for {total_allocated} students. {message}.{skipped_note}', 'success')
    else:
        flash(f'Seating generated for {total_allocated} students but {message}.{skipped_note}', 'warning')

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
