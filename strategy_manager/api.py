"""Flask blueprint exposing strategy management endpoints."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from .models import StrategyStatus
from .service import strategy_service
from .storage import storage

bp = Blueprint("strategies", __name__, url_prefix="/api/strategies")


@bp.get("")
def list_strategies():
    return jsonify({"success": True, "strategies": strategy_service.list_strategies()})


@bp.post("")
def create_strategy():
    payload = request.get_json() or {}
    strategy = strategy_service.create_strategy(payload)
    return jsonify({"success": True, "strategy": strategy.to_dict()})


@bp.put("/<strategy_id>")
def update_strategy(strategy_id: str):
    payload = request.get_json() or {}
    strategy = strategy_service.update_strategy(strategy_id, payload)
    if not strategy:
        return jsonify({"success": False, "message": "策略不存在"}), 404
    return jsonify({"success": True, "strategy": strategy.to_dict()})


@bp.delete("/<strategy_id>")
def delete_strategy(strategy_id: str):
    success = strategy_service.delete_strategy(strategy_id)
    if not success:
        return jsonify({"success": False, "message": "策略不存在"}), 404
    return jsonify({"success": True})


@bp.post("/<strategy_id>/pause")
def pause_strategy(strategy_id: str):
    strategy = strategy_service.pause_strategy(strategy_id)
    if not strategy:
        return jsonify({"success": False, "message": "策略不存在"}), 404
    return jsonify({"success": True, "strategy": strategy.to_dict()})


@bp.post("/<strategy_id>/resume")
def resume_strategy(strategy_id: str):
    strategy = strategy_service.resume_strategy(strategy_id)
    if not strategy:
        return jsonify({"success": False, "message": "策略不存在"}), 404
    return jsonify({"success": True, "strategy": strategy.to_dict()})


@bp.post("/<strategy_id>/stop")
def stop_strategy(strategy_id: str):
    strategy = strategy_service.stop_strategy(strategy_id)
    if not strategy:
        return jsonify({"success": False, "message": "策略不存在"}), 404
    return jsonify({"success": True, "strategy": strategy.to_dict()})


@bp.get("/status")
def strategy_status():
    strategies = strategy_service.list_strategies()
    return jsonify({"success": True, "strategies": strategies})


@bp.post("/webhook")
def webhook_handler():
    payload = request.get_json() or {}
    level = strategy_service.handle_webhook(payload)
    if not level:
        return jsonify({"success": False, "message": "未找到对应的策略或level"}), 404
    return jsonify({"success": True})


@bp.get("/trades")
def trade_logs():
    limit = request.args.get("limit", type=int)
    trades = storage.load_trades(limit=limit)
    return jsonify({"success": True, "trades": trades})
