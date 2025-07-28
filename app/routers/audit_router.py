# app/routers/audit_router.py
from fastapi import APIRouter, HTTPException, Query, Depends, Request
from fastapi.responses import StreamingResponse, JSONResponse
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_, func
import csv
import json
import io

from app.database.audit_database import get_audit_db
from app.services.audit_service import AuditService
from app.models.audit_models import (
    AuditSession, FileOperationLog, PIIProcessingLog, 
    UserActionLog, SystemEventLog, PIIDetectionLog
)

router = APIRouter(prefix="/api/audit", tags=["audit"])

@router.get("/statistics")
async def get_audit_statistics(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db: Session = Depends(get_audit_db)
):
    """Get comprehensive audit statistics"""
    try:
        with AuditService() as audit:
            stats = audit.get_audit_statistics(days)
            
            if stats is None:
                raise HTTPException(status_code=500, detail="Failed to retrieve statistics")
            
            return {
                "success": True,
                "data": stats,
                "generated_at": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")

@router.get("/sessions")
async def get_audit_sessions(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    active_only: bool = Query(False),
    db: Session = Depends(get_audit_db)
):
    """Get audit sessions with pagination"""
    try:
        query = db.query(AuditSession)
        
        if active_only:
            query = query.filter(AuditSession.is_active == True)
        
        total = query.count()
        sessions = query.order_by(desc(AuditSession.created_at)).offset(offset).limit(limit).all()
        
        return {
            "success": True,
            "data": {
                "sessions": [
                    {
                        "id": session.id,
                        "session_id": session.session_id,
                        "ip_address": session.ip_address,
                        "user_agent": session.user_agent,
                        "created_at": session.created_at.isoformat(),
                        "last_activity": session.last_activity.isoformat(),
                        "is_active": session.is_active
                    }
                    for session in sessions
                ],
                "total": total,
                "limit": limit,
                "offset": offset
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get sessions: {str(e)}")

@router.get("/file-operations")
async def get_file_operations(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    operation_type: Optional[str] = Query(None, description="Filter by operation type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_audit_db)
):
    """Get file operations with filtering and pagination"""
    try:
        query = db.query(FileOperationLog)
        
        # Apply filters
        if operation_type:
            query = query.filter(FileOperationLog.operation_type == operation_type)
        
        if status:
            query = query.filter(FileOperationLog.status == status)
        
        if start_date:
            query = query.filter(FileOperationLog.timestamp >= start_date)
        
        if end_date:
            query = query.filter(FileOperationLog.timestamp <= end_date)
        
        total = query.count()
        operations = query.order_by(desc(FileOperationLog.timestamp)).offset(offset).limit(limit).all()
        
        return {
            "success": True,
            "data": {
                "operations": [
                    {
                        "id": op.id,
                        "session_id": op.session_id,
                        "task_id": op.task_id,
                        "operation_type": op.operation_type,
                        "timestamp": op.timestamp.isoformat(),
                        "file_name": op.file_name,
                        "file_type": op.file_type,
                        "file_size": op.file_size,
                        "enabled_pii_categories": op.enabled_pii_categories,
                        "total_pii_categories": op.total_pii_categories,
                        "processing_time_seconds": op.processing_time_seconds,
                        "status": op.status,
                        "error_message": op.error_message,
                        "ip_address": op.ip_address
                    }
                    for op in operations
                ],
                "total": total,
                "limit": limit,
                "offset": offset
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get file operations: {str(e)}")

@router.get("/pii-processing")
async def get_pii_processing(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_audit_db)
):
    """Get PII processing logs with pagination"""
    try:
        query = db.query(PIIProcessingLog)
        
        if start_date:
            query = query.filter(PIIProcessingLog.timestamp >= start_date)
        
        if end_date:
            query = query.filter(PIIProcessingLog.timestamp <= end_date)
        
        total = query.count()
        processing_logs = query.order_by(desc(PIIProcessingLog.timestamp)).offset(offset).limit(limit).all()
        
        return {
            "success": True,
            "data": {
                "processing_logs": [
                    {
                        "id": log.id,
                        "session_id": log.session_id,
                        "file_operation_id": log.file_operation_id,
                        "timestamp": log.timestamp.isoformat(),
                        "total_pii_found": log.total_pii_found,
                        "total_pii_masked": log.total_pii_masked,
                        "processing_time_seconds": log.processing_time_seconds,
                        "selectable_pii_found": log.selectable_pii_found,
                        "non_selectable_pii_found": log.non_selectable_pii_found,
                        "masked_categories": log.masked_categories,
                        "average_confidence": log.average_confidence,
                        "low_confidence_count": log.low_confidence_count
                    }
                    for log in processing_logs
                ],
                "total": total,
                "limit": limit,
                "offset": offset
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get PII processing logs: {str(e)}")

@router.get("/user-actions")
async def get_user_actions(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    action_type: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_audit_db)
):
    """Get user actions with filtering and pagination"""
    try:
        query = db.query(UserActionLog)
        
        if action_type:
            query = query.filter(UserActionLog.action_type == action_type)
        
        if session_id:
            query = query.filter(UserActionLog.session_id == session_id)
        
        if start_date:
            query = query.filter(UserActionLog.timestamp >= start_date)
        
        if end_date:
            query = query.filter(UserActionLog.timestamp <= end_date)
        
        total = query.count()
        actions = query.order_by(desc(UserActionLog.timestamp)).offset(offset).limit(limit).all()
        
        return {
            "success": True,
            "data": {
                "actions": [
                    {
                        "id": action.id,
                        "session_id": action.session_id,
                        "timestamp": action.timestamp.isoformat(),
                        "action_type": action.action_type,
                        "action_name": action.action_name,
                        "action_details": action.action_details,
                        "page_url": action.page_url,
                        "http_method": action.http_method,
                        "endpoint": action.endpoint,
                        "response_status": action.response_status,
                        "response_time_ms": action.response_time_ms,
                        "ip_address": action.ip_address
                    }
                    for action in actions
                ],
                "total": total,
                "limit": limit,
                "offset": offset
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get user actions: {str(e)}")

@router.get("/system-events")
async def get_system_events(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    event_type: Optional[str] = Query(None),
    severity_level: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_audit_db)
):
    """Get system events with filtering and pagination"""
    try:
        query = db.query(SystemEventLog)
        
        if event_type:
            query = query.filter(SystemEventLog.event_type == event_type)
        
        if severity_level:
            query = query.filter(SystemEventLog.severity_level == severity_level)
        
        if start_date:
            query = query.filter(SystemEventLog.timestamp >= start_date)
        
        if end_date:
            query = query.filter(SystemEventLog.timestamp <= end_date)
        
        total = query.count()
        events = query.order_by(desc(SystemEventLog.timestamp)).offset(offset).limit(limit).all()
        
        return {
            "success": True,
            "data": {
                "events": [
                    {
                        "id": event.id,
                        "session_id": event.session_id,
                        "timestamp": event.timestamp.isoformat(),
                        "event_type": event.event_type,
                        "event_category": event.event_category,
                        "event_name": event.event_name,
                        "event_message": event.event_message,
                        "severity_level": event.severity_level,
                        "component": event.component,
                        "error_code": event.error_code,
                        "context_data": event.context_data,
                        "memory_usage_mb": event.memory_usage_mb,
                        "cpu_usage_percent": event.cpu_usage_percent
                    }
                    for event in events
                ],
                "total": total,
                "limit": limit,
                "offset": offset
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get system events: {str(e)}")

@router.get("/export/csv")
async def export_audit_data_csv(
    table: str = Query(..., description="Table to export: sessions, file_operations, pii_processing, user_actions, system_events"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    limit: int = Query(10000, ge=1, le=50000),
    db: Session = Depends(get_audit_db)
):
    """Export audit data as CSV"""
    try:
        # Map table names to models
        table_models = {
            "sessions": AuditSession,
            "file_operations": FileOperationLog,
            "pii_processing": PIIProcessingLog,
            "user_actions": UserActionLog,
            "system_events": SystemEventLog
        }
        
        if table not in table_models:
            raise HTTPException(status_code=400, detail=f"Invalid table: {table}")
        
        model = table_models[table]
        query = db.query(model)
        
        # Apply date filters if provided
        if hasattr(model, 'timestamp'):
            if start_date:
                query = query.filter(model.timestamp >= start_date)
            if end_date:
                query = query.filter(model.timestamp <= end_date)
        elif hasattr(model, 'created_at'):
            if start_date:
                query = query.filter(model.created_at >= start_date)
            if end_date:
                query = query.filter(model.created_at <= end_date)
        
        # Get data
        data = query.limit(limit).all()
        
        # Create CSV content
        output = io.StringIO()
        if data:
            # Get column names from the first record
            columns = [column.name for column in model.__table__.columns]
            writer = csv.DictWriter(output, fieldnames=columns)
            writer.writeheader()
            
            for record in data:
                row = {}
                for column in columns:
                    value = getattr(record, column)
                    if isinstance(value, datetime):
                        row[column] = value.isoformat()
                    elif isinstance(value, (dict, list)):
                        row[column] = json.dumps(value)
                    else:
                        row[column] = value
                writer.writerow(row)
        
        # Create response
        output.seek(0)
        filename = f"audit_{table}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode()),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export data: {str(e)}")

@router.get("/export/json")
async def export_audit_data_json(
    table: str = Query(..., description="Table to export"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    limit: int = Query(10000, ge=1, le=50000),
    db: Session = Depends(get_audit_db)
):
    """Export audit data as JSON"""
    try:
        # Use the same logic as CSV export but return JSON
        table_models = {
            "sessions": AuditSession,
            "file_operations": FileOperationLog,
            "pii_processing": PIIProcessingLog,
            "user_actions": UserActionLog,
            "system_events": SystemEventLog
        }
        
        if table not in table_models:
            raise HTTPException(status_code=400, detail=f"Invalid table: {table}")
        
        model = table_models[table]
        query = db.query(model)
        
        # Apply date filters
        if hasattr(model, 'timestamp'):
            if start_date:
                query = query.filter(model.timestamp >= start_date)
            if end_date:
                query = query.filter(model.timestamp <= end_date)
        elif hasattr(model, 'created_at'):
            if start_date:
                query = query.filter(model.created_at >= start_date)
            if end_date:
                query = query.filter(model.created_at <= end_date)
        
        data = query.limit(limit).all()
        
        # Convert to JSON-serializable format
        json_data = []
        for record in data:
            row = {}
            for column in model.__table__.columns:
                value = getattr(record, column.name)
                if isinstance(value, datetime):
                    row[column.name] = value.isoformat()
                else:
                    row[column.name] = value
            json_data.append(row)
        
        filename = f"audit_{table}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        
        return JSONResponse(
            content={
                "success": True,
                "table": table,
                "exported_at": datetime.utcnow().isoformat(),
                "record_count": len(json_data),
                "data": json_data
            },
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export JSON: {str(e)}")
