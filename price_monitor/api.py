"""价格监控API接口"""
import json
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from .models import OptionInfo, MonitorTask
from .monitor_service import get_monitor_service, stop_monitor_service
from .config import MonitorConfig

# 配置日志
logging.basicConfig(
    level=getattr(logging, MonitorConfig.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(MonitorConfig.LOG_FILE),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def _load_active_task_snapshot() -> Dict[str, Any]:
    """读取活跃任务快照文件。"""
    file_path = MonitorConfig.ACTIVE_TASKS_FILE
    if not file_path.exists():
        return {"updated_at": None, "tasks": []}

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data.setdefault("tasks", [])
            return data
        return {"updated_at": None, "tasks": []}
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("读取活跃任务快照失败: %s", exc)
        return {"updated_at": None, "tasks": []}


def _find_snapshot_task(task_id: str) -> Optional[Dict[str, Any]]:
    """在快照中查找指定任务。"""
    snapshot = _load_active_task_snapshot()
    for item in snapshot.get("tasks", []):
        if item.get("task_id") == task_id:
            item["snapshot_updated_at"] = snapshot.get("updated_at")
            return item
    return None

# 创建FastAPI应用
app = FastAPI(
    title="期权价格监控API",
    description="实时监控期权价格并在达到目标价格时发送webhook通知",
    version="1.0.0"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 请求模型
class CreateMonitorTaskRequest(BaseModel):
    """创建监控任务请求"""
    task_id: str = Field(..., description="任务唯一编号")
    option_symbol: str = Field(..., description="期权合约符号，如: BTC-17JAN25-100000-C")
    target_price: float = Field(..., gt=0, description="目标价格（必须大于0）")
    webhook_url: str = Field(..., description="接收webhook的网址")
    timeout_hours: int = Field(24, ge=1, le=168, description="任务超时时间（小时），默认24小时，最大168小时")
    strategy_id: str = Field(..., description="策略ID")
    level_id: str = Field(..., description="Level ID")
    monitor_type: str = Field(..., description="监控类型: ENTRY/TAKE_PROFIT/STOP_LOSS")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="附加数据")
    monitor_instrument: str = Field('option', description="监控标的类型: option 或 spot")
    monitor_symbol: Optional[str] = Field(None, description="实际监控的symbol，option模式默认为期权符号")
    
    @validator('option_symbol')
    def validate_option_symbol(cls, v):
        """验证期权合约符号格式"""
        # 支持两种格式：
        # 1. BTC-17JAN25-100000-C (旧格式)
        # 2. BTC-17JAN25-100000-C-USDT (新格式，Bybit实际使用的)
        parts = v.split('-')
        if len(parts) not in [4, 5]:
            raise ValueError("期权合约符号格式错误，应为: BASE-EXPIRY-STRIKE-TYPE 或 BASE-EXPIRY-STRIKE-TYPE-USDT")
        
        base_coin = parts[0]
        expiry = parts[1]
        strike = parts[2]
        option_type = parts[3]
        
        if base_coin not in ['BTC', 'ETH']:
            raise ValueError("基础币种只支持 BTC 或 ETH")
        
        if option_type not in ['C', 'P', 'Call', 'Put']:
            raise ValueError("期权类型只支持 C/Call（看涨）或 P/Put（看跌）")
        
        try:
            float(strike)
        except ValueError:
            raise ValueError("执行价格必须是有效数字")
        
        # 如果是5部分格式，检查最后一部分是否为USDT
        if len(parts) == 5 and parts[4] not in ['USDT']:
            raise ValueError("目前只支持USDT结算的期权")
        
        return v
    
    @validator('webhook_url')
    def validate_webhook_url(cls, v):
        """验证webhook URL"""
        if not v.startswith(('http://', 'https://')):
            raise ValueError("webhook URL必须以 http:// 或 https:// 开头")
        return v

    @validator('monitor_type')
    def validate_monitor_type(cls, v):
        allowed = {'ENTRY', 'TAKE_PROFIT', 'STOP_LOSS'}
        if v not in allowed:
            raise ValueError(f"monitor_type 必须是 {allowed}")
        return v

    @validator('monitor_instrument')
    def validate_monitor_instrument(cls, v):
        allowed = {'option', 'spot'}
        if v not in allowed:
            raise ValueError(f"monitor_instrument 必须是 {allowed}")
        return v

    @validator('monitor_symbol', always=True)
    def ensure_monitor_symbol(cls, v, values):
        instrument = values.get('monitor_instrument', 'option')
        option_symbol = values.get('option_symbol')
        if instrument == 'spot':
            if not v:
                raise ValueError("monitor_symbol 在 spot 模式下必填")
            return v.upper()
        return (v or option_symbol).upper()

class TaskStatusResponse(BaseModel):
    """任务状态响应"""
    task_id: str
    status: str
    option_symbol: str
    monitor_symbol: str
    monitor_instrument: str
    target_price: float
    current_price: float = None
    created_at: str
    expires_at: str
    triggered_at: str = None
    webhook_url: str

class ApiResponse(BaseModel):
    """API响应"""
    success: bool
    message: str
    data: Dict[str, Any] = None

# API路由
@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    try:
        # 启动监控服务
        await get_monitor_service()
        logger.info("期权价格监控API启动成功")
    except Exception as e:
        logger.error(f"启动监控服务失败: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    try:
        await stop_monitor_service()
        logger.info("期权价格监控API关闭完成")
    except Exception as e:
        logger.error(f"关闭监控服务失败: {e}")

@app.get("/", response_model=ApiResponse)
async def root():
    """根路径"""
    return ApiResponse(
        success=True,
        message="期权价格监控API运行中",
        data={
            "version": "1.0.0",
            "endpoints": {
                "create_task": "POST /api/monitor/create",
                "get_task": "GET /api/monitor/{task_id}",
                "delete_task": "DELETE /api/monitor/{task_id}",
                "list_tasks": "GET /api/monitor/tasks"
            }
        }
    )

@app.get("/health")
async def health_check():
    """健康检查"""
    try:
        monitor_service = await get_monitor_service()
        is_healthy = monitor_service.running and monitor_service.ws_client.running
        
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "websocket_connected": monitor_service.ws_client.running,
            "active_tasks": len(monitor_service.active_tasks)
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }

@app.post("/api/monitor/create", response_model=ApiResponse)
async def create_monitor_task(request: CreateMonitorTaskRequest):
    """创建监控任务"""
    try:
        # 获取监控服务
        monitor_service = await get_monitor_service()
        
        # 检查任务ID是否已存在
        existing_task = await monitor_service.get_task_status(request.task_id)
        if existing_task:
            raise HTTPException(
                status_code=400,
                detail=f"任务ID '{request.task_id}' 已存在"
            )
        
        # 检查活跃任务数量限制
        if len(monitor_service.active_tasks) >= MonitorConfig.MAX_TASKS:
            raise HTTPException(
                status_code=429,
                detail=f"活跃任务数量已达到上限 {MonitorConfig.MAX_TASKS}"
            )
        
        # 解析期权信息
        option_info = _parse_option_symbol(request.option_symbol)

        if request.monitor_instrument == 'spot' and request.monitor_symbol != 'BTCUSDT':
            raise HTTPException(
                status_code=422,
                detail="当前仅支持 BTCUSDT 现货价格监控"
            )

        # 创建监控任务
        current_time = datetime.now()
        expires_at = current_time + timedelta(hours=request.timeout_hours)
        
        task = MonitorTask(
            task_id=request.task_id,
            option_info=option_info,
            monitor_symbol=request.monitor_symbol,
            monitor_instrument=request.monitor_instrument,
            target_price=request.target_price,
            webhook_url=request.webhook_url,
            created_at=current_time,
            expires_at=expires_at,
            strategy_id=request.strategy_id,
            level_id=request.level_id,
            monitor_type=request.monitor_type,
            metadata=request.metadata
        )
        
        # 添加任务到监控服务
        success = await monitor_service.add_monitor_task(task)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="创建监控任务失败"
            )
        
        logger.info(f"创建监控任务成功: {request.task_id}")
        
        return ApiResponse(
            success=True,
            message="监控任务创建成功",
            data={
                "task_id": request.task_id,
                "option_symbol": request.option_symbol,
                "monitor_symbol": request.monitor_symbol,
                "monitor_instrument": request.monitor_instrument,
                "target_price": request.target_price,
                "expires_at": expires_at.isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建监控任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/monitor/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """获取任务状态"""
    try:
        snapshot_task = _find_snapshot_task(task_id)
        if snapshot_task:
            return TaskStatusResponse(
                task_id=snapshot_task["task_id"],
                status=snapshot_task.get("status"),
                option_symbol=snapshot_task.get("option_symbol"),
                monitor_symbol=snapshot_task.get("monitor_symbol", snapshot_task.get("option_symbol")),
                monitor_instrument=snapshot_task.get("monitor_instrument", "option"),
                target_price=snapshot_task.get("target_price"),
                current_price=snapshot_task.get("current_price"),
                created_at=snapshot_task.get("created_at"),
                expires_at=snapshot_task.get("expires_at"),
                triggered_at=snapshot_task.get("triggered_at"),
                webhook_url=snapshot_task.get("webhook_url"),
            )

        monitor_service = await get_monitor_service()
        task = await monitor_service.get_task_status(task_id)

        if not task:
            raise HTTPException(
                status_code=404,
                detail=f"任务 '{task_id}' 不存在"
            )
        
        return TaskStatusResponse(
            task_id=task.task_id,
            status=task.status,
            option_symbol=task.option_info.symbol,
            monitor_symbol=task.monitor_symbol,
            monitor_instrument=task.monitor_instrument,
            target_price=task.target_price,
            current_price=task.current_price,
            created_at=task.created_at.isoformat(),
            expires_at=task.expires_at.isoformat(),
            triggered_at=task.triggered_at.isoformat() if task.triggered_at else None,
            webhook_url=task.webhook_url
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/monitor/{task_id}", response_model=ApiResponse)
async def delete_monitor_task(task_id: str):
    """删除监控任务"""
    try:
        monitor_service = await get_monitor_service()
        
        # 检查任务是否存在
        task = await monitor_service.get_task_status(task_id)
        if not task:
            raise HTTPException(
                status_code=404,
                detail=f"任务 '{task_id}' 不存在"
            )
        
        # 删除任务
        success = await monitor_service.remove_monitor_task(task_id)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail="删除监控任务失败"
            )
        
        logger.info(f"删除监控任务成功: {task_id}")
        
        return ApiResponse(
            success=True,
            message="监控任务删除成功",
            data={"task_id": task_id}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除监控任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/monitor/tasks", response_model=ApiResponse)
async def list_monitor_tasks():
    """获取所有活跃监控任务"""
    try:
        snapshot = _load_active_task_snapshot()
        task_list = snapshot.get("tasks", [])
        message = f"当前有 {len(task_list)} 个活跃监控任务"
        if snapshot.get("updated_at"):
            message += f"，最近更新时间 {snapshot['updated_at']}"

        return ApiResponse(
            success=True,
            message=message,
            data={
                "tasks": task_list,
                "updated_at": snapshot.get("updated_at"),
            }
        )

    except Exception as e:
        logger.error(f"获取监控任务列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def _parse_option_symbol(symbol: str) -> OptionInfo:
    """解析期权合约符号"""
    parts = symbol.split('-')
    base_coin = parts[0]
    expiry = parts[1]
    strike = parts[2]
    option_type = parts[3]
    
    # 处理期权类型
    if option_type in ['C', 'Call']:
        opt_type = "Call"
    elif option_type in ['P', 'Put']:
        opt_type = "Put"
    else:
        opt_type = option_type
    
    return OptionInfo(
        symbol=symbol,
        base_coin=base_coin,
        strike_price=float(strike),
        expiry_date=expiry,
        option_type=opt_type
    )

# 错误处理
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """HTTP异常处理"""
    return {
        "success": False,
        "message": exc.detail,
        "status_code": exc.status_code
    }

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """通用异常处理"""
    logger.error(f"未处理的异常: {exc}")
    return {
        "success": False,
        "message": "服务器内部错误",
        "status_code": 500
    }

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "api:app",
        host=MonitorConfig.HOST,
        port=MonitorConfig.PORT,
        reload=MonitorConfig.DEBUG,
        log_level=MonitorConfig.LOG_LEVEL.lower()
    )
