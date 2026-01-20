# 多线程和内存管理说明

## 概述

NVMe SSD测试系统已经实现了完善的多线程管理和内存管理机制，确保程序在Windows系统上稳定运行，防止内存溢出，并在程序关闭时正确处理所有多线程任务。

## 新增模块

### thread_manager.py

新增的线程管理模块，包含以下核心类：

#### 1. ThreadPoolManager - 线程池管理器

**功能**：
- 统一管理所有线程的创建和销毁
- 限制最大线程数量，防止线程过多导致资源耗尽
- 提供优雅的关闭机制
- 跟踪所有活跃线程

**主要方法**：
```python
# 提交新任务
submit(target, args=(), kwargs=None, daemon=True) -> threading.Thread

# 关闭线程池
shutdown(wait=True, timeout=5.0)

# 等待所有线程完成
join_all(timeout=5.0)

# 获取活跃线程数
get_active_count() -> int
```

**使用示例**：
```python
# 创建线程池
thread_pool = ThreadPoolManager(max_workers=20, logger=console_logger)

# 提交任务
test_thread = thread_pool.submit(self._run_test)

# 程序退出时清理
thread_pool.shutdown(wait=True, timeout=5)
```

#### 2. ThreadSafeDict - 线程安全字典

**功能**：
- 提供线程安全的字典操作
- 自动限制最大大小，防止内存溢出
- 超出限制时自动删除最旧数据

**主要方法**：
```python
set(key, value)           # 设置键值对
get(key, default=None)   # 获取值
pop(key, default=None)    # 删除并返回值
clear()                   # 清空字典
items()                   # 获取所有项
```

**使用示例**：
```python
# 创建线程安全字典，最大1000条记录
safe_dict = ThreadSafeDict(max_size=1000, logger=console_logger)

# 线程安全地设置值
safe_dict.set('temperature', 25.5)

# 线程安全地获取值
temp = safe_dict.get('temperature')
```

#### 3. ThreadSafeList - 线程安全列表

**功能**：
- 提供线程安全的列表操作
- 自动限制最大大小，防止内存溢出
- 超出限制时自动删除最旧数据

**主要方法**：
```python
append(item)        # 添加元素
extend(items)       # 批量添加元素
get_all()          # 获取所有元素的副本
clear()             # 清空列表
```

**使用示例**：
```python
# 创建线程安全列表，最大1000条记录
safe_list = ThreadSafeList(max_size=1000, logger=console_logger)

# 线程安全地添加元素
safe_list.append('log message')

# 线程安全地批量添加
safe_list.extend(['msg1', 'msg2', 'msg3'])
```

#### 4. CircularBuffer - 循环缓冲区

**功能**：
- 固定大小的循环缓冲区
- 超出限制时自动覆盖最旧数据
- 适合存储实时监控数据

**主要方法**：
```python
append(item)              # 添加元素
get_all()                # 获取所有元素
get_latest(count=1)       # 获取最新的N个元素
clear()                   # 清空缓冲区
```

**使用示例**：
```python
# 创建100个元素的循环缓冲区
buffer = CircularBuffer(size=100, logger=console_logger)

# 添加温度数据
buffer.append(25.5)

# 获取最新的10个温度值
latest_temps = buffer.get_latest(10)
```

#### 5. ResourceCleaner - 资源清理器（单例模式）

**功能**：
- 使用弱引用跟踪所有资源
- 程序退出时自动清理所有资源
- 支持多种清理方法（close、cleanup、stop、shutdown）

**主要方法**：
```python
register(resource)        # 注册资源
unregister(resource)      # 注销资源
cleanup_all()            # 清理所有资源
set_logger(logger)       # 设置日志记录器
```

**使用示例**：
```python
# 获取资源清理器实例
cleaner = ResourceCleaner()
cleaner.set_logger(console_logger)

# 注册资源
cleaner.register(chamber_controller)
cleaner.register(host_manager)

# 程序退出时清理所有资源
cleaner.cleanup_all()
```

#### 6. MemoryMonitor - 内存监控器

**功能**：
- 实时监控程序内存使用情况
- 内存使用过高时自动执行垃圾回收
- 支持回调机制，自定义内存监控逻辑

**主要方法**：
```python
start()                                    # 启动监控
stop()                                     # 停止监控
add_callback(callback)                       # 添加回调函数
```

**回调函数签名**：
```python
def memory_callback(rss: float, vms: float) -> None:
    """
    rss: 实际物理内存使用量（MB）
    vms: 虚拟内存使用量（MB）
    """
    pass
```

