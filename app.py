import os
import requests
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer as Serializer

app = Flask(__name__)

# --- CONFIGURATION ---

# 1. SEARCH API
SERP_API_KEY = "d66eccb121b3453152187f2442537b0fe5b3c82c4b8d4d56b89ed4d52c9f01a6"

# 2. EMAIL CONFIGURATION (Required for Forgot Password)
# Note: For Gmail, you must enable 2FA and create an 'App Password'
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your_email@gmail.com'  # <--- PUT YOUR EMAIL HERE
app.config['MAIL_PASSWORD'] = 'your_app_password'     # <--- PUT YOUR APP PASSWORD HERE

# 3. DATABASE CONFIGURATION
NEON_DB_URL = "postgresql://neondb_owner:npg_d3OshXYJxvl6@ep-misty-hat-a1bla5w6.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require" 

database_url = os.environ.get('DATABASE_URL')
if not database_url and "neon" in NEON_DB_URL:
    database_url = NEON_DB_URL
elif not database_url:
    database_url = 'sqlite:///users.db'

if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_key_123')

db = SQLAlchemy(app)
mail = Mail(app)  # Initialize Mail
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- DATABASE MODELS ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    history = db.relationship('SearchHistory', backref='user', lazy=True)

    # Generate a secure token that expires in 1800 seconds (30 mins)
    def get_reset_token(self):
        s = Serializer(app.config['SECRET_KEY'])
        return s.dumps({'user_id': self.id})

    # Verify the token and return the user
    @staticmethod
    def verify_reset_token(token, expires_sec=1800):
        s = Serializer(app.config['SECRET_KEY'])
        try:
            user_id = s.loads(token, max_age=expires_sec)['user_id']
        except:
            return None
        return User.query.get(user_id)

class SearchHistory(db.Model):
    __tablename__ = 'search_history_v2' 
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    search_query = db.Column(db.String(200), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- HELPER FUNCTIONS ---
def send_reset_email(user):
    token = user.get_reset_token()
    msg = Message('Password Reset Request',
                  sender='noreply@futureshop.com',
                  recipients=[user.email])
    
    # We create the link dynamically
    link = url_for('reset_token', token=token, _external=True)
    
    msg.body = f'''To reset your password, visit the following link:
{link}

If you did not make this request then simply ignore this email and no changes will be made.
'''
    mail.send(msg)

def get_logo(store):
    if not store: return "default.png"
    s = store.lower()
    if "amazon" in s: return "amazon.png"
    if "flipkart" in s: return "flipkart.png"
    if "reliance" in s: return "reliance.png"
    return "default.png"

def extract_price(p):
    if not p: return 0
    try:
        clean_price = p.replace("₹", "").replace(",", "").strip()
        return int(float(clean_price.split()[0])) 
    except:
        return 0

# --- ROUTES ---

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == "POST":
        action = request.form.get('action')
        
        if action == 'register':
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            
            user_email = User.query.filter_by(email=email).first()
            user_name = User.query.filter_by(username=username).first()

            if user_email:
                flash('Email already exists.', 'error')
            elif user_name:
                flash('Username already exists.', 'error')
            else:
                hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
                new_user = User(username=username, email=email, password=hashed_pw)
                db.session.add(new_user)
                db.session.commit()
                flash('Account created! Please sign in.', 'success')
                return redirect(url_for('login'))
                
        elif action == 'login':
            username = request.form.get('username')
            password = request.form.get('password')
            user = User.query.filter_by(username=username).first()
            
            if user and check_password_hash(user.password, password):
                login_user(user)
                return redirect(url_for('index'))
            else:
                flash('Invalid credentials.', 'error')

    return render_template("login.html")

# --- NEW: PASSWORD RESET REQUEST ROUTE ---
@app.route("/reset_password", methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if user:
            send_reset_email(user)
        # We flash success regardless of whether the email exists for security
        flash('If an account with that email exists, an email has been sent with instructions to reset your password.', 'success')
        return redirect(url_for('login'))
    return render_template('reset_request.html')

# --- NEW: PASSWORD RESET TOKEN ROUTE ---
@app.route("/reset_password/<token>", methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    user = User.verify_reset_token(token)
    if not user:
        flash('That is an invalid or expired token', 'error')
        return redirect(url_for('reset_request'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
        user.password = hashed_pw
        db.session.commit()
        flash('Your password has been updated! You are now able to log in', 'success')
        return redirect(url_for('login'))
        
    return render_template('reset_token.html')

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route("/")
@login_required
def index():
    return render_template("index.html", user=current_user)

@app.route("/account")
@login_required
def account():
    user_history = SearchHistory.query.filter_by(user_id=current_user.id).order_by(SearchHistory.timestamp.desc()).all()
    return render_template("account.html", user=current_user, history=user_history)

@app.route("/update_profile", methods=["POST"])
@login_required
def update_profile():
    new_username = request.form.get("username")
    new_email = request.form.get("email")
    new_password = request.form.get("password")

    if new_username: current_user.username = new_username
    if new_email: current_user.email = new_email
    if new_password: 
        current_user.password = generate_password_hash(new_password, method='pbkdf2:sha256')

    try:
        db.session.commit()
        flash('Profile updated successfully!', 'success')
    except:
        flash('Error updating profile. Username taken.', 'error')
    
    return redirect(url_for('account'))

@app.route("/search", methods=["POST"])
@login_required
def search():
    product = request.form.get("product")
    sort_order = request.form.get("sort")

    if product:
        new_search = SearchHistory(user_id=current_user.id, search_query=product)
        db.session.add(new_search)
        db.session.commit()

    params = {
        "engine": "google_shopping",
        "q": product,
        "hl": "en",
        "gl": "in",
        "api_key": SERP_API_KEY
    }

    try:
        response = requests.get("https://serpapi.com/search", params=params)
        data = response.json()
    except Exception as e:
        print(f"Error: {e}")
        return render_template("index.html", error="Failed to fetch results", user=current_user)

    results = []
    shopping_results = data.get("shopping_results", [])

    for item in shopping_results:
        store = item.get("source", "Unknown")
        price = item.get("price", "N/A")
        link = item.get("link")
        if not link: link = item.get("product_link")
        if link and link.startswith("/"): link = f"https://www.google.co.in{link}"

        results.append({
            "title": item.get("title"),
            "store": store,
            "price": price,
            "price_value": extract_price(price),
            "link": link,
            "thumbnail": item.get("thumbnail"),
            "logo": get_logo(store)
        })

    results.sort(key=lambda x: x["price_value"], reverse=(sort_order == "high"))

    return render_template("results.html", product=product, results=results, sort_order=sort_order, user=current_user)

if __name__ == "__main__":
    app.run(debug=True)