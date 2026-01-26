import paramiko
import socket
from typing import Tuple, Optional
from logger import ConsoleLogger


class SSHConnectionTester:
    def __init__(self, ip: str, port: int = 22, username: str = 'root', 
                 password: str = '1', timeout: int = 30, 
                 logger: Optional[ConsoleLogger] = None):
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout
        self.logger = logger if logger else self._create_default_logger()
    
    def _create_default_logger(self) -> ConsoleLogger:
        class DefaultLogger:
            def info(self, msg):
                print(f'[INFO] {msg}')
            
            def error(self, msg):
                print(f'[ERROR] {msg}')
            
            def warning(self, msg):
                print(f'[WARNING] {msg}')
        
        return DefaultLogger()
  
    def test_port_open(self) -> Tuple[bool, str]:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((self.ip, self.port))
            sock.close()
            
            if result == 0:
                return True, f'端口{self.port}开放'
            else:
                return False, f'端口{self.port}关闭或被防火墙阻止'
        except socket.timeout:
            return False, f'端口检查超时（2秒）'
        except Exception as e:
            return False, f'端口检查异常: {str(e)}'

    def test_ssh_connection(self) -> Tuple[bool, str]:
        try:
            if self.logger:
                self.logger.info(f'尝试SSH连接: {self.username}@{self.ip}:{self.port}')
                self.logger.info(f'连接参数: 超时={self.timeout}秒')
            
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_client.connect(
                self.ip,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=self.timeout,
                banner_timeout=10
            )
            
            if self.logger:
                self.logger.info('SSH连接成功')
            
            return True, 'SSH连接成功'
            
        except paramiko.AuthenticationException as e:
            error_msg = f'SSH认证失败: 用户名或密码错误'
            if self.logger:
                self.logger.error(error_msg)
                self.logger.error(f'详细信息: {str(e)}')
            return False, error_msg
            
        except paramiko.SSHException as e:
            error_msg = f'SSH连接失败: {str(e)}'
            if self.logger:
                self.logger.error(error_msg)
                self.logger.error(f'异常类型: {type(e).__name__}')
            return False, error_msg
            
        except socket.timeout:
            error_msg = f'SSH连接超时: 在{self.timeout}秒内无法建立连接'
            if self.logger:
                self.logger.error(error_msg)
            return False, error_msg
            
        except ConnectionRefusedError as e:
            error_msg = f'连接被拒绝: SSH服务可能未启动或端口{self.port}未开放'
            if self.logger:
                self.logger.error(error_msg)
                self.logger.error(f'详细信息: {str(e)}')
            return False, error_msg
            
        except Exception as e:
            error_msg = f'未知异常: {type(e).__name__} - {str(e)}'
            if self.logger:
                self.logger.error(error_msg)
            return False, error_msg

    def test_ssh_command_execution(self, command: str = 'ls /dev/nvme*') -> Tuple[bool, str, str, str]:
        try:
            if self.logger:
                self.logger.info(f'尝试执行SSH命令: {command}')
            
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_client.connect(
                self.ip,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=self.timeout
            )
            
            stdin, stdout, stderr = ssh_client.exec_command(command, timeout=10)
            exit_status = stdout.channel.recv_exit_status()
            output = stdout.read().decode('utf-8')
            error = stderr.read().decode('utf-8')
            
            ssh_client.close()
            
            if exit_status == 0:
                if self.logger:
                    self.logger.info(f'命令执行成功: {command}')
                    self.logger.info(f'输出: {output[:200]}...' if len(output) > 200 else output)
                return True, '命令执行成功', output
            else:
                error_msg = f'命令执行失败，退出状态: {exit_status}'
                if self.logger:
                    self.logger.error(error_msg)
                    if error:
                        self.logger.error(f'错误输出: {error}')
                return False, error_msg, ''
            
        except paramiko.AuthenticationException as e:
            error_msg = f'SSH认证失败: 用户名或密码错误'
            if self.logger:
                self.logger.error(error_msg)
                self.logger.error(f'详细信息: {str(e)}')
            return False, error_msg, ''
            
        except Exception as e:
            error_msg = f'命令执行异常: {type(e).__name__} - {str(e)}'
            if self.logger:
                self.logger.error(error_msg)
            return False, error_msg, ''

    def run_full_test(self) -> dict:
        results = {
            'ip': self.ip,
            'port': self.port,
            'username': self.username,
            'password': self.password,
            'timeout': self.timeout
        }
        
        if self.logger:
            self.logger.info('=' * 60)
            self.logger.info(f'SSH连接测试开始 - {self.ip}:{self.port}')
            self.logger.info('=' * 60)
        
        port_open, port_msg = self.test_port_open()
        results['port_test'] = {'success': port_open, 'message': port_msg}
        
        if self.logger:
            self.logger.info(f'步骤1: 端口检查 - {port_msg}')
        
        ssh_connected, ssh_msg = self.test_ssh_connection()
        results['ssh_connection'] = {'success': ssh_connected, 'message': ssh_msg}
        
        if self.logger:
            self.logger.info(f'步骤2: SSH连接 - {ssh_msg}')
        
        if ssh_connected:
            cmd_success, cmd_msg, cmd_output = self.test_ssh_command_execution('ls /dev/nvme*')
            results['command_execution'] = {'success': cmd_success, 'message': cmd_msg, 'output': cmd_output}
            
            if self.logger:
                self.logger.info(f'步骤3: 命令执行 - {cmd_msg}')
        
        if self.logger:
            self.logger.info('=' * 60)
            self.logger.info('测试结果汇总:')
            self.logger.info(f'  端口{self.port}: {"开放" if port_open else "关闭"}')
            self.logger.info(f'  SSH连接: {"成功" if ssh_connected else "失败"}')
            self.logger.info(f'  命令执行: {"成功" if cmd_success else "失败"}')
            self.logger.info('=' * 60)
        
        results['overall_success'] = ssh_connected and cmd_success
        
        return results