**使用示例**：
```python
# 创建内存监控器
monitor = MemoryMonitor(logger=console_logger)

# 添加回调函数
def on_memory_high(rss, vms):
    if rss > 500:
        print(f'内存使用过高: {rss}MB')

monitor.add_callback(on_memory_high)

# 启动监控
monitor.start()

# 程序退出时停止
monitor.stop()
```

## 主程序改进（main.py）

### 1. 初始化改进

**新增内容**：
```python
# 创建线程池管理器
self.thread_pool = ThreadPoolManager(max_workers=20, logger=self.console_logger)

# 创建资源清理器
self.resource_cleaner = ResourceCleaner()
self.resource_cleaner.set_logger(self.console_logger)

# 创建内存监控器
self.memory_monitor = MemoryMonitor(logger=self.console_logger)

# 设置信号处理器
self._setup_signal_handlers()

# 设置退出处理器
self._setup_exit_handlers()

# 启动内存监控
self.memory_monitor.start()
```

### 2. 信号处理

**新增方法**：
```python
def _setup_signal_handlers(self):
    # 处理Ctrl+C（SIGINT）
    signal.signal(signal.SIGINT, self._signal_handler)
    
    # 处理终止信号（SIGTERM）
    signal.signal(signal.SIGTERM, self._signal_handler)

def _signal_handler(self, signum, frame):
    # 收到信号时执行清理
    self.console_logger.info(f'收到信号 {signum}，准备退出...')
    self._cleanup()
    sys.exit(0)
```

### 3. 退出处理

**新增方法**：
```python
def _setup_exit_handlers(self):
    # 注册atexit回调，确保程序退出时清理
    atexit.register(self._cleanup_on_exit)

def _cleanup_on_exit(self):
    self.console_logger.info('程序退出，执行清理...')
    self._cleanup()
```

### 4. 资源清理

**新增方法**：
```python
def _cleanup(self):
    try:
        # 1. 停止测试线程
        if self.test_thread and self.test_thread.is_alive():
            if self.test_executor:
                self.test_executor.stop_test()
            self.test_thread.join(timeout=5)
        
        # 2. 停止监控线程
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.is_monitoring = False
            self.monitor_thread.join(timeout=5)
        
        # 3. 停止实时监控
        if self.real_time_monitor:
            self.real_time_monitor.stop_monitoring()
        
        # 4. 停止内存监控
        if self.memory_monitor:
            self.memory_monitor.stop()
        
        # 5. 关闭线程池
        if self.thread_pool:
            self.thread_pool.shutdown(wait=True, timeout=5)
        
        # 6. 清理所有资源
        if self.resource_cleaner:
            self.resource_cleaner.cleanup_all()
        
        # 7. 关闭温箱串口
        if self.chamber_controller:
            self.chamber_controller.close()
        
        # 8. 断开所有SSH连接
        if self.host_manager:
            self.host_manager.disconnect_all_hosts()
        
        self.console_logger.info('资源清理完成')
    
    except Exception as e:
        self.console_logger.error(f'清理资源时发生错误: {e}')
```

### 5. 线程创建改进

**修改前**：
```python
self.test_thread = threading.Thread(target=self._run_test, daemon=True)
self.test_thread.start()
```

**修改后**：
```python
self.test_thread = self.thread_pool.submit(self._run_test)

if not self.test_thread:
    self._log_to_monitor('创建测试线程失败', 'error')
    return
```

**优势**：
- 统一管理所有线程
- 限制最大线程数量
- 自动清理僵尸线程

## 内存管理策略

### 1. 数据结构限制

**ThreadSafeDict**：
- 默认最大1000条记录
- 超出时自动删除最旧数据
- 防止字典无限增长

**ThreadSafeList**：
- 默认最大1000条记录
- 超出时自动删除最旧数据
- 防止列表无限增长

**CircularBuffer**：
- 固定大小（如100个元素）
- 超出时自动覆盖最旧数据
- 适合实时监控数据

### 2. 内存监控

**监控内容**：
- RSS（实际物理内存使用量）
- VMS（虚拟内存使用量）

**监控策略**：
- 每60秒检查一次内存使用
- 内存超过500MB时自动执行垃圾回收
- 记录内存使用日志

**垃圾回收触发条件**：
```python
if rss > 500:  # 超过500MB
    gc.collect()  # 执行垃圾回收
```

### 3. 线程数量限制

**ThreadPoolManager**：
- 最大20个工作线程
- 防止创建过多线程
- 线程池关闭时拒绝新任务

## 程序关闭流程

### 正常关闭

