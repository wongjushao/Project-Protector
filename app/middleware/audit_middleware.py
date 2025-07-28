# app/middleware/audit_middleware.py
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse
import time
import uuid
import json
from typing import Callable
from app.services.audit_service import AuditService
import logging

logger = logging.getLogger(__name__)

class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware to automatically audit all HTTP requests and responses"""
    
    def __init__(self, app, exclude_paths: list = None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or [
            "/static/", "/favicon.ico", "/docs", "/openapi.json", "/redoc"
        ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> StarletteResponse:
        # Skip audit for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
        
        # Start timing
        start_time = time.time()
        
        # Get or create session ID
        session_id = self._get_or_create_session_id(request)
        
        # Get client information
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")
        
        # Process request first
        response = None
        error_occurred = False
        error_message = None

        try:
            response = await call_next(request)
        except Exception as e:
            error_occurred = True
            error_message = str(e)
            logger.error(f"Request error: {e}")
            # Re-raise the exception
            raise
        finally:
            # Calculate response time
            response_time_ms = (time.time() - start_time) * 1000

            # Log the request asynchronously (don't block response)
            try:
                await self._log_request_async(
                    request, response, session_id, client_ip,
                    user_agent, response_time_ms, error_occurred, error_message
                )
            except Exception as e:
                logger.error(f"Failed to log request: {e}")
        
        return response
    
    def _get_or_create_session_id(self, request: Request) -> str:
        """Get existing session ID or create new one"""
        # Try to get from cookie first
        session_id = request.cookies.get("audit_session_id")
        
        if not session_id:
            # Create new session ID
            session_id = str(uuid.uuid4())
            # Store in request state for response cookie setting
            request.state.new_session_id = session_id
        
        return session_id
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address, handling proxies"""
        # Check for forwarded headers first
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # Fallback to direct client IP
        if hasattr(request.client, "host"):
            return request.client.host
        
        return "unknown"
    
    async def _log_request_async(
        self,
        request: Request,
        response: Response,
        session_id: str,
        client_ip: str,
        user_agent: str,
        response_time_ms: float,
        error_occurred: bool,
        error_message: str = None
    ):
        """Log the HTTP request details asynchronously"""

        # Create audit service for this request
        try:
            with AuditService() as audit:
                # Create session if new
                if not hasattr(request.state, "audit_session_created"):
                    audit.create_session(session_id, client_ip, user_agent)
                    request.state.audit_session_created = True

                # Determine action type based on request
                action_type = self._determine_action_type(request)
                action_name = self._determine_action_name(request)

                # Get request data (sanitized)
                request_data = await self._get_request_data(request)

                # Get response status
                response_status = response.status_code if response else 500

                # Log user action
                audit.log_user_action(
            session_id=session_id,
            action_type=action_type,
            action_name=action_name,
            ip_address=client_ip,
            user_agent=user_agent,
            action_details={
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "error_occurred": error_occurred,
                "error_message": error_message
            },
            page_url=str(request.url),
            http_method=request.method,
            endpoint=request.url.path,
            request_data=request_data,
            response_status=response_status,
            response_time_ms=response_time_ms
        )
        
                # Log system event if error occurred
                if error_occurred:
                    audit.log_system_event(
                        event_type="error",
                        event_category="system",
                        event_name="request_error",
                        event_message=f"Request failed: {error_message}",
                        severity_level="high",
                        component="http_middleware",
                        session_id=session_id,
                        context_data={
                            "method": request.method,
                            "path": request.url.path,
                            "client_ip": client_ip,
                            "user_agent": user_agent
                        }
                    )
        except Exception as e:
            logger.error(f"Failed to create audit log: {e}")
    
    def _determine_action_type(self, request: Request) -> str:
        """Determine the type of action based on request"""
        if request.method == "GET":
            return "page_visit"
        elif request.method == "POST":
            if "/api/" in request.url.path:
                return "api_call"
            else:
                return "form_submit"
        elif request.method in ["PUT", "PATCH", "DELETE"]:
            return "data_modification"
        else:
            return "other"
    
    def _determine_action_name(self, request: Request) -> str:
        """Determine the specific action name"""
        path = request.url.path
        
        # Map common paths to action names
        action_mapping = {
            "/": "home_page",
            "/audit": "audit_dashboard",
            "/api/upload_files": "file_upload",
            "/api/process/": "file_process",
            "/api/download/": "file_download",
            "/api/audit/": "audit_query"
        }
        
        # Check for exact matches
        if path in action_mapping:
            return action_mapping[path]
        
        # Check for pattern matches
        for pattern, name in action_mapping.items():
            if pattern.endswith("/") and path.startswith(pattern):
                return name
        
        # Default to path-based name
        return path.replace("/", "_").replace("-", "_").strip("_") or "root"
    
    async def _get_request_data(self, request: Request) -> dict:
        """Extract and sanitize request data"""
        try:
            data = {}
            
            # Add query parameters
            if request.query_params:
                data["query_params"] = dict(request.query_params)
            
            # Add form data for POST requests (but not file uploads)
            if request.method == "POST":
                content_type = request.headers.get("content-type", "")
                
                if "application/json" in content_type:
                    try:
                        # For JSON requests, we need to be careful not to consume the body
                        # as it might be needed by the actual endpoint
                        pass  # Skip JSON body for now to avoid consumption issues
                    except:
                        pass
                elif "application/x-www-form-urlencoded" in content_type:
                    try:
                        form_data = await request.form()
                        data["form_data"] = {key: value for key, value in form_data.items() 
                                           if not hasattr(value, 'read')}  # Exclude file uploads
                    except:
                        pass
            
            return data
            
        except Exception as e:
            logger.warning(f"Could not extract request data: {e}")
            return {}

class AuditResponseMiddleware:
    """Middleware to set audit session cookies in responses"""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Create a custom send function to modify response
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                # Check if we need to set session cookie
                request = scope.get("state", {})
                if hasattr(request, "new_session_id"):
                    # Add session cookie to headers
                    headers = list(message.get("headers", []))
                    cookie_value = f"audit_session_id={request.new_session_id}; Path=/; HttpOnly; SameSite=Lax"
                    headers.append((b"set-cookie", cookie_value.encode()))
                    message["headers"] = headers
            
            await send(message)
        
        await self.app(scope, receive, send_wrapper)
