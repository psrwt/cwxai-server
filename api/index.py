# api/index.py
from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from utils.mongodb import client, logger
from routes.auth import auth_bp
# from routes.user_info_route import user_bp
# from routes.llm_calls import problem_bp
# from routes.chat import chat_bp
from routes.plans import plans_bp
# from routes.payments.create_order import create_order_bp
# from routes.payments.verify_payment import verify_payment_bp
# from routes.payments.failed_payment import failed_payment_bp
# from routes.payments.mark_cancel import mark_cancelled_bp
# from routes.payments.coupon_route import coupon_bp

from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Enable CORS globally for your frontend
CORS(
    app,
    origins=[
        "https://cwxai.vercel.app",
        "http://localhost:5173",
        "http://20.244.81.247:9000"
    ],
    methods=["GET", "POST", "OPTIONS", "DELETE", "PUT"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "X-Razorpay-Signature",
        "X-Frame-Options",
        "X-Content-Type-Options",
        "X-XSS-Protection",
    ],
    supports_credentials=True
)

@app.route('/')
def home():
    return jsonify({"message": "CWxAI backend is running!"})

# JWT configuration
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")

# Celery configuration
# app.config["CELERY_BROKER_URL"] = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
# app.config["CELERY_RESULT_BACKEND"] = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
# app.config["CELERY_TASK_SERIALIZER"] = "json"
# app.config["CELERY_RESULT_SERIALIZER"] = "json"
# app.config["CELERY_ACCEPT_CONTENT"] = ["json"]
# app.config["CELERY_TIMEZONE"] = "UTC"
# app.config["CELERY_ENABLE_UTC"] = True

# Initialize JWT
jwt = JWTManager(app)

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/auth')
# app.register_blueprint(problem_bp, url_prefix='/api')
# app.register_blueprint(chat_bp, url_prefix='/chat')
# app.register_blueprint(create_order_bp, url_prefix='/create')
# app.register_blueprint(verify_payment_bp, url_prefix='/verify')
# app.register_blueprint(failed_payment_bp, url_prefix='/payments')
# app.register_blueprint(mark_cancelled_bp, url_prefix='/cancel/payment')
# app.register_blueprint(coupon_bp, url_prefix='/coupon')
app.register_blueprint(plans_bp, url_prefix='/get')
# app.register_blueprint(user_bp, url_prefix='/info')

# No app.run() here—Vercel handles the server


