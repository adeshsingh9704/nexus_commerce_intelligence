import os
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "ecommerce_intelligence")
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "true").lower() == "true"
SECRET_KEY = os.getenv("SECRET_KEY", "local-development-only-change-me")
