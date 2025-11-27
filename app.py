from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import os
from dotenv import load_dotenv
import pickle
import numpy as np
from functools import wraps
from datetime import timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import json

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'mohit_secret_key_change_in_production')

# Session configuration
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# Load ML model
model = pickle.load(open('model.pkl', 'rb'))

# Simple JSON-based user storage (in production, use a real database)
USERS_FILE = 'users.json'

def load_users():
    """Load users from JSON file"""
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_users(users):
    """Save users to JSON file"""
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    if session.get('user_id'):
        return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('user_id'):
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        
        users = load_users()
        
        if email in users and check_password_hash(users[email]['password'], password):
            # Login successful
            session.clear()
            session['user_id'] = email
            session['user_name'] = users[email]['name']
            session.permanent = True
            
            print(f"✅ User logged in: {email}")
            flash(f'Welcome back, {users[email]["name"]}!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid email or password.', 'error')
    
    return render_template('login_simple.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if session.get('user_id'):
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validation
        if not name or not email or not password:
            flash('All fields are required.', 'error')
            return render_template('register_simple.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return render_template('register_simple.html')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('register_simple.html')
        
        users = load_users()
        
        if email in users:
            flash('Email already registered. Please login.', 'error')
            return redirect(url_for('login'))
        
        # Create new user
        users[email] = {
            'name': name,
            'email': email,
            'password': generate_password_hash(password)
        }
        save_users(users)
        
        # Auto login after registration
        session.clear()
        session['user_id'] = email
        session['user_name'] = name
        session.permanent = True
        
        print(f"✅ New user registered: {email}")
        flash(f'Welcome, {name}! Your account has been created.', 'success')
        return redirect(url_for('home'))
    
    return render_template('register_simple.html')

@app.route('/home', methods=['GET', 'POST'])
@login_required
def home():
    if request.method == 'POST':
        try:
            # Get user-friendly inputs
            bedrooms = float(request.form['bedrooms'])
            bathrooms = float(request.form['bathrooms'])
            sqft_living = float(request.form['sqft_living'])
            sqft_lot = float(request.form['sqft_lot'])
            floors = float(request.form.get('floors', 1))
            yr_built = float(request.form['yr_built'])
            condition = float(request.form['condition'])
            
            # Optional fields with smart defaults
            grade = float(request.form.get('grade') or 7)
            yr_renovated = float(request.form.get('yr_renovated') or 0)
            waterfront = float(request.form.get('waterfront') or 0)
            view = float(request.form.get('view') or 0)
            
            # Calculate derived fields
            sqft_above = sqft_living * 0.85
            sqft_basement = sqft_living - sqft_above
            
            # Default location (Seattle area average)
           # Location handling
            location = request.form.get('location', 'delhi')

            # Define latitude and longitude for common Indian cities
            location_coords = {
                "delhi": (28.6139, 77.2090),
                "mumbai": (19.0760, 72.8777),
                "bangalore": (12.9716, 77.5946),
                "chennai": (13.0827, 80.2707),
                "kolkata": (22.5726, 88.3639),
                "pune": (18.5204, 73.8567),
                "hyderabad": (17.3850, 78.4867),
                "ahmedabad": (23.0225, 72.5714),
                "jaipur": (26.9124, 75.7873),
                "lucknow": (26.8467, 80.9462)
            }

# Get lat/long from map or use Delhi as default
            lat, long = location_coords.get(location, (28.6139, 77.2090))

            
            # Neighborhood averages
            living15 = sqft_living
            lot15 = sqft_lot
            
            # Create feature array
            features = [
                bedrooms, bathrooms, floors, sqft_living, sqft_lot,
                grade, yr_built, yr_renovated, waterfront, view,
                condition, sqft_above, lat, long,
                living15, lot15
            ]
            
            # Make prediction
            prediction = model.predict([features])[0]
            formatted_price = f"₹{prediction * 88:,.0f}"

            
            print(f"✅ Prediction made by {session.get('user_name')}: {formatted_price}")
            
            return render_template('home_simple.html', 
            prediction_text=f"Estimated House Price in {location.title()}: {formatted_price}",
            user_name=session.get('user_name'))

        except Exception as e:
            print(f"❌ Prediction error: {e}")
            import traceback
            traceback.print_exc()
            flash('Error: Please check your inputs', 'error')
    
    return render_template('home_simple.html', user_name=session.get('user_name'))

@app.route('/logout')
def logout():
    user_id = session.get('user_id', 'unknown')
    session.clear()
    print(f"🚪 User logged out: {user_id}")
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'users_count': len(load_users())
    })

if __name__ == "__main__":
    print("=" * 50)
    print("✅ Flask app with simple authentication ready!")
    print("=" * 50)
    app.run(debug=True)
