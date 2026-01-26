import os
import requests
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer as Serializer
from textblob import TextBlob
import random

app = Flask(__name__)

# --- CONFIGURATION ---
SERP_API_KEY = "d66eccb121b3453152187f2442537b0fe5b3c82c4b8d4d56b89ed4d52c9f01a6"

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'pupuhari123@gmail.com'
app.config['MAIL_PASSWORD'] = 'flfl rpac nsqz wprl'.replace(" ", "")

# Database Config
NEON_DB_URL = "postgresql://neondb_owner:npg_d3OshXYJxvl6@ep-misty-hat-a1bla5w6.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
database_url = os.environ.get('DATABASE_URL') or NEON_DB_URL
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'future_shop_secret_999'

db = SQLAlchemy(app)
mail = Mail(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- MODELS ---
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
        try: user_id = s.loads(token, max_age=expires_sec)['user_id']
        except: return None
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

with app.app_context(): db.create_all()

@login_manager.user_loader
def load_user(user_id): return User.query.get(int(user_id))

# --- HELPERS ---
def extract_price(p):
    if not p: return 0
    try: return int(float(p.replace("₹", "").replace(",", "").strip().split()[0])) 
    except: return 0

def get_ai_trust_score(product_title, store):
    if "amazon" in store.lower() or "flipkart" in store.lower():
        base_reviews = ["Great product", "Fast delivery", "Genuine item", "Loved it", "Good packaging"]
    else:
        base_reviews = ["Okay product", "Late delivery", "Average quality", "Decent for the price"]
    variations = ["Worth the money", "Not bad", "Could be better", "Amazing performance", "Terrible support"]
    
    product_reviews = random.sample(base_reviews + variations, 5)
    total_polarity = sum([TextBlob(review).sentiment.polarity for review in product_reviews])
    
    trust_score = int((total_polarity / len(product_reviews) + 1) * 50) 
    if "amazon" in store.lower() or "flipkart" in store.lower(): trust_score += 10
    return min(max(trust_score, 0), 100)

# --- ROUTES ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated: return redirect(url_for('index'))
    if request.method == "POST":
        action = request.form.get('action')
        if action == 'register':
            if User.query.filter_by(email=request.form.get('email')).first(): flash('Email exists.', 'error')
            else:
                db.session.add(User(username=request.form.get('username'), email=request.form.get('email'), password=generate_password_hash(request.form.get('password'), method='pbkdf2:sha256')))
                db.session.commit(); flash('Account created!', 'success')
        elif action == 'login':
            user = User.query.filter_by(username=request.form.get('username')).first()
            if user and check_password_hash(user.password, request.form.get('password')): login_user(user); return redirect(url_for('index'))
            else: flash('Invalid credentials.', 'error')
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout(): logout_user(); return redirect(url_for('login'))

@app.route("/")
@login_required
def index(): return render_template("index.html", user=current_user)

@app.route("/account")
@login_required
def account(): return render_template("account.html", user=current_user, history=SearchHistory.query.filter_by(user_id=current_user.id).order_by(SearchHistory.timestamp.desc()).all())

@app.route("/wishlist")
@login_required
def wishlist(): return render_template("wishlist.html", wishlist=Wishlist.query.filter_by(user_id=current_user.id).all(), user=current_user)

@app.route("/add_to_wishlist", methods=["POST"])
@login_required
def add_to_wishlist():
    if not Wishlist.query.filter_by(user_id=current_user.id, link=request.form.get("link")).first():
        db.session.add(Wishlist(user_id=current_user.id, title=request.form.get("title"), price=request.form.get("price"), link=request.form.get("link"), image=request.form.get("image"), store=request.form.get("store")))
        db.session.commit(); flash('Added to Wishlist!', 'success')
    return redirect(request.referrer)

@app.route("/remove_wishlist/<int:id>")
@login_required
def remove_wishlist(id):
    item = Wishlist.query.get_or_404(id)
    if item.user_id == current_user.id: db.session.delete(item); db.session.commit(); flash('Removed.', 'success')
    return redirect(url_for('wishlist'))

@app.route("/search", methods=["GET", "POST"])
@login_required
def search():
    product = request.args.get("q") or request.form.get("product")
    sort_order = request.args.get("sort")
    if not product: return redirect(url_for('index'))
    
    if request.method == "POST" or (request.args.get("q") and not request.args.get("sort")):
        last = SearchHistory.query.filter_by(user_id=current_user.id).order_by(SearchHistory.timestamp.desc()).first()
        if not last or last.search_query != product: db.session.add(SearchHistory(user_id=current_user.id, search_query=product)); db.session.commit()

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
        print(e); return render_template("index.html", error="Search failed")

# --- CHATBOT ROUTE ---
@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message", "").lower()
    
    # Simple Rule-Based Logic
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

# --- PASSWORD RESET ROUTES ---
@app.route("/reset_password", methods=['GET', 'POST'])
def reset_request():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email')).first()
        if user: send_reset_email(user); flash('Email sent.', 'success')
        else: flash('Email not found.', 'error')
        return redirect(url_for('login'))
    return render_template('reset_request.html')

@app.route("/reset_password/<token>", methods=['GET', 'POST'])
def reset_token(token):
    user = User.verify_reset_token(token)
    if not user: flash('Invalid token.', 'error'); return redirect(url_for('reset_request'))
    if request.method == 'POST':
        user.password = generate_password_hash(request.form.get('password'), method='pbkdf2:sha256')
        db.session.commit(); flash('Password updated.', 'success'); return redirect(url_for('login'))
    return render_template('reset_token.html')

def send_reset_email(user):
    token = user.get_reset_token()
    msg = Message('Reset Password', sender=app.config['MAIL_USERNAME'], recipients=[user.email])
    msg.body = f"Click to reset: {url_for('reset_token', token=token, _external=True)}"
    try: mail.send(msg)
    except: pass

if __name__ == "__main__":
    app.run(debug=True)