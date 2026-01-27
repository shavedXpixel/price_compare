import os
import requests
import json
import random
import io
import cloudinary
import cloudinary.uploader
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from textblob import TextBlob
from sqlalchemy import func
from xhtml2pdf import pisa 

app = Flask(__name__)

# --- 1. CONFIGURATION ---

# SERP API KEY (For Google Shopping & Lens)
SERP_API_KEY = "d66eccb121b3453152187f2442537b0fe5b3c82c4b8d4d56b89ed4d52c9f01a6"

# CLOUDINARY CONFIG (For Visual Search Image Hosting)
# GET THESE FREE FROM: https://cloudinary.com/console
cloudinary.config(
  cloud_name = "YOUR_CLOUD_NAME", 
  api_key = "YOUR_API_KEY", 
  api_secret = "YOUR_API_SECRET" 
)

# Database Config (Neon + Local Fallback)
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
login_manager.login_message = None 

# --- 2. MULTI-LANGUAGE DICTIONARY ---
TRANSLATIONS = {
    'en': {
        'hello': "Hello", 'looking_for': "What are you looking for today?", 'placeholder': "Enter product name...",
        'search_btn': "Search", 'history_btn': "History", 'admin_btn': "Admin Panel", 'logout_btn': "Logout",
        'rec_title': "Recommended based on", 'voice_listen': "Listening...", 'ai_assistant': "AI Assistant",
        'ask_me': 'Ask me to "Search for phones" or "Go to wishlist".', 'footer': "Made with ❤️ by Priyansu"
    },
    'hi': {
        'hello': "नमस्ते", 'looking_for': "आज आप क्या खोज रहे हैं?", 'placeholder': "उत्पाद का नाम दर्ज करें...",
        'search_btn': "खोजें", 'history_btn': "इतिहास", 'admin_btn': "एडमिन पैनल", 'logout_btn': "लॉग आउट",
        'rec_title': "इसके आधार पर अनुशंसित", 'voice_listen': "सुन रहा हूँ...", 'ai_assistant': "एआई सहायक",
        'ask_me': 'मुझसे "फोन खोजें" या "विशलिस्ट पर जाएं" के लिए कहें।', 'footer': "प्रियंशु द्वारा ❤️ के साथ बनाया गया"
    },
    'od': {
        'hello': "ନମସ୍କାର", 'looking_for': "ଆଜି ଆପଣ କଣ ଖୋଜୁଛନ୍ତି?", 'placeholder': "ଉତ୍ପାଦର ନାମ ଦିଅନ୍ତୁ...",
        'search_btn': "ସନ୍ଧାନ କରନ୍ତୁ", 'history_btn': "ଇତିହାସ", 'admin_btn': "ପ୍ରଶାସକ ପ୍ୟାନେଲ୍", 'logout_btn': "ଲଗ୍ ଆଉଟ୍",
        'rec_title': "ଏହା ଉପରେ ଆଧାରିତ ସୁପାରିଶ", 'voice_listen': "ଶୁଣୁଛି...", 'ai_assistant': "AI ସହାୟକ",
        'ask_me': 'ମୋତେ "ଫୋନ୍ ଖୋଜନ୍ତୁ" କିମ୍ବା "ୱିଶଲିଷ୍ଟକୁ ଯାଆନ୍ତୁ" ବୋଲି କୁହନ୍ତୁ |', 'footer': "ପ୍ରିୟାଂଶୁଙ୍କ ଦ୍ୱାରା ❤️ ସହିତ ତିଆରି"
    }
}

# --- 3. DATABASE MODELS ---
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

class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(500), nullable=False)
    price = db.Column(db.String(100))
    price_val = db.Column(db.Float, default=0.0) 
    image = db.Column(db.String(500))
    store = db.Column(db.String(100))

# Create Tables
with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- 4. HELPER FUNCTIONS ---
def extract_price(p):
    if not p: return 0
    try:
        return float(p.replace("₹", "").replace("$", "").replace(",", "").strip().split()[0]) 
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

