# app/services/audit_service.py
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import hashlib
import json
import psutil
import time
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_, or_

from app.database.audit_database import get_audit_db_sync
from app.models.audit_models import (
    AuditSession, FileOperationLog, PIIProcessingLog, PIIDetectionLog,
    UserActionLog, SystemEventLog, AuditSummary
)
import logging

logger = logging.getLogger(__name__)

class AuditService:
    """Comprehensive audit service for tracking all system activities"""

    def __init__(self):
        self.db = None

    def __enter__(self):
        self.db = get_audit_db_sync()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.db:
            self.db.close()

    def _get_db(self):
        """Get database connection, create if needed"""
        if self.db is None:
            self.db = get_audit_db_sync()
        return self.db
    
    # ===== SESSION MANAGEMENT =====
    
    def create_session(self, session_id: str, ip_address: str, user_agent: str = None) -> str:
        """Create a new audit session"""
        try:
            db = self._get_db()
            session = AuditSession(
                session_id=session_id,
                ip_address=ip_address,
                user_agent=user_agent,
                created_at=datetime.utcnow(),
                last_activity=datetime.utcnow(),
                is_active=True
            )

            db.add(session)
            db.commit()

            logger.info(f"✅ Created audit session: {session_id}")
            return session.id

        except Exception as e:
            logger.error(f"❌ Failed to create audit session: {e}")
            if self.db:
                self.db.rollback()
            return None
    
    def update_session_activity(self, session_id: str):
        """Update session last activity timestamp"""
        try:
            db = self._get_db()
            session = db.query(AuditSession).filter(
                AuditSession.session_id == session_id
            ).first()

            if session:
                session.last_activity = datetime.utcnow()
                db.commit()

        except Exception as e:
            logger.error(f"❌ Failed to update session activity: {e}")
    
    def close_session(self, session_id: str):
        """Close an audit session"""
        try:
            session = self.db.query(AuditSession).filter(
                AuditSession.session_id == session_id
            ).first()
            
            if session:
                session.is_active = False
                session.last_activity = datetime.utcnow()
                self.db.commit()
                
        except Exception as e:
            logger.error(f"❌ Failed to close session: {e}")
    
    # ===== FILE OPERATIONS =====
    
    def log_file_operation(
        self,
        session_id: str,
        task_id: str,
        operation_type: str,
        file_name: str,
        file_type: str,
        file_size: int,
        enabled_pii_categories: List[str],
        ip_address: str,
        user_agent: str = None,
        file_content: bytes = None,
        processing_time: float = None,
        status: str = "success",
        error_message: str = None
    ) -> str:
        """Log file operation (upload, process, download)"""
        try:
            # Generate file hash for integrity
            file_hash = None
            if file_content:
                file_hash = hashlib.sha256(file_content).hexdigest()
            
            file_op = FileOperationLog(
                session_id=session_id,
                task_id=task_id,
                operation_type=operation_type,
                timestamp=datetime.utcnow(),
                file_name=file_name,
                file_type=file_type,
                file_size=file_size,
                file_hash=file_hash,
                enabled_pii_categories=enabled_pii_categories,
                total_pii_categories=len(enabled_pii_categories) if enabled_pii_categories else 0,
                processing_time_seconds=processing_time,
                status=status,
                error_message=error_message,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            self.db.add(file_op)
            self.db.commit()
            
            # Update session activity
            self.update_session_activity(session_id)
            
            logger.info(f"✅ Logged file operation: {operation_type} - {file_name}")
            return file_op.id
            
        except Exception as e:
            logger.error(f"❌ Failed to log file operation: {e}")
            self.db.rollback()
            return None
    
    # ===== PII PROCESSING =====
    
    def log_pii_processing(
        self,
        session_id: str,
        file_operation_id: str,
        total_pii_found: int,
        total_pii_masked: int,
        processing_time: float,
        selectable_pii_found: Dict[str, int],
        non_selectable_pii_found: Dict[str, int],
        masked_categories: List[str],
        average_confidence: float = None,
        low_confidence_count: int = 0
    ) -> str:
        """Log PII processing summary"""
        try:
            pii_log = PIIProcessingLog(
                session_id=session_id,
                file_operation_id=file_operation_id,
                timestamp=datetime.utcnow(),
                total_pii_found=total_pii_found,
                total_pii_masked=total_pii_masked,
                processing_time_seconds=processing_time,
                selectable_pii_found=selectable_pii_found,
                non_selectable_pii_found=non_selectable_pii_found,
                masked_categories=masked_categories,
                average_confidence=average_confidence,
                low_confidence_count=low_confidence_count
            )
            
            self.db.add(pii_log)
            self.db.commit()
            
            logger.info(f"✅ Logged PII processing: {total_pii_found} found, {total_pii_masked} masked")
            return pii_log.id
            
        except Exception as e:
            logger.error(f"❌ Failed to log PII processing: {e}")
            self.db.rollback()
            return None
    
    def log_pii_detection(
        self,
        file_operation_id: str,
        pii_type: str,
        pii_category: str,
        pii_value: str,
        confidence_score: float,
        was_masked: bool,
        detection_method: str,
        position_in_text: int = None
    ) -> str:
        """Log individual PII detection (with anonymized value)"""
        try:
            # Hash the PII value for privacy
            pii_value_hash = hashlib.sha256(pii_value.encode()).hexdigest()
            
            detection_log = PIIDetectionLog(
                file_operation_id=file_operation_id,
                timestamp=datetime.utcnow(),
                pii_type=pii_type,
                pii_category=pii_category,
                pii_value_hash=pii_value_hash,
                pii_length=len(pii_value),
                confidence_score=confidence_score,
                was_masked=was_masked,
                detection_method=detection_method,
                position_in_text=position_in_text
            )
            
            self.db.add(detection_log)
            self.db.commit()
            
            return detection_log.id
            
        except Exception as e:
            logger.error(f"❌ Failed to log PII detection: {e}")
            self.db.rollback()
            return None
    
    # ===== USER ACTIONS =====
    
    def log_user_action(
        self,
        session_id: str,
        action_type: str,
        action_name: str,
        ip_address: str,
        user_agent: str = None,
        action_details: Dict[str, Any] = None,
        page_url: str = None,
        http_method: str = None,
        endpoint: str = None,
        request_data: Dict[str, Any] = None,
        response_status: int = None,
        response_time_ms: float = None
    ) -> str:
        """Log user action"""
        try:
            # Sanitize request data (remove sensitive information)
            sanitized_request = self._sanitize_request_data(request_data)
            
            action_log = UserActionLog(
                session_id=session_id,
                timestamp=datetime.utcnow(),
                action_type=action_type,
                action_name=action_name,
                action_details=action_details,
                page_url=page_url,
                http_method=http_method,
                endpoint=endpoint,
                request_data=sanitized_request,
                response_status=response_status,
                response_time_ms=response_time_ms,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            self.db.add(action_log)
            self.db.commit()
            
            # Update session activity
            self.update_session_activity(session_id)
            
            return action_log.id
            
        except Exception as e:
            logger.error(f"❌ Failed to log user action: {e}")
            self.db.rollback()
            return None
    
    # ===== SYSTEM EVENTS =====
    
    def log_system_event(
        self,
        event_type: str,
        event_category: str,
        event_name: str,
        event_message: str,
        severity_level: str,
        component: str = None,
        session_id: str = None,
        error_code: str = None,
        stack_trace: str = None,
        context_data: Dict[str, Any] = None,
        affected_files: List[str] = None
    ) -> str:
        """Log system event"""
        try:
            # Get system metrics
            memory_usage = psutil.virtual_memory().percent
            cpu_usage = psutil.cpu_percent()
            
            system_log = SystemEventLog(
                session_id=session_id,
                timestamp=datetime.utcnow(),
                event_type=event_type,
                event_category=event_category,
                event_name=event_name,
                event_message=event_message,
                severity_level=severity_level,
                component=component,
                error_code=error_code,
                stack_trace=stack_trace,
                context_data=context_data,
                affected_files=affected_files,
                memory_usage_mb=memory_usage,
                cpu_usage_percent=cpu_usage
            )
            
            self.db.add(system_log)
            self.db.commit()
            
            logger.info(f"✅ Logged system event: {event_type} - {event_name}")
            return system_log.id
            
        except Exception as e:
            logger.error(f"❌ Failed to log system event: {e}")
            self.db.rollback()
            return None
    
    # ===== UTILITY METHODS =====
    
    def _sanitize_request_data(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive data from request logs"""
        if not request_data:
            return None
        
        sensitive_keys = {
            'password', 'token', 'key', 'secret', 'auth', 'credential',
            'ic', 'email', 'phone', 'credit_card', 'bank_account'
        }
        
        sanitized = {}
        for key, value in request_data.items():
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in sensitive_keys):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, (dict, list)):
                sanitized[key] = "[COMPLEX_DATA]"
            else:
                sanitized[key] = str(value)[:100]  # Limit length
        
        return sanitized

    def get_audit_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Get audit statistics for the specified number of days"""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)

            # File operations stats
            file_ops = self.db.query(FileOperationLog).filter(
                FileOperationLog.timestamp >= start_date
            ).all()

            # PII processing stats
            pii_ops = self.db.query(PIIProcessingLog).filter(
                PIIProcessingLog.timestamp >= start_date
            ).all()

            # User actions stats
            user_actions = self.db.query(UserActionLog).filter(
                UserActionLog.timestamp >= start_date
            ).all()

            # System events stats
            system_events = self.db.query(SystemEventLog).filter(
                SystemEventLog.timestamp >= start_date
            ).all()

            stats = {
                "period_days": days,
                "start_date": start_date.isoformat(),
                "end_date": datetime.utcnow().isoformat(),
                "file_operations": {
                    "total": len(file_ops),
                    "uploads": len([op for op in file_ops if op.operation_type == "upload"]),
                    "processes": len([op for op in file_ops if op.operation_type == "process"]),
                    "downloads": len([op for op in file_ops if op.operation_type == "download"]),
                    "errors": len([op for op in file_ops if op.status == "error"])
                },
                "pii_processing": {
                    "total_operations": len(pii_ops),
                    "total_pii_found": sum(op.total_pii_found for op in pii_ops),
                    "total_pii_masked": sum(op.total_pii_masked for op in pii_ops),
                    "average_processing_time": sum(op.processing_time_seconds for op in pii_ops if op.processing_time_seconds) / len(pii_ops) if pii_ops else 0
                },
                "user_activity": {
                    "total_actions": len(user_actions),
                    "page_visits": len([a for a in user_actions if a.action_type == "page_visit"]),
                    "button_clicks": len([a for a in user_actions if a.action_type == "button_click"]),
                    "config_changes": len([a for a in user_actions if a.action_type == "config_change"])
                },
                "system_events": {
                    "total": len(system_events),
                    "errors": len([e for e in system_events if e.event_type == "error"]),
                    "warnings": len([e for e in system_events if e.event_type == "warning"]),
                    "security": len([e for e in system_events if e.event_category == "security"])
                }
            }

            return stats

        except Exception as e:
            logger.error(f"❌ Failed to get audit statistics: {e}")
            return None

# Global audit service instance
audit_service = AuditService()
