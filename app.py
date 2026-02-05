from flask import Flask, render_template, request, session, flash, redirect, url_for, g
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import re  # For email validation

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this to a random string in production

DATABASE = 'expense_tracker.db'

# Helper function to get DB connection
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

# Close DB connection after request
@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# Categories for expenses
CATEGORIES = ['Food', 'Travel', 'Rent', 'Shopping']

# Route decorators for protected pages
def login_required(f):
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip()
        mobile = request.form['mobile'].strip()
        password = request.form['password']
        
        # Validation
        if not all([username, email, mobile, password]):
            flash('All fields are required.', 'danger')
            return redirect(url_for('register'))
        if not re.match(r'^[a-zA-Z0-9._%+-]+@gmail\.com$', email):
            flash('Email must be a valid Gmail address.', 'danger')
            return redirect(url_for('register'))
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return redirect(url_for('register'))
        
        hashed_password = generate_password_hash(password)
        db = get_db()
        try:
            db.execute('INSERT INTO users (username, email, mobile, password) VALUES (?, ?, ?, ?)',
                       (username, email, mobile, hashed_password))
            db.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username, email, or mobile already exists.', 'danger')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form['identifier'].strip()  # Can be username, email, or mobile
        password = request.form['password']
        
        if not identifier or not password:
            flash('All fields are required.', 'danger')
            return redirect(url_for('login'))
        
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ? OR email = ? OR mobile = ?',
                          (identifier, identifier, identifier)).fetchone()
        if user and check_password_hash(user[4], password):  # user[4] is password
            session['user_id'] = user[0]
            session['username'] = user[1]
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials.', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))

@app.route('/forgot', methods=['GET', 'POST'])
def forgot():
    if request.method == 'POST':
        identifier = request.form['identifier'].strip()
        new_password = request.form['new_password']
        
        if not identifier or not new_password:
            flash('All fields are required.', 'danger')
            return redirect(url_for('forgot'))
        if len(new_password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return redirect(url_for('forgot'))
        
        db = get_db()
        hashed_password = generate_password_hash(new_password)
        cursor = db.execute('UPDATE users SET password = ? WHERE username = ? OR email = ? OR mobile = ?',
                            (hashed_password, identifier, identifier, identifier))
        if cursor.rowcount > 0:
            db.commit()
            flash('Password reset successful! Please log in.', 'success')
            return redirect(url_for('login'))
        else:
            flash('User not found.', 'danger')
    
    return render_template('forgot.html')

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']
    db = get_db()
    expenses = db.execute('SELECT * FROM expenses WHERE user_id = ? ORDER BY date DESC', (user_id,)).fetchall()
    total_expense = sum(exp[2] for exp in expenses)  # exp[2] is amount
    
    # Prepare data for charts
    category_data = {}
    date_data = {}
    for exp in expenses:
        category = exp[3]
        date = exp[4][:7]  # YYYY-MM for monthly grouping
        amount = exp[2]
        category_data[category] = category_data.get(category, 0) + amount
        date_data[date] = date_data.get(date, 0) + amount
    
    # Pie chart: categories
    pie_labels = list(category_data.keys())
    pie_data = list(category_data.values())
    
    # Bar chart: dates
    bar_labels = list(date_data.keys())
    bar_data = list(date_data.values())
    
    return render_template('dashboard.html', expenses=expenses, total_expense=total_expense,
                           pie_labels=pie_labels, pie_data=pie_data,
                           bar_labels=bar_labels, bar_data=bar_data)

@app.route('/add_expense', methods=['GET', 'POST'])
@login_required
def add_expense():
    if request.method == 'POST':
        amount = request.form['amount']
        category = request.form['category']
        date = request.form['date']
        description = request.form['description'].strip()
        
        if not all([amount, category, date]):
            flash('Amount, category, and date are required.', 'danger')
            return redirect(url_for('add_expense'))
        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError
        except ValueError:
            flash('Amount must be a positive number.', 'danger')
            return redirect(url_for('add_expense'))
        
        db = get_db()
        db.execute('INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)',
                   (session['user_id'], amount, category, date, description))
        db.commit()
        flash('Expense added successfully!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('add_expense.html', categories=CATEGORIES)

@app.route('/delete_expense/<int:expense_id>')
@login_required
def delete_expense(expense_id):
    db = get_db()
    db.execute('DELETE FROM expenses WHERE id = ? AND user_id = ?', (expense_id, session['user_id']))
    db.commit()
    flash('Expense deleted successfully!', 'success')
    return redirect(url_for('dashboard'))
# ... (rest of app.py remains the same)

@app.route('/stats')
@login_required
def stats():
    user_id = session['user_id']
    db = get_db()
    expenses = db.execute('SELECT * FROM expenses WHERE user_id = ?', (user_id,)).fetchall()
    
    # Prepare data for category pie chart
    category_data = {}
    for exp in expenses:
        category = exp[3]
        amount = exp[2]
        category_data[category] = category_data.get(category, 0) + amount
    
    pie_labels = list(category_data.keys())
    pie_data = list(category_data.values())
    
    return render_template('stats.html', pie_labels=pie_labels, pie_data=pie_data)

# ... (rest of app.py remains the same)

if __name__ == '__main__':
    app.run(debug=True)