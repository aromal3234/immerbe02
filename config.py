import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'fallback-secret-key')
    MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/certdb')
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'Admin@1234')
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@certverify.com')
    BASE_URL = os.getenv('BASE_URL', 'http://localhost:5000')
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
    QRCODE_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'qrcodes')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
