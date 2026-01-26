import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Optional


class ConsoleLogger:
    def __init__(self, log_dir: str = './console_log', max_log_size: int = 10485760, backup_count: int = 5):
        self.log_dir = log_dir
        self.max_log_size = max_log_size
        self.backup_count = backup_count
        self.logger = None
        self._setup_logger()

    def _setup_logger(self):
        os.makedirs(self.log_dir, exist_ok=True)
        
        self.logger = logging.getLogger('nvme_test_console')
        self.logger.setLevel(logging.DEBUG)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        log_file = os.path.join(self.log_dir, 'log.txt')
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=self.max_log_size,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def debug(self, message: str):
        self.logger.debug(message)

    def info(self, message: str):
        self.logger.info(message)

    def warning(self, message: str):
        self.logger.warning(message)

    def error(self, message: str):
        self.logger.error(message)

    def critical(self, message: str):
        self.logger.critical(message)


class TestResultLogger:
    def __init__(self, log_dir: str = './nvme_test_log'):
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)

    def _get_test_time(self) -> str:
        return datetime.now().strftime('%Y%m%d_%H%M%S')

    def _create_test_log_path(self, ssd_sn: str, test_time: str) -> str:
        test_path = os.path.join(self.log_dir, test_time, ssd_sn)
        os.makedirs(test_path, exist_ok=True)
        return test_path

    def _generate_filename(self, test_time: str, ssd_sn: str, test_item: str, temperature: float) -> str:
        return f'{test_time}-{ssd_sn}-{test_item}-{temperature}C.txt'

    def log_test_result(self, ssd_sn: str, test_item: str, temperature: float, content: str, test_time: Optional[str] = None, append: bool = False, custom_filename: Optional[str] = None):
        if test_time is None:
            test_time = self._get_test_time()
        
        test_path = self._create_test_log_path(ssd_sn, test_time)
        
        if custom_filename:
            filename = custom_filename
        else:
            file_time = self._get_test_time()
            filename = self._generate_filename(file_time, ssd_sn, test_item, temperature)
        filepath = os.path.join(test_path, filename)
        
        mode = 'a' if append else 'w'
        with open(filepath, mode, encoding='utf-8') as f:
            f.write(content)

    def log_ssd_info(self, ssd_sn: str, ssd_info: dict, test_time: Optional[str] = None):
        if test_time is None:
            test_time = self._get_test_time()
        
        test_path = self._create_test_log_path(ssd_sn, test_time)
        filename = f'{test_time}-{ssd_sn}-info.txt'
        filepath = os.path.join(test_path, filename)
        
        content = 'SSD基本信息:\n'
        for key, value in ssd_info.items():
            content += f'{key}: {value}\n'
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

    def log_smart_info(self, ssd_sn: str, smart_info: str, test_time: Optional[str] = None):
        if test_time is None:
            test_time = self._get_test_time()
        
        test_path = self._create_test_log_path(ssd_sn, test_time)
        filename = f'{test_time}-{ssd_sn}-smart.txt'
        filepath = os.path.join(test_path, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(smart_info)

    def log_temperature_data(self, ssd_sn: str, temperature_data: list, test_time: Optional[str] = None):
        if test_time is None:
            test_time = self._get_test_time()
        
        test_path = self._create_test_log_path(ssd_sn, test_time)
        filename = f'{test_time}-{ssd_sn}-temperature.txt'
        filepath = os.path.join(test_path, filename)
        
        content = '温度监控数据:\n'
        for data in temperature_data:
            content += f'{data}\n'
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

    def log_temperature_monitor_data(self, ssd_sn: str, monitor_data: list, test_time: Optional[str] = None):
        if test_time is None:
            test_time = self._get_test_time()
        
        test_path = self._create_test_log_path(ssd_sn, test_time)
        filename = f'{test_time}-{ssd_sn}-temperature-monitor.txt'
        filepath = os.path.join(test_path, filename)
        
        content = '温度监控记录（每30秒一次）:\n'
        content += f'{"="*60}\n'
        for data in monitor_data:
            content += f'{data}\n'
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

    def log_error(self, ssd_sn: str, error_type: str, error_message: str, test_time: Optional[str] = None, 
                 test_item: Optional[str] = None, temperature: Optional[float] = None, cycle: Optional[int] = None):
        if test_time is None:
            test_time = self._get_test_time()
        
        test_path = self._create_test_log_path(ssd_sn, test_time)
        filename = f'{test_time}-{ssd_sn}-error.txt'
        filepath = os.path.join(test_path, filename)
        
        content = f'{"="*60}\n'
        content += f'错误记录\n'
        content += f'{"="*60}\n'
        content += f'测试时间: {test_time}\n'
        content += f'错误时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n'
        if test_item:
            content += f'测试项: {test_item}\n'
        if temperature is not None:
            content += f'测试温度: {temperature}°C\n'
        if cycle is not None:
            content += f'测试轮次: 第{cycle}轮\n'
        content += f'SSD SN: {ssd_sn}\n'
        content += f'错误类型: {error_type}\n'
        content += f'{"="*60}\n'
        content += f'错误信息:\n{error_message}\n'
        content += f'{"="*60}\n'
        
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(content + '\n\n')