# --- 5. ROUTES ---

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated: return redirect(url_for('index'))
    if request.method == "POST":
        action = request.form.get('action')
        user_input = request.form.get('username')
        password = request.form.get('password')
        
        if action == 'register':
            email = request.form.get('email')
            if User.query.filter_by(email=email).first():
                flash('Email already exists.', 'error')
            else:
                hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
                new_user = User(username=user_input, email=email, password=hashed_pw)
                db.session.add(new_user)
                db.session.commit()
                flash('Account created! Please login.', 'success')
        
        elif action == 'login':
            user = User.query.filter((User.username == user_input) | (User.email == user_input)).first()
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
            flash('Email not found.', 'error')
            return redirect(url_for('reset_request'))
    return render_template('reset_request.html', step='email')

# --- MAIN ROUTE ---
@app.route("/")
@login_required
def index():
    lang = request.args.get('lang', 'en')
    t = TRANSLATIONS.get(lang, TRANSLATIONS['en']) 

    recommendations = []
    last_search = SearchHistory.query.filter_by(user_id=current_user.id).order_by(SearchHistory.timestamp.desc()).first()
    query = "futuristic gadgets"
    if last_search: query = last_search.search_query

    try:
        params = {"engine": "google_shopping", "q": query, "hl": "en", "gl": "in", "api_key": SERP_API_KEY, "num": 3}
        data = requests.get("https://serpapi.com/search", params=params).json()
        
        for item in data.get("shopping_results", [])[:3]:
            # Link Fix for Recommendations
            link = item.get("link") or item.get("product_link")
            if link and link.startswith("/"):
                link = f"https://www.google.com{link}"

            trust_score = get_ai_trust_score(item.get("title"), item.get("source", "Unknown"))
            recommendations.append({
                "title": item.get("title"), "price": item.get("price", "N/A"), "image": item.get("thumbnail"),
                "link": link, "score": trust_score
            })
    except Exception as e:
        print(f"Error: {e}")
    
    return render_template("index.html", user=current_user, recommendations=recommendations, rec_topic=query, t=t, lang=lang)

# --- VISUAL SEARCH (CLOUDINARY) ---
@app.route("/visual_search", methods=["POST"])
@login_required
def visual_search():
    if 'image' not in request.files:
        flash('No image uploaded', 'error')
        return redirect(url_for('index'))
    
    file = request.files['image']
    if file.filename == '':
        flash('No image selected', 'error')
        return redirect(url_for('index'))

    if file:
        try:
            # 1. Upload directly to Cloudinary
            flash("Uploading image to AI cloud...", "info")
            upload_result = cloudinary.uploader.upload(file)
            img_url = upload_result["secure_url"]
            
            # 2. Send Public URL to Google Lens (SerpApi)
            params = {
                "engine": "google_lens",
                "url": img_url,
                "api_key": SERP_API_KEY
            }
            data = requests.get("https://serpapi.com/search", params=params).json()
            
            # 3. Extract Best Match
            if "visual_matches" in data and len(data["visual_matches"]) > 0:
                best_match = data["visual_matches"][0].get("title")
                flash(f"AI identified: {best_match}", "success")
                return redirect(url_for('search', q=best_match))
            else:
                flash("AI couldn't identify the image. Try a clearer photo.", "error")

        except Exception as e:
            print(f"Visual Search Error: {e}")
            flash("Visual search failed. Check console for details.", "error")
            
    return redirect(url_for('index'))

# --- USER ROUTES ---
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
            user_id=current_user.id, title=request.form.get("title"), price=request.form.get("price"), 
            link=link, image=request.form.get("image"), store=request.form.get("store")
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

@app.route("/cart")
@login_required
def cart():
    cart_items = Cart.query.filter_by(user_id=current_user.id).all()
    total_price = sum(item.price_val for item in cart_items)
    return render_template("cart.html", cart=cart_items, total=total_price, user=current_user)

@app.route("/add_to_cart", methods=["POST"])
@login_required
def add_to_cart():
    price_str = request.form.get("price")
    price_val = extract_price(price_str)
    new_item = Cart(
        user_id=current_user.id, title=request.form.get("title"),
        price=price_str, price_val=price_val,
        image=request.form.get("image"), store=request.form.get("store")
    )
    db.session.add(new_item)
    db.session.commit()
    flash('Added to Cart!', 'success')
    return redirect(request.referrer)