def test_single_host(ip: str, username: str = 'root', password: str = '1', 
                   port: int = 22, timeout: int = 30, 
                   logger: Optional[ConsoleLogger] = None) -> dict:
    tester = SSHConnectionTester(ip, port, username, password, timeout, logger)
    return tester.run_full_test()


def test_multiple_hosts(hosts_config: list, logger: Optional[ConsoleLogger] = None) -> list:
    results = []
    
    if logger:
        logger.info('=' * 60)
        logger.info(f'开始批量SSH连接测试，共{len(hosts_config)}台主机')
        logger.info('=' * 60)
    
    for i, config in enumerate(hosts_config, 1):
        if logger:
            logger.info(f'\n测试主机 {i}/{len(hosts_config)}: {config.get("name", "unknown")}')
        
        result = test_single_host(
            ip=config.get('ip', 'unknown'),
            username=config.get('username', 'root'),
            password=config.get('password', '1'),
            port=config.get('port', 22),
            timeout=config.get('timeout', 30),
            logger=logger
        )
        results.append(result)
    
    if logger:
        logger.info('=' * 60)
        logger.info('批量测试完成')
        logger.info('=' * 60)
    
    return results


if __name__ == '__main__':
    print('SSH连接测试工具')
    print('=' * 60)
    print()
    print('使用方法:')
    print('  python ssh_test.py --ip <IP地址> --username <用户名> --password <密码>')
    print()
    print('示例:')
    print('  python ssh_test.py --ip 192.168.1.124 --username root --password 1')
    print()
    print('或使用配置文件测试所有主机:')
    print('  python ssh_test.py --config config.ini')
    print('=' * 60)
    ss=SSHConnectionTester('192.168.1.124', 22, 'root', '1', 30)
    ss.run_full_test()
