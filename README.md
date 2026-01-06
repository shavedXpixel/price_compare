📦 AI Price Comparison Website

A modern price comparison web application built using Flask that helps users find the best prices across Indian shopping platforms with a clean UI, particle background, and secure API handling.

🔗 Live Demo: https://priyansu.me

✨ Features

🔍 Text-based product search
🇮🇳 India-focused shopping results
💰 Price comparison across multiple stores
🏷️ Highlights best available deals
🔗 Direct external store links (Amazon, Flipkart, etc.)
🌌 Animated particle background
🧊 Glassmorphism UI design
🚫 No image upload / file input
🔐 Secure API key handling via environment variables

🛠️ Tech Stack

Frontend: HTML, CSS, JavaScript
Backend: Python (Flask)
API: SerpAPI (Google Shopping)
Hosting: Render
Version Control: Git & GitHub

📁 Project Structure

price_compare/
│
├── app.py
├── requirements.txt
│
├── templates/
│   ├── index.html
│   └── results.html
│
└── static/
    └── logos/
        ├── amazon.png
        ├── flipkart.png
        ├── reliance.png
        └── default.png

🚀 How It Works

User enters a product name
Flask sends request to SerpAPI (Google Shopping)
Prices are fetched and processed
Results are sorted and displayed
Clicking View Offer opens the store website in a new tab

🔐 Environment Variables

This project uses environment variables to keep API keys secure.

🌍 Deployment

Code is hosted on GitHub
Automatically deployed via Render
Custom domain configured: priyansu.me

⚠️ Notes

Some products may not have direct store links; these are safely handled
Prices depend on SerpAPI availability and response format
API key is never hardcoded in production

📌 Future Enhancements

📊 Price history charts
❤️ Wishlist / saved products
🧠 AI-based product comparison summaries
📱 Mobile UI optimizations

👨‍💻 Author

Priyansu Dash
🌐 https://priyansu.me

⭐ Support

If you like this project, give it a ⭐ on GitHub!
