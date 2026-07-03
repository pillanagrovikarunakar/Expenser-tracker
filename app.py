from flask import Flask, render_template, request, session, flash, redirect, url_for, g
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import re  # For email validation
import os
import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this to a random string in production

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'expense_tracker.db')

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

# Sources for income
INCOME_SOURCES = ['Salary', 'Freelance', 'Investments', 'Gifts', 'Other']

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
        if not re.match(r'^\d{10}$', mobile):
            flash('Mobile number must be exactly 10 digits.', 'danger')
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
    
    # 1. Fetch all expenses and incomes
    expenses = db.execute('SELECT * FROM expenses WHERE user_id = ? ORDER BY date DESC', (user_id,)).fetchall()
    incomes = db.execute('SELECT * FROM incomes WHERE user_id = ? ORDER BY date DESC', (user_id,)).fetchall()
    
    # 2. Calculate general totals
    total_income = sum(inc[2] for inc in incomes)
    total_expense = sum(exp[2] for exp in expenses)
    total_balance = total_income - total_expense
    
    # 3. Monthly calculations
    today = datetime.date.today()
    current_month_str = today.strftime('%Y-%m')
    
    # Previous month calculation
    first_of_this_month = today.replace(day=1)
    last_day_of_prev_month = first_of_this_month - datetime.timedelta(days=1)
    prev_month_str = last_day_of_prev_month.strftime('%Y-%m')
    
    current_month_income = sum(inc[2] for inc in incomes if inc[4][:7] == current_month_str)
    current_month_expense = sum(exp[2] for exp in expenses if exp[4][:7] == current_month_str)
    monthly_savings = current_month_income - current_month_expense
    
    prev_month_expense = sum(exp[2] for exp in expenses if exp[4][:7] == prev_month_str)
    
    # Previous Month Comparison
    if prev_month_expense > 0:
        pct_change = ((current_month_expense - prev_month_expense) / prev_month_expense) * 100
        comp_text = f"{'+' if pct_change >= 0 else ''}{pct_change:.1f}% from last month"
    else:
        if current_month_expense > 0:
            comp_text = "New spending this month"
        else:
            comp_text = "No expenses recorded"
            
    # 4. Highest Expense Category (current month)
    category_totals = {}
    for exp in expenses:
        if exp[4][:7] == current_month_str:
            category_totals[exp[3]] = category_totals.get(exp[3], 0) + exp[2]
            
    highest_category = "N/A"
    if category_totals:
        max_cat = max(category_totals, key=category_totals.get)
        highest_category = f"{max_cat} (${category_totals[max_cat]:.2f})"
        
    # 5. Latest Transactions (Merge and sort)
    latest_transactions = []
    for exp in expenses:
        latest_transactions.append({
            'id': exp[0],
            'type': 'Expense',
            'amount': exp[2],
            'category': exp[3],
            'date': exp[4],
            'description': exp[5] or 'N/A'
        })
    for inc in incomes:
        latest_transactions.append({
            'id': inc[0],
            'type': 'Income',
            'amount': inc[2],
            'category': inc[3],  # source
            'date': inc[4],
            'description': inc[5] or 'N/A'
        })
    latest_transactions.sort(key=lambda x: x['date'], reverse=True)
    latest_transactions = latest_transactions[:10]
    
    # 6. Chart 1: Monthly Income vs Expense
    monthly_data = {}
    for inc in incomes:
        m = inc[4][:7]
        if m not in monthly_data:
            monthly_data[m] = {'income': 0, 'expense': 0}
        monthly_data[m]['income'] += inc[2]
    for exp in expenses:
        m = exp[4][:7]
        if m not in monthly_data:
            monthly_data[m] = {'income': 0, 'expense': 0}
        monthly_data[m]['expense'] += exp[2]
        
    # Get last 6 months in chronological order
    sorted_months = sorted(list(monthly_data.keys()))[-6:]
    chart_months = sorted_months
    chart_monthly_income = [monthly_data[m]['income'] for m in sorted_months]
    chart_monthly_expense = [monthly_data[m]['expense'] for m in sorted_months]
    
    # Chart 2: Expense by Category (Pie Chart) - current month
    pie_category_totals = {}
    for exp in expenses:
        if exp[4][:7] == current_month_str:
            pie_category_totals[exp[3]] = pie_category_totals.get(exp[3], 0) + exp[2]
    if not pie_category_totals:
        # Fallback to overall
        for exp in expenses:
            pie_category_totals[exp[3]] = pie_category_totals.get(exp[3], 0) + exp[2]
            
    pie_labels = list(pie_category_totals.keys())
    pie_data = list(pie_category_totals.values())
    
    # Chart 3: Weekly Spending Trend (Last 7 days, day-by-day)
    weekly_labels = []
    weekly_data = []
    for i in range(6, -1, -1):
        day = today - datetime.timedelta(days=i)
        day_str = day.strftime('%Y-%m-%d')
        day_label = day.strftime('%a %d')
        day_total = sum(exp[2] for exp in expenses if exp[4] == day_str)
        weekly_labels.append(day_label)
        weekly_data.append(day_total)
        
    # Chart 4: Monthly Savings Chart
    chart_monthly_savings = [monthly_data[m]['income'] - monthly_data[m]['expense'] for m in sorted_months]
    
    return render_template(
        'dashboard.html',
        total_income=total_income,
        total_expense=total_expense,
        total_balance=total_balance,
        current_month_expense=current_month_expense,
        monthly_savings=monthly_savings,
        comp_text=comp_text,
        highest_category=highest_category,
        latest_transactions=latest_transactions,
        chart_months=chart_months,
        chart_monthly_income=chart_monthly_income,
        chart_monthly_expense=chart_monthly_expense,
        pie_labels=pie_labels,
        pie_data=pie_data,
        weekly_labels=weekly_labels,
        weekly_data=weekly_data,
        chart_monthly_savings=chart_monthly_savings
    )

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
        if category not in CATEGORIES:
            flash('Invalid category selected.', 'danger')
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

@app.route('/add_income', methods=['GET', 'POST'])
@login_required
def add_income():
    if request.method == 'POST':
        amount = request.form['amount']
        source = request.form['source']
        date = request.form['date']
        description = request.form['description'].strip()
        
        if not all([amount, source, date]):
            flash('Amount, source, and date are required.', 'danger')
            return redirect(url_for('add_income'))
        if source not in INCOME_SOURCES:
            flash('Invalid source selected.', 'danger')
            return redirect(url_for('add_income'))
        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError
        except ValueError:
            flash('Amount must be a positive number.', 'danger')
            return redirect(url_for('add_income'))
        
        db = get_db()
        db.execute('INSERT INTO incomes (user_id, amount, source, date, description) VALUES (?, ?, ?, ?, ?)',
                   (session['user_id'], amount, source, date, description))
        db.commit()
        flash('Income added successfully!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('add_income.html', sources=INCOME_SOURCES)

@app.route('/delete_income/<int:income_id>')
@login_required
def delete_income(income_id):
    db = get_db()
    db.execute('DELETE FROM incomes WHERE id = ? AND user_id = ?', (income_id, session['user_id']))
    db.commit()
    flash('Income deleted successfully!', 'success')
    return redirect(url_for('dashboard'))


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


if __name__ == '__main__':
    app.run(debug=True)