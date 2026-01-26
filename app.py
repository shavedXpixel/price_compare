import os
import requests
import json
import random
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from textblob import TextBlob
from sqlalchemy import func 

app = Flask(__name__)

# --- 1. CONFIGURATION ---
SERP_API_KEY = "d66eccb121b3453152187f2442537b0fe5b3c82c4b8d4d56b89ed4d52c9f01a6"

# Email Config (REVERTED TO PUPUHARI123)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'pupuhari123@gmail.com'  # <--- BACK TO ORIGINAL
app.config['MAIL_PASSWORD'] = 'flfl rpac nsqz wprl' # <--- UPDATE THIS CODE!

# Database Config
NEON_DB_URL = "postgresql://neondb_owner:npg_d3OshXYJxvl6@ep-misty-hat-a1bla5w6.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"

database_url = os.environ.get('DATABASE_URL')
if not database_url:
    database_url = NEON_DB_URL 

if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'future_shop_secret_key_999')

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- 2. DATABASE MODELS ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)

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
def extract_price(p):
    if not p: return 0
    try:
        return int(float(p.replace("₹", "").replace(",", "").strip().split()[0])) 
    except:
        return 0

def get_ai_trust_score(product_title, store):
    if "amazon" in store.lower() or "flipkart" in store.lower():
        base_reviews = ["Great product", "Fast delivery", "Genuine item", "Loved it", "Good packaging"]
    else:
        base_reviews = ["Okay product", "Late delivery", "Average quality", "Decent for the price"]

    variations = ["Worth the money", "Not bad", "Could be better", "Amazing performance", "Terrible support"]
    product_reviews = random.sample(base_reviews + variations, 5)
    
    total_polarity = 0
    for review in product_reviews:
        analysis = TextBlob(review)
        total_polarity += analysis.sentiment.polarity

    avg_polarity = total_polarity / len(product_reviews)
    trust_score = int((avg_polarity + 1) * 50) 
    if "amazon" in store.lower() or "flipkart" in store.lower():
        trust_score += 10
    return min(max(trust_score, 0), 100)

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
            user = User.query.filter((User.username == username) | (User.email == username)).first()
            if user and check_password_hash(user.password, password):
                login_user(user)
                return redirect(url_for('index'))
            else:
                flash('Invalid credentials.', 'error')
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- DIRECT PASSWORD RESET (NO EMAIL REQUIRED) ---
@app.route("/reset_password", methods=['GET', 'POST'])
def reset_request():
    if request.method == 'POST':
        email = request.form.get('email')
        new_password = request.form.get('password')
        
        if new_password:
            user = User.query.filter_by(email=email).first()
            if user:
                hashed_pw = generate_password_hash(new_password, method='pbkdf2:sha256')
                user.password = hashed_pw
                db.session.commit()
                flash('Success! Password has been changed.', 'success')
                return redirect(url_for('login'))
        
        user = User.query.filter_by(email=email).first()
        if user:
            flash(f'Account found for {email}. Set new password below.', 'success')
            return render_template('reset_request.html', step='password', email=email)
        else:
            flash('Email not found in our database.', 'error')
            return redirect(url_for('reset_request'))

    return render_template('reset_request.html', step='email')

# --- MAIN APP ROUTES ---
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
    exists = Wishlist.query.filter_by(user_id=current_user.id, link=link).first()
    if exists:
        flash('Item is already in your wishlist!', 'info')
    else:
        new_item = Wishlist(
            user_id=current_user.id, title=request.form.get("title"), 
            price=request.form.get("price"), link=link, 
            image=request.form.get("image"), store=request.form.get("store")
        )
        db.session.add(new_item)
        db.session.commit()
        flash('Added to Wishlist!', 'success')
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

