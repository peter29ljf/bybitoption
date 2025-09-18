#!/usr/bin/env python3
"""
期权价格监控服务启动脚本
"""
import asyncio
import logging
import signal
import sys
from .api import app
from .config import MonitorConfig

def setup_logging():
    """设置日志"""
    logging.basicConfig(
        level=getattr(logging, MonitorConfig.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(MonitorConfig.LOG_FILE),
            logging.StreamHandler()
        ]
    )

def signal_handler(signum, frame):
    """信号处理器"""
    logger = logging.getLogger(__name__)
    logger.info(f"接收到信号 {signum}，正在关闭服务...")
    sys.exit(0)

def main():
    """主函数"""
    # 设置日志
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("=" * 50)
    logger.info("期权价格监控服务")
    logger.info("=" * 50)
    logger.info(f"服务地址: http://{MonitorConfig.HOST}:{MonitorConfig.PORT}")
    logger.info(f"WebSocket: {MonitorConfig.WS_URL}")
    logger.info(f"最大任务数: {MonitorConfig.MAX_TASKS}")
    logger.info(f"Redis支持: {'是' if MonitorConfig.USE_REDIS else '否'}")
    logger.info(f"调试模式: {'是' if MonitorConfig.DEBUG else '否'}")
    logger.info("=" * 50)
    
    try:
        import uvicorn
        
        # 启动服务
        uvicorn.run(
            app,
            host=MonitorConfig.HOST,
            port=MonitorConfig.PORT,
            reload=MonitorConfig.DEBUG,
            log_level=MonitorConfig.LOG_LEVEL.lower(),
            access_log=True
        )
        
    except KeyboardInterrupt:
        logger.info("服务被用户中断")
    except Exception as e:
        logger.error(f"服务启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()