1. 用户点击窗口关闭按钮
2. PySimpleGUI触发 `sg.WIN_CLOSED` 事件
3. 执行 `self.window.close()`
4. atexit机制触发 `_cleanup_on_exit()`
5. 执行 `_cleanup()` 清理所有资源
6. 记录日志：`NVMe SSD测试系统关闭`

### 异常关闭（Ctrl+C）

1. 用户按下Ctrl+C
2. 操作系统发送 `SIGINT` 信号
3. 信号处理器 `_signal_handler()` 被调用
4. 执行 `_cleanup()` 清理所有资源
5. 调用 `sys.exit(0)` 退出程序

### 强制关闭（任务管理器）

1. 用户通过任务管理器强制关闭
2. 操作系统发送 `SIGTERM` 信号
3. 信号处理器 `_signal_handler()` 被调用
4. 执行 `_cleanup()` 清理所有资源
5. 调用 `sys.exit(0)` 退出程序

## 资源清理顺序

1. **测试线程**：停止测试执行，等待线程结束（最多5秒）
2. **监控线程**：设置停止标志，等待线程结束（最多5秒）
3. **实时监控**：停止温度和进度监控
4. **内存监控**：停止内存监控线程
5. **线程池**：关闭线程池，等待所有线程结束（最多5秒）
6. **资源清理器**：清理所有注册的资源
7. **温箱串口**：关闭串口连接
8. **SSH连接**：断开所有测试主机的SSH连接

## 依赖更新

**新增依赖**：
```
psutil==5.9.0
```

**psutil用途**：
- 获取进程内存信息
- 监控RSS和VMS内存使用量
- 跨平台支持（Windows/Linux/Mac）

## 测试建议

### 1. 内存泄漏测试

**测试方法**：
```python
# 长时间运行测试
for i in range(1000):
    # 执行各种操作
    # 检查内存使用
    pass
```

**检查点**：
- 内存使用是否持续增长
- 垃圾回收是否有效
- 数据结构是否自动清理

### 2. 线程清理测试

**测试方法**：
```python
# 快速启动和停止测试
for i in range(10):
    start_test()
    time.sleep(5)
    stop_test()
```

**检查点**：
- 线程是否正确停止
- 是否有僵尸线程
- 资源是否正确释放

### 3. 异常退出测试

**测试方法**：
1. 运行测试
2. 按Ctrl+C强制退出
3. 检查日志

**检查点**：
- 是否记录退出日志
- 资源是否正确清理
- 是否有异常信息

## 最佳实践

### 1. 使用线程池

**推荐做法**：
```python
# 使用线程池管理所有线程
thread = self.thread_pool.submit(target_function)
```

**不推荐做法**：
```python
# 直接创建线程，难以管理
thread = threading.Thread(target=target_function)
thread.start()
```

### 2. 使用线程安全数据结构

**推荐做法**：
```python
# 使用线程安全字典
safe_dict = ThreadSafeDict(max_size=1000)
safe_dict.set('key', value)
```

**不推荐做法**：
```python
# 直接使用字典，可能发生竞态条件
data = {}
data['key'] = value
```

### 3. 注册资源

**推荐做法**：
```python
# 注册资源到清理器
cleaner.register(resource)
```

**不推荐做法**：
```python
# 手动管理资源，容易遗漏
# 忘记清理某个资源
```

### 4. 设置超时

**推荐做法**：
```python
# 设置合理的超时时间
thread.join(timeout=5)
```

**不推荐做法**：
```python
# 无限等待，可能永远阻塞
thread.join()
```

## 性能优化

### 1. 减少锁竞争

**策略**：
- 使用RLock代替Lock（允许同一线程多次获取锁）
- 减少锁的持有时间
- 使用线程安全数据结构

### 2. 批量操作

**策略**：
```python
# 批量添加数据
safe_list.extend(items)  # 一次获取锁
```

**不推荐**：
```python
# 逐个添加数据
for item in items:
    safe_list.append(item)  # 多次获取锁
```

### 3. 及时释放资源

**策略**：
- 使用完资源立即释放
- 使用with语句管理资源
- 注册到资源清理器

## 总结

通过以上改进，NVMe SSD测试系统现在具备：

✅ **完善的线程管理**：统一管理所有线程，限制线程数量
✅ **内存监控**：实时监控内存使用，自动垃圾回收
✅ **数据结构限制**：防止数据结构无限增长
✅ **优雅退出**：支持多种退出方式，正确清理资源
✅ **资源清理**：自动清理所有注册的资源
✅ **异常处理**：捕获所有异常，记录详细日志

这些改进确保程序在Windows系统上稳定运行，防止内存溢出，并在程序关闭时正确处理所有多线程任务。
