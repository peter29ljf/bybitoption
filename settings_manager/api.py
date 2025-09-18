"""Flask blueprint for updating application settings."""

from __future__ import annotations

from flask import Blueprint, jsonify, request, current_app

from .manager import AppSettings, settings_manager

bp = Blueprint("settings", __name__, url_prefix="/api/settings")


def _mask_secret(secret: str) -> str:
    if not secret:
        return ""
    if len(secret) <= 4:
        return "*" * len(secret)
    return secret[:2] + "*" * (len(secret) - 4) + secret[-2:]


@bp.get("")
def get_settings():
    settings = settings_manager.get_settings()
    data = settings.to_dict()
    data["api_secret_masked"] = _mask_secret(data.get("api_secret", ""))
    return jsonify({"success": True, "settings": data})


@bp.post("")
def update_settings():
    payload = request.get_json() or {}
    required_fields = {"api_key", "api_secret", "is_testnet"}
    missing = [field for field in required_fields if field not in payload]
    if missing:
        return jsonify({"success": False, "message": f"缺少字段: {', '.join(missing)}"}), 400

    settings = settings_manager.update(payload)
    handler = current_app.extensions.get("settings_apply_callback")
    if handler:
        handler(settings)
    return jsonify({"success": True, "settings": settings.to_dict()})
