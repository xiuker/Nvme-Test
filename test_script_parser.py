import configparser
from typing import List, Dict, Optional, Tuple
from logger import ConsoleLogger


class TestCommand:
    def __init__(self, command_type: str, params: Dict):
        self.command_type = command_type
        self.params = params

    def __repr__(self):
        return f'TestCommand({self.command_type}, {self.params})'


class TestScriptParser:
    def __init__(self, logger: Optional[ConsoleLogger] = None):
        self.logger = logger
        self.commands = []

    def parse_script(self, script_path: str) -> List[TestCommand]:
        self.commands = []
        
        try:
            with open(script_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                
                if not line or line.startswith('#'):
                    continue
                
                try:
                    command = self._parse_line(line)
                    if command:
                        self.commands.append(command)
                        if self.logger:
                            self.logger.debug(f'解析命令成功 [行{line_num}]: {command}')
                except Exception as e:
                    if self.logger:
                        self.logger.error(f'解析命令失败 [行{line_num}]: {line}, 错误: {e}')
            
            if self.logger:
                self.logger.info(f'测试脚本解析完成，共解析{len(self.commands)}条命令')
            return self.commands
        
        except Exception as e:
            if self.logger:
                self.logger.error(f'读取测试脚本失败: {e}')
            return []

    def _parse_line(self, line: str) -> Optional[TestCommand]:
        parts = line.split()
        
        if not parts:
            return None
        
        command_type = parts[0].upper()
        
        if command_type == 'TEMP':
            if len(parts) >= 3:
                temperature = float(parts[1])
                hold_time = int(parts[2])
                return TestCommand('TEMP', {'temperature': temperature, 'hold_time': hold_time})
        
        elif command_type == 'PCT':
            if len(parts) >= 2:
                cycles = int(parts[1])
                return TestCommand('PCT', {'cycles': cycles})
            else:
                return TestCommand('PCT', {'cycles': 1})
        
        elif command_type == 'BIT':
            if len(parts) >= 2:
                capacity_percent = int(parts[1])
                if 1 <= capacity_percent <= 100:
                    return TestCommand('BIT', {'capacity_percent': capacity_percent})
                else:
                    raise ValueError('BIT测试容量百分比必须在1-100之间')
            else:
                return TestCommand('BIT', {'capacity_percent': 100})
        
        elif command_type == 'CTTW':
            return TestCommand('CTTW', {})
        
        elif command_type == 'CTTR':
            return TestCommand('CTTR', {})
        
        else:
            raise ValueError(f'未知命令类型: {command_type}')
        
        return None

    def get_commands(self) -> List[TestCommand]:
        return self.commands

    def validate_script(self, script_path: str) -> Tuple[bool, List[str]]:
        errors = []
        
        try:
            commands = self.parse_script(script_path)
            
            if not commands:
                errors.append('测试脚本为空或解析失败')
                return False, errors
            
            for i, command in enumerate(commands):
                if command.command_type == 'TEMP':
                    temp = command.params.get('temperature')
                    if temp < -50 or temp > 100:
                        errors.append(f'第{i+1}条命令: 温度{temp}超出合理范围(-50~100)')
                
                elif command.command_type == 'BIT':
                    capacity = command.params.get('capacity_percent', 100)
                    if capacity < 1 or capacity > 100:
                        errors.append(f'第{i+1}条命令: BIT容量百分比{capacity}超出范围(1-100)')
            
            if errors:
                return False, errors
            
            if self.logger:
                self.logger.info('测试脚本验证通过')
            return True, []
        
        except Exception as e:
            errors.append(f'验证测试脚本时发生错误: {e}')
            return False, errors


class TestConfigParser:
    def __init__(self, config_path: str = './config.ini', logger: Optional[ConsoleLogger] = None):
        self.config_path = config_path
        self.logger = logger
        self.config = None
        self._load_config()

    def _load_config(self):
        self.config = configparser.ConfigParser()
        try:
            self.config.read(self.config_path, encoding='utf-8')
            if self.logger:
                self.logger.info(f'配置文件加载成功: {self.config_path}')
        except Exception as e:
            if self.logger:
                self.logger.error(f'配置文件加载失败: {e}')
            raise

    def get_serial_config(self) -> Dict:
        return {
            'port': self.config.get('serial', 'port', fallback='COM1'),
            'baudrate': self.config.getint('serial', 'baudrate', fallback=2400),
            'bytesize': self.config.getint('serial', 'bytesize', fallback=8),
            'parity': self.config.get('serial', 'parity', fallback='N'),
            'stopbits': self.config.getint('serial', 'stopbits', fallback=1),
            'timeout': self.config.getint('serial', 'timeout', fallback=2)
        }

    def get_chamber_config(self) -> Dict:
        return {
            'command_set': self.config.getint('chamber', 'command_set', fallback=1),
            'wait_time_after_start': self.config.getint('chamber', 'wait_time_after_start', fallback=300),
            'wait_time_after_stop': self.config.getint('chamber', 'wait_time_after_stop', fallback=60)
        }

    def get_test_hosts_config(self) -> List[Dict]:
        hosts = []
        test_hosts_section = self.config['test_hosts']
        
        for key in test_hosts_section:
            if key.endswith('_ip'):
                host_num = key.split('_')[0]
                ip = test_hosts_section.get(key)
                mac = test_hosts_section.get(f'{host_num}_mac', '')
                name = test_hosts_section.get(f'{host_num}_name', f'host_{host_num}')
                
                if ip and mac:
                    hosts.append({
                        'ip': ip,
                        'mac': mac,
                        'name': name
                    })
        
        return hosts

    def get_ssh_config(self) -> Dict:
        return {
            'username': self.config.get('ssh', 'username', fallback='root'),
            'password': self.config.get('ssh', 'password', fallback='1'),
            'port': self.config.getint('ssh', 'port', fallback=22),
            'connect_timeout': self.config.getint('ssh', 'connect_timeout', fallback=30),
            'command_timeout': self.config.getint('ssh', 'command_timeout', fallback=300)
        }

    def get_pct_config(self) -> Dict:
        return {
            'wait_time_after_wol': self.config.getint('pct', 'wait_time_after_wol', fallback=40),
            'wait_time_after_shutdown': self.config.getint('pct', 'wait_time_after_shutdown', fallback=15),
            'fio_size': self.config.get('pct', 'fio_size', fallback='1G')
        }

    def get_bit_config(self) -> Dict:
        return {
            'temperature_check_interval': self.config.getint('bit', 'temperature_check_interval', fallback=30)
        }

    def get_cttw_config(self) -> Dict:
        return {
            'temperature_check_interval': self.config.getint('cttw', 'temperature_check_interval', fallback=30)
        }

    def get_cttr_config(self) -> Dict:
        return {
            'temperature_check_interval': self.config.getint('cttr', 'temperature_check_interval', fallback=30)
        }

    def get_logging_config(self) -> Dict:
        return {
            'console_log_dir': self.config.get('logging', 'console_log_dir', fallback='./console_log'),
            'test_log_dir': self.config.get('logging', 'test_log_dir', fallback='./nvme_test_log'),
            'max_log_size': self.config.getint('logging', 'max_log_size', fallback=10485760),
            'log_backup_count': self.config.getint('logging', 'log_backup_count', fallback=5)
        }

    def get_analysis_config(self) -> Dict:
        return {
            'max_temperature': self.config.getint('analysis', 'max_temperature', fallback=85),
            'min_temperature': self.config.getint('analysis', 'min_temperature', fallback=-45)
        }

    def reload_config(self):
        self._load_config()
