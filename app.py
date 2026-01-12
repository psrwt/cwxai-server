from flask import Flask
from flask_cors import CORS  # Import CORS
from flask_jwt_extended import JWTManager
from utils.mongodb import client, logger
from routes.auth import auth_bp
from routes.user_info_route import user_bp
from routes.llm_calls import problem_bp
# from routes.chill_route import chill_bp  # Import the chill routes
# from routes.google_search_route import search_bp
# from routes.generate_scraped_website_summaries import scrape_bp
# from routes.bulk_summarization_route import summarization_bp
# from routes.conversation import conversation_bp
from routes.chat import chat_bp
# from routes.user_form_data_routes import user_form_bp
# from routes.json_report_route import json_report_bp

# plans, payment and coupon routes
from routes.plans import plans_bp
from routes.payments.create_order import create_order_bp
from routes.payments.verify_payment import verify_payment_bp
from routes.payments.failed_payment import failed_payment_bp
from routes.payments.mark_cancel import mark_cancelled_bp
from routes.payments.coupon_route import coupon_bp 

# from routes.summarized_workflow_route import workflow_bp
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# print(os.getenv("RAZORPAY_KEY_ID"))

app = Flask(__name__)

# Enable CORS globally (for the whole app)
# CORS(app, origins=["http://localhost:5173", "http://20.244.81.247:9000", "https://cwxai.in"],
#      methods=["GET", "POST", "OPTIONS", "DELETE"],
#      allow_headers=["Content-Type", "Authorization"])

CORS(app, 
     origins=["http://localhost:5173", "http://20.244.81.247:9000", "https://cwxai.in", "https://www.cwxai.in", "https://validate.cwxai.in"], 
     methods=["GET", "POST", "OPTIONS", "DELETE", "PUT"], 
     allow_headers=[
         "Content-Type", 
         "Authorization", 
         "X-Requested-With",  # Needed for AJAX requests
         "X-Razorpay-Signature",  # Razorpay webhook verification
         "X-Frame-Options",  # Prevents clickjacking
         "X-Content-Type-Options",  # Prevents MIME type sniffing
         "X-XSS-Protection",  # XSS protection
     ],
     supports_credentials=True  # Allows sending cookies and auth headers
)

app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")  # JWT secret key
# app.config["CELERY_BROKER_URL"] = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
# app.config["CELERY_RESULT_BACKEND"] = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

# Celery configuration using the new style with a namespace.
app.config["CELERY_BROKER_URL"] = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
app.config["CELERY_RESULT_BACKEND"] = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
app.config["CELERY_TASK_SERIALIZER"] = "json"
app.config["CELERY_RESULT_SERIALIZER"] = "json"
app.config["CELERY_ACCEPT_CONTENT"] = ["json"]
app.config["CELERY_TIMEZONE"] = "UTC"
app.config["CELERY_ENABLE_UTC"] = True
# Do not include an unprefixed "include" key!

# Initialize JWT Manager
jwt = JWTManager(app)

# Register Blueprints
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(problem_bp, url_prefix='/api')
# Register the chill blueprint
# app.register_blueprint(chill_bp, url_prefix='/chill')
# app.register_blueprint(search_bp, url_prefix='/google-search')
# app.register_blueprint(scrape_bp, url_prefix='/scraping')
# app.register_blueprint(summarization_bp, url_prefix='/summarization')
# app.register_blueprint(conversation_bp, url_prefix='/convo')
app.register_blueprint(chat_bp, url_prefix='/chat')
# app.register_blueprint(workflow_bp, url_prefix='/run')
# app.register_blueprint(user_form_bp, url_prefix='/user-data')

# Register the payment blueprint
app.register_blueprint(create_order_bp, url_prefix='/create')
app.register_blueprint(verify_payment_bp, url_prefix='/verify')
app.register_blueprint(failed_payment_bp, url_prefix='/payments')
app.register_blueprint(mark_cancelled_bp, url_prefix='/cancel/payment')

app.register_blueprint(coupon_bp, url_prefix='/coupon')

app.register_blueprint(plans_bp, url_prefix='/get')
app.register_blueprint(user_bp, url_prefix='/info')

# app.register_blueprint(json_report_bp, url_prefix='/generate')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
