import threading
import queue
import time
from typing import Dict, List, Optional, Callable
from datetime import datetime
import weakref

from logger import ConsoleLogger


class ThreadPoolManager:
    def __init__(self, max_workers: int = 10, logger: Optional[ConsoleLogger] = None):
        self.max_workers = max_workers
        self.logger = logger
        self.threads = []
        self.lock = threading.Lock()
        self.is_shutdown = False

    def submit(self, target: Callable, args: tuple = (), kwargs: dict = None, daemon: bool = True) -> threading.Thread:
        if self.is_shutdown:
            if self.logger:
                self.logger.warning('线程池已关闭，无法提交新任务')
            return None
        
        if kwargs is None:
            kwargs = {}
        
        thread = threading.Thread(target=target, args=args, kwargs=kwargs, daemon=daemon)
        
        with self.lock:
            self.threads.append(thread)
        
        thread.start()
        
        if self.logger:
            self.logger.debug(f'创建新线程: {thread.name}, 当前线程数: {len(self.threads)}')
        
        return thread

    def shutdown(self, wait: bool = True, timeout: float = 5.0):
        self.is_shutdown = True
        
        if self.logger:
            self.logger.info(f'开始关闭线程池，当前线程数: {len(self.threads)}')
        
        if wait:
            self.join_all(timeout)
        
        with self.lock:
            self.threads.clear()

    def join_all(self, timeout: float = 5.0):
        with self.lock:
            threads = self.threads.copy()
        
        for thread in threads:
            if thread.is_alive():
                thread.join(timeout=timeout)
                if thread.is_alive():
                    if self.logger:
                        self.logger.warning(f'线程 {thread.name} 未在{timeout}秒内停止')

    def get_active_count(self) -> int:
        with self.lock:
            return sum(1 for t in self.threads if t.is_alive())


class ThreadSafeDict:
    def __init__(self, max_size: int = 1000, logger: Optional[ConsoleLogger] = None):
        self.data = {}
        self.lock = threading.RLock()
        self.max_size = max_size
        self.logger = logger

    def set(self, key: str, value):
        with self.lock:
            self.data[key] = value
            
            if len(self.data) > self.max_size:
                oldest_key = next(iter(self.data))
                del self.data[oldest_key]
                if self.logger:
                    self.logger.debug(f'数据字典超出最大大小，删除最旧数据: {oldest_key}')

    def get(self, key: str, default=None):
        with self.lock:
            return self.data.get(key, default)

    def pop(self, key: str, default=None):
        with self.lock:
            return self.data.pop(key, default)

    def clear(self):
        with self.lock:
            self.data.clear()

    def items(self):
        with self.lock:
            return self.data.items()

    def __len__(self):
        with self.lock:
            return len(self.data)


class ThreadSafeList:
    def __init__(self, max_size: int = 1000, logger: Optional[ConsoleLogger] = None):
        self.data = []
        self.lock = threading.RLock()
        self.max_size = max_size
        self.logger = logger

    def append(self, item):
        with self.lock:
            self.data.append(item)
            
            if len(self.data) > self.max_size:
                removed = self.data.pop(0)
                if self.logger:
                    self.logger.debug(f'列表超出最大大小，删除最旧数据')

    def extend(self, items):
        with self.lock:
            self.data.extend(items)
            
            if len(self.data) > self.max_size:
                remove_count = len(self.data) - self.max_size
                self.data = self.data[remove_count:]
                if self.logger:
                    self.logger.debug(f'列表超出最大大小，删除{remove_count}条最旧数据')

    def get_all(self):
        with self.lock:
            return self.data.copy()

    def clear(self):
        with self.lock:
            self.data.clear()

    def __len__(self):
        with self.lock:
            return len(self.data)


class CircularBuffer:
    def __init__(self, size: int = 100, logger: Optional[ConsoleLogger] = None):
        self.size = size
        self.buffer = []
        self.lock = threading.RLock()
        self.logger = logger

    def append(self, item):
        with self.lock:
            self.buffer.append(item)
            
            if len(self.buffer) > self.size:
                self.buffer.pop(0)

    def get_all(self):
        with self.lock:
            return self.buffer.copy()

    def get_latest(self, count: int = 1):
        with self.lock:
            if count >= len(self.buffer):
                return self.buffer.copy()
            return self.buffer[-count:]

    def clear(self):
        with self.lock:
            self.buffer.clear()

    def __len__(self):
        with self.lock:
            return len(self.buffer)


class ResourceCleaner:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self.resources = weakref.WeakSet()
        self.logger = None

    def register(self, resource: object):
        self.resources.add(resource)
        if self.logger:
            self.logger.debug(f'注册资源: {type(resource).__name__}')

    def unregister(self, resource: object):
        self.resources.discard(resource)
        if self.logger:
            self.logger.debug(f'注销资源: {type(resource).__name__}')

    def cleanup_all(self):
        if self.logger:
            self.logger.info(f'开始清理所有资源，共{len(self.resources)}个')
        
        for resource in list(self.resources):
            try:
                if hasattr(resource, 'close'):
                    resource.close()
                elif hasattr(resource, 'cleanup'):
                    resource.cleanup()
                elif hasattr(resource, 'stop'):
                    resource.stop()
                elif hasattr(resource, 'shutdown'):
                    resource.shutdown()
                
                if self.logger:
                    self.logger.debug(f'清理资源: {type(resource).__name__}')
            except Exception as e:
                if self.logger:
                    self.logger.error(f'清理资源失败 {type(resource).__name__}: {e}')

    def set_logger(self, logger: ConsoleLogger):
        self.logger = logger


class MemoryMonitor:
    def __init__(self, logger: Optional[ConsoleLogger] = None):
        self.logger = logger
        self.check_interval = 60
        self.monitor_thread = None
        self.is_running = False
        self.callbacks = []

    def add_callback(self, callback: Callable[[float, float], None]):
        self.callbacks.append(callback)

    def start(self):
        if self.is_running:
            return
        
        self.is_running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        if self.logger:
            self.logger.info('内存监控已启动')

    def stop(self):
        self.is_running = False
        
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        if self.logger:
            self.logger.info('内存监控已停止')

    def _monitor_loop(self):
        import psutil
        import gc
        
        while self.is_running:
            try:
                process = psutil.Process()
                memory_info = process.memory_info()
                
                rss = memory_info.rss / 1024 / 1024
                vms = memory_info.vms / 1024 / 1024
                
                if self.logger:
                    self.logger.debug(f'内存使用: RSS={rss:.2f}MB, VMS={vms:.2f}MB')
                
                for callback in self.callbacks:
                    try:
                        callback(rss, vms)
                    except Exception as e:
                        if self.logger:
                            self.logger.error(f'内存监控回调失败: {e}')
                
                if rss > 500:
                    gc.collect()
                    if self.logger:
                        self.logger.warning(f'内存使用过高({rss:.2f}MB)，执行垃圾回收')
                
                time.sleep(self.check_interval)
            
            except Exception as e:
                if self.logger:
                    self.logger.error(f'内存监控异常: {e}')
                time.sleep(self.check_interval)
