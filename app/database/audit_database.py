# app/database/audit_database.py
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import os
from app.models.audit_models import Base
from datetime import datetime, timedelta
import logging

# Database configuration
DATABASE_URL = os.getenv("AUDIT_DATABASE_URL", "sqlite:///./audit_logs.db")

# Create engine with connection pooling
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False  # Set to True for SQL debugging
    )
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_audit_tables():
    """Create all audit tables"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Audit database tables created successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to create audit tables: {e}")
        return False

def get_audit_db() -> Session:
    """Get database session for audit operations"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_audit_db_sync() -> Session:
    """Get synchronous database session for audit operations"""
    return SessionLocal()

class AuditDatabaseManager:
    """Manage audit database operations and maintenance"""
    
    def __init__(self):
        self.engine = engine
        self.SessionLocal = SessionLocal
    
    def initialize_database(self):
        """Initialize the audit database"""
        try:
            # Create tables
            create_audit_tables()
            
            # Run initial setup
            self._setup_database_triggers()
            
            logger.info("🚀 Audit database initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize audit database: {e}")
            return False
    
    def _setup_database_triggers(self):
        """Set up database triggers and constraints"""
        try:
            # Add any database-specific triggers or constraints here
            # For SQLite, we can add some basic constraints
            
            with self.engine.connect() as conn:
                # Add indexes for better query performance
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_file_operations_timestamp
                    ON file_operation_logs(timestamp)
                """))

                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_pii_processing_timestamp
                    ON pii_processing_logs(timestamp)
                """))

                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_user_actions_timestamp
                    ON user_action_logs(timestamp)
                """))

                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_system_events_timestamp
                    ON system_event_logs(timestamp)
                """))

                conn.commit()
                
            logger.info("✅ Database triggers and indexes created")
            
        except Exception as e:
            logger.warning(f"⚠️ Could not create database triggers: {e}")
    
    def cleanup_old_logs(self, retention_days: int = 90):
        """Clean up old audit logs based on retention policy"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            
            with self.SessionLocal() as db:
                from app.models.audit_models import (
                    FileOperationLog, PIIProcessingLog, UserActionLog, 
                    SystemEventLog, PIIDetectionLog
                )
                
                # Count records to be deleted
                counts = {
                    "file_operations": db.query(FileOperationLog).filter(
                        FileOperationLog.timestamp < cutoff_date
                    ).count(),
                    "pii_processing": db.query(PIIProcessingLog).filter(
                        PIIProcessingLog.timestamp < cutoff_date
                    ).count(),
                    "user_actions": db.query(UserActionLog).filter(
                        UserActionLog.timestamp < cutoff_date
                    ).count(),
                    "system_events": db.query(SystemEventLog).filter(
                        SystemEventLog.timestamp < cutoff_date
                    ).count(),
                    "pii_detections": db.query(PIIDetectionLog).filter(
                        PIIDetectionLog.timestamp < cutoff_date
                    ).count()
                }
                
                # Delete old records
                db.query(PIIDetectionLog).filter(
                    PIIDetectionLog.timestamp < cutoff_date
                ).delete()
                
                db.query(PIIProcessingLog).filter(
                    PIIProcessingLog.timestamp < cutoff_date
                ).delete()
                
                db.query(UserActionLog).filter(
                    UserActionLog.timestamp < cutoff_date
                ).delete()
                
                db.query(SystemEventLog).filter(
                    SystemEventLog.timestamp < cutoff_date
                ).delete()
                
                db.query(FileOperationLog).filter(
                    FileOperationLog.timestamp < cutoff_date
                ).delete()
                
                db.commit()
                
                total_deleted = sum(counts.values())
                logger.info(f"🧹 Cleaned up {total_deleted} old audit records")
                logger.info(f"   Details: {counts}")
                
                return counts
                
        except Exception as e:
            logger.error(f"❌ Failed to cleanup old logs: {e}")
            return None
    
    def get_database_stats(self):
        """Get database statistics"""
        try:
            with self.SessionLocal() as db:
                from app.models.audit_models import (
                    AuditSession, FileOperationLog, PIIProcessingLog, 
                    UserActionLog, SystemEventLog, PIIDetectionLog
                )
                
                stats = {
                    "sessions": db.query(AuditSession).count(),
                    "file_operations": db.query(FileOperationLog).count(),
                    "pii_processing": db.query(PIIProcessingLog).count(),
                    "user_actions": db.query(UserActionLog).count(),
                    "system_events": db.query(SystemEventLog).count(),
                    "pii_detections": db.query(PIIDetectionLog).count(),
                    "database_size_mb": self._get_database_size()
                }
                
                return stats
                
        except Exception as e:
            logger.error(f"❌ Failed to get database stats: {e}")
            return None
    
    def _get_database_size(self):
        """Get database file size in MB"""
        try:
            if DATABASE_URL.startswith("sqlite"):
                db_file = DATABASE_URL.replace("sqlite:///", "").replace("./", "")
                if os.path.exists(db_file):
                    size_bytes = os.path.getsize(db_file)
                    return round(size_bytes / (1024 * 1024), 2)
            return 0
        except:
            return 0
    
    def backup_database(self, backup_path: str = None):
        """Create a backup of the audit database"""
        try:
            if not backup_path:
                timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                backup_path = f"audit_backup_{timestamp}.db"
            
            if DATABASE_URL.startswith("sqlite"):
                import shutil
                db_file = DATABASE_URL.replace("sqlite:///", "").replace("./", "")
                if os.path.exists(db_file):
                    shutil.copy2(db_file, backup_path)
                    logger.info(f"✅ Database backed up to {backup_path}")
                    return backup_path
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Failed to backup database: {e}")
            return None

# Global database manager instance
audit_db_manager = AuditDatabaseManager()

# Initialize database on module import
def init_audit_database():
    """Initialize audit database on startup"""
    return audit_db_manager.initialize_database()

# Event listener to ensure database is initialized
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Set SQLite pragmas for better performance"""
    if DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=10000")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.close()