@app.route("/search", methods=["GET", "POST"])
@login_required
def search():
    product = request.args.get("q") or request.form.get("product")
    sort_order = request.args.get("sort")
    if not product: return redirect(url_for('index'))

    if request.method == "POST" or (request.args.get("q") and not request.args.get("sort")):
        last = SearchHistory.query.filter_by(user_id=current_user.id).order_by(SearchHistory.timestamp.desc()).first()
        if not last or last.search_query != product:
            db.session.add(SearchHistory(user_id=current_user.id, search_query=product))
            db.session.commit()

    try:
        params = {"engine": "google_shopping", "q": product, "hl": "en", "gl": "in", "api_key": SERP_API_KEY}
        data = requests.get("https://serpapi.com/search", params=params).json()
        results = []
        for item in data.get("shopping_results", []):
            link = item.get("link") or item.get("product_link")
            if link and link.startswith("/"): link = f"https://www.google.co.in{link}"
            trust_score = get_ai_trust_score(item.get("title"), item.get("source", "Unknown"))
            results.append({
                "title": item.get("title"), "store": item.get("source", "Unknown"), "price": item.get("price", "N/A"),
                "price_value": extract_price(item.get("price", "0")), "link": link, "thumbnail": item.get("thumbnail"),
                "trust_score": trust_score 
            })
        if sort_order == 'low': results.sort(key=lambda x: x["price_value"])
        elif sort_order == 'high': results.sort(key=lambda x: x["price_value"], reverse=True)
        return render_template("results.html", product=product, results=results, sort_order=sort_order)
    except Exception as e:
        print(f"Search Error: {e}")
        return render_template("index.html", error="Search failed")

@app.route("/compare", methods=["POST"])
@login_required
def compare():
    p1_json = request.form.get("product1")
    p2_json = request.form.get("product2")
    p1 = json.loads(p1_json)
    p2 = json.loads(p2_json)
    winner = None
    try:
        price1 = float(p1.get('price_value', 0))
        price2 = float(p2.get('price_value', 0))
        if price1 > 0 and price2 > 0:
            if price1 < price2: winner = 'p1'
            elif price2 < price1: winner = 'p2'
    except: pass
    return render_template("compare.html", p1=p1, p2=p2, winner=winner)

# --- ADMIN DASHBOARD ---
@app.route("/admin")
@login_required
def admin():
    # SECURITY REVERTED: Only pupuhari123 can access
    if current_user.email != 'pupuhari123@gmail.com':
        flash("Access Denied: Admins only.", "error")
        return redirect(url_for('index'))

    total_users = User.query.count()
    total_searches = SearchHistory.query.count()
    total_wishlist = Wishlist.query.count()
    
    top_searches = db.session.query(
        SearchHistory.search_query, 
        func.count(SearchHistory.search_query).label('count')
    ).group_by(SearchHistory.search_query).order_by(func.count(SearchHistory.search_query).desc()).limit(5).all()

    labels = [s[0] for s in top_searches]
    values = [s[1] for s in top_searches]

    return render_template("admin.html", total_users=total_users, total_searches=total_searches, total_wishlist=total_wishlist, labels=labels, values=values, user=current_user)

@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message", "").lower()
    if "hello" in user_message or "hi" in user_message:
        response = "Hello! I am your Future Shop Assistant. Ask me to search for something!"
    elif "help" in user_message:
        response = "I can help you search. Try saying 'Search for iPhone' or 'Go to wishlist'."
    elif "search for" in user_message:
        query = user_message.replace("search for", "").strip()
        return jsonify({"response": f"Searching for {query}...", "redirect": url_for('search', q=query)})
    elif "wishlist" in user_message:
         return jsonify({"response": "Taking you to your wishlist...", "redirect": url_for('wishlist')})
    elif "history" in user_message:
         return jsonify({"response": "Opening your search history...", "redirect": url_for('account')})
    else:
        response = "I didn't quite catch that. Try saying 'Search for laptops'."
    return jsonify({"response": response})

if __name__ == "__main__":
    app.run(debug=True)