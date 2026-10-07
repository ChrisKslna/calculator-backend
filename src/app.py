"""Flask JSON API: validate, calculate, persist, query and delete."""

import os
import sqlite3
from pathlib import Path

from flask import Flask, request
from werkzeug.exceptions import HTTPException

from src import database
from src.calculator import CalculationError, calculate_expression


def create_app(test_config=None):
    """Create an app with a configurable, persistent SQLite database."""
    app = Flask(__name__, static_folder=None)
    default_db = Path(__file__).resolve().parent.parent / "instance/history.db"
    app.config.from_mapping(
        MAX_CONTENT_LENGTH=16 * 1024,
        DATABASE=os.environ.get("CALCULATOR_DATABASE", str(default_db)),
    )
    if test_config:
        app.config.update(test_config)
    app.json.ensure_ascii = False
    database.initialize(app.config["DATABASE"])

    @app.get("/api/health")
    def health():
        with database.connect(app.config["DATABASE"]) as connection:
            connection.execute("SELECT 1 FROM calculation_history LIMIT 1")
        return {"success": True, "message": "Calculator backend is running"}

    @app.post("/api/calculate")
    def calculate():
        if not request.is_json:
            return failure("请使用 JSON 格式发送请求。", "INVALID_TYPE"), 415
        payload = request.get_json()
        if not isinstance(payload, dict):
            return failure("请求内容必须是 JSON 对象。", "INVALID_INPUT"), 400
        expression = payload.get("expression")
        result = calculate_expression(expression)
        record = database.save_calculation(
            app.config["DATABASE"], expression.strip(), result
        )
        # Success is returned only after the database transaction commits.
        return {"success": True, **record}

    @app.get("/api/history")
    def history():
        try:
            page = int(request.args.get("page", "1"))
            page_size = int(request.args.get("page_size", "8"))
            if not 1 <= page <= 1000000 or not 1 <= page_size <= 100:
                raise ValueError
        except ValueError:
            return failure(
                "页码须为正整数，每页条数须在 1 到 100 之间。",
                "INVALID_PAGINATION",
            ), 400
        data = database.list_history(app.config["DATABASE"], page, page_size)
        return {"success": True, **data}

    @app.delete("/api/history/<int:record_id>")
    def delete_history(record_id):
        if not database.delete_calculation(app.config["DATABASE"], record_id):
            return failure("这条记录已不存在，请刷新列表。", "NOT_FOUND"), 404
        return {"success": True, "deleted_id": record_id}

    @app.errorhandler(CalculationError)
    def handle_calculation_error(error):
        response = failure(str(error), error.code)
        if error.position is not None:
            response["position"] = error.position
        return response, 400

    @app.errorhandler(sqlite3.Error)
    def handle_database_error(error):
        app.logger.exception("Database operation failed")
        return failure(
            "历史记录服务暂时不可用，请稍后重试。", "DATABASE_ERROR"
        ), 503

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        messages = {
            400: "请求格式不正确，请检查 JSON 内容。",
            404: "请求的接口不存在。",
            405: "该接口不支持此请求方法。",
            413: "请求内容过长。",
            500: "服务器暂时出现问题，请稍后重试。",
        }
        response = error.get_response()
        response.data = app.json.dumps(failure(
            messages.get(error.code, error.description),
            error.name.upper().replace(" ", "_"),
        ))
        response.content_type = "application/json"
        return response

    @app.after_request
    def response_headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    return app


def failure(message, code):
    return {"success": False, "message": message, "code": code}
