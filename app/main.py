from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.middleware.audit_middleware import AuditMiddleware
from app.database.audit_database import init_audit_database
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Project Protector API", version="0.1")

# Initialize audit database (optional, non-blocking)
audit_enabled = False
try:
    # Only try to initialize if SQLAlchemy is available
    import sqlalchemy
    from app.database.audit_database import init_audit_database
    init_audit_database()
    audit_enabled = True
    logger.info("✅ Audit database initialized successfully")
except ImportError:
    logger.warning("⚠️ SQLAlchemy not available - audit system disabled")
except Exception as e:
    logger.warning(f"⚠️ Audit system initialization failed: {e} - continuing without audit")

# Add audit middleware only if audit system is working
if audit_enabled:
    try:
        app.add_middleware(AuditMiddleware)
        logger.info("✅ Audit middleware enabled")
    except Exception as e:
        logger.warning(f"⚠️ Failed to add audit middleware: {e}")
        audit_enabled = False

# Import routers with error handling
try:
    from app.routers import upload
    app.include_router(upload.router, prefix="/api")
    print("✅ Upload router loaded successfully")
except Exception as e:
    print(f"❌ Failed to load upload router: {e}")

try:
    from app.routers import download_router
    app.include_router(download_router.router, prefix="/api")
    print("✅ Download router loaded successfully")
except Exception as e:
    print(f"❌ Failed to load download router: {e}")
try: 
    from app.routers import process_router
    app.include_router(process_router.router, prefix="/api")
    print("✅ Process router loaded successfully")
except Exception as e:
    print(f"❌ Failed to load process router: {e}")

try:
    from app.routers import decrypt_router
    app.include_router(decrypt_router.router, prefix="/api")
    print("✅ Decrypt router loaded successfully")
except Exception as e:
    print(f"❌ Failed to load decrypt router: {e}")

# Load audit routers only if audit system is enabled
if audit_enabled:
    try:
        from app.routers import audit_router
        app.include_router(audit_router.router)
        print("✅ Audit router loaded successfully")
    except Exception as e:
        print(f"❌ Failed to load audit router: {e}")

    try:
        from app.routers import dashboard_router
        app.include_router(dashboard_router.router)
        print("✅ Dashboard router loaded successfully")
    except Exception as e:
        print(f"❌ Failed to load dashboard router: {e}")
else:
    print("⚠️ Audit routers disabled - audit system not available")

# Load Human Review router
try:
    from app.routers import human_review
    app.include_router(human_review.router)
    print("✅ Human Review router loaded successfully")
except Exception as e:
    print(f"❌ Failed to load Human Review router: {e}")

# Create static directories if they don't exist
os.makedirs("static", exist_ok=True)
os.makedirs("static/css", exist_ok=True)
os.makedirs("static/js", exist_ok=True)
os.makedirs("templates", exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Serve the main page
@app.get("/")
async def read_index():
    return FileResponse('templates/index.html')

# Serve the decrypt page
@app.get("/decrypt")
async def read_decrypt():
    return FileResponse('templates/decrypt.html')
