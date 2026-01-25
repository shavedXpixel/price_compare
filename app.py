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

# --- 1. CONFIGURATION ---
SERP_API_KEY = "d66eccb121b3453152187f2442537b0fe5b3c82c4b8d4d56b89ed4d52c9f01a6"

# Email Config
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'pupuhari123@gmail.com'
app.config['MAIL_PASSWORD'] = 'flfl rpac nsqz wprl'.replace(" ", "")

# Database Config (Neon + Local Fallback)
NEON_DB_URL = "postgresql://neondb_owner:npg_d3OshXYJxvl6@ep-misty-hat-a1bla5w6.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"

database_url = os.environ.get('DATABASE_URL')
if not database_url:
    database_url = NEON_DB_URL # Use Neon by default even locally

if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'future_shop_secret_key_999')

db = SQLAlchemy(app)
mail = Mail(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- 2. DATABASE MODELS ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    
    def get_reset_token(self):
        s = Serializer(app.config['SECRET_KEY'])
        return s.dumps({'user_id': self.id})

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

class Wishlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(500), nullable=False)
    price = db.Column(db.String(100))
    link = db.Column(db.String(500))
    image = db.Column(db.String(500))
    store = db.Column(db.String(100))

# Create Tables
with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- 3. HELPER FUNCTIONS ---
def send_reset_email(user):
    token = user.get_reset_token()
    link = url_for('reset_token', token=token, _external=True)
    msg = Message('Password Reset Request', sender=app.config['MAIL_USERNAME'], recipients=[user.email])
    msg.body = f'To reset your password, visit: {link}'
    try:
        mail.send(msg)
    except Exception as e:
        print(f"Email Error: {e}") # Don't crash app if email fails

def extract_price(p):
    if not p: return 0
    try:
        return int(float(p.replace("₹", "").replace(",", "").strip().split()[0])) 
    except:
        return 0

# --- 4. ROUTES ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated: return redirect(url_for('index'))
    if request.method == "POST":
        action = request.form.get('action')
        username = request.form.get('username')
        password = request.form.get('password')
        
        if action == 'register':
            email = request.form.get('email')
            if User.query.filter_by(email=email).first():
                flash('Email already exists.', 'error')
            else:
                hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
                new_user = User(username=username, email=email, password=hashed_pw)
                db.session.add(new_user)
                db.session.commit()
                flash('Account created! Please login.', 'success')
        
        elif action == 'login':
            user = User.query.filter_by(username=username).first()
            if user and check_password_hash(user.password, password):
                login_user(user)
                return redirect(url_for('index'))
            else:
                flash('Invalid credentials.', 'error')
    return render_template("login.html")

@app.route("/reset_password", methods=['GET', 'POST'])
def reset_request():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email')).first()
        if user:
            send_reset_email(user)
            flash('Email sent with instructions.', 'success')
        else:
            flash('Email not found.', 'error')
        return redirect(url_for('login'))
    return render_template('reset_request.html')

@app.route("/reset_password/<token>", methods=['GET', 'POST'])
def reset_token(token):
    user = User.verify_reset_token(token)
    if not user:
        flash('Invalid or expired token.', 'error')
        return redirect(url_for('reset_request'))
    if request.method == 'POST':
        hashed_pw = generate_password_hash(request.form.get('password'), method='pbkdf2:sha256')
        user.password = hashed_pw
        db.session.commit()
        flash('Password updated! Please login.', 'success')
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
    history = SearchHistory.query.filter_by(user_id=current_user.id).order_by(SearchHistory.timestamp.desc()).all()
    return render_template("account.html", user=current_user, history=history)

@app.route("/update_profile", methods=["POST"])
@login_required
def update_profile():
    current_user.username = request.form.get("username")
    current_user.email = request.form.get("email")
    if request.form.get("password"):
        current_user.password = generate_password_hash(request.form.get("password"), method='pbkdf2:sha256')
    db.session.commit()
    flash('Profile updated!', 'success')
    return redirect(url_for('account'))

@app.route("/wishlist")
@login_required
def wishlist():
    user_wishlist = Wishlist.query.filter_by(user_id=current_user.id).all()
    return render_template("wishlist.html", wishlist=user_wishlist, user=current_user)

@app.route("/add_to_wishlist", methods=["POST"])
@login_required
def add_to_wishlist():
    link = request.form.get("link")
    if not Wishlist.query.filter_by(user_id=current_user.id, link=link).first():
        new_item = Wishlist(
            user_id=current_user.id, 
            title=request.form.get("title"), 
            price=request.form.get("price"), 
            link=link, 
            image=request.form.get("image"), 
            store=request.form.get("store")
        )
        db.session.add(new_item)
        db.session.commit()
        flash('Added to Wishlist!', 'success')
    else:
        flash('Already in Wishlist.', 'info')
    return redirect(request.referrer)

@app.route("/remove_wishlist/<int:id>")
@login_required
def remove_wishlist(id):
    item = Wishlist.query.get_or_404(id)
    if item.user_id == current_user.id:
        db.session.delete(item)
        db.session.commit()
        flash('Removed from Wishlist.', 'success')
    return redirect(url_for('wishlist'))

@app.route("/search", methods=["POST"])
@login_required
def search():
    product = request.form.get("product")
    sort_order = request.form.get("sort")
    
    if product:
        db.session.add(SearchHistory(user_id=current_user.id, search_query=product))
        db.session.commit()

    try:
        params = {"engine": "google_shopping", "q": product, "hl": "en", "gl": "in", "api_key": SERP_API_KEY}
        data = requests.get("https://serpapi.com/search", params=params).json()
        results = []
        for item in data.get("shopping_results", []):
            link = item.get("link") or item.get("product_link")
            if link and link.startswith("/"): link = f"https://www.google.co.in{link}"
            
            results.append({
                "title": item.get("title"),
                "store": item.get("source", "Unknown"),
                "price": item.get("price", "N/A"),
                "price_value": extract_price(item.get("price", "0")),
                "link": link,
                "thumbnail": item.get("thumbnail")
            })
        
        if sort_order:
            results.sort(key=lambda x: x["price_value"], reverse=(sort_order == "high"))
            
        return render_template("results.html", product=product, results=results, sort_order=sort_order)
    except Exception as e:
        print(e)
        return render_template("index.html", error="Search failed")

if __name__ == "__main__":
    app.run(debug=True)