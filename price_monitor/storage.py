"""
任务存储管理
"""
import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from datetime import datetime
from .models import MonitorTask
from .config import MonitorConfig

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)

class TaskStorage(ABC):
    """任务存储抽象基类"""
    
    @abstractmethod
    def save_task(self, task: MonitorTask) -> bool:
        """保存任务"""
        pass
    
    @abstractmethod
    def get_task(self, task_id: str) -> Optional[MonitorTask]:
        """获取任务"""
        pass
    
    @abstractmethod
    def get_all_active_tasks(self) -> List[MonitorTask]:
        """获取所有活跃任务"""
        pass
    
    @abstractmethod
    def update_task_status(self, task_id: str, status: str, triggered_at: Optional[datetime] = None) -> bool:
        """更新任务状态"""
        pass
    
    @abstractmethod
    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        pass

class MemoryStorage(TaskStorage):
    """内存存储实现"""
    
    def __init__(self):
        self.tasks: Dict[str, MonitorTask] = {}
        logger.info("使用内存存储")
    
    def save_task(self, task: MonitorTask) -> bool:
        """保存任务到内存"""
        try:
            self.tasks[task.task_id] = task
            logger.info(f"任务 {task.task_id} 已保存到内存")
            return True
        except Exception as e:
            logger.error(f"保存任务失败: {e}")
            return False
    
    def get_task(self, task_id: str) -> Optional[MonitorTask]:
        """从内存获取任务"""
        return self.tasks.get(task_id)
    
    def get_all_active_tasks(self) -> List[MonitorTask]:
        """获取所有活跃任务"""
        return [task for task in self.tasks.values() if task.status == "active"]
    
    def update_task_status(self, task_id: str, status: str, triggered_at: Optional[datetime] = None) -> bool:
        """更新任务状态"""
        try:
            if task_id in self.tasks:
                self.tasks[task_id].status = status
                if triggered_at:
                    self.tasks[task_id].triggered_at = triggered_at
                logger.info(f"任务 {task_id} 状态更新为 {status}")
                return True
            return False
        except Exception as e:
            logger.error(f"更新任务状态失败: {e}")
            return False
    
    def delete_task(self, task_id: str) -> bool:
        """从内存删除任务"""
        try:
            if task_id in self.tasks:
                del self.tasks[task_id]
                logger.info(f"任务 {task_id} 已从内存删除")
                return True
            return False
        except Exception as e:
            logger.error(f"删除任务失败: {e}")
            return False

class RedisStorage(TaskStorage):
    """Redis存储实现"""
    
    def __init__(self, redis_url: str = None):
        if not REDIS_AVAILABLE:
            raise ImportError("Redis 未安装，请安装 redis 包")
        
        self.redis_url = redis_url or MonitorConfig.REDIS_URL
        self.redis_client = redis.from_url(self.redis_url)
        self.task_prefix = "monitor_task:"
        self.active_tasks_set = "active_tasks"
        
        # 测试连接
        try:
            self.redis_client.ping()
            logger.info(f"Redis连接成功: {self.redis_url}")
        except Exception as e:
            logger.error(f"Redis连接失败: {e}")
            raise
    
    def save_task(self, task: MonitorTask) -> bool:
        """保存任务到Redis"""
        try:
            key = f"{self.task_prefix}{task.task_id}"
            task_data = json.dumps(task.to_dict())
            
            # 保存任务数据
            self.redis_client.set(key, task_data)
            
            # 如果是活跃任务，加入活跃任务集合
            if task.status == "active":
                self.redis_client.sadd(self.active_tasks_set, task.task_id)
            
            logger.info(f"任务 {task.task_id} 已保存到Redis")
            return True
        except Exception as e:
            logger.error(f"保存任务到Redis失败: {e}")
            return False
    
    def get_task(self, task_id: str) -> Optional[MonitorTask]:
        """从Redis获取任务"""
        try:
            key = f"{self.task_prefix}{task_id}"
            task_data = self.redis_client.get(key)
            
            if task_data:
                data = json.loads(task_data.decode('utf-8'))
                return MonitorTask.from_dict(data)
            
            return None
        except Exception as e:
            logger.error(f"从Redis获取任务失败: {e}")
            return None
    
    def get_all_active_tasks(self) -> List[MonitorTask]:
        """获取所有活跃任务"""
        try:
            active_task_ids = self.redis_client.smembers(self.active_tasks_set)
            tasks = []
            
            for task_id in active_task_ids:
                task = self.get_task(task_id.decode('utf-8'))
                if task and task.status == "active":
                    tasks.append(task)
                elif task and task.status != "active":
                    # 清理不一致的数据
                    self.redis_client.srem(self.active_tasks_set, task_id)
            
            return tasks
        except Exception as e:
            logger.error(f"获取活跃任务失败: {e}")
            return []
    
    def update_task_status(self, task_id: str, status: str, triggered_at: Optional[datetime] = None) -> bool:
        """更新任务状态"""
        try:
            task = self.get_task(task_id)
            if not task:
                return False
            
            task.status = status
            if triggered_at:
                task.triggered_at = triggered_at
            
            # 保存更新后的任务
            self.save_task(task)
            
            # 如果状态不再是active，从活跃任务集合中移除
            if status != "active":
                self.redis_client.srem(self.active_tasks_set, task_id)
            
            logger.info(f"任务 {task_id} 状态更新为 {status}")
            return True
        except Exception as e:
            logger.error(f"更新任务状态失败: {e}")
            return False
    
    def delete_task(self, task_id: str) -> bool:
        """从Redis删除任务"""
        try:
            key = f"{self.task_prefix}{task_id}"
            
            # 删除任务数据
            self.redis_client.delete(key)
            
            # 从活跃任务集合中移除
            self.redis_client.srem(self.active_tasks_set, task_id)
            
            logger.info(f"任务 {task_id} 已从Redis删除")
            return True
        except Exception as e:
            logger.error(f"从Redis删除任务失败: {e}")
            return False

def get_storage() -> TaskStorage:
    """获取存储实例"""
    if MonitorConfig.USE_REDIS and REDIS_AVAILABLE:
        try:
            return RedisStorage()
        except Exception as e:
            logger.warning(f"Redis初始化失败，使用内存存储: {e}")
            return MemoryStorage()
    else:
        return MemoryStorage()


