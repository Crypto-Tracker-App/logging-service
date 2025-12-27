"""Structured JSON logging configuration."""
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs, urlencode
from flask import request, has_request_context, g


# Service metadata
SERVICE_NAME = os.getenv("SERVICE_NAME", "pricing-service")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "1.0.0")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")


def sanitize_path(path):
    """Remove or redact sensitive query parameters from path."""
    if '?' not in path:
        return path
    
    parsed = urlparse(path)
    query_params = parse_qs(parsed.query)
    
    # Sensitive parameter names to redact
    sensitive_params = {'password', 'token', 'api_key', 'secret', 'authorization', 'credit_card'}
    
    # Redact sensitive parameters
    sanitized = {}
    for key, values in query_params.items():
        if key.lower() in sensitive_params:
            sanitized[key] = ['***REDACTED***']
        else:
            sanitized[key] = values
    
    # Reconstruct path with sanitized query
    if sanitized:
        sanitized_query = urlencode(sanitized, doseq=True)
        return f"{parsed.path}?{sanitized_query}"
    return parsed.path


def get_correlation_id():
    """Get or create correlation ID for the current request."""
    if not has_request_context():
        return None
    
    # Try to get from Flask's g object
    if hasattr(g, 'correlation_id'):
        return g.correlation_id
    
    # Try to get from request headers (passed from other services)
    correlation_id = request.headers.get('X-Correlation-ID') or request.headers.get('X-Request-ID')
    
    # Generate new one if not found
    if not correlation_id:
        correlation_id = str(uuid.uuid4())
    
    # Store in g for this request
    g.correlation_id = correlation_id
    return correlation_id


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def format(self, record):
        log_data = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "service": SERVICE_NAME,
            "version": SERVICE_VERSION,
            "environment": ENVIRONMENT,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add correlation ID if available
        correlation_id = get_correlation_id()
        if correlation_id:
            log_data["correlation_id"] = correlation_id

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add request context if available
        if has_request_context():
            log_data["request"] = {
                "method": request.method,
                "path": sanitize_path(request.full_path.rstrip('?')),
                "endpoint": request.endpoint,
            }

        # Add any extra fields from the log record
        # Skip built-in fields and redundant/null fields
        reserved_attrs = {
            'name', 'msg', 'args', 'created', 'filename', 'funcName', 'levelname',
            'levelno', 'lineno', 'module', 'msecs', 'message', 'pathname', 'process',
            'processName', 'relativeCreated', 'thread', 'threadName', 'exc_info',
            'exc_text', 'stack_info', 'correlation_id', 'endpoint', 'taskName'
        }
        
        for key, value in record.__dict__.items():
            if key not in reserved_attrs and not key.startswith('_') and value is not None:
                log_data[key] = value

        return json.dumps(log_data)


def setup_logging():
    """Configure structured JSON logging for all handlers."""
    json_formatter = JSONFormatter()

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Remove default handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add stdout handler with JSON formatter
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(json_formatter)
    root_logger.addHandler(stdout_handler)
    
    # Disable werkzeug's default request logging (we handle this ourselves)
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(logging.WARNING)  # Only show warnings/errors, not INFO


def get_logger(name):
    """Get a logger instance with the given name."""
    return logging.getLogger(name)


def setup_request_logging(app):
    """Set up before/after request logging for the Flask app."""
    logger = get_logger('app.request')
    
    @app.before_request
    def log_request_start():
        """Log incoming requests and ensure correlation ID is set."""
        # Ensure correlation ID is initialized
        correlation_id = get_correlation_id()
        
        logger.info(
            "Request received",
            extra={
                "correlation_id": correlation_id,
                "endpoint": request.endpoint
            }
        )
    
    @app.after_request
    def log_request_end(response):
        """Log request completion with status code."""
        correlation_id = get_correlation_id()
        
        logger.info(
            f"Request completed with status {response.status_code}",
            extra={
                "correlation_id": correlation_id,
                "status_code": response.status_code
            }
        )
        
        # Add correlation ID to response headers for client tracking
        response.headers['X-Correlation-ID'] = correlation_id
        
        return response
    
    @app.teardown_request
    def log_request_error(exception=None):
        """Log any unhandled exceptions."""
        if exception:
            logger.error(
                f"Unhandled exception: {str(exception)}",
                exc_info=True,
                extra={"correlation_id": get_correlation_id()}
            )