@app.route("/remove_cart/<int:id>")
@login_required
def remove_cart(id):
    item = Cart.query.get_or_404(id)
    if item.user_id == current_user.id:
        db.session.delete(item)
        db.session.commit()
        flash('Removed from Cart.', 'success')
    return redirect(url_for('cart'))

# --- NEW CHECKOUT FLOW (Payment -> Invoice) ---

@app.route("/checkout")
@login_required
def checkout_page():
    cart_items = Cart.query.filter_by(user_id=current_user.id).all()
    if not cart_items:
        flash("Your cart is empty!", "error")
        return redirect(url_for('cart'))
    total_price = sum(item.price_val for item in cart_items)
    return render_template("payment.html", total=total_price)

@app.route("/generate_invoice")
@login_required
def generate_invoice():
    # 1. Get Items
    cart_items = Cart.query.filter_by(user_id=current_user.id).all()
    if not cart_items:
        return redirect(url_for('cart'))
        
    total_price = sum(item.price_val for item in cart_items)
    date_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 2. Render HTML for PDF
    rendered_html = render_template("invoice_pdf.html", user=current_user, items=cart_items, total=total_price, date=date_now)
    
    # 3. Clear Cart
    for item in cart_items: db.session.delete(item)
    db.session.commit()
    
    # 4. Generate PDF
    pdf_buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.BytesIO(rendered_html.encode("utf-8")), dest=pdf_buffer)
    
    if pisa_status.err: return "Error creating PDF", 500
    pdf_buffer.seek(0)
    
    return send_file(pdf_buffer, as_attachment=True, download_name=f"Invoice_{current_user.username}.pdf", mimetype='application/pdf')

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
                "title": item.get("title"), "store": item.get("source", "Unknown"), 
                "price": item.get("price", "N/A"), "price_value": extract_price(item.get("price", "0")), 
                "link": link, "thumbnail": item.get("thumbnail"), "trust_score": trust_score 
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
    p1 = json.loads(request.form.get("product1"))
    p2 = json.loads(request.form.get("product2"))
    winner = None
    try:
        price1 = float(p1.get('price_value', 0))
        price2 = float(p2.get('price_value', 0))
        if price1 > 0 and price2 > 0:
            if price1 < price2: winner = 'p1'
            elif price2 < price1: winner = 'p2'
    except: pass
    return render_template("compare.html", p1=p1, p2=p2, winner=winner)

@app.route("/admin")
@login_required
def admin():
    if current_user.email != 'pupuhari123@gmail.com':
        flash("Access Denied: Admins only.", "error")
        return redirect(url_for('index'))
    total_users = User.query.count()
    total_searches = SearchHistory.query.count()
    total_wishlist = Wishlist.query.count()
    top_searches = db.session.query(SearchHistory.search_query, func.count(SearchHistory.search_query).label('count')).group_by(SearchHistory.search_query).order_by(func.count(SearchHistory.search_query).desc()).limit(5).all()
    labels = [s[0] for s in top_searches]
    values = [s[1] for s in top_searches]
    return render_template("admin.html", total_users=total_users, total_searches=total_searches, total_wishlist=total_wishlist, labels=labels, values=values, user=current_user)

@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message", "").lower()
    if "hello" in user_message or "hi" in user_message: response = "Hello! I am your Future Shop Assistant."
    elif "help" in user_message: response = "Try saying 'Search for iPhone' or 'Go to wishlist'."
    elif "search for" in user_message:
        query = user_message.replace("search for", "").strip()
        return jsonify({"response": f"Searching for {query}...", "redirect": url_for('search', q=query)})
    elif "wishlist" in user_message: return jsonify({"response": "Opening wishlist...", "redirect": url_for('wishlist')})
    elif "cart" in user_message: return jsonify({"response": "Opening shopping cart...", "redirect": url_for('cart')})
    elif "history" in user_message: return jsonify({"response": "Opening history...", "redirect": url_for('account')})
    else: response = "I didn't quite catch that."
    return jsonify({"response": response})

if __name__ == "__main__":
    app.run(debug=True)