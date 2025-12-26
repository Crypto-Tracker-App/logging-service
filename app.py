"""
Sample Flask application with structured JSON logging.
Used for development and testing of the logging-service.
"""
import json
import logging
import sys
from datetime import datetime
from flask import Flask, jsonify, request

app = Flask(__name__)


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record):
        log_data = {
            "timestamp": datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add request context if available
        if request:
            log_data["request"] = {
                "method": request.method,
                "path": request.path,
                "remote_addr": request.remote_addr,
            }
        
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


setup_logging()
logger = logging.getLogger(__name__)


@app.before_request
def log_request():
    """Log incoming requests."""
    logger.info(f"Incoming {request.method} request", extra={
        "request_path": request.path,
        "remote_addr": request.remote_addr
    })


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    logger.info("Health check passed")
    return jsonify({"status": "healthy"}), 200


@app.route("/api/data", methods=["GET"])
def get_data():
    """Sample data endpoint."""
    try:
        logger.info("Fetching data", extra={"action": "fetch_data"})
        data = {"items": [1, 2, 3], "count": 3}
        logger.info("Data fetched successfully", extra={"items_count": 3})
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"Error fetching data: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/error", methods=["GET"])
def trigger_error():
    """Endpoint that intentionally triggers an error for testing."""
    logger.warning("Error trigger endpoint called")
    try:
        raise ValueError("This is a test error")
    except Exception as e:
        logger.error(f"Test error occurred: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    logger.info("Starting Flask application", extra={"version": "1.0.0"})
    app.run(host="0.0.0.0", port=5000, debug=False)
