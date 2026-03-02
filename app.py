from flask import Flask, render_template, request, redirect, url_for, flash, session
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
    'A': ['CS', 'CE'], 'B': ['ME', 'EC'], 'C': ['CS', 'ME'],
    'D': ['CE', 'EC'], 'E': ['CD', 'CS'], 'F': ['CE', 'ME'],
    'G': ['EC', 'CD'], 'H': ['CS', 'CE'], 'I': ['ME', 'CD']
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
        
        # Read CSV with proper encoding handling
        try:
            # Try UTF-8 first
            stream = io.StringIO(file.stream.read().decode("utf-8-sig"), newline=None)
        except:
            # Fallback to latin-1
            stream = io.StringIO(file.stream.read().decode("latin-1"), newline=None)
        
        csv_reader = csv.DictReader(stream)
        
        # Debug: print headers
        headers = csv_reader.fieldnames
        print(f"CSV Headers: {headers}")
        
        # Normalize headers (remove BOM, spaces, lowercase)
        if headers:
            csv_reader.fieldnames = [h.strip().replace('\ufeff', '').lower() for h in headers]
        
        conn = get_db()
        cursor = conn.cursor()
        
        success_count = 0
        error_count = 0
        errors = []
        row_num = 1
        
        for row in csv_reader:
            row_num += 1
            try:
                # Debug: print row
                print(f"Processing row {row_num}: {row}")
                
                # Get values with flexible key matching
                reg_num = row.get('register_number', '').strip() or row.get('register number', '').strip()
                name = row.get('name', '').strip()
                dept = row.get('department', '').strip().upper() or row.get('dept', '').strip().upper()
                join_year_str = row.get('join_year', '').strip() or row.get('join year', '').strip()
                
                if not reg_num:
                    raise ValueError("Register number is empty")
                if not name:
                    raise ValueError("Name is empty")
                if not dept:
                    raise ValueError("Department is empty")
                if not join_year_str:
                    raise ValueError("Join year is empty")
                
                join_year = int(join_year_str)
                current_year = calculate_current_year(join_year)
                
                cursor.execute("""
                    INSERT INTO students (register_number, name, department, join_year, current_year)
                    VALUES (%s, %s, %s, %s, %s)
                """, (reg_num, name, dept, join_year, current_year))
                success_count += 1
                
            except Exception as e:
                error_count += 1
                reg = row.get('register_number', 'Row ' + str(row_num))
                errors.append(f"{reg}: {str(e)}")
        
        conn.commit()
        conn.close()
        
        flash(f'Uploaded {success_count} students successfully. {error_count} errors.', 
              'success' if error_count == 0 else 'warning')
        
        if errors:
            for error in errors[:10]:
                flash(error, 'danger')
    
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

@app.route('/admin/create_session', methods=['GET', 'POST'])
@login_required('admin')
def create_session():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM halls")
    halls = cursor.fetchall()
    conn.close()
    
    if request.method == 'POST':
        session_type = request.form['session_type']
        dept = request.form['department']
        year = int(request.form['year'])
        hall_id = int(request.form['hall_id'])
        time_slot = '9:30 AM - 11:00 AM' if session_type == 'FN' else '2:30 PM - 4:00 PM'
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO exam_sessions (session_type, time_slot, department, year, hall_id)
            VALUES (%s, %s, %s, %s, %s)
        """, (session_type, time_slot, dept, year, hall_id))
        conn.commit()
        session_id = cursor.lastrowid
        conn.close()
        flash('Session created!', 'success')
        return redirect(url_for('admin_dashboard'))
    
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
    
    cursor.execute("""
        SELECT i.id, i.name, i.department, COUNT(ai.id) as workload
        FROM invigilators i
        LEFT JOIN allocated_invigilator ai ON i.id = ai.invigilator_id
        WHERE i.availability = 'Available'
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

@app.route('/admin/generate_seating/<int:session_id>', methods=['POST'])
@login_required('admin')
def generate_seating(session_id):
    conn = get_db()
    cursor = conn.cursor()
    
    # Get session details
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
    
    for col in columns:
        year = COLUMN_YEAR_MAP[col]
        dept_pair = COLUMN_DEPT_PAIR[col]
        
        dept_groups = fetch_students_by_year(conn, year)
        column_students = alternate_departments(dept_groups, dept_pair, total_rows)
        
        for row_idx, student in enumerate(column_students, start=1):
            cursor.execute("""
                INSERT INTO allocations 
                (student_id, session_id, hall_id, `row_number`, `column_name`)
                VALUES (%s, %s, %s, %s, %s)
            """, (student['id'], session_id, hall_id, row_idx, col))
            total_allocated += 1
    
    # AUTOMATIC INVIGILATOR ASSIGNMENT
    invigilator, message = assign_invigilator_auto(hall_id, session_id)
    
    conn.commit()
    conn.close()
    
    if invigilator:
        flash(f'Seating generated for {total_allocated} students. {message}', 'success')
    else:
        flash(f'Seating generated but {message}', 'warning')
    
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
        SELECT a.*, h.hall_name, es.session_type, es.time_slot, es.department, es.year,
               ai.invigilator_id, i.name as invigilator_name
        FROM allocations a
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
        SELECT ai.*, h.hall_name, es.session_type, es.time_slot, es.department, es.year
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