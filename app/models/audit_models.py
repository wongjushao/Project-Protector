# app/models/audit_models.py
from sqlalchemy import Column, Integer, String, DateTime, Float, Text, Boolean, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()

class AuditSession(Base):
    """Track user sessions and basic information"""
    __tablename__ = "audit_sessions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, unique=True, nullable=False)
    ip_address = Column(String, nullable=False)
    user_agent = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    file_operations = relationship("FileOperationLog", back_populates="session")
    pii_operations = relationship("PIIProcessingLog", back_populates="session")
    user_actions = relationship("UserActionLog", back_populates="session")
    system_events = relationship("SystemEventLog", back_populates="session")

class FileOperationLog(Base):
    """Log all file upload and processing operations"""
    __tablename__ = "file_operation_logs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("audit_sessions.session_id"), nullable=False)
    task_id = Column(String, nullable=False)
    operation_type = Column(String, nullable=False)  # upload, process, download
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # File details
    file_name = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    file_hash = Column(String)  # SHA256 hash for integrity
    
    # PII configuration
    enabled_pii_categories = Column(JSON)
    total_pii_categories = Column(Integer)
    
    # Processing details
    processing_time_seconds = Column(Float)
    status = Column(String, nullable=False)  # success, error, in_progress
    error_message = Column(Text)
    
    # Security and compliance
    ip_address = Column(String, nullable=False)
    user_agent = Column(Text)
    
    # Relationships
    session = relationship("AuditSession", back_populates="file_operations")
    pii_detections = relationship("PIIDetectionLog", back_populates="file_operation")

class PIIProcessingLog(Base):
    """Log detailed PII detection and masking operations"""
    __tablename__ = "pii_processing_logs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("audit_sessions.session_id"), nullable=False)
    file_operation_id = Column(String, ForeignKey("file_operation_logs.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Processing summary
    total_pii_found = Column(Integer, default=0)
    total_pii_masked = Column(Integer, default=0)
    processing_time_seconds = Column(Float)
    
    # Category breakdown
    selectable_pii_found = Column(JSON)  # {"NAMES": 5, "RACES": 2, ...}
    non_selectable_pii_found = Column(JSON)  # {"IC": 3, "EMAIL": 2, ...}
    masked_categories = Column(JSON)  # Categories that were actually masked
    
    # Confidence and quality metrics
    average_confidence = Column(Float)
    low_confidence_count = Column(Integer, default=0)
    
    # Relationships
    session = relationship("AuditSession", back_populates="pii_operations")
    file_operation = relationship("FileOperationLog")

class PIIDetectionLog(Base):
    """Log individual PII detections (anonymized)"""
    __tablename__ = "pii_detection_logs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    file_operation_id = Column(String, ForeignKey("file_operation_logs.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # PII details (anonymized)
    pii_type = Column(String, nullable=False)  # NAMES, IC, EMAIL, etc.
    pii_category = Column(String, nullable=False)  # selectable, non_selectable
    pii_value_hash = Column(String, nullable=False)  # SHA256 hash of actual value
    pii_length = Column(Integer)  # Length of original value
    confidence_score = Column(Float)
    
    # Processing details
    was_masked = Column(Boolean, nullable=False)
    detection_method = Column(String)  # regex, dictionary, ml_model
    position_in_text = Column(Integer)  # Character position
    
    # Relationships
    file_operation = relationship("FileOperationLog", back_populates="pii_detections")

class UserActionLog(Base):
    """Log all user interactions and actions"""
    __tablename__ = "user_action_logs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("audit_sessions.session_id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Action details
    action_type = Column(String, nullable=False)  # page_visit, button_click, config_change
    action_name = Column(String, nullable=False)  # upload_page, submit_files, select_pii
    action_details = Column(JSON)  # Additional context data
    
    # Page/endpoint information
    page_url = Column(String)
    http_method = Column(String)
    endpoint = Column(String)
    
    # Request details
    request_data = Column(JSON)  # Sanitized request data
    response_status = Column(Integer)
    response_time_ms = Column(Float)
    
    # Security context
    ip_address = Column(String, nullable=False)
    user_agent = Column(Text)
    
    # Relationships
    session = relationship("AuditSession", back_populates="user_actions")

class SystemEventLog(Base):
    """Log system events, errors, and status changes"""
    __tablename__ = "system_event_logs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("audit_sessions.session_id"), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Event details
    event_type = Column(String, nullable=False)  # error, warning, info, security
    event_category = Column(String, nullable=False)  # system, security, performance
    event_name = Column(String, nullable=False)
    event_message = Column(Text, nullable=False)
    
    # Technical details
    severity_level = Column(String, nullable=False)  # critical, high, medium, low, info
    component = Column(String)  # Which part of system generated event
    error_code = Column(String)
    stack_trace = Column(Text)
    
    # Context data
    context_data = Column(JSON)  # Additional event context
    affected_files = Column(JSON)  # Files affected by this event
    
    # Performance metrics
    memory_usage_mb = Column(Float)
    cpu_usage_percent = Column(Float)
    processing_time_ms = Column(Float)
    
    # Relationships
    session = relationship("AuditSession", back_populates="system_events")

class AuditSummary(Base):
    """Daily/hourly audit summaries for reporting"""
    __tablename__ = "audit_summaries"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    summary_date = Column(DateTime, nullable=False)
    summary_type = Column(String, nullable=False)  # daily, hourly
    
    # Activity counts
    total_sessions = Column(Integer, default=0)
    total_file_uploads = Column(Integer, default=0)
    total_files_processed = Column(Integer, default=0)
    total_downloads = Column(Integer, default=0)
    total_pii_detected = Column(Integer, default=0)
    total_pii_masked = Column(Integer, default=0)
    
    # Performance metrics
    average_processing_time = Column(Float)
    total_data_processed_mb = Column(Float)
    
    # Error tracking
    total_errors = Column(Integer, default=0)
    total_warnings = Column(Integer, default=0)
    
    # PII category breakdown
    pii_category_stats = Column(JSON)  # Detailed breakdown by category
    
    # Security metrics
    unique_ip_addresses = Column(Integer, default=0)
    suspicious_activities = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
